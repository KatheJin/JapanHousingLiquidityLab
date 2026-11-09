"""Synthetic spatial diagnostics; no fitting, network or production DB writes."""
import copy
import unittest
import numpy as np
import pandas as pd
from japan_housing_liquidity_lab import area_comparison as a
from japan_housing_liquidity_lab.benchmark import Features

Q={'reference_date':'2026-11-10','asking_price_jpy':30000000,'市区町村名':'甲区','最寄駅：名称':'基準駅','面積（㎡）':'25','建築年':'2005年','間取り':'1K','建物の構造':'RC','最寄駅：距離（分）':'10'}
class Model:
    def __init__(self,offsets):self.offsets=offsets;self.calls=[]
    def predict(self,frame):
        self.calls.append(frame.copy())
        return np.log([1000000*self.offsets.get(s,1) for s in frame['最寄駅：名称']])

def resources():
    markets=[('甲区','基準駅'),('乙区','候補B'),('丙区','候補C'),('丁区','小標本')]
    rows=[]
    for city,station in markets:
        for i in range(40):
            rows.append(dict(Q,quarter='2026Q2',**{'市区町村名':city,'最寄駅：名称':station,'面積（㎡）':'25' if station!='小標本' or i<2 else '80'}))
    pool=Features().transform(pd.DataFrame(rows));pool['period']='2026Q2';pool['actual']=1000000
    models={m:Model({'候補B':1.02 if m!=a.METHODS[1] else 1.2,'候補C':1.05}) for m in a.METHODS}
    dev=pd.DataFrame({'municipality':[c for c,s in markets]*10,'station':[s for c,s in markets]*10,'actual':[1100000]*40,**{m:[1000000]*40 for m in a.METHODS}})
    return dict(pool=pool,bundle={'models':models,'ranges':{'area':[15,110]}},metadata={'available_on':'2026-11-08','reference_quarter':'2026Q2','model_period':['2023Q1','2026Q2']},development=dev,known={m:{'municipality':set(c for c,s in markets),'station':set(s for c,s in markets),'layout':{'1K'},'structure':{'RC'}} for m in a.METHODS})

class AreaTests(unittest.TestCase):
    def test_fixed_attributes_and_year_reference(self):
        r=resources();q=copy.deepcopy(Q);result=a.compare(r,q)
        self.assertEqual(q,Q);self.assertEqual(result['common_attributes']['age_at_reference'],21)
        for model in r['bundle']['models'].values():
            frame=model.calls[0]
            for key in ['面積（㎡）','建築年','間取り','建物の構造','最寄駅：距離（分）']:
                self.assertEqual(set(frame[key]),{Q[key]})
            self.assertEqual(set(frame.quarter),{'2026Q2'})
    def test_profile_support_after_filters_and_same_target_gate(self):
        r=resources();result=a.compare(r,Q)
        self.assertNotIn('小標本',[x['station'] for x in result['candidates']])
        poor=a.compare(r,Q|{'市区町村名':'丁区','最寄駅：名称':'小標本'})
        self.assertEqual(poor['status'],'unavailable');self.assertEqual(poor['target']['support_n'],2)
        self.assertEqual(poor['candidates'],[])
    def test_research_prices_are_separate_and_not_intervals(self):
        result=a.compare(resources(),Q)
        self.assertEqual(result['status'],'research_only')
        for row in [result['target']]+result['candidates']:
            self.assertIsNone(row['reference_unit_price_jpy_m2']);self.assertIsNone(row['relative_gap_pct'])
            self.assertGreater(row['diagnostic_reference_unit_price_jpy_m2'],0)
            self.assertFalse(row['uncertainty']['model_spread_is_prediction_interval'])
            self.assertNotIn('rank',row)
    def test_percent_units_and_grouped_alphabetic_order(self):
        result=a.compare(resources(),Q);b=next(x for x in result['candidates'] if x['station']=='候補B')
        self.assertAlmostEqual(b['diagnostic_relative_gap_pct'],2)
        self.assertEqual(b['proximity_band'],'method_dependent')
        self.assertEqual(result['candidates'][0]['station'],'候補C')
        self.assertEqual(result['rank_stability']['compared_market_n'],2)
    def test_price_not_filter_and_missing_required_feature_refuses(self):
        first=a.compare(resources(),Q);second=a.compare(resources(),Q|{'asking_price_jpy':100})
        self.assertEqual(first['candidates'],second['candidates'])
        for key in ['最寄駅：距離（分）','間取り','建物の構造']:
            self.assertEqual(a.compare(resources(),Q|{key:''})['status'],'unavailable')
    def test_asof_and_unknown_station_are_not_invented(self):
        with self.assertRaises(ValueError):a.compare(resources(),Q|{'reference_date':'2025-01-01'})
        result=a.compare(resources(),Q|{'最寄駅：名称':'基準駅(東京)'})
        self.assertEqual(result['status'],'unavailable')
    def test_extended_history_does_not_inflate_model_support(self):
        r=resources();old=r['pool'].copy();old['period']='2018Q1'
        r['pool']=pd.concat([r['pool'],old],ignore_index=True)
        result=a.compare(r,Q)
        self.assertEqual(result['target']['support_n'],40)
        self.assertEqual(result['target']['model_period_sample_n'],40)
        self.assertEqual(result['target']['expanded_period_sample_n'],40)
    def test_pooled_and_unseen_categories_abstain(self):
        r=resources();r['known'][a.METHODS[1]]['station'].remove('基準駅')
        self.assertEqual(a.compare(r,Q)['status'],'unavailable')
        r=resources();r['known'][a.METHODS[1]]['layout']=set()
        result=a.compare(r,Q);self.assertEqual(result['status'],'unavailable')
        self.assertTrue(any('pooled layout' in x for x in result['target']['reasons']))

    def test_absent_recent_joint_profile_is_explicit(self):
        r=resources();r['pool']['period']='2024Q4'
        row=a.compare(r,Q)['target']
        self.assertEqual(row['recent_support_n'],0)
        self.assertTrue(any('No matching joint profile' in x for x in row['reasons']))
        self.assertEqual(row['uncertainty']['joint_profile_support_by_model']['recent_no_time'],0)

    def test_explainable_groups_and_gap_spread_threshold(self):
        r=resources();result=a.compare(r,Q)
        b=next(x for x in result['candidates'] if x['station']=='候補B')
        c=next(x for x in result['candidates'] if x['station']=='候補C')
        self.assertEqual(b['evidence_group'],'model_disagreement');self.assertFalse(b['model_agreement'])
        self.assertAlmostEqual(b['diagnostic_gap_spread_percentage_points'],18)
        self.assertEqual(c['evidence_group'],'multi_model_agreement');self.assertTrue(c['model_agreement'])
        # Both models can stay within the broad10% band while disagreeing by more than5 points.
        r['bundle']['models'][a.METHODS[1]].offsets['候補C']=.98
        c=next(x for x in a.compare(r,Q)['candidates'] if x['station']=='候補C')
        self.assertEqual(c['proximity_band'],'all_methods_within_10pct')
        self.assertEqual(c['evidence_group'],'model_disagreement');self.assertFalse(c['model_agreement'])

    def test_sparse_recent_support_takes_precedence_without_erasing_model_agreement(self):
        r=resources();r['pool'].loc[r['pool'].station=='候補C','period']='2024Q4'
        result=a.compare(r,Q);c=next(x for x in result['candidates'] if x['station']=='候補C')
        self.assertEqual(c['evidence_group'],'insufficient_sample');self.assertTrue(c['model_agreement'])
        self.assertEqual(c['historical_joint_profile']['sample_n'],40)
        self.assertEqual(c['historical_joint_profile']['recent']['sample_n'],0)
        self.assertIsNone(c['historical_joint_profile']['recent']['raw_unit_price_jpy_m2']['median'])
        self.assertEqual(result['evidence_group_counts']['insufficient_sample'],1)

    def test_raw_empirical_prices_use_joint_filter_and_separate_periods(self):
        r=resources();mask=r['pool'].station=='候補C'
        r['pool'].loc[mask,'actual']=np.arange(40)*10000+500000
        r['pool'].loc[r['pool'].index[mask][:30],'period']='2024Q4'
        # Neither an unmatched large unit nor an earlier expansion record enters these quartiles.
        extra=r['pool'].loc[mask].iloc[:2].copy();extra['actual']=100000000
        extra.iloc[0,extra.columns.get_loc('area')]=80
        extra.iloc[1,extra.columns.get_loc('period')]='2019Q4'
        r['pool']=pd.concat([r['pool'],extra],ignore_index=True)
        c=next(x for x in a.compare(r,Q)['candidates'] if x['station']=='候補C')
        stats=c['historical_joint_profile']
        self.assertEqual(stats['sample_n'],40);self.assertEqual(stats['valid_price_n'],40)
        self.assertEqual(stats['raw_unit_price_jpy_m2'],{'q1':597500.,'median':695000.,'q3':792500.})
        self.assertEqual(stats['period_start'],'2024Q4');self.assertEqual(stats['recent']['sample_n'],10)
        self.assertEqual(stats['recent']['raw_unit_price_jpy_m2']['median'],845000.)
        self.assertFalse(stats['adjusted']);self.assertIsNone(c['reference_unit_price_jpy_m2'])
        self.assertNotEqual(stats['raw_unit_price_jpy_m2']['median'],c['diagnostic_reference_unit_price_jpy_m2'])

    def test_small_or_invalid_price_samples_report_counts_without_quartiles(self):
        r=resources();poor=a.compare(r,Q|{'市区町村名':'丁区','最寄駅：名称':'小標本'})
        stats=poor['target']['historical_joint_profile']
        self.assertEqual(stats['sample_n'],2);self.assertEqual(stats['status'],'insufficient_sample')
        self.assertTrue(all(v is None for v in stats['raw_unit_price_jpy_m2'].values()))
        self.assertEqual(poor['target']['evidence_group'],'insufficient_sample')
        self.assertIsNone(poor['target']['model_agreement']);self.assertEqual(poor['candidates'],[])
        frame=r['pool'].iloc[:12].copy();frame['actual']=frame.actual.astype(float);frame.loc[frame.index[:4],'actual']=[np.nan,np.inf,0,-1]
        stats=a._raw_distribution(frame,['2023Q1','2026Q2'])
        self.assertEqual(stats['valid_price_n'],8);self.assertEqual(stats['missing_or_invalid_price_n'],4)
        self.assertIsNone(stats['raw_unit_price_jpy_m2']['median'])

    def test_error_metrics_are_prior_out_of_training_evidence(self):
        row=a.compare(resources(),Q)['target']
        self.assertEqual(row['uncertainty']['development_station']['n'],10)
        self.assertAlmostEqual(row['uncertainty']['development_station']['mae'],100000)
        self.assertAlmostEqual(row['uncertainty']['development_station']['mean_signed_error_jpy_m2'],-100000)
        self.assertIn('not current-fit calibration',row['uncertainty']['evidence'])

if __name__=='__main__':unittest.main()
