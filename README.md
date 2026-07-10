# Regime-Conditioned CVaR Portfolio Optimization

## Repo layout

Everything runs flat, in one directory — no nested folders. Every script
looks for a `data/`, `results/`, and/or `figures/` subfolder sitting next
to itself, auto-creating them if needed.

```
.
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── Pre-Data-Collection Decisions.md   <- full design-decision log
│
├── code/
│   ├── cvar_smoke_test.py                    <- validates the CVaR optimizer core
│   ├── pull_equity_data.py                   <- pulls the 12-stock universe
│   ├── pull_fred_data.py                     <- pulls FRED regime-signal series
│   ├── pull_market_benchmark.py              <- pulls SPY (regime signal only)
│   ├── pull_market_caps.py                   <- pulls shares outstanding (cap-weight input)
│   ├── check_data_alignment.py               <- coverage/gap diagnostic across all data
│   ├── splice_dollar_index.py                <- splices DTWEXB + DTWEXBGS into one series
│   ├── build_regime_labels.py                <- the regime classifier (kappa function)
│   ├── portfolio_construction.py             <- baseline strategy weight functions (library)
│   ├── run_baselines.py                      <- walk-forward backtest, six baselines
│   ├── cvar_model.py                         <- [MODIFIED] CVaR optimizer core (library) — now also returns the VaR/eta threshold
│   ├── run_cvar_historical.py                <- [MODIFIED] Historical CVaR backtest (rho=0) — now saves VaR + regime_at_decision
│   ├── run_cvar_regime_aware.py               <- [MODIFIED] Regime-Aware CVaR backtest (rho>0) — now saves VaR, turnover, regime_at_decision
│   ├── diagnose_dollar_strength.py           <- weight/scenario-count diagnostic
│   ├── run_sensitivity_analysis.py           <- [MODIFIED] alpha/lookback/txn-cost/turnover sweep — one-line fix, see note below
│   ├── additional-metrics-analysis.py        <- [NEW] closes the checklist's small analysis gaps (VaR summary, txn-cost drag, regime-stratified baselines, unclassified-vs-tranquil test, sector-cap check)
│   ├── generate_figures.py                   <- [NEW] builds all 6 figures below from results/ only (no backtest re-run)
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
│   ├── historical_cvar_var.csv                              <- [NEW] VaR (eta) per rebalance, Historical CVaR
│   ├── historical_cvar_regime_at_decision.csv               <- [NEW] regime label at each decision date
│   ├── regime_cvar_returns_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv
│   ├── regime_cvar_weights_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv
│   ├── regime_cvar_turnover_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv               <- [NEW]
│   ├── regime_cvar_var_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv                     <- [NEW]
│   ├── regime_cvar_regime_at_decision_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv      <- [NEW]
│   ├── sensitivity_analysis_summary.csv
│   └── additional-metrics-analysis/          <- [NEW] outputs of additional-metrics-analysis.py
│       ├── var_summary.csv
│       ├── txn_cost_drag.csv
│       ├── regime_stratified_all_strategies_long.csv
│       ├── regime_stratified_all_strategies_pivot.csv
│       ├── unclassified_vs_tranquil.csv
│       └── sector_cap_check.csv
│
└── figures/                       <- [NEW] outputs of generate_figures.py
    ├── 01_cumulative_wealth_curve.png
    ├── 02_drawdown_curve.png
    ├── 02_drawdown_max_by_strategy.csv
    ├── 03_return_vs_cvar_frontier.png
    ├── 03_return_vs_cvar_frontier_data.csv
    ├── 04_regime_stratified_performance.png
    ├── 05_robustness_chart.png
    ├── 05_robustness_table_formatted.csv
    ├── 05_robustness_table_formatted.md
    └── 06_weight_heatmap_optional.png
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

# 7. Additional metrics analysis (VaR summary, txn-cost drag,
#    regime-stratified baselines, unclassified-vs-tranquil test,
#    sector-cap check) — run after step 5 has produced the
#    *_var.csv / *_regime_at_decision*.csv files it depends on
python additional-metrics-analysis.py

# 8. Figures — reads only from results/, does not re-run any backtest
python generate_figures.py
```

**Note on `run_sensitivity_analysis.py`:** adding the VaR return value to
`cvar_weights()` (step 5's change) means every caller that unpacks its
return tuple needed updating. `run_cvar_historical.py` and
`run_cvar_regime_aware.py` were updated when the change was made, but
`run_sensitivity_analysis.py` was missed in that pass and would have
crashed (`too many values to unpack`) the next time it ran. Fixed by
changing `w, _ = cvar_weights(...)` to `w, _, _ = cvar_weights(...)` —
already applied in the version in this repo, just flagging it so the
history makes sense if you're comparing diffs.

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

## Additional metrics analysis findings (VaR, transaction costs,
regime-stratified baselines, unclassified bucket, sector cap, factor
exposure)

- **VaR (η)**: mean ≈ 0.042–0.045 across ρ=0..3; declines slightly as ρ
  increases, but the worst-case single-month VaR rises (0.065 → 0.089–0.091).
- **Transaction-cost drag**: under 5bps one-way, drag is under 0.2% of
  annual return for every strategy — doesn't affect any ranking.
- **Regime-stratified performance**: now computed for all 8 strategies,
  not just the two CVaR models — see
  `results/additional-metrics-analysis/regime_stratified_all_strategies_pivot.csv`,
  visualized in `figures/04_regime_stratified_performance.png`.
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

Full write-up: `additional-metrics-analysis_findings.md` (not part of
this repo tree by default — add it under a `writeups/` or `docs/` folder
once those exist if you want it version-controlled alongside the code).

## Figures

All in `figures/`, built by `code/generate_figures.py` from `results/`
only (no backtest re-run required):

- **01 — Cumulative wealth curve**: all 8 strategies, log scale.
- **02 — Drawdown curve**: same 8 strategies; this is where Historical
  CVaR's shallower 2008 drawdown vs. e.g. mean-variance's -42% becomes
  visually obvious.
- **03 — Return-vs-CVaR frontier**: annualized return vs. realized
  monthly CVaR at 95%, with the Pareto frontier drawn through the
  non-dominated strategies.
- **04 — Regime-stratified performance**: annotated heatmap (not grouped
  bars — with only 5 regimes × 8 strategies, a heatmap reads far better
  than 40 skinny bars) of mean monthly return by regime, all strategies.
- **05 — Robustness**: a 4-panel chart (α, lookback, transaction cost,
  turnover cap) showing Sharpe ratio's sensitivity to each design choice,
  base case circled, plus the full formatted table
  (`05_robustness_table_formatted.csv` / `.md`).
- **06 — Portfolio weight heatmap** *(optional, lower priority per the
  outline)*: Historical CVaR's allocation across all 12 stocks over time,
  quarterly average.

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
- **Factor exposure (Fama-French)** was not decomposed — see Additional
  metrics analysis findings above for the rationale.



  
