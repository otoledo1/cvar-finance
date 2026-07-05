"""
Pull current shares outstanding for the 12-stock universe, used to build
the cap-weighted index benchmark (market cap = price * shares outstanding).

IMPORTANT SIMPLIFICATION, flagged rather than hidden: this uses each
stock's CURRENT shares outstanding as a static value applied across the
whole backtest (i.e. market cap at each historical month = that month's
price * TODAY's share count). This captures price-driven changes in
relative market cap correctly, but not share-count changes over time
(buybacks, issuances, splits already handled by adjusted prices). For a
12-large-cap-stock universe over a multi-decade backtest, this is a
standard and defensible simplification for a benchmark, but it should be
named as a limitation in the paper, not presented as precise historical
market cap.

Usage:
    python pull_market_caps.py
"""

import pandas as pd
import yfinance as yf
from pathlib import Path

TICKERS = [
    "JNJ", "PG", "KO", "XOM", "JPM", "MSFT",
    "IBM", "CAT", "MMM", "WMT", "DIS", "PFE",
]

OUTPUT_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "shares_outstanding.csv"


def pull_shares_outstanding():
    rows = []
    print("Pulling current shares outstanding (static, see docstring for caveat)...")
    for ticker in TICKERS:
        info = yf.Ticker(ticker).get_info()
        shares = info.get("sharesOutstanding")
        rows.append({"ticker": ticker, "shares_outstanding": shares})
        print(f"  {ticker}: {shares}")

    df = pd.DataFrame(rows).set_index("ticker")
    missing = df[df["shares_outstanding"].isna()]
    if not missing.empty:
        print(f"\nWARNING: missing shares outstanding for {list(missing.index)}. "
              "Cap-weighted index will need a fallback (e.g. equal weight) "
              "for these names unless you fill this in manually.")

    df.to_csv(OUTPUT_PATH)
    print(f"\nSaved to {OUTPUT_PATH}")
    return df


if __name__ == "__main__":
    pull_shares_outstanding()



