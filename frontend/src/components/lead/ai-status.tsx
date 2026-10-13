"use client";

import { CircleCheck, Loader2, RefreshCw, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useReanalyze } from "@/hooks/use-lead-mutations";
import { formatDateTime } from "@/lib/format";
import type { Lead } from "@/lib/types";

const FAILURE_COPY: Record<string, string> = {
  interrupted: "The last update was interrupted.",
  unconfigured: "AI is not configured on the server.",
};

export function AiStatus({
  leadId,
  lead,
  timeZone,
}: {
  leadId: string;
  lead: Lead;
  timeZone: string;
}) {
  const reanalyze = useReanalyze(leadId);
  const run = () =>
    reanalyze.mutate(undefined, {
      onError: () => toast.error("Couldn't start the analysis. Please try again."),
    });

  let body;
  if (lead.analysis_status === "pending" || reanalyze.isPending) {
    body = (
      <span className="inline-flex items-center gap-1.5 text-muted-foreground">
        <Loader2 aria-hidden className="size-4 motion-safe:animate-spin" />
        Reading the latest chat and redrafting…
      </span>
    );
  } else if (lead.analysis_status === "failed") {
    const fallback = lead.analysis_source === "rules_fallback";
    const reason = (lead.analysis_error && FAILURE_COPY[lead.analysis_error]) ?? "";
    body = (
      <>
        <span className="inline-flex items-center gap-1.5 text-destructive">
          <TriangleAlert aria-hidden className="size-4" />
          {fallback
            ? "Rule-based (AI unavailable)"
            : "Couldn't refresh the analysis; showing the last result."}
          {reason && <span className="text-muted-foreground"> {reason}</span>}
        </span>
        <Button variant="outline" size="sm" onClick={run}>
          <RefreshCw aria-hidden />
          Retry analysis
        </Button>
      </>
    );
  } else if (lead.analysis_status === "never") {
    body = (
      <>
        <span className="text-muted-foreground">Not analysed yet.</span>
        <Button variant="outline" size="sm" onClick={run}>
          Analyse now
        </Button>
      </>
    );
  } else {
    body = (
      <>
        <span className="inline-flex items-center gap-1.5 text-muted-foreground">
          <CircleCheck aria-hidden className="size-4 text-success" />
          Analysed by Gemini
          {lead.analysis_updated_at && ` · ${formatDateTime(lead.analysis_updated_at, timeZone)}`}
        </span>
        <Button variant="ghost" size="sm" onClick={run}>
          <RefreshCw aria-hidden />
          Re-analyse
        </Button>
      </>
    );
  }

  return (
    <div aria-live="polite" className="flex flex-wrap items-center justify-between gap-2 text-sm">
      {body}
    </div>
  );
}
