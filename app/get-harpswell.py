#! /usr/bin/env python3

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import arg_util, ftp, util, xylem

MAXIMUM_WINDOW = timedelta(days=10)

logger = logging.getLogger(__name__)


def main(argv=None):

    # Keep the root logger at INFO so library debug output stays quiet
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s: %(levelname)s %(module)s %(message)s",
    )
    parser, args = arg_util.process_params(argv, include_type=True)
    if args.verbose:
        logging.getLogger("app").setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    job_type = (
        util.JobType.HARPSWELL_EXO if args.type == "E" else util.JobType.HARPSWELL_MET
    )

    last_dt: datetime | None = util.read_marker_file(job_type)

    start, end, auto_mode = arg_util.get_window(parser, args, last_dt, MAXIMUM_WINDOW)
    logger.info(
        f"Processing {start} to {end}, auto_mode={auto_mode}, type={job_type.value}"
    )

    # Pull the data from the API
    streams: dict[str, str] = (
        xylem.EXO_DATA_STREAMS
        if job_type == util.JobType.HARPSWELL_EXO
        else xylem.MET_DATA_STREAMS
    )
    observations: dict[str, list[xylem.StreamObservations]] = xylem.get_observations(
        start, end, list(streams)
    )

    if len(observations) == 0:
        logger.warning(f"No {job_type.value} data returned")
    else:
        # Convert to CSV format
        csv_data = xylem.to_timestamp_rows(list(streams.values()), observations)
        if len(csv_data) < 2:
            raise util.AppError("No csv data!")
        # Write the csv file to disk
        data_filepath = util.build_outfilepath(
            job_type, datetime.fromisoformat(csv_data[1][0])
        )
        util.write_data_file(data_filepath, csv_data)
        logger.info(
            f"Wrote {len(csv_data) - 1} records to {os.path.basename(data_filepath)}"
        )
        # Ftp the file
        if not args.dryrun and not args.noftp:
            ftp.send_file(data_filepath)
        else:
            logger.debug(f"Not sending ftp file, dryrun={args.dryrun}")

        # If we made it this far, we succeeded. Write the marker file if in auto mode.
        if auto_mode and not args.dryrun:
            util.write_marker_file(job_type, csv_data[-1][0])
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
