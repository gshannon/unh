import os
from typing import Any

from suds.client import Client
from suds.transport import Request
from suds.transport.https import HttpAuthenticated, HttpTransport

CDMO_WSDL = "https://cdmo.baruch.sc.edu/webservices2/requests.cfc?wsdl"
TIMEOUT_SEC = 300


class CustomTransport(HttpAuthenticated):
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        HttpAuthenticated.__init__(self, username=username, password=password)

    def open(self, request: Request) -> Any:
        request.headers["authorization"] = f"Basic {self._basic_auth()}"
        return HttpTransport.open(self, request)

    def _basic_auth(self) -> str:
        import base64

        credentials = f"{self.username}:{self.password}"
        return base64.b64encode(credentials.encode("utf-8")).decode("utf-8")


class SoapClient:
    """Singleton class to hold the suds Client object, since creating it is expensive and seems to cause CDMO to reject the user/password if done on every request. This is a workaround until that issue is resolved."""

    _client = None

    @classmethod
    def get_client(cls) -> Client:
        if cls._client is None:
            user_name = os.environ.get("CDMO_USER", None)
            password = os.environ.get("CDMO_PASSWORD", None)
            transport = (
                CustomTransport(user_name, password) if user_name and password else None
            )
            if transport is not None:
                cls._client = Client(
                    CDMO_WSDL,
                    retxml=True,
                    transport=transport,
                )
            else:
                cls._client = Client(
                    CDMO_WSDL,
                    retxml=True,
                )
            # This is the only way to override the default 90 sec.  Doesn't work in constructor.
            cls._client.set_options(timeout=TIMEOUT_SEC)
        return cls._client
