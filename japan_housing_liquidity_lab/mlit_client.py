"""XIT001: private local credentials, scoped acquisition and header-only authentication."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode
from .net_http import Client,save

ORIGIN='https://www.reinfolib.mlit.go.jp'
KEY_NAME='JHLL_REINFOLIB_API_KEY'
PRIVATE_CONFIG=Path(__file__).resolve().parent.parent/'.env.mlit-local'

def load_credential(config=PRIVATE_CONFIG):
    key=os.environ.get(KEY_NAME) or os.environ.get('REINFOLIB_API_KEY')
    if not key and Path(config).exists():
        config=Path(config).resolve()
        ignored=subprocess.run(['git','check-ignore','--quiet','--',str(config)],cwd=config.parent,capture_output=True).returncode==0
        tracked=subprocess.run(['git','ls-files','--error-unmatch','--',str(config)],cwd=config.parent,capture_output=True).returncode==0
        if not ignored or tracked:raise ValueError('Private credential file must be Git-ignored and untracked')
        values=[]
        for line in config.read_text(encoding='utf-8-sig').splitlines():
            line=line.strip()
            if not line or line.startswith('#'):continue
            if line.startswith('export '):line=line[7:].lstrip()
            name,sep,value=line.partition('=')
            if name.strip()!=KEY_NAME or not sep:continue
            value=value.strip()
            if len(value)>=2 and value[0]==value[-1] and value[0] in {'"',"'"}:value=value[1:-1]
            values.append(value)
        if len(values)!=1:raise ValueError('Private configuration requires exactly one API credential variable')
        key=values[0]
    if not key:raise ValueError('Approved API key unavailable; live test Pending')
    if any(ord(c)<33 or ord(c)>126 for c in key):raise ValueError('Invalid API credential format')
    return key


def fetch_quarter(client,quarter,directory,acquired=(),*,classification='01',city=None):
    if not re.fullmatch(r'20[0-9]{2}Q[1-4]',quarter) or quarter<'2005Q3': raise ValueError('Invalid quarter')
    if classification not in {'01','02'}:raise ValueError('Classification must be 01 or 02')
    if classification=='02' and quarter<'2021Q1':raise ValueError('Contract-price coverage starts at 2021Q1')
    if city is not None and not re.fullmatch(r'13[0-9]{3}',city):raise ValueError('Tokyo municipality code required')
    params=dict(year=int(quarter[:4]),quarter=int(quarter[-1]))
    params.update(dict(city=city) if city else dict(area='13'))
    params.update(priceClassification=classification,language='ja')
    path='/ex-api/external/XIT001?'+urlencode(params)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    stem=quarter if classification=='01' and city is None else quarter+'-price'+classification+('-city'+city if city else '-area13')
    manifest=directory/(stem+'-manifest.json');data_path=directory/(stem+'.json')
    if quarter in acquired: return dict(status='already_acquired_external',quarter=quarter)
    if manifest.exists():
        m=json.loads(manifest.read_text(encoding='utf-8'))
        if m.get('source')!=client.origin+path:raise ValueError('Stored request scope mismatch')
        if not data_path.exists() or hashlib.sha256(data_path.read_bytes()).hexdigest()!=m['sha256']: raise ValueError('Stored quarter integrity failure')
        return m
    key=load_credential() if client.origin==ORIGIN else 'LOCAL-SIMULATION-NOT-A-KEY'
    if client.origin!=ORIGIN and client.u.hostname not in {'127.0.0.1','localhost','::1'}: raise ValueError('Unapproved API origin')
    status,body,kind=client.get(path,{'Ocp-Apim-Subscription-Key':key},conditional=False)
    if key in body:raise ValueError('Response unexpectedly contains credential; persistence refused')
    if status==404: return dict(status='not_available_or_no_data',quarter=quarter,classification=classification,city=city) # Never mark acquired.
    if status!=200 or 'json' not in kind: raise ValueError('API HTTP/media failure')
    payload=json.loads(body)
    if not isinstance(payload,dict) or payload.get('status')!='OK' or not isinstance(payload.get('data'),list) or not payload['data']: raise ValueError('API schema/empty response requires review')
    seen=set();duplicates=0
    for r in payload['data']:
        if not isinstance(r,dict) or not all(isinstance(r.get(k),str) for k in ['Type','TradePrice','Area','Period','MunicipalityCode']): raise ValueError('API row schema changed')
        if not r['MunicipalityCode'].startswith('13') or (city and r['MunicipalityCode']!=city) or r['Period']!=f'{quarter[:4]}年第{quarter[-1]}四半期': raise ValueError('API coverage mismatch')
        fingerprint=hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest();duplicates+=fingerprint in seen;seen.add(fingerprint)
    # Preserve legitimate anonymous duplicate trades; deduplicate acquisition units only.
    save(data_path,payload)
    m=dict(status='acquired',quarter=quarter,acquired_at=datetime.now(timezone.utc).isoformat(),records=len(payload['data']),exact_duplicate_rows=duplicates,
           sha256=hashlib.sha256(data_path.read_bytes()).hexdigest(),fields=sorted({k for r in payload['data'] for k in r}),source=client.origin+path,publication_date=None,classification=classification,city=city)
    save(manifest,m);return m


def main():
    p=argparse.ArgumentParser();p.add_argument('--published',type=Path,required=True,help='Operator-verified JSON list, not inferred from calendar');p.add_argument('--acquired',type=Path,help='JSON list already held for the exact selected classification and region');p.add_argument('--classification',choices=['01','02'],default='01');p.add_argument('--city');p.add_argument('--directory',type=Path,default=Path('data/task012/mlit'));a=p.parse_args()
    quarters=json.loads(a.published.read_text(encoding='utf-8'));acquired=json.loads(a.acquired.read_text(encoding='utf-8')) if a.acquired else []
    if not isinstance(quarters,list) or not isinstance(acquired,list): raise ValueError('Quarter lists required')
    c=Client(ORIGIN,a.directory/'http-cache.json',interval=10,timeout=30,retries=1)
    try:
        for q in sorted(set(quarters)): print(json.dumps(fetch_quarter(c,q,a.directory,acquired,classification=a.classification,city=a.city)))
    finally: save(a.directory/'request-log.json',dict(metrics=c.metrics(),requests=c.logs))

if __name__=='__main__': main()
