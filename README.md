# TruthCheck — Fake News Detection & Media Literacy

TruthCheck is an educational, production-quality single-page web application combining **machine learning text analysis**, **rule-based warning-sign detection**, and **external news verification via FreeNewsAPI.ai** — complete with interactive media-literacy guidance, a 10-question educational quiz, and local browser check history.

> **Important Limitation:** TruthCheck is an **AI-assisted language-pattern detector** and educational media-literacy tool. It evaluates linguistic style, structural warning signs, and supporting outside news coverage to provide an estimated **Credibility Score** — it is **not** an authoritative arbiter of absolute factual truth.

---

## Features

| Feature | Description |
|---------|-------------|
| **News Detector** | Analyze headlines, articles, or social claims. Produces a continuous Credibility Score (0–100%), flags 10 rule-based warning signs (sensationalism, clickbait, absolute claims, unsupported statements, missing attribution, excessive punctuation, ALL-CAPS, emotional hooks, artificial urgency, missing dates), and searches supporting coverage. |
| **Result Card** | Clean three-tier verdict (🟢 **Likely True** · 🟡 **Needs Verification** · 🔴 **Likely Fake**) with single **Credibility Score**, balanced explanatory summary, and 4 practical media-literacy action steps. |
| **Media Literacy** | Six structured educational cards: **Source**, **Date**, **Author**, **Evidence**, **Cross-check**, **Context** — each with *What to check*, *Why it matters*, and *What to do*. |
| **Interactive Quiz** | 10-question interactive media-literacy quiz with progress bar, option validation, instant feedback, scoring, and complete review mode. |
| **Check History** | Stores the last 15 checks locally in browser `localStorage` with verdict, credibility score, and timestamp; one-click restore and clear confirmation. |

---

## Architecture & Data Flow

```text
Browser User Interface
         │
         ▼  (POST /api/analyze)
Flask Backend (app.py)
         │
         ├──► ML Detector (detector/detector.py)
         │       • TF-IDF (1–2 grams, sublinear TF) + Logistic Regression
         │       • Outputs P(misleading_style)
         │       • Credibility Score = round((1 - P(misleading)) * 100)
         │       • Rule-based Warning Signs (regex patterns)
         │
         └──► News Verification Service (services/verification.py)
                 • Deterministic entity/topic extraction (build_search_query)
                 • FreeNewsAPI.ai (/v1/search) — Keyless, public endpoint
                 • URL safety validation (http/https only, netloc required)
                 • In-process LRU cache (prevents duplicate queries)
                 • Multi-tier error handling (safe fallback, no stack traces)
```

**Primacy Principle:** The ML detector remains the primary analysis engine. FreeNewsAPI.ai acts strictly as supporting context; news search results **never** alter the ML credibility score or independently declare a story true or fake.

---

## How the Verdict is Formed

1. **Text Preprocessing** — Normalizes whitespace, Unicode quotes/dashes, extracts URLs and email tokens, cleans punctuation while preserving numbers, names, and entities.
2. **Language Model** — Cleaned text → TF-IDF Vectorizer (5,000 max features, 1–2 ngrams, sublinear scaling) → Logistic Regression → `P(misleading-style)`.
3. **Credibility Score** — `round((1.0 - P(misleading-style)) * 100)`. Higher score represents higher likelihood of reliable journalistic style.
4. **Single Public Threshold**:
   - `Credibility Score < 50%` → 🔴 **Likely Fake**
   - `Credibility Score = 50%` → 🟡 **Needs Verification**
   - `Credibility Score > 50%` → 🟢 **Likely True**
5. **Warning-Sign Detection** — Independent regex checks flag sensationalism, ALL-CAPS, clickbait, absolutes, unsupported claims, missing attribution, emotional language, sharing urgency, and missing date cues.
6. **External Verification** — Extracts key topical entities and searches FreeNewsAPI.ai for related coverage, returning normalized source cards (title, host/sitename, URL, publication date, description).

---

## Technology Stack

- **Backend**: Python 3.10+, Flask 3.0+
- **Machine Learning**: scikit-learn (TF-IDF Vectorizer + Logistic Regression, balanced class weights)
- **External News Search**: FreeNewsAPI.ai (REST API, keyless)
- **Frontend**: Semantic HTML5, Vanilla CSS3 (responsive grid/flexbox, editorial aesthetic), Vanilla JavaScript (ES6+, zero frontend frameworks, localStorage persistence)
- **Testing**: Python standard `unittest` framework (unit, integration, mock, live API, and end-to-end tests)

---

## Quick Start

### 1. Prerequisites & Virtual Environment
```bash
cd TruthCheck

# Create and activate virtual environment
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows Command Prompt:
.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. (Optional) Regenerate Dataset & Retrain Model
```bash
python scripts/generate_dataset.py
python -c "from detector.detector import NewsDetector; print(NewsDetector().train())"
```

### 3. Run the Application
```bash
python app.py
```
Open your browser to: **http://localhost:5000** (or **http://127.0.0.1:5000**).

---

## Running the Automated Test Suite

Execute the complete automated test suite (42 tests covering ML pipeline, FreeNewsAPI adapter, Flask API endpoints, and demo buttons):

```bash
# Using active venv:
python -m unittest discover tests

# Or directly with venv binary:
.venv\Scripts\python.exe -m unittest discover tests
```

---

## API Documentation

### `POST /api/analyze`
Analyzes a submitted news headline or article.
- **Request Body:** `{"text": "Headline or article text (min 20, max 8,000 chars)"}`
- **Response Structure:**
  ```json
  {
    "verdict": {
      "id": "likely_true",
      "label": "Likely True",
      "emoji": "🟢",
      "tone": "ok"
    },
    "credibility_score": 88,
    "summary": "This news shows patterns commonly associated with reliable news (88% credibility)...",
    "why": ["Language patterns match neutral reporting.", "..."],
    "signals": [
      {"id": "source", "label": "Source", "detail": "..."},
      {"id": "language", "label": "Language", "detail": "..."},
      {"id": "evidence", "label": "Evidence", "detail": "..."}
    ],
    "warning_signs": [],
    "model": {
      "probabilities": {
        "reliable_style": 0.88,
        "misleading_style": 0.12
      },
      "note": "Credibility signal only — not proof of truth or falsehood."
    },
    "verification": {
      "status": "ok",
      "message": "Found 5 related articles.",
      "sources": [
        {
          "title": "Article Title",
          "url": "https://example.com/story",
          "source": "Publisher Name",
          "publishedAt": "2026-09-23T12:00:00Z",
          "description": "Short excerpt..."
        }
      ]
    },
    "tips": ["Still check the publication date.", "..."],
    "elapsed_ms": 420
  }
  ```

### `GET /api/health`
Returns system status, ML detector readiness, metrics, and verification status:
```json
{
  "status": "ok",
  "model": "ready",
  "metrics": {
    "accuracy": 1.0,
    "precision": 1.0,
    "recall": 1.0,
    "f1": 1.0,
    "train_rows": 1200
  },
  "verification": "configured"
}
```

---

## Known Limitations

1. **Linguistic Heuristic, Not Fact Oracle:** TruthCheck evaluates writing style and journalistic patterns. An authentic journalist quoting a ridiculous statement or a malicious actor writing in dry, neutral bureaucratic style may produce unexpected credibility scores.
2. **Dataset Nature:** The demo dataset contains 1,200 curated, balanced samples across multiple real-world news categories (space, medicine, economy, policy) and misinformation categories (miracle cures, conspiracies, clickbait). Real-world news diversity is vast; for production deployment at national scale, fine-tuning on academic datasets (such as LIAR or FEVER) is recommended.
3. **Public FreeNewsAPI Quotas:** External verification depends on the public FreeNewsAPI.ai service. If the external service experiences downtime or network rate-limiting, TruthCheck gracefully falls back to local linguistic analysis without crashing.
