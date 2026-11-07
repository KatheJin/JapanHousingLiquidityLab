"""Frozen temporal benchmark. No network, raw mutation, or test-driven tuning."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import platform
import re
import unicodedata
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, TransformerMixin, RegressorMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

NUM=['area','age','minutes','distance_width','quarter_index']
CAT=['municipality','station','distance_kind','layout','structure']

def norm(v):
    return unicodedata.normalize('NFKC',str(v or '')).strip()

def distance(v):
    v=norm(v)
    if re.fullmatch(r'\d+(\.\d+)?',v): return float(v),0.,'exact'
    ranges={'30分~60分':(45.,30.,'interval'),'1H~1H30':(75.,30.,'interval'),
            '1H30~2H':(105.,30.,'interval'),'2H~':(120.,np.nan,'lower_bound')}
    return ranges.get(v,(np.nan,np.nan,'unknown'))

class Features(TransformerMixin,BaseEstimator):
    def fit(self,X,y=None): return self
    def transform(self,X):
        records=[]
        for r in X.to_dict('records'):
            q=norm(r['quarter'])
            if not re.fullmatch(r'\d{4}Q[1-4]',q): raise ValueError('quarter must be YYYYQn')
            year=int(q[:4]); quarter=int(q[-1])
            by=norm(r.get('建築年','')); match=re.fullmatch(r'(\d{4})年?',by)
            age=year-int(match[1]) if match else np.nan
            if not np.isnan(age) and not 0<=age<=150: age=np.nan
            try: area=float(norm(r['面積（㎡）']).replace(',',''))
            except ValueError: area=np.nan
            if not np.isfinite(area) or area<=0: area=np.nan
            minutes,width,kind=distance(r.get('最寄駅：距離（分）',''))
            records.append(dict(area=area,age=age,minutes=minutes,distance_width=width,
                quarter_index=(year-2023)*4+quarter-1,
                municipality=norm(r.get('市区町村名','')) or np.nan,
                station=norm(r.get('最寄駅：名称','')) or np.nan,
                distance_kind=kind,layout=norm(r.get('間取り','')) or np.nan,
                structure=norm(r.get('建物の構造','')) or np.nan))
        return pd.DataFrame(records,columns=NUM+CAT)

class GroupMedian(RegressorMixin,BaseEstimator):
    def fit(self,X,y):
        groups=defaultdict(list)
        self.global_=float(np.median(y))
        for row,target in zip(X,y): groups[tuple(row)].append(target)
        self.groups_={k:float(np.median(v)) for k,v in groups.items()}
        return self
    def predict(self,X): return np.array([self.groups_.get(tuple(r),self.global_) for r in X])

def model(name):
    numeric=Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler())])
    if name=='median':
        prep=ColumnTransformer([('group',SimpleImputer(strategy='most_frequent'),['municipality'])])
        reg=GroupMedian()
    elif name=='ridge':
        cat=Pipeline([('impute',SimpleImputer(strategy='constant',fill_value='UNKNOWN')),
            ('encode',OneHotEncoder(handle_unknown='ignore',min_frequency=10))])
        prep=ColumnTransformer([('num',numeric,NUM),('cat',cat,CAT)])
        reg=Ridge(alpha=10.,solver='lsqr')
    else:
        cat=Pipeline([('impute',SimpleImputer(strategy='constant',fill_value='UNKNOWN')),
            ('encode',OrdinalEncoder(handle_unknown='use_encoded_value',unknown_value=-1,max_categories=200,min_frequency=10))])
        # Categoricals first: no arbitrary numeric ordering is imposed on station IDs.
        prep=ColumnTransformer([('cat',cat,CAT),('num',numeric,NUM)])
        reg=HistGradientBoostingRegressor(max_iter=200,max_leaf_nodes=15,learning_rate=.07,
            l2_regularization=10.,min_samples_leaf=30,early_stopping=False,random_state=42,
            categorical_features=list(range(len(CAT))))
    return Pipeline([('features',Features()),('preprocess',prep),('model',reg)])

def metrics(y,p):
    error=np.abs(y-p)
    return dict(n=len(y),mae=float(error.mean()),median_ae=float(np.median(error)),
        mape_pct=float(np.mean(error/y)*100),median_ape_pct=float(np.median(error/y)*100),
        wape_pct=float(error.sum()/y.sum()*100),rmsle=float(np.sqrt(np.mean((np.log(y)-np.log(p))**2))))

def train(data,out):
    if out.exists(): raise FileExistsError('Use a new experiment directory')
    out.mkdir(parents=True)
    protocol=dict(version='task004-v1',train='2023Q1–2024Q4',validation='2025Q1–2025Q4',test='2026Q1–2026Q2',
        selection='minimum validation MAE among three primary models',target='log(JPY per m2)',
        sensitivity='fixed HGB with training log-target clipped at training 1st/99th percentiles; validation and test untouched',
        interval='validation 90th percentile absolute log residual, descriptive empirical range; no temporal coverage guarantee',
        refit=False,seed=42,test_policy='all predeclared models tested once after selection; no test-based tuning',
        vintage='retrospective temporal holdout, NOT historical as-of backtest; publication dates unknown',
        input_sha256=hashlib.sha256(data.read_bytes()).hexdigest(),python=platform.python_version(),sklearn=sklearn.__version__)
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    df=pd.read_csv(data,encoding='utf-8-sig',dtype=str,keep_default_na=False)
    y=pd.to_numeric(df['unit_price_jpy_m2'],errors='coerce').to_numpy()
    valid=np.isfinite(y)&(y>0)
    excluded=df.loc[~valid,['source_file','source_row','quality_flags']]
    excluded.to_csv(out/'uncomputable_target.csv',index=False)
    df=df.loc[valid].reset_index(drop=True); y=y[valid]
    masks={name:df.quarter.str[:4].isin(years).to_numpy() for name,years in
        [('train',['2023','2024']),('validation',['2025']),('test',['2026'])]}
    if sum(m.sum() for m in masks.values())!=len(df): raise ValueError('Unexpected period')
    transformed=Features().transform(df)
    audit={name:dict(n=int(mask.sum()),missing=transformed.loc[mask].isna().sum().to_dict()) for name,mask in masks.items()}
    audit['duplicates_retained']=int(df.drop(columns=['source_file','source_row','quality_flags'],errors='ignore').duplicated().sum())
    audit['uncomputable_targets']=len(excluded)
    (out/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    tr,va,te=(masks[k] for k in ('train','validation','test'))
    fitted={}; results={}; failures=[]; radii={}
    for name in ['median','ridge','hgb','hgb_winsor']:
        try:
            pipe=model(name); target=np.log(y[tr])
            if name=='hgb_winsor': target=np.clip(target,*np.quantile(target,[.01,.99]))
            with threadpool_limits(limits=4):
                pipe.fit(df.loc[tr],target)
                pred=np.exp(pipe.predict(df.loc[va]))
            results[name]={'validation':metrics(y[va],pred)}
            radii[name]=float(np.quantile(np.abs(np.log(y[va])-np.log(pred)),.90,method='higher'))
            fitted[name]=pipe
            print(name,results[name],flush=True)
        except Exception as exc:
            failures.append(dict(model=name,error=repr(exc)))
    (out/'failures.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
    if not all(k in fitted for k in ['median','ridge','hgb']): raise RuntimeError('Primary experiment failed; see failures.json')
    chosen=min(['median','ridge','hgb'],key=lambda k:results[k]['validation']['mae'])
    (out/'selection.json').write_text(json.dumps(dict(selected=chosen,validation_results=results,interval_radius=radii[chosen]),indent=2),encoding='utf-8')
    # Selection is persisted before any test prediction or metric.
    predictions=df.loc[te,['quarter','市区町村名','source_file','source_row']].copy()
    predictions['actual']=y[te]
    for name,pipe in fitted.items():
        with threadpool_limits(limits=4): pred=np.exp(pipe.predict(df.loc[te]))
        predictions[name]=pred
        results[name]['test']=metrics(y[te],pred)
    predictions.to_csv(out/'test_predictions.csv',index=False,encoding='utf-8-sig')
    (out/'metrics.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    boundaries=np.quantile(y[tr],[.25,.5,.75])
    predictions['price_band']=np.searchsorted(boundaries,y[te])
    for field in ['市区町村名','price_band','quarter']:
        rows=[]
        for label,g in predictions.groupby(field):
            for name in fitted: rows.append(dict(group=str(label),model=name,**metrics(g.actual.to_numpy(),g[name].to_numpy())))
        pd.DataFrame(rows).to_csv(out/f'errors_{field}.csv',index=False,encoding='utf-8-sig')
    p=predictions[chosen].to_numpy(); radius=radii[chosen]
    coverage=float(np.mean((y[te]>=p*np.exp(-radius))&(y[te]<=p*np.exp(radius))))
    artifact=dict(pipeline=fitted[chosen],selected=chosen,version='task004-v1',radius=radius,
        validation_metrics=results[chosen]['validation'],test_coverage=coverage,scope='Tokyo used condos; temporal test 2026Q1–Q2; trained 2023–2024',
        protocol=protocol,train_area_range=[float(transformed.loc[tr,'area'].min()),float(transformed.loc[tr,'area'].max())])
    joblib.dump(artifact,out/'benchmark.joblib')
    (out/'uncertainty.json').write_text(json.dumps(dict(radius=radius,test_coverage=coverage,nominal=.9,price_band_boundaries=boundaries.tolist()),indent=2),encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    axes[0].scatter(y[te],p,s=4,alpha=.25); axes[0].set(xscale='log',yscale='log',xlabel='Actual JPY/m²',ylabel='Predicted JPY/m²')
    limits=[min(y[te].min(),p.min()),max(y[te].max(),p.max())]; axes[0].plot(limits,limits,'k--')
    axes[1].hist(np.log(y[te])-np.log(p),bins=70); axes[1].set(xlabel='Log residual: actual minus predicted',ylabel='Count')
    fig.suptitle(f'2026 temporal holdout — {chosen}; current data vintage, not an as-of backtest')
    fig.tight_layout(); fig.savefig(out/'evaluation.png',dpi=150); plt.close(fig)
    print(json.dumps(dict(selected=chosen,results=results,coverage=coverage)),flush=True)

def predict(artifact,input_path):
    bundle=joblib.load(artifact) # Load only your own trusted local artifact.
    r=json.loads(input_path.read_text(encoding='utf-8'))
    f=Features().transform(pd.DataFrame([r])); area=f.area.iloc[0]
    if not np.isfinite(area) or area<=0: raise ValueError('A positive area is required')
    if not '2023Q1'<=r['quarter']<='2026Q2': raise ValueError('Outside evaluated quarter scope')
    if not norm(r.get('市区町村名','')): raise ValueError('Municipality is required')
    known=bundle['pipeline']['preprocess'].named_transformers_['cat']['encode'].categories_[0] if bundle['selected']!='median' else None
    if known is not None and norm(r['市区町村名']) not in known: raise ValueError('Municipality not represented in training scope')
    with threadpool_limits(limits=4): value=float(np.exp(bundle['pipeline'].predict(pd.DataFrame([r]))[0]))
    radius=bundle['radius']
    result=dict(unit_price_jpy_m2=value,reference_total_jpy=value*area,
        empirical_unit_price_range=[value*np.exp(-radius),value*np.exp(radius)],
        version=bundle['version'],model=bundle['selected'],scope=bundle['scope'],
        warning='Validation residual range, not a guaranteed property-specific interval. Rounded areas, missing attributes, temporal drift and unseen categories can materially change error.')
    print(json.dumps(result,ensure_ascii=True,indent=2))

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
    t=sub.add_parser('train'); t.add_argument('--data',type=Path,default=Path('reports/history-003-verified/merged_retained.csv')); t.add_argument('--output',type=Path,required=True)
    t=sub.add_parser('predict'); t.add_argument('--artifact',type=Path,required=True); t.add_argument('--input',type=Path,required=True)
    a=p.parse_args()
    if a.command=='train': train(a.data,a.output)
    else: predict(a.artifact,a.input)

if __name__=='__main__':
    from japan_housing_liquidity_lab.benchmark import main as run
    run()
