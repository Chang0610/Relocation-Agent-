import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from run_qa_regression import report_exit_code


class QaRunnerTest(unittest.TestCase):
    def test_all_scenarios_must_pass_for_success_exit_code(self):
        report = {"cases": [{"status": "pass"}, {"status": "pass"}]}
        self.assertEqual(report_exit_code(report), 0)

    def test_review_status_fails_the_scenario_gate(self):
        report = {"cases": [{"status": "pass"}, {"status": "review"}]}
        self.assertEqual(report_exit_code(report), 1)

    def test_request_error_fails_the_scenario_gate(self):
        report = {"cases": [{"status": "error"}]}
        self.assertEqual(report_exit_code(report), 1)


if __name__ == "__main__":
    unittest.main()
