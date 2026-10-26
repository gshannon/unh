#! /usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.xylem import get_sites_v2


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
