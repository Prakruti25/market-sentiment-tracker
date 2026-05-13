"""
Financial news data collector for the Market Sentiment Tracker.
Pulls recent news headlines for given stock tickers via Yahoo Finance.
"""

import time
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone


def fetch_news(tickers: list) -> pd.DataFrame:
    """
    Fetch recent news headlines for a list of stock tickers.

    Args:
        tickers: List of stock symbols (e.g., ['NVDA', 'TSLA']).

    Returns:
        DataFrame with news article metadata.
    """
    records = []

    for ticker_symbol in tickers:
        print(f"📰 Fetching news for {ticker_symbol}...")
        ticker = yf.Ticker(ticker_symbol)

        try:
            news_items = ticker.news or []
        except Exception as e:
            print(f"⚠️  Error fetching {ticker_symbol}: {e}")
            continue

        for item in news_items:
            # yfinance wraps news in a 'content' object in newer versions
            content = item.get("content", item)

            title = content.get("title", "")
            summary = content.get("summary") or content.get("description", "")

            # Publisher can live in different places depending on yfinance version
            provider = content.get("provider")
            if isinstance(provider, dict):
                publisher = provider.get("displayName", "")
            else:
                publisher = content.get("publisher", "")

            # URL can also vary
            canonical = content.get("canonicalUrl")
            if isinstance(canonical, dict):
                url = canonical.get("url", "")
            else:
                url = content.get("link", "")

            # Parse date safely
            pub_date_str = content.get("pubDate", "")
            try:
                pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pub_date = datetime.now(timezone.utc)

            if title:  # only keep records with an actual headline
                records.append({
                    "ticker": ticker_symbol,
                    "title": title,
                    "summary": summary,
                    "publisher": publisher,
                    "url": url,
                    "published_at": pub_date,
                })

        time.sleep(0.5)  # be polite to Yahoo's servers

    df = pd.DataFrame(records)
    print(f"✅ Fetched {len(df)} articles total")
    return df

def fetch_prices(tickers: list, period: str = "5d", interval: str = "1h") -> pd.DataFrame:
    """
    Fetch historical stock prices for a list of tickers.

    Args:
        tickers: List of stock symbols.
        period: How far back to pull (e.g., '1d', '5d', '1mo', '3mo', '1y').
        interval: Candle interval (e.g., '1m', '5m', '1h', '1d').

    Returns:
        Long-format DataFrame with one row per (ticker, timestamp).
    """
    print(f"💹 Fetching price data ({period}, {interval}) for {len(tickers)} tickers...")

    # yfinance returns wide format with multi-index columns when given a list
    raw = yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        group_by="ticker",
        auto_adjust=True,
        progress=False,
    )

    records = []
    for ticker_symbol in tickers:
        try:
            df_ticker = raw[ticker_symbol].copy()
        except KeyError:
            print(f"⚠️  No price data for {ticker_symbol}")
            continue

        df_ticker = df_ticker.dropna().reset_index()
        df_ticker.columns = [c.lower() for c in df_ticker.columns]

        # Standardize timestamp column name (yfinance uses Datetime or Date)
        ts_col = "datetime" if "datetime" in df_ticker.columns else "date"

        for _, row in df_ticker.iterrows():
            records.append({
                "ticker": ticker_symbol,
                "timestamp": pd.to_datetime(row[ts_col]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
            })

    df = pd.DataFrame(records)
    print(f"✅ Fetched {len(df)} price candles total")
    return df

if __name__ == "__main__":
    from database import init_db, save_news, save_prices

    # Make sure tables exist
    init_db()

    # Watchlist of tickers to track
    tickers = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "GOOGL", "META"]

    # Fetch news
    news_df = fetch_news(tickers)
    if not news_df.empty:
        news_df.to_csv("data/raw/news_latest.csv", index=False)
        save_news(news_df)

    # Fetch prices (last 5 days, hourly candles)
    prices_df = fetch_prices(tickers, period="5d", interval="1h")
    if not prices_df.empty:
        prices_df.to_csv("data/raw/prices_latest.csv", index=False)
        save_prices(prices_df)

    print("\n🎉 Pipeline complete!")