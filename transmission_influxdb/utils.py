import datetime


def now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
