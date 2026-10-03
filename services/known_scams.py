"""Known scam pattern matching engine.

Computes weighted cosine similarity between extracted message social engineering
levers and curated known scam patterns from data/known_scams.json.
Zero external database required — runs fully deterministic and in-process.
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from detector.fraud_weights import LEVER_WEIGHTS, strength_of

logger = logging.getLogger(__name__)

SCAM_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "known_scams.json"
KNOWN_SCAM_HIT_THRESHOLD = 0.50
MAX_MATCHES = 3

_cached_patterns: list[dict[str, Any]] | None = None


def load_scam_patterns() -> list[dict[str, Any]]:
    """Load known scam patterns from JSON database."""
    global _cached_patterns
    if _cached_patterns is not None:
        return _cached_patterns

    try:
        if SCAM_DB_PATH.exists():
            with open(SCAM_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                _cached_patterns = data.get("patterns", [])
                return _cached_patterns
    except Exception as e:
        logger.error("Failed to load known scams database: %s", e)

    return []


def lever_cosine_similarity(v1: dict[str, int], v2: dict[str, int]) -> float:
    """Compute weighted cosine similarity between two lever strength vectors."""
    dot_product = 0.0
    norm1_sq = 0.0
    norm2_sq = 0.0

    for key, weight in LEVER_WEIGHTS.items():
        val1 = v1.get(key, 0)
        val2 = v2.get(key, 0)
        w = float(weight)

        dot_product += w * val1 * val2
        norm1_sq += w * (val1 ** 2)
        norm2_sq += w * (val2 ** 2)

    if norm1_sq <= 0 or norm2_sq <= 0:
        return 0.0

    return dot_product / (math.sqrt(norm1_sq) * math.sqrt(norm2_sq))


class KnownScamMatcher:
    """Matches messages against known attack patterns."""

    def __init__(self, patterns: list[dict[str, Any]] | None = None):
        self.patterns = patterns if patterns is not None else load_scam_patterns()

    def match(self, levers: dict[str, Any], text: str = "") -> dict[str, Any]:
        """Find matching known scam templates for the given message levers and text."""
        msg_strengths = strength_of(levers)
        raw_text = (text or "").lower()

        matches = []
        for pattern in self.patterns:
            pat_levers = pattern.get("levers", {})
            pat_strengths = strength_of(pat_levers)

            vec_sim = lever_cosine_similarity(msg_strengths, pat_strengths)

            # Keyword matching bonus
            keywords = pattern.get("keywords", [])
            kw_hits = sum(1 for kw in keywords if kw in raw_text)
            if keywords and kw_hits == 0:
                vec_sim *= 0.70
            kw_boost = min(0.35, kw_hits * 0.09)

            total_sim = min(1.0, vec_sim + kw_boost)

            if total_sim >= KNOWN_SCAM_HIT_THRESHOLD:
                matches.append({
                    "id": pattern.get("id"),
                    "title": pattern.get("title"),
                    "category": pattern.get("category"),
                    "similarity": round(total_sim, 2),
                    "advisory": pattern.get("advisory", ""),
                })

        matches.sort(key=lambda m: m["similarity"], reverse=True)
        top_matches = matches[:MAX_MATCHES]

        return {
            "status": "ok" if top_matches else "no_match",
            "matches": top_matches,
            "has_match": len(top_matches) > 0,
        }
