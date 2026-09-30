import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from demo import answer, response


class DemoTest(unittest.TestCase):
    def test_demo_is_explicit_and_uses_area_data(self):
        result = answer([{"role": "user", "content": "Compare areas near Zhangjiang; commute within 40 minutes; monthly rent budget CNY 4,000; I am okay with shared housing."}])
        self.assertIn("no language model was called", result.lower())
        self.assertIn("Pudong Zhangjiang", result)
        self.assertIn("listing sample", result)
        self.assertNotRegex(result, r"[\u3400-\u9fff]")

    def test_demo_plan_response_contains_only_unconfirmed_suggestions(self):
        result = response(
            [{"role": "user", "content": "Create a relocation plan from my saved profile."}],
            {"start_date": "2026-10-20"}, {"confirmed": [], "pending": None},
        )
        self.assertEqual(result["calendar_intent"], "propose")
        self.assertEqual(result["response_mode"], "B")
        self.assertEqual(len(result["operations"]), 3)
        self.assertTrue(all(not item["hard_deadline"] for item in result["operations"]))


if __name__ == "__main__":
    unittest.main()
