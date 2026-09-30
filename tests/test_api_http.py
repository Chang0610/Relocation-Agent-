"""HTTP-level API integration tests; model calls are deterministic and free."""

import json
import os
import sys
import tempfile
import threading
import unittest
from datetime import timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch
from urllib.request import Request, urlopen

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import server  # noqa: E402
from time_utils import shanghai_today  # noqa: E402


class QuietHandler(server.Handler):
    def log_message(self, _format, *_args):
        pass


class ChatApiHttpIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.httpd.server_port}/api/chat"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)

    def post_chat(self, payload):
        request = Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            return response.status, json.load(response)

    def test_plan_proposal_round_trip_preserves_enum_and_requires_confirmation(self):
        due = (shanghai_today() + timedelta(days=14)).isoformat()

        def fake_model(_messages, _evidence, _calendar, profile):
            return {
                "response_mode": "B",
                "answer": "I prepared a plan for your review.",
                "calendar_intent": "propose",
                "operations": [{
                    "action": "add", "id": "", "title": "Confirm onboarding with HR",
                    "start_date": due, "due_date": due, "due_time": None,
                    "detail": "Verify your reporting location and required documents.",
                    "kind": "task", "date_basis": "建议日期", "source_note": "Suggested from your work start date.",
                    "sources": [], "hard_deadline": False, "depends_on_ids": [], "depends_on_titles": [],
                }],
                "profile_updates": [{"field": "start_date", "value": profile["start_date"]}],
            }

        payload = {
            "messages": [{"role": "user", "content": "Please create my relocation plan."}],
            "calendar": {"confirmed": [], "pending": None},
            "profile": {"company_location": "Zhangjiang Hi-Tech", "start_date": due},
        }
        with patch.object(server, "llm_answer", side_effect=fake_model):
            status, result = self.post_chat(payload)
            self.assertEqual(status, 200)
            self.assertEqual(result["response_mode"], "B")
            self.assertIn("review", result["answer"].lower())
            self.assertIsNotNone(result["proposal"])
            proposed_event = result["proposal"]["events"][0]
            self.assertEqual(proposed_event["date_basis"], "建议日期")
            self.assertEqual(result["profile"]["start_date"], due)

            # Before confirmation, the client still submits an empty confirmed calendar.
            follow_up = {
                "messages": [
                    {"role": "user", "content": "Please create my relocation plan."},
                    {"role": "assistant", "content": result["answer"]},
                    {"role": "user", "content": "What is the first step?"},
                ],
                "calendar": {"confirmed": [], "pending": result["proposal"]["events"]},
                "profile": result["profile"],
            }

            def answer_question(*_args):
                return {"response_mode": "C", "answer": "Confirm the reporting details with HR.", "calendar_intent": "none", "operations": [], "profile_updates": []}

            with patch.object(server, "llm_answer", side_effect=answer_question):
                status, follow_up_result = self.post_chat(follow_up)
            self.assertEqual(status, 200)
            self.assertIsNone(follow_up_result["proposal"])

            # The explicit confirm action is represented by moving pending -> confirmed.
            confirmed = {
                "messages": [
                    {"role": "user", "content": "Please create my relocation plan."},
                    {"role": "assistant", "content": result["answer"]},
                    {"role": "user", "content": "What is the first step?"},
                    {"role": "assistant", "content": follow_up_result["answer"]},
                    {"role": "user", "content": "Move my viewing to Friday."},
                ],
                "calendar": {"confirmed": [proposed_event], "pending": None},
                "profile": result["profile"],
            }
            status, _ = self.post_chat(confirmed)
            self.assertEqual(status, 200)

    def test_invalid_messages_are_rejected_by_http_api(self):
        request = Request(
            self.url,
            data=json.dumps({"messages": []}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)

    def test_request_boundary_rejects_wrong_content_type_and_cross_origin(self):
        url = self.url
        body = json.dumps({"messages": [{"role": "user", "content": "hello"}]}).encode()
        for headers, expected in (
            ({"Content-Type": "text/plain"}, 415),
            ({"Content-Type": "application/json", "Origin": "https://attacker.example"}, 403),
        ):
            request = Request(url, data=body, headers=headers, method="POST")
            with self.subTest(expected=expected), self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, expected)

    def test_chat_request_body_limit_is_enforced(self):
        request = Request(
            self.url,
            data=b" " * 200_001,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 413)

    def test_security_headers_are_present(self):
        with urlopen(self.url.replace("/api/chat", "/health"), timeout=5) as response:
            self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
            self.assertEqual(response.headers.get("Referrer-Policy"), "no-referrer")

    def test_demo_mode_generates_a_reviewable_plan_without_model_call(self):
        due = (shanghai_today() + timedelta(days=21)).isoformat()
        payload = {
            "messages": [{"role": "user", "content": "Create a relocation plan from my saved profile."}],
            "profile": {"company_location": "Zhangjiang Hi-Tech Park", "start_date": due},
            "calendar": {"confirmed": [], "pending": None},
        }
        with patch.dict(os.environ, {"DEMO_MODE": "1"}), patch.object(server, "llm_answer", side_effect=AssertionError("demo mode must not call a model")):
            status, result = self.post_chat(payload)
        self.assertEqual(status, 200)
        self.assertEqual(result["response_mode"], "B")
        self.assertIsNotNone(result["proposal"])
        self.assertEqual(len(result["proposal"]["changes"]), 3)
        self.assertIn("fictional sample profile", result["answer"].lower())

    def test_demo_mode_does_not_persist_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            feedback_path = Path(directory) / "feedback.jsonl"
            request = Request(
                self.url.replace("/api/chat", "/api/feedback"),
                data=json.dumps({"rating": "helpful", "response_mode": "C"}).encode(),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with patch.dict(os.environ, {"DEMO_MODE": "1"}), patch.object(server, "FEEDBACK_PATH", feedback_path):
                with urlopen(request, timeout=5) as response:
                    result = json.load(response)
            self.assertEqual(result, {"ok": True, "stored": False})
            self.assertFalse(feedback_path.exists())

    def test_demo_html_has_isolated_demo_storage_configuration(self):
        with patch.dict(os.environ, {"DEMO_MODE": "1"}):
            with urlopen(self.url.replace("/api/chat", "/"), timeout=5) as response:
                html = response.read().decode()
        self.assertIn("window.RELOCATION_DEMO_MODE=true;", html)


if __name__ == "__main__":
    unittest.main()
