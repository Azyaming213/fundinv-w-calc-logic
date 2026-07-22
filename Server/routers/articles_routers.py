import requests
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas.auth_schema import StandardResponse
from dependencies import require_claim
import appconstants as AppConstants

router = APIRouter(prefix="/api/articles", tags=["Articles"])

YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}

SEARCH_QUERIES = {
    "market": "S&P 500 stock market",
    "tech": "technology stocks AAPL MSFT NVDA",
    "finance": "banking finance stocks JPM GS",
    "etf": "ETF index fund SPY QQQ",
}


def fetch_yahoo_news(query: str, category: str) -> list[dict]:
    try:
        resp = requests.get(
            YAHOO_SEARCH_URL,
            params={"q": query, "quotesCount": 0, "newsCount": 15},
            headers=YAHOO_HEADERS,
            timeout=10,
        )
        data = resp.json()
    except Exception:
        return []

    articles = []
    for item in data.get("news", []):
        tickers = item.get("relatedTickers", [])
        pub_date = item.get("providerPublishTime")

        from datetime import datetime, timezone
        published_iso = None
        if pub_date:
            try:
                published_iso = datetime.fromtimestamp(pub_date, tz=timezone.utc).isoformat()
            except Exception:
                pass

        articles.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "url": item.get("link", ""),
            "source": item.get("publisher", "Yahoo Finance"),
            "category": category,
            "tickers": [t for t in tickers if t and t != "NULL"],
            "published_at": published_iso,
        })

    return articles


@router.get("/", response_model=StandardResponse)
def list_articles(
    category: str = Query("", max_length=50),
    current_user: User = Depends(require_claim(AppConstants.CLAIMS["readArticles"])),
    db: Session = Depends(get_db),
):
    all_articles = []

    queries = (
        SEARCH_QUERIES.items() if not category else
        [(cat, q) for cat, q in SEARCH_QUERIES.items() if cat == category]
    )

    seen_urls = set()
    seen_titles = set()
    for cat, query in queries:
        articles = fetch_yahoo_news(query, cat)
        for article in articles:
            url = article.get("url", "")
            title = article.get("title", "")
            if url and url in seen_urls:
                continue
            if title and title in seen_titles:
                continue
            if url:
                seen_urls.add(url)
            seen_titles.add(title)
            all_articles.append(article)

    all_articles.sort(key=lambda a: a.get("published_at") or "", reverse=True)

    return StandardResponse(
        success=True,
        data={"articles": all_articles},
        error=None,
    )
