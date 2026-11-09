"""Bounded GET transport: exact origin, TLS verification, conditional cache, safe logs."""
import gzip
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import socket
import time
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit


class NetworkError(ValueError): pass


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf-8');os.replace(tmp,path)


class Client:
    def __init__(self,origin,cache,timeout=2,interval=1,retries=2,backoff=.25,max_wait=30,sleep=time.sleep,clock=time.monotonic):
        u=urlsplit(origin)
        if u.scheme not in {'https','http'} or u.username or u.password or u.path not in {'','/'} or u.query or u.fragment: raise ValueError('Exact origin required')
        if u.scheme=='http' and u.hostname not in {'127.0.0.1','localhost','::1'}: raise ValueError('Plain HTTP is loopback-only')
        if timeout<=0 or interval<0 or not 0<=retries<=5 or backoff<0 or max_wait<0: raise ValueError('Invalid transport limits')
        self.origin=origin.rstrip('/');self.u=u;self.path=Path(cache)
        stored=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'origin':origin.rstrip('/'),'entries':{}}
        if stored['origin']!=origin.rstrip('/'): raise ValueError('Cache origin mismatch; separate workspace required')
        self.cache=stored['entries']
        self.timeout=timeout;self.interval=interval;self.retries=retries;self.backoff=backoff;self.max_wait=max_wait
        self.sleep=sleep;self.clock=clock;self.last=None;self.logs=[]
    def get(self,path,headers=None,conditional=True):
        if not path.startswith('/') or path.startswith('//') or urlsplit(path).scheme or '#' in path: raise ValueError('Relative same-origin path required')
        cached=self.cache.get(path) if conditional else None
        h={'User-Agent':'JapanHousingLiquidityLab/Task012 (owned simulator or approved API)','Accept-Encoding':'gzip',**(headers or {})}
        if cached:
            if cached.get('etag'): h['If-None-Match']=cached['etag']
            if cached.get('modified'): h['If-Modified-Since']=cached['modified']
        for attempt in range(self.retries+1):
            if self.last is not None: self.sleep(max(0,self.interval-(self.clock()-self.last)))
            start=self.clock();self.last=start;status=None;size=0;rh={};body=b''
            cls=http.client.HTTPSConnection if self.u.scheme=='https' else http.client.HTTPConnection
            conn=cls(self.u.hostname,self.u.port,timeout=self.timeout)
            try:
                conn.request('GET',path,headers=h);r=conn.getresponse();status=r.status;rh={k.lower():v for k,v in r.getheaders()}
                body=r.read(4_000_001);size=len(body)
                if size>4_000_000: raise NetworkError('Response size limit')
                if rh.get('content-encoding')=='gzip':
                    with gzip.GzipFile(fileobj=io.BytesIO(body)) as f: body=f.read(4_000_001)
                    if len(body)>4_000_000: raise NetworkError('Decoded size limit')
            except (OSError,http.client.HTTPException,EOFError) as exc:
                status=None
            finally:
                conn.close()
                self.logs.append(dict(path=urlsplit(path).path,status=status,attempt=attempt+1,elapsed_s=self.clock()-start,bytes=size,failed=status is None or status>=400))
            if status in {None,429,500,503}:
                if attempt==self.retries: raise NetworkError('Retry budget exhausted')
                delay=self.backoff*2**attempt
                if 'retry-after' in rh:
                    try: retry=float(rh['retry-after'])
                    except ValueError:
                        try: retry=(parsedate_to_datetime(rh['retry-after'])-datetime.now(timezone.utc)).total_seconds()
                        except (ValueError,TypeError): raise NetworkError('Invalid Retry-After') from None
                    delay=max(delay,retry)
                if delay>self.max_wait: raise NetworkError('Retry-After exceeds budget; defer run')
                self.sleep(max(0,delay));continue
            if status==304:
                if not cached or hashlib.sha256(cached['body'].encode()).hexdigest()!=cached['sha256']: raise NetworkError('304 without valid cached representation')
                return 304,cached['body'],cached['type']
            if status==200:
                text=body.decode('utf-8')
                if conditional:
                    self.cache[path]=dict(body=text,sha256=hashlib.sha256(body).hexdigest(),etag=rh.get('etag'),modified=rh.get('last-modified'),type=rh.get('content-type',''))
                    save(self.path,dict(origin=self.origin,entries=self.cache))
                return status,text,rh.get('content-type','')
            return status,'',rh.get('content-type','') # No redirect following or credential forwarding.
    def metrics(self):
        n=len(self.logs)
        return dict(attempts=n,failed_attempts=sum(x['failed'] for x in self.logs),failure_rate=sum(x['failed'] for x in self.logs)/n if n else 0,
                    response_bytes=sum(x['bytes'] for x in self.logs),request_elapsed_s=sum(x['elapsed_s'] for x in self.logs))
