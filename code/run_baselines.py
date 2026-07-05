"""
Walk-forward backtest for the baseline strategies: equal weight,
cap-weighted index, minimum variance, mean-variance, risk parity,
momentum.

Design choices (matching Section 4 of the checklist):
    - 60-month trailing lookback window for covariance/mean estimation
    - Monthly rebalancing
    - Flat 5 bps one-way transaction cost on turnover, applied uniformly
      to every strategy for a fair comparison
    - No turnover cap applied here (that constraint is specific to the
      main CVaR optimization model per Section 4 -- baselines rebalance
      fully to target each month)
    - 25% single-name position cap for min-variance, mean-variance, and
      risk parity (NOT applied to equal-weight, cap-weighted, or
      momentum, which are meant to show what unconstrained/naive
      benchmarks look like)

Usage:
    python run_baselines.py
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from portfolio_construction import (
    equal_weight, cap_weight, min_variance, mean_variance,
    risk_parity, momentum,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
RETURNS_PATH = DATA_DIR / "equity_returns_monthly.csv"
SHARES_PATH = DATA_DIR / "shares_outstanding.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOOKBACK = 60  # months
TXN_COST_BPS = 5  # one-way, in basis points


def load_data():
    returns = pd.read_csv(RETURNS_PATH, index_col=0, parse_dates=True)
    shares = None
    if SHARES_PATH.exists():
        shares = pd.read_csv(SHARES_PATH, index_col=0)["shares_outstanding"]
        shares = shares.reindex(returns.columns)
    return returns, shares


def run_backtest(returns, shares):
    dates = returns.index
    n_assets = returns.shape[1]
    tickers = returns.columns.tolist()
    txn_cost = TXN_COST_BPS / 10000.0

    strategies = ["equal_weight", "cap_weighted", "min_variance",
                  "mean_variance", "risk_parity", "momentum"]
    prev_weights = {s: np.zeros(n_assets) for s in strategies}
    net_returns = {s: [] for s in strategies}
    turnover_history = {s: [] for s in strategies}
    result_dates = []

    # We need: 60 months of trailing returns to estimate cov/mu, plus we
    # need a price level to compute cap-weights at each date (approximated
    # via cumulative return from period 0, scaled by shares outstanding).
    cum_price_proxy = (1 + returns).cumprod()

    for t in range(LOOKBACK, len(dates) - 1):
        window = returns.iloc[t - LOOKBACK:t]
        cov = window.cov().values * 12  # annualize for numerical stability
        mu = window.mean().values * 12

        trailing_12mo = (1 + returns.iloc[t - 12:t]).prod().values - 1

        weights = {}
        weights["equal_weight"] = equal_weight(n_assets)

        if shares is not None and shares.notna().all():
            caps_now = cum_price_proxy.iloc[t].values * shares.values
            weights["cap_weighted"] = cap_weight(caps_now)
        else:
            weights["cap_weighted"] = equal_weight(n_assets)  # fallback

        weights["min_variance"] = min_variance(cov)
        weights["mean_variance"] = mean_variance(mu, cov)
        weights["risk_parity"] = risk_parity(cov)
        weights["momentum"] = momentum(trailing_12mo)

        next_month_return = returns.iloc[t + 1].values
        result_dates.append(dates[t + 1])

        for s in strategies:
            w = weights[s]
            turnover = np.abs(w - prev_weights[s]).sum()
            gross_return = w @ next_month_return
            cost_drag = turnover * txn_cost
            net_return = gross_return - cost_drag

            net_returns[s].append(net_return)
            turnover_history[s].append(turnover)
            prev_weights[s] = w

    returns_df = pd.DataFrame(net_returns, index=result_dates)
    turnover_df = pd.DataFrame(turnover_history, index=result_dates)
    return returns_df, turnover_df


def compute_metrics(returns_df, turnover_df):
    metrics = {}
    for col in returns_df.columns:
        r = returns_df[col]
        ann_return = (1 + r).prod() ** (12 / len(r)) - 1
        ann_vol = r.std() * np.sqrt(12)
        sharpe = ann_return / ann_vol if ann_vol > 0 else np.nan

        downside = r[r < 0]
        downside_vol = downside.std() * np.sqrt(12) if len(downside) > 0 else np.nan
        sortino = ann_return / downside_vol if downside_vol and downside_vol > 0 else np.nan

        cum = (1 + r).cumprod()
        running_max = cum.cummax()
        drawdown = (cum - running_max) / running_max
        max_dd = drawdown.min()

        avg_turnover = turnover_df[col].mean()

        metrics[col] = {
            "ann_return": ann_return,
            "ann_vol": ann_vol,
            "sharpe": sharpe,
            "sortino": sortino,
            "max_drawdown": max_dd,
            "avg_monthly_turnover": avg_turnover,
        }
    return pd.DataFrame(metrics).T


if __name__ == "__main__":
    returns, shares = load_data()
    print(f"Loaded {returns.shape[1]} assets, {returns.shape[0]} months "
          f"({returns.index.min().date()} to {returns.index.max().date()})")
    if shares is None:
        print("WARNING: shares_outstanding.csv not found -- cap-weighted "
              "index will fall back to equal weight. Run pull_market_caps.py "
              "first for a real cap-weighted benchmark.")

    returns_df, turnover_df = run_backtest(returns, shares)
    metrics = compute_metrics(returns_df, turnover_df)

    pd.set_option("display.float_format", lambda x: f"{x:.4f}")
    print("\n=== Baseline strategy performance "
          f"({returns_df.index.min().date()} to {returns_df.index.max().date()}) ===")
    print(metrics)

    returns_df.to_csv(OUTPUT_DIR / "baseline_returns.csv")
    metrics.to_csv(OUTPUT_DIR / "baseline_metrics.csv")
    print(f"\nSaved monthly returns to {OUTPUT_DIR / 'baseline_returns.csv'}")
    print(f"Saved metrics to {OUTPUT_DIR / 'baseline_metrics.csv'}")



