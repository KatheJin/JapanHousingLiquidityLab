"""Local Tokyo transaction EDA; no network operations."""
import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import re
from statistics import median
import unicodedata
from .mlit import inspect_csv

FIELDS = ['種類', '都道府県名', '市区町村名', '取引価格（総額）', '面積（㎡）', '取引時点']

def number(value):
    value = unicodedata.normalize('NFKC', value).strip().replace(',', '')
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value):
        raise ValueError('missing, bounded or nonnumeric value')
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError('nonpositive or nonfinite value')
    return result

def quantile(values, fraction):
    values = sorted(values)
    index = (len(values)-1)*fraction
    low = int(index)
    return values[low] + (values[min(low+1,len(values)-1)]-values[low])*(index-low)

def describe(values):
    if not values:
        return {'n': 0}
    return dict(n=len(values), min=min(values), p25=quantile(values,.25),
                median=median(values), p75=quantile(values,.75), max=max(values))

def analyze(path, latest_quarter=None):
    if latest_quarter is not None and not re.fullmatch(r'[0-9]{4}Q[1-4]',latest_quarter):
        raise ValueError('latest_quarter must be YYYYQ1..4')
    quality = inspect_csv(path)
    aliases = {'取引時期': '取引時点', '面積（平方メートル）': '面積（㎡）', '面積(m²)': '面積（㎡）'}
    headers = [aliases.get(h,h) for h in quality['columns']]
    if len(set(headers)) != len(headers):
        raise ValueError('ambiguous area columns')
    missing = set(FIELDS)-set(headers)
    if missing:
        raise ValueError('Missing required columns: '+', '.join(sorted(missing)))
    rejected, accepted, seen = Counter(), [], set()
    duplicates = 0
    with Path(path).open(encoding=quality['encoding'], newline='') as source:
        reader = csv.reader(source, strict=True)
        next(reader)
        for line, values in enumerate(reader, 2):
            if not values:
                continue
            if len(values) != len(headers):
                rejected['malformed_width'] += 1
                continue
            identity = tuple(values)
            duplicates += identity in seen
            seen.add(identity)  # Flag only: rounded records may represent distinct transactions.
            row = dict(zip(headers, values))
            if row['都道府県名'] != '東京都' or row['種類'] != '中古マンション等':
                rejected['outside_region_or_type'] += 1
                continue
            if '価格情報区分' in row and row['価格情報区分'] != '不動産取引価格情報':
                rejected['other_price_category'] += 1
                continue
            period = re.fullmatch(r'([0-9]{4})年第([1-4])四半期', unicodedata.normalize('NFKC',row['取引時点']).strip())
            if not period or int(period[1]) < 2023 or (latest_quarter and f'{period[1]}Q{period[2]}' > latest_quarter):
                rejected['outside_period_or_invalid_period'] += 1
                continue
            if not row['市区町村名'].strip():
                rejected['missing_municipality'] += 1
                continue
            try:
                price, area = number(row['取引価格（総額）']), number(row['面積（㎡）'])
            except ValueError:
                rejected['invalid_price_or_area'] += 1
                continue
            accepted.append(dict(source_row=line, municipality=row['市区町村名'],
                quarter=f'{period[1]}Q{period[2]}', price_jpy=price, area_m2=area,
                jpy_per_m2=price/area))
    values = [r['jpy_per_m2'] for r in accepted]
    overall = describe(values)
    outliers = 0
    if values:
        spread = overall['p75']-overall['p25']
        for row in accepted:
            row['iqr_outlier'] = row['jpy_per_m2'] < overall['p25']-1.5*spread or row['jpy_per_m2'] > overall['p75']+1.5*spread
            outliers += row['iqr_outlier']
    groups = {}
    for field in ('municipality','quarter'):
        grouped = defaultdict(list)
        for row in accepted:
            grouped[row[field]].append(row['jpy_per_m2'])
        groups[field] = {k:describe(v) for k,v in sorted(grouped.items())}
    return dict(input=quality, accepted=len(accepted), rejected=dict(rejected),
        exact_duplicate_rows_flagged=duplicates, iqr_outliers_retained=outliers,
        price_category_verified='価格情報区分' in headers,
        overall_jpy_per_m2=overall, distributions=groups,
        latest_verified_quarter=latest_quarter,
        missing_quarters=([f'{y}Q{q}' for y in range(2023,int(latest_quarter[:4])+1) for q in range(1,5)
                          if f'{y}Q{q}' <= latest_quarter and f'{y}Q{q}' not in groups['quarter']] if latest_quarter else []),
        missing_quarters_meaning='not observed in this file; never zero transactions'), accepted

def main():
    parser=argparse.ArgumentParser(description='Local transaction CSV EDA')
    parser.add_argument('csv',type=Path)
    parser.add_argument('--latest-quarter', help='Officially verified latest quarter, YYYYQn')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        summary, rows=analyze(args.csv, args.latest_quarter)
        args.output.mkdir(parents=True,exist_ok=False)
        (args.output/'quality_and_eda.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        if rows:
            with (args.output/'cleaned.csv').open('w',encoding='utf-8-sig',newline='') as target:
                writer=csv.DictWriter(target,fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
        for group, stats in summary['distributions'].items():
            with (args.output/f'{group}.csv').open('w',encoding='utf-8-sig',newline='') as target:
                writer=csv.writer(target); writer.writerow([group,'n','min','p25','median','p75','max'])
                for key, values in stats.items():
                    writer.writerow([key]+list(values.values()))
        print(json.dumps(summary,ensure_ascii=False,indent=2))
    except (ValueError,OSError,csv.Error) as exc:
        parser.exit(2,f'Error: {exc}\n')

if __name__=='__main__':
    main()
