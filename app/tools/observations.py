#! /usr/bin/env python3

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

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
        help="Start time with naive in UTC, e.g. 2025-01-31T08:00",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        required=True,
        help="End time",
    )
    args = parser.parse_args()
    start_dt = datetime.strptime(args.start_time, "%Y-%m-%dT%H:%M").replace(tzinfo=UTC)
    end_dt = datetime.strptime(args.end_time, "%Y-%m-%dT%H:%M").replace(tzinfo=UTC)

    observations = get_observations(
        datastream_ids=[i for i in (args.datastream_id1, args.datastream_id2) if i],
        start=start_dt,
        end=end_dt,
    )
    print(json.dumps(observations, indent=2))


if __name__ == "__main__":
    get_api_observations()
