"""
Pull the macro/financial series used as regime-classification signals
(NOT held as portfolio assets -- see checklist Section 3 note on why an
all-equity portfolio still uses these for regime labeling).

NOTE: This sandbox cannot reach the FRED API directly. Run this on your
own machine.

Get a free FRED API key at https://fred.stlouisfed.org/docs/api/api_key.html

Usage:
    pip install fredapi pandas
    python pull_fred_data.py YOUR_API_KEY
"""

import sys
import pandas as pd
from fredapi import Fred
from pathlib import Path

SERIES = {
    "VIXCLS": "VIX (volatility)",
    "DGS10": "10-year Treasury yield",
    "DGS2": "2-year Treasury yield",
    "T10Y2Y": "10y-2y yield curve slope",
    "DTWEXBGS": "Trade-weighted dollar index (2006-present)",
    "DTWEXB": "Trade-weighted dollar index, discontinued (1995-2019; splice with DTWEXBGS for full history)",
    "CPIAUCSL": "CPI (inflation)",
    "BAMLH0A0HYM2": "High-yield credit spread (FRED-restricted to ~3yr as of Apr 2026)",
    "BAA10Y": "Baa corporate spread vs 10yr Treasury (full history since 1986, unrestricted)",
}

START_DATE = "1995-01-01"

# Output goes to a "data" folder next to this script, created automatically
# if it doesn't exist yet -- works regardless of whether you're using the
# /scripts + /data repo layout or a flat folder.
OUTPUT_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "fred_regime_signals.csv"


def pull_fred_series(api_key):
    fred = Fred(api_key=api_key)
    frames = {}

    print("Pulling FRED series...")
    for code, description in SERIES.items():
        try:
            series = fred.get_series(code, observation_start=START_DATE)
            frames[code] = series
            print(f"  {code} ({description}): {series.index.min().date()} to "
                  f"{series.index.max().date()}, {len(series.dropna())} obs")
        except Exception as e:
            print(f"  {code}: FAILED -- {e}")

    if not frames:
        print("\nNo series were successfully pulled -- stopping before the "
              "resample step. Most likely cause: an invalid FRED API key. "
              "Check that the key is exactly 32 lowercase alphanumeric "
              "characters, copied from your FRED account's API Keys page.")
        sys.exit(1)

    if len(frames) < len(SERIES):
        missing = set(SERIES) - set(frames)
        print(f"\nWarning: {len(missing)} series failed and will be missing "
              f"from the output: {sorted(missing)}")

    df = pd.DataFrame(frames)
    # Resample everything to monthly (some series are daily, CPI is already monthly)
    df_monthly = df.resample("MS").last()
    df_monthly.to_csv(OUTPUT_PATH)
    print(f"\nSaved monthly regime signals to {OUTPUT_PATH}")
    return df_monthly


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pull_fred_data.py YOUR_FRED_API_KEY")
        sys.exit(1)

    key = sys.argv[1]
    if not (len(key) == 32 and key.isalnum() and key == key.lower()):
        print(f"Warning: '{key}' doesn't look like a valid FRED API key.")
        print("FRED keys are exactly 32 lowercase alphanumeric characters. "
              "Double-check you copied it from your FRED account's API Keys "
              "page (https://fred.stlouisfed.org/docs/api/api_key.html) "
              "rather than a different service.")
        print("Attempting the request anyway in case this check is wrong...\n")

    pull_fred_series(key)



