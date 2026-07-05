"""
Diagnostic: why does regime-conditioning on dollar-strength hurt
performance relative to ordinary historical CVaR?

Two angles:
  (A) Weight comparison: what does the optimizer actually do differently
      during dollar-strength decision months at rho=0 vs higher rho?
      Compares average per-ticker weight and portfolio concentration
      (Herfindahl-Hirschman Index).
  (B) Effective scenario count: "56 months total" doesn't mean 56 were
      available at every decision point. If dollar-strength months
      cluster in time (e.g. a specific multi-year dollar-surge episode),
      many individual 60-month trailing windows might contain very few
      dollar-strength scenarios to actually condition on, even though the
      full-sample count looks reasonable. This checks the distribution of
      "how many trailing scenarios matched" across all dollar-strength
      decision months.

Usage:
    python diagnose_dollar_strength.py [rho]
    (rho defaults to 3.0 -- the run where the effect is most pronounced;
    pass a different value to compare against a different rho run)
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
REGIME_PATH = DATA_DIR / "regime_labels.csv"

LOOKBACK = 60
TARGET_REGIME = "dollar_strength"


def load_weights(rho):
    hist_path = RESULTS_DIR / "historical_cvar_weights.csv"
    suffix = f"rho{rho}".replace(".", "p")
    regime_path = RESULTS_DIR / f"regime_cvar_weights_{suffix}.csv"

    if not hist_path.exists():
        raise FileNotFoundError(f"{hist_path} not found -- run run_cvar_historical.py first")
    if not regime_path.exists():
        raise FileNotFoundError(f"{regime_path} not found -- run "
                                 f"'python run_cvar_regime_aware.py {rho}' first")

    w_hist = pd.read_csv(hist_path, index_col=0, parse_dates=True)
    w_regime = pd.read_csv(regime_path, index_col=0, parse_dates=True)
    return w_hist, w_regime


def herfindahl(weights_df):
    """Portfolio concentration: sum of squared weights, averaged over rows.
    Higher = more concentrated. Equal-weight-12 baseline = 1/12 = 0.083."""
    return (weights_df ** 2).sum(axis=1)


def weight_comparison(w_hist, w_regime, regimes, rho):
    dollar_dates = regimes[regimes == TARGET_REGIME].index
    dollar_dates_hist = dollar_dates.intersection(w_hist.index)
    dollar_dates_regime = dollar_dates.intersection(w_regime.index)

    print(f"=== (A) Weight comparison during {TARGET_REGIME} decision months ===")
    print(f"  {len(dollar_dates_hist)} dollar-strength months found in the backtest period\n")

    avg_hist = w_hist.loc[dollar_dates_hist].mean()
    avg_regime = w_regime.loc[dollar_dates_regime].mean()
    diff = (avg_regime - avg_hist).sort_values()

    print(f"  Average weight per ticker during {TARGET_REGIME} months:")
    print(f"  {'Ticker':8s} {'rho=0':>8s} {'rho=' + str(rho):>8s} {'Diff':>8s}")
    for ticker in diff.index:
        print(f"  {ticker:8s} {avg_hist[ticker]:8.3f} {avg_regime[ticker]:8.3f} {diff[ticker]:+8.3f}")

    hhi_hist = herfindahl(w_hist.loc[dollar_dates_hist]).mean()
    hhi_regime = herfindahl(w_regime.loc[dollar_dates_regime]).mean()
    print(f"\n  Avg concentration (HHI, higher=more concentrated):")
    print(f"    rho=0:        {hhi_hist:.4f}")
    print(f"    rho={rho}:  {hhi_regime:.4f}")
    print(f"    (equal-weight-12 baseline = {1/12:.4f})")

    biggest_overweight = diff.idxmax()
    biggest_underweight = diff.idxmin()
    print(f"\n  Biggest overweight vs rho=0: {biggest_overweight} ({diff[biggest_overweight]:+.3f})")
    print(f"  Biggest underweight vs rho=0: {biggest_underweight} ({diff[biggest_underweight]:+.3f})")


def effective_scenario_count(regimes):
    print(f"\n=== (B) Effective {TARGET_REGIME} scenario count per decision month ===")
    dollar_dates = regimes[regimes == TARGET_REGIME].index

    counts = []
    for date in dollar_dates:
        loc = regimes.index.get_loc(date)
        if loc < LOOKBACK:
            continue  # not enough trailing history yet
        window = regimes.iloc[loc - LOOKBACK:loc]
        match_count = (window == TARGET_REGIME).sum()
        counts.append(match_count)

    counts = pd.Series(counts)
    print(f"  Across {len(counts)} {TARGET_REGIME} decision months, the number of "
          f"matching scenarios in that month's trailing {LOOKBACK}-month window:")
    print(f"    min:    {counts.min()}")
    print(f"    median: {counts.median()}")
    print(f"    mean:   {counts.mean():.1f}")
    print(f"    max:    {counts.max()}")
    thin = (counts <= 5).sum()
    print(f"\n  {thin} of {len(counts)} decision months ({100*thin/len(counts):.0f}%) had "
          f"5 or fewer matching scenarios to condition on in that specific window --")
    print("  even though the aggregate full-sample count (56 months) looks reasonable, "
          "individual decision points may be conditioning on a very thin, clustered "
          "subset if dollar-strength months aren't evenly spread across the 30-year sample.")


if __name__ == "__main__":
    rho = sys.argv[1] if len(sys.argv) > 1 else "3.0"

    regimes = pd.read_csv(REGIME_PATH, index_col=0, parse_dates=True).iloc[:, 0]
    w_hist, w_regime = load_weights(rho)

    weight_comparison(w_hist, w_regime, regimes, rho)
    effective_scenario_count(regimes)




