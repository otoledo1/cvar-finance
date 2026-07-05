# Repo layout

Everything runs flat, in one directory — no nested folders. Every script
looks for a data/ and/or results/ subfolder sitting next to itself,
auto-creating them if needed. This was a deliberate simplification partway
through the project (see checklist history) rather than the originally
scaffolded /scripts + /backtest + /optimization split.

.
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── pre_data_collection_checklist_draft.md   <- full design-decision log
│
├── cvar_smoke_test.py            <- validates the CVaR optimizer core
├── pull_equity_data.py           <- pulls the 12-stock universe
├── pull_fred_data.py             <- pulls FRED regime-signal series
├── pull_market_benchmark.py      <- pulls SPY (regime signal only)
├── pull_market_caps.py           <- pulls shares outstanding (cap-weight input)
├── check_data_alignment.py       <- coverage/gap diagnostic across all data
├── splice_dollar_index.py        <- splices DTWEXB + DTWEXBGS into one series
├── build_regime_labels.py        <- the regime classifier (kappa function)
├── portfolio_construction.py     <- baseline strategy weight functions (library)
├── run_baselines.py              <- walk-forward backtest, six baselines
├── cvar_model.py                 <- CVaR optimizer core (library)
├── run_cvar_historical.py        <- Historical CVaR backtest (rho=0)
├── run_cvar_regime_aware.py      <- Regime-Aware CVaR backtest (rho>0)
├── diagnose_dollar_strength.py   <- weight/scenario-count diagnostic
├── run_sensitivity_analysis.py   <- alpha/lookback/txn-cost/turnover sweep
│
├── data/                          <- pulled data (gitignored, re-pullable)
│   ├── equity_prices_monthly.csv
│   ├── equity_returns_monthly.csv
│   ├── fred_regime_signals.csv
│   ├── dollar_momentum_spliced.csv
│   ├── spy_prices_monthly.csv
│   ├── shares_outstanding.csv
│   └── regime_labels.csv
│
└── results/                       <- backtest outputs (tracked in git —
                                       these are the numbers the paper cites)
    ├── baseline_returns.csv
    ├── baseline_metrics.csv
    ├── historical_cvar_returns.csv
    ├── historical_cvar_weights.csv
    ├── historical_cvar_turnover.csv
    ├── regime_cvar_returns_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv
    ├── regime_cvar_weights_rho0p5.csv / rho1p0.csv / rho2p0.csv / rho3p0.csv
    └── sensitivity_analysis_summary.csv

# Pipeline (run in this order)

pip install -r requirements.txt

1. Environment check
python cvar_smoke_test.py

2. Data pulls
python pull_equity_data.py
python pull_fred_data.py YOUR_FRED_API_KEY
python pull_market_benchmark.py
python pull_market_caps.py
python splice_dollar_index.py
python check_data_alignment.py      # verify no unexpected gaps

3. Regime classification
python build_regime_labels.py       # prints regime distribution + crisis spot-check

4. Baselines
python run_baselines.py             # equal weight, cap-weighted, min-var,
                                     # mean-var, risk parity, momentum

5. CVaR models
python run_cvar_historical.py       # rho=0, the primary result
python run_cvar_regime_aware.py 1   # rho=1 (repeat with 0.5, 2, 3 for the sweep)

6. Diagnostics and robustness
python diagnose_dollar_strength.py 3.0
python run_sensitivity_analysis.py

Universe (12 stocks, 8 sectors)

JNJ/PFE (healthcare-pharma), PG/KO (consumer staples), MSFT/IBM
(technology), CAT/MMM (industrials), XOM (energy), JPM (financials), WMT
(retail), DIS (media)

Headline results (as of the last full run)

StrategyAnn. returnAnn. volSharpeMax drawdownEqual weight0.1090.1360.801-0.356Cap-weighted0.0950.1520.627-0.348Min variance0.0930.1210.769-0.284Mean-variance0.0940.1520.619-0.420Risk parity0.1040.1260.825-0.327Momentum0.1020.1360.751-0.330Historical CVaR (ρ=0)0.1060.1270.834-0.275Regime-Aware CVaR (ρ=1)0.1000.1250.799-0.294

Historical CVaR (ρ=0) is the best performer on both Sharpe and max
drawdown. Regime-conditioning (ρ>0) does not improve on this and degrades
monotonically as ρ increases, an effect concentrated in and driven by the
dollar-strength regime specifically (see diagnose_dollar_strength.py
output and the checklist for the full mechanism discussion).

Known simplifications (worth naming explicitly in the paper)


Cap weights use current shares outstanding applied across the whole
backtest history — captures price-driven market cap changes, not
share-count changes (buybacks/issuances) over time.
Momentum baseline is a concrete but unspecified-by-the-outline
choice: equal-weight the top 6 of 12 stocks by trailing 12-month return.
Mean-variance risk aversion (λ=2.0) is an untuned draft default.
Credit-spread (BAA10Y/BAMLH0A0HYM2) was collected as a candidate
regime feature but the frozen threshold rule never actually conditions
on it — only VIX, rate-of-change in DGS10, dollar momentum, and equity
momentum drive classification. Discovered after backtesting had begun;
documented rather than retroactively fixed, to avoid post-hoc rule
tweaking.
Rate-shock regime has only 14 months across the full 30-year sample
— thin, noisy, treat any rate-shock-specific finding cautiously.
Transaction costs are applied as a post-hoc drag on realized
returns for every strategy (not embedded in the optimization objective
the way Formula 10 in the outline specifies), so the CVaR model and the
six baselines are directly comparable on the same accounting basis.


