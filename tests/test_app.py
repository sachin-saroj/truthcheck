"""Integration tests for TruthCheck Flask endpoints and ML model stability."""
import json
import unittest
from unittest.mock import MagicMock, patch

from app import app
from detector.detector import NewsDetector


class TestFlaskEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["model"], "ready")
        self.assertIn("metrics", data)
        self.assertEqual(data["verification"], "configured")

    def test_index_page(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("TruthCheck", html)
        self.assertIn("News detector", html)

    def test_analyze_empty_input(self):
        resp = self.client.post("/api/analyze", json={"text": ""})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)

    def test_analyze_short_input(self):
        resp = self.client.post("/api/analyze", json={"text": "Short headline"})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("at least 20 characters", data["error"])

    def test_analyze_long_input(self):
        resp = self.client.post("/api/analyze", json={"text": "A" * 8001})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("under 8,000 characters", data["error"])

    @patch("app.fact_checker.analyze")
    def test_analyze_unicode_input(self, mock_analyze):
        mock_analyze.return_value = {
            "verdict": {"id": "likely_true", "label": "Likely True", "emoji": "🟢", "tone": "ok"},
            "credibility_score": 85,
            "summary": "Valid economic announcement reported.",
            "key_points": ["Reported by official sources"],
            "sources": [{"title": "Source 1", "url": "https://example.com", "source": "News"}],
            "has_sources": True,
            "ai_info": {"model": "qwen/qwen3.8-27b:free", "is_ai_verified": True, "is_configured": True},
            "tips": ["Verify source"],
            "elapsed_ms": 100,
        }
        text = "L’ancien président a déclaré lundi : « La nouvelle mesure économique est validée. »"
        resp = self.client.post("/api/analyze", json={"text": text})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("verdict", data)
        self.assertIn("credibility_score", data)
        self.assertEqual(data["verdict"]["id"], "likely_true")

    @patch("app.fact_checker.analyze")
    def test_analyze_url_input(self, mock_analyze):
        mock_analyze.return_value = {
            "verdict": {"id": "likely_true", "label": "Likely True", "emoji": "🟢", "tone": "ok"},
            "credibility_score": 90,
            "summary": "Verified climate report.",
            "key_points": ["Reuters coverage"],
            "sources": [{"title": "Reuters", "url": "https://reuters.com", "source": "Reuters"}],
            "has_sources": True,
            "ai_info": {"model": "qwen/qwen3.8-27b:free", "is_ai_verified": True, "is_configured": True},
            "tips": ["Verify source"],
            "elapsed_ms": 100,
        }
        text = "According to https://reuters.com/news officials have reported new climate metrics today."
        resp = self.client.post("/api/analyze", json={"text": text})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("verdict", data)

    @patch("app.fact_checker.analyze")
    def test_analyze_xss_input(self, mock_analyze):
        mock_analyze.return_value = {
            "verdict": {"id": "needs_verification", "label": "Needs Verification", "emoji": "🟡", "tone": "warn"},
            "credibility_score": 50,
            "summary": "Educational grant claims require official verification.",
            "key_points": [],
            "sources": [],
            "has_sources": False,
            "ai_info": {"model": "qwen/qwen3.8-27b:free", "is_ai_verified": False, "is_configured": False},
            "tips": ["Verify source"],
            "elapsed_ms": 100,
        }
        text = '<script>alert("xss")</script> <img src=x onerror=alert(1)> Officials confirmed new educational grants.'
        resp = self.client.post("/api/analyze", json={"text": text})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("verdict", data)

    def test_verdict_threshold_logic(self):
        """Verify exact public thresholds: <50 likely_fake, ==50 needs_verification, >50 likely_true."""
        self.assertEqual(NewsDetector.calculate_verdict(49), "likely_fake")
        self.assertEqual(NewsDetector.calculate_verdict(0), "likely_fake")
        self.assertEqual(NewsDetector.calculate_verdict(50), "needs_verification")
        self.assertEqual(NewsDetector.calculate_verdict(51), "likely_true")
        self.assertEqual(NewsDetector.calculate_verdict(100), "likely_true")

    @patch("app.fact_checker.analyze")
    def test_demo_sample_buttons_coverage(self, mock_analyze):
        """Verify endpoint correctly handles Likely True, Likely Fake, and Needs Verification."""
        mock_analyze.side_effect = [
            {
                "verdict": {"id": "likely_true", "label": "Likely True", "emoji": "🟢", "tone": "ok"},
                "credibility_score": 85,
                "summary": "Confirmed reporting.",
                "key_points": ["Verified fact"],
                "sources": [{"title": "BBC", "url": "https://bbc.com"}],
                "has_sources": True,
                "ai_info": {"model": "qwen/qwen3.8-27b:free", "is_ai_verified": True, "is_configured": True},
                "tips": [],
                "elapsed_ms": 100,
            },
            {
                "verdict": {"id": "likely_fake", "label": "Likely Fake", "emoji": "🔴", "tone": "bad"},
                "credibility_score": 20,
                "summary": "Debunked scam.",
                "key_points": ["Contradicts official records"],
                "sources": [],
                "has_sources": False,
                "ai_info": {"model": "qwen/qwen3.8-27b:free", "is_ai_verified": True, "is_configured": True},
                "tips": [],
                "elapsed_ms": 100,
            },
            {
                "verdict": {"id": "needs_verification", "label": "Needs Verification", "emoji": "🟡", "tone": "warn"},
                "credibility_score": 50,
                "summary": "Insufficient evidence.",
                "key_points": ["No clear source"],
                "sources": [],
                "has_sources": False,
                "ai_info": {"model": "qwen/qwen3.8-27b:free", "is_ai_verified": False, "is_configured": False},
                "tips": [],
                "elapsed_ms": 100,
            },
        ]

        r_rep = self.client.post("/api/analyze", json={"text": "India won the T20 World Cup in 2024"}).get_json()
        r_sus = self.client.post("/api/analyze", json={"text": "Free laptop scheme on whatsapp link"}).get_json()
        r_soc = self.client.post("/api/analyze", json={"text": "Unverified rumor about treatment"}).get_json()

        self.assertEqual(r_rep["verdict"]["id"], "likely_true")
        self.assertGreater(r_rep["credibility_score"], 50)

        self.assertEqual(r_sus["verdict"]["id"], "likely_fake")
        self.assertLess(r_sus["credibility_score"], 50)

        self.assertEqual(r_soc["verdict"]["id"], "needs_verification")
        self.assertEqual(r_soc["credibility_score"], 50)


if __name__ == "__main__":
    unittest.main()

