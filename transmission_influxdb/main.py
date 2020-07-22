import os
import time
import logging

from transmission_influxdb import config

log = logging.getLogger("main")


def main() -> None:
    while True:
        log.debug("Starting connection(s) to transmission client(s)")
        pass
        log.debug("Completed main loop")
        time.sleep(config.get_wait_time())


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
    try:
        main()
    except Exception:
        log.exception("Unexpected exception in main")
