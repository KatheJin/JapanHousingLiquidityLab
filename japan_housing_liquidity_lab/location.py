"""Offline location/budget research. No railway routing, model fitting or price ranking."""
import argparse
from datetime import date
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from .benchmark import Features, distance, norm
from .expansion import digest, dump, qi, qs, read
from .transactions import number

UNKNOWN = '(unknown)'
MIN_N = 30  # Reporting gate, not a confidence guarantee.
PROFILE_MIN_N = 10
DESTINATIONS = ['渋谷', '新宿', '東京', '品川', '池袋']
TRANSPORT_MODES = ('public_transport', 'private_car', 'bicycle', 'mixed')
PROFILE = dict(area_m2=50, age_at_trade=20, layout='2LDK', structure='RC')
LIMITATIONS = [
    'Historical MLIT sample records, not all transactions, listings or future opportunities.',
    'Budget matching uses nominal historical sale prices, not current asking prices or acquisition costs.',
    'Nearest-station access minutes are not railway or door-to-door commute minutes.',
    'Station names are not verified railway IDs; municipality plus station name is a local market label.',
    'Unknown first-publication vintages: retrospective current-vintage description only.',
    'IQR is sample dispersion, not a confidence interval; reporting thresholds do not establish reliability.',
    'Duplicates and outliers retained; anonymous repeated properties may be dependent.',
    'Unobserved floor, renovation, orientation and management can confound all comparisons.',
    'No causal distance penalty, single-city-centre assumption, value ranking or appreciation forecast.',
    '2026Q2 coverage can be incomplete/revised; missing quarters are not zero transactions.',
]


def numeric(value):
    try:
        return number(value)
    except ValueError:
        return np.nan


def walk_bounds(value):
    """Keep interval endpoints; never turn a band midpoint into observed access time."""
    v = norm(value)
    minutes, _, kind = distance(v)
    bounds = {'30分~60分': (30., 60.), '1H~1H30': (60., 90.),
              '1H30~2H': (90., 120.), '2H~': (120., np.inf)}
    if kind == 'exact':
        return minutes, minutes
    return bounds.get(v, (np.nan, np.nan))


def walk_band(value):
    lo, hi = walk_bounds(value)
    if np.isnan(lo):
        return UNKNOWN
    if lo != hi:
        return 'interval:' + norm(value)
    for cap, label in [(5, '0-5'), (10, '>5-10'), (15, '>10-15'), (20, '>15-20'), (29, '>20-29')]:
        if hi <= cap:
            return label
    return 'exact:30+'


def prepare(raw):
    required = {'record_id', 'quarter', '市区町村名', '最寄駅：名称', '最寄駅：距離（分）',
                '取引価格（総額）', '面積（㎡）', '建築年', '間取り', '建物の構造', 'unit_price_jpy_m2'}
    if not required.issubset(raw.columns) or raw.empty:
        raise ValueError('Nonempty Task008 merged data and required fields needed')
    if raw.record_id.duplicated().any():
        raise ValueError('Duplicate source IDs; transaction duplicates must retain different source IDs')
    for quarter in raw.quarter.unique():
        qi(quarter)
    f = Features().transform(raw)
    result = f.copy()
    result['record_id'] = raw.record_id.to_numpy()
    result['quarter'] = raw.quarter.to_numpy()
    result['year'] = raw.quarter.str[:4].to_numpy()
    result['total_jpy'] = raw['取引価格（総額）'].map(numeric).to_numpy()
    result['unit_jpy_m2'] = result.total_jpy / result.area
    saved = pd.to_numeric(raw.unit_price_jpy_m2, errors='coerce').to_numpy()
    if not np.allclose(result.unit_jpy_m2, saved, equal_nan=True):
        raise ValueError('Unit-price mismatch with Task008 retained targets')
    for col in ['municipality', 'station', 'layout', 'structure']:
        result[col] = result[col].fillna(UNKNOWN)
    bounds = [walk_bounds(v) for v in raw['最寄駅：距離（分）']]
    result['walk_lower'] = [v[0] for v in bounds]
    result['walk_upper'] = [v[1] for v in bounds]
    result['walk_band'] = raw['最寄駅：距離（分）'].map(walk_band).to_numpy()
    for col in ['exact_duplicate_flag', 'same_attributes_other_period_flag']:
        result[col] = raw[col].str.lower().eq('true').to_numpy() if col in raw else False
    result['quality_flagged'] = raw.quality_flags.ne('').to_numpy() if 'quality_flags' in raw else False
    result['standardized_unit'] = np.nan
    result['profile_support'] = False
    return result


def validate_query(query, quarters, available_on):
    if not isinstance(query, dict) or not {'reference_date','budget_max_jpy'}.issubset(query):
        raise ValueError('JSON object with reference_date and budget_max_jpy required')
    allowed = {'reference_date', 'history_start', 'history_end', 'budget_min_jpy', 'budget_max_jpy',
               'min_area_m2', 'max_area_m2', 'max_age', 'max_walk_minutes', 'layouts', 'structures',
               'municipalities', 'destinations', 'max_commute_minutes', 'transport_modes'}
    if set(query) - allowed:
        raise ValueError('Unknown query fields: ' + ', '.join(sorted(set(query) - allowed)))
    q = dict(query)
    if date.fromisoformat(q['reference_date']) < date.fromisoformat(available_on):
        raise ValueError('Data vintage not known available at reference date')
    latest = max(quarters)
    q.setdefault('history_end', latest)
    q.setdefault('history_start', qs(max(qi(min(quarters)), qi(q['history_end'])-5)))
    start, end = qi(q['history_start']), qi(q['history_end'])
    if start > end or not {qs(i) for i in range(start, end+1)}.issubset(quarters):
        raise ValueError('Requested quarters unavailable; never count missing/unpublished quarters as zero')
    q.setdefault('budget_min_jpy', 0)
    q.setdefault('min_area_m2', 0)
    for key in ['budget_min_jpy', 'budget_max_jpy', 'min_area_m2', 'max_area_m2', 'max_age', 'max_walk_minutes', 'max_commute_minutes']:
        if key not in q:
            continue
        if isinstance(q[key], bool) or not isinstance(q[key], (float, int)) or not np.isfinite(q[key]) or q[key] < 0:
            raise ValueError('Nonnegative finite numeric value required: ' + key)
    if (q['budget_max_jpy'] <= 0 or q['budget_max_jpy'] < q['budget_min_jpy']
            or q.get('max_area_m2', np.inf) <= 0 or q.get('max_area_m2', np.inf) < q['min_area_m2']):
        raise ValueError('Invalid budget or area range')
    for key in ['layouts', 'structures', 'municipalities', 'destinations']:
        value = q.setdefault(key, DESTINATIONS.copy() if key == 'destinations' else [])
        if not isinstance(value, list) or any(not isinstance(v, str) or not norm(v) for v in value):
            raise ValueError('Expected list of nonempty names: ' + key)
        q[key] = list(dict.fromkeys(norm(v) for v in value))
    modes=q.setdefault('transport_modes', ['public_transport'])
    if not isinstance(modes, list) or not modes or any(not isinstance(m, str) or m not in TRANSPORT_MODES for m in modes):
        raise ValueError('transport_modes must be a nonempty list of: ' + ', '.join(TRANSPORT_MODES))
    q['transport_modes']=list(dict.fromkeys(modes))
    return q


def commute_result(q):
    """Capability declaration only. No speeds, routes, mode blending or inferred times."""
    return dict(status='unavailable_not_verified', destinations=q['destinations'],
                limit_minutes=q.get('max_commute_minutes'), constraints_applied=False,
                door_to_door_minutes=None, requested_modes=q['transport_modes'],
                by_mode={mode:dict(status='unsupported_no_verified_route_data',
                                   door_to_door_minutes=None, within_limit=None)
                         for mode in q['transport_modes']},
                reason='No verified mode-specific routes, service/traffic conditions or transfer data loaded')


def budget_mask(frame, q):
    mask = frame.quarter.between(q['history_start'], q['history_end'])
    mask &= frame.total_jpy.between(q['budget_min_jpy'], q['budget_max_jpy'])
    mask &= frame.area.ge(q['min_area_m2']) & frame.area.notna()
    if 'max_area_m2' in q:
        mask &= frame.area.le(q['max_area_m2'])
    if 'max_age' in q:
        mask &= frame.age.le(q['max_age']) & frame.age.notna()
    if 'max_walk_minutes' in q:
        mask &= frame.walk_upper.le(q['max_walk_minutes']) & frame.walk_upper.notna()
    for field, key in [('layout', 'layouts'), ('structure', 'structures'), ('municipality', 'municipalities')]:
        if q[key]:
            mask &= frame[field].isin(q[key])
    return mask


def standardize(raw, frame, bundle):
    """Property-only diagnostic: retain location, access and trade quarter, not time-adjustment."""
    if bundle['latest_quarter'] != '2026Q2':
        raise ValueError('Expected frozen Task005 v2 artifact; review scope before using another model')
    out = frame.copy()
    known = (out.municipality != UNKNOWN) & (out.station != UNKNOWN)
    known &= out.age.notna() & out.area.notna() & out.unit_jpy_m2.notna()
    known &= out.layout.ne(UNKNOWN) & out.structure.ne(UNKNOWN) & out.walk_lower.notna()
    # No extrapolation of the 2023+ artifact into 2018--2022.
    known &= out.quarter.between('2023Q1', bundle['latest_quarter'])
    pairs = set(zip(bundle['pool'].municipality, bundle['pool'].station))
    known &= pd.Series([(c, s) in pairs for c, s in zip(out.municipality, out.station)], index=out.index)
    if known.any():
        rows = raw.loc[known].copy()
        cf = rows.copy()
        cf['面積（㎡）'] = str(PROFILE['area_m2'])
        cf['建築年'] = (cf.quarter.str[:4].astype(int)-PROFILE['age_at_trade']).astype(str)+'年'
        cf['間取り'] = PROFILE['layout']; cf['建物の構造'] = PROFILE['structure']
        model = bundle['models']['history_with_time']
        with threadpool_limits(limits=4):
            adjusted = out.loc[known, 'unit_jpy_m2'].to_numpy()*np.exp(
                np.asarray(model.predict(cf))-np.asarray(model.predict(rows)))
        if not np.isfinite(adjusted).all():
            raise ValueError('Nonfinite standardized prices')
        out.loc[known, 'standardized_unit'] = adjusted
    out['profile_support'] = (known & out.area.between(PROFILE['area_m2']*.8, PROFILE['area_m2']*1.2)
                              & (out.age-PROFILE['age_at_trade']).abs().le(10)
                              & out.layout.eq(PROFILE['layout']) & out.structure.eq(PROFILE['structure']))
    return out


def stats(g):
    result = dict(n=len(g), period_min=g.quarter.min() if len(g) else None,
                  period_max=g.quarter.max() if len(g) else None,
                  quarter_count=g.quarter.nunique(), status='descriptive_support' if len(g) >= MIN_N else 'insufficient_sample',
                  quality_flagged_n=int(g.quality_flagged.sum()), exact_duplicate_flag_n=int(g.exact_duplicate_flag.sum()))
    for col in ['total_jpy', 'unit_jpy_m2', 'area', 'age', 'standardized_unit']:
        values=g[col].dropna()
        result[col+'_n'] = len(values)
        gate = len(values) >= MIN_N
        if col == 'standardized_unit':
            result['profile_support_n'] = int(g.profile_support.sum())
            gate &= result['profile_support_n'] >= PROFILE_MIN_N
        for label, quantile in [('p25', .25), ('median', .5), ('p75', .75)]:
            result[col+'_'+label] = float(values.quantile(quantile)) if gate else None
            if col == 'standardized_unit':
                # Paired raw comparison: same records, avoiding missingness/period composition changes.
                paired=g.loc[g.standardized_unit.notna(), 'unit_jpy_m2']
                result['standardized_subset_raw_unit_'+label] = float(paired.quantile(quantile)) if gate else None
    result['layout_missing_n'] = int(g.layout.eq(UNKNOWN).sum())
    result['station_missing_n'] = int(g.station.eq(UNKNOWN).sum())
    result['walk_missing_n'] = int(g.walk_lower.isna().sum())
    counts=g.loc[g.layout.ne(UNKNOWN), 'layout'].value_counts()
    result['modal_layout'] = counts.index[0] if counts.sum() >= MIN_N else None
    result['modal_layout_share_known'] = float(counts.iloc[0]/counts.sum()) if result['modal_layout'] else None
    return result


def table(frame, keys, match=None):
    rows=[]
    for group, g in frame.groupby(keys, sort=True, dropna=False):
        if not isinstance(group, tuple):
            group=(group,)
        selected=g if match is None else g.loc[match.loc[g.index]]
        r=dict(zip(keys, group)) | stats(selected)
        if any(r.get(k) == UNKNOWN for k in ['municipality','station']):
            r['status'] = 'unknown_location'
        if match is not None:
            r['period_sample_n'] = len(g)
            r['matched_fraction_of_period_sample'] = len(selected)/len(g)
            r['commute_verified'] = False
        rows.append(r)
    return pd.DataFrame(rows)


def walk_contrasts(frame):
    """Nonparametric within-station/year contrast; no imposed linear 10-minute penalty."""
    rows=[]
    for key, g in frame.groupby(['municipality', 'station', 'year']):
        if UNKNOWN in key:
            continue
        near=g[g.walk_band.eq('0-5')]; far=g[g.walk_band.eq('>10-15')]
        n=stats(near); f=stats(far)
        if n['unit_jpy_m2_n'] < MIN_N or f['unit_jpy_m2_n'] < MIN_N:
            continue
        r=dict(zip(['municipality', 'station', 'year'], key))
        r.update(near_n=len(near), far_n=len(far),
                 raw_far_to_near=f['unit_jpy_m2_median']/n['unit_jpy_m2_median'],
                 standardized_far_to_near=None)
        if n['standardized_unit_median'] and f['standardized_unit_median']:
            r['standardized_far_to_near']=f['standardized_unit_median']/n['standardized_unit_median']
        rows.append(r)
    return pd.DataFrame(rows, columns=['municipality','station','year','near_n','far_n','raw_far_to_near','standardized_far_to_near'])


def run(data, quality_path, query_path, output, reference=None):
    if output.exists():
        raise FileExistsError('Use a new output directory; old experiments are immutable')
    quality=json.loads(quality_path.read_text(encoding='utf-8'))
    if digest(data) != quality['combined_sha256']:
        raise ValueError('Input SHA-256 differs from Task008 quality report')
    raw=read(data).reset_index(drop=True)
    if len(raw) != quality['total'] or sorted(raw.quarter.unique()) != quality['quarters']:
        raise ValueError('Task008 coverage/count mismatch')
    available=max(m['acquired_at'][:10] for m in quality['sources'])
    q=validate_query(json.loads(query_path.read_text(encoding='utf-8')), set(raw.quarter), available)
    frame=prepare(raw)
    model_metadata=None
    if reference is not None:
        bundle=joblib.load(reference)  # Local trusted project artifact only; never downloaded user models.
        if q['reference_date'] < bundle['protocol']['available_on']:
            raise ValueError('Reference model vintage unavailable at query date')
        frame=standardize(raw, frame, bundle)
        model_metadata=dict(sha256=digest(reference),source=str(reference),version=bundle['protocol']['version'],
                            fit_start='2023Q1',fit_end=bundle['latest_quarter'],profile=PROFILE,
                            formula='observed_unit * exp(f(profile, same location/access/quarter) - f(observed))',
                            evidence='Retrospective fitted attribute sensitivity, NOT independent prediction performance',
                            time_adjustment=False,profile_min_n=PROFILE_MIN_N)
    tables={}
    for label, keys in [('regions',['municipality']),('stations',['municipality','station'])]:
        tables[label+'_all']=table(frame, keys)
        tables[label+'_year']=table(frame, keys+['year'])
        tables[label+'_quarter']=table(frame, keys+['quarter'])
    period=frame[frame.quarter.between(q['history_start'],q['history_end'])]
    match=budget_mask(period, q)
    tables['budget_regions']=table(period, ['municipality'], match)
    tables['budget_stations']=table(period, ['municipality','station'], match)
    tables['walk_all']=table(frame, ['walk_band'])
    tables['walk_region_year']=table(frame, ['municipality','year','walk_band'])
    tables['walk_station_year']=table(frame, ['municipality','station','year','walk_band'])
    tables['walk_contrasts']=walk_contrasts(frame)
    tables['layout_distribution']=frame.groupby(['municipality','year','layout']).size().rename('n').reset_index()
    tables['budget_layouts']=period.loc[match].groupby(['municipality','station','layout']).size().rename('n').reset_index()
    coverage=[]
    for year, g in frame.groupby('year'):
        coverage.append(dict(year=year,n=len(g),quarters=sorted(g.quarter.unique()),
                             full_calendar_year=g.quarter.nunique()==4,complete_population=False,
                             publication_date=None))
    quality_fields=['municipality','station','area','age','layout','structure','walk_lower','total_jpy','unit_jpy_m2']
    missing={k:int((frame[k].isna() | frame[k].eq(UNKNOWN)).sum()) for k in quality_fields}
    summary=dict(version='task009-v2',data_sha256=digest(data),query_sha256=digest(query_path),
                 n=len(frame),period=[frame.quarter.min(),frame.quarter.max()],query=q,available_on=available,
                 year_coverage=coverage,missing_or_unparsed=missing,min_descriptive_n=MIN_N,
                 support_threshold_is_confidence_guarantee=False,model=model_metadata,
                 region_groups_ge30=int((tables['regions_all'].n>=MIN_N).sum()),
                 station_groups_ge30=int(((tables['stations_all'].n>=MIN_N)&tables['stations_all'].station.ne(UNKNOWN)).sum()),
                 budget=dict(period_sample_n=len(period),matched_n=int(match.sum()),
                             supported_regions=int((tables['budget_regions'].n>=MIN_N).sum()),
                             supported_station_groups=int(((tables['budget_stations'].n>=MIN_N)&tables['budget_stations'].station.ne(UNKNOWN)).sum()),
                             evidence='Historical nominal transactions meeting housing filters only'),
                 commute=commute_result(q),
                 new_independent_test=False,causal_interpretation=False,final_conclusion='无法判断当前性价比或通勤可行性',
                 limitations=LIMITATIONS)
    output.mkdir(parents=True)
    for name, value in tables.items():
        value.to_csv(output/(name+'.csv'),index=False,encoding='utf-8-sig')
    dump(output/'analysis.json',summary)
    dump(output/'budget_comparison.json',dict(metadata=summary['budget'],query=q,commute=summary['commute'],
         limitations=LIMITATIONS,
         regions=json.loads(tables['budget_regions'].to_json(orient='records',force_ascii=False)),
         stations=json.loads(tables['budget_stations'].to_json(orient='records',force_ascii=False))))
    return summary


def main():
    p=argparse.ArgumentParser(description='Historical location/budget analysis; public transport, private car, bicycle and mixed commute modes accepted in query JSON; all route times unavailable')
    p.add_argument('--data',type=Path,default=Path('reports/task008-data/merged_retained.csv'))
    p.add_argument('--quality',type=Path,default=Path('reports/task008-data/quality.json'))
    p.add_argument('--query',type=Path,required=True)
    p.add_argument('--reference',type=Path,help='Optional trusted local Task005 v2 reference.joblib; never fits new models')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=run(args.data,args.quality,args.query,args.output,args.reference)
    print(json.dumps({k:result[k] for k in ['n','period','budget','commute','final_conclusion']},ensure_ascii=False))


if __name__=='__main__':
    main()
