/* TruthCheck — single-page frontend logic
   Detector · Results · Quiz · History (localStorage) */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  /* ============================================================ NAV */
  const navToggle = $("#navToggle");
  const navLinks = $(".nav-links");
  navToggle.addEventListener("click", () => {
    const open = navLinks.classList.toggle("open");
    navToggle.setAttribute("aria-expanded", String(open));
  });
  $$(".nav-links a").forEach((a) =>
    a.addEventListener("click", () => {
      navLinks.classList.remove("open");
      navToggle.setAttribute("aria-expanded", "false");
    })
  );

  // Active section highlighting
  const sectionIds = ["detect", "learn", "quiz", "history"];
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          $$(".nav-links a").forEach((a) =>
            a.classList.toggle("active", a.getAttribute("href") === `#${entry.target.id}`)
          );
        }
      });
    },
    { rootMargin: "-40% 0px -55% 0px" }
  );
  sectionIds.forEach((id) => {
    const el = document.getElementById(id);
    if (el) observer.observe(el);
  });

  /* ======================================================== DETECTOR */
  /* ======================================================== DETECTOR */
  const newsInput = $("#newsInput");
  const charCount = $("#charCount");
  const analyzeBtn = $("#analyzeBtn");
  const clearBtn = $("#clearBtn");
  const spinner = $("#spinner");
  const errorBox = $("#errorBox");
  const resultCard = $("#resultCard");

  const modeNewsBtn = $("#modeNewsBtn");
  const modeFraudBtn = $("#modeFraudBtn");
  const detectTitle = $("#detectTitle");
  const detectSubtitle = $("#detectSubtitle");
  const newsSamples = $("#newsSamples");
  const fraudSamples = $("#fraudSamples");

  let currentMode = "news"; // "news" or "fraud"

  const NEWS_EXAMPLES = {
    report:
      "India won the ICC Men's T20 World Cup in 2024 defeating South Africa in the final match in Barbados.",
    suspicious:
      "Government of India is offering free laptops and recharge vouchers to all students who click this WhatsApp link immediately.",
    social:
      "NASA confirmed the James Webb Space Telescope detected chemical signs of possible water and methane on exoplanet K2-18b.",
    claim:
      "ISRO successfully performed the soft landing of Chandrayaan-3 near the south pole of the Moon.",
  };

  const FRAUD_EXAMPLES = {
    kyc: "SBI Alert: Dear customer, your YONO account will be blocked today. Please update your PAN immediately by clicking: http://sbi-kyc-update.xyz",
    upi: "Dear User, You received ₹2,500 cashback reward from PhonePe! Approve collect request and enter UPI PIN here: http://phonepe-reward-claim.online",
    electricity: "Urgent Notice: Your electricity power will be disconnected tonight at 9:30 PM due to unpaid previous month bill. Call Electricity Officer immediately at 9876543210.",
    job: "Part-time Work From Home! Earn ₹3,000 daily by liking YouTube videos. Contact our manager on Telegram @work_hr_india now.",
    safe: "Your A/C XX4589 is credited by ₹15,000 on 03-Oct-26 via UPI Ref 427819283741. Available balance ₹42,500. - HDFC Bank",
  };

  function setMode(mode) {
    currentMode = mode;
    if (mode === "news") {
      if (modeNewsBtn) modeNewsBtn.classList.add("active");
      if (modeFraudBtn) modeFraudBtn.classList.remove("active");
      if (detectTitle) detectTitle.textContent = "Real-world Fact Checker";
      if (detectSubtitle)
        detectSubtitle.textContent =
          "News detector & fact verifier — paste any news headline, tweet, viral post, or fact claim…";
      newsInput.placeholder =
        "Paste any real-world news, headline, claim or viral fact here...";
      analyzeBtn.textContent = "Verify Facts ★";
      if (newsSamples) newsSamples.classList.remove("hidden");
      if (fraudSamples) fraudSamples.classList.add("hidden");
    } else {
      if (modeFraudBtn) modeFraudBtn.classList.add("active");
      if (modeNewsBtn) modeNewsBtn.classList.remove("active");
      if (detectTitle) detectTitle.textContent = "Message & Fraud Safety";
      if (detectSubtitle)
        detectSubtitle.textContent =
          "Scam & phishing detector — paste any suspicious SMS, WhatsApp message, email, UPI alert, or link…";
      newsInput.placeholder =
        "Paste any suspicious SMS, WhatsApp message, email, UPI alert, or link here...";
      analyzeBtn.textContent = "Check Message Safety ★";
      if (newsSamples) newsSamples.classList.add("hidden");
      if (fraudSamples) fraudSamples.classList.remove("hidden");
    }
    resultCard.classList.add("hidden");
    errorBox.classList.add("hidden");
  }

  if (modeNewsBtn) modeNewsBtn.addEventListener("click", () => setMode("news"));
  if (modeFraudBtn) modeFraudBtn.addEventListener("click", () => setMode("fraud"));

  newsInput.addEventListener("input", () => {
    charCount.textContent = `${newsInput.value.length} / 8000`;
  });

  clearBtn.addEventListener("click", () => {
    newsInput.value = "";
    charCount.textContent = "0 / 8000";
    resultCard.classList.add("hidden");
    errorBox.classList.add("hidden");
    newsInput.focus();
  });

  $$("[data-example]").forEach((btn) =>
    btn.addEventListener("click", () => {
      newsInput.value = NEWS_EXAMPLES[btn.dataset.example] || "";
      newsInput.dispatchEvent(new Event("input"));
      errorBox.classList.add("hidden");
      newsInput.focus();
    })
  );

  $$("[data-fraud-example]").forEach((btn) =>
    btn.addEventListener("click", () => {
      newsInput.value = FRAUD_EXAMPLES[btn.dataset.fraudExample] || "";
      newsInput.dispatchEvent(new Event("input"));
      errorBox.classList.add("hidden");
      newsInput.focus();
    })
  );

  // Check Another Story — scroll back, keep text for editing, focus input
  $("#checkAnotherBtn").addEventListener("click", () => {
    $("#detect").scrollIntoView({ behavior: "smooth", block: "start" });
    newsInput.focus({ preventScroll: true });
    newsInput.select();
  });

  let analyzing = false;

  analyzeBtn.addEventListener("click", async () => {
    if (analyzing) return;
    const text = newsInput.value.trim();
    errorBox.classList.add("hidden");

    if (text.length === 0) {
      errorBox.textContent = currentMode === "fraud"
        ? "Paste a message, SMS, or email to begin."
        : "Paste a headline or article to begin.";
      errorBox.classList.remove("hidden");
      newsInput.focus();
      return;
    }
    const minChars = currentMode === "fraud" ? 10 : 20;
    if (text.length < minChars) {
      errorBox.textContent = `Please enter at least ${minChars} characters.`;
      errorBox.classList.remove("hidden");
      newsInput.focus();
      return;
    }

    analyzing = true;
    analyzeBtn.disabled = true;
    analyzeBtn.classList.add("is-loading");
    analyzeBtn.textContent = "Analyzing…";
    spinner.classList.remove("hidden");
    resultCard.classList.add("hidden");

    const endpoint = currentMode === "fraud" ? "/api/analyze-fraud" : "/api/analyze";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || "Something went wrong. Please try again.");
      }
      renderResult(data);
      saveHistory(text, data);
      resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (err) {
      errorBox.textContent =
        err.message || "Could not reach the server. Please try again shortly.";
      errorBox.classList.remove("hidden");
    } finally {
      analyzing = false;
      analyzeBtn.disabled = false;
      analyzeBtn.classList.remove("is-loading");
      analyzeBtn.textContent = currentMode === "fraud" ? "Check Message Safety ★" : "Verify Facts ★";
      spinner.classList.add("hidden");
    }
  });

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // View Sources toggle handler
  const viewSourcesBtn = $("#viewSourcesBtn");
  const sourcesDrawer = $("#sourcesDrawer");
  const viewSourcesText = $("#viewSourcesText");
  const sourcesToggleIcon = $("#sourcesToggleIcon");

  if (viewSourcesBtn && sourcesDrawer) {
    viewSourcesBtn.addEventListener("click", () => {
      const isHidden = sourcesDrawer.classList.contains("hidden");
      if (isHidden) {
        sourcesDrawer.classList.remove("hidden");
        if (viewSourcesText) viewSourcesText.textContent = "Hide Sources";
        if (sourcesToggleIcon) sourcesToggleIcon.textContent = "▲";
      } else {
        sourcesDrawer.classList.add("hidden");
        const count = window._currentSourcesCount || 0;
        if (viewSourcesText) viewSourcesText.textContent = count ? `View Sources (${count})` : "View Sources";
        if (sourcesToggleIcon) sourcesToggleIcon.textContent = "▼";
      }
    });
  }

  function renderResult(data) {
    const isFraud = data.mode === "fraud";
    const v = data.verdict || { id: "unknown", label: "ANALYZED", emoji: "✦", tone: "ok" };
    const verdictBox = $("#resultVerdict");
    verdictBox.className = `result-verdict tone-${v.tone}`;
    resultCard.className = `result tone-${v.tone}`;

    // Exact emoji map based on contract tone
    const emojiMap = {
      ok: "🟢",
      bad: "🔴",
      warn: "🟡",
    };
    $("#verdictEmoji").textContent = v.emoji || emojiMap[v.tone] || "✦";
    $("#verdictLabel").textContent = v.label || "VERDICT";

    // Kicker & Score Pill
    const kickerEl = $("#resultKickerText");
    if (kickerEl) {
      kickerEl.textContent = isFraud ? "MESSAGE SAFETY ✎" : "ANALYSIS RESULT ✎";
    }

    const confidencePill = $("#confidencePill");
    if (confidencePill) {
      if (isFraud && Number.isFinite(data.risk_score)) {
        confidencePill.textContent = `Risk Score: ${data.risk_score}`;
      } else {
        const score = Number.isFinite(data.confidence)
          ? data.confidence
          : Number.isFinite(data.credibility_score)
          ? data.credibility_score
          : 50;
        confidencePill.textContent = `Confidence: ${score}%`;
      }
    }

    // Status Badge (e.g. UNVERIFIED, VERIFIED FRAUD)
    const statusBadge = $("#statusBadge");
    const statusBadgeText = $("#statusBadgeText");
    if (statusBadge && statusBadgeText) {
      if (isFraud && data.verification_status) {
        statusBadgeText.textContent = data.verification_status.replace(/_/g, " ");
        statusBadge.classList.remove("hidden");
      } else {
        statusBadge.classList.add("hidden");
      }
    }

    // WHY Section (2-3 short sentences)
    $("#resultSummary").textContent = data.summary || "Analysis complete.";

    // Signals Section (Fraud mode)
    const signalsBlock = $("#signalsBlock");
    const signalsList = $("#signalsList");
    if (signalsBlock && signalsList) {
      const signals = data.signals || [];
      if (isFraud && signals.length > 0) {
        signalsList.innerHTML = "";
        signals.forEach((sig) => {
          const li = document.createElement("li");
          li.textContent = typeof sig === "string" ? sig : `${sig.label || "Signal"}: ${sig.detail || ""}`;
          signalsList.appendChild(li);
        });
        signalsBlock.classList.remove("hidden");
      } else {
        signalsBlock.classList.add("hidden");
      }
    }

    // Recommendation Section (Fraud mode)
    const recBlock = $("#recommendationBlock");
    const recBody = $("#recommendationBody");
    if (recBlock && recBody) {
      if (isFraud && data.recommendation) {
        recBody.textContent = data.recommendation;
        recBlock.classList.remove("hidden");
      } else {
        recBlock.classList.add("hidden");
      }
    }

    // EVIDENCE Section Heading
    const evHeading = $("#evidenceHeading");
    if (evHeading) {
      evHeading.textContent = isFraud ? "EVIDENCE & ADVISORIES" : "EVIDENCE";
    }

    // Render AI Badge
    const aiBadge = $("#aiBadge");
    if (aiBadge) {
      const isAi = data.ai_info?.is_ai_verified;
      const model = data.ai_info?.model || (isFraud ? "TruthCheck Threat Engine" : "Qwen 3.8 27B");
      if (isFraud) {
        aiBadge.innerHTML = `<span>🛡️ <strong>${escapeHtml(model)}</strong></span> · Threat Intelligence`;
      } else {
        aiBadge.innerHTML = isAi
          ? `<span>🤖 Verified by <strong>${escapeHtml(model)}</strong></span> · Live Web Search`
          : `<span>🔍 Real-Time Web Evidence Search</span> · Live Sources`;
      }
    }

    // Render API Notice if key is missing
    const apiNotice = $("#apiNotice");
    if (apiNotice) {
      if (data.ai_info && !data.ai_info.is_configured) {
        apiNotice.classList.remove("hidden");
      } else {
        apiNotice.classList.add("hidden");
      }
    }

    // EVIDENCE Section (Bullet points)
    const evidenceList = $("#evidenceList");
    if (evidenceList) {
      evidenceList.innerHTML = "";
      let points = data.key_points || [];
      if (!points.length && data.sources && data.sources.length) {
        points = data.sources.slice(0, 3).map((s) => `${s.source || "Source"} — ${s.title || "Report"}`);
      }
      points.forEach((pt) => {
        const li = document.createElement("li");
        li.textContent = pt.replace(/^[\s•*-]+/, "");
        evidenceList.appendChild(li);
      });
    }

    // Render Live Sources in Collapsible Drawer
    const sourcesGrid = $("#sourcesGrid");
    const sources = data.sources || [];
    window._currentSourcesCount = sources.length;
    if (viewSourcesText) {
      viewSourcesText.textContent = sources.length > 0 ? `View Sources (${sources.length})` : "View Sources";
    }
    if (sourcesToggleIcon) sourcesToggleIcon.textContent = "▼";
    if (sourcesDrawer) sourcesDrawer.classList.add("hidden");

    if (sourcesGrid) {
      sourcesGrid.innerHTML = "";
      sources.forEach((src) => {
        const card = document.createElement("a");
        card.className = "source-card";
        card.href = src.url;
        card.target = "_blank";
        card.rel = "noopener noreferrer";

        const dateStr = src.date ? src.date.split("T")[0] : "Verified Source";
        card.innerHTML = `
          <span class="source-card-badge">${escapeHtml(src.source || "Source")}</span>
          <h4 class="source-card-title">${escapeHtml(src.title || src.url)}</h4>
          <p class="source-card-snippet">${escapeHtml(src.snippet || "Click to view original reporting and full context.")}</p>
          <div class="source-card-footer">
            <span>${escapeHtml(dateStr)}</span>
            <span class="source-card-link-text">Read Source ↗</span>
          </div>
        `;
        sourcesGrid.appendChild(card);
      });
    }

    resultCard.classList.remove("hidden");
  }


  /* ========================================================== HISTORY */
  const HISTORY_KEY = "truthcheck_history";
  const HISTORY_MAX = 15;

  function loadHistory() {
    try {
      const raw = localStorage.getItem(HISTORY_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch {
      return [];
    }
  }

  function saveHistory(text, data) {
    // Compact but complete payload so a click can restore the full result.
    const entry = {
      text: text.slice(0, 500),
      verdict: data.verdict,
      score: data.credibility_score,
      signals: (data.key_points || []).length,
      time: Date.now(),
      result: {
        verdict: data.verdict,
        credibility_score: data.credibility_score,
        summary: data.summary || "",
        key_points: data.key_points || [],
        sources: (data.sources || []).slice(0, 6),
        ai_info: data.ai_info || {},
        tips: data.tips || [],
      },
    };
    let list;
    try {
      list = [entry, ...loadHistory()].slice(0, HISTORY_MAX);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
    } catch {
      try {
        list.forEach((e) => { if (e.result) delete e.result; });
        localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
      } catch { /* ignore */ }
    }
    renderHistory();
  }


  function formatTime(ts) {
    const d = new Date(ts);
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    if (sameDay) return `Today · ${time}`;
    if (d.toDateString() === yesterday.toDateString()) return `Yesterday`;
    return `${d.toLocaleDateString([], { month: "short", day: "numeric" })} · ${time}`;
  }

  function restoreEntry(entry) {
    newsInput.value = entry.text || "";
    newsInput.dispatchEvent(new Event("input"));
    if (entry.result && entry.result.verdict) {
      renderResult(entry.result);
      resultCard.classList.remove("hidden");
      resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } else {
      $("#detect").scrollIntoView({ behavior: "smooth" });
    }
  }

  function renderHistory() {
    const list = loadHistory();
    const ul = $("#historyList");
    const empty = $("#historyEmpty");
    ul.innerHTML = "";
    if (list.length === 0) {
      empty.classList.remove("hidden");
      ul.classList.add("hidden");
      return;
    }
    empty.classList.add("hidden");
    ul.classList.remove("hidden");

    list.forEach((entry) => {
      const li = document.createElement("li");
      li.className = "history-item";
      li.tabIndex = 0;
      li.setAttribute("role", "button");
      li.setAttribute(
        "aria-label",
        `View result: ${entry.verdict?.label || "unknown"} — ${(entry.text || "").slice(0, 60)}`
      );

      const dot = document.createElement("span");
      const tone = entry.verdict?.tone || "warn";
      dot.className = `history-dot ${tone}`;
      dot.setAttribute("aria-hidden", "true");

      const main = document.createElement("div");
      main.className = "history-main";
      const top = document.createElement("div");
      top.className = "history-top";
      const verdict = document.createElement("span");
      verdict.className = `history-verdict ${tone}`;
      verdict.textContent = entry.verdict?.label || "Unknown";
      // score / indicator chip
      const chip = document.createElement("span");
      chip.className = "history-chip";
      const bits = [];
      if (typeof entry.score === "number") bits.push(`${entry.score}% credibility`);
      if (typeof entry.signals === "number") bits.push(`${entry.signals} signal${entry.signals === 1 ? "" : "s"}`);
      chip.textContent = bits.join(" · ") || "—";
      top.append(verdict, chip);
      const snippet = document.createElement("div");
      snippet.className = "history-text";
      snippet.textContent = entry.text || "";
      main.append(top, snippet);

      const time = document.createElement("span");
      time.className = "history-time";
      time.textContent = formatTime(entry.time);

      li.append(dot, main, time);
      const reload = () => restoreEntry(entry);
      li.addEventListener("click", reload);
      li.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); reload(); }
      });
      ul.appendChild(li);
    });
  }

  $("#clearHistoryBtn").addEventListener("click", () => {
    const list = loadHistory();
    if (list.length === 0) return;
    const ok = window.confirm("Clear all saved checks? This cannot be undone.");
    if (!ok) return;
    localStorage.removeItem(HISTORY_KEY);
    renderHistory();
  });

  /* ============================================================= LEARN */
  $$(".link-more").forEach((btn) => {
    btn.addEventListener("click", () => {
      const card = btn.closest(".polaroid");
      const more = card.querySelector(".card-more");
      const open = more.classList.toggle("hidden") === false;
      btn.setAttribute("aria-expanded", String(open));
      btn.textContent = open ? "Hide Case Study ✕" : "Inspect Case Study ➔";
    });
  });

  /* ============================================================ QUIZ */
  const QUESTIONS = [
    {
      q: "What should you check first when you see suspicious news?",
      options: ["Source", "Font", "Emojis", "Comments"],
      answer: 0,
    },
    {
      q: "A headline says 'You won't believe…'. What technique is this?",
      options: ["Citation", "Clickbait", "Summarising", "Editorial review"],
      answer: 1,
    },
    {
      q: "Why is the publication date of an article important?",
      options: [
        "It affects the page layout",
        "Old stories can be reshared out of context",
        "Longer articles rank higher",
        "Dates prove the headline is accurate",
      ],
      answer: 1,
    },
    {
      q: "What is the strongest sign that a claim has supporting evidence?",
      options: [
        "It uses ALL CAPS",
        "It has many exclamation marks",
        "It links to primary data or named experts",
        "A celebrity shared it",
      ],
      answer: 2,
    },
    {
      q: "Before sharing a shocking story, you should:",
      options: [
        "Share it immediately so friends can check",
        "Compare it with other reliable sources",
        "Add your own opinion in the caption",
        "Delete the original link",
      ],
      answer: 1,
    },
    {
      q: "What does 'cross-checking' mean in media literacy?",
      options: [
        "Reading the story twice",
        "Checking comments for facts",
        "Verifying the same claim across multiple reliable outlets",
        "Comparing font styles between sites",
      ],
      answer: 2,
    },
    {
      q: "Which is a red flag that an article may be misleading?",
      options: [
        "Named author with citations",
        "Emotional language with no evidence",
        "A correction note at the bottom",
        "Quotes from officials",
      ],
      answer: 1,
    },
    {
      q: "Why should you read beyond the headline?",
      options: [
        "Headlines are often shortened and can distort the story",
        "Longer reads are always correct",
        "It increases the website's views",
        "Headlines never change meaning",
      ],
      answer: 0,
    },
    {
      q: "Who is most responsible for verifying information before you repost it?",
      options: ["The group chat", "The platform algorithm", "You, the sharer", "The first commenter"],
      answer: 2,
    },
    {
      q: "An article gives no author, no date and no sources. Best next step?",
      options: [
        "Trust it if it looks professional",
        "Treat it cautiously and verify elsewhere",
        "Share it with a warning emoji",
        "Assume it is satire",
      ],
      answer: 1,
    },
  ];

  let quizIndex = 0;
  let quizAnswers = new Array(QUESTIONS.length).fill(null);

  const quizQView = $("#quizQuestionView");
  const quizRView = $("#quizResultView");
  const quizReviewView = $("#quizReviewView");
  const quizPrevBtn = $("#quizPrevBtn");
  const quizNextBtn = $("#quizNextBtn");
  const quizMsg = $("#quizMsg");

  function renderQuestion() {
    const item = QUESTIONS[quizIndex];
    $("#quizProgress").textContent = `Question ${quizIndex + 1} / ${QUESTIONS.length}`;
    $("#quizBarFill").style.width = `${((quizIndex + 1) / QUESTIONS.length) * 100}%`;
    $("#quizQuestionText").textContent = item.q;
    quizMsg.classList.add("hidden");

    const box = $("#quizOptions");
    box.innerHTML = "";
    item.options.forEach((opt, i) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "quiz-option" + (quizAnswers[quizIndex] === i ? " selected" : "");
      btn.setAttribute("role", "radio");
      btn.setAttribute("aria-checked", String(quizAnswers[quizIndex] === i));
      const radio = document.createElement("span");
      radio.className = "radio";
      radio.setAttribute("aria-hidden", "true");
      radio.textContent = String.fromCharCode(65 + i); // A / B / C / D
      btn.append(radio, document.createTextNode(opt));
      btn.addEventListener("click", () => {
        quizAnswers[quizIndex] = i;
        quizMsg.classList.add("hidden");
        renderQuestion();
      });
      box.appendChild(btn);
    });

    quizPrevBtn.disabled = quizIndex === 0;
    // Next stays enabled so an unanswered click can show the validation message.
    quizNextBtn.disabled = false;
    quizNextBtn.textContent = quizIndex === QUESTIONS.length - 1 ? "Submit" : "Next";
  }

  quizPrevBtn.addEventListener("click", () => {
    if (quizIndex > 0) { quizIndex -= 1; renderQuestion(); }
  });

  quizNextBtn.addEventListener("click", () => {
    if (quizAnswers[quizIndex] === null) {
      quizMsg.classList.remove("hidden");
      return;
    }
    quizMsg.classList.add("hidden");
    if (quizIndex < QUESTIONS.length - 1) {
      quizIndex += 1;
      renderQuestion();
    } else {
      submitQuiz();
    }
  });

  function computeScore() {
    return QUESTIONS.reduce((acc, q, i) => acc + (quizAnswers[i] === q.answer ? 1 : 0), 0);
  }

  function submitQuiz() {
    const score = computeScore();
    const total = QUESTIONS.length;
    const pct = Math.round((score / total) * 100);

    let label, msg;
    const short = `You answered ${score} of ${total} correctly.`;
    if (pct >= 90) {
      label = "Media Literacy: Excellent";
      msg = `${short} Sharp instincts.`;
    } else if (pct >= 70) {
      label = "Media Literacy: Good";
      msg = `${short} Solid foundation.`;
    } else if (pct >= 50) {
      label = "Media Literacy: Developing";
      msg = `${short} Review the six checks, then retry.`;
    } else {
      label = "Media Literacy: Needs Practice";
      msg = `${short} Try the Learn section first.`;
    }

    quizQView.classList.add("hidden");
    quizReviewView.classList.add("hidden");
    quizRView.classList.remove("hidden");
    $("#scoreFraction").textContent = `${score} / ${total}`;
    $("#scorePercent").textContent = `${pct}%`;
    $("#scoreRing").style.setProperty("--pct", String(pct));
    $("#scoreLabel").textContent = label;
    $("#scoreMessage").textContent = msg;
  }

  function renderReview() {
    const list = $("#reviewList");
    list.innerHTML = "";
    QUESTIONS.forEach((q, i) => {
      const li = document.createElement("li");
      const correct = quizAnswers[i] === q.answer;
      li.className = `review-item ${correct ? "is-correct" : "is-wrong"}`;

      const head = document.createElement("div");
      head.className = "review-head";
      const num = document.createElement("span");
      num.className = "review-num";
      num.textContent = String(i + 1).padStart(2, "0");
      const mark = document.createElement("span");
      mark.className = "review-mark";
      mark.textContent = correct ? "Correct" : "Incorrect";
      mark.setAttribute("aria-hidden", "true");
      head.append(num, mark);

      const qEl = document.createElement("p");
      qEl.className = "review-q";
      qEl.textContent = q.q;

      const ans = document.createElement("p");
      ans.className = "review-ans";
      const yours = quizAnswers[i] === null ? "— not answered" : q.options[quizAnswers[i]];
      ans.textContent = `Your answer: ${yours} · Correct: ${q.options[q.answer]}`;

      li.append(head, qEl, ans);
      list.appendChild(li);
    });
  }

  $("#quizReviewBtn").addEventListener("click", () => {
    renderReview();
    quizRView.classList.add("hidden");
    quizReviewView.classList.remove("hidden");
  });
  $("#quizBackBtn").addEventListener("click", () => {
    quizReviewView.classList.add("hidden");
    quizRView.classList.remove("hidden");
  });

  function retryQuiz() {
    quizIndex = 0;
    quizAnswers = new Array(QUESTIONS.length).fill(null);
    quizRView.classList.add("hidden");
    quizReviewView.classList.add("hidden");
    quizQView.classList.remove("hidden");
    renderQuestion();
  }
  $("#quizRetryBtn").addEventListener("click", retryQuiz);
  $("#quizRetryBtn2").addEventListener("click", retryQuiz);

  /* ====================================================== FOOTER DLG */
  $$("[data-dialog]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dlg = document.getElementById(btn.dataset.dialog);
      if (dlg && typeof dlg.showModal === "function") dlg.showModal();
    });
  });
  $$(".dlg").forEach((dlg) => {
    dlg.addEventListener("click", (e) => {
      if (e.target.hasAttribute("data-close") || e.target === dlg) dlg.close();
    });
  });

  /* ============================================= DATELINE + REVEAL */
  const datelineEl = document.getElementById("dateline");
  if (datelineEl) {
    datelineEl.textContent = new Date().toLocaleDateString("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }

  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const revealEls = $$(".reveal");
  if (prefersReduced || !("IntersectionObserver" in window)) {
    revealEls.forEach((el) => el.classList.add("is-visible"));
  } else {
    const revealObserver = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            obs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach((el) => revealObserver.observe(el));
  }

  /* =========================================================== INIT */
  renderQuestion();
  renderHistory();
})();
