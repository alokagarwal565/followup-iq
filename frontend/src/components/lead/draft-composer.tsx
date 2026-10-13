"use client";

import { Ban, Check, Copy, Info, MessageSquarePlus, Undo2 } from "lucide-react";
import { useEffect, useState, type KeyboardEvent, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  useAcceptSuggestion,
  useSaveDraft,
  useSendDraft,
  useUndoSend,
} from "@/hooks/use-lead-mutations";
import { useUnsavedGuard } from "@/hooks/use-unsaved-guard";
import { ApiError, api } from "@/lib/api";
import { formatDateTime, formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Draft, Lead } from "@/lib/types";

const MAX_LENGTH = 1000;
// The counter is noise until it matters, so it only appears near the limit.
const COUNTER_FROM = 800;

function statusLabel(draft: Draft, dirty: boolean, timeZone: string): string {
  if (dirty) return "Unsaved changes";
  if (draft.status === "edited") return "Edited by you";
  if (draft.status === "sent")
    return draft.sent_at ? `Sent ${formatDateTime(draft.sent_at, timeZone)}` : "Sent";
  return "AI draft · check before sending";
}

interface Props {
  lead: Lead;
  draft: Draft;
  timeZone: string;
  /** Lead header and reason card, shown above the conversation. */
  top?: ReactNode;
  /** The conversation; the draft is rendered as the next message after it. */
  thread?: ReactNode;
  onLogChat?: () => void;
}

/**
 * The draft is presented as the next, not-yet-sent message at the end of the conversation, with
 * its actions pinned below like a chat composer: the rep reads the thread and replies in place.
 */
export function DraftComposer({ lead, draft, timeZone, top, thread, onLogChat }: Props) {
  const [text, setText] = useState(draft.body);
  // The server version the rep's text is based on; rep writes are checked against it.
  const [base, setBase] = useState({ body: draft.body, version: draft.version });
  const [conflict, setConflict] = useState(false);
  const [updatedInBackground, setUpdatedInBackground] = useState(false);
  const [dismissedSuggestion, setDismissedSuggestion] = useState<string | null>(null);
  const [composingAfterSend, setComposingAfterSend] = useState(false);
  const dirty = text !== base.body;

  const guard = useUnsavedGuard();
  useEffect(() => guard.setDirty(dirty), [dirty, guard]);
  useEffect(() => () => guard.setDirty(false), [guard]);

  // Server refreshes never clobber what the rep is typing; they only replace an untouched draft.
  // Adjusting state while rendering (keyed on the last version seen) avoids an extra effect pass.
  const [seenVersion, setSeenVersion] = useState(draft.version);
  if (draft.version !== seenVersion) {
    setSeenVersion(draft.version);
    if (dirty) {
      setUpdatedInBackground(true);
    } else {
      setText(draft.body);
      setBase({ body: draft.body, version: draft.version });
      setUpdatedInBackground(false);
      setComposingAfterSend(false);
    }
  }

  const save = useSaveDraft(lead.id);
  const send = useSendDraft(lead.id);
  const undo = useUndoSend(lead.id);
  const accept = useAcceptSuggestion(lead.id);
  const busy = save.isPending || send.isPending || accept.isPending || undo.isPending;
  const firstName = lead.name.split(" ")[0];

  const onConflictOrError = (error: unknown, action: string) => {
    if (error instanceof ApiError && error.code === "version_conflict") {
      setConflict(true);
      return;
    }
    toast.error(
      error instanceof ApiError ? error.message : `Couldn't ${action}. Please try again.`,
    );
  };

  const saveWith = (version: number) =>
    save.mutate(
      { body: text, version },
      {
        onSuccess: (saved) => {
          setBase({ body: saved.body, version: saved.version });
          setText(saved.body);
          setConflict(false);
          setUpdatedInBackground(false);
          // No toast: the label switching to "Edited by you" is the confirmation, in place.
        },
        onError: (error) => onConflictOrError(error, "save the draft"),
      },
    );

  const saveMineAnyway = async () => {
    try {
      const latest = await api.lead(lead.id);
      saveWith(latest.draft.version);
    } catch {
      toast.error("Couldn't load the latest draft. Please try again.");
    }
  };

  const reloadDraft = () => {
    setText(draft.body);
    setBase({ body: draft.body, version: draft.version });
    setConflict(false);
    setUpdatedInBackground(false);
  };

  const undoSend = () =>
    undo.mutate(undefined, {
      onSuccess: (restored) => {
        setText(restored.draft.body);
        setBase({ body: restored.draft.body, version: restored.draft.version });
        setComposingAfterSend(false);
        toast.success("Undone. The draft is back.");
      },
      onError: () => toast.error("Undo is no longer available."),
    });

  const markSent = () =>
    send.mutate(
      { body: text.trim(), version: base.version },
      {
        onSuccess: (detail) => {
          setText(detail.draft.body);
          setBase({ body: detail.draft.body, version: detail.draft.version });
          setComposingAfterSend(false);
          toast.success(`Marked as sent to ${firstName}.`, {
            duration: 10_000,
            action: { label: "Undo", onClick: undoSend },
          });
        },
        onError: (error) => onConflictOrError(error, "mark the message as sent"),
      },
    );

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied. Paste it into WhatsApp.");
    } catch {
      toast.error("Couldn't copy. Select the text and copy it manually.");
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      if (dirty && !busy) saveWith(base.version);
    }
  };

  const suggestion =
    draft.suggested_body && draft.suggested_body !== dismissedSuggestion
      ? draft.suggested_body
      : null;
  const alreadySent = draft.status === "sent" && !dirty;
  const showBubble = !lead.do_not_contact && (!alreadySent || composingAfterSend);
  const pendingNextDraft = alreadySent && lead.analysis_status === "pending";

  return (
    // The composer spans the whole workspace so its bar can stay sticky at the bottom of the
    // visible area at every size. Only "tall" windows pin the top and scroll the thread alone.
    <div className="flex min-h-full flex-col gap-4 tall:h-full tall:min-h-0">
      {top && <div className="shrink-0 space-y-4">{top}</div>}
      <div
        data-thread-scroll
        // In the pinned layout the top fade is a scroll-edge cue under the reason card.
        className="relative flex-1 space-y-3 pb-4 tall:min-h-0 tall:overflow-y-auto tall:[mask-image:linear-gradient(to_bottom,transparent,black_1.5rem)] tall:pt-3 tall:pr-2"
      >
        {thread}

        {lead.do_not_contact && (
          <div className="flex gap-2 rounded-lg border bg-muted px-4 py-3 text-sm text-muted-foreground">
            <Ban aria-hidden className="mt-0.5 size-4 shrink-0" />
            <p>
              The buyer asked not to be contacted, so there is no follow-up or draft for this lead.
            </p>
          </div>
        )}

        {suggestion && !lead.do_not_contact && (
          <section
            aria-label="New suggestion from Gemini"
            className="ml-auto max-w-[85%] space-y-2 rounded-lg border border-primary/40 bg-selected px-4 py-3 text-sm"
          >
            <p className="font-medium">Gemini suggested a new draft after the latest chat.</p>
            <p className="whitespace-pre-wrap text-foreground">{suggestion}</p>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => accept.mutate(draft.version)} disabled={busy}>
                Use new draft
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setDismissedSuggestion(suggestion)}>
                Keep mine
              </Button>
            </div>
          </section>
        )}

        {alreadySent && !composingAfterSend && !lead.do_not_contact && (
          <div className="ml-auto flex max-w-[85%] flex-wrap items-center justify-end gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <Check aria-hidden className="size-4 text-success" />
              {draft.sent_at ? `Sent at ${formatTime(draft.sent_at, timeZone)}.` : "Sent."}
              {pendingNextDraft && " The agent is drafting the next follow-up…"}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setText("");
                setComposingAfterSend(true);
              }}
            >
              Write another message
            </Button>
          </div>
        )}

        {showBubble && (
          <div className="ml-auto max-w-[85%] min-w-[min(100%,18rem)]">
            <div className="rounded-lg border border-dashed border-draft-border bg-draft px-3 pt-2 pb-1 focus-within:ring-2 focus-within:ring-ring">
              <label
                htmlFor={`draft-${lead.id}`}
                className="flex items-center justify-between gap-3 text-xs font-medium text-muted-foreground"
              >
                <span>Next message</span>
                <span className="font-normal">{statusLabel(draft, dirty, timeZone)}</span>
              </label>
              <textarea
                id={`draft-${lead.id}`}
                value={text}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={onKeyDown}
                maxLength={MAX_LENGTH}
                rows={Math.min(8, Math.max(3, Math.ceil(text.length / 60)))}
                placeholder="Write the next message"
                aria-describedby={`draft-help-${lead.id}`}
                className="mt-1 block w-full resize-y bg-transparent text-base leading-relaxed text-foreground outline-none placeholder:text-muted-foreground"
              />
              {text.length >= COUNTER_FROM && (
                <p className="pb-1 text-right text-xs text-muted-foreground tabular-nums">
                  {text.length}/{MAX_LENGTH}
                </p>
              )}
            </div>
            <p
              id={`draft-help-${lead.id}`}
              className="mt-1.5 text-right text-xs text-muted-foreground"
            >
              Nothing is sent to WhatsApp. Copy it, send it from your phone, then mark it as sent.
            </p>
          </div>
        )}

        {updatedInBackground && !conflict && (
          <p className="ml-auto flex max-w-[85%] flex-wrap items-center justify-end gap-1.5 text-xs text-muted-foreground">
            <Info aria-hidden className="size-3.5" />
            The draft was updated in the background. Your edits are kept.
            <button type="button" className="underline underline-offset-2" onClick={reloadDraft}>
              Load the new draft
            </button>
          </p>
        )}
        {conflict && (
          <div
            role="alert"
            className="ml-auto max-w-[85%] space-y-2 rounded-lg border border-destructive/40 bg-card px-4 py-3 text-sm"
          >
            <p>This draft changed since you opened it.</p>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={reloadDraft}>
                Reload draft
              </Button>
              <Button size="sm" onClick={saveMineAnyway} disabled={busy}>
                Save mine anyway
              </Button>
            </div>
          </div>
        )}
      </div>

      <div
        className={cn(
          // Sticky against the scrolling workspace, so the actions stay in view (and in thumb reach)
          // however long the conversation is.
          "sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center gap-2 border-t bg-background/95 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur lg:mx-0 lg:px-0",
        )}
      >
        {onLogChat && (
          <Button variant="outline" size="lg" onClick={onLogChat}>
            <MessageSquarePlus aria-hidden />
            Log chat
          </Button>
        )}
        {draft.can_undo && alreadySent && (
          <Button
            variant="ghost"
            size="lg"
            onClick={undoSend}
            disabled={busy}
            aria-label="Undo marking as sent"
          >
            <Undo2 aria-hidden />
            Undo
          </Button>
        )}
        {!lead.do_not_contact && (
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <Button variant="ghost" size="lg" onClick={copy} disabled={!text.trim()}>
              <Copy aria-hidden />
              Copy
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => saveWith(base.version)}
              disabled={!dirty || busy}
            >
              Save draft
            </Button>
            <Button size="lg" onClick={markSent} disabled={!text.trim() || busy || alreadySent}>
              Mark as sent
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
