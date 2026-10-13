# FollowUpIQ: technical note

**What I built.** A lead follow-up agent with a one-screen web app for a 5-rep packaging-equipment seller. The queue shows Overdue → Due today → Upcoming, most urgent first, and overdue rows are marked with red text and an icon. Opening a lead shows its WhatsApp chat, a Hot/Warm/Cold tag with a one-line reason, the next follow-up date and a ready-to-send draft. Reps edit the draft, copy it to WhatsApp and mark it as sent (with Undo); nothing is sent automatically. Logging a new chat or adding a lead makes the agent re-read that lead and update its tag, date and draft within seconds. The stack is Next.js (Vercel), FastAPI (Render) and Postgres (Supabase), with 22 fictional leads and 12 chats.

**How it decides Hot/Warm/Cold.** Gemini reads the chat and returns structured signals: intent, timeline, evaluation, objections, disqualification, "buyer is waiting", and promised dates quoted word for word. Fixed rules then decide the tag:
- **Cold:** lost, no fit or do-not-contact; or 3+ unanswered follow-ups after 21+ days of silence.
- **Hot:** clear buying intent, a timeline within 30 days or active evaluation, and a reply in the last 14 days.
- **Warm:** everything else.

The follow-up date comes from the same rules. A waiting buyer is due today, a promise ("call me in January") is honoured if its quote really appears in the chat, and otherwise a cadence applies. The model writes the reason and the draft. Drafts that invent prices, discounts or delivery dates are rejected and re-asked. If Gemini fails, the system tries other keys and models, then keeps the last good result or shows a clearly labelled rule-based one.

**AI tools.** Gemini (3.6 Flash with Flash and Flash-Lite fallbacks) powers the agent at runtime. I built the app with Claude Code as a coding assistant: planning, test-first implementation and reviews. I checked its output against a live evaluation, where 22/22 sample tags matched, and against 200 backend, 47 frontend and Playwright end-to-end tests.

**What I'd build next.** Import of WhatsApp chat exports and the Excel sheet, so reps don't retype history. Then per-rep login and an owner view of follow-up discipline.
