"""Deterministic, band-aware fraud explanation and safety recommendation generator.

Adapted from KangaL's fallbackReason engine:
- Never references inactive levers (zero hallucination).
- Calibrates tone according to the deterministic risk band (CRITICAL/HIGH vs CAUTION vs LOW).
- Accurately integrates concrete investigation findings (domain age in days, auth failure).
- Delivers calm, actionable advice without fear-mongering.
"""
from __future__ import annotations

from typing import Any

from detector.fraud_weights import (
    BONUS_DOMAIN_AGE_DAYS_THRESHOLD,
    DANGER_SCORE_THRESHOLD,
    LEVER_WEIGHTS,
    SUSPICIOUS_SCORE_THRESHOLD,
    strength_of,
)

CTA_ACTION_PHRASES = {
    "transfer_money": "requests an immediate money transfer or fee payment",
    "input_credentials": "asks you to enter confidential passwords, PINs, or OTPs",
    "install_app": "directs you to install an application or remote-access tool",
    "scan_qr": "instructs you to scan an external QR code",
    "click_link": "pressures you to click an unverified external link",
    "call_number": "asks you to call an unofficial telephone number",
}

IMPERSONATES_PHRASES = {
    "financial": "claims to represent a bank, payment provider, or credit agency",
    "government": "claims to represent a government department, court, or police",
    "business_partner": "claims to be a trusted corporate partner or vendor",
    "executive": "claims to be a CEO, director, or workplace manager",
    "delivery": "claims to be a postal courier or customs delivery service",
    "platform": "claims to represent an online platform or telecom operator",
}

URGENCY_TACTIC_PHRASES = {
    "deadline": "creates intense time pressure with a strict deadline",
    "account_freeze": "threatens immediate account suspension or service disconnection",
    "limited_offer": "uses artificial urgency with a limited-time reward hook",
}

INCENTIVE_HOOK_PHRASES = {
    "prize": "lures you with an unearned prize, cashback, or lottery reward",
    "refund": "promises an unexpected refund or rebate",
    "penalty": "intimidates you with fines, disconnection, or legal penalties",
    "account_loss": "alarms you with imminent account or data loss",
    "legal_threat": "threatens arrest, police complaint, or legal action",
}

PERSONALIZATION_PHRASES = {
    "segmented": "tailors wording to mimic legitimate transactional context",
    "targeted": "references personal identifying details or references",
}

ISOLATION_TACTIC_PHRASES = {
    "secrecy": "urges you to keep this matter confidential from colleagues or family",
    "bypass_approval": "pressures you to skip regular approval or verification channels",
    "direct_channel": "demands continuing the conversation over a private off-platform channel",
}


def build_fraud_explanation(
    levers: dict[str, Any],
    risk_score: int,
    investigation: dict[str, Any] | None = None,
) -> tuple[str, list[str], str]:
    """Build a deterministic explanation, signal list, and recommendation.

    Returns:
        tuple: (summary_why, signals_list, recommendation)
    """
    strengths = strength_of(levers)
    is_danger = risk_score >= DANGER_SCORE_THRESHOLD
    is_suspicious = risk_score >= SUSPICIOUS_SCORE_THRESHOLD and not is_danger

    # 1. Build list of active signals and rank them
    active_signals: list[dict[str, Any]] = []

    urg = levers.get("urgency", {})
    if urg.get("tactic") != "none" and strengths["urgency"] > 0:
        phrase = URGENCY_TACTIC_PHRASES.get(urg.get("tactic"), "creates artificial urgency")
        active_signals.append({
            "key": "urgency",
            "label": "Urgency Pressure",
            "phrase": phrase,
            "rank": strengths["urgency"] * LEVER_WEIGHTS["urgency"],
        })

    auth = levers.get("authority", {})
    if auth.get("impersonates") != "none" and strengths["authority"] > 0:
        phrase = IMPERSONATES_PHRASES.get(auth.get("impersonates"), "claims authoritative status")
        active_signals.append({
            "key": "authority",
            "label": "Authority / Impersonation",
            "phrase": phrase,
            "rank": strengths["authority"] * LEVER_WEIGHTS["authority"],
        })

    inc = levers.get("incentive", {})
    if strengths["incentive"] > 0:
        phrase = INCENTIVE_HOOK_PHRASES.get(inc.get("hook"), "uses emotional leverage")
        active_signals.append({
            "key": "incentive",
            "label": "Incentive / Fear Hook",
            "phrase": phrase,
            "rank": strengths["incentive"] * LEVER_WEIGHTS["incentive"],
        })

    cta = levers.get("callToAction", {})
    if strengths["callToAction"] > 0:
        phrase = CTA_ACTION_PHRASES.get(cta.get("action"), "prompts immediate user action")
        active_signals.append({
            "key": "cta",
            "label": "Call To Action",
            "phrase": phrase,
            "rank": strengths["callToAction"] * LEVER_WEIGHTS["callToAction"],
        })

    pers = levers.get("personalization", {})
    if pers.get("level") != "broadcast" and strengths["personalization"] > 0:
        phrase = PERSONALIZATION_PHRASES.get(pers.get("level"), "uses personalized context")
        active_signals.append({
            "key": "personalization",
            "label": "Personalization Cue",
            "phrase": phrase,
            "rank": strengths["personalization"] * LEVER_WEIGHTS["personalization"],
        })

    iso = levers.get("isolation", {})
    if iso.get("tactic") != "none" and strengths["isolation"] > 0:
        phrase = ISOLATION_TACTIC_PHRASES.get(iso.get("tactic"), "urges secrecy")
        active_signals.append({
            "key": "isolation",
            "label": "Isolation Pressure",
            "phrase": phrase,
            "rank": strengths["isolation"] * LEVER_WEIGHTS["isolation"],
        })

    # Sort signals by importance
    active_signals.sort(key=lambda s: s["rank"], reverse=True)

    # 2. Build external investigation observation
    inv_clauses: list[str] = []
    if investigation:
        url_rep = investigation.get("url_reputation", {})
        if url_rep.get("status") == "ok" and url_rep.get("threats"):
            inv_clauses.append("the destination link has been flagged as high-risk or malicious")

        dom_age = investigation.get("domain_age", {})
        if dom_age.get("status") == "ok":
            age = dom_age.get("age_days")
            if isinstance(age, (int, float)) and age < BONUS_DOMAIN_AGE_DAYS_THRESHOLD:
                inv_clauses.append(f"the destination website was registered only {age} day{'s' if age != 1 else ''} ago")

        sender_auth = investigation.get("sender_auth", {})
        if sender_auth.get("status") == "ok" and sender_auth.get("is_spoofed"):
            inv_clauses.append("sender verification checks (SPF/DKIM/DMARC) failed, suggesting sender address spoofing")

        scams = investigation.get("known_scams", {})
        if scams.get("status") == "ok" and scams.get("matches"):
            inv_clauses.append(f"the structure matches {len(scams['matches'])} known fraudulent scam patterns")

    # 3. Assemble WHY summary
    top_phrases = [s["phrase"] for s in active_signals[:3]]
    signals_display = [f"{s['label']}: {s['phrase'].capitalize()}." for s in active_signals]
    for clause in inv_clauses:
        signals_display.append(f"External Finding: {clause.capitalize()}.")

    if is_danger:
        if top_phrases:
            why = f"This message shows clear markers of a social engineering attack: it {', '.join(top_phrases)}."
        else:
            why = "This communication contains critical security warning indicators."
        if inv_clauses:
            why += f" In addition, {'; '.join(inv_clauses)}."
        recommendation = (
            "Do NOT click any link, do NOT provide any password, PIN, or OTP, and do NOT send money. "
            "Verify this request independently through the official institution's verified app or helpline."
        )
    elif is_suspicious:
        if top_phrases:
            why = f"This communication contains questionable indicators: it {', '.join(top_phrases)}."
        else:
            why = "Some aspects of this message warrant scrutiny before responding."
        if inv_clauses:
            why += f" Furthermore, {'; '.join(inv_clauses)}."
        recommendation = (
            "Proceed with caution. Do not share confidential information or approve payments without "
            "confirming through an established, independent contact method."
        )
    else:  # LOW_RISK
        if top_phrases:
            why = f"While the message mentions {', '.join(top_phrases)}, it lacks strong fraudulent pressure or malicious threat cues."
        else:
            why = "This message does not exhibit common social engineering pressures, credential harvesting, or known scam vectors."
        recommendation = (
            "No high-risk fraud patterns detected. However, if this message refers to a private financial "
            "transaction, verify directly through your official banking portal before trusting it."
        )

    return why, signals_display, recommendation
