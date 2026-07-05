"""
Coverage and alignment check for the equity price data and FRED regime
signals, before building the regime classifier on top of them.

Run this after both pull_equity_data.py and pull_fred_data.py have
succeeded. It does NOT fix anything automatically -- it just reports
what's there, so you can make deliberate decisions (see the "Open items"
section of pre_data_collection_checklist_draft.md) rather than discovering
gaps deep inside the backtest loop.

Usage:
    python check_data_alignment.py
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
EQUITY_RETURNS_PATH = DATA_DIR / "equity_returns_monthly.csv"
FRED_PATH = DATA_DIR / "fred_regime_signals.csv"


def load_data():
    equity = pd.read_csv(EQUITY_RETURNS_PATH, index_col=0, parse_dates=True)
    fred = pd.read_csv(FRED_PATH, index_col=0, parse_dates=True)
    return equity, fred


def report_coverage(df, name):
    print(f"\n--- {name} ---")
    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            print(f"  {col}: NO DATA")
            continue
        print(f"  {col}: {series.index.min().date()} to {series.index.max().date()} "
              f"({len(series)} non-null obs)")


def report_missing_months(df, name):
    """
    Flags any month within a series' own start-to-end range that is
    NaN. A few scattered gaps near the present are usually just
    publication lag (e.g. CPI is released with a delay) and are safe to
    forward-fill. Gaps in the middle of the series are worth investigating.
    """
    print(f"\n--- {name}: missing months within each series' own range ---")
    any_gaps = False
    for col in df.columns:
        series = df[col]
        valid = series.dropna()
        if valid.empty:
            continue
        full_range = pd.date_range(valid.index.min(), valid.index.max(), freq="MS")
        missing = full_range.difference(valid.index.union(series.index[series.notna()]))
        # recompute cleanly: months in [min,max] where value is NaN
        windowed = series.reindex(full_range)
        missing = windowed[windowed.isna()].index
        if len(missing):
            any_gaps = True
            missing_str = ", ".join(d.strftime("%Y-%m") for d in missing)
            print(f"  {col}: {len(missing)} missing month(s) -> {missing_str}")
    if not any_gaps:
        print("  None found.")


def report_alignment(equity, fred):
    """
    Checks whether the equity and FRED monthly indices actually line up
    (same day-of-month convention, no unexpected offset).
    """
    print("\n--- Index alignment check (equity vs. FRED) ---")
    print(f"  Equity index range: {equity.index.min().date()} to {equity.index.max().date()}")
    print(f"  FRED index range:   {fred.index.min().date()} to {fred.index.max().date()}")

    eq_days = equity.index.day.unique()
    fred_days = fred.index.day.unique()
    print(f"  Equity day-of-month values used: {sorted(eq_days)}")
    print(f"  FRED day-of-month values used:   {sorted(fred_days)}")
    if set(eq_days) != set(fred_days):
        print("  WARNING: equity and FRED indices use different day-of-month "
              "conventions (likely month-end vs. month-start). Reindex one "
              "to match the other before merging, or you'll get silent "
              "misalignment when joining on date.")
    else:
        print("  OK: consistent day-of-month convention.")

    overlap_start = max(equity.index.min(), fred.index.min())
    overlap_end = min(equity.index.max(), fred.index.max())
    print(f"\n  Usable overlap window for a combined backtest: "
          f"{overlap_start.date()} to {overlap_end.date()}")


def recommend_next_steps(fred):
    print("\n--- Recommendations ---")
    if "BAMLH0A0HYM2" in fred.columns:
        series = fred["BAMLH0A0HYM2"].dropna()
        if not series.empty and series.index.min().year >= 2022:
            print("  - BAMLH0A0HYM2 (credit spread) only covers "
                  f"{series.index.min().date()} onward. This is a real FRED "
                  "policy change (ICE BofA series restricted to a rolling "
                  "3-year window as of April 2026), not a pull error. "
                  "Consider swapping to BAA10Y (Moody's Baa spread, full "
                  "history back to 1986, not subject to this restriction) "
                  "if you want credit-stress regime classification further "
                  "back than 2023.")
    if "DTWEXBGS" in fred.columns:
        series = fred["DTWEXBGS"].dropna()
        if not series.empty:
            print(f"  - DTWEXBGS (dollar index) starts {series.index.min().date()}, "
                  "which is later than your 1995 equity data start. This "
                  "constrains any dollar-strength regime classification to "
                  "post-2006, or you accept a shorter combined backtest window.")


if __name__ == "__main__":
    equity, fred = load_data()
    report_coverage(equity, "Equity monthly returns")
    report_coverage(fred, "FRED regime signals")
    report_missing_months(fred, "FRED regime signals")
    report_alignment(equity, fred)
    recommend_next_steps(fred)


