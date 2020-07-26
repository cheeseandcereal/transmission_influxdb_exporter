from typing import List, Dict, Any, cast
import logging

import influxdb

from transmission_influxdb import config

log = logging.getLogger("influxdb")

key_value_cache: Dict[str, Any] = {}

# Will get created when a method using the client is called
client = cast(influxdb.InfluxDBClient, None)


def _connect_if_necessary() -> None:
    global client
    if not client:
        log.info("Connecting to influxdb")
        db_config = config.get_influxdb_config()
        client = influxdb.InfluxDBClient(**db_config)
        version = client.ping()
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


# The following functions are a very hacky way to do (locally) write-through cached
# key-value storage in influxdb. This exists because I'm too stubborn to add a second
# persistent storage mechanism requirement to this application, especially since it would
# complicate backups to do so.
#
# This was done so that a persistent storage mechanism besides influxdb does not have
# to be used for very simple key-value storage needs
#
# The 'key' is represented in influxdb as a measurement name. Upon writing new data, it
# will delete the entire measurement, then write a new point with a single field 'data'
# containing the value for the key-value pair. DON'T use a key which is the measurement
# name for other data or this will result in permanent data loss.
#
# Note: This writing is not atomic, so a db failure between the delete and write operation
# could result in data-loss. (Yes, I know this is a hacky solution; don't use this with serious data)
#
# Retrieval can be done by simply grabbing the 'data' field from the last point in the
# measurement named with the 'key' from an influxdb query if it is not already locally cached

def write_kvp(key: str, data: str) -> None:
    # First write-through to cache
    key_value_cache[key] = data
    _connect_if_necessary()
    client.drop_measurement(key)
    client.write_points([{'measurement': key, 'tags': {}, 'fields': {'data': data}}])

def get_kvp(key: str) -> str:
    if key in key_value_cache:
        return key_value_cache[key]
    # Not cached, retrieve data from influxdb
    _connect_if_necessary()
    influx_points = list(client.query(f'select last("data") from "{key}";').get_points())
    if not influx_points:
        return ''
    data = influx_points[0]["last"]
    key_value_cache[key] = data
    return data
