"""SSRF-safe URL analysis, extraction, and reputation checking.

Inspects URLs without ever fetching them directly:
1. Google Web Risk lookup (when WEB_RISK_API_KEY is configured).
2. Safe heuristic pattern analysis (IP hostnames, suspicious TLDs, punycode,
   typosquatting keywords, URL shorteners) when API key is unavailable.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

WEB_RISK_ENDPOINT = "https://webrisk.googleapis.com/v1/uris:search"
DEFAULT_TIMEOUT = 5

URL_PATTERN = re.compile(
    r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
)

HIGH_RISK_TLDS = {
    "xyz", "top", "tk", "ml", "ga", "cf", "gq", "click", "buzz", "live", "loan",
    "work", "rest", "surf", "monster", "cfd", "online",
}

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "rb.gy", "goo.gl", "ow.ly",
}

BRAND_PHISHING_KEYWORDS = [
    "sbi", "hdfc", "icici", "axis", "pnb", "rbi", "kyc", "pan-card", "aadhaar",
    "paytm", "phonepe", "gpay", "electricity", "bill-payment", "challan", "police-fine",
    "courier-clearance", "customs-duty", "free-recharge", "lottery", "prize-claim",
]


def extract_urls(text: str) -> list[str]:
    """Extract and normalize all web URLs found in text."""
    if not text:
        return []
    matches = URL_PATTERN.findall(text)
    urls = []
    seen = set()
    for m in matches:
        raw_url = m[0] if isinstance(m, tuple) else m
        if not raw_url:
            continue
        if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
            candidate = f"https://{raw_url}"
        else:
            candidate = raw_url

        try:
            parsed = urlparse(candidate)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                clean_url = candidate.strip().rstrip(".,;:)'\"")
                if clean_url not in seen:
                    seen.add(clean_url)
                    urls.append(clean_url)
        except Exception:
            continue

    return urls


class UrlAnalyzer:
    """Safe URL intelligence checking without executing user links."""

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.api_key = (api_key or os.getenv("WEB_RISK_API_KEY", "")).strip()
        self.session = session or requests.Session()
        self.timeout = timeout

    def check_url_reputation(self, url: str) -> dict[str, Any]:
        """Check URL against Google Web Risk API or safe heuristic rules."""
        if not url:
            return {"status": "error", "reason": "empty_url"}

        # 1. Reject unsafe schemes directly
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return {
                "status": "unsafe_scheme",
                "url": url,
                "threats": ["MALICIOUS_SCHEME"],
                "reason": f"Disallowed scheme: {parsed.scheme}",
            }

        hostname = (parsed.hostname or "").lower()

        # 2. SSRF Guard: Reject internal IPs / localhost / private networks
        if self._is_private_or_internal(hostname):
            return {
                "status": "blocked",
                "url": url,
                "threats": ["PRIVATE_IP_OR_LOCALHOST"],
                "reason": "Host points to internal or loopback address",
            }

        # 3. If Google Web Risk API key is configured, perform remote query
        if self.api_key:
            web_risk_res = self._check_web_risk(url)
            if web_risk_res.get("status") == "ok":
                return web_risk_res

        # 4. Fallback: Safe Heuristic URL Reputation Analysis
        return self._heuristic_analysis(url, hostname)

    def _is_private_or_internal(self, hostname: str) -> bool:
        """Check if hostname points to private or loopback networks."""
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return True
        if re.match(r"^10\.|^192\.168\.|^172\.(1[6-9]|2[0-9]|3[0-1])\.|^169\.254\.", hostname):
            return True
        return False

    def _check_web_risk(self, url: str) -> dict[str, Any]:
        """Query Google Web Risk API (hardcoded endpoint)."""
        params = {
            "uri": url,
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "key": self.api_key,
        }
        try:
            resp = self.session.get(WEB_RISK_ENDPOINT, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                threats = data.get("threat", {}).get("threatTypes", [])
                return {
                    "status": "ok",
                    "url": url,
                    "threats": threats,
                    "source": "Google Web Risk",
                }
            logger.warning("Web Risk API error HTTP %s: %s", resp.status_code, resp.text[:120])
            return {"status": "unavailable", "reason": f"HTTP {resp.status_code}"}
        except Exception as e:
            logger.info("Web Risk query failed: %s", e)
            return {"status": "unavailable", "reason": str(e)}

    def _heuristic_analysis(self, url: str, hostname: str) -> dict[str, Any]:
        """Heuristic check for phishing indicators when Web Risk key is absent."""
        threats: list[str] = []
        signals: list[str] = []

        # Check for IP address as hostname (e.g. http://185.220.101.5/...)
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", hostname):
            threats.append("IP_HOST_ADDRESS")
            signals.append("Numerical IP address used as website address")

        # Check for high-risk TLD
        tld = hostname.split(".")[-1] if "." in hostname else ""
        if tld in HIGH_RISK_TLDS:
            signals.append(f"High-risk top-level domain (.{tld})")
            # If coupled with brand keywords, treat as social engineering
            if any(k in hostname for k in BRAND_PHISHING_KEYWORDS):
                threats.append("SOCIAL_ENGINEERING")

        # Check for Punycode / IDN lookalike
        if "xn--" in hostname:
            threats.append("PUNYCODE_LOOKALIKE")
            signals.append("Punycode internationalized domain mimicry")

        # Check for brand impersonation keywords in non-official domains
        matched_brands = [b for b in BRAND_PHISHING_KEYWORDS if b in hostname]
        if matched_brands:
            signals.append(f"Suspicious brand keyword in hostname: {', '.join(matched_brands)}")
            if len(matched_brands) >= 2 or tld in HIGH_RISK_TLDS:
                threats.append("SOCIAL_ENGINEERING")

        # Check for URL shorteners
        if hostname in SHORTENERS:
            signals.append("Obfuscated URL shortener link")

        # Excessive subdomain nesting
        if hostname.count(".") >= 4:
            signals.append("Excessive subdomain depth")

        return {
            "status": "ok",
            "url": url,
            "threats": threats,
            "signals": signals,
            "source": "TruthCheck URL Heuristics",
        }
