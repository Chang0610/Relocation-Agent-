import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from server import attach_operation_sources, compose_answer, conflict_quick_choices, enforce_response_mode, follow_up_questions, structured_answer_sources, CALENDAR_SCHEMA


class AnswerFormatTest(unittest.TestCase):
    def test_hard_deadline_conflict_has_concrete_choices(self):
        choices = conflict_quick_choices(['Hard deadline: old-home lease handover (2026-10-12) is before move completion on 2026-10-13'])
        self.assertEqual(choices, ['Move before the deadline (2026-10-11)', 'Verify the old-home handover and temporary storage arrangements first'])

    def test_follow_ups_only_contain_answerable_questions(self):
        raw = [
            'Confirm your monthly rent budget and commute preference before comparing areas.',
            'Review the lease for move-out notice, inspection, and service termination requirements.',
            'What is your monthly rent budget?',
            'How much notice does your landlord require before move-out?',
        ]
        self.assertEqual(follow_up_questions(raw), raw[2:])
        answer = compose_answer({'response_mode': 'C', 'answer': '目前信息总结：待补充。', 'advice_items': [{
            'title': '确认租房条件', 'why': '便于筛选区域', 'when': '租房前',
            'prerequisite': '公司位置', 'completion': '预算确定', 'basis': '信息待确认',
        }], 'follow_ups': raw})
        self.assertIn('Follow-up questions:\n1. What is your monthly rent budget?', answer)
        self.assertNotIn('Confirm your monthly rent budget and commute preference', answer)

    def test_sources_are_bound_to_advice_and_unverified_urls_are_not_linked(self):
        result = {"answer": "Summary of current information: Verify the housing fund details.", "advice_items": [{"title": "Verify housing fund enrollment", "why": "Confirm your benefits after starting work", "when": "After your first workday", "prerequisite": "Confirm your employer", "completion": "Find the enrollment record", "basis": "Needs confirmation with the provider", "sources": [
            {"source_name": "Shanghai Housing Fund Center", "source_url": "https://example.gov.cn/rule", "source_status": "Official source verified", "verified_at": "2099-01-01"},
            {"source_name": "Unknown site", "source_url": "https://made-up.example/rule", "source_status": "Official source verified", "verified_at": "2099-01-01"},
        ]}]}
        answer = compose_answer(result)
        evidence = {"policies": [{"topic": "Housing fund", "source": "https://example.gov.cn/rule", "status": "verified"}]}
        sources = structured_answer_sources(answer, result, evidence)[0]["sources"]
        self.assertEqual(sources[0]["source_url"], "https://example.gov.cn/rule")
        self.assertEqual(sources[0]["verified_at"], "")
        self.assertEqual(sources[1]["source_url"], "")
        self.assertEqual(sources[1]["source_status"], "Pending verification")

    def test_operation_schema_contains_range_deadline_and_dependencies(self):
        fields = CALENDAR_SCHEMA["properties"]["operations"]["items"]["properties"]
        self.assertTrue({"start_date", "due_date", "hard_deadline", "depends_on_ids", "sources"} <= set(fields))

    def test_plan_sources_use_evidence_status_and_real_date(self):
        result = {"operations": [{"action": "add", "date_basis": "建议日期", "sources": [
            {"source_name": "Fabricated name", "source_url": "https://example.gov.cn/rule", "source_status": "Official source verified", "verified_at": "2099-01-01"},
            {"source_name": "Unknown", "source_url": "https://made-up.example/rule", "source_status": "Official source verified", "verified_at": "2099-01-01"},
        ]}]}
        evidence = {"policies": [{"topic": "Housing fund", "source": "https://example.gov.cn/rule", "status": "verified", "verified_at": "2026-09-23"}]}
        attach_operation_sources(result, evidence)
        sources = result["operations"][0]["sources"]
        self.assertEqual(sources[0]["verified_at"], "2026-09-23")
        self.assertEqual(sources[0]["source_name"], "Housing fund")
        self.assertEqual(sources[1]["source_url"], "")
        self.assertEqual(sources[1]["source_status"], "Pending verification")

    def test_structured_items_are_complete_and_limited(self):
        item = {"title": "Confirm housing", "why": "You need an address before moving", "when": "By October 10", "prerequisite": "Confirm your work location", "completion": "Sign the lease", "basis": "Pending verification: confirm details with the landlord"}
        answer = compose_answer({"answer": "Summary of current information: Your office is in Zhangjiang.", "advice_items": [item] * 4, "follow_ups": ["Are you open to shared housing?"]})
        self.assertIn("Summary of current information: Your office is in Zhangjiang.", answer)
        self.assertIn("Upcoming tasks:", answer)
        self.assertIn("Evidence and status: Pending verification", answer)
        self.assertEqual(answer.count("Why:"), 3)
        self.assertIn("Follow-up questions:", answer)

    def test_information_collection_mode_only_shows_key_questions(self):
        result = enforce_response_mode({
            "response_mode": "A", "answer": "Some information is needed to prepare your plan.",
            "advice_items": [{"title": "Must not appear"}], "follow_ups": ["What area is your office in?", "When do you start work?", "What is your monthly rent budget?", "Extra question"],
            "calendar_intent": "propose", "operations": [{"action": "add"}],
        })
        answer = compose_answer(result)
        self.assertEqual(result["calendar_intent"], "none")
        self.assertEqual(result["operations"], [])
        self.assertNotIn("Must not appear", answer)
        self.assertIn("Please provide:\n1. What area is your office in?", answer)
        self.assertNotIn("Extra question", answer)

    def test_plan_generation_uses_confirmation_table_for_details(self):
        answer = compose_answer({
            "response_mode": "B", "answer": "I organized the plan in chronological order.",
            "advice_items": [{"title": "Must not appear"}], "follow_ups": ["Can the move date change?"],
        })
        self.assertIn("I organized the plan in chronological order.", answer)
        self.assertIn("Assumptions to confirm:", answer)
        self.assertNotIn("Task details:", answer)
