"""Independent REINS monthly aggregates; no listing probabilities or MLIT joins.

Offline, fail-closed importer for condominium pages 2--4, 8, 12 and 16.
Both PDF engines must agree. Preserve source vintages before selecting data.
"""
import argparse
import calendar
import csv
from datetime import date
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import statistics
import unicodedata

REGIONS = ("首都圏", "東京都", "埼玉県", "千葉県", "神奈川県")
TOKYO_DISTRICTS = ("東京都 都心3区", "東京都 城東地区", "東京都 城南地区", "東京都 城西地区", "東京都 城北地区")
WARD_GROUPS = dict(zip(TOKYO_DISTRICTS, (
    ("千代田区", "中央区", "港区"),
    ("台東区", "江東区", "江戸川区", "墨田区", "葛飾区", "足立区", "荒川区"),
    ("品川区", "大田区", "目黒区", "世田谷区"),
    ("新宿区", "渋谷区", "杉並区", "中野区"),
    ("文京区", "豊島区", "北区", "板橋区", "練馬区"),
)))
ALL_REGIONS = REGIONS + TOKYO_DISTRICTS + ("東京23区（5地区合算）",)
METRICS = {"contracts": "成約状況", "new_registrations": "新規登録状況", "inventory": "在庫状況"}
BREAK = "2025-01"
ATTRIBUTION = "Created by JapanHousingLiquidityLab based on East Japan REINS Market Watch."


def shift_month(month, offset):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError(f"Invalid month: {month}")
    year, mon = map(int, month.split("-"))
    value = year * 12 + mon - 1 + offset
    return f"{value // 12:04d}-{value % 12 + 1:02d}"


def months_between(start, end):
    shift_month(start, 0)
    shift_month(end, 0)
    if start > end:
        raise ValueError("Start month must not follow end month")
    result = []
    while start <= end:
        result.append(start)
        start = shift_month(start, 1)
    return result


def geography(region):
    if region == "首都圏":
        return "capital_region"
    if region in REGIONS:
        return "prefecture"
    return "derived_23_wards" if region == ALL_REGIONS[-1] else "official_ward_group"


def parse_table(text, metric, report_month, regions=REGIONS):
    """Read only the count and its printed YoY; reject changed table schemas."""
    text = unicodedata.normalize("NFKC", text)
    if "中古マンションレポート" not in text or METRICS[metric] not in text:
        raise ValueError(f"Unexpected page heading for {metric}")
    if regions == TOKYO_DISTRICTS:
        for group in re.split(r"[○〇]", text)[1:]:
            header = re.match(r"([^()]+)\(([^)]+)\)", group)
            if not header:
                raise ValueError("Missing official ward membership")
            label = re.sub(r"\s+", " ", header[1]).strip()
            members = re.sub(r"\s+", "", header[2]).split("、")
            if label not in WARD_GROUPS or set(members) != set(WARD_GROUPS[label]) or len(members) != len(WARD_GROUPS[label]):
                raise ValueError("Official ward membership changed; review before summing 23 wards")
    rows, region, year = [], None, None
    pattern = re.compile(r"^(?:(\d{2})/)?(\d{2})\s+([\d,]+)\s+(-?\d+(?:\.\d+)?|[-ー−])(?:\s|$)")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("○", "〇")):
            region, year = re.split(r"\s*\(", line[1:].strip())[0].strip(), None
            region = re.sub(r"\s+", " ", region)
            if region not in regions:
                raise ValueError(f"Unexpected region: {region}")
            continue
        match = pattern.match(line)
        if not match or region is None:
            continue
        yy, mm, count, yoy = match.groups()
        if yy:
            year = 2000 + int(yy)
        if year is None:
            raise ValueError("Missing year context")
        month = f"{year:04d}-{mm}"
        shift_month(month, 0)
        if not re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)", count):
            raise ValueError("Malformed count")
        rows.append(dict(month=month, region=region, metric=metric,
                         value=int(count.replace(",", "")),
                         printed_yoy_pct=float(yoy) if re.fullmatch(r"-?\d+(?:\.\d+)?", yoy) else None))
    expected = {(r, m) for r in regions for m in months_between(shift_month(report_month, -12), report_month)}
    keys = [(r["region"], r["month"]) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError(f"Incomplete/duplicate {metric} table; expected 65 cells, got {len(keys)}")
    index = {(r["region"], r["month"]): r["value"] for r in rows}
    for month in months_between(shift_month(report_month, -12), report_month):
        if regions == REGIONS and index["首都圏", month] != sum(index[r, month] for r in REGIONS[1:]):
            raise ValueError(f"Prefecture sum does not match capital total: {month}")
    return sorted(rows, key=lambda r: (r["region"], r["month"]))


def read_pdf(path, acquired_on):
    import pdfplumber
    from pypdf import PdfReader
    acquired_on = date.fromisoformat(acquired_on).isoformat()
    name = re.fullmatch(r"MW_(\d{4})(\d{2})data\.pdf", path.name)
    if not name:
        raise ValueError(f"Unsupported source filename: {path.name}")
    report_month = f"{name[1]}-{name[2]}"
    shift_month(report_month, 0)
    reader = PdfReader(path)
    cover = unicodedata.normalize("NFKC", reader.pages[0].extract_text())
    cover_month = re.search(r"(20\d{2})\s*\([^)]*\)\s*年\s*(\d{1,2})\s*月度", cover)
    if not cover_month or f"{cover_month[1]}-{int(cover_month[2]):02d}" != report_month:
        raise ValueError("Cover reporting month differs from filename")
    dates = re.findall(r"(20\d{2})\s*\([^)]*\)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", cover)
    if len(dates) != 1:
        raise ValueError("Cannot uniquely identify publication date on cover")
    published = date(*map(int, dates[0])).isoformat()
    if published <= report_month + "-" + str(calendar.monthrange(int(name[1]), int(name[2]))[1]) or published > acquired_on:
        raise ValueError("Invalid publication/acquisition chronology")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = dict(source_file=path.name, source_sha256=digest,
                    source_url=f"https://www.reins.or.jp/pdf/trend/mw/{path.name}",
                    report_month=report_month, published_on=published,
                    acquired_on=acquired_on, housing_type="中古マンション",
                    source_version=f"{path.stem}:{digest[:12]}")
    all_rows = []
    with pdfplumber.open(path) as pdf:
        pages = [(i, metric, REGIONS) for i, metric in enumerate(METRICS, start=1)]
        pages += [(i, metric, TOKYO_DISTRICTS) for i, metric in zip((7, 11, 15), METRICS)]
        for page_index, metric, regions in pages:
            first = parse_table(reader.pages[page_index].extract_text(extraction_mode="layout"), metric, report_month, regions)
            second = parse_table(pdf.pages[page_index].extract_text(), metric, report_month, regions)
            if first != second:
                raise ValueError(f"PDF extractors disagree: {path.name}, page {page_index + 1}")
            for row in first:
                row.update(metadata, source_page=page_index + 1,
                           geography_level=geography(row["region"]), derivation="direct_official_count")
            all_rows.extend(first)
            if regions == TOKYO_DISTRICTS:
                for month in months_between(shift_month(report_month, -12), report_month):
                    components = [r for r in first if r["month"] == month]
                    derived = dict(components[0], region=ALL_REGIONS[-1], geography_level="derived_23_wards",
                                   value=sum(r["value"] for r in components), printed_yoy_pct=None,
                                   derivation="sum of five disjoint official Tokyo ward groups (3+7+4+4+5 wards)")
                    tokyo = next(r["value"] for r in all_rows if r["region"] == "東京都" and r["month"] == month and r["metric"] == metric)
                    if derived["value"] > tokyo:
                        raise ValueError("Derived 23-ward count exceeds Tokyo prefecture")
                    all_rows.append(derived)
    return all_rows, dict(metadata, count_cells=len(all_rows), dual_extractor_agreement=True,
                          direct_count_cells=390, derived_count_cells=39, prefecture_sum_checks=39)


def select_vintage(rows, as_of=None):
    if as_of:
        as_of = date.fromisoformat(as_of).isoformat()
    selected, revisions, overlaps = {}, [], 0
    for row in sorted(rows, key=lambda r: (r["published_on"], r["source_version"])):
        if as_of and row["published_on"] > as_of:
            continue
        key = (row["region"], row["month"], row["metric"])
        previous = selected.get(key)
        if previous:
            overlaps += 1
            if previous["value"] != row["value"]:
                if previous["published_on"] == row["published_on"]:
                    raise ValueError("Conflicting values with same publication date")
                revisions.append(dict(region=key[0], month=key[1], metric=key[2],
                                      old_value=previous["value"], new_value=row["value"],
                                      old_source=previous["source_version"], new_source=row["source_version"]))
        selected[key] = row
    return list(selected.values()), revisions, overlaps


def analyze(rows, start, end):
    months = months_between(start, end)
    index = {(r["region"], r["month"], r["metric"]): r for r in rows}
    if len(index) != len(rows):
        raise ValueError("Select source vintages before analysis")
    output, missing, yoy_checks, yoy_differences = [], [], 0, []
    for region in ALL_REGIONS:
        for month in months:
            entry = dict(region=region, month=month, geography_level=geography(region),
                         housing_type="中古マンション")
            for metric in METRICS:
                row = index.get((region, month, metric))
                entry[metric] = row["value"] if row else None
                entry[metric + "_source_version"] = row["source_version"] if row else None
                entry[metric + "_published_on"] = row["published_on"] if row else None
                if row is None:
                    missing.append(dict(region=region, month=month, metric=metric))
                for lag, label in ((1, "mom"), (12, "yoy")):
                    prior_month = shift_month(month, -lag)
                    prior = index.get((region, prior_month, metric))
                    change = (row["value"] / prior["value"] - 1) * 100 if row and prior and prior["value"] else None
                    crossed = metric == "contracts" and prior_month < BREAK <= month
                    entry[f"{metric}_{label}_raw_pct"] = change
                    entry[f"{metric}_{label}_crosses_2025_break"] = crossed
                    entry[f"{metric}_{label}_comparable_pct"] = None if crossed else change
                    if label == "yoy" and change is not None and row["printed_yoy_pct"] is not None:
                        yoy_checks += 1
                        if abs(change - row["printed_yoy_pct"]) > .11:
                            yoy_differences.append(dict(region=region, month=month, metric=metric,
                                                        calculated=change, printed=row["printed_yoy_pct"]))
            contracts = entry["contracts"]
            for numerator in ("new_registrations", "inventory"):
                entry[numerator + "_to_contracts_descriptive_ratio"] = entry[numerator] / contracts if contracts and entry[numerator] is not None else None
            output.append(entry)
    profiles, seasonality = [], []
    years = sorted({m[:4] for m in months})
    for region in ALL_REGIONS:
        for metric in METRICS:
            for year in years:
                values = [index.get((region, f"{year}-{m:02d}", metric)) for m in range(1, 13)]
                # Partial requested years and incomplete source years never enter annual normalization.
                if any(v is None or v["month"] not in months for v in values):
                    continue
                mean = statistics.mean(v["value"] for v in values)
                if mean == 0:
                    continue
                for m, v in enumerate(values, 1):
                    profiles.append(dict(region=region, metric=metric, year=int(year), month_of_year=m,
                                         regime="pre_2025" if year < "2025" else "post_2025",
                                         annual_mean_normalized=100 * v["value"] / mean))
            for regime in ("pre_2025", "post_2025"):
                for m in range(1, 13):
                    samples = [p["annual_mean_normalized"] for p in profiles if p["region"] == region and p["metric"] == metric and p["regime"] == regime and p["month_of_year"] == m]
                    if samples:
                        seasonality.append(dict(region=region, metric=metric, regime=regime, month_of_year=m,
                                                complete_years=len(samples), mean_index=statistics.mean(samples),
                                                min_index=min(samples), max_index=max(samples),
                                                evidence="single_year_not_seasonality" if len(samples) < 2 else "exploratory_only"))
    return dict(monthly=output, annual_profiles=profiles, seasonality=seasonality,
                quality=dict(missing_cells=missing, printed_yoy_checks=yoy_checks,
                             printed_yoy_differences=yoy_differences))


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_results(result, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    for ax, metric in zip(axes, METRICS):
        for region, label in (("首都圏", "Greater Tokyo"), ("東京都", "Tokyo prefecture")):
            data = [r for r in result["monthly"] if r["region"] == region]
            ax.plot([date.fromisoformat(r["month"] + "-01") for r in data], [r[metric] if r[metric] is not None else float("nan") for r in data], label=label)
        ax.axvline(date(2025, 1, 1), linestyle="--", color="gray", label="2025 reporting change")
        ax.set_ylabel(metric.replace("_", " ") + " (count)")
        ax.grid(alpha=.2)
    axes[0].legend()
    fig.suptitle("REINS monthly activity | contract reports, registration events, month-end stock")
    fig.text(.02, .01, ATTRIBUTION + "\nDescriptive aggregates; not probabilities or sale durations.", fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, .97))
    fig.savefig(output / "activity.png", dpi=140)
    plt.close(fig)
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), sharex=True)
    for i, metric in enumerate(METRICS):
        for j, (region, label) in enumerate((("東京都", "Tokyo prefecture"), ("首都圏", "Greater Tokyo"))):
            ax = axes[i, j]
            for year in sorted({r["year"] for r in result["annual_profiles"]}):
                data = [r for r in result["annual_profiles"] if r["region"] == region and r["metric"] == metric and r["year"] == year]
                if data:
                    ax.plot([r["month_of_year"] for r in data], [r["annual_mean_normalized"] for r in data], label=str(year), linestyle="--" if year >= 2025 else "-")
            ax.set_title(label + " / " + metric.replace("_", " "))
            ax.axhline(100, color="gray", linewidth=.5)
            ax.set_xticks(range(1, 13))
            ax.grid(alpha=.2)
    axes[0, 0].legend()
    fig.suptitle("Within-year profiles (annual mean = 100); NOT seasonally adjusted series")
    fig.text(.02, .01, ATTRIBUTION + "\n2025 is a separate reporting regime; incomplete years excluded. Trends remain in these profiles.", fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, .97))
    fig.savefig(output / "seasonality.png", dpi=140)
    plt.close(fig)


def build(paths, output, acquired_on, start="2023-01", end=None, as_of=None, plots=False):
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    if not paths:
        raise ValueError("At least one PDF is required")
    rows, sources = [], []
    for path in paths:
        values, source = read_pdf(path, acquired_on)
        rows.extend(values)
        sources.append(source)
    if len({s["source_file"] for s in sources}) != len(sources):
        raise ValueError("Duplicate source filename")
    selected, revisions, overlaps = select_vintage(rows, as_of)
    if not selected:
        raise ValueError("No source vintage available at the requested as-of date")
    end = end or max(r["month"] for r in selected)
    result = analyze(selected, start, end)
    summary = dict(data_kind="REINS_MONTHLY_AGGREGATES_NOT_MLIT", start=start, end=end,
                   as_of=as_of, vintage_policy="latest supplied publication on/before as_of; otherwise latest supplied",
                   original_monthly_release_dates_known=False,
                   raw_count_cells=len(rows), selected_count_cells=sum(start <= r["month"] <= end for r in selected),
                   regions=list(ALL_REGIONS), metrics=list(METRICS), sources=sources,
                   overlapping_cells=overlaps, revisions=revisions, quality=result["quality"],
                   extractor_versions={p: importlib.metadata.version(p) for p in ("pypdf", "pdfplumber")},
                   attribution=ATTRIBUTION,
                   limitations=["Contracts are reports received, not actual contract dates.",
                                "New registrations are events, not unique newly marketed homes.",
                                "Inventory is month-end stock and must not be summed over time.",
                                "2025-01 system correction can affect contract reporting comparability; post-change comparisons are not guaranteed free of reporting effects.",
                                "2022-01 new registration definition changed; pre-2022 not imported.",
                                "No station-level inference, sale probabilities or future opportunity forecasts.",
                                "Annual mean normalization does not remove within-year trend or calendar effects.",
                                "Snapshot publication dates are conservative availability bounds, not first releases."])
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "source_vintages.csv", rows)
    write_csv(output / "selected_counts.csv", [r for r in selected if start <= r["month"] <= end])
    for name in ("monthly", "annual_profiles", "seasonality"):
        write_csv(output / f"{name}.csv", result[name])
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if plots:
        plot_results(result, output)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Offline REINS monthly PDF analysis (independent of MLIT)")
    parser.add_argument("pdfs", nargs="+", type=Path)
    parser.add_argument("--acquired-on", required=True, help="Actual local acquisition date, YYYY-MM-DD")
    parser.add_argument("--start", default="2023-01")
    parser.add_argument("--end")
    parser.add_argument("--as-of", help="Conservative source publication cutoff, YYYY-MM-DD")
    parser.add_argument("--output", required=True, type=Path, help="New directory; existing results never overwritten")
    parser.add_argument("--plots", action="store_true")
    args = parser.parse_args()
    try:
        result = build(args.pdfs, args.output, args.acquired_on, args.start, args.end, args.as_of, args.plots)
        print(json.dumps({k: result[k] for k in ("start", "end", "raw_count_cells", "selected_count_cells", "overlapping_cells", "quality", "limitations")}, ensure_ascii=False, indent=2))
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
