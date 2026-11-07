import csv
import tempfile
from pathlib import Path
import unittest
from japan_housing_liquidity_lab.history import build, FEATURES

class HistoricalTests(unittest.TestCase):
    def fixture(self,root,period='2023年第1四半期'):
        folder=root/'2023Q1'; folder.mkdir()
        path=folder/'sample.csv'
        headers=['種類','価格情報区分','都道府県名']+FEATURES
        base=['中古マンション等','不動産取引価格情報','東京都','架空区','架空町','駅','30分～60分','50','2000年','2LDK','RC','30000000',period]
        invalid=base.copy(); invalid[7]='0'
        other=base.copy(); other[1]='成約価格情報'
        with path.open('w',encoding='cp932',newline='') as f:
            w=csv.writer(f); w.writerow(headers); w.writerows([base,invalid,other])
        path.with_suffix('.zip').write_bytes(b'fixture archive for hashing')

    def test_retention_scope_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'raw'; root.mkdir(); self.fixture(root)
            out=Path(tmp)/'out'; result=build(root,out,'2023Q2')
            self.assertEqual(result['total_target'],2)
            self.assertEqual(result['quarterly'][0]['n'],1)
            self.assertEqual(result['missing'],['2023Q2'])
            with (out/'merged_retained.csv').open(encoding='utf-8-sig') as source:
                rows=list(csv.DictReader(source))
            self.assertEqual(len(rows),2)
            self.assertIn('invalid',rows[1]['quality_flags'])
            self.assertEqual(rows[0]['最寄駅：距離（分）'],'30分～60分')
            with self.assertRaises(FileExistsError): build(root,out,'2023Q2')

    def test_wrong_period_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'raw'; root.mkdir(); self.fixture(root,'2024年第1四半期')
            with self.assertRaises(ValueError): build(root,Path(tmp)/'out')
