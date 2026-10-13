# FollowUpIQ demo script (target 2:30, hard limit 3:00)

## Before recording (10 minutes)
1. Shift the demo dates so "today" looks current: `python -m app.cli.seed --rebase-demo` against the production database (see [deployment.md §6](deployment.md#6-before-you-submit-or-record-the-demo)).
2. Wake the API: open `https://<render-app>/health` until it returns `{"status":"ok"}`, then load the web app once.
3. Browser at about 1440×900, zoom 100%, bookmarks bar hidden, a clean profile (no extensions in view). Close other tabs.
4. Recorder: Loom or OBS, mic check, cursor highlighting on. Have the two snippets below ready to paste.
   - Snippet A (draft edit), appended to Rahul's draft: ` I can also walk you through it on a quick call today.`
   - Snippet B (new chat for Vikram): `Two of my clients have confirmed. Please send a quotation for 5 band sealers, we need delivery within 2 weeks.`

## Script

| Time | Do | Say |
|---|---|---|
| 0:00–0:15 | Show the dashboard as it loads. | "A packaging-equipment company with five reps keeps leads in Excel and WhatsApp, and good leads go cold because nobody follows up. FollowUpIQ is one screen that tells each rep who to follow up with today, and what to say." |
| 0:15–0:35 | Point at the **Overdue** section, then the counts bar. Open **Viewing: Priya Sharma**, then switch back to All reps. | "Overdue follow-ups are always first, in red with the number of days, then today's, then upcoming. These counts are filters. Each rep can view just their own queue." |
| 0:35–1:05 | Search "Rahul" and open **Rahul Mehta**. Point to **Why Hot** and the follow-up date, then the conversation ending in the dashed **AI draft** bubble. | "Rahul asked for a quote for two pouch fillers to order this month, and we promised it but haven't sent it. The agent tagged him Hot and explains why with evidence from the chat. Because he's waiting on us, he's due now even though we last spoke two days ago." |
| 1:05–1:30 | Paste snippet A at the end of the draft bubble → **Save draft** (the label changes to "Edited by you") → **Copy** → **Mark as sent**. Show the lead leaving Overdue and **Undo** in the bar. | "The draft sits right where I'd reply, as the next message in the chat. I can tweak it, copy it into WhatsApp, and mark it as sent. Nothing is sent automatically: it records what I sent, and the follow-up date moves forward straight away. If I clicked by mistake, Undo stays right there." |
| 1:30–2:00 | Search "Vikram" and open **Vikram Joshi** (Warm). Click **Log chat** in the bar, keep Buyer, paste snippet B → **Log chat**. Wait for "Reading the latest chat and redrafting…" → **Tag changed: Warm → Hot**, the new date and draft. | "When something new happens, I log the chat. The agent re-reads the conversation: Vikram now wants a quote for five machines within two weeks, so he's Hot, due today, with a fresh draft, all within a few seconds." |
| 2:00–2:20 | Point to **Why Hot**, open **Show evidence**, and point to "Analysed by Gemini". | "Under the hood, Gemini reads the chat and extracts signals like intent, timeline, and whether the buyer is waiting. Fixed rules then decide Hot, Warm or Cold and the date, so tags are consistent and explainable. Drafts that invent prices or promises are rejected, and if a model or key fails it falls back to others, or to a clearly labelled rule-based result." |
| 2:20–2:30 | Return to the full queue. | "So every rep opens one screen, sees who to contact first, and has the message ready. Next I'd add WhatsApp and Excel import so nothing is typed twice. Thanks." |

## If something goes wrong while recording
- **Cold start** ("Waking up the server…"): wait, or cut that part of the video. The app is fine.
- **Gemini is slow or rate-limited:** "Reading the latest chat and redrafting…" can take 10–20 s. Keep talking over it, or edit the pause out. If it shows "Rule-based (AI unavailable)", click **Retry analysis** and mention the fallback. That is a feature worth showing.
