"""OpenRouter AI service for fact verification using Qwen 3.8 27B (free).

Analyzes news claims against real-world evidence retrieved from live search.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests

import time

from services.evidence_verifier import EvidenceVerifier

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemma-4-31b-it:free"
TIMEOUT_SECONDS = 9

# Class-level cooldown tracking for models that hit 429 or timeout
_model_cooldowns: dict[str, float] = {}
COOLDOWN_SECONDS = 180  # 3 minutes


class OpenRouterService:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        if api_key is None:
            self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        else:
            self.api_key = api_key.strip()

        if model is None:
            self.model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL).strip()
        else:
            self.model = model.strip()

        self.evidence_verifier = EvidenceVerifier()

        self.session = requests.Session()

    @property
    def is_configured(self) -> bool:
        """Check if OpenRouter API key is set."""
        return bool(self.api_key)

    def verify_claim(
        self,
        claim: str,
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Verify a claim against retrieved real-world evidence using fast AI."""
        if not self.is_configured:
            logger.info("OpenRouter API key not configured, using heuristic fallback.")
            return self._heuristic_fallback(claim, evidence, reason="missing_key")

        # Build prompt with evidence
        evidence_text = ""
        for i, ev in enumerate(evidence, 1):
            title = ev.get("title", "")
            source = ev.get("source", "")
            snippet = ev.get("snippet", "")
            evidence_text += f"[{i}] Source: {source} | Title: {title}\nSnippet: {snippet}\n\n"

        if not evidence_text.strip():
            evidence_text = "No clear outside sources found on this specific claim."

        system_prompt = (
            "You are an impartial, highly rigorous fact-checking journalist and intelligence analyst.\n"
            "Your mission: Compare the user's news claim against the provided live web search evidence and determine its factual truth.\n\n"
            "Classification Rules:\n"
            "1. 'likely_true': SUPPORTED — The claim is substantiated and confirmed by credible reporting or official sources.\n"
            "   * summary: 2–3 short sentences explaining what the evidence shows and why the claim is supported.\n"
            "2. 'likely_fake': FALSE — The claim is directly contradicted by facts, debunked by fact-checkers, or fabricated.\n"
            "   * summary: 2–3 short sentences explaining what the claim says, what reliable evidence shows, and why it is contradicted.\n"
            "3. 'needs_verification': INSUFFICIENT EVIDENCE — Available evidence is not sufficient to confirm or contradict the claim, or reports conflict.\n"
            "   * summary: 2–3 short sentences explaining why available evidence isn't sufficient to confirm or contradict the claim.\n\n"
            "Confidence Score Guidelines:\n"
            "- For SUPPORTED: 75–99% confidence\n"
            "- For FALSE: 75–99% confidence\n"
            "- For INSUFFICIENT EVIDENCE: 40–58% confidence (reflecting uncertainty)\n\n"
            "Evidence Points (key_points):\n"
            "Provide 2 to 4 concrete bullet points detailing the sources found, formatted like:\n"
            "  'Source Name — Description of finding/evidence'\n"
            "Example: 'ISRO Official Bulletin — Confirmed Vikram lander touched down on 23 August 2023.'\n\n"
            "Output Requirement (STRICT JSON ONLY):\n"
            "{\n"
            '  "verdict_id": "likely_true" | "likely_fake" | "needs_verification",\n'
            '  "confidence": <integer from 0 to 100>,\n'
            '  "summary": "<2-3 short sentences for WHY section>",\n'
            '  "key_points": [\n'
            '    "Source 1 — detail",\n'
            '    "Source 2 — detail"\n'
            '  ]\n'
            "}"
        )

        user_prompt = (
            f"User Claim to verify:\n\"{claim}\"\n\n"
            f"Real-World Search Evidence:\n{evidence_text}\n\n"
            "Analyze the claim against the evidence now and return the JSON object."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "TruthCheck Fact Checker",
        }

        # Order candidates: healthy models first, models on cooldown last
        candidate_models = [self.model]
        for fallback in (
            "google/gemma-4-31b-it:free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "google/gemma-4-26b-a4b-it:free",
            "nvidia/nemotron-3.5-lightning:free",
            "qwen/qwen3.8-27b:free",
            "nex-agi/nex-n2.5-mini:free",
            "openrouter/free",
        ):
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        now = time.time()
        healthy_models = [m for m in candidate_models if now - _model_cooldowns.get(m, 0) > COOLDOWN_SECONDS]
        cooldown_models = [m for m in candidate_models if m not in healthy_models]
        ordered_models = healthy_models + cooldown_models

        last_error = "unknown_error"

        for model_name in ordered_models:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 800,
            }

            try:
                resp = requests.post(
                    OPENROUTER_URL,
                    headers=headers,
                    json=payload,
                    timeout=TIMEOUT_SECONDS,
                )

                if resp.status_code == 200:
                    _model_cooldowns.pop(model_name, None)
                    data = resp.json()
                    message = data.get("choices", [{}])[0].get("message", {})
                    content = (message.get("content") or message.get("reasoning") or "").strip()
                    if not content:
                        logger.warning("Empty content from model %s", model_name)
                        _model_cooldowns[model_name] = time.time()
                        continue

                    parsed = self._extract_json(content)
                    if parsed:
                        raw_score = parsed.get("confidence") or parsed.get("credibility_score") or 50
                        try:
                            num = float(raw_score)
                            if 0.0 <= num <= 1.0:
                                score = int(round(num * 100))
                            else:
                                score = int(round(num))
                            score = max(0, min(100, score))
                        except Exception:
                            score = 50

                        raw_verdict = str(parsed.get("verdict_id") or parsed.get("verdict") or "").strip().lower()
                        if any(k in raw_verdict for k in ("true", "support", "likely_true", "verified", "correct")):
                            verdict_id = "likely_true"
                        elif any(k in raw_verdict for k in ("fake", "false", "contradict", "debunk", "misleading", "scam")):
                            verdict_id = "likely_fake"
                        elif any(k in raw_verdict for k in ("insufficient", "uncertain", "unverified", "needs_verification", "unknown")):
                            verdict_id = "needs_verification"
                        else:
                            if score >= 65:
                                verdict_id = "likely_true"
                            elif score <= 45:
                                verdict_id = "likely_fake"
                            else:
                                verdict_id = "needs_verification"

                        summary = parsed.get("summary", "").strip()
                        key_points = parsed.get("key_points", [])
                        if not isinstance(key_points, list):
                            key_points = []

                        return {
                            "verdict_id": verdict_id,
                            "credibility_score": score,
                            "summary": summary,
                            "key_points": key_points,
                            "model": model_name,
                            "ai_verified": True,
                        }
                    else:
                        logger.warning("Could not parse JSON from model %s: %s", model_name, content[:150])
                        _model_cooldowns[model_name] = time.time()
                        continue
                elif resp.status_code in (429, 500, 502, 503, 504):
                    err_msg = ""
                    try:
                        err_msg = resp.json().get("error", {}).get("message", "")
                    except Exception:
                        pass
                    if "free-models-per-day" in err_msg or "daily limit" in err_msg.lower():
                        logger.warning("OpenRouter free daily limit exceeded for this account. Delegating to EvidenceVerifier.")
                        return self._heuristic_fallback(claim, evidence, reason="api_error_429")

                    logger.warning("Model %s returned HTTP %s. Putting on cooldown and falling back.", model_name, resp.status_code)
                    _model_cooldowns[model_name] = time.time()
                    last_error = f"api_error_{resp.status_code}"
                    continue
                else:
                    logger.error("OpenRouter API error %s for model %s: %s", resp.status_code, model_name, resp.text[:200])
                    _model_cooldowns[model_name] = time.time()
                    last_error = f"api_error_{resp.status_code}"
                    continue

            except Exception as exc:
                logger.warning("OpenRouter request exception for %s: %s", model_name, exc)
                _model_cooldowns[model_name] = time.time()
                last_error = "connection_error"
                continue

        return self._heuristic_fallback(claim, evidence, reason=last_error)


    def _extract_json(self, content: str) -> dict[str, Any] | None:
        """Robustly parse JSON object even if enclosed in markdown code fences or think tags."""
        content = content.strip()
        # Remove <think>...</think> reasoning tags if present
        content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()
        # Extract from markdown code block if present
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, flags=re.IGNORECASE)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except Exception:
                pass
        try:
            return json.loads(content)
        except Exception:
            # Try finding the outermost { and }
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
        return None

    def _heuristic_fallback(
        self,
        claim: str,
        evidence: list[dict[str, Any]],
        reason: str = "missing_key",
    ) -> dict[str, Any]:
        """Delegate to EvidenceVerifier for factual cross-referencing when LLM is unavailable."""
        res = self.evidence_verifier.verify(claim, evidence, fallback_reason=reason)
        res["model"] = "TruthCheck Evidence Engine"
        if reason == "missing_key":
            res["key_points"].append("💡 Note: Add your free OPENROUTER_API_KEY in .env to enable deep LLM reasoning.")
        elif reason == "api_error_429":
            res["key_points"].append("⚡ Note: OpenRouter free tier daily limit reached (50/50). Claim verified using live web news evidence.")
        return res
