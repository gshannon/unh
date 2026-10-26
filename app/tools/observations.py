#! /usr/bin/env python3

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from app.util import eastern

sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.xylem import get_observations


def get_api_observations():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--datastream-id1",
        type=str,
        required=True,
        help="Datastream ID to fetch observations for",
    )
    parser.add_argument(
        "--datastream-id2",
        type=str,
        required=False,
        help="Optional second datastream ID to fetch observations for",
    )
    parser.add_argument(
        "--start-time",
        type=str,
        required=True,
        help="Start time (Eastern), e.g. 2025-01-31T08:00",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        required=True,
        help="End time (Eastern), e.g. 2025-01-31T17:00",
    )
    args = parser.parse_args()
    start_dt = datetime.strptime(args.start_time, "%Y-%m-%dT%H:%M").replace(
        tzinfo=eastern
    )
    end_dt = datetime.strptime(args.end_time, "%Y-%m-%dT%H:%M").replace(tzinfo=eastern)

    observations = get_observations(
        datastream_ids=[i for i in (args.datastream_id1, args.datastream_id2) if i],
        start_time=start_dt,
        end_time=end_dt,
    )
    print(json.dumps(observations, indent=2))


if __name__ == "__main__":
    get_api_observations()
