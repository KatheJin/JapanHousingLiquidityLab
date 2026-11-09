"""Owned-loopback HTML adapter. A third-party adapter requires separate permission review."""
import argparse
from datetime import datetime,timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import uuid
from .net_http import Client,NetworkError,save
from . import listings


class Page(HTMLParser):
    def __init__(self,body):
        super().__init__(convert_charrefs=True);self.meta={};self.links=[];self.next=[];self.fields={};self.field=None;self.feed(body)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='html': self.meta=a
        if tag=='a' and a.get('class')=='listing': self.links.append(a.get('href',''))
        if tag=='a' and a.get('rel')=='next': self.next.append(a.get('href',''))
        if tag=='dd':
            self.field=a.get('data-field')
            if self.field in self.fields: raise ValueError('Duplicate HTML field')
            if self.field: self.fields[self.field]=''
    def handle_data(self,data):
        if self.field: self.fields[self.field]+=data
    def handle_endtag(self,tag):
        if tag=='dd': self.field=None


def crawl(origin,workspace,journal,**options):
    if urlsplit(origin).hostname not in {'127.0.0.1','localhost','::1'}: raise ValueError('Only owned loopback simulator is enabled')
    workspace=Path(workspace);workspace.mkdir(parents=True,exist_ok=True)
    lock=workspace/'writer.lock'
    try: lock.touch(exist_ok=False)
    except FileExistsError: raise ValueError('Crawler locked; inspect interrupted writer before recovery') from None
    try: return _crawl(origin,workspace,Path(journal),**options)
    finally: lock.unlink()


def _crawl(origin,work,journal,**options):
    start=time.monotonic();client=Client(origin,work/'cache.json',**options)
    outbox=work/'pending.json'
    if outbox.exists():
        pending=json.loads(outbox.read_text(encoding='utf-8'));listings.ingest(journal,pending);outbox.unlink()
    records=[];errors=[];visited=set();seen=set();generation=None;scope=None;total=None;path='/listings?page=1'
    def page(path):
        if not robot.can_fetch('*',origin+path): raise ValueError('robots disallows path')
        status,body,kind=client.get(path)
        if status not in {200,304} or 'text/html' not in kind: raise ValueError('HTTP or media type failure')
        p=Page(body)
        if p.meta.get('data-schema')!='listing-v1' or p.meta.get('data-generation') is None: raise ValueError('HTML schema changed')
        return p
    robot=RobotFileParser()
    try:
        status,body,kind=client.get('/robots.txt')
        if status not in {200,304}: raise ValueError('robots unavailable')
        robot.parse(body.splitlines());client.interval=max(client.interval,robot.crawl_delay('*') or 0)
        rate=robot.request_rate('*')
        if rate: client.interval=max(client.interval,rate.seconds/rate.requests)
        while path:
            if path in visited or len(visited)>=100: raise ValueError('Pagination loop or page budget')
            if not path.startswith('/listings?'): raise ValueError('Unexpected pagination target')
            visited.add(path);p=page(path)
            if generation is None: generation=p.meta['data-generation'];scope=p.meta.get('data-scope');total=int(p.meta['data-total'])
            if p.meta['data-generation']!=generation or p.meta.get('data-scope')!=scope or int(p.meta['data-total'])!=total or len(p.next)>1: raise ValueError('Coverage/revision changed during crawl')
            for link in p.links:
                if not link.startswith('/listing/') or '?' in link or link in seen or len(seen)>=1000: raise ValueError('Invalid/duplicate detail link')
                seen.add(link)
                try:
                    d=page(link)
                    if d.meta['data-generation']!=generation: raise ValueError('Mixed revision')
                    r=d.fields
                    if r.get('listing_id')!=link.split('/')[-1] or not {'price_jpy','area_m2','municipality','station'}.issubset(r): raise ValueError('Detail fields missing')
                    for k in ['price_jpy','area_m2','walk_minutes','built_year']:
                        if k in r: r[k]=float(r[k])
                    r.update(status='present',evidence='Owned synthetic HTML observation')
                    listings.validate(batch(origin,[r],'partial','validation',scope))
                    records.append(r)
                except (ValueError,UnicodeError) as exc: errors.append(dict(path=link,error=type(exc).__name__))
            path=p.next[0] if p.next else None
        if len(seen)!=total or len(records)!=total: raise ValueError('Count/integrity mismatch')
        # Revalidate first page after traversal to detect concurrent revision changes.
        if page('/listings?page=1').meta['data-generation']!=generation: raise ValueError('Revision changed at completion')
    except (ValueError,UnicodeError) as exc: errors.append(dict(path=path,error=type(exc).__name__))
    old_scope=work/'scope.json'
    if old_scope.exists() and json.loads(old_scope.read_text(encoding='utf-8'))!=scope: errors.append(dict(path=None,error='ScopeChanged'))
    if not errors: save(old_scope,scope)
    complete='complete' if not errors else 'partial' if records else 'failed'
    b=batch(origin,records,complete,str(uuid.uuid4()),scope)
    # Persist before committing: interruption can replay this exact batch idempotently.
    save(outbox,b);listings.ingest(journal,b);outbox.unlink()
    result=dict(batch_id=b['batch_id'],completeness=complete,records=len(records),quarantine=errors,pages=len(visited),elapsed_s=time.monotonic()-start,**client.metrics())
    save(work/(b['batch_id']+'-run.json'),dict(summary=result,requests=client.logs))
    return result


def batch(origin,records,complete,bid,scope):
    return dict(version=listings.VERSION,batch_id=bid,source='owned-html:'+origin,scope_id='all-owned',
        scope=dict(coverage_type='entire_source_feed',definition='Owned synthetic feed; immutable scope verified separately',listing_ids=[]),
        observed_at=datetime.now(timezone.utc).isoformat(),completeness=complete,check_evidence='Owned HTML pagination/count/revision validation; failures prohibit absence inference',
        data_kind='synthetic',rights=dict(basis='synthetic',evidence='Project-owned synthetic server',local_retention_allowed=True,url_retention_allowed=False),records=records)


def main():
    p=argparse.ArgumentParser();p.add_argument('--origin',default='http://127.0.0.1:8765');p.add_argument('--workspace',type=Path,default=Path('data/task012/crawler'));p.add_argument('--journal',type=Path,default=Path('data/task012/journal.json'));a=p.parse_args()
    print(json.dumps(crawl(a.origin,a.workspace,a.journal),ensure_ascii=False))

if __name__=='__main__': main()
