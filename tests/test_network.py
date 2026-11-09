import gzip
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
from japan_housing_liquidity_lab.net_http import Client,NetworkError,save
from japan_housing_liquidity_lab import mock_site,crawler,listings,mlit_client


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.state=self.root/'site.json';self.s=mock_site.initial();save(self.state,self.s)
        self.http=mock_site.server(self.state);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.origin=f'http://127.0.0.1:{self.http.server_port}'
    def tearDown(self): self.http.shutdown();self.http.server_close();self.thread.join();self.tmp.cleanup()
    def client(self,**kw): return Client(self.origin,self.root/'cache.json',interval=0,backoff=0,**kw)
    def scan(self): return crawler.crawl(self.origin,self.root/'crawler',self.root/'journal.json',interval=0,backoff=0)
    def update(self): save(self.state,self.s)
    def test_real_html_pagination_and_conditional_restart(self):
        r=self.scan();self.assertEqual(r['records'],5);self.assertEqual(r['completeness'],'complete');self.assertEqual(r['pages'],3)
        r=self.scan();self.assertGreater(sum(x['status']==304 for x in json.loads(next((self.root/'crawler').glob(r['batch_id']+'-run.json')).read_text(encoding='utf-8'))['requests']),0)
        self.assertEqual(len(listings.report(self.root/'journal.json')['listings']),5)
    def test_price_absence_reappearance_and_partial(self):
        self.scan();self.s['generation']+=1;self.s['rows'][0]['price_jpy']-=1000000;self.update();self.scan()
        self.s['faults']={'/listings?page=2':[{'status':503}]*3};self.update();r=self.scan();self.assertEqual(r['completeness'],'partial')
        self.assertFalse(any(e['kind']=='listing_disappeared' for e in listings.report(self.root/'journal.json')['events']))
        self.s['faults']={};row=self.s['rows'].pop(0);self.s['generation']+=1;self.update();self.scan()
        self.s['rows'].append(row);self.s['generation']+=1;self.update();self.scan()
        kinds=[e['kind'] for e in listings.report(self.root/'journal.json')['events']]
        self.assertIn('price_down',kinds);self.assertIn('source_disappearance',kinds);self.assertIn('reappeared',kinds)
    def test_429_500_503_bounded_retries(self):
        for status in [429,500,503]:
            self.s['faults']={'/listing/1':[{'status':status}]};self.update();c=self.client();self.assertIn(c.get('/listing/1')[0],{200,304})
            self.assertEqual(c.logs[0]['status'],status);self.assertEqual(len(c.logs),2)
        self.s['faults']={'/listing/2':[{'status':503}]*10};self.update();c=self.client()
        with self.assertRaises(NetworkError): c.get('/listing/2')
        self.assertEqual(len(c.logs),3)
    def test_retry_after_budget_and_exponential_backoff(self):
        self.s['faults']={'/listing/1':[{'status':429,'retry_after':99}]};self.update();c=self.client(max_wait=1)
        with self.assertRaises(NetworkError): c.get('/listing/1')
        self.assertEqual(len(c.logs),1)
        self.s['faults']={'/listing/2':[{'status':500},{'status':503}]};self.update();delays=[]
        c=Client(self.origin,self.root/'second.json',interval=0,backoff=.1,sleep=delays.append);c.get('/listing/2')
        self.assertIn(.1,delays);self.assertIn(.2,delays)
    def test_timeout_drop_connection_and_404(self):
        self.s['faults']={'/listing/1':[{'delay':.15}]*3,'/listing/2':[{'drop':True}]*3};self.update()
        for path in ['/listing/1','/listing/2']:
            c=self.client(timeout=.02,retries=1)
            with self.assertRaises(NetworkError): c.get(path)
            self.assertEqual(len(c.logs),2)
        self.assertEqual(self.client().get('/listing/missing')[0],404)
        with socket.socket() as sock: sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        c=Client(f'http://127.0.0.1:{port}',self.root/'no.json',interval=0,backoff=0,retries=1)
        with self.assertRaises(NetworkError): c.get('/')
    def test_last_modified_cache_tampering_and_rate(self):
        delays=[];c=Client(self.origin,self.root/'c.json',interval=1,sleep=delays.append)
        c.get('/listing/1');c.cache['/listing/1']['etag']=None
        self.assertEqual(c.get('/listing/1')[0],304);self.assertGreater(delays[-1],.8)
        c.cache['/listing/1']['body']='corrupt'
        with self.assertRaises(NetworkError): c.get('/listing/1')
    def test_schema_bad_data_scope_and_pagination_loop_quarantine(self):
        self.scan()
        for mutation in [dict(broken=True),dict(scope='changed'),dict(loop=True)]:
            old=dict(self.s);self.s.update(mutation);self.s['generation']+=1;self.update()
            self.assertNotEqual(self.scan()['completeness'],'complete');self.s=old
        self.s['rows'][0]['area_m2']=-1;self.s['generation']+=1;self.update();r=self.scan();self.assertTrue(r['quarantine']);self.assertEqual(r['completeness'],'partial')
        self.assertFalse(any(e['kind']=='listing_disappeared' for e in listings.report(self.root/'journal.json')['events']))
    def test_outbox_interruption_resume(self):
        with patch.object(crawler.listings,'ingest',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.scan()
        pending=json.loads((self.root/'crawler/pending.json').read_text(encoding="utf-8"));self.scan()
        batches=listings.report(self.root/'journal.json')['batches']
        self.assertEqual(sum(b['batch_id']==pending['batch_id'] for b in batches),1)
        self.assertFalse((self.root/'crawler/pending.json').exists())
    def test_external_crawl_is_disabled(self):
        with self.assertRaises(ValueError): crawler.crawl('https://suumo.jp',self.root/'c',self.root/'j')
    def test_robots_and_missing_detail_never_disappear(self):
        self.scan();self.s['faults']={'/listing/1':[{'status':404}]};self.update()
        self.assertEqual(self.scan()['completeness'],'partial')
        self.s['robots']='User-agent: *\nDisallow: /\n';self.update()
        self.assertEqual(self.scan()['completeness'],'failed')
        self.assertFalse(any(e['kind']=='listing_disappeared' for e in listings.report(self.root/'journal.json')['events']))
    def test_cache_origin_and_entire_feed_absence(self):
        self.scan();self.s['rows']=[];self.s['generation']+=1;self.update();self.assertEqual(self.scan()['completeness'],'complete')
        self.assertTrue(all(p['state']=='full_disappearance' for p in listings.report(self.root/'journal.json')['properties']))
        with self.assertRaises(ValueError): Client('http://localhost:1',self.root/'crawler/cache.json')
    def test_streamlit_renders_collected_journal(self):
        from streamlit.testing.v1 import AppTest
        from japan_housing_liquidity_lab import web_adapter
        self.scan();self.s['rows'][0]['price_jpy']-=1000000;self.s['generation']+=1;self.update();self.scan()
        imported=web_adapter.append_batches([],web_adapter.import_bytes('journal.json',(self.root/'journal.json').read_bytes()))
        with patch.dict('os.environ',{'JHLL_ENABLE_REAL':'0','JHLL_LOCAL_SAVE':'0'}):
            a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=30).run()
            a.session_state['journal_demo']=imported;a.sidebar.radio[1].set_value('掲載追跡').run()
            self.assertFalse(a.exception)
            self.assertTrue(any('価格低下' in str(x.value) for x in a.dataframe))
            self.assertEqual(len(a.session_state['journal_demo']),2)


class APITests(unittest.TestCase):
    def test_real_http_mock_auth_gzip_parameters_incremental_and_errors(self):
        calls=[];mode={'status':200,'bad':False}
        class H(BaseHTTPRequestHandler):
            def log_message(self,*a): pass
            def do_GET(self):
                calls.append((self.path,self.headers.get('Ocp-Apim-Subscription-Key')))
                row=dict(Type='中古マンション等',TradePrice='60000000',Area='70',Period='2023年第1四半期',MunicipalityCode='13112')
                body=gzip.compress(json.dumps({'status':'BAD' if mode['bad'] else 'OK','data':[row,row]}).encode())
                self.send_response(mode['status']);self.send_header('Content-Type','application/json');self.send_header('Content-Encoding','gzip');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        http=ThreadingHTTPServer(('127.0.0.1',0),H);t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);c=Client(f'http://127.0.0.1:{http.server_port}',root/'cache',interval=0,backoff=0)
                with patch.dict('os.environ',{'REINFOLIB_API_KEY':'NEVER-SEND-THIS-REAL-KEY'}):
                    m=mlit_client.fetch_quarter(c,'2023Q1',root/'data')
                self.assertEqual(calls[0][1],'LOCAL-SIMULATION-NOT-A-KEY');self.assertIn('priceClassification=01',calls[0][0]);self.assertIn('area=13',calls[0][0])
                self.assertEqual(m['records'],2);self.assertEqual(m['exact_duplicate_rows'],1)
                mlit_client.fetch_quarter(c,'2023Q1',root/'data');self.assertEqual(len(calls),1)
                mlit_client.fetch_quarter(c,'2024Q1',root/'data',['2024Q1']);self.assertEqual(len(calls),1)
                for code in [401,403]:
                    mode['status']=code
                    with self.assertRaises(ValueError): mlit_client.fetch_quarter(c,'2023Q2',root/'data')
                mode['status']=404;self.assertEqual(mlit_client.fetch_quarter(c,'2023Q2',root/'data')['status'],'not_available_or_no_data')
                self.assertFalse((root/'data/2023Q2-manifest.json').exists())
                mode['status']=200;mode['bad']=True
                with self.assertRaises(ValueError): mlit_client.fetch_quarter(c,'2023Q2',root/'data')
                self.assertNotIn('NEVER-SEND',json.dumps(c.logs))
        finally: http.shutdown();http.server_close();t.join()
    def test_missing_key_pending_without_network(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(mlit_client,'load_credential',side_effect=ValueError('Approved API key unavailable; live test Pending')):
            c=Client(mlit_client.ORIGIN,Path(tmp)/'cache')
            with self.assertRaisesRegex(ValueError,'Pending'): mlit_client.fetch_quarter(c,'2023Q1',Path(tmp)/'d')
            self.assertEqual(c.logs,[])

if __name__=='__main__': unittest.main()
