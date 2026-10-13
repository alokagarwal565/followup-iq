import { ArrowRight, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { dueLabel } from "@/lib/format";
import type { LeadRow, Summary } from "@/lib/types";

const SHORTCUTS: [string, string][] = [
  ["j / k", "move through the queue"],
  ["/", "search"],
  ["n", "add a lead"],
];

/**
 * Fills the workspace pane when no lead is open, so a wide screen never shows an empty half.
 * It restates the day's workload and offers the same "most urgent first" start as the queue.
 */
export function WorkspacePlaceholder({
  summary,
  first,
  today,
  onOpen,
}: {
  summary: Summary | undefined;
  first: LeadRow | undefined;
  today: string;
  onOpen: (id: string) => void;
}) {
  const due = summary ? summary.overdue + summary.today : 0;
  const heading = !summary
    ? "Your follow-ups"
    : due === 0
      ? "Nothing due today"
      : `${summary.overdue} overdue · ${summary.today} due today`;

  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-6 py-12 text-center">
      <Inbox aria-hidden className="size-8 text-muted-foreground" />
      <div className="space-y-1">
        <h2 className="text-xl font-semibold tabular-nums">{heading}</h2>
        <p className="text-sm text-muted-foreground">
          {first
            ? "Open a lead to see why it's due and the message to send."
            : "No lead in this view. Change the filters or add a lead."}
        </p>
      </div>
      {first && (
        <Button size="lg" onClick={() => onOpen(first.id)} className="h-auto py-2.5">
          <span className="flex flex-col items-start text-left">
            <span>Start with {first.name}</span>
            <span className="text-xs font-normal">
              {first.company} · {dueLabel(first, today)}
            </span>
          </span>
          <ArrowRight aria-hidden />
        </Button>
      )}
      <ul className="flex flex-wrap justify-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
        {SHORTCUTS.map(([keys, label]) => (
          <li key={keys} className="flex items-center gap-1.5">
            <kbd className="rounded border bg-muted px-1.5 py-0.5 font-sans text-foreground">
              {keys}
            </kbd>
            {label}
          </li>
        ))}
      </ul>
    </div>
  );
}
