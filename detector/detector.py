"""TruthCheck detector: TF-IDF + Logistic Regression classifier plus rule-based
warning-sign analysis and a combined three-tier verdict.

The model output is a *language-pattern* score — not proof of factual truth.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .preprocessing import clean_text

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = BASE_DIR / "data" / "dataset.csv"
DEFAULT_MODEL = Path(__file__).resolve().parent / "model.pkl"

# Three-tier verdicts used across the product.
VERDICTS = {
    "likely_true": {"id": "likely_true", "label": "Likely True", "emoji": "🟢", "tone": "ok"},
    "needs_verification": {"id": "needs_verification", "label": "Needs Verification", "emoji": "🟡", "tone": "warn"},
    "likely_fake": {"id": "likely_fake", "label": "Likely Fake", "emoji": "🔴", "tone": "bad"},
}

SENTIMENT_WORDS = [
    "shocking", "shock", "unbelievable", "insane", "horrific", "outrageous",
    "bombshell", "explosive", "jaw-dropping", "terrifying", "viral", "urgent",
    "breaking", "scandal", "exposed", "miracle", "catastrophic",
]
ABSOLUTE_WORDS = [
    "always", "never", "every time", "no one", "everyone", "100%", "completely",
    "guaranteed", "undeniable", "proven", "definitely", "impossible", "all of them",
]
CLICKBAIT_PATTERNS = [
    r"you\s+(won'?t|will\s+not)\s+believe",
    r"what\s+happens?\s+next",
    r"share\s+(this|before|with)",
    r"before\s+it\s+(is\s+)?(deleted|removed|banned)",
    r"doctors?\s+(don'?t|do\s+not)\s+want",
    r"the\s+truth\s+(they|the\s+media)",
    r"one\s+trick",
    r"do\s+not\s+(ignore|miss)",
    r"click\s+here",
    r"wake\s+up",
]
UNSUPPORTED_CLAIM_PATTERNS = [
    r"miracle\s+cure",
    r"cures?\s+\w+\s+overnight",
    r"secret(ly)?\s+(bill|plan|law|meeting)",
    r"they\s+(don'?t|do\s+not)\s+want\s+you",
    r"leaked\s+dossier",
    r"mainstream\s+media\s+(refuses|hides|covers)",
    r"elites?\s+(are\s+)?hiding",
    r"insiders?\s+break",
    r"official\s+story\s+is\s+collapsing",
    r"satellite\s+signals",
    r"read\s+your\s+thoughts",
]
ATTRIBUTION_PATTERNS = [
    r"\baccording\s+to\b", r"\bsaid\b", r"\breported\b", r"\bofficials?\b",
    r"\bstudy\b", r"\breport\b", r"\bpublished\b", r"\bdata\b", r"\bsource\b",
    r"\bresearchers?\b", r"\bconfirmed\b", r"\bbriefed\b",
]
# Emotional language — distinct from sensational hype (fear/anger/outrage hooks).
EMOTIONAL_WORDS = [
    "outraged", "outrage", "furious", "heartbreaking", "devastating", "panic",
    "terrified", "rage", "disgusting", "betrayal", "shameful", "tragic",
    "grief", "anger", "fear",
]
# Sharing-pressure / artificial urgency.
URGENCY_PATTERNS = [
    r"share\s+(this|it|now|before|with\s+everyone)",
    r"forward\s+(this|it|to\s+all|everyone)",
    r"repost\s+(this|it|now)?",
    r"send\s+to\s+(everyone|all|your\s+(friends|family|contacts))",
    r"right\s+now", r"\bhurry\b", r"act\s+now", r"last\s+chance",
    r"before\s+it.?s?\s+too\s+late", r"don.?t\s+wait", r"time.?s?\s+running",
    r"before\s+(it|this)\s+is\s+(deleted|removed)",
]
# Date cues (publish date present?).
DATE_PATTERNS = [
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\b(yesterday|today|tomorrow|last\s+week|this\s+week|this\s+month)\b",
    r"\b(19|20)\d{2}\b",
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\bago\b",
]
SENSATIONAL_RE = re.compile(r"\b(" + "|".join(SENTIMENT_WORDS) + r")\b", re.IGNORECASE)
ABSOLUTE_RE = re.compile(r"\b(" + "|".join(ABSOLUTE_WORDS) + r")\b", re.IGNORECASE)
CLICKBAIT_RE = re.compile("|".join(CLICKBAIT_PATTERNS), re.IGNORECASE)
UNSUPPORTED_RE = re.compile("|".join(UNSUPPORTED_CLAIM_PATTERNS), re.IGNORECASE)
ATTRIBUTION_RE = re.compile("|".join(ATTRIBUTION_PATTERNS), re.IGNORECASE)
EMOTIONAL_RE = re.compile(r"\b(" + "|".join(EMOTIONAL_WORDS) + r")\b", re.IGNORECASE)
URGENCY_RE = re.compile("|".join(URGENCY_PATTERNS), re.IGNORECASE)
DATE_RE = re.compile("|".join(DATE_PATTERNS), re.IGNORECASE)
EXCESS_PUNCT_RE = re.compile(r"!{2,}|\?{2,}|[!?]{1}\s+[!?]")  # !!! or !! or ?!
WORD_RE = re.compile(r"[A-Za-z']+")

# IDs used by the frontend's "language" signal grouping.
LANGUAGE_SIGN_IDS = {
    "sensational", "punctuation", "caps", "absolute",
    "clickbait", "emotional", "urgency",
}


@dataclass
class Prediction:
    label: int                      # 0 = reliable-style, 1 = misleading-style
    probability: float              # P(misleading)
    probabilities: dict[str, float] # both classes
    credibility_score: int = 0
    warning_signs: list[dict[str, str]] = field(default_factory=list)
    verdict_id: str = "needs_verification"
    verdict: dict[str, Any] = field(default_factory=dict)
    summary: str = ""


class NewsDetector:
    """Loads / trains the TF-IDF + Random Forest pipeline and scores text."""

    def __init__(self, model_path: Path = DEFAULT_MODEL, dataset_path: Path = DEFAULT_DATASET):
        self.model_path = Path(model_path)
        self.dataset_path = Path(dataset_path)
        self.pipeline: Pipeline | None = None
        self.metrics: dict[str, float] = {}

    # ------------------------------------------------------------------ train
    def build_pipeline(self) -> Pipeline:
        return Pipeline([
            ("tfidf", TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                min_df=2,
                max_df=0.95,
                sublinear_tf=True,
            )),
            ("clf", LogisticRegression(
                C=1.0,
                max_iter=1000,
                class_weight="balanced",
                random_state=42,
            )),
        ])

    def train(self, export: bool = True) -> dict[str, float]:
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset not found at {self.dataset_path}. "
                "Run `python scripts/generate_dataset.py` first."
            )
        df = pd.read_csv(self.dataset_path)
        if "text" not in df.columns or "label" not in df.columns:
            raise ValueError("dataset.csv must have columns: text,label")
        df = df.dropna(subset=["text", "label"])
        df["cleaned"] = df["text"].astype(str).map(clean_text)
        df = df[df["cleaned"].str.len() > 0]

        X = df["cleaned"]
        y = df["label"].astype(int)

        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        pipeline = self.build_pipeline()
        pipeline.fit(X_tr, y_tr)
        preds = pipeline.predict(X_te)
        self.metrics = {
            "accuracy": float(round(accuracy_score(y_te, preds), 4)),
            "precision": float(round(precision_score(y_te, preds, zero_division=0), 4)),
            "recall": float(round(recall_score(y_te, preds, zero_division=0), 4)),
            "f1": float(round(f1_score(y_te, preds, zero_division=0), 4)),
            "train_rows": int(len(df)),
        }
        self.pipeline = pipeline
        if export:
            self.save()
        return self.metrics

    def save(self) -> None:
        if self.pipeline is None:
            raise RuntimeError("No pipeline to save")
        joblib.dump({"pipeline": self.pipeline, "metrics": self.metrics}, self.model_path)

    def load(self) -> bool:
        if not self.model_path.exists():
            return False
        try:
            bundle = joblib.load(self.model_path)
            self.pipeline = bundle.get("pipeline")
            self.metrics = bundle.get("metrics", {})
            return self.pipeline is not None
        except Exception:
            return False

    def ensure_ready(self) -> dict[str, float]:
        """Load the model if present, otherwise train from the dataset."""
        if not self.load():
            return self.train()
        return self.metrics

    # ---------------------------------------------------------------- predict
    @property
    def is_ready(self) -> bool:
        return self.pipeline is not None

    def predict(self, text: str) -> Prediction:
        if self.pipeline is None:
            raise RuntimeError("Model is not loaded")
        cleaned = clean_text(text)
        proba = self.pipeline.predict_proba([cleaned])[0]
        classes = list(self.pipeline.classes_)
        prob_map = {int(c): float(p) for c, p in zip(classes, proba)}
        p_misleading = prob_map.get(1, 0.0)
        label = 1 if p_misleading >= 0.5 else 0

        signs = self.detect_warning_signs(text)
        credibility_score = self.credibility_score(p_misleading)
        verdict_id = self.calculate_verdict(credibility_score)
        summary = self._summary(verdict_id, credibility_score)

        return Prediction(
            label=label,
            probability=p_misleading,
            probabilities={"reliable_style": prob_map.get(0, 0.0), "misleading_style": p_misleading},
            credibility_score=credibility_score,
            warning_signs=signs,
            verdict_id=verdict_id,
            verdict=VERDICTS[verdict_id],
            summary=summary,
        )

    # ---------------------------------------------------------- warning signs
    def detect_warning_signs(self, text: str) -> list[dict[str, str]]:
        signs: list[dict[str, str]] = []
        raw = text or ""

        sens = SENSATIONAL_RE.findall(raw)
        if sens:
            words = sorted({w.lower() for w in sens})[:5]
            signs.append({
                "id": "sensational",
                "title": "Sensational language",
                "detail": f"Loaded wording (e.g. {', '.join(words)}).",
            })

        if EXCESS_PUNCT_RE.search(raw) or raw.count("!") >= 3 or raw.count("?") >= 3:
            signs.append({
                "id": "punctuation",
                "title": "Excessive punctuation",
                "detail": "Repeated !!! or ??? — clickbait-style.",
            })

        words = WORD_RE.findall(raw)
        long_words = [w for w in words if len(w) >= 4]
        caps_words = [w for w in long_words if w.isupper()]
        letters = [c for c in raw if c.isalpha()]
        caps_ratio = (sum(1 for c in letters if c.isupper()) / len(letters)) if letters else 0
        if len(caps_words) >= 2 or caps_ratio > 0.30:
            signs.append({
                "id": "caps",
                "title": "Heavy ALL-CAPS usage",
                "detail": "Shouting-style emphasis.",
            })

        abs_hits = ABSOLUTE_RE.findall(raw)
        if abs_hits:
            signs.append({
                "id": "absolute",
                "title": "Absolute statements",
                "detail": f"Black-and-white claims (e.g. {', '.join(sorted({h.lower() for h in abs_hits})[:3])}).",
            })

        click = CLICKBAIT_RE.search(raw)
        if click:
            signs.append({
                "id": "clickbait",
                "title": "Clickbait-style wording",
                "detail": "Curiosity/urgency hooks instead of information.",
            })

        unsup = UNSUPPORTED_RE.search(raw)
        if unsup:
            signs.append({
                "id": "unsupported",
                "title": "Unsupported claim pattern",
                "detail": "Extraordinary claim with no evidence.",
            })

        if len(raw.split()) >= 8 and not ATTRIBUTION_RE.search(raw):
            signs.append({
                "id": "attribution",
                "title": "Source unclear",
                "detail": "No 'according to', named source or report.",
            })

        emo = EMOTIONAL_RE.findall(raw)
        if emo:
            words_e = sorted({w.lower() for w in emo})[:5]
            signs.append({
                "id": "emotional",
                "title": "Emotional language",
                "detail": f"Strong-reaction words (e.g. {', '.join(words_e)}).",
            })

        urg = URGENCY_RE.search(raw)
        if urg:
            signs.append({
                "id": "urgency",
                "title": "Urgent sharing language",
                "detail": "Pressure to share or act now.",
            })

        # Missing date: only flag article-length text (short headlines often omit it).
        if len(words) >= 12 and not DATE_RE.search(raw):
            signs.append({
                "id": "date",
                "title": "No publication date",
                "detail": "No date or time reference found.",
            })

        return signs

    # ---------------------------------------------------------- verdict logic
    @staticmethod
    def credibility_score(misleading_probability: float) -> int:
        """Convert the model's misleading-style probability into credibility."""
        return round((1.0 - misleading_probability) * 100)

    @staticmethod
    def calculate_verdict(credibility_score: int) -> str:
        """Apply the single public threshold for the credibility score."""
        if credibility_score < 50:
            return "likely_fake"
        if credibility_score > 50:
            return "likely_true"
        return "needs_verification"

    @staticmethod
    def _summary(verdict_id: str, credibility_score: int) -> str:
        if verdict_id == "likely_true":
            return (
                f"This news shows patterns commonly associated with reliable news "
                f"({credibility_score}% credibility). You can still check the sources before sharing."
            )
        if verdict_id == "needs_verification":
            return (
                "The result is too close to the middle to make a clear classification. "
                "Check the sources before sharing."
            )
        return (
            "This news shows patterns commonly associated with unreliable or misleading news. "
            "Check the sources before sharing."
        )
