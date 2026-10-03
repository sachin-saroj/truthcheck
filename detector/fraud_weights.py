"""Deterministic risk scoring, isolation floors, and investigation bonus math.

Adapted from KangaL's weights engine:
- Linear weighted combination across 6 social engineering levers
- Hard isolation floor ensuring strong isolation pushes into warning/danger
- Additive investigation bonuses (capped at +25) for confirmed domain/URL/auth threats
"""
from __future__ import annotations

from typing import Any

LEVER_WEIGHTS = {
    "urgency": 2,
    "authority": 2,
    "incentive": 2,
    "callToAction": 3,
    "personalization": 3,
    "isolation": 5,
}

CTA_DANGER = {
    "transfer_money": 3,
    "input_credentials": 3,
    "install_app": 2,
    "scan_qr": 2,
    "click_link": 2,
    "call_number": 1,
}

FRICTION_ADJ = {
    "low": 0,
    "mid": -1,
    "high": -2,
}

PERSONALIZATION_LEVEL_RANK = {
    "broadcast": 0,
    "segmented": 1,
    "targeted": 2,
}

# When isolation is moderate or strong, enforce an absolute risk floor
ISOLATION_FLOORS = {
    0: 0,
    1: 0,
    2: 55,
    3: 75,
}

BONUS_WEB_RISK_THREAT = 15
BONUS_DOMAIN_YOUNG = 10
BONUS_DOMAIN_AGE_DAYS_THRESHOLD = 30
BONUS_SENDER_AUTH_FAIL = 8
BONUS_KNOWN_SCAM_PER_MATCH = 5
BONUS_KNOWN_SCAM_CAP = 15
BONUS_OFFICIAL_ALERT = 8
INVESTIGATION_BONUS_CAP = 25

DANGER_SCORE_THRESHOLD = 65
SUSPICIOUS_SCORE_THRESHOLD = 45


def max_raw_score() -> int:
    """Maximum possible raw weighted score before 0-100 normalization (51)."""
    return 3 * sum(LEVER_WEIGHTS.values())


def strength_of(levers: dict[str, Any]) -> dict[str, int]:
    """Calculate the normalized 0-3 strength score for each of the 6 levers."""
    urgency = levers.get("urgency", {})
    authority = levers.get("authority", {})
    incentive = levers.get("incentive", {})
    cta = levers.get("callToAction", {})
    pers = levers.get("personalization", {})
    iso = levers.get("isolation", {})

    # Urgency: directly uses intensity
    urg_intensity = max(0, min(3, int(urgency.get("intensity", 0))))

    # Authority: 0 if 'none', else 1 + number of credibility tricks
    impersonates = str(authority.get("impersonates", "none")).lower()
    if impersonates == "none":
        auth_strength = 0
    else:
        tricks = authority.get("credibilityTricks", [])
        auth_strength = min(3, 1 + len(tricks))

    # Incentive: directly uses intensity
    inc_intensity = max(0, min(3, int(incentive.get("intensity", 0))))

    # CTA: danger rating adjusted by execution friction
    action = str(cta.get("action", "click_link")).lower()
    friction = str(cta.get("friction", "mid")).lower()
    raw_cta = CTA_DANGER.get(action, 2) + FRICTION_ADJ.get(friction, -1)
    cta_strength = max(0, min(3, raw_cta))

    # Personalization: rank by broadcast/segmented/targeted + bonus for signals
    level = str(pers.get("level", "broadcast")).lower()
    signals = pers.get("signals", [])
    raw_pers = PERSONALIZATION_LEVEL_RANK.get(level, 0) + (1 if signals else 0)
    pers_strength = min(3, raw_pers)

    # Isolation: directly uses intensity
    iso_intensity = max(0, min(3, int(iso.get("intensity", 0))))

    return {
        "urgency": urg_intensity,
        "authority": auth_strength,
        "incentive": inc_intensity,
        "callToAction": cta_strength,
        "personalization": pers_strength,
        "isolation": iso_intensity,
    }


def compute_base_score(levers: dict[str, Any]) -> int:
    """Calculate linear weighted sum normalized to 0-100 and lifted by isolation floor."""
    strengths = strength_of(levers)
    raw = sum(strengths[k] * LEVER_WEIGHTS[k] for k in LEVER_WEIGHTS)
    linear = round((raw / max_raw_score()) * 100)

    iso_intensity = max(0, min(3, int(levers.get("isolation", {}).get("intensity", 0))))
    floor = ISOLATION_FLOORS.get(iso_intensity, 0)
    return max(linear, floor)


def compute_investigation_bonus(investigation: dict[str, Any] | None) -> dict[str, Any]:
    """Calculate additive bonus points from external checks, capped at 25 points."""
    if not investigation:
        return {"items": [], "total": 0, "capped": False}

    items: list[dict[str, Any]] = []

    # 1. URL Reputation threat
    url_rep = investigation.get("url_reputation", {})
    if url_rep.get("status") == "ok" and url_rep.get("threats"):
        items.append({"source": "web_risk", "points": BONUS_WEB_RISK_THREAT})

    # 2. Young domain (< 7 days)
    domain_age = investigation.get("domain_age", {})
    if domain_age.get("status") == "ok":
        age_days = domain_age.get("age_days")
        if isinstance(age_days, (int, float)) and age_days < BONUS_DOMAIN_AGE_DAYS_THRESHOLD:
            items.append({"source": "domain_age", "points": BONUS_DOMAIN_YOUNG})

    # 3. Sender authentication failure
    sender_auth = investigation.get("sender_auth", {})
    if sender_auth.get("status") == "ok":
        spf = sender_auth.get("spf")
        dkim = sender_auth.get("dkim")
        dmarc = sender_auth.get("dmarc")
        if any(v == "fail" for v in (spf, dkim, dmarc)):
            items.append({"source": "sender_auth", "points": BONUS_SENDER_AUTH_FAIL})

    # 4. Matched known scams
    known_scams = investigation.get("known_scams", {})
    if known_scams.get("status") == "ok":
        matches = known_scams.get("matches", [])
        if matches:
            points = min(BONUS_KNOWN_SCAM_CAP, len(matches) * BONUS_KNOWN_SCAM_PER_MATCH)
            items.append({"source": "known_scams", "points": points})

    # 5. Official advisory alert match
    official_alerts = investigation.get("official_alerts", {})
    if official_alerts.get("status") == "ok" and official_alerts.get("matches"):
        items.append({"source": "official_alerts", "points": BONUS_OFFICIAL_ALERT})

    raw_total = sum(item["points"] for item in items)
    total = min(INVESTIGATION_BONUS_CAP, raw_total)
    return {
        "items": items,
        "total": total,
        "raw_total": raw_total,
        "capped": raw_total > INVESTIGATION_BONUS_CAP,
    }


def compute_fraud_score(
    levers: dict[str, Any],
    investigation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate overall risk score, risk level, and verification status."""
    base_score = compute_base_score(levers)
    bonus_data = compute_investigation_bonus(investigation)
    risk_score = min(100, base_score + bonus_data["total"])

    # Determine Risk Level
    if risk_score >= 85:
        risk_level = "CRITICAL"
    elif risk_score >= DANGER_SCORE_THRESHOLD:
        risk_level = "HIGH_RISK"
    elif risk_score >= SUSPICIOUS_SCORE_THRESHOLD:
        risk_level = "SUSPICIOUS"
    else:
        risk_level = "LOW_RISK"

    # Determine Verification Status
    # Principle: LOW RISK != GUARANTEED SAFE; UNVERIFIED != FRAUD
    # Do NOT call something VERIFIED_FRAUD merely because it looks suspicious.
    # VERIFIED_FRAUD requires confirmed external threat intelligence (e.g. Google Web Risk API).
    has_threat_intel = False
    if investigation:
        url_rep = investigation.get("url_reputation", {})
        url_threats = url_rep.get("threats", [])
        if url_threats and url_rep.get("source") == "Google Web Risk":
            has_threat_intel = True

    if has_threat_intel:
        verification_status = "VERIFIED_FRAUD"
        # If external threat intelligence verified active malware/phishing, risk must be at least HIGH_RISK
        risk_score = max(risk_score, DANGER_SCORE_THRESHOLD)
        risk_level = "CRITICAL" if risk_score >= 85 else "HIGH_RISK"
    elif risk_level in ("HIGH_RISK", "CRITICAL") and bonus_data.get("items"):
        # Multiple confirming suspicious indicators without external registry verification
        verification_status = "UNVERIFIED"
    elif risk_level == "LOW_RISK":
        sender_auth = (investigation or {}).get("sender_auth", {})
        if sender_auth.get("status") == "ok" and sender_auth.get("spf") == "pass" and sender_auth.get("dmarc") == "pass":
            verification_status = "VERIFIED_LEGITIMATE"
        else:
            verification_status = "UNVERIFIED"
    else:
        verification_status = "UNVERIFIED"

    return {
        "risk_score": risk_score,
        "base_score": base_score,
        "bonus": bonus_data,
        "risk_level": risk_level,
        "verification_status": verification_status,
    }
