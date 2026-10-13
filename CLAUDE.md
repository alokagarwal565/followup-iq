# CLAUDE.md: FollowUpIQ

Lead follow-up agent + web app for a B2B packaging-equipment sales team (Gushwork FDE take-home).
Authoritative docs: [docs/BRD.md](docs/BRD.md) (what and why) and [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) (how, task cards, tracker). Read the plan's tracker before starting work.

## Hard rules
- **No git write commands** (init, add, commit, push, gh repo). The owner handles version control.
- **No deployments** (Vercel, Render) and **no writes to a production database** without explicit owner approval.
- **Env files:** the backend reads only `backend/.env`, which the owner creates from `backend/.env.example`. Never create, copy, print or edit files that contain secrets.
- Out of scope: login, real WhatsApp sending, payments.

## Architecture
- `frontend/`: Next.js 16 App Router, strict TS, Tailwind 4, shadcn/ui, TanStack Query. It talks only to the backend. → Vercel
- `backend/`: FastAPI (async), Pydantic, psycopg 3 async pool with raw parameterized SQL, google-genai. → Render
- Database: Supabase Postgres via the **session pooler** (port 5432). Migrations are plain SQL in `backend/migrations/`.
- Gemini **extracts signals and writes prose**; `app/domain/rules.py` **decides** the tag, the follow-up date and the queue order.

## Commands (run from `backend/` or `frontend/`)
| Task | Command |
|---|---|
| Backend venv | `py -3.12 -m venv .venv` then `.venv\Scripts\python -m uv pip sync requirements.txt requirements-dev.txt` |
| Lock deps | `python -m uv pip compile requirements.in --universal --python-version 3.12 --generate-hashes -o requirements.txt` (same for `-dev`) |
| Backend gates | `python -m ruff format --check . ; python -m ruff check . ; python -m mypy app ; python -m pytest -q` |
| Run API (local) | `python -m app.cli.serve --port 8000` (selector loop for Windows); Linux: `uvicorn app.main:build_app --factory --no-access-log` |
| Migrate / seed | `python -m app.db.migrate` · `python -m app.cli.seed [--rebase-demo]` · `python -m app.cli.analyze --pending` |
| Live AI checks (cost quota) | `python -m app.cli.smoke` · `python -m app.cli.eval [--all] [--only key]` |
| API types | `python -m app.cli.openapi` then `cd ../frontend; npm run gen:api` |
| E2E | `cd frontend; npx playwright test` (own stack: fake AI, schema `e2e_frontend`, ports 8001/3001) |
| Frontend gates | `npx prettier --check . ; npm run lint ; npx tsc --noEmit ; npm test -- --run ; npm run build` |

Never run two pytest processes at once against `TEST_DATABASE_URL`. `DATABASE_SCHEMA` isolates a local copy (e.g. `app_dev`) inside a shared database; never point local runs at the production database without the owner's approval.

## Conventions
- **TDD:** write the failing test, watch it fail, write the minimal code, watch it pass. Never claim a pass without command output.
- **Comments explain why, not what:** business rules, edge cases, trade-offs, constraints. No narration and no TODOs unless actionable.
- API under `/api/v1`. Errors use `{"error":{"code","message","request_id"}}`. Request models use `extra="forbid"`.
- Logs use `event=name key=value` via `app.logging.get_logger`. Log `lead_id` only, never names, phones, message text or keys.
- Dates: `next_follow_up_date` is a business-TZ calendar day (`BUSINESS_TZ`, default Asia/Kolkata). Timestamps are UTC. The frontend uses `meta.today` from the server and never parses date-only strings with `new Date()`.
- Frontend API types are generated (`npm run gen:api`); never hand-edit `src/lib/api-types.ts`.
- When a task completes, update the tracker in `docs/IMPLEMENTATION_PLAN.md` in all three places (card header, Status bullet, tracker table + progress).

## Environment variable names
Backend: `ENV`, `LOG_LEVEL`, `BUSINESS_TZ`, `DATABASE_URL`, `DATABASE_SCHEMA`, `TEST_DATABASE_URL`, `CORS_ORIGINS`, `CORS_ORIGIN_REGEX`, `GEMINI_API_KEY`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`, `GEMINI_API_KEY_FALLBACKS`, `GEMINI_MODEL_HEAVY`, `GEMINI_MODEL_FALLBACK_HEAVY`, `GEMINI_MODEL_FAST`, `GEMINI_MODEL_FALLBACK_FAST`, `GEMINI_MODEL_CHAIN`, `GEMINI_REQUEST_TIMEOUT_SECONDS`, `GEMINI_ANALYSIS_DEADLINE_SECONDS`, `GEMINI_MAX_RETRIES`, `GEMINI_RETRY_BACKOFF_BASE_SECONDS`, `GEMINI_MAX_ATTEMPTS`, `GEMINI_FAKE`, `RATE_LIMIT_WRITES_PER_MIN`, `RATE_LIMIT_ANALYZE_PER_MIN`.
Frontend: `NEXT_PUBLIC_API_BASE_URL` (public URL only, inlined at build time).
File storage (`STORAGE_*`, `AWS_*`) is reserved and unused.

## Deployment
See `docs/deployment.md`. The owner runs it.
