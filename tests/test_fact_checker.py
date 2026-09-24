"""Tests for SearchService, OpenRouterService, and FactChecker."""
import unittest
from unittest.mock import MagicMock, patch

from services.fact_checker import FactChecker, VERDICTS
from services.openrouter_service import OpenRouterService
from services.search_service import SearchService, clean_query_text, extract_source_name, is_safe_url


class TestSearchService(unittest.TestCase):
    def test_clean_query_text(self):
        text = "SHOCKING: India won the T20 World Cup yesterday! Click here."
        q = clean_query_text(text)
        self.assertTrue("India" in q or "T20" in q)
        self.assertNotIn("!", q)
        self.assertNotIn(":", q)

    def test_extract_source_name(self):
        self.assertEqual(extract_source_name("https://www.reuters.com/world/india"), "Reuters")
        self.assertEqual(extract_source_name("https://en.wikipedia.org/wiki/ISRO"), "Wikipedia")
        self.assertEqual(extract_source_name("invalid"), "Web Source")

    def test_is_safe_url(self):
        self.assertTrue(is_safe_url("https://bbc.com/news/123"))
        self.assertTrue(is_safe_url("http://example.org"))
        self.assertFalse(is_safe_url("javascript:alert(1)"))
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url(""))


class TestOpenRouterService(unittest.TestCase):
    def test_extract_json_clean(self):
        svc = OpenRouterService(api_key="mock-key")
        raw = '{"verdict_id": "likely_true", "credibility_score": 90, "summary": "Confirmed by all.", "key_points": ["Point 1"]}'
        parsed = svc._extract_json(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["verdict_id"], "likely_true")
        self.assertEqual(parsed["credibility_score"], 90)

    def test_extract_json_markdown_fences(self):
        svc = OpenRouterService(api_key="mock-key")
        raw = '```json\n{"verdict_id": "likely_fake", "credibility_score": 10, "summary": "Debunked hoax.", "key_points": ["Fact 1"]}\n```'
        parsed = svc._extract_json(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["verdict_id"], "likely_fake")

    def test_heuristic_fallback_when_no_key(self):
        svc = OpenRouterService(api_key="")
        evidence = [
            {"title": "Fact check: Viral claim is completely false", "snippet": "PIB debunked this fake scheme", "source": "PIB"}
        ]
        res = svc.verify_claim("Free laptop scheme", evidence)
        self.assertEqual(res["verdict_id"], "likely_fake")
        self.assertFalse(res["ai_verified"])
        self.assertIn("debunked", res["summary"].lower() + " ".join(res["key_points"]).lower())

    @patch("services.openrouter_service.requests.post")
    def test_verify_claim_with_mock_api(self, mock_post):
        svc = OpenRouterService(api_key="test-key", model="qwen/qwen3.8-27b:free")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"verdict_id": "likely_true", "credibility_score": 95, "summary": "Multiple reputable outlets confirm India won.", "key_points": ["Defeated SA in final", "Unbeaten run"]}'
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        res = svc.verify_claim("India won the T20 World Cup in 2024", [
            {"title": "India wins T20 WC", "source": "BBC", "snippet": "India won by 7 runs"}
        ])

        self.assertEqual(res["verdict_id"], "likely_true")
        self.assertEqual(res["credibility_score"], 95)
        self.assertTrue(res["ai_verified"])
        self.assertIn("India won", res["summary"])


class TestFactCheckerOrchestrator(unittest.TestCase):
    def test_fact_checker_analyze_integration(self):
        mock_search = MagicMock()
        mock_search.search_evidence.return_value = [
            {
                "title": "Chandrayaan-3 Moon Landing",
                "source": "ISRO",
                "url": "https://isro.gov.in/chandrayaan3",
                "snippet": "Soft landing completed on the lunar south pole",
                "date": "2023-08-23",
            }
        ]

        mock_ai = MagicMock()
        mock_ai.is_configured = True
        mock_ai.verify_claim.return_value = {
            "verdict_id": "likely_true",
            "credibility_score": 98,
            "summary": "ISRO successfully soft-landed Chandrayaan-3 on the Moon on August 23, 2023.",
            "key_points": ["First spacecraft to land near the south pole", "Officially confirmed by ISRO"],
            "model": "qwen/qwen3.8-27b:free",
            "ai_verified": True,
        }

        mock_gemini = MagicMock()
        mock_gemini.is_configured = False

        fc = FactChecker(search_service=mock_search, ai_service=mock_ai, gemini_service=mock_gemini)
        result = fc.analyze("Chandrayaan-3 landed on Moon")

        self.assertEqual(result["verdict"]["id"], "likely_true")
        self.assertEqual(result["credibility_score"], 98)
        self.assertTrue(len(result["sources"]) == 1)
        self.assertTrue(result["ai_info"]["is_ai_verified"])
        self.assertEqual(len(result["key_points"]), 2)
        self.assertIn("Chandrayaan-3", result["summary"])


if __name__ == "__main__":
    unittest.main()
