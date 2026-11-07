"""Retrospective transaction descriptions. No training or future probability."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .benchmark import Features,norm
from .competitiveness import assess,make_pool
from .transactions import describe

def quarter_index(q):
    if not re.fullmatch(r'\d{4}Q[1-4]',q): raise ValueError('Quarter must be YYYYQ1..4')
    return (int(q[:4])-2023)*4+int(q[-1])-1

def strict_mask(pool,query,start,end):
    f=Features().transform(pd.DataFrame([query])).iloc[0]
    if not np.isfinite(f.age) or not np.isfinite(f.area) or not norm(query.get('最寄駅：名称','')):
        return pd.Series(False,index=pool.index)
    mask=(pool.municipality==f.municipality)&(pool.station==f.station)&pool.area.between(.8*f.area,1.2*f.area)&((pool.age-f.age).abs()<=10)&pool.quarter_index.between(quarter_index(start),quarter_index(end))
    if norm(query.get('地区名','')): mask &= pool.town==norm(query['地区名'])
    # Supplied layout/structure are exact constraints, never silently relaxed.
    for field,raw in [('layout','間取り'),('structure','建物の構造')]:
        if norm(query.get(raw,'')): mask &= pool[field]==norm(query[raw])
    return mask

def adjusted_price(actual,query_log,row_log):
    values=np.asarray(actual)*np.exp(np.asarray(query_log)-np.asarray(row_log))
    if not np.isfinite(values).all() or (values<=0).any(): raise ValueError('Invalid adjustment')
    return values

def stats(values,asking,min_n=10):
    values=np.asarray(values,dtype=float)
    n=len(values); below=int((values<asking).sum())
    return dict(distribution_jpy_m2=describe(values.tolist()),lower_price_record_count=below,
        lower_price_record_fraction=below/n if n>=min_n else None,
        status='descriptive_only' if n>=min_n else '无法判断',
        denominator='observed comparable transaction records, not unique homes or all market sales')

def analyze(bundle,df,query):
    # Reuse Task005 validation and conservative vintage availability gate.
    validation=assess(bundle,query)
    q=dict(query); q['quarter']=bundle['latest_quarter']
    if not q.get('建築年') and 'age' in q:
        q['建築年']=str(date.fromisoformat(q['reference_date']).year-int(q['age']))+'年'
    start=q.get('history_start','2023Q1'); end=q.get('history_end',bundle['latest_quarter'])
    if not 0<=quarter_index(start)<=quarter_index(end)<=quarter_index(bundle['latest_quarter']):
        raise ValueError('Historical window must fall within acquired 2023Q1–2026Q2 scope')
    y=pd.to_numeric(df.unit_price_jpy_m2,errors='coerce').to_numpy()
    if not (np.isfinite(y)&(y>0)).all(): raise ValueError('Invalid targets require explicit review')
    pool=make_pool(df,y)
    mask=strict_mask(pool,q,start,end)
    selected=df.loc[mask].copy(); actual=y[mask]; n=len(selected)
    asking=float(q['asking_price_jpy'])/float(q['面積（㎡）'])
    columns={'raw_unit_price':actual}
    if n:
        with threadpool_limits(limits=4):
            for label,name in [('quality_all_history','all_history_no_time'),('quality_recent_sensitivity','recent_no_time'),('quality_and_time','history_with_time')]:
                m=bundle['models'][name]
                columns[label]=adjusted_price(actual,m.predict(pd.DataFrame([q]))[0],m.predict(selected))
            # Isolate the model's time term: hold each trade's age and attributes fixed.
            counterfactual=selected.copy()
            shift=int(q['quarter'][:4])-selected.quarter.str[:4].astype(int)
            counterfactual['建築年']=[str(int(norm(v).removesuffix('年'))+int(s))+'年' for v,s in zip(selected['建築年'],shift)]
            counterfactual['quarter']=q['quarter']
            m=bundle['models']['history_with_time']
            columns['time_only']=adjusted_price(actual,m.predict(counterfactual),m.predict(selected))
    else:
        for key in ['quality_all_history','quality_recent_sensitivity','quality_and_time','time_only']: columns[key]=np.array([])
    table=selected[['source_file','source_row','quarter','市区町村名','地区名','最寄駅：名称','面積（㎡）','建築年','間取り','建物の構造']].reset_index(drop=True)
    for label,values in columns.items(): table[label]=values
    summaries={label:stats(v,asking) for label,v in columns.items()}
    periods=[]
    for index in range(quarter_index(start),quarter_index(end)+1):
        period=f'{2023+index//4}Q{index%4+1}'
        acquired=bool((df.quarter==period).any())
        subset=table[table.quarter==period]
        periods.append(dict(quarter=period,acquired=acquired,comparable_n=len(subset) if acquired else None,
            methods={label:stats(subset[label],asking) for label in columns} if acquired else None,
            revision_warning=period=='2026Q2'))
    recent=table.quarter>='2025Q3'
    contrasts={name:{label:stats(table.loc[flag,label],asking) for label in columns}
               for name,flag in [('recent_2025Q3_2026Q2',recent),('earlier_through_2025Q2',~recent)]}
    if n:
        ratios=columns['quality_and_time']/actual
        flags=dict(adjustment_below_half=int((ratios<.5).sum()),adjustment_above_double=int((ratios>2).sum()))
    else: flags={}
    sensitivity=[r['lower_price_record_fraction'] for r in summaries.values() if r['lower_price_record_fraction'] is not None]
    result=dict(version='task006-v1',reference_date=q['reference_date'],input=q,historical_window=[start,end],
        comparable_n=n,minimum_for_fraction=10,methods=summaries,quarterly=periods,period_comparison=contrasts,
        method_fraction_spread=max(sensitivity)-min(sensitivity) if sensitivity else None,adjustment_flags=flags,
        conclusion='无法判断',conclusion_scope='Current value-for-money and future opportunities cannot be established',
        rules='Same city/station, optional exact town; area ±20%, age at trade ±10 years; exact supplied layout/structure; no relaxation',
        uncertainty=dict(development_error_log_radii=bundle['radii'],calibrated=False,
            note='Task005 development errors are context only; adjustment ratios have no calibrated uncertainty or independent validation.'),
        limitations=['Historical sales differ from current asking prices; lower adjusted price is not better overall value.',
            'Record counts are not unique homes, listing supply, complete market sales or future probability.',
            'Current-vintage retrospective adjustment may include model training rows: no prediction-performance claim.',
            'Unknown floors, renovation, orientation and management; anonymous repeats retained.',
            'Anchor is 2026Q2, not November; 2026Q2 may be incomplete/revised.',
            'No historical as-of use before conservative acquisition availability date.'],
        data_lag_days=validation['data_lag_days'])
    return result,table

def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,required=True)
    p.add_argument('--artifact',type=Path,default=Path('reports/competitiveness-005-v2/reference.joblib'))
    p.add_argument('--data',type=Path,default=Path('reports/history-003-verified/merged_retained.csv'))
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists(): raise FileExistsError('Use a new output directory')
    bundle=joblib.load(a.artifact)
    if hashlib.sha256(a.data.read_bytes()).hexdigest()!=bundle['protocol']['data_sha256']: raise ValueError('Data hash differs from fitted artifact')
    df=pd.read_csv(a.data,encoding='utf-8-sig',dtype=str,keep_default_na=False)
    result,rows=analyze(bundle,df,json.loads(a.input.read_text(encoding='utf-8')))
    a.output.mkdir(parents=True)
    result['provenance']={'data_sha256':bundle['protocol']['data_sha256'],'artifact_sha256':hashlib.sha256(a.artifact.read_bytes()).hexdigest(),'available_on':bundle['protocol']['available_on']}
    (a.output/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    rows.to_csv(a.output/'comparable_records.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame([dict(quarter=r['quarter'],acquired=r['acquired'],comparable_n=r['comparable_n'],revision_warning=r['revision_warning']) for r in result['quarterly']]).to_csv(a.output/'quarter_counts.csv',index=False)
    # Reuse exposed Task005 regional coverage, explicitly labeled instead of inventing current coverage.
    previous=a.artifact.parent/'development_subgroups.csv'
    if previous.exists():
        regional=pd.read_csv(previous)
        regional=regional[(regional.dimension=='municipality')&(regional.method=='comparable')].copy()
        regional['scope']='Task005 fixed-2024-pool / 2025 development; looser layout/structure rule; NOT Task006 current coverage'
        regional.to_csv(a.output/'prior_regional_coverage_context.csv',index=False,encoding='utf-8-sig')
    print(json.dumps({'comparable_n':result['comparable_n'],'methods':result['methods'],'conclusion':result['conclusion']},ensure_ascii=True))

if __name__=='__main__': main()
