# cvar-finance

# Regime-Aware CVaR Allocation — Equity Universe
 
Companion code repo to `pre_data_collection_checklist_draft.md`. Refer back
to that document for the locked-in design decisions (regime rule, α, ρ,
turnover cap, etc.) before changing anything here.
 
## Status: Week 1 (asset universe and data)
 
- [x] Repo scaffolded
- [x] CVaR optimization core validated (`optimization/cvar_smoke_test.py`)
      against the tutorial's known 10-scenario answer (16.0) and a toy
      3-stock crash-risk example
- [ ] Equity price data pulled (`scripts/pull_equity_data.py` -- run locally,
      this sandbox can't reach Yahoo Finance)
- [ ] FRED regime signals pulled (`scripts/pull_fred_data.py` -- run locally,
      needs a free FRED API key)
- [ ] Data coverage checked (all 12 tickers, no unexpected gaps)
## Structure
 
```
/data          -- raw and processed price/macro data (populated by scripts/)
/scripts       -- data pulling and cleaning
/optimization  -- CVaR model core (smoke-tested), later the full regime-aware model
/backtest      -- walk-forward engine (not yet built)
/figures       -- output plots and tables (not yet populated)
```
 
## Universe (12 stocks)
 
JNJ, PG, KO, XOM, JPM, MSFT, IBM, CAT, MMM, WMT, DIS, PFE
 
## Next steps
 
1. Run `scripts/pull_equity_data.py` and `scripts/pull_fred_data.py` locally
2. Check the data coverage report each script prints -- flag any gaps before
   moving on
3. Resolve the open items in the checklist (regime set, sector cap value,
   ρ, backtest start date) using the real data coverage as a guide
4. Move to Week 2: baseline benchmarks (equal weight, cap-weighted index,
   min variance, mean-variance, risk parity, momentum)
