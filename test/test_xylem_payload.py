import json
import os
from datetime import datetime
from unittest import TestCase

import app.xylem as xy
from app import util

test_data_dir = os.path.dirname(os.path.abspath(__file__)) + "/data"

start = datetime(2026, 10, 30, 10, 0, tzinfo=util.utc)
end = datetime(2026, 10, 30, 10, 47, tzinfo=util.utc)


class TestXylemData(TestCase):
    def test_complete(self):
        """Able to process normal Xylem payload."""

        with open(f"{test_data_dir}/complete.json", "r", encoding="utf-8") as file:
            json_dict = json.load(file)

        normal = xy.normalize_xylem_json(json_dict)

        self.assertTrue(xy.is_valid_content(normal))

        rows = xy.to_timestamp_rows(
            list(xy.EXO_DATA_STREAMS.values()), normal, start, end
        )

        self.assertEqual(len(rows), 5)

    def test_missing1(self):
        """Able to process normal Xylem payload."""

        with open(f"{test_data_dir}/missing1.json", "r", encoding="utf-8") as file:
            json_dict = json.load(file)

        normal = xy.normalize_xylem_json(json_dict)

        self.assertFalse(xy.is_valid_content(normal))
        # rows = xy.to_timestamp_rows(
        #     list(xy.EXO_DATA_STREAMS.values()), normal, start, end
        # )
        # self.assertEqual(len(rows), 5)
