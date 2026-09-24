"""External verification service (FreeNewsAPI.ai).

The API provides *related coverage / context* for a claim — it does not replace
the ML model and is never called directly from the browser.
FreeNewsAPI.ai requires no API key.
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

FREENEWS_SEARCH_URL = "https://freenewsapi.ai/v1/search"
TIMEOUT_SECONDS = 8

# Words that add noise to a news search query (stopwords, temporal markers, generic reporting verbs).
_EXTENDED_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "at", "is", "are", "was", "were",
    "and", "or", "for", "with", "that", "this", "it", "as", "by", "from", "be",
    "has", "have", "had", "not", "but", "his", "her", "their", "its", "will",
    "would", "could", "should", "about", "into", "than", "then", "them",
    "they", "you", "your", "we", "our", "us", "he", "she", "who", "what",
    "when", "where", "how", "why", "said", "says", "according", "expected",
    "issued", "told", "also", "after", "before", "during", "over", "under",
    "more", "most", "some", "any", "all", "each", "every", "am", "pm",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "yesterday", "today", "tomorrow", "new", "announced", "confirmed", "reported",
}


def build_search_query(text: str, max_words: int = 5) -> str:
    """Turn submitted text into a short, entity-rich search query.

    Filters out conversational lead-ins ('According to...'), reporting verbs,
    temporal markers ('Monday'), and grammatical stopwords, prioritizing
    core topical nouns and entities (e.g. 'Ministry Education scholarship scheme').
    """
    if not text:
        return ""
    raw = str(text).strip().splitlines()[0]
    raw = raw.split(".")[0]
    # Alphanumeric + spaces only (kills quotes, dashes, emojis, colons…)
    raw = re.sub(r"[^A-Za-z0-9\s]", " ", raw)
    tokens = raw.split()
    content = [t for t in tokens if t.lower() not in _EXTENDED_STOPWORDS]
    if len(content) < 2:
        basic_stop = {"the", "a", "an", "of", "to", "in", "on", "at", "is", "was", "for", "with", "that", "this", "it", "and"}
        content = [t for t in tokens if t.lower() not in basic_stop] or tokens

    query = " ".join(content[:max_words])
    return re.sub(r"\s+", " ", query).strip()


class VerificationService:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        session: requests.Session | None = None,
    ):
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or FREENEWS_SEARCH_URL).strip()
        self.session = session or requests.Session()
        # Tiny in-process cache so repeated demos don't burn network requests.
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_max = 50

    @property
    def is_configured(self) -> bool:
        """FreeNewsAPI.ai is a public keyless endpoint and is ready by default."""
        return True

    def search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """Return {status, message, sources}.

        status ∈ ok | no_results | error

        Messages are user-facing: friendly, no key names, no HTTP codes,
        no stack traces — technical detail goes to the server log only.
        """
        unavailable = (
            "Verification sources are temporarily unavailable. "
            "The language-pattern analysis is still available."
        )
        no_results_msg = "No matching verification sources were found."

        query = build_search_query(query)
        if not query:
            return {"status": "no_results", "message": no_results_msg, "sources": []}

        cache_key = f"{query}|{max_results}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        headers = {
            "Accept": "application/json",
            "User-Agent": "TruthCheck/1.0",
        }
        params: dict[str, Any] = {
            "q": query,
            "size": max_results,
        }

        try:
            resp = self.session.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.warning("Verification API request failed: %s", exc)
            return {"status": "error", "message": unavailable, "sources": []}

        if resp.status_code in (401, 403):
            logger.error("Verification API auth/access failed (HTTP %s)", resp.status_code)
            return {"status": "error", "message": unavailable, "sources": []}

        if resp.status_code == 429:
            logger.warning("Verification API rate limited (HTTP 429)")
            return {"status": "error", "message": unavailable, "sources": []}

        if resp.status_code == 400:
            logger.warning(
                "Verification API rejected query %r: %s", query, resp.text[:240]
            )
            # Fall back: retry once with a minimal 3-keyword query.
            minimal = " ".join(query.split()[:3])
            if minimal and minimal != query:
                try:
                    retry = self.session.get(
                        self.base_url,
                        params={"q": minimal, "size": max_results},
                        headers=headers,
                        timeout=TIMEOUT_SECONDS,
                    )
                    if retry.status_code == 200:
                        resp = retry
                    else:
                        logger.warning("Minimal-query retry HTTP %s", retry.status_code)
                        return {"status": "error", "message": unavailable, "sources": []}
                except requests.RequestException:
                    return {"status": "error", "message": unavailable, "sources": []}
            else:
                return {"status": "error", "message": unavailable, "sources": []}

        if resp.status_code != 200:
            logger.warning("Verification API HTTP %s: %s", resp.status_code, resp.text[:200])
            return {"status": "error", "message": unavailable, "sources": []}

        try:
            payload = resp.json()
        except (ValueError, TypeError):
            logger.warning("Verification API returned non-JSON body")
            return {"status": "error", "message": unavailable, "sources": []}

        if not isinstance(payload, dict):
            logger.warning("Verification API returned unexpected top-level payload: %s", type(payload))
            return {"status": "error", "message": unavailable, "sources": []}

        raw_results = payload.get("results")
        if raw_results is None or not isinstance(raw_results, list):
            logger.warning("Verification API payload missing or invalid results field")
            return {"status": "no_results", "message": no_results_msg, "sources": []}

        sources = []
        for art in raw_results:
            if not isinstance(art, dict):
                continue
            title = (art.get("title") or "").strip() if isinstance(art.get("title"), str) else ""
            url = (art.get("url") or "").strip() if isinstance(art.get("url"), str) else ""
            if not title or not url:
                continue
            if not self._safe_url(url):
                logger.warning("Dropped source with unsafe or invalid URL: %r", url)
                continue

            sitename = (art.get("sitename") or "").strip() if isinstance(art.get("sitename"), str) else ""
            host = (art.get("host") or "").strip() if isinstance(art.get("host"), str) else ""
            source_name = sitename or host or "Unknown source"

            published_at = (art.get("published_at") or "").strip() if isinstance(art.get("published_at"), str) else ""
            raw_desc = art.get("description")
            description = raw_desc.strip()[:240] if isinstance(raw_desc, str) else ""

            sources.append({
                "title": title,
                "url": url,
                "source": source_name,
                "publishedAt": published_at,
                "description": description,
            })
            if len(sources) >= max_results:
                break

        if not sources:
            result = {"status": "no_results", "message": no_results_msg, "sources": []}
        else:
            result = {
                "status": "ok",
                "message": f"Found {len(sources)} related article{'s' if len(sources) != 1 else ''}.",
                "sources": sources,
            }

        # Cache only definitive answers (not transient errors) to save requests.
        if result["status"] in {"ok", "no_results"}:
            if len(self._cache) >= self._cache_max:
                self._cache.pop(next(iter(self._cache)))
            self._cache[cache_key] = result
        return result

    @staticmethod
    def _safe_url(url: Any) -> bool:
        """Only allow valid http(s) source links with a non-empty domain."""
        if not isinstance(url, str):
            return False
        url = url.strip()
        if not url:
            return False
        try:
            parsed = urlparse(url)
            return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)
        except Exception:
            return False
