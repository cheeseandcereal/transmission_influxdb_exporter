from typing import List, Dict, Optional, Any
import re
import json
import base64
import hashlib
import logging

from transmission import Transmission

from transmission_influxdb import influxdb
from transmission_influxdb import utils

TRACKER_STAT_STORAGE_KEY = "tracker_storage"

log = logging.getLogger("transmission")

url_domain_regex = re.compile(r"(https?|udp|tcp):\/\/(tracker\.)?(.*?)(:\d+)?\/.*", re.IGNORECASE | re.UNICODE)


class TransmissionClient(object):
    def __init__(self, client_config: Dict[str, Any]) -> None:
        self.name = client_config["name"]
        del client_config["name"]
        self.disable_individual_collection = client_config["disable_individual_collection"]
        del client_config["disable_individual_collection"]
        self.address = f"{client_config['host']}:{client_config['port']}"
        self.client = Transmission(**client_config)
        self.connected = False

    def __repr__(self) -> str:
        return f"Transmission({self.name} [{self.address}])"

    def connect_if_necessary(self) -> None:
        if not self.connected:
            log.info(f"Connecting to transmission daemon {self.name} at {self.address}")
            version = self.client.call("session-get", fields=["version"]).get("version")
            log.debug(f"{self.name} connected. Transmission version: {version}")
            self.connected = True

    def _create_empty_tracker_point(self, time: str, tracker: str) -> Dict[str, Any]:
        return {
            "measurement": "trackers",
            "time": time,
            "tags": {"client_name": self.name, "tracker": tracker},
            "fields": {
                "downloaded": 0,
                "uploaded": 0,
                "download_speed": 0,
                "upload_speed": 0,
                "connected_peers": 0,
                "seeding": 0,
                "downloading": 0,
                "stopped": 0,
                "errored": 0,
            },
        }

    def _get_client_stats_point(self, time: str) -> Dict[str, Any]:
        session = self.client.call("session-get", fields=["download-dir", "version"])
        version = session.get("version")
        free_space = self.client.call("free-space", path=session.get("download-dir")).get("size-bytes")
        stats = self.client.call("session-stats")
        return {
            "measurement": "stats",
            "time": time,
            "tags": {"client_name": self.name, "version": version},
            "fields": {
                "free_space": free_space,
                "downloaded": stats.get("cumulative-stats").get("downloadedBytes"),
                "uploaded": stats.get("cumulative-stats").get("uploadedBytes"),
                "torrents": stats.get("torrentCount"),
                "download_speed": stats.get("downloadSpeed"),
                "upload_speed": stats.get("uploadSpeed"),
                # These counts are iterated when going through torrents below
                "seeding": 0,
                "downloading": 0,
                "errored": 0,
                "stopped": 0,
                "connected_peers": 0,
            },
        }

    def _get_historical_tracker_stats(self) -> Dict[str, Any]:
        tracker_stat_data = influxdb.get_kvp(TRACKER_STAT_STORAGE_KEY)
        if not tracker_stat_data:
            tracker_stat_data = "{}"
        historical_tracker_stats = json.loads(tracker_stat_data)
        if self.name not in historical_tracker_stats:
            historical_tracker_stats[self.name] = {}
        return historical_tracker_stats

    def get_data_points(self, time: Optional[str] = None) -> List[Dict[str, Any]]:
        # TODO: Break this function up so it's not an ugly monolith
        self.connect_if_necessary()
        if time is None:
            time = utils.now()
        stats_point = self._get_client_stats_point(time)
        torrents = self.client.call(
            "torrent-get",
            fields=[
                "addedDate",
                "downloadedEver",
                "error",
                "hashString",
                "name",
                "peersConnected",
                "percentDone",
                "rateDownload",
                "rateUpload",
                "status",
                "trackers",
                "uploadedEver",
            ],
        ).get("torrents")
        historical_tracker_stats = self._get_historical_tracker_stats()
        tracker_points = {}
        points = []
        for torrent in torrents:
            tracker = ""
            # Only keep track of first tracker in any given torrent to not complicate tags
            first_tracker = torrent.get("trackers")[0].get("announce") if torrent.get("trackers") else "" 
            match = url_domain_regex.match(first_tracker)
            if match:
                tracker = match.group(3)
            else:
                log.warning(f"Torrent {torrent.get('name')} could not get tracker. Not recording this data point")
                continue
            if tracker not in tracker_points:
                tracker_points[tracker] = self._create_empty_tracker_point(time, tracker)
            # Append stats for these torrents to their relevant tracker/client points
            if tracker not in historical_tracker_stats[self.name]:
                historical_tracker_stats[self.name][tracker] = {}
            historical_tracker_stats[self.name][tracker][get_unique_torrent_id(torrent.get("hashString"), torrent.get("addedDate"))] = {
                "downloaded": torrent.get("downloadedEver"),
                "uploaded": torrent.get("uploadedEver"),
            }
            status = get_status(torrent.get("status"))
            if status == "downloading":
                stats_point["fields"]["downloading"] += 1
                tracker_points[tracker]["fields"]["downloading"] += 1
            elif status == "seeding":
                stats_point["fields"]["seeding"] += 1
                tracker_points[tracker]["fields"]["seeding"] += 1
            elif status == "stopped":
                stats_point["fields"]["stopped"] += 1
                tracker_points[tracker]["fields"]["stopped"] += 1
            if torrent.get("error") != 0:
                stats_point["fields"]["errored"] += 1
                tracker_points[tracker]["fields"]["errored"] += 1
            tracker_points[tracker]["fields"]["download_speed"] += torrent.get("rateDownload")
            tracker_points[tracker]["fields"]["upload_speed"] += torrent.get("rateUpload")
            tracker_points[tracker]["fields"]["connected_peers"] += torrent.get("peersConnected")
            stats_point["fields"]["connected_peers"] += torrent.get("peersConnected")
            if not self.disable_individual_collection:
                # Create point for this individual torrent
                points.append(
                    {
                        "measurement": "torrents",
                        "time": time,
                        "tags": {
                            "client_name": self.name,
                            "infohash": torrent.get("hashString"),
                            "torrent_name": torrent.get("name"),
                            "tracker": tracker,
                            "error": str(torrent.get("error")),
                            "status": status,
                        },
                        "fields": {
                            "downloaded": torrent.get("downloadedEver"),
                            "uploaded": torrent.get("uploadedEver"),
                            "download_speed": torrent.get("rateDownload"),
                            "upload_speed": torrent.get("rateUpload"),
                            "connected_peers": torrent.get("peersConnected"),
                            "percent_done": float(torrent.get("percentDone")),
                        },
                    }
                )
        influxdb.write_kvp(TRACKER_STAT_STORAGE_KEY, json.dumps(historical_tracker_stats))
        for tracker, tracker_torrent_stats in historical_tracker_stats[self.name].items():
            for _, values in tracker_torrent_stats.items():
                if tracker not in tracker_points:
                    tracker_points[tracker] = self._create_empty_tracker_point(time, tracker)
                tracker_points[tracker]["fields"]["downloaded"] += values["downloaded"]
                tracker_points[tracker]["fields"]["uploaded"] += values["uploaded"]
            points.append(tracker_points[tracker])
        points.append(stats_point)
        return points


def get_status(status_code: int) -> str:
    # https://github.com/transmission/transmission/blob/7e1da2d8fe5c95299414e013aee6cbae3b1e2e65/libtransmission/transmission.h#L1651
    if status_code == 0:
        return "stopped"
    elif status_code <= 2:
        return "checking"
    elif status_code <= 4:
        return "downloading"
    else:
        return "seeding"


def get_unique_torrent_id(infohash: str, add_date: int) -> str:
    """This function creates a unique string based on an instance of a torrent in transmission.
    This takes into account the infohash and added time so we can track the same torrent as separate
    instances if a torrent was removed then re-added. This way we can track their stats separately."""
    hash_data = f"{infohash}{add_date}".encode("ascii")
    hash_digest = hashlib.blake2b(hash_data, digest_size=12).digest()
    # turn the digest bytes back into a string via base64
    return base64.b64encode(hash_digest).decode("ascii")
