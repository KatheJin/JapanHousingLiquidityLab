import copy,csv,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from japan_housing_liquidity_lab.listings import VERSION,validate,ingest,report,load_input,export


def row(id='a',pid=None,price=60000000,**kw):
    r=dict(listing_id=id,status='present',evidence='SYNTHETIC observation',price_jpy=price,area_m2=70,
           municipality='架空区',town='架空町',station='架空駅',walk_minutes=10,built_year=2005,layout='3LDK',structure='RC')
    if pid: r.update(property_id=pid,match_evidence='SYNTHETIC exact dwelling crosswalk verified')
    return r|kw


def batch(day=1,source='A',records=None,complete='complete',**kw):
    return dict(version=VERSION,batch_id=f'{source}-{day}',source=source,scope_id='fixed',
                scope=dict(coverage_type='tracked_listing_ids',definition='SYNTHETIC fixed watch list',listing_ids=['a','b']),
                observed_at=f'2026-11-{day:02d}T12:00:00+09:00',completeness=complete,
                check_evidence='SYNTHETIC check: fixed IDs verified',data_kind='synthetic',
                rights=dict(basis='synthetic',evidence='Invented fixture',local_retention_allowed=True,url_retention_allowed=False),
                records=[row()] if records is None else records)|kw


class ListingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=self.root/'journal.json'
    def tearDown(self): self.temp.cleanup()
    def add(self,*batches):
        for b in batches: ingest(self.store,b)
        return report(self.store)
    def test_price_changes_and_snapshot_retention(self):
        r=self.add(batch(1),batch(2,records=[row(price=59000000)]),batch(3,records=[row(price=59000000)]),batch(4,records=[row(price=61000000)]))
        self.assertEqual(len(r['snapshots']),4)
        self.assertEqual([e['kind'] for e in r['events'] if e['kind'].startswith('price_')],['price_down','price_unchanged','price_up'])
        self.assertAlmostEqual(r['listings'][0]['unit_price_jpy_m2'],61000000/70)
        self.assertIsNone(r['listings'][0]['first_listed_at'])
    def test_multi_platform_first_partial_full_and_lag(self):
        r=self.add(batch(1,records=[row(pid='home')]),batch(1,'B',[row('b','home')]),
                   batch(2,records=[]),batch(4,'B',[]))
        events=r['events'];p=r['properties'][0]
        self.assertEqual(len([e for e in events if e['kind']=='first_source_disappearance']),1)
        states=[e['state'] for e in events if e['kind']=='property_state_changed']
        self.assertIn('partial_disappearance',states);self.assertEqual(p['state'],'full_disappearance')
        self.assertEqual(p['first_source_check_lag_seconds'],2*86400)
        self.assertTrue(all(e['exact_end_at'] is None for e in events if e['kind']=='source_disappearance'))
    def test_failed_and_partial_checks_never_disappear(self):
        r=self.add(batch(),batch(2,records=[],complete='failed'),batch(3,records=[],complete='partial'))
        self.assertFalse(any(e['kind']=='listing_disappeared' for e in r['events']))
        self.assertEqual(r['listings'][0]['state'],'present')
        self.assertEqual(r['properties'][0]['state'],'unknown_coverage')
        self.assertEqual(r['listings'][0]['last_successful_check_at'],validate(batch())['observed_at'])
    def test_coverage_changes_and_filtered_search_do_not_infer_absence(self):
        b=batch(2,records=[],scope_id='different')
        r=self.add(batch(),b)
        self.assertFalse(any(e['kind']=='listing_disappeared' for e in r['events']))
        b=batch(3,records=[],scope=dict(coverage_type='filtered_search',definition='price band',listing_ids=[]))
        with self.assertRaises(ValueError): ingest(self.store,b)
        self.store.unlink()
        a=batch(scope=b['scope']);r=self.add(a,b)
        self.assertFalse(any(e['kind']=='listing_disappeared' for e in r['events']))
    def test_reappearance_and_new_listing_link(self):
        r=self.add(batch(records=[row(pid='home')]),batch(2,records=[]),batch(3,records=[row(pid='home')]),
                   batch(4,records=[row('b','home')]))
        self.assertTrue(any(e['kind']=='reappeared' for e in r['events']))
        self.assertTrue(any(e['kind']=='new_listing_linked' for e in r['events']))
        self.assertEqual(len(r['listings']),2)
        self.assertEqual(r['properties'][0]['state'],'presence_observed')
    def test_provider_sold_is_source_claim_not_sale_date(self):
        r=self.add(batch(),batch(2,records=[row(status='provider_sold',price=None)]),batch(3,records=[]))
        self.assertEqual(r['listings'][0]['state'],'provider_sold')
        self.assertEqual(r['listings'][0]['last_seen_at'],validate(batch())['observed_at'])
        self.assertNotIn('sold_at',r['properties'][0])
    def test_cross_platform_match_requires_evidence(self):
        self.add(batch(records=[row(pid='home')]))
        bad=row('b',pid='home');bad.pop('match_evidence')
        original=self.store.read_bytes()
        with self.assertRaises(ValueError): ingest(self.store,batch(2,'B',[bad]))
        self.assertEqual(self.store.read_bytes(),original)
        r=self.add(batch(2,'B',[row('b')]))
        self.assertEqual(len(r['properties']),2)
    def test_same_source_multiple_listings_not_premature_source_disappearance(self):
        r=self.add(batch(records=[row('a','home'),row('b','home')]),batch(2,records=[row('b','home')]))
        self.assertTrue(any(e['kind']=='listing_disappeared' for e in r['events']))
        self.assertFalse(any(e['kind']=='source_disappearance' for e in r['events']))
    def test_idempotency_conflict_and_out_of_order(self):
        b=batch();self.add(b);before=self.store.read_bytes()
        self.assertFalse(ingest(self.store,b)['imported'])
        self.assertFalse(ingest(self.store,b|dict(batch_id='duplicate-name'))['imported'])
        with self.assertRaises(ValueError): ingest(self.store,b|dict(records=[row(price=1)]))
        self.assertEqual(before,self.store.read_bytes())
        self.add(batch(3))
        with self.assertRaises(ValueError): ingest(self.store,batch(2))
    def test_validation_permissions_dates_personal_fields(self):
        for mutation in [dict(observed_at='2026-11-01'),dict(data_kind='real')]:
            with self.assertRaises(ValueError): validate(batch()|mutation)
        for change in [dict(price_jpy=-1),dict(area_m2=0),dict(phone='123'),dict(url='https://example.com/a'),
                       dict(first_listed_at='2027-01-01T00:00:00Z'),dict(built_year=2027),dict(age_at_observation=1)]:
            with self.assertRaises(ValueError): validate(batch(records=[row(**change)]))
    def test_first_listed_and_attribute_changes(self):
        start='2026-10-01T00:00:00Z'
        r=self.add(batch(records=[row(first_listed_at=start)]),batch(2,records=[row(area_m2=71)]))
        self.assertEqual(r['listings'][0]['first_listed_at'],validate(batch(records=[row(first_listed_at=start)]))['records'][0]['first_listed_at'])
        self.assertTrue(any(e['kind']=='attributes_changed' for e in r['events']))
    def test_recovery_from_failure_does_not_repeat_disappearance(self):
        r=self.add(batch(),batch(2,records=[]),batch(3,records=[],complete='failed'),batch(4,records=[]))
        self.assertEqual(len([e for e in r['events'] if e['kind']=='source_disappearance']),1)
    def test_csv_json_equivalence_and_cli_export(self):
        b=batch();meta=self.root/'metadata.json';data=self.root/'rows.csv'
        meta.write_text(json.dumps({k:v for k,v in b.items() if k!='records'}),encoding='utf-8')
        with data.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(b['records'][0]));w.writeheader();w.writerows(b['records'])
        self.assertEqual(validate(load_input(data,meta)),validate(b))
        command=[sys.executable,'-m','japan_housing_liquidity_lab.listings','--store',str(self.store)]
        r=subprocess.run(command+['import',str(data),'--metadata',str(meta)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        r=subprocess.run(command+['history','--output',str(self.root/'out')],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue((self.root/'out/events.csv').exists())
        with self.assertRaises(FileExistsError): export(report(self.store),self.root/'out')
    def test_lock_and_property_query(self):
        self.add(batch(records=[row('a','one'),row('b','two')]))
        r=report(self.store,'one')
        self.assertEqual(len(r['listings']),1)
        self.assertEqual(len(r['batches'][0]['records']),1)
        lock=Path(str(self.store)+'.lock');lock.touch()
        with self.assertRaises(ValueError): ingest(self.store,batch(2))

    def test_identity_conflict_abstains_and_crosslink_rejects(self):
        self.add(batch(records=[row(pid='home')]))
        with self.assertRaises(ValueError): ingest(self.store,batch(2,'B',[row('b','home',area_m2=20)]))
        r=self.add(batch(2,records=[row(pid='home',area_m2=20)]))
        self.assertEqual(r['listings'][0]['identity_status'],'review_required')
        self.assertEqual(r['properties'][0]['state'],'unknown_coverage')

    def test_date_only_listing_start_keeps_source_precision(self):
        b=batch(records=[row(first_listed_at='2026-11-01')],observed_at='2026-11-01T00:01:00+09:00')
        r=self.add(b)
        self.assertEqual(r['listings'][0]['first_listed_at'],'2026-11-01')
        self.assertNotEqual(r['listings'][0]['first_seen_at'],'2026-11-01')

    def test_source_disappearance_after_separate_partial_confirmations(self):
        r=self.add(batch(records=[row('a','home'),row('b','home')]),
                   batch(2,records=[row('a','home',status='provider_withdrawn')],complete='partial'),
                   batch(3,records=[row('b','home',status='provider_withdrawn')],complete='partial'))
        self.assertFalse(any(e['kind']=='source_disappearance' for e in r['events']))
        r=self.add(batch(4,records=[]))
        disappears=[e for e in r['events'] if e['kind']=='source_disappearance']
        self.assertEqual(len(disappears),1)
        self.assertEqual(disappears[0]['observed_at'],validate(batch(4))['observed_at'])
        self.assertEqual(r['properties'][0]['state'],'full_disappearance')
        r=self.add(batch(5,records=[],complete='failed'),batch(6,records=[]))
        self.assertEqual(len([e for e in r['events'] if e['kind']=='source_disappearance']),1)

    def test_second_disappearance_episode_preserves_first_time(self):
        r=self.add(batch(),batch(2,records=[]),batch(3),batch(4,records=[]))
        self.assertEqual(len([e for e in r['events'] if e['kind']=='source_disappearance']),2)
        self.assertEqual(len([e for e in r['events'] if e['kind']=='first_source_disappearance']),1)
        self.assertEqual(r['properties'][0]['first_source_disappeared_at'],validate(batch(2))['observed_at'])

    def test_csv_unknown_blank_headers_rejected_before_disappearance(self):
        self.add(batch());original=self.store.read_bytes()
        meta=self.root/'meta.json';data=self.root/'empty.csv'
        meta.write_text(json.dumps({k:v for k,v in batch(2).items() if k!='records'}),encoding='utf-8')
        for content in ['phone\n','listing_id,evidence,phone\n','listing_id,listing_id,evidence\n']:
            data.write_text(content,encoding='utf-8')
            with self.assertRaises(ValueError): ingest(self.store,load_input(data,meta))
        self.assertEqual(self.store.read_bytes(),original)

    def test_normalized_ids_rights_object_and_japan_new_year(self):
        for rights in [None,[],1]:
            with self.assertRaises(ValueError): validate(batch(rights=rights))
        b=batch();b['scope']['listing_ids']=[' a ','b']
        self.assertEqual(validate(b)['scope']['listing_ids'],['a','b'])
        b['scope']['listing_ids']=['a',' a ']
        with self.assertRaises(ValueError): validate(b)
        b=batch(observed_at='2026-01-01T00:01:00+09:00',records=[row(built_year=2005,age_at_observation=21)])
        self.assertEqual(validate(b)['records'][0]['age_at_observation'],21)

    def test_unresolved_identity_prevents_new_crosslink(self):
        self.add(batch(records=[row(pid='home')]),batch(2,records=[row(pid='home',area_m2=71)]))
        before=self.store.read_bytes()
        with self.assertRaises(ValueError): ingest(self.store,batch(3,'B',[row('b','home',area_m2=71)]))
        self.assertEqual(self.store.read_bytes(),before)

    def test_cli_rights_and_real_data_disclosure(self):
        command=[sys.executable,'-X','utf8','-m','japan_housing_liquidity_lab.listings','--store',str(self.store)]
        help_result=subprocess.run(command+['--help'],capture_output=True,encoding='utf-8')
        self.assertEqual(help_result.returncode,0)
        self.assertIn('0 real listings',' '.join(help_result.stdout.split()))
        data=self.root/'batch.json';data.write_text(json.dumps(batch()),encoding='utf-8')
        result=subprocess.run(command+['import',str(data)],capture_output=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout)
        self.assertEqual(value['real_observation_rows_in_batch'],0)
        self.assertIn('does not grant reuse rights',value['rights_notice'])
        self.assertEqual(report(self.store)['data_summary'],dict(real_observation_rows=0,synthetic_observation_rows=1))


if __name__=='__main__': unittest.main()
