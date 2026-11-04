import csv
import json
import logging
import os
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
utc = ZoneInfo("UTC")

# Note:
# EXO comes in at 01:04 past the 15-min.
# MET comes in at 00:04 past the 15-min.


class JobType(Enum):
    WELLS = "wells"
    HARPSWELL_EXO = "harpsexo"
    HARPSWELL_MET = "harpsmet"


NAN = "NaN"

_root_dir = Path(__file__).parent.parent


class AppError(Exception):
    """Raised for custom error scenarios."""


def assure_utc(dt: datetime) -> None:
    if dt.dst() is not None and dt.dst() != timedelta(0):
        raise RuntimeError()


def build_outfilepath(job_type: JobType, dt: datetime) -> Path:
    return _root_dir / "data" / f"{job_type.value}-{dt.strftime('%Y%m%d-%H%M')}.csv"


def parse_time(value: str) -> datetime:
    """Parse an ISO datetime; a naive value is taken as UTC."""
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=utc) if dt.tzinfo is None else dt


def is_dst(dt: datetime) -> bool:
    """Returns whether the given datetime is in DST."""
    dst = dt.dst()
    return dst is not None and dst > timedelta(hours=0)


def write_marker_file(job_type: JobType, iso: str) -> None:
    filename = f".last-{job_type.value}"
    filepath = Path(_root_dir) / filename
    logger.debug(f"writing to marker file: {iso}")
    with filepath.open("w") as file:
        file.write(iso)


def read_marker_file(job_type: JobType) -> datetime:
    filename = f".last-{job_type.value}"
    filepath = Path(f"{_root_dir / filename}")
    if filepath.is_file():
        with filepath.open("r") as f:
            iso_string = f.read().strip()
        logger.debug(f"Marker file contents: {iso_string}")
        return datetime.fromisoformat(iso_string).replace(second=0, microsecond=0)
    else:
        return None


def write_data_file(filepath: Path, data: list[list[str]]) -> None:
    logger.debug(f"Writing {len(data)} lines to {filepath}")
    with filepath.open("w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(data)


def dump_json(file_path: Path, json_content: dict) -> None:
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(json_content, file, indent=4)


def dump_xml(file_path: Path, xml: bytes) -> None:
    decoded = bytes.fromhex(xml.hex()).decode("ASCII")
    with open(file_path, "w") as file:
        file.write(decoded)


def read_xml(file_path: Path) -> bytes:
    with file_path.open("r") as f:
        s = f.read()
        return bytes(s, "utf-8")


def delete_old_files(prefix: str, age: timedelta) -> None:
    """Delete csv files starting with a prefix and whose last modification is older than `age`."""
    directory = _root_dir / "data"
    cutoff = datetime.now(utc) - age
    for path in sorted(directory.rglob(f"{prefix}*.csv")):
        modified = datetime.fromtimestamp(path.stat().st_mtime, utc)
        if modified < cutoff:
            logger.debug(f"deleting, older than {age}: {os.path.basename(path)}")
            path.unlink()
        else:
            logger.debug(f"kept, not older than {age}: {os.path.basename(path)}")
