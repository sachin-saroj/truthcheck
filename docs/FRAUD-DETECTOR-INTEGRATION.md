# TruthCheck Fraud Detector Integration Plan
**Adapting KangaL Fraud Detection Engine into TruthCheck**

---

## 1. Executive Summary

TruthCheck is currently a working Python/Flask fact-checking and news verification system. KangaL is a reference implementation written in TypeScript/Next.js demonstrating multi-agent fraud investigation, psychological lever decomposition, and threat scoring.

This document defines the exact migration and integration plan to extract, adapt, and integrate the working fraud detection logic from KangaL into TruthCheck without breaking the existing news/claim verification architecture.

---

## 2. TruthCheck Existing Architecture

### 2.1 Backend & Services
- **Framework**: Flask 3.1.3 (`app.py`), Python 3.13.
- **Detector Layer (`detector/`)**:
  - `detector.py`: Scikit-learn TF-IDF + Logistic Regression trained on 1,200 samples (`data/dataset.csv`). Extracts linguistic warning signs (sensationalism, clickbait, attribution cues, emotional tone, absolute claims).
  - `preprocessing.py`: Text cleaning and normalizations.
- **Verification & AI Layer (`services/`)**:
  - `fact_checker.py`: Master orchestrator for real-world claim verification.
  - `search_service.py`: Real-time internet search via DuckDuckGo Search (`ddgs`) with in-memory caching and safe URL validation.
  - `openrouter_service.py`: Multi-model cascade (`google/gemma-4-31b-it:free`, `nvidia/nemotron-3-ultra-550b-a55b:free`, `qwen/qwen3.8-27b:free`) with in-memory cooldown tracking on 429/timeout errors.
  - `gemini_service.py`: Direct Google AI Studio REST integration (`gemini-3.5-flash`, etc.).
  - `evidence_verifier.py`: Deterministic fallback cross-referencing engine detecting entity contradictions, debunk signals, and corroboration.
  - `verification.py`: Keyless FreeNewsAPI.ai integration.
- **Frontend (`templates/`, `static/`)**:
  - Neo-brutalist single-page UI (`templates/index.html`, `static/css/style.css`, `static/js/app.js`).
  - Sections: Hero, 01 Detect, 02 Learn (Media Literacy), 03 Quiz, 04 History.
- **Test Suite**:
  - 56 passing unit and integration tests across `tests/` (`.venv\Scripts\python -m unittest discover tests`).

---

## 3. KangaL Architecture & Findings

### 3.1 Source Investigation Summary
KangaL implements an end-to-end multi-agent fraud detector alongside a hackathon attack-evolution loop.

1. **Working Defense Components (Valuable & Reusable)**:
   - **Psychological Levers (`leversSchema.ts`, `analyzeStructure.ts`)**: 6 core social engineering levers:
     - Urgency (tactics: `deadline`, `account_freeze`, `limited_offer`, `none`; intensity: 0–3)
     - Authority (impersonates: `financial`, `government`, `business_partner`, `executive`, `delivery`, `platform`, `none`)
     - Incentive (type: `reward`, `fear`; hook: `prize`, `refund`, `penalty`, `account_loss`, `legal_threat`)
     - Call to Action (action: `click_link`, `transfer_money`, `input_credentials`, `call_number`, `install_app`, `scan_qr`; friction: `low`, `mid`, `high`)
     - Personalization (level: `broadcast`, `segmented`, `targeted`)
     - Isolation (tactic: `secrecy`, `bypass_approval`, `direct_channel`, `none`; intensity: 0–3)
   - **Investigation Tools (`src/tools/`)**:
     - `checkUrlReputation.ts`: Google Web Risk API lookup (`MALWARE`, `SOCIAL_ENGINEERING`, `UNWANTED_SOFTWARE`). Hardcoded endpoint, no arbitrary URL fetching (SSRF safe).
     - `checkDomainAge.ts`: Queries `https://rdap.org/domain/{domain}`, extracts registration event, calculates `ageDays`. Hardcoded endpoint, strict regex domain validation (SSRF safe).
     - `verifySenderAuth.ts`: Regex parser for SPF, DKIM, and DMARC tokens in `Authentication-Results` headers.
     - `matchKnownScams.ts` / `leverVector.ts`: Weighted cosine similarity against known scam vector combinations.
   - **Scoring & Evaluation (`weights.ts`)**:
     - Linear weighted combination + `ISOLATION_FLOORS` (intensity 2 -> 55, intensity 3 -> 75).
     - Investigation bonuses: +15 (Web Risk threat), +10 (domain < 7 days old), +8 (SPF/DKIM/DMARC fail), +5 per scam match, +8 (official alert), capped at +25.
   - **Security Protections**:
     - `untrustedInput.ts`: Wraps untrusted text in nonce tags (`<untrusted_input_{randomUUID()}>`) to prevent boundary breakout and prompt injection.
     - `inputLimits.ts`: 8,000 char message cap, 4,000 char auth header cap.
     - `rateLimit.ts`: In-memory IP-based sliding window rate limiter.
     - `fallbackReason.ts`: Full deterministic reason generation when LLM is unavailable or offline.
   - **Email & MIME Parsing (`gmailParse.ts`)**:
     - MIME part traversal, Base64URL decoding, RFC2047 encoded-word decoding, URL folding/compression.

2. **Attack / Demo Machinery (DO NOT PORT)**:
   - `attacker.ts`: Synthetic scam message generation.
   - `loop.ts`: Red-team vs defender feedback mutation loop.
   - `firestore.ts`, `corpusWriter.ts`, `feedbackWriter.ts`: Cloud Firestore write infrastructure.
   - `gmailOAuth.ts`, `gmailClient.ts`, `gmailSession.ts`: Full OAuth 2.0 web flow (unnecessary complexity for first deadline).
   - `officialAlerts.json`: Fictional Japanese mock data ("カンガル銀行", "クマ証券").

---

## 4. Component Migration Matrix

| KangaL Component | Purpose in KangaL | Classification | TruthCheck Destination | Implementation & Adaptation Details |
|---|---|---|---|---|
| `src/lib/untrustedInput.ts` | Nonce-tagged prompt injection defense | **DIRECTLY REUSABLE** | `services/untrusted.py` | Port to Python using `uuid.uuid4()`. Wraps text with `<untrusted_input_{uuid}>` and enforces data-only boundary in prompts. |
| `src/lib/inputLimits.ts` | Input length caps (8k msg, 4k auth) | **DIRECTLY REUSABLE** | `services/fraud_detector.py` | Constants `MAX_MESSAGE_LENGTH = 8000`, `MAX_AUTH_LENGTH = 4000`. |
| `src/lib/rateLimit.ts` | In-memory IP rate limiter | **DIRECTLY REUSABLE** | `services/rate_limiter.py` | Python in-memory sliding window rate limiter (10 req/min per IP, 30 req/min global). |
| `src/agents/shared/leversSchema.ts` | 6 psychological social engineering levers schema | **DIRECTLY REUSABLE** | `detector/fraud_levers.py` | Python dataclasses/dicts defining the 6 levers, allowed enums, and default neutral values. |
| `src/agents/shared/validateLevers.ts` | Lever schema validation | **DIRECTLY REUSABLE** | `detector/fraud_levers.py` | Python validation function checking types, enums, and bounds (0–3). |
| `src/lib/weights.ts` | Risk scoring math, isolation floors, investigation bonus | **DIRECTLY REUSABLE** | `detector/fraud_weights.py` | Exact mathematical port: `LEVER_WEIGHTS`, `ISOLATION_FLOORS`, `CTA_DANGER`, `FRICTION_ADJ`, bonus points (+15 web risk, +10 young domain, +8 auth fail, +5 scam match, +8 alert, cap 25). |
| `src/lib/fallbackReason.ts` | Deterministic explanation builder | **DIRECTLY REUSABLE** | `services/fraud_explainer.py` | Port phrase mappings to English, tuned for global and Indian fraud patterns (UPI, KYC, courier, lottery). Band-aware (danger vs caution). |
| `src/tools/checkDomainAge.ts` | RDAP domain age lookup via rdap.org | **REUSABLE WITH MODIFICATION** | `services/domain_analyzer.py` | Python `requests` lookup to `https://rdap.org/domain/{domain}`. Enforces strict domain regex (no schemes, paths, or private IPs), 5s timeout, LRU cache. |
| `src/tools/checkUrlReputation.ts` | Google Web Risk API lookup | **REUSABLE WITH MODIFICATION** | `services/url_analyzer.py` | Python `requests` to Web Risk endpoint if `WEB_RISK_API_KEY` set. Added regex URL extractor and heuristic reputation fallback (suspicious TLDs, IP in host, punycode). |
| `src/tools/verifySenderAuth.ts` | Regex parser for SPF, DKIM, DMARC | **DIRECTLY REUSABLE** | `services/sender_analyzer.py` | Python `re` regex parser for `Authentication-Results` header strings, normalizing results to pass/fail/none. |
| `src/lib/gmailParse.ts` | MIME body, base64url, RFC2047, URL folding | **REUSABLE WITH MODIFICATION** | `services/message_parser.py` | Python `email` standard library parser for raw MIME emails, header extraction, URL extraction, and URL folding. |
| `src/tools/matchKnownScams.ts` & `src/lib/leverVector.ts` | Vector similarity against scam DB | **REIMPLEMENT IN TRUTHCHECK** | `services/known_scams.py` | Zero external DB! Uses local `data/known_scams.json` with weighted cosine similarity over lever blocks. |
| `src/tools/checkOfficialAlerts.ts` & `src/data/officialAlerts.json` | Official alert checking | **REIMPLEMENT IN TRUTHCHECK** | `services/search_service.py` & `data/known_scams.json` | Replace fictional Japanese mock alerts with live search queries for official advisories (RBI, PIB, FTC, CERT-In) via existing `SearchService`. |
| `src/agents/analyzeStructure.ts` | LLM decomposes message into 6 levers | **REUSABLE WITH MODIFICATION** | `services/fraud_detector.py` | Uses existing `OpenRouterService` / `GeminiService` with prompt-injection defense. Includes deterministic regex-based fallback if LLM is offline. |
| `src/agents/judge.ts` | Master judge: score + explanation | **REUSABLE WITH MODIFICATION** | `services/fraud_detector.py` | Master orchestrator combining deterministic scoring, external investigations, and LLM explanation. |
| `src/app/api/judge/route.ts` | API route controller | **REIMPLEMENT IN TRUTHCHECK** | `app.py` (`POST /api/analyze-fraud`) | Flask route in `app.py`. Preserves existing `POST /api/analyze` completely unchanged. |
| `src/agents/attacker.ts` | Red-team synthetic attack generator | **DO NOT PORT** | N/A | Demo-only synthetic scam generator. Unneeded for defense. |
| `src/agents/loop.ts` | Attack evolution feedback loop | **DO NOT PORT** | N/A | Demo-only mutation loop. |
| `src/lib/firestore.ts`, `corpusWriter.ts`, `feedbackWriter.ts` | Firestore read/write | **DO NOT PORT** | N/A | Avoids GCP Firestore dependency. Replaced with zero-dependency local JSON. |
| `src/lib/gmailOAuth.ts`, `gmailClient.ts`, `gmailSession.ts` | Gmail OAuth 2.0 flow | **DO NOT PORT** | N/A | Excluded to eliminate OAuth setup friction. Raw message/email parsing handles emails directly. |
| `src/lib/holdoutEval.ts` | Synthetic benchmark harness | **DO NOT PORT** | N/A | Not needed for core application. |

---

## 5. TruthCheck Integration Architecture

```
                 USER SUBMISSION
    (SMS / WhatsApp / Email / Bank Message / UPI / URL)
                        │
                        ▼
             POST /api/analyze-fraud
                        │
       ┌────────────────┴────────────────┐
       ▼                                 ▼
Rate Limiter (10 req/min)        Input Bounded Guard (8k msg, 4k auth)
       └────────────────┬────────────────┘
                        │
                        ▼
              Message / Email Parser
         (Extracts body, URLs, sender, SPF/DKIM/DMARC)
                        │
                        ▼
             Fraud Signal Analysis
       (Decomposes into 6 Psychological Levers:
  Urgency, Authority, Incentive, CTA, Personalization, Isolation)
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
 Sender Analysis   URL Analysis    Domain Analysis
  (SPF/DKIM/DMARC) (Google WebRisk)  (RDAP domain age)
        │               │               │
        └───────────────┼───────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
Known Scam Matching             Live Evidence Search
(Cosine similarity on DB)     (Official advisories: RBI/PIB/FTC)
        └───────────────┬───────────────┘
                        │
                        ▼
          Deterministic Risk Evaluation
   • baseScore = weighted sum of 6 levers
   • isolationFloor = 55 / 75 enforcement
   • investigationBonus = +15 WebRisk, +10 DomainAge,
     +8 AuthFail, +5 ScamMatch, +8 OfficialAlert (cap 25)
   • riskScore = min(100, max(base, floor) + bonus)
   • riskLevel = CRITICAL | HIGH_RISK | SUSPICIOUS | LOW_RISK
   • verificationStatus = VERIFIED_FRAUD | UNVERIFIED | VERIFIED_LEGITIMATE
                        │
                        ▼
           OpenRouter / Gemini AI Reasoning
   • Nonce-tagged prompt-injection protection (<untrusted_input_{uuid}>)
   • Calibrated tone (danger vs caution)
   • Deterministic fallback explanation if LLM is offline
                        │
                        ▼
             Structured Fraud Result
                        │
                        ▼
          TruthCheck Dual-Mode Frontend
   • Toggle: [ 📰 News / Claim ] vs [ 🛡️ Message & Fraud Safety ]
   • Renders Verdict, Score, Signals, External Evidence & Safety Advice
```

---

## 6. Files To Create

1. `services/untrusted.py`:
   - Nonce-tagged prompt-injection wrapper (`wrap_untrusted(text)`) generating `<untrusted_input_{uuid}>`.
2. `services/rate_limiter.py`:
   - In-memory thread-safe sliding window rate limiter (client IP and global).
3. `detector/fraud_levers.py`:
   - Python dataclasses and validation for the 6 psychological levers, plus deterministic heuristic fallback lever extractor.
4. `detector/fraud_weights.py`:
   - Exact mathematical implementation of `LEVER_WEIGHTS`, `ISOLATION_FLOORS`, `CTA_DANGER`, `FRICTION_ADJ`, and `compute_investigation_bonus`.
5. `services/domain_analyzer.py`:
   - RDAP domain age querying (`https://rdap.org/domain/{domain}`) with strict regex validation, 5s timeout, and LRU cache.
6. `services/url_analyzer.py`:
   - URL extraction from text, SSRF-safe Google Web Risk integration, and heuristic suspicious URL pattern checks (IP-based URLs, suspicious TLDs, excessive subdomains).
7. `services/sender_analyzer.py`:
   - Email header and `Authentication-Results` parser for SPF, DKIM, and DMARC status.
8. `services/message_parser.py`:
   - Parses raw pasted messages, SMS, or MIME RFC822 emails, extracts clean body, headers, and folded URLs.
9. `services/known_scams.py`:
   - Vector similarity matcher evaluating lever similarity against known scam templates.
10. `data/known_scams.json`:
    - Curated database of scam patterns: Bank KYC block, UPI collect fraud, electricity cutoff, fake job offer, customs parcel, lottery/crypto, executive impersonation.
11. `services/fraud_explainer.py`:
    - Deterministic plain-language, non-alarmist reason generator supporting danger and safe bands, integrating active levers and investigation findings.
12. `services/fraud_detector.py`:
    - Master fraud detection orchestrator coordinating parser, signals, tools, scoring, evidence, and explanation.
13. `tests/test_fraud_detector.py`:
    - Comprehensive unit and integration test suite covering levers, weights, domain age, sender auth, known scam matching, rate limiter, prompt injection defense, and end-to-end fraud pipeline.

---

## 7. Files To Modify

1. `app.py`:
   - Add `POST /api/analyze-fraud` route.
   - Update `GET /api/health` to report fraud detector readiness.
   - **DO NOT TOUCH** `POST /api/analyze` or existing news detector initialization.
2. `templates/index.html`:
   - Add a mode switcher in the Detect section: `[ 📰 News & Claim ]` and `[ 🛡️ Message & Fraud Safety ]`.
   - Add sample buttons for fraud scenarios (Bank KYC, UPI Payment, Job Offer, Lottery).
   - Ensure the result card cleanly displays fraud risk levels, verification status, signals, and actionable recommendations.
3. `static/js/app.js`:
   - Support active mode switching between News Analysis (`/api/analyze`) and Fraud Analysis (`/api/analyze-fraud`).
   - Format fraud result cards with risk score, verification status badge, psychological signals, and safety recommendations.
4. `.env.example`:
   - Add optional `WEB_RISK_API_KEY=` entry.

---

## 8. Files To Leave Untouched

- `detector/detector.py`: Existing scikit-learn news model and linguistic warning sign detector.
- `detector/preprocessing.py`: Existing news text preprocessing.
- `detector/model.pkl`: Serialized news classification model.
- `data/dataset.csv`: News training dataset.
- `services/fact_checker.py`: News fact-checking orchestrator.
- `services/evidence_verifier.py`: Semantic news evidence verifier.
- `services/verification.py`: FreeNewsAPI integration.
- `tests/test_app.py`, `tests/test_detector.py`, `tests/test_evidence_verifier.py`, `tests/test_fact_checker.py`, `tests/test_gemini_service.py`, `tests/test_verification.py`: Existing 56 passing tests.

---

## 9. Dependencies Assessment

### Dependencies to Reuse:
- `Flask>=3.0`: Backend routing.
- `requests>=2.31`: HTTP requests for RDAP and Web Risk.
- `python-dotenv>=1.0`: Configuration management.
- `ddgs>=9.0.0`: Live search for official advisories.
- Python Standard Library:
  - `re`: Regex parsing (domain, URLs, authentication headers).
  - `uuid`: Nonce generation for prompt injection defense.
  - `email`: MIME and RFC822 email parsing.
  - `urllib.parse`: Safe URL and domain decomposition.
  - `json`: Data parsing.
  - `time`: Timing and rate limiting.

### Dependencies NOT Needed:
- Google Cloud Firestore SDK (`@google-cloud/firestore`): Replaced with local JSON dataset.
- Google Vertex AI SDK (`@google/genai`): TruthCheck already has direct Gemini API and OpenRouter REST clients.
- Next.js / React / TypeScript / Node.js runtime: Not needed in TruthCheck's Python backend.

---

## 10. Security Considerations

1. **SSRF (Server-Side Request Forgery) Prevention**:
   - The server **NEVER** performs an HTTP fetch on user-supplied URLs.
   - Domain age checks query only hardcoded `https://rdap.org/domain/{domain}`.
   - Reputation checks query only hardcoded Google Web Risk endpoints with user URLs passed as string query parameters.
   - Strict regex validation rejects URLs/domains containing internal IP ranges (`127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`, `localhost`) or non-standard protocols (`file://`, `gopher://`).
2. **Prompt Injection Defense**:
   - User messages, emails, headers, and external snippets are labeled as untrusted data using random UUID nonces (`<untrusted_input_{uuid}>...`).
   - System prompts explicitly instruct the LLM that content inside the nonce tag is passive data to analyze, never instructions to execute.
   - In multi-turn tool outputs, raw user header values are stripped before re-prompting.
3. **Input Limits & DoS Protection**:
   - `MAX_MESSAGE_LENGTH = 8000` characters.
   - `MAX_AUTH_LENGTH = 4000` characters.
   - IP-based sliding window rate limiter (10 req/min per IP) preventing endpoint abuse.
4. **API Key & Secret Safety**:
   - All API keys (`OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `WEB_RISK_API_KEY`) remain strictly on the backend and are never returned in JSON responses or exposed to the client.

---

## 11. Core Verification Principles (LOW RISK ≠ SAFE, UNVERIFIED ≠ FRAUD)

The Fraud Detector strictly implements the following state matrix:
1. **Low Risk ≠ Guaranteed Safe**: A benign-looking message (e.g. "Your account credited with Rs 50,000") is marked `LOW_RISK`, but its `verificationStatus` remains `UNVERIFIED` because a private transaction cannot be proven by an external system.
2. **Unverified ≠ Fraud**: A message lacking public corroboration is flagged as `UNVERIFIED`, not automatically labeled `FRAUD`.
3. **Risk Score vs. Confidence**: `riskScore` represents the deterministic threat level (0–100) based on detected attack levers and investigation bonuses. `confidence` is reported separately and represents the degree of certainty in the signal extraction.

---

## 12. Implementation Sequence

1. **Step 1: Security & Utilities Foundation**:
   - Implement `services/untrusted.py` (nonce wrapping).
   - Implement `services/rate_limiter.py` (IP rate limiting).
2. **Step 2: Signal Extraction & Scoring Engine**:
   - Implement `detector/fraud_levers.py` (6-lever definitions and validator).
   - Implement `detector/fraud_weights.py` (mathematical scoring, floors, and bonuses).
   - Implement `services/fraud_explainer.py` (deterministic reason generator).
3. **Step 3: Investigation Tools**:
   - Implement `services/domain_analyzer.py` (RDAP lookup with SSRF guards).
   - Implement `services/url_analyzer.py` (safe URL extraction and reputation).
   - Implement `services/sender_analyzer.py` (SPF/DKIM/DMARC parsing).
   - Implement `services/known_scams.py` and create `data/known_scams.json`.
4. **Step 4: Orchestrator Integration**:
   - Implement `services/message_parser.py` (MIME and message parsing).
   - Implement `services/fraud_detector.py` (master orchestrator).
5. **Step 5: API Route & Frontend Integration**:
   - Add `POST /api/analyze-fraud` in `app.py`.
   - Update `templates/index.html` and `static/js/app.js` with mode switching and fraud card presentation.
6. **Step 6: Testing & Quality Gate**:
   - Create `tests/test_fraud_detector.py`.
   - Verify all 56 existing tests pass alongside new fraud tests.
