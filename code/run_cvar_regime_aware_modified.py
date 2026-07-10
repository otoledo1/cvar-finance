"""
Walk-forward backtest for Regime-Aware CVaR (rho>0) -- Formula (5)'s
regime-weighted scenario probabilities, layered on top of the same CVaR
epigraph optimizer used for Historical CVaR (rho=0). This is the other
half of the paper's primary comparison.

Formula (5):
    pi_s(t) = (1 + rho * 1{k_s = k_t}) / sum_q (1 + rho * 1{k_q = k_t})

Scenario s gets extra weight if its historical regime label k_s matches
the CURRENT month's regime k_t. rho=0 reduces this to uniform weights,
i.e. ordinary historical CVaR -- so this script and run_cvar_historical.py
are literally the same optimizer, differing only in scenario_weights.

Handling regime labels at the edges (matches the "insufficient_history"
and "unclassified" design from build_regime_labels.py):
    - If the CURRENT month's regime is "insufficient_history", there's no
      meaningful regime to condition on, so fall back to uniform weights
      for that month (equivalent to historical CVaR).
    - "insufficient_history" scenario months (only relevant in the very
      earliest rebalance windows) never receive the regime-match bonus,
      but still count in the scenario set with base weight, same as any
      non-matching scenario.
    - "unclassified" is treated as a legitimate 5th regime category (per
      the earlier decision to leave it as-is) -- it can match against
      itself like any other regime label.

Usage:
    python run_cvar_regime_aware.py [rho]
    (rho defaults to 1.0, the checklist's draft main setting; pass e.g.
    "python run_cvar_regime_aware.py 2" to run the rho=2 sensitivity check)
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cvar_model import cvar_weights, build_sector_index_groups

DATA_DIR = Path(__file__).resolve().parent / "data"
RETURNS_PATH = DATA_DIR / "equity_returns_monthly.csv"
REGIME_PATH = DATA_DIR / "regime_labels.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOOKBACK = 60
TXN_COST_BPS = 5
ALPHA = 0.95
DEFAULT_RHO = 1.0

NO_MATCH_LABELS = {"insufficient_history"}


def load_data():
    returns = pd.read_csv(RETURNS_PATH, index_col=0, parse_dates=True)
    regimes = pd.read_csv(REGIME_PATH, index_col=0, parse_dates=True).iloc[:, 0]
    regimes = regimes.reindex(returns.index).fillna("insufficient_history")
    return returns, regimes


def formula5_weights(scenario_regimes, current_regime, rho):
    N = len(scenario_regimes)
    if current_regime in NO_MATCH_LABELS:
        return np.full(N, 1.0 / N)  # no meaningful regime to condition on

    match = np.array([
        1.0 if (r == current_regime and r not in NO_MATCH_LABELS) else 0.0
        for r in scenario_regimes
    ])
    raw = 1.0 + rho * match
    return raw / raw.sum()


def run_backtest(returns, regimes, rho):
    dates = returns.index
    tickers = returns.columns.tolist()
    n_assets = len(tickers)
    txn_cost = TXN_COST_BPS / 10000.0
    sector_groups = build_sector_index_groups(tickers)

    prev_weights = np.zeros(n_assets)
    net_returns, turnover_history, cvar_values, var_values, weight_history = [], [], [], [], []
    regime_at_rebalance = []
    result_dates = []

    for t in range(LOOKBACK, len(dates) - 1):
        window_returns = returns.iloc[t - LOOKBACK:t].values
        window_regimes = regimes.iloc[t - LOOKBACK:t].values
        current_regime = regimes.iloc[t - 1]  # most recent known regime at decision time

        scenario_weights = formula5_weights(window_regimes, current_regime, rho)

        w, cvar_val, var_val = cvar_weights(
            window_returns, alpha=ALPHA, prev_weights=prev_weights,
            scenario_weights=scenario_weights,
            sector_groups=sector_groups,
        )

        next_month_return = returns.iloc[t + 1].values
        turnover = np.abs(w - prev_weights).sum()
        gross_return = w @ next_month_return
        net_return = gross_return - turnover * txn_cost

        net_returns.append(net_return)
        turnover_history.append(turnover)
        cvar_values.append(cvar_val)
        var_values.append(var_val)
        weight_history.append(w)
        regime_at_rebalance.append(current_regime)
        result_dates.append(dates[t + 1])
        prev_weights = w

    r = pd.Series(net_returns, index=result_dates, name=f"regime_cvar_rho{rho}")
    turnover_s = pd.Series(turnover_history, index=result_dates, name="turnover")
    cvar_s = pd.Series(cvar_values, index=result_dates, name="cvar_estimate")
    var_s = pd.Series(var_values, index=result_dates, name="var_estimate")
    weights_df = pd.DataFrame(weight_history, index=result_dates, columns=tickers)
    regime_s = pd.Series(regime_at_rebalance, index=result_dates, name="regime_at_decision")

    return r, turnover_s, cvar_s, var_s, weights_df, regime_s


def compute_metrics(r):
    ann_return = (1 + r).prod() ** (12 / len(r)) - 1
    ann_vol = r.std() * np.sqrt(12)
    sharpe = ann_return / ann_vol if ann_vol > 0 else np.nan
    downside = r[r < 0]
    downside_vol = downside.std() * np.sqrt(12) if len(downside) > 0 else np.nan
    sortino = ann_return / downside_vol if downside_vol and downside_vol > 0 else np.nan
    cum = (1 + r).cumprod()
    drawdown = (cum - cum.cummax()) / cum.cummax()
    max_dd = drawdown.min()
    return {"ann_return": ann_return, "ann_vol": ann_vol, "sharpe": sharpe,
            "sortino": sortino, "max_drawdown": max_dd}


if __name__ == "__main__":
    rho = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RHO

    returns, regimes = load_data()
    print(f"Loaded {returns.shape[1]} assets, {returns.shape[0]} months "
          f"({returns.index.min().date()} to {returns.index.max().date()})")
    print(f"Running Regime-Aware CVaR with rho={rho}")

    r, turnover, cvar_est, var_est, weights, regime_at_decision = run_backtest(returns, regimes, rho)
    metrics = compute_metrics(r)

    print(f"\n=== Regime-Aware CVaR (alpha={ALPHA}, rho={rho}) performance "
          f"({r.index.min().date()} to {r.index.max().date()}) ===")
    for k, v in metrics.items():
        print(f"  {k:15s} {v:.4f}")
    print(f"  avg_turnover    {turnover.mean():.4f}")
    print(f"  avg_VaR (eta)   {var_est.mean():.4f}")
    print(f"  avg_max_weight  {weights.max(axis=1).mean():.4f}")

    print("\n=== Performance by regime (at decision time) ===")
    combined = pd.DataFrame({"return": r, "regime": regime_at_decision})
    for regime_label, group in combined.groupby("regime"):
        print(f"  {regime_label:22s} n={len(group):4d}  "
              f"mean monthly return={group['return'].mean():.4f}  "
              f"vol={group['return'].std():.4f}")

    suffix = f"rho{rho}".replace(".", "p")
    r.to_csv(OUTPUT_DIR / f"regime_cvar_returns_{suffix}.csv")
    weights.to_csv(OUTPUT_DIR / f"regime_cvar_weights_{suffix}.csv")
    turnover.to_csv(OUTPUT_DIR / f"regime_cvar_turnover_{suffix}.csv")
    var_est.to_csv(OUTPUT_DIR / f"regime_cvar_var_{suffix}.csv")
    regime_at_decision.to_csv(OUTPUT_DIR / f"regime_cvar_regime_at_decision_{suffix}.csv")
    print(f"\nSaved results to {OUTPUT_DIR}/ (suffix: {suffix})")




