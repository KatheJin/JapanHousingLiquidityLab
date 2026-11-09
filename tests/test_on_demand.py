"""No live HTTP. PG tests use only dedicated jhll_test, existing synthetic fixtures."""
import json
import os
import unittest
from unittest.mock import patch
import sqlalchemy as sa
from japan_housing_liquidity_lab import on_demand as d,listing_pipeline as p
from japan_housing_liquidity_lab.pg_store import engine,PostgresStore
from tests import test_postgres as pg_tests
from tests.test_listing_pipeline import Fake,ENTRY,URL,URL2,DETAIL,listing
Q={'reference_date':'2026-11-10','asking_price_jpy':1000000,'市区町村名':'武蔵村山市','最寄駅：名称':'架空駅','面積（㎡）':'54','建築年':'2024年','間取り':'2LDK','建物の構造':'','最寄駅：距離（分）':'10'}

class MatchTests(unittest.TestCase):
    def test_price_not_used_and_unknown_walk_explicit(self):
        row=dict(municipality='武蔵村山市',station='架空駅',area_m2=54,built_year=2024,layout='2LDK',price_jpy=9999999999)
        self.assertTrue(d.matches(row,Q,2026))
        self.assertFalse(d.matches(row,Q|{'walk_tolerance_minutes':5},2026))
        self.assertTrue(d.matches(row|{'walk_minutes':12},Q|{'walk_tolerance_minutes':5},2026))
        self.assertFalse(d.matches(row|{'area_m2':200},Q,2026))
    def test_station_priority_no_price_exclusion(self):
        html=listing((URL,URL2),2).replace('住宅</a>','住宅</a>',1)
        html=html.replace('nc_20179967/?fmlg=test">住宅','nc_20179967/?fmlg=test">架空駅 2LDK')
        links,_,_=d.PrioritizedDiscovery(Q).discover(html,ENTRY,ENTRY)
        self.assertEqual(len(links),2);self.assertEqual(next(iter(links)), '20179967')

    def test_card_fields_units_unknown_and_bus(self):
        from bs4 import BeautifulSoup
        html='<dl><dt>専有面積</dt><dd>５４.３４m <sup>2</sup>（壁芯）</dd><dt>築年月</dt><dd>2024年5月</dd><dt>間取り</dt><dd>２ＬＤＫ</dd><dt>沿線・駅</dt><dd>線「架空駅」バス10分 歩3分</dd></dl>'
        row,raw=d.card_fields(BeautifulSoup(html,'html.parser'))
        self.assertEqual(row['area_m2'],54.34);self.assertEqual(row['built_year'],2024)
        self.assertEqual(row['layout'],'2LDK');self.assertNotIn('walk_minutes',row)
        self.assertTrue(d.relaxed({},Q,2026,partial=True));self.assertFalse(d.relaxed({},Q,2026))
    def test_strict_approximate_disjoint_and_reasons(self):
        row=dict(municipality='武蔵村山市',station='別駅',area_m2=68,built_year=2010,layout='2DK',structure='SRC',price_jpy=9999999999)
        self.assertFalse(d.matches(row,Q,2026));self.assertTrue(d.relaxed(row,Q,2026))
        reasons=d.differences(row,Q)
        self.assertIn('面積が±20%の範囲外',reasons);self.assertIn('駅が異なる／不明',reasons)
        self.assertFalse(d.relaxed(row|{'layout':'3LDK'},Q,2026))
    def test_card_prefilter_keeps_unknown_and_no_price_test(self):
        html=listing((URL,URL2),2).replace('住宅</a>','住宅</a><dl><dt>専有面積</dt><dd>500m2</dd></dl>',1)
        adapter=d.PrioritizedDiscovery(Q);links,_,total=adapter.discover(html,ENTRY,ENTRY)
        self.assertEqual(total,2);self.assertEqual(len(links),2)
        self.assertFalse(adapter.should_fetch('20179966'));self.assertTrue(adapter.should_fetch('20179967'))
    def test_pause_interrupts_shared_throttle_before_http(self):
        from unittest.mock import MagicMock
        store=MagicMock();store.db.execute.return_value.fetchone.return_value=[100.0]
        client=p.PublicHTTP(store,'suumo','synthetic');client.robot=MagicMock();client.robot.can_fetch.return_value=True
        stopped=[False];client.cancel_check=lambda:stopped[0]
        def sleep(_):stopped[0]=True
        with patch.object(p.time,'time',return_value=100.0),patch.object(p.time,'sleep',side_effect=sleep),patch.object(p,'Client') as network:
            with self.assertRaises(p.CollectionPaused):client.get(URL)
            network.assert_not_called()

    def test_server_endpoint_not_used_or_robots_bypassed(self):
        html=listing()+'<form action="/jj/bukken/ichiran/JJ012FC001/"><select name="mb"><option>20</option></select></form>'
        links,nxt,_=d.PrioritizedDiscovery(Q).discover(html,ENTRY,ENTRY)
        self.assertIsNone(nxt);self.assertEqual(list(links.values()),[URL])

@unittest.skipUnless(os.environ.get('JHLL_TEST_DATABASE_URL'),'Dedicated PG test DB not configured')
class DemandPGTests(unittest.TestCase):
    def setUp(self):
        pg_tests.PostgresTests.setUp(self)
        self.entry_patch=patch.object(d,'_entry',return_value=ENTRY);self.entry_patch.start();self.addCleanup(self.entry_patch.stop)
    def run_task(self,**kw):
        task=d.create(Q,**kw);return task,d.execute(task,transport=Fake)
    def test_task_dedup_snapshots_and_repeat_no_network(self):
        task,r=self.run_task()
        self.assertEqual(r['status'],'completed');self.assertEqual(r['result']['matched_n'],1)
        self.assertEqual(d.create(Q),task);self.assertEqual(d.create(Q|{'地区名':'','面積（㎡）':'54.0','最寄駅：距離（分）':'10.0'}),task);calls=list(Fake.calls)
        d.execute(task,transport=Fake);self.assertEqual(Fake.calls,calls)
        self.assertFalse(r['result']['asking_price_filter_used'])
    def test_budget_partial_and_long_run_untouched(self):
        s=PostgresStore()
        with s.db:s.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',('long','suumo',ENTRY,p.scope_fingerprint('suumo',ENTRY),'running',p.now(),p.now(),None))
        s.close();Fake.pages[ENTRY]=listing((URL,URL2),2);Fake.pages[URL2]=DETAIL
        task,r=self.run_task(max_details=1)
        self.assertEqual(r['status'],'partial');self.assertEqual(r['result']['matched_n'],1)
        e=engine()
        with e.connect() as c:self.assertEqual(c.execute(sa.text("SELECT status FROM runs WHERE id='long'")).scalar(),'running')
        e.dispose()
    def test_global_plan_lock_blocks_any_http(self):
        e=engine();c=e.connect();c.execute(sa.text('SELECT pg_advisory_lock(12012002)'));c.commit()
        try:
            task,r=self.run_task();self.assertEqual(r['status'],'waiting_central_worker');self.assertEqual(Fake.calls,[])
        finally:c.close();e.dispose()
    def test_failed_page_resume_and_no_disappearance(self):
        Fake.pages[ENTRY]=p.StopCollection('HTTP_503');task,r=self.run_task()
        self.assertEqual(r['status'],'failed');self.assertEqual(r['result']['matched_n'],0)
        with patch.object(d,'start') as start:
            queued=d.retry(task);self.assertEqual(queued['status'],'queued');start.assert_called_once_with(task)
        Fake.pages[ENTRY]=listing()
        r=d.execute(task,transport=Fake)
        self.assertEqual(r['status'],'completed');self.assertEqual(r['result']['matched_n'],1)
        e=engine()
        with e.connect() as c:self.assertEqual(c.execute(sa.text("SELECT count(*) FROM events WHERE body_json->>'kind' LIKE '%disappear%' ")).scalar(),0)
        e.dispose()
    def test_interrupt_reuses_same_run_and_does_not_repeat_completed_details(self):
        Fake.pages[ENTRY]=listing((URL,URL2),2);Fake.pages[URL2]=KeyboardInterrupt()
        task=d.create(Q)
        with self.assertRaises(KeyboardInterrupt):d.execute(task,transport=Fake)
        old=d.progress(task)['progress']['id'];Fake.pages[URL2]=DETAIL;Fake.calls=[]
        with patch.object(d,'start'):d.retry(task)
        r=d.execute(task,transport=Fake)
        self.assertEqual(r['progress']['id'],old);self.assertNotIn(URL,Fake.calls)
        self.assertEqual(r['result']['matched_n'],2)
    def test_all_pages_ranked_before_detail_budget(self):
        nxt=ENTRY+'?page=2'
        Fake.pages[ENTRY]=listing((URL,),2,nxt).replace('住宅</a>','別駅 2DK</a><dl><dt>専有面積</dt><dd>68m2</dd><dt>間取り</dt><dd>2DK</dd><dt>築年月</dt><dd>2010年1月</dd></dl>')
        Fake.pages[nxt]=listing((URL2,),2).replace('住宅</a>','架空駅 2LDK</a><dl><dt>専有面積</dt><dd>54m2</dd><dt>間取り</dt><dd>2LDK</dd><dt>築年月</dt><dd>2024年1月</dd></dl>');Fake.pages[URL2]=DETAIL
        task,r=self.run_task(max_pages=2,max_details=1)
        self.assertEqual(r['result']['pages_scanned'],2);self.assertEqual(r['result']['candidate_n'],2)
        self.assertEqual(r['result']['matched_n'],1);self.assertEqual(r['result']['records'][0]['listing_id'],'20179967')
        self.assertNotIn(URL,Fake.calls);self.assertIn(URL2,Fake.calls)
    def test_excluded_cards_preserve_discovery_and_counts(self):
        Fake.pages[ENTRY]=listing((URL,URL2),2).replace('住宅</a>','住宅</a><dl><dt>専有面積</dt><dd>500m2</dd></dl>',1);Fake.pages[URL2]=DETAIL
        task,r=self.run_task()
        result=r['result'];self.assertEqual(result['discovered_ids'],2);self.assertEqual(result['candidate_n'],1)
        self.assertEqual(result['prefilter_excluded_n'],1);self.assertNotIn(URL,Fake.calls)
        self.assertEqual(result['observation_counts']['newly_discovered'],1)
        self.assertTrue(result['list_traversal_complete'])
    def test_old_cache_does_not_count_as_reconfirmed(self):
        task,r=self.run_task();Fake.calls=[]
        second=d.create(Q|{'asking_price_jpy':2000000})
        result=d.execute(second,transport=Fake)['result']
        self.assertEqual(result['matched_n'],0);self.assertEqual(result['successful_details'],0)
        self.assertEqual(result['old_database_match_n'],1);self.assertEqual(result['old_database_records'][0]['observation_kind'],'old_database')
        self.assertNotIn(URL,Fake.calls)
    def test_redirect_retains_successes_and_does_not_follow_or_disappear(self):
        Fake.pages[ENTRY]=listing((URL,URL2),2);Fake.pages[URL2]=p.StopCollection('HTTP_301')
        task,r=self.run_task()
        self.assertEqual(r['status'],'failed');self.assertEqual(r['result']['matched_n'],1)
        self.assertEqual(r['result']['failed_details'][0]['error'],'HTTP_301')
        self.assertEqual(r['result']['unverified_or_stale_ids'],1)
        self.assertEqual(Fake.calls,[ENTRY,URL,URL2])
        e=engine()
        with e.connect() as c:self.assertEqual(c.execute(sa.text("SELECT count(*) FROM events WHERE body_json->>'kind' LIKE '%disappear%'")).scalar(),0)
        e.dispose()

    def test_pause_queued_and_waiting_sends_no_http(self):
        task=d.create(Q)
        self.assertEqual(d.pause(task)['status'],'paused')
        self.assertEqual(d.execute(task,transport=Fake)['status'],'paused')
        self.assertEqual(Fake.calls,[])
        with patch.object(d,'start'):d.retry(task)
        self.assertEqual(d.execute(task,transport=Fake)['result']['matched_n'],1)
    def test_cooperative_pause_retains_snapshot_and_live_result_then_resumes(self):
        Fake.pages[ENTRY]=listing((URL,URL2),2);Fake.pages[URL2]=DETAIL
        task=d.create(Q);live=[]
        class PausingFake(Fake):
            def get(self,url,*args):
                body=super().get(url,*args)
                if url==URL: d.pause(task)
                return body
        r=d.execute(task,transport=PausingFake)
        self.assertEqual(r['status'],'paused');self.assertEqual(r['result']['matched_n'],1)
        old=r['progress']['id'];self.assertNotIn(URL2,Fake.calls)
        # A freshly queried running view exposes committed results, not old cached output.
        payload=d._read(task)['payload'];d._update(task,'queued',payload);d._update(task,'running',payload)
        live=d.progress(task);self.assertTrue(live['result']['live_partial']);self.assertEqual(live['result']['matched_n'],1)
        Fake.calls=[]
        with patch.object(d,'start'):d.retry(task)
        result=d.execute(task,transport=Fake)
        self.assertEqual(result['progress']['id'],old);self.assertEqual(result['result']['matched_n'],2)
        self.assertNotIn(URL,Fake.calls)
    def test_pause_request_survives_card_progress_write(self):
        task=d.create(Q);payload=d._read(task)['payload'];d._update(task,'running',payload)
        self.assertEqual(d.pause(task)['status'],'pause_requested')
        payload['cards']={'test':{'eligible':True}};d._update(task,'running',payload)
        row=d._read(task);self.assertEqual(row['status'],'pause_requested');self.assertIn('test',row['payload']['cards'])

    def test_approximate_not_added_to_strict(self):
        Fake.pages[URL]=DETAIL.replace('架空駅','別駅')
        _,r=self.run_task();result=r['result']
        self.assertEqual(result['matched_n'],0);self.assertEqual(result['approximate_n'],1)
        self.assertEqual(result['approximate_records'][0]['match_tier'],'approximate')
        self.assertIn('駅が異なる／不明',result['approximate_records'][0]['relaxed_conditions'])

class DemandPageTests(unittest.TestCase):
    def test_shared_subject_form_and_no_network_in_ui_test(self):
        from streamlit.testing.v1 import AppTest
        from pathlib import Path
        record=dict(listing_id='SYNTHETIC',price_jpy=42000000,unit_price_jpy_m2=42000000/54,area_m2=54,age=2,station='架空駅',walk_minutes=10,layout='2LDK',url='https://example.test/',observed_at='2026-11-10T00:00:00+00:00')
        response=dict(status='completed',progress={},error=None,result=dict(matched_n=1,discovered_ids=1,unverified_or_stale_ids=0,checked_at='SYNTHETIC',records=[record]))
        with patch.dict(os.environ,{'JHLL_ENABLE_REAL':'1','JHLL_ENABLE_DEMO':'0'}),patch.object(d,'create',return_value='a'*32) as create,patch.object(d,'start') as start,patch.object(d,'progress',return_value=response),patch('japan_housing_liquidity_lab.pg_admin.local_environment'):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
            app.session_state['housing_subject']=dict(Q)
            app.sidebar.radio[1].set_value('現在の類似掲載').run()
            self.assertEqual(next(x for x in app.text_input if x.label=='検索対象の駅').value,'架空駅')
            next(x for x in app.checkbox if x.label=='ローカル私的利用と限定HTTP取得を確認').check()
            next(x for x in app.button if x.label=='限定した実掲載検索を開始').click().run()
            self.assertFalse(app.exception);self.assertEqual(create.call_count,1);self.assertEqual(start.call_count,1)
            self.assertEqual(create.call_args[0][0]['asking_price_jpy'],Q['asking_price_jpy'])
            self.assertEqual(len(app.dataframe[0].value),1)

if __name__=='__main__':unittest.main()
