import argparse
import csv
import json
from pathlib import Path

from .mlit import inspect_csv
from .survival import conditional_risk, kaplan_meier, synthetic_listings


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Offline housing research starter")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Synthetic Kaplan-Meier baseline")
    demo.add_argument("--n", type=int, default=500)
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--output", type=Path, default=Path("reports/synthetic-baseline"))
    inspect = commands.add_parser("inspect-mlit", help="Inspect a local CSV only")
    inspect.add_argument("path", type=Path)
    inspect.add_argument("--encoding")
    args = parser.parse_args()
    try:
        if args.command == "inspect-mlit":
            print(json.dumps(inspect_csv(args.path, args.encoding), ensure_ascii=False, indent=2))
            return
        rows = synthetic_listings(args.n, args.seed)
        curve = kaplan_meier([r["duration_days"] for r in rows],
                             [r["event_observed"] for r in rows])
        risks = {}
        for days in (7, 30):
            try:
                risks[str(days)] = conditional_risk(curve, 0, days)
            except ValueError:
                risks[str(days)] = None
        summary = {"data_kind": "SYNTHETIC_ONLY", "seed": args.seed,
                   "n": args.n, "events": sum(r["event_observed"] for r in rows),
                   "censored": sum(not r["event_observed"] for r in rows),
                   "risk_from_day_zero": risks,
                   "limitations": "Pipeline demo, not real market predictions or causal price effects."}
        # A new output directory prevents accidental replacement of previous runs.
        args.output.mkdir(parents=True, exist_ok=False)
        write_csv(args.output / "synthetic_listings.csv", rows)
        write_csv(args.output / "km_curve.csv", curve)
        (args.output / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
    except (ValueError, OSError, LookupError, csv.Error) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
