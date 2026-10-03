"""Sender authentication and email header analysis.

Extracts and validates SPF, DKIM, and DMARC results from RFC 8601
Authentication-Results headers. Flags authentication failures which strongly
indicate sender address spoofing.
"""
from __future__ import annotations

import re
from typing import Any

SPF_REGEX = re.compile(
    r"\bspf\s*=\s*(pass|fail|softfail|neutral|none|temperror|permerror)\b",
    re.IGNORECASE,
)
DKIM_REGEX = re.compile(
    r"\bdkim\s*=\s*(pass|fail|neutral|none|temperror|permerror|policy)\b",
    re.IGNORECASE,
)
DMARC_REGEX = re.compile(
    r"\bdmarc\s*=\s*(pass|fail|none|temperror|permerror)\b",
    re.IGNORECASE,
)
FROM_REGEX = re.compile(
    r"(?i)\bFrom:\s*([^\r\n<]+)?(?:<([^>]+)>)?",
)


def normalize_auth_verdict(raw: str | None) -> str:
    """Normalize RFC 8601 auth results into 'pass', 'fail', or 'none'."""
    if not raw:
        return "none"
    v = raw.strip().lower()
    if v == "pass":
        return "pass"
    if v in ("fail", "softfail", "temperror", "permerror"):
        return "fail"
    return "none"


class SenderAnalyzer:
    """Analyzes email sender authentication headers."""

    def analyze_sender_auth(self, headers_text: str | None) -> dict[str, Any]:
        """Parse authentication headers for SPF/DKIM/DMARC status."""
        if not headers_text or not isinstance(headers_text, str) or not headers_text.strip():
            return {
                "status": "unavailable",
                "spf": "none",
                "dkim": "none",
                "dmarc": "none",
                "has_auth": False,
                "is_spoofed": False,
                "sender_info": {},
            }

        raw = headers_text.strip()

        spf_match = SPF_REGEX.search(raw)
        dkim_match = DKIM_REGEX.search(raw)
        dmarc_match = DMARC_REGEX.search(raw)

        spf = normalize_auth_verdict(spf_match.group(1) if spf_match else None)
        dkim = normalize_auth_verdict(dkim_match.group(1) if dkim_match else None)
        dmarc = normalize_auth_verdict(dmarc_match.group(1) if dmarc_match else None)

        has_auth = bool(spf_match or dkim_match or dmarc_match)

        # Extract From name and address if available
        sender_info: dict[str, str] = {}
        from_match = FROM_REGEX.search(raw)
        if from_match:
            display_name = (from_match.group(1) or "").strip(' \t\r\n"\'')
            email_addr = (from_match.group(2) or "").strip()
            if display_name:
                sender_info["display_name"] = display_name
            if email_addr:
                sender_info["email"] = email_addr

        # Determine status
        if not has_auth:
            status = "unavailable"
        else:
            status = "ok"

        return {
            "status": status,
            "spf": spf,
            "dkim": dkim,
            "dmarc": dmarc,
            "has_auth": has_auth,
            "is_spoofed": (spf == "fail" or dkim == "fail" or dmarc == "fail"),
            "sender_info": sender_info,
        }
