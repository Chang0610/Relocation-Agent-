# Testing Guide

## Deterministic regression checks

Run the full Python regression suite from the repository root. It includes PRD-derived scenarios, unit tests, and a local HTTP integration suite. The HTTP suite binds a loopback port, so the environment running it must permit local sockets. These tests use deterministic model doubles and do not call OpenAI:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
node tests/test_frontend_english.cjs
node tests/test_frontend_persistence.cjs
python3 -m py_compile backend/*.py tests/*.py
```

The current Python suite has 138 passing tests: 130 deterministic tests (including 27 English PRD scenarios and QA-runner exit-code checks) and 8 local HTTP integration tests. The frontend English behavior and persistence checks are separate Node.js tests. The HTTP suite exercises validation, structured proposal response, profile round-trip, and the confirmed/pending calendar contract. It verifies HTTP/API integration, not live language-model behavior.

`tests/run_qa_regression.py` is a separate, model-backed scenario runner that calls an already-running API at `http://127.0.0.1:8766`; its multi-turn relocation cases require the configured model and may incur charges. It is not part of unittest discovery. Its process now exits nonzero if any case is a request error or an assertion review. `DEMO_MODE=1` is unbilled but intentionally supports only scripted demo flows, so it is not expected to pass the full agent scenario set. For visual/manual browser testing, use [WEB_ACCEPTANCE.md](WEB_ACCEPTANCE.md).

## One-request live model smoke test

This optional test makes exactly one real request to the configured OpenAI API through `/api/chat`, using synthetic dates and a synthetic work location. It checks for a valid English plan proposal and does not print the response body or API key. It is billable at the configured model's current token rates.

1. Configure `OPENAI_API_KEY` in the environment or a local `.env.local` file. The runner never writes or prints the key.
2. Review the configured model and current API billing before running.
3. Explicitly opt in:

```bash
python3 tests/live_api_smoke.py --confirm-one-billable-call
```

If the test fails, it suppresses provider response bodies to avoid leaking user/provider data. Do not turn it into a high-volume test loop.

## Test status and limits

- The full unittest discovery command and frontend checks above passed during the latest regression repair.
- The live smoke test is a single request, not statistical evaluation of model quality.
- The separate API scenario runner and billable live smoke test are not implied by a passing deterministic suite; run them only when their service/configuration prerequisites are intentionally met.
- Any policy, price, or area research change requires source re-verification in addition to code tests.
- Passing automated tests does not imply production security, cloud readiness, or completed accessibility review.
