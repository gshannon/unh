#! /usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.xylem import CUNDY_HARBOR_ID, get_datastreams


def get_api_data_streams():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--site-id",
        type=str,
        default=CUNDY_HARBOR_ID,
        help="Site ID to fetch data streams for",
    )
    args = parser.parse_args()
    data_streams = get_datastreams(site_id=args.site_id)
    print(json.dumps(data_streams, indent=2))


if __name__ == "__main__":
    get_api_data_streams()
