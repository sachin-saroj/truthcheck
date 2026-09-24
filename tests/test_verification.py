"""Unit and integration tests for FreeNewsAPI.ai verification service."""
import unittest
from unittest.mock import MagicMock, patch

import requests

from services.verification import VerificationService, build_search_query


class TestBuildSearchQuery(unittest.TestCase):
    def test_empty_and_none(self):
        self.assertEqual(build_search_query(""), "")
        self.assertEqual(build_search_query(None), "")

    def test_short_query(self):
        self.assertEqual(build_search_query("NASA Mars"), "NASA Mars")

    def test_strip_punctuation_and_stopwords(self):
        text = "According to the Ministry of Education, a new scholarship scheme was announced on Monday."
        query = build_search_query(text)
        self.assertEqual(query, "Ministry Education scholarship scheme")

    def test_nasa_entity_query(self):
        text = "NASA has confirmed a new water discovery on Mars."
        query = build_search_query(text)
        self.assertEqual(query, "NASA water discovery Mars")


class TestVerificationService(unittest.TestCase):
    def setUp(self):
        self.service = VerificationService()

    def test_is_configured(self):
        self.assertTrue(self.service.is_configured)

    def test_empty_query(self):
        result = self.service.search("")
        self.assertEqual(result["status"], "no_results")
        self.assertEqual(result["sources"], [])

    def test_safe_url(self):
        self.assertTrue(self.service._safe_url("https://example.com/article"))
        self.assertTrue(self.service._safe_url("http://news.bbc.co.uk/story/123"))
        self.assertFalse(self.service._safe_url("javascript:alert('xss')"))
        self.assertFalse(self.service._safe_url("data:text/html,evil"))
        self.assertFalse(self.service._safe_url("file:///etc/passwd"))
        self.assertFalse(self.service._safe_url("ftp://ftp.example.com/file"))
        self.assertFalse(self.service._safe_url("http://"))
        self.assertFalse(self.service._safe_url("//schemeless.com"))
        self.assertFalse(self.service._safe_url(None))
        self.assertFalse(self.service._safe_url(123))

    def test_freenews_success_normalization(self):
        mock_payload = {
            "took_ms": 35,
            "total": 1,
            "size": 1,
            "offset": 0,
            "results": [
                {
                    "id": "abc123",
                    "url": "https://example.com/news/mars-mission",
                    "title": "NASA Rover Finds Fascinating Rocks on Mars",
                    "description": "Perseverance has uncovered intriguing new minerals on the Martian surface.",
                    "published_at": "2026-09-23T12:00:00Z",
                    "host": "example.com",
                    "sitename": "Example News",
                    "lang": "en",
                }
            ],
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        service = VerificationService(session=mock_session)
        result = service.search("NASA Mars", max_results=5)

        self.assertEqual(result["status"], "ok")
        self.assertIn("Found 1 related article", result["message"])
        self.assertEqual(len(result["sources"]), 1)

        source = result["sources"][0]
        self.assertEqual(source["title"], "NASA Rover Finds Fascinating Rocks on Mars")
        self.assertEqual(source["url"], "https://example.com/news/mars-mission")
        self.assertEqual(source["source"], "Example News")
        self.assertEqual(source["publishedAt"], "2026-09-23T12:00:00Z")
        self.assertIn("Perseverance", source["description"])

    def test_empty_results(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"took_ms": 10, "total": 0, "size": 5, "results": []}

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        service = VerificationService(session=mock_session)
        result = service.search("nonexistentqueryxyz", max_results=5)

        self.assertEqual(result["status"], "no_results")
        self.assertEqual(result["sources"], [])
        self.assertIn("No matching verification sources", result["message"])

    def test_api_unavailable_500(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service Unavailable"

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        service = VerificationService(session=mock_session)
        result = service.search("NASA Mars")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["sources"], [])
        self.assertIn("temporarily unavailable", result["message"])

    def test_api_auth_failure_401_403(self):
        for code in (401, 403):
            mock_resp = MagicMock()
            mock_resp.status_code = code

            mock_session = MagicMock()
            mock_session.get.return_value = mock_resp

            service = VerificationService(session=mock_session)
            result = service.search("NASA Mars")

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["sources"], [])
            self.assertIn("temporarily unavailable", result["message"])

    def test_rate_limit_429(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        service = VerificationService(session=mock_session)
        result = service.search("NASA Mars")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["sources"], [])
        self.assertIn("temporarily unavailable", result["message"])

    def test_timeout(self):
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.Timeout("Connection timed out")

        service = VerificationService(session=mock_session)
        result = service.search("NASA Mars")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["sources"], [])
        self.assertIn("temporarily unavailable", result["message"])

    def test_connection_error(self):
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.ConnectionError("Failed to connect")

        service = VerificationService(session=mock_session)
        result = service.search("NASA Mars")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["sources"], [])
        self.assertIn("temporarily unavailable", result["message"])

    def test_malformed_json(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("Invalid JSON")

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        service = VerificationService(session=mock_session)
        result = service.search("NASA Mars")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["sources"], [])
        self.assertIn("temporarily unavailable", result["message"])

    def test_missing_results_field(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"took_ms": 10}

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        service = VerificationService(session=mock_session)
        result = service.search("NASA Mars")

        self.assertEqual(result["status"], "no_results")
        self.assertEqual(result["sources"], [])

    def test_malformed_article_objects_and_unsafe_urls(self):
        mock_payload = {
            "results": [
                None,
                "not a dict",
                {"title": "Missing URL"},
                {"url": "https://example.com/no-title"},
                {"title": "Unsafe JS", "url": "javascript:alert(1)"},
                {"title": "Unsafe data", "url": "data:text/html,alert(1)"},
                {"title": "Unsafe file", "url": "file:///etc/passwd"},
                {
                    "title": "Legitimate Article",
                    "url": "https://valid.com/news/1",
                    "host": "valid.com",
                    "sitename": "",
                    "description": "Safe news description",
                    "published_at": "2026-09-24T00:00:00Z",
                },
            ]
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        service = VerificationService(session=mock_session)
        result = service.search("test query")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["title"], "Legitimate Article")
        self.assertEqual(result["sources"][0]["source"], "valid.com")

    def test_in_process_cache(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "Cache Test",
                    "url": "https://example.com/cache",
                    "sitename": "Test",
                }
            ]
        }
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        service = VerificationService(session=mock_session)
        res1 = service.search("Cache Test Query")
        res2 = service.search("Cache Test Query")

        self.assertEqual(res1, res2)
        # Should only call HTTP get once due to cache
        self.assertEqual(mock_session.get.call_count, 1)

    def test_http_400_retry(self):
        resp_400 = MagicMock()
        resp_400.status_code = 400
        resp_400.text = "Bad Request"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "results": [
                {
                    "title": "Recovered Article",
                    "url": "https://example.com/recovered",
                    "sitename": "Recovery News",
                }
            ]
        }

        mock_session = MagicMock()
        mock_session.get.side_effect = [resp_400, resp_200]

        service = VerificationService(session=mock_session)
        # Multi-word query where minimal 3-word query is different
        result = service.search("one two three four five")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(mock_session.get.call_count, 2)


class TestRealFreeNewsAPI(unittest.TestCase):
    def test_live_freenewsapi_call(self):
        """Phase 12: Real API test with 'NASA Mars'."""
        service = VerificationService()
        result = service.search("NASA Mars", max_results=5)
        self.assertIn(result["status"], ("ok", "no_results", "error"))
        if result["status"] == "ok":
            self.assertGreater(len(result["sources"]), 0)
            for source in result["sources"]:
                self.assertTrue(source["url"].startswith("http://") or source["url"].startswith("https://"))
                self.assertTrue(bool(source["title"]))
                self.assertIn("source", source)
                self.assertIn("publishedAt", source)
                self.assertIn("description", source)


if __name__ == "__main__":
    unittest.main()
