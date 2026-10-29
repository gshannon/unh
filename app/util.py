import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
utc = ZoneInfo("UTC")
eastern = ZoneInfo("America/New_York")

MARKER_FILE = ".lastend"
_module_dir = Path(__file__).parent
_marker_file_path = _module_dir / MARKER_FILE


class ExpectedError(Exception):
    """Raised for custom error scenarios."""


def is_dst(dt: datetime) -> bool:
    """Returns whether the given datetime is in DST."""
    dst = dt.dst()
    return dst is not None and dst > timedelta(hours=0)


def write_marker_file(dt: datetime) -> None:
    logger.debug(f"writing to marker file: {dt}")
    with _marker_file_path.open("w") as file:
        last_hour = dt.replace(minute=0, second=0, microsecond=0)
        file.write(last_hour.isoformat())


def read_marker_file() -> datetime:
    if _marker_file_path.is_file():
        with _marker_file_path.open("r") as f:
            iso_string = f.read().strip()
        return datetime.fromisoformat(iso_string).replace(
            minute=0, second=0, microsecond=0
        )
    else:
        return None


def write_data_file(filepath: Path, data: list[list[str]]) -> None:
    logger.debug(f"Writing {len(data)} lines to {filepath}")
    with filepath.open("w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(data)
