"""
Build monthly regime labels using the draft threshold rule from Section 3
of pre_data_collection_checklist_draft.md (Formula 3/4 in the outline).

Regime feature vector:
    - Equity momentum: 12-month trailing return on SPY
    - Volatility: VIX level
    - Yield-curve slope: T10Y2Y (not currently used in the threshold rule
      itself, but kept available for later robustness checks)
    - Credit stress: BAA10Y (primary; BAMLH0A0HYM2 is the 2023+ robustness
      check, applied separately -- see compare_credit_spread_robustness.py)
    - Dollar momentum: spliced 6-month momentum (DTWEXB + DTWEXBGS)
    - Inflation: 12-month CPI change (pulled in but not yet used by the
      draft threshold rule -- available for future regime refinements)

Threshold rule kappa(.) -- UPDATED tie-break (was fixed priority order,
now margin-based per user decision after reviewing real-data spot-checks):
    - rate-shock:       |MoM change in DGS10| > trailing 3yr 90th pct
    - risk-off:         VIX > trailing 3yr 75th pct
    - dollar-strength:  6mo dollar momentum > trailing 3yr 75th pct
    - tranquil/risk-on: VIX < trailing 3yr median AND equity momentum > 0
      (checked only if none of the three stress conditions triggered)
    - TIE-BREAK: if more than one of {rate-shock, risk-off, dollar-strength}
      triggers in the same month, classify by whichever condition is
      exceeded by the largest margin -- measured as each variable's
      percentile rank within its own trailing 36-month window, minus its
      trigger threshold (90 for rate-shock, 75 for the other two). This
      puts VIX levels, rate-of-change in yields, and dollar momentum on a
      common 0-100 scale so they're comparable despite being different
      units. Previously this used a fixed priority order (rate-shock >
      risk-off > dollar-strength), which caused March 2020 (COVID) to be
      classified rate-shock even though it's more commonly understood as
      the canonical risk-off/volatility event -- margin-based tie-breaking
      fixes that by asking which signal was actually MORE extreme that
      month, rather than which category is checked first.
    - anything matching none of the above is labeled "unclassified" -- left
      as its own category for now (per user decision), to revisit once
      backtest results are available rather than force a definition now.

All rolling windows are 36-month trailing, inclusive of the current month
(no look-ahead: only past-and-current data is used to set each month's
thresholds and percentile ranks).

Usage:
    python build_regime_labels.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
FRED_PATH = DATA_DIR / "fred_regime_signals.csv"
DOLLAR_MOM_PATH = DATA_DIR / "dollar_momentum_spliced.csv"
SPY_PATH = DATA_DIR / "spy_prices_monthly.csv"
OUTPUT_PATH = DATA_DIR / "regime_labels.csv"

ROLL_WINDOW = 36  # months, i.e. trailing 3 years

RATE_SHOCK_PCT = 90
RISK_OFF_PCT = 75
DOLLAR_STRENGTH_PCT = 75


def build_feature_frame():
    fred = pd.read_csv(FRED_PATH, index_col=0, parse_dates=True)
    dollar_mom = pd.read_csv(DOLLAR_MOM_PATH, index_col=0, parse_dates=True).iloc[:, 0]
    spy = pd.read_csv(SPY_PATH, index_col=0, parse_dates=True).iloc[:, 0]

    feat = pd.DataFrame(index=fred.index)
    feat["vix"] = fred["VIXCLS"]
    feat["dgs10"] = fred["DGS10"]
    feat["dgs10_mom_change"] = feat["dgs10"].diff(1)
    feat["credit_stress"] = fred["BAA10Y"]  # primary credit-stress series
    feat["cpi"] = fred["CPIAUCSL"].ffill()  # forward-fill the one known Oct-2025 gap
    feat["inflation_yoy"] = feat["cpi"].pct_change(12)
    feat["dollar_momentum"] = dollar_mom
    feat["equity_momentum"] = spy.pct_change(12)

    return feat.dropna(subset=["vix", "dgs10_mom_change"])  # keep rows with core inputs


def rolling_percentile_rank(series, window):
    """
    Percentile rank (0-100) of the current value within its own trailing
    `window`-month history, inclusive of the current month. Used so that
    VIX levels, rate-of-change in yields, and dollar momentum -- all
    different units -- can be compared on a common scale when breaking
    ties between simultaneously-triggered regime conditions.
    """
    def _rank(x):
        return (x <= x[-1]).mean() * 100

    return series.rolling(window, min_periods=window).apply(_rank, raw=True)


def classify_regimes(feat):
    w = ROLL_WINDOW

    vix_median = feat["vix"].rolling(w, min_periods=w).median()
    vix_p75 = feat["vix"].rolling(w, min_periods=w).quantile(0.75)
    rate_change_p90 = feat["dgs10_mom_change"].abs().rolling(w, min_periods=w).quantile(0.90)
    dollar_p75 = feat["dollar_momentum"].rolling(w, min_periods=w).quantile(0.75)

    ready = vix_median.notna() & rate_change_p90.notna() & dollar_p75.notna()

    is_rate_shock_trig = ready & (feat["dgs10_mom_change"].abs() > rate_change_p90)
    is_risk_off_trig = ready & (feat["vix"] > vix_p75)
    is_dollar_trig = ready & (feat["dollar_momentum"] > dollar_p75)

    # Percentile ranks for margin-based tie-breaking -- only computed where
    # needed (any month where 2+ conditions triggered simultaneously).
    rate_rank = rolling_percentile_rank(feat["dgs10_mom_change"].abs(), w)
    vix_rank = rolling_percentile_rank(feat["vix"], w)
    dollar_rank = rolling_percentile_rank(feat["dollar_momentum"], w)

    rate_margin = rate_rank - RATE_SHOCK_PCT
    risk_off_margin = vix_rank - RISK_OFF_PCT
    dollar_margin = dollar_rank - DOLLAR_STRENGTH_PCT

    labels = pd.Series(index=feat.index, dtype=object)
    labels[~ready] = "insufficient_history"

    margins = pd.DataFrame({
        "rate_shock": rate_margin.where(is_rate_shock_trig, -np.inf),
        "risk_off": risk_off_margin.where(is_risk_off_trig, -np.inf),
        "dollar_strength": dollar_margin.where(is_dollar_trig, -np.inf),
    })

    any_stress_triggered = ready & (is_rate_shock_trig | is_risk_off_trig | is_dollar_trig)
    winner = margins.loc[any_stress_triggered].idxmax(axis=1)
    labels.loc[any_stress_triggered] = winner

    no_stress = ready & ~any_stress_triggered
    is_tranquil = no_stress & (feat["vix"] < vix_median) & (feat["equity_momentum"] > 0)
    labels.loc[is_tranquil] = "tranquil"
    labels.loc[no_stress & ~is_tranquil] = "unclassified"

    return labels


def summarize(labels):
    print("=== Regime label counts (full sample) ===")
    counts = labels.value_counts()
    pct = (counts / len(labels) * 100).round(1)
    for label in counts.index:
        print(f"  {label:22s} {counts[label]:4d} months  ({pct[label]}%)")

    classified = labels[~labels.isin(["insufficient_history"])]
    print(f"\n=== Regime label counts (excluding the {ROLL_WINDOW}-month warm-up) ===")
    counts2 = classified.value_counts()
    pct2 = (counts2 / len(classified) * 100).round(1)
    for label in counts2.index:
        print(f"  {label:22s} {counts2[label]:4d} months  ({pct2[label]}%)")

    unclassified_pct = pct2.get("unclassified", 0.0)
    if unclassified_pct > 15:
        print(f"\nNOTE: {unclassified_pct}% of classified months fall into "
              "'unclassified' -- meaning they're neither risk-off, rate-shock, "
              "dollar-strength, nor tranquil under the draft rule. This is a "
              "real gap in the draft threshold rule (Section 3 of the "
              "checklist doesn't define a catch-all). Worth deciding: leave "
              "'unclassified' as its own regime, or loosen the tranquil "
              "definition to be the residual case (i.e. 'tranquil' = "
              "anything not risk-off/rate-shock/dollar-strength) instead of "
              "requiring VIX-below-median AND positive equity momentum "
              "simultaneously.")

    print("\n=== First and last 5 classified months ===")
    print(classified.head())
    print("...")
    print(classified.tail())


def diagnose_gaps(feat, labels):
    print("\n=== Diagnostic: NaN counts in each raw input (full sample) ===")
    for col in ["vix", "dgs10_mom_change", "dollar_momentum", "equity_momentum"]:
        n_nan = feat[col].isna().sum()
        print(f"  {col:18s} {n_nan} NaN month(s) out of {len(feat)}")

    # If insufficient_history is meaningfully larger than one clean 36-month
    # warm-up block, some of it is coming from scattered gaps mid-sample
    # rather than just the initial ramp-up.
    insufficient = labels[labels == "insufficient_history"]
    if len(insufficient) > ROLL_WINDOW + 5:  # small buffer for the dropna offset
        print(f"\n=== Diagnostic: insufficient_history dates beyond the initial "
              f"{ROLL_WINDOW}-month warm-up ===")
        first_classified_date = labels[labels != "insufficient_history"].index.min()
        late_gaps = insufficient[insufficient.index > first_classified_date]
        if len(late_gaps):
            print(f"  {len(late_gaps)} extra insufficient-history month(s) appear "
                  f"AFTER classification had already started on "
                  f"{first_classified_date.date()}:")
            print(f"  {[d.date().isoformat() for d in late_gaps.index]}")
            print("  This means a NaN somewhere in vix/dgs10_mom_change/"
                  "dollar_momentum/equity_momentum re-breaks the rolling "
                  "36-month window at these later dates. Check the NaN counts "
                  "above to see which column to investigate.")
        else:
            print("  None -- all insufficient_history months are a single "
                  "contiguous warm-up block at the start. (The count being "
                  "larger than 36 just reflects the dropna offset plus "
                  "dollar_momentum's later start date.)")


def spot_check_known_events(labels):
    print("\n=== Spot-check against known crisis periods ===")
    known_events = {
        "2001-09-01": "9/11 / dot-com bust aftermath",
        "2008-09-01": "Lehman collapse",
        "2008-10-01": "2008 crisis peak",
        "2011-08-01": "US downgrade / European debt crisis",
        "2018-12-01": "Dec 2018 selloff",
        "2020-03-01": "COVID crash",
        "2020-04-01": "COVID crash aftermath",
        "2022-06-01": "2022 rate-hike cycle",
        "2022-09-01": "2022 rate-hike cycle",
    }
    for date_str, description in known_events.items():
        date = pd.Timestamp(date_str)
        if date in labels.index:
            print(f"  {date_str} ({description}): {labels[date]}")
        else:
            print(f"  {date_str} ({description}): not in sample")


if __name__ == "__main__":
    feat = build_feature_frame()
    labels = classify_regimes(feat)
    summarize(labels)
    diagnose_gaps(feat, labels)
    spot_check_known_events(labels)
    labels.to_csv(OUTPUT_PATH, header=["regime"])
    print(f"\nSaved regime labels to {OUTPUT_PATH}")



