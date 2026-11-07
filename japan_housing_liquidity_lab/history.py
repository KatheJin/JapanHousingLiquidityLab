"""Reproducible local historical EDA; raw rows retained, no network access."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
from .mlit import inspect_csv
from .transactions import analyze, describe, number
from .batches import audit_batches

FEATURES=['市区町村名','地区名','最寄駅：名称','最寄駅：距離（分）','面積（㎡）','建築年','間取り','建物の構造','取引価格（総額）','取引時期']

def write_csv(path,rows,fields=None):
    fields=fields or (list(rows[0]) if rows else [])
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

def value_type(value):
    if not value.strip(): return 'missing'
    try: number(value); return 'positive_numeric'
    except ValueError: return 'text_or_nonpositive'

def build(raw,output,latest='2026Q2'):
    if not re.fullmatch(r'\d{4}Q[1-4]',latest): raise ValueError('Invalid latest quarter')
    paths=sorted(raw.glob('*/*.csv'))
    if not paths: raise ValueError('No local CSV batches')
    if output.exists(): raise FileExistsError('Output already exists')
    output.mkdir(parents=True)
    all_rows=[]; feature_rows=[]; batches=[]; analyses=[]
    snapshots=[]
    for path in paths:
        quarter=path.parent.name
        if not re.fullmatch(r'\d{4}Q[1-4]',quarter) or not '2023Q1'<=quarter<=latest: continue
        quality=inspect_csv(path)
        with path.open(encoding=quality['encoding'],newline='') as f:
            raw_rows=list(csv.DictReader(f))
        if quality['malformed_rows']: raise ValueError(f'Malformed rows: {path}')
        period=f'{quarter[:4]}年第{quarter[-1]}四半期'
        if any(r.get('取引時期',r.get('取引時点'))!=period for r in raw_rows):
            raise ValueError(f'Batch period mismatch: {path}')
        selected=[r for r in raw_rows if r.get('価格情報区分')=='不動産取引価格情報'
                  and r.get('都道府県名')=='東京都' and r.get('種類')=='中古マンション等']
        if not selected: raise ValueError(f'No target transactions: {path}')
        report,clean=analyze(path,latest)
        analyses.append(report)
        by_line={r['source_row']:r for r in clean}
        numeric=[]
        for line,r in enumerate(raw_rows,2):
            if r.get('価格情報区分')!='不動産取引価格情報' or r.get('都道府県名')!='東京都' or r.get('種類')!='中古マンション等': continue
            out=dict(r,source_file=path.name,source_row=line,quarter=quarter,unit_price_jpy_m2=None,quality_flags='')
            if line in by_line:
                c=by_line[line]; out['unit_price_jpy_m2']=c['jpy_per_m2']
                if c['iqr_outlier']: out['quality_flags']='unit_price_iqr'
                numeric.append(c)
            else: out['quality_flags']='uncomputable_price_area_or_missing_municipality'
            all_rows.append(out)
        # Separate price and area IQR flags. No rows removed.
        for field in ('取引価格（総額）','面積（㎡）'):
            vals=[]
            for r in selected:
                try: vals.append(number(r[field]))
                except ValueError: pass
            stats=describe(vals)
            if vals:
                spread=stats['p75']-stats['p25']
                for r in all_rows[-len(selected):]:
                    try:
                        v=number(r[field])
                        if v<stats['p25']-1.5*spread or v>stats['p75']+1.5*spread:
                            r['quality_flags']+=';'+field+'_iqr'
                    except ValueError: r['quality_flags']+=';'+field+'_invalid'
        for field in FEATURES:
            values=[r.get(field,'') for r in selected]
            missing=sum(not v.strip() for v in values)
            feature_rows.append(dict(quarter=quarter,field=field,column_present=field in quality['columns'],
                n=len(values),missing=missing,missing_rate=missing/len(values),
                value_types=json.dumps(Counter(value_type(v) for v in values)),
                distinct_nonempty=len(set(v for v in values if v.strip()))))
        archive=path.with_suffix('.zip')
        # mtime retained from actual browser download; never use as publication date.
        acquired=datetime.fromtimestamp(archive.stat().st_mtime,timezone(timedelta(hours=9))).isoformat()
        manifest=dict(trade_quarter=quarter,acquired_at=acquired,published_at=None,
            first_observed_available_at=acquired,source='https://www.reinfolib.mlit.go.jp/realEstatePrices/',
            csv_sha256=quality['sha256'],zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
            raw_records=len(raw_rows),target_records=len(selected),raw_fields=quality['columns'],encoding=quality['encoding'],
            categories=dict(Counter(r.get('価格情報区分') for r in raw_rows)),
            status='downloaded; survey coverage and future revisions not guaranteed')
        mp=path.parent/'historical_manifest.json'
        if not mp.exists(): mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        snapshots.append(manifest)
        batches.append(dict(quarter=quarter,raw_records=len(raw_rows),target_records=len(selected),
            computable_unit_prices=len(numeric),encoding=quality['encoding'],fields=len(quality['columns']),
            same_schema_as_first=quality['columns']==snapshots[0]['raw_fields'],
            exact_duplicates=report['exact_duplicate_rows_flagged'],unit_price_outliers=report['iqr_outliers_retained']))
    if not all_rows: raise ValueError('No in-scope data')
    fields=list(dict.fromkeys(k for r in all_rows for k in r))
    write_csv(output/'merged_retained.csv',all_rows,fields)
    write_csv(output/'feature_availability.csv',feature_rows)
    write_csv(output/'batch_comparison.csv',batches)
    def grouped(keys):
        groups=defaultdict(list)
        for r in all_rows: groups[tuple(r[k] for k in keys)].append(r)
        result=[]
        for key,rows in sorted(groups.items()):
            values=[r['unit_price_jpy_m2'] for r in rows if r['unit_price_jpy_m2'] is not None]
            stats=describe(values)
            result.append(dict(zip(keys,key))|dict(sample_n=len(rows))|stats)
        return result
    quarterly=grouped(['quarter'])
    for name,keys in [('quarterly',['quarter']),('municipality',['市区町村名']),('quarter_municipality',['quarter','市区町村名'])]:
        write_csv(output/f'{name}.csv',grouped(keys))
    expected=[f'{y}Q{q}' for y in range(2023,int(latest[:4])+1) for q in range(1,5) if f'{y}Q{q}'<=latest]
    audit=audit_batches(paths)
    summary=dict(acquired=[b['quarter'] for b in batches],missing=[q for q in expected if q not in {b['quarter'] for b in batches}],
        total_target=len(all_rows),batches=batches,quarterly=quarterly,
        flags=dict(Counter(flag for r in all_rows for flag in r['quality_flags'].split(';') if flag)),
        cross_file_audit=audit,manifest_snapshots=snapshots,
        limitations='Downloaded quarters are not a census. Latest releases can be revised. Missing quarters are unknown, not zero. Current vintage is unavailable for historical as-of prediction before acquisition; publication dates unknown.')
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary

def plot(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary=json.loads((output/'summary.json').read_text(encoding='utf-8'))
    data={r['quarter']:r for r in summary['quarterly']}
    quarters=sorted(set(data)|set(summary['missing']))
    values=lambda key:[data[q][key]/10000 if q in data else float('nan') for q in quarters]
    fig,ax=plt.subplots(figsize=(12,5))
    ax.fill_between(quarters,values('p25'),values('p75'),alpha=.2,label='25th–75th percentile')
    ax.plot(quarters,values('median'),marker='o',label='Median')
    ax.set(ylabel='JPY 10,000 / m²',title='Tokyo used condominiums: observed transaction prices')
    ax.tick_params(axis='x',rotation=45); ax.legend(); ax.grid(alpha=.2)
    fig.text(.5,.015,'Unadjusted sample composition changes; NOT a house price index. Latest quarter subject to revisions.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,1)); fig.savefig(output/'quarterly_prices.png',dpi=160); plt.close(fig)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--raw',type=Path,default=Path('data/raw')); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--latest-quarter',default='2026Q2'); p.add_argument('--plot-only',action='store_true')
    a=p.parse_args()
    if a.plot_only: plot(a.output)
    else:
        summary=build(a.raw,a.output,a.latest_quarter)
        print(json.dumps({k:summary[k] for k in ('acquired','missing','total_target','flags','quarterly')},ensure_ascii=True))

if __name__=='__main__': main()
