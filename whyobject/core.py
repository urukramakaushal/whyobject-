"""whyobject: find the exact cells that stop pandas from reading a column as numbers or dates."""
import io
import math
import re
import warnings
from collections import Counter

import pandas as pd

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")  # latin-1 never fails, so it goes last

# Strings pandas turns into NaN on its own, so they do not stop a column from being numeric.
PANDAS_NA = {"", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND",
             "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null"}
# Strings people use to mean "no value".
MISSING_WORDS = {"-", "--", "---", "?", "??", "nil", "missing", "unknown", "not available",
                 "n.a.", "n.a", "tbd", "none", "na", "n/a", "null", "nan", "#n/a"}

_CUR = r"(?:[$₹€£¥]|rs\.?|inr|usd|eur|gbp)"
_CURRENCY = re.compile(rf"^{_CUR}\s*|\s*{_CUR}$", re.I)
_THOUSANDS = re.compile(r"^[+-]?\d{1,3}(,\d{2,3})+(\.\d+)?$")  # 1,200  1,200,000  1,20,000
_DEC_COMMA = re.compile(r"^[+-]?\d+,\d{1,2}$")                   # 3,5
_UNIT = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*([A-Za-z/²³°]+)$")  # 12kg  5 km


def _to_float(t):
    if "_" in t:
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def classify_number(raw):
    """Return (value, category). value is None when the text cannot be read as a number."""
    t = raw.strip()
    if t == "":
        return None, "empty"
    if t.lower() in MISSING_WORDS:
        return None, "missing_token"
    t = t.replace("−", "-")
    if t.startswith("(") and t.endswith(")"):
        v, _ = classify_number(t[1:-1])
        return ((-abs(v), "parentheses_negative") if v is not None else (None, "junk"))
    cat = "ok"
    stripped = _CURRENCY.sub("", t).strip()
    if stripped != t:
        t, cat = stripped, "currency_symbol"
    if t.endswith("%"):
        t, cat = t[:-1].strip(), "percent_sign"
    v = _to_float(t)
    if v is not None:
        return v, cat
    if _THOUSANDS.match(t):
        return float(t.replace(",", "")), (cat if cat != "ok" else "thousands_separator")
    if _DEC_COMMA.match(t):
        return float(t.replace(",", ".")), "decimal_comma"
    m = _UNIT.match(t)
    if m:
        return float(m.group(1)), "unit_suffix"
    return None, "junk"


def to_numeric(series):
    """Clean-convert a text Series to floats; unreadable cells become NaN."""
    vals = [None if pd.isna(v) else classify_number(str(v))[0] for v in series]
    return pd.Series(vals, index=series.index, dtype="float64")


def to_datetime(series):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return pd.to_datetime(series, errors="coerce", format="mixed")
        except (TypeError, ValueError):
            return pd.to_datetime(series, errors="coerce")


def load_csv(source):
    """Read a CSV (path or raw bytes) as text, trying common encodings."""
    if isinstance(source, bytes):
        raw = source
    else:
        with open(source, "rb") as f:
            raw = f.read()
    last = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, encoding=enc)
        except UnicodeDecodeError as e:
            last = e
    raise last


def _examples(items, k=3):
    return [{"row": r, "value": v[:30]} for r, v in items[:k]]


def _numeric_entry(col, parsed, usable):
    groups = {}
    for r, v, val, cat in parsed:
        if cat in ("ok", "empty") or v in PANDAS_NA:
            continue
        groups.setdefault(cat, []).append((r, v))
    if not groups:
        return None
    share = sum(p[2] is not None for p in usable) / len(usable)
    return {
        "column": col, "intent": "numeric", "share": round(share, 3),
        "breakers": {c: {"count": len(x), "examples": _examples(x)} for c, x in groups.items()},
        "fix": f"from whyobject import to_numeric\ndf[{col!r}] = to_numeric(df[{col!r}])",
    }


def _shape(v):
    return re.sub(r"\d", "9", re.sub(r"[A-Za-z]", "a", v))


def _date_entry(col, cells):
    vals = [(r, v) for r, v in cells if v not in PANDAS_NA]
    if not vals:
        return None
    if sum(any(ch.isdigit() for ch in v) for _, v in vals) / len(vals) < 0.6:
        return None  # text such as month names, not dates
    ok = to_datetime(pd.Series([v for _, v in vals])).notna().tolist()
    share = sum(ok) / len(vals)
    if share < 0.6:
        return None
    bad = [(r, v) for (r, v), good in zip(vals, ok) if not good]
    groups = {}
    for r, v in bad:
        groups.setdefault("missing_token" if v.strip().lower() in MISSING_WORDS else "unparseable", []).append((r, v))
    shapes = Counter(_shape(v) for (r, v), good in zip(vals, ok) if good)
    example = {}
    for (r, v), good in zip(vals, ok):
        if good:
            example.setdefault(_shape(v), v)
    mixed = []
    if len(shapes) > 1 and shapes.most_common(2)[1][1] / sum(shapes.values()) >= 0.05:
        mixed = [{"pattern": s, "count": n, "example": example[s][:30]} for s, n in shapes.most_common(3)]
    if not groups and not mixed:
        return None
    return {
        "column": col, "intent": "date", "share": round(share, 3),
        "breakers": {c: {"count": len(x), "examples": _examples(x)} for c, x in groups.items()},
        "mixed_formats": mixed,
        "fix": f'df[{col!r}] = pd.to_datetime(df[{col!r}], errors="coerce", format="mixed")',
    }


def diagnose(df):
    """Return one entry per column that has cells blocking numeric or date parsing."""
    results = []
    for col in df.columns:
        cells = [(i + 2, str(v)) for i, v in enumerate(df[col]) if str(v).strip() != ""]  # i+2 = Excel row
        if not cells:
            continue
        parsed = [(r, v, *classify_number(v)) for r, v in cells]
        usable = [p for p in parsed if p[3] != "missing_token"]
        if usable and sum(p[2] is not None for p in usable) / len(usable) >= 0.6:
            res = _numeric_entry(col, parsed, usable)
        else:
            res = _date_entry(col, cells)
        if res:
            results.append(res)
    return results


def apply_fix(df, diagnosis):
    """Convert every diagnosed column. Returns (fixed_df, stats)."""
    out, stats = df.copy(), []
    for d in diagnosis:
        col = d["column"]
        if d["intent"] == "numeric":
            out[col] = to_numeric(df[col])
            unreadable = sum(classify_number(str(v))[1] == "junk" for v in df[col])
        else:
            s = df[col].astype(str)
            s = s.where(s.str.strip() != "")
            out[col] = to_datetime(s)
            real = s.notna() & ~s.isin(PANDAS_NA) & ~s.str.strip().str.lower().isin(MISSING_WORDS)
            unreadable = int((real & out[col].isna()).sum())
        stats.append({"column": col, "intent": d["intent"], "unreadable_set_to_missing": int(unreadable)})
    return out, stats


def format_report(diag, rows):
    if not diag:
        return f"No problem cells found in {rows} rows. Numeric and date columns look clean."
    lines = [f"Found {len(diag)} problem column(s) in {rows} rows "
             "(row numbers match Excel/Sheets, header = row 1).", ""]
    for d in diag:
        lines.append(f"● {d['column']}  looks {d['intent']} ({d['share']:.0%} of values)")
        if d["intent"] == "numeric":
            lines.append("  pandas reads it as text because of:")
        elif d["breakers"]:
            lines.append("  these cells will not parse as dates:")
        for cat, info in sorted(d["breakers"].items(), key=lambda kv: -kv[1]["count"]):
            ex = ", ".join(f"row {e['row']}: {e['value']!r}" for e in info["examples"])
            lines.append(f"    {cat:<20}{info['count']:>5} cell(s)   e.g. {ex}")
        if d.get("mixed_formats"):
            lines.append("  mixed date formats (day/month order may be ambiguous):")
            for m in d["mixed_formats"]:
                lines.append(f"    {m['pattern']:<20}{m['count']:>5} cell(s)   e.g. {m['example']!r}")
        lines.append("  fix:")
        lines += ["    " + ln for ln in d["fix"].splitlines()]
        lines.append("")
    return "\n".join(lines).rstrip()
