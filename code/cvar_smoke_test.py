"""
Smoke test for the CVaR optimization model, before building the full
regime-aware version.

Part 1 reproduces the CVaR tutorial's 10-scenario example by hand
(no decision variables, just checking the auxiliary-function formula
against the known answer of 16).

Part 2 solves a toy 3-stock portfolio CVaR problem with CVXPY, to confirm
the epigraph formulation (Formulas 7-9, 17-18 in the outline) is wired up
correctly before scaling to 12 stocks with real data.
"""

import numpy as np
import cvxpy as cp


# ---------------------------------------------------------------------
# Part 1: reproduce the tutorial's 10-scenario example by hand
# ---------------------------------------------------------------------
losses = np.array([0, 1, 1, 2, 2, 3, 4, 5, 12, 20], dtype=float)
alpha = 0.8
n = len(losses)

t = cp.Variable()
xi = cp.Variable(n, nonneg=True)

constraints = [xi >= losses - t]
objective = cp.Minimize(t + (1.0 / ((1 - alpha) * n)) * cp.sum(xi))
prob = cp.Problem(objective, constraints)
prob.solve()

print("=== Part 1: tutorial sanity check ===")
print(f"Solved CVaR value:   {prob.value:.4f}  (expected: 16.0)")
print(f"Solved threshold t:  {t.value:.4f}  (any value in [5, 12] is valid)")
assert abs(prob.value - 16.0) < 1e-4, "CVaR value does not match tutorial example!"
print("PASSED\n")


# ---------------------------------------------------------------------
# Part 2: toy 3-stock portfolio CVaR optimization
# ---------------------------------------------------------------------
# Fake scenario returns for 3 stocks, 8 equally-likely scenarios.
# Stock C is deliberately the "crash risk" asset: usually fine, occasionally
# terrible -- this is what CVaR should penalize relative to plain variance.
np.random.seed(0)
N_scenarios = 8
returns = np.array([
    [0.02,  0.01,  0.03],
    [0.01,  0.02, -0.01],
    [-0.01, 0.00,  0.02],
    [0.03, -0.01,  0.01],
    [0.00,  0.01, -0.20],   # crash scenario for stock C
    [0.02,  0.02,  0.02],
    [-0.02, 0.01,  0.01],
    [0.01,  0.00,  0.015],
])

n_assets = returns.shape[1]
alpha = 0.90

w = cp.Variable(n_assets, nonneg=True)
t = cp.Variable()
xi = cp.Variable(N_scenarios, nonneg=True)

portfolio_losses = -returns @ w  # Formula (2): L_s(w) = -sum_i r_s,i * w_i

constraints = [
    xi >= portfolio_losses - t,          # Formula (8)/(17)
    cp.sum(w) == 1,                       # Formula (11): full investment
    w <= 0.6,                             # Formula (12): concentration cap
]

cvar_expr = t + (1.0 / ((1 - alpha) * N_scenarios)) * cp.sum(xi)
objective = cp.Minimize(cvar_expr)
prob = cp.Problem(objective, constraints)
prob.solve()

print("=== Part 2: toy 3-stock CVaR-minimizing portfolio ===")
print(f"Status:              {prob.status}")
print(f"Minimized CVaR:      {prob.value:.4f}")
print(f"Weights (A, B, C):   {np.round(w.value, 4)}")
print("Expectation: weight on stock C (the crash-risk asset) should be pulled "
      "down relative to an equal-weight or mean-variance solution, since CVaR "
      "penalizes its tail scenario directly.")
