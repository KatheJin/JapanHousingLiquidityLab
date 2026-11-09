"""Real historical records; configurable comparison scope, no model fitting or diagnostics as prices."""
from datetime import date,datetime,timezone,timedelta
from pathlib import Path
from .hedonic_adjustment import formal_adjustment_status
from .expansion import qi,qs
import json
import numpy as np
import pandas as pd
from .benchmark import Features,norm
from .competitiveness import make_pool
from .opportunity import strict_mask,quarter_index
from .web_adapter import load_real
from .transactions import describe
from .location import walk_bounds

MODES=('strict_station','municipality','selected_locations')

def load(root):
    root=Path(root)
    _,df,available=load_real(root,'location')
    quality=json.loads((root/'reports/task008-data/quality.json').read_text(encoding='utf-8'))
    return df,dict(available_on=available,data_sha256=quality['combined_sha256'],source='国土交通省 不動産情報ライブラリ 不動産取引価格情報',
                   url='https://www.reinfolib.mlit.go.jp/realEstatePrices/',coverage=sorted(df.quarter.unique()),records=len(df),publication_date=None,published_quarters=sorted(df.quarter.unique()),calendar_end=qs(qi(f'{datetime.now(timezone(timedelta(hours=9))).year}Q{(datetime.now(timezone(timedelta(hours=9))).month-1)//3+1}')+1))

def search(df,query,metadata,*,mode='strict_station',locations=None):
    df=df.reset_index(drop=True)
    if mode not in MODES:raise ValueError('Unknown comparison mode')
    ref=date.fromisoformat(query['reference_date'])
    if ref<date.fromisoformat(metadata['available_on']):raise ValueError('Data was not known available at this reference date')
    start=query.get('history_start','2018Q1');end=query.get('history_end','2026Q2')
    if quarter_index(start)>quarter_index(end) or not metadata['coverage'][0]<=start<=end<=metadata.get('calendar_end',metadata['coverage'][-1]):raise ValueError('Outside acquired historical coverage')
    q=dict(query,quarter=f'{ref.year}Q{(ref.month-1)//3+1}')
    for k in ['asking_price_jpy','面積（㎡）']:
        if not np.isfinite(float(q[k])) or float(q[k])<=0:raise ValueError('Positive finite price and area required')
    if not norm(q.get('市区町村名','')) or (mode=='strict_station' and not norm(q.get('最寄駅：名称',''))):raise ValueError('Location required')
    f=Features().transform(pd.DataFrame([q])).iloc[0]
    if not np.isfinite(f.age):raise ValueError('Known valid construction year required')
    y=pd.to_numeric(df.unit_price_jpy_m2,errors='coerce').to_numpy();pool=make_pool(df,y)
    if mode=='strict_station':mask=strict_mask(pool,q,start,end)
    else:
        mask=pool.area.between(.8*f.area,1.2*f.area)&((pool.age-f.age).abs()<=10)&df.quarter.between(start,end)
        if mode=='municipality':mask &= pool.municipality.eq(f.municipality)
        else:
            if not locations or any(set(x)!={'municipality','station'} or not all(norm(v) for v in x.values()) for x in locations):raise ValueError('Explicit city/station pairs required')
            allowed={(norm(x['municipality']),norm(x['station'])) for x in locations}
            mask &= pd.Series([(c,s) in allowed for c,s in zip(pool.municipality,pool.station)],index=df.index)
        for field,raw in [('town','地区名'),('layout','間取り'),('structure','建物の構造')]:
            if norm(q.get(raw,'')):mask &= pool[field].eq(norm(q[raw]))
    walk_info=dict(enabled=False,base_n=int(mask.sum()),unknown_n=0,interval_overlap_only_n=0)
    unknown_records=[]
    tolerance=q.get('walk_tolerance_minutes')
    if tolerance is not None:
        target=float(q.get('最寄駅：距離（分）',''));tolerance=float(tolerance)
        if not np.isfinite(target) or not np.isfinite(tolerance) or target<0 or tolerance<0:raise ValueError('Known nonnegative walking minutes and tolerance required')
        bounds=pd.DataFrame([walk_bounds(v) for v in df['最寄駅：距離（分）']],columns=['lo','hi'])
        unknown=mask&bounds.lo.isna();lo=max(0,target-tolerance);hi=target+tolerance
        overlap=mask&bounds.lo.le(hi)&bounds.hi.ge(lo)
        contained=bounds.lo.ge(lo)&bounds.hi.le(hi)
        unknown_records=df.loc[unknown,['source_file','source_row','quarter','最寄駅：距離（分）']].astype(str).to_dict('records')
        walk_info=dict(enabled=True,base_n=int(mask.sum()),range_minutes=[lo,hi],unknown_n=int(unknown.sum()),interval_overlap_only_n=int((overlap&~contained).sum()),rule='Entire distance interval must lie inside tolerance; unknown and partial overlaps excluded, reported separately')
        mask &= contained
    selected=df.loc[mask].copy();rows=[]
    for i,r in selected.iterrows():
        unit=float(y[i]);valid=bool(np.isfinite(unit) and unit>0)
        gate=formal_adjustment_status(r.quarter)
        rows.append(dict(record_id=r.get('record_id',str(r.source_file)+':'+str(r.source_row)),source_file=r.source_file,source_row=str(r.source_row),
            quarter=r.quarter,municipality=r['市区町村名'],town=r['地区名'],station=r['最寄駅：名称'],
            walk_raw=r.get('最寄駅：距離（分）',''),walk_status='unknown' if np.isnan(walk_bounds(r.get('最寄駅：距離（分）',''))[0]) else 'known',area_m2=float(pool.loc[i,'area']),construction_year=r['建築年'],
            age_at_trade=float(pool.loc[i,'age']),layout=r['間取り'],structure=r['建物の構造'],total_price_raw=r['取引価格（総額）'],
            raw_unit_price_jpy_m2=unit if valid else None,
            cohort='expanded_2018_2022' if r.quarter<'2023Q1' else 'existing_2023_2026',
            adjustment_status='unavailable',attribute_adjusted_unit_price=None,time_adjusted_unit_price=None,aging_adjusted_unit_price=None,
            adjustment_reason=gate['reason']))
    values=[r['raw_unit_price_jpy_m2'] for r in rows if r['raw_unit_price_jpy_m2'] is not None]
    missing={field:int(selected[field].map(norm).eq('').sum()) for field in ['地区名','最寄駅：名称','最寄駅：距離（分）','建築年','間取り','建物の構造']}
    quarterly=[]
    now=datetime.now(timezone(timedelta(hours=9)));current=f'{now.year}Q{(now.month-1)//3+1}'
    for t in (qs(i) for i in range(qi(start),qi(end)+1)):
        n=sum(r['quarter']==t for r in rows) if t in metadata['coverage'] else None
        state=('acquired_matches' if n else 'acquired_zero') if n is not None else ('not_published' if t in metadata.get('known_unpublished_quarters',[]) or t>current else 'not_acquired' if t in metadata.get('published_quarters',metadata['coverage']) else 'publication_unverified')
        quarterly.append(dict(quarter=t,acquired=n is not None,n=n,state=state))
    result=dict(version='phase3-v1',query=q,mode=mode,locations=locations,comparable_n=len(rows),valid_price_n=len(values),records=rows,
        raw_distribution=describe(values),walk_filter=walk_info,walk_unknown_records=unknown_records,quarterly=quarterly,source=metadata,missing_fields=missing,
        unknown_age_in_requested_period=int(pool.loc[df.quarter.between(start,end),'age'].isna().sum()),
        cohort_counts={c:sum(r['cohort']==c for r in rows) for c in ['expanded_2018_2022','existing_2023_2026']},
        adjustment=dict(status='unavailable',formal_adjustment_enabled=False,diagnostics_used=False),
        rules='Area ±20%; age at trade versus target age at reference date ±10y; exact supplied town/layout/structure; no automatic relaxation. Walking time is displayed, not a matching threshold.',
        warnings=['駅は市区町村と正規化した名称で比較し、駅ID・座標による同一性は未検証です。',
                  '観測した匿名取引記録の件数で、住宅の実数や市場全件数ではありません。重複候補は保持します。',
                  '過去の低価格記録は将来の購入確率ではありません。価格の低さだけで品質優位とは判断できません。',
                  '2026Q2は不完全・改訂の可能性があり、公表当時の版ではありません。',
                  '属性・時間・老化の独立検証が不足し、正式な調整価格は利用不可です。'])
    return result
