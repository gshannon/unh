from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

utc = ZoneInfo("UTC")
eastern = ZoneInfo("US/Eastern")

MARKER_FILE = ".lastend"
_module_dir = Path(__file__).parent
_marker_file_path = _module_dir / MARKER_FILE


def epoch_to_datetime(epoch_time_ms: int, tzinfo=utc) -> datetime:
    """
    Convert epoch time with milliseconds to local datetime in the specified timezone.
    Milliseconds are expected, but will be ignored.

    :param epoch_time_ms: Epoch time (milliseconds since Jan 1, 1970)
    :param tzinfo: Timezone information (default is UTC)
    :return: Local datetime object
    """
    if tzinfo is None:
        raise ValueError("tzinfo must be provided and cannot be None")

    if not isinstance(epoch_time_ms, int):
        raise TypeError(
            "epoch_time_ms must be an integer representing milliseconds since Jan 1, 1970"
        )

    utc_dt = datetime.fromtimestamp(epoch_time_ms / 1000, tz=utc)
    if tzinfo == utc:
        return utc_dt

    return utc_dt.astimezone(tzinfo)


datetime_to_epoch_ms = lambda dt: int(dt.timestamp() * 1000)


def isDst(dt: datetime) -> bool:
    """Returns whether the given datetime is in DST."""
    dst = dt.dst()
    return dst is not None and dst > timedelta(hours=0)


def writeMarkerFile(dt: datetime) -> None:
    with _marker_file_path.open("w") as file:
        last_hour = dt.replace(minute=0, second=0, microsecond=0)
        print(last_hour)
        file.write(last_hour.isoformat())


def readMarkerFile() -> datetime:
    if _marker_file_path.is_file():
        with _marker_file_path.open("r") as f:
            iso_string = f.read().strip()
        return datetime.fromisoformat(iso_string).replace(
            minute=0, second=0, microsecond=0
        )
    else:
        return None
