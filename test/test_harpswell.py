import json
import os
from datetime import datetime
from unittest import TestCase

import app.xylem as xy
from app import util

test_data_dir = os.path.dirname(os.path.abspath(__file__)) + "/data"

start = datetime(2026, 10, 30, 10, 0, tzinfo=util.utc)
end = datetime(2026, 10, 30, 10, 47, tzinfo=util.utc)


class HarpswellTest(TestCase):
    def test_mostly_complete(self):
        """Able to process Xylem payload with no data for one stream."""

        test_exo_streams = {
            "2282799": "pH",
            "2282795": "Depth_m",
            "1282790": "Mystery",
            "2282805": "Temp_DegC",
        }
        with open(f"{test_data_dir}/xylem-good.json", "r", encoding="utf-8") as file:
            json_dict = json.load(file)

        normal = xy.normalize_xylem_json(json_dict)

        rows = xy.to_timestamp_rows(list(test_exo_streams.values()), normal)

        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertEqual(len(row), 5)
        for row in rows[1:]:
            self.assertEqual(row[3], util.NAN)
        self.assertEqual(rows[0][1], "pH")
        self.assertEqual(rows[0][2], "Depth_m")
        self.assertEqual(rows[0][3], "Mystery")
        self.assertEqual(rows[0][4], "Temp_DegC")

    def test_missing1(self):
        """Able to process normal Xylem payload."""

        test_exo_streams_2 = {
            "2282799": "pH",
            "2282795": "Depth_m",
            "2282802": "Salinity_PSU",
            "2282803": "Sonde_Battery_Power_V",
            "2282805": "Temp_DegC",
        }

        with open(
            f"{test_data_dir}/xylem-missing-1.json", "r", encoding="utf-8"
        ) as file:
            json_dict = json.load(file)

        normal = xy.normalize_xylem_json(json_dict)

        rows = xy.to_timestamp_rows(list(test_exo_streams_2.values()), normal)

        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertEqual(len(row), 6)
        # Salinity & Sonde params are completely missing.
        for row in rows[1:]:
            self.assertEqual(row[3], util.NAN)
            self.assertEqual(row[4], util.NAN)
        self.assertEqual(rows[0][1], "pH")
        self.assertEqual(rows[0][2], "Depth_m")
        self.assertEqual(rows[0][5], "Temp_DegC")
