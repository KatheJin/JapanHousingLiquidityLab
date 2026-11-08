"""CLI consumers must receive the interpretation warnings, not just counts."""
import contextlib
import importlib
import io
import json
import unittest
from unittest.mock import patch


class ReinsCliTests(unittest.TestCase):
    def test_cli_preserves_analysis_limitations(self):
        cases = (
            ("reins", ["sample.pdf", "--acquired-on", "2026-11-08", "--output", "unused"],
             dict(start="2023-01", end="2026-09", raw_count_cells=0, selected_count_cells=0, overlapping_cells=0, quality={})),
            ("reins_prices", ["--monthly-output", "cached", "--raw", "local", "--output", "unused"],
             dict(raw_band_cells=0, selected_band_cells=0, quarters=[], overlapping_band_cells=0)),
        )
        warnings = ["Fixed nominal price band migration is not demand change.", "2025 reporting effects remain possible."]
        for name, arguments, result in cases:
            with self.subTest(cli=name):
                module = importlib.import_module("japan_housing_liquidity_lab." + name)
                output = io.StringIO()
                with patch.object(module, "build", return_value=dict(result, limitations=warnings)), patch("sys.argv", [name] + arguments), contextlib.redirect_stdout(output):
                    module.main()
                self.assertEqual(json.loads(output.getvalue())["limitations"], warnings)
