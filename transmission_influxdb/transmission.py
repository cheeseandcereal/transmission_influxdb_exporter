from typing import Dict, Any
import logging

from transmission import Transmission

log = logging.getLogger("transmission")


class TransmissionClient(object):
    def __init__(self, client_config: Dict[str, Any]) -> None:
        self.name = f"{client_config['host']}:{client_config['port']}"
        log.info(f"Connecting to transmission daemon {self.name}")
        self.client = Transmission(**client_config)

    def __repr__(self) -> str:
        return f"Transmission({self.name})"
