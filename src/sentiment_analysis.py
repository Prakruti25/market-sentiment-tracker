"""
Sentiment scoring for news articles using VADER.
Reads unscored articles from the DB, computes sentiment, writes results back.
"""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from src.database import SessionLocal, NewsArticle, SentimentScore


def score_text(analyzer: SentimentIntensityAnalyzer, text: str) -> dict:
    """Return VADER sentiment scores for a piece of text."""
    if not text or not text.strip():
        return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}
    return analyzer.polarity_scores(text)


def score_unscored_articles():
    """Score every article in the DB that doesn't have a sentiment row yet."""
    analyzer = SentimentIntensityAnalyzer()
    session = SessionLocal()
    scored_count = 0

    try:
        # Find which article IDs are already scored
        already_scored = {
            row[0] for row in session.query(SentimentScore.article_id).all()
        }

        # Pull articles that haven't been scored yet
        query = session.query(NewsArticle)
        if already_scored:
            query = query.filter(~NewsArticle.id.in_(already_scored))
        articles = query.all()

        print(f"📝 Scoring {len(articles)} new article(s)...")

        for article in articles:
            # Combine title + summary for richer context
            text = f"{article.title}. {article.summary or ''}"
            scores = score_text(analyzer, text)

            sentiment = SentimentScore(
                article_id=article.id,
                compound=scores["compound"],
                positive=scores["pos"],
                negative=scores["neg"],
                neutral=scores["neu"],
            )
            session.add(sentiment)
            scored_count += 1

        session.commit()
        print(f"✅ Saved {scored_count} sentiment scores to DB")
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
    finally:
        session.close()


def show_extremes(top_n: int = 5):
    """Display the most positive and most negative headlines in the DB."""
    session = SessionLocal()
    try:
        results = (
            session.query(NewsArticle.ticker, NewsArticle.title, SentimentScore.compound)
            .join(SentimentScore, NewsArticle.id == SentimentScore.article_id)
            .all()
        )
        if not results:
            print("No scored articles yet.")
            return

        sorted_results = sorted(results, key=lambda r: r[2], reverse=True)

        print(f"\n🟢 TOP {top_n} MOST POSITIVE HEADLINES:")
        for ticker, title, score in sorted_results[:top_n]:
            print(f"  [{score:+.3f}] {ticker} — {title[:100]}")

        print(f"\n🔴 TOP {top_n} MOST NEGATIVE HEADLINES:")
        for ticker, title, score in sorted_results[-top_n:]:
            print(f"  [{score:+.3f}] {ticker} — {title[:100]}")
    finally:
        session.close()


if __name__ == "__main__":
    score_unscored_articles()
    show_extremes(top_n=5)