"""Unit tests for EvidenceVerifier semantic cross-examination engine."""
import unittest
from services.evidence_verifier import EvidenceVerifier


class TestEvidenceVerifier(unittest.TestCase):
    def setUp(self):
        self.verifier = EvidenceVerifier()

    def test_celestial_conflict_sun_vs_moon(self):
        claim = "ISRO successfully performed the soft landing of Chandrayaan-3 near the south pole of the sun."
        evidence = [
            {
                "source": "MSN",
                "title": "Chandrayaan-3 wins top global astronautics honour for Moon south pole landing",
                "snippet": "Vikram lander touched down near lunar south pole on August 23, 2023."
            }
        ]
        res = self.verifier.verify(claim, evidence)
        self.assertEqual(res["verdict_id"], "likely_fake")
        self.assertGreaterEqual(res["confidence"], 90)
        self.assertIn("moon", res["summary"].lower())
        self.assertIn("sun", res["summary"].lower())

    def test_debunk_scam_detection(self):
        claim = "Government giving free laptops to everyone who forwards WhatsApp link"
        evidence = [
            {
                "source": "PIB Fact Check",
                "title": "Fact check: Viral message about free laptop scheme is fake",
                "snippet": "Government of India has not launched any such scheme. Beware of phishing links."
            }
        ]
        res = self.verifier.verify(claim, evidence)
        self.assertEqual(res["verdict_id"], "likely_fake")
        self.assertGreaterEqual(res["confidence"], 90)
        self.assertIn("debunked", " ".join(res["key_points"]).lower())

    def test_corroborated_true_claim(self):
        claim = "ISRO successfully launched Chandrayaan-3 mission from Sriharikota"
        evidence = [
            {
                "source": "The Hindu",
                "title": "ISRO launches Chandrayaan-3 into orbit from Sriharikota",
                "snippet": "India launches moon mission aboard LVM3 rocket from Sriharikota."
            },
            {
                "source": "NDTV",
                "title": "ISRO launches Chandrayaan-3 successfully",
                "snippet": "Chandrayaan-3 launched by ISRO from Sriharikota spaceport."
            }
        ]
        res = self.verifier.verify(claim, evidence)
        self.assertEqual(res["verdict_id"], "likely_true")
        self.assertGreaterEqual(res["confidence"], 85)

    def test_chandrayaan3_moon_soft_landing(self):
        claim = "ISRO successfully performed the soft landing of Chandrayaan-3 near the south pole of the moon"
        evidence = [
            {
                "source": "MSN",
                "title": "India's Chandrayaan-3 wins top global space honour for historic Moon landing",
                "snippet": "India's Chandrayaan-3 mission has received one of the highest honours in global space exploration for soft landing."
            },
            {
                "source": "Gov",
                "title": "Chandrayaan-3",
                "snippet": "Overview of India's historic Chandrayaan-3 mission achieving successful soft landing on the lunar south pole."
            }
        ]
        res = self.verifier.verify(claim, evidence)
        self.assertEqual(res["verdict_id"], "likely_true")
        self.assertGreaterEqual(res["confidence"], 85)

    def test_insufficient_evidence(self):
        claim = "Scientists discovered living dinosaur inside local cave yesterday"
        res = self.verifier.verify(claim, [])
        self.assertEqual(res["verdict_id"], "needs_verification")
        self.assertLessEqual(res["confidence"], 55)


if __name__ == "__main__":
    unittest.main()
