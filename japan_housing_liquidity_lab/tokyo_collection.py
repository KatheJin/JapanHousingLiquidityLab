"""Bounded central SUUMO expansion; existing transport and snapshot writer only."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
import uuid
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import sqlalchemy as sa
from . import listing_pipeline as p
from .pg_store import PostgresStore,engine
from .net_http import save

WARDS=('千代田区','中央区','港区','新宿区','文京区','台東区','墨田区','江東区','品川区','目黒区','大田区','世田谷区','渋谷区','中野区','杉並区','豊島区','北区','荒川区','板橋区','練馬区','足立区','葛飾区','江戸川区')
ROOT='https://suumo.jp/ms/chuko/tokyo/'
KOMAE=dict(municipality='狛江市',entry=ROOT+'sc_komae/')
DEFAULT=Path('data/tokyo-collection')

def parse_plan(html):
    found={}
    for a in BeautifulSoup(html,'html.parser').select('a[href]'):
        name=a.get_text(strip=True);url=urljoin(ROOT,a['href'])
        if name not in WARDS:continue
        try:p.SuumoDiscovery().entry(url)
        except ValueError:continue
        if name in found and found[name]!=url:raise ValueError('Ambiguous municipality entry')
        found[name]=url
    if set(found)!=set(WARDS):raise ValueError('Official Tokyo index does not expose all 23 ward entries')
    return [KOMAE]+[dict(municipality=n,entry=found[n]) for n in WARDS]

def discover_plan(folder=DEFAULT):
    """One normal index GET with existing rules, throttle, request audit and writer lock."""
    s=PostgresStore();rid=uuid.uuid4().hex
    try:
        with s.db:s.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',(rid,'suumo',ROOT,'tokyo-plan-index','running',p.now(),p.now(),None))
        try:
            http=p.PublicHTTP(s,'suumo',rid);http.review();html=http.get(ROOT)
            regions=parse_plan(html)
            save(Path(folder)/'plan.json',dict(version=1,source='suumo',index_url=ROOT,observed_at=p.now(),index_sha256=hashlib.sha256(html.encode()).hexdigest(),regions=regions))
            with s.db:s.db.execute('UPDATE runs SET status=?,updated_at=? WHERE id=?',('completed',p.now(),rid))
            return regions
        except BaseException as exc:
            with s.db:s.db.execute('UPDATE runs SET status=?,updated_at=?,error=? WHERE id=?',('blocked',p.now(),str(exc),rid))
            raise
    finally:s.close()

def report(regions):
    e=engine()
    try:
        with e.connect().execution_options(isolation_level='REPEATABLE READ') as c:
            c.exec_driver_sql('SET TRANSACTION READ ONLY')
            def rows(sql,**params):return [dict(r) for r in c.execute(sa.text(sql),params).mappings()]
            totals=rows("SELECT COUNT(*) FILTER(WHERE success=1) successful_snapshots,COUNT(*) FILTER(WHERE success=0) failed_snapshots,COUNT(DISTINCT listing_id) FILTER(WHERE success=1) successful_unique,MAX(observed_at) last_observation_at FROM snapshots WHERE source='suumo'")[0]
            latest=rows("SELECT DISTINCT ON(listing_id) listing_id,municipality,attributes FROM snapshots WHERE source='suumo' AND success=1 ORDER BY listing_id,rowid DESC")
            observed=rows("SELECT municipality,COUNT(*) snapshots FROM snapshots WHERE source='suumo' AND success=1 GROUP BY municipality")
            region_stats=[]
            for region in regions:
                recent=rows("SELECT id,status,error,updated_at FROM runs WHERE source='suumo' AND entry=:entry ORDER BY rowid DESC LIMIT 1",entry=region['entry'])
                run=recent[0] if recent else None
                q=rows("SELECT kind,state,COUNT(*) n FROM jobs WHERE run_id=:rid GROUP BY kind,state",rid=run['id']) if run else []
                pages=rows("SELECT advertised_total FROM pages WHERE run_id=:rid ORDER BY rowid DESC",rid=run['id']) if run else []
                discovered=rows("SELECT COUNT(DISTINCT listing_id) n FROM page_links WHERE run_id=:rid",rid=run['id'])[0]['n'] if run else 0
                supported=rows("SELECT COUNT(DISTINCT l.listing_id) n FROM page_links l WHERE l.run_id=:rid AND EXISTS(SELECT 1 FROM snapshots s WHERE s.source='suumo' AND s.listing_id=l.listing_id AND s.success=1)",rid=run['id'])[0]['n'] if run else 0
                errors=rows("SELECT error,COUNT(*) n FROM snapshots WHERE run_id=:rid AND success=0 GROUP BY error",rid=run['id']) if run else []
                advertised=pages[0]['advertised_total'] if pages else None
                region_stats.append(dict(**region,successful_unique=sum(r['municipality']==region['municipality'] for r in latest),successful_snapshots=next((x['snapshots'] for x in observed if x['municipality']==region['municipality']),0),latest_run=run,queue=q,discovered_in_run=discovered,successful_discovered_in_run=supported,advertised_total=advertised,coverage_fraction=min(supported/advertised,1) if advertised else None,coverage_comparable=bool(pages) and len({x['advertised_total'] for x in pages})==1 and discovered==advertised,failures=errors))
            keys=['price_jpy','area_m2','built_year','layout','structure','municipality','town','station','walk_minutes']
            quality={k:sum(x['attributes'].get(k) not in (None,'') for x in latest)/len(latest) if latest else None for k in keys}
            restrictions=rows("SELECT status,error,observed_at,url FROM requests WHERE source='suumo' AND (status IN(403,429) OR error='Access_challenge') ORDER BY id DESC LIMIT 1")
            cooldown=bool(restrictions) and datetime.now(timezone.utc)-datetime.fromisoformat(restrictions[0]['observed_at'])<p.timedelta(hours=24)
            return dict(observed_at=p.now(),source='suumo',**totals,regions=region_stats,other_observed_regions=[x for x in observed if x['municipality'] not in {r['municipality'] for r in regions}],field_completeness=quality,field_completeness_denominator=len(latest),access_cooldown=cooldown,last_restriction=restrictions[0] if restrictions else None,interpretation='Source listing IDs, not verified distinct dwellings. Advertised counts are not acquisitions. Coverage is a traversal diagnostic, not a market census.')
    finally:e.dispose()

def choose(status,mode):
    # Finish the specifically requested existing Komae traversal before the wards.
    koma=next(r for r in status['regions'] if r['municipality']=='狛江市')
    eligible=lambda r:not r['latest_run'] or r['latest_run']['status'] not in {'completed','completed_with_errors'}
    if eligible(koma):return koma
    wards=[r for r in status['regions'] if r['municipality'] in WARDS and eligible(r)]
    if wards:return min(wards,key=lambda r:(r['successful_unique'],WARDS.index(r['municipality'])))
    if mode=='incremental':return min(status['regions'],key=lambda r:r['latest_run']['updated_at'])
    return None

def validate(folder=DEFAULT,target=3000):
    """Read-only full-population checks; optional missing values are reported, not removed."""
    folder=Path(folder);plan=folder/'plan.json'
    regions=json.loads(plan.read_text(encoding='utf-8'))['regions'] if plan.exists() else [KOMAE]
    result=report(regions);e=engine()
    try:
        with e.connect() as c:
            c.exec_driver_sql('SET TRANSACTION READ ONLY')
            checks={
                'duplicate_source_ids':"SELECT COUNT(*) FROM (SELECT source,listing_id FROM discovered GROUP BY source,listing_id HAVING COUNT(*)>1) x",
                'orphan_snapshots':"SELECT COUNT(*) FROM snapshots s LEFT JOIN runs r ON s.run_id=r.id LEFT JOIN discovered d ON s.source=d.source AND s.listing_id=d.listing_id WHERE r.id IS NULL OR d.listing_id IS NULL OR s.source<>r.source",
                'orphan_batches':"SELECT COUNT(*) FROM batches b LEFT JOIN snapshots s ON s.id=b.id WHERE s.id IS NULL OR b.source<>s.source OR b.listing_id<>s.listing_id",
                'orphan_events':"SELECT COUNT(*) FROM events e LEFT JOIN snapshots s ON s.id=e.observation_id WHERE s.id IS NULL OR e.source<>s.source OR e.listing_id<>s.listing_id",
                'timestamp_mismatches':"SELECT COUNT(*) FROM snapshots WHERE observed_at_utc IS DISTINCT FROM observed_at::timestamptz",
                'projection_mismatches':"SELECT COUNT(*) FROM snapshots WHERE success=1 AND (attributes IS DISTINCT FROM data::jsonb OR price_jpy IS DISTINCT FROM (attributes->>'price_jpy')::numeric OR municipality IS DISTINCT FROM attributes->>'municipality' OR listing_id IS DISTINCT FROM attributes->>'listing_id')",
                'invalid_price_or_area':"SELECT COUNT(*) FROM snapshots WHERE success=1 AND ((attributes->>'price_jpy')::numeric IS NULL OR (attributes->>'price_jpy')::numeric<=0 OR (attributes->>'area_m2')::numeric IS NULL OR (attributes->>'area_m2')::numeric<=0)"
            }
            result['integrity_errors']={k:c.execute(sa.text(q)).scalar() for k,q in checks.items()}
            result['constraints_validated']=all(c.execute(sa.text("SELECT convalidated FROM pg_constraint WHERE connamespace=current_schema()::regnamespace")).scalars())
        result['target_met']=result['successful_unique']>=target
        result['integrity_passed']=not any(result['integrity_errors'].values()) and result['constraints_validated']
        active=Path('data/postgres-runtime/active.json')
        if active.exists():
            marker=json.loads(active.read_text(encoding='utf-8'));original=Path(marker['source'])
            result['original_sqlite_hash_unchanged']=original.exists() and hashlib.sha256(original.read_bytes()).hexdigest()==marker['verified_source_sha256']
        save(folder/'validation.json',result);return result
    finally:e.dispose()

def collect(folder=DEFAULT,target=3000,max_batches=200,max_seconds=86400,mode='initial',max_details=50,max_pages=2):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    if target<1 or not 1<=max_batches<=1000 or max_seconds<=0:raise ValueError('Invalid bounded plan budget')
    lock=engine();connection=lock.connect()
    if not connection.execute(sa.text('SELECT pg_try_advisory_lock(12012002)')).scalar():
        connection.close();lock.dispose();raise ValueError('Tokyo central plan already active')
    connection.commit();started=time.monotonic();log=folder/'batches.jsonl'
    def publish(status,phase,**extra):
        value=dict(status,phase=phase,mode=mode,target=target,**extra);save(folder/'status.json',value);return value
    try:
        if (folder/'plan.json').exists():regions=json.loads((folder/'plan.json').read_text(encoding='utf-8'))['regions']
        else:
            # Do not even fetch the plan index during an existing access cooldown.
            base=report([KOMAE])
            if base['access_cooldown']:return publish(base,'blocked_access')
            regions=discover_plan(folder)
        for i in range(max_batches):
            status=report(regions)
            if status['access_cooldown']:return publish(status,'blocked_access')
            if mode=='initial' and status['successful_unique']>=target:
                checked=validate(folder,target)
                return publish(checked,'target_reached' if checked['integrity_passed'] else 'blocked_integrity')
            if time.monotonic()-started>=max_seconds:return publish(status,'paused_budget')
            region=choose(status,mode)
            if region is None:return publish(status,'available_plan_finished')
            publish(status,'collecting',current_region=region['municipality'],batch_index=i+1)
            result=p.run(folder/'worker','suumo',region['entry'],max_pages=max_pages,max_details=max_details,recheck_hours=1e9 if mode=='initial' else 24,resume=True,local_private_only=True,store_factory=PostgresStore)
            with log.open('a',encoding='utf-8') as f:f.write(json.dumps(dict(observed_at=p.now(),municipality=region['municipality'],mode=mode,**{k:result[k] for k in ['run_id','status','successful_this_invocation','pages_scanned_this_invocation','pending_jobs','failures','error']}),ensure_ascii=False)+'\n')
            current=report(regions);publish(current,'batch_finished',current_region=region['municipality'],batch_index=i+1)
            print(json.dumps(dict(region=region['municipality'],successful_unique=current['successful_unique'],successful_snapshots=current['successful_snapshots'],batch_status=result['status'],pending=result['pending_jobs']),ensure_ascii=False),flush=True)
            if result['status']=='blocked':return publish(current,'blocked_review',error=result['error'])
            if len(result['failures'])>=5:return publish(current,'blocked_quality',error='Five or more detail failures in a batch; inspect parser before continuing')
        return publish(report(regions),'paused_budget')
    except BaseException as exc:
        save(folder/'operator-error.json',dict(observed_at=p.now(),error_type=type(exc).__name__,error=str(exc)))
        raise
    finally:
        connection.rollback();connection.execute(sa.text('SELECT pg_advisory_unlock(12012002)'));connection.commit();connection.close();lock.dispose()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['collect','status','validate']);parser.add_argument('--folder',type=Path,default=DEFAULT);parser.add_argument('--target',type=int,default=3000);parser.add_argument('--max-batches',type=int,default=200);parser.add_argument('--max-seconds',type=int,default=86400);parser.add_argument('--mode',choices=['initial','incremental'],default='initial');parser.add_argument('--max-details',type=int,default=50);parser.add_argument('--max-pages',type=int,default=2)
    a=parser.parse_args()
    from .pg_admin import local_environment
    local_environment()
    if a.command=='validate':result=validate(a.folder,a.target)
    elif a.command=='status':
        plan=a.folder/'plan.json';regions=json.loads(plan.read_text(encoding='utf-8'))['regions'] if plan.exists() else [KOMAE]
        result=report(regions);save(a.folder/'status-live.json',result)
    else:result=collect(a.folder,a.target,a.max_batches,a.max_seconds,a.mode,a.max_details,a.max_pages)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result.get('phase','').startswith('blocked'):raise SystemExit(2)

if __name__=='__main__':main()
