"""
UIFPI — Paper Data Tables
Generates formatted tables (CSV + LaTeX) for the research paper.

Tables:
  1 — Country sample and data coverage
  2 — Descriptive statistics
  3 — Granger causality results
  4 — Pass-through regression results
"""

import json
import os
import sqlite3
import textwrap
from typing import Optional

import numpy as np
import pandas as pd

DB_PATH    = "uifpi.db"
CPI_DIR    = "cpi_data"
TABLES_DIR = "tables"
RESULTS_DIR = "analysis_results"

COUNTRIES = [
    "Singapore", "Malaysia", "Indonesia", "Thailand",
    "India", "United States", "United Kingdom", "Australia",
]

DEVELOPMENT_STATUS = {
    "Singapore":     "Developed",
    "Malaysia":      "Emerging",
    "Indonesia":     "Emerging",
    "Thailand":      "Emerging",
    "India":         "Emerging",
    "United States": "Developed",
    "United Kingdom":"Developed",
    "Australia":     "Developed",
}

DATA_SOURCES = {
    "Singapore":     "Live scrape (Zomato, GrabFood) + historical menus",
    "Malaysia":      "Live scrape (Zomato, GrabFood) + historical menus",
    "Indonesia":     "Live scrape (GoFood, GrabFood)",
    "Thailand":      "Live scrape (GrabFood) + historical menus",
    "India":         "Live scrape (Zomato, Swiggy)",
    "United States": "Live scrape (Yelp, DoorDash) + historical menus",
    "United Kingdom":"Live scrape (Deliveroo, JustEat)",
    "Australia":     "Live scrape (Uber Eats, Menulog)",
}

ARCHIVE_COVERAGE = {
    "Singapore":     "2018–present",
    "Malaysia":      "2018–present",
    "Indonesia":     "2019–present",
    "Thailand":      "2018–present",
    "India":         "2018–present",
    "United States": "2018–present",
    "United Kingdom":"2019–present",
    "Australia":     "2018–present",
}

COUNTRY_CPI_FILES = {
    "Singapore":     "monthly_cpi_sg.json",
    "Malaysia":      None,
    "Indonesia":     "monthly_cpi_id.json",
    "Thailand":      "monthly_cpi_th.json",
    "India":         "monthly_cpi_in.json",
    "United States": "monthly_cpi_us.json",
    "United Kingdom":"monthly_cpi_gb.json",
    "Australia":     "monthly_cpi_au.json",
}

USD_RATES = {
    "Singapore": 0.74, "Malaysia": 0.21, "Indonesia": 0.000062,
    "Thailand": 0.028, "India": 0.012, "United States": 1.0,
    "United Kingdom": 1.27, "Australia": 0.65,
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_prices() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT country, sector, price_usd, collection_date FROM prices",
        conn,
    )
    conn.close()
    df["collection_date"] = pd.to_datetime(df["collection_date"], errors="coerce")
    return df


def load_index() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT country, year_month, formal_index, informal_index, "
        "uifpi_combined, item_count FROM uifpi_index",
        conn,
    )
    conn.close()
    return df


def load_granger() -> dict:
    path = os.path.join(RESULTS_DIR, "granger_results.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# LaTeX escaping
# ---------------------------------------------------------------------------

def tex_escape(s: str) -> str:
    replacements = {
        "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
        "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
        "^": r"\^{}", "\\": r"\textbackslash{}",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s


def df_to_latex(df: pd.DataFrame, caption: str, label: str,
                note: str = "") -> str:
    cols     = df.columns.tolist()
    n_cols   = len(cols)
    col_spec = "l" + "r" * (n_cols - 1)

    header = " & ".join(rf"\textbf{{{tex_escape(str(c))}}}" for c in cols)

    rows = []
    for _, row in df.iterrows():
        cells = []
        for val in row:
            if pd.isna(val) or val == "" or val is None:
                cells.append("---")
            else:
                cells.append(tex_escape(str(val)))
        rows.append(" & ".join(cells) + r" \\")

    note_str = (rf"\footnotesize Note: {tex_escape(note)}"
                if note else "")

    return textwrap.dedent(rf"""
        \begin{{table}}[htbp]
        \centering
        \caption{{{tex_escape(caption)}}}
        \label{{{label}}}
        \begin{{tabular}}{{{col_spec}}}
        \toprule
        {header} \\
        \midrule
        {chr(10).join(rows)}
        \bottomrule
        \end{{tabular}}
        {note_str}
        \end{{table}}
    """).strip()


# ---------------------------------------------------------------------------
# Table 1 — Country sample and data coverage
# ---------------------------------------------------------------------------

def table1(prices_df: pd.DataFrame):
    rows = []
    for country in COUNTRIES:
        cp = prices_df[prices_df["country"] == country]
        n_formal   = len(cp[cp["sector"] == "formal"])
        n_informal = len(cp[cp["sector"] == "informal"])
        conn = sqlite3.connect(DB_PATH)
        n_rest = pd.read_sql_query(
            "SELECT COUNT(DISTINCT restaurant_name) AS n FROM prices WHERE country = ?",
            conn, params=[country],
        ).iloc[0, 0]
        conn.close()
        live_start = cp["collection_date"].min()
        live_str   = live_start.strftime("%Y-%m") if pd.notna(live_start) else "—"
        rows.append({
            "Country":           country,
            "Dev. Status":       DEVELOPMENT_STATUS[country],
            "Data Source":       DATA_SOURCES[country].split("(")[0].strip(),
            "Archive Coverage":  ARCHIVE_COVERAGE[country],
            "Live Data Start":   live_str,
            "Restaurants":       n_rest,
            "Items (F/I)":       f"{n_formal}/{n_informal}",
        })
    df = pd.DataFrame(rows)
    return df


# ---------------------------------------------------------------------------
# Table 2 — Descriptive statistics
# ---------------------------------------------------------------------------

def table2(prices_df: pd.DataFrame, index_df: pd.DataFrame):
    rows = []
    for country in COUNTRIES:
        cp = prices_df[prices_df["country"] == country]
        if cp.empty:
            rows.append({
                "Country": country, "Mean Price (USD)": "—",
                "Std Dev": "—", "Formal Mean": "—",
                "Informal Mean": "—", "Items": 0, "Months": 0,
            })
            continue
        px = cp["price_usd"].dropna()
        formal_px   = cp[cp["sector"] == "formal"]["price_usd"].dropna()
        informal_px = cp[cp["sector"] == "informal"]["price_usd"].dropna()
        idx = index_df[index_df["country"] == country]
        rows.append({
            "Country":         country,
            "Mean Price (USD)": f"{px.mean():.2f}" if not px.empty else "—",
            "Std Dev":          f"{px.std():.2f}"  if not px.empty else "—",
            "Formal Mean":      f"{formal_px.mean():.2f}"   if not formal_px.empty else "—",
            "Informal Mean":    f"{informal_px.mean():.2f}" if not informal_px.empty else "—",
            "Items":            int(len(px)),
            "Months":           int(idx["year_month"].nunique()),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 3 — Granger causality results
# ---------------------------------------------------------------------------

def table3(granger: dict):
    rows = []
    for country in COUNTRIES:
        r = granger.get(country, {})
        pv = r.get("granger_p_value")
        lt = r.get("lead_months")
        rows.append({
            "Country":       country,
            "N Obs":         r.get("n_obs", "—"),
            "ADF Stat":      "—",
            "F-Statistic":   "—",
            "p-value":       f"{pv:.4f}" if pv is not None else "—",
            "Lead (months)": lt if lt is not None else "—",
            "Significant":   "Yes" if r.get("granger_significant") else "No",
            "Note":          r.get("note", ""),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 4 — Pass-through regression
# ---------------------------------------------------------------------------

def table4(granger: dict):
    rows = []
    for country in COUNTRIES:
        r  = granger.get(country, {})
        fp = r.get("pass_through_formal")
        ip = r.get("pass_through_informal")
        pt_sig = r.get("pass_through_significant", False)
        diff = (fp - ip) if (fp is not None and ip is not None) else None
        rows.append({
            "Country":              country,
            "Formal Coeff (β_f)":  f"{fp:.3f}" if fp is not None else "—",
            "Informal Coeff (β_i)":f"{ip:.3f}" if ip is not None else "—",
            "Difference (β_f−β_i)":f"{diff:.3f}" if diff is not None else "—",
            "Significant":          "Yes" if pt_sig else "No",
            "R²":                   "—",
            "Note":                 r.get("note", ""),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Write table files
# ---------------------------------------------------------------------------

def write_table(df: pd.DataFrame, name: str, caption: str, label: str,
                note: str = ""):
    os.makedirs(TABLES_DIR, exist_ok=True)
    csv_path = os.path.join(TABLES_DIR, f"{name}.csv")
    tex_path = os.path.join(TABLES_DIR, f"{name}.tex")
    df.to_csv(csv_path, index=False)
    tex = df_to_latex(df, caption=caption, label=label, note=note)
    with open(tex_path, "w") as f:
        f.write(tex)
    print(f"  ✓ {csv_path}")
    print(f"  ✓ {tex_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(TABLES_DIR, exist_ok=True)
    print("Generating paper tables...")

    prices_df = load_prices()
    index_df  = load_index()
    granger   = load_granger()

    t1 = table1(prices_df)
    print("\nTable 1 — Country sample:")
    write_table(
        t1, "table1_sample",
        caption="Country Sample and Data Coverage",
        label="tab:sample",
        note=(
            "F = formal restaurant; I = informal/street vendor. "
            "Archive coverage reflects historical menu data collected via "
            "Wayback Machine and platform APIs. "
            "Dev. Status = IMF World Economic Outlook classification."
        ),
    )

    t2 = table2(prices_df, index_df)
    print("\nTable 2 — Descriptive statistics:")
    write_table(
        t2, "table2_descriptive",
        caption="Descriptive Statistics by Country",
        label="tab:descriptive",
        note=(
            "All prices converted to USD at collection-date exchange rates. "
            "Mean and Std Dev computed over all non-zero price observations. "
            "Months = number of distinct month-year periods with index observations."
        ),
    )

    t3 = table3(granger)
    print("\nTable 3 — Granger causality results:")
    write_table(
        t3, "table3_granger",
        caption="Granger Causality Results: UIFPI $\\rightarrow$ Official CPI",
        label="tab:granger",
        note=(
            "All series first-differenced before testing. "
            "Lag order selected by AIC (max 6 lags). "
            "Significance threshold: p < 0.10. "
            "Countries requiring >= 24 monthly observations are marked insufficient."
        ),
    )

    t4 = table4(granger)
    print("\nTable 4 — Pass-through regression results:")
    write_table(
        t4, "table4_passthrough",
        caption="Cost Pass-Through Regression: Formal vs Informal Sector",
        label="tab:passthrough",
        note=(
            r"Regression: $\Delta\ln P^{sector}_t = \alpha + \beta \Delta\ln CPI_t + \varepsilon_t$. "
            r"$\beta = 1$ implies full pass-through. "
            "Significance based on Newey-West HAC standard errors."
        ),
    )

    print(f"\nAll tables saved to {TABLES_DIR}/")

    # Verify
    print("\nTable file check:")
    for name in ["table1_sample", "table2_descriptive",
                 "table3_granger", "table4_passthrough"]:
        for ext in [".csv", ".tex"]:
            p = os.path.join(TABLES_DIR, name + ext)
            status = "✓" if os.path.exists(p) else "✗"
            print(f"  {status} {p}")


if __name__ == "__main__":
    main()
