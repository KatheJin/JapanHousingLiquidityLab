"""Local, evidence-based listing journal. Standard library only; no network acquisition."""
import argparse
import csv
from datetime import date, datetime, timezone, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid5, NAMESPACE_URL

VERSION = 'task010-v1'
ATTRS = {'municipality','town','station','walk_minutes','area_m2','built_year','age_at_observation','layout','structure'}
ROW_FIELDS = ATTRS | {'listing_id','property_id','match_evidence','source_record_id','url','price_jpy','first_listed_at','status','evidence'}
ABSENT = {'not_observed_complete','provider_withdrawn','provider_sold'}


def stamp(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        if d.tzinfo is None: raise ValueError()
        return d.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Timezone-aware ISO observation timestamp required') from None


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def text(value, name):
    if not isinstance(value,str) or not value.strip(): raise ValueError('Nonempty text required: '+name)
    return value.strip()


def validate(batch):
    allowed={'version','batch_id','source','scope_id','scope','observed_at','completeness','check_evidence','rights','data_kind','records'}
    if not isinstance(batch,dict) or set(batch)-allowed: raise ValueError('Unknown batch fields')
    b=json.loads(canonical(batch))
    if b.get('version')!=VERSION: raise ValueError('Unsupported batch version')
    for k in ['batch_id','source','scope_id','check_evidence']: b[k]=text(b.get(k),k)
    b['observed_at']=stamp(b.get('observed_at'))
    if b.get('data_kind') not in {'synthetic','real'}: raise ValueError('Explicit synthetic/real data_kind required')
    if b.get('completeness') not in {'complete','partial','failed'}: raise ValueError('Invalid completeness')
    rights=b.get('rights',{})
    if not isinstance(rights,dict) or set(rights)-{'basis','evidence','local_retention_allowed','url_retention_allowed'}: raise ValueError('Invalid rights object or unknown fields')
    if rights.get('basis') not in {'synthetic','manual_owned','provider_permission','open_license'} or rights.get('local_retention_allowed') is not True:
        raise ValueError('Documented local retention rights required')
    text(rights.get('evidence'),'rights evidence')
    if not isinstance(rights.get('url_retention_allowed'),bool): raise ValueError('Explicit URL retention permission required')
    if (rights['basis']=='synthetic') != (b['data_kind']=='synthetic'): raise ValueError('Synthetic rights/data_kind mismatch')
    scope=b.get('scope')
    if not isinstance(scope,dict) or set(scope)!={'coverage_type','definition','listing_ids'}: raise ValueError('Explicit stable scope required')
    if scope['coverage_type'] not in {'tracked_listing_ids','entire_source_feed','filtered_search'}: raise ValueError('Unknown scope coverage')
    text(scope['definition'],'scope definition')
    ids=scope['listing_ids']
    if not isinstance(ids,list) or any(not isinstance(x,str) or not x.strip() for x in ids): raise ValueError('Invalid scope listing_ids')
    scope['listing_ids']=ids=[x.strip() for x in ids]
    if len(set(ids))!=len(ids): raise ValueError('Duplicate normalized scope listing_ids')
    if scope['coverage_type']=='tracked_listing_ids' and not ids: raise ValueError('Tracked IDs required')
    records=b.get('records')
    if not isinstance(records,list) or (records and b['completeness']=='failed'): raise ValueError('Failed batches cannot assert records')
    seen=set()
    for r in records:
        if not isinstance(r,dict) or set(r)-ROW_FIELDS: raise ValueError('Unknown record fields; no personal/contact/image fields accepted')
        r['listing_id']=text(r.get('listing_id'),'stable listing_id')
        if r['listing_id'] in seen: raise ValueError('Duplicate listing ID in batch')
        seen.add(r['listing_id'])
        if scope['coverage_type']=='tracked_listing_ids' and r['listing_id'] not in ids: raise ValueError('Record outside tracked IDs')
        status=r.setdefault('status','present')
        if status not in {'present','provider_withdrawn','provider_sold'}: raise ValueError('Invalid explicit record status')
        text(r.get('evidence'),'record status evidence')
        if r.get('property_id') is not None: r['property_id']=text(r['property_id'],'property_id')
        for k in ['price_jpy','area_m2','walk_minutes','built_year','age_at_observation']:
            v=r.get(k)
            if v is not None:
                if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v<0 or (k in {'price_jpy','area_m2','built_year'} and v<=0):
                    raise ValueError('Invalid numeric field: '+k)
                if k in {'built_year','age_at_observation'} and v!=int(v): raise ValueError('Integer year/age required')
                observation_year=datetime.fromisoformat(b['observed_at']).astimezone(timezone(timedelta(hours=9))).year
                if k=='built_year' and v>observation_year: raise ValueError('Future construction year for used condominium')
                r[k]=float(v)
        if r.get('built_year') is not None and r.get('age_at_observation') is not None:
            if observation_year-r['built_year']!=r['age_at_observation']: raise ValueError('Inconsistent year and age (calendar-year convention)')
        for k in ['municipality','town','station','layout','structure','source_record_id','match_evidence']:
            if r.get(k) is not None: text(r[k],k)
        if r.get('first_listed_at') is not None:
            v=r['first_listed_at']
            if isinstance(v,str) and len(v)==10:
                day=date.fromisoformat(v)
                if day>datetime.fromisoformat(b['observed_at']).astimezone(timezone(timedelta(hours=9))).date():
                    raise ValueError('Listing start after observation (Japan calendar date)')
            else:
                r['first_listed_at']=stamp(v)
                if r['first_listed_at']>b['observed_at']: raise ValueError('Listing start after observation')
        if r.get('url') is not None:
            u=urlsplit(r['url'])
            if not rights['url_retention_allowed'] or u.scheme not in {'http','https'} or not u.netloc or u.username or u.query or u.fragment:
                raise ValueError('URL must be permitted public URL without credentials/query/fragment')
    return b


def load_input(path,metadata=None):
    if path.suffix.lower()=='.json':
        if metadata: raise ValueError('JSON batch already contains metadata')
        return json.loads(path.read_text(encoding='utf-8-sig'))
    if path.suffix.lower()!='.csv' or metadata is None: raise ValueError('CSV requires --metadata JSON batch header')
    b=json.loads(metadata.read_text(encoding='utf-8-sig'))
    if 'records' in b: raise ValueError('CSV metadata must not contain records')
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if (not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames)
                or set(reader.fieldnames)-ROW_FIELDS or not {'listing_id','evidence'}.issubset(reader.fieldnames)):
            raise ValueError('CSV headers invalid; only documented observation fields are accepted')
        rows=[]
        for r in reader:
            if None in r or any(v is None for v in r.values()): raise ValueError('Malformed CSV row')
            r={k:v for k,v in r.items() if v!=''}
            for k in ['price_jpy','area_m2','walk_minutes','built_year','age_at_observation']:
                if k in r: r[k]=float(r[k])
            rows.append(r)
    b['records']=rows
    return b


def replay(batches):
    listings={}; snapshots=[]; events=[]; scopes={}; property_states={}; property_first={}; source_last_confirmed={}
    def event(kind,pid,at,**values): events.append(dict(kind=kind,property_id=pid,observed_at=at,**values))
    def aggregate(pid):
        by_source={}
        for l in listings.values():
            if l['property_id']==pid: by_source.setdefault(l['source'],[]).append(l)
        source_states={}
        for source,ls in by_source.items():
            if any(l['state']=='present' and l['health']=='confirmed' and l['identity_status']!='review_required' for l in ls): state='present'
            elif all(l['state'] in ABSENT and l['health']=='confirmed' and l['identity_status']!='review_required' for l in ls): state='absent'
            else: state='unknown'
            source_states[source]=state
        vals=list(source_states.values())
        state=('full_disappearance' if vals and all(v=='absent' for v in vals) else
               'partial_disappearance' if 'absent' in vals and 'present' in vals else
               'presence_observed' if vals and all(v=='present' for v in vals) else 'unknown_coverage')
        return state,source_states
    for b in batches:
        at=b['observed_at'];src=b['source'];scopekey=canonical([src,b['scope_id']])
        if scopekey in scopes and scopes[scopekey]!=b['scope']: raise ValueError('Scope definition changed under same scope_id')
        scopes[scopekey]=b['scope']
        seen=set()
        for r in b['records']:
            key=canonical([src,r['listing_id']]);seen.add(key);old=listings.get(key)
            pid=r.get('property_id') or (old['property_id'] if old else str(uuid5(NAMESPACE_URL,key)))
            if old and pid!=old['property_id']: raise ValueError('Cannot silently remap an existing listing to another home')
            linked=any(l['property_id']==pid for l in listings.values())
            if not old and linked and not r.get('match_evidence'): raise ValueError('Verified cross-listing match evidence required; otherwise keep separate properties')
            if not old and linked:
                for other in listings.values():
                    if other['property_id']==pid:
                        if other['identity_status']=='review_required': raise ValueError('Existing dwelling identity requires review before linking')
                        for f in ['municipality','area_m2','built_year']:
                            if r.get(f) is not None and f in other['attributes'] and r[f]!=other['attributes'][f]:
                                raise ValueError('Conflicting dwelling attributes; cross-platform matching requires review')
            if old is None:
                old=dict(property_id=pid,source=src,listing_id=r['listing_id'],first_seen_at=None,last_seen_at=None,
                         first_listed_at=None,first_disappeared_at=None,last_successful_check_at=None,
                         state='unknown',health='unknown',scopes=[],attributes={},price_jpy=None,
                         identity_status='explicit_verified_match' if linked else 'source_isolated',match_evidence=r.get('match_evidence'))
                listings[key]=old
                if linked: event('new_listing_linked',pid,at,source=src,listing_id=r['listing_id'],match_evidence=r['match_evidence'])
            if b['scope_id'] not in old['scopes']: old['scopes'].append(b['scope_id'])
            previous=old['state'];old['state']=r['status'];old['health']='confirmed';old['last_successful_check_at']=at
            old['last_evidence']=r['evidence'];old['rights']=b['rights']
            for field in ['url','source_record_id']:
                if r.get(field) is not None: old[field]=r[field]
            if r['status']=='present':
                if old['first_seen_at'] is None: old['first_seen_at']=at
                old['last_seen_at']=at
                if previous in ABSENT: event('reappeared',pid,at,source=src,listing_id=r['listing_id'])
                price=r.get('price_jpy')
                if price is not None:
                    prev=old['price_jpy']
                    if prev is not None:
                        event('price_down' if price<prev else 'price_up' if price>prev else 'price_unchanged',pid,at,
                              source=src,listing_id=r['listing_id'],before=prev,after=price)
                    old['price_jpy']=price
                    old['price_observed_at']=at
                attrs={k:r[k] for k in ATTRS if r.get(k) is not None}
                changed={k:dict(before=old['attributes'][k],after=v) for k,v in attrs.items() if k in old['attributes'] and old['attributes'][k]!=v}
                if changed: event('attributes_changed',pid,at,source=src,listing_id=r['listing_id'],changes=changed)
                if set(changed)&{'municipality','area_m2','built_year'}:
                    old['identity_status']='review_required'
                    event('identity_review_required',pid,at,source=src,listing_id=r['listing_id'])
                old['attributes'].update(attrs)
            if r.get('first_listed_at'):
                if old['first_listed_at'] and old['first_listed_at']!=r['first_listed_at']:
                    event('listing_start_conflict',pid,at,source=src,listing_id=r['listing_id'])
                else: old['first_listed_at']=r['first_listed_at']
            if r['status'] in ABSENT and previous not in ABSENT:
                old['first_disappeared_at']=old['first_disappeared_at'] or at
                event('listing_disappeared',pid,at,source=src,listing_id=r['listing_id'],evidence=r['evidence'],
                      reason=r['status'],last_seen_at=old['last_seen_at'],exact_end_at=None)
            snapshots.append(dict(property_id=pid,source=src,listing_id=r['listing_id'],batch_id=b['batch_id'],observed_at=at,
                                  record=r,evidence=r['evidence'],rights=b['rights'],missing_fields=sorted(ROW_FIELDS-set(r)),
                                  unit_price_jpy_m2=r['price_jpy']/r['area_m2'] if r.get('price_jpy') and r.get('area_m2') else None))
        for key,l in listings.items():
            if l['source']!=src or key in seen or b['scope_id'] not in l['scopes']: continue
            eligible=b['scope']['coverage_type']=='entire_source_feed' or (b['scope']['coverage_type']=='tracked_listing_ids' and l['listing_id'] in b['scope']['listing_ids'])
            if b['completeness']=='complete' and eligible:
                previous=l['state']
                if previous not in ABSENT: l['state']='not_observed_complete'
                l['health']='confirmed';l['last_successful_check_at']=at
                if previous not in ABSENT:
                    l['first_disappeared_at']=l['first_disappeared_at'] or at
                    event('listing_disappeared',l['property_id'],at,source=src,listing_id=l['listing_id'],
                          reason='not_observed_complete',evidence=b['check_evidence'],last_seen_at=l['last_seen_at'],exact_end_at=None)
                snapshots.append(dict(property_id=l['property_id'],source=src,listing_id=l['listing_id'],batch_id=b['batch_id'],
                                      observed_at=at,record=None,evidence=b['check_evidence'],rights=b['rights'],state=l['state']))
            else:
                l['health']='unknown_coverage'
                event('observation_incomplete',l['property_id'],at,source=src,listing_id=l['listing_id'],reason=b['completeness'] if eligible else 'filtered_search_not_listing_check')
        for pid in sorted({l['property_id'] for l in listings.values()}):
            state,source_states=aggregate(pid)
            for source,state_s in source_states.items():
                source_key=(pid,source)
                if state_s=='absent' and source_last_confirmed.get(source_key)!='absent':
                    event('source_disappearance',pid,at,source=source,exact_end_at=None)
                    if pid not in property_first:
                        property_first[pid]=at;event('first_source_disappearance',pid,at,source=source,exact_end_at=None)
                if state_s!='unknown': source_last_confirmed[source_key]=state_s
            if property_states.get(pid)!=state:
                event('property_state_changed',pid,at,state=state,source_states=source_states)
            property_states[pid]=state
    properties=[]
    for pid in property_states:
        state,source_states=aggregate(pid)
        disappear=[e for e in events if e['property_id']==pid and e['kind']=='source_disappearance']
        firsts={s:min(e['observed_at'] for e in disappear if e['source']==s) for s in sorted({e['source'] for e in disappear})}
        tracking={}
        for source in source_states:
            ls=[l for l in listings.values() if l['property_id']==pid and l['source']==source]
            times=lambda field:[l[field] for l in ls if l.get(field)]
            tracking[source]=dict(first_seen_at=min(times('first_seen_at'),default=None),last_seen_at=max(times('last_seen_at'),default=None),
                                  first_disappeared_at=firsts.get(source),last_successful_check_at=max(times('last_successful_check_at'),default=None))
        full=[e['observed_at'] for e in events if e['property_id']==pid and e['kind']=='property_state_changed' and e['state']=='full_disappearance']
        lag=(datetime.fromisoformat(max(firsts.values()))-datetime.fromisoformat(min(firsts.values()))).total_seconds() if len(firsts)>1 else None
        properties.append(dict(property_id=pid,state=state,source_states=source_states,first_source_disappeared_at=property_first.get(pid),
                               source_tracking=tracking,first_full_disappeared_at=min(full,default=None),
                               first_disappearance_by_source=firsts,first_source_check_lag_seconds=lag,
                               lag_is_sale_timing=False,monitored_sources_only=True))
    for l in listings.values():
        area=l['attributes'].get('area_m2');l['unit_price_jpy_m2']=l['price_jpy']/area if l['price_jpy'] and area else None
    return dict(version=VERSION,properties=properties,listings=list(listings.values()),snapshots=snapshots,events=events,batches=batches,
                data_summary=dict(real_observation_rows=sum(len(b['records']) for b in batches if b['data_kind']=='real'),
                                  synthetic_observation_rows=sum(len(b['records']) for b in batches if b['data_kind']=='synthetic')),
                limitations=['first_seen is our observation, not listing start','Disappearance is source/scope evidence, never a proven sale date',
                             'Latest evidence across asynchronous checks, not simultaneous market census','Stable source IDs can be recycled; user must review identity conflicts',
                             'Cross-platform links are explicit user-verified assertions, not automatic matching',
                             'Manual entry does not grant reuse rights; permission evidence is an importer assertion',
                             'Free-text evidence is not automatically screened for personal information; keep stores/exports in ignored data/reports directories'])


def ingest(path,batch):
    b=validate(batch);path.parent.mkdir(parents=True,exist_ok=True)
    lock=Path(str(path)+'.lock')
    try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError: raise ValueError('Store is locked; concurrent writer or interrupted import; inspect before recovery') from None
    temp=Path(str(path)+'.tmp')
    try:
        os.close(fd)
        journal=json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(version=VERSION,batches=[])
        if journal['version']!=VERSION: raise ValueError('Store version mismatch')
        batches=journal['batches']
        same=[x for x in batches if x['source']==b['source'] and x['batch_id']==b['batch_id']]
        if same:
            if canonical(same[0])!=canonical(b): raise ValueError('Existing batch ID has different content')
            return dict(imported=False,batches=len(batches))
        if any({k:v for k,v in x.items() if k!='batch_id'}=={k:v for k,v in b.items() if k!='batch_id'} for x in batches):
            return dict(imported=False,batches=len(batches))
        if batches and (b['observed_at']<batches[-1]['observed_at'] or b['data_kind']!=batches[0]['data_kind']):
            raise ValueError('Import in observation order; real and synthetic journals must be separate')
        updated=batches+[b];replay(updated)  # Validate all transitions before atomic replacement.
        temp.write_text(canonical(dict(version=VERSION,batches=updated)),encoding='utf-8')
        os.replace(temp,path)
        return dict(imported=True,batches=len(updated))
    finally:
        if temp.exists(): temp.unlink()
        lock.unlink()


def report(path,property_id=None):
    journal=json.loads(path.read_text(encoding='utf-8'))
    result=replay(journal['batches'])
    if property_id:
        for key in ['properties','listings','snapshots','events']: result[key]=[r for r in result[key] if r['property_id']==property_id]
        keys={(r['source'],r['listing_id']) for r in result['listings']}
        sources={k[0] for k in keys}
        result['batches']=[dict(b,records=[r for r in b['records'] if (b['source'],r['listing_id']) in keys]) for b in result['batches'] if b['source'] in sources]
        result['data_summary']={kind+'_observation_rows':sum(len(b['records']) for b in result['batches'] if b['data_kind']==kind)
                                for kind in ['real','synthetic']}
    return result


def export(result,output):
    output.mkdir(parents=True,exist_ok=False)
    (output/'history.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    for key in ['properties','listings','snapshots','events']:
        rows=result[key];fields=sorted({k for r in rows for k in r}) or ['property_id']
        with (output/(key+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for r in rows: w.writerow({k:canonical(v) if isinstance(v,(dict,list)) else v for k,v in r.items()})


def main():
    p=argparse.ArgumentParser(description='許可された掲載観測。消失は成約日ではない。 / Authorized listing snapshots; absence never implies sale',
        epilog='手入力も利用許諾が必要。権利根拠は申告であり自動検証しない。Task 010取得実データ0件、同梱例は合成のみ。保存先はGit無視のdata/reports内。 / '
               'Manual input does not grant reuse rights; rights evidence is an importer assertion. Task 010 acquired 0 real listings; bundled examples are synthetic. Keep stores/exports in Git-ignored data/reports.')
    p.add_argument('--store',type=Path,default=Path('data/listings/journal.json'))
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('import');a.add_argument('input',type=Path);a.add_argument('--metadata',type=Path)
    a=sub.add_parser('history');a.add_argument('--property-id');a.add_argument('--output',type=Path)
    a=sub.add_parser('validate');a.add_argument('input',type=Path);a.add_argument('--metadata',type=Path)
    args=p.parse_args()
    try:
        if args.command in {'import','validate'}:
            b=load_input(args.input,args.metadata)
            value=ingest(args.store,b) if args.command=='import' else dict(valid=bool(validate(b)))
            value.update(data_kind=b['data_kind'],real_observation_rows_in_batch=len(b['records']) if b['data_kind']=='real' else 0,
                         rights_notice='手入力も利用許諾が必要。 / Manual input does not grant reuse rights; permission evidence is an importer assertion.')
        else:
            value=report(args.store,args.property_id)
            if args.output: export(value,args.output)
        print(json.dumps(value,ensure_ascii=True,allow_nan=False))
    except (ValueError,OSError,KeyError,TypeError,csv.Error) as e: p.exit(2,str(e)+'\n')


if __name__=='__main__': main()
