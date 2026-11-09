import io
import csv
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from japan_housing_liquidity_lab import web_adapter as ui, competitiveness, listings
from japan_housing_liquidity_lab import web_presentation as display, opportunity

ROOT=Path(__file__).resolve().parents[1]


class AdapterTests(unittest.TestCase):
    def query(self, **kw):
        values=dict(city='架空区',town='',station='架空駅',walk=10,area=70,year=2005,age=None,
                    layout='2LDK',structure='RC',price_man=6000,reference='2026-11-08')
        return ui.home_query(**(values|kw))
    def test_units_age_and_invalid_values(self):
        q=self.query(year=None,age=21)
        self.assertEqual(q['asking_price_jpy'],60000000)
        self.assertEqual(q['建築年'],'2005年')
        self.assertEqual(float(q['面積（㎡）']),70)
        for change in [dict(area=0),dict(price_man=float('nan')),dict(year=2027),dict(age=20),dict(station=''),dict(year=None,age=None),dict(walk=-1)]:
            with self.assertRaises(ValueError): self.query(**change)
    def test_existing_price_result_identical(self):
        b,df=ui.demo();q=self.query()
        self.assertEqual(ui.analyze_home(b,df,q),competitiveness.assess(b,q))
    def test_opportunity_methods_and_small_sample(self):
        b,df=ui.demo();q=self.query(town='存在しない町')
        r=ui.analyze_home(b,df,q,True)
        self.assertEqual(r['comparable_n'],0)
        self.assertEqual(len(r['methods']),5)
        self.assertTrue(all(v['lower_price_record_fraction'] is None for v in r['methods'].values()))
        self.assertFalse(r['uncertainty']['calibrated'])
    def test_budget_support_and_unknown_transport(self):
        _,df=ui.demo()
        q=dict(reference_date='2026-11-08',history_start='2025Q1',history_end='2026Q2',budget_max_jpy=1,transport_modes=['private_car','bicycle','mixed'])
        r=ui.budget(df,q,'2026-11-08')
        self.assertEqual(r['matched_n'],0)
        self.assertTrue(all(x['n']==0 and x['area_median'] is None for x in r['regions']))
        self.assertIsNone(r['commute']['door_to_door_minutes'])
    def test_missing_real_data(self):
        with tempfile.TemporaryDirectory() as folder:
            for need in ['home','location']:
                with self.assertRaises(ValueError): ui.load_real(folder,need)
    def test_snapshots_restore_export_and_isolation(self):
        args=dict(source='A',listing_id='1',price_man=6000,observed='2026-11-08T12:00:00+09:00',status='present',evidence='SYNTHETIC',rights_evidence='SYNTHETIC',synthetic=True)
        b=ui.manual_batch(**args);one=ui.append_batches([],[b]);empty=[]
        two=ui.append_batches(one,[ui.manual_batch(**(args|dict(price_man=5900,observed='2026-11-09T12:00:00+09:00')))])
        self.assertEqual(len(one),1);self.assertEqual(empty,[])
        self.assertEqual(len(ui.append_batches(two,[two[-1]])),2)
        with zipfile.ZipFile(io.BytesIO(ui.journal_zip(two))) as z:
            restored=ui.import_bytes('journal.json',z.read('journal.json'))
            self.assertIn('events.csv',z.namelist())
        self.assertEqual(ui.append_batches([],restored),two)
        self.assertTrue(any(e['kind']=='price_down' for e in listings.replay(two)['events']))
    def test_cross_platform_and_coverage(self):
        args=dict(source='A',listing_id='1',price_man=6000,observed='2026-11-08T12:00:00+09:00',status='present',evidence='SYNTHETIC',rights_evidence='SYNTHETIC',synthetic=True,property_id='home')
        one=ui.append_batches([],[ui.manual_batch(**args)])
        with self.assertRaises(ValueError): ui.append_batches(one,[ui.manual_batch(**(args|dict(source='B')))])
        two=ui.append_batches(one,[ui.manual_batch(**(args|dict(source='B',match_evidence='SYNTHETIC verified dwelling')))])
        failed=ui.manual_batch(**(args|dict(status='failed',observed='2026-11-09T12:00:00+09:00')))
        two=ui.append_batches(two,[failed]);self.assertFalse(any(e['kind']=='source_disappearance' for e in listings.replay(two)['events']))
        missing=ui.manual_batch(**(args|dict(status='missing',observed='2026-11-10T12:00:00+09:00')))
        self.assertEqual(listings.replay(ui.append_batches(two,[missing]))['properties'][0]['state'],'partial_disappearance')
    def test_csv_import_and_upload_limit(self):
        content=(ROOT/'examples/listing-tracking/03-records.csv').read_bytes()
        meta=(ROOT/'examples/listing-tracking/03-metadata.json').read_bytes()
        self.assertEqual(ui.import_bytes('x.csv',content,meta)[0]['data_kind'],'synthetic')
        with self.assertRaises(ValueError): ui.import_bytes('x.json',b' '*2_000_001)

    def test_readable_formats_and_preserved_method_values(self):
        self.assertEqual(display.percent(.65),'65%')
        self.assertEqual(display.percent(0),'0%')
        self.assertEqual(display.percent(1),'100%')
        self.assertEqual(display.percent(None),'算出保留')
        self.assertEqual(display.unit_price(857142.857),'85.71 万円/㎡')
        b,df=ui.demo();r=ui.analyze_home(b,df,self.query(),True)
        before=json.dumps(r,sort_keys=True)
        rows=display.method_rows(r)
        self.assertEqual(len(rows),5)
        self.assertTrue(all('%' in x['低価格記録割合'] for x in rows))
        self.assertEqual(before,json.dumps(r,sort_keys=True))
    def test_abstention_reasons_specific_to_sample_and_demo(self):
        b,df=ui.demo();q=self.query(town='存在しない町')
        r=ui.analyze_home(b,df,q,True)
        reasons=display.reasons(r,True,False)
        self.assertTrue(any('0件' in x and '最低10件' in x for x in reasons))
        self.assertFalse(any('合成デモ' in x for x in reasons))
        self.assertIn('合成デモ',display.reasons(r,True,True)[0])

    def test_hostile_csv_and_nested_json_are_user_errors(self):
        b=ui.manual_batch('SYNTHETIC','1',1,'2026-11-09T00:00:00Z','present','SYNTHETIC','SYNTHETIC',True)
        meta=json.dumps({k:v for k,v in b.items() if k!='records'}).encode()
        with self.assertRaises(ValueError): ui.import_bytes('x.csv',('listing_id,evidence\nx,'+'a'*150000).encode(),meta)
        with self.assertRaises(ValueError): ui.import_bytes('x.json',b'['*2000+b']'*2000)

    def test_download_csv_formula_guard_keeps_exact_json(self):
        b=ui.manual_batch('=1+1','@SUM(1)',1,'2026-11-09T00:00:00Z','present','SYNTHETIC','SYNTHETIC',True)
        with zipfile.ZipFile(io.BytesIO(ui.journal_zip([b]))) as z:
            rows=list(csv.DictReader(io.StringIO(z.read('listings.csv').decode('utf-8-sig'))))
            self.assertEqual(rows[0]['source'],"'=1+1")
            self.assertEqual(rows[0]['listing_id'],"'@SUM(1)")
            self.assertEqual(ui.import_bytes('journal.json',z.read('journal.json')),[b])


class PageTests(unittest.TestCase):
    def test_mode_switch_does_not_carry_tracking_consent_or_attributes(self):
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ,{'JHLL_ENABLE_REAL':'1'}):
            a=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=30).run()
            a.sidebar.radio[1].set_value('掲載追跡').run()
            next(x for x in a.text_input if x.label=='町名').set_value('架空専用町')
            a.checkbox[0].check()
            a.sidebar.radio[0].set_value('ローカル実データ').run()
            self.assertFalse(a.exception)
            self.assertFalse(a.checkbox[0].value)
            self.assertEqual(next(x for x in a.text_input if x.label=='町名').value,'')
            self.assertIsNone(next(x for x in a.number_input if x.label=='観測価格（万円）').value)
            self.assertTrue(any('ローカル実データ' in x.value for x in a.main.info))
    def app(self):
        from streamlit.testing.v1 import AppTest
        config=patch.dict(os.environ,{'JHLL_ENABLE_REAL':'0','JHLL_LOCAL_SAVE':'0'})
        config.start();self.addCleanup(config.stop)
        a=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=30).run()
        self.assertFalse(a.exception)
        return a
    def test_price_page_submit(self):
        a=self.app();next(x for x in a.button if x.label=='分析する').click().run()
        self.assertFalse(a.exception)
        self.assertIn('判断できません',a.error[0].value)
        self.assertEqual(a.session_state['home_result'][2]['input']['asking_price_jpy'],60000000)
    def test_historical_page(self):
        a=self.app();a.sidebar.radio[1].set_value('過去の購入機会').run();next(x for x in a.button if x.label=='分析する').click().run()
        self.assertFalse(a.exception)
        self.assertEqual(len(a.session_state['home_result'][2]['result']['methods']),5)
        advanced=next(x for x in a.expander if x.label.startswith('高度な分析'))
        self.assertFalse(advanced.proto.expanded)
        table=advanced.dataframe[0].value
        self.assertEqual(len(table),5)
        self.assertIn('万円/㎡',table['単価中央値'].iloc[0])
        self.assertIn('%',table['低価格記録割合'].iloc[0])
        self.assertTrue(any('将来65%' in x.value for x in a.warning))
        self.assertTrue(any('同じ高さの棒' in x.value and '架空' in x.value for x in a.warning))
        self.assertTrue(any(x.label=='掲載単価を下回る過去記録の割合（未調整）' and '%' in x.value for x in a.metric))
    def test_budget_page(self):
        a=self.app();a.sidebar.radio[1].set_value('地域と予算').run();next(x for x in a.button if x.label=='地域を比較する').click().run()
        self.assertFalse(a.exception)
        self.assertGreater(a.session_state['budget_result'][1]['result']['matched_n'],0)
    def test_input_error(self):
        a=self.app();next(x for x in a.number_input if x.label=='専有面積（㎡）').set_value(0.)
        next(x for x in a.button if x.label=='分析する').click().run();self.assertFalse(a.exception);self.assertTrue(a.error)
        self.assertNotIn('home_result',a.session_state)
    def test_tracking_and_two_sessions(self):
        a=self.app();a.sidebar.radio[1].set_value('掲載追跡').run()
        for label in ['観測の確認根拠（個人情報を除く参照ID）','利用・保管権利の根拠（参照ID）']:
            next(x for x in a.text_input if x.label==label).set_value('SYNTHETIC')
        a.checkbox[0].check();next(x for x in a.button if x.label=='観測を記録する').click().run()
        self.assertFalse(a.exception);self.assertEqual(len(a.session_state['journal_demo']),1)
        b=self.app();b.sidebar.radio[1].set_value('掲載追跡').run()
        self.assertNotIn('journal_demo',b.session_state)
    def test_real_missing_page(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'JHLL_ENABLE_REAL':'1','JHLL_DATA_ROOT':folder}):
            a=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=30).run()
            a.sidebar.radio[0].set_value('ローカル実データ').run()
            a.sidebar.radio[1].set_value('住宅価格分析').run()
            for label,value in [('市区町村','区'),('最寄駅','駅')]: next(x for x in a.text_input if x.label==label).set_value(value)
            for label,value in [('専有面積（㎡）',70.),('掲載総額（万円）',6000.),('建築年（西暦）',2005)]: next(x for x in a.number_input if x.label==label).set_value(value)
            next(x for x in a.button if x.label=='分析する').click().run();self.assertFalse(a.exception);self.assertTrue(a.error)
            self.assertNotIn('home_result',a.session_state)

    @unittest.skipUnless((ROOT/'reports/competitiveness-005-v2/reference.joblib').exists() and (ROOT/'reports/history-003-verified/merged_retained.csv').exists(), 'Local private artifacts not present')
    def test_real_existing_example_page_and_original_algorithm_parity(self):
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ,{'JHLL_ENABLE_REAL':'1','JHLL_DATA_ROOT':str(ROOT),'JHLL_LOCAL_SAVE':'0'}):
            a=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=60).run()
            a.sidebar.radio[0].set_value('ローカル実データ').run()
            a.sidebar.radio[1].set_value('住宅価格分析').run()
            for label,value in [('市区町村','世田谷区'),('最寄駅','三軒茶屋'),('間取り（不明は空欄）','２ＬＤＫ'),('構造（不明は空欄）','ＲＣ')]:
                next(x for x in a.text_input if x.label==label).set_value(value)
            for label,value in [('専有面積（㎡）',70.),('掲載総額（万円）',6000.),('建築年（西暦）',2005),('駅までの徒歩分（不明は空欄）',10)]:
                next(x for x in a.number_input if x.label==label).set_value(value)
            next(x for x in a.button if x.label=='分析する').click().run()
            self.assertFalse(a.exception)
            b,df,available=ui.load_real(ROOT,'home')
            payload=a.session_state['home_result'][2]
            self.assertEqual(payload['result'],competitiveness.assess(b,payload['input']))
            self.assertEqual(payload['result']['comparables']['n'],2)
            self.assertEqual(len(df),55652)
            a.sidebar.radio[1].set_value('過去の購入機会').run()
            next(x for x in a.button if x.label=='分析する').click().run()
            self.assertFalse(a.exception)
            payload=a.session_state['home_result'][2]
            expected,_=opportunity.analyze(b,df,payload['input'])
            self.assertEqual(payload['result'],expected)
            self.assertEqual(expected['comparable_n'],5)
            self.assertTrue(all(v['lower_price_record_fraction'] is None for v in expected['methods'].values()))
            self.assertTrue(any('5件' in x.value for x in a.markdown))

if __name__=='__main__': unittest.main()


