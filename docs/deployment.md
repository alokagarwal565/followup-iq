# FollowUpIQ deployment runbook

Supabase (database) → Render (API) → Vercel (web). Follow the steps in order; each ends with a check. Nothing in this repo deploys automatically.

> **Never paste secrets into chat tools, commits or tickets.** They go only into `backend/.env` (local) and the Render / Vercel dashboards.

## 0. Prerequisites
- The code is pushed to a GitHub repository (owner's step).
- Accounts: Supabase, Render, Vercel, Google AI Studio (Gemini keys).
- Locally: Python 3.12 with `backend/.venv` installed (see README → Local setup).

## 1. Supabase (database)

1. **Project settings → Data API:** keep **Data API off** and **automatic RLS on**. FollowUpIQ never uses the REST API; the backend connects directly with SQL.
2. **Copy the Session pooler connection string:** click **Connect** (top bar) → **Session pooler** and copy the URI. It looks like
   `postgresql://postgres.<project-ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres`
   - Use the **session pooler (port 5432)**, not the direct `db.<ref>.supabase.co` host. The direct host is IPv6-only and Render cannot reach it. Also avoid the transaction pooler (6543).
   - **Percent-encode special characters in the password**: `?` → `%3F`, `@` → `%40`, `#` → `%23`, `/` → `%2F`, `:` → `%3A`.
   - Append `?sslmode=require`.
3. **Create the schema, seed the demo data and run the first analysis** from your machine. This writes to production, so do it deliberately:
   ```powershell
   cd backend
   $env:DATABASE_URL = "<session pooler URI from step 2>"   # this shell only
   Remove-Item Env:DATABASE_SCHEMA -ErrorAction SilentlyContinue
   .venv\Scripts\python -m app.db.migrate              # creates tables (safe to re-run)
   .venv\Scripts\python -m app.cli.seed                # 22 fictional leads (safe to re-run)
   .venv\Scripts\python -m app.cli.analyze --pending   # Gemini analysis, ~2 minutes, paced
   ```
   **Check:** the last command prints `Done: written=22` (or a few `fallback`; re-run `--pending` to retry those). In Supabase → Table editor you should see `leads` (22 rows), `messages`, `drafts` and `schema_migrations`.

## 2. Render (API)

1. Render dashboard → **New → Blueprint** → pick the GitHub repo. Render reads `render.yaml` (service `followupiq-api`, free plan, Singapore region, `rootDir: backend`).
2. When prompted for the `sync: false` variables, enter:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | The session pooler URI from step 1.2 |
   | `GEMINI_API_KEY`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3` | Your keys (slot order matters) |
   | `CORS_ORIGINS` | `http://localhost:3000` for now (updated in step 4) |
   | `CORS_ORIGIN_REGEX` | Leave empty, or `^https://followupiq-[a-z0-9-]+\.vercel\.app$` to allow Vercel previews |

3. Deploy. Render installs pinned dependencies (`--require-hashes`), runs migrations (a no-op after step 1.3), and starts uvicorn.

**Checks** (replace the host with your Render URL):
```bash
curl https://followupiq-api.onrender.com/health
# {"status":"ok"}
curl https://followupiq-api.onrender.com/api/v1/health/ready
# {"status":"ok","db":"ok","ai":"configured"}
curl "https://followupiq-api.onrender.com/api/v1/summary"
# {"overdue":…,"today":…,"hot":…,"active":21}
```
- **First request after 15 minutes idle takes 30–60 s:** that's the free-tier cold start, not a failure. The UI shows "Waking up the server…" while it happens.
- **`db` not ok:** recheck the pooler URI (user `postgres.<ref>`, port 5432, encoded password).
- **`ai` unconfigured:** the Gemini key variables are missing.

## 3. Vercel (web)

1. Vercel → **Add New → Project** → import the repo → set **Root Directory: `frontend`**. The framework is detected as Next.js; keep the default build command.
2. **Environment variable** (Production and Preview):
   `NEXT_PUBLIC_API_BASE_URL = https://followupiq-api.onrender.com` (no trailing slash).
   This is a public URL, not a secret. It is inlined at **build time**, so after changing it, **redeploy**.
3. Deploy and note the production URL, e.g. `https://followupiq.vercel.app`.

## 4. Connect them (CORS)
In Render → `followupiq-api` → Environment, set
`CORS_ORIGINS = https://followupiq.vercel.app,http://localhost:3000`
then save; Render redeploys. **Check:** the Vercel site loads the queue. If the browser console shows a CORS error, the origin doesn't exactly match (scheme, host, no trailing slash).

## 5. Smoke checklist (run on the live URLs)
1. `/health` → 200; `/api/v1/health/ready` → `db: ok`, `ai: configured`.
2. The dashboard opens; the **Overdue** section is visible within 10 s (allow up to 60 s on a cold start).
3. Open a lead: chat, tag, reason, follow-up date and draft are all visible.
4. Edit the draft → **Save draft** → reload → the edit is still there.
5. **Mark as sent** → the lead leaves Overdue → **Undo** restores it.
6. **Add lead** → it appears under *Due today* → its tag and draft arrive within about 15 s.
7. **Log chat** with a quote request → "Updating…" → the tag, date and draft change.
8. DevTools → Network: responses contain no keys or connection strings; requests go only to the Render origin.
9. Render → Manual Deploy → Restart → the data is unchanged.

## 6. Before recording the demo or showcasing
```powershell
cd backend
$env:DATABASE_URL = "<session pooler URI>"
.venv\Scripts\python -m app.cli.seed --rebase-demo   # shifts only demo rows so "today" looks current
```
**Optional keep-warm during active demos:** free Render services sleep after 15 minutes. A free external monitor (e.g. UptimeRobot or cron-job.org) can call `GET /health` every 14 minutes. 750 free instance-hours a month covers one service running continuously. Remove the monitor afterwards.

## 7. Rollback
- **Vercel:** Deployments → pick the previous deployment → **Promote to Production** (instant).
- **Render:** Events → choose an earlier deploy → **Rollback**, or redeploy a previous commit.
- **Database:** migrations are forward-only and additive. A bad migration is fixed with a new migration file, never by editing an applied one. The demo data can always be restored with `app.cli.seed`: it is idempotent and never deletes.

## 8. Free-tier notes
- **Render:** spins down after 15 minutes idle; cold start is 30–60 s.
- **Supabase:** free projects pause after about a week without activity; resume from the dashboard.
- **Gemini free tier:** rate limits apply **per Google Cloud project**, not per key. Keys from different projects add headroom; keys from the same project do not. When limits are hit, the app falls back across keys and models, and finally to a clearly labelled rule-based result.
