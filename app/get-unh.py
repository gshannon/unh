#! /usr/bin/env python3

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import cdmo, ftp, util, xylem

MAXIMUM_WINDOW = timedelta(days=10)

# Xylum has data at 46:xx minutes after the hour, so this will include those
END_MINUTE = 47
# After this many minutes past any hour, the complete data for the previous hour should be ready.
DATA_CUTOFF_MINUTES = 35

logger = logging.getLogger(__name__)
_module_dir = Path(__file__).parent.parent
_data_dir = _module_dir / "data"


def get_window(parser, args) -> tuple[datetime, datetime]:
    """Return (start, end) from --start or --start/--end, validating the combination."""
    if args.end_time and not args.start_time:
        parser.error("--end requires --start")
    if args.start_time and not args.end_time:
        parser.error("--start requires --end")

    auto_mode = True  # Read the last hour read from the marker file
    if args.start_time:
        start = util.parse_time(args.start_time)
        end = util.parse_time(args.end_time) if args.end_time else datetime.now(UTC)
        if start >= end:
            parser.error("Start time is after end time")
        auto_mode = False
    else:
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        # Data for previous hour should be available after a certain number of minutes past the hour.
        # If the current time is before that, the latest available will be the previous hour.
        # Determine the query end time of the most recent hour that should be available, to minute precision.
        latest_available_end = now.replace(minute=END_MINUTE) - timedelta(
            hours=(1 if now.minute > DATA_CUTOFF_MINUTES else 2)
        )
        logger.debug(f"latest available should be {latest_available_end}")

        marker_hour = util.read_marker_file()
        if marker_hour is not None:
            # if args.verbose:
            logger.debug(f"Last hour from marker file: {marker_hour}")
            start = marker_hour + timedelta(hours=1)
            end = latest_available_end
            if start >= end:
                raise util.AppError(f"Data for {start} should not be available yet")
        else:
            # There's no marker file, so just try to get the previous hour's data.
            start = latest_available_end.replace(minute=0)
            end = latest_available_end
            logger.warning(
                f"No marker file, defaulting to {start.strftime('%Y-%m-%d %H UTC')}"
            )

    if start >= end:
        parser.error("Nothing to do -- start time is after end time")
    if end - start > MAXIMUM_WINDOW:
        parser.error(f"window exceeds the {MAXIMUM_WINDOW.days}-day limit")
    return start, end, auto_mode


def build_outfilepath(prefix: str, start: datetime) -> str:
    as_utc = start.astimezone(util.utc)
    return _data_dir / f"{prefix}-{as_utc.strftime('%Y%m%d%H%M')}.csv"


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
    parser.add_argument(
        "--nostrict", action="store_true", help="Do not fail if missing data"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print extra diagnostics"
    )
    args = parser.parse_args(argv)
    return parser, args


def main(argv=None):

    parser, args = process_params(argv)
    # Keep the root logger at INFO so library debug output stays quiet;
    # only this project's loggers ("app.*" and __main__) go to DEBUG with -v.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s: %(levelname)s %(module)s %(message)s",
    )
    if args.verbose:
        logging.getLogger("app").setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    start, end, auto_mode = get_window(parser, args)
    files_to_send = []
    logger.info(
        f"Processing {start} to {end}, auto_mode={auto_mode}, nostrict={args.nostrict}"
    )

    # Harpswell data from Xylem
    if args.type is None or args.type == "H":
        logger.info("Pulling Harpswell data...")
        observations: dict[str, list[xylem.StreamObservations]] = (
            xylem.get_observations(
                list(xylem.EXO_DATA_STREAMS) + list(xylem.MET_DATA_STREAMS),
                start,
                end,
                strict=not args.nostrict,
            )
        )

        loop_hour = util.Hour(start.date(), start.hour, start.tzinfo)
        while loop_hour.as_datetime() < end:
            _start = loop_hour.as_datetime()
            _end = _start.replace(minute=END_MINUTE)

            data_filepath = build_outfilepath("harps-exo", _start)
            csv_data = xylem.to_timestamp_rows(
                xylem.EXO_DATA_STREAMS, observations, _start, _end
            )
            util.write_data_file(data_filepath, csv_data)
            files_to_send.append(data_filepath)

            data_filepath = build_outfilepath("harps-met", _start)
            csv_data = xylem.to_timestamp_rows(
                xylem.MET_DATA_STREAMS, observations, _start, _end
            )
            util.write_data_file(data_filepath, csv_data)
            files_to_send.append(data_filepath)

            loop_hour = loop_hour.next()

    # Wells data from CDMO
    if args.type is None or args.type == "W":
        logger.info("Pulling Wells data...")
        water = cdmo.get_water_data(start, end, not args.nostrict)

        loop_hour = util.Hour(start.date(), start.hour, start.tzinfo)
        while loop_hour.as_datetime() < end:
            _start = loop_hour.as_datetime()
            _end = _start.replace(minute=END_MINUTE)

            data_filepath = build_outfilepath("wells", _start)
            csv_data = cdmo.to_cdmo_rows(water, _start, _end)
            util.write_data_file(data_filepath, csv_data)
            files_to_send.append(data_filepath)
            loop_hour = loop_hour.next()

    if files_to_send and not args.dryrun:
        ftp.send_files(*files_to_send)
    else:
        logger.debug(
            f"Not sending {len(files_to_send)} ftp files, dryrun={args.dryrun}, files_to_send={len(files_to_send)}"
        )

    # If we made it this far, we succeeded. Write the marker file if in auto mode.
    if auto_mode and not args.dryrun:
        util.write_marker_file(end)
    else:
        logger.info(
            f"Not writing marker file, auto_mode={auto_mode} dryrun={args.dryrun}"
        )


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except util.AppError as e:
        logger.error(e)
        sys.exit(0)
