"""Real-data end-to-end checks are optional when private inputs are not installed."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from japan_housing_liquidity_lab import historical_query as h
from japan_housing_liquidity_lab.benchmark import norm
ROOT=Path(__file__).resolve().parents[1]
QUERY={'reference_date':'2026-11-10','asking_price_jpy':30000000,'市区町村名':'世田谷区','地区名':'','最寄駅：名称':'三軒茶屋','最寄駅：距離（分）':'10','面積（㎡）':'25','建築年':'2005年','間取り':'１Ｋ','建物の構造':'ＲＣ','history_start':'2018Q1','history_end':'2026Q2'}

@unittest.skipUnless((ROOT/'reports/task008-data/merged_retained.csv').exists(),'Private historical data not installed')
class RealHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df,cls.meta=h.load(ROOT);cls.result=h.search(cls.df,QUERY,cls.meta)
    def independent_rows(self):
        d=self.df;area=pd.to_numeric(d['面積（㎡）'],errors='coerce')
        by=pd.to_numeric(d['建築年'].map(norm).str.extract(r'^(\d{4})年?$',expand=False),errors='coerce')
        age=d.quarter.str[:4].astype(int)-by
        mask=d['市区町村名'].map(norm).eq('世田谷区')&d['最寄駅：名称'].map(norm).eq('三軒茶屋')&area.between(20,30)&age.between(11,31)&d['間取り'].map(norm).eq('1K')&d['建物の構造'].map(norm).eq('RC')
        return d.loc[mask]
    def test_actual_count_and_every_detail_match_source_independently(self):
        source=self.independent_rows();r=self.result
        self.assertGreater(len(source),0);self.assertEqual(r['comparable_n'],len(source))
        expected={(x.source_file,str(x.source_row)):x for x in source.itertuples(index=False)}
        for row in r['records']:
            key=(row['source_file'],row['source_row']);raw=source[(source.source_file==key[0])&(source.source_row.astype(str)==key[1])].iloc[0]
            self.assertEqual(row['quarter'],raw.quarter)
            self.assertEqual(row['construction_year'],raw['建築年'])
            self.assertEqual(row['station'],raw['最寄駅：名称'])
            self.assertEqual(row['layout'],raw['間取り']);self.assertEqual(row['area_m2'],float(raw['面積（㎡）']))
            self.assertAlmostEqual(row['raw_unit_price_jpy_m2'],float(raw['unit_price_jpy_m2']))
            self.assertAlmostEqual(row['age_at_trade'],int(raw.quarter[:4])-int(norm(raw['建築年']).removesuffix('年')))
            self.assertIsNone(row['time_adjusted_unit_price']);self.assertEqual(row['adjustment_status'],'unavailable')
        self.assertEqual(set(expected),{(r['source_file'],r['source_row']) for r in r['records']})
    def test_scope_extension_and_gates(self):
        r=h.search(self.df,QUERY,self.meta,mode='selected_locations',locations=[dict(municipality='世田谷区',station='三軒茶屋')])
        self.assertEqual(r['comparable_n'],self.result['comparable_n'])
        r=h.search(self.df,QUERY,self.meta,mode='municipality')
        self.assertGreaterEqual(r['comparable_n'],self.result['comparable_n'])
        self.assertFalse(r['adjustment']['diagnostics_used'])
        self.assertEqual(sum(r['cohort_counts'].values()),r['comparable_n'])
        with self.assertRaises(ValueError):h.search(self.df,QUERY|{'reference_date':'2020-01-01'},self.meta)
        with self.assertRaises(ValueError):h.search(self.df,QUERY,self.meta,mode='selected_locations')
    def test_real_streamlit_form_count_expanded_details_and_isolation(self):
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ,{'JHLL_DATA_ROOT':str(ROOT),'JHLL_ENABLE_REAL':'1','JHLL_ENABLE_DEMO':'0'}):
            app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=120).run()
            self.assertEqual(app.sidebar.radio[0].value,'ローカル実データ')
            app.sidebar.radio[1].set_value('歴史成約分析').run()
            for label,v in [('対象の市区町村','世田谷区'),('対象の最寄駅','三軒茶屋'),('対象の間取り（任意）','１Ｋ'),('対象の構造（任意）','ＲＣ')]:next(x for x in app.text_input if x.label==label).set_value(v)
            for label,v in [('対象の専有面積（㎡）',25.),('対象の建築年',2005),('対象の掲載価格（万円）',3000.)]:next(x for x in app.number_input if x.label==label).set_value(v)
            from datetime import date
            app.date_input[0].set_value(date(2026,11,10))
            next(x for x in app.button if x.label=='歴史取引を検索').click().run()
            self.assertFalse(app.exception)
            r=app.session_state['phase3_result'];self.assertEqual(r['comparable_n'],len(self.independent_rows()))
            exp=next(x for x in app.expander if x.label=='実際の比較取引明細（全件）')
            table=exp.dataframe[0].value
            self.assertEqual(len(table),r['comparable_n'])
            self.assertEqual(table['未調整単価円/㎡'].tolist(),[x['raw_unit_price_jpy_m2'] for x in r['records']])
            self.assertEqual(table['取引四半期'].tolist(),[x['quarter'] for x in r['records']])
            self.assertEqual(table.columns[:2].tolist(),['取引四半期','成約総額円（原表記）'])
            self.assertGreater(table.columns.get_loc('record_id'),table.columns.get_loc('駅距離原表記'))
            self.assertEqual(len(app.get('download_button')),2)
            other=AppTest.from_file(str(ROOT/'streamlit_app.py')).run()
            self.assertNotIn('phase3_result',other.session_state)

class HistoryPolishTests(unittest.TestCase):
    def fixture(self):
        rows=[]
        for i,walk in enumerate(['10','','30分～60分']):
            rows.append(dict(source_file='synthetic.csv',source_row=str(i+2),record_id=str(i),quarter='2023Q1',**{'市区町村名':'区','地区名':'町','最寄駅：名称':'駅','最寄駅：距離（分）':walk,'面積（㎡）':'25','建築年':'2005年','間取り':'1K','建物の構造':'RC','取引価格（総額）':'30000000','unit_price_jpy_m2':'1200000'}))
        return pd.DataFrame(rows),dict(available_on='2026-01-01',data_sha256='SYNTHETIC',coverage=['2023Q1','2023Q3'],published_quarters=['2023Q1','2023Q2','2023Q3'],known_unpublished_quarters=['2023Q4'],calendar_end='2023Q4')
    def test_optional_walk_unknown_and_interval_not_midpoint(self):
        df,meta=self.fixture();q=QUERY|{'市区町村名':'区','最寄駅：名称':'駅','history_start':'2023Q1','history_end':'2023Q3'}
        self.assertEqual(h.search(df,q,meta)['comparable_n'],3)
        r=h.search(df,q|{'walk_tolerance_minutes':5},meta)
        self.assertEqual(r['comparable_n'],1);self.assertEqual(r['walk_filter']['unknown_n'],1)
        r=h.search(df,q|{'最寄駅：距離（分）':'45','walk_tolerance_minutes':0},meta)
        self.assertEqual(r['comparable_n'],0);self.assertEqual(r['walk_filter']['interval_overlap_only_n'],1)
    def test_quarter_acquired_zero_missing_and_not_published(self):
        df,meta=self.fixture();r=h.search(df,QUERY|{'市区町村名':'区','最寄駅：名称':'駅','history_start':'2023Q1','history_end':'2023Q4'},meta)
        states={x['quarter']:x for x in r['quarterly']}
        self.assertEqual(states['2023Q1']['state'],'acquired_matches')
        self.assertEqual(states['2023Q2']['state'],'not_acquired');self.assertIsNone(states['2023Q2']['n'])
        self.assertEqual(states['2023Q3']['state'],'acquired_zero');self.assertEqual(states['2023Q3']['n'],0)
        self.assertEqual(states['2023Q4']['state'],'not_published');self.assertIsNone(states['2023Q4']['n'])
    def test_unknown_walk_requires_target_value_if_enabled(self):
        df,meta=self.fixture()
        with self.assertRaises(ValueError):h.search(df,QUERY|{'最寄駅：距離（分）':'','walk_tolerance_minutes':5},meta)

class HistoryUnavailableTests(unittest.TestCase):
    def test_missing_data_real_page_has_no_demo_fallback(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'JHLL_DATA_ROOT':folder,'JHLL_ENABLE_REAL':'1','JHLL_ENABLE_DEMO':'0'}):
            app=AppTest.from_file(str(ROOT/'streamlit_app.py')).run()
            app.sidebar.radio[1].set_value('歴史成約分析').run()
            self.assertFalse(app.exception);self.assertTrue(app.error)
            self.assertNotIn('phase3_result',app.session_state)
if __name__=='__main__':unittest.main()
