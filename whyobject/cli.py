import argparse
import json
import sys

from .core import apply_fix, diagnose, format_report, load_csv


def main():
    p = argparse.ArgumentParser(prog="whyobject", description="Find the exact cells that stop pandas from reading a column as numbers or dates.")
    p.add_argument("path", help="CSV file to check")
    p.add_argument("--fix", metavar="OUT", help="write a cleaned CSV (numbers and dates converted) to this path")
    p.add_argument("--json", action="store_true", help="print the diagnosis as JSON")
    a = p.parse_args()

    df = load_csv(a.path)
    diag = diagnose(df)
    print(json.dumps(diag, indent=2, default=str) if a.json else format_report(diag, len(df)))
    if a.fix:
        fixed, stats = apply_fix(df, diag)
        fixed.to_csv(a.fix, index=False)
        print(f"\nCleaned copy saved to {a.fix}", file=sys.stderr)
        for s in stats:
            print(f"  {s['column']}: {s['unreadable_set_to_missing']} unreadable cell(s) set to missing", file=sys.stderr)
    sys.exit(1 if diag else 0)  # non-zero exit lets you use it in CI


if __name__ == "__main__":
    main()
