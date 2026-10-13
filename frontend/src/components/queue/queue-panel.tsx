"use client";

import { AlertCircle, CalendarClock, ChevronRight, Inbox } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { addDays } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { LeadRow } from "@/lib/types";
import { QueueRow } from "./queue-row";

interface Props {
  items: LeadRow[];
  status: "pending" | "error" | "success";
  today: string;
  timeZone: string;
  selectedId: string | null;
  filtered: boolean;
  onSelect: (id: string) => void;
  onRetry: () => void;
  onClearFilters: () => void;
}

function Section({
  title,
  icon,
  tone,
  rows,
  children,
}: {
  title: string;
  icon?: ReactNode;
  tone?: string;
  rows: number;
  children: ReactNode;
}) {
  return (
    <section aria-label={title}>
      <h2
        className={cn(
          "sticky top-0 z-10 flex items-center gap-1.5 border-b bg-background/95 px-4 py-2 text-xs font-semibold tracking-wide backdrop-blur",
          tone ?? "text-muted-foreground",
        )}
      >
        {icon}
        {`${title} (${rows})`}
      </h2>
      {children}
    </section>
  );
}

export function QueuePanel(props: Props) {
  const {
    items,
    status,
    today,
    timeZone,
    selectedId,
    filtered,
    onSelect,
    onRetry,
    onClearFilters,
  } = props;
  const [showUnscheduled, setShowUnscheduled] = useState(false);

  if (status === "pending" && items.length === 0) {
    return (
      <div role="status" aria-label="Loading follow-ups" className="divide-y">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="space-y-2 px-4 py-3">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        ))}
      </div>
    );
  }

  if (status === "error" && items.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3 px-4 py-8">
        <p className="text-sm text-foreground">We couldn&apos;t load the follow-up queue.</p>
        <Button variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3 px-4 py-8">
        <Inbox aria-hidden className="size-5 text-muted-foreground" />
        {filtered ? (
          <>
            <p className="text-sm">No leads match these filters.</p>
            <Button variant="outline" onClick={onClearFilters}>
              Clear filters
            </Button>
          </>
        ) : (
          <p className="text-sm">No leads yet. Add your first lead to start the queue.</p>
        )}
      </div>
    );
  }

  const row = (lead: LeadRow) => (
    <QueueRow
      key={lead.id}
      row={lead}
      today={today}
      timeZone={timeZone}
      selected={lead.id === selectedId}
      onSelect={onSelect}
    />
  );
  const overdue = items.filter((i) => i.due_state === "overdue");
  const dueToday = items.filter((i) => i.due_state === "today");
  const upcoming = items.filter((i) => i.due_state === "upcoming");
  const unscheduled = items.filter((i) => i.due_state === "none");
  const tomorrow = addDays(today, 1);
  const weekEnd = addDays(today, 7);
  const upcomingGroups: [string, LeadRow[]][] = [
    ["Tomorrow", upcoming.filter((i) => i.next_follow_up_date === tomorrow)],
    [
      "This week",
      upcoming.filter(
        (i) => (i.next_follow_up_date ?? "") > tomorrow && (i.next_follow_up_date ?? "") <= weekEnd,
      ),
    ],
    ["Later", upcoming.filter((i) => (i.next_follow_up_date ?? "") > weekEnd)],
  ];

  return (
    <div>
      {overdue.length > 0 && (
        <Section
          title="Overdue"
          tone="text-overdue"
          icon={<AlertCircle aria-hidden className="size-3.5" />}
          rows={overdue.length}
        >
          <ul className="divide-y">{overdue.map(row)}</ul>
        </Section>
      )}
      <Section
        title="Due today"
        tone="text-primary"
        icon={<CalendarClock aria-hidden className="size-3.5" />}
        rows={dueToday.length}
      >
        {dueToday.length > 0 ? (
          <ul className="divide-y">{dueToday.map(row)}</ul>
        ) : (
          <p className="px-4 py-3 text-sm text-muted-foreground">
            Nothing else due today. Check Upcoming or add a lead.
          </p>
        )}
      </Section>
      {upcoming.length > 0 && (
        <Section title="Upcoming" rows={upcoming.length}>
          {upcomingGroups
            .filter(([, group]) => group.length > 0)
            .map(([label, group]) => (
              <div key={label}>
                <p className="bg-muted/60 px-4 py-1 text-xs text-muted-foreground">{label}</p>
                <ul className="divide-y">{group.map(row)}</ul>
              </div>
            ))}
        </Section>
      )}
      {unscheduled.length > 0 && (
        <Section title="No follow-up" rows={unscheduled.length}>
          <button
            type="button"
            aria-expanded={showUnscheduled}
            onClick={() => setShowUnscheduled((v) => !v)}
            className="flex min-h-11 w-full items-center gap-1.5 px-4 text-left text-sm text-muted-foreground hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset"
          >
            <ChevronRight
              aria-hidden
              className={cn(
                "size-4 transition-transform duration-150",
                showUnscheduled && "rotate-90",
              )}
            />
            {showUnscheduled ? "Hide" : "Show"} no follow-up leads
          </button>
          {showUnscheduled && <ul className="divide-y">{unscheduled.map(row)}</ul>}
        </Section>
      )}
    </div>
  );
}
