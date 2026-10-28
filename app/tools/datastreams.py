#! /usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.security import get_token
from app.xylem import _get

# Sandbox url:
# DATASTREAMS_URL = "https://cloudfront-gc.xylem-cloud.com/xcloud/data-export/site/{site_id}/datastreams"
DATASTREAMS_URL = (
    "https://cloud.xylem.com/xcloud/data-export/site/{site_id}/datastreams"
)
CUNDY_HARBOR_ID = "68ae13a5f9101a3a0812f688"


def get_datastreams(site_id: str) -> list[dict]:
    """Fetch the datastreams (sensors) for a site.

    Each datastream has id, name, description, parameterReference and
    unitOfMeasurement. Raises XylemApiError on an error response (404 if the
    site doesn't exist).
    """
    url = DATASTREAMS_URL.format(site_id=quote(site_id, safe=""))
    return _get(url, get_token())


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
