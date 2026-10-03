"""TruthCheck — Flask backend.

Single-page frontend + ML detector + external verification service.
Run:  python app.py   (then open http://localhost:5000)
"""
from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, render_template, request

from detector.detector import NewsDetector
from detector.preprocessing import first_line
from services.fact_checker import FactChecker
from services.fraud_detector import FraudDetector
from services.verification import VerificationService

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("truthcheck")

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.config["TEMPLATES_AUTO_RELOAD"] = True

detector = NewsDetector()
fact_checker = FactChecker()
verification = VerificationService()
fraud_detector = FraudDetector()

# ------------------------------------------------------------------ lifecycle
with app.app_context():
    metrics = detector.ensure_ready()
    logger.info("Model ready: %s", metrics)
    logger.info("FactChecker ready: AI model=%s, configured=%s", fact_checker.ai.model, fact_checker.ai.is_configured)
    logger.info("FraudDetector ready: known_scams=%d", len(fraud_detector.scam_matcher.patterns))


VERIFICATION_TIPS = {
    "likely_true": [
        "Still check the publication date.",
        "Skim one source below to confirm.",
        "For big claims, prefer the original report.",
    ],
    "needs_verification": [
        "Find the original source before sharing.",
        "Compare two reputable outlets.",
        "Check if the headline overstates the article.",
    ],
    "likely_fake": [
        "Don’t share yet — read the sources first.",
        "Look for evidence, not just emotion.",
        "Cross-check with reliable outlets.",
    ],
}

VERIFICATION_WHYS = {
    "likely_true": [
        "Language patterns match neutral reporting.",
        "Source cues were present.",
        "Few warning signs detected.",
    ],
    "needs_verification": [
        "Some cues need a closer look.",
        "Evidence or attribution may be incomplete.",
        "Compare related coverage before trusting it.",
    ],
    "likely_fake": [
        "Patterns match misleading content.",
        "Emotional wording outweighs evidence.",
        "Verify independently before sharing.",
    ],
}


def build_signals(prediction, verification_result: dict) -> list[dict]:
    """Group warning signs + verification state into three key signals.

    Returns the KEY SIGNALS block the frontend renders:
    Source · Language · Evidence (brief §7).
    """
    from detector.detector import LANGUAGE_SIGN_IDS

    sign_ids = {s["id"] for s in prediction.warning_signs}
    n_sources = len(verification_result.get("sources") or [])
    ver_status = verification_result.get("status", "error")

    # --- Source ---
    if "attribution" in sign_ids:
        source_detail = "No clear source identified."
        if n_sources:
            source_detail += f" {n_sources} related article{'s' if n_sources != 1 else ''} found."
    elif n_sources:
        source_detail = f"Source cues present · {n_sources} related article{'s' if n_sources != 1 else ''}."
    else:
        source_detail = "Source cues present in the text."

    # --- Language ---
    language_signs = [s for s in prediction.warning_signs if s["id"] in LANGUAGE_SIGN_IDS]
    if language_signs:
        titles = ", ".join(s["title"].lower() for s in language_signs[:3])
        language_detail = f"Detected: {titles}."
    else:
        language_detail = "Neutral, report-style language."

    # --- Evidence ---
    if "unsupported" in sign_ids or "absolute" in sign_ids:
        evidence_detail = "Extraordinary claim without supporting evidence."
    elif n_sources:
        evidence_detail = "Related coverage found — compare with the claim."
    elif ver_status == "no_results":
        evidence_detail = "No supporting evidence established."
    elif ver_status in {"error", "not_configured"}:
        evidence_detail = "External check unavailable — judge from the text."
    else:
        evidence_detail = "No strong evidence cues in the text."

    return [
        {"id": "source", "label": "Source", "detail": source_detail},
        {"id": "language", "label": "Language", "detail": language_detail},
        {"id": "evidence", "label": "Evidence", "detail": evidence_detail},
    ]


# --------------------------------------------------------------------- routes
@app.get("/")
def index():
    resp = make_response(render_template("index.html"))
    # Dev-friendly: never serve a stale shell (old HTML + missing asset versions).
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "model": "ready" if detector.is_ready else "missing",
        "metrics": detector.metrics,
        "verification": "configured" if verification.is_configured else "not_configured",
        "fact_checker": {
            "model": fact_checker.ai.model,
            "configured": fact_checker.ai.is_configured,
            "search": "ready",
        },
        "fraud_detector": {
            "status": "ready",
            "patterns": len(fraud_detector.scam_matcher.patterns),
        },
    })



@app.post("/api/analyze")
def analyze():
    started = time.time()
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()

    if len(text) < 20:
        return jsonify({
            "error": "Please enter at least 20 characters.",
        }), 400
    if len(text) > 8000:
        return jsonify({
            "error": "Please keep your text under 8,000 characters.",
        }), 400

    # 1. Linguistic style & warning signs (Layer 1)
    try:
        prediction = detector.predict(text)
    except Exception:
        logger.exception("Linguistic analysis failed")
        prediction = None

    # 2. Real-World Fact Verification & Live Search (Layer 2 & 3)
    try:
        fact_result = fact_checker.analyze(text)
    except Exception:
        logger.exception("FactChecker execution failed")
        return jsonify({"error": "Fact verification failed unexpectedly. Please try again."}), 500

    verdict = fact_result["verdict"]

    # Build key signals combining linguistic patterns + live sources
    signals = build_signals(prediction, {"sources": fact_result["sources"]}) if prediction else []

    return jsonify({
        "verdict": verdict,
        "confidence": fact_result.get("confidence", fact_result["credibility_score"]),
        "credibility_score": fact_result["credibility_score"],
        "summary": fact_result["summary"],
        "key_points": fact_result["key_points"],
        "sources": fact_result["sources"],
        "signals": signals,
        "warning_signs": prediction.warning_signs if prediction else [],
        "ai_info": fact_result["ai_info"],
        "model": {
            "name": fact_result["ai_info"]["model"],
            "ai_verified": fact_result["ai_info"]["is_ai_verified"],
            "note": "Grounded in live search & Qwen 3.8 AI reasoning.",
        },
        "verification": {
            "status": "ok" if fact_result["has_sources"] else "no_results",
            "message": f"Found {len(fact_result['sources'])} live web sources." if fact_result["has_sources"] else "No direct live sources found.",
            "sources": fact_result["sources"],
        },
        "tips": fact_result["tips"],
        "elapsed_ms": fact_result["elapsed_ms"],
    })


@app.post("/api/analyze-fraud")
def analyze_fraud():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or payload.get("message") or "").strip()
    auth_header = payload.get("authentication_results") or payload.get("auth_header")

    # Extract client IP supporting proxy headers
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.remote_addr or "127.0.0.1")

    res = fraud_detector.analyze(text=text, auth_header=auth_header, client_ip=client_ip)
    if "error" in res:
        status_code = res.get("status_code", 400)
        resp = jsonify({"error": res["error"]})
        if res.get("retry_after"):
            resp.headers["Retry-After"] = str(res["retry_after"])
        return resp, status_code

    return jsonify(res)


if __name__ == "__main__":
    # Bind 0.0.0.0 so the sandbox preview (and LAN demos) can reach the app.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)

