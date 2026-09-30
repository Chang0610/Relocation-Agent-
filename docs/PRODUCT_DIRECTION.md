# Product Direction: Relocation Assistant as a Web Agent

**Decision:** The English edition is a focused, web-first AI agent for planning a Shanghai relocation for work. It is not a general-purpose agent builder, and the active delivery target is not a WeChat mini program.

## What the agent does

The agent uses the user's stated relocation context and the English evidence pack to organize next steps: what to do, when, prerequisites, completion criteria, uncertainty, and official verification paths. It can propose calendar changes, but the user must review and confirm them before they become part of the confirmed plan.

The agent provides information organization and planning support only. It does not submit forms, make appointments, act as the user, pay fees, make legal or medical determinations, or guarantee an outcome.

## Product boundary

In scope for the web product:

- English chat grounded in the English PRD and Shanghai knowledge materials.
- Relocation profile and user-controlled plan/calendar.
- Source-aware task proposals with explicit uncertainty and confirmation before writes.
- Responsive browser experience suitable for desktop and mobile web.

Out of scope for the current product direction:

- A platform for users to create arbitrary agents or workflows.
- WeChat mini-program release or device acceptance.
- Autonomous external actions, transactions, applications, or bookings.
- Public cloud deployment before authentication, data isolation, abuse controls, and privacy operations are designed and implemented.

## Source and compatibility policy

The supplied source PRD and research package are preserved in the owner's development workspace, but intentionally omitted from this curated public-release copy. This release contains the runtime English retrieval data needed by the web app. The Chinese product and its knowledge/PRD sources remain separate and untouched.

## Web acceptance principles

- The core workflow works in a browser at desktop and narrow mobile widths.
- All active user-facing product copy and model answers are English-only, apart from proper names, source titles, and official names that have no reliable English equivalent.
- The user can review a proposed plan before confirming it; a dismissed proposal does not mutate confirmed events.
- Evidence quality and uncertainty remain visible; estimates are not represented as live or verified facts.
- The interface reports unavailable API/network states honestly and never implies an action succeeded when it did not.

## Current implementation boundary

The existing browser prototype and API provide a useful foundation, but state is browser-local and the API is a localhost development service without accounts or server-side user isolation. The project is not yet a production cloud web agent. See [Architecture](ARCHITECTURE.md), [Web Acceptance](WEB_ACCEPTANCE.md), and [Release Checklist](RELEASE_CHECKLIST.md) for gaps and gates.
