import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase

from app import cdmo, util

test_data_dir = os.path.dirname(os.path.abspath(__file__)) + "/data"

start = datetime(2026, 10, 31, 6, 0, tzinfo=util.utc)
end = datetime(2026, 10, 31, 10, 0, tzinfo=util.utc)


class WellsTest(TestCase):
    def test_complete(self):
        """Able to process normal CDMO payload."""

        xml: bytes = util.read_xml(Path(test_data_dir) / "cdmo-full.xml")
        data: dict[datetime, dict[str, str]] = cdmo.parse_cdmo_xml(start, end, xml)
        self.assertEqual(len(data), 17)
        expected_values = len(cdmo.WATER_PARAMS)
        for values in data.values():
            self.assertEqual(len(values), expected_values)

        self.assertEqual(min(data), start)
        self.assertEqual(max(data), end)

    def test_missing_clevel_warnings(self):
        """Handles warning conditions"""

        xml: bytes = util.read_xml(Path(test_data_dir) / "cdmo-missing-1.xml")
        data: dict[datetime, dict[str, str]] = cdmo.parse_cdmo_xml(start, end, xml)
        self.assertEqual(len(data), 16)  # One was removed
        expected_values = len(cdmo.WATER_PARAMS)
        for values in data.values():
            self.assertEqual(len(values), expected_values)

        self.assertEqual(min(data), start)
        self.assertEqual(max(data), end - timedelta(minutes=15))

        xml: bytes = util.read_xml(Path(test_data_dir) / "cdmo-missing-3.xml")
        data: dict[datetime, dict[str, str]] = cdmo.parse_cdmo_xml(start, end, xml)
        self.assertEqual(len(data), 14)  # 3 were removed
        expected_values = len(cdmo.WATER_PARAMS)
        for values in data.values():
            self.assertEqual(len(values), expected_values)

        self.assertEqual(min(data), start)
        self.assertEqual(max(data), end - timedelta(minutes=45))

    def test_other_missing(self):
        """Handles error conditions"""

        xml: bytes = util.read_xml(Path(test_data_dir) / "cdmo-missing-middle.xml")
        # 09:00 UTC has no cLevel
        missing_time = datetime(2026, 10, 31, 9, 0, tzinfo=util.utc)

        data: dict[datetime, dict[str, str]] = cdmo.parse_cdmo_xml(start, end, xml)

        rows: list[list[str]] = cdmo.to_csv_rows(data)
        for record in rows:
            self.assertEqual(
                len(record), len(cdmo.WATER_PARAMS) + 1
            )  # add 1 for datetime
            if record[0] == missing_time.isoformat():
                self.assertTrue(util.NAN in record)
            else:
                self.assertTrue(util.NAN not in record)

        # With several missing fields, should emit warnings but does not fail
        xml: bytes = util.read_xml(Path(test_data_dir) / "cdmo-missing-many.xml")
        data = cdmo.parse_cdmo_xml(start, end, xml)
        self.assertEqual(len(data), 17)
