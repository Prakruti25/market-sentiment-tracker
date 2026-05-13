"""
Streamlit dashboard for the Market Sentiment Tracker.
Visualizes news sentiment vs. stock prices across tracked tickers.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so `from src...` imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.database import SessionLocal, NewsArticle, StockPrice, SentimentScore


# === PAGE CONFIG ===
st.set_page_config(
    page_title="Market Sentiment Tracker",
    page_icon="📈",
    layout="wide",
)


# === DATA LOADERS (cached for speed) ===
@st.cache_data(ttl=300)
def load_articles_with_sentiment() -> pd.DataFrame:
    session = SessionLocal()
    try:
        rows = (
            session.query(
                NewsArticle.ticker,
                NewsArticle.title,
                NewsArticle.publisher,
                NewsArticle.url,
                NewsArticle.published_at,
                SentimentScore.compound,
            )
            .join(SentimentScore, NewsArticle.id == SentimentScore.article_id)
            .all()
        )
        return pd.DataFrame(rows, columns=[
            "ticker", "title", "publisher", "url", "published_at", "sentiment"
        ])
    finally:
        session.close()


@st.cache_data(ttl=300)
def load_prices() -> pd.DataFrame:
    session = SessionLocal()
    try:
        rows = session.query(
            StockPrice.ticker, StockPrice.timestamp,
            StockPrice.open, StockPrice.high, StockPrice.low,
            StockPrice.close, StockPrice.volume,
        ).all()
        return pd.DataFrame(rows, columns=[
            "ticker", "timestamp", "open", "high", "low", "close", "volume"
        ])
    finally:
        session.close()


def mood_emoji(score: float) -> str:
    if score >= 0.05:
        return "🟢"
    if score <= -0.05:
        return "🔴"
    return "⚪"


# === SIDEBAR: REFRESH CONTROL ===
with st.sidebar:
    st.header("⚙️ Controls")
    st.write("Pull the latest news, prices, and run sentiment scoring.")
    if st.button("🔄 Refresh data", use_container_width=True):
        with st.spinner("Pulling latest news + prices..."):
            from src.data_collection import fetch_news, fetch_prices
            from src.database import save_news, save_prices
            from src.sentiment_analysis import score_unscored_articles

            tickers = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "GOOGL", "META"]
            news_df = fetch_news(tickers)
            if not news_df.empty:
                save_news(news_df)
            prices_df = fetch_prices(tickers, period="5d", interval="1h")
            if not prices_df.empty:
                save_prices(prices_df)
            score_unscored_articles()
            st.cache_data.clear()
        st.success("✅ Data refreshed!")
        st.rerun()

    st.divider()
    st.caption("Built with Python, SQLAlchemy, VADER, and Streamlit.")


# === LOAD DATA ===
articles = load_articles_with_sentiment()
prices = load_prices()


# === HEADER ===
st.title("📈 Market Sentiment Tracker")
st.markdown(
    "Real-time correlation between financial news sentiment and stock prices. "
    "Headlines scored with **VADER NLP**, prices from **Yahoo Finance**, stored in **SQLite**."
)

if articles.empty:
    st.warning("No data yet — click 🔄 Refresh data in the sidebar.")
    st.stop()


# === KPI ROW ===
c1, c2, c3, c4 = st.columns(4)
c1.metric("📰 Articles", f"{len(articles):,}")
c2.metric("💹 Price candles", f"{len(prices):,}")
c3.metric("🎯 Tickers tracked", articles["ticker"].nunique())

avg_sent = float(articles["sentiment"].mean())
mood_label = "Bullish 📈" if avg_sent > 0.05 else "Bearish 📉" if avg_sent < -0.05 else "Neutral ⚖️"
c4.metric("😊 Avg sentiment", f"{avg_sent:+.3f}", delta=mood_label)

st.divider()


# === TICKER DRILLDOWN ===
all_tickers = sorted(articles["ticker"].unique().tolist())
selected_ticker = st.selectbox("🔍 Select a ticker to drill into:", all_tickers)

ticker_articles = articles[articles["ticker"] == selected_ticker].sort_values("published_at")
ticker_prices = prices[prices["ticker"] == selected_ticker].sort_values("timestamp")


# === DUAL-AXIS CHART ===
st.subheader(f"📊 {selected_ticker} — Price vs Headline Sentiment")

fig = make_subplots(specs=[[{"secondary_y": True}]])

if not ticker_prices.empty:
    fig.add_trace(
        go.Scatter(
            x=ticker_prices["timestamp"],
            y=ticker_prices["close"],
            name="Price ($)",
            line=dict(color="#1f77b4", width=2.5),
            mode="lines",
        ),
        secondary_y=False,
    )

if not ticker_articles.empty:
    colors = [
        "#2ca02c" if s > 0.05 else "#d62728" if s < -0.05 else "#888"
        for s in ticker_articles["sentiment"]
    ]
    sizes = [max(10, abs(s) * 25) for s in ticker_articles["sentiment"]]
    fig.add_trace(
        go.Scatter(
            x=ticker_articles["published_at"],
            y=ticker_articles["sentiment"],
            name="Article sentiment",
            mode="markers",
            marker=dict(color=colors, size=sizes, line=dict(color="white", width=1)),
            text=ticker_articles["title"].str.slice(0, 90),
            hovertemplate="<b>%{text}</b><br>Sentiment: %{y:+.3f}<extra></extra>",
        ),
        secondary_y=True,
    )

fig.update_xaxes(title_text="Time")
fig.update_yaxes(title_text="Price ($)", secondary_y=False)
fig.update_yaxes(title_text="Sentiment", secondary_y=True, range=[-1, 1])
fig.update_layout(
    height=500,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=10, r=10, t=10, b=10),
)

st.plotly_chart(fig, use_container_width=True)


# === TWO-COLUMN BOTTOM ===
left, right = st.columns([3, 2])

with left:
    st.subheader(f"📰 Recent {selected_ticker} Headlines")
    if ticker_articles.empty:
        st.info("No articles for this ticker.")
    else:
        display_df = ticker_articles.sort_values("published_at", ascending=False).copy()
        display_df["Mood"] = display_df["sentiment"].apply(mood_emoji)
        display_df = display_df[["Mood", "published_at", "title", "publisher", "sentiment"]]
        display_df.columns = ["", "When", "Headline", "Source", "Score"]
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score": st.column_config.NumberColumn(format="%+.3f"),
                "When": st.column_config.DatetimeColumn(format="MMM D, h:mm a"),
            },
        )

with right:
    st.subheader("🏆 Sentiment by Ticker")
    summary = (
        articles.groupby("ticker")["sentiment"]
        .agg(["mean", "count"])
        .reset_index()
        .sort_values("mean")
    )
    bar = go.Figure(go.Bar(
        x=summary["mean"],
        y=summary["ticker"],
        orientation="h",
        marker_color=["#2ca02c" if v > 0 else "#d62728" for v in summary["mean"]],
        text=[f"{v:+.2f}  (n={c})" for v, c in zip(summary["mean"], summary["count"])],
        textposition="auto",
    ))
    bar.update_layout(
        height=400,
        xaxis_title="Average sentiment",
        xaxis_range=[-1, 1],
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(bar, use_container_width=True)


# === FOOTER ===
st.divider()
st.caption(
    f"Data: Yahoo Finance · Sentiment: VADER NLP · "
    f"Last rendered: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)