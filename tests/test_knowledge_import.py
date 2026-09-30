import io
import json
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from knowledge import CITY_KNOWLEDGE, context_for
from evidence_tags import annotate_answer
from server import openai_answer


def evidence(question):
    return context_for([{"role": "user", "content": question}])


class ImportedKnowledgeTest(unittest.TestCase):
    def test_snapshot_and_references(self):
        self.assertEqual(Counter(r["status"] for r in CITY_KNOWLEDGE["knowledge_entries"]),
                         {"verified": 24, "pending_verification": 33, "sample_reference": 2})
        self.assertEqual(len(CITY_KNOWLEDGE["entries"]), 41)
        self.assertEqual(len(CITY_KNOWLEDGE["task_templates"]), 12)
        ids = {r["id"] for r in CITY_KNOWLEDGE["entries"]}
        for row in CITY_KNOWLEDGE["knowledge_entries"]:
            self.assertTrue(set(row.get("entry_ids") or []) <= ids)

    def test_rent_round_two_and_pending_amount(self):
        city = evidence("Can I withdraw housing fund contributions for rent without online lease registration?")["city_knowledge"]
        rows = {r["id"]: r for r in city["knowledge_entries"]}
        self.assertEqual(rows["ke_rent_001"]["status"], "verified")
        self.assertEqual(rows["ke_rent_006"]["status"], "pending_verification")
        self.assertIn("4000", json.dumps(rows["ke_rent_006"], ensure_ascii=False))
        self.assertEqual(rows["ke_rent_015"]["status"], "pending_verification")
        self.assertEqual({g["id"] for g in city["data_gaps"] if g["severity"] == "P0"}, {"dg_grad_001", "gap_rentpolicy_entries_001", "gap_rent_001", "gap_rent_002"})
        rent = next(t for t in city["task_templates"] if t["template_id"] == "tpl_rent")
        # The owner-supplied template intentionally has no linked policy IDs:
        # the rent-policy verification gap is still open.
        self.assertEqual(rent["available_knowledge_entry_ids"], [])

    def test_hotlines_and_incomplete_records(self):
        city = evidence("What is the electricity hotline, and what should I verify before using Huolala movers?")["city_knowledge"]
        rows = {r["id"]: r for r in city["knowledge_entries"]}
        power = rows["hotline-electricity-001"]
        self.assertEqual(power["status"], "pending_verification")
        self.assertIn("95598", power["summary"])
        self.assertIsNone(power["evidence"])
        self.assertEqual(rows["moving-huolala-001"]["status"], "pending_verification")
        self.assertIsNone(rows["moving-huolala-001"]["evidence"])
        incomplete = next(e for e in city["entries"] if e["id"] == "entry-ziroom-001")
        self.assertEqual(incomplete["status"], "pending_verification")

    def test_topic_history_and_price_gaps(self):
        result = context_for([{"role": "user", "content": "I am moving to Shanghai with my cat."},
                              {"role": "assistant", "content": "Please confirm your move date."},
                              {"role": "user", "content": "Next month."}])
        self.assertIn("Pets", {r["category"] for r in result["city_knowledge"]["knowledge_entries"]})
        result = evidence("What do electricity, water, gas, and broadband services cost?")
        self.assertTrue(all(r["data_status"] == "pending_verification"
                            for r in result["utilities"] if r["utility"] == "gas"))

    def test_shared_url_does_not_upgrade_pending_policy(self):
        data = evidence("Housing fund withdrawal for rent")
        row = next(r for r in data["city_knowledge"]["knowledge_entries"] if r["id"] == "ke_rent_006")
        labels = annotate_answer("Evidence and status: " + row["evidence"][0]["url"], data)
        self.assertIn("Pending verification", labels[0]["tags"])
        self.assertNotIn("Knowledge source verified", labels[0]["tags"])

    def test_model_request_contains_actual_new_evidence(self):
        question = "What is the electricity hotline, how should I verify a pre-employment health check, and how do I verify rental housing fund withdrawal and household registration eligibility?"
        captured = {}
        def respond(request, **kwargs):
            captured.update(json.loads(request.data))
            return io.BytesIO(json.dumps({"output": [{"type": "message", "content": [{
                "type": "output_text", "text": json.dumps({
                    "answer": "向HR核验", "operations": [], "profile_updates": []
                })}]}]}).encode())
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}), patch("urllib.request.urlopen", respond):
            openai_answer([{"role": "user", "content": question}], evidence(question), {}, {})
        payload = captured["input"][0]["content"]
        for term in ("hotline-electricity-001", "ke_health_001", "ke_rent_006", "dg_grad_001", "tpl_rent", "fallback"):
            self.assertIn(term, payload)
        self.assertIn("preserve verification status", captured["instructions"])
        self.assertIn("Do not promise household-registration eligibility", captured["instructions"])


if __name__ == "__main__":
    unittest.main()
