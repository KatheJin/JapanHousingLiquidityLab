"""Synthetic HTML only. Live listing content never enters Git fixtures."""
import json
from pathlib import Path
import tempfile
import unittest
from japan_housing_liquidity_lab import listing_pipeline as p
from tests.test_public_listings import HTML

ENTRY='https://suumo.jp/ms/chuko/tokyo/sc_musashimurayama/'
URL=ENTRY+'nc_20179966/'
URL2=ENTRY+'nc_20179967/'
DETAIL=HTML+'<table><th>所在地</th><td>東京都武蔵村山市本町１</td><th>交通</th><td>線「架空駅」歩10分</td><th>構造</th><td>RC3階建</td><th>物件名</th><td>架空住宅</td></table>'


def listing(links=(URL,),total=1,nxt=None):
    cards=''.join('<div class="property_unit"><a href="'+u+'?fmlg=test">住宅</a></div>' for u in links)
    return '<title>架空 中古マンション</title><div class="pagination_set-hit">'+str(total)+' 件</div>'+cards+('<div class="pagination"><a href="'+nxt+'">次へ</a></div>' if nxt else '')


class Fake:
    pages={};calls=[]
    def __init__(self,*args): pass
    def review(self): pass
    def get(self,url,*args):
        self.calls.append(url);body=self.pages[url]
        if isinstance(body,BaseException): raise body
        return body


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.db=Path(self.t.name)/'private.sqlite3'
        Fake.pages={ENTRY:listing(),URL:DETAIL};Fake.calls=[]
    def run_once(self,**kwargs): return p.run(self.db,'suumo',ENTRY,local_private_only=True,transport_factory=Fake,**kwargs)
    def store(self):
        s=p.Store(self.db);self.addCleanup(s.close);return s
    def test_discovery_canonical_dedup_recommendations_and_pagination(self):
        body=listing((URL,URL),2,ENTRY+'?pn=2')+'<a href="'+URL2+'">recommendation</a>'
        links,nxt,n=p.SuumoDiscovery().discover(body,ENTRY,ENTRY)
        self.assertEqual(links,{'20179966':URL});self.assertEqual(nxt,ENTRY+'?pn=2')
        with self.assertRaises(ValueError): p.SuumoDiscovery().discover('<title>login</title>',ENTRY,ENTRY)
        links,nxt,n=p.SuumoDiscovery().discover(listing((URL,),2,ENTRY+'?page=2'),ENTRY,ENTRY)
        self.assertEqual(nxt,ENTRY+'?page=2')
    def test_sqlite_live_shape_and_incremental_due(self):
        r=self.run_once();self.assertEqual(r['status'],'completed');s=self.store()
        q=s.search(municipality='武蔵村山市',max_price=50000000);self.assertEqual(len(q),1)
        self.assertEqual(q[0]['data']['price_jpy'],42000000);self.assertEqual(q[0]['metadata']['name'],'架空住宅')
        r=self.run_once();self.assertEqual(r['successful_this_invocation'],0);self.assertEqual(r['discovered_this_run'],1)
        r=self.run_once(recheck_hours=0);self.assertEqual(r['successful_this_invocation'],1)
        self.assertEqual(len(s.history('suumo','20179966')),2)
        self.assertEqual(s.summary('suumo')['successful_unique'],1)
    def test_prices_and_failure_never_mean_sale(self):
        self.run_once();Fake.pages[URL]=DETAIL.replace('4200万円','4100万円');self.run_once(recheck_hours=0)
        Fake.pages[URL]=p.StopCollection('HTTP_404');self.run_once(recheck_hours=0)
        s=self.store();events=s.events('suumo','20179966')
        self.assertIn('price_down',[x['kind'] for x in events]);self.assertNotIn('listing_disappeared',[x['kind'] for x in events])
        self.assertEqual(s.search()[0]['state'],'unknown_coverage')
    def test_pagination_failure_resume_no_repeat_completed_pages(self):
        Fake.pages[ENTRY]=listing((URL,),2,ENTRY+'?pn=2');Fake.pages[ENTRY+'?pn=2']=p.StopCollection('HTTP_503')
        r=self.run_once();self.assertEqual(r['status'],'blocked')
        Fake.calls=[];Fake.pages[ENTRY+'?pn=2']=listing((URL2,),2);Fake.pages[URL2]=DETAIL
        r=self.run_once(resume=True);self.assertEqual(r['status'],'completed');self.assertNotIn(ENTRY,Fake.calls)
        self.assertEqual(r['discovered_this_run'],2)
    def test_bounded_queue_and_resume(self):
        Fake.pages[ENTRY]=listing((URL,URL2),2);Fake.pages[URL2]=DETAIL
        r=self.run_once(max_details=1);self.assertEqual(r['status'],'paused')
        Fake.calls=[];r=self.run_once(resume=True,max_details=1)
        self.assertEqual(r['status'],'completed');self.assertEqual(Fake.calls,[URL2])
        self.assertEqual(self.store().summary('suumo')['successful_snapshots'],2)
    def test_process_interruption_resumes_transactional_jobs(self):
        Fake.pages[ENTRY]=listing((URL,URL2),2);Fake.pages[URL2]=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.run_once()
        Fake.pages[URL2]=DETAIL;Fake.calls=[];r=self.run_once(resume=True)
        self.assertEqual(r['successful_this_invocation'],1);self.assertNotIn(URL,Fake.calls)
    def test_search_count_disagreement_never_complete(self):
        Fake.pages[ENTRY]=listing((URL,),3);r=self.run_once();self.assertEqual(r['status'],'blocked')
        self.assertIn('pagination_changed',r['error'])
    def test_bus_walk_and_no_personal_content_retained(self):
        row,raw=p.suumo_detail(DETAIL.replace('歩10分','バス20分停歩2分'),URL)
        self.assertEqual(row['municipality'],'武蔵村山市');self.assertNotIn('walk_minutes',row)
        self.assertNotIn('NEVER_RETAIN_PERSON',json.dumps(raw))
    def test_ward_boundary_precedes_city_character_in_town(self):
        for address,municipality,town in [
            ('東京都新宿区市谷架空町１','新宿区','市谷架空町'),
            ('東京都世田谷区架空市町１','世田谷区','架空市町'),
            ('東京都武蔵村山市本町１','武蔵村山市','本町'),
            ('東京都町田市架空町１','町田市','架空町')]:
            with self.subTest(address=address):
                row,raw=p.suumo_detail(DETAIL.replace('東京都武蔵村山市本町１',address),URL)
                self.assertEqual(row['municipality'],municipality)
                self.assertEqual(row['town'],town)
                self.assertIn(address,raw['field_mapping']['所在地'])

    def test_storage_room_layout_is_preserved_not_imputed(self):
        row,raw=p.suumo_detail(DETAIL.replace('2LDK','2LDK+S（納戸）'),URL)
        self.assertEqual(row['layout'],'2LDK+S(納戸)')
        self.assertIn('2LDK+S（納戸）',raw['field_mapping']['間取り'])
        with self.assertRaises(ValueError): p.suumo_detail(DETAIL.replace('2LDK','2LDK～3LDK'),URL)
    def test_source_ids_separate_and_no_automerge(self):
        self.run_once();s=self.store()
        self.assertEqual(s.search(source='homes'),[])
        with self.assertRaises(ValueError): p.run(self.db,'suumo','https://evil.test/',local_private_only=True)
        with self.assertRaises(ValueError): p.run(self.db,'suumo',ENTRY)
    def test_failed_detail_validation_rolls_back_batch(self):
        self.run_once();s=self.store();before=len(s.history('suumo','20179966'))
        with self.assertRaises(ValueError): s.record('fake','suumo','20179966',dict(listing_id='20179966',price_jpy=-1,evidence='test'),{})
        self.assertEqual(before,len(s.history('suumo','20179966')))
    def test_reused_source_identity_does_not_become_confident_presence(self):
        self.run_once();Fake.pages[URL]=DETAIL.replace('54.34m','50.34m');self.run_once(recheck_hours=0)
        s=self.store();self.assertIn('attributes_changed',[e['kind'] for e in s.events('suumo','20179966')])
        self.assertEqual(s.search()[0]['state'],'unknown_identity')

if __name__=='__main__': unittest.main()
