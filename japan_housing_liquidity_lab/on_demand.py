"""Bounded user-requested SUUMO jobs. Reuses HTTP, parser, queue, snapshots and PG locks."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
import hashlib
import json
import re
import uuid
import threading
from pathlib import Path
import sqlalchemy as sa
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from . import listing_pipeline as p
from .benchmark import norm
from .pg_store import engine,PostgresStore
from .pg_schema import metadata
from .tokyo_collection import ROOT,parse_plan
from .location import walk_bounds

COMMANDS=metadata.tables['collection_commands']
EXECUTOR=ThreadPoolExecutor(max_workers=1,thread_name_prefix='jhll-demand')
FUTURES={}
FUTURE_LOCK=threading.Lock()

class Busy(ValueError):pass

class DemandStore(PostgresStore):
    def __init__(self,path=None):
        self.guard_engine=engine();self.guard=self.guard_engine.connect()
        if not self.guard.execute(sa.text('SELECT pg_try_advisory_lock(12012002)')).scalar():
            self.guard.close();self.guard_engine.dispose();raise Busy('Central plan active; retry later')
        self.guard.commit()
        try:super().__init__(path)
        except BaseException:
            self.guard.close();self.guard_engine.dispose();raise
    def close(self):
        try:super().close()
        finally:self.guard.close();self.guard_engine.dispose()

def layout_family(value):
    value=norm(value)
    if value in ('ワンルーム','1R'):return '1'
    m=re.match(r'^(\d+)(?:R|K|DK|LDK|SDK|SLDK)',value)
    return m[1] if m else None


def relaxed(row,query,year,*,partial=False):
    """Explicit alternative envelope; never price-based, never a quality ranking."""
    def known(key):return row.get(key) not in (None,'')
    try:
        if known('municipality') and norm(row['municipality'])!=norm(query['市区町村名']):return False
        if known('area_m2') and not .65*float(query['面積（㎡）'])<=float(row['area_m2'])<=1.35*float(query['面積（㎡）']):return False
        if known('built_year') and (not 0<=year-int(row['built_year'])<=150 or abs(int(row['built_year'])-int(norm(query['建築年']).removesuffix('年')))>20):return False
        if known('layout') and norm(query.get('間取り','')) and (layout_family(row['layout']) is None or layout_family(row['layout'])!=layout_family(query['間取り'])):return False
        if query.get('walk_tolerance_minutes') is not None and known('walk_minutes'):
            lo,hi=walk_bounds(str(row['walk_minutes']));t=float(query['最寄駅：距離（分）']);w=float(query['walk_tolerance_minutes'])+5
            if not lo>=max(0,t-w) or not hi<=t+w:return False
        return partial or all(known(k) for k in ('area_m2','built_year','municipality','layout'))
    except (ValueError,KeyError,TypeError):return False


def differences(row,query,strict_station=True):
    out=[]
    if abs(float(row['area_m2'])/float(query['面積（㎡）'])-1)>.20000001:out.append('面積が±20%の範囲外')
    if abs(int(row['built_year'])-int(norm(query['建築年']).removesuffix('年')))>10:out.append('建築年が±10年の範囲外')
    if strict_station and norm(row.get('station',''))!=norm(query.get('最寄駅：名称','')):out.append('駅が異なる／不明')
    for key,q,label in [('layout','間取り','間取り'),('structure','建物の構造','構造')]:
        if norm(query.get(q,'')) and norm(row.get(key,''))!=norm(query[q]):out.append(label+'が異なる／不明')
    if query.get('walk_tolerance_minutes') is not None:
        lo,hi=walk_bounds(str(row.get('walk_minutes','')));t=float(query['最寄駅：距離（分）']);w=float(query['walk_tolerance_minutes'])
        if not lo>=max(0,t-w) or not hi<=t+w:out.append('徒歩条件外／不明')
    return out


def card_fields(card):
    """Only labelled factual fields. No ads, contacts, images or free text retained."""
    raw={}
    for dt in card.select('dt'):
        key=norm(dt.get_text(' ',strip=True));dd=dt.find_next_sibling('dd')
        if key in ('専有面積','間取り','築年月','沿線・駅','所在地') and dd is not None:
            raw.setdefault(key,[]).append(p.normalized(dd.get_text(' ',strip=True)))
    raw={k:v[0] for k,v in raw.items() if len(set(v))==1};row={}
    for key,label,pattern,cast in [('area_m2','専有面積',r'^(\d+(?:\.\d+)?)m2',float),('built_year','築年月',r'^(\d{4})年',int)]:
        m=re.match(pattern,raw.get(label,''))
        if m:row[key]=cast(m[1])
    if '間取り' in raw:row['layout']=raw['間取り']
    transport=raw.get('沿線・駅','');m=re.search(r'[「｢]([^」｣]+)[」｣]',transport)
    if m:row['station']=m[1]
    m=re.search(r'[」｣](?:徒歩|歩)(\d+)分',transport)
    if m and 'バス' not in transport:row['walk_minutes']=int(m[1])
    m=re.match(r'東京都(.+?[市区]|.+?郡.+?[町村])',raw.get('所在地',''))
    if m:row['municipality']=m[1]
    return row,raw


class PrioritizedDiscovery(p.SuumoDiscovery):
    def __init__(self,query,*,strict_station=True,cards=None,on_update=None):
        self.query=query;self.strict_station=strict_station;self.cards=cards or {};self.on_update=on_update
    def discover(self,html,url,entry):
        links,nxt,total=super().discover(html,url,entry)
        for card in BeautifulSoup(html,'html.parser').select('.property_unit'):
            fields,raw=card_fields(card)
            # Text only helps order synthetic/unknown cards, never excludes them.
            text=norm(card.get_text(' ',strip=True));score=sum(norm(self.query.get(k,'')) in text for k in ['最寄駅：名称','間取り'] if norm(self.query.get(k,'')))
            for a in card.select('a[href]'):
                target=urljoin(url,a['href']).split('?')[0]
                for lid,detail in links.items():
                    if target==detail:self.cards[lid]=dict(fields=fields,raw_fields=raw,eligible=relaxed(fields,self.query,datetime.now(timezone(timedelta(hours=9))).year,partial=True),text_score=score)
        if self.on_update:self.on_update(self.cards)
        return dict(sorted(links.items(),key=lambda kv:self.priority(kv[0]))),nxt,total
    def should_fetch(self,lid):return self.cards.get(lid,{}).get('eligible',True)
    def priority(self,lid):
        meta=self.cards.get(lid,{});row=meta.get('fields',{});q=self.query
        # Strict possibilities precede alternatives, across ALL scanned pages.
        violations=0
        if row.get('area_m2') is not None:violations+=not .8*float(q['面積（㎡）'])<=row['area_m2']<=1.2*float(q['面積（㎡）'])
        if row.get('built_year') is not None:violations+=abs(row['built_year']-int(norm(q['建築年']).removesuffix('年')))>10
        for key,qkey in [('layout','間取り')]+([('station','最寄駅：名称')] if self.strict_station else []):
            if row.get(key) and q.get(qkey):violations+=norm(row[key])!=norm(q[qkey])
        return (violations,-meta.get('text_score',0),abs(row.get('area_m2',float(q['面積（㎡）']))-float(q['面積（㎡）'])))
    def next_detail(self,store,rid):
        jobs=list(store.db.execute("SELECT * FROM jobs WHERE run_id=? AND kind='detail' AND state='pending' ORDER BY rowid",(rid,)))
        return min(jobs,key=lambda j:self.priority(j['listing_id'])) if jobs else None


def matches(row,query,year,strict_station=True):
    try:
        area=float(row['area_m2']);built=int(row['built_year']);target_area=float(query['面積（㎡）']);target_year=int(norm(query['建築年']).removesuffix('年'))
        if not .8*target_area<=area<=1.2*target_area or not 0<=year-built<=150 or abs(built-target_year)>10:return False
        if norm(row.get('municipality',''))!=norm(query['市区町村名']):return False
        if strict_station and norm(row.get('station',''))!=norm(query.get('最寄駅：名称','')):return False
        for k,q in [('layout','間取り'),('structure','建物の構造')]:
            if norm(query.get(q,'')) and norm(row.get(k,''))!=norm(query[q]):return False
        if query.get('walk_tolerance_minutes') is not None:
            lo,hi=walk_bounds(str(row.get('walk_minutes','')));t=float(query['最寄駅：距離（分）']);w=float(query['walk_tolerance_minutes'])
            if not lo>=max(0,t-w) or not hi<=t+w:return False
        return True
    except (ValueError,KeyError,TypeError):return False

def _read(task_id):
    if not re.fullmatch(r'[a-f0-9]{32}',task_id):raise ValueError('Invalid task ID')
    e=engine()
    try:
        with e.connect() as c:
            row=c.execute(sa.select(COMMANDS).where(COMMANDS.c.id==task_id,COMMANDS.c.action=='demand-search')).mappings().one()
            return dict(row)|dict(payload=json.loads(row['scope']))
    finally:e.dispose()

def _update(task_id,status,payload):
    e=engine()
    try:
        with e.begin() as c:
            statement=COMMANDS.update().where(COMMANDS.c.id==task_id)
            new_status=sa.case((COMMANDS.c.status.in_(['pause_requested','paused']),COMMANDS.c.status),else_=status) if status in ['running','waiting_central_worker'] else status
            c.execute(statement.values(status=new_status,scope=json.dumps(payload,ensure_ascii=False)))
    finally:e.dispose()

def search_fingerprint(payload):
    q=payload['query']
    normalized={k:norm(q.get(k,'')) for k in ['市区町村名','最寄駅：名称','建築年','間取り','建物の構造','reference_date']}
    for key in ['面積（㎡）','asking_price_jpy','最寄駅：距離（分）','walk_tolerance_minutes']:
        normalized[key]=float(q[key]) if q.get(key) not in (None,'') else None
    definition={k:payload.get(k) for k in ['max_pages','max_details','strict_station','search_version']}
    definition['query']=normalized
    return hashlib.sha256(json.dumps(definition,sort_keys=True).encode()).hexdigest()


def create(query,*,max_pages=10,max_details=12,strict_station=True,destination=None):
    if not 1<=max_pages<=20 or not 1<=max_details<=30:raise ValueError('Budget exceeds local search limits')
    q=dict(query)
    if destination:
        q['市区町村名']=destination['municipality'];q['最寄駅：名称']=destination.get('station','');strict_station=bool(destination.get('station'))
    # Reuse shared input validation; do not use asking price as a listing filter.
    from .web_adapter import home_query
    from datetime import date
    home_query(q['市区町村名'],q.get('地区名',''),q.get('最寄駅：名称','') or '(area)',None,float(q['面積（㎡）']),int(norm(q['建築年']).removesuffix('年')),None,q.get('間取り',''),q.get('建物の構造',''),float(q['asking_price_jpy'])/10000,datetime.now(timezone(timedelta(hours=9))).date())
    payload=dict(query=q,original_query=query,max_pages=max_pages,max_details=max_details,strict_station=strict_station,search_version=2)
    fingerprint=search_fingerprint(payload);payload['fingerprint']=fingerprint
    e=engine()
    try:
        with e.begin() as c:
            c.execute(sa.text('SELECT pg_advisory_xact_lock(12012003)'))
            recent=c.execute(sa.select(COMMANDS).where(COMMANDS.c.action=='demand-search').order_by(COMMANDS.c.requested_at.desc()).limit(100)).mappings().all()
            for row in recent:
                old=json.loads(row['scope'])
                if search_fingerprint(old)==fingerprint and (row['status'] in ['queued','running','waiting_central_worker','interrupted','pause_requested'] or datetime.now(timezone.utc)-row['requested_at']<timedelta(minutes=15)):return row['id']
            if c.execute(sa.select(sa.func.count()).select_from(COMMANDS).where(COMMANDS.c.action=='demand-search',COMMANDS.c.status.in_(['queued','running','waiting_central_worker','interrupted','pause_requested']))).scalar()>=20:raise Busy('Central request queue is full')
            task=uuid.uuid4().hex;c.execute(COMMANDS.insert().values(id=task,source='suumo',scope=json.dumps(payload,ensure_ascii=False),action='demand-search',status='queued',requested_at=datetime.now(timezone.utc)))
            return task
    finally:e.dispose()

def _entry(store,task_id,query,transport):
    path=Path('data/tokyo-collection/plan.json')
    if path.exists():regions=json.loads(path.read_text(encoding='utf-8'))['regions']
    else:
        rid='demand-index-'+task_id
        if not store.db.execute('SELECT 1 FROM runs WHERE id=?',(rid,)).fetchone():
            with store.db:store.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',(rid,'suumo',ROOT,'demand-bootstrap','running',p.now(),p.now(),None))
        client=transport(store,'suumo',rid);client.cancel_check=lambda:_read(task_id)['status'] in ['pause_requested','paused'];client.review();regions=parse_plan(client.get(ROOT))
        with store.db:store.db.execute('UPDATE runs SET status=?,updated_at=? WHERE id=?',('completed',p.now(),rid))
        # No long-running collector or permanent plan setup required.
    found=[r['entry'] for r in regions if norm(r['municipality'])==norm(query['市区町村名'])]
    if len(set(found))!=1:raise ValueError('Municipality entry not verified; only official verified Tokyo entries supported')
    return p.SuumoDiscovery().entry(found[0])

def progress(task_id):
    task=_read(task_id);payload=task['payload'];e=engine();counts={}
    try:
        with e.connect() as c:
            if payload.get('entry'):
                fingerprint=p.scope_fingerprint('suumo',payload['entry'],'demand-'+task_id)
                run=c.execute(sa.text('SELECT id,status,error FROM runs WHERE scope=:s ORDER BY rowid DESC LIMIT 1'),dict(s=fingerprint)).mappings().first()
                if run:
                    counts=dict(run);counts['jobs']=[dict(r) for r in c.execute(sa.text('SELECT kind,state,count(*) n FROM jobs WHERE run_id=:r GROUP BY kind,state'),dict(r=run['id'])).mappings()]
    finally:e.dispose()
    result=payload.get('result')
    # Read already committed observations while a worker runs; never mutate its queue.
    if counts and task['status'] in ['running','pause_requested','interrupted']:
        result=_results(counts['id'],payload['query'],payload['strict_station'],payload.get('cards',{}))
        result['live_partial']=True
    if result:
        for row in result.get('records',[])+result.get('approximate_records',[])+result.get('old_database_records',[]):row['freshness_seconds']=(datetime.now(timezone.utc)-datetime.fromisoformat(row['observed_at'])).total_seconds()
    return dict(task_id=task_id,status=task['status'],progress=counts,result=result,error=payload.get('error'),requested_at=task['requested_at'].isoformat(),query=payload['query'])

def _results(run_id,query,strict_station,cards=None):
    e=engine();strict=[];approx=[];old=[];failures=[];unverified=[];now=datetime.now(timezone.utc);cards=cards or {}
    provenance={'newly_discovered':0,'reconfirmed':0,'previously_discovered_first_detail':0,'old_database':0,'access_or_parse_failed':0,'not_fetched':0}
    year=now.astimezone(timezone(timedelta(hours=9))).year
    try:
        with e.connect() as c:
            run=c.execute(sa.text('SELECT * FROM runs WHERE id=:r'),dict(r=run_id)).mappings().one()
            links=c.execute(sa.text('SELECT DISTINCT listing_id FROM page_links WHERE run_id=:r'),dict(r=run_id)).scalars().all()
            for lid in links:
                observations=c.execute(sa.text("SELECT run_id,observed_at,success,attributes,error FROM snapshots WHERE source='suumo' AND listing_id=:id ORDER BY rowid DESC"),dict(id=lid)).mappings().all()
                current=next((x for x in observations if x['run_id']==run_id),None)
                previous=next((x for x in observations if x['run_id']!=run_id and x['success']),None)
                if current and not current['success']:
                    provenance['access_or_parse_failed']+=1;failures.append(dict(listing_id=lid,error=current['error'],observed_at=current['observed_at']))
                if current and current['success']:
                    first=c.execute(sa.text("SELECT first_seen_at FROM discovered WHERE source='suumo' AND listing_id=:id"),dict(id=lid)).scalar()
                    kind='reconfirmed' if previous else 'newly_discovered' if first and first>=run['started_at'] else 'previously_discovered_first_detail'
                    provenance[kind]+=1;s=current
                else:
                    s=previous
                    if s:provenance['old_database']+=1
                    elif not current:provenance['not_fetched']+=1;unverified.append(lid)
                    kind='old_database'
                if not s:continue
                row=s['attributes'];tier='strict' if matches(row,query,year,strict_station) else 'approximate' if relaxed(row,query,year) else None
                if not tier:continue
                data=dict(row,listing_id=lid,unit_price_jpy_m2=float(row['price_jpy'])/float(row['area_m2']),age=year-int(row['built_year']),observed_at=s['observed_at'],source='suumo',freshness_seconds=(now-datetime.fromisoformat(s['observed_at'])).total_seconds(),observation_kind=kind,match_tier=tier,relaxed_conditions=differences(row,query,strict_station),current_check_failed=bool(current and not current['success']))
                if kind=='old_database':old.append(data)
                elif tier=='strict':strict.append(data)
                else:approx.append(data)
            pages=c.execute(sa.text('SELECT url,observed_at,advertised_total,detail_n,next_url FROM pages WHERE run_id=:r ORDER BY rowid'),dict(r=run_id)).mappings().all()
            jobs=c.execute(sa.text('SELECT kind,state,count(*) n FROM jobs WHERE run_id=:r GROUP BY kind,state'),dict(r=run_id)).mappings().all()
            requests=c.execute(sa.text('SELECT status,error,count(*) n,sum(elapsed_s) elapsed_s FROM requests WHERE run_id=:r GROUP BY status,error'),dict(r=run_id)).mappings().all()
            totals=sorted(set(x['advertised_total'] for x in pages if x['advertised_total'] is not None))
            pending_pages=sum(x['n'] for x in jobs if x['kind']=='list' and x['state']=='pending')
            eligible=sum(cards.get(lid,{}).get('eligible',True) for lid in links)
            return dict(records=strict,approximate_records=approx,old_database_records=old,matched_n=len(strict),approximate_n=len(approx),old_database_match_n=len(old),discovered_ids=len(links),candidate_n=eligible,prefilter_excluded_n=len(links)-eligible,unverified_or_stale_ids=len(links)-sum(provenance[k] for k in ('newly_discovered','reconfirmed','previously_discovered_first_detail')),not_fetched_ids=unverified,failed_details=failures,observation_counts=provenance,pages_scanned=len(pages),page_evidence=[dict(x) for x in pages],advertised_totals=totals,list_traversal_complete=bool(pages) and not pending_pages and not run['error'],pending_pages=pending_pages,detail_attempts=sum(x['n'] for x in jobs if x['kind']=='detail' and x['state'] in ('done','error')),successful_details=sum(provenance[k] for k in ('newly_discovered','reconfirmed','previously_discovered_first_detail')),pending_details=sum(x['n'] for x in jobs if x['kind']=='detail' and x['state']=='pending'),http_requests=sum(x['n'] for x in requests),http_statuses=[dict(x) for x in requests],elapsed_seconds=((now if run['status']=='running' else datetime.fromisoformat(run['updated_at']))-datetime.fromisoformat(run['started_at'])).total_seconds(),checked_at=now.isoformat(),started_at=run['started_at'],scope='Bounded municipal pages; zero matches is not zero inventory; source IDs are not verified unique dwellings',server_filters=dict(enabled=False,reason='Official form endpoint disallowed by robots.txt; no query-path workaround',endpoint='/jj/bukken/ichiran/JJ012FC001/'),asking_price_filter_used=False,criteria=dict(strict='Same municipality; area ±20%; built year ±10; exact supplied layout/structure; optional same station and walking tolerance',approximate='Same municipality; area ±35%; built year ±20; same room-count family including studio/1K/1DK/1LDK; other stations/structures allowed; optional walking tolerance widened by 5 minutes, unknown walking labelled'))
    finally:e.dispose()


def execute(task_id,*,transport=p.PublicHTTP,store_factory=DemandStore):
    task=_read(task_id)
    if task['status'] in ['completed','partial','failed','paused']:return progress(task_id)
    payload=task['payload'];store=None
    try:
        store=store_factory(None)
        if _read(task_id)['status']=='paused':return progress(task_id)
        _update(task_id,'running',payload)
        # Bootstrap must honor the same source-wide access cooldown.
        last=store.db.execute("SELECT observed_at FROM requests WHERE source='suumo' AND (status IN(403,429) OR error='Access_challenge') ORDER BY id DESC LIMIT 1").fetchone()
        if last and datetime.now(timezone.utc)-datetime.fromisoformat(last[0])<timedelta(hours=24):raise p.StopCollection('Access_restriction_cooldown_24h')
        payload['entry']=_entry(store,task_id,payload['query'],transport);_update(task_id,'running',payload)
        scope=p.scope_fingerprint('suumo',payload['entry'],'demand-'+task_id)
        old=store.db.execute('SELECT id FROM runs WHERE scope=? ORDER BY rowid DESC LIMIT 1',(scope,)).fetchone()
        pages=details=0
        if old:
            pages=store.db.execute('SELECT COUNT(*) FROM pages WHERE run_id=?',(old[0],)).fetchone()[0]
            details=store.db.execute("SELECT COUNT(*) FROM jobs WHERE run_id=? AND kind='detail' AND state IN('done','error')",(old[0],)).fetchone()[0]
        def save_cards(cards):
            payload['cards']=cards;_update(task_id,'running',payload)
        result=p.run(Path('data/on-demand'),'suumo',payload['entry'],max_pages=max(0,payload['max_pages']-pages),max_details=max(0,payload['max_details']-details),recheck_hours=1,resume=True,local_private_only=True,transport_factory=transport,store_factory=lambda _:store,isolated_scope='demand-'+task_id,discovery=PrioritizedDiscovery(payload['query'],strict_station=payload['strict_station'],cards=payload.get('cards'),on_update=save_cards),should_pause=lambda:_read(task_id)['status'] in ['pause_requested','paused'])
        store=None # runner released both locks
        payload['result']=_results(result['run_id'],payload['query'],payload['strict_station'],payload.get('cards',{}))|dict(run={k:v for k,v in result.items() if k!='summary'})
        state='paused' if result.get('user_paused') else 'failed' if result['status']=='blocked' else 'partial' if result['status']!='completed' else 'completed'
        _update(task_id,state,payload)
    except p.CollectionPaused:
        _update(task_id,'paused',payload)
    except (Busy,ValueError) as exc:
        if 'already active' in str(exc) or isinstance(exc,Busy):
            if task['status']!='running':_update(task_id,'waiting_central_worker',payload)
        else:payload['error']=str(exc) if isinstance(exc,p.StopCollection) else type(exc).__name__;_update(task_id,'failed',payload)
    except Exception as exc:
        payload['error']=type(exc).__name__;_update(task_id,'interrupted',payload)
    finally:
        if store is not None and not store.connection.closed:store.close()
    return progress(task_id)

def start(task_id):
    # At most one thread in this process; PostgreSQL coordinates every process.
    with FUTURE_LOCK:
        old=FUTURES.get(task_id)
        if old is not None and not old.done():return old
        for key in list(FUTURES):
            if FUTURES[key].done():del FUTURES[key]
        future=EXECUTOR.submit(execute,task_id);FUTURES[task_id]=future;return future

def retry(task_id):
    task=_read(task_id)
    if task['status'] in ['completed','partial']:return progress(task_id)
    store=DemandStore()
    try:_update(task_id,'queued',task['payload'])
    finally:store.close()
    start(task_id)
    return progress(task_id)


def pause(task_id):
    """Stop waiting or ask the active worker to pause at a safe boundary."""
    _read(task_id)  # validate ID; retain full payload and original observations
    e=engine()
    try:
        with e.begin() as c:
            c.execute(COMMANDS.update().where(COMMANDS.c.id==task_id,COMMANDS.c.status.in_(['queued','waiting_central_worker','interrupted','running'])).values(status=sa.case((COMMANDS.c.status=='running','pause_requested'),else_='paused')))
    finally:e.dispose()
    return progress(task_id)
