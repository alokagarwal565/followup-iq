# Design review and revamp plan: FollowUpIQ

Method: the `apple-design` skill (`.claude/skills/apple-design`). FollowUpIQ is a **responsive web app** (Next.js), so per the skill's scope rules Apple's *principles and foundations* apply (accessibility, color, typography, layout, writing), but iOS/macOS platform conventions (menu bar, tab bars, settings window) do not. Sources: current build screenshots at 1440 px and 390 px, the token values in `globals.css`, measured control sizes, and the UI copy.

## Design review: FollowUpIQ dashboard

### Summary
**Thesis:** one screen that tells a rep who to message next and hands them the message. The queue and hierarchy are sound and contrast is measured, not guessed, but the look is a competent shadcn default: neutral slate, a generic blue, every section in a bordered card. Nothing in it says "WhatsApp follow-ups for a sales team". Overall rating: **Needs work** (no Critical findings, several High).

### Improvements
- **High: no dark appearance, no increased-contrast response.**
  - **What:** the app is light-only and ignores `prefers-color-scheme` and `prefers-contrast`.
  - **Why:** `color.md › Best practices`: "Make sure all your app's colors work well in light, dark, and increased contrast contexts." `dark-mode.md › Best practices`: "Avoid offering an app-specific appearance setting."
  - **Fix:** semantic tokens with dark values under `@media (prefers-color-scheme: dark)` and a stronger set under `prefers-contrast: more`. Follow the system setting only, with no in-app toggle. Contrast is verified by script for both appearances.
- **High: touch targets below the mobile default.**
  - **What:** measured at 390 px: Re-analyze 28 px tall, the copy-phone icon 28×28, the rep select 28, the dialog close 28×28, the Viewing select and Add another message 32.
  - **Why:** `accessibility.md › Mobility`: "iOS, iPadOS default 44x44 pt, minimum 28x28 pt." These sit at the minimum, not the default.
  - **Fix:** under `(pointer: coarse)` every button and select gets `min-height: 44px`, and icon buttons get `min-width: 44px`. Desktop keeps 28–32 px, which is above the macOS 28 pt default.
- **High: the draft and the conversation are visually unrelated.**
  - **What:** the draft sits in a card above the chat. A rep reads the reason, then the draft, then scrolls down to the chat that justifies it, so the most important thing (what to say next) is cut off from its context.
  - **Why:** `layout.md › Visual hierarchy`: "Group related items to clearly express related information or functions." `writing.md › Best practices`: "Consider each screen's purpose."
  - **Fix:** see Signature below. The draft becomes the next, unsent message at the bottom of the thread, with its actions pinned beneath it.
- **Medium: Undo lives only in a 10-second toast.**
  - **Why:** `accessibility.md › Cognitive`: "Minimize use of time-boxed interface elements… Prefer dismissing views with an explicit action."
  - **Fix:** keep the toast, and also show a persistent "Sent 4:05 pm · Undo" in the composer bar for as long as the server allows undo (`draft.can_undo`).
- **Medium: overdue tint on every row.**
  - **What:** six consecutive pink rows make the warning wallpaper and dilute it.
  - **Why:** `color.md › Best practices`: "Avoid using the same color to mean different things." Judgment: emphasis spent everywhere reads as emphasis nowhere.
  - **Fix:** keep the red section header, and move the signal into a red-tinted "3d overdue" chip with an icon on each row. Row backgrounds stay neutral; selection keeps its own tint.
- **Medium: generation feedback is generic.**
  - **Why:** `generative-ai.md › Outputs`: "Consider giving specific, reassuring feedback during generation… instead of 'Processing…'."
  - **Fix:** "Reading the latest chat and redrafting…".
- **Medium: AI output isn't framed for review.**
  - **Why:** `generative-ai.md › Inputs`: "Raise awareness about and minimize the chance of hallucinations."
  - **Fix:** the draft label reads "AI draft · check before sending". Edit, Re-analyse and Undo stay next to it (`generative-ai.md › Outputs`: "Make it easy for people to refine or revert generated results").
- **Medium: mixed spelling.**
  - **What:** "Analysed by Gemini", "Analyse now", "Analysing…" next to "Re-analyze".
  - **Why:** `writing.md › Best practices`: "Build language patterns. Consistency builds familiarity."
  - **Fix:** British spelling throughout ("Re-analyse"), matching the Indian English the reps and buyers write in.
- **Low: on mobile the header uses about 200 px before the first lead.**
  - **Fix:** two compact rows (brand + date + Add lead, then rep + search).

### Craft notes
- **High: templated, no point of view.** Slate neutrals, a generic blue accent and cards around everything: you could swap the logo and ship it as any SaaS admin. The product's own vernacular is the WhatsApp conversation, and that's where its identity should come from.
- **Remove one accessory:** the "Next message" card and the "Conversation" heading both go once the draft joins the thread. The always-visible character counter only appears near the limit.

### What works
- The queue order (Overdue → Today → Upcoming → No follow-up) and the server-sorted rows answer "who first" in seconds.
- Status is never color alone: icon + text + tint on tags and due states.
- Contrast is computed (23 pairs, all AA), focus rings are visible, and axe reports no serious or critical issues. Keep the contrast script as the gate.
- Selection persists in the split view (`split-views.md › Best practices`: "persistently highlight the current selection").

## Revamp plan

**Subject:** a 5-rep Indian B2B sales team whose real workplace is WhatsApp. The screen's single job is to clear today's follow-ups, one message at a time.

**Tokens (light / dark, verified by `npm run contrast`).**
- **Surface:** cool off-white / deep blue-grey. Cards are white / a slightly lifted dark.
- **Accent:** **deep teal**, the colour of WhatsApp-era chat chrome, used only for the primary action, selection and "today". It replaces generic blue and stays distinct from the Cold tag's blue.
- **Signals:** keep the Hot / Warm / Cold / Overdue hues, with dark variants (lighter foreground, deeper tint).
- **Increased contrast:** muted text and borders get stronger.

**Type:** Geist only (system-like, legible). Hierarchy through weight and color. Body text in chat bubbles and the draft stays at 16 px. `tabular-nums` for all dates and counts.

**Layout:** the queue stays as is. The workspace becomes a messaging layout: header and reason at the top, the thread scrolling in the middle, the composer pinned at the bottom.

```
Regular (≥1024 px)                                  Compact (<1024 px)
┌ Queue ─────────┬ Workspace ───────────────────┐   ┌ ← Queue   Rahul Mehta [Hot] ┐
│ [Overdue 6]…   │ Rahul Mehta [Hot]  Next lead → │  │ Shree Snacks · ☎ · Priya ▾ │
│ ⚠ Overdue (6)  │ Shree Snacks · ☎ · Priya ▾     │   │ Why Hot  ▸ details          │
│ Rahul · 2d ⚠   │ ┌ Why Hot ─────────────────┐  │   ├─────────────────────────────┤
│ Deepa · 2d ⚠   │ │ reason · due ⚠ 2d · ▸    │  │   │ buyer ▏…                    │
│ ─ Due today ─  │ └──────────────────────────┘  │   │            …▕ rep           │
│ Imran          │ thread (scrolls, newest last) │   │   ┊ Draft · not sent yet ┊  │
│ …              │  buyer ▏…                      │   │   ┊ Hi Rahul ji, …       ┊  │
│                │               …▕ rep           │   ├─────────────────────────────┤
│                │     ┊ AI draft · check first ┊ │   │ Log chat  Copy  [Mark sent] │
│                │     ┊ Hi Rahul ji, …         ┊ │   └─────────────────────────────┘
│                │ Log chat  Copy  Save [Mark as sent] │
└────────────────┴───────────────────────────────┘
```

**Signature:** *the draft is the next message in the conversation.* It renders as an outgoing bubble with a dashed outline, right-aligned after the last message, labelled "AI draft · check before sending". It's editable in place, and its actions sit in a bar pinned to the bottom like a chat composer. This belongs to this product and no other: the app's whole job is "what do I send next", and the answer now sits exactly where the rep will send it. Everything else stays quiet.

**Motion:** none added. The thread opens scrolled to the newest message, with no animation.

**Log chat** moves into a dialog opened from the composer bar ("a temporary, focused task", per `cross-platform.md`). That frees the workspace for reading and replying.

**Plan critique:** would the same plan suit a similar brief for a different product? The token change alone would, but the signature only makes sense for a message-drafting agent, so the plan stays. Conventions are kept: standard buttons, selects, a dialog, a split view and a list. Identity lives in color and in the one signature element.

**Order of work:** accessibility (targets, dark, contrast) → conventions/layout → craft (signature, overdue chip, copy) → polish. Then verify: unit + E2E tests, the contrast script for both appearances, axe at both viewports, and screenshots in light and dark.

## Implementation result (13 Oct)

Everything in the plan above shipped. Changes beyond it, found while building and checking screenshots:

| Change | Why |
|---|---|
| Toasts moved from bottom-right to top-centre, and the "Draft saved." toast was removed | The E2E run caught the toast **covering the pinned Mark as sent button** for about 4 s. The draft label changing to "Edited by you" is the in-place confirmation (`feedback.md › Best practices`: "Consider integrating status feedback into your interface"). |
| The pinned layout (header and reason fixed, only the thread scrolls) applies only to windows at least 1024 px wide **and** 800 px tall. Smaller windows scroll the whole workspace under a `sticky` composer bar | Reported on a 1080p laptop at 150% zoom (about 1280×607 CSS px): the reason card took the height, the thread shrank to 29 px and the draft was invisible. The header, reason, thread, draft and bar now share one sticky context, so the bar is always on screen and the draft is one scroll away. Regression test: `quality.spec.ts › short window`. |
| On wide screens Esc returns focus to the lead's queue row instead of closing the lead; the workspace pane is never empty | Esc used to clear the selection, leaving half the screen blank. Side by side, the queue is already visible, so there is nothing to go "back" to (`split-views.md › Best practices`: "persistently highlight the current selection"). When no lead is open (empty filter, deleted lead), the pane shows the day's workload with "Start with <most urgent lead>" and the shortcuts. Phones keep Esc = back to the queue. |
| Scroll panes are `position: relative` | Visually hidden (`sr-only`, absolute) headings inside a scroll pane escaped its clipping and stretched the page by 151 px, adding an outer scrollbar and blank space below the footer. |
| "Next lead" folded into the name row on wide screens | It had occupied an otherwise empty row. |
| Top fade on the scrolling thread | A scroll-edge cue (`layout.md › Visual hierarchy`) where older messages pass under the reason card. |
| "Write another message" after a send | A sent draft is no longer shown as an editable bubble that duplicates the sent message in the thread. |

**Verification:**
- `npm run contrast`: every pair passes in **light and dark**.
- Unit tests: 51 passed (4 new: persistent Undo, write another message, counter near the limit, draft rendered after the thread).
- Playwright: 10 passed, including axe with **0 serious/critical violations in dark** at 1440 and 390 px.
- Screenshots checked in both appearances at both widths.
- Measured touch targets: every button and select is ≥ 44 px under `pointer: coarse`.
