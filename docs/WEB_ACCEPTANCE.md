# Web Acceptance Checklist

Use this checklist for the active browser product. Record browser/version, viewport, test date, and issues for each run. Use synthetic profile data.

## Launch, layout, and navigation

- [ ] Open the local or candidate web build; no blank page, console-breaking error, clipped control, or horizontal overflow.
- [ ] Verify desktop and narrow mobile widths, browser zoom, long English labels, keyboard-open composer, scrolling, and sticky/fixed navigation.
- [ ] Move between Assistant, Plan, and Profile; active navigation and displayed page remain in sync.
- [ ] Check loading, empty, offline, backend-error, and long-response states; errors explain recovery without falsely indicating success.

## Profile and local persistence

- [ ] Save and edit work location, first work day, target move-in date, rent budget, commute preference, and housing preference.
- [ ] Clear a previously saved field and confirm it is removed rather than silently restored.
- [ ] Refresh/reopen the browser and verify profile, conversation, confirmed plan, completion flags, and pending draft behave as documented.
- [ ] Verify privacy messaging is visible and no sensitive identifier or payment data is requested.

## Agent planning and calendar safety

- [ ] Ask for a relocation plan from known profile facts; response is in English and distinguishes current information, next steps, dates, prerequisites, completion criteria, and evidence/official verification path.
- [ ] Generate a plan and verify it remains a proposal; no event enters confirmed Plan before explicit confirmation.
- [ ] Dismiss a proposal and verify confirmed items remain unchanged.
- [ ] Propose additions, updates, and deletions against existing events; only actual changes appear in the review, and dates/actions are clear.
- [ ] Confirm the proposal; verify the candidate plan appears in Plan and survives refresh.
- [ ] Ask an unrelated follow-up while a proposal is pending; verify the draft remains reviewable.
- [ ] Test unknown dates, hard-deadline conflicts, and dependency/date changes; verify uncertainty/risk is explicit and hard deadlines are not silently shifted.
- [ ] Mark an event complete, reopen it, and verify the completion state persists.

## Language, sources, and privacy

- [ ] Verify active visible labels, placeholders, date labels, errors, proposal titles, and assistant responses are English-only, allowing proper names and source titles when necessary.
- [ ] Verify source names/links/statuses are readable and listing samples, commute estimates, and pending verification are not presented as verified/live facts.
- [ ] Inspect browser network requests: no API key is sent; only the intended recent conversation, profile, and calendar context is transmitted.
- [ ] Disable network and send a message, then restore network; verify recovery does not create duplicate confirmed events.
- [ ] Confirm the backend only returns proposed changes and the user action is required to update confirmed state.

## Portfolio demo mode

- [ ] Start with `DEMO_MODE=1`; `/health` reports demo mode and no API key is required.
- [ ] A fresh demo browser gets the fictional sample profile/calendar under demo-specific storage keys; normal app storage is neither read nor overwritten.
- [ ] Compare-area and plan prompts work deterministically; the plan remains a proposal until confirmed.
- [ ] Confirm no model-provider call occurs and feedback is not written to a server file.
- [ ] Reset demo clears only demo storage and restores the fictional seed.

## Accessibility basics

- [ ] Complete core navigation, form editing, chat submission, proposal review, and confirmation using keyboard only.
- [ ] Verify visible focus, meaningful accessible names/labels, logical focus order, and no keyboard trap.
- [ ] Check text contrast and browser text zoom; ensure dynamic loading/error/proposal states are announced or otherwise discoverable.

## Execution log

| Field | Value |
| --- | --- |
| Status | Partial local demo acceptance; full checklist remains open |
| Browser / version | Codex In-app Browser; engine version not exposed |
| Viewport / OS | Narrow mobile viewport 390 × 844; host OS macOS |
| Build / commit | Local English web prototype; working tree |
| API environment / model | Local `DEMO_MODE=1`; no model calls |
| Tester / date | Codex-assisted check, 2026-09-30 |
| Issues | Launch and Assistant/Plan/Profile navigation checked. Demo plan stayed pending; dismiss left confirmed calendar unchanged. Narrow Profile view showed no horizontal overflow or navigation obstruction. No browser console errors; the development server returned a harmless 404 for the browser's automatic `/favicon.ico` request. Keyboard-only, offline/error recovery, accessibility, and desktop acceptance remain untested. |
