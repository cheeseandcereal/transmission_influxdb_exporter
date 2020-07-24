from typing import List, Dict, Optional, Any
import re
import base64
import hashlib
import logging

from transmission import Transmission

from transmission_influxdb import utils

log = logging.getLogger("transmission")

url_domain_regex = re.compile(r"(https?|udp|tcp):\/\/(.*?)\/.*", re.IGNORECASE | re.UNICODE)


class TransmissionClient(object):
    def __init__(self, client_config: Dict[str, Any]) -> None:
        self.name = client_config["name"]
        del client_config["name"]
        self.address = f"{client_config['host']}:{client_config['port']}"
        log.info(f"Connecting to transmission daemon {self.name} at {self.address}")
        self.client = Transmission(**client_config)
        version = self.client.call("session-get", fields=["version"]).get("version")
        log.debug(f"{self.name} connected. Transmission version: {version}")

    def __repr__(self) -> str:
        return f"Transmission({self.name} [{self.address}])"

    def get_daemon_stats(self, time: Optional[str] = None) -> List[Dict[str, Any]]:
        if time is None:
            time = utils.now()
        session = self.client.call("session-get", fields=["download-dir", "version"])
        version = session.get("version")
        free_space = self.client.call("free-space", path=session.get("download-dir")).get("size-bytes")
        stats = self.client.call("session-stats")
        return [
            {
                "measurement": "stats",
                "time": time,
                "tags": {"client_name": self.name, "version": version},
                "fields": {
                    "free_space": free_space,
                    "downloaded": stats.get("cumulative-stats").get("downloadedBytes"),
                    "uploaded": stats.get("cumulative-stats").get("uploadedBytes"),
                    "active_torrents": stats.get("activeTorrentCount"),
                    "paused_torrents": stats.get("pausedTorrentCount"),
                    "download_speed": stats.get("downloadSpeed"),
                    "upload_speed": stats.get("uploadSpeed"),
                },
            }
        ]

    def get_torrent_stats(self, time: Optional[str] = None) -> List[Dict[str, Any]]:
        if time is None:
            time = utils.now()
        torrents = self.client.call(
            "torrent-get",
            fields=[
                "downloadedEver",
                "error",
                "hashString",
                "id",
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
        points = []
        for torrent in torrents:
            unique_torrent_hash = get_unique_torrent_hash(self.name, torrent.get("id"), torrent.get("hashString"))
            tracker = ""
            # Only keep track of first tracker in any given torrent to not complicate tags
            match = url_domain_regex.match(torrent.get("trackers")[0].get("announce"))
            if match:
                tracker = match.group(2)
            else:
                log.error(f"Torrent {torrent.get('name')} could not parse tracker. Not recording this data point")
                continue
            points.append(
                {
                    "measurement": "torrents",
                    "time": time,
                    "tags": {
                        "client_name": self.name,
                        "infohash": torrent.get("hashString"),
                        "torrent_name": torrent.get("name"),
                        "tracker": tracker,
                        "error": torrent.get("error") != 0,
                        "status": get_status(torrent.get("status")),
                    },
                    "fields": {
                        "downloaded": torrent.get("downloadedEver"),
                        "uploaded": torrent.get("uploadedEver"),
                        "download_speed": torrent.get("rateDownload"),
                        "upload_speed": torrent.get("rateUpload"),
                        "connected_peers": torrent.get("peersConnected"),
                        "percent_done": float(torrent.get("percentDone")),
                        # this field allows us to use distinct("unique_id") when doing influxdb queries against multiple torrents
                        # with ambiguous times between collections (so we don't have to rely on group by fixed time intervals)
                        "unique_id": unique_torrent_hash,
                    },
                }
            )
        return points


def get_unique_torrent_hash(client_name: str, torrent_id: int, infohash: str) -> str:
    """Function for generating a deterministically unique string
    for a torrent based on its client name, torrent id, and infohash"""
    digest_str = f"{client_name}{torrent_id}{infohash}"
    raw_digest = hashlib.blake2b(digest_str.encode("utf8"), digest_size=16).digest()
    return base64.b64encode(raw_digest).decode("ascii").rstrip("=")


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
