import csv
import math
from pathlib import Path
import tempfile
import unittest

from japan_housing_liquidity_lab.mlit import inspect_csv
from japan_housing_liquidity_lab.survival import (
    conditional_risk, kaplan_meier, survival_at, synthetic_listings,
)


class SurvivalTests(unittest.TestCase):
    def test_hand_calculated_ties_and_censoring(self):
        curve = kaplan_meier([1, 2, 2, 3], [1, 1, 0, 1])
        self.assertEqual([r["at_risk"] for r in curve], [4, 3, 1])
        self.assertAlmostEqual(survival_at(curve, 1), .75)
        self.assertAlmostEqual(survival_at(curve, 2), .5)
        self.assertAlmostEqual(conditional_risk(curve, 1, 1), 1 / 3)
        self.assertEqual(survival_at(curve, 3), 0)

    def test_all_censored_and_all_events(self):
        self.assertEqual(survival_at(kaplan_meier([1, 2], [0, 0]), 2), 1)
        self.assertEqual(survival_at(kaplan_meier([1, 2], [1, 1]), 2), 0)

    def test_bad_inputs(self):
        for durations, events in [([], []), ([1], []), ([-1], [1]),
                                  ([math.nan], [1]), ([math.inf], [1]), ([1], [2])]:
            with self.assertRaises(ValueError):
                kaplan_meier(durations, events)
        curve = kaplan_meier([1], [1])
        for age, horizon in [(1, 0), (0, 2), (-1, 1), (0, -1)]:
            with self.assertRaises(ValueError):
                conditional_risk(curve, age, horizon)

    def test_synthetic_reproducibility_and_curve_properties(self):
        rows = synthetic_listings()
        self.assertEqual(rows, synthetic_listings())
        self.assertNotEqual(rows, synthetic_listings(seed=1))
        self.assertEqual({r["event_observed"] for r in rows}, {0, 1})
        curve = kaplan_meier([r["duration_days"] for r in rows],
                             [r["event_observed"] for r in rows])
        values = [r["survival"] for r in curve]
        self.assertTrue(all(0 <= v <= 1 for v in values))
        self.assertEqual(values, sorted(values, reverse=True))
        with self.assertRaises(ValueError):
            synthetic_listings(0)


class CsvTests(unittest.TestCase):
    def test_encodings_missing_and_malformed_rows(self):
        for encoding in ("utf-8-sig", "cp932"):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "fixture.csv"
                with path.open("w", encoding=encoding, newline="") as target:
                    csv.writer(target).writerows([
                        ["市区町村名", "取引価格（総額）"], ["架空市", "30000000"],
                        ["架空市", " "], ["bad"],
                    ])
                result = inspect_csv(path)
                self.assertEqual(result["encoding"], encoding)
                self.assertEqual(result["rows"], 3)
                self.assertEqual(result["malformed_rows"], 1)
                self.assertEqual(result["missing_in_valid_rows"]["取引価格（総額）"], 1)
                self.assertEqual(len(result["sha256"]), 64)

    def test_empty_duplicate_and_blank_headers_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            for content in ("", "a,a\n1,2", "a,\n1,2"):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    inspect_csv(path)


if __name__ == "__main__":
    unittest.main()
