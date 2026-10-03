"""Untrusted input boundary protection.

Wraps externally-sourced text (user messages, emails, headers, scraped snippets)
in a per-request random UUID nonce tag. Defeats boundary-token injection attacks
where malicious payloads attempt to close XML/HTML style wrappers.
"""
from __future__ import annotations

import uuid


def wrap_untrusted(text: str) -> tuple[str, str]:
    """Wrap untrusted text in a unique nonce tag.

    Returns:
        tuple[str, str]: (wrapped_text, tag_name)
    """
    raw_text = str(text or "")
    for _ in range(5):
        tag = f"untrusted_input_{uuid.uuid4().hex}"
        if tag not in raw_text:
            return f"<{tag}>\n{raw_text}\n</{tag}>", tag

    raise RuntimeError("untrusted_input_nonce_collision")
