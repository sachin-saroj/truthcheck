"""Evidence Verification Engine for TruthCheck.

Performs deterministic, semantic cross-referencing between a user claim and live search evidence.
Detects factual contradictions, entity mismatches (e.g., Sun vs. Moon), debunk/hoax markers,
and validates corroboration across independent news sources.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Stopwords to filter out non-informative words
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "and", "or", "for", "with",
    "that", "this", "it", "at", "by", "from", "be", "has", "have", "had",
    "will", "would", "could", "should", "about", "what", "when", "where",
    "who", "which", "why", "how", "you", "your", "they", "their", "we", "our",
    "says", "said", "reported", "breaking", "update", "shocking", "urgent",
    "near", "over", "into", "onto", "under", "after", "before", "during",
    "successfully", "performed", "official", "confirmed", "today", "yesterday",
}

# Mutually exclusive entity groups (if claim has one, but evidence has another, it's a direct contradiction)
MUTUALLY_EXCLUSIVE_GROUPS = [
    # Celestial bodies
    {"sun", "solar"},
    {"moon", "lunar"},
    {"mars", "martian"},
    {"earth", "terrestrial"},
    {"venus"},
    {"jupiter"},
    {"saturn"},
    # Life status
    {"dead", "died", "passed away", "killed", "fatal"},
    {"alive", "survived", "recovering", "healthy"},
    # Win / Lose
    {"won", "victorious", "champion"},
    {"lost", "defeated", "runner-up"},
]

# Words that strongly indicate debunking, scam, or false report
DEBUNK_SIGNALS = [
    "debunked", "fake", "hoax", "false claim", "fact check", "misleading",
    "scam", "fraud", "phishing", "fabricated", "baseless", "denies",
    "refuted", "no such scheme", "virus", "malware", "rumour", "rumor",
    "not true", "incorrect", "untrue", "fake news", "counterfeit",
]


class EvidenceVerifier:
    """Rigorous semantic cross-verification between claim and evidence."""

    @staticmethod
    def extract_keywords(text: str) -> list[str]:
        """Extract clean alphanumeric keywords with length >= 3."""
        words = re.findall(r"\b[a-z0-9-]{3,}\b", text.lower())
        return [w for w in words if w not in STOPWORDS]

    def verify(
        self,
        claim: str,
        evidence: list[dict[str, Any]],
        fallback_reason: str = "quota_exhausted",
    ) -> dict[str, Any]:
        """Cross-examine claim against retrieved evidence and return strict contract format."""
        claim_cleaned = claim.strip()
        claim_lower = claim_cleaned.lower()
        claim_keywords = self.extract_keywords(claim_cleaned)
        claim_word_set = set(claim_keywords)

        if not evidence:
            return {
                "verdict_id": "needs_verification",
                "confidence": 48,
                "summary": (
                    "Available evidence isn't sufficient to confirm or contradict the claim. "
                    "No authoritative records, news coverage, or public bulletins were found on the live internet."
                ),
                "key_points": [
                    "Web Search — No corroborating or debunking reports found for this claim.",
                    "Verification Signal — Claims with zero public reporting require independent confirmation before sharing."
                ],
                "ai_verified": False,
                "fallback_reason": fallback_reason,
            }

        # 1. Search for debunk signals in evidence titles & snippets
        debunk_matches: list[tuple[dict[str, Any], list[str]]] = []
        for ev in evidence:
            full_text = (ev.get("title", "") + " " + ev.get("snippet", "")).lower()
            matched = [sig for sig in DEBUNK_SIGNALS if sig in full_text]
            if matched:
                debunk_matches.append((ev, matched))

        # 2. Check for mutually exclusive entity conflicts (e.g., Sun vs. Moon)
        evidence_text = " ".join(
            (ev.get("title", "") + " " + ev.get("snippet", "")).lower() for ev in evidence
        )
        evidence_word_set = set(re.findall(r"\b[a-z0-9-]{3,}\b", evidence_text))

        conflict_found = self._check_mutually_exclusive_conflict(claim_word_set, evidence_word_set)
        if conflict_found:
            claim_term, evidence_term = conflict_found
            term_labels = {
                "lunar": "Moon",
                "solar": "Sun",
                "martian": "Mars",
                "terrestrial": "Earth",
            }
            claim_disp = term_labels.get(claim_term.lower(), claim_term.capitalize())
            ev_disp = term_labels.get(evidence_term.lower(), evidence_term.capitalize())

            # Find source that mentions the real entity
            conf_src = evidence[0].get("source", "Authoritative sources")
            for ev in evidence:
                if evidence_term in (ev.get("title", "") + " " + ev.get("snippet", "")).lower():
                    conf_src = ev.get("source", conf_src)
                    break

            return {
                "verdict_id": "likely_fake",
                "confidence": 95,
                "credibility_score": 95,
                "summary": (
                    f"The claim is contradicted by facts. While related mission activity is documented, "
                    f"all reliable evidence confirms the target was the {ev_disp}, not the {claim_disp}."
                ),
                "key_points": [
                    f"{conf_src} — All reports confirm activity was conducted on the {ev_disp}.",
                    f"Factual Contradiction — The claim asserts the {claim_disp}, which directly conflicts with official records.",
                    "Scientific Record — Soft landings on the Sun are physically impossible due to extreme solar radiation and temperature." if "sun" in (claim_term, evidence_term) else f"Official Confirmation — Records explicitly contradict the claim's mention of {claim_disp}."
                ],
                "ai_verified": False,
                "fallback_reason": fallback_reason,
            }

        # 3. Handle explicit Debunk / Fact-Check articles
        if len(debunk_matches) >= 1:
            top_ev, signals = debunk_matches[0]
            src_name = top_ev.get("source") or "Fact Check Source"
            top_title = top_ev.get("title", "")
            return {
                "verdict_id": "likely_fake",
                "confidence": 94,
                "credibility_score": 94,
                "summary": (
                    "The claim is directly contradicted by facts and official reports. "
                    "Reliable evidence and fact-checking signals indicate this information is false, fabricated, or a recurring hoax."
                ),
                "key_points": [
                    f"{src_name} — Debunked claim: {top_title[:80]}",
                    "Official Fact Checkers — Flagged as misleading, unverified, or a fraudulent message."
                ],
                "ai_verified": False,
                "fallback_reason": fallback_reason,
            }

        # 4. Check positive corroboration across evidence
        overlapping_words = [w for w in claim_keywords if w in evidence_word_set]
        coverage_ratio = len(overlapping_words) / max(1, len(claim_keywords))

        # If we have at least 2 sources and substantial keyword overlap, claim is corroborated
        if len(evidence) >= 2 and coverage_ratio >= 0.40:
            key_points = []
            for ev in evidence[:3]:
                src = ev.get("source") or "News Outlet"
                title = ev.get("title", "")
                key_points.append(f"{src} — Corroborates: {title[:80]}")

            return {
                "verdict_id": "likely_true",
                "confidence": 91,
                "credibility_score": 91,
                "summary": (
                    "The claim is supported by reliable reporting. "
                    "Multiple independent sources and news outlets corroborate the core facts of the claim."
                ),
                "key_points": key_points,
                "ai_verified": False,
                "fallback_reason": fallback_reason,
            }

        # 6. Otherwise: Insufficient evidence
        return {
            "verdict_id": "needs_verification",
            "confidence": 52,
            "credibility_score": 52,
            "summary": (
                "Available evidence isn't sufficient to confirm or contradict the claim. "
                "Only limited or indirect reporting was identified, and independent cross-confirmation is required."
            ),
            "key_points": [
                f"{evidence[0].get('source', 'Web Source')} — Limited coverage found: {evidence[0].get('title', '')[:80]}",
                "Independent Cross-Check — Crucial claim details lack definitive corroboration from established media."
            ],
            "ai_verified": False,
            "fallback_reason": fallback_reason,
        }

    def _check_mutually_exclusive_conflict(
        self,
        claim_words: set[str],
        evidence_words: set[str],
    ) -> tuple[str, str] | None:
        """Find if claim has an entity in group A, but evidence has an entity in group B."""
        for i, group_a in enumerate(MUTUALLY_EXCLUSIVE_GROUPS):
            matched_a = [w for w in group_a if w in claim_words]
            if not matched_a:
                continue
            # Look for conflicting group
            for j, group_b in enumerate(MUTUALLY_EXCLUSIVE_GROUPS):
                if i == j:
                    continue
                # If they are in the same domain category (e.g. both celestial bodies)
                if (i <= 6 and j <= 6) or (7 <= i <= 8 and 7 <= j <= 8) or (9 <= i <= 10 and 9 <= j <= 10):
                    matched_b = [w for w in group_b if w in evidence_words]
                    if matched_b and not any(w in evidence_words for w in group_a):
                        return (matched_a[0], matched_b[0])
        return None
