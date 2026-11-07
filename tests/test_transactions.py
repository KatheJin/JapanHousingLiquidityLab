import csv
from pathlib import Path
import tempfile
import unittest
from japan_housing_liquidity_lab.transactions import FIELDS, analyze, number
from japan_housing_liquidity_lab.xit001 import request_url, fetch

class TransactionTests(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(number('３０,０００'),30000)
        for value in ('','0','-1','NaN','2000以上','10～20','inf'):
            with self.assertRaises(ValueError): number(value)

    def test_analysis_and_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fixture.csv'
            base=['中古マンション等','東京都','架空区','30000000','50','2023年第1四半期']
            rows=[base,base,base[:3]+['60000000','50','2024年第2四半期'],
                  base[:4]+['0',base[5]],base[:5]+['2022年第1四半期'],['bad']]
            with path.open('w',encoding='cp932',newline='') as target:
                writer=csv.writer(target); writer.writerow(FIELDS); writer.writerows(rows)
            report,clean=analyze(path, '2025Q4')
            self.assertEqual(report['accepted'],3)
            self.assertEqual(sum(report['rejected'].values()),3)
            self.assertEqual(report['overall_jpy_per_m2']['median'],600000)
            self.assertEqual(report['exact_duplicate_rows_flagged'],1)
            self.assertEqual(len(report['missing_quarters']),10)
            self.assertEqual(clean[2]['jpy_per_m2'],1200000)

    def test_schema_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.csv'; path.write_text('a,b\n1,2',encoding='utf-8')
            with self.assertRaises(ValueError): analyze(path)

    def test_api_is_disabled(self):
        self.assertIn('priceClassification=01',request_url(2023,1))
        with self.assertRaises(ValueError): request_url(2023,5)
        with self.assertRaises(NotImplementedError): fetch()
