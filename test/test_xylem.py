import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import requests

from app.xylem import (
    DATASTREAMS_URL,
    OBSERVATIONS_URL,
    SITES_URL,
    SITES_V2_URL,
    XylemApiError,
    get_datastreams,
    get_observations,
    get_sites,
    get_sites_v2,
)

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


class GetSitesTest(unittest.TestCase):
    def call(self, resp):
        with (
            patch("app.xylem.get_token", return_value="tok"),
            patch("app.xylem.requests.get", return_value=resp) as get,
        ):
            self.get = get
            return get_sites()

    def test_success(self):
        self.assertEqual(self.call(make_response(200, [SITE])), [SITE])
        self.assertEqual(self.get.call_args.args[0], SITES_URL)
        self.assertEqual(
            self.get.call_args.kwargs["headers"], {"Authorization": "bearer tok"}
        )

    def test_success_empty(self):
        self.assertEqual(self.call(make_response(200, [])), [])

    def test_documented_errors(self):
        cases = [
            (400, "BAD_REQUEST_ERROR", "Bad request"),
            (401, "UNAUTHORIZED_ERROR", "Invalid token"),
            (403, "ACCESS_DENIED_ERROR", "Not allowed"),
            (404, "NOT_FOUND_ERROR", "No such resource"),
            (500, "INTERNAL_ERROR", "Server exploded"),
        ]
        for status, code, message in cases:
            with self.subTest(status=status):
                body = {
                    "timestamp": 1677148413293,
                    "errorCode": code,
                    "message": message,
                }
                with self.assertRaises(XylemApiError) as cm:
                    self.call(make_response(status, body))
                self.assertEqual(cm.exception.status_code, status)
                self.assertEqual(cm.exception.error_code, code)
                self.assertEqual(cm.exception.message, message)
                self.assertIn(code, str(cm.exception))

    def test_error_with_plain_text_body(self):
        # The "default" response is a plain string, not an ErrorResponse.
        with self.assertRaises(XylemApiError) as cm:
            self.call(make_response(502, text="Bad Gateway"))
        self.assertEqual(cm.exception.status_code, 502)
        self.assertIsNone(cm.exception.error_code)
        self.assertEqual(cm.exception.message, "Bad Gateway")

    def test_error_with_empty_body(self):
        with self.assertRaises(XylemApiError) as cm:
            self.call(make_response(503, text=""))
        self.assertEqual(cm.exception.message, "reason")

    def test_token_failure_propagates(self):
        with (
            patch("app.xylem.get_token", side_effect=RuntimeError("no creds")),
            patch("app.xylem.requests.get") as get,
            self.assertRaisesRegex(RuntimeError, "no creds"),
        ):
            get_sites()
        get.assert_not_called()

    def test_network_error_propagates(self):
        with (
            patch("app.xylem.get_token", return_value="tok"),
            patch(
                "app.xylem.requests.get",
                side_effect=requests.ConnectionError("offline"),
            ),
            self.assertRaises(requests.ConnectionError),
        ):
            get_sites()


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


class GetSitesV2Test(unittest.TestCase):
    def call(self, responses, **kwargs):
        with (
            patch("app.xylem.get_token", return_value="tok") as token,
            patch("app.xylem.requests.get", side_effect=responses) as get,
        ):
            self.get, self.token = get, token
            return get_sites_v2(**kwargs)

    def sent_params(self):
        return [c.kwargs["params"] for c in self.get.call_args_list]

    def test_multiple_pages(self):
        a, b, c = ({**SITE, "id": i} for i in "abc")
        result = self.call([page([a, b], 0, 2), page([c], 1, 2)], page_size=2)
        self.assertEqual(result, [a, b, c])
        self.assertEqual(
            self.sent_params(), [{"page": 0, "size": 2}, {"page": 1, "size": 2}]
        )
        self.assertEqual(self.get.call_args.args[0], SITES_V2_URL)
        self.assertEqual(
            self.get.call_args.kwargs["headers"], {"Authorization": "bearer tok"}
        )
        self.token.assert_called_once()  # one token for all pages

    def test_single_page(self):
        self.assertEqual(self.call([page([SITE], 0, 1)]), [SITE])
        self.assertEqual(len(self.sent_params()), 1)

    def test_empty(self):
        self.assertEqual(self.call([page([], 0, 0)]), [])
        self.assertEqual(len(self.sent_params()), 1)

    def test_null_total_pages_stops_on_short_page(self):
        result = self.call(
            [page([SITE, SITE], 0, None), page([SITE], 1, None)], page_size=2
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(len(self.sent_params()), 2)

    def test_max_records_truncates_and_limits_page_size(self):
        a, b = ({**SITE, "id": i} for i in "ab")
        result = self.call([page([a, b], 0, 5)], page_size=500, max_records=2)
        self.assertEqual(result, [a, b])
        self.assertEqual(self.sent_params(), [{"page": 0, "size": 2}])

    def test_max_records_truncates_single_page(self):
        sites = [{**SITE, "id": i} for i in "abc"]
        self.assertEqual(
            self.call([page(sites, 0, 1)], page_size=3, max_records=2), sites[:2]
        )

    def test_max_records_spans_pages(self):
        sites = [{**SITE, "id": i} for i in "abcde"]
        result = self.call(
            [page(sites[:2], 0, 3), page(sites[2:4], 1, 3)], page_size=2, max_records=3
        )
        self.assertEqual(result, sites[:3])
        self.assertEqual(len(self.sent_params()), 2)

    def test_max_records_larger_than_total(self):
        self.assertEqual(self.call([page([SITE], 0, 1)], max_records=10), [SITE])

    def test_error_on_later_page(self):
        body = {"timestamp": 1, "errorCode": "INTERNAL_ERROR", "message": "boom"}
        with self.assertRaises(XylemApiError) as cm:
            self.call([page([SITE, SITE], 0, 2), make_response(500, body)], page_size=2)
        self.assertEqual(cm.exception.status_code, 500)


DATASTREAM = {
    "id": "ds-id-1270137",
    "name": "Battery",
    "description": "Battery voltage",
    "parameterReference": "00:1A:2B:3C:4D:5E/battery",
    "unitOfMeasurement": {"name": "volt"},
}


class GetDatastreamsTest(unittest.TestCase):
    def call(self, resp, site_id="site1"):
        with patch("app.xylem.get_token", return_value="tok"), patch(
            "app.xylem.requests.get", return_value=resp
        ) as get:
            self.get = get
            return get_datastreams(site_id)

    def test_success(self):
        self.assertEqual(self.call(make_response(200, [DATASTREAM])), [DATASTREAM])
        self.assertEqual(
            self.get.call_args.args[0], DATASTREAMS_URL.format(site_id="site1")
        )
        self.assertEqual(
            self.get.call_args.kwargs["headers"], {"Authorization": "bearer tok"}
        )

    def test_empty(self):
        self.assertEqual(self.call(make_response(200, [])), [])

    def test_site_id_is_url_encoded(self):
        self.call(make_response(200, []), site_id="a/b c")
        self.assertEqual(
            self.get.call_args.args[0], DATASTREAMS_URL.format(site_id="a%2Fb%20c")
        )

    def test_documented_errors(self):
        cases = [
            (400, "BAD_REQUEST_ERROR"),
            (401, "UNAUTHORIZED_ERROR"),
            (403, "ACCESS_DENIED_ERROR"),
            (404, "NOT_FOUND_ERROR"),
            (500, "INTERNAL_ERROR"),
        ]
        for status, code in cases:
            with self.subTest(status=status):
                body = {"timestamp": 1, "errorCode": code, "message": "msg"}
                with self.assertRaises(XylemApiError) as cm:
                    self.call(make_response(status, body))
                self.assertEqual(cm.exception.status_code, status)
                self.assertEqual(cm.exception.error_code, code)


START = datetime(2025, 3, 1, tzinfo=timezone.utc)
END = datetime(2025, 3, 2, tzinfo=timezone.utc)
START_MS, END_MS = 1740787200000, 1740873600000
OBS = {"phenomenonTime": 1740790000000, "resultTime": 1740790001000, "value": 23.4}


class GetObservationsTest(unittest.TestCase):
    def call(self, resp, ids=("ds1",)):
        with patch("app.xylem.get_token", return_value="tok"), patch(
            "app.xylem.requests.get", return_value=resp
        ) as get:
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
        self.assertEqual(self.get.call_args.kwargs["params"]["datastreamIds"], "ds1,ds2")

    def test_no_observations_in_range(self):
        self.assertEqual(self.call(make_response(200, {"ds1": []})), {"ds1": []})

    def test_times_are_sent_as_epoch_ms_regardless_of_timezone(self):
        eastern = ZoneInfo("America/New_York")
        start = datetime(2025, 2, 28, 19, 0, tzinfo=eastern)  # == START in UTC
        end = datetime(2025, 3, 1, 19, 0, tzinfo=eastern)  # == END in UTC
        with patch("app.xylem.get_token", return_value="tok"), patch(
            "app.xylem.requests.get", return_value=make_response(200, {})
        ) as get:
            get_observations(["ds1"], start, end)
        params = get.call_args.kwargs["params"]
        self.assertEqual((params["from"], params["until"]), (START_MS, END_MS))

    def test_window_of_exactly_14_days_is_allowed(self):
        with patch("app.xylem.get_token", return_value="tok"), patch(
            "app.xylem.requests.get", return_value=make_response(200, {})
        ) as get:
            get_observations(["ds1"], START, START + timedelta(days=14))
        get.assert_called_once()

    def test_window_over_14_days_raises_without_calling_api(self):
        end = START + timedelta(days=14, seconds=1)
        with patch("app.xylem.get_token") as token, patch(
            "app.xylem.requests.get"
        ) as get:
            with self.assertRaisesRegex(ValueError, "14-day limit"):
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
        with patch("app.xylem.get_token", side_effect=RuntimeError("no creds")), patch(
            "app.xylem.requests.get"
        ) as get:
            with self.assertRaisesRegex(RuntimeError, "no creds"):
                get_observations(["ds1"], START, END)
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
