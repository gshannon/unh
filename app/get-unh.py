#! /usr/bin/env python3

import argparse
import csv
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.cdmo import get_water_data, to_cdmo_rows
from app.ftp import send_files
from app.util import eastern, readMarkerFile, writeMarkerFile
from app.xylem import (
    EXO_DATA_STREAMS,
    MET_DATA_STREAMS,
    StreamObservations,
    get_observations,
    to_timestamp_rows,
)

MAXIMUM_WINDOW = timedelta(days=10)

# Xylum has data at 46:xx minutes after the hour, so this will include those
END_MINUTE = 47
# After this many minutes past any hour, the complete data for the previous hour should be ready.
DATA_CUTOFF_MINUTES = 35

_module_dir = Path(__file__).parent.parent
_data_dir = _module_dir / "data"


def parse_time(value: str) -> datetime:
    """Parse an ISO datetime; a naive value is taken as US/Eastern."""
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=eastern) if dt.tzinfo is None else dt


def get_window(parser, args) -> tuple[datetime, datetime]:
    """Return (start, end) from --start or --start/--end, validating the combination."""
    if args.end_time and not args.start_time:
        parser.error("--end requires --start")
    if args.start_time and not args.end_time:
        parser.error("--start requires --end")

    auto_mode = False
    if args.start_time:
        start = parse_time(args.start_time)
        end = parse_time(args.end_time) if args.end_time else datetime.now(UTC)
        if start >= end:
            parser.error("Start time is after end time")
    else:
        auto_mode = True
        # auto mode. Read the last hour read from the marker file

        now = datetime.now(UTC).replace(second=0, microsecond=0)
        # Data for previous hour should be available after a certain number of minutes past the hour.
        # Determine the query end time of the most recent hour that should be available, to minute precision.
        latest_available_end = now.replace(minute=END_MINUTE) - timedelta(
            hours=(1 if now.minute > DATA_CUTOFF_MINUTES else 2)
        )

        marker_hour = readMarkerFile()
        if marker_hour is not None:
            # if args.verbose:
            print(f"  Using marker file: {marker_hour}")
            start = marker_hour + timedelta(hours=1)
            end = latest_available_end
            if start >= end:
                raise Exception(f"Data for {start} should not be available yet")  # noQA
        else:
            # There's no marker file, so just try to get the previous hour's data.
            start = latest_available_end.replace(minute=0)
            end = latest_available_end
            print(
                f"  No marker file, defaulting to {start.strftime('%Y-%m-%d %H UTC')}"
            )

    if start >= end:
        parser.error("Nothing to do -- start time is after end time")
    if end - start > MAXIMUM_WINDOW:
        parser.error(f"window exceeds the {MAXIMUM_WINDOW.days}-day limit")
    return start, end, auto_mode


def build_outfilepath(prefix: str, start: datetime) -> str:
    return _data_dir / f"{prefix}-{start.strftime('%Y%m%d%H%M')}.csv"


def process_params(argv=None):
    parser = argparse.ArgumentParser(
        description="Pull observations for Harpswell and Wells, create csv files and send to target."
    )
    parser.add_argument(
        "-s",
        "--start",
        dest="start_time",
        metavar="START-TIME",
        help="Start time, e.g. 2025-03-01T08:00 (US/Eastern unless an offset is given)",
    )
    parser.add_argument(
        "-e",
        "--end",
        dest="end_time",
        metavar="END-TIME",
        help="End time, same format as --start",
    )
    parser.add_argument(
        "-t",
        "--type",
        required=False,
        choices=["W", "H"],
        dest="type",
        metavar="TYPE",
        help="data type: W=Wells, H=Harpswell (default=both)",
    )
    parser.add_argument("-d", "--dryrun", action="store_true", help="Do not ftp if set")
    parser.add_argument("--strict", action="store_true", help="Fail if missing data")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print extra diagnostics"
    )
    args = parser.parse_args(argv)
    return parser, args


def main(argv=None):

    parser, args = process_params(argv)
    start, end, auto_mode = get_window(parser, args)
    files_to_send = []
    print(
        f"{(datetime.now(UTC)).strftime('%a %b %d %H:%M:%S UTC')} Processing {start} to {end}"
    )

    # Harpswell data from Xylem
    if args.type is None or args.type == "H":
        print("  Pulling Harpswell data...")
        observations: dict[str, list[StreamObservations]] = get_observations(
            list(EXO_DATA_STREAMS) + list(MET_DATA_STREAMS),
            start,
            end,
            strict=args.strict,
        )

        harpswell_filepath = build_outfilepath("harps-exo", start)
        with harpswell_filepath.open("w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(to_timestamp_rows(EXO_DATA_STREAMS, observations))
        files_to_send.append(harpswell_filepath)

        harpswell_filepath = build_outfilepath("harps-met", start)
        with harpswell_filepath.open("w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(to_timestamp_rows(MET_DATA_STREAMS, observations))
        files_to_send.append(harpswell_filepath)

    # Wells data from CDMO
    if args.type is None or args.type == "W":
        print("  Pulling Wells data...")
        water = get_water_data(start, end, args.strict)
        wells_filepath = build_outfilepath("wells", start)
        with wells_filepath.open("w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(to_cdmo_rows(water))
        files_to_send.append(wells_filepath)

    if files_to_send and not args.dryrun:
        send_files(*files_to_send)

    # If we made it this far, we succeeded. Write the marker file if in auto mode.
    if auto_mode and not args.dryrun:
        writeMarkerFile(end)


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception as e:  # noQA
        print(e)
        sys.exit(1)
