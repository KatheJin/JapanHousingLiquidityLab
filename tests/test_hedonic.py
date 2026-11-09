"""Synthetic units and temporal boundaries; no network/database access."""
import unittest
from types import SimpleNamespace
import numpy as np
import pandas as pd
from japan_housing_liquidity_lab.hedonic_adjustment import feature_states,decompose
from japan_housing_liquidity_lab.hedonic_experiment import target_for_training,estimator
from japan_housing_liquidity_lab.temporal import split_masks
from japan_housing_liquidity_lab.expansion import qs,qi

ROW={'quarter':'2023Q1','建築年':'2000年','面積（㎡）':'70','市区町村名':'架空区','最寄駅：名称':'架空駅','最寄駅：距離（分）':'10','間取り':'2LDK','建物の構造':'RC'}
class Identity:
    def transform(self,x):return x
class Linear:
    def predict(self,x):return np.log(1000000)+.01*x.area-.02*x.age+.03*x.quarter_index
PIPE={'preprocess':Identity(),'model':Linear()}
class HedonicTests(unittest.TestCase):
    def test_same_property_construction_year_and_age(self):
        old=dict(ROW);states=feature_states(ROW,'2025Q1')
        self.assertEqual(ROW,old);self.assertEqual([float(x.age.iloc[0]) for x in states],[23,23,23,25])
        self.assertEqual(float(states[2].quarter_index.iloc[0]-states[1].quarter_index.iloc[0]),8)
    def test_separate_components_telescope_without_double_aging(self):
        ref=dict(ROW,**{'面積（㎡）':'80','建築年':'2005年'})
        result=decompose(PIPE,ROW,'2025Q1',1000000,ref,train_period=['2023Q1','2025Q1'])
        d=result['diagnostic'];self.assertEqual(d['original_construction_year'],'2000年');self.assertEqual(d['comparison_construction_year'],'2005年');self.assertTrue(d['construction_year_preserved_on_aging_path']);self.assertAlmostEqual(d['attribute_log_effect'],.2)
        self.assertAlmostEqual(d['time_log_effect'],.24);self.assertAlmostEqual(d['aging_log_effect'],-.04)
        self.assertAlmostEqual(d['total_log_effect'],.4)
        self.assertAlmostEqual(d['fitted_adjusted_unit_price'],1000000*np.exp(.4))
        self.assertEqual(result['status'],'unavailable');self.assertIsNone(result['adjusted_unit_price'])
    def test_constant_year_within_year_has_no_aging(self):
        d=decompose(PIPE,ROW,'2023Q4',1000000)['diagnostic']
        self.assertAlmostEqual(d['aging_log_effect'],0);self.assertAlmostEqual(d['time_log_effect'],.09)
    def test_unknown_age_refused_no_imputation(self):
        self.assertIsNone(decompose(PIPE,dict(ROW,建築年=''), '2025Q1',1000000)['diagnostic'])
        with self.assertRaises(ValueError):decompose(PIPE,ROW,'2025Q1',-1)
        self.assertIsNone(decompose(PIPE,ROW,'2022Q1',1000000)['diagnostic'])
    def test_outside_time_support_is_explicit(self):
        r=decompose(PIPE,ROW,'2026Q2',1000000,train_period=['2023Q1','2025Q4'])
        self.assertTrue(any('outside' in x for x in r['reasons']))
    def test_only_upper_training_tail_capped(self):
        y=np.arange(1,1001,dtype=float);before=y.copy()
        for v,q in [('upper99',.99),('upper995',.995)]:
            z,cap=target_for_training(y,v)
            np.testing.assert_allclose(np.exp(z),np.minimum(y,np.quantile(y,q)))
            self.assertAlmostEqual(np.exp(z)[0],1)
        np.testing.assert_array_equal(y,before)
        self.assertIsNone(target_for_training(y,'raw')[1])
    def test_rolling_common_holdouts_and_full_windows(self):
        f=pd.DataFrame({'quarter':[qs(i) for i in range(qi('2018Q1'),qi('2026Q2')+1)]})
        for origin in ['2026Q1','2026Q2']:
            for years in [3,5,8]:
                tr,va=split_masks(f,origin,years)
                self.assertEqual(tr.sum(),4*years);self.assertEqual(f.loc[va,'quarter'].tolist(),[origin])
                self.assertLess(f.loc[tr,'quarter'].max(),origin)
    def test_real_pipeline_decomposition_matches_direct_prediction(self):
        from threadpoolctl import threadpool_limits
        from japan_housing_liquidity_lab.benchmark import model
        rows=[dict(ROW,quarter='2023Q'+str(i%4+1),**{'面積（㎡）':str(40+i),'建築年':str(1980+i%30)+'年'}) for i in range(80)]
        data=pd.DataFrame(rows)
        with threadpool_limits(limits=2):
            for name in ['ridge','hgb']:
                pipe=model(name);pipe.fit(data,np.log(np.arange(80)+500000))
                end=dict(ROW,quarter='2025Q1')
                expected=float(1000000*np.exp(pipe.predict(pd.DataFrame([end]))[0]-pipe.predict(pd.DataFrame([ROW]))[0]))
                result=decompose(pipe,ROW,'2025Q1',1000000)
                self.assertAlmostEqual(result['diagnostic']['fitted_adjusted_unit_price'],expected,places=5)

    def test_high_price_threshold_includes_exact_boundary(self):
        from japan_housing_liquidity_lab.hedonic_experiment import high_price_metrics
        f=pd.DataFrame(dict(actual=[1499999,1500000,1500001],predicted=[1,1400000,1400001],years=3,model='ridge',variant='raw'))
        summary=high_price_metrics(f).iloc[0]
        self.assertEqual(summary['n'],2);self.assertEqual(summary['mae'],100000)

    def test_robust_estimators_keep_existing_features(self):
        for name in ['ridge','hgb']:
            p=estimator(name,'raw');r=estimator(name,'robust')
            self.assertEqual(type(p['features']),type(r['features']))
            self.assertEqual(type(p['preprocess']),type(r['preprocess']))
        self.assertEqual(estimator('hgb','robust')['model'].loss,'absolute_error')
if __name__=='__main__':unittest.main()
