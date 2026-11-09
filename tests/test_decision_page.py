"""Unified UI checks use synthetic fixtures or installed historical data, never live HTTP."""
from pathlib import Path
from datetime import date
import os
import unittest
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
from japan_housing_liquidity_lab import decision_page as ui

ROOT=Path(__file__).resolve().parents[1]
Q={'reference_date':'2026-11-10','asking_price_jpy':30000000,'市区町村名':'世田谷区','地区名':'','最寄駅：名称':'三軒茶屋','最寄駅：距離（分）':'10','面積（㎡）':'25','建築年':'2005年','間取り':'1K','建物の構造':'RC'}
SOURCE='from japan_housing_liquidity_lab.decision_page import render\nrender()'
ACTUAL_RENDER_TASK=ui.on_demand_page.render_task


def fixture():
    rows=[dict(source_file='SYNTHETIC.csv',source_row=str(i+2),record_id='SYNTHETIC-'+str(i),quarter='2023Q1',**{k:v for k,v in Q.items() if k not in ['reference_date','asking_price_jpy']},**{'取引価格（総額）':'30000000','unit_price_jpy_m2':'1200000'}) for i in range(2)]
    meta=dict(available_on='2026-11-08',data_sha256='SYNTHETIC',source='SYNTHETIC test fixture',coverage=['2023Q1'],calendar_end='2023Q1',records=2,publication_date=None)
    target=dict(municipality='世田谷区',station='三軒茶屋',status='research_candidate',support_n=30,reference_unit_price_jpy_m2=None,relative_gap_pct=None,diagnostic_reference_unit_price_jpy_m2=1200000,diagnostic_relative_gap_pct=0,uncertainty={'calibrated':False},reasons=[])
    profile=dict(status='descriptive_only',sample_n=30,valid_price_n=30,missing_or_invalid_price_n=0,period_start='2023Q1',period_end='2026Q2',configured_period=['2023Q1','2026Q2'],raw_unit_price_jpy_m2=dict(q1=1000000,median=1200000,q3=1400000))
    target.update(recent_support_n=12,historical_joint_profile=profile)
    candidate=target|dict(evidence_group='multi_model_agreement',model_agreement=True,diagnostic_gap_spread_percentage_points=3.0,diagnostic_by_method={'ridge':{'relative_gap_pct':5.0},'hgb':{'relative_gap_pct':8.0}},municipality='試験区',station='試験駅',support_n=25,diagnostic_reference_unit_price_jpy_m2=1260000,diagnostic_relative_gap_pct=5.0,rank_stability={'min_rank':1,'max_rank':8})
    result=dict(status='research_only',target=target,candidates=[candidate],common_attributes=dict(area_m2=25,construction_year=2005,age_at_reference=21,layout='1K',structure='RC',walk_minutes=10,reference_quarter='2026Q2'),reference_quarter='2026Q2',warnings=['SYNTHETIC test-only research warning'])
    return pd.DataFrame(rows),meta,result


class UnifiedPageTests(unittest.TestCase):
    def setUp(self):
        ui.history_resources.clear();ui.area_resources.clear()
        df,meta,self.regions=fixture()
        for name,options in [('history_resources',dict(return_value=(df,meta))),('area_resources',dict(return_value={})),('compare_areas',dict(return_value=self.regions))]:
            p=patch.object(ui,name,**options);mock=p.start();self.addCleanup(p.stop);setattr(self,name,mock)
        for name in ['create','start']:
            p=patch.object(ui.demand,name,return_value='a'*32);mock=p.start();self.addCleanup(p.stop);setattr(self,name,mock)
        p=patch.object(ui.on_demand_page,'render_task');self.render_task=p.start();self.addCleanup(p.stop)
        p=patch('japan_housing_liquidity_lab.pg_admin.local_environment');p.start();self.addCleanup(p.stop)
    def page(self,subject=Q):
        app=AppTest.from_string(SOURCE,default_timeout=30)
        if subject:app.session_state['housing_subject']=dict(subject)
        return app.run()
    def submit(self,app):
        next(x for x in app.button if x.label=='この住宅で歴史と地域を比較').click().run()
        self.assertFalse(app.exception)
        return app
    def test_one_subject_history_and_regions_no_initial_network(self):
        app=self.page();self.submit(app)
        self.assertEqual(app.session_state['decision_history']['comparable_n'],2)
        self.assertEqual(self.compare_areas.call_args[0][1],app.session_state['decision_subject'])
        self.assertEqual(app.session_state['decision_history']['query']['面積（㎡）'],'25.0')
        self.assertEqual(app.session_state['decision_regions']['target']['reference_unit_price_jpy_m2'],None)
        self.create.assert_not_called();self.start.assert_not_called()
        self.assertEqual(len(next(x for x in app.expander if x.label=='歴史的な成約明細を開く').dataframe[0].value),2)
    def test_consent_and_destination_preserve_original_subject(self):
        app=self.submit(self.page());before=dict(app.session_state['decision_subject'])
        next(x for x in app.button if x.label=='対象と同じ地域の掲載を調べる').click().run()
        self.create.assert_not_called()
        next(x for x in app.checkbox if x.label=='限定したSUUMO取得とローカル私的利用を確認').check()
        next(x for x in app.button if x.label=='選択した候補地域の掲載を調べる').click().run()
        self.assertFalse(app.exception)
        args,kwargs=self.create.call_args
        self.assertEqual(args[0],before)
        self.assertEqual(kwargs['destination'],{'municipality':'試験区','station':'試験駅'})
        self.assertEqual(app.session_state['housing_subject'],before)
        self.render_task.assert_called_with('a'*32,key_prefix='decision_candidate_')
    def test_model_failure_does_not_block_history_or_current(self):
        self.area_resources.side_effect=OSError('private model unavailable')
        app=self.submit(self.page());self.assertEqual(app.session_state['decision_history']['comparable_n'],2)
        self.assertTrue(app.session_state['decision_region_error'])
        next(x for x in app.checkbox if x.label=='限定したSUUMO取得とローカル私的利用を確認').check()
        next(x for x in app.button if x.label=='対象と同じ地域の掲載を調べる').click().run()
        self.create.assert_called_once();self.assertIsNone(self.create.call_args.kwargs['destination'])
    def test_history_failure_does_not_block_other_panels(self):
        self.history_resources.side_effect=OSError('private data unavailable')
        app=self.submit(self.page());self.assertTrue(app.session_state['decision_history_error'])
        self.assertEqual(app.session_state['decision_regions']['status'],'research_only')
        self.assertTrue(any(x.label=='対象と同じ地域の掲載を調べる' for x in app.button))
    def test_invalid_input_and_independent_session(self):
        app=self.submit(self.page(subject=None));self.assertTrue(app.error)
        self.compare_areas.assert_not_called();self.create.assert_not_called()
        app=self.submit(self.page());other=self.page(subject=None)
        self.assertNotIn('decision_subject',other.session_state);self.assertNotIn('decision_history',other.session_state)
    def test_diagnostic_percent_units_and_unavailable_state(self):
        app=self.submit(self.page())
        exp=next(x for x in app.expander if x.label.startswith('研究用の標準化価格'))
        table=exp.dataframe[0].value
        self.assertEqual(table.iloc[1]['研究用差%'],5.0);self.assertEqual(table.iloc[1]['研究用単価万円/㎡'],126.0)
        self.compare_areas.return_value=dict(status='unavailable',target={},candidates=[],warnings=['不足'],reference_quarter='2026Q2',common_attributes={})
        self.submit(app);self.assertTrue(any('相近い価格水準を判断できません' in x.value for x in app.info))
        self.assertTrue(any(x.label=='対象と同じ地域の掲載を調べる' for x in app.button))


    def test_candidate_groups_raw_prices_and_no_candidate_fetch_on_select(self):
        base=self.regions['candidates'][0]
        self.regions['candidates']=[base|dict(evidence_group='model_disagreement',municipality='不一致区',station='不一致駅'),base|dict(evidence_group='insufficient_sample',municipality='不足区',station='不足駅',recent_support_n=3,model_agreement=True)]
        app=self.submit(self.page())
        markdown=' '.join(x.value for x in app.markdown)
        self.assertIn('複数モデルが近い価格水準を示す：0地域',markdown)
        self.assertIn('モデルによって判断が分かれる：1地域',markdown)
        self.assertIn('直近の比較記録が不足：1地域',markdown)
        tables=[x.value for x in app.dataframe if '原単価中央値（万円/㎡）' in x.value.columns]
        self.assertEqual(len(tables),2)
        self.assertEqual(tables[0].iloc[0]['原単価中央値（万円/㎡）'],'120.0')
        self.assertEqual(tables[0].iloc[0]['原単価中央50%（万円/㎡）'],'100.0～140.0')
        self.assertEqual(tables[0].iloc[0]['研究用標準化単価（万円/㎡）'],126.0)
        self.assertEqual(tables[0].iloc[0]['モデルによる対象との差'],'+5.0～+8.0%')
        self.assertEqual(tables[1].iloc[0]['直近の記録'],3)
        next(x for x in app.selectbox if x.label=='掲載を調べたい候補地域').select(1).run()
        self.assertFalse(app.exception);self.create.assert_not_called();self.start.assert_not_called()
        self.assertEqual(app.session_state['decision_subject']['最寄駅：名称'],'三軒茶屋')
        self.assertEqual([x.value for x in app.subheader][:3],['1. 歴史的な類似成約','2. 同じ地域の現在掲載','3. 価格水準の近い地域'])

    def test_database_failure_keeps_history_and_regions_and_hides_exception_details(self):
        self.create.side_effect=ConnectionError('PRIVATE_CONNECTION_STRING')
        app=self.submit(self.page())
        next(x for x in app.checkbox if x.label=='限定したSUUMO取得とローカル私的利用を確認').check()
        next(x for x in app.button if x.label=='対象と同じ地域の掲載を調べる').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['decision_history']['comparable_n'],2)
        self.assertEqual(app.session_state['decision_regions']['status'],'research_only')
        self.assertTrue(any('歴史・地域比較の結果は保持' in x.value for x in app.error))
        self.assertNotIn('PRIVATE_CONNECTION_STRING',' '.join(x.value for x in app.error))
        self.start.assert_not_called()

    def test_failed_partial_and_zero_listing_results_do_not_block_other_panels(self):
        self.render_task.side_effect=ACTUAL_RENDER_TASK
        result=dict(matched_n=0,approximate_n=0,records=[],approximate_records=[],old_database_records=[],discovered_ids=3,checked_at='2026-11-10T00:00:00Z',started_at='2026-11-09T23:59:00Z',elapsed_seconds=60,pages_scanned=1,pending_pages=1,pending_details=2,list_traversal_complete=False,run={'error':'HTTP 503'})
        payload=dict(status='partial',query=dict(Q),progress={},error=None,result=result)
        with patch.object(ui.demand,'progress',return_value=payload) as progress:
            app=self.submit(self.page())
            app.session_state['decision_tasks']={'target':{'task_id':'a'*32,'destination':{'municipality':'世田谷区','station':'三軒茶屋'}}}
            app.run();self.assertFalse(app.exception)
            self.assertTrue(any('在庫0' in x.value for x in app.warning))
            self.assertTrue(any('今回確認できませんでした' in x.value for x in app.info))
            self.assertEqual(app.session_state['decision_history']['comparable_n'],2)
            self.assertTrue(any(x.label=='選択した候補地域の掲載を調べる' for x in app.button))
            progress.return_value=payload|dict(status='failed',result=None,error='HTTP 503')
            app.run();self.assertFalse(app.exception)
            self.assertTrue(any('再開' in x.label for x in app.button))
            self.assertEqual(app.session_state['decision_regions']['status'],'research_only')
            self.create.assert_not_called();self.start.assert_not_called()

    def test_missing_raw_distribution_is_unknown_not_zero(self):
        self.assertEqual(ui.raw_profile_text(None),('表示不可','表示不可'))
        self.assertEqual(ui.raw_profile_text({'valid_price_n':6,'raw_unit_price_jpy_m2':{'q1':None,'median':None,'q3':None}}),('表示不可','表示不可'))
        self.regions['target']['historical_joint_profile']=dict(valid_price_n=6,raw_unit_price_jpy_m2=dict(q1=None,median=None,q3=None))
        app=self.submit(self.page())
        self.assertTrue(any('10件未満のため' in x.value for x in app.info))


@unittest.skipUnless((ROOT/'reports/task008-data/merged_retained.csv').exists(),'Private data not installed')
class RealUnifiedHistoryTests(unittest.TestCase):
    def test_real_sangenjaya_count_and_details_without_model_or_http(self):
        ui.history_resources.clear()
        with patch.dict(os.environ,{'JHLL_DATA_ROOT':str(ROOT)}),patch.object(ui,'area_resources',side_effect=OSError('No model for this isolation check')),patch.object(ui.demand,'start') as start:
            app=AppTest.from_string(SOURCE,default_timeout=120)
            app.session_state['housing_subject']=dict(Q);app.run()
            next(x for x in app.button if x.label=='この住宅で歴史と地域を比較').click().run()
            self.assertFalse(app.exception)
            result=app.session_state['decision_history'];self.assertEqual(result['comparable_n'],106)
            table=next(x for x in app.expander if x.label=='歴史的な成約明細を開く').dataframe[0].value
            self.assertEqual(len(table),106);self.assertEqual(table['成約四半期'].tolist(),[r['quarter'] for r in result['records']])
            self.assertEqual(result['cohort_counts'],{'expanded_2018_2022':66,'existing_2023_2026':40})
            self.assertTrue(all(r['adjustment_status']=='unavailable' for r in result['records']));start.assert_not_called()
        ui.history_resources.clear()

if __name__=='__main__':unittest.main()
