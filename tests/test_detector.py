"""Unit tests for TruthCheck ML detector and warning signs."""
import unittest

from detector.detector import NewsDetector, VERDICTS
from detector.preprocessing import clean_text, first_line


class TestDetector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = NewsDetector()
        cls.detector.ensure_ready()

    def test_model_readiness(self):
        self.assertTrue(self.detector.is_ready)
        self.assertIn("accuracy", self.detector.metrics)
        self.assertIn("f1", self.detector.metrics)
        self.assertIn("train_rows", self.detector.metrics)
        self.assertGreaterEqual(self.detector.metrics["train_rows"], 100)

    def test_score_conversion(self):
        self.assertEqual(NewsDetector.credibility_score(0.0), 100)
        self.assertEqual(NewsDetector.credibility_score(0.20), 80)
        self.assertEqual(NewsDetector.credibility_score(0.50), 50)
        self.assertEqual(NewsDetector.credibility_score(0.80), 20)
        self.assertEqual(NewsDetector.credibility_score(1.0), 0)

    def test_threshold_boundaries(self):
        self.assertEqual(NewsDetector.calculate_verdict(0), "likely_fake")
        self.assertEqual(NewsDetector.calculate_verdict(49), "likely_fake")
        self.assertEqual(NewsDetector.calculate_verdict(50), "needs_verification")
        self.assertEqual(NewsDetector.calculate_verdict(51), "likely_true")
        self.assertEqual(NewsDetector.calculate_verdict(100), "likely_true")

    def test_prediction_reliable_news(self):
        text = "According to the Ministry of Education, a new scholarship scheme was announced on Monday. Officials confirmed the data."
        pred = self.detector.predict(text)
        self.assertEqual(pred.verdict_id, "likely_true")
        self.assertGreater(pred.credibility_score, 50)
        self.assertEqual(pred.verdict["label"], "Likely True")
        self.assertIn("credibility", pred.summary)

    def test_prediction_space_discovery(self):
        text = "NASA has confirmed a new water discovery on Mars."
        pred = self.detector.predict(text)
        self.assertEqual(pred.verdict_id, "likely_true")
        self.assertGreater(pred.credibility_score, 50)

    def test_prediction_misleading_sensational(self):
        text = "BREAKING!!! Scientists reveal shocking secret cure that doctors don't want you to know!!! Share before it is deleted!!!"
        pred = self.detector.predict(text)
        self.assertEqual(pred.verdict_id, "likely_fake")
        self.assertLess(pred.credibility_score, 50)
        self.assertEqual(pred.verdict["label"], "Likely Fake")

    def test_prediction_miracle_cure(self):
        text = "Doctors are hiding this miracle treatment from the public."
        pred = self.detector.predict(text)
        self.assertEqual(pred.verdict_id, "likely_fake")
        self.assertLess(pred.credibility_score, 50)

    def test_warning_signs_detection(self):
        text = "SHOCKING!!! You WON'T believe this miracle cure — doctors don't want you to know! Share this before it is deleted now!!!"
        signs = self.detector.detect_warning_signs(text)
        sign_ids = {s["id"] for s in signs}
        self.assertIn("sensational", sign_ids)
        self.assertIn("punctuation", sign_ids)
        self.assertIn("clickbait", sign_ids)

    def test_unicode_and_accented_text(self):
        text = "L’ancien président a confirmé lundi que l’hôpital recevra un financement d’urgence de 12 millions d’euros."
        pred = self.detector.predict(text)
        self.assertIsInstance(pred.credibility_score, int)
        self.assertIn(pred.verdict_id, VERDICTS)

    def test_clean_text_normalization(self):
        raw = "Check this out: https://example.com/story?ref=123 with “quotes” and ‘apostrophes’!"
        cleaned = clean_text(raw)
        self.assertNotIn("https://", cleaned)
        self.assertIn("url", cleaned)
        self.assertIn("quotes", cleaned)

    def test_first_line(self):
        multiline = "First line headline here.\nSecond line body paragraph."
        self.assertEqual(first_line(multiline), "First line headline here.")
        self.assertEqual(first_line(""), "")


if __name__ == "__main__":
    unittest.main()
