# Pre-Data-Collection Decisions: Regime-Conditioned CVaR Portfolio Optimization (Equity-Only)

Draft answers to lock in before pulling any data. Everything here is a starting proposal — the goal is to have *something* fixed in writing before you look at results, not to get every number perfect on the first pass.

---

## 1. Research design — UPDATED (equity-only scope)

**Primary research question (final wording):**
> Does a regime-aware CVaR allocation rule across a diversified universe of well-established equities reduce downside tail risk and maximum drawdown relative to standard allocation benchmarks, while preserving competitive risk-adjusted returns after transaction costs?

**Secondary questions:**
- Does conditioning the historical scenario set on the current market regime improve tail-risk control relative to ordinary (unconditioned) historical CVaR?
- In which regimes does the strategy help most — tranquil/risk-on, high-volatility risk-off, rate-shock, or dollar-strength — *given that all holdings are domestic equities*?
- How sensitive are results to transaction costs, turnover caps, lookback window, CVaR confidence level, and sector concentration limits?

**Note on scope change:** the paper is now a single-asset-class (equity) regime-aware CVaR study rather than a cross-asset-class one. This simplifies the story (no duration/credit/FX exposure to explain) but also weakens the case for rate-shock and dollar-strength regimes, since none of your 12 holdings directly hedge rates or currency. Decide now whether to keep those regimes as macro backdrop or narrow to equity-relevant regimes (risk-on/risk-off, high-volatility, sector-rotation-type regimes).

**Framing sentence (use this consistently in the paper and in conversation with your mentor):**
> "This paper tests whether regime-conditioned historical scenarios improve downside-risk management relative to ordinary historical CVaR, for a diversified portfolio of established equities, especially under realistic trading frictions. It does not claim to find a guaranteed alpha strategy."

**Primary comparison (the one that isolates your contribution):**
- Historical CVaR (ρ = 0) **vs.** Regime-aware CVaR (ρ > 0), both on the same 12-stock universe

**Secondary comparisons (context, not the main claim):**
- Equal weight, cap-weighted index of the 12 stocks, minimum variance, mean-variance, risk parity, momentum allocation
- ~~60/40 equity/debt~~ — removed, no longer meaningful with an equity-only universe

---

## 2. Asset universe — UPDATED (equity-only, 12 individual stocks)

**Draft universe (12 stocks, sector-diverse, all long-established — no recent IPOs):**

| Ticker | Sector | Approx. public since |
|---|---|---|
| JNJ | Healthcare / pharma | 1944 |
| PG | Consumer staples | 1929 (modern listing) |
| KO | Consumer staples / beverage | 1919 |
| XOM | Energy | 1972 (predecessor entities much older) |
| JPM | Financials | 1969 (predecessor entities much older) |
| MSFT | Technology | 1986 |
| IBM | Technology / legacy hardware | 1911 |
| CAT | Industrials | 1929 |
| MMM | Industrials / conglomerate | 1946 |
| WMT | Retail | 1970 |
| DIS | Media / entertainment | 1957 |
| PFE | Pharma | 1942 |

This gives 8 distinct sectors (healthcare/pharma appears twice via JNJ/PFE, industrials twice via CAT/MMM, consumer staples twice via PG/KO, tech twice via MSFT/IBM) — reasonably diversified without being so broad it stops feeling like a hand-picked, interpretable universe.

**What changed from the original ETF-based universe:**
- No more debt sleeve (SHY, IEF, TLT, LQD, HYG) and no more FX sleeve (UUP) — these are dropped as *assets*. The underlying macro series (yields, credit spreads, dollar index) can still be kept as *regime signals* even though they're no longer held as positions — see Section 3 note.
- "Economic role" framing per asset class no longer applies; instead, briefly justify each stock's sector and why it's liquid/well-covered enough to include.

**Inception-date check:** all 12 names above have decades of public trading history, so unlike the ETF universe, inception-date constraints are no longer a binding issue — you should be able to start the backtest as early as data quality allows (e.g., 1990s onward) rather than being forced to 2008. Worth double-checking split-adjusted price history availability for each ticker before finalizing the start date.

**Open question to resolve:** do you want exactly these 12, or do you want to swap any for sector balance (e.g., no current utilities, materials, or telecom representation)? Flagging this as a deliberate choice rather than an oversight — the current list favors staples/healthcare/industrials/tech and is light on utilities, materials, and telecom.

---

## 3. Regimes and thresholds (fix before touching performance data)

**Note on scope change:** the regime *feature vector* below still uses macro series (VIX, yield curve, credit spread, dollar) even though those series are no longer held as assets — they're kept purely as regime-classification signals. This is fine, but worth stating explicitly in the paper so it doesn't look inconsistent: "although the strategy invests only in equities, regime classification uses broader macro/financial signals because sector- and stock-level returns respond to these same stress channels." Decide whether to keep all four regimes (tranquil, risk-off, rate-shock, dollar-strength) or narrow to the two most equity-relevant ones (tranquil/risk-on, high-volatility risk-off) and drop rate-shock/dollar-strength since your holdings don't directly hedge rates or FX.

**Draft regime feature vector** (Formula 3):
- Equity momentum: 12-month trailing return on SPY
- Volatility: VIX level (VIXCLS)
- Yield-curve slope: 10Y minus 2Y (T10Y2Y or DGS10 − DGS2)
- Credit stress: **BAA10Y** (Moody's Baa spread vs. 10yr Treasury) — chosen as the primary credit-stress signal for its full 1986+ history, so regime classification isn't truncated to 2023+. See "Credit-spread validation" note below.
- Dollar momentum: 6-month trailing return on DTWEXBGS
- Inflation pressure: 12-month CPI change (CPIAUCSL)

**Credit-spread validation (resolved — using both series):**
- `BAA10Y` drives regime classification for the full backtest (1995–present)
- `BAMLH0A0HYM2` (high-yield OAS) is pulled alongside it but only has data from 2023-07 onward (FRED restricted this ICE series to a rolling 3-year window in April 2026)
- As a robustness check, re-run regime classification for just the 2023-07–present overlap window using `BAMLH0A0HYM2` in place of `BAA10Y`, and compare the resulting regime labels. Report the agreement rate in the paper's robustness section — this validates (or flags a limitation of) using `BAA10Y` as the long-history stand-in.

**Draft threshold rule κ(·):** (simple, transparent, decided now — not tuned later)
- **Tranquil/risk-on:** VIX below its trailing 3-year median AND equity momentum positive
- **High-volatility risk-off:** VIX above its trailing 3-year 75th percentile
- **Rate-shock:** |month-over-month change in DGS10| above its trailing 3-year 90th percentile
- **Dollar-strength:** dollar 6-month momentum above its trailing 3-year 75th percentile
- Ties broken by priority order: rate-shock > risk-off > dollar-strength > tranquil (i.e., check in that order, assign first match)

*(This is a reasonable starting rule, not a final one — the important thing is that whatever you land on gets written down and frozen before backtesting begins.)*

**Draft parameters:**
- α (CVaR confidence level): **0.95**, with 0.90 and 0.99 as robustness checks
- ρ (regime-weighting strength): **ρ = 1** for the main regime-aware run (regime-matched scenarios get 2× weight vs. non-matched), with ρ = 0 as the baseline comparison and ρ = 2, 3 as sensitivity checks

---

## 4. Modeling choices for the backtest

- **Walk-forward window:** 60-month lookback (more stable scenario sets than 36-month given only 12 stocks)
- **Rebalancing frequency:** monthly
- **Turnover cap τ:** draft value 20% of portfolio per month (revisit once you see baseline turnover from equal-weight/cap-weighted-index)
- **Transaction costs c_i:** draft flat 5 bps one-way for all names (single-asset-class equity now, so the earlier FX-specific 10 bps line is dropped)
- **Position limits u_i:** draft cap of 25% per single asset, no shorting (long-only)
- **Asset-class bounds (L_g, U_g):** ~~no longer applicable~~ — with a single asset class, repurpose this constraint as a **sector cap** instead (e.g., no more than 30% in any one sector, so the optimizer can't concentrate in just 2–3 correlated names like JNJ+PFE or CAT+MMM)
- **No-forecast robustness version:** run μ_t = 0 (or equal across assets) as a required companion run from week 1, not an afterthought — this isolates whether the CVaR/regime mechanism works without a return forecast doing the work
- **Expected-return model coefficients (β₀, β₁, β₂, β₃ in Formula 19):** fix these using only pre-test-period data (e.g., a short initial calibration window), or estimate them via rolling re-estimation strictly using only data available before each rebalance date — pick rolling re-estimation as the default, since it's more defensible against look-ahead bias
- **Shrinkage γ (Formula 25):** draft value γ = 0.3 (expected-return tilts have limited influence relative to the asset-class base return)

---

## 5. Data access verification — UPDATED (equity-only)

- [ ] Confirm you can retrieve adjusted price histories for: JNJ, PG, KO, XOM, JPM, MSFT, IBM, CAT, MMM, WMT, DIS, PFE
- [ ] ~~Bond ETF and FX ETF price pulls no longer needed~~ (SHY, IEF, TLT, LQD, HYG, UUP dropped as held assets)
- [ ] Confirm FRED pulls for regime signals (used for classification only, not held as assets): VIXCLS, DGS10, DGS2, T10Y2Y, DTWEXBGS, CPIAUCSL, BAMLH0A0HYM2
- [ ] Confirm Kenneth French factor library access (only needed for the factor-exposure check in Section 4.3 — lower priority than the core pulls)

**Data dictionary template (fill in as you confirm each source):**

| Series | Source | Frequency | Transformation | Date range available |
|---|---|---|---|---|
| JNJ, PG, KO, XOM, JPM, MSFT, IBM, CAT, MMM, WMT, DIS, PFE (adjusted close, each) | Yahoo/Stooq | Daily → monthly | Log return | — |
| VIXCLS | FRED | Daily → monthly | Level | — |
| DGS10, DGS2 | FRED | Daily → monthly | Level, spread | — |
| DTWEXBGS | FRED | Daily → monthly | 6-mo momentum | — |
| CPIAUCSL | FRED | Monthly | 12-mo % change | — |
| BAMLH0A0HYM2 | FRED | Daily → monthly | Level | — |

*(Leave date-range column blank until you've actually pulled each series — don't guess.)*

---

## 6. Technical environment

- [ ] Install CVXPY (`pip install cvxpy`) and confirm a toy CVaR LP solves end to end (a 3-asset, 10-scenario version of the tutorial example is a good smoke test)
- [ ] Repo structure (draft):
  ```
  /data          — raw pulls, cached
  /scripts        — data cleaning, regime construction
  /optimization   — CVaR model, benchmark solvers
  /backtest       — walk-forward engine
  /figures        — output plots/tables
  requirements.txt
  ```
- [ ] Set up git repo now, commit the toy CVaR test as the first commit
- [ ] Decide solver (CVXPY default ECOS/SCS should be fine for this LP size — no need for a commercial solver)

---

## 7. Documentation and alignment

- [ ] Re-check Week 1 of the roadmap (asset universe + data pull) matches what you're about to execute
- [ ] Draft mentor briefing memo skeleton now (asset universe, regime definitions, model summary, open decisions) so it's a living document, not reconstructed later
- [ ] Fixed benchmark list for reporting: Equal weight, Cap-weighted index of the 12 stocks, Minimum variance, Mean-variance, Risk parity, Momentum, Historical CVaR, Regime-aware CVaR

  *(60/40 removed — no debt sleeve left to benchmark against)*
- [ ] Fixed metric list for reporting: annualized return, annualized volatility, Sharpe, Sortino, max drawdown, VaR, CVaR, turnover, transaction-cost drag, regime-stratified performance, factor exposure

---

## Open items you should decide (flagged, not defaulted)

These are the choices most likely to shape your results, so double-check them rather than accepting the drafts above outright:

1. **Final 12-stock list** — the sector mix above is a starting proposal; decide if you want different sector coverage (currently no utilities, materials, or telecom)
2. **Backtest start date** — RESOLVED by data pull: all 12 stocks have full history back to 1995. The binding constraint is now the macro series, not the stocks — see item 8 below.
3. **Whether to keep rate-shock and dollar-strength regimes** — these were originally motivated by bond/FX exposure that no longer exists in the portfolio; decide if they still add value as macro context or should be dropped in favor of equity-relevant regimes
4. **ρ = 1 as the main regime-aware setting** — arbitrary starting point; consider whether a smaller/larger value better reflects "moderate" regime conditioning
5. **Turnover cap and transaction costs** — draft numbers are placeholders; worth a quick sanity check against typical single-stock trading costs before locking in
6. **Regime threshold rule — RESOLVED AND VALIDATED:** the original fixed priority-order tie-break (rate-shock > risk-off > dollar-strength > tranquil) caused March 2020 (COVID) to classify as rate-shock rather than risk-off, since rate-shock was checked first regardless of which signal was actually more extreme. Switched to **margin-based tie-breaking**: when multiple stress conditions trigger in the same month, classify by whichever condition is exceeded by the largest margin (percentile rank within its own trailing 36-month window, minus its trigger threshold). Confirmed on real data: 2020-03 now correctly classifies as risk_off. Final validated distribution (378 months, 1998-06 to 2026-06 after warm-up): tranquil 33.3%, risk_off 21.7%, unclassified 15.6%, dollar_strength 14.8%, insufficient_history 10.8%, **rate_shock only 3.7% (14 months)** — this dropped sharply from the old priority-order rule (was 8.7%), since rate-shock now only wins when it's genuinely the most extreme signal that month rather than by default. **New flag for later:** 14 months is a thin sample for the regime-weighted scenario set (Formula 5) — keep this in mind when interpreting rate-shock-specific results, since that regime's scenario set will be the noisiest of the four.
7. **Sector cap value** — the proposed 30% sector cap (replacing the old asset-class bounds) is a placeholder; check it against how concentrated your final 12-stock sector mix actually is
8. **Credit-spread series — RESOLVED, WITH A CAVEAT DISCOVERED LATER:** Use `BAA10Y` as the primary credit-stress feature for regime classification across the full backtest (confirmed clean, 1995-01 to 2026-07, no gaps). Use `BAMLH0A0HYM2` as a secondary robustness check: after the main backtest, re-run regime classification for the 2023-07-onward overlap window using BAMLH0A0HYM2 instead of BAA10Y and compare regime labels. Report whether they agree as a robustness note. **CAVEAT (found during the sensitivity-analysis phase, after backtesting had begun):** the frozen threshold rule κ(·) in Section 3 never actually conditions on credit spread at all — it only uses VIX, the rate-of-change in DGS10, dollar momentum, and equity momentum. BAA10Y/BAMLH0A0HYM2 were collected as part of the broader feature vector (Formula 3) but the operational classification rule doesn't reference them. Since the rule was locked in before touching performance data, retroactively adding a credit-based condition now would itself be a form of post-hoc rule tweaking — not done. **Resolution: this robustness check is moot as originally conceived (swapping BAA10Y for BAMLH0A0HYM2 would change zero regime labels) and is documented in the paper as a known scope simplification** rather than actually run.
9. **Sensitivity analysis (alpha, lookback, transaction costs, turnover cap) — RESOLVED, ROBUST:** ran a one-factor-at-a-time sweep against the primary Historical CVaR (rho=0) result. Findings: alpha=0.95 outperforms both 0.90 and 0.99 (Sharpe 0.834 vs. 0.755 vs. 0.809); the 60-month lookback clearly beats 36-month (Sharpe 0.834 vs. 0.703 — validates the original design reasoning); transaction costs from 0-20bps move Sharpe only from 0.837 to 0.824 (no cliff effect); turnover cap from 0.10 to uncapped keeps Sharpe in a tight 0.81-0.83 band, with looser caps trading a bit of Sharpe for a shallower max drawdown. **Overall: the "Historical CVaR beats all six baselines" result is not fragile to any of these draft parameter choices.**
9. **Dollar-strength regime window — RESOLVED AND VERIFIED:** spliced `DTWEXB` (1995-2019) with `DTWEXBGS` (2006-present) on 6-month momentum. Overlap-window correlation = **0.996**. A bug in the original splice (blindly overwriting the post-2006 range with the new series, including its own 6-month NaN warm-up) was found and fixed after it showed up as a false "insufficient_history" gap spanning 2006-2009 — which was masking the 2008 Lehman crisis in the regime spot-check. After the fix, 2008-09 and 2008-10 both correctly classify as risk_off.
10. **CPI gap (Oct 2025) — RESOLVED:** single missing month, confirmed isolated (not a systemic gap). Safe to forward-fill from Sept 2025 when building the inflation-pressure feature.
11. **Confirmed backtest window:** equity and FRED data align cleanly (same day-of-month convention) from 1995-02-01 to 2026-07-01. This is the maximum usable window; the actual regime-feature window is narrower depending on how item 9 is resolved.
12. **"Unclassified" bucket (~17.5% of months) — DECISION: leave as-is for now.** Rather than force every month into one of the four named regimes, unclassified stays its own category. Revisit after seeing backtest results — if regime-aware CVaR performs notably differently across regimes, it may be worth deciding then whether "unclassified" behaves like a fifth distinct regime worth reporting on, or should be folded into tranquil.
