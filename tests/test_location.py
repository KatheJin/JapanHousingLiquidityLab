import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

from japan_housing_liquidity_lab.benchmark import Features
from japan_housing_liquidity_lab.expansion import digest
from japan_housing_liquidity_lab.location import (
    UNKNOWN, prepare, walk_bounds, walk_band, validate_query, budget_mask,
    standardize, stats, table, walk_contrasts, run, commute_result, TRANSPORT_MODES,
)


def row(i=0, quarter='2025Q1', city='区A', station='駅', minutes='10', area='50', price='50000000', built='2005年'):
    return {'record_id':f'synthetic:{i}', 'quarter':quarter, '市区町村名':city,
            '最寄駅：名称':station, '最寄駅：距離（分）':minutes, '面積（㎡）':area,
            '取引価格（総額）':price, '建築年':built, '間取り':'２ＬＤＫ', '建物の構造':'ＲＣ',
            'unit_price_jpy_m2':str(float(price)/float(area)) if area.isdigit() else '',
            'exact_duplicate_flag':'false', 'quality_flags':''}


def query(**kwargs):
    return validate_query(dict(reference_date='2026-11-08',budget_max_jpy=60000000,
                               history_start='2025Q1',history_end='2025Q1',**kwargs), {'2025Q1'}, '2026-11-08')


class AnalyticalModel:
    """Synthetic known function for testing cancellation, not a fitted research model."""
    def predict(self, frame):
        f=Features().transform(frame)
        return np.log(1000000)+f.area*.01-f.age*.02+f.quarter_index*.1+f.minutes*.003


class LocationTests(unittest.TestCase):
    def test_support_gate_applies_after_all_housing_filters(self):
        raw=pd.DataFrame([row(i,price='50000000' if i<29 else '70000000') for i in range(100)])
        f=prepare(raw)
        f['standardized_unit']=1000000
        f['profile_support']=True
        self.assertEqual(table(f,['municipality','station']).iloc[0]['status'],'descriptive_support')
        selected=table(f,['municipality','station'],budget_mask(f,query())).iloc[0]
        self.assertEqual(selected['n'],29)
        self.assertEqual(selected['period_sample_n'],100)
        self.assertEqual(selected['profile_support_n'],29)
        self.assertEqual(selected['status'],'insufficient_sample')
        self.assertTrue(pd.isna(selected['unit_jpy_m2_median']))
        self.assertTrue(pd.isna(selected['standardized_unit_median']))

    def test_default_history_start_is_relative_to_requested_end(self):
        quarters={f'{y}Q{q}' for y in range(2018,2027) for q in range(1,5)}
        q=validate_query(dict(reference_date='2026-11-08',budget_max_jpy=60000000,history_end='2024Q4'),quarters,'2026-11-08')
        self.assertEqual(q['history_start'],'2023Q3')
        self.assertEqual(q['history_end'],'2024Q4')

    def test_inclusive_equal_budget_and_area_bounds(self):
        q=validate_query(dict(reference_date='2026-11-08',budget_min_jpy=50000000,budget_max_jpy=50000000,
                              min_area_m2=50,max_area_m2=50),{'2025Q1'},'2026-11-08')
        f=prepare(pd.DataFrame([row(0),row(1,area='49'),row(2,price='50000001')]))
        self.assertEqual(budget_mask(f,q).tolist(),[True,False,False])
        with self.assertRaises(ValueError):
            validate_query(dict(reference_date='2026-11-08',budget_max_jpy=0),{'2025Q1'},'2026-11-08')

    def test_age_is_at_trade_and_period_boundaries_are_inclusive(self):
        f=prepare(pd.DataFrame([row(0,quarter='2024Q4'),row(1,quarter='2025Q1'),row(2,quarter='2025Q2'),row(3,quarter='2026Q1')]))
        q=query(max_age=20)
        self.assertEqual(budget_mask(f,q).tolist(),[False,True,False,False])
        q.update(history_end='2026Q1')
        self.assertEqual(budget_mask(f,q).tolist(),[False,True,True,False])

    def test_station_format_normalizes_width_but_preserves_qualifiers(self):
        f=prepare(pd.DataFrame([row(0,station=' 浅草(つくばＥＸＰ) '),row(1,station='浅草(つくばEXP)'),row(2,station='浅草')]))
        t=table(f,['municipality','station'])
        self.assertEqual(len(t),2)
        self.assertEqual(t.loc[t.station=='浅草(つくばEXP)','n'].iloc[0],2)

    def test_all_transport_modes_abstain_without_affecting_housing_filters(self):
        f=prepare(pd.DataFrame([row()]))
        for mode in TRANSPORT_MODES:
            q=query(transport_modes=[mode],max_commute_minutes=1)
            result=commute_result(q)
            self.assertIsNone(result['by_mode'][mode]['door_to_door_minutes'])
            self.assertIsNone(result['by_mode'][mode]['within_limit'])
            self.assertEqual(result['by_mode'][mode]['status'],'unsupported_no_verified_route_data')
            self.assertFalse(result['constraints_applied'])
            self.assertTrue(budget_mask(f,q).iloc[0])
        for modes in [[],['flying'],'private_car',[None]]:
            with self.assertRaises(ValueError): query(transport_modes=modes)

    def test_required_query_fields_fail_explicitly(self):
        for value in [[],{},dict(reference_date='2026-11-08')]:
            with self.assertRaisesRegex(ValueError,'required'):
                validate_query(value,{'2025Q1'},'2026-11-08')

    def test_distance_intervals_are_not_midpoint_commutes(self):
        self.assertEqual(walk_bounds('３０分～６０分'),(30,60))
        self.assertEqual(walk_bounds('2H～'),(120,np.inf))
        self.assertEqual(walk_band('5'),'0-5')
        self.assertEqual(walk_band('6'),'>5-10')
        self.assertEqual(walk_band('30分～60分'),'interval:30分~60分')
        self.assertEqual(walk_band('不明'),UNKNOWN)

    def test_budget_units_boundaries_and_unknown_age(self):
        raw=pd.DataFrame([row(0,area='40',price='60000000'),row(1,area='39'),
                          row(2,price='60000001'),row(3,built='不明')])
        f=prepare(raw); q=query(min_area_m2=40,max_age=40)
        self.assertEqual(budget_mask(f,q).tolist(),[True,False,False,False])
        self.assertEqual(f.unit_jpy_m2.iloc[0],1500000)

    def test_walk_filter_conservative_interval_and_missing(self):
        f=prepare(pd.DataFrame([row(0,minutes='30分～60分'),row(1,minutes='45'),row(2,minutes='')]))
        self.assertEqual(budget_mask(f,query(max_walk_minutes=45)).tolist(),[False,True,False])
        self.assertTrue(budget_mask(f,query(max_walk_minutes=60)).iloc[0])

    def test_station_names_do_not_merge_across_municipalities(self):
        f=prepare(pd.DataFrame([row(0,city='区A'),row(1,city='区B'),row(2,station='')]))
        t=table(f,['municipality','station'])
        self.assertEqual(len(t),3)
        self.assertEqual(t.loc[t.station==UNKNOWN,'status'].iloc[0],'unknown_location')

    def test_bounded_area_and_duplicate_transactions_retained(self):
        raw=pd.DataFrame([row(0,area='2,000㎡以上'),row(1),row(2)])
        f=prepare(raw)
        self.assertEqual(len(f),3)
        self.assertTrue(np.isnan(f.area.iloc[0]))
        self.assertFalse(budget_mask(f,query()).iloc[0])
        with self.assertRaisesRegex(ValueError,'Duplicate source IDs'):
            prepare(pd.DataFrame([row(1),row(1)]))

    def test_price_integrity_and_input_immutable(self):
        raw=pd.DataFrame([row()]); before=raw.copy(deep=True)
        prepare(raw); pd.testing.assert_frame_equal(raw,before)
        raw.loc[0,'unit_price_jpy_m2']='1'
        with self.assertRaisesRegex(ValueError,'Unit-price mismatch'): prepare(raw)

    def test_missing_quarters_and_future_vintage_refused(self):
        q=dict(reference_date='2026-11-08',budget_max_jpy=1,history_start='2025Q1',history_end='2025Q3')
        with self.assertRaisesRegex(ValueError,'quarters unavailable'):
            validate_query(q,{'2025Q1','2025Q3'},'2026-11-08')
        q.update(reference_date='2025-01-01',history_end='2025Q1')
        with self.assertRaisesRegex(ValueError,'vintage'): validate_query(q,{'2025Q1'},'2026-11-08')

    def test_query_validation_and_custom_destination(self):
        for kw in [dict(max_age=float('nan')),dict(max_walk_minutes=-1),dict(layouts='2LDK'),dict(typo=3)]:
            with self.assertRaises(ValueError): query(**kw)
        self.assertEqual(query(destinations=['大手町'])['destinations'],['大手町'])

    def test_layout_normalization_and_filter(self):
        f=prepare(pd.DataFrame([row()]))
        self.assertTrue(budget_mask(f,query(layouts=['２ＬＤＫ'],structures=['ＲＣ'])).iloc[0])
        self.assertFalse(budget_mask(f,query(layouts=['1K'])).iloc[0])

    def test_small_sample_and_missing_metric_support(self):
        f=prepare(pd.DataFrame([row(i,built='不明') for i in range(30)]))
        self.assertIsNone(stats(f.iloc[:29])['unit_jpy_m2_median'])
        self.assertEqual(stats(f)['unit_jpy_m2_median'],1000000)
        self.assertIsNone(stats(f)['age_median'])
        self.assertIsNone(stats(f)['standardized_unit_median'])

    def test_adjusted_comparison_uses_identical_rows_and_layout_denominator(self):
        raw=pd.DataFrame([row(i,price='1000000' if i==30 else '50000000') for i in range(31)])
        raw.loc[:29,'間取り']=''
        f=prepare(raw)
        f.loc[:29,'standardized_unit']=1200000
        f.loc[:29,'profile_support']=True
        s=stats(f)
        self.assertIsNone(s['modal_layout'])
        self.assertEqual(s['standardized_subset_raw_unit_median'],1000000)
        self.assertEqual(s['standardized_unit_median'],1200000)

    def test_property_adjustment_preserves_trade_time_and_access(self):
        raw=pd.DataFrame([row(0,quarter='2018Q1'),row(1,quarter='2025Q1',area='60'),
                          row(2,quarter='2026Q2',area='60'),row(3,quarter='2026Q3')])
        original=raw.copy(deep=True); f=prepare(raw)
        b=dict(latest_quarter='2026Q2',pool=pd.DataFrame({'municipality':['区A'],'station':['駅']}),
               models={'history_with_time':AnalyticalModel()})
        g=standardize(raw,f,b)
        self.assertTrue(g.standardized_unit.iloc[[0,3]].isna().all())
        expected1=f.unit_jpy_m2.iloc[1]*np.exp(-.1)  # area only; original age equals 20
        expected2=f.unit_jpy_m2.iloc[2]*np.exp(-.1+.02)  # age 21 -> 20
        np.testing.assert_allclose(g.standardized_unit.iloc[1:3],[expected1,expected2])
        pd.testing.assert_frame_equal(raw,original)
        self.assertTrue(f.standardized_unit.isna().all())

    def test_within_station_year_walk_contrast_and_refusal(self):
        raw=pd.DataFrame([row(i,minutes='3') for i in range(30)]+
                         [row(i+30,minutes='13',price='40000000') for i in range(30)])
        f=prepare(raw); result=walk_contrasts(f)
        self.assertAlmostEqual(result.raw_far_to_near.iloc[0],.8)
        self.assertTrue(pd.isna(result.standardized_far_to_near.iloc[0]))
        self.assertTrue(walk_contrasts(f.iloc[:-1]).empty)

    def test_end_to_end_cli_refuses_commute_claims_and_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); data=root/'data.csv'; quality=root/'quality.json'; qpath=root/'query.json'
            pd.DataFrame([row(i) for i in range(30)]).to_csv(data,index=False,encoding='utf-8-sig')
            quality.write_text(json.dumps(dict(combined_sha256=digest(data),total=30,quarters=['2025Q1'],
                                              sources=[dict(acquired_at='2026-11-08T12:00:00+09:00')])),encoding='utf-8')
            qpath.write_text(json.dumps(query(max_commute_minutes=45,transport_modes=list(TRANSPORT_MODES)),ensure_ascii=False),encoding='utf-8')
            out=root/'output'
            cmd=[sys.executable,'-X','utf8','-m','japan_housing_liquidity_lab.location','--data',str(data),'--quality',str(quality),
                 '--query',str(qpath),'--output',str(out)]
            result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['n'],30)
            report=json.loads((out/'analysis.json').read_text(encoding='utf-8'))
            self.assertEqual(report['budget']['matched_n'],30)
            self.assertFalse(report['commute']['constraints_applied'])
            self.assertIsNone(report['commute']['door_to_door_minutes'])
            self.assertEqual(set(report['commute']['by_mode']),set(TRANSPORT_MODES))
            comparison=json.loads((out/'budget_comparison.json').read_text(encoding='utf-8'))
            self.assertEqual(comparison['commute'],report['commute'])
            self.assertFalse(report['new_independent_test'])
            with self.assertRaises(FileExistsError): run(data,quality,qpath,out)
            data.write_text('tampered',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'SHA-256'): run(data,quality,qpath,root/'invalid')
            self.assertFalse((root/'invalid').exists())


if __name__=='__main__':
    unittest.main()
