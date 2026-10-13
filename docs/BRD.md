# FollowUpIQ: Business Requirements Document

| | |
|---|---|
| Product | **FollowUpIQ**: AI Sales Follow-ups |
| Tagline | Know who to follow up with. Know what to say. |
| Status | Draft for review |
| Date | 12 Oct 2026 |
| Source of truth | The Gushwork FDE take-home assignment, summarised in §1–§2 and traced in §13 |
| Companion | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) covers how each requirement is built and tested |

---

## 1. Background

A small B2B company sells packaging equipment (pouch fillers, labelers, sealers and related machines) to manufacturers and distributors. Five sales reps handle all leads.

| Today | Consequence |
|---|---|
| Leads live in one Excel sheet; conversations happen in each rep's WhatsApp | No single view of a lead's status |
| Reps rely on memory to follow up | Promising leads go cold |
| The owner has no visibility of who is hot or who is waiting on a reply | Revenue leaks and no accountability |

The owner wants **one simple screen that tells each rep who to follow up with today, and what to say**.

## 2. Business objectives and success measures

| # | Objective | Success measure (maps to the reviewer's pass/fail checks) |
|---|---|---|
| O1 | The tool works reliably | The live link opens and the main flow runs with no errors ("It works") |
| O2 | The agent's judgement is trustworthy | The Hot/Warm/Cold tags and reasons make sense for the chats ("Agent is useful") |
| O3 | Reps save time writing messages | A rep could send the draft with small edits or none ("Drafts are usable") |
| O4 | Instant prioritisation | A rep knows who to contact today **within 10 seconds** of opening the app ("Screen is clear") |
| O5 | Focus | Only what was asked, done well, with no half-built extras ("Scope is right") |
| O6 | Explainability | The note and video clearly explain how it works and why ("You can explain it") |

## 3. Stakeholders and personas

| Persona | Goal | Key needs |
|---|---|---|
| **Sales rep** (5 people, e.g. *Priya Sharma*) | Clear today's follow-ups quickly | Their own queue, most urgent first; the chat context; a ready message they can copy into WhatsApp; a record that it was sent |
| **Owner** | Make sure no good lead goes cold | Overdue follow-ups that are impossible to miss; hot leads visible at a glance; all reps' queues in one place |
| **Reviewer** (Gushwork) | Judge the build in minutes | A public link with no setup, realistic data, and a visible agent update after adding a chat |

## 4. Scope

### In scope
1. Sample data: at least 20 fictional leads and at least 10 WhatsApp-style chats.
2. An agent that reads leads and chats, then tags each lead Hot, Warm or Cold with a one-line reason, sets the next follow-up date and drafts the next message.
3. A web screen with: today's follow-ups at the top, most urgent first; overdue follow-ups that stand out; a lead detail view (chat, tag, reason, date, draft); editing the draft; marking it as sent; adding a new lead or a new chat, after which the agent updates that lead.

### Out of scope (explicitly excluded by the assignment)
- Login, users and permissions
- Real WhatsApp sending or a WhatsApp integration
- Payments

### Deliberately deferred (listed as "what's next")
Excel/CSV import, a WhatsApp chat-export parser, a manual snooze/reschedule control, "Open in WhatsApp" pre-filled links, an owner analytics view, dark mode, per-rep login.

## 5. Functional requirements

Each requirement traces back to the assignment. Its acceptance criteria are the tests the requirement must pass.

### FR-01: Sample leads *(Step 1)*
At least 20 fictional leads, each with name, company, phone, source and last contact date, spread across the 5 reps.
- **AC1** The database holds ≥ 20 leads after seeding, and re-running the seed never duplicates them.
- **AC2** All data is clearly fictional. Phones are in the synthetic `+91 90000 0XXXX` range, with no real people or companies.
- **AC3** Sources vary: Excel sheet, WhatsApp, Website, Referral, Trade show, IndiaMART.

### FR-02: Sample chats *(Step 1)*
At least 10 short WhatsApp-style chats between a rep and a buyer.
- **AC1** ≥ 10 chats of 3–9 messages, each with a clear sender (rep or buyer) and chronological timestamps.
- **AC2** Together the chats cover: explicit purchase intent, a quote or demo request, a defined timeline, technical evaluation, a price objection, a follow-up commitment, a delayed project, weak interest, no response after several attempts, a lost or disqualified lead, and a do-not-contact request.
- **AC3** At least one lead has **no chat** (an Excel-only lead) and the app still works for it.

### FR-03: The agent reads leads and chats *(Step 2.1)*
- **AC1** Analysis uses the lead's fields and its full chat history (the most recent 40 messages if a chat is longer).
- **AC2** The agent runs when a lead is created, when a chat is added, after a message is marked as sent, and when a rep presses **Re-analyze**. It never runs just because a page is opened.

### FR-04: Hot / Warm / Cold tag with a one-line reason *(Step 2.2)*
- **AC1** Every analyzed lead has exactly one tag (Hot, Warm or Cold) and a reason of 160 characters or fewer that cites evidence from the chat.
- **AC2** The tag follows the business rules in section 6.1. The AI interprets the chat, and the rules decide the tag.
- **AC3** Reasons never invent facts such as a budget, an agreed date, a requirement or a commitment.

### FR-05: Next follow-up date *(Step 2.3)*
- **AC1** Every lead has a next follow-up date, except a lead whose buyer asked not to be contacted (section 6.2, rule 1).
- **AC2** The date follows the rules in section 6.2 and is explained in a short follow-up reason.

### FR-06: Draft the next follow-up message *(Step 2.4)*
- **AC1** Every contactable lead has a draft WhatsApp message that follows the guidelines in section 6.4.
- **AC2** The draft never invents prices, discounts, specifications, delivery dates or stock availability.

### FR-07: Today's follow-ups at the top, most urgent first *(Step 3)*
- **AC1** The queue is grouped as **Overdue → Due today → Upcoming → No follow-up**, and ordered within each group by the rules in section 6.3.
- **AC2** On a desktop screen, the first viewport shows the queue and the most urgent lead's details and draft with no scrolling.
- **AC3** A filter bar shows counts for *Overdue*, *Due today*, *Hot* and *All active*, and each count filters the queue.
- **AC4** A rep can switch the view to just their own leads, and the app remembers the choice.

### FR-08: Overdue follow-ups stand out *(Step 3)*
- **AC1** Overdue leads appear first, in their own group, with an alert icon, a red tint and text such as "3d overdue". Overdue is never shown by colour alone.
- **AC2** The browser tab title shows the number of leads needing action, e.g. "(7) FollowUpIQ".

### FR-09: Open a lead *(Step 3)*
- **AC1** The lead view shows contact details (name, company, phone, source, assigned rep), the tag, the reason with up to 3 evidence points, the next follow-up date with its reason, the full chat in order, and the draft.
- **AC2** The view has its own URL, so refresh, back and shared links all work.
- **AC3** It shows the analysis status: analyzed by AI, updating, rule-based (AI unavailable), or failed with a Retry button.

### FR-10: Edit the draft and mark it as sent *(Step 3)*
- **AC1** A rep can edit the draft and save it. The edit survives a refresh, and later AI updates never overwrite it silently: a new AI suggestion is offered alongside it instead.
- **AC2** **Mark as sent** records the message in the chat history (labelled "Marked sent via FollowUpIQ") and updates the last contact date and the next follow-up date immediately.
- **AC3** The UI makes clear that nothing is sent to WhatsApp. A **Copy** button supports the real workflow: copy, paste into WhatsApp, then mark as sent.
- **AC4** **Undo** is available for 10 minutes after marking as sent, as long as no newer message has been added.

### FR-11: Add a new lead or a new chat; the agent updates that lead *(Step 3)*
- **AC1** **Add lead** validates name, company, phone and source. A phone number that already exists is flagged and the rep can open the existing lead instead.
- **AC2** **Log chat** adds one or more messages (sender, text, optional time) to a lead.
- **AC3** After either action the lead shows "Updating…", and the tag, reason, date and draft refresh without reloading the page. If the tag changes, the change is visible (e.g. "Warm → Hot").
- **AC4** If the AI is unavailable, the new data is still saved and a Retry option appears.

### FR-12: Excluded features stay out *(Out of scope)*
- **AC1** No login, no WhatsApp sending and no payments exist anywhere in the product.

## 6. Business rules

### 6.1 Hot / Warm / Cold decision table
The AI reads the chat and extracts **signals**: intent, timeline, whether the buyer is evaluating, objections, disqualification, a do-not-contact request, whether the buyer is waiting on us, and any commitment. Deterministic rules then decide the tag. The first matching rule wins.

| Rule | Tag | Condition | Example |
|---|---|---|---|
| C1 | Cold | Buyer is not interested, bought elsewhere, is not a fit, or asked not to be contacted | "We've gone with another supplier." |
| C2 | Cold | 3 or more rep messages unanswered, and no buyer reply for 21+ days (or ever) | Three nudges over 4 weeks with no reply |
| C3 | Cold | No conversation at all, and no contact for 30+ days | An old Excel row |
| H1 | Hot | Clear buying intent (quote, demo, negotiation, ready to order) **and** (a timeline of 30 days or less **or** active evaluation) **and** a buyer reply within the last 14 days | "Send the quote, we want to order this month." |
| W1–W4 | Warm | Everything else: interest without a timeline (W1), a postponed project (W2), waiting on information (W3), a new lead with no conversation yet (W4) | "Share the spec sheet, we'll review." |

Guardrails:
- **Recent contact alone never makes a lead Hot. A short silence alone never makes it Cold.**
- When the evidence is thin, the tag stays conservative (Warm or Cold) and the reason says why.
- If the AI's own suggested tag disagrees with the rules, the rules win, and the reason and draft are regenerated to match.

### 6.2 Follow-up date rules
The rules are checked in this order:
1. **Do not contact**: no date, no draft. This is the only lead without a follow-up date.
2. **Buyer is waiting on us**: the last message is from the buyer and asks something. The follow-up is due **that same day**, so it is overdue if older. *Urgency is separate from intent, so a Warm lead can be the most urgent item today.*
3. **A commitment exists** (e.g. "call me after Diwali", "I'll send the quote Friday"): use that date. A missed commitment stays in the past and **shows as overdue**.
4. **Default cadence** from the last contact: Hot +1 day; Warm +3 days; Cold because unresponsive +14 days (a gentle close-the-loop message); Cold because lost +90 days (a polite check-in). A brand-new lead with no chat is due **on the day it was added**, so it goes overdue if nobody makes first contact. *A lapsed Cold cadence restarts from today instead of landing in the past.* Without this, stale cold leads would flood Overdue and push live Hot work down. Cold leads still go overdue through missed promises or unanswered buyer questions.

All dates are calendar days in the business timezone (**Asia/Kolkata** by default; configurable). "Overdue" means the follow-up date is before today, and "due today" means it equals today. Leads become overdue automatically at midnight.

### 6.3 Queue order
1. **Overdue**: oldest missed date first; then Hot, Warm, Cold.
2. **Due today**: buyers waiting on a reply first; then Hot, Warm, Cold; then the longest time since last contact.
3. **Upcoming**: nearest date first.
4. **No follow-up**: do-not-contact leads, collapsed.

Any remaining tie is broken by a fixed internal id, so the order never changes between page loads.

### 6.4 Draft message guidelines
- WhatsApp tone: friendly, professional and direct. Under 80 words, with no excessive enthusiasm.
- Address the buyer by first name and refer to the actual last topic.
- One clear next step or question.
- Mirror the buyer's language: if they write in Hinglish, reply in Hinglish.
- Never invent prices, discounts, specifications, delivery dates, stock or catalogue details.
- After repeated non-replies, no pressure: a short, polite close-the-loop message.
- No draft at all for a do-not-contact lead.

### 6.5 Draft states

| State | Meaning | Changes to |
|---|---|---|
| AI draft | Written by the agent, not yet touched by the rep | Edited by you (rep saves); Sent (mark as sent) |
| Edited by you | Rep's own text, protected from AI overwrite | Sent; AI draft (rep chooses "Use new draft") |
| Sent | Recorded as sent; appears in the chat | AI draft (the next suggestion arrives); back to the previous state on Undo (within 10 min) |
| None | Do-not-contact lead | — |

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Usability | Who to contact is clear within 10 seconds. Keyboard shortcuts (`j`/`k`, `/`, `n`). Works on a phone (360 px and up). |
| Accessibility | WCAG 2.2 AA target: visible labels, focus rings, text plus icon plus colour for every status, screen-reader announcements for analysis updates, 0 serious or critical automated axe violations. |
| Performance | The queue loads in under 1 s once the server is warm. An AI update typically lands in 3–15 s. The free-tier server can take 30–60 s to wake up, and the UI says so rather than looking broken. |
| Reliability | If the AI fails, all data is kept, the last good analysis stays visible and a Retry button appears. Model and API-key fallback is automatic and bounded. No analysis can stay stuck on "Updating…". |
| Data integrity | Changes are saved atomically. Duplicate clicks never create duplicate messages. Concurrent edits are detected rather than silently overwritten. |
| Security | AI keys and database credentials stay on the server only. Requests are rate-limited to protect the AI budget. The demo holds fictional data only. Logs never contain names, phone numbers or message text. |
| Timezone | One configurable business timezone. "Today" never depends on the viewer's computer clock. |
| Maintainability | Typed contracts end to end; the business rules are isolated and fully unit-tested; comments explain the reasoning behind non-obvious code. |

## 8. Edge cases (business-facing acceptance)

| Situation | Expected behaviour |
|---|---|
| Lead from Excel with no chat | Tagged Warm (new) or Cold (stale) with a reason saying there is no conversation yet; a short intro draft; due today if new. |
| Buyer asked a question and nobody replied | Shows as due today or overdue even if the lead is Warm. |
| Rep promised something and missed the date | Shows as overdue. |
| "Call me after Diwali" | The follow-up date is set to that date; an unclear or implausible date falls back to the default cadence. |
| Buyer asked not to be contacted | Tagged Cold, no date, no draft, with a notice in place of the message box. |
| Buyer writes in Hinglish | The draft is in Hinglish. |
| A buyer's message tries to manipulate the AI | It has no effect on the tag, because the rules decide; the rep always reviews the draft before sending. |
| AI is down or out of quota | Data is saved; the last good analysis stays; new leads get a clearly labelled rule-based result; Retry is available. |
| Rep is typing while the AI updates the draft | The rep's text is never replaced; the new suggestion is offered instead. |
| Two people edit the same draft | The second save is told the draft changed and can reload or keep their version. |
| Double-click on Add lead, Log chat or Mark as sent | Exactly one record is created. |
| Same phone number entered twice | Flagged as a duplicate, with a link to the existing lead. |
| Rep marks sent by mistake | Undo within 10 minutes. |
| The free server was asleep | A "Waking up the server…" message, then normal operation. |
| Demo data gets older between seeding and review | An operator command re-bases the sample dates so the demo still shows overdue, today and upcoming leads. |

## 9. Assumptions

1. A single company and a single timezone (India, IST). No multi-tenancy.
2. Reps copy the draft into WhatsApp themselves. The app records that it was sent but does not send it.
3. The five reps are a fixed list. Reassigning a lead between reps is enough; managing reps is not needed.
4. Gemini (Google) is the AI provider, under free or low-cost tiers.
5. Hosting: Vercel (web), Render (API), Supabase (Postgres), all on free tiers.

## 10. Constraints

- Delivery within the assignment window (36–48 hours).
- No login is allowed, so the public demo is open to anyone with the link.
- Free-tier limits: server sleep on Render, AI quotas per Google Cloud project, a small database connection budget.

## 11. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| The AI tags a lead wrongly | Trust lost ("Agent is useful" fails) | Rules decide the tag from extracted signals; every tag stores the rule that fired; an evaluation run over the sample chats compares expected and actual tags before submission |
| AI quota exhausted during the review | Analysis fails | Model and key fallback; rule-based fallback, clearly labelled; sample data analyzed in advance |
| The public demo is spammed | AI cost, messy data | Per-visitor rate limits; no delete feature; fictional data only |
| A cold start looks like an outage | "It works" fails | An explicit waking-up message; an optional keep-warm ping during the review window |
| Sample data looks stale on review day | Empty "today" queue | Demo date re-base command run just before submission |

## 12. Deliverables

| # | Deliverable | Owner |
|---|---|---|
| 1 | Live link (Vercel + Render + Supabase) | Built and documented by Claude; **deployed by the user** using `docs/deployment.md` |
| 2 | GitHub repository | Code prepared locally by Claude; **committed and pushed by the user** |
| 3 | Video, 3 minutes or less | Script by Claude (`docs/demo-script.md`); **recorded by the user** |
| 4 | Half-page note | `docs/technical-note.md` by Claude |

## 13. Traceability

| Assignment line | Requirement |
|---|---|
| ≥ 20 fake leads (name, company, phone, source, last contact) | FR-01 |
| ≥ 10 WhatsApp-style chats | FR-02 |
| Agent reads leads and chats | FR-03 |
| Tag Hot/Warm/Cold with a one-line reason | FR-04 |
| Next follow-up date | FR-05 |
| Draft the next message | FR-06 |
| Today's follow-ups at the top, most urgent first | FR-07 |
| Overdue follow-ups stand out | FR-08 |
| Open a lead: chat, tag, reason, draft | FR-09 |
| Edit the draft and mark it as sent | FR-10 |
| Add a lead or chat, and the agent updates the lead | FR-11 |
| Out of scope: login, WhatsApp sending, payments | FR-12 |
