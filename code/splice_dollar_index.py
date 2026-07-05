"""
Splice DTWEXB (discontinued, 1995-2019) and DTWEXBGS (2006-present) into a
single continuous 6-month dollar-momentum series covering 1995-present.

Why splicing on momentum instead of levels: the two series use different
base-year indexing (DTWEXB uses a 1997 base, DTWEXBGS uses a 2006 base), so
their raw levels aren't directly comparable. But the regime feature we
actually need is 6-month trailing momentum (Formula 3 in the outline), which
is scale-invariant -- computing % change within each series separately and
then concatenating avoids the rebasing problem entirely.

Usage:
    python splice_dollar_index.py
(run after pull_fred_data.py has produced data/fred_regime_signals.csv)
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
FRED_PATH = DATA_DIR / "fred_regime_signals.csv"
OUTPUT_PATH = DATA_DIR / "dollar_momentum_spliced.csv"

MOMENTUM_MONTHS = 6


def splice_dollar_series():
    fred = pd.read_csv(FRED_PATH, index_col=0, parse_dates=True)

    if "DTWEXB" not in fred.columns or "DTWEXBGS" not in fred.columns:
        raise ValueError(
            "Expected both DTWEXB and DTWEXBGS columns in fred_regime_signals.csv. "
            "Re-run pull_fred_data.py first -- it now fetches both."
        )

    old = fred["DTWEXB"].dropna()
    new = fred["DTWEXBGS"].dropna()

    print(f"DTWEXB (old, discontinued): {old.index.min().date()} to {old.index.max().date()}")
    print(f"DTWEXBGS (new):             {new.index.min().date()} to {new.index.max().date()}")

    # Momentum computed independently within each series -- avoids the
    # base-year mismatch entirely.
    old_mom = old.pct_change(MOMENTUM_MONTHS)
    new_mom = new.pct_change(MOMENTUM_MONTHS)

    # Use the old series' momentum wherever the new series doesn't have
    # enough trailing history yet (i.e. before new series start + 6 months),
    # otherwise prefer the new series. IMPORTANT: only overwrite with the new
    # series where it actually has a value -- the new series' own first 6
    # months are themselves NaN (pct_change needs 6 trailing months), and
    # blindly overwriting with those NaNs would destroy perfectly good old-
    # series data for that stretch, then poison every 36-month rolling
    # window that touches it.
    switch_date = new.index.min()
    spliced = old_mom.combine_first(new_mom)
    valid_new_mask = new_mom.notna() & (new_mom.index >= switch_date)
    spliced.loc[new_mom.index[valid_new_mask]] = new_mom[valid_new_mask]

    spliced = spliced.dropna().sort_index()
    spliced.name = "dollar_6mo_momentum"

    print(f"\nSpliced series: {spliced.index.min().date()} to {spliced.index.max().date()} "
          f"({len(spliced)} months)")

    # Sanity check: look at the overlap window (2006-2019) and confirm the
    # two series' momentum estimates broadly agree in direction, as a check
    # that the splice isn't introducing an artificial discontinuity.
    overlap_start = max(old.index.min(), new.index.min())
    overlap_end = min(old.index.max(), new.index.max())
    if overlap_start < overlap_end:
        check = pd.DataFrame({"old_mom": old_mom, "new_mom": new_mom}).loc[overlap_start:overlap_end].dropna()
        corr = check["old_mom"].corr(check["new_mom"])
        print(f"\nOverlap window ({overlap_start.date()} to {overlap_end.date()}): "
              f"correlation between old-series and new-series momentum = {corr:.3f}")
        print("(Should be high, e.g. >0.9, if the splice is safe. Low correlation "
              "would mean the two series disagree enough that splicing is risky.)")

    spliced.to_csv(OUTPUT_PATH)
    print(f"\nSaved spliced dollar-momentum series to {OUTPUT_PATH}")
    return spliced


if __name__ == "__main__":
    splice_dollar_series()


