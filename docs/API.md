# API Reference

The API is a local prototype contract, not a public production API. By default it listens on `127.0.0.1:8765`.

## `GET /health`

Returns service/configuration status without exposing credentials.

```json
{"ok": true, "llm_configured": true, "demo_mode": false, "model": "gpt-5.6-luna"}
```

With `DEMO_MODE=1`, the served HTML marks the browser demo namespace, `/api/chat` returns deterministic scripted responses without calling a model, and `/api/feedback` validates but does not persist ratings (`{"ok":true,"stored":false}`).

## `POST /api/chat`

Request JSON:

```json
{
  "messages": [
    {"role": "user", "content": "Please create a relocation plan."}
  ],
  "profile": {
    "company_location": "Zhangjiang Hi-Tech",
    "start_date": "2026-11-02",
    "move_deadline": "2026-11-01"
  },
  "calendar": {
    "confirmed": [],
    "pending": null
  }
}
```

Constraints: `messages` has 1–30 items; each item has role `user` or `assistant`, and content is at most 4,000 characters. The final message must be from the user. Requests over 200 KB are rejected. Profile fields are allow-listed by `backend/profile.py`.

The response includes:

- `answer`: user-facing English text.
- `answer_evidence` and `answer_sources`: evidence annotations and structured source references.
- `response_mode` and `quick_choices`: the interaction mode and optional short choices.
- `proposal`: `null` or a proposal containing a complete candidate `events` calendar and a `changes` delta. A proposal is never committed by the API.
- `calendar_clarifications`: possible duplicate or ambiguous changes to resolve.
- `profile`: the resulting sanitized profile.

Clients must persist accepted profile and calendar state themselves. To accept a proposal, replace the client's `calendar.confirmed` with `proposal.events` and set `calendar.pending` to `null`. To keep an unconfirmed proposal across another turn, send its events as `calendar.pending`; do not treat them as confirmed.

Calendar event dates use `YYYY-MM-DD`; times use `HH:MM`. The machine `date_basis` enum is one of `用户明确`, `建议日期`, or `日期待确认`; preserve it when sending events back to the API, but render its meaning in English.

## `POST /api/feedback`

Accepts `{ "rating": "helpful|inaccurate|missing", "response_mode": "A|B|C|D|E|unknown" }`. The current prototype writes only the rating/mode and timestamp to `data/answer_feedback.jsonl`; it does not include message content.

## Error responses

Malformed JSON or request data returns HTTP 400; oversized requests return 413; unknown paths return 404; model configuration or provider errors return 503. Never display raw server traces or credentials to end users.

## Operational warning

These routes currently have no authentication, authorization, account separation, CORS policy, or rate limiting. Keep the service local. Production deployment requires a security review and a protected HTTPS API gateway or equivalent controls.
