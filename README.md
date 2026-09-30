# Shanghai Relocation Agent — Web Edition

An English-first web agent that helps people relocating to Shanghai for work organize a move into a safe, source-aware plan. It turns user context into ordered tasks, dates, prerequisites, completion criteria, evidence, official entry points, and a calendar proposal. The user remains in control: the agent does not submit applications, book appointments, pay fees, or guarantee outcomes, and calendar changes are saved only after confirmation.

This is a focused relocation assistant, not a generic platform for creating arbitrary agents. The current browser app is a local prototype, not a cloud-hosted production service.

## Product scope and source precedence

- The English web app is the active product direction. See [Product Direction](docs/PRODUCT_DIRECTION.md).
- The supplied source PRD/research package and the Chinese project remain in the owner's development workspace; they are intentionally not included in this curated public-release copy.
- This copy includes only the English web app, runtime English data, tests, demo documentation, and portfolio screenshots. The runtime data keeps its evidence-status labels.

## Project layout

- `preview/` — browser app prototype (chat, plan calendar, profile)
- `backend/` — local HTTP API, model adapter, English retrieval, and calendar proposal validation
- `data/` — runtime English knowledge, area data, and task templates
- `tests/` — deterministic API, scenario, and browser-state regression tests
- `docs/` — product direction, architecture, API, testing, web acceptance, and release guidance

## Run locally

For the portfolio demo, start the deterministic, no-model mode; it needs no API key:

```bash
DEMO_MODE=1 python3 backend/server.py
```

Open `http://127.0.0.1:8765/`. The demo seeds a fictional profile and sample calendar in a demo-only browser-storage namespace. It does not read or overwrite normal app storage, call a language model, persist chat/profile/feedback on the application server, or send feedback. Requests are processed transiently; use fictional information only. **Reset demo** clears only this app's demo browser state.

For local model-backed development, create `.env.local` from the example and add a server-side API key. Do not commit the key or place it in browser code.

```bash
cp .env.local.example .env.local
# Set OPENAI_API_KEY in .env.local
python3 backend/server.py
```

Open `http://127.0.0.1:8765/`. Without an API key, deterministic tests still run, but live chat is unavailable. The backend currently binds to localhost and is not ready for public deployment.

## Regression checks

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
node tests/test_frontend_english.cjs
node tests/test_frontend_persistence.cjs
python3 -m py_compile backend/*.py tests/*.py
```

Run the commands from this repository root. The HTTP integration suite binds a temporary loopback port; the test environment must permit local socket binding. The Python tests are deterministic and do not call a model. `tests/run_qa_regression.py` is a separate model-backed scenario suite and may incur charges.

See [Testing Guide](docs/TESTING.md) for coverage details. The opt-in live API smoke test makes one billable model request; do not run it as a repeated test loop.

## Evidence and safety

Policy, price, commute, and location claims retain their source status. Rental figures are listing samples rather than live quotes; commute figures are network estimates rather than measured trips; facilities require map verification. Sensitive identity and payment information should not be stored in the profile. Proposed schedule changes remain drafts until the user confirms them.

## Project documentation

- [Product Direction](docs/PRODUCT_DIRECTION.md)
- [Architecture and production gaps](docs/ARCHITECTURE.md)
- [Deployment decisions (proposal; no cloud resources created)](docs/DEPLOYMENT_DECISIONS.md)
- [API reference](docs/API.md)
- [Testing guide](docs/TESTING.md)
- [Web acceptance checklist](docs/WEB_ACCEPTANCE.md)
- [Portfolio demo guide](docs/DEMO_GUIDE.md)
- [Portfolio case study and resume-ready bullets](docs/PORTFOLIO.md)
- Portfolio screenshots: [`screenshots/`](docs/screenshots/)
- [Render Blueprint](render.yaml) (configuration only; no service has been created)
- [Release checklist](docs/RELEASE_CHECKLIST.md)
