import pandas as pd
import streamlit as st
from whyobject.core import apply_fix, diagnose, load_csv

st.set_page_config(page_title="whyobject", page_icon="🔍", layout="centered")
st.title("🔍 whyobject")
st.write("**Why is my column `object`?** Upload a CSV and see the exact cells that stop pandas from reading numbers and dates.")

file = st.file_uploader("CSV file", type="csv")
if file:
    try:
        df = load_csv(file.getvalue())
    except Exception as e:
        st.error(f"Could not read this file as a CSV: {e}")
        st.stop()
    st.caption(f"{df.shape[0]} rows × {df.shape[1]} columns (row numbers match Excel; header = row 1)")

    diag = diagnose(df)
    if not diag:
        st.success("No problem cells found. Numeric and date columns look clean.")
    else:
        st.error(f"{len(diag)} problem column(s)")
        for d in diag:
            with st.expander(f"{d['column']} — looks {d['intent']} ({d['share']:.0%} of values)", expanded=True):
                rows = [{"cause": c, "cells": i["count"],
                         "examples": ", ".join(f"row {e['row']}: {e['value']!r}" for e in i["examples"])}
                        for c, i in sorted(d["breakers"].items(), key=lambda kv: -kv[1]["count"])]
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                for m in d.get("mixed_formats", []):
                    st.write(f"Mixed format `{m['pattern']}`: {m['count']} cells, e.g. `{m['example']}`")
                st.code(d["fix"], language="python")
        fixed, stats = apply_fix(df, diag)
        st.subheader("Cleaned preview")
        st.dataframe(fixed.head(10), use_container_width=True)
        st.download_button("Download cleaned CSV", fixed.to_csv(index=False).encode("utf-8"),
                           file_name="cleaned.csv", mime="text/csv", type="primary")
else:
    st.info("Upload a CSV to get started.")
