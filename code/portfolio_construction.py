"""
Weight-generation functions for each baseline strategy. Each function takes
whatever trailing-window inputs it needs (returns, covariance, market caps)
and returns a weight vector (numpy array, sums to 1, long-only).

Shared constraints across the constructed strategies (min-variance,
mean-variance, risk parity): long-only, no single name above 25%, matching
the position-limit draft in Section 4 of the checklist. The cap-weighted
index and equal-weight benchmarks are deliberately left UNCONSTRAINED by
the 25% cap, since the whole point of comparing against them is to show
what an unconstrained/naive benchmark looks like.
"""

import numpy as np
import cvxpy as cp
from scipy.optimize import minimize

POSITION_CAP = 0.25


def equal_weight(n_assets):
    return np.full(n_assets, 1.0 / n_assets)


def cap_weight(market_caps):
    """market_caps: array of market cap values (price * shares outstanding)."""
    weights = market_caps / market_caps.sum()
    return weights


def min_variance(cov_matrix, position_cap=POSITION_CAP):
    n = cov_matrix.shape[0]
    w = cp.Variable(n, nonneg=True)
    objective = cp.Minimize(cp.quad_form(w, cov_matrix))
    constraints = [cp.sum(w) == 1, w <= position_cap]
    prob = cp.Problem(objective, constraints)
    prob.solve()
    if prob.status != "optimal":
        return equal_weight(n)  # fallback if solver fails on a given month
    return np.array(w.value).flatten()


def mean_variance(mu, cov_matrix, risk_aversion=2.0, position_cap=POSITION_CAP):
    """
    Classic Markowitz: maximize mu^T w - risk_aversion * w^T Sigma w.
    risk_aversion=2.0 is a draft default (not yet tuned) -- flagged as an
    open item, same spirit as the checklist's other placeholder parameters.
    """
    n = cov_matrix.shape[0]
    w = cp.Variable(n, nonneg=True)
    objective = cp.Maximize(mu @ w - risk_aversion * cp.quad_form(w, cov_matrix))
    constraints = [cp.sum(w) == 1, w <= position_cap]
    prob = cp.Problem(objective, constraints)
    prob.solve()
    if prob.status != "optimal":
        return equal_weight(n)
    return np.array(w.value).flatten()


def risk_parity(cov_matrix, position_cap=POSITION_CAP):
    """
    Equal risk contribution portfolio. No simple closed form for the
    long-only, position-capped case, so solved numerically: minimize the
    sum of squared deviations between each asset's risk contribution and
    the equal-contribution target (1/n of total portfolio variance).
    """
    n = cov_matrix.shape[0]

    def risk_contributions(w):
        portfolio_var = w @ cov_matrix @ w
        marginal_contrib = cov_matrix @ w
        return w * marginal_contrib / portfolio_var

    def objective(w):
        rc = risk_contributions(w)
        target = 1.0 / n
        return np.sum((rc - target) ** 2)

    x0 = equal_weight(n)
    bounds = [(0.0, position_cap) for _ in range(n)]
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    result = minimize(objective, x0, bounds=bounds, constraints=constraints,
                       method="SLSQP", options={"maxiter": 1000, "ftol": 1e-12})
    if not result.success:
        return x0  # fallback to equal weight if the numerical solve fails
    return result.x


def momentum(trailing_12mo_returns, top_k=6):
    """
    Equal-weight the top_k assets by trailing 12-month return.
    ASSUMPTION flagged: the outline doesn't specify an exact momentum rule,
    so this is a concrete default (top-6-of-12 equal weight) -- easy to
    change to a different top_k or a continuous momentum tilt if you'd
    rather.
    """
    n = len(trailing_12mo_returns)
    top_k = min(top_k, n)
    ranked = np.argsort(-trailing_12mo_returns)  # descending
    selected = ranked[:top_k]
    weights = np.zeros(n)
    weights[selected] = 1.0 / top_k
    return weights


