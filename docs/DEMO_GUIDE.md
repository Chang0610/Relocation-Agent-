# Portfolio Demo Guide

## Purpose and safety boundary

This mode is for an interactive résumé/portfolio showcase using a fictional Shanghai relocation scenario. It is not a production pilot and should not be used with real personal information.

When `DEMO_MODE=1`:

- No language-model provider is called. Answers and plan proposals are deterministic demonstration responses.
- The browser starts with a fictional sample profile and sample calendar, held in demo-specific `localStorage` keys. It never reads, overwrites, or clears the normal app's browser-storage keys.
- Profile, calendar, conversation, and feedback are not written to application-server files or a database. Requests reach the server transiently to render a response; the server handler does not log request bodies.
- Feedback is not collected. The UI tells the visitor this when clicked.
- The **Reset demo** control clears only the demo-specific browser keys and reloads the fictional seed.

Browser-local state persists in that visitor's browser until they reset it or clear site data. This mode does not promise deletion of infrastructure-level access metadata that may be retained by a future hosting provider; review provider logging and retention settings before public hosting.

## Run the demo locally

From the repository root:

```bash
DEMO_MODE=1 python3 backend/server.py
```

Visit `http://127.0.0.1:8765/`. No OpenAI key is needed. The app shows a fictional Alex Chen profile, sample confirmed schedule items, and prompt buttons for area comparisons, plan generation, and HR questions. Plan generation produces a deterministic draft that can be reviewed and confirmed in the browser.

## Render portfolio deployment

The repository includes [`render.yaml`](../render.yaml), a Render Blueprint for a free Singapore-region web service. It sets `HOST=0.0.0.0`, `DEMO_MODE=1`, and `/health` as the health check; it does not configure an API key, database, or other paid dependency. Automatic deploys are disabled. The server also refuses a non-loopback bind unless demo mode is enabled.

No Render service has been created or deployed. To deploy later, the owner must first push this curated release repository to a Git provider and connect it in Render. In the Render dashboard, select the repository and set **Blueprint Path** to `render.yaml`; review the proposed service, free-tier behavior, Singapore region, and public-demo privacy risks before applying it. Render services must be connected to a Git repository, so deployment is intentionally not performed from this local-only copy.

Before publishing a public portfolio deployment:

1. Confirm the Render service is in demo mode and `/health` reports `demo_mode: true`.
2. Verify the served HTML injects the demo-storage flag and that the demo namespace is isolated from normal browser storage.
3. Confirm the deployed app never calls a model provider and the feedback endpoint does not write a file.
4. Review HTTPS, account security, usage limits, health monitoring, access logs, retention, and request-body logging. Application code avoids body logging, but hosting-level policies are separate.
5. Run deterministic tests and the manual browser checklist with synthetic inputs. Do not invite visitors until HTTPS and host privacy/logging behavior have been checked.

Render's free services can spin down after inactivity and may have usage limits; this is suitable only for a portfolio demo, not an availability commitment. Use fictional inputs only, and do not publish a demo URL until the owner has reviewed those limitations.

The current repository has not been deployed publicly. Local runs still bind to localhost by default. The Render Blueprint is configuration only and does not create cloud resources.

## Known demo limitations

- Answers are scripted and are not evidence of live agent reasoning, model quality, or current policy verification.
- Suggested tasks/dates are illustrative, not deadlines. The visitor must still confirm every proposal.
- Browser state is local to one browser and is not synced across devices.
- There is no visitor identity, server-side profile store, account deletion workflow, or production SLA because this demo intentionally avoids real-user accounts and stored user profiles.
