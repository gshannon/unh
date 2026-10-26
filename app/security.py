import os

import requests
from dotenv import load_dotenv

load_dotenv()


# Sandbox:
# TOKEN_URL = "https://cloudfront-gc.xylem-cloud.com/xcloud/auth/realms/xcloud/protocol/openid-connect/token"

# Production:
TOKEN_URL = (
    "https://cloud.xylem.com/xcloud/auth/realms/xcloud/protocol/openid-connect/token"
)


def get_token() -> str:
    """Request an OAuth access token using client credentials from the environment.

    Reads API_CLIENT_ID (client_id) and API_CLIENT_SECRET (client_secret), and returns
    the access token as a string. API_TOKEN_URL optionally overrides TOKEN_URL.
    """
    try:
        client_id = os.environ["API_CLIENT_ID"]
        client_secret = os.environ["API_CLIENT_SECRET"]
    except KeyError as e:
        raise RuntimeError(f"Missing environment variable: {e.args[0]}") from None

    resp = requests.post(
        os.environ.get("API_TOKEN_URL", TOKEN_URL),
        headers={"Accept": "application/json"},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]
