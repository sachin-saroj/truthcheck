"""SSRF-safe domain analysis and domain age verification via RDAP.

Queries https://rdap.org/domain/{domain} to retrieve authoritative domain
registration date and calculate age in days. Newly registered domains (< 7 days)
are strong indicators of ephemeral phishing infrastructure.

Security:
- Never executes user-supplied URLs
- Strictly validates domain strings with regex (rejects schemes, paths, IPs, ports, localhost)
- Enforces strict 5-second timeout and in-process TTL caching
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

RDAP_BASE = "https://rdap.org/domain/"
DEFAULT_TIMEOUT = 5
CACHE_TTL = 3600  # 1 hour

# Strict alphanumeric dot-separated labels, no ports/schemes/paths/spaces
DOMAIN_REGEX = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$",
    re.IGNORECASE,
)

# Reject localhost, loopback, private IPs, and link-local metadata
DISALLOWED_PATTERNS = [
    re.compile(r"^localhost$", re.IGNORECASE),
    re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"),
    re.compile(r"^127\."),
    re.compile(r"^10\."),
    re.compile(r"^192\.168\."),
    re.compile(r"^172\.(1[6-9]|2[0-9]|3[0-1])\."),
    re.compile(r"^169\.254\."),
    re.compile(r":"),  # IPv6
]

_cache: dict[str, tuple[dict[str, Any], float]] = {}


def extract_domain(input_str: str) -> str | None:
    """Extract clean domain name from a URL or raw domain string."""
    if not input_str or not isinstance(input_str, str):
        return None

    cleaned = input_str.strip().lower()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        try:
            parsed = urlparse(cleaned)
            cleaned = parsed.hostname or ""
        except Exception:
            return None

    # Remove ports if accidentally attached
    if ":" in cleaned:
        cleaned = cleaned.split(":")[0]

    cleaned = cleaned.rstrip(".")
    if not cleaned or not DOMAIN_REGEX.match(cleaned):
        return None

    for pattern in DISALLOWED_PATTERNS:
        if pattern.search(cleaned):
            return None

    return cleaned


class DomainAnalyzer:
    """Queries RDAP proxy for domain age while guaranteeing SSRF safety."""

    def __init__(self, session: requests.Session | None = None, timeout: int = DEFAULT_TIMEOUT):
        self.session = session or requests.Session()
        self.timeout = timeout

    def check_domain_age(self, target: str) -> dict[str, Any]:
        """Lookup registration date and age in days for the given domain."""
        domain = extract_domain(target)
        if not domain:
            return {
                "status": "invalid_domain",
                "domain": target,
                "reason": "Invalid or disallowed domain name",
            }

        now = time.time()
        cached = _cache.get(domain)
        if cached and cached[1] > now:
            return cached[0]

        url = f"{RDAP_BASE}{domain}"
        headers = {
            "Accept": "application/rdap+json, application/json",
            "User-Agent": "TruthCheck/1.0",
        }

        try:
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code == 404:
                result = {"status": "not_found", "domain": domain, "reason": "Domain not registered in RDAP"}
                _cache[domain] = (result, now + CACHE_TTL)
                return result

            if resp.status_code != 200:
                return {
                    "status": "unknown",
                    "domain": domain,
                    "reason": f"RDAP service returned status {resp.status_code}",
                }

            data = resp.json()
            events = data.get("events", [])
            reg_date_str = None
            for ev in events:
                if isinstance(ev, dict) and ev.get("eventAction") == "registration":
                    reg_date_str = ev.get("eventDate")
                    break

            if not reg_date_str:
                result = {"status": "unknown", "domain": domain, "reason": "No registration event in record"}
                _cache[domain] = (result, now + CACHE_TTL)
                return result

            # Parse ISO 8601 timestamp
            # Normal format e.g. 2024-05-10T12:00:00Z
            clean_date = reg_date_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            current_dt = datetime.now(timezone.utc)
            age_days = max(0, (current_dt - dt).days)

            result = {
                "status": "ok",
                "domain": domain,
                "registered_at": reg_date_str,
                "age_days": age_days,
                "is_young": age_days < 7,
            }
            _cache[domain] = (result, now + CACHE_TTL)
            return result

        except Exception as e:
            logger.info("RDAP lookup failed for %s: %s", domain, e)
            return {
                "status": "unknown",
                "domain": domain,
                "reason": "Lookup timed out or network error",
            }


def clear_cache_for_tests() -> None:
    _cache.clear()
