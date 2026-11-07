import unittest
import numpy as np
import pandas as pd
from japan_housing_liquidity_lab.benchmark import Features,distance,model,metrics

class BenchmarkTests(unittest.TestCase):
    def sample(self,city='架空区',quarter='2023Q1'):
        return {'quarter':quarter,'市区町村名':city,'最寄駅：名称':'駅','面積（㎡）':'50','建築年':'2000年',
                '最寄駅：距離（分）':'30分～60分','間取り':'２ＬＤＫ','建物の構造':'ＲＣ'}
    def test_feature_semantics(self):
        f=Features().transform(pd.DataFrame([self.sample()]))
        self.assertEqual(f.age.iloc[0],23)
        self.assertEqual(f.minutes.iloc[0],45)
        self.assertEqual(f.layout.iloc[0],'2LDK')
        self.assertEqual(distance('2H～')[2],'lower_bound')
        r=self.sample(); r['建築年']='戦前'
        self.assertTrue(np.isnan(Features().transform(pd.DataFrame([r])).age.iloc[0]))
        r['建築年']='2028年'
        self.assertTrue(np.isnan(Features().transform(pd.DataFrame([r])).age.iloc[0]))
    def test_train_only_encoding_and_unknown_prediction(self):
        X=pd.DataFrame([self.sample(),self.sample()]); y=np.log([500000.,700000.])
        m=model('ridge').fit(X,y)
        unseen=self.sample('未知区','2026Q1'); unseen['最寄駅：名称']='未知駅'
        before=m['preprocess'].named_transformers_['cat']['encode'].categories_[0].copy()
        self.assertTrue(np.isfinite(m.predict(pd.DataFrame([unseen]))).all())
        np.testing.assert_array_equal(before,m['preprocess'].named_transformers_['cat']['encode'].categories_[0])
        self.assertNotIn('未知区',before)
    def test_baseline_fallback_and_metrics(self):
        m=model('median').fit(pd.DataFrame([self.sample()]),np.log([600000.]))
        self.assertAlmostEqual(np.exp(m.predict(pd.DataFrame([self.sample('未知区')]))[0]),600000)
        result=metrics(np.array([100.,200.]),np.array([110.,180.]))
        self.assertEqual(result['mae'],15)
        self.assertAlmostEqual(result['mape_pct'],10)
