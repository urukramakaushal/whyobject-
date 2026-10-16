import pandas as pd
from whyobject.core import apply_fix, classify_number, diagnose, load_csv, to_numeric


def test_classify_cases():
    cases = {
        "42": (42.0, "ok"), "$30": (30.0, "currency_symbol"), "₹1,20,000": (120000.0, "currency_symbol"),
        "1,200": (1200.0, "thousands_separator"), "45%": (45.0, "percent_sign"),
        "(500)": (-500.0, "parentheses_negative"), "12kg": (12.0, "unit_suffix"),
        "3,5": (3.5, "decimal_comma"), "-": (None, "missing_token"), "TBD": (None, "missing_token"),
        "abc": (None, "junk"), "1_000": (None, "junk"), "inf": (None, "junk"), "": (None, "empty"),
    }
    for raw, expected in cases.items():
        assert classify_number(raw) == expected, raw


def test_scientific_notation_is_ok():
    assert classify_number("1e5") == (100000.0, "ok")


def _df():
    return pd.DataFrame({
        "name": ["Ravi", "Mina", "Tom", "Sam", "Ann", "Joe"],
        "price": ["10", "$30", "1,200", "-", "N/A", "25"],
        "clean": ["1", "2", "3", "4", "5", "6"],
        "when": ["2024-01-05", "2024-02-10", "not a date", "2024-03-01", "2024-04-02", "2024-05-06"],
    })


def test_diagnose_finds_only_problem_columns():
    diag = diagnose(_df())
    assert [d["column"] for d in diag] == ["price", "when"]
    price = diag[0]
    assert price["intent"] == "numeric"
    assert set(price["breakers"]) == {"currency_symbol", "thousands_separator", "missing_token"}
    assert "N/A" not in str(price["breakers"])  # pandas already treats N/A as missing


def test_row_numbers_match_excel():
    price = diagnose(_df())[0]
    assert price["breakers"]["currency_symbol"]["examples"][0]["row"] == 3  # 2nd data row


def test_date_breaker():
    when = diagnose(_df())[1]
    assert when["intent"] == "date"
    assert when["breakers"]["unparseable"]["examples"][0]["value"] == "not a date"


def test_mixed_date_formats():
    df = pd.DataFrame({"d": ["2024-01-05"] * 5 + ["05/01/2024"] * 5})
    d = diagnose(df)[0]
    assert len(d["mixed_formats"]) == 2


def test_text_and_month_names_ignored():
    df = pd.DataFrame({"m": ["Jan", "Feb", "March", "April"], "n": ["a", "b", "c", "d"]})
    assert diagnose(df) == []


def test_apply_fix():
    df = _df()
    fixed, stats = apply_fix(df, diagnose(df))
    assert fixed["price"].tolist()[:3] == [10.0, 30.0, 1200.0]
    assert fixed["price"].isna().sum() == 2
    assert pd.isna(fixed["when"][2])
    assert {s["column"]: s["unreadable_set_to_missing"] for s in stats}["when"] == 1


def test_to_numeric_series():
    assert to_numeric(pd.Series(["$1", "x", None])).tolist()[0] == 1.0


def test_load_csv_cp1252():
    raw = "name,price\nÜnal,$5\n".encode("cp1252")
    assert load_csv(raw)["name"][0] == "Ünal"
