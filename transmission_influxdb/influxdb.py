from typing import List, Dict, Any, cast
import logging

import influxdb

from transmission_influxdb import config

log = logging.getLogger("influxdb")

# Will get created when a method using the client is called
client = cast(influxdb.InfluxDBClient, None)


def _connect_if_necessary() -> None:
    global client
    if not client:
        log.info("Connecting to influxdb")
        db_config = config.get_influxdb_config()
        client = influxdb.InfluxDBClient(**db_config)
        version = client.request("ping", expected_response_code=204).headers["X-Influxdb-Version"]
        log.debug(f"Influxdb version: {version}")
        db_name = db_config["database"]
        if db_name not in [db["name"] for db in client.get_list_database()]:
            log.info(f"Creating database {db_name}")
            client.create_database(db_name)
        if "transmission_exporter_retention" not in [x["name"] for x in client.get_list_retention_policies(database=db_name)]:
            log.info(f"Creating retention policy for {db_name}")
            client.create_retention_policy(
                name="transmission_exporter_retention", duration="INF", replication="1", database=db_name, default=True, shard_duration="1h"
            )


def write_datapoints(data: List[Dict[str, Any]]) -> None:
    _connect_if_necessary()
    client.write_points(data)
