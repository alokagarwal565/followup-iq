"use client";

import { AlertCircle, CalendarClock, ChevronRight } from "lucide-react";
import { useState } from "react";
import { formatFullDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Lead } from "@/lib/types";
import { AiStatus } from "./ai-status";

export function AnalysisCard({ lead, timeZone }: { lead: Lead; timeZone: string }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const overdue = lead.due_state === "overdue";
  const heading = lead.classification ? `Why ${lead.classification}` : "Why this tag";

  return (
    <section aria-labelledby={`why-${lead.id}`} className="space-y-3 rounded-lg border bg-card p-4">
      <h3 id={`why-${lead.id}`} className="text-sm font-semibold">
        {heading}
      </h3>
      <p className="text-sm leading-relaxed">
        {lead.classification_reason ?? "The agent hasn't analysed this lead yet."}
      </p>
      {lead.evidence.length > 0 && (
        <div>
          {/* Progressive disclosure: the reason is enough to act; quotes are there to verify it. */}
          <button
            type="button"
            aria-expanded={showEvidence}
            onClick={() => setShowEvidence((value) => !value)}
            className="inline-flex min-h-8 items-center gap-1 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none pointer-coarse:min-h-11"
          >
            <ChevronRight
              aria-hidden
              className={cn(
                "size-3.5 transition-transform duration-150",
                showEvidence && "rotate-90",
              )}
            />
            {showEvidence ? "Hide evidence" : `Show evidence (${lead.evidence.length})`}
          </button>
          {showEvidence && (
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {lead.evidence.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      <div
        className={cn(
          "flex gap-2 rounded-md px-3 py-2 text-sm",
          overdue ? "bg-overdue-tint text-overdue" : "bg-muted text-foreground",
        )}
      >
        {overdue ? (
          <AlertCircle aria-hidden className="mt-0.5 size-4 shrink-0" />
        ) : (
          <CalendarClock aria-hidden className="mt-0.5 size-4 shrink-0" />
        )}
        <p>
          <span className="font-medium">
            {lead.next_follow_up_date
              ? `Next follow-up: ${formatFullDate(lead.next_follow_up_date)}${
                  overdue ? ` (${lead.days_overdue}d overdue)` : ""
                }`
              : "No follow-up scheduled"}
          </span>
          {lead.follow_up_reason && (
            <span className={cn("block", overdue ? "text-foreground" : "text-muted-foreground")}>
              {lead.follow_up_reason}
            </span>
          )}
        </p>
      </div>
      <AiStatus leadId={lead.id} lead={lead} timeZone={timeZone} />
    </section>
  );
}
