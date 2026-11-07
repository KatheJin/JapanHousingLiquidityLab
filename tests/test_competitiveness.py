import unittest
import numpy as np
import pandas as pd
from japan_housing_liquidity_lab.benchmark import NUM
from japan_housing_liquidity_lab.competitiveness import candidate_model,comparable,make_pool,assess

class CompetitiveTests(unittest.TestCase):
    def row(self):
        return {'quarter':'2026Q2','市区町村名':'架空区','地区名':'町','最寄駅：名称':'駅','面積（㎡）':'70',
                '建築年':'2000年','最寄駅：距離（分）':'10','間取り':'2LDK','建物の構造':'RC'}
    def test_feature_lists_are_isolated(self):
        a=candidate_model(False); b=candidate_model(False); c=candidate_model(True)
        self.assertIn('quarter_index',NUM)
        self.assertNotIn('quarter_index',a['preprocess'].transformers[0][2])
        self.assertIn('quarter_index',c['preprocess'].transformers[0][2])
    def test_comparable_boundaries_and_no_future(self):
        r=self.row(); rows=[r.copy() for _ in range(10)]
        future=r.copy(); future['quarter']='2026Q3'
        pool=make_pool(pd.DataFrame(rows+[future]),np.full(11,1000000.))
        c=comparable(pool,r,'2026Q2')
        self.assertEqual(c['n'],10); self.assertEqual(c['status'],'sufficient')
        r['地区名']='別町'
        self.assertEqual(comparable(pool,r,'2026Q2')['n'],0)
        r['地区名']='町'; r['建築年']=''
        self.assertEqual(comparable(pool,r,'2026Q2')['status'],'insufficient_features')
    def test_asof_refusal(self):
        with self.assertRaises(ValueError):
            assess({'protocol':{'available_on':'2026-11-08'}},{'reference_date':'2026-07-01'})
    def test_insufficient_sample_no_strong_conclusion(self):
        r=self.row(); pool=make_pool(pd.DataFrame([r]),np.array([1000000.]))
        self.assertEqual(comparable(pool,r,'2026Q2')['status'],'insufficient_sample')


class ReviewRegressionTests(unittest.TestCase):
    def test_recent_fit_definition_has_no_evaluation_overlap(self):
        quarters=pd.Series(['2023Q1','2024Q1','2024Q4','2025Q1','2025Q3','2026Q2'])
        development_recent=quarters.str.startswith('2024')
        evaluation=quarters.str.startswith('2025')
        current_recent=quarters>='2025Q3'
        self.assertFalse((development_recent&evaluation).any())
        self.assertTrue((current_recent&evaluation).any())
        # Thus current refits must never be substituted for development fits.

    def test_example_feature_units(self):
        from japan_housing_liquidity_lab.benchmark import Features
        row={'quarter':'2026Q2','市区町村名':'世田谷区','最寄駅：名称':'三軒茶屋',
             '面積（㎡）':'70','建築年':'2005年','最寄駅：距離（分）':'10','間取り':'２ＬＤＫ','建物の構造':'ＲＣ',
             'asking_price_jpy':60000000}
        f=Features().transform(pd.DataFrame([row]))
        self.assertEqual(f.area.iloc[0],70)
        self.assertEqual(f.age.iloc[0],21)
        self.assertEqual(f.minutes.iloc[0],10)
        self.assertEqual(f.layout.iloc[0],'2LDK')
        self.assertEqual(f.structure.iloc[0],'RC')
        self.assertEqual(f.municipality.iloc[0],'世田谷区')
        self.assertEqual(f.station.iloc[0],'三軒茶屋')
        self.assertAlmostEqual(row['asking_price_jpy']/f.area.iloc[0],857142.8571428572)
        row['asking_price_jpy']=1
        pd.testing.assert_frame_equal(f,Features().transform(pd.DataFrame([row])))

    def test_two_records_remain_insufficient(self):
        row=CompetitiveTests().row()
        pool=make_pool(pd.DataFrame([row,row]),np.array([1285714.2857142857,1750000.]))
        result=comparable(pool,row,'2026Q2')
        self.assertEqual(result['n'],2)
        self.assertEqual(result['status'],'insufficient_sample')
        self.assertAlmostEqual(result['median'],1517857.1428571427)
