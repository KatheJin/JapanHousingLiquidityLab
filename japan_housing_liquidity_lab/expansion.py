"""Task 008 offline import and audit. Existing Task 003/006 outputs are immutable."""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .benchmark import Features, norm
from .competitiveness import make_pool
from .opportunity import strict_mask, adjusted_price
from .history import FEATURES
from .mlit import inspect_csv
from .transactions import number

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def read(path):
    return pd.read_csv(path, encoding='utf-8-sig', dtype=str, keep_default_na=False)


def qi(q):
    if not re.fullmatch(r'\d{4}Q[1-4]', q):
        raise ValueError('Expected YYYYQ1..4')
    return int(q[:4])*4 + int(q[-1])-1


def qs(i):
    return f'{i//4}Q{i%4+1}'


def keep_age_at(df, quarter):
    """Counterfactual year shift preserves age; no raw construction years are mutated."""
    result=df.copy()
    shift=int(quarter[:4])-df.quarter.str[:4].astype(int)
    years=df['建築年'].map(norm).str.extract(r'^(\d{4})年?$', expand=False)
    if years.isna().any():
        raise ValueError('Age-preserving adjustment requires known Gregorian construction years')
    result['建築年']=(years.astype(int)+shift).astype(str)+'年'
    result['quarter']=quarter
    return result


def import_history(downloads, raw, old_data, output):
    if raw.exists() or output.exists():
        raise FileExistsError('Use new raw/output directories')
    archives=[downloads/f'Tokyo_{y}{q}_{y}{q}.zip' for y in range(2018,2023) for q in range(1,5)]
    if any(not p.exists() for p in archives):
        raise ValueError('All 20 explicitly downloaded quarterly archives required')
    raw.mkdir(parents=True); output.mkdir(parents=True)
    original_schema=list(read(old_data).columns[:21])
    manifests=[]; frames=[]
    for archive in archives:
        quarter=f'{archive.stem[6:10]}Q{archive.stem[10]}'
        folder=raw/quarter; folder.mkdir()
        target=folder/archive.name; shutil.copy2(archive,target)
        with zipfile.ZipFile(target) as z:
            members=[n for n in z.namelist() if n.lower().endswith('.csv')]
            if len(members)!=1 or Path(members[0]).name != members[0]:
                raise ValueError('Unexpected archive contents')
            csv_path=folder/members[0]; csv_path.write_bytes(z.read(members[0]))
        info=inspect_csv(csv_path)
        if info['malformed_rows']:
            raise ValueError('Malformed CSV rows')
        frame=pd.read_csv(csv_path,encoding=info['encoding'],dtype=str,keep_default_na=False)
        required={'種類','価格情報区分','都道府県名','取引時期','取引価格（総額）','面積（㎡）'}
        if not required.issubset(frame.columns):
            raise ValueError('Missing scope/target fields; no silent mapping')
        periods=frame['取引時期'].map(norm)
        if not periods.eq(f'{quarter[:4]}年第{quarter[-1]}四半期').all():
            raise ValueError('Downloaded period does not match filename')
        scope=(frame['種類']=='中古マンション等')&(frame['価格情報区分']=='不動産取引価格情報')&(frame['都道府県名']=='東京都')
        if not scope.all():
            raise ValueError('Unexpected property, price category or region; review raw download')
        acquired=datetime.fromtimestamp(target.stat().st_mtime,timezone(timedelta(hours=9))).isoformat()
        manifest=dict(trade_quarter=quarter,source='https://www.reinfolib.mlit.go.jp/realEstatePrices/',
                      acquisition_method='official UI download; one quarter; no crawler/API',acquired_at=acquired,
                      publication_date=None,first_observed_available_at=acquired,csv_sha256=digest(csv_path),
                      zip_sha256=digest(target),records=len(frame),raw_fields=list(frame.columns),encoding=info['encoding'],
                      same_schema_as_task003=list(frame.columns)==original_schema,
                      license_checked_on='2026-11-08',license='MLIT terms / PDL1.0 with attribution and processing credit')
        dump(folder/'manifest.json',manifest); manifests.append(manifest)
        frame['source_file']=csv_path.name; frame['source_row']=np.arange(2,len(frame)+2)
        frame['quarter']=quarter; values=[]; flags=[]
        for p,a in zip(frame['取引価格（総額）'],frame['面積（㎡）']):
            try: values.append(number(p)/number(a)); flags.append('')
            except ValueError: values.append(np.nan); flags.append('uncomputable_price_area')
        frame['unit_price_jpy_m2']=values; frame['quality_flags']=flags
        frames.append(frame)
    new=pd.concat(frames,ignore_index=True)
    combined=pd.concat([new,read(old_data)],ignore_index=True).fillna('')
    # Normalize metadata types only. Original property fields remain untouched.
    combined['source_row']=combined.source_row.astype(int)
    combined['record_id']=combined.source_file+':'+combined.source_row.astype(str)
    if combined.record_id.duplicated().any():
        raise ValueError('Ambiguous source identifiers')
    f=Features().transform(combined)
    combined['age_at_trade']=f.age
    for column,name in [('取引価格（総額）','price'),('面積（㎡）','area'),('unit_price_jpy_m2','unit_price')]:
        numeric=pd.to_numeric(combined[column],errors='coerce')
        for quarter,index in combined.groupby('quarter').groups.items():
            vals=numeric.loc[index]; p25,p75=vals.quantile([.25,.75]); width=p75-p25
            flag=vals.lt(p25-1.5*width)|vals.gt(p75+1.5*width)
            ids=flag.index[flag]
            combined.loc[ids,'quality_flags']=combined.loc[ids,'quality_flags']+';task008_'+name+'_iqr'
    original_columns=[c for c in original_schema if c in combined]
    exact=combined.duplicated(original_columns,keep=False)
    possible=combined.duplicated([c for c in original_columns if c!='取引時期'],keep=False)
    combined['exact_duplicate_flag']=exact; combined['same_attributes_other_period_flag']=possible&~exact
    combined.to_csv(output/'merged_retained.csv',index=False,encoding='utf-8-sig')
    quality=[]
    for quarter,g in combined.groupby('quarter'):
        for field in FEATURES:
            values=g[field].map(norm) if field in g else pd.Series('',index=g.index)
            quality.append(dict(quarter=quarter,field=field,column_present=field in g,n=len(g),
                                missing=int(values.eq('').sum()),missing_rate=float(values.eq('').mean())))
        index=g.index
        quality.append(dict(quarter=quarter,field='age_at_trade_parsed',column_present=True,n=len(g),
                            missing=int(f.loc[index,'age'].isna().sum()),missing_rate=float(f.loc[index,'age'].isna().mean())))
    pd.DataFrame(quality).to_csv(output/'field_quality.csv',index=False,encoding='utf-8-sig')
    quarterly=combined.groupby('quarter').agg(n=('record_id','size'),age_unknown=('age_at_trade',lambda x:x.isna().sum()))
    quarterly.to_csv(output/'quarterly.csv',encoding='utf-8-sig')
    positive=pd.to_numeric(combined.unit_price_jpy_m2,errors='coerce')
    report=dict(new_records=len(new),old_records=len(combined)-len(new),total=len(combined),quarters=list(quarterly.index),
                sources=manifests,exact_duplicate_rows_retained=int(exact.sum()),possible_same_attributes_rows_retained=int((possible&~exact).sum()),
                uncomputable_targets=int((~np.isfinite(positive)|(positive<=0)).sum()),
                all_new_schemas_equal=all(m['same_schema_as_task003'] for m in manifests),
                old_data_sha256=digest(old_data),combined_sha256=digest(output/'merged_retained.csv'),
                limitations=['Current downloaded vintage, NOT historical publication vintage.',
                             'Anonymous rounded records do not identify buildings; same-building repeated trades cannot be reliably linked.',
                             'Age equals trade year minus construction year and increases across years for fixed construction year.',
                             'No outlier or duplicate row automatically deleted; invalid targets cannot enter log-price fitting.'])
    dump(output/'quality.json',report)
    return report


def decompose(data, artifact, query, old_records, output):
    if output.exists(): raise FileExistsError('Use new audit directory')
    df=read(data); bundle=joblib.load(artifact); q=json.loads(query.read_text(encoding='utf-8'))
    q['quarter']=bundle['latest_quarter']; ask=float(q['asking_price_jpy'])/float(q['面積（㎡）'])
    y=pd.to_numeric(df.unit_price_jpy_m2).to_numpy()
    mask=strict_mask(make_pool(df,y),q,'2023Q1',q['quarter']); rows=df.loc[mask].copy()
    actual=y[mask]; query_frame=pd.DataFrame([q]); cf=keep_age_at(rows,q['quarter'])
    m0=bundle['models']['all_history_no_time']; mt=bundle['models']['history_with_time']
    with threadpool_limits(limits=4):
        q0=m0.predict(query_frame)[0]; qt=mt.predict(query_frame)[0]
        r0=m0.predict(rows); rt=mt.predict(rows); ct=mt.predict(cf)
        xq=mt['preprocess'].transform(mt['features'].transform(query_frame))
        xc=mt['preprocess'].transform(mt['features'].transform(cf))
    result=rows[['source_file','source_row','quarter','市区町村名','地区名','最寄駅：名称','面積（㎡）','建築年','最寄駅：距離（分）']].reset_index(drop=True)
    result['actual_unit']=actual
    result['historical_reference_no_time']=np.exp(r0); result['historical_reference_with_time']=np.exp(rt)
    result['quality_no_time_log_factor']=q0-r0
    result['refitted_attribute_log_factor']=qt-ct
    result['time_log_factor']=ct-rt
    result['raw']=actual
    result['quality_no_time']=adjusted_price(actual,q0,r0)
    result['timed_model_attributes_only']=adjusted_price(actual,qt,ct)
    result['quality_plus_time']=adjusted_price(actual,qt,rt)
    result['time_only']=adjusted_price(actual,ct,rt)
    names=mt['preprocess'].get_feature_names_out()
    xq=xq.toarray() if hasattr(xq,'toarray') else xq
    xc=xc.toarray() if hasattr(xc,'toarray') else xc
    effects=(xq-xc)*mt['model'].coef_
    for col in ['area','age','minutes','distance_width']:
        loc=list(names).index('num__'+col)
        result[col+'_attribute_log_contribution']=effects[:,loc]
    result['other_attribute_log_contribution']=(qt-ct)-result[[c+'_attribute_log_contribution' for c in ['area','age','minutes','distance_width']]].sum(axis=1)
    methods=['raw','quality_no_time','timed_model_attributes_only','quality_plus_time','time_only']
    for method in methods: result[method+'_below_asking']=result[method]<ask
    old=read(old_records)
    for a,b in [('raw','raw_unit_price'),('quality_no_time','quality_all_history'),('quality_plus_time','quality_and_time'),('time_only','time_only')]:
        if not np.allclose(result[a],pd.to_numeric(old[b]),rtol=1e-10): raise ValueError('Old result cannot be reproduced')
    report=dict(asking_unit=ask,n=len(rows),query_reference_no_time=float(np.exp(q0)),query_reference_with_time=float(np.exp(qt)),
                fractions={m:float((result[m]<ask).mean()) for m in methods},
                counts={m:int((result[m]<ask).sum()) for m in methods},
                train_overlap_all=len(rows),train_overlap_recent=int((rows.quarter>='2025Q3').sum()),
                row_order=[dict(source_file=r.source_file,source_row=int(r.source_row)) for r in result.itertuples()],
                formula='adjusted_i = actual_i * exp(log_reference_query - log_reference_i)',
                decomposition='log(quality_plus_time/raw) = refitted_attribute_log_factor + time_log_factor',
                interpretation='All-period retrospective fitted residuals, not contemporaneous out-of-sample relative competitiveness.',
                old_data_sha256=digest(data),artifact_sha256=digest(artifact),query_sha256=digest(query))
    output.mkdir(parents=True); result.to_csv(output/'decomposition.csv',index=False,encoding='utf-8-sig'); dump(output/'audit.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description='Task008 offline historical import / existing adjustment audit')
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('import'); a.add_argument('--downloads',type=Path,required=True); a.add_argument('--raw',type=Path,required=True)
    a.add_argument('--old-data',type=Path,default=Path('reports/history-003-verified/merged_retained.csv')); a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('audit'); a.add_argument('--data',type=Path,default=Path('reports/history-003-verified/merged_retained.csv'))
    a.add_argument('--artifact',type=Path,default=Path('reports/competitiveness-005-v2/reference.joblib'))
    a.add_argument('--query',type=Path,default=Path('examples/opportunity-small-unit.json'))
    a.add_argument('--old-records',type=Path,default=Path('reports/opportunity-006-small-unit/comparable_records.csv')); a.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command=='import': r=import_history(a.downloads,a.raw,a.old_data,a.output); print({k:r[k] for k in ['new_records','total','all_new_schemas_equal','uncomputable_targets']})
    else: r=decompose(a.data,a.artifact,a.query,a.old_records,a.output); print({k:r[k] for k in ['n','asking_unit','query_reference_no_time','query_reference_with_time','fractions']})


if __name__=='__main__': main()
