"""Message and email content parsing, normalization, and URL extraction.

Supports SMS, WhatsApp messages, social media text, and raw RFC822/MIME emails.
Safely extracts message bodies, header metadata, authentication results, and
folds oversized tracking URLs to protect downstream token limits.
"""
from __future__ import annotations

import email
from email.header import decode_header
import re
from typing import Any

from services.url_analyzer import extract_urls

MAX_MESSAGE_LENGTH = 8000
MAX_AUTH_LENGTH = 4000
URL_FOLD_THRESHOLD = 65


def decode_mime_header(header_val: str | None) -> str:
    """Decode RFC2047 encoded words in email headers (e.g. Subject, From)."""
    if not header_val:
        return ""
    try:
        decoded_parts = decode_header(header_val)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                result.append(str(part))
        return "".join(result).strip()
    except Exception:
        return str(header_val).strip()


def fold_long_urls(text: str, threshold: int = URL_FOLD_THRESHOLD) -> str:
    """Fold over-length URLs to 'https://host/...' to save token space."""
    def replacer(match: re.Match) -> str:
        url = match.group(0)
        if len(url) <= threshold:
            return url
        host_match = re.match(r"^(https?://[^/\s]+)", url)
        if host_match:
            return f"{host_match.group(1)}/..."
        return url

    return re.sub(r"https?://[^\s<>'\"]+", replacer, text)


class MessageParser:
    """Parses and normalizes incoming user messages and emails."""

    def parse(self, text: str, raw_auth: str | None = None) -> dict[str, Any]:
        """Parse raw user input into a standardized message structure."""
        text = (text or "").strip()

        # Check if the text is a raw RFC822 / MIME email
        if self._is_raw_email(text):
            return self._parse_email(text, raw_auth)

        # Normal text message (SMS / WhatsApp / Social / Chat)
        clean_body = text[:MAX_MESSAGE_LENGTH]
        urls = extract_urls(clean_body)
        auth_header = (raw_auth or "")[:MAX_AUTH_LENGTH].strip()

        return {
            "is_email": False,
            "subject": "",
            "from_sender": "",
            "body": clean_body,
            "folded_body": fold_long_urls(clean_body),
            "authentication_results": auth_header,
            "urls": urls,
        }

    def _is_raw_email(self, text: str) -> bool:
        """Heuristic check for RFC822 email headers at the top of input."""
        first_chunk = text[:1000]
        header_patterns = [
            r"(?m)^From:\s*.+",
            r"(?m)^Subject:\s*.+",
            r"(?m)^To:\s*.+",
            r"(?m)^Authentication-Results:\s*.+",
            r"(?m)^Received:\s*.+",
            r"(?m)^MIME-Version:\s*.+",
        ]
        matches = sum(1 for p in header_patterns if re.search(p, first_chunk))
        return matches >= 2

    def _parse_email(self, text: str, raw_auth: str | None = None) -> dict[str, Any]:
        """Extract clean body, headers, and authentication from RFC822 email."""
        try:
            msg = email.message_from_string(text)

            subject = decode_mime_header(msg.get("Subject", ""))
            from_sender = decode_mime_header(msg.get("From", ""))
            auth_results = msg.get("Authentication-Results", "") or (raw_auth or "")

            # Extract body (prefer text/plain, fallback to text/html stripped)
            body_parts: list[str] = []
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    if "attachment" in content_disposition:
                        continue
                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body_parts.append(payload.decode(charset, errors="replace"))
                            break
                if not body_parts:
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            payload = part.get_payload(decode=True)
                            if payload:
                                charset = part.get_content_charset() or "utf-8"
                                html_text = payload.decode(charset, errors="replace")
                                # Basic HTML tag stripping
                                clean = re.sub(r"<[^>]+>", " ", html_text)
                                clean = re.sub(r"\s+", " ", clean).strip()
                                body_parts.append(clean)
                                break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    raw_decoded = payload.decode(charset, errors="replace")
                    if msg.get_content_type() == "text/html":
                        raw_decoded = re.sub(r"<[^>]+>", " ", raw_decoded)
                        raw_decoded = re.sub(r"\s+", " ", raw_decoded).strip()
                    body_parts.append(raw_decoded)

            body = "\n\n".join(body_parts).strip()
            if not body:
                # If email parsing yielded empty body, fallback to raw text
                body = text

            clean_body = body[:MAX_MESSAGE_LENGTH]
            urls = extract_urls(clean_body)

            return {
                "is_email": True,
                "subject": subject,
                "from_sender": from_sender,
                "body": clean_body,
                "folded_body": fold_long_urls(clean_body),
                "authentication_results": auth_results[:MAX_AUTH_LENGTH].strip(),
                "urls": urls,
            }
        except Exception:
            clean_body = text[:MAX_MESSAGE_LENGTH]
            return {
                "is_email": False,
                "subject": "",
                "from_sender": "",
                "body": clean_body,
                "folded_body": fold_long_urls(clean_body),
                "authentication_results": (raw_auth or "")[:MAX_AUTH_LENGTH].strip(),
                "urls": extract_urls(clean_body),
            }
