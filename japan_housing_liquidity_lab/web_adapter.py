"""Session-safe UI adapters. No fitting, network acquisition or shared user cache."""
import hashlib
import csv
import io
import json
import math
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from . import competitiveness as prices, opportunity, location, listings


def home_query(city, town, station, walk, area, year, age, layout, structure, price_man, reference):
    reference=date.fromisoformat(str(reference))
    for name,value,positive in [('面積',area,True),('価格',price_man,True),('徒歩分',walk,False)]:
        if value is not None and (isinstance(value,bool) or not math.isfinite(float(value)) or float(value)<0 or (positive and float(value)==0)):
            raise ValueError(name+'を正しい単位の正数で入力してください。')
    if area is None or price_man is None or not city.strip() or not station.strip():
        raise ValueError('市区町村・駅・面積・価格は必須です。')
    if year is None and age is None: raise ValueError('建築年または築年数を入力してください。')
    if age is not None:
        if not float(age).is_integer() or not 0<=age<=150: raise ValueError('築年数は0～150の整数です。')
        converted=reference.year-int(age)
        if year is not None and year!=converted: raise ValueError('建築年と築年数が一致しません。')
        year=converted
    if not float(year).is_integer() or not 1800<=year<=reference.year: raise ValueError('建築年を確認してください。')
    return {'reference_date':reference.isoformat(),'asking_price_jpy':float(price_man)*10000,
            '市区町村名':city.strip(),'地区名':town.strip(),'最寄駅：名称':station.strip(),
            '最寄駅：距離（分）':'' if walk is None else str(walk),'面積（㎡）':str(area),
            '建築年':str(int(year))+'年','間取り':layout.strip(),'建物の構造':structure.strip()}


class SyntheticReference:
    """Invented arithmetic for UI demonstrations; not a trained or validated model."""
    def __init__(self, unit): self.unit=unit
    def predict(self, frame): return np.full(len(frame),np.log(self.unit))


def demo():
    rows=[]
    for i in range(120):
        area=60+i%5*5; unit=600000+i%20*20000
        rows.append(dict(record_id=f'SYNTHETIC-{i}',source_file='SYNTHETIC',source_row=str(i+1),
            quarter=['2025Q1','2025Q2','2025Q3','2025Q4','2026Q1','2026Q2'][i%6],市区町村名='架空区',地区名='架空町',
            **{'最寄駅：名称':'架空駅','最寄駅：距離（分）':str(5+i%11),'面積（㎡）':str(area),
               '建築年':'2005年','間取り':'2LDK','建物の構造':'RC','取引価格（総額）':str(area*unit),
               'unit_price_jpy_m2':str(unit)}))
    df=pd.DataFrame(rows)
    bundle=dict(models={k:SyntheticReference(v) for k,v in [('all_history_no_time',800000),('recent_no_time',850000),('history_with_time',900000)]},
        radii={k:.5 for k in ['all_history_no_time','recent_no_time','history_with_time']},
        protocol=dict(available_on='2026-11-08',version='SYNTHETIC-not-trained'),
        known_cities={'架空区'},latest_quarter='2026Q2',latest_period_end='2026-06-30',ranges={'area':[20,150]},
        pool=prices.make_pool(df,pd.to_numeric(df.unit_price_jpy_m2).to_numpy()))
    return bundle,df


def load_real(root, need):
    """Only operator-controlled trusted artifacts. Never accept uploaded pickle/joblib."""
    root=Path(root)
    if need=='location':
        path=root/'reports/task008-data/merged_retained.csv'; quality_path=path.with_name('quality.json')
        if not path.exists() or not quality_path.exists(): raise ValueError('地域分析用データがありません。合成デモを選ぶか管理者へ連絡してください。')
        quality=json.loads(quality_path.read_text(encoding='utf-8'))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=quality['combined_sha256']: raise ValueError('地域データの検証に失敗しました。')
        df=pd.read_csv(path,encoding='utf-8-sig',dtype=str,keep_default_na=False)
        if len(df)!=quality['total'] or sorted(df.quarter.unique())!=quality['quarters']: raise ValueError('地域データの件数・期間が一致しません。')
        return None,df,max(x['acquired_at'][:10] for x in quality['sources'])
    artifact=root/'reports/competitiveness-005-v2/reference.joblib'
    path=root/'reports/history-003-verified/merged_retained.csv'
    if not artifact.exists() or not path.exists(): raise ValueError('価格参照モデルまたは対応データがありません。合成デモを選ぶか管理者へ連絡してください。')
    bundle=joblib.load(artifact)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=bundle['protocol']['data_sha256']: raise ValueError('モデルとデータの版が一致しません。')
    return bundle,pd.read_csv(path,encoding='utf-8-sig',dtype=str,keep_default_na=False),bundle['protocol']['available_on']


def analyze_home(bundle, df, query, historical=False):
    if historical:
        result,_=opportunity.analyze(bundle,df,query)
        # Do not expose raw transaction rows or source paths to beta viewers.
        return result
    return prices.assess(bundle,query)


def budget(df, query, available):
    q=location.validate_query(query,set(df.quarter),available)
    f=location.prepare(df); period=f[f.quarter.between(q['history_start'],q['history_end'])]
    mask=location.budget_mask(period,q)
    selected=period.loc[mask]
    return dict(query=q,matched_n=int(mask.sum()),period_sample_n=len(period),
        regions=json.loads(location.table(period,['municipality'],mask).to_json(orient='records')),
        stations=json.loads(location.table(period,['municipality','station'],mask).to_json(orient='records')),
        layouts=selected.groupby(['municipality','layout']).size().rename('n').reset_index().to_dict('records'),
        commute=location.commute_result(q),limitations=location.LIMITATIONS)


def import_bytes(name, content, metadata=None):
    try:
        return _import_bytes(name,content,metadata)
    except (csv.Error, RecursionError, AttributeError) as exc:
        raise ValueError('入力ファイルの構造・文字列長を確認してください。') from exc


def _import_bytes(name, content, metadata=None):
    if len(content)>2_000_000 or (metadata and len(metadata)>100_000): raise ValueError('入力ファイルが大きすぎます（最大2MB）。')
    suffix=Path(name).suffix.lower()
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/('input'+suffix);p.write_bytes(content)
        meta=None
        if metadata is not None:
            meta=Path(tmp)/'metadata.json';meta.write_bytes(metadata)
        obj=listings.load_input(p,meta)
        if isinstance(obj,dict) and set(obj)=={'version','batches'}:
            if obj['version']!=listings.VERSION or not isinstance(obj['batches'],list): raise ValueError('履歴の形式が異なります。')
            return [listings.validate(b) for b in obj['batches']]
        return [listings.validate(obj)]


def append_batches(existing, incoming):
    # Reuse the canonical Task010 validation/idempotency/transition rules atomically.
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'journal.json'
        for b in [*existing,*incoming]: listings.ingest(p,b)
        return json.loads(p.read_text(encoding='utf-8'))['batches'] if p.exists() else []


def journal_zip(batches):
    with tempfile.TemporaryDirectory() as tmp:
        out=Path(tmp)/'output';listings.export(listings.replay(batches),out)
        # Spreadsheet-safe viewing CSVs; exact values remain in JSON for restoration.
        for p in out.glob('*.csv'):
            with p.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.reader(f))
            with p.open('w',encoding='utf-8-sig',newline='') as f:
                csv.writer(f).writerows([["'"+v if v.lstrip().startswith(('=','+','-','@')) or v.startswith(('\t','\r','\n')) else v for v in row] for row in rows])
        (out/'journal.json').write_text(json.dumps(dict(version=listings.VERSION,batches=batches),ensure_ascii=False),encoding='utf-8')
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
            for p in out.iterdir(): z.write(p,p.name)
        return buf.getvalue()


def manual_batch(source, listing_id, price_man, observed, status, evidence, rights_evidence,
                 synthetic=False, property_id='', match_evidence='', **attributes):
    if not evidence.strip() or not rights_evidence.strip(): raise ValueError('確認根拠と利用権利の根拠が必要です。')
    row=dict(listing_id=listing_id,evidence=evidence,status='present' if status=='missing' else status)
    if property_id.strip(): row.update(property_id=property_id.strip(),match_evidence=match_evidence.strip() or None)
    if status=='present': row.update(price_jpy=float(price_man)*10000,**attributes)
    body=dict(version=listings.VERSION,source=source,scope_id='individual:'+listing_id,
        scope=dict(coverage_type='tracked_listing_ids',definition='固定ID個別確認',listing_ids=[listing_id]),
        observed_at=observed,completeness='failed' if status=='failed' else 'partial' if status=='partial' else 'complete',
        check_evidence=evidence,data_kind='synthetic' if synthetic else 'real',
        rights=dict(basis='synthetic' if synthetic else 'manual_owned',evidence=rights_evidence,local_retention_allowed=True,url_retention_allowed=False),
        records=[] if status in {'missing','failed','partial'} else [row])
    body['batch_id']=hashlib.sha256(listings.canonical(body).encode()).hexdigest()
    return listings.validate(body)
