"""Phase 2 fixed exploratory rolling experiments. No production models or DB writes."""
import argparse
import json
import time
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import HuberRegressor
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits
from .benchmark import model,Features
from .temporal import split_masks,score
from .expansion import read,dump,digest
from .hedonic_adjustment import decompose

ORIGINS=('2026Q1','2026Q2')
VARIANTS=('raw','upper99','upper995','robust')

def target_for_training(y,variant):
    if variant not in VARIANTS:raise ValueError('Unknown variant')
    cap=float(np.quantile(y, .99 if variant=='upper99' else .995)) if variant in ('upper99','upper995') else None
    return np.log(np.minimum(y,cap) if cap is not None else y),cap

def estimator(name,variant):
    pipe=model(name)
    if variant=='robust':
        if name=='ridge':pipe.set_params(model=HuberRegressor(epsilon=1.35,alpha=.01,max_iter=500,tol=1e-5))
        else:pipe.set_params(model__loss='absolute_error')
    return pipe

def high_price_metrics(predictions):
    # User threshold is inclusive: exactly JPY1.5m/m2 must be retained here.
    rows=[]
    for labels,g in predictions[predictions.actual>=1500000].groupby(['years','model','variant']):
        rows.append(dict(zip(['years','model','variant'],labels))|score(g.actual.to_numpy(),g.predicted.to_numpy()))
    return pd.DataFrame(rows)

def run(data,output):
    output=Path(output)
    if output.exists():raise FileExistsError('Use a new experiment directory')
    output.mkdir(parents=True)
    raw=read(data);y=pd.to_numeric(raw.unit_price_jpy_m2,errors='coerce').to_numpy()
    valid=np.isfinite(y)&(y>0)
    raw.loc[~valid].to_csv(output/'uncomputable_targets.csv',index=False,encoding='utf-8-sig')
    df=raw.loc[valid].reset_index(drop=True);y=y[valid]
    quality=json.loads(Path(data).with_name('quality.json').read_text(encoding='utf-8'))
    if digest(data)!=quality['combined_sha256'] or len(raw)!=quality['total']:raise ValueError('Verified input hash/count mismatch')
    protocol=dict(version='hedonic-phase2-v1',data_sha256=digest(data),records=len(raw),origins=ORIGINS,windows=[3,5,8],variants=VARIANTS,
        target='log JPY/m2; only TRAIN upper tail is capped, no lower capping or deletion',
        validation='quarterly rolling origin; identical full holdouts for every candidate',
        independent_test=False,publication_asof_backtest=False,selection='exploratory only; do not replace production model',
        uncertainty='Q2 empirical range from prior Q1 out-of-sample residuals only; not calibrated',
        limitations=['2026 already viewed; no independent test claim','2026Q2 may be incomplete/revised','Anonymous duplicates retained',
        'No causal separation of age/period/cohort; no certified time-adjusted prices'],threads=2)
    dump(output/'protocol.json',protocol)
    features=Features().transform(df);predictions=[];folds=[];failures=[];diagnostics=[];prior={}
    for origin in ORIGINS:
      for years in (3,5,8):
        split=split_masks(df,origin,years)
        if split is None:raise ValueError('Full training window unavailable')
        tr,va=split
        for name in ('ridge','hgb'):
          for variant in VARIANTS:
            start=time.monotonic();pipe=estimator(name,variant);target,cap=target_for_training(y[tr],variant)
            try:
              with warnings.catch_warnings(record=True) as ws,threadpool_limits(limits=2):
                warnings.simplefilter('always',ConvergenceWarning)
                pipe.fit(df.loc[tr],target);lp=pipe.predict(df.loc[va]);pred=np.exp(lp)
              if not np.isfinite(pred).all() or (pred<=0).any():raise ValueError('Invalid predictions')
              converged=not any(issubclass(w.category,ConvergenceWarning) for w in ws)
              key=(years,name,variant);radius=prior.get(key)
              rows=pd.DataFrame(dict(record_id=df.loc[va,'record_id'].to_numpy(),quarter=origin,years=years,model=name,variant=variant,
                  actual=y[va],predicted=pred,municipality=df.loc[va,'市区町村名'].to_numpy(),
                  price_band=pd.cut(y[va],[0,500000,1000000,1500000,np.inf],labels=['<=50man','50-100man','100-150man','>150man']).astype(str),
                  age_band=pd.cut(features.loc[va,'age'],[-1,10,20,40,np.inf],labels=['0-10','11-20','21-40','41+']).astype(str).to_numpy(),
                  area_band=pd.cut(features.loc[va,'area'],[0,30,50,80,np.inf],labels=['<=30','30-50','50-80','>80']).astype(str).to_numpy(),
                  layout=features.loc[va,'layout'].fillna('UNKNOWN').to_numpy(),
                  empirical_covered=np.abs(np.log(y[va])-lp)<=radius if radius is not None else np.nan))
              predictions.append(rows)
              folds.append(dict(quarter=origin,years=years,model=name,variant=variant,train_start=df.loc[tr,'quarter'].min(),
                  train_end=df.loc[tr,'quarter'].max(),train_n=int(tr.sum()),holdout_n=int(va.sum()),cap_jpy_m2=cap,
                  capped_train_n=int((y[tr]>cap).sum()) if cap is not None else 0,converged=converged,
                  warnings=[str(w.message) for w in ws],seconds=time.monotonic()-start,**score(y[va],pred)))
              prior[key]=float(np.quantile(abs(np.log(y[va])-lp),.9,method='higher'))
              # Deterministic training midpoint per fold/window, not matched cross-window sensitivity.
              r=df.loc[tr].iloc[len(df.loc[tr])//2].to_dict()
              d=decompose(pipe,r,origin,float(r['unit_price_jpy_m2']),train_period=[df.loc[tr,'quarter'].min(),df.loc[tr,'quarter'].max()])
              diagnostics.append(dict(record_id=r['record_id'],source_quarter=r['quarter'],quarter=origin,years=years,model=name,variant=variant,**d))
              print(origin,years,name,variant,'MAE',round(folds[-1]['mae']),'converged',converged,flush=True)
            except Exception as exc:failures.append(dict(quarter=origin,years=years,model=name,variant=variant,error=repr(exc)))
            dump(output/'folds.json',folds);dump(output/'failures.json',failures)
    p=pd.concat(predictions,ignore_index=True)
    p.to_csv(output/'predictions.csv.gz',index=False,encoding='utf-8',compression='gzip')
    pd.DataFrame(folds).drop(columns='warnings').to_csv(output/'folds.csv',index=False)
    for dimension in [None,'quarter','price_band','municipality','age_band','area_band','layout']:
        keys=['years','model','variant']+([dimension] if dimension else [])
        rows=[]
        for labels,g in p.groupby(keys,dropna=False):
            covered=g.empirical_covered.dropna()
            rows.append(dict(zip(keys,labels))|score(g.actual.to_numpy(),g.predicted.to_numpy())|
                        dict(empirical_coverage=float(covered.mean()) if len(covered) else None,empirical_n=len(covered)))
        pd.DataFrame(rows).to_csv(output/('metrics_'+(dimension or 'overall')+'.csv'),index=False,encoding='utf-8-sig')
    high_price_metrics(p).to_csv(output/'metrics_high_price_inclusive.csv',index=False,encoding='utf-8-sig')
    dump(output/'adjustment_diagnostics.json',diagnostics)
    return folds

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path('reports/task008-data/merged_retained.csv'));p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.data,a.output)
if __name__=='__main__':main()
