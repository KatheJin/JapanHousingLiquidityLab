import csv
import tempfile
from pathlib import Path
import unittest
from japan_housing_liquidity_lab.batches import audit_batches
from japan_housing_liquidity_lab.xit001 import pending_quarters, request_url
from japan_housing_liquidity_lab.transactions import FIELDS, analyze

class BatchTests(unittest.TestCase):
    def test_dynamic_release_inventory(self):
        self.assertEqual(pending_quarters(['2023Q1','2026Q2'],['2023Q1']),['2026Q2'])
        self.assertIn('year=2027',request_url(2027,1))
        with self.assertRaises(ValueError): pending_quarters(['2026Q5'],[])

    def test_cross_file_and_latest_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a.csv',Path(tmp)/'b.csv'
            with a.open('w',encoding='utf-8',newline='') as f:
                w=csv.writer(f); w.writerow(['取引時期' if f=='取引時点' else f for f in FIELDS])
                w.writerow(['中古マンション等','東京都','架空区','10000000','20','2026年第2四半期'])
                w.writerow(['中古マンション等','東京都','架空区','10000000','20','2026年第3四半期'])
            b.write_bytes(a.read_bytes())
            audit=audit_batches([a,b])
            self.assertEqual(audit['exact_cross_file_signatures'],2)
            self.assertEqual(len(audit['identical_files']),1)
            result,_=analyze(a,'2026Q2')
            self.assertEqual(result['accepted'],1)
            self.assertNotIn('2026Q3',result['missing_quarters'])
