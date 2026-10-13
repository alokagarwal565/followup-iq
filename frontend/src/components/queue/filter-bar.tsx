import { cn } from "@/lib/utils";
import type { Summary } from "@/lib/types";

export type Segment = "all" | "overdue" | "today" | "hot";

const SEGMENTS: { id: Segment; label: string; count: (s: Summary) => number; tone?: string }[] = [
  { id: "overdue", label: "Overdue", count: (s) => s.overdue, tone: "text-overdue" },
  { id: "today", label: "Due today", count: (s) => s.today, tone: "text-primary" },
  { id: "hot", label: "Hot", count: (s) => s.hot, tone: "text-hot-foreground" },
  { id: "all", label: "All active", count: (s) => s.active },
];

/** Counts double as filters, so every number on screen is something a rep can act on. */
export function FilterBar({
  summary,
  active,
  onChange,
}: {
  summary: Summary | undefined;
  active: Segment;
  onChange: (segment: Segment) => void;
}) {
  return (
    <div role="group" aria-label="Filter the queue" className="flex gap-1 overflow-x-auto p-1">
      {SEGMENTS.map((segment) => {
        const pressed = active === segment.id;
        const count = summary ? segment.count(summary) : null;
        return (
          <button
            key={segment.id}
            type="button"
            aria-pressed={pressed}
            aria-label={count === null ? segment.label : `${segment.label} ${count}`}
            onClick={() => onChange(pressed && segment.id !== "all" ? "all" : segment.id)}
            className={cn(
              "flex min-h-10 shrink-0 items-baseline gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-[background-color,border-color] duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none",
              pressed
                ? "border-primary bg-selected font-medium text-foreground"
                : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <span>{segment.label}</span>
            <span className={cn("font-semibold tabular-nums", segment.tone ?? "text-foreground")}>
              {count ?? "–"}
            </span>
          </button>
        );
      })}
    </div>
  );
}
