# TruthCheck — Upgrade Plan (Pre-Approval)
**Date:** 2026-09-23 · **Status:** Awaiting approval · **Scope:** College/CEP assignment, single-page app

---

## 1. Current Architecture Summary

```
Browser (index.html + style.css + app.js, vanilla JS)
   │  POST /api/analyze {text}
   ▼
app.py (Flask, 162 lines)
   ├─ detector/detector.py  — NewsDetector: clean_text → TF-IDF(1–2gram) → Random Forest
   │     • 7 warning-sign rules: sensational, punctuation, caps, absolute,
   │       clickbait, unsupported, attribution
   │     • 3-tier verdict: P(misleading) + sign count → Likely Reliable /
   │       Needs Verification / Potentially Misleading
   │     • model.pkl trained at startup from data/dataset.csv (440 synthetic rows)
   ├─ services/verification.py — FreeNewsAPI.ai client (isolated, keyless)
   │     • statuses: ok | no_results | not_configured | error
   └─ Conservative downgrade: model says "reliable" but no corroboration
        + ≥1 sign → Needs Verification

Frontend sections (one page): Hero → Detector → Result → Learn → Quiz → History → Footer
State: quiz in JS memory · history in localStorage (max 15) · no DB, no auth
```

**Verified live (today):** server up :5000 · `/api/health` 200 (model ready) ·
analyze 200/400 correct · CSS/JS 200 · XSS probe: HTML reflected only via
`textContent` (safe) · `.env` gitignored, key never sent to client.

---

## 2. Current UI/UX Problems Found

### Critical (violates brief)
| # | Problem | Where |
|---|---------|-------|
| C1 | **Footer exposes tech stack** — "TF-IDF · Random Forest · GNews · localStorage" (brief §16 forbids) | `index.html` footer |
| C2 | **Hero method list also exposes tech** (TF-IDF + Random Forest, GNews) in main UI | `index.html` hero |
| C3 | **Typography: serif used for everything** — brief §4B wants serif headings + **sans body/UI/buttons**; buttons are currently mono | `style.css` |
| C4 | **Footer missing About / Methodology / Privacy** links | `index.html` |
| C5 | **Clear History has no confirmation** (brief §14) | `app.js` |
| C6 | **History stores no score/indicator** — only text+verdict+time (brief §14 wants score/indicator) | `app.js` |
| C7 | **History click reloads textarea only** — does not restore the result view | `app.js` |
| C8 | **Quiz: no "Review Results", no "Please select an answer"** message (Next is silently disabled) (brief §13, §17F) | `app.js` |
| C9 | **Sources show no description and no "Open Source" button** — description already received from API but not rendered (brief §7) | `app.js` |
| C10 | **Loading state is one line** — brief wants 3-step: "Analyzing… / Checking language patterns… / Looking for verification sources…" | `index.html`/`app.js` |
| C11 | **Only 2 samples** — brief wants Report, Suspicious, Social Post, Claim (4) | `index.html` |
| C12 | **`not_configured` message is developer-facing** — "Add VERIFICATION_API_KEY to .env" shown to users (internals leak; brief §9 wants friendly copy) | `app.py` |

### Important (polish)
| # | Problem |
|---|---------|
| I1 | Warning signs missing: **missing date**, **urgency/sharing pressure**, distinct **emotional language** (brief §11 lists 10) |
| I2 | Result lacks a unified **KEY SIGNALS** block (Source / Language / Evidence grouping as in brief §7 example) — currently "Why" and "Warning signs" are two separate lists |
| I3 | Result missing **"Check Another Story"** CTA (brief §4D) |
| I4 | Learn cards missing **WHAT TO CHECK / WHY IT MATTERS / WHAT TO DO** structure + **[Learn more]** expand (brief §12) |
| I5 | Hero missing small disclaimer line under CTA and a true **[How it works]** secondary button (brief §5) |
| I6 | Empty-detector inline hint ("Paste a headline… to begin") not shown as a state (brief §17B) |
| I7 | No distinct **"No matching verification sources were found"** vs API-down copy in result (§17C/D — backend has it, UI copy must match exactly) |
| I8 | Button **active/loading** states incomplete; "Try Sample" phrasing per brief |
| I9 | Spacing: hero slightly tall; detector should appear faster (brief §5) |
| I10 | History rows show no score indicator chip |

### Already good — preserve
Editorial identity (paper palette, red accent, Newsreader headings, numbered nav) · sticky nav with active state + smooth scroll · 3-tier honest verdicts · warning-sign list only shows detected signs · quiz progress bar · localStorage 15-cap · reveal animation (respects `prefers-reduced-motion`) · responsive breakpoints · dateline detail · no gradients/glassmorphism/shadows abuse.

---

## 3. Files to Modify

| File | Changes |
|------|---------|
| `templates/index.html` | Hero (disclaimer, How-it-works btn, de-tech the method list), detector (4 samples, 3-step loader, empty hint), result (Key Signals grouping, Open Source buttons, Check Another Story), Learn cards (3-part + Learn more), Quiz (Review Results view, validation msg), History (score chip, confirm UI), Footer (About/Methodology/Privacy, remove tech string) |
| `static/css/style.css` | Add sans body font; keep serif for headings only; button state matrix; spacing rhythm; new components (signal blocks, dialog/expand, review view, toast/confirm) |
| `static/js/app.js` | Sample set → 4; staged loading copy; render description + Open Source; Key Signals build; Check Another Story; quiz review + validation; history score + confirm + restore result; friendlier state copy |
| `app.py` | User-facing verification messages (no .env instructions); include signal-group payload (source/language/evidence) for UI |
| `detector/detector.py` | Add warning checks: missing date, urgency, emotional language; expose grouped signals helper |
| `services/verification.py` | User-safe error copy; keep statuses; ensure description always present |
| `README.md` | Sync docs with final UX (About/Methodology content lives here too) |

## 4. Files to Create

**None required.** (Brief §20 — no new folders. Optional later: nothing.)
Tests will be executed as inline scripts/commands, not a new `tests/` folder.

## 5. Files to Preserve (do not rewrite)

- `detector/preprocessing.py` — working clean_text/first_line
- `detector/model.pkl`, `data/dataset.csv`, `scripts/generate_dataset.py` — ML chain
- `services/verification.py` structure (isolation pattern) — extend, don't replace
- `.env`, `.env.example`, `.gitignore`, `requirements.txt`
- Verdict logic + conservative downgrade in `detector.py`/`app.py`
- Editorial visual identity tokens (palette, type scale, nav numbering)

---

## 6. API Integration Plan

```
User input → Flask /api/analyze
              ├─ ML signal        (existing)
              ├─ warning signs    (existing + date/urgency/emotional)
              └─ services/verification.py → FreeNewsAPI.ai
                     ├─ ok            → sources[] {title, source, description, url, publishedAt}
                     ├─ no_results    → "No matching verification sources were found."
                     ├─ not_configured→ "External verification is not enabled…
                     │                   Language-pattern analysis is still available."
                     └─ error/timeout → "Verification sources are temporarily unavailable.
                                         The language-pattern analysis is still available."
Frontend renders sources with description, domain, date, [Open Source] → target=_blank rel=noopener
Key stays in .env · never in JS · errors never return stack traces or key material
```

---

## 7. Implementation Phases (after approval)

| Phase | Work | Verify after |
|-------|------|--------------|
| **P1 — Backend signals & copy** | friendly API messages; grouped `signals` payload (source/language/evidence); +3 warning checks | curl: analyze ok/400/no-key/error copy; unit-check detectors |
| **P2 — Detector UX** | 4 samples, 3-step loading, empty hint, button states, char count | manual + HTML/ID cross-check |
| **P3 — Result experience** | Key Signals render, sources w/ description + Open Source, Check Another Story, exact state copy | curl→render DOM assertions |
| **P4 — Hero + typography + footer** | sans body font, hero disclaimer/How it works, de-tech footer + About/Methodology/Privacy (in-page dialogs) | visual + grep no tech strings in footer/hero |
| **P5 — Learn + Quiz + History** | card 3-part + Learn more; quiz review + validation; history score chip, confirm clear, restore result | scripted JS checks + manual |
| **P6 — Responsive, a11y, states, cleanup** | focus states, labels, breakpoints, console-error sweep, README sync | full checklist (§8) |

After **each phase:** run tests, report changed files + remaining issues. Never claim untested.

## 8. Testing Plan

**Backend (scripted):**
- `GET /` `/static/...` → 200 · `GET /api/health` → model ready
- `POST /api/analyze`: valid text 200 w/ verdict+signals+sources; `<20` chars → 400; >8000 → 400; HTML/script payload → reflected only as plain text
- Verification: no-key copy is user-friendly; (with key, if provided) ok/no_results paths
- Grep: no API key in HTML/JS response; `.env` in `.gitignore`

**Frontend (DOM/scripted + manual):**
- Detector → loading 3-step → result renders all 7 blocks
- Samples ×4 fill textarea; Clear resets; empty analyze → inline message
- Quiz: full run, validation message, Review Results, Retry
- History: save → score chip → click restores result → Clear asks confirm
- Nav: smooth scroll + active state; mobile toggle
- No console errors; no broken href/src (ID cross-check script)
- Responsive: 1440 / 1024 / 768 / 390 px spot checks
- Footer/hero: zero tech-stack strings; About/Methodology/Privacy reachable

## 9. Risks & Limitations

1. **FreeNewsAPI.ai keyless service** — works out of the box without requiring an API key. If the external service is ever down or unreachable, the app degrades gracefully with user-friendly messages.
2. **Model accuracy 1.0 is synthetic-data artifact** — honest limitation; UI already avoids confidence claims (keep it that way).
3. **No browser-automation tool here** — UI verified via DOM assertions, curl, and code review; final visual pass needs your eyes on the live preview.
4. **"Restore full result from history"** needs result JSON stored (larger localStorage) — cap fields, store compact payload (≤15 × ~2–3KB, safe).
5. **In-page About/Methodology/Privacy** — no separate pages allowed, so native `<dialog>` or footer expanders; keeps single-page rule.
6. **Font change (sans body)** adds one Google Font request — negligible; system-sans fallback if offline.
7. **Scope creep risk** — brief forbids over-engineering; anything not in §3–§4 will **not** be added.

---

**Approval:** bol do "approve" (ya corrections) — main Phase 1 se shuru karke phase-wise test report dunga.
