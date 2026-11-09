"""Real PostgreSQL tests use a dedicated disposable database, never production data."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from japan_housing_liquidity_lab import listing_pipeline as pipeline
from japan_housing_liquidity_lab.pg_store import PostgresStore,ListingQuery,DataUnavailable,engine
from japan_housing_liquidity_lab.pg_schema import metadata,TABLES
from japan_housing_liquidity_lab.pg_migrate import migrate,upgrade
from tests.test_listing_pipeline import Fake,ENTRY,URL,DETAIL,listing


@unittest.skipUnless(os.environ.get('JHLL_TEST_DATABASE_URL'),'Dedicated PostgreSQL test database not configured')
class PostgresTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'JHLL_DATABASE_URL':os.environ['JHLL_TEST_DATABASE_URL']});self.env.start();self.addCleanup(self.env.stop)
        e=engine()
        with e.connect() as c:self.assertEqual(c.execute(sa.text('SELECT current_database()')).scalar(),'jhll_test')
        e.dispose();upgrade();e=engine()
        with e.begin() as c:
            self.assertEqual(c.execute(sa.text('SELECT current_database()')).scalar(),'jhll_test')
            c.execute(sa.text('TRUNCATE '+','.join(metadata.tables)+' RESTART IDENTITY CASCADE'))
        e.dispose();self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        Fake.pages={ENTRY:listing(),URL:DETAIL};Fake.calls=[]
    def pg_collect(self):
        return pipeline.run(self.root/'worker','suumo',ENTRY,local_private_only=True,transport_factory=Fake,store_factory=PostgresStore,recheck_hours=0)
    def test_migration_exact_fields_timestamps_and_idempotence(self):
        path=self.root/'source.sqlite3';pipeline.run(path,'suumo',ENTRY,local_private_only=True,transport_factory=Fake)
        first=migrate(path,self.root/'backups');second=migrate(path,self.root/'backups')
        self.assertEqual(first['counts'],second['counts']);self.assertTrue(first['foreign_keys_verified']);self.assertTrue(first['timestamps_verified'])
        self.assertEqual(first['source_sha256'],second['source_sha256'])
    def test_real_postgres_pipeline_writes_price_events_and_queries(self):
        first=self.pg_collect();self.assertEqual(first['successful_this_invocation'],1)
        Fake.pages[URL]=DETAIL.replace('4200万円','4100万円');self.pg_collect()
        s=PostgresStore()
        try:
            self.assertEqual(len(s.history('suumo','20179966')),2)
            self.assertIn('price_down',[x['kind'] for x in s.events('suumo','20179966')])
        finally:s.close()
        records=ListingQuery().search(source='suumo',municipality='武蔵村山市',max_price=41500000)
        self.assertEqual(len(records),1);self.assertEqual(records[0]['attributes']['price_jpy'],41000000)
        self.assertEqual(len(ListingQuery().history('suumo','20179966')),2)
        self.assertEqual(ListingQuery().coverage('suumo')[0]['status'],'completed')
        with patch.dict(os.environ,{'JHLL_DATABASE_URL':''}):
            with self.assertRaises(DataUnavailable):ListingQuery().search()
    def test_failure_abstains_and_no_false_disappearance(self):
        self.pg_collect();Fake.pages[URL]=ValueError('parse failed');self.pg_collect();s=PostgresStore()
        try:
            self.assertEqual(s.search()[0]['state'],'unknown_coverage')
            self.assertNotIn('listing_disappeared',[x['kind'] for x in s.events('suumo','20179966')])
        finally:s.close()
    def test_tokyo_report_matches_successes_and_failed_coverage(self):
        from japan_housing_liquidity_lab.tokyo_collection import report,validate
        self.pg_collect();Fake.pages[URL]=ValueError('parse failed');self.pg_collect()
        r=report([dict(municipality='武蔵村山市',entry=ENTRY)])
        self.assertEqual(r['successful_unique'],1);self.assertEqual(r['successful_snapshots'],1)
        self.assertEqual(r['failed_snapshots'],1)
        self.assertEqual(r['field_completeness_denominator'],1)
        region=r['regions'][0];self.assertEqual(region['successful_unique'],1)
        self.assertEqual(region['coverage_fraction'],1)
        self.assertEqual(region['failures'][0]['n'],1)
        self.assertEqual(region['latest_run']['status'],'completed_with_errors')
        checked=validate(self.root,target=3000)
        self.assertTrue(checked['integrity_passed']);self.assertFalse(checked['target_met'])
        self.assertTrue(all(n==0 for n in checked['integrity_errors'].values()))
    def test_restriction_cooldown_survives_later_success_log(self):
        self.pg_collect();s=PostgresStore()
        try:
            rid=s.db.execute('SELECT id FROM runs ORDER BY rowid DESC LIMIT 1').fetchone()[0]
            with s.db:
                for status in [403,200]:s.db.execute('INSERT INTO requests(run_id,source,url,observed_at,status,elapsed_s,error) VALUES(?,?,?,?,?,?,?)',(rid,'suumo',ENTRY,pipeline.now(),status,0.1,'HTTP_403' if status==403 else None))
        finally:s.close()
        Fake.calls=[];result=self.pg_collect()
        self.assertEqual(result['error'],'Access_restriction_cooldown_24h');self.assertEqual(Fake.calls,[])
    def test_transaction_and_foreign_key_rollback(self):
        s=PostgresStore()
        try:
            with self.assertRaises(IntegrityError):
                with s.db:s.db.execute('INSERT INTO jobs(run_id,kind,url) VALUES(?,?,?)',('missing','list','https://example.test'))
            self.assertEqual(s.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
            with self.assertRaises(RuntimeError):
                with s.db:
                    s.db.execute('INSERT INTO controls VALUES(?,?)',('suumo',1.0));raise RuntimeError('crash')
            self.assertEqual(s.db.execute('SELECT COUNT(*) FROM controls').fetchone()[0],0)
        finally:s.close()
    def test_single_central_worker_lock(self):
        s=PostgresStore()
        try:
            with self.assertRaises(ValueError):PostgresStore()
        finally:s.close()
    def test_resume_after_lost_worker_ignores_stale_file_lock(self):
        from tests.test_listing_pipeline import URL2
        Fake.pages[ENTRY]=listing((URL,URL2),2);Fake.pages[URL2]=DETAIL
        path=self.root/'worker'
        first=pipeline.run(path,'suumo',ENTRY,max_details=1,local_private_only=True,transport_factory=Fake,store_factory=PostgresStore)
        self.assertEqual(first['pending_jobs'],1)
        s=PostgresStore()
        try:
            # A killed process can leave a running row and an old filesystem lock.
            with s.db:s.db.execute("UPDATE runs SET status='running' WHERE id=?",(first['run_id'],))
        finally:s.close()
        stale=Path(str(path)+'.collector.lock');stale.touch();Fake.calls=[]
        second=pipeline.run(path,'suumo',ENTRY,resume=True,max_details=1,local_private_only=True,transport_factory=Fake,store_factory=PostgresStore)
        self.assertEqual(second['run_id'],first['run_id']);self.assertEqual(second['status'],'completed')
        self.assertEqual(Fake.calls,[URL2]);self.assertEqual(second['summary']['successful_snapshots'],2)
        self.assertTrue(stale.exists())  # PG must not delete another backend's lock.
        repeated=pipeline.run(path,'suumo',ENTRY,local_private_only=True,transport_factory=Fake,store_factory=PostgresStore)
        self.assertEqual(repeated['successful_this_invocation'],0)
        self.assertEqual(repeated['summary']['successful_snapshots'],2)
    def test_source_namespaces_and_parent_relationship(self):
        self.pg_collect();s=PostgresStore()
        try:
            with s.db:
                s.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',('homes-test','homes','https://example.test','synthetic','completed',pipeline.now(),pipeline.now(),None))
                s.db.execute('INSERT INTO discovered VALUES(?,?,?,?,?)',('homes','20179966','https://example.test',pipeline.now(),pipeline.now()))
            row=dict(listing_id='20179966',price_jpy=40000000,area_m2=60,status='present',evidence='SYNTHETIC fixture')
            with self.assertRaises(ValueError):s.record('homes-test','suumo','20179966',row,{})
            s.record('homes-test','homes','20179966',row,{})
            self.assertEqual(len(s.search()),2)
        finally:s.close()
    def test_repeat_migration_after_incremental_update_no_overwrite(self):
        path=self.root/'source.sqlite3';pipeline.run(path,'suumo',ENTRY,local_private_only=True,transport_factory=Fake)
        migrate(path,self.root/'backups');Fake.pages[URL]=DETAIL.replace('4200万円','4100万円');self.pg_collect()
        m=migrate(path,self.root/'backups');self.assertEqual(m['counts']['snapshots']['postgres'],2)
        self.assertEqual(ListingQuery().search()[0]['attributes']['price_jpy'],41000000)
    def test_frozen_sqlite_is_readonly(self):
        import sqlite3
        path=self.root/'source.sqlite3';pipeline.run(path,'suumo',ENTRY,local_private_only=True,transport_factory=Fake)
        marker=self.root/'data/postgres-runtime/active.json';marker.parent.mkdir(parents=True)
        marker.write_text(json.dumps({'source':str(path.resolve())}),encoding='utf-8')
        prior=Path.cwd()
        try:
            os.chdir(self.root)
            s=pipeline.Store(path)
            try:
                with self.assertRaises(sqlite3.OperationalError):s.db.execute("DELETE FROM snapshots")
                self.assertEqual(s.summary('suumo')['successful_snapshots'],1)
            finally:s.close()
        finally:os.chdir(prior)

if __name__=='__main__':unittest.main()
