"""Text cleaning utilities for the TruthCheck detector."""
from __future__ import annotations

import re
import string

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_TABLE = str.maketrans({c: " " for c in string.punctuation})


def clean_text(text: str | None) -> str:
    """Normalise raw news text before feature extraction."""
    if not text:
        return ""
    text = str(text)
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = URL_RE.sub(" url ", text)
    text = EMAIL_RE.sub(" email ", text)
    text = text.translate(_PUNCT_TABLE)
    text = WHITESPACE_RE.sub(" ", text).strip().lower()
    return text


def first_line(text: str | None, max_len: int = 100) -> str:
    """Return a short query-friendly snippet (usually the headline)."""
    if not text:
        return ""
    line = str(text).strip().splitlines()[0].strip()
    line = URL_RE.sub("", line)
    if len(line) > max_len:
        line = line[:max_len].rsplit(" ", 1)[0]
    return line
