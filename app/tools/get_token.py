#! /usr/bin/env python3

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.security import get_token


def get_api_token():
    """Request an OAuth access token using client credentials from the environment.

    Reads API_CLIENT_ID (client_id) and API_CLIENT_SECRET (client_secret), and returns
    the access token as a string. API_TOKEN_URL optionally overrides TOKEN_URL.
    """
    print(get_token())


if __name__ == "__main__":
    get_api_token()
