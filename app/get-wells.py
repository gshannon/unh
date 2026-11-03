#! /usr/bin/env python3

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import arg_util, cdmo, ftp, util

MAXIMUM_WINDOW = timedelta(days=10)

logger = logging.getLogger(__name__)


def main(argv=None):

    # Keep the root logger at INFO so library debug output stays quiet;
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s: %(levelname)s %(module)s %(message)s",
    )
    parser, args = arg_util.process_params(argv)
    if args.verbose:
        logging.getLogger("app").setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    last_dt = util.read_marker_file(util.JobType.WELLS)

    start, end, auto_mode = arg_util.get_window(parser, args, last_dt, MAXIMUM_WINDOW)
    logger.info(f"Processing {start} to {end}, auto_mode={auto_mode}")

    water: dict[datetime, dict[str, str]] = cdmo.get_water_data(start, end)

    if len(water) == 0:
        logger.warning("No CDMO data returned")
    else:
        csv_data = cdmo.to_cdmo_rows(water)
        if len(csv_data) < 2:
            raise util.AppError("No csv data!")
        data_filepath = util.build_outfilepath(
            util.JobType.WELLS, datetime.fromisoformat(csv_data[1][0])
        )
        util.write_data_file(data_filepath, csv_data)
        logger.info(
            f"Wrote {len(csv_data) - 1} records to {os.path.basename(data_filepath)}"
        )

        if not args.dryrun and not args.noftp:
            ftp.send_file(data_filepath)
        else:
            logger.debug(
                f"Not sending {data_filepath}, dryrun={args.dryrun}, noftp={args.noftp}"
            )

        # If we made it this far, we succeeded. Write the marker file if in auto mode.
        if auto_mode and not args.dryrun:
            util.write_marker_file(util.JobType.WELLS, csv_data[-1][0])
        else:
            logger.info(
                f"Not writing marker file, auto_mode={auto_mode} dryrun={args.dryrun}"
            )
    # deleted = ftp.clean_files(1)
    # logger.info(f"DELETED {deleted} ftp files")


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except util.AppError as e:
        logger.error(e)
        sys.exit(0)
