"""Exploratory current-vintage forward validation; never replaces Task004--006 artifacts."""
import argparse
from datetime import date
import json
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .benchmark import Features, metrics, norm
from .competitiveness import candidate_model, make_pool
from .opportunity import strict_mask
from .expansion import read, dump, digest, qi, qs, keep_age_at

EXPERIMENT_AVAILABLE_ON = '2026-11-08'


def validate_query(query):
    # This is a frozen current-vintage experiment, not a historical as-of service.
    if date.fromisoformat(query['reference_date']) < date.fromisoformat(EXPERIMENT_AVAILABLE_ON):
        raise ValueError('Task008 current vintage was not known available at that reference date')
    for field in ('asking_price_jpy','面積（㎡）'):
        value=float(query[field])
        if not np.isfinite(value) or value<=0:
            raise ValueError('Positive finite asking price and area required')
    return dict(query,quarter='2026Q2')


def window_bounds(origin, years):
    if years not in (3,5,8): raise ValueError('Only predeclared 3/5/8-year windows')
    end=qi(origin)
    return qs(end-4*years), qs(end-1)


def split_masks(df, origin, years):
    start,end=window_bounds(origin,years)
    known=set(df.quarter)
    expected={qs(i) for i in range(qi(start),qi(end)+1)}
    if not expected.issubset(known): return None
    train=df.quarter.between(start,end)
    valid=df.quarter.eq(origin)
    if not train.any() or not valid.any(): return None
    if not (df.loc[train,'quarter'].max()<df.loc[valid,'quarter'].min()):
        raise ValueError('Temporal overlap')
    return train,valid


def strict_support(pool, targets):
    """Same Task006 constraints; optional supplied town/layout/structure stay exact."""
    groups={key:g for key,g in pool.groupby(['municipality','station'])}
    counts=[]
    for r in targets.to_dict('records'):
        if not np.isfinite(r['age']) or not np.isfinite(r['area']) or not isinstance(r['station'],str) or not r['station']:
            counts.append(0); continue
        g=groups.get((r['municipality'],r['station']))
        if g is None: counts.append(0); continue
        mask=(g.area.to_numpy()>=r['area']*.8)&(g.area.to_numpy()<=r['area']*1.2)&(np.abs(g.age.to_numpy()-r['age'])<=10)
        for col in ('town','layout','structure'):
            if isinstance(r.get(col),str) and r[col]: mask &= g[col].to_numpy()==r[col]
        counts.append(int(mask.sum()))
    return np.array(counts)


def score(y,p):
    result=metrics(np.asarray(y),np.asarray(p))
    result.update(mean_signed_error_jpy_m2=float(np.mean(p-y)),mean_signed_pct=float(np.mean((p-y)/y)*100),
                  overprediction_fraction=float(np.mean(p>y)))
    return result


def summarize(predictions, group_columns):
    rows=[]
    for keys,g in predictions.groupby(group_columns,dropna=False):
        if not isinstance(keys,tuple): keys=(keys,)
        result=dict(zip(group_columns,keys))|score(g.actual.to_numpy(),g.predicted.to_numpy())
        result['strict_support_ge10_rate']=float((g.comparable_n>=10).mean())
        ok=g.empirical_radius.notna()
        result['empirical_interval_n']=int(ok.sum())
        result['empirical_interval_coverage']=float((np.abs(g.loc[ok,'log_residual'])<=g.loc[ok,'empirical_radius']).mean()) if ok.any() else None
        rows.append(result)
    return pd.DataFrame(rows)


def fraction(values,threshold):
    a=np.asarray(values,dtype=float); a=a[np.isfinite(a)]
    return dict(n=len(a),lower_count=int((a<threshold).sum()),fraction=float((a<threshold).mean()) if len(a)>=10 else None,
                status='descriptive_only' if len(a)>=10 else '无法判断')


def run(data, query_path, output):
    if output.exists(): raise FileExistsError('New experiment directory required')
    q=validate_query(json.loads(query_path.read_text(encoding='utf-8')))
    output.mkdir(parents=True)
    protocol=dict(version='task008-exploratory-v1',data_sha256=digest(data),query_sha256=digest(query_path),
                  training_windows_years=[3,5,8],validation='one quarter strictly after training; expanding origins',
                  estimator='Task005 Ridge(alpha=10), fixed settings, with linear quarter term; municipality median baseline',
                  availability='CURRENT VINTAGE retrospective temporal validation, NOT historical publication-as-of backtest',
                  prior_test='2026Q1/Q2 already viewed in Task004; all Task008 comparisons exploratory, no new independent test',
                  A='Only model training-window length changes; common validation rows and fixed comparison pool.',
                  B='Only comparison records window changes; same fitted model and query reference.',
                  C='Only time adjustment is toggled using one fixed model and fixed selected rows.',
                  D='Only attribute adjustment is toggled using one fixed model and fixed selected rows.',
                  uncertainty='90th percentile absolute log residual from four preceding OOF quarters, when available; empirical transferred range, not calibrated guarantee',
                  future_test='No unused quarter beyond 2026Q2 in this dataset. Freeze settings before collecting a later release.',
                  conclusion_policy='Always abstain from current value judgement or future opportunity probabilities.')
    dump(output/'protocol.json',protocol)
    all_data=read(data)
    target=pd.to_numeric(all_data.unit_price_jpy_m2,errors='coerce')
    valid=np.isfinite(target)&(target>0)
    all_data.loc[~valid].to_csv(output/'uncomputable_targets_retained.csv',index=False,encoding='utf-8-sig')
    df=all_data.loc[valid].reset_index(drop=True); y=pd.to_numeric(df.unit_price_jpy_m2).to_numpy()
    features=make_pool(df,y)
    ask=float(q['asking_price_jpy'])/float(q['面積（㎡）']); qframe=pd.DataFrame([q])
    predictions=[]; fold_metrics=[]; failures=[]; residual_history={3:[],5:[],8:[]}; frozen={}
    for origin in sorted(set(df.quarter)):
        if origin<'2021Q1': continue
        for years in (3,5,8):
            split=split_masks(df,origin,years)
            if split is None:
                failures.append(dict(origin=origin,years=years,reason='full training window unavailable; not silently shortened'))
                continue
            train,holdout=split; tr=df.loc[train]; va=df.loc[holdout]
            model=candidate_model(True)
            with threadpool_limits(limits=4):
                model.fit(tr,np.log(y[train])); logpred=model.predict(va)
            pred=np.exp(logpred)
            if not np.isfinite(pred).all(): raise ValueError('Nonfinite predictions')
            support=strict_support(features.loc[train],features.loc[holdout])
            medians=pd.DataFrame({'city':tr['市区町村名'],'target':y[train]}).groupby('city').target.median()
            baseline=va['市区町村名'].map(medians).fillna(np.median(y[train])).to_numpy()
            previous=[(quarter,errors) for quarter,errors in residual_history[years] if qi(origin)-4<=qi(quarter)<qi(origin)]
            radius=float(np.quantile(np.concatenate([e for _,e in previous]),.9,method='higher')) if len(previous)==4 else np.nan
            rows=pd.DataFrame(dict(record_id=va.record_id.to_numpy(),quarter=origin,years=years,actual=y[holdout],predicted=pred,
                                   log_residual=np.log(y[holdout])-logpred,comparable_n=support,
                                   train_start=tr.quarter.min(),train_end=tr.quarter.max(),train_n=len(tr),method='ridge',empirical_radius=radius,
                                   municipality=va['市区町村名'].to_numpy(),layout=features.loc[holdout,'layout'].fillna('UNKNOWN').to_numpy()))
            rows['price_band']=pd.cut(rows.actual,[0,500000,1000000,1500000,np.inf],labels=['<=50man','50-100man','100-150man','>150man']).astype(str)
            rows['age_band']=pd.cut(features.loc[holdout,'age'].to_numpy(),[-1,10,20,40,np.inf],labels=['0-10','11-20','21-40','41+']).astype(str)
            rows['area_band']=pd.cut(features.loc[holdout,'area'].to_numpy(),[0,30,50,80,np.inf],labels=['<=30','30-50','50-80','>80']).astype(str)
            predictions.append(rows)
            b=rows.copy(); b['method']='municipality_median'; b['predicted']=baseline
            b['log_residual']=np.log(b.actual)-np.log(baseline); b['empirical_radius']=np.nan; predictions.append(b)
            residual_history[years].append((origin,np.abs(rows.log_residual.to_numpy())))
            fold_metrics.append(dict(origin=origin,years=years,train_start=tr.quarter.min(),train_end=tr.quarter.max(),train_n=len(tr),
                                     validation_n=len(va),mae=score(y[holdout],pred)['mae'],strict_support=float((support>=10).mean())))
            if origin=='2026Q2': frozen[years]=(model,train)
            print(f'{origin} / {years}y: n={len(va)}, MAE={fold_metrics[-1]["mae"]:.0f}',flush=True)
    p=pd.concat(predictions,ignore_index=True)
    p.to_csv(output/'forward_predictions.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(fold_metrics).to_csv(output/'folds.csv',index=False)
    dump(output/'unavailable_windows.json',failures)
    # All three windows evaluated on identical previously viewed quarters; no winner selection.
    common=set.intersection(*[set(p.loc[p.years==years,'quarter']) for years in (3,5,8)])
    common_p=p[p.quarter.isin(common)]
    summarize(common_p,['years','method']).to_csv(output/'common_window_metrics.csv',index=False)
    summarize(p,['quarter','years','method']).to_csv(output/'all_fold_metrics.csv',index=False)
    for dimension in ['price_band','municipality','age_band','area_band','layout']:
        summarize(common_p,['years','method',dimension]).to_csv(output/f'subgroup_{dimension}.csv',index=False,encoding='utf-8-sig')

    # Strict comparable pool held fixed across A/C/D. No same-quarter target used to fit query model.
    current_pool=features.copy()
    strict=strict_mask(current_pool,q,'2018Q1','2026Q2')
    common_records=df.loc[strict&(df.quarter>='2023Q1')].copy()
    all_records=df.loc[strict].copy()
    factorial=[]; fit_sensitivity=[]; current_references={}
    for years,(model,train) in frozen.items():
        with threadpool_limits(limits=4): qlog=float(model.predict(qframe)[0])
        current_references[years]=qlog
        # A: fixed records and mapping, only fitted window differs. Explicitly fitted/in-sample sensitivity.
        with threadpool_limits(limits=4): predicted=model.predict(common_records)
        ratios=pd.to_numeric(common_records.unit_price_jpy_m2).to_numpy()/np.exp(predicted)
        fit_sensitivity.append(dict(factor='A_training_window_only',years=years,query_reference=float(np.exp(qlog)),
                                    **fraction(ratios,ask/np.exp(qlog)),train_overlap=int(common_records.record_id.isin(df.loc[train,'record_id']).sum()),
                                    evidence='fitted diagnostic, NOT independent historical performance'))
    base,train=frozen[3]; qlog=current_references[3]
    for start in ('2023Q1','2021Q1','2018Q1'):
        rows=all_records[all_records.quarter>=start]
        with threadpool_limits(limits=4): logref=base.predict(rows)
        factor=pd.to_numeric(rows.unit_price_jpy_m2).to_numpy()*np.exp(qlog-logref)
        factorial.append(dict(factor='B_comparison_window_only',start=start,end='2026Q2',**fraction(factor,ask),
                              overlap=int(rows.record_id.isin(df.loc[train,'record_id']).sum()),evidence='same frozen 3y model; descriptive fitted comparison'))
    rows=common_records; actual=pd.to_numeric(rows.unit_price_jpy_m2).to_numpy(); cf=keep_age_at(rows,'2026Q2')
    with threadpool_limits(limits=4): historical=base.predict(rows); anchor=base.predict(cf)
    decomposition=pd.DataFrame({'record_id':rows.record_id,'quarter':rows.quarter,'raw':actual,
                                'attribute_only':actual*np.exp(qlog-anchor),'time_only':actual*np.exp(anchor-historical),
                                'attribute_and_time':actual*np.exp(qlog-historical)})
    decomposition.to_csv(output/'controlled_CD_records.csv',index=False,encoding='utf-8-sig')
    for method in ['raw','attribute_only','time_only','attribute_and_time']:
        factorial.append(dict(factor='CD_fixed_coefficients_2x2',method=method,start='2023Q1',end='2026Q2',
                              **fraction(decomposition[method],ask),evidence='descriptive fitted sensitivity, NOT independent performance'))
    dump(output/'factorial_sensitivity.json',dict(A=fit_sensitivity,BCD=factorial))

    # Relative advantage uses each trade's strictly prior-quarter model. No random cross-fitting.
    oof=p[(p.method=='ridge')&p.record_id.isin(all_records.record_id)].copy()
    oof['relative_price_ratio']=oof.actual/oof.predicted
    oof['current_asking_ratio']=[ask/np.exp(current_references[int(w)]) for w in oof.years]
    oof['lower_relative_ratio']=oof.relative_price_ratio<oof.current_asking_ratio
    oof['evidence']='current-vintage forward OOF reference; not a proven bargain or future probability'
    oof.to_csv(output/'relative_oof_records.csv',index=False,encoding='utf-8-sig')
    robust=[]
    for years in (3,5,8):
        for start in ('2018Q1','2021Q1','2023Q1','2025Q3'):
            g=oof[(oof.years==years)&(oof.quarter>=start)]
            eligible=all_records[all_records.quarter>=start]
            robust.append(dict(years=years,history_start=start,eligible_strict_n=len(eligible),oof_n=len(g),
                               not_evaluable_n=len(eligible)-len(g),
                               **fraction(g.relative_price_ratio,ask/np.exp(current_references[years])),
                               full_history_fraction=None if len(g)!=len(eligible) else fraction(g.relative_price_ratio,ask/np.exp(current_references[years]))['fraction'],
                               conclusion='无法判断'))
    # Isolate A on identical OOF records available under all windows, including n<10 refusals.
    common_ids=set.intersection(*[set(oof.loc[oof.years==w,'record_id']) for w in (3,5,8)])
    matched=[]
    for years in (3,5,8):
        g=oof[(oof.years==years)&oof.record_id.isin(common_ids)]
        matched.append(dict(years=years,**fraction(g.relative_price_ratio,ask/np.exp(current_references[years]))))
    # Quarterly reliability for this query and regional support without weakening matching rules.
    support_summary=[]
    for origin in sorted(df.quarter.unique()):
        subset=all_records[all_records.quarter==origin]
        support_summary.append(dict(quarter=origin,strict_n=len(subset),raw_lower_count=int((pd.to_numeric(subset.unit_price_jpy_m2)<ask).sum()),
                                    status='无法判断' if len(subset)<10 else 'descriptive_only'))
    pd.DataFrame(support_summary).to_csv(output/'query_quarter_support.csv',index=False)
    summary=dict(common_validation_quarters=sorted(common),strict_historical_n=len(all_records),strict_original_window_n=len(common_records),
                 raw_historical=fraction(pd.to_numeric(all_records.unit_price_jpy_m2),ask),
                 forward_oof_historical_relative_comparisons=robust,matched_training_window_sensitivity=matched,
                 query_reference={str(w):float(np.exp(logv)) for w,logv in current_references.items()},
                 final_conclusion='无法判断',publication_vintage_backtest=False,new_independent_test=False,
                 limitations=['Before sufficient earlier training history, historical relative advantage is not evaluable.',
                              'OOF residuals include model error, omitted characteristics and transaction circumstances, not pure value.',
                              'Current asking ratio is compared against lagged transaction references; no validated asking-to-sale adjustment.',
                              'Original Task004 test observations are reused only as explicitly exploratory data; no new independent claims.',
                              'Empirical ranges are not calibrated prediction intervals; no confidence interval for fractions.',
                              'Anonymous records may be correlated/repeated properties, so binomial independence is not assumed.'])
    dump(output/'robustness.json',summary)
    return summary


def main():
    p=argparse.ArgumentParser(description='Task008 exploratory forward validation, fixed Ridge settings')
    p.add_argument('--data',type=Path,required=True); p.add_argument('--query',type=Path,default=Path('examples/opportunity-small-unit.json'))
    p.add_argument('--output',type=Path,required=True); args=p.parse_args()
    result=run(args.data,args.query,args.output)
    print(json.dumps({k:result[k] for k in ['common_validation_quarters','strict_historical_n','strict_original_window_n','final_conclusion']},ensure_ascii=False))


if __name__=='__main__': main()
