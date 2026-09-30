# Web Product Release Checklist

This is a staged release gate. Passing local prototype checks does not imply production readiness.

## Incremental progress

- [x] Step 1 — local API request boundary: bounded JSON bodies, JSON-object/content-type validation, same-authority browser `Origin` check, baseline security response headers, and HTTP regression coverage. This reduces accidental browser/API exposure but does not make the service safe for public deployment.
- [x] Step 2 — portfolio demo host selected and local Render Blueprint prepared; no cloud service has been created. Account-backed storage remains out of scope.
- [ ] Remaining deployment, privacy, observability, web-acceptance, and release gates below.
- [x] Portfolio demo slice: `DEMO_MODE=1`, fictional seed, isolated browser-storage keys, model calls and feedback persistence disabled; public binds are blocked unless demo mode is active.
- [x] Render Blueprint prepared with demo mode, health check, no secrets/database, and automatic deploys disabled. The owner must connect a Git provider and review/apply the Blueprint before a public service exists.

## Product and evidence

- [x] Confirm the web-first product scope in [Product Direction](PRODUCT_DIRECTION.md); keep the original supplied PRD and Chinese edition unchanged.
- [ ] Re-verify policy, price, commute, and service-entry sources; record verified dates and applicability.
- [ ] Keep estimates, listing samples, unresolved research gaps, and official service links clearly distinguished.
- [ ] Review active UI strings, prompt paths, errors, templates, and sample content for English-only output (except proper names/source titles where needed).
- [ ] Confirm the agent never claims to have submitted, booked, paid, or changed a confirmed schedule before the user completes the relevant action.

## Web acceptance and regression

- [ ] Complete the browser checklist in [WEB_ACCEPTANCE.md](WEB_ACCEPTANCE.md) on desktop and narrow mobile widths.
- [ ] Run deterministic PRD scenario, HTTP integration, browser behavior, persistence, and Python syntax tests.
- [ ] Run one opt-in live API smoke test using synthetic data only; record model/date and inspect that no secret is logged.
- [ ] Validate local-state recovery, proposal confirmation/dismissal, cancellation, hard deadlines, and dependent tasks.
- [ ] Review API schema changes against the active browser client.
- [ ] Complete accessibility checks for keyboard navigation, focus visibility, labels, contrast, and screen-reader announcements.

## Before public cloud deployment

- [ ] Connect the repository in Render, review the proposed Singapore-region free service and host logging/retention behavior, then explicitly apply the Blueprint.
- [ ] Choose account/session requirements and a data retention/deletion policy before any real-user pilot (not needed for synthetic demo mode).
- [ ] Implement authentication/authorization and server-side user isolation before storing user data server-side.
- [ ] Add HTTPS, secure secret storage, rate/spend limits, request-size limits, abuse controls, monitoring, health checks, backups, and incident response.
- [ ] Review privacy disclosures and data flows, including profile/chat context sent to the configured model provider.
- [ ] Add a deployment pipeline, environment separation, rollback, and production smoke/health checks.
- [ ] Do not expose the current localhost development API publicly.

## Demo and handoff

- [x] Provide a resettable synthetic demo profile and scripted demo flow without exposing an API key.
- [x] Capture permission-safe screenshots from the local demo build; see [screenshots](screenshots/).
- [x] Document known limitations; do not claim guaranteed policy outcomes, measured commute values, live rent prices, or actions done on the user's behalf.

## Explicitly not an active release gate

WeChat AppID registration, WeChat domain allowlisting, and physical-device sign-off are outside this web-only portfolio release.
