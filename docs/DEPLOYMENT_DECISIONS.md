# Deployment Decisions — Portfolio Demo Selected; Provisioning Pending

This document records decisions for the English web edition. **The owner selected Option A (portfolio/demo deployment) and accepted Render as the deployment target.** A local Render Blueprint is prepared at `render.yaml`; no Render account, cloud service, database, or paid service has been created. The app remains local-only until the owner connects a Git provider and explicitly reviews/applies the Blueprint.

## First decision: demo or real-user pilot?

### Option A — portfolio/demo deployment

- Use synthetic/resettable data only; do not collect or retain real users' relocation profiles or chat history.
- Keep profile, calendar, and chat history in the browser as they are today.
- Deploy the web app/API behind HTTPS with server-side model secrets and strict usage limits.
- Skip accounts and server-side user data for the first public demo. State clearly that the demo is not for personal data.
- This is the smallest next step for a résumé/portfolio showcase, but it is not a multi-user production launch.

### Option B — real-user pilot

- Require an account before saving profile, conversation, or plan data server-side.
- Use managed authentication and a managed PostgreSQL database, with a `user_id` owner on every user-data row.
- Verify access tokens in the Python API and enforce tenant scoping on every read/write; add database row-level security as defense in depth.
- Provide account deletion and data export/deletion workflows, retention rules, privacy disclosure, and backup/restore procedures before inviting real users.
- Obtain a privacy/data-location review before selecting a hosting region or processing real relocation profiles. A cloud region setting controls data location but is not itself proof of legal compliance.

## Provisional technical recommendation

If the goal later becomes a real-user pilot, the proposed default is:

| Layer | Proposal | Why it fits this codebase |
| --- | --- | --- |
| Browser | Keep the current vanilla HTML/CSS/JS web client; use same-origin calls to the Python API | Avoid a frontend rewrite while adding production foundations |
| Authentication + database | Supabase Auth + managed Postgres, initially email-based sign-in; store profile, confirmed plan, pending proposal, and chat history in separate user-owned rows | One managed service provides account identity and relational storage; Postgres suits plans and event dependencies |
| Application/API hosting | Render web service in Singapore, serving the browser app and Python API from one origin | Render lists Singapore as an available region and supports Python services; same-origin avoids a separate browser CORS setup |
| Data region | Singapore is only a provisional performance candidate, not an approved residency decision | Both hosting candidates offer Singapore; choose only after defining intended users and data-location/privacy requirements |
| User data | Start with the minimum required fields; store no government IDs, payment information, or detailed addresses; define explicit retention and deletion | Matches existing product safety constraints and reduces exposure |

For the selected portfolio-demo milestone, `render.yaml` proposes a free Singapore-region web service with `DEMO_MODE=1`, a `/health` check, and automatic deploys disabled. Singapore is a suggested initial region, not a data-residency/compliance determination. Render's free service availability and spin-down behavior are acceptable only for a portfolio showcase.

The API must verify a Supabase-issued JWT's signature, issuer, audience, and expiry. Every persistence operation must be scoped to the verified token subject, not a client-supplied `user_id`. If a privileged database credential is used server-side, it bypasses ordinary user-level database policies; keep it out of the browser and compensate with strict API authorization and tested database policies. Supabase's own guidance calls for RLS and correct grants on exposed tables, and warns that adding policies alone does not revoke grants.

## Alternatives considered

- **Clerk + Render + a separate Postgres provider:** polished hosted sign-in, but identity and application data are split across vendors. This project still needs its own database tenant enforcement and billing/data deletion integration.
- **Firebase Auth + Google Cloud Run/Firestore:** cohesive Google Cloud stack and mature auth, but would introduce a document database/Google deployment path that is less aligned with the current Python + relational task/calendar model.
- **Self-managed authentication:** avoids an auth-vendor dependency, but adds password/session security, email delivery, recovery, and abuse-prevention work. Not recommended as the first production step for this project.

## Cost envelope (indicative, USD)

For the provisional real-user stack, current published entry pricing suggests about **$32/month before model usage, domain, taxes, or optional email delivery**: Supabase Pro from $25/month and a small Render web service from $7/month. This is an indicative floor, not a quote; actual usage, backups, storage, bandwidth, provider plan changes, and account location can change it. Supabase Free can be used for development, but projects may pause after a week of inactivity and the free tier does not include automatic backups. Recheck provider pricing immediately before creating resources.

## Remaining gates before deployment

Do not create the public service or persist real-user data until:

1. The owner has pushed this repository to a Git provider, connected the repository, and reviewed the Render Blueprint proposal, including the Singapore region and public visibility.
2. HTTPS, free-tier limits, access-log/retention behavior, and the synthetic-data-only disclaimer are acceptable.
3. A future real-user pilot has separately defined intended user geography, data-location/privacy review, sign-in preference, and retention/deletion rules.

Since Option A and Render are now selected, continue with the demo slice and local/public-readiness checks without adding accounts or a user-data database. If/when a real-user pilot is approved, the next engineering step will be schema and migration design plus auth/API boundary tests—not immediate cloud provisioning.

## Sources checked

- [Supabase regions and data residency](https://supabase.com/docs/guides/platform/regions)
- [Supabase pricing](https://supabase.com/pricing)
- [Supabase Row Level Security guidance](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase JWT guidance](https://supabase.com/docs/guides/auth/jwts)
- [Render regions](https://render.com/docs/regions)
- [Render pricing](https://render.com/pricing)
