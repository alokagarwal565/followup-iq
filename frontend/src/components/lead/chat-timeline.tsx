import { CheckCheck, MessagesSquare } from "lucide-react";
import { Fragment } from "react";
import { businessDay, formatDateOnly, formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Message } from "@/lib/types";

export function ChatTimeline({
  messages,
  buyerName,
  repName,
  timeZone,
}: {
  messages: Message[];
  buyerName: string;
  repName: string;
  timeZone: string;
}) {
  if (messages.length === 0) {
    return (
      <div className="flex gap-2 rounded-lg border border-dashed px-4 py-4 text-sm text-muted-foreground">
        <MessagesSquare aria-hidden className="mt-0.5 size-4 shrink-0" />
        <p>
          No chat history yet. This lead came in without a conversation; use Log chat to add the
          first one.
        </p>
      </div>
    );
  }

  const days = messages.map((message) => businessDay(message.sent_at, timeZone));
  return (
    <ol className="space-y-2" aria-label="Conversation">
      {messages.map((message, index) => {
        const day = days[index];
        const showDay = index === 0 || day !== days[index - 1];
        const fromRep = message.sender_type === "rep";
        return (
          <Fragment key={message.id}>
            {showDay && (
              <li
                aria-hidden
                className="flex items-center gap-3 py-1 text-xs text-muted-foreground"
              >
                <span className="h-px flex-1 bg-border" />
                {formatDateOnly(day)}
                <span className="h-px flex-1 bg-border" />
              </li>
            )}
            <li className={cn("flex", fromRep ? "justify-end" : "justify-start")}>
              <div
                className={cn(
                  "max-w-[85%] rounded-lg border px-3 py-2 text-base leading-relaxed",
                  fromRep ? "border-primary/20 bg-selected" : "bg-card",
                )}
              >
                <p className="sr-only">
                  {fromRep ? repName : buyerName}, {formatDateOnly(day)}{" "}
                  {formatTime(message.sent_at, timeZone)}:
                </p>
                <p className="break-words whitespace-pre-wrap">{message.body}</p>
                <p
                  aria-hidden
                  className="mt-1 flex items-center justify-end gap-1 text-xs text-muted-foreground"
                >
                  {message.origin === "draft_sent" && (
                    <>
                      <CheckCheck className="size-3.5" />
                      Marked sent via FollowUpIQ ·
                    </>
                  )}
                  {formatTime(message.sent_at, timeZone)}
                </p>
              </div>
            </li>
          </Fragment>
        );
      })}
    </ol>
  );
}
