"""Unit tests for GeminiService."""
from unittest import TestCase
from unittest.mock import MagicMock, patch

from services.gemini_service import GeminiService


class TestGeminiService(TestCase):
    def test_not_configured_when_no_key(self):
        svc = GeminiService(api_key="")
        self.assertFalse(svc.is_configured)
        res = svc.verify_claim("Some claim", [])
        self.assertIsNone(res)

    @patch("services.gemini_service.requests.post")
    def test_verify_claim_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"verdict_id": "likely_fake", "confidence": 92, "summary": "Chandrayaan-3 landed on the Moon, not the Sun.", "key_points": ["Source 1 - Confirmed moon mission"]}'
                            }
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        svc = GeminiService(api_key="test-gemini-key")
        self.assertTrue(svc.is_configured)
        res = svc.verify_claim(
            "Chandrayaan-3 landed on the Sun",
            [{"source": "ISRO", "title": "Moon Landing", "snippet": "ISRO lands on lunar south pole."}],
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["verdict_id"], "likely_fake")
        self.assertEqual(res["confidence"], 92)
        self.assertIn("Chandrayaan-3", res["summary"])
