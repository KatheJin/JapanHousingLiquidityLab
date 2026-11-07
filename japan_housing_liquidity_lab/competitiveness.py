"""Lag-aware transaction references, not live listing valuations."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .benchmark import Features, model, metrics, norm

def candidate_model(timed):
    p=model('ridge')
    if not timed:
        name, transform, columns = p['preprocess'].transformers[0]
        p['preprocess'].transformers[0] = (name, transform, [c for c in columns if c != 'quarter_index'])
    return p

def comparable(pool, query, end_quarter, min_count=10):
    """Strict station/city, optional town, ±20% area, ±10 years, last 4 quarters."""
    f=Features().transform(pd.DataFrame([query])).iloc[0]
    if not np.isfinite(f.area) or not np.isfinite(f.age) or not norm(query.get('最寄駅：名称','')):
        return {'n':0,'status':'insufficient_features'}
    end=(int(end_quarter[:4])-2023)*4+int(end_quarter[-1])-1
    mask=((pool.municipality==f.municipality)&(pool.station==f.station)&
          (pool.area.between(f.area*.8,f.area*1.2))&
          ((pool.age-f.age).abs()<=10)&(pool.quarter_index.between(end-3,end)))
    if norm(query.get('地区名','')): mask &= pool.town==norm(query['地区名'])
    rows=pool.loc[mask]
    result={'n':len(rows),'status':'sufficient' if len(rows)>=min_count else 'insufficient_sample',
            'period_min':rows.period.min() if len(rows) else None,'period_max':rows.period.max() if len(rows) else None}
    if len(rows):
        result.update(median=float(rows.target.median()),p25=float(rows.target.quantile(.25)),p75=float(rows.target.quantile(.75)))
    return result

def make_pool(df,y):
    pool=Features().transform(df)
    pool['town']=[norm(v) for v in df['地区名']]
    pool['period']=df.quarter.to_numpy(); pool['target']=y
    return pool

def build(data,raw,out):
    if out.exists(): raise FileExistsError('New output directory required')
    out.mkdir(parents=True)
    manifests=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(raw.glob('*/historical_manifest.json'))]
    if not manifests: raise ValueError('Acquisition manifests required')
    for m in manifests:
        paths=list((raw/m['trade_quarter']).glob('*.csv'))
        if len(paths)!=1 or hashlib.sha256(paths[0].read_bytes()).hexdigest()!=m['csv_sha256']:
            raise ValueError('Source hash mismatch')
    available=max(m['first_observed_available_at'][:10] for m in manifests)
    protocol={'version':'task005-v1','evaluation':'2025 development holdout; NOT independent test or historical as-of backtest',
        'training':'2023–2024; recent model uses 2024 only','current_fit':'all data through 2026Q2; recent uses 2025Q3–2026Q2',
        'methods':['all_history_no_time','recent_no_time','history_with_time'],
        'parameters':'Ridge alpha=10, Task004 pipeline; no tuning or model selection',
        'comparables':'same municipality/station; town exact if supplied; area ±20%; age ±10 years; preceding 4 quarters; minimum 10',
        'uncertainty':'2025 90th percentile absolute log error; transferred to current fit, not coverage guarantee',
        'publication_policy':'acquisition date is conservative first-known availability, not release date; reject earlier reference dates',
        'data_sha256':hashlib.sha256(data.read_bytes()).hexdigest(),'available_on':available,
        'test_2026':'used only for current fitting, no new test claims or 2026 metrics'}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    df=pd.read_csv(data,encoding='utf-8-sig',dtype=str,keep_default_na=False)
    y=pd.to_numeric(df.unit_price_jpy_m2,errors='coerce').to_numpy()
    valid=np.isfinite(y)&(y>0)
    if not valid.all(): raise ValueError('Uncomputable targets: explicit review required')
    tr=(df.quarter<='2024Q4').to_numpy(); va=df.quarter.str.startswith('2025').to_numpy()
    specs={'all_history_no_time':(tr,False),'recent_no_time':((df.quarter.str.startswith('2024')).to_numpy(),False),'history_with_time':(tr,True)}
    predictions=pd.DataFrame({'actual':y[va],'municipality':df.loc[va,'市区町村名'].to_numpy()})
    age=Features().transform(df.loc[va]).age
    predictions['age_band']=pd.cut(age,[-1,10,20,40,150],labels=['0–10','11–20','21–40','41+']).astype(str)
    predictions['price_band']=np.searchsorted(np.quantile(y[tr],[.25,.5,.75]),y[va])
    results={}; radii={}
    for name,(mask,timed) in specs.items():
        p=candidate_model(timed)
        with threadpool_limits(limits=4):
            p.fit(df.loc[mask],np.log(y[mask])); pred=np.exp(p.predict(df.loc[va]))
        predictions[name]=pred; results[name]=metrics(y[va],pred)
        radii[name]=float(np.quantile(abs(np.log(y[va])-np.log(pred)),.9,method='higher'))
        print(name,results[name],flush=True)
    pool=make_pool(df.loc[tr].reset_index(drop=True),y[tr])
    values=[]; counts=[]
    for r in df.loc[va].to_dict('records'):
        r.pop('地区名',None) # Station-level development evaluation; town is optional at runtime.
        c=comparable(pool,r,'2024Q4'); counts.append(c['n'])
        values.append(c.get('median',np.nan) if c['status']=='sufficient' else np.nan)
    predictions['comparable']=values; predictions['comparable_n']=counts
    covered=np.isfinite(values)
    results['comparable']={'coverage':float(covered.mean()),**(metrics(y[va][covered],np.array(values)[covered]) if covered.any() else {})}
    matched={name:metrics(y[va][covered],predictions[name].to_numpy()[covered]) for name in specs} if covered.any() else {}
    subgroup=[]
    for field in ['municipality','price_band','age_band']:
        for label,g in predictions.groupby(field):
            for name in list(specs)+['comparable']:
                ok=g[name].notna(); stats=metrics(g.actual[ok].to_numpy(),g[name][ok].to_numpy()) if ok.any() else {'n':0}
                subgroup.append(dict(dimension=field,group=str(label),method=name,coverage=float(ok.mean()),**stats))
    pd.DataFrame(subgroup).to_csv(out/'development_subgroups.csv',index=False,encoding='utf-8-sig')
    predictions.to_csv(out/'development_predictions.csv',index=False,encoding='utf-8-sig')
    (out/'evaluation.json').write_text(json.dumps({'all':results,'matched_comparable_subset':matched},indent=2),encoding='utf-8')
    fitted={}
    for name in specs:
        mask=(df.quarter>='2025Q3').to_numpy() if name=='recent_no_time' else np.ones(len(df),dtype=bool)
        p=candidate_model(name=='history_with_time')
        with threadpool_limits(limits=4): p.fit(df.loc[mask],np.log(y[mask]))
        fitted[name]=p
    bundle=dict(models=fitted,radii=radii,pool=make_pool(df,y),protocol=protocol,
        known_cities=set(df['市区町村名']),latest_quarter='2026Q2',latest_period_end='2026-06-30',
        ranges={'area':np.quantile(Features().transform(df).area,[.01,.99]).tolist()})
    joblib.dump(bundle,out/'reference.joblib')
    (out/'failures.json').write_text('[]',encoding='utf-8')

def assess(bundle,r):
    reference=date.fromisoformat(r['reference_date'])
    if reference<date.fromisoformat(bundle['protocol']['available_on']):
        raise ValueError('Data vintage not known available by requested date; historical as-of use refused')
    price=float(r['asking_price_jpy']); area=float(r['面積（㎡）'])
    if not np.isfinite(price) or price<=0 or not np.isfinite(area) or area<=0: raise ValueError('Positive finite price and area required')
    if norm(r.get('市区町村名','')) not in bundle['known_cities']: raise ValueError('Unsupported municipality')
    r=dict(r)
    if not r.get('建築年') and 'age' in r:
        age=float(r['age'])
        if not age.is_integer() or not 0<=age<=150: raise ValueError('Age must be integer 0–150')
        r['建築年']=str(reference.year-int(age))+'年'
    # Anchor to latest observed quarter: never extrapolate a current/future market trend.
    r['quarter']=bundle['latest_quarter']
    feature=Features().transform(pd.DataFrame([r])).iloc[0]
    c=comparable(bundle['pool'],r,bundle['latest_quarter'])
    references={}
    with threadpool_limits(limits=4):
        for name,p in bundle['models'].items():
            unit=float(np.exp(p.predict(pd.DataFrame([r]))[0])); radius=bundle['radii'][name]
            references[name]=dict(unit_price=unit,total_price=unit*area,deviation_pct=(price/(unit*area)-1)*100,
                empirical_total_range=[unit*area*np.exp(-radius),unit*area*np.exp(radius)])
    if 'median' in c: c['asking_vs_unadjusted_median_pct']=(price/area/c['median']-1)*100
    reasons=['No live listing or contemporaneous transaction evidence; historical reference only',
             'Transferred development error ranges are not validated current-market intervals']
    if c['n']<10: reasons.append('Too few comparable transactions')
    if not np.isfinite(feature.age): reasons.append('Unknown or invalid construction year')
    if feature.distance_kind=='unknown': reasons.append('Unknown station distance')
    if not bundle['ranges']['area'][0]<=area<=bundle['ranges']['area'][1]: reasons.append('Area outside central 98% training support')
    return dict(version='task005-v1',reference_date=r['reference_date'],asking_price_jpy=price,
        asking_unit_price=price/area,reference_basis_quarter=bundle['latest_quarter'],
        data_lag_days=(reference-date.fromisoformat(bundle['latest_period_end'])).days,
        conclusion='无法可靠判断',reason=reasons,model_references=references,comparables=c,
        interpretation='Deviations compare asking price with lagged transaction references, not a current bargain ranking or forecast.')

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build'); b.add_argument('--data',type=Path,default=Path('reports/history-003-verified/merged_retained.csv')); b.add_argument('--raw',type=Path,default=Path('data/raw')); b.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('assess'); a.add_argument('--artifact',type=Path,required=True); a.add_argument('--input',type=Path,required=True); a.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.command=='build': build(args.data,args.raw,args.output)
    else:
        result=assess(joblib.load(args.artifact),json.loads(args.input.read_text(encoding='utf-8')))
        with args.output.open('x',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
        print(json.dumps(result,ensure_ascii=True,indent=2))

if __name__=='__main__':
    from japan_housing_liquidity_lab.competitiveness import main as run
    run()
