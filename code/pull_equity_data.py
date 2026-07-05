"""
Pull adjusted monthly price history for the 12-stock universe.

NOTE: This sandbox's network access is restricted to package registries
(pypi, npm, github, etc.) and cannot reach Yahoo Finance directly. Run this
script on your own machine (or Colab) where `pip install yfinance` and
outbound internet access both work.

Usage:
    pip install yfinance pandas
    python pull_equity_data.py
"""

import pandas as pd
import yfinance as yf
from pathlib import Path

# Draft 12-stock universe -- see pre_data_collection_checklist_draft.md
# Section 2 for the sector rationale. Update this list if you swap any names.
TICKERS = [
    "JNJ",  # Healthcare / pharma
    "PG",   # Consumer staples
    "KO",   # Consumer staples / beverage
    "XOM",  # Energy
    "JPM",  # Financials
    "MSFT", # Technology
    "IBM",  # Technology / legacy hardware
    "CAT",  # Industrials
    "MMM",  # Industrials / conglomerate
    "WMT",  # Retail
    "DIS",  # Media / entertainment
    "PFE",  # Pharma
]

# Draft start date -- adjust based on the "Open items" note in the checklist
# (all 12 names have decades of history, so this is a data-quality choice,
# not an inception-date constraint).
START_DATE = "1995-01-01"
END_DATE = None  # None = through today

# Output goes to a "data" folder next to this script, created automatically
# if it doesn't exist yet -- works regardless of whether you're using the
# /scripts + /data repo layout or a flat folder.
OUTPUT_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "equity_prices_monthly.csv"


def pull_prices():
    print(f"Pulling {len(TICKERS)} tickers from {START_DATE} to present...")
    raw = yf.download(
        TICKERS,
        start=START_DATE,
        end=END_DATE,
        interval="1mo",
        auto_adjust=True,   # adjusted close, dividends/splits baked in
        progress=False,
    )

    # yfinance returns a MultiIndex column frame when given multiple tickers;
    # pull just the Close (which is adjusted, since auto_adjust=True)
    prices = raw["Close"]

    # Report any tickers with missing/short history so you catch data gaps
    # before they surface as NaNs deep in the backtest.
    print("\nData coverage check:")
    for ticker in TICKERS:
        if ticker not in prices.columns:
            print(f"  {ticker}: NOT RETURNED -- check ticker symbol")
            continue
        series = prices[ticker].dropna()
        if series.empty:
            print(f"  {ticker}: NO DATA")
        else:
            print(f"  {ticker}: {series.index.min().date()} to {series.index.max().date()}  "
                  f"({len(series)} months)")

    prices.to_csv(OUTPUT_PATH)
    print(f"\nSaved monthly adjusted prices to {OUTPUT_PATH}")
    return prices


def compute_monthly_returns(prices):
    returns = prices.pct_change().dropna(how="all")
    returns_path = OUTPUT_DIR / "equity_returns_monthly.csv"
    returns.to_csv(returns_path)
    print(f"Saved monthly returns to {returns_path}")
    return returns


if __name__ == "__main__":
    prices = pull_prices()
    compute_monthly_returns(prices)


    