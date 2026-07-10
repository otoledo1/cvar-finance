# Regime-Conditioned CVaR Portfolio Optimization

## Repo layout

Everything runs flat, in one directory — no nested folders. Every script
looks for a `data/` and/or `results/` subfolder sitting next to itself,
auto-creating them if needed.

```
.
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── Pre-Data-Collection Decisions.md   <- full design-decision log
│
├── code/
│   ├── cvar_smoke_test.py            <- validates the CVaR optimizer core
│   ├── pull_equity_data.py           <- pulls the 12-stock universe
│   ├── pull_fred_data.py             <- pulls FRED regime-signal series
│   ├── pull_market_benchmark.py      <- pulls SPY (regime signal only)
│   ├── pull_market_caps.py           <- pulls shares outstanding (cap-weight input)
│   ├── check_data_alignment.py       <- coverage/gap diagnostic across all data
│   ├── splice_dollar_index.py        <- splices DTWEXB + DTWEXBGS into one series
│   ├── build_regime_labels.py        <- the regime classifier (kappa function)
│   ├── portfolio_construction.py     <- baseline strategy weight functions (library)
│   ├── run_baselines.py              <- walk-forward backtest, six baselines
│   ├── cvar_model.py                 <- [MODIFIED] CVaR optimizer core (library) — now also returns the VaR/eta threshold
│   ├── run_cvar_historical.py        <- [MODIFIED] Historical CVaR backtest (rho=0) — now saves VaR + regime_at_decision
│   ├── run_cvar_regime_aware.py      <- [MODIFIED] Regime-Aware CVaR backtest (rho>0) — now saves VaR, turnover, regime_at_decision
│   ├── diagnose_dollar_strength.py   <- weight/scenario-count diagnostic
│   ├── run_sensitivity_analysis.py   <- alpha/lookback/txn-cost/turnover sweep
│   ├── section_a_analysis.py         <- [NEW] closes the Section A checklist gaps (VaR summary, txn-cost drag, regime-stratified baselines, unclassified-vs-tranquil test, sector-cap check)
│
├── data/                          <- pulled data (re-pullable)
│   ├── equity_prices_monthly.csv
│   ├── equity_returns_monthly.csv
│   ├── fred_regime_signals.csv
│   ├── dollar_momentum_spliced.csv
│   ├── spy_prices_monthly.csv
│   ├── shares_outstanding.csv
│   └── regime_labels.csv
│
├── results/                       <- backtest outputs (tracked in git — these are the numbers the paper cites)
│   ├── baseline_returns.csv
│   ├── baseline_metrics.csv
│   ├── historical_cvar_returns.csv
│   ├── historical_cvar_weights.csv
│   ├── historical_cvar_turnover.csv
│   ├── historical_cvar_var.csv                          <- [NEW] VaR (eta) per rebalance, Historical CVaR
│   ├── historical_cvar_regime_at_decision.csv           <- [NEW] regime label at each decision date
│   ├── regime_cvar_returns_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv
│   ├── regime_cvar_weights_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv
│   ├── regime_cvar_turnover_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv       <- [NEW]
│   ├── regime_cvar_var_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv            <- [NEW]
│   ├── regime_cvar_regime_at_decision_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv <- [NEW]
│   ├── sensitivity_analysis_summary.csv
│   └── section_a/                     <- [NEW] outputs of section_a_analysis.py
│       ├── var_summary.csv
│       ├── txn_cost_drag.csv
│       ├── regime_stratified_all_strategies_long.csv
│       ├── regime_stratified_all_strategies_pivot.csv
│       ├── unclassified_vs_tranquil.csv
│       └── sector_cap_check.csv
```

## Pipeline (run in this order)

```bash
pip install -r requirements.txt

# 1. Environment check
python cvar_smoke_test.py

# 2. Data pulls
python pull_equity_data.py
python pull_fred_data.py YOUR_FRED_API_KEY
python pull_market_benchmark.py
python pull_market_caps.py
python splice_dollar_index.py
python check_data_alignment.py      # verify no unexpected gaps

# 3. Regime classification
python build_regime_labels.py       # prints regime distribution + crisis spot-check

# 4. Baselines
python run_baselines.py             # equal weight, cap-weighted, min-var,
                                     # mean-var, risk parity, momentum

# 5. CVaR models
python run_cvar_historical.py       # rho=0, the primary result
python run_cvar_regime_aware.py 0.5 # repeat for 0.5, 1, 2, 3 (the sweep)
python run_cvar_regime_aware.py 1
python run_cvar_regime_aware.py 2
python run_cvar_regime_aware.py 3

# 6. Diagnostics and robustness
python diagnose_dollar_strength.py 3.0
python run_sensitivity_analysis.py

# 7. Section A analysis (VaR summary, txn-cost drag, regime-stratified
#    baselines, unclassified-vs-tranquil test, sector-cap check) — run
#    after step 5 has produced the *_var.csv / *_regime_at_decision*.csv
#    files it depends on
python section_a_analysis.py
```

## Universe (12 stocks, 8 sectors)

JNJ/PFE (healthcare-pharma), PG/KO (consumer staples), MSFT/IBM
(technology), CAT/MMM (industrials), XOM (energy), JPM (financials), WMT
(retail), DIS (media)

## Headline results (as of the last full run)

| Strategy | Ann. return | Ann. vol | Sharpe | Max drawdown |
|---|---|---|---|---|
| Equal weight | 0.109 | 0.136 | 0.801 | -0.356 |
| Cap-weighted | 0.095 | 0.152 | 0.627 | -0.348 |
| Min variance | 0.093 | 0.121 | 0.769 | -0.284 |
| Mean-variance | 0.094 | 0.152 | 0.619 | -0.420 |
| Risk parity | 0.104 | 0.126 | 0.825 | -0.327 |
| Momentum | 0.102 | 0.136 | 0.751 | -0.330 |
| **Historical CVaR (ρ=0)** | **0.106** | **0.127** | **0.834** | **-0.275** |
| Regime-Aware CVaR (ρ=1) | 0.100 | 0.125 | 0.799 | -0.294 |

Historical CVaR (ρ=0) is the best performer on both Sharpe and max
drawdown. Regime-conditioning (ρ>0) does not improve on this and degrades
monotonically as ρ increases, an effect concentrated in and driven by the
dollar-strength regime specifically (see `diagnose_dollar_strength.py`
output and the checklist for the full mechanism discussion).

## Section A findings (VaR, transaction costs, regime-stratified
baselines, unclassified bucket, sector cap, factor exposure)

- **VaR (η)**: mean ≈ 0.042–0.045 across ρ=0..3; declines slightly as ρ
  increases, but the worst-case single-month VaR rises (0.065 → 0.089–0.091).
- **Transaction-cost drag**: under 5bps one-way, drag is under 0.2% of
  annual return for every strategy — doesn't affect any ranking.
- **Regime-stratified performance**: now computed for all 8 strategies,
  not just the two CVaR models — see `results/section_a/regime_stratified_all_strategies_pivot.csv`.
- **Unclassified vs. tranquil**: mean returns differ (0.61%/mo vs.
  1.27%/mo) but not statistically at n=52 (Welch p=0.207); variances are
  statistically identical (Levene p=0.957). Decision: keep unclassified
  as its own bucket, note the ambiguity rather than resolve it either way.
- **Sector cap**: binds often, not just a placeholder — up to ~22% of
  months for consumer staples (PG+KO).
- **Factor exposure (Fama-French)**: scoped out of the paper body. All 8
  strategies share the same 12-stock universe, so cross-strategy
  differences can't be attributed to differential factor exposure —
  documented as a one-line limitation instead of pulling French library
  data.

Full write-up: `section_a_findings.md` (not part of this repo tree by
default — add it under a `writeups/` or `docs/` folder if you want it
version-controlled alongside the code).

## Known simplifications (worth naming explicitly in the paper)

- **Cap weights** use current shares outstanding applied across the whole
  backtest history — captures price-driven market cap changes, not
  share-count changes (buybacks/issuances) over time.
- **Momentum baseline** is a concrete but unspecified-by-the-outline
  choice: equal-weight the top 6 of 12 stocks by trailing 12-month return.
- **Mean-variance risk aversion (λ=2.0)** is an untuned draft default.
- **Credit-spread (BAA10Y/BAMLH0A0HYM2)** was collected as a candidate
  regime feature but the frozen threshold rule never actually conditions
  on it — only VIX, rate-of-change in DGS10, dollar momentum, and equity
  momentum drive classification. Discovered after backtesting had begun;
  documented rather than retroactively fixed, to avoid post-hoc rule
  tweaking.
- **Rate-shock regime** has only 14 months across the full 30-year sample
  — thin, noisy, treat any rate-shock-specific finding cautiously.
- **Transaction costs** are applied as a post-hoc drag on realized
  returns for every strategy (not embedded in the optimization objective
  the way Formula 10 in the outline specifies), so the CVaR model and the
  six baselines are directly comparable on the same accounting basis.
- **Factor exposure (Fama-French)** was not decomposed — see Section A
  findings above for the rationale.
