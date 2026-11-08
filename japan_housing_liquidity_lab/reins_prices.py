"""Quarterly price-band aggregates, independently checked against cached monthly counts."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from .reins import REGIONS, METRICS, ATTRIBUTION, months_between, shift_month, write_csv

BANDS = ("～1,000万円", "～2,000万円", "～3,000万円", "～4,000万円", "～5,000万円", "～7,000万円", "～10,000万円", "10,000万円～")


def parse_bands(text, metric, report_month):
    text = unicodedata.normalize("NFKC", text)
    if "首都圏・都県別価格帯別件数" not in text or METRICS[metric] not in text:
        raise ValueError("Unexpected price-band page heading")
    rows = []
    groups = re.split(r"[○〇]", text)[1:]
    for group in groups:
        region = group.splitlines()[0].strip()
        if region not in REGIONS:
            raise ValueError("Unknown price-band geography")
        header = next((line for line in group.splitlines() if "1,000" in line and "10,000" in line), "")
        if re.findall(r"[\d,]+", header) != ["1,000", "2,000", "3,000", "4,000", "5,000", "7,000", "10,000", "10,000"]:
            raise ValueError("Price-band thresholds changed")
        dates, counts, shares = [], [], []
        # Preserve independent row order; PDF engines can put the date before or after its counts.
        for line in group.splitlines()[1:]:
            match = re.search(r"(20\d{2})/(\d{2})(?:[~～](\d{2})|末)", line)
            if match:
                year, first, last = match.groups()
                if (metric == "inventory") != (last is None):
                    raise ValueError("Stock/flow period mismatch")
                end = f"{year}-{last or first}"
                start = end if last is None else f"{year}-{first}"
                if end[-2:] not in ("03", "06", "09", "12") or (last and shift_month(start, 2) != end):
                    raise ValueError("Not a full calendar quarter")
                dates.append((start, end))
                line = line[:match.start()] + line[match.end():]
            tokens = line.split()
            if len(tokens) == 9 and all(re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)", t) for t in tokens):
                counts.append([int(t.replace(",", "")) for t in tokens])
            percent = re.findall(r"\(\s*(\d+(?:\.\d+)?)\s*\)", line)
            if percent:
                if len(percent) != 9:
                    raise ValueError("Incomplete printed price-band shares")
                shares.append(list(map(float, percent)))
        expected = [shift_month(report_month, offset) for offset in (-12, -9, -6, -3, 0)]
        if len(counts) != 5 or len(shares) != 5 or [d[1] for d in dates] != expected:
            raise ValueError("Incomplete price-band periods/counts/shares")
        for (start, end), values, percentages in zip(dates, counts, shares):
            if sum(values[:8]) != values[8] or percentages[8] != 100:
                raise ValueError("Price-band sum does not equal published total")
            for band, value, percent in zip(BANDS, values[:8], percentages[:8]):
                calculated = value / values[8] * 100 if values[8] else None
                if calculated is not None and abs(calculated - percent) > .11:
                    raise ValueError("Printed price-band percentage mismatch")
                rows.append(dict(region=region, metric=metric, period_start=start, period_end=end,
                                 quarter=f"{end[:4]}Q{int(end[-2:]) // 3}",
                                 time_basis="quarter_end_stock" if metric == "inventory" else "quarterly_event_count",
                                 price_basis="reported_contract_price" if metric == "contracts" else "registered_price_not_contract_price",
                                 band_label=band, count=value, total=values[8], share_pct=calculated))
    if len(rows) != 200 or {r["region"] for r in rows} != set(REGIONS):
        raise ValueError("Incomplete price-band regions")
    for end in expected:
        for band in BANDS:
            values = {r["region"]: r["count"] for r in rows if r["period_end"] == end and r["band_label"] == band}
            if values["首都圏"] != sum(values[r] for r in REGIONS[1:]):
                raise ValueError("Price-band prefecture sum mismatch")
    return rows


def reconcile(rows, monthly):
    index = {(r["source_version"], r["region"], r["metric"], r["month"]): int(r["value"]) for r in monthly}
    checked, unavailable = 0, []
    unique = {(r["source_version"], r["region"], r["metric"], r["period_end"]): r for r in rows}
    for key, row in unique.items():
        months = months_between(row["period_start"], row["period_end"])
        cells = [index.get((key[0], key[1], key[2], m)) for m in months]
        if any(v is None for v in cells):
            unavailable.append(dict(source_version=key[0], region=key[1], metric=key[2], period_end=key[3]))
        elif sum(cells) != row["total"]:
            raise ValueError(f"Price-band total differs from same-vintage monthly data: {key}")
        else:
            checked += 1
    return dict(same_vintage_monthly_checks=checked, unavailable_monthly_checks=unavailable)


def build(monthly_output, raw, output, as_of=None):
    from datetime import date
    import pdfplumber
    from pypdf import PdfReader
    if output.exists():
        raise FileExistsError("Existing results will not be overwritten")
    if as_of:
        as_of = date.fromisoformat(as_of).isoformat()
    summary = json.loads((monthly_output / "summary.json").read_text(encoding="utf-8"))
    with (monthly_output / "source_vintages.csv").open(encoding="utf-8-sig", newline="") as f:
        monthly = list(csv.DictReader(f))
    rows = []
    for source in summary["sources"]:
        path = raw / source["source_file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["source_sha256"]:
            raise ValueError("Source changed since monthly analysis")
        reader = PdfReader(path)
        with pdfplumber.open(path) as pdf:
            for page, metric in zip((4, 5, 6), METRICS):
                first = parse_bands(reader.pages[page].extract_text(extraction_mode="layout"), metric, source["report_month"])
                second = parse_bands(pdf.pages[page].extract_text(), metric, source["report_month"])
                if first != second:
                    raise ValueError("Price-band PDF extractors disagree")
                for row in first:
                    row.update({k: source[k] for k in ("source_version", "source_file", "source_sha256", "source_url", "published_on", "acquired_on")})
                    row.update(source_page=page + 1, geography_level="capital_region" if row["region"] == "首都圏" else "prefecture", housing_type="中古マンション")
                rows.extend(first)
    quality = reconcile(rows, monthly)
    selected, overlaps, revisions = {}, 0, []
    for row in sorted(rows, key=lambda r: (r["published_on"], r["source_version"])):
        if as_of and row["published_on"] > as_of:
            continue
        if row["period_end"] < "2023-03":
            continue
        key = (row["region"], row["metric"], row["quarter"], row["band_label"])
        if key in selected:
            overlaps += 1
            if selected[key]["count"] != row["count"]:
                if selected[key]["published_on"] == row["published_on"]:
                    raise ValueError("Ambiguous same-date price-band revision")
                revisions.append(dict(key=list(key), old_count=selected[key]["count"], new_count=row["count"]))
        selected[key] = row
    if not selected:
        raise ValueError("No price-band data available by as-of")
    report = dict(attribution=ATTRIBUTION, raw_band_cells=len(rows), selected_band_cells=len(selected),
                  as_of=as_of, quarters=sorted({r["quarter"] for r in selected.values()}),
                  geography=list(REGIONS), tokyo_23_ward_price_bands_available=False,
                  overlapping_band_cells=overlaps, revisions=revisions, quality=quality,
                  dual_extractor_agreement=True,
                  limitations=["Official labels retained; exact threshold inclusion not inferred.",
                               "Contract/new counts cover whole quarters; inventory is quarter-end, never summed monthly.",
                               "Quarterly price bands must not be used as monthly seasonality observations.",
                               "Fixed nominal price bands can gain or lose properties as overall prices rise or fall; band migration is not evidence of demand-structure change.",
                               "The January 2025 REINS system correction may affect contract counts and cross-year price-band comparisons; post-change comparisons are not guaranteed free of reporting effects.",
                               "Contract-price and registered-price distributions describe different populations.",
                               "Tokyo prefecture bands cannot be attributed to 23 wards or individual stations.",
                               "No price-band sale probability, quality-adjusted price index or causal demand inference."])
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "source_vintages.csv", rows)
    write_csv(output / "quarterly_price_bands.csv", list(selected.values()))
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="REINS quarterly price bands; reuse existing monthly validation")
    parser.add_argument("--monthly-output", required=True, type=Path)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--as-of")
    args = parser.parse_args()
    try:
        report = build(args.monthly_output, args.raw, args.output, args.as_of)
        print(json.dumps({k: report[k] for k in ("raw_band_cells", "selected_band_cells", "quarters", "overlapping_band_cells", "limitations")}, indent=2))
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
