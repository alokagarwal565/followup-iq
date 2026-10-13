"use client";

import { ArrowRightLeft } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useLead } from "@/hooks/use-queries";
import { ApiError } from "@/lib/api";
import type { Classification, Meta } from "@/lib/types";
import { AnalysisCard } from "./analysis-card";
import { ChatTimeline } from "./chat-timeline";
import { DraftComposer } from "./draft-composer";
import { LeadHeader } from "./lead-header";
import { LogChatDialog } from "./log-chat-dialog";

interface Props {
  leadId: string;
  meta: Meta;
  focusHeading: boolean;
  inCurrentFilter: boolean;
  onBack: () => void;
  onNext: (() => void) | null;
  onMissing: () => void;
}

export function LeadWorkspace({
  leadId,
  meta,
  focusHeading,
  inCurrentFilter,
  onBack,
  onNext,
  onMissing,
}: Props) {
  const query = useLead(leadId);
  const heading = useRef<HTMLHeadingElement>(null);
  const article = useRef<HTMLElement>(null);
  const tagBeforeUpdate = useRef<Classification | null | undefined>(undefined);
  const [tagChange, setTagChange] = useState<string | null>(null);
  const [logOpen, setLogOpen] = useState(false);
  const data = query.data;
  const loaded = Boolean(data);
  const messageCount = data?.messages.length ?? 0;

  useEffect(() => {
    if (focusHeading && loaded) heading.current?.focus({ preventScroll: true });
  }, [focusHeading, loaded]);

  // Like any messaging app, the thread opens at the newest message, where the draft waits.
  useLayoutEffect(() => {
    const thread = article.current?.querySelector<HTMLElement>("[data-thread-scroll]");
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [loaded, messageCount]);

  useEffect(() => {
    if (query.error instanceof ApiError && query.error.status === 404) onMissing();
  }, [query.error, onMissing]);

  // Surface the agent's update: when an analysis finishes with a different tag, say so.
  useEffect(() => {
    if (!data) return;
    const { analysis_status: status, classification } = data.lead;
    if (status === "pending") {
      if (tagBeforeUpdate.current === undefined) tagBeforeUpdate.current = classification;
      return;
    }
    const before = tagBeforeUpdate.current;
    tagBeforeUpdate.current = undefined;
    if (before !== undefined && before && classification && before !== classification) {
      setTagChange(`Tag changed: ${before} → ${classification}`);
    }
  }, [data]);

  if (query.isPending) {
    return (
      <div role="status" aria-label="Loading lead" className="space-y-4">
        <Skeleton className="h-7 w-1/2" />
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (query.isError || !data) {
    return (
      <div className="space-y-3">
        <p className="text-sm">We couldn&apos;t load this lead.</p>
        <Button variant="outline" onClick={() => void query.refetch()}>
          Try again
        </Button>
      </div>
    );
  }

  const { lead, messages, draft } = data;
  return (
    <article ref={article} className="min-h-full tall:h-full">
      <DraftComposer
        lead={lead}
        draft={draft}
        timeZone={meta.business_tz}
        onLogChat={() => setLogOpen(true)}
        top={
          <>
            <LeadHeader
              ref={heading}
              lead={lead}
              reps={meta.reps}
              inCurrentFilter={inCurrentFilter}
              onBack={onBack}
              onNext={onNext}
            />
            {tagChange && (
              <p
                role="status"
                className="flex items-center gap-2 rounded-md bg-selected px-3 py-2 text-sm font-medium"
              >
                <ArrowRightLeft aria-hidden className="size-4" />
                {tagChange}
              </p>
            )}
            <AnalysisCard lead={lead} timeZone={meta.business_tz} />
          </>
        }
        thread={
          <section aria-labelledby={`chat-${lead.id}`}>
            <h3 id={`chat-${lead.id}`} className="sr-only">
              Conversation
            </h3>
            <ChatTimeline
              messages={messages}
              buyerName={lead.name}
              repName={lead.assigned_rep}
              timeZone={meta.business_tz}
            />
          </section>
        }
      />
      <LogChatDialog
        open={logOpen}
        onOpenChange={setLogOpen}
        leadId={lead.id}
        leadName={lead.name.split(" ")[0]}
        timeZone={meta.business_tz}
      />
    </article>
  );
}
