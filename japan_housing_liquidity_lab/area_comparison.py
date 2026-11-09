"""Frozen-artifact spatial hedonic diagnostics; no training, HTTP or formal rankings."""
from datetime import date
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .benchmark import Features, norm, metrics
from .web_adapter import load_real

METHODS=('all_history_no_time','recent_no_time','history_with_time')
PRIMARY='history_with_time'
MIN_MARKET=30
MIN_PROFILE=10
RECENT_START='2025Q3'
AGREEMENT_LIMIT_PCT=10
AGREEMENT_SPREAD_PCT=5


def _raw_distribution(frame,configured_period):
    """Raw joint-profile observations; no modeled or time-adjusted prices."""
    prices=pd.to_numeric(frame.actual,errors='coerce')
    valid=prices[np.isfinite(prices)&prices.gt(0)]
    enough=len(valid)>=MIN_PROFILE
    quartiles=valid.quantile([.25,.5,.75]).tolist() if enough else [None,None,None]
    return dict(status='descriptive_only' if enough else 'insufficient_sample',
        sample_n=len(frame),valid_price_n=len(valid),missing_or_invalid_price_n=len(frame)-len(valid),
        configured_period=list(configured_period),period_start=str(frame.period.min()) if len(frame) else None,
        period_end=str(frame.period.max()) if len(frame) else None,
        raw_unit_price_jpy_m2=dict(zip(['q1','median','q3'],quartiles)),
        minimum_price_sample_n=MIN_PROFILE,adjusted=False,
        interpretation='Unadjusted observed transactions after joint-profile filters. Mixed periods and remaining property differences; not standardized prices, intervals, or proof of equivalent markets.')

def load(root):
    root=Path(root)
    _,raw,available=load_real(root,'location')
    bundle,model_raw,model_available=load_real(root,'home')
    if bundle['latest_quarter']!='2026Q2' or set(bundle['models'])!=set(METHODS):
        raise ValueError('Frozen model scope differs; review before using new artifacts')
    pool=Features().transform(raw)
    pool['period']=raw.quarter.to_numpy()
    pool['actual']=pd.to_numeric(raw.unit_price_jpy_m2,errors='coerce').to_numpy()
    dev_path=root/'reports/competitiveness-005-v2/development_predictions.csv'
    dev=pd.read_csv(dev_path,encoding='utf-8-sig')
    validation=model_raw[model_raw.quarter.str.startswith('2025')].reset_index(drop=True)
    if len(dev)!=len(validation) or not np.allclose(dev.actual,pd.to_numeric(validation.unit_price_jpy_m2)) or not validation['市区町村名'].eq(dev.municipality).all():
        raise ValueError('Development prediction alignment cannot be verified')
    dev['station']=validation['最寄駅：名称'].map(norm)
    known={}
    for name,model in bundle['models'].items():
        encoder=model['preprocess'].named_transformers_['cat']['encode']
        known[name]={}
        for field,i in [('municipality',0),('station',1),('layout',3),('structure',4)]:
            pooled=encoder.infrequent_categories_[i]
            known[name][field]=set(encoder.categories_[i])-set(pooled if pooled is not None else [])
    artifact=root/'reports/competitiveness-005-v2/reference.joblib'
    phase2=root/'reports/hedonic-phase2-v1/metrics_high_price_inclusive.csv'
    prior=pd.read_csv(phase2).query("variant=='raw' and model=='ridge'").to_dict('records') if phase2.exists() else []
    metadata=dict(source='国土交通省 不動産情報ライブラリ 不動産取引価格情報',url='https://www.reinfolib.mlit.go.jp/',
        available_on=max(available,model_available),records=len(raw),model_records=len(model_raw),
        model_period=['2023Q1','2026Q2'],expanded_period=['2018Q1','2022Q4'],reference_quarter='2026Q2',
        data_sha256=hashlib.sha256((root/'reports/task008-data/merged_retained.csv').read_bytes()).hexdigest(),
        artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),model_version=bundle['protocol']['version'],
        development_prediction_sha256=hashlib.sha256(dev_path.read_bytes()).hexdigest(),
        development_evaluation='2025 exploratory development holdout, fitted only on2023–24 (recent:2024); transferred evidence, not current-fit calibration',
        independent_test=False,publication_asof_backtest=False,quarter_coverage_may_be_incomplete=True,
        model_periods={'all_history_no_time':'2023Q1–2026Q2 pooled, no time feature','recent_no_time':'2025Q3–2026Q2 pooled, no time feature','history_with_time':'2023Q1–2026Q2, linear quarter feature'},
        phase2_window_models_retained=False,phase2_high_price_prior=prior)
    return dict(pool=pool,bundle=bundle,metadata=metadata,development=dev,known=known)


def _error(frame,method):
    if frame.empty:return dict(n=0,mae=None,mape_pct=None,mean_signed_error_jpy_m2=None)
    y=frame.actual.to_numpy(float);p=frame[method].to_numpy(float)
    return metrics(y,p)|dict(mean_signed_error_jpy_m2=float(np.mean(p-y)))


def _profile(pool,f):
    # Joint support is calculated after ALL fixed property filters, not from whole history.
    return (pool.area.between(.8*f.area,1.2*f.area)&pool.age.between(f.age-10,f.age+10)
        &pool.layout.eq(f.layout)&pool.structure.eq(f.structure)&pool.distance_kind.eq('exact')
        &pool.minutes.between(max(0,f.minutes-5),f.minutes+5))


def compare(resources,query):
    meta=resources['metadata'];bundle=resources['bundle'];pool=resources['pool'];dev=resources['development']
    q=dict(query,quarter=meta['reference_quarter'])
    if date.fromisoformat(q['reference_date'])<date.fromisoformat(meta['available_on']):
        raise ValueError('Current data vintage unavailable at requested reference date')
    f=Features().transform(pd.DataFrame([q])).iloc[0]
    warnings=['研究用候補です。地区間の標準化価格差は独立検証されておらず、正式価格・推奨順位は利用不可です。',
        '2026Q2基準の歴史的参考で、現在の売出価格ではありません。2026Q2は不完全・改訂の可能性があります。',
        '同じ住宅属性で地区だけを変えたモデル依存の比較です。因果効果や実在住宅の同品質を保証しません。',
        '3本の既存Ridgeの感度を比較。時間項なしの2本は期間平均的な参照で、2026Q2の時点価格を独立検証したものではありません。',
        '3/5/8年実験の学習済みモデルは保存されていないため、その窓による候補順位の再計算はしていません。',
        '駅名は自治体と組み合わせたMLIT文字列です。路線IDやSUUMO駅名との同一性は未検証です。',
        '実取引の四分位数は同じ条件帯で絞った未調整価格です。モデル診断とは別で、時期や残る品質差を調整していません。']
    common=dict(area_m2=float(f.area) if np.isfinite(f.area) else None,construction_year=q.get('建築年'),
        age_at_reference=float(f.age) if np.isfinite(f.age) else None,layout=q.get('間取り'),structure=q.get('建物の構造'),
        walk_minutes=float(f.minutes) if np.isfinite(f.minutes) else None,reference_quarter=q['quarter'])
    result=dict(version='phase5-research-v1',status='unavailable',query=dict(query),common_attributes=common,
        reference_quarter=q['quarter'],source=meta,warnings=warnings,target=None,candidates=[],
        selection_rule='Union of closest10 markets under each frozen model; broad proximity bands then alphabetical display; never a validated ranking',
        evidence_group_policy=dict(insufficient_sample='Recent joint-profile observations below10; existing overall market/profile gates unchanged',
            multi_model_agreement='All three diagnostic relative gaps within plus/minus10% and max-minus-min spread at most5 percentage points; descriptive agreement only, not validated equivalence',
            model_disagreement='At least one relative gap outside plus/minus10%, or gap spread exceeds5 percentage points; no validated superiority',
            recent_period=[RECENT_START,meta['reference_quarter']],recent_sample_min=MIN_PROFILE,agreement_limit_pct=AGREEMENT_LIMIT_PCT,agreement_spread_percentage_points=AGREEMENT_SPREAD_PCT,
            target_support_caveat='Candidate grouping does not remove sparse target support; all formal outputs remain unavailable'),
        evidence_group_counts={'multi_model_agreement':0,'model_disagreement':0,'insufficient_sample':0},
        support_policy=dict(market_min=MIN_MARKET,profile_min=MIN_PROFILE,model_period=meta['model_period'],area_tolerance_pct=20,age_tolerance_years=10,walk_tolerance_minutes=5,layout_structure_exact=True,threshold_is_reliability_guarantee=False))
    reasons=[]
    for field in ['area','age','minutes']:
        if not np.isfinite(f[field]):reasons.append('Required property feature missing: '+field)
    for field in ['municipality','station','layout','structure']:
        if pd.isna(f[field]) or not f[field]:reasons.append('Required property feature missing: '+field)
    if np.isfinite(f.area) and not bundle['ranges']['area'][0]<=f.area<=bundle['ranges']['area'][1]:reasons.append('Area outside central98% model support')
    for method in METHODS:
        for field in ['layout','structure']:
            if f[field] not in resources['known'][method][field]:reasons.append('Unseen or pooled '+field+' in '+method)
    if f.distance_kind!='exact' or (np.isfinite(f.minutes) and f.minutes<0):reasons.append('Known nonnegative exact walking minutes required')
    def blank(city,station,why):
        return dict(municipality=city,station=station,market_granularity='municipality_station',town=None,status='unavailable',
            reference_unit_price_jpy_m2=None,relative_gap_pct=None,diagnostic_reference_unit_price_jpy_m2=None,
            diagnostic_relative_gap_pct=None,support_n=0,reasons=why,uncertainty={},
            evidence_group='insufficient_sample',evidence_group_reasons=why,historical_joint_profile=None,
            model_agreement=None,diagnostic_gap_spread_percentage_points=None)
    if reasons:
        result['target']=blank(q.get('市区町村名'),q.get('最寄駅：名称'),reasons);return result
    model_period=pool.period.between(*meta['model_period'])
    profile=_profile(pool,f)
    current=pool.loc[model_period]
    def historical_profile(city,station):
        frame=pool.loc[model_period&profile&pool.municipality.eq(city)&pool.station.eq(station)]
        summary=_raw_distribution(frame,meta['model_period'])
        summary['recent']=_raw_distribution(frame.loc[frame.period.ge(RECENT_START)],[RECENT_START,meta['reference_quarter']])
        return summary
    groups=current.groupby(['municipality','station']).size().rename('market_n').to_frame()
    for name,mask in [('support_n',model_period&profile),('recent_support_n',model_period&profile&pool.period.ge(RECENT_START)),
                      ('expanded_period_sample_n',pool.period.lt('2023Q1'))]:
        groups[name]=pool.loc[mask].groupby(['municipality','station']).size()
    groups=groups.fillna(0).astype(int)
    target_key=(f.municipality,f.station)
    if target_key not in groups.index:
        result['target']=blank(*target_key,['Target market absent from model training period']);return result
    supported=groups.market_n.ge(MIN_MARKET)&groups.support_n.ge(MIN_PROFILE)
    known=resources['known']
    for method in METHODS:
        supported &= pd.Series([(c in known[method]['municipality'] and s in known[method]['station']) for c,s in groups.index],index=groups.index)
    result['market_pool_n']=len(groups);result['profile_supported_market_n']=int(supported.sum())
    if not supported.loc[target_key]:
        target=blank(*target_key,['Target joint-profile or market sample support insufficient; no model-only recommendation'])
        target.update(groups.loc[target_key].to_dict());target['historical_joint_profile']=historical_profile(*target_key)
        result['target']=target;return result
    selected=groups.loc[supported].copy();index=list(selected.index)
    rows=pd.DataFrame([dict(q,**{'市区町村名':c,'最寄駅：名称':s}) for c,s in index])
    target_pos=index.index(target_key)
    with threadpool_limits(limits=2):
        values={name:np.exp(bundle['models'][name].predict(rows)) for name in METHODS}
    if any(not np.isfinite(v).all() or (v<=0).any() for v in values.values()):raise ValueError('Invalid spatial model response')
    gaps={name:values[name]/values[name][target_pos]-1 for name in METHODS}
    non_target=[i for i in range(len(index)) if i!=target_pos]
    top={name:sorted(non_target,key=lambda i:(abs(gaps[name][i]),index[i]))[:10] for name in METHODS}
    ranks={name:dict(zip(sorted(non_target,key=lambda i:(abs(gaps[name][i]),index[i])),range(1,len(non_target)+1))) for name in METHODS}
    union=set().union(*[set(v) for v in top.values()]);intersection=set.intersection(*[set(v) for v in top.values()])
    result['rank_stability']=dict(compared_market_n=len(non_target),top10_union_n=len(union),top10_intersection_n=len(intersection),
        top10_all_model_jaccard=len(intersection)/len(union) if union else None,evidence='Model-definition sensitivity, not confidence or accuracy')
    def make(i):
        city,station=index[i];unit=float(values[PRIMARY][i]);support=selected.iloc[i]
        method_prices={name:dict(unit_price_jpy_m2=float(values[name][i]),relative_gap_pct=float(gaps[name][i]*100)) for name in METHODS}
        frame=dev[(dev.municipality==city)&(dev.station==station)]
        band=int(np.searchsorted([500000,1000000,1500000],unit,side='left'))
        dev_band=np.searchsorted([500000,1000000,1500000],dev[PRIMARY].to_numpy(),side='left')
        why=['Cross-market hedonic contrasts have no independent validation; formal price and rank unavailable']
        if support.recent_support_n<MIN_PROFILE:why.append('Recent joint-profile support below10')
        if support.recent_support_n==0:why.append('No matching joint profile in the recent model window; separate known categories do not establish joint support')
        if len(frame)<30:why.append('2025 station-level development error sample below30')
        spread=max(ranks[m].get(i,0) for m in METHODS)-min(ranks[m].get(i,0) for m in METHODS)
        if spread>5:why.append('Candidate order changes materially across model definitions')
        if unit>=1500000:why.append('High-price tail shows systematic underprediction in prior Phase2 experiments')
        vals=[float(values[m][i]) for m in METHODS]
        gap_spread=(max(gaps[m][i] for m in METHODS)-min(gaps[m][i] for m in METHODS))*100
        coherent=bool(all(abs(gaps[m][i]*100)<=AGREEMENT_LIMIT_PCT for m in METHODS) and gap_spread<=AGREEMENT_SPREAD_PCT)
        if support.recent_support_n<MIN_PROFILE:
            evidence_group='insufficient_sample';group_reasons=['Recent joint-profile observations below10; model agreement cannot remedy limited observations']
        elif coherent:
            evidence_group='multi_model_agreement';group_reasons=['All diagnostic gaps within plus/minus10% and spread at most5 percentage points; descriptive agreement, not validated equivalence']
        else:
            evidence_group='model_disagreement';group_reasons=['At least one gap outside plus/minus10% or spread exceeds5 percentage points; conclusion depends on model definition']
        return dict(municipality=city,station=station,market_granularity='municipality_station',town=None,status='research_candidate',
            reference_unit_price_jpy_m2=None,relative_gap_pct=None,diagnostic_reference_unit_price_jpy_m2=unit,
            diagnostic_relative_gap_pct=float(gaps[PRIMARY][i]*100),diagnostic_by_method=method_prices,
            support_n=int(support.support_n),model_period_sample_n=int(support.market_n),recent_support_n=int(support.recent_support_n),
            expanded_period_sample_n=int(support.expanded_period_sample_n),reasons=why,
            evidence_group=evidence_group,evidence_group_reasons=group_reasons,historical_joint_profile=historical_profile(city,station),
            model_agreement=coherent,diagnostic_gap_spread_percentage_points=float(gap_spread),
            proximity_band='all_methods_within_10pct' if all(abs(gaps[m][i])<=.1 for m in METHODS) else 'method_dependent',
            rank_stability=dict(min_rank=min(ranks[m].get(i,0) for m in METHODS),max_rank=max(ranks[m].get(i,0) for m in METHODS),spread=spread,by_method={m:ranks[m].get(i) for m in METHODS},validated=False),
            source_search_station_status='unverified_name_match',
            uncertainty=dict(development_station=_error(frame,PRIMARY),development_municipality=_error(dev[dev.municipality==city],PRIMARY),
                development_predicted_price_band=_error(dev.loc[dev_band==band],PRIMARY),price_band_index=band,price_band_definition='2025 development PREDICTED unit-price bands; not actual high-price-tail accuracy',price_band_bounds_jpy_m2=[500000,1000000,1500000],
                model_reference_min_max_jpy_m2=[min(vals),max(vals)],model_spread_is_prediction_interval=False,
                joint_profile_support_by_model={m:int(support.recent_support_n if m=='recent_no_time' else support.support_n) for m in METHODS},
                separate_known_categories_do_not_validate_joint_combination=True,
                evidence='2025 out-of-training predictions for prior fits; not current-fit calibration, not a station contrast test'))
    result['target']=make(target_pos)
    result['candidates']=sorted([make(i) for i in union],key=lambda r:(r['proximity_band']!='all_methods_within_10pct',r['municipality'],r['station']))
    for candidate in result['candidates']:result['evidence_group_counts'][candidate['evidence_group']]+=1
    result['status']='research_only';return result
