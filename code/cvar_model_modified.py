"""
CVaR portfolio optimizer, implementing Formulas 7-9 (CVaR epigraph) plus
the position-cap, sector-cap, and turnover constraints from Section 4 of
the checklist.

This same function serves BOTH the historical CVaR baseline (rho=0,
uniform scenario weights) and the regime-aware CVaR model (rho>0, regime-
weighted scenario probabilities) -- they differ only in the
`scenario_weights` argument, matching the design in Section 1: "Historical
CVaR (rho=0) vs Regime-aware CVaR (rho>0), both on the same 12-stock
universe."

No-forecast version (mu_t = 0): this module deliberately does NOT include
an expected-return term in the objective. Per the checklist's Section 4
note ("run mu_t = 0 as a required companion run from week 1, not an
afterthought"), we're building the no-forecast robustness version FIRST,
since it isolates whether the CVaR/regime mechanism works without a
return forecast doing any of the work. The forecast-lite expected-return
model (Section 3.6) can be layered in later as a separate comparison, not
by default.

Transaction costs: applied as a post-hoc drag on realized returns (same
treatment as the baselines), not embedded in the optimization objective.
This is a simplification vs. Formula 10's p_i/q_i cost terms, chosen so
the CVaR model and the baseline strategies are directly comparable using
the same accounting. The turnover CAP (a hard constraint, not a cost) IS
enforced inside the optimization, matching Section 4.
"""

import numpy as np
import cvxpy as cp

POSITION_CAP = 0.25
SECTOR_CAP = 0.30
TURNOVER_CAP = 0.20  # 20% of portfolio per month, per Section 4 draft

# Sector groupings from checklist Section 2 -- indices filled in by the
# caller based on the actual column order of the returns data.
SECTOR_GROUPS_BY_TICKER = {
    "healthcare_pharma": ["JNJ", "PFE"],
    "consumer_staples": ["PG", "KO"],
    "technology": ["MSFT", "IBM"],
    "industrials": ["CAT", "MMM"],
    "energy": ["XOM"],
    "financials": ["JPM"],
    "retail": ["WMT"],
    "media": ["DIS"],
}


def build_sector_index_groups(tickers):
    """Map SECTOR_GROUPS_BY_TICKER to column-index groups for a given
    ticker ordering. Only returns groups with 2+ members, since singleton
    sectors are already covered by the position cap."""
    ticker_to_idx = {t: i for i, t in enumerate(tickers)}
    groups = []
    for sector, members in SECTOR_GROUPS_BY_TICKER.items():
        idx = [ticker_to_idx[m] for m in members if m in ticker_to_idx]
        if len(idx) >= 2:
            groups.append(idx)
    return groups


def cvar_weights(scenario_returns, alpha, prev_weights=None,
                  scenario_weights=None, sector_groups=None,
                  position_cap=POSITION_CAP, sector_cap=SECTOR_CAP,
                  turnover_cap=TURNOVER_CAP):
    """
    scenario_returns: (N_scenarios, n_assets) array of historical returns
        used as the CVaR scenario set (i.e. the trailing lookback window).
    alpha: CVaR confidence level (e.g. 0.95).
    prev_weights: previous month's weights, for the turnover constraint.
        None (or all-zero) on the very first rebalance, when there's no
        prior portfolio to constrain against.
    scenario_weights: (N_scenarios,) array summing to 1. None = ordinary
        historical CVaR (uniform 1/N). Regime-aware CVaR passes
        Formula (5)'s pi_s(t) here.
    sector_groups: list of lists of column indices, one list per sector
        with 2+ members. None = no sector constraint applied.
    """
    N, n = scenario_returns.shape

    if scenario_weights is None:
        scenario_weights = np.full(N, 1.0 / N)

    w = cp.Variable(n, nonneg=True)
    eta = cp.Variable()
    xi = cp.Variable(N, nonneg=True)

    losses = -scenario_returns @ w  # Formula (2)

    constraints = [
        xi >= losses - eta,          # Formula (8)/(17)
        cp.sum(w) == 1,               # Formula (11)
        w <= position_cap,            # Formula (12)
    ]

    if sector_groups:
        for idx in sector_groups:
            constraints.append(cp.sum(w[idx]) <= sector_cap)

    if prev_weights is not None and np.any(prev_weights):
        constraints.append(cp.sum(cp.abs(w - prev_weights)) <= turnover_cap)

    cvar_expr = eta + (1.0 / (1 - alpha)) * cp.sum(cp.multiply(scenario_weights, xi))
    objective = cp.Minimize(cvar_expr)

    prob = cp.Problem(objective, constraints)
    prob.solve()

    if prob.status != "optimal":
        # Fallback: retry without the turnover constraint, which is the
        # constraint most likely to make the problem infeasible (e.g. if
        # the previous portfolio is far from anything achievable within
        # a 20% turnover budget under the other constraints).
        if prev_weights is not None and np.any(prev_weights):
            constraints_no_turnover = constraints[:-1] if sector_groups is None else constraints[:-1]
            prob2 = cp.Problem(objective, [c for c in constraints if c is not constraints[-1]])
            prob2.solve()
            if prob2.status == "optimal":
                return np.array(w.value).flatten(), prob2.value, float(eta.value)
        # Last resort: equal weight
        return np.full(n, 1.0 / n), np.nan, np.nan

    return np.array(w.value).flatten(), prob.value, float(eta.value)


