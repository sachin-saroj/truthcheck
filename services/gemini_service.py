"""Google Gemini AI service for TruthCheck fact verification.

Provides free, high-limit AI verification (1,500 requests/day free tier)
via direct Google Gemini 1.5/2.0 Flash REST endpoint.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv
import requests

logger = logging.getLogger(__name__)

GEMINI_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3-flash-preview",
]


class GeminiService:
    def __init__(self, api_key: str | None = None):
        load_dotenv()
        if api_key is None:
            self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        else:
            self.api_key = api_key.strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _extract_json(self, content: str) -> dict[str, Any] | None:
        """Parse JSON robustly even if wrapped in think tags or markdown fences."""
        content = content.strip()
        content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, flags=re.IGNORECASE)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except Exception:
                pass
        try:
            return json.loads(content)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
        return None

    def verify_claim(
        self,
        claim: str,
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Verify claim using Google Gemini."""
        if not self.is_configured:
            return None

        evidence_text = ""
        for i, ev in enumerate(evidence, 1):
            title = ev.get("title", "")
            source = ev.get("source", "")
            snippet = ev.get("snippet", "")
            evidence_text += f"[{i}] {source}: {title} — {snippet}\n"

        if not evidence_text.strip():
            evidence_text = "No direct news sources found on this exact claim."

        prompt = (
            "You are an impartial, highly rigorous fact-checking intelligence analyst.\n"
            "Compare the user's claim against the real-world web evidence and determine its factual truth.\n\n"
            f"User Claim: \"{claim}\"\n\n"
            f"Live Search Evidence:\n{evidence_text}\n\n"
            "Classification Rules:\n"
            "1. 'likely_true': SUPPORTED — substantiated by credible reporting.\n"
            "2. 'likely_fake': FALSE — contradicted by facts, debunked, or fabricated.\n"
            "3. 'needs_verification': INSUFFICIENT EVIDENCE — not enough evidence to confirm or contradict.\n\n"
            "Return STRICT JSON ONLY:\n"
            "{\n"
            '  "verdict_id": "likely_true" | "likely_fake" | "needs_verification",\n'
            '  "confidence": <integer from 70 to 99>,\n'
            '  "summary": "<2-3 short sentences explaining why the claim is supported or false>",\n'
            '  "key_points": [\n'
            '    "Source 1 — detail",\n'
            '    "Source 2 — detail"\n'
            '  ]\n'
            "}"
        )

        for model_name in GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 2048,
                    "responseMimeType": "application/json",
                }
            }

            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    parsed = self._extract_json(raw_text)
                    if not parsed:
                        logger.warning("Could not parse JSON from Gemini model %s: %s", model_name, raw_text[:120])
                        continue

                    raw_verdict = str(parsed.get("verdict_id") or parsed.get("verdict") or "").strip().lower()
                    if any(k in raw_verdict for k in ("true", "support", "likely_true", "verified", "correct")):
                        verdict_id = "likely_true"
                    elif any(k in raw_verdict for k in ("fake", "false", "contradict", "debunk", "misleading", "scam")):
                        verdict_id = "likely_fake"
                    else:
                        verdict_id = "needs_verification"

                    raw_conf = parsed.get("confidence", 85)
                    if isinstance(raw_conf, str):
                        conf = 92 if "high" in raw_conf.lower() else (45 if "low" in raw_conf.lower() else 75)
                    else:
                        try:
                            conf = int(raw_conf)
                        except Exception:
                            conf = 85
                    conf = max(40, min(99, conf))

                    key_points = parsed.get("key_points", [])
                    if not isinstance(key_points, list):
                        key_points = []

                    return {
                        "verdict_id": verdict_id,
                        "confidence": conf,
                        "credibility_score": conf,
                        "summary": parsed.get("summary", ""),
                        "key_points": key_points,
                        "model": f"Google Gemini ({model_name})",
                        "ai_verified": True,
                    }
                else:
                    logger.warning("Gemini model %s returned status %s: %s", model_name, resp.status_code, resp.text[:100])
                    continue
            except Exception as exc:
                logger.warning("Gemini request exception for %s: %s", model_name, exc)
                continue

        return None
