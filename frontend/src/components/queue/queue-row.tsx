import { AlertCircle, Loader2, MessageCircleQuestion, TriangleAlert } from "lucide-react";
import type { MouseEvent } from "react";
import { TagBadge } from "@/components/tag-badge";
import { dueLabel, lastContactLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { LeadRow } from "@/lib/types";

function shortRep(name: string): string {
  const [first, last] = name.split(" ");
  return last ? `${first} ${last[0]}.` : first;
}

export function QueueRow({
  row,
  today,
  timeZone,
  selected,
  onSelect,
}: {
  row: LeadRow;
  today: string;
  timeZone: string;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const overdue = row.due_state === "overdue";
  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    // Keep native behaviour for new-tab clicks; otherwise select in place.
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    onSelect(row.id);
  };

  return (
    <li>
      <a
        href={`?lead=${row.id}`}
        onClick={onClick}
        aria-current={selected ? "true" : undefined}
        data-due={row.due_state}
        data-lead-id={row.id}
        className={cn(
          "block min-h-11 px-4 py-3 transition-[background-color] duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset",
          // Overdue is carried by the chip, not the whole row: a column of tinted rows reads as
          // wallpaper and dilutes the warning.
          selected ? "bg-selected" : "hover:bg-accent",
        )}
      >
        <div className="flex min-w-0 items-baseline justify-between gap-3">
          <p className="min-w-0 truncate text-sm">
            <span className="font-semibold text-foreground">{row.name}</span>
            <span className="text-muted-foreground"> · {row.company}</span>
          </p>
          <span
            className={cn(
              "flex shrink-0 items-center gap-1 text-xs font-medium tabular-nums",
              overdue
                ? "rounded-md bg-overdue-tint px-1.5 py-0.5 font-semibold text-overdue"
                : row.due_state === "today"
                  ? "text-primary"
                  : "text-muted-foreground",
            )}
          >
            {overdue && <AlertCircle aria-hidden className="size-3.5" />}
            {dueLabel(row, today)}
          </span>
        </div>
        <div className="mt-1.5 flex min-w-0 items-center gap-2">
          <TagBadge label={row.classification} className="shrink-0" />
          <p className="line-clamp-1 min-w-0 text-sm text-muted-foreground">
            {row.classification_reason ?? "Waiting for the first analysis."}
          </p>
        </div>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>{lastContactLabel(row.last_contact_at, today, timeZone)}</span>
          <span aria-hidden>·</span>
          <span>{shortRep(row.assigned_rep)}</span>
          {row.awaiting_our_reply && (
            <span className="inline-flex items-center gap-1 font-medium text-foreground">
              <MessageCircleQuestion aria-hidden className="size-3.5" />
              Buyer waiting
            </span>
          )}
          {row.analysis_status === "pending" && (
            <span className="inline-flex items-center gap-1">
              <Loader2 aria-hidden className="size-3.5 motion-safe:animate-spin" />
              Updating
            </span>
          )}
          {row.analysis_status === "failed" && (
            <span className="inline-flex items-center gap-1 text-destructive">
              <TriangleAlert aria-hidden className="size-3.5" />
              {row.analysis_source === "rules_fallback" ? "Rule-based" : "AI failed"}
            </span>
          )}
        </p>
      </a>
    </li>
  );
}
