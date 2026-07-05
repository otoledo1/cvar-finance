"""
Pull SPY monthly adjusted prices -- used ONLY as the equity-momentum
regime-classification signal (Formula 3's first component), not as a
portfolio holding. Your actual holdings are the 12 stocks pulled by
pull_equity_data.py; SPY here is a broad-market proxy for "is the market
in an uptrend," kept separate so it's clear it's a regime input, not
part of the investable universe.

Usage:
    python pull_market_benchmark.py
"""

import pandas as pd
import yfinance as yf
from pathlib import Path

START_DATE = "1995-01-01"
END_DATE = None

OUTPUT_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "spy_prices_monthly.csv"


def pull_spy():
    print("Pulling SPY (regime-signal only, not a portfolio holding)...")
    raw = yf.download(
        "SPY",
        start=START_DATE,
        end=END_DATE,
        interval="1mo",
        auto_adjust=True,
        progress=False,
    )
    prices = raw["Close"]
    prices = prices.dropna()
    print(f"  SPY: {prices.index.min().date()} to {prices.index.max().date()} "
          f"({len(prices)} months)")
    prices.to_csv(OUTPUT_PATH)
    print(f"Saved to {OUTPUT_PATH}")
    return prices


if __name__ == "__main__":
    pull_spy()


