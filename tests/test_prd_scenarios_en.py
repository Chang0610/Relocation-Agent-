import re
import sys
import unittest
import json
from copy import deepcopy
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from calendar_plan import (
    _explicit_move_target,
    _move_change_requested,
    _complete_first_plan,
    _pending_rejected,
    augment_model_result,
    build_proposal,
    clean_calendar,
    clean_event,
)
from knowledge import context_for, extract_constraints
from profile import explicit_profile_updates
from server import SYSTEM, _english_display, enforce_response_mode


TODAY = date(2026, 9, 29)


def event(event_id, title, due_date, *, hard=False, kind="task", depends_on_ids=None, done=False):
    return clean_event({
        "id": event_id,
        "title": title,
        "due_date": due_date,
        "date_basis": "用户明确",
        "hard_deadline": hard,
        "kind": kind,
        "depends_on_ids": depends_on_ids or [],
        "done": done,
        "source_note": "User-provided date.",
    })


def operation(action, event_id="", title="", due_date=None, *, hard=False, depends_on_ids=None):
    return {
        "action": action,
        "id": event_id,
        "title": title,
        "due_date": due_date,
        "due_time": None,
        "reminder_at": None,
        "detail": "",
        "kind": "task",
        "date_basis": "用户明确",
        "source_note": "User-provided date.",
        "sources": [],
        "depends_on_ids": depends_on_ids or [],
        "hard_deadline": hard,
    }


class EnglishPrdScenarioTests(unittest.TestCase):
    def test_internal_calendar_enums_survive_english_response_sanitization(self):
        payload = _english_display({
            "date_basis": "建议日期",
            "title": "张江看房",
        })
        self.assertEqual(payload["date_basis"], "建议日期")
        self.assertEqual(payload["title"], "Saved detail")

    def test_replayable_prd_scenarios_are_english_and_use_english_calendar_fields(self):
        scenarios_path = Path(__file__).parent / "scenarios" / "qa_regression.json"
        scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(scenarios), 10)
        for scenario in scenarios:
            self.assertFalse(re.search(r"[\u3400-\u9fff]", scenario["name"] + " ".join(scenario["turns"])))
            for item in scenario.get("calendar", {}).get("confirmed", []):
                self.assertIn("due_date", item)
                self.assertNotIn("date", item)

    def test_first_round_profile_and_knowledge_retrieval_use_english_inputs(self):
        message = "I start work at Zhangjiang Hi-Tech on October 15, 2026. Monthly rent 3500 yuan, accept shared rental, commute within 40 minutes."
        updates = explicit_profile_updates(message, TODAY)
        self.assertIn({"field": "start_date", "value": "2026-10-15"}, updates)
        constraints = extract_constraints([{"role": "user", "content": message}], {"company_location": "Zhangjiang Hi-Tech"})
        self.assertEqual(constraints, {"office_hub": "Zhangjiang Hi-Tech", "commute_minutes": 40, "monthly_rent": 3500, "shared": True})

    def test_follow_up_retrieval_preserves_constraints_from_earlier_turns(self):
        messages = [
            {"role": "user", "content": "My company is near Zhangjiang Hi-Tech. Rent budget 3,000 yuan, commute up to 45 minutes."},
            {"role": "assistant", "content": "Does that budget include utilities and internet?"},
            {"role": "user", "content": "Rent only, and shared housing is okay."},
        ]
        constraints = extract_constraints(messages)
        self.assertEqual(constraints, {"office_hub": "Zhangjiang Hi-Tech", "commute_minutes": 45, "monthly_rent": 3000, "shared": True})

    def test_area_comparison_mentions_do_not_override_saved_office_location(self):
        messages = [{"role": "user", "content": "Compare Lujiazui and Xujiahui for rent; my company is near Zhangjiang Hi-Tech."}]
        constraints = extract_constraints(messages, {"company_location": "Zhangjiang Hi-Tech"})
        self.assertEqual(constraints["office_hub"], "Zhangjiang Hi-Tech")

    def test_retrieved_context_contains_no_chinese_annotations(self):
        context = context_for([{"role": "user", "content": "Tell me about renting near Zhangjiang Hi-Tech."}], {})
        self.assertIsNotNone(context["area_data"])
        self.assertGreater(len(context["area_data"]["areas"]), 0)
        self.assertFalse(re.search(r"[\u3400-\u9fff]", str(context)))

    def test_first_plan_fallback_is_meaningful_english_and_confirmation_only(self):
        profile = {"start_date": "2026-10-15", "move_deadline": "2026-10-14"}
        augmented = augment_model_result(clean_calendar(None), {"response_mode": "B", "calendar_intent": "none", "operations": []}, profile, "Please give me a relocation plan.", TODAY)
        operations = augmented["operations"]
        titles = [item["title"] for item in operations]
        self.assertTrue(any("view" in title.lower() for title in titles))
        self.assertTrue(any("broadband" in title.lower() for title in titles))
        self.assertTrue(any("commute" in title.lower() for title in titles))
        self.assertTrue(any("check in with your employer" in title.lower() for title in titles))
        visible_operation_text = " ".join(" ".join(str(item.get(key, "")) for key in ("title", "detail", "source_note")) for item in operations)
        self.assertFalse(re.search(r"[\u3400-\u9fff]", visible_operation_text))
        state = clean_calendar(None)
        before = deepcopy(state)
        proposal = build_proposal(state, {"calendar_intent": "propose", "operations": operations}, profile, TODAY)
        self.assertIsNotNone(proposal)
        self.assertEqual(state, before)  # Building a proposal never writes confirmed state.

    def test_area_consultation_asks_budget_scope_without_changing_calendar(self):
        answer = "Which areas suit a 3,000 yuan monthly rent budget and a 45-minute commute?"
        result = augment_model_result(clean_calendar(None), {"response_mode": "C", "operations": [], "calendar_intent": "none"}, {"company_location": "Zhangjiang Hi-Tech"}, answer, TODAY)
        self.assertEqual(result["response_mode"], "C")
        self.assertEqual(result["calendar_intent"], "none")
        self.assertEqual(result["operations"], [])
        self.assertTrue(any("utilities" in question.lower() for question in result["follow_ups"]))

    def test_explicit_single_event_preserves_unknown_clock_time(self):
        state = clean_calendar(None)
        proposal = build_proposal(state, {"calendar_intent": "propose", "operations": [operation("add", title="Confirm lease contract", due_date="2026-10-10")]}, today=TODAY)
        self.assertEqual(len(proposal["changes"]), 1)
        self.assertIsNone(proposal["events"][0]["due_time"])
        self.assertEqual(state["confirmed"], [])

    def test_residence_confirmation_unlocks_follow_up_tasks_without_deleting_history(self):
        done_viewing = event("done-view", "View apartments", "2026-10-08", done=True)
        pending_viewing = event("view", "Property viewing", "2026-10-09")
        state = clean_calendar({"confirmed": [done_viewing, pending_viewing]})
        profile = {"housing_handover_date": "2026-10-12"}
        result = augment_model_result(state, {"response_mode": "D", "operations": []}, profile, "The apartment is settled; handover is on October 12, 2026.", TODAY)
        proposal = build_proposal(state, result, profile, TODAY)
        self.assertIsNotNone(proposal)
        self.assertTrue(any(change["type"] == "删除" and change["id"] == "view" for change in proposal["changes"]))
        self.assertFalse(any(change["id"] == "done-view" for change in proposal["changes"]))
        self.assertTrue(any("broadband" in change["title"].lower() for change in proposal["changes"]))

    def test_handover_delay_reschedules_broadband_and_move_without_claiming_external_action(self):
        state = clean_calendar({"confirmed": [
            event("handover", "New-home handover", "2026-10-12"),
            event("net", "Broadband installation booked", "2026-10-13"),
            event("move", "Move completion", "2026-10-13"),
        ]})
        message = "Handover is delayed from October 12 to October 14, 2026; I already booked broadband myself."
        profile = {"housing_handover_date": "2026-10-14"}
        result = augment_model_result(state, {"response_mode": "D", "operations": []}, profile, message, TODAY)
        proposal = build_proposal(state, result, profile, TODAY)
        self.assertIsNotNone(proposal)
        proposed = {item["id"]: item for item in proposal["events"]}
        self.assertEqual(proposed["handover"]["due_date"], "2026-10-14")
        self.assertGreaterEqual(proposed["net"]["due_date"], "2026-10-14")
        self.assertGreaterEqual(proposed["move"]["due_date"], "2026-10-14")
        broadband = next(item for item in result["operations"] if item.get("id") == "net")
        self.assertIn("not been rescheduled", broadband["detail"].lower())
        public_fields = " ".join(str(item.get(key, "")) for item in result["operations"] for key in ("title", "detail", "source_note"))
        self.assertFalse(re.search(r"[\u3400-\u9fff]", public_fields))

    def test_half_day_capacity_proposes_shifting_nonblocking_tasks(self):
        same_day = "2026-10-10"
        events = [
            event("view", "Property viewing", same_day),
            event("hr", "Confirm onboarding with HR", same_day),
            event("broadband", "Verify broadband options", same_day),
            event("inventory", "Inventory items for moving", same_day),
            event("utilities", "Verify utility handover", same_day),
        ]
        state = clean_calendar({"confirmed": events})
        result = augment_model_result(state, {"response_mode": "C", "operations": [], "calendar_intent": "none"}, {}, "I only have half a day free on Saturdays, about three or four hours.", TODAY)
        self.assertEqual(result["calendar_intent"], "propose")
        self.assertTrue(result["operations"])
        self.assertTrue(all(item["due_date"] != same_day for item in result["operations"]))
        self.assertFalse(re.search(r"[\u3400-\u9fff]", result["answer"]))

    def test_half_day_capacity_conflict_explains_english_risk_without_changes(self):
        events = [
            event("hard1", "Hard deadline: submit required documents", "2026-10-10", hard=True),
            event("hard2", "Hard deadline: attend employer check-in", "2026-10-10", hard=True),
            event("hard3", "Hard deadline: old-home handover", "2026-10-10", hard=True),
            event("hard4", "Hard deadline: verify rental contract", "2026-10-10", hard=True),
            event("hard5", "Hard deadline: complete move", "2026-10-10", hard=True),
            event("soft", "Verify broadband conditions", "2026-10-10"),
        ]
        result = augment_model_result(clean_calendar({"confirmed": events}), {"response_mode": "C", "operations": []}, {}, "I only have half a day free on Saturdays, about three or four hours.", TODAY)
        self.assertEqual(result["response_mode"], "E")
        self.assertEqual(result["calendar_intent"], "none")
        self.assertEqual(result["operations"], [])
        self.assertIn("Hard deadlines", result["answer"])
        self.assertFalse(re.search(r"[\u3400-\u9fff]", result["answer"]))

    def test_completed_move_proposes_deletion_but_keeps_onboarding_and_benefit_tasks(self):
        state = clean_calendar({"confirmed": [
            event("move", "Move completion", "2026-10-10"),
            event("lease", "Review and sign rental agreement", "2026-10-08"),
            event("hr", "Confirm onboarding with HR", "2026-10-15"),
            event("fund", "Verify housing fund enrollment", "2026-10-16"),
        ]})
        result = augment_model_result(state, {"response_mode": "C", "operations": []}, {}, "I have already moved.", TODAY)
        proposal = build_proposal(state, result, today=TODAY)
        self.assertEqual({item["id"] for item in proposal["events"]}, {"hr", "fund"})
        self.assertEqual({item["type"] for item in proposal["changes"]}, {"删除"})
        self.assertIn("confirm", result["answer"].lower())

    def test_response_modes_a_c_and_e_cannot_write_calendar_operations(self):
        for mode in ("A", "C", "E"):
            result = enforce_response_mode({
                "response_mode": mode,
                "calendar_intent": "propose",
                "operations": [operation("add", title="Confirm lease")],
                "follow_ups": ["One?", "Two?", "Three?", "Four?"],
            })
            self.assertEqual(result["calendar_intent"], "none")
            self.assertEqual(result["operations"], [])
            self.assertLessEqual(len(result["follow_ups"]), 3)

    def test_pending_rejection_clears_only_pending_proposal(self):
        self.assertTrue(_pending_rejected("No need to change the current schedule."))
        pending = [event("draft", "View apartments", "2026-10-11")]
        state = clean_calendar({"confirmed": [], "pending": pending})
        result = augment_model_result(state, {"response_mode": "C", "operations": []}, {}, "No need to change the current schedule.", TODAY)
        self.assertTrue(result["clear_pending"])
        self.assertEqual(result["calendar_intent"], "none")
        self.assertEqual(result["operations"], [])
        self.assertEqual([item["id"] for item in state["pending"]], ["draft"])

    def test_duplicate_lease_signing_does_not_create_a_second_event(self):
        existing = event("lease", "Confirm lease signing", "2026-10-10")
        state = clean_calendar({"confirmed": [existing]})
        result = build_proposal(state, {"calendar_intent": "propose", "operations": [operation("add", title="Confirm lease signing", due_date="2026-10-10")]}, today=TODAY)
        self.assertIsNone(result)
        self.assertEqual(len(state["confirmed"]), 1)

    def test_hard_old_home_deadline_is_not_shifted_when_move_date_changes(self):
        old_handover = event("old-home", "Old-home lease handover", "2026-10-12", hard=True)
        move = event("move", "Move completion", "2026-10-11", depends_on_ids=["old-home"])
        state = clean_calendar({"confirmed": [old_handover, move]})
        proposal = build_proposal(state, {"calendar_intent": "propose", "operations": [operation("update", "move", "Move completion", "2026-10-13")]}, today=TODAY)
        self.assertIsNotNone(proposal)
        self.assertTrue(proposal["conflicts"])
        self.assertEqual(next(item for item in proposal["events"] if item["id"] == "old-home")["due_date"], "2026-10-12")

    def test_move_date_change_shifts_linked_old_home_handover(self):
        handover = event("old-home", "Old-home lease handover", "2026-10-10")
        move = event("move", "Move completion", "2026-10-11")
        state = clean_calendar({"confirmed": [handover, move]})
        proposed = build_proposal(state, {"calendar_intent": "propose", "operations": [operation("update", "move", "Move completion", "2026-10-13")]}, today=TODAY)
        proposed_events = {item["id"]: item for item in proposed["events"]}
        self.assertEqual(proposed_events["old-home"]["due_date"], "2026-10-12")
        self.assertEqual({item["id"] for item in proposed["changes"]}, {"move", "old-home"})

    def test_natural_english_move_in_date_change_is_recognized_and_confirmed(self):
        message = "Please move my move-in date to October 13, 2026."
        self.assertTrue(_move_change_requested(message))
        self.assertEqual(_explicit_move_target(message, TODAY), "2026-10-13")
        state = clean_calendar({"confirmed": [
            event("move", "Move into the new home and complete an inspection", "2026-10-11"),
            event("old-home", "Confirm moving arrangements and old-home handover", "2026-10-10"),
        ]})
        result = augment_model_result(state, {"response_mode": "C", "calendar_intent": "none", "operations": []}, {}, message, TODAY)
        proposal = build_proposal(state, result, today=TODAY)
        proposed = {item["id"]: item for item in proposal["events"]}
        self.assertEqual(proposed["move"]["due_date"], "2026-10-13")
        self.assertEqual(proposed["old-home"]["due_date"], "2026-10-12")
        self.assertEqual(result["response_mode"], "D")
        self.assertEqual(state["confirmed"][0]["due_date"], "2026-10-11")

    def test_hard_deadline_move_conflict_preserves_deadline_and_english_risk(self):
        handover = event("old-home", "Old-home lease handover", "2026-10-12", hard=True)
        move = event("move", "Move completion", "2026-10-11", depends_on_ids=["old-home"])
        state = clean_calendar({"confirmed": [handover, move]})
        proposal = build_proposal(state, {"calendar_intent": "propose", "operations": [operation("update", "move", "Move completion", "2026-10-13")]}, today=TODAY)
        self.assertTrue(proposal["conflicts"])
        self.assertIn("Hard deadline", proposal["conflicts"][0])
        self.assertEqual(next(item for item in proposal["events"] if item["id"] == "old-home")["due_date"], "2026-10-12")

    def test_english_onboarding_change_moves_commute_walkthrough_only(self):
        commute = event("commute", "Test the commute before your start date", "2026-10-16")
        move = event("move", "Move into the new home", "2026-10-12")
        state = clean_calendar({"confirmed": [commute, move]})
        result = augment_model_result(state, {"response_mode": "C", "operations": []}, {}, "My onboarding date has changed to October 15, 2026; please adjust the arrangements accordingly.", TODAY)
        proposal = build_proposal(state, result, today=TODAY)
        self.assertEqual(result["response_mode"], "D")
        self.assertEqual(proposal["changes"], [{"id": "commute", "type": "修改", "title": "Test the commute before your start date"}])
        self.assertEqual(next(item for item in proposal["events"] if item["id"] == "commute")["due_date"], "2026-10-14")
        self.assertEqual(next(item for item in proposal["events"] if item["id"] == "move")["due_date"], "2026-10-12")
        updated = next(item for item in result["operations"] if item.get("id") == "commute")
        self.assertIn("must take place before", updated["detail"].lower())
        self.assertNotEqual(updated["detail"], "Saved detail")
        self.assertFalse(re.search(r"[\u3400-\u9fff]", updated["detail"] + updated["source_note"]))

    def test_initial_plan_dates_are_not_misread_as_an_onboarding_change(self):
        message = (
            "Using my saved details, create a concise dated relocation plan now. "
            "My office is near Zhangjiang Hi-Tech, I start work on 2026-10-29, "
            "and I want to finish moving by 2026-10-27. Keep all tasks as a draft for my confirmation."
        )
        profile = {"company_location": "Zhangjiang Hi-Tech", "start_date": "2026-10-29", "move_deadline": "2026-10-27"}
        state = clean_calendar(None)
        result = augment_model_result(state, {"response_mode": "D", "answer": "Draft plan.", "calendar_intent": "propose", "operations": []}, profile, message, TODAY)
        proposal = build_proposal(state, result, profile, TODAY)
        self.assertEqual(result["response_mode"], "B")
        self.assertIsNotNone(proposal)
        self.assertNotIn("Your start date is now", result["answer"])

    def test_explicit_handover_and_residence_facts_are_saved_as_profile_updates(self):
        updates = explicit_profile_updates("I found an apartment. Handover is on October 12, 2026.", TODAY)
        self.assertIn({"field": "current_housing", "value": "I found an apartment. Handover is on October 12, 2026."}, updates)
        self.assertIn({"field": "housing_handover_date", "value": "2026-10-12"}, updates)

    def test_onboarding_date_change_moves_commute_walkthrough_before_start(self):
        commute = event("commute", "Commute walkthrough", "2026-10-16")
        move = event("move", "Move completion", "2026-10-12")
        state = clean_calendar({"confirmed": [commute, move]})
        result = augment_model_result(state, {"response_mode": "C", "operations": []}, {}, "My onboarding date has been changed to October 15, 2026; please adjust the arrangements accordingly.", TODAY)
        self.assertEqual(result["response_mode"], "D")
        proposal = build_proposal(state, result, today=TODAY)
        self.assertEqual(proposal["changes"], [{"id": "commute", "type": "修改", "title": "Commute walkthrough"}])
        self.assertEqual(next(item for item in proposal["events"] if item["id"] == "commute")["due_date"], "2026-10-14")

    def test_reminder_settings_are_not_calendar_operations_or_wechat_claims(self):
        result = augment_model_result(clean_calendar(None), {"response_mode": "C", "operations": []}, {}, "Change the moving reminder to three days in advance, and turn on WeChat reminders.", TODAY)
        self.assertEqual(result["calendar_intent"], "none")
        self.assertEqual(result["operations"], [])
        self.assertIn("not connected", result["answer"].lower())
        self.assertNotIn("enabled", result["answer"].lower())

    def test_medical_exam_prompt_requires_hr_verification(self):
        self.assertIn("do not recommend tests", SYSTEM.lower())
        self.assertIn("verify the institution", SYSTEM.lower())


if __name__ == "__main__":
    unittest.main()
