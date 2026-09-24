"""Live internet search service using DDGS for real-world fact verification.

Retrieves actual live news coverage, fact-checking portal reports, and
authoritative sources to ground claims in empirical evidence.
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

logger = logging.getLogger(__name__)

# Search stopwords that dilute search queries
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "and", "or", "for", "with",
    "that", "this", "it", "at", "by", "from", "be", "has", "have", "had",
    "will", "would", "could", "should", "about", "what", "when", "where",
    "who", "which", "why", "how", "you", "your", "they", "their", "we", "our",
    "says", "said", "reported", "breaking", "update", "shocking", "urgent",
}


def clean_query_text(text: str, max_words: int = 8) -> str:
    """Extract core factual claim keywords from input text."""
    if not text:
        return ""
    # Use first sentence or up to newline
    first_chunk = text.strip().splitlines()[0]
    first_chunk = re.split(r"[.!?]", first_chunk)[0]
    # Keep alphanumeric words and common punctuation
    cleaned = re.sub(r"[^\w\s-]", " ", first_chunk)
    words = [w for w in cleaned.split() if w.lower() not in _STOPWORDS and len(w) > 1]
    if len(words) < 2:
        words = [w for w in cleaned.split() if len(w) > 1]
    return " ".join(words[:max_words]).strip()


def extract_source_name(url: str, default: str = "Web Source") -> str:
    """Extract clean display domain/source name from URL."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        parts = netloc.split(".")
        if len(parts) >= 2:
            return parts[-2].capitalize()
        return netloc or default
    except Exception:
        return default


def is_safe_url(url: str) -> bool:
    """Ensure URL is http/https and has a valid domain."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


class SearchService:
    """Service to search the live web and news for evidence on claims."""

    def __init__(self, cache_size: int = 50):
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._cache_size = cache_size

    def search_evidence(self, text: str, max_results: int = 6) -> list[dict[str, Any]]:
        """Search live news and web for factual evidence regarding text."""
        query = clean_query_text(text)
        if not query:
            return []

        cache_key = query.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        if DDGS is None:
            logger.warning("DDGS library not available for search.")
            return []

        try:
            ddgs = DDGS(timeout=4)
            # 1. First, search live news articles (fastest & most authoritative)
            try:
                news_items = list(ddgs.news(query, max_results=max_results))
                for item in news_items:
                    url = item.get("url") or item.get("href") or ""
                    if not url or url in seen_urls or not is_safe_url(url):
                        continue
                    seen_urls.add(url)
                    source_name = item.get("source") or extract_source_name(url)
                    results.append({
                        "title": item.get("title", "").strip(),
                        "url": url,
                        "source": source_name,
                        "snippet": (item.get("body") or item.get("excerpt") or "").strip(),
                        "date": item.get("date", ""),
                        "type": "news",
                    })
            except Exception as news_err:
                logger.info("News search had no hits or failed: %s", news_err)

            # 2. Only do a second query if news returned fewer than 3 sources
            if len(results) < 3:
                needed = max_results - len(results)
                try:
                    text_items = list(ddgs.text(f"{query} fact check", max_results=needed + 1))
                    for item in text_items:
                        url = item.get("href") or item.get("url") or ""
                        if not url or url in seen_urls or not is_safe_url(url):
                            continue
                        seen_urls.add(url)
                        source_name = extract_source_name(url)
                        results.append({
                            "title": item.get("title", "").strip(),
                            "url": url,
                            "source": source_name,
                            "snippet": (item.get("body") or "").strip(),
                            "date": "",
                            "type": "web",
                        })
                        if len(results) >= max_results:
                            break
                except Exception as text_err:
                    logger.info("Web text search had no hits or failed: %s", text_err)

        except Exception as e:
            logger.error("Live search failed for query %r: %s", query, e)

        # Store in cache
        if len(self._cache) >= self._cache_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key] = results
        return results
