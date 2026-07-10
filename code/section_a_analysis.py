"""
Section A analysis: closes the small analysis gaps from the remaining-work
checklist before building figures / writing the paper.

Covers:
    A1. VaR (eta) reported explicitly -- already saved per-strategy by
        run_cvar_historical.py / run_cvar_regime_aware.py as *_var.csv;
        this script just summarizes it.
    A2. Transaction-cost drag, reported explicitly, for all 8 strategies.
    A3. Regime-stratified performance for the six baselines (not just CVaR).
    A4. Unclassified-bucket check: does it behave like tranquil?
    A5. Sector cap sanity check: does the 30% cap ever bind?

Assumes run_cvar_historical.py and run_cvar_regime_aware.py (all four rho
values) have already been (re-)run so that results/ contains the
*_var.csv, *_regime_at_decision*.csv, and turnover files this script reads.

Usage:
    python section_a_analysis.py
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

DATA_DIR = Path(__file__).resolve().parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
OUT_DIR = RESULTS_DIR / "section_a"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TXN_COST_BPS = 5
TXN_COST = TXN_COST_BPS / 10000.0

SECTOR_GROUPS = {
    "healthcare_pharma": ["JNJ", "PFE"],
    "consumer_staples": ["PG", "KO"],
    "technology": ["MSFT", "IBM"],
    "industrials": ["CAT", "MMM"],
}
SECTOR_CAP = 0.30

RHO_SUFFIXES = ["rho0p5", "rho1p0", "rho2p0", "rho3p0"]


def ann_return(r):
    return (1 + r).prod() ** (12 / len(r)) - 1


def summarize_var():
    rows = {}
    hist_var = pd.read_csv(RESULTS_DIR / "historical_cvar_var.csv", index_col=0).iloc[:, 0]
    rows["historical_cvar (rho=0)"] = {
        "mean_VaR": hist_var.mean(), "median_VaR": hist_var.median(),
        "min_VaR": hist_var.min(), "max_VaR": hist_var.max(),
    }
    for suffix in RHO_SUFFIXES:
        path = RESULTS_DIR / f"regime_cvar_var_{suffix}.csv"
        if not path.exists():
            continue
        v = pd.read_csv(path, index_col=0).iloc[:, 0]
        rho_label = suffix.replace("rho", "rho=").replace("p", ".")
        rows[f"regime_cvar ({rho_label})"] = {
            "mean_VaR": v.mean(), "median_VaR": v.median(),
            "min_VaR": v.min(), "max_VaR": v.max(),
        }
    df = pd.DataFrame(rows).T
    df.to_csv(OUT_DIR / "var_summary.csv")
    return df


def txn_cost_drag():
    rows = {}
    metrics = pd.read_csv(RESULTS_DIR / "baseline_metrics.csv", index_col=0)
    baseline_returns = pd.read_csv(RESULTS_DIR / "baseline_returns.csv", index_col=0, parse_dates=True)
    for strat in baseline_returns.columns:
        avg_turnover = metrics.loc[strat, "avg_monthly_turnover"]
        avg_monthly_drag = avg_turnover * TXN_COST
        net = baseline_returns[strat]
        ann_net = ann_return(net)
        approx_ann_drag = avg_monthly_drag * 12
        rows[strat] = {
            "avg_monthly_turnover": avg_turnover,
            "avg_monthly_cost_drag": avg_monthly_drag,
            "approx_annualized_drag": approx_ann_drag,
            "ann_net_return": ann_net,
            "approx_ann_gross_return": ann_net + approx_ann_drag,
        }

    def exact_drag(name, returns_path, turnover_path):
        r = pd.read_csv(returns_path, index_col=0, parse_dates=True).iloc[:, 0]
        turnover = pd.read_csv(turnover_path, index_col=0, parse_dates=True).iloc[:, 0]
        cost = turnover * TXN_COST
        gross = r + cost
        ann_net = ann_return(r)
        ann_gross = ann_return(gross)
        rows[name] = {
            "avg_monthly_turnover": turnover.mean(),
            "avg_monthly_cost_drag": cost.mean(),
            "approx_annualized_drag": ann_gross - ann_net,
            "ann_net_return": ann_net,
            "approx_ann_gross_return": ann_gross,
        }

    exact_drag(
        "historical_cvar (rho=0)",
        RESULTS_DIR / "historical_cvar_returns.csv",
        RESULTS_DIR / "historical_cvar_turnover.csv",
    )
    for suffix in RHO_SUFFIXES:
        rp = RESULTS_DIR / f"regime_cvar_returns_{suffix}.csv"
        tp = RESULTS_DIR / f"regime_cvar_turnover_{suffix}.csv"
        if rp.exists() and tp.exists():
            rho_label = suffix.replace("rho", "rho=").replace("p", ".")
            exact_drag(f"regime_cvar ({rho_label})", rp, tp)

    df = pd.DataFrame(rows).T
    df.to_csv(OUT_DIR / "txn_cost_drag.csv")
    return df


def regime_stratified_baselines():
    baseline_returns = pd.read_csv(RESULTS_DIR / "baseline_returns.csv", index_col=0, parse_dates=True)
    regime = pd.read_csv(RESULTS_DIR / "historical_cvar_regime_at_decision.csv", index_col=0, parse_dates=True).iloc[:, 0]

    assert baseline_returns.index.equals(regime.index), (
        "Baseline return dates and regime_at_decision dates don't line up -- "
        "check LOOKBACK/date construction consistency between run_baselines.py "
        "and run_cvar_historical.py before trusting this table."
    )

    hist_cvar = pd.read_csv(RESULTS_DIR / "historical_cvar_returns.csv", index_col=0, parse_dates=True).iloc[:, 0]
    regime_cvar_1 = pd.read_csv(RESULTS_DIR / "regime_cvar_returns_rho1p0.csv", index_col=0, parse_dates=True).iloc[:, 0]

    all_strats = baseline_returns.copy()
    all_strats["historical_cvar"] = hist_cvar
    all_strats["regime_cvar_rho1.0"] = regime_cvar_1

    records = []
    for regime_label, idx in regime.groupby(regime).groups.items():
        for strat in all_strats.columns:
            r = all_strats.loc[idx, strat]
            records.append({
                "regime": regime_label,
                "strategy": strat,
                "n_months": len(r),
                "mean_monthly_return": r.mean(),
                "monthly_vol": r.std(),
                "ann_return_in_regime": r.mean() * 12,
            })
    df = pd.DataFrame(records)
    pivot = df.pivot(index="strategy", columns="regime", values="mean_monthly_return")
    df.to_csv(OUT_DIR / "regime_stratified_all_strategies_long.csv", index=False)
    pivot.to_csv(OUT_DIR / "regime_stratified_all_strategies_pivot.csv")
    return df, pivot


def unclassified_vs_tranquil():
    hist_cvar = pd.read_csv(RESULTS_DIR / "historical_cvar_returns.csv", index_col=0, parse_dates=True).iloc[:, 0]
    regime = pd.read_csv(RESULTS_DIR / "historical_cvar_regime_at_decision.csv", index_col=0, parse_dates=True).iloc[:, 0]

    tranquil = hist_cvar[regime == "tranquil"]
    unclassified = hist_cvar[regime == "unclassified"]

    t_stat, p_value_mean = stats.ttest_ind(unclassified, tranquil, equal_var=False)
    f_stat = np.var(unclassified, ddof=1) / np.var(tranquil, ddof=1)
    levene_stat, p_value_var = stats.levene(unclassified, tranquil)

    result = {
        "tranquil_n": len(tranquil),
        "tranquil_mean_monthly_return": tranquil.mean(),
        "tranquil_vol": tranquil.std(),
        "unclassified_n": len(unclassified),
        "unclassified_mean_monthly_return": unclassified.mean(),
        "unclassified_vol": unclassified.std(),
        "welch_t_stat": t_stat,
        "welch_p_value_mean_diff": p_value_mean,
        "variance_ratio_unclassified_over_tranquil": f_stat,
        "levene_stat": levene_stat,
        "levene_p_value_var_diff": p_value_var,
    }
    df = pd.DataFrame([result])
    df.to_csv(OUT_DIR / "unclassified_vs_tranquil.csv", index=False)
    return result


def sector_cap_check():
    weight_files = {
        "historical_cvar (rho=0)": RESULTS_DIR / "historical_cvar_weights.csv",
    }
    for suffix in RHO_SUFFIXES:
        p = RESULTS_DIR / f"regime_cvar_weights_{suffix}.csv"
        if p.exists():
            rho_label = suffix.replace("rho", "rho=").replace("p", ".")
            weight_files[f"regime_cvar ({rho_label})"] = p

    records = []
    for strat_name, path in weight_files.items():
        w = pd.read_csv(path, index_col=0, parse_dates=True)
        for sector, tickers in SECTOR_GROUPS.items():
            sector_sum = w[tickers].sum(axis=1)
            records.append({
                "strategy": strat_name,
                "sector": sector,
                "max_sector_weight": sector_sum.max(),
                "mean_sector_weight": sector_sum.mean(),
                "months_within_1pt_of_cap": int((sector_sum >= SECTOR_CAP - 0.01).sum()),
                "months_at_cap": int((sector_sum >= SECTOR_CAP - 0.001).sum()),
                "total_months": len(sector_sum),
            })
    df = pd.DataFrame(records)
    df.to_csv(OUT_DIR / "sector_cap_check.csv", index=False)
    return df


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.4f}")
    pd.set_option("display.width", 140)

    print("=== A1. VaR (eta) summary ===")
    var_df = summarize_var()
    print(var_df)

    print("\n=== A2. Transaction-cost drag ===")
    drag_df = txn_cost_drag()
    print(drag_df)

    print("\n=== A3. Regime-stratified performance, all strategies (pivot) ===")
    long_df, pivot_df = regime_stratified_baselines()
    print(pivot_df)

    print("\n=== A4. Unclassified vs tranquil ===")
    result = unclassified_vs_tranquil()
    for k, v in result.items():
        print(f"  {k:45s} {v}")

    print("\n=== A5. Sector cap sanity check ===")
    sector_df = sector_cap_check()
    print(sector_df.to_string(index=False))

    print(f"\nAll Section A outputs saved to {OUT_DIR}/")
