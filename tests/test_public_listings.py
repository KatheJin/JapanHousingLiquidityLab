"""Offline regression cases. HTML below is synthetic, not a retained listing page."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from japan_housing_liquidity_lab import public_listings as p, listings

URL = 'https://suumo.jp/ms/chuko/aichi/sc_nagoyashiatsuta/nc_21863680/'
URL2 = URL.replace('21863680', '21863681')
HTML = '''<title>架空 中古マンション物件情報</title><table>
<tr><th><div class="fl">価格</div>ヒント</th><td><p>4200万円</p><p>[支払]</p></td></tr>
<tr><th>専有面積</th><td>54.34m<sup>2</sup>（16.43坪）（壁芯）</td></tr>
<tr><th>完成時期（築年月）</th><td>2024年7月</td></tr>
<tr><th>間取り</th><td>2LDK</td></tr>
<tr><th>担当者</th><td>NEVER_RETAIN_PERSON</td></tr></table>'''


class Fake:
    interval = 10
    def __init__(self, robots='User-agent: *\nAllow: /', pages=None):
        self.robots = robots
        self.pages = pages or {}
        self.logs = []
    def get(self, url, media):
        self.logs.append(dict(url=url))
        if url.endswith('robots.txt'): return self.robots
        if url == p.TERMS: return 'terms'
        result = self.pages.get(url, HTML)
        if isinstance(result, Exception): raise result
        return result


class PublicListingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.hash_patch = patch.object(p, 'TERMS_HASH', p.terms_hash('terms'))
        self.hash_patch.start()
        self.addCleanup(self.hash_patch.stop)
        self.date_patch = patch.object(p, 'REVIEW_DATE', p.datetime.now(p.timezone.utc).date().isoformat())
        self.date_patch.start()
        self.addCleanup(self.date_patch.stop)

    def run_pilot(self, client=None, urls=None):
        return p.collect('suumo', urls or [URL], self.root/'collector', self.root/'journal.json',
                         local_private_only=True, transport=client or Fake())

    def test_price_units_and_ranges(self):
        self.assertEqual(p.price_jpy('1億2500万円'), 125000000)
        self.assertEqual(p.price_jpy('４，２００万円'), 42000000)
        for value in ['4200～4500万円', '相談', '万円', '0万円', '4200万円より']:
            with self.assertRaises(ValueError): p.price_jpy(value)

    def test_whitelist_and_identity(self):
        row = p.SuumoAdapter().parse(HTML, URL)
        self.assertEqual(row['area_m2'], 54.34)
        self.assertEqual(row['built_year'], 2024)
        self.assertNotIn('NEVER_RETAIN_PERSON', json.dumps(row))
        for url in [URL+'?x=1', URL+'#x', URL.replace('suumo.jp', 'evil.test'), 'http://127.0.0.1/', URL+'/../']:
            with self.assertRaises(ValueError): p.SuumoAdapter().listing_id(url)
        with self.assertRaises(ValueError):
            p.SuumoAdapter().parse('<link rel="canonical" href="'+URL2+'">'+HTML, URL)

    def test_parser_drift_and_conflicting_tables(self):
        for html in [HTML.replace('専有面積', '敷地面積'), '<title>Login</title>',
                     HTML+'<table><th>価格</th><td>4300万円</td></table>',
                     HTML.replace('54.34m', '54～60m')]:
            with self.assertRaises(ValueError): p.SuumoAdapter().parse(html, URL)

    def test_robots_wildcard_stops_before_terms_and_details(self):
        fake = Fake('User-agent: *\nDisallow: /ms/*/nc_*')
        result = self.run_pilot(fake)
        self.assertEqual(result['real_records'], 0)
        self.assertEqual(len(fake.logs), 1)
        self.assertIn('Robots_disallow', result['errors'])

    def test_changed_terms_stops(self):
        with patch.object(p, 'TERMS_HASH', 'changed'):
            result = self.run_pilot()
        self.assertEqual(len(result['requests']), 2)
        self.assertEqual(result['real_records'], 0)

    def test_budget_and_scope_before_network(self):
        fake = Fake()
        for urls in [[], [URL]*2, [URL,URL2,URL2,URL2]]:
            with self.assertRaises(ValueError):
                p.collect('suumo',urls,self.root/'c',self.root/'j',local_private_only=True,transport=fake)
        with self.assertRaises(ValueError): p.collect('suumo',[URL],self.root/'c',self.root/'j',transport=fake)
        self.assertEqual(fake.logs, [])

    def test_stop_on_denial_and_no_disappearance(self):
        first = self.run_pilot()
        self.assertEqual(first['real_records'], 1)
        # Advance only offline test state; production cooldown has no CLI override.
        (self.root/'collector/last-run.json').unlink()
        fake = Fake(pages={URL:p.StopCollection('HTTP_429')})
        second = self.run_pilot(fake,[URL,URL2])
        self.assertEqual(len(fake.logs),3)
        self.assertEqual(second['completeness'],'failed')
        batches=json.loads((self.root/'journal.json').read_text(encoding='utf-8'))['batches']
        history=listings.replay(batches)
        self.assertFalse(any(e['kind']=='listing_disappeared' for e in history['events']))
        self.assertEqual(history['data_summary']['real_observation_rows'],1)

    def test_partial_success_and_cooldown(self):
        result=self.run_pilot(Fake(pages={URL2:p.StopCollection('HTTP_404')}),[URL,URL2])
        self.assertEqual(result['real_records'],1)
        self.assertEqual(result['completeness'],'partial')
        fake=Fake()
        with self.assertRaises(ValueError): self.run_pilot(fake)
        self.assertEqual(fake.logs,[])

    def test_ingestion_web_roundtrip(self):
        self.run_pilot()
        from japan_housing_liquidity_lab.web_adapter import import_bytes, append_batches
        data=(self.root/'journal.json').read_bytes()
        batches=import_bytes('journal.json',data)
        self.assertEqual(append_batches(batches,batches),batches)
        self.assertEqual(batches[0]['data_kind'],'real')
        self.assertEqual(batches[0]['rights']['basis'],'public_terms_review')

    def test_future_year_rejected(self):
        result=self.run_pilot(Fake(pages={URL:HTML.replace('2024年','2999年')}))
        self.assertEqual(result['real_records'],0)

    def test_transport_denial_redirect_and_challenge(self):
        for status, body in [(403,b''),(429,b''),(302,b''),(200,b'<title>Access Denied</title>')]:
            from unittest.mock import MagicMock
            response=MagicMock()
            response.__enter__.return_value=response
            response.status_code=status
            response.headers={'Content-Type':'text/html'}
            response.iter_content.return_value=[body]
            with patch.object(p.requests,'get',return_value=response) as get:
                with self.assertRaises(p.StopCollection): p.Transport().get(URL,'text/html')
                self.assertEqual(get.call_count,1)
                self.assertFalse(get.call_args.kwargs['allow_redirects'])


if __name__=='__main__': unittest.main()
