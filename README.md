# whyobject 🔍

**Why is my numeric column loading as `object`?**

`whyobject` finds the exact cells that stop pandas from reading a column as numbers or dates, groups them by cause, and fixes them.

```
$ whyobject messy.csv

Found 3 problem column(s) in 40 rows (row numbers match Excel/Sheets, header = row 1).

● price  looks numeric (87% of values)
  pandas reads it as text because of:
    junk                    5 cell(s)   e.g. row 20: 'TBD?', row 26: 'TBD?'
    missing_token           2 cell(s)   e.g. row 5: '-', row 35: '-'
    parentheses_negative    2 cell(s)   e.g. row 8: '(500)', row 11: '(500)'
    unit_suffix             2 cell(s)   e.g. row 14: '12kg', row 29: '12kg'
    currency_symbol         1 cell(s)   e.g. row 17: '$30'
    thousands_separator     1 cell(s)   e.g. row 41: '1,200'
  fix:
    from whyobject import to_numeric
    df['price'] = to_numeric(df['price'])

● score  looks numeric (100% of values)
  pandas reads it as text because of:
    percent_sign           10 cell(s)   e.g. row 2: '76%', row 6: '88%', row 10: '41%'
  fix:
    from whyobject import to_numeric
    df['score'] = to_numeric(df['score'])
```

## What it recognises
Currency symbols (`$ ₹ € £ ¥ Rs INR`), thousands separators (including Indian `1,20,000`), percent signs, accounting negatives `(500)`, units (`12kg`), decimal commas (`3,5`), missing-value words (`-`, `?`, `TBD`), and junk. For dates it reports unparseable cells and mixed formats.

## Install
```bash
pip install .
```

## Usage
```bash
whyobject data.csv                         # diagnose
whyobject data.csv --fix cleaned.csv       # also write a cleaned copy
whyobject data.csv --json                  # machine-readable
```
In Python:
```python
from whyobject import load_csv, diagnose, to_numeric
df = load_csv("data.csv")        # tries utf-8, cp1252, latin-1
print(diagnose(df))
df["price"] = to_numeric(df["price"])
```
Exit code is `1` when problems are found, `0` when clean, so it works in CI.

## Web app
```bash
pip install streamlit pandas
streamlit run app.py
```

## Limitations
- `3,5` is read as a decimal comma, but could mean something else in your data.
- `45%` becomes `45`, not `0.45`.
- Day/month order in dates like `05/01/2024` is ambiguous; mixed formats are flagged, not guessed.
- A column is treated as numeric or date only when at least 60% of its values parse.

## Test
```bash
pip install pytest && pytest
```

## Roadmap
- Boolean columns (`yes/no/Y/N/TRUE`)
- Excel input
- `--strict` mode for CI
- Locale options for decimal comma

MIT licensed. Contributions welcome.
