"""Batch provenance and pre-merge comparison. No automatic record deletion."""
import csv
from collections import defaultdict
from pathlib import Path
from .mlit import inspect_csv

def audit_batches(paths):
    exact, possible = defaultdict(set), defaultdict(set)
    inspections = []
    hashes = defaultdict(list)
    for index, path in enumerate(paths):
        quality = inspect_csv(path)
        inspections.append(quality)
        hashes[quality['sha256']].append(str(path))
        with Path(path).open(encoding=quality['encoding'],newline='') as source:
            reader = csv.DictReader(source)
            for row in reader:
                if None in row or None in row.values():
                    continue
                if '取引時期' in row:
                    row['取引時点'] = row.pop('取引時期')
                # Compare all labeled fields independent of column order.
                exact[tuple(sorted(row.items()))].add(index)
                key = tuple(row.get(k,'') for k in
                    ('都道府県名','市区町村名','地区名','種類','取引時点','取引価格（総額）','面積（㎡）'))
                possible[key].add(index)
    return dict(files=inspections,
        identical_files=[v for v in hashes.values() if len(v)>1],
        exact_cross_file_signatures=sum(len(v)>1 for v in exact.values()),
        possible_cross_file_signatures=sum(len(v)>1 for v in possible.values()),
        policy='No merge or deletion: identical rounded rows may be distinct real trades; candidate counts overlap exact counts')
