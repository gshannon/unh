import json
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import requests

from app.xylem import OBSERVATIONS_URL, XylemApiError, get_observations

SITE = {
    "description": "sample description",
    "id": "681d7ab9e0d26d769ab147b2",
    "location": [{"latitude": 41.525002, "longitude": -119.866997}],
    "name": "49 MOUNTAIN (49M)",
}


def make_response(status_code, body=None, text=None):
    """Build a real requests.Response so ok/json/text behave as in production."""
    resp = requests.Response()
    resp.status_code = status_code
    resp.reason = "reason"
    if text is None:
        text = json.dumps(body)
    resp._content = text.encode()
    return resp


def page(content, number, total_pages, size=2):
    return make_response(
        200,
        {
            "size": size,
            "number": number,
            "numberOfElements": len(content),
            "totalPages": total_pages,
            "content": content,
        },
    )


DATASTREAM = {
    "id": "ds-id-1270137",
    "name": "Battery",
    "description": "Battery voltage",
    "parameterReference": "00:1A:2B:3C:4D:5E/battery",
    "unitOfMeasurement": {"name": "volt"},
}


START = datetime(2025, 3, 1, tzinfo=UTC)
END = datetime(2025, 3, 2, tzinfo=UTC)
START_MS, END_MS = 1740787200000, 1740873600000
OBS = {"phenomenonTime": 1740790000000, "resultTime": 1740790001000, "value": 23.4}


class GetObservationsTest(unittest.TestCase):
    def call(self, resp, ids=("ds1",)):
        with (
            patch("app.xylem.get_token", return_value="tok"),
            patch("app.xylem.requests.get", return_value=resp) as get,
        ):
            self.get = get
            return get_observations(list(ids), START, END)

    def test_success(self):
        result = self.call(make_response(200, {"ds1": [OBS]}))
        self.assertEqual(result, {"ds1": [OBS]})
        self.assertEqual(self.get.call_args.args[0], OBSERVATIONS_URL)
        self.assertEqual(
            self.get.call_args.kwargs["headers"], {"Authorization": "bearer tok"}
        )
        self.assertEqual(
            self.get.call_args.kwargs["params"],
            {"datastreamIds": "ds1", "from": START_MS, "until": END_MS},
        )

    def test_multiple_datastreams(self):
        body = {"ds1": [OBS], "ds2": []}
        self.assertEqual(self.call(make_response(200, body), ids=("ds1", "ds2")), body)
        self.assertEqual(
            self.get.call_args.kwargs["params"]["datastreamIds"], "ds1,ds2"
        )

    def test_no_observations_in_range(self):
        self.assertEqual(self.call(make_response(200, {"ds1": []})), {"ds1": []})

    def test_times_are_sent_as_epoch_ms_regardless_of_timezone(self):
        eastern = ZoneInfo("America/New_York")
        start = datetime(2025, 2, 28, 19, 0, tzinfo=eastern)  # == START in UTC
        end = datetime(2025, 3, 1, 19, 0, tzinfo=eastern)  # == END in UTC
        with (
            patch("app.xylem.get_token", return_value="tok"),
            patch("app.xylem.requests.get", return_value=make_response(200, {})) as get,
        ):
            get_observations(["ds1"], start, end)
        params = get.call_args.kwargs["params"]
        self.assertEqual((params["from"], params["until"]), (START_MS, END_MS))

    def test_window_of_exactly_14_days_is_allowed(self):
        with (
            patch("app.xylem.get_token", return_value="tok"),
            patch("app.xylem.requests.get", return_value=make_response(200, {})) as get,
        ):
            get_observations(["ds1"], START, START + timedelta(days=14))
        get.assert_called_once()

    def test_window_over_14_days_raises_without_calling_api(self):
        end = START + timedelta(days=14, seconds=1)
        with (
            patch("app.xylem.get_token") as token,
            patch("app.xylem.requests.get") as get,
            self.assertRaisesRegex(ValueError, "14-day limit"),
        ):
            get_observations(["ds1"], START, end)
        token.assert_not_called()
        get.assert_not_called()

    def test_documented_errors(self):
        cases = [
            (400, "BAD_REQUEST_ERROR", "Invalid request"),
            (401, "UNAUTHORIZED_ERROR", "Invalid token"),
            (403, "ACCESS_DENIED_ERROR", "Not allowed"),
            (404, "NOT_FOUND_ERROR", "Datastream not found"),
            (500, "INTERNAL_ERROR", "Server exploded"),
        ]
        for status, code, message in cases:
            with self.subTest(status=status):
                body = {"timestamp": 1, "errorCode": code, "message": message}
                with self.assertRaises(XylemApiError) as cm:
                    self.call(make_response(status, body))
                self.assertEqual(cm.exception.status_code, status)
                self.assertEqual(cm.exception.error_code, code)
                self.assertEqual(cm.exception.message, message)

    def test_token_failure_propagates(self):
        with (
            patch("app.xylem.get_token", side_effect=RuntimeError("no creds")),
            patch("app.xylem.requests.get") as get,
        ):
            with self.assertRaisesRegex(RuntimeError, "no creds"):
                get_observations(["ds1"], START, END)
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
