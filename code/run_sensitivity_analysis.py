"""
Sensitivity analysis for the Historical CVaR (rho=0) model -- Section 4's
pre-registered robustness checks: transaction costs, turnover cap,
lookback window, and CVaR confidence level (alpha). Run against rho=0
since that's the best-performing, primary result to stress-test.

One-factor-at-a-time design: each parameter is varied while holding the
other three at their base/draft values (alpha=0.95, lookback=60,
txn_cost=5bps, turnover_cap=0.20), matching how the checklist poses the
question ("how sensitive are results to X, Y, Z...").

Usage:
    python run_sensitivity_analysis.py
(takes a few minutes -- reruns the full walk-forward backtest ~12 times)
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cvar_model import cvar_weights, build_sector_index_groups

DATA_DIR = Path(__file__).resolve().parent / "data"
RETURNS_PATH = DATA_DIR / "equity_returns_monthly.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Base/draft configuration (matches the main historical CVaR run)
BASE_ALPHA = 0.95
BASE_LOOKBACK = 60
BASE_TXN_BPS = 5
BASE_TURNOVER_CAP = 0.20

# Sweep grids -- one factor varied at a time, others held at base
ALPHA_GRID = [0.90, 0.95, 0.99]
LOOKBACK_GRID = [36, 60]
TXN_BPS_GRID = [0, 5, 10, 20]
TURNOVER_CAP_GRID = [0.10, 0.20, 0.30, 2.0]  # 2.0 ~= effectively unconstrained


def load_data():
    return pd.read_csv(RETURNS_PATH, index_col=0, parse_dates=True)


def run_one_config(returns, alpha, lookback, txn_bps, turnover_cap):
    dates = returns.index
    tickers = returns.columns.tolist()
    n_assets = len(tickers)
    txn_cost = txn_bps / 10000.0
    sector_groups = build_sector_index_groups(tickers)

    prev_weights = np.zeros(n_assets)
    net_returns, turnover_history = [], []

    for t in range(lookback, len(dates) - 1):
        window_returns = returns.iloc[t - lookback:t].values
        w, _ = cvar_weights(
            window_returns, alpha=alpha, prev_weights=prev_weights,
            scenario_weights=None, sector_groups=sector_groups,
            turnover_cap=turnover_cap,
        )
        next_month_return = returns.iloc[t + 1].values
        turnover = np.abs(w - prev_weights).sum()
        net_return = w @ next_month_return - turnover * txn_cost

        net_returns.append(net_return)
        turnover_history.append(turnover)
        prev_weights = w

    r = pd.Series(net_returns, index=dates[lookback + 1:])
    turnover_s = pd.Series(turnover_history, index=dates[lookback + 1:])
    return r, turnover_s


def compute_metrics(r, turnover_s):
    ann_return = (1 + r).prod() ** (12 / len(r)) - 1
    ann_vol = r.std() * np.sqrt(12)
    sharpe = ann_return / ann_vol if ann_vol > 0 else np.nan
    cum = (1 + r).cumprod()
    max_dd = ((cum - cum.cummax()) / cum.cummax()).min()
    return {
        "ann_return": ann_return, "ann_vol": ann_vol, "sharpe": sharpe,
        "max_drawdown": max_dd, "avg_turnover": turnover_s.mean(),
    }


if __name__ == "__main__":
    returns = load_data()
    print(f"Loaded {returns.shape[1]} assets, {returns.shape[0]} months "
          f"({returns.index.min().date()} to {returns.index.max().date()})")

    results = {}
    t0 = time.time()

    print("\n--- Sweeping alpha (CVaR confidence level) ---")
    for alpha in ALPHA_GRID:
        r, turnover_s = run_one_config(returns, alpha, BASE_LOOKBACK, BASE_TXN_BPS, BASE_TURNOVER_CAP)
        results[f"alpha={alpha}"] = compute_metrics(r, turnover_s)
        print(f"  alpha={alpha} done ({time.time()-t0:.0f}s elapsed)")

    print("\n--- Sweeping lookback window ---")
    for lookback in LOOKBACK_GRID:
        r, turnover_s = run_one_config(returns, BASE_ALPHA, lookback, BASE_TXN_BPS, BASE_TURNOVER_CAP)
        results[f"lookback={lookback}mo"] = compute_metrics(r, turnover_s)
        print(f"  lookback={lookback} done ({time.time()-t0:.0f}s elapsed)")

    print("\n--- Sweeping transaction costs ---")
    for txn_bps in TXN_BPS_GRID:
        r, turnover_s = run_one_config(returns, BASE_ALPHA, BASE_LOOKBACK, txn_bps, BASE_TURNOVER_CAP)
        results[f"txn_cost={txn_bps}bps"] = compute_metrics(r, turnover_s)
        print(f"  txn_cost={txn_bps}bps done ({time.time()-t0:.0f}s elapsed)")

    print("\n--- Sweeping turnover cap ---")
    for turnover_cap in TURNOVER_CAP_GRID:
        label = "uncapped" if turnover_cap >= 1.0 else f"{turnover_cap}"
        r, turnover_s = run_one_config(returns, BASE_ALPHA, BASE_LOOKBACK, BASE_TXN_BPS, turnover_cap)
        results[f"turnover_cap={label}"] = compute_metrics(r, turnover_s)
        print(f"  turnover_cap={label} done ({time.time()-t0:.0f}s elapsed)")

    summary = pd.DataFrame(results).T
    pd.set_option("display.float_format", lambda x: f"{x:.4f}")
    print(f"\n=== Full sensitivity summary (base case: alpha={BASE_ALPHA}, "
          f"lookback={BASE_LOOKBACK}mo, txn={BASE_TXN_BPS}bps, "
          f"turnover_cap={BASE_TURNOVER_CAP}) ===")
    print(summary)

    summary.to_csv(OUTPUT_DIR / "sensitivity_analysis_summary.csv")
    print(f"\nSaved to {OUTPUT_DIR / 'sensitivity_analysis_summary.csv'}")
    print(f"Total runtime: {time.time()-t0:.0f}s")


