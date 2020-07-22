from typing import List, Dict, Any, cast
import json

config_cache: Dict[str, Any] = {}


def _load_config_if_necessary() -> None:
    global config_cache
    if not config_cache:
        with open("config.json") as f:
            config_cache = json.load(f)
            # Validate config file
            if not isinstance(config_cache.get("seconds_between_collections"), int):
                raise Exception("seconds_between_collections must exist in config.json and be an integer")

            # Influxdb option validation
            influx_options = cast(Dict[str, Any], config_cache.get("influxdb"))
            if not isinstance(influx_options.get("host_addr"), str):
                raise Exception("host_addr must exist within influxdb in config.json and be a string")
            if not isinstance(influx_options.get("host_port"), int):
                raise Exception("host_port must exist within influxdb in config.json and be an integer")
            if not isinstance(influx_options.get("use_ssl"), bool):
                raise Exception("use_ssl must exist within influxdb in config.json and be a boolean")
            if not isinstance(influx_options.get("verify_ssl"), bool):
                raise Exception("verify_ssl must exist within influxdb in config.json and be a boolean")
            if not isinstance(influx_options.get("database"), str):
                raise Exception("database must exist within influxdb in config.json and be a string")
            if not isinstance(influx_options.get("username"), str):
                raise Exception("username must exist within influxdb in config.json and be a string")
            if not isinstance(influx_options.get("password"), str):
                raise Exception("password must exist within influxdb in config.json and be a string")

            # Transmission client option validation
            transmission_clients = cast(List[Dict[str, Any]], config_cache.get("transmission_clients"))
            if len(transmission_clients) == 0:
                raise Exception("No transmission clients configured!")
            for client in transmission_clients:
                if not isinstance(client.get("rpc_addr"), str):
                    raise Exception("rpc_addr must exist within transmission_clients in config.json and be a string")
                if not isinstance(client.get("rpc_port"), int):
                    raise Exception("rpc_port must exist within transmission_clients in config.json and be an integer")
                if not isinstance(client.get("rpc_path"), str):
                    raise Exception("rpc_path must exist within transmission_clients in config.json and be a string")
                if not isinstance(client.get("rpc_user"), str):
                    raise Exception("rpc_user must exist within transmission_clients in config.json and be a string")
                if not isinstance(client.get("rpc_password"), str):
                    raise Exception("rpc_password must exist within transmission_clients in config.json and be a string")
                if not isinstance(client.get("rpc_verified_tls"), bool):
                    raise Exception("rpc_verified_tls must exist within transmission_clients in config.json and be a boolean")
                if not isinstance(client.get("rpc_timeout"), int):
                    raise Exception("rpc_timeout must exist within transmission_clients in config.json and be an integer")


def get_wait_time() -> int:
    _load_config_if_necessary()
    return config_cache["seconds_between_collections"]


def get_influxdb_config() -> Dict[str, Any]:
    _load_config_if_necessary()
    options = config_cache["influxdb"]
    return {
        "host": options["host_addr"],
        "port": options["host_port"],
        "username": options["username"],
        "password": options["password"],
        "database": options["database"],
        "ssl": options["use_ssl"],
        "verify_ssl": options["verify_ssl"],
    }


def get_torrent_client_configs() -> List[Dict[str, Any]]:
    _load_config_if_necessary()
    clients = config_cache["transmission_clients"]
    return [
        {
            "host": options["rpc_addr"],
            "port": options["rpc_port"],
            "path": options["rpc_path"],
            "username": options["rpc_user"],
            "password": options["rpc_password"],
            "ssl": options["rpc_verified_tls"],
            "timeout": options["rpc_timeout"],
        }
        for options in clients
    ]
