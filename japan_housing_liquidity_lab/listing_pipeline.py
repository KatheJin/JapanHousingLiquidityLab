"""Resumable, bounded public-listing discovery and local/private SQLite snapshots."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlsplit,urljoin,urlencode,parse_qs,urlunsplit
import uuid

from bs4 import BeautifulSoup
from protego import Protego
from . import listings
from .net_http import Client
from .public_listings import SuumoAdapter,normalized,price_jpy,terms_hash,TERMS,TERMS_HASH,StopCollection

UA='JapanHousingLiquidityLab/0.2 (local private housing evaluation; bounded HTTP)'
SOURCES={
 'suumo':dict(origin='https://suumo.jp',terms=TERMS),
 'homes':dict(origin='https://www.homes.co.jp',terms='https://www.homes.co.jp/kiyaku/'),
 'athome':dict(origin='https://www.athome.co.jp',terms='https://www.athome.co.jp/help/kiyaku.html')}


def now(): return datetime.now(timezone.utc).isoformat()
def encoded(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False)


class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        active=Path('data/postgres-runtime/active.json')
        if active.exists() and self.path.resolve()==Path(json.loads(active.read_text(encoding='utf-8'))['source']):
            self.db=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True);self.db.row_factory=sqlite3.Row;return
        self.db=sqlite3.connect(self.path,timeout=10);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON');self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,source TEXT,entry TEXT,scope TEXT,status TEXT,started_at TEXT,updated_at TEXT,error TEXT);
        CREATE TABLE IF NOT EXISTS jobs(run_id TEXT,kind TEXT,url TEXT,listing_id TEXT,state TEXT DEFAULT 'pending',error TEXT,PRIMARY KEY(run_id,kind,url));
        CREATE TABLE IF NOT EXISTS discovered(source TEXT,listing_id TEXT,url TEXT,first_seen_at TEXT,last_discovered_at TEXT,PRIMARY KEY(source,listing_id));
        CREATE TABLE IF NOT EXISTS pages(run_id TEXT,url TEXT,observed_at TEXT,sha256 TEXT,detail_n INTEGER,next_url TEXT,PRIMARY KEY(run_id,url));
        CREATE TABLE IF NOT EXISTS page_links(run_id TEXT,url TEXT,listing_id TEXT,PRIMARY KEY(run_id,url,listing_id));
        CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,run_id TEXT,source TEXT,listing_id TEXT,observed_at TEXT,success INTEGER,data TEXT,raw TEXT,error TEXT);
        CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY,source TEXT,listing_id TEXT,body TEXT);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,source TEXT,listing_id TEXT,body TEXT);
        CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY,run_id TEXT,source TEXT,url TEXT,observed_at TEXT,status INTEGER,elapsed_s REAL,error TEXT);
        CREATE TABLE IF NOT EXISTS controls(source TEXT PRIMARY KEY,last_request_at REAL);
        CREATE INDEX IF NOT EXISTS snapshot_lookup ON snapshots(source,listing_id,observed_at);
        ''')
        if 'advertised_total' not in [r[1] for r in self.db.execute('PRAGMA table_info(pages)')]: self.db.execute('ALTER TABLE pages ADD COLUMN advertised_total INTEGER')
        self.db.commit()
    def close(self): self.db.close()
    def record(self,run,source,lid,row,raw,error=None):
        at=now();bid=uuid.uuid4().hex
        batch=dict(version=listings.VERSION,batch_id=bid,source=source,scope_id='individual:'+lid,
            scope=dict(coverage_type='tracked_listing_ids',definition='Individual public detail; errors never prove absence',listing_ids=[lid]),
            observed_at=at,completeness='partial' if row else 'failed',check_evidence='Public detail observation; search omissions do not imply withdrawal',
            data_kind='real',rights=dict(basis='public_terms_review',evidence='Local private noncommercial factual-field evaluation; source terms reviewed; no redistribution or bulk clearance claimed',local_retention_allowed=True,url_retention_allowed=True),records=[row] if row else [])
        batch=listings.validate(batch)
        old=[json.loads(r[0]) for r in self.db.execute('SELECT body FROM batches WHERE source=? AND listing_id=? ORDER BY rowid',(source,lid))]
        previous=listings.replay(old)['events'] if old else []
        history=listings.replay(old+[batch])
        with self.db:
            self.db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,?,?)',(bid,run,source,lid,at,int(row is not None),encoded(row) if row else None,encoded(raw),error))
            self.db.execute('INSERT INTO batches VALUES(?,?,?,?)',(bid,source,lid,encoded(batch)))
            for i,e in enumerate(history['events'][len(previous):]): self.db.execute('INSERT INTO events VALUES(?,?,?,?)',(bid+':'+str(i),source,lid,encoded(e)))
            self.db.execute("UPDATE jobs SET state=?,error=? WHERE run_id=? AND kind='detail' AND listing_id=?",('done' if row else 'error',error,run,lid))
    def history(self,source,lid):
        return [dict(r)|dict(data=json.loads(r['data']) if r['data'] else None,raw=json.loads(r['raw'])) for r in self.db.execute('SELECT observed_at,success,data,raw,error FROM snapshots WHERE source=? AND listing_id=? ORDER BY rowid',(source,lid))]
    def events(self,source,lid):
        return [json.loads(r[0]) for r in self.db.execute('SELECT body FROM events WHERE source=? AND listing_id=? ORDER BY rowid',(source,lid))]
    def search(self,source=None,municipality=None,min_price=0,max_price=1e15,limit=100):
        if not 1<=limit<=1000: raise ValueError('Query limit 1..1000')
        rows=self.db.execute('''SELECT s.* FROM snapshots s WHERE success=1 AND rowid=(SELECT MAX(t.rowid) FROM snapshots t WHERE t.source=s.source AND t.listing_id=s.listing_id AND success=1) ORDER BY observed_at DESC''')
        out=[]
        for r in rows:
            d=json.loads(r['data'])
            if source and r['source']!=source or municipality and d.get('municipality')!=municipality: continue
            if not min_price<=d.get('price_jpy',0)<=max_price: continue
            last=self.db.execute('SELECT observed_at,success,error FROM snapshots WHERE source=? AND listing_id=? ORDER BY rowid DESC LIMIT 1',(r['source'],r['listing_id'])).fetchone()
            first=self.db.execute('SELECT MIN(observed_at) FROM snapshots WHERE source=? AND listing_id=? AND success=1',(r['source'],r['listing_id'])).fetchone()[0]
            discovery=self.db.execute('SELECT first_seen_at,last_discovered_at FROM discovered WHERE source=? AND listing_id=?',(r['source'],r['listing_id'])).fetchone()
            uncertain=any(e['kind']=='identity_review_required' for e in self.events(r['source'],r['listing_id']))
            state='unknown_identity' if uncertain else 'presence_observed' if last['success'] else 'unknown_coverage'
            out.append(dict(source=r['source'],listing_id=r['listing_id'],first_discovered_at=discovery[0] if discovery else None,first_seen_at=first,last_seen_at=r['observed_at'],last_check_at=last['observed_at'],state=state,identity_status='review_required' if uncertain else 'source_isolated',data=d,metadata=json.loads(r['raw'])))
            if len(out)>=limit: break
        return out
    def summary(self,source):
        n=self.db.execute('SELECT COUNT(*) FROM discovered WHERE source=?',(source,)).fetchone()[0]
        rows=[json.loads(r[0]) for r in self.db.execute('SELECT data FROM snapshots WHERE source=? AND success=1',(source,))]
        unique=self.db.execute('SELECT COUNT(DISTINCT listing_id) FROM snapshots WHERE source=? AND success=1',(source,)).fetchone()[0]
        fields=['municipality','town','station','walk_minutes','area_m2','built_year','layout','structure','price_jpy']
        latest=self.search(source=source,limit=1000)
        completeness={k:sum(r['data'].get(k) is not None and r['data'].get(k)!='' for r in latest)/len(latest) if latest else None for k in fields}
        completeness.update({k:sum(r['metadata'].get(k) is not None and r['metadata'].get(k)!='' for r in latest)/len(latest) if latest else None for k in ['name','built_month']})
        return dict(source=source,discovered_unique=n,successful_unique=unique,successful_snapshots=len(rows),failed_observations=self.db.execute('SELECT COUNT(*) FROM snapshots WHERE source=? AND success=0',(source,)).fetchone()[0],list_pages_scanned=self.db.execute('SELECT COUNT(*) FROM pages JOIN runs ON pages.run_id=runs.id WHERE runs.source=?',(source,)).fetchone()[0],error_counts=[dict(r) for r in self.db.execute('SELECT error,COUNT(*) n FROM snapshots WHERE source=? AND error IS NOT NULL GROUP BY error',(source,))],request_errors=[dict(r) for r in self.db.execute('SELECT url,status,error,observed_at FROM requests WHERE source=? AND error IS NOT NULL',(source,))],field_completeness=completeness,completeness_denominator=min(unique,1000),runs=[dict(r) for r in self.db.execute('SELECT * FROM runs WHERE source=? ORDER BY started_at',(source,))],database=str(self.path.resolve()))


class PublicHTTP:
    def __init__(self,store,source,run,interval=10):
        self.store=store;self.source=source;self.run=run;self.interval=interval;self.clients={};self.robot=None
    def get(self,url,media='text/html',check=True):
        u=urlsplit(url);origin=f'{u.scheme}://{u.netloc}'
        permitted={SOURCES[self.source]['origin'],f'{urlsplit(SOURCES[self.source]["terms"]).scheme}://{urlsplit(SOURCES[self.source]["terms"]).netloc}'}
        if origin not in permitted or u.scheme!='https' or u.username or u.fragment: raise StopCollection('Unapproved URL')
        if check and (self.robot is None or not self.robot.can_fetch(url,UA)): raise StopCollection('Robots_disallow')
        last=self.store.db.execute('SELECT last_request_at FROM controls WHERE source=?',(self.source,)).fetchone()
        if last: time.sleep(max(0,self.interval-(time.time()-last[0])))
        with self.store.db: self.store.db.execute('INSERT OR REPLACE INTO controls VALUES(?,?)',(self.source,time.time()))
        if origin not in self.clients:
            self.clients[origin]=Client(origin,self.store.path.parent/('unused-'+self.source+'.json'),timeout=20,interval=self.interval,retries=0)
        c=self.clients[origin];start=time.monotonic();status=None;error=None
        try:
            status,body,kind=c.get(u.path+('?' +u.query if u.query else ''),{'User-Agent':UA},conditional=False)
            if status!=200: raise StopCollection('HTTP_'+str(status))
            if media not in kind: raise StopCollection('Media_changed')
            soup=BeautifulSoup(body,'html.parser')
            if soup.title and re.search('captcha|access denied|just a moment|アクセス制限|認証',soup.title.get_text(),re.I): raise StopCollection('Access_challenge')
            return body
        except ValueError as e:
            if c.logs: status=c.logs[-1]['status']
            error='HTTP_'+str(status) if status and status!=200 else str(e)
            raise StopCollection(error) from None
        finally:
            with self.store.db: self.store.db.execute('INSERT INTO requests(run_id,source,url,observed_at,status,elapsed_s,error) VALUES(?,?,?,?,?,?,?)',(self.run,self.source,url,now(),status,time.monotonic()-start,error))
    def review(self):
        if self.source=='athome': raise StopCollection('Terms_explicitly_prohibit_crawlers; verified 2026-11-09 https://www.athome.co.jp/help/kiyaku.html')
        text=self.get(SOURCES[self.source]['origin']+'/robots.txt','text/plain',check=False)
        self.robot=Protego.parse(text)
        rate=self.robot.request_rate(UA);delay=self.robot.crawl_delay(UA)
        self.interval=max(self.interval,float(delay or 0),float(rate.seconds/rate.requests) if rate else 0)
        if self.interval>60: raise StopCollection('Site_delay_exceeds_run_budget')
        body=self.get(SOURCES[self.source]['terms'],check=False)
        if self.source=='suumo' and terms_hash(body)!=TERMS_HASH: raise StopCollection('Terms_changed_review_required')
        # Other providers are probed, not automatically approved by a hash match.
        return hashlib.sha256(body.encode()).hexdigest()


class SuumoDiscovery:
    source='suumo'
    def entry(self,url):
        if not re.fullmatch(r'https://suumo\.jp/ms/chuko/tokyo/sc_[a-z]+/',url): raise ValueError('Canonical Tokyo municipality entry required')
        return url
    def discover(self,html,url,entry):
        soup=BeautifulSoup(html,'html.parser')
        if not soup.title or '中古マンション' not in soup.title.get_text(): raise ValueError('Search schema changed')
        hit=soup.select_one('.pagination_set-hit')
        if hit is None: raise ValueError('Search result count missing')
        m=re.search(r'([\d,]+)\s*件',hit.get_text());total=int(m[1].replace(',','')) if m else None
        if total is None: raise ValueError('Count unparsed')
        links={}
        for card in soup.select('.property_unit'):
            for a in card.select('a[href]'):
                u=urlsplit(urljoin(url,a['href']));canonical=urlunsplit((u.scheme,u.netloc,u.path,'',''))
                if not canonical.startswith(entry): continue
                try: lid=SuumoAdapter().listing_id(canonical)
                except ValueError: continue
                links[lid]=canonical
        if total and not links: raise ValueError('No main search result links')
        current_query=parse_qs(urlsplit(url).query)
        pn=int(current_query.get('page',current_query.get('pn',['1']))[0]);nexts=[]
        for a in soup.select('.pagination a[href],.pagination_set a[href]'):
            target=urljoin(url,a['href']);u=urlsplit(target);q=parse_qs(u.query)
            if u.scheme+'://'+u.netloc+u.path!=entry or set(q)-{'pn','page'} or len(q)>1: continue
            parameter='page' if 'page' in q else 'pn'
            try: number=int(q.get(parameter,['1'])[0])
            except ValueError: continue
            if number==pn+1: nexts.append(entry+'?'+urlencode({parameter:number}))
        return links,min(nexts) if nexts else None,total


class HomesDiscovery:
    source='homes'
    def entry(self,url):
        if not re.fullmatch(r'https://www\.homes\.co\.jp/mansion/chuko/tokyo/[a-z-]+/list/',url): raise ValueError('Canonical HOME\'S municipality entry required')
        return url
    def discover(self,html,url,entry):
        soup=BeautifulSoup(html,'html.parser');links={}
        # This adapter remains unverified until a permitted live list is obtained.
        for a in soup.select('a[href]'):
            target=urljoin(url,a['href']);m=re.fullmatch(r'https://www\.homes\.co\.jp/mansion/b-(\d+)/?(?:\?.*)?',target)
            if m: links[m[1]]='https://www.homes.co.jp/mansion/b-'+m[1]+'/'
        if not links: raise ValueError('HOME\'S list schema unverified')
        nxt=soup.select_one('a[rel="next"][href]');nexturl=urljoin(url,nxt['href']) if nxt else None
        if nexturl and not nexturl.startswith(entry): raise ValueError('Out-of-scope pagination')
        return links,nexturl,None


class AthomeDiscovery:
    source='athome'
    def entry(self,url):
        if not re.fullmatch(r'https://www\.athome\.co\.jp/mansion/chuko/tokyo/[a-z-]+/list/',url): raise ValueError('Canonical at home entry required')
        return url
    def discover(self,html,url,entry):
        soup=BeautifulSoup(html,'html.parser');links={}
        for a in soup.select('a[href]'):
            target=urljoin(url,a['href']);m=re.fullmatch(r'https://www\.athome\.co\.jp/mansion/(\d+)/?(?:\?.*)?',target)
            if m: links[m[1]]='https://www.athome.co.jp/mansion/'+m[1]+'/'
        if not links: raise ValueError('at home list schema unverified')
        nxt=soup.select_one('a[rel="next"][href]');nexturl=urljoin(url,nxt['href']) if nxt else None
        if nexturl and not nexturl.startswith(entry): raise ValueError('Out-of-scope pagination')
        return links,nexturl,None


ADAPTERS={a.source:a for a in [SuumoDiscovery(),HomesDiscovery(),AthomeDiscovery()]}


def suumo_detail(html,url):
    soup=BeautifulSoup(html,'html.parser');raw={}
    allowed={'物件名','所在地','住所','交通','構造・階建て','構造','完成時期(築年月)','価格','専有面積','間取り'}
    for th in soup.select('th'):
        label=normalized((th.select_one('.fl') or th).get_text()).replace('ヒント','');td=th.find_next_sibling('td')
        if label not in allowed or td is None: continue
        for node in td.select('script,style,input,select,button,[hidden]'): node.decompose()
        value=td.get_text(' ',strip=True).split('[')[0].strip();raw.setdefault(label,[]).append(value)
    for key in raw: raw[key]=list(dict.fromkeys(raw[key]))
    def one(key):
        v=raw.get(key,[]);return v[0] if len(v)==1 else None
    try: row=SuumoAdapter().parse(html,url)
    except ValueError as exc:
        actual=normalized(one('間取り') or '')
        if str(exc)!='Ambiguous layout' or not re.fullmatch(r'(?:[1-9]\d?(?:R|K|DK|LDK|SLDK|SDK)(?:\+\d*S(?:\(納戸\))?)?|ワンルーム)',actual): raise
        # Reuse all existing price/area/year/identity checks; replace only the
        # temporary validation input, then immediately restore the actual layout.
        for th in soup.select('th'):
            label=normalized((th.select_one('.fl') or th).get_text()).replace('ヒント','')
            if label=='間取り' and th.find_next_sibling('td'): th.find_next_sibling('td').string='1LDK'
        row=SuumoAdapter().parse(str(soup),url);row['layout']=actual
    address=one('所在地') or one('住所')
    if address:
        m=re.match(r'東京都(.+?[市区]|.+?郡.+?[町村])(.+)',normalized(address))
        if m:
            row['municipality']=m[1]
            town=re.split(r'[0-9０-９]',m[2])[0].rstrip('-－')
            if town: row['town']=town
    transport=one('交通')
    if transport:
        m=re.search(r'[「｢]([^」｣]+)[」｣]',transport)
        if m: row['station']=m[1]
        # Bus plus stop walking is not station walking; unknown is preserved.
        walking=re.search(r'[」｣]\s*(?:徒歩|歩)\s*(\d+)分',transport)
        if walking and 'バス' not in transport: row['walk_minutes']=int(walking[1])
    structure=one('構造・階建て') or one('構造')
    if structure:
        for token,normed in [('SRC','SRC'),('RC','RC'),('鉄骨鉄筋','SRC'),('鉄筋','RC'),('鉄骨','S')]:
            if token in normalized(structure): row['structure']=normed;break
    built=one('完成時期(築年月)');month=re.search(r'(\d{4})年(\d{1,2})月',normalized(built or ''))
    extra=dict(name=one('物件名'),built_month=int(month[2]) if month else None,field_mapping=raw,missing_fields=[k for k in ['municipality','town','station','walk_minutes','structure'] if k not in row])
    return row,extra


def run(db,source,entry,*,max_pages=3,max_details=20,recheck_hours=24,resume=False,local_private_only=False,transport_factory=PublicHTTP,store_factory=Store):
    if not local_private_only: raise ValueError('Only local/private/noncommercial evaluation is enabled')
    if not 1<=max_pages<=20 or not 1<=max_details<=100 or recheck_hours<0: raise ValueError('Invalid bounded run budget')
    adapter=ADAPTERS[source];adapter.entry(entry);store=store_factory(db)
    lock=None if getattr(store,'database_worker_lock',False) else Path(str(db)+'.collector.lock')
    if lock is not None:
        try: lock.touch(exist_ok=False)
        except FileExistsError: store.close();raise ValueError('Collector locked; inspect interrupted process') from None
    try:
        if getattr(store,'database_worker_lock',False):
            # Acquiring the sole writer lock proves no previous PG worker remains.
            with store.db: store.db.execute("UPDATE runs SET status='interrupted',updated_at=? WHERE status='running'",(now(),))
        fingerprint=hashlib.sha256((source+entry).encode()).hexdigest()
        if not resume and store.db.execute("SELECT 1 FROM runs WHERE scope=? AND status IN ('paused','interrupted','blocked')",(fingerprint,)).fetchone():
            # A fresh scope traversal can supersede old pending work explicitly;
            # preserve old rows for audit rather than running both queues later.
            with store.db: store.db.execute("UPDATE runs SET status='superseded',updated_at=? WHERE scope=? AND status IN ('paused','interrupted','blocked')",(now(),fingerprint))
        old=store.db.execute("SELECT * FROM runs WHERE scope=? AND status IN ('paused','interrupted','blocked') ORDER BY started_at DESC LIMIT 1",(fingerprint,)).fetchone() if resume else None
        rid=old['id'] if old else uuid.uuid4().hex
        if not old:
            with store.db:
                store.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',(rid,source,entry,fingerprint,'running',now(),now(),None))
                store.db.execute('INSERT INTO jobs(run_id,kind,url) VALUES(?,?,?)',(rid,'list',entry))
        else:
            with store.db:store.db.execute("UPDATE runs SET status='running',updated_at=? WHERE id=?",(now(),rid))
        client=transport_factory(store,source,rid);pages=0;success=0;failures=[];error=None
        try:
            latest=store.db.execute("SELECT status,error,observed_at FROM requests WHERE source=? AND (status IN (403,429) OR error='Access_challenge') ORDER BY id DESC LIMIT 1",(source,)).fetchone()
            if latest and (latest['status'] in {403,429} or latest['error']=='Access_challenge') and datetime.now(timezone.utc)-datetime.fromisoformat(latest['observed_at'])<timedelta(hours=24): raise StopCollection('Access_restriction_cooldown_24h')
            client.review()
            while pages<max_pages:
                job=store.db.execute("SELECT * FROM jobs WHERE run_id=? AND kind='list' AND state='pending' ORDER BY rowid LIMIT 1",(rid,)).fetchone()
                if not job: break
                html=client.get(job['url']);links,nxt,total=adapter.discover(html,job['url'],entry)
                existing_queue=store.db.execute("SELECT COUNT(*) FROM jobs WHERE run_id=? AND state='pending'",(rid,)).fetchone()[0]
                if len(links)>300: raise StopCollection('Discovery_page_budget_300')
                if existing_queue+len(links)+1>1000: break # Drain bounded detail work before resuming this page.
                pages+=1
                with store.db:
                    for lid,url in links.items():
                        store.db.execute('INSERT OR IGNORE INTO page_links VALUES(?,?,?)',(rid,job['url'],lid))
                        store.db.execute('INSERT INTO discovered VALUES(?,?,?,?,?) ON CONFLICT(source,listing_id) DO UPDATE SET last_discovered_at=excluded.last_discovered_at,url=excluded.url',(source,lid,url,now(),now()))
                        last=store.db.execute('SELECT observed_at FROM snapshots WHERE source=? AND listing_id=? AND success=1 ORDER BY rowid DESC LIMIT 1',(source,lid)).fetchone()
                        due=not last or datetime.now(timezone.utc)-datetime.fromisoformat(last[0])>=timedelta(hours=recheck_hours)
                        if due: store.db.execute('INSERT OR IGNORE INTO jobs(run_id,kind,url,listing_id) VALUES(?,?,?,?)',(rid,'detail',url,lid))
                    if nxt:
                        if store.db.execute("SELECT 1 FROM jobs WHERE run_id=? AND kind='list' AND url=?",(rid,nxt)).fetchone(): raise ValueError('Pagination loop')
                        store.db.execute('INSERT INTO jobs(run_id,kind,url) VALUES(?,?,?)',(rid,'list',nxt))
                    store.db.execute('INSERT OR REPLACE INTO pages VALUES(?,?,?,?,?,?,?)',(rid,job['url'],now(),hashlib.sha256(html.encode()).hexdigest(),len(links),nxt,total))
                    store.db.execute("UPDATE jobs SET state='done' WHERE run_id=? AND kind='list' AND url=?",(rid,job['url']))
                queued=store.db.execute("SELECT COUNT(*) FROM jobs WHERE run_id=? AND state='pending'",(rid,)).fetchone()[0]
                if queued>1000: raise StopCollection('Queue_capacity_1000')
            for _ in range(max_details):
                job=store.db.execute("SELECT * FROM jobs WHERE run_id=? AND kind='detail' AND state='pending' ORDER BY rowid LIMIT 1",(rid,)).fetchone()
                if not job: break
                try:
                    html=client.get(job['url'])
                    if source!='suumo': raise ValueError('Detail adapter unverified; not enabled')
                    row,raw=suumo_detail(html,job['url'])
                    if row.get('municipality') and row['municipality'] not in BeautifulSoup(html,'html.parser').get_text(): raise ValueError('Location mismatch')
                    store.record(rid,source,job['listing_id'],row,raw);success+=1
                except ValueError as exc:
                    store.record(rid,source,job['listing_id'],None,{},str(exc));failures.append(dict(listing_id=job['listing_id'],error=str(exc)))
                    if isinstance(exc,StopCollection): raise
        except ValueError as exc: error=str(exc)
        except BaseException:
            with store.db: store.db.execute("UPDATE runs SET status='interrupted',updated_at=? WHERE id=?",(now(),rid))
            raise
        pending=store.db.execute("SELECT COUNT(*) FROM jobs WHERE run_id=? AND state='pending'",(rid,)).fetchone()[0]
        totals=[r[0] for r in store.db.execute('SELECT DISTINCT advertised_total FROM pages WHERE run_id=? AND advertised_total IS NOT NULL',(rid,))]
        discovered=store.db.execute('SELECT COUNT(DISTINCT listing_id) FROM page_links WHERE run_id=?',(rid,)).fetchone()[0]
        list_pending=store.db.execute("SELECT COUNT(*) FROM jobs WHERE run_id=? AND kind='list' AND state='pending'",(rid,)).fetchone()[0]
        if not list_pending and totals and (len(totals)!=1 or totals[0]!=discovered): error=error or 'Search_count_or_pagination_changed; start a fresh discovery run'
        errors_n=store.db.execute("SELECT COUNT(*) FROM jobs WHERE run_id=? AND state='error'",(rid,)).fetchone()[0]
        state='blocked' if error else 'paused' if pending else 'completed_with_errors' if errors_n else 'completed'
        with store.db: store.db.execute('UPDATE runs SET status=?,updated_at=?,error=? WHERE id=?',(state,now(),error,rid))
        result=dict(run_id=rid,source=source,entry=entry,status=state,pages_scanned_this_invocation=pages,successful_this_invocation=success,failures=failures,error=error,pending_jobs=pending,summary=store.summary(source))
        result['discovered_this_run']=discovered
        result['detail_jobs_this_run']=store.db.execute("SELECT COUNT(*) FROM jobs WHERE run_id=? AND kind='detail'",(rid,)).fetchone()[0]
        return result
    finally:
        try:
            if lock is not None: lock.unlink()
        finally: store.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--backend',choices=['postgresql','sqlite']);p.add_argument('command',choices=['collect','summary','search']);p.add_argument('--database',type=Path,default=Path('data/listing-extension/listings.sqlite3'));p.add_argument('--source',choices=SOURCES,default='suumo');p.add_argument('--entry');p.add_argument('--max-pages',type=int,default=3);p.add_argument('--max-details',type=int,default=20);p.add_argument('--recheck-hours',type=float,default=24);p.add_argument('--resume',action='store_true');p.add_argument('--local-private-only',action='store_true');a=p.parse_args()
    active=Path('data/postgres-runtime/active.json').exists()
    backend=a.backend or ('postgresql' if active else 'sqlite')
    factory=Store
    if backend=='postgresql':
        from .pg_store import PostgresStore
        factory=PostgresStore
    elif active and a.command=='collect' and a.database.resolve()==Path('data/listing-extension/listings.sqlite3').resolve():
        raise ValueError('Original SQLite is frozen after verified cutover')
    if a.command=='collect': result=run(a.database,a.source,a.entry,max_pages=a.max_pages,max_details=a.max_details,recheck_hours=a.recheck_hours,resume=a.resume,local_private_only=a.local_private_only,store_factory=factory)
    else:
        s=factory(a.database)
        try: result=s.summary(a.source) if a.command=='summary' else s.search(source=a.source)
        finally:s.close()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if a.command=='collect' and result['status'] in {'blocked','completed_with_errors'}: raise SystemExit(2)

if __name__=='__main__': main()
