# FollowUpIQ

**Know who to follow up with. Know what to say.**

A lead follow-up agent with a one-screen web app for a small B2B packaging-equipment company (5 sales reps). It reads each lead and its WhatsApp chat, tags the lead **Hot / Warm / Cold** with a one-line reason, sets the **next follow-up date**, and **drafts the next message**. The screen puts today's follow-ups first, makes overdue ones impossible to miss, and lets a rep edit the draft, mark it as sent, and log new chats or leads. The agent then updates itself.

Built for the Gushwork Forward Deployed Engineer take-home. The requirements, as understood, are in the [BRD](docs/BRD.md).

| Deliverable | Where |
|---|---|
| Live app | *Added after deployment* (see [deployment runbook](docs/deployment.md)) |
| Code | This repository |
| Video (≤ 3 min) | Script: [docs/demo-script.md](docs/demo-script.md) |
| Short note | [docs/technical-note.md](docs/technical-note.md) |

> **Demo only:** all data is fictional. There is no login, by design of the assignment, so please don't enter real customer information.

---

## What it does

- **Follow-up queue:** **Overdue → Due today → Upcoming → No follow-up**, most urgent first.
  - Overdue rows are red-tinted with an alert icon and the text "3d overdue". Colour is never the only signal.
  - The counts (Overdue / Due today / Hot / All active) double as one-click filters.
  - Rep selector ("Viewing: Priya Sharma"), search, keyboard shortcuts (`j`/`k`, `/`, `n`).
- **Lead workspace, laid out like a chat:** the reason card ("Why Hot") with expandable evidence, the follow-up date and why, and AI status with Re-analyse. Below it is the conversation, ending in the **AI draft as the next, unsent message**, with the actions pinned underneath like a messaging composer. On desktop the most urgent lead opens automatically next to the queue.
- **Draft composer:**
  - Edit and save. Version-checked, so concurrent edits are never silently lost.
  - **Copy**, then **Mark as sent**. **Undo** stays in the composer bar for 10 minutes. Nothing is sent to WhatsApp; the app records it.
  - A newer AI suggestion never overwrites a rep's edit; it is offered alongside.
- **Light and dark** follow the system setting, plus an increased-contrast variant; every colour pair is verified for both appearances. Touch screens get 44 px targets.
- **Log chat / Add lead:** new information is saved first, then the agent re-reads the lead and updates the tag, date and draft within seconds ("Tag changed: Warm → Hot").
- **Resilient AI:**
  - Model fallback plus API-key fallback, bounded by a timeout and an attempt budget.
  - Invented prices, discounts or delivery promises in drafts are rejected and re-asked.
  - If Gemini is down, the last good analysis stays visible. Never-analysed leads get a clearly labelled **rule-based** result with a Retry.

Out of scope, per the assignment: login, real WhatsApp sending, payments.

## How the agent decides

Gemini **reads** the chat and returns structured signals. Deterministic rules then **decide**, so tags are explainable, testable and can't be talked into "Hot" by a message in the chat.

| Rule | Tag | When |
|---|---|---|
| C1 | Cold | Not interested, bought elsewhere, not a fit, or asked not to be contacted |
| C2 | Cold | 3+ follow-ups unanswered and silent for 21+ days |
| C3 | Cold | No conversation and no contact for 30+ days |
| H1 | Hot | Clear buying intent (quote / demo / negotiation / ordering) **and** a ≤ 30-day timeline or active evaluation **and** a reply within 14 days |
| W1–W4 | Warm | Everything else (interest without timeline, postponed, evaluating, new lead) |

**Follow-up date, in priority order:**
1. Do-not-contact: no date.
2. **The buyer asked something and is waiting:** due that day, whatever the tag.
3. A promise in the chat ("call me in January"), **verified by its exact quote** and dated from the message it appears in.
4. Cadence: Hot +1 day, Warm +3, Cold +14 or +90.

Dates are calendar days in the business timezone (Asia/Kolkata). Full rules: [BRD §6](docs/BRD.md#6-business-rules).

## Architecture

```
Next.js 16 (Vercel) ──HTTPS/JSON──▶ FastAPI (Render) ──SQL──▶ Postgres (Supabase)
  TanStack Query                     domain rules · services          leads · conversations
  no secrets                         BackgroundTasks analysis         messages · drafts
                                            │
                                            ▼ google-genai
                                     Gemini (model × key fallback)
```
The browser only talks to the API. The API owns the database and every Gemini call. Details, decisions and the task tracker: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md). Requirements: [docs/BRD.md](docs/BRD.md).

```
backend/   FastAPI app (app/domain = pure rules, app/ai = Gemini, app/services, app/api, app/cli), SQL migrations, pytest
frontend/  Next.js App Router app (components/queue, components/lead), Vitest + Playwright
docs/      BRD, implementation plan, design review, deployment runbook, technical note, demo script
```

## Local setup

**Prerequisites:** Python 3.12, Node 22+, a Postgres database (Supabase, Neon or local) and Gemini API keys.

```powershell
# Backend
cd backend
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install uv
.venv\Scripts\python -m uv pip sync requirements.txt requirements-dev.txt
copy .env.example .env          # then fill in DATABASE_URL, TEST_DATABASE_URL and the Gemini keys
.venv\Scripts\python -m app.db.migrate
.venv\Scripts\python -m app.cli.seed
.venv\Scripts\python -m app.cli.analyze --pending
.venv\Scripts\python -m app.cli.serve --port 8000   # http://localhost:8000/docs

# Frontend (second terminal)
cd frontend
npm install
copy .env.example .env.local    # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev                     # http://localhost:3000
```
macOS/Linux: use `.venv/bin/python` and `cp`. On Linux you can also run `uvicorn app.main:build_app --factory --no-access-log`. On Windows, `app.cli.serve` supplies the selector event loop that async psycopg needs.

`DATABASE_SCHEMA=app_dev` keeps a local copy isolated inside a shared database.

### Environment variables
All variables are documented, with placeholders only, in [backend/.env.example](backend/.env.example) and [frontend/.env.example](frontend/.env.example). The important ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres (Supabase **session pooler**, port 5432) |
| `GEMINI_API_KEY`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3` | Key slots, tried in order |
| `GEMINI_MODEL_HEAVY` / `_FALLBACK_HEAVY` / `_FAST` / `_FALLBACK_FAST` | Model chain (default `3.6-flash → 3.8-flash → 3.5-flash-lite → 3.1-flash-lite`) |
| `BUSINESS_TZ` | Defines "today" (default `Asia/Kolkata`) |
| `CORS_ORIGINS` | Exact allowed web origins |
| `NEXT_PUBLIC_API_BASE_URL` | API URL for the web app (public, build-time) |

## Tests and quality gates

| Command | What it checks |
|---|---|
| `cd backend; .venv\Scripts\python -m pytest -q` | 202 tests: rules, AI schema/guards/fallback, services, API, DB schema gate. DB tests use `TEST_DATABASE_URL` in a throwaway schema |
| `.venv\Scripts\python -m ruff format --check . ; ruff check . ; mypy app` | Formatting, lint, strict types |
| `cd frontend; npm test -- --run` | 51 component/unit tests (run in a US timezone to catch date bugs) |
| `npm run lint ; npx tsc --noEmit ; npx prettier --check . ; npm run build` | Lint, types, format, production build |
| `npm run contrast` | WCAG AA contrast for every colour pairing, in light and dark |
| `npm run gen:api:check` | Frontend API types match the backend's OpenAPI schema |
| `npx playwright test` | End-to-end rep journey + axe accessibility (light and dark) + security headers. Starts its own stack with a fake AI in an isolated schema |
| `.venv\Scripts\python -m app.cli.smoke` / `app.cli.eval` | **Live** Gemini check per model × key / tag accuracy on the sample chats (uses quota; manual) |

Last live evaluation: **22/22** sample leads tagged as expected.

## Deployment
Step by step: [docs/deployment.md](docs/deployment.md) (Supabase → Render via `render.yaml` → Vercel → CORS → smoke checks → rollback).

## Security notes
- Gemini keys and the database URL live only in the backend environment. The browser bundle was scanned and contains no secrets.
- Logs carry `lead_id` and request ids only: no names, phones, message text, keys or query strings.
- Input validation at the API boundary. Parameterised SQL with escaped search wildcards. Chat text is passed to the model as untrusted data, and model output is never executed.
- Per-client rate limits protect the AI budget on this public, login-free demo. In-memory state suits the single instance.
- Not hardened for real customer data: there is no authentication by design.

## Known limitations and what's next
- No login or per-rep permissions, by design. Anyone with the link can edit demo data.
- Free tiers: a 30–60 s cold start after idle; Gemini quotas are per Google Cloud project.
- Chats are logged by hand. **Next:** WhatsApp export / Excel import, a manual snooze, an "Open in WhatsApp" prefilled link, and an owner view of per-rep follow-up discipline.
