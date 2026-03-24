"""Fetch company news from Finnhub for mover events."""

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import finnhub

import config

_last_call_time = 0.0


def _rate_limit():
    """Simple rate limiter: sleep if needed to stay under Finnhub's 60/min."""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < config.FINNHUB_DELAY:
        time.sleep(config.FINNHUB_DELAY - elapsed)
    _last_call_time = time.time()


def _cache_path(ticker: str, event_date: str) -> Path:
    return Path(config.CACHE_DIR) / f"news_{ticker}_{event_date}.json"


def fetch_news_for_mover(
    ticker: str,
    event_date: str,
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch news articles for a ticker around an event date.

    Searches Finnhub company news in a ±1 day window around the event.
    Returns list of dicts with keys: headline, summary, url, source, published_at
    """
    cache_file = _cache_path(ticker, event_date)

    if not force_refresh and cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    if not config.FINNHUB_API_KEY:
        return []

    client = finnhub.Client(api_key=config.FINNHUB_API_KEY)
    event_dt = date.fromisoformat(event_date)
    from_date = (event_dt - timedelta(days=1)).isoformat()
    to_date = (event_dt + timedelta(days=1)).isoformat()

    articles = []
    try:
        _rate_limit()
        raw = client.company_news(ticker, _from=from_date, to=to_date)

        for item in (raw or [])[:20]:  # Cap at 20 articles
            articles.append({
                "headline": item.get("headline", ""),
                "summary": item.get("summary", "")[:500],
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "published_at": item.get("datetime", ""),
            })
    except Exception as e:
        print(f"  Finnhub error for {ticker}: {e}")
        # Retry once after delay
        try:
            time.sleep(2)
            _rate_limit()
            raw = client.company_news(ticker, _from=from_date, to=to_date)
            for item in (raw or [])[:20]:
                articles.append({
                    "headline": item.get("headline", ""),
                    "summary": item.get("summary", "")[:500],
                    "url": item.get("url", ""),
                    "source": item.get("source", ""),
                    "published_at": item.get("datetime", ""),
                })
        except Exception as e2:
            print(f"  Finnhub retry failed for {ticker}: {e2}")

    # Deduplicate by headline
    seen = set()
    deduped = []
    for a in articles:
        h = a["headline"].strip().lower()
        if h and h not in seen:
            seen.add(h)
            deduped.append(a)

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(deduped, f)

    return deduped
