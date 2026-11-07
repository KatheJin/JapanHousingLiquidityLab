import unittest
import numpy as np
import pandas as pd
from japan_housing_liquidity_lab.competitiveness import make_pool
from japan_housing_liquidity_lab.opportunity import strict_mask,stats,adjusted_price,quarter_index

class OpportunityTests(unittest.TestCase):
    def row(self):
        return {'quarter':'2026Q2','市区町村名':'区','地区名':'町','最寄駅：名称':'駅','面積（㎡）':'70',
                '建築年':'2005年','間取り':'２ＬＤＫ','建物の構造':'ＲＣ','最寄駅：距離（分）':'10'}
    def test_strict_fields_and_period(self):
        a=self.row(); b=dict(a,間取り='3LDK'); c=dict(a,quarter='2026Q3')
        pool=make_pool(pd.DataFrame([a,b,c]),np.array([1.,2.,3.]))
        self.assertEqual(strict_mask(pool,a,'2023Q1','2026Q2').tolist(),[True,False,False])
        a['地区名']='別町'; self.assertFalse(strict_mask(pool,a,'2023Q1','2026Q2').any())
    def test_ratio_adjustment_identity_and_scaling(self):
        np.testing.assert_allclose(adjusted_price([100,200],np.log(2),[np.log(2),np.log(2)]),[100,200])
        np.testing.assert_allclose(adjusted_price([100],np.log(4),[np.log(2)]),[200])
    def test_small_sample_abstention_and_ties(self):
        self.assertIsNone(stats([1,2],3)['lower_price_record_fraction'])
        self.assertIsNone(stats([],3)['lower_price_record_fraction'])
        s=stats([1]*5+[2]*5,2)
        self.assertEqual(s['lower_price_record_count'],5)
        self.assertEqual(s['lower_price_record_fraction'],.5)
        self.assertEqual(s['status'],'descriptive_only')
    def test_period_validation(self):
        self.assertEqual(quarter_index('2026Q2'),13)
        with self.assertRaises(ValueError): quarter_index('2026Q5')
