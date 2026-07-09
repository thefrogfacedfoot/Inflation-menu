"""
UIFPI — Index Builder
Constructs the monthly Unified Informal-Formal Price Index per country
from the prices and nlp_results tables in uifpi.db.

Methodology:
  • Matched-model: only items present in both consecutive months are compared
  • Hedonic quality adjustment: ±% applied when quality signals are detected
  • Geometric mean of price relatives at category level
  • Separate formal / informal sector indices, combined by expenditure share

Run order: after nlp_pipeline.py.
Outputs: uifpi_index table in uifpi.db + uifpi_index.csv
"""

import json
import os
import sqlite3
from collections import defaultdict
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from data_quality import QUARANTINED_SLICES

DB_PATH = "uifpi.db"
CSV_OUT = "uifpi_index.csv"

# Per-(country, month) cap on rows used for index construction.
# Methodological choice — not data deletion. The raw uifpi.db keeps every
# scraped row; this cap only governs index aggregation so that a country
# with one extremely dense month (e.g. Singapore in 2026-06 with ~5k rows)
# doesn't dominate the cross-country index. With the cap, every country
# contributes equally per month regardless of scrape volume.
MAX_ROWS_PER_COUNTRY = 300
# Fixed RNG seed so the sampled index is reproducible across runs.
SAMPLE_SEED = 42

# Sources excluded from index construction. Rows survive in the raw `prices`
# table for downstream / diagnostic analysis but never enter the published
# UICPI index.
#
# wayback-doordash: Delivery-platform pricing reflects platform dynamics
# (surge pricing, promotions, delivery/service fees, marketplace markup)
# that are not present in traditional menu scrapes. Source-stratified
# Granger on US confirmed inclusion of DoorDash collapses the lag-1 menu→
# CPI F-stat from 5.56 (p=0.026, n=31) to 0.006 (p=0.94, n=38). The
# leading-indicator signal that holds in chain/independent menu data
# dissolves when delivery prices are pooled in. See diagnostics/
# diag_us_no_doordash.py for the reproducer.
EXCLUDED_SOURCES = ("wayback-doordash",)

# Approximate informal sector share of food expenditure by country.
# Source: author estimates from World Bank household survey data.
# Update these when real survey weights become available.
INFORMAL_WEIGHTS = {
    "Singapore":     0.35,
    "Malaysia":      0.45,
    "Indonesia":     0.55,
    "Thailand":      0.50,
    "India":         0.60,
    "United States": 0.20,
    "United Kingdom":0.15,
    "Australia":     0.20,
    "Vietnam":            0.60,
    "United Arab Emirates": 0.20,
}

# Hedonic adjustment factors
HEDGE_PREMIUM   = -0.05   # PREMIUM_UPGRADE → effective price 5% lower after adjustment
HEDGE_PORTION   = +0.08   # PORTION_REDUCTION → effective price 8% higher after adjustment

# Approximate USD exchange rates used when price_usd is NULL (single source of truth)
from fx_rates import FALLBACK_RATES


# ── Database helpers ──────────────────────────────────────────────────────────

def init_output_table(conn: sqlite3.Connection) -> None:
    """Create (and clear) the uifpi_index table.

    Truncating before each rebuild is required: INSERT OR REPLACE only
    overwrites months we re-emit, so months a new run no longer produces
    would otherwise survive as stale rows and contaminate downstream
    Granger analysis.
    """
    # Create a stub nlp_results table so the LEFT JOIN in load_price_data works
    # even when nlp_pipeline.py hasn't been run yet.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nlp_results (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name         TEXT NOT NULL,
            restaurant_name   TEXT,
            country           TEXT,
            category          TEXT,
            quality_signals   TEXT,
            language_detected TEXT,
            confidence        REAL,
            processed_date    TEXT,
            UNIQUE(item_name)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uifpi_index (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            country          TEXT NOT NULL,
            year_month       TEXT NOT NULL,
            formal_index     REAL,
            informal_index   REAL,
            uifpi_combined   REAL,
            item_count       INTEGER,
            coverage_note    TEXT,
            UNIQUE(country, year_month)
        )
    """)
    # Clear prior rows so this rebuild's months are the only ones in the table.
    conn.execute("DELETE FROM uifpi_index")
    conn.commit()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS category_relatives (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            country         TEXT NOT NULL,
            category        TEXT NOT NULL,
            year_month      TEXT NOT NULL,
            price_relative  REAL,
            item_count      INTEGER,
            adjusted_count  INTEGER,
            UNIQUE(country, category, year_month)
        )
    """)
    conn.commit()


def load_price_data(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Load prices joined with NLP categories.
    Backfills price_usd from price + currency when NULL.
    """
    df = pd.read_sql_query("""
        SELECT
            p.id,
            p.restaurant_name,
            p.item_name,
            p.price,
            p.currency,
            p.price_usd,
            p.country,
            p.sector,
            p.source,
            p.collection_date,
            COALESCE(n.category, 'OTHER')        AS category,
            COALESCE(n.quality_signals, '[]')    AS quality_signals,
            COALESCE(n.language_detected, 'en')  AS language_detected,
            COALESCE(n.confidence, 0.0)          AS confidence
        FROM prices p
        LEFT JOIN nlp_results n ON p.item_name = n.item_name
        WHERE p.price IS NOT NULL AND p.price > 0
    """, conn)

    # Backfill price_usd
    null_mask = df["price_usd"].isna()
    if null_mask.any():
        rates = df.loc[null_mask, "currency"].map(FALLBACK_RATES).fillna(1.0)
        df.loc[null_mask, "price_usd"] = df.loc[null_mask, "price"] / rates
        backfilled = null_mask.sum()
        print(f"  Backfilled price_usd for {backfilled:,} rows using fallback exchange rates.")

    df = df[df["price_usd"] > 0].copy()

    # TripAdvisor priceRange tier markers ($/$$/$$$/$$$$) were purged from
    # the raw `prices` table on 2026-06-17 and are no longer ingested.

    df["collection_date"] = pd.to_datetime(df["collection_date"], errors="coerce")
    df = df.dropna(subset=["collection_date"])
    df["year_month"] = df["collection_date"].dt.to_period("M").astype(str)

    # Restrict to UIFPI-relevant sectors BEFORE the per-month row cap so that
    # out-of-scope rows (e.g. BLS APU grocery, official CPI input series)
    # cannot perturb the deterministic sampling of menu prices. Out-of-scope
    # rows survive in the raw `prices` table for downstream analysis but
    # never enter the index.
    # The 2026-06-21 taxonomy rename (commit 93c5e34) was partial — both old
    # (formal/informal) and new (chain/independent) labels coexist in the DB.
    # Accept both and remap new→legacy so downstream code (which still uses
    # formal/informal variable names per the taxonomy decision) is unaffected.
    df = df[df["sector"].isin(("formal", "informal",
                               "chain",  "independent"))].copy()
    df["sector"] = df["sector"].replace({"chain": "formal",
                                         "independent": "informal"})

    # Drop sources excluded from index construction (see EXCLUDED_SOURCES
    # docstring at top of file for rationale).
    if EXCLUDED_SOURCES:
        before_excl = len(df)
        df = df[~df["source"].isin(EXCLUDED_SOURCES)].copy()
        dropped = before_excl - len(df)
        if dropped > 0:
            print(f"  Excluded {dropped:,} rows from sources "
                  f"{list(EXCLUDED_SOURCES)} (kept in raw DB).")

    # Drop quarantined (country, source) slices with corrupted prices — see
    # data_quality.py / docs/data_quality_2026-07.md.
    for q_country, q_source in QUARANTINED_SLICES:
        before_q = len(df)
        df = df[~((df["country"] == q_country) & (df["source"] == q_source))].copy()
        dropped_q = before_q - len(df)
        if dropped_q > 0:
            print(f"  Quarantined {dropped_q:,} rows: {q_country}/{q_source} "
                  f"(kept in raw DB)")

    # Cap rows per (country, year_month) so dense months don't dominate the
    # cross-country index. Deterministic via SAMPLE_SEED.
    before_rows = len(df)
    df = (df.groupby(["country", "year_month"], group_keys=False)
            .apply(lambda g: g.sample(n=min(len(g), MAX_ROWS_PER_COUNTRY),
                                      random_state=SAMPLE_SEED)))
    capped = before_rows - len(df)
    if capped > 0:
        print(f"  Sampled to {MAX_ROWS_PER_COUNTRY}/country/month for index "
              f"construction (dropped {capped:,} excess rows; raw DB unchanged).")

    return df


# ── Hedonic adjustment ────────────────────────────────────────────────────────

def apply_hedonic_adjustment(price: float, signals_json: str) -> tuple[float, bool]:
    """
    Apply hedonic quality adjustments based on detected quality signals.
    Returns (adjusted_price, was_adjusted).

    Adjustments are additive when multiple signals are present.
    Design choice: cap total adjustment at ±15% to avoid over-correction.
    """
    try:
        signals = json.loads(signals_json or "[]")
    except json.JSONDecodeError:
        signals = []

    adjustment = 0.0
    if "PREMIUM_UPGRADE" in signals:
        adjustment += HEDGE_PREMIUM
    if "PORTION_REDUCTION" in signals:
        adjustment += HEDGE_PORTION

    # Cap
    adjustment = max(-0.15, min(0.15, adjustment))
    if adjustment == 0.0:
        return price, False

    return price * (1 + adjustment), True


# ── Price relative calculation ────────────────────────────────────────────────

def geometric_mean(values: list[float]) -> float:
    """Geometric mean of a list of positive floats."""
    if not values:
        return 1.0
    valid = [v for v in values if v > 0]
    if not valid:
        return 1.0
    return float(np.exp(np.log(valid).mean()))


def build_monthly_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate to median price per (country, sector, category, restaurant, item, year_month).
    Also carry quality_signals for the most common variant per group.
    """
    agg = (df
           .groupby(["country", "sector", "category", "restaurant_name",
                     "item_name", "year_month"])
           .agg(
               price_usd=("price_usd", "median"),
               quality_signals=("quality_signals", "first"),
           )
           .reset_index())
    return agg


_MIN_STABLE_ITEMS = 3
_MIN_MONTHS_PER_ITEM = 2


def build_stable_basket_index(df: pd.DataFrame, country: str) -> list[dict]:
    """
    Fallback when matched-model finds no consecutive-month overlap.

    Instead of comparing cross-item *mean prices* (which conflates basket
    churn with inflation and previously produced indices like Singapore
    712 / UK 1047 in 2026-06), this builds a smaller "stable basket" of
    items that appear in at least _MIN_MONTHS_PER_ITEM month observations,
    then for each such item computes:

        relative_t = price_t / price_earliest

    The monthly index for a sector is the geometric mean of all stable-item
    relatives present in that month, × 100. Formal and informal sub-indices
    are computed separately and combined using INFORMAL_WEIGHTS.

    When the stable basket has < _MIN_STABLE_ITEMS items, rows are still
    emitted but the index columns are NULL with a coverage_note explaining
    why — better an honest "insufficient data" than a fabricated ratio.
    """
    c_df = df[df["country"] == country].copy()
    if c_df.empty:
        return []

    item_key = ["restaurant_name", "item_name"]
    month_counts = c_df.groupby(item_key)["year_month"].nunique()
    stable_keys = month_counts[month_counts >= _MIN_MONTHS_PER_ITEM].index

    # Helper: emit insufficient-data rows so the dashboard sees the gap
    # rather than silently dropping the country.
    def _insufficient(note: str) -> list[dict]:
        rows = []
        for ym, grp in c_df.groupby("year_month"):
            rows.append({
                "country":        country,
                "year_month":     ym,
                "formal_index":   None,
                "informal_index": None,
                "uifpi_combined": None,
                "item_count":     int(len(grp)),
                "coverage_note":  note,
            })
        return rows

    if len(stable_keys) < _MIN_STABLE_ITEMS:
        return _insufficient(
            f"insufficient stable basket "
            f"({len(stable_keys)} items in ≥{_MIN_MONTHS_PER_ITEM} months, "
            f"need {_MIN_STABLE_ITEMS})"
        )

    # Restrict to stable items
    stable_mask = c_df.set_index(item_key).index.isin(set(stable_keys))
    stable_df = c_df[stable_mask].copy()

    # Base price per item = price at its earliest month
    stable_df = stable_df.sort_values("year_month")
    base = (stable_df.groupby(item_key, as_index=False)
                     .agg(base_price_usd=("price_usd", "first")))
    stable_df = stable_df.merge(base, on=item_key, how="left")
    stable_df = stable_df[stable_df["base_price_usd"] > 0].copy()
    stable_df["relative"] = stable_df["price_usd"] / stable_df["base_price_usd"]

    informal_weight = INFORMAL_WEIGHTS.get(country, 0.40)
    n_stable = len(stable_keys)
    coverage_note = (f"stable-basket fallback "
                     f"({n_stable} items in ≥{_MIN_MONTHS_PER_ITEM} months)")

    def _gmean(values: pd.Series) -> Optional[float]:
        pos = values[values > 0]
        if pos.empty:
            return None
        return float(np.exp(np.log(pos).mean()) * 100.0)

    # Iterate over every month the country has data in, not just months
    # with stable-basket coverage. Months with no stable-basket items
    # emit NULL index columns + a "no coverage this month" note so the
    # dashboard shows the gap honestly.
    rows: list[dict] = []
    for ym, orig_grp in c_df.groupby("year_month"):
        grp = stable_df[stable_df["year_month"] == ym]

        if grp.empty:
            note = (f"{coverage_note} — no stable-basket items in this month "
                    f"(new items haven't appeared in ≥{_MIN_MONTHS_PER_ITEM} "
                    f"monthly observations yet)")
            rows.append({
                "country":        country,
                "year_month":     ym,
                "formal_index":   None,
                "informal_index": None,
                "uifpi_combined": None,
                "item_count":     int(len(orig_grp)),
                "coverage_note":  note,
            })
            continue

        formal_idx   = _gmean(grp.loc[grp["sector"] == "formal",   "relative"])
        informal_idx = _gmean(grp.loc[grp["sector"] == "informal", "relative"])

        if formal_idx is not None and informal_idx is not None:
            combined = informal_weight * informal_idx + (1 - informal_weight) * formal_idx
        else:
            combined = formal_idx if formal_idx is not None else informal_idx

        rows.append({
            "country":        country,
            "year_month":     ym,
            "formal_index":   round(formal_idx, 4)   if formal_idx   is not None else None,
            "informal_index": round(informal_idx, 4) if informal_idx is not None else None,
            "uifpi_combined": round(combined, 4)     if combined     is not None else None,
            "item_count":     int(len(orig_grp)),
            "coverage_note":  coverage_note,
        })
    return rows


# Alias kept for any external caller still using the old name; the
# implementation has changed.
build_mean_price_index = build_stable_basket_index


def build_restaurant_median_index(df: pd.DataFrame, country: str) -> list[dict]:
    """
    Restaurant-level index, robust to item-level basket churn.

    For each (country, restaurant, year_month) compute the median price.
    Then for each (sector, year_month) take the geometric mean across
    restaurants. The earliest month is the base (100); later months are
    expressed as a ratio. Formal/informal are computed separately and
    combined with INFORMAL_WEIGHTS.

    Trade-off vs stable-basket: this is sensitive to which restaurants
    appear in a given month (composition bias). But on data where
    individual menu items rarely span ≥2 months for the same restaurant
    — true of Wayback TripAdvisor snapshots, which extract whatever
    happened to be on that archive's page — stable-basket collapses to
    a near-constant index. This method produces real variation and is
    the right choice when item-level matching isn't feasible.
    """
    c_df = df[df["country"] == country].copy()
    if c_df.empty:
        return []

    # Restaurant-month median price, keep sector tag.
    rm = (c_df.groupby(["restaurant_name", "sector", "year_month"], as_index=False)
              .agg(price_usd=("price_usd", "median")))
    rm = rm[rm["price_usd"] > 0]
    if rm.empty:
        return []

    informal_weight = INFORMAL_WEIGHTS.get(country, 0.40)

    def _gmean(values: pd.Series) -> Optional[float]:
        pos = values[values > 0]
        return float(np.exp(np.log(pos).mean())) if not pos.empty else None

    # Per-sector month-level geometric means
    per_sector_month: dict = {}
    for sector in ("formal", "informal"):
        sd = rm[rm["sector"] == sector]
        if sd.empty:
            continue
        for ym, grp in sd.groupby("year_month"):
            gm = _gmean(grp["price_usd"])
            if gm is not None:
                per_sector_month[(sector, ym)] = gm

    # Base = earliest month with data per sector
    bases: dict = {}
    for sector in ("formal", "informal"):
        months_with = sorted(ym for (s, ym) in per_sector_month if s == sector)
        if months_with:
            bases[sector] = per_sector_month[(sector, months_with[0])]

    all_months = sorted(c_df["year_month"].unique())
    rows: list[dict] = []
    for ym in all_months:
        formal_v   = per_sector_month.get(("formal",   ym))
        informal_v = per_sector_month.get(("informal", ym))
        formal_idx   = (formal_v   / bases["formal"]   * 100.0) if (formal_v   and bases.get("formal"))   else None
        informal_idx = (informal_v / bases["informal"] * 100.0) if (informal_v and bases.get("informal")) else None

        if formal_idx is not None and informal_idx is not None:
            combined = informal_weight * informal_idx + (1 - informal_weight) * formal_idx
        else:
            combined = formal_idx if formal_idx is not None else informal_idx

        item_count = int((c_df["year_month"] == ym).sum())
        rows.append({
            "country":        country,
            "year_month":     ym,
            "formal_index":   round(formal_idx, 4)   if formal_idx   is not None else None,
            "informal_index": round(informal_idx, 4) if informal_idx is not None else None,
            "uifpi_combined": round(combined, 4)     if combined     is not None else None,
            "item_count":     item_count,
            "coverage_note":  f"restaurant-median index "
                              f"({rm[rm['year_month'] == ym]['restaurant_name'].nunique()} restaurants this month)",
        })
    return rows


def compute_price_relatives(monthly: pd.DataFrame,
                             months: list[str]) -> dict:
    """
    Build matched-model price relatives for consecutive month pairs.

    Returns a dict keyed by (country, sector, category, year_month) →
    {relative, item_count, adjusted_count}.

    Drop logic: items absent for > 3 consecutive months are excluded.
    """
    drop_log = []
    relatives = {}

    countries = monthly["country"].unique()

    for country in countries:
        c_data = monthly[monthly["country"] == country].copy()
        country_months = sorted(c_data["year_month"].unique())

        if len(country_months) < 2:
            print(f"  {country}: only {len(country_months)} month(s) of data — "
                  f"index initialised at base (100).")
            continue

        # Track consecutive absence per item
        item_absences: dict = defaultdict(int)

        for i in range(1, len(country_months)):
            t      = country_months[i]
            t_prev = country_months[i - 1]

            data_t    = c_data[c_data["year_month"] == t]
            data_prev = c_data[c_data["year_month"] == t_prev]

            matched = data_t.merge(
                data_prev,
                on=["restaurant_name", "item_name", "sector", "category"],
                suffixes=("_t", "_prev"),
            )

            # Track which items appeared / didn't
            all_items = set(zip(c_data["restaurant_name"], c_data["item_name"]))
            present_t = set(zip(data_t["restaurant_name"], data_t["item_name"]))
            for item in all_items:
                if item in present_t:
                    item_absences[item] = 0
                else:
                    item_absences[item] += 1

            # Drop items absent > 3 consecutive months
            drop_items = {k for k, v in item_absences.items() if v > 3}
            if drop_items:
                drop_log.append(
                    f"  {country} {t}: dropped {len(drop_items)} items "
                    f"(absent >3 months)"
                )
                matched = matched[
                    ~matched.apply(
                        lambda r: (r["restaurant_name"], r["item_name"])
                        in drop_items, axis=1
                    )
                ]

            if matched.empty:
                continue

            for (sector, category), group in matched.groupby(["sector", "category"]):
                price_ratios = []
                adjusted_count = 0

                for _, row in group.iterrows():
                    p_curr, adj = apply_hedonic_adjustment(
                        row["price_usd_t"], row["quality_signals_t"]
                    )
                    if adj:
                        adjusted_count += 1
                    ratio = p_curr / row["price_usd_prev"]
                    if 0.01 < ratio < 100:   # sanity filter
                        price_ratios.append(ratio)

                if not price_ratios:
                    continue

                key = (country, sector, category, t)
                relatives[key] = {
                    "relative":       geometric_mean(price_ratios),
                    "item_count":     len(price_ratios),
                    "adjusted_count": adjusted_count,
                }

    if drop_log:
        print("\n  Item drop log:")
        for msg in drop_log:
            print(msg)

    return relatives


# ── Index construction ────────────────────────────────────────────────────────

def build_country_index(country: str,
                        relatives: dict,
                        monthly: pd.DataFrame) -> list[dict]:
    """
    Build the formal, informal, and combined UIFPI series for one country.
    Uses equal category weights within each sector (unweighted geometric mean).
    Returns a list of row dicts ready for DB insert.
    """
    c_data = monthly[monthly["country"] == country]
    months = sorted(c_data["year_month"].unique())

    informal_weight = INFORMAL_WEIGHTS.get(country, 0.40)

    # Initialise sector indices at 100.0 for base month
    formal_idx   = {months[0]: 100.0}
    informal_idx = {months[0]: 100.0}

    for i in range(1, len(months)):
        t = months[i]

        # Collect category relatives for this month
        formal_rels   = []
        informal_rels = []
        for (c2, sector, cat, ym), v in relatives.items():
            if c2 == country and ym == t:
                if sector == "formal":
                    formal_rels.append(v["relative"])
                elif sector == "informal":
                    informal_rels.append(v["relative"])

        formal_rel   = geometric_mean(formal_rels)   if formal_rels   else 1.0
        informal_rel = geometric_mean(informal_rels) if informal_rels else 1.0

        formal_idx[t]   = formal_idx[months[i-1]]   * formal_rel
        informal_idx[t] = informal_idx[months[i-1]] * informal_rel

    rows = []
    for t in months:
        fi  = formal_idx.get(t)
        ii  = informal_idx.get(t)
        uifpi = (
            (1 - informal_weight) * fi + informal_weight * ii
            if fi is not None and ii is not None
            else None
        )
        item_count = int(c_data[c_data["year_month"] == t].shape[0])
        note = "base period (100.0)" if t == months[0] else None

        rows.append({
            "country":         country,
            "year_month":      t,
            "formal_index":    round(fi,    4) if fi    is not None else None,
            "informal_index":  round(ii,    4) if ii    is not None else None,
            "uifpi_combined":  round(uifpi, 4) if uifpi is not None else None,
            "item_count":      item_count,
            "coverage_note":   note,
        })

    # If all non-base values are 100.0 (no matched-model overlap found),
    # flag the issue — caller will use mean-price fallback instead.
    non_base = [r for r in rows if r["coverage_note"] != "base period (100.0)"]
    all_constant = non_base and all(
        r["uifpi_combined"] == 100.0 for r in non_base
    )
    if all_constant:
        return []   # signal to caller: use mean-price fallback

    return rows


# ── Category relatives storage ────────────────────────────────────────────────

def save_category_relatives(conn: sqlite3.Connection, relatives: dict) -> None:
    """Persist category-level price relatives to category_relatives table."""
    for (country, sector, category, ym), v in relatives.items():
        conn.execute("""
            INSERT OR REPLACE INTO category_relatives
                (country, category, year_month, price_relative,
                 item_count, adjusted_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            f"{country}/{sector}", category, ym,
            v["relative"], v["item_count"], v["adjusted_count"],
        ))
    conn.commit()


# ── Summary printing ──────────────────────────────────────────────────────────

def print_index_summary(all_rows: list[dict]) -> None:
    """Print a readable table of index values per country and year."""
    print(f"\n{'='*70}")
    print("UIFPI Index Summary")
    print(f"{'='*70}")
    print(f"{'Country':<22} {'Month':<10} {'Formal':>8} {'Informal':>10} "
          f"{'UIFPI':>8} {'Items':>6}")
    print("-" * 70)

    current_country = None
    for row in sorted(all_rows, key=lambda r: (r["country"], r["year_month"])):
        if row["country"] != current_country:
            current_country = row["country"]
            print()

        fi  = f"{row['formal_index']:.2f}"    if row["formal_index"]   else "—"
        ii  = f"{row['informal_index']:.2f}"  if row["informal_index"] else "—"
        ui  = f"{row['uifpi_combined']:.2f}"  if row["uifpi_combined"] else "—"

        print(f"  {row['country']:<20} {row['year_month']:<10} "
              f"{fi:>8} {ii:>10} {ui:>8} {row['item_count']:>6}")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def run(db_path: str = DB_PATH, csv_out: str = CSV_OUT,
        method: str = "restaurant-median") -> None:
    """Build the UIFPI for all countries and save results.

    method:
      - "restaurant-median" (default): geometric mean of per-restaurant
        monthly medians, chained against the country's earliest month.
        Robust to item-level basket churn — the right choice for the
        current Wayback-snapshot dataset, where the same menu item
        rarely reappears across archive visits and stable-basket would
        emit nulls for most countries.
      - "stable-basket": within-item price relatives. More rigorous when
        the data actually supports it, but degenerates to constant 100
        (or all-null rows) when no item appears in ≥2 months for the
        same restaurant. Kept available for future data sources where
        item-level matching is feasible.
    """
    conn = sqlite3.connect(db_path)
    init_output_table(conn)

    print("\nIndex Builder")
    print("─" * 60)
    print("Step 1 — Loading price data …")
    df = load_price_data(conn)
    print(f"  Loaded {len(df):,} price observations across "
          f"{df['country'].nunique()} countries")
    print(f"  Date range: {df['collection_date'].min().date()} — "
          f"{df['collection_date'].max().date()}")

    print("\nStep 2 — Building monthly price panel …")
    monthly = build_monthly_prices(df)
    months_all = sorted(monthly["year_month"].unique())
    print(f"  {len(monthly):,} (country, sector, category, restaurant, item, month) cells")
    print(f"  Months covered: {months_all[0]} → {months_all[-1]}")

    print("\nStep 3 — Computing matched-model price relatives …")
    relatives = compute_price_relatives(monthly, months_all)
    print(f"  {len(relatives)} category-relative observations computed")

    print("\nStep 4 — Saving category relatives …")
    save_category_relatives(conn, relatives)

    print(f"\nStep 5 — Building sector and combined indices (method={method}) …")
    all_index_rows: list[dict] = []
    for country in sorted(monthly["country"].unique()):
        if method == "restaurant-median":
            # Skip matched-model entirely — restaurant-median is the index.
            rmrows = build_restaurant_median_index(df, country)
            if rmrows:
                all_index_rows.extend(rmrows)
                print(f"  {country}: {len(rmrows)} monthly observations (restaurant-median)")
            else:
                print(f"  {country}: insufficient data — skipped")
            continue

        irows = build_country_index(country, relatives, monthly)
        if irows:
            all_index_rows.extend(irows)
            print(f"  {country}: {len(irows)} monthly observations (matched-model)")
        else:
            # No consecutive-month overlap in matched-model — fall back
            # to the stable-basket index (each item compared to its own
            # earliest price). When the stable basket itself is too sparse
            # the rows are emitted with NULL index values so the dashboard
            # sees "insufficient data" rather than silently dropping.
            fallback = build_stable_basket_index(df, country)
            if fallback:
                all_index_rows.extend(fallback)
                note = fallback[0]["coverage_note"]
                print(f"  {country}: {len(fallback)} monthly observations ({note})")
            else:
                print(f"  {country}: insufficient data — skipped")

    print("\nStep 6 — Saving to database and CSV …")
    for row in all_index_rows:
        conn.execute("""
            INSERT OR REPLACE INTO uifpi_index
                (country, year_month, formal_index, informal_index,
                 uifpi_combined, item_count, coverage_note)
            VALUES (:country, :year_month, :formal_index, :informal_index,
                    :uifpi_combined, :item_count, :coverage_note)
        """, row)
    conn.commit()
    print(f"  {len(all_index_rows)} rows written to uifpi_index table")

    if all_index_rows:
        out_df = pd.DataFrame(all_index_rows)
        out_df.to_csv(csv_out, index=False)
        print(f"  Exported to {csv_out}")
    else:
        print("  ⚠  No index rows produced — insufficient data for any country.")
        print("     Collect data for >= 2 months and re-run.")

    conn.close()
    print_index_summary(all_index_rows)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="Build the UIFPI from uifpi.db price observations."
    )
    ap.add_argument("--method", default="restaurant-median",
                    choices=("stable-basket", "restaurant-median"),
                    help="Index aggregation method (default: restaurant-median).")
    args = ap.parse_args()
    run(method=args.method)
