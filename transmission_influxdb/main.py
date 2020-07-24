from typing import List
import os
import time
import logging


from transmission_influxdb import utils
from transmission_influxdb import config
from transmission_influxdb import influxdb
from transmission_influxdb import transmission

log = logging.getLogger("main")


def main() -> None:
    transmission_clients: List[transmission.TransmissionClient] = [transmission.TransmissionClient(x) for x in config.get_torrent_client_configs()]
    while True:
        try:
            log.debug("Starting collection(s) from transmission client(s)")
            data_point_time = utils.now()
            data_points = []
            for client in transmission_clients:
                log.debug(f"Gathering from {client.name}")
                daemon_stats = client.get_daemon_stats(data_point_time)
                torrent_stats = client.get_torrent_stats(data_point_time)
                log.info(f"Transmission client {client.name} {len(torrent_stats)} torrents found for recording")
                data_points += daemon_stats + torrent_stats
            log.info(f"Writing {len(data_points)} data points to influxdb")
            influxdb.write_datapoints(data_points)
            log.debug("Completed main loop")
        except Exception:
            log.exception("Unexpected exception in main")

        time.sleep(config.get_wait_time())


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
    main()
