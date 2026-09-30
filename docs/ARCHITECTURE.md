# Architecture

## System overview

The active target is a focused web relocation agent. The current implementation is a browser prototype backed by a local Python API. The API is stateless: the browser sends recent conversation, profile, and calendar state with each request and persists accepted state in browser local storage.

```text
Browser web app ── POST /api/chat ── request validation ── English retrieval ── model adapter
      │                                                               │
      │                                                               ▼
      └─ browser-local profile/calendar/history ◀─ response ◀─ policy checks + proposal diff
                                              │
                                      user reviews and confirms
```

## Request lifecycle

1. The browser sends up to 30 recent user/assistant messages, a profile object, and `{ confirmed, pending }` calendar state.
2. `backend/server.py` validates the request, extracts explicit profile facts, and sanitizes legacy Chinese text for the English edition.
3. `backend/knowledge.py` retrieves English knowledge and area context from `data/`.
4. The configured model returns structured JSON. `backend/calendar_plan.py` normalizes operations, applies date/dependency rules, detects conflicts, and builds a proposal delta.
5. The API returns the answer, profile, and optional proposal. It does not write confirmed calendar state.
6. The browser renders changes for review. Confirming updates local confirmed events; dismissing a proposal leaves confirmed events unchanged.

## Data ownership and boundaries

- `data/` contains the runtime English retrieval data included in this curated release. Original supplied source documents and research files are intentionally kept out of this public-ready copy.
- Browser local storage is the only current user-state store. There are no accounts, cross-device sync, or server-side user database.
- The API key belongs only in server-side environment/secret storage; never place it in browser JavaScript, a request body, or a public repository.
- Calendar `date_basis` values are internal machine enums inherited from the existing API contract. They must not be shown as untranslated internal identifiers or Chinese UI copy.
- Knowledge entries preserve evidence status. Rental listings are samples, commute values are network estimates, and facilities need map verification.
- `DEMO_MODE=1` selects deterministic no-model replies, a demo-specific browser-storage namespace, a seeded fictional profile/calendar, and non-persistent feedback. This is an interactive portfolio-demo boundary, not real-user hosting.

## Current deployment boundary and production gaps

The backend uses Python's standard-library HTTP server and binds to `127.0.0.1` by default. The local API now enforces bounded JSON object requests, rejects browser POSTs with a cross-origin `Origin`, and emits baseline browser security headers. These are defense-in-depth for the prototype, not a substitute for an authenticated production gateway or a security review. The current prototype still has no production authentication, user isolation, durable server-side storage, rate limiting, abuse monitoring, TLS termination, backup/restore, or operational alerting. Do not bind it to a public interface or deploy it publicly as-is.

Before a real-user cloud launch, the project needs a deliberate production design and implementation for at least:

1. **Identity and isolation:** account/session model, authorization checks, and tenant-safe access to every profile, conversation, and plan.
2. **Persistence and privacy:** server-side data model, encryption, retention/deletion, export, backup, and incident procedures; update user-facing privacy disclosures.
3. **API security and reliability:** HTTPS termination, production request validation/size limits, a reviewed CSRF/CORS strategy, rate and spend limits, abuse controls, secrets management, timeouts, retries, and safe error responses. The local request-boundary checks do not complete this production gate.
4. **Agent quality and observability:** traceable retrieval citations, prompt/model versioning, structured-output validation, privacy-safe logs, evaluation set, failure metrics, and rollback strategy.
5. **Web readiness:** keyboard and screen-reader accessibility, responsive browser QA, browser compatibility, loading/offline/recovery behavior, and a deployment pipeline with health checks.

These are production readiness requirements, not claims that the current prototype already satisfies them. A provisional comparison and stack recommendation is recorded in [Deployment Decisions](DEPLOYMENT_DECISIONS.md); it is not approved or provisioned. The intended audience, hosting/data region, login requirements, and data retention policy must be confirmed before implementing account-backed storage or public deployment.

## Key modules

- `backend/server.py`: HTTP routes, model API adapter, response validation, and composition.
- `backend/knowledge.py`: English retrieval, constraints, and source/status filtering.
- `backend/calendar_plan.py`: calendar normalization, deduplication, dependency propagation, conflict checks, and proposals.
- `backend/profile.py`: profile validation and explicit-fact extraction.
- `preview/`: browser prototype for chat, Plan, and Profile.
