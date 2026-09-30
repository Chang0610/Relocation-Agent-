# Engineering Case Study

## Project

**Shanghai Relocation Agent — Full-Stack AI Web Application**

An English-language web prototype that combines a browser client, Python JSON API, local retrieval data, and an optional model adapter. The relocation use case provides realistic constraints; the engineering focus is request handling, evidence-aware response construction, safe state transitions, and testability.

## What I built

- Implemented the browser application in semantic HTML, CSS, and vanilla JavaScript, including chat, profile, calendar, local persistence, and proposal review flows.
- Built a Python standard-library HTTP API that validates request boundaries, extracts explicit profile updates, retrieves relevant English knowledge, invokes a model adapter, and returns structured responses.
- Added calendar operation normalization and validation for duplicate events, dependency-aware date changes, hard-deadline conflicts, and explicit review-before-write behavior.
- Implemented a deterministic demo mode that does not call a model, uses synthetic profile/calendar data, isolates its browser-storage namespace, and avoids server-side feedback persistence.
- Added GitHub Actions CI for deterministic Python, HTTP integration, frontend regression, and syntax checks; CI does not require secrets or incur model charges.

## Engineering decisions

### Proposal before persistence

The API treats model-suggested calendar operations as untrusted proposals. Backend validation computes a change set, and the browser only updates confirmed calendar state after explicit user confirmation. This separates suggestion generation from a state-changing action and makes the operation reviewable.

### Stateless API prototype

The browser sends the relevant profile, recent messages, and calendar state with each chat request; accepted state remains in browser storage. This keeps the prototype simple and avoids server-side storage of user profiles, but it does not provide accounts, cross-device sync, or multi-user data isolation.

### Deterministic testing boundary

Core tests use deterministic model doubles and local HTTP integration. Model-backed scenarios are opt-in, so routine regression is repeatable and does not require an API key or incur usage charges.

## Stack

- **Languages:** Python, JavaScript, HTML, CSS
- **Backend:** Python standard library HTTP server, JSON API, model adapter
- **Frontend:** vanilla JavaScript, browser local storage
- **Data:** curated English JSON retrieval dataset with source and evidence-status metadata
- **Tests / CI:** Python `unittest`, Node.js regression scripts, GitHub Actions

## Verification

The latest local deterministic run passed 138 Python tests, including local HTTP integration tests, and both Node.js frontend checks. CI runs these tests plus Python syntax compilation. It does not run the optional model-backed QA suite. The project is a local/demo prototype: desktop accessibility, full browser compatibility, and offline/error recovery acceptance are still open.

## Resume bullets

**Shanghai Relocation Agent | Full-Stack AI Web Application**

- Built a full-stack web app with a vanilla JavaScript client and Python JSON API, integrating profile state, English knowledge retrieval, model-backed responses, and calendar planning.
- Implemented a validated proposal workflow with dependency-aware date updates, duplicate prevention, hard-deadline safeguards, and explicit user confirmation before calendar state is persisted.
- Added a deterministic no-key demo mode and GitHub Actions CI; wrote 138 Python regression tests and Node.js frontend checks without requiring live model calls.

Describe this as a **full-stack prototype**, not a deployed or production-ready service. The source PRD and original Chinese edition are outside this curated release repository.

## Further work

- Complete accessibility, desktop, browser-compatibility, and offline/recovery acceptance.
- Add authentication, authorization, server-side persistence, and tenant isolation before supporting real users.
- Define privacy-safe observability, retention/deletion, rate/spend limits, deployment, and rollback processes before production deployment.
- Review the redistribution terms and attribution requirements for runtime knowledge and source records.
