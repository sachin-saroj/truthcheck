"""Fraud detection psychological levers taxonomy and heuristic extraction.

Decomposes messages into 6 core social engineering dimensions:
1. Urgency (time pressure, account freeze threat)
2. Authority (financial, government, delivery, corporate impersonation)
3. Incentive (fear of loss or allure of unearned reward)
4. Call to Action (link click, credential harvesting, money transfer, APK install)
5. Personalization (broadcast spam vs targeted spear-phishing)
6. Isolation (forcing secrecy or bypassing usual verification channels)
"""
from __future__ import annotations

import re
from typing import Any

URGENCY_TACTICS = ["deadline", "account_freeze", "limited_offer", "none"]
IMPERSONATES = [
    "financial",
    "government",
    "business_partner",
    "executive",
    "delivery",
    "platform",
    "none",
]
CREDIBILITY_TRICKS = ["logo_mimicry", "formal_tone", "reference_number", "url_lookalike"]
INCENTIVE_TYPES = ["reward", "fear"]
INCENTIVE_HOOKS = ["prize", "refund", "penalty", "account_loss", "legal_threat"]
CTA_ACTIONS = [
    "click_link",
    "transfer_money",
    "input_credentials",
    "call_number",
    "install_app",
    "scan_qr",
]
FRICTIONS = ["low", "mid", "high"]
PERSONALIZATION_LEVELS = ["broadcast", "segmented", "targeted"]
PERSONALIZATION_SIGNALS = [
    "real_name",
    "transaction_history",
    "thread_injection",
    "internal_jargon",
]
ISOLATION_TACTICS = ["secrecy", "bypass_approval", "direct_channel", "none"]

NEUTRAL_LEVERS: dict[str, Any] = {
    "urgency": {"tactic": "none", "intensity": 0},
    "authority": {"impersonates": "none", "credibilityTricks": []},
    "incentive": {"type": "reward", "hook": "prize", "intensity": 0},
    "callToAction": {"action": "click_link", "friction": "high"},
    "personalization": {"level": "broadcast", "signals": []},
    "isolation": {"tactic": "none", "intensity": 0},
}


def validate_levers(data: Any) -> dict[str, Any]:
    """Validate and sanitize a raw dictionary into a strictly conforming levers structure."""
    if not isinstance(data, dict):
        return NEUTRAL_LEVERS.copy()

    result = NEUTRAL_LEVERS.copy()

    # 1. Urgency
    urg = data.get("urgency")
    if isinstance(urg, dict):
        tactic = str(urg.get("tactic", "none")).lower()
        if tactic not in URGENCY_TACTICS:
            tactic = "none"
        try:
            intensity = max(0, min(3, int(urg.get("intensity", 0))))
        except (ValueError, TypeError):
            intensity = 0
        result["urgency"] = {"tactic": tactic, "intensity": intensity}

    # 2. Authority
    auth = data.get("authority")
    if isinstance(auth, dict):
        imp = str(auth.get("impersonates", "none")).lower()
        if imp not in IMPERSONATES:
            imp = "none"
        raw_tricks = auth.get("credibilityTricks") or auth.get("credibility_tricks") or []
        tricks = []
        if isinstance(raw_tricks, list):
            for t in raw_tricks:
                if isinstance(t, str) and t.lower() in CREDIBILITY_TRICKS and t.lower() not in tricks:
                    tricks.append(t.lower())
        result["authority"] = {"impersonates": imp, "credibilityTricks": tricks}

    # 3. Incentive
    inc = data.get("incentive")
    if isinstance(inc, dict):
        itype = str(inc.get("type", "reward")).lower()
        if itype not in INCENTIVE_TYPES:
            itype = "reward"
        hook = str(inc.get("hook", "prize")).lower()
        if hook not in INCENTIVE_HOOKS:
            hook = "prize"
        try:
            intensity = max(0, min(3, int(inc.get("intensity", 0))))
        except (ValueError, TypeError):
            intensity = 0
        result["incentive"] = {"type": itype, "hook": hook, "intensity": intensity}

    # 4. Call to Action
    cta = data.get("callToAction") or data.get("call_to_action")
    if isinstance(cta, dict):
        action = str(cta.get("action", "click_link")).lower()
        if action not in CTA_ACTIONS:
            action = "click_link"
        friction = str(cta.get("friction", "mid")).lower()
        if friction not in FRICTIONS:
            friction = "mid"
        result["callToAction"] = {"action": action, "friction": friction}

    # 5. Personalization
    pers = data.get("personalization")
    if isinstance(pers, dict):
        level = str(pers.get("level", "broadcast")).lower()
        if level not in PERSONALIZATION_LEVELS:
            level = "broadcast"
        raw_signals = pers.get("signals") or []
        signals = []
        if isinstance(raw_signals, list):
            for s in raw_signals:
                if isinstance(s, str) and s.lower() in PERSONALIZATION_SIGNALS and s.lower() not in signals:
                    signals.append(s.lower())
        result["personalization"] = {"level": level, "signals": signals}

    # 6. Isolation
    iso = data.get("isolation")
    if isinstance(iso, dict):
        tactic = str(iso.get("tactic", "none")).lower()
        if tactic not in ISOLATION_TACTICS:
            tactic = "none"
        try:
            intensity = max(0, min(3, int(iso.get("intensity", 0))))
        except (ValueError, TypeError):
            intensity = 0
        result["isolation"] = {"tactic": tactic, "intensity": intensity}

    return result


def extract_heuristic_levers(text: str) -> dict[str, Any]:
    """Deterministic regex-based heuristic extractor used as offline fallback.

    Ensures the system produces consistent social engineering signals even when
    external LLMs are unavailable, rate limited, or disabled.
    """
    raw = (text or "").lower()

    # --- Authority Detection ---
    impersonates = "none"
    credibility_tricks: list[str] = []

    financial_patterns = [
        r"\b(sbi|hdfc|icici|axis|pnb|bob|bank|banking|rbi|debit card|credit card|kyc|pan card|aadhaar|account block|upi|paytm|phonepe|gpay|wallet)\b"
    ]
    govt_patterns = [
        r"\b(income tax|itr|challan|court|police|cbi|ed|customs|ministry|pib|aadhaar update|pm yojana|sarkari|electricity|power|bijli|department|energy)\b"
    ]
    delivery_patterns = [
        r"\b(courier|parcel|delivery|fedex|dhl|bluedart|speedpost|india post|consignment|shipment|post office|customs duty)\b"
    ]
    platform_patterns = [
        r"\b(netflix|amazon|whatsapp|instagram|facebook|telegram|google|apple id|microsoft|kbc|jio|airtel)\b"
    ]

    if any(re.search(p, raw) for p in financial_patterns):
        impersonates = "financial"
    elif any(re.search(p, raw) for p in govt_patterns):
        impersonates = "government"
    elif any(re.search(p, raw) for p in delivery_patterns):
        impersonates = "delivery"
    elif any(re.search(p, raw) for p in platform_patterns):
        impersonates = "platform"

    if re.search(r"\b(ref|reference|ticket|case|utr|id|parcel|ind\d+|tracking)[:\s#]*[a-z0-9-]{4,}\b", raw):
        credibility_tricks.append("reference_number")
    if re.search(r"\b(dear customer|valued customer|sir/madam|officer|strictly confidential|alert:)\b", raw):
        credibility_tricks.append("formal_tone")

    # --- Urgency Detection ---
    urgency_tactic = "none"
    urgency_intensity = 0

    if re.search(r"\b(block|suspend|deactivat|freeze|cut\s*off|disconnect|terminat|halt)\w*\b", raw):
        urgency_tactic = "account_freeze"
        urgency_intensity = 3
    elif re.search(r"\b(immediately|urgent|within\s*\d+\s*(hours?|mins?|days?)|today|by tonight|tonight|before midnight|24 hours?|now\b)\b", raw):
        urgency_tactic = "deadline"
        urgency_intensity = 2
    elif re.search(r"\b(limited period|offer ends|first \d+ users|valid only)\b", raw):
        urgency_tactic = "limited_offer"
        urgency_intensity = 2

    # --- Incentive Detection ---
    incentive_type = "reward"
    incentive_hook = "prize"
    incentive_intensity = 0

    if urgency_tactic == "account_freeze" or re.search(r"\b(penalty|legal action|arrest|fir|police complaint|court order|blacklisted|held\b|unpaid|fee|overdue|fine|duty)\b", raw):
        incentive_type = "fear"
        incentive_hook = "penalty" if re.search(r"\b(held|duty|fee|unpaid|fine|overdue)\b", raw) else "account_loss"
        incentive_intensity = 3
    elif re.search(r"\b(won|winner|lottery|prize|cashback|bonus|gift voucher|congratulations|reward|free recharge|lucky draw|earn\b|salary|work from home|part-time|daily income)\b", raw):
        incentive_type = "reward"
        incentive_hook = "prize"
        incentive_intensity = 3
    elif re.search(r"\b(refund|tax rebate|subsidy|overpaid|approved amount)\b", raw):
        incentive_type = "reward"
        incentive_hook = "refund"
        incentive_intensity = 2

    # --- Call to Action Detection ---
    cta_action = "click_link"
    cta_friction = "high"

    has_link = bool(re.search(r"https?://|\.apk\b|bit\.ly|tinyurl|\.xyz\b|\.top\b", raw))

    if re.search(r"\b(enter otp|submit otp|share otp|enter pin|mpin|password|pan details|update.*pan|verify kyc)\b", raw):
        cta_action = "input_credentials"
        cta_friction = "low"
    elif re.search(r"\b(\.apk\b|install app|download app|anydesk|teamviewer|rustdesk)\b", raw):
        cta_action = "install_app"
        cta_friction = "low"
    elif re.search(r"\b(pay\b|send rs|transfer|processing fee|clearance fee|deposit|recharge|unpaid duty|duty fee|unpaid bill)\b", raw):
        cta_action = "transfer_money"
        cta_friction = "low"
    elif re.search(r"\b(scan qr|scan this code)\b", raw):
        cta_action = "scan_qr"
        cta_friction = "low"
    elif re.search(r"\b(call\b|contact officer|officer.*at|helpline:?\s*\+?\d{8,}|\b\d{10}\b)\b", raw):
        cta_action = "call_number"
        cta_friction = "mid"
    elif has_link:
        cta_action = "click_link"
        cta_friction = "low"
    else:
        cta_friction = "high"

    # --- Personalization Detection ---
    pers_level = "broadcast"
    pers_signals: list[str] = []

    if re.search(r"\b(utr\s*[:#]?\s*\w+|ac\s*no\.?\s*x{2,}\d{3,}|txn\s*id)\b", raw):
        pers_signals.append("transaction_history")
        pers_level = "segmented"
    if re.search(r"\b(mr\.|mrs\.|ms\.)\s+[a-z]{3,}\b", raw):
        pers_signals.append("real_name")
        pers_level = "targeted"

    # --- Isolation Detection ---
    isolation_tactic = "none"
    isolation_intensity = 0

    if re.search(r"\b(do not (tell|share|inform)|keep (this )?secret|strictly confidential|do not discuss|do not contact bank)\b", raw):
        isolation_tactic = "secrecy"
        isolation_intensity = 3
    elif re.search(r"\b(contact.*(whatsapp|telegram)|message.*(whatsapp|telegram)|join.*telegram|manager on telegram|@work_\w+|direct personal telegram|bypass)\b", raw):
        isolation_tactic = "direct_channel"
        isolation_intensity = 2

    return {
        "urgency": {"tactic": urgency_tactic, "intensity": urgency_intensity},
        "authority": {"impersonates": impersonates, "credibilityTricks": credibility_tricks},
        "incentive": {"type": incentive_type, "hook": incentive_hook, "intensity": incentive_intensity},
        "callToAction": {"action": cta_action, "friction": cta_friction},
        "personalization": {"level": pers_level, "signals": pers_signals},
        "isolation": {"tactic": isolation_tactic, "intensity": isolation_intensity},
    }
