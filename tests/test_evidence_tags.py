import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evidence_tags import annotate_answer


class EvidenceTagTest(unittest.TestCase):
    def test_only_known_official_url_is_verified(self):
        official = "https://example.gov/known"
        evidence = {"policies": [{"source": official, "status": "verified"}]}
        answer = "Task details\nEvidence and status: https://example.com/unknown\nEvidence and status: " + official
        tags = annotate_answer(answer, evidence)
        self.assertEqual(tags[0]["tags"], ["Entry point or evidence needs verification"])
        self.assertIsNone(tags[0]["verified_url"])
        self.assertEqual(tags[1]["tags"], ["Official source verified"])
        self.assertEqual(tags[1]["verified_url"], official)

    def test_estimate_and_pending_are_distinguished(self):
        answer = "Evidence and status: Commute estimate, rent needs verification, amenities pending map verification\nEvidence and status: Pending verification"
        tags = annotate_answer(answer, {})
        self.assertEqual(tags[0]["tags"], ["Commute estimate", "Amenities pending verification", "Partially verified"])
        self.assertEqual(tags[1]["tags"], ["Pending verification"])
