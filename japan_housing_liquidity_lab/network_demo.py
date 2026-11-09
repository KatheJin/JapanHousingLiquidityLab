"""Repeatable real-loopback-HTTP experiment; exports Task010 journal for Streamlit."""
import argparse
import json
from pathlib import Path
import threading
from .mock_site import server,initial
from .net_http import save
from .crawler import crawl
from . import listings


def run(out):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=False)
    state=out/'site.json';s=initial();save(state,s);http=server(state);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    origin=f'http://127.0.0.1:{http.server_port}';runs=[]
    def scan(label):
        r=crawl(origin,out/'crawler',out/'journal.json',interval=.01,backoff=.01)
        runs.append(dict(scenario=label,**r));print(json.dumps(runs[-1]),flush=True)
    try:
        scan('initial');scan('conditional_unchanged')
        s['generation']+=1;s['rows'][0]['price_jpy']-=1000000;save(state,s);scan('price_down')
        s['faults']={'/listing/1':[{'status':429,'retry_after':0},{'status':503,'retry_after':0}]};save(state,s);scan('429_503_recovered')
        s['faults']={'/listings?page=2':[{'status':503}]*3};save(state,s);scan('partial_no_absence')
        s['faults']={};removed=s['rows'].pop(0);s['generation']+=1;save(state,s);scan('disappearance')
        s['rows'].insert(0,removed);s['generation']+=1;save(state,s);scan('reappearance')
        report=listings.report(out/'journal.json');listings.export(report,out/'history')
        save(out/'metrics.json',dict(runs=runs,events={k:sum(e['kind']==k for e in report['events']) for k in sorted({e['kind'] for e in report['events']})},real_listing_records=0,official_api='Not exercised by this synthetic network demo; see separate live-verification report'))
        return runs
    finally: http.shutdown();http.server_close();thread.join()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)

if __name__=='__main__': main()
