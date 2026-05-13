"""
Database setup for the Market Sentiment Tracker.
Uses SQLAlchemy with a local SQLite database stored at data/market.db.
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float, DateTime,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# Database file lives inside the data/ folder
DB_URL = "sqlite:///data/market.db"

engine = create_engine(DB_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class NewsArticle(Base):
    """One row per news article."""
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    title = Column(Text, nullable=False)
    summary = Column(Text)
    publisher = Column(String(100))
    url = Column(Text)
    published_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("ticker", "url", name="uq_ticker_url"),
    )


class StockPrice(Base):
    """One row per (ticker, timestamp) price candle."""
    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)

    __table_args__ = (
        UniqueConstraint("ticker", "timestamp", name="uq_ticker_timestamp"),
    )

class SentimentScore(Base):
    """One row per scored article. compound is the headline sentiment in [-1, +1]."""
    __tablename__ = "sentiment_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, nullable=False, unique=True, index=True)
    compound = Column(Float, nullable=False)   # overall sentiment, -1 (neg) to +1 (pos)
    positive = Column(Float)
    negative = Column(Float)
    neutral = Column(Float)
    scored_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)
    print("✅ Database initialized at data/market.db")


def save_news(df):
    """Insert news articles into the database, skipping duplicates."""
    if df.empty:
        print("⚠️  No news to save")
        return 0

    session = SessionLocal()
    inserted = 0
    try:
        for _, row in df.iterrows():
            # Skip if (ticker, url) already exists
            exists = session.query(NewsArticle).filter_by(
                ticker=row["ticker"], url=row["url"]
            ).first()
            if exists:
                continue

            article = NewsArticle(
                ticker=row["ticker"],
                title=row["title"],
                summary=row.get("summary", ""),
                publisher=row.get("publisher", ""),
                url=row["url"],
                published_at=row["published_at"],
            )
            session.add(article)
            inserted += 1

        session.commit()
        print(f"💾 Saved {inserted} new news articles to DB")
    except Exception as e:
        session.rollback()
        print(f"❌ Error saving news: {e}")
    finally:
        session.close()

    return inserted


def save_prices(df):
    """Insert stock price candles, skipping duplicates."""
    if df.empty:
        print("⚠️  No prices to save")
        return 0

    session = SessionLocal()
    inserted = 0
    try:
        for _, row in df.iterrows():
            exists = session.query(StockPrice).filter_by(
                ticker=row["ticker"], timestamp=row["timestamp"]
            ).first()
            if exists:
                continue

            price = StockPrice(
                ticker=row["ticker"],
                timestamp=row["timestamp"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            session.add(price)
            inserted += 1

        session.commit()
        print(f"💾 Saved {inserted} new price candles to DB")
    except Exception as e:
        session.rollback()
        print(f"❌ Error saving prices: {e}")
    finally:
        session.close()

    return inserted


if __name__ == "__main__":
    init_db()