"""
Walk-forward backtest for Historical CVaR (rho=0, uniform scenario
weights) -- the "Historical CVaR" row in Table 2's benchmark set, and the
baseline half of the paper's primary comparison (Historical CVaR vs
Regime-aware CVaR).

Same 60-month lookback and monthly rebalancing as the other baselines,
same 5bps transaction-cost treatment (applied post-hoc to realized
returns), but now with the position cap, sector cap, and turnover cap
enforced INSIDE the optimization (per Section 4), rather than just
measured afterward.

Usage:
    python run_cvar_historical.py
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cvar_model import cvar_weights, build_sector_index_groups

DATA_DIR = Path(__file__).resolve().parent / "data"
RETURNS_PATH = DATA_DIR / "equity_returns_monthly.csv"
REGIME_PATH = DATA_DIR / "regime_labels.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOOKBACK = 60
TXN_COST_BPS = 5
ALPHA = 0.95  # CVaR confidence level, draft value from checklist Section 3


def load_data():
    returns = pd.read_csv(RETURNS_PATH, index_col=0, parse_dates=True)
    regimes = None
    if REGIME_PATH.exists():
        regimes = pd.read_csv(REGIME_PATH, index_col=0, parse_dates=True).iloc[:, 0]
        regimes = regimes.reindex(returns.index).fillna("insufficient_history")
    return returns, regimes


def run_backtest(returns, regimes=None):
    dates = returns.index
    tickers = returns.columns.tolist()
    n_assets = len(tickers)
    txn_cost = TXN_COST_BPS / 10000.0
    sector_groups = build_sector_index_groups(tickers)

    prev_weights = np.zeros(n_assets)
    net_returns = []
    turnover_history = []
    cvar_values = []
    weight_history = []
    regime_at_rebalance = []
    result_dates = []

    for t in range(LOOKBACK, len(dates) - 1):
        window_returns = returns.iloc[t - LOOKBACK:t].values

        w, cvar_val = cvar_weights(
            window_returns, alpha=ALPHA, prev_weights=prev_weights,
            scenario_weights=None,  # None = uniform = ordinary historical CVaR
            sector_groups=sector_groups,
        )

        next_month_return = returns.iloc[t + 1].values
        turnover = np.abs(w - prev_weights).sum()
        gross_return = w @ next_month_return
        net_return = gross_return - turnover * txn_cost

        net_returns.append(net_return)
        turnover_history.append(turnover)
        cvar_values.append(cvar_val)
        weight_history.append(w)
        if regimes is not None:
            regime_at_rebalance.append(regimes.iloc[t - 1])
        result_dates.append(dates[t + 1])
        prev_weights = w

    returns_series = pd.Series(net_returns, index=result_dates, name="historical_cvar")
    turnover_series = pd.Series(turnover_history, index=result_dates, name="turnover")
    cvar_series = pd.Series(cvar_values, index=result_dates, name="cvar_estimate")
    weights_df = pd.DataFrame(weight_history, index=result_dates, columns=tickers)
    regime_series = pd.Series(regime_at_rebalance, index=result_dates, name="regime_at_decision") if regimes is not None else None

    return returns_series, turnover_series, cvar_series, weights_df, regime_series


def compute_metrics(r):
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

    return {
        "ann_return": ann_return, "ann_vol": ann_vol, "sharpe": sharpe,
        "sortino": sortino, "max_drawdown": max_dd,
    }


if __name__ == "__main__":
    returns, regimes = load_data()
    print(f"Loaded {returns.shape[1]} assets, {returns.shape[0]} months "
          f"({returns.index.min().date()} to {returns.index.max().date()})")

    r, turnover, cvar_est, weights, regime_at_decision = run_backtest(returns, regimes)
    metrics = compute_metrics(r)

    print(f"\n=== Historical CVaR (alpha={ALPHA}, rho=0) performance "
          f"({r.index.min().date()} to {r.index.max().date()}) ===")
    for k, v in metrics.items():
        print(f"  {k:15s} {v:.4f}")
    print(f"  avg_turnover    {turnover.mean():.4f}")
    print(f"  avg_sector_max  {weights.max(axis=1).mean():.4f}  (largest single-name weight, averaged over time)")

    if regime_at_decision is not None:
        print("\n=== Performance by regime (at decision time) ===")
        combined = pd.DataFrame({"return": r, "regime": regime_at_decision})
        for regime_label, group in combined.groupby("regime"):
            print(f"  {regime_label:22s} n={len(group):4d}  "
                  f"mean monthly return={group['return'].mean():.4f}  "
                  f"vol={group['return'].std():.4f}")

    r.to_csv(OUTPUT_DIR / "historical_cvar_returns.csv")
    weights.to_csv(OUTPUT_DIR / "historical_cvar_weights.csv")
    turnover.to_csv(OUTPUT_DIR / "historical_cvar_turnover.csv")
    print(f"\nSaved returns, weights, and turnover to {OUTPUT_DIR}/")

