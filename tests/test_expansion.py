import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from japan_housing_liquidity_lab.expansion import import_history

HEADERS=['種類','価格情報区分','市区町村コード','都道府県名','市区町村名','地区名','最寄駅：名称','最寄駅：距離（分）','取引価格（総額）','間取り','面積（㎡）','建築年','建物の構造','用途','今後の利用目的','都市計画','建ぺい率（％）','容積率（％）','取引時期','改装','取引の事情等']


def csv_bytes(year,quarter,wrong=False):
    row=['中古マンション等','不動産取引価格情報','13100','東京都','架空区','架空町','架空駅','10','30000000','１Ｋ','25','2005年','ＲＣ','','','','','','2023年第1四半期' if wrong else f'{year}年第{quarter}四半期','','']
    bounded=row.copy(); bounded[10]='2,000㎡以上'
    stream=io.StringIO(newline=''); w=csv.writer(stream); w.writerow(HEADERS); w.writerows([row,row,bounded])
    return stream.getvalue().encode('cp932')


class ExpansionTests(unittest.TestCase):
    def setup_inputs(self,root,wrong=False):
        downloads=root/'downloads'; downloads.mkdir()
        for y in range(2018,2023):
            for q in range(1,5):
                stem=f'Tokyo_{y}{q}_{y}{q}'
                with zipfile.ZipFile(downloads/(stem+'.zip'),'w') as archive:
                    archive.writestr(stem+'.csv',csv_bytes(y,q,wrong and y==2018 and q==1))
        old=root/'old.csv'
        source=list(csv.DictReader(io.StringIO(csv_bytes(2023,1).decode('cp932'))))[0]
        source.update(source_file='old.csv',source_row=2,quarter='2023Q1',unit_price_jpy_m2=1200000,quality_flags='')
        with old.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(source)); writer.writeheader(); writer.writerow(source)
        return downloads,old

    def test_preserves_duplicates_bounded_area_and_unknown_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); downloads,old=self.setup_inputs(root)
            prior=old.read_bytes()
            result=import_history(downloads,root/'raw',old,root/'out')
            self.assertEqual(result['new_records'],60)
            self.assertEqual(result['total'],61)
            self.assertEqual(result['uncomputable_targets'],20)
            self.assertEqual(result['exact_duplicate_rows_retained'],40)
            self.assertEqual(old.read_bytes(),prior)
            manifest=json.loads((root/'raw/2018Q1/manifest.json').read_text(encoding='utf-8'))
            self.assertIsNone(manifest['publication_date'])
            self.assertEqual(len(manifest['csv_sha256']),64)
            self.assertTrue(result['all_new_schemas_equal'])

    def test_rejects_wrong_quarter(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); downloads,old=self.setup_inputs(root,True)
            with self.assertRaisesRegex(ValueError,'period'):
                import_history(downloads,root/'raw',old,root/'out')

    def test_missing_batches_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaises(ValueError): import_history(root,root/'raw',root/'old',root/'out')
            self.assertFalse((root/'raw').exists())


if __name__=='__main__': unittest.main()
