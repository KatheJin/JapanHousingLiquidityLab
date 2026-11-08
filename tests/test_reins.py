"""Small synthetic tables; no redistributed REINS source observations."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from japan_housing_liquidity_lab.reins import (
    REGIONS, TOKYO_DISTRICTS, WARD_GROUPS, METRICS, analyze, build, months_between,
    parse_table, select_vintage, shift_month,
)


def row(month, value=10, metric="contracts", published="2025-01-14", version="v1"):
    return dict(region="東京都", month=month, metric=metric, value=value,
                published_on=published, source_version=version, printed_yoy_pct=None)


def table(metric="contracts", regions=REGIONS):
    lines = ["中古マンションレポート", METRICS[metric]]
    for region in regions:
        lines.append("○" + region + ("（" + "、".join(WARD_GROUPS[region]) + "）" if region in WARD_GROUPS else ""))
        for month in months_between("2023-12", "2024-12"):
            label = month[2:].replace("-", "/") if month in ("2023-12", "2024-01") else month[5:]
            count = 4000 if region == "首都圏" else 1000
            lines.append(f"{label} {count:,} 0.0 99.99")
    return "\n".join(lines)


class ReinsTests(unittest.TestCase):
    def test_calendar_validation(self):
        self.assertEqual(shift_month("2025-01", -1), "2024-12")
        self.assertEqual(shift_month("2025-01", -12), "2024-01")
        with self.assertRaises(ValueError):
            months_between("2025-13", "2026-01")
        with self.assertRaises(ValueError):
            months_between("2026-01", "2025-12")

    def test_table_count_year_rollover_and_fullwidth(self):
        parsed = parse_table(table().replace("24/01", "２４/０１"), "contracts", "2024-12")
        self.assertEqual(len(parsed), 65)
        self.assertEqual({r["month"] for r in parsed}, set(months_between("2023-12", "2024-12")))
        self.assertEqual(next(r["value"] for r in parsed if r["region"] == "東京都"), 1000)
        self.assertEqual(len(parse_table(table(regions=TOKYO_DISTRICTS), "contracts", "2024-12", TOKYO_DISTRICTS)), 65)

    def test_23_wards_membership_not_prefecture_proxy(self):
        members = [w for group in WARD_GROUPS.values() for w in group]
        self.assertEqual(len(members), 23)
        self.assertEqual(len(set(members)), 23)
        with self.assertRaises(ValueError):
            parse_table(table(regions=TOKYO_DISTRICTS).replace("世田谷区", "架空区"), "contracts", "2024-12", TOKYO_DISTRICTS)

    def test_changed_schema_and_missing_cells_rejected(self):
        for bad in (table().replace("成約状況", "在庫状況"), table().replace("24/01 1,000 0.0 99.99", ""), table().replace("○東京都", "○架空県")):
            with self.assertRaises(ValueError):
                parse_table(bad, "contracts", "2024-12")

    def test_bad_totals_duplicates_and_bad_integer_rejected(self):
        for bad in (table().replace("4,000", "4,001", 1), table() + "\n12 1,000 0.0 99.99", table().replace("4,000", "40,00", 1)):
            with self.assertRaises(ValueError):
                parse_table(bad, "contracts", "2024-12")

    def test_as_of_filters_publication_not_transaction_month(self):
        values = [row("2024-01", published="2025-01-14")]
        self.assertEqual(select_vintage(values, "2024-12-31")[0], [])
        self.assertEqual(len(select_vintage(values, "2025-01-14")[0]), 1)

    def test_revisions_preserve_old_version(self):
        values = [row("2024-01"), row("2024-01", 11, published="2026-01-13", version="v2")]
        selected, revisions, overlaps = select_vintage(values)
        self.assertEqual(selected[0]["value"], 11)
        self.assertEqual(revisions[0]["old_value"], 10)
        self.assertEqual(overlaps, 1)
        self.assertEqual(select_vintage(values, "2025-06-01")[0][0]["value"], 10)
        self.assertEqual(values[0]["value"], 10)

    def test_conflicting_same_date_rejected(self):
        with self.assertRaises(ValueError):
            select_vintage([row("2024-01"), row("2024-01", 11, version="v2")])

    def test_missing_month_not_zero_or_previous_observation(self):
        result = analyze([row("2024-01"), row("2024-03", 20)], "2024-01", "2024-03")
        tokyo = [r for r in result["monthly"] if r["region"] == "東京都"]
        self.assertIsNone(tokyo[1]["contracts"])
        self.assertIsNone(tokyo[2]["contracts_mom_raw_pct"])
        self.assertEqual(result["annual_profiles"], [])

    def test_system_break_raw_vs_comparable(self):
        values = [row("2024-01"), row("2024-12"), row("2025-01", 20), row("2026-01", 30)]
        result = analyze(values, "2025-01", "2026-01")
        tokyo = [r for r in result["monthly"] if r["region"] == "東京都"]
        self.assertEqual(tokyo[0]["contracts_yoy_raw_pct"], 100)
        self.assertIsNone(tokyo[0]["contracts_yoy_comparable_pct"])
        self.assertIsNone(tokyo[0]["contracts_mom_comparable_pct"])
        self.assertEqual(tokyo[-1]["contracts_yoy_comparable_pct"], 50)

    def test_zero_denominator_and_descriptive_ratio(self):
        values = [row("2024-01", 0), row("2024-02", 10), row("2024-02", 30, "inventory")]
        result = analyze(values, "2024-01", "2024-02")
        feb = next(r for r in result["monthly"] if r["region"] == "東京都" and r["month"] == "2024-02")
        self.assertIsNone(feb["contracts_mom_raw_pct"])
        self.assertEqual(feb["inventory_to_contracts_descriptive_ratio"], 3)

    def test_complete_years_only_and_regime_separation(self):
        values = [row(m, int(m[-2:])) for m in months_between("2023-01", "2026-09")]
        result = analyze(values, "2023-01", "2026-09")
        self.assertEqual({p["year"] for p in result["annual_profiles"]}, {2023, 2024, 2025})
        pre = next(p for p in result["seasonality"] if p["regime"] == "pre_2025")
        post = next(p for p in result["seasonality"] if p["regime"] == "post_2025")
        self.assertEqual(pre["complete_years"], 2)
        self.assertEqual(post["evidence"], "single_year_not_seasonality")

    def test_duplicate_vintages_require_selection(self):
        with self.assertRaises(ValueError):
            analyze([row("2024-01"), row("2024-01")], "2024-01", "2024-01")

    def test_existing_artifacts_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):
                build([], Path(temp), "2026-11-08")

    def test_empty_as_of_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "new"
            with patch("japan_housing_liquidity_lab.reins.read_pdf", return_value=([row("2024-01")], {"source_file": "fixture.pdf"})):
                with self.assertRaises(ValueError):
                    build([Path("fixture.pdf")], output, "2026-11-08", as_of="2024-01-01")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
