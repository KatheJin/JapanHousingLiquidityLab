import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

from japan_housing_liquidity_lab.expansion import qi,qs,keep_age_at
from japan_housing_liquidity_lab.benchmark import Features
from japan_housing_liquidity_lab.competitiveness import make_pool
from japan_housing_liquidity_lab.opportunity import adjusted_price,strict_mask
from japan_housing_liquidity_lab.temporal import window_bounds,split_masks,strict_support,fraction,score,run,validate_query


def sample(quarter='2023Q1',area='25',built='2005年',station='駅',town='町',layout='１Ｋ'):
    return {'quarter':quarter,'面積（㎡）':area,'建築年':built,'最寄駅：名称':station,'地区名':town,
            '市区町村名':'区','最寄駅：距離（分）':'10','間取り':layout,'建物の構造':'ＲＣ'}


class TemporalTests(unittest.TestCase):
    def test_current_vintage_rejects_earlier_reference_or_invalid_money(self):
        query=dict(sample(),reference_date='2026-11-08',asking_price_jpy=30000000)
        self.assertEqual(validate_query(query)['quarter'],'2026Q2')
        with self.assertRaises(ValueError): validate_query(dict(query,reference_date='2025-12-31'))
        with self.assertRaises(ValueError): validate_query(dict(query,asking_price_jpy=float('nan')))
    def test_quarter_roundtrip_and_validation(self):
        for q in ('2018Q1','2022Q4','2026Q2'):
            self.assertEqual(qs(qi(q)),q)
        with self.assertRaises(ValueError): qi('2026Q5')

    def test_full_8_year_window_and_strict_boundary(self):
        frame=pd.DataFrame({'quarter':[qs(i) for i in range(qi('2018Q1'),qi('2026Q3'))]})
        self.assertEqual(window_bounds('2026Q1',8),('2018Q1','2025Q4'))
        train,val=split_masks(frame,'2026Q1',8)
        self.assertEqual(train.sum(),32)
        self.assertFalse((train&val).any())
        self.assertLess(frame.loc[train,'quarter'].max(),frame.loc[val,'quarter'].min())
        self.assertIsNone(split_masks(frame,'2025Q4',8))

    def test_missing_training_quarter_never_silently_shortened(self):
        frame=pd.DataFrame({'quarter':[qs(i) for i in range(qi('2018Q1'),qi('2026Q3'))]})
        frame=frame[frame.quarter!='2020Q2']
        self.assertIsNone(split_masks(frame,'2026Q1',8))
        self.assertIsNotNone(split_masks(frame,'2026Q1',3))

    def test_future_rows_do_not_change_training_membership(self):
        frame=pd.DataFrame({'quarter':[qs(i) for i in range(qi('2018Q1'),qi('2026Q3'))]})
        a=split_masks(frame,'2023Q1',5)[0]
        later=pd.concat([frame,pd.DataFrame({'quarter':['2027Q1']})],ignore_index=True)
        b=split_masks(later,'2023Q1',5)[0]
        self.assertEqual(frame.loc[a,'quarter'].tolist(),later.loc[b,'quarter'].tolist())

    def test_age_moves_with_trade_year(self):
        f=Features().transform(pd.DataFrame([sample('2018Q1'),sample('2026Q2')]))
        self.assertEqual(f.age.tolist(),[13,21])

    def test_counterfactual_holds_age_and_does_not_mutate(self):
        frame=pd.DataFrame([sample('2018Q1'),sample('2023Q2')]); original=frame.copy(deep=True)
        moved=keep_age_at(frame,'2026Q2')
        self.assertEqual(Features().transform(frame).age.tolist(),Features().transform(moved).age.tolist())
        pd.testing.assert_frame_equal(frame,original)
        with self.assertRaises(ValueError): keep_age_at(pd.DataFrame([sample(built='不明')]),'2026Q2')

    def test_strict_support_matches_task006(self):
        frame=pd.DataFrame([sample(area='20'),sample(area='30'),sample(area='31'),sample(station='別駅'),sample(layout='2LDK'),sample(built='1970年')])
        pool=make_pool(frame,np.ones(len(frame)))
        query=sample()
        expected=strict_mask(pool,query,'2023Q1','2023Q4').sum()
        got=strict_support(pool,make_pool(pd.DataFrame([query]),[1]))[0]
        self.assertEqual(got,expected)
        self.assertEqual(got,2)

    def test_unknown_age_abstains_support(self):
        pool=make_pool(pd.DataFrame([sample()]),[1])
        q=make_pool(pd.DataFrame([sample(built='不明')]),[1])
        self.assertEqual(strict_support(pool,q)[0],0)

    def test_multiplicative_decomposition_and_relative_ratio_identity(self):
        actual=np.array([100.,130.]); row=np.log([110.,120.]); cf=np.log([140.,160.]); query=np.log(150.)
        quality=actual*np.exp(query-cf); time=np.exp(cf-row)
        both=adjusted_price(actual,query,row)
        np.testing.assert_allclose(quality*time,both)
        np.testing.assert_array_equal(both<140,actual/np.exp(row)<140/np.exp(query))

    def test_small_sample_and_ties(self):
        self.assertIsNone(fraction([1]*9,2)['fraction'])
        self.assertEqual(fraction([2]*10,2)['fraction'],0.)

    def test_signed_errors_not_accuracy(self):
        result=score(np.array([100.,200.]),np.array([110.,220.]))
        self.assertAlmostEqual(result['mape_pct'],10)
        self.assertAlmostEqual(result['mean_signed_pct'],10)
        self.assertEqual(result['overprediction_fraction'],1.)

    def test_no_output_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError): run(Path('absent'),Path('absent'),Path(temp))


if __name__=='__main__': unittest.main()
