"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { LogChatForm } from "./log-chat-form";

/** Logging a chat is a short, focused task, so it opens over the conversation it extends. */
export function LogChatDialog({
  open,
  onOpenChange,
  leadId,
  leadName,
  timeZone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  leadId: string;
  leadName: string;
  timeZone: string;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Log chat</DialogTitle>
          <DialogDescription>
            Add what {leadName} and the rep said on WhatsApp or a call. The agent re-reads the
            conversation and updates the tag, follow-up date and draft.
          </DialogDescription>
        </DialogHeader>
        <LogChatForm leadId={leadId} timeZone={timeZone} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
