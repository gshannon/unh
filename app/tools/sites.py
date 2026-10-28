#! /usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.security import get_token
from app.xylem import _get

# Sandbox urls:
# SITES_URL = "https://cloudfront-gc.xylem-cloud.com/xcloud/data-export/sites"
# SITES_V2_URL = "https://cloudfront-gc.xylem-cloud.com/xcloud/data-export/v2/sites"
SITES_URL = "https://cloud.xylem.com/xcloud/data-export/sites"
SITES_V2_URL = "https://cloud.xylem.com/xcloud/data-export/v2/sites"


def get_sites() -> list[dict]:
    """Fetch the list of sites from the Xylem data-export API.

    Raises XylemApiError on an error response. Note this endpoint returns at
    most 1000 sites; use get_sites_v2() for more.
    """
    return _get(SITES_URL, get_token())


def get_sites_v2(page_size: int = 500, max_records: int | None = None) -> list[dict]:
    """Fetch all sites from the paginated /v2/sites endpoint.

    Requests pages of page_size sites until the last page and returns them
    as a single list. If max_records is given, stops once that many sites have
    been fetched and returns at most that many. Raises XylemApiError on an
    error response.
    """
    if max_records is not None:
        page_size = min(page_size, max_records)
    token = get_token()
    sites: list[dict] = []
    page = 0
    while True:
        body = _get(SITES_V2_URL, token, {"page": page, "size": page_size})
        content = body.get("content") or []
        sites.extend(content)
        if max_records is not None and len(sites) >= max_records:
            return sites[:max_records]
        total_pages = body.get("totalPages")
        if total_pages is not None:
            if page + 1 >= total_pages:
                break
        elif len(content) < page_size:  # totalPages is nullable in the spec
            break
        page += 1
    return sites


def get_api_sites():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--max",
        type=int,
        default=5,
        help="Maximum number of sites to print. -1 for all",
    )
    args = parser.parse_args()
    sites = get_sites_v2(max_records=None if args.max == -1 else args.max)
    print(json.dumps(sites, indent=2))


if __name__ == "__main__":
    get_api_sites()
