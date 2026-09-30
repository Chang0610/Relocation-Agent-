import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from knowledge import AREA_DATA, area_references, context_for, extract_constraints


class KnowledgeTest(unittest.TestCase):
    def test_data_scope(self):
        self.assertEqual(len(AREA_DATA["areas"]), 8)
        self.assertTrue(all(not poi["verified"] for a in AREA_DATA["areas"] for group in a["facilities"].values() for poi in group))

    def test_constraints_and_estimates(self):
        messages = [{"role": "user", "content": "My office is in Zhangjiang Hi-Tech. I need a commute under 40 minutes, monthly rent under CNY 3,000, and I am open to shared housing."}]
        self.assertEqual(extract_constraints(messages), {"office_hub": "Zhangjiang Hi-Tech", "commute_minutes": 40, "monthly_rent": 3000, "shared": True})
        result = area_references(messages)
        self.assertTrue(result["areas"])
        self.assertTrue(all(a["commute_estimate"]["to"] == "Zhangjiang Hi-Tech" for a in result["areas"]))
        self.assertTrue(all(a["rent_status"] == "sample_reference" for a in result["areas"]))

    def test_no_claim_for_unknown_office(self):
        evidence = context_for([{"role": "user", "content": "My office is in Wujiaochang. Which areas are within a 30-minute commute?"}])
        self.assertIsNone(evidence["area_data"]["constraints"]["office_hub"])
        self.assertTrue(all(a["commute_estimate"] is None for a in evidence["area_data"]["areas"]))

    def test_shared_housing_negation(self):
        messages = [{"role": "user", "content": "I am not open to shared housing; I only want a whole apartment. My monthly rent budget is CNY 4,000."}]
        self.assertFalse(extract_constraints(messages)["shared"])

    def test_plan_request_includes_area_evidence(self):
        messages = [{"role": "user", "content": "Please create a relocation plan."}]
        profile = {"company_location": "Zhangjiang Hi-Tech", "commute_preference": "30-60 minutes", "monthly_rent_budget": "CNY 3,500", "shared_housing": "Open to shared housing"}
        evidence = context_for(messages, profile)
        self.assertEqual(evidence["area_data"]["constraints"]["commute_minutes"], 60)
        self.assertTrue(evidence["area_data"]["areas"])


if __name__ == "__main__":
    unittest.main()
