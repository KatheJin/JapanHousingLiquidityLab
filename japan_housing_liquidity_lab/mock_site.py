"""Owned synthetic HTML site; no third-party listing collection."""
import argparse
from datetime import datetime,timezone
from email.utils import format_datetime
import hashlib
import html
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit,parse_qs
from .net_http import save


def initial():
    return dict(generation=1,scope='owned-tokyo-v1',faults={},rows=[dict(listing_id=str(i),price_jpy=60000000+i*1000000,area_m2=70,municipality='架空区',town='架空町',station='架空駅',walk_minutes=10,built_year=2005,layout='2LDK',structure='RC') for i in range(1,6)])


def server(state_path,port=0):
    counts={};lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            s=json.loads(Path(state_path).read_text(encoding='utf-8'));route=urlsplit(self.path).path
            fault=s.get('faults',{}).get(self.path,s.get('faults',{}).get(route,[]));key=(self.path,json.dumps(fault,sort_keys=True))
            with lock: n=counts.get(key,0);counts[key]=n+1
            if n<len(fault):
                f=fault[n];time.sleep(f.get('delay',0))
                if f.get('drop'): self.connection.close();return
                if f.get('status',200)!=200:
                    self.send_response(f['status']);self.send_header('Retry-After',str(f.get('retry_after',0)));self.end_headers();return
            if route=='/robots.txt': body=s.get('robots','User-agent: *\nAllow: /\nCrawl-delay: 0\n');kind='text/plain'
            elif route=='/listings':
                page=int(parse_qs(urlsplit(self.path).query).get('page',['1'])[0]);rows=s['rows'];part=rows[(page-1)*2:page*2]
                links=''.join(f'<a class="listing" href="/listing/{html.escape(r["listing_id"],quote=True)}">合成住宅</a>' for r in part)
                next_link=f'<a rel="next" href="/listings?page={page+1}">次へ</a>' if page*2<len(rows) else ''
                if s.get('loop'): next_link='<a rel="next" href="/listings?page=1">loop</a>'
                body=f'<html data-schema="listing-v1" data-generation="{s["generation"]}" data-scope="{s["scope"]}" data-total="{len(rows)}"><h1>架空中古マンション</h1>{links}{next_link}</html>';kind='text/html'
            elif route.startswith('/listing/'):
                row=next((r for r in s['rows'] if r['listing_id']==route.split('/')[-1]),None)
                if row is None: self.send_response(404);self.end_headers();return
                fields=''.join(f'<dt>{k}</dt><dd data-field="{k}">{html.escape(str(v))}</dd>' for k,v in row.items())
                body=f'<html data-schema="listing-v1" data-generation="{s["generation"]}"><h1>合成住戸</h1><dl>{fields}</dl></html>';kind='text/html'
            else: self.send_response(404);self.end_headers();return
            if s.get('broken') and route!='/robots.txt': body='<html>changed structure</html>'
            raw=body.encode();etag='"'+hashlib.sha256(raw).hexdigest()+'"'
            # Last-Modified changes with the scenario revision, including rapid updates.
            modified=format_datetime(datetime.fromtimestamp(1794182400+int(s['generation']),timezone.utc),usegmt=True)
            not_modified=self.headers.get('If-None-Match')==etag or ('If-None-Match' not in self.headers and self.headers.get('If-Modified-Since')==modified)
            self.send_response(304 if not_modified else 200);self.send_header('ETag',etag);self.send_header('Last-Modified',modified);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(0 if not_modified else len(raw)));self.end_headers()
            if not not_modified:
                try: self.wfile.write(raw)
                except OSError: pass
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def main():
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True);p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    if not a.state.exists(): save(a.state,initial())
    print(f'SYNTHETIC owned site http://127.0.0.1:{a.port}',flush=True)
    server(a.state,a.port).serve_forever()

if __name__=='__main__': main()
