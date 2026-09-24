"""TruthCheck Fact Checker Orchestrator.

Combines real-time internet search with Qwen 3.8 27B AI model to deliver
verifiable, source-backed truth assessments and 2-3 line explanations.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from services.gemini_service import GeminiService
from services.openrouter_service import OpenRouterService
from services.search_service import SearchService

logger = logging.getLogger(__name__)

VERDICTS = {
    "likely_true": {
        "id": "likely_true",
        "label": "SUPPORTED",
        "emoji": "🟢",
        "tone": "ok",
    },
    "needs_verification": {
        "id": "needs_verification",
        "label": "INSUFFICIENT EVIDENCE",
        "emoji": "🟡",
        "tone": "warn",
    },
    "likely_fake": {
        "id": "likely_fake",
        "label": "FALSE",
        "emoji": "🔴",
        "tone": "bad",
    },
}


DEFAULT_TIPS = {
    "likely_true": [
        "Still check the publication date to ensure the context is recent.",
        "Skim at least one linked source below to read full details.",
        "For major official claims, prefer primary government or scientific bulletins.",
    ],
    "needs_verification": [
        "Find the original named source before sharing with others.",
        "Compare at least two independent reputable news outlets.",
        "Check whether headlines overstate what has actually been confirmed.",
    ],
    "likely_fake": [
        "Do not share or forward — evidence indicates this is misleading or false.",
        "Look for verified official statements or reputable fact-checkers.",
        "Notice if high-emotion words were used to bypass critical thinking.",
    ],
}


class FactChecker:
    """Master service combining live search and deep AI reasoning."""

    def __init__(
        self,
        search_service: SearchService | None = None,
        ai_service: OpenRouterService | None = None,
        gemini_service: GeminiService | None = None,
    ):
        self.search = search_service or SearchService()
        self.ai = ai_service or OpenRouterService()
        self.gemini = gemini_service or GeminiService()

    def analyze(self, text: str) -> dict[str, Any]:
        """Perform end-to-end real-world fact checking on user text."""
        start_time = time.time()
        text = text.strip()

        # 1. Search live web and news for corroboration/debunking
        sources = self.search.search_evidence(text, max_results=6)

        # 2. Feed claim and live evidence to AI reasoning engine
        ai_result = None
        if self.gemini.is_configured:
            ai_result = self.gemini.verify_claim(text, sources)

        if not ai_result:
            ai_result = self.ai.verify_claim(text, sources)

        verdict_id = ai_result.get("verdict_id", "needs_verification")
        if verdict_id not in VERDICTS:
            verdict_id = "needs_verification"

        verdict_meta = VERDICTS[verdict_id]
        raw_score = ai_result.get("confidence") or ai_result.get("credibility_score") or 50

        # Calibrate confidence according to verdict contract
        if verdict_id == "likely_true":
            confidence = max(70, min(99, int(raw_score)))
            credibility_score = confidence
        elif verdict_id == "likely_fake":
            confidence = max(70, min(99, int(raw_score)))
            credibility_score = max(5, 100 - confidence)
        else:  # needs_verification
            confidence = min(58, max(42, int(raw_score))) if raw_score > 60 else max(35, min(58, int(raw_score)))
            credibility_score = 50

        summary = ai_result.get("summary", "")
        key_points = ai_result.get("key_points", [])

        elapsed_ms = int((time.time() - start_time) * 1000)

        return {
            "verdict": verdict_meta,
            "credibility_score": credibility_score,
            "confidence": confidence,
            "summary": summary,
            "key_points": key_points,

            "sources": sources,
            "has_sources": len(sources) > 0,
            "ai_info": {
                "model": ai_result.get("model", "TruthCheck AI"),
                "is_ai_verified": ai_result.get("ai_verified", False),
                "is_configured": self.gemini.is_configured or self.ai.is_configured,
            },
            "tips": DEFAULT_TIPS[verdict_id],
            "elapsed_ms": elapsed_ms,
        }
