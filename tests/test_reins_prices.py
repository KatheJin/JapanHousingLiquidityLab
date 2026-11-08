import unittest
from japan_housing_liquidity_lab.reins import REGIONS, METRICS
from japan_housing_liquidity_lab.reins_prices import BANDS, parse_bands, reconcile


def fixture(metric="contracts", date_first=True):
    lines = ["首都圏・都県別価格帯別件数", METRICS[metric]]
    for region in REGIONS:
        lines += ["○" + region, "～1,000 ～2,000 ～3,000 ～4,000 ～5,000 ～7,000 ～10,000 10,000"]
        for period in ("2023/10～12", "2024/01～03", "2024/04～06", "2024/07～09", "2024/10～12"):
            if metric == "inventory":
                period = period[:5] + period[-2:] + "末"
            counts = " ".join(["4"] * 8 + ["32"]) if region == "首都圏" else " ".join(["1"] * 8 + ["8"])
            lines += [period + " " + counts] if date_first else [counts, period]
            lines += [" ".join(["(12.5)"] * 8 + ["(100.0)"])]
    return "\n".join(lines)


class PriceBandTests(unittest.TestCase):
    def test_both_pdf_row_orders(self):
        first = parse_bands(fixture(), "contracts", "2024-12")
        self.assertEqual(first, parse_bands(fixture(date_first=False), "contracts", "2024-12"))
        self.assertEqual(len(first), 200)
        self.assertEqual(first[0]["time_basis"], "quarterly_event_count")

    def test_inventory_is_point_in_time(self):
        rows = parse_bands(fixture("inventory"), "inventory", "2024-12")
        self.assertEqual(rows[0]["period_start"], rows[0]["period_end"])
        self.assertEqual(rows[0]["time_basis"], "quarter_end_stock")
        self.assertEqual(rows[0]["price_basis"], "registered_price_not_contract_price")

    def test_stock_flow_period_mismatch(self):
        with self.assertRaises(ValueError):
            parse_bands(fixture().replace("成約状況", "在庫状況"), "inventory", "2024-12")

    def test_totals_percentages_schema_fail_closed(self):
        for bad in (fixture().replace("32", "33", 1), fixture().replace("(12.5)", "(99.0)", 1), fixture().replace("～7,000", "～8,000"), fixture().replace("2024/01～03", "2024/02～03")):
            with self.assertRaises(ValueError):
                parse_bands(bad, "contracts", "2024-12")

    def test_inventory_reconciliation_never_sums_three_months(self):
        base = dict(source_version="v1", region="東京都", metric="inventory")
        bands = [dict(base, period_start="2024-03", period_end="2024-03", total=10)]
        monthly = [dict(base, month=m, value=10) for m in ("2024-01", "2024-02", "2024-03")]
        self.assertEqual(reconcile(bands, monthly)["same_vintage_monthly_checks"], 1)

    def test_flow_reconciliation_requires_matching_vintage(self):
        base = dict(source_version="v1", region="東京都", metric="contracts")
        bands = [dict(base, period_start="2024-01", period_end="2024-03", total=30)]
        monthly = [dict(base, month=m, value=10) for m in ("2024-01", "2024-02", "2024-03")]
        self.assertEqual(reconcile(bands, monthly)["same_vintage_monthly_checks"], 1)
        monthly[0]["source_version"] = "later_revision"
        self.assertEqual(len(reconcile(bands, monthly)["unavailable_monthly_checks"]), 1)
        monthly[0].update(source_version="v1", value=11)
        with self.assertRaises(ValueError):
            reconcile(bands, monthly)


if __name__ == "__main__":
    unittest.main()
