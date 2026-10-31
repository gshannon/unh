import argparse
import logging
from datetime import datetime, timedelta

from app import util

logger = logging.getLogger(__name__)


def process_params(argv=None, include_type: bool = False):
    parser = argparse.ArgumentParser(
        description="Pull observations, create csv files and send to target."
    )
    parser.add_argument(
        "-s",
        "--start",
        dest="start_time",
        metavar="START-TIME",
        help="Start time, e.g. 2025-03-01T08:00 (UTC)",
    )
    parser.add_argument(
        "-e",
        "--end",
        dest="end_time",
        metavar="END-TIME",
        help="End time, same format as --start",
    )
    if include_type:
        parser.add_argument(
            "-t",
            "--type",
            metavar="TYPE",
            choices=["E", "M"],
            required=True,
            help="[E]XO or [M]ET",
        )
    parser.add_argument("-d", "--dryrun", action="store_true", help="Do not ftp if set")
    parser.add_argument(
        "--nostrict", action="store_true", help="Do not fail if missing data"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print extra diagnostics"
    )
    parser.add_argument("--noftp", action="store_true", help="Do not ftp results")
    args = parser.parse_args(argv)
    return parser, args


def get_window(
    parser, args, marker_file_dt: datetime, max_window: int
) -> tuple[datetime, datetime]:
    """Return (start, end) from --start or --start/--end, validating the combination."""
    if args.end_time and not args.start_time:
        parser.error("--end requires --start")
    if args.start_time and not args.end_time:
        parser.error("--start requires --end")

    auto_mode = False
    if args.start_time:
        start = util.parse_time(args.start_time)
        end = (
            util.parse_time(args.end_time) if args.end_time else datetime.now(util.utc)
        )
        if start >= end:
            parser.error("Start time is after end time")
    else:
        auto_mode = True
        end = datetime.now(util.utc).replace(second=0, microsecond=0)

        if marker_file_dt is not None:
            start = marker_file_dt + timedelta(minutes=1)
            if start >= end:
                raise util.AppError(
                    f"Last dt is {marker_file_dt}, can't get future data"
                )
        else:
            # There's no marker file, so just try to get the previous hour or 2 of data.
            start = end - timedelta(hours=2)
            logger.warning(
                f"No marker file, defaulting to {start.strftime('%Y-%m-%d %H:%M UTC')}"
            )

    if end - start > max_window:
        parser.error(f"window exceeds the {max_window.days}-day limit")
    return start, end, auto_mode
