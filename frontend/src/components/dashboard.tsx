"use client";

import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { AddLeadDialog } from "@/components/add-lead-dialog";
import { AppHeader } from "@/components/app-header";
import { LeadWorkspace } from "@/components/lead/lead-workspace";
import { WorkspacePlaceholder } from "@/components/lead/workspace-placeholder";
import { FilterBar, type Segment } from "@/components/queue/filter-bar";
import { QueuePanel } from "@/components/queue/queue-panel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useLeads, useMeta, useSummary } from "@/hooks/use-queries";
import { useRepFilter } from "@/hooks/use-rep-filter";
import { useSelectedLead } from "@/hooks/use-selected-lead";
import { UnsavedGuardProvider, useUnsavedGuard } from "@/hooks/use-unsaved-guard";
import { cn } from "@/lib/utils";
import type { LeadFilters, Meta } from "@/lib/types";

const PRODUCT_TITLE = "FollowUpIQ — AI Sales Follow-ups";
const COLD_START_HINT_MS = 4_000;
/** Queue and workspace sit side by side from the `lg` breakpoint. */
const SIDE_BY_SIDE = "(min-width: 1024px)";

function filtersFor(segment: Segment): Pick<LeadFilters, "due_state" | "classification"> {
  if (segment === "overdue") return { due_state: "overdue" };
  if (segment === "today") return { due_state: "today" };
  if (segment === "hot") return { classification: "Hot" };
  return {};
}

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return Boolean(
    el &&
    (el.isContentEditable ||
      ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) ||
      el.closest("[role=dialog]")),
  );
}

function Startup() {
  const meta = useMeta();
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!meta.isPending) return;
    const timer = setTimeout(() => setSlow(true), COLD_START_HINT_MS);
    return () => clearTimeout(timer);
  }, [meta.isPending]);

  if (meta.data) return <DashboardReady meta={meta.data} />;
  return (
    <main className="mx-auto w-full max-w-screen-2xl flex-1 space-y-4 px-4 py-6">
      <p className="text-lg font-semibold">FollowUpIQ</p>
      {meta.isError ? (
        <div className="space-y-3">
          <p className="text-sm">We couldn&apos;t reach the server.</p>
          <Button variant="outline" onClick={() => void meta.refetch()}>
            Try again
          </Button>
        </div>
      ) : (
        <div role="status" aria-label="Loading FollowUpIQ" className="space-y-3">
          {slow && (
            <p className="text-sm text-muted-foreground">
              Waking up the server. Free hosting can take up to a minute after a quiet period…
            </p>
          )}
          <Skeleton className="h-10 w-full max-w-xl" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}
    </main>
  );
}

function DashboardReady({ meta }: { meta: Meta }) {
  const [rep, setRep] = useRepFilter(meta.reps);
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const [segment, setSegment] = useState<Segment>("all");
  const filters = useMemo<LeadFilters>(
    () => ({ rep: rep ?? undefined, q: q || undefined, ...filtersFor(segment) }),
    [rep, q, segment],
  );
  const leads = useLeads(filters);
  const summary = useSummary(rep ?? undefined);
  const [selectedId, select] = useSelectedLead();
  const [focusWorkspace, setFocusWorkspace] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const autoSelected = useRef(false);
  const guard = useUnsavedGuard();
  const items = useMemo(() => leads.data?.items ?? [], [leads.data]);

  // Desktop opens the most urgent lead straight away so the first screen answers "who" and
  // "what to say"; mobile keeps the list first. A deep-linked lead is never overridden.
  useEffect(() => {
    if (autoSelected.current || selectedId || items.length === 0) return;
    autoSelected.current = true;
    if (window.matchMedia(SIDE_BY_SIDE).matches) select(items[0].id, { replace: true });
  }, [items, selectedId, select]);

  useEffect(() => {
    const due = summary.data ? summary.data.overdue + summary.data.today : 0;
    document.title = due > 0 ? `(${due}) ${PRODUCT_TITLE}` : PRODUCT_TITLE;
  }, [summary.data]);

  const selectLead = useCallback(
    (id: string | null) => {
      if (id === selectedId || !guard.confirmLeave()) return;
      setFocusWorkspace(Boolean(id));
      select(id);
    },
    [guard, select, selectedId],
  );

  const index = items.findIndex((item) => item.id === selectedId);
  const nextLead = index >= 0 && index < items.length - 1 ? items[index + 1].id : null;

  const onMissing = useCallback(() => {
    toast.error("That lead couldn't be found.");
    select(null, { replace: true });
  }, [select]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (
        event.defaultPrevented ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        isTyping(event.target)
      )
        return;
      if (event.key === "/") {
        event.preventDefault();
        searchRef.current?.focus();
      } else if (event.key === "n") {
        event.preventDefault();
        setAddOpen(true);
      } else if (event.key === "Escape" && selectedId) {
        // Side by side, the queue is already on screen, so Esc hands focus back to it rather than
        // closing the lead and leaving the pane empty. Full-screen (phones), Esc goes back.
        if (window.matchMedia(SIDE_BY_SIDE).matches) {
          document.querySelector<HTMLElement>(`[data-lead-id="${selectedId}"]`)?.focus();
        } else {
          selectLead(null);
        }
      } else if ((event.key === "j" || event.key === "ArrowDown") && items.length) {
        event.preventDefault();
        selectLead(items[Math.min(index + 1, items.length - 1)].id);
      } else if ((event.key === "k" || event.key === "ArrowUp") && items.length) {
        event.preventDefault();
        selectLead(items[Math.max(index - 1, 0)].id);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, items, selectLead, selectedId]);

  const filtered = Boolean(filters.q || filters.due_state || filters.classification || filters.rep);
  const clearFilters = () => {
    setSearch("");
    setSegment("all");
    setRep(null);
  };

  return (
    <div className="flex h-dvh flex-col">
      <a
        href="#queue"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
      >
        Skip to follow-up queue
      </a>
      <AppHeader
        ref={searchRef}
        meta={meta}
        rep={rep}
        onRepChange={setRep}
        search={search}
        onSearchChange={setSearch}
        onAddLead={() => setAddOpen(true)}
      />
      <h1 className="sr-only">Follow-up queue</h1>
      <div className="mx-auto grid min-h-0 w-full max-w-screen-2xl flex-1 grid-rows-[minmax(0,1fr)] lg:grid-cols-[minmax(360px,440px)_1fr]">
        <nav
          id="queue"
          aria-label="Follow-up queue"
          className={cn(
            "relative min-h-0 min-w-0 overflow-y-auto border-r bg-background lg:block",
            selectedId ? "hidden" : "block",
          )}
        >
          <div className="sticky top-0 z-20 border-b bg-background">
            <FilterBar summary={summary.data} active={segment} onChange={setSegment} />
          </div>
          <QueuePanel
            items={items}
            status={leads.status}
            today={meta.today}
            timeZone={meta.business_tz}
            selectedId={selectedId}
            filtered={filtered}
            onSelect={selectLead}
            onRetry={() => void leads.refetch()}
            onClearFilters={clearFilters}
          />
        </nav>
        <main
          className={cn(
            // Wide and tall windows pin the header, reason and composer and scroll only the thread.
            // Anything smaller scrolls the whole workspace under a sticky composer bar. `relative` makes
            // this the containing block for sr-only (absolute) descendants, so they cannot grow the page.
            "relative min-h-0 min-w-0 overflow-y-auto px-4 pt-5 lg:px-8 tall:flex tall:flex-col tall:overflow-hidden",
            selectedId ? "block" : "hidden lg:block",
          )}
        >
          {selectedId ? (
            <LeadWorkspace
              key={selectedId}
              leadId={selectedId}
              meta={meta}
              focusHeading={focusWorkspace}
              inCurrentFilter={leads.isPending || items.some((item) => item.id === selectedId)}
              onBack={() => selectLead(null)}
              onNext={nextLead ? () => selectLead(nextLead) : null}
              onMissing={onMissing}
            />
          ) : (
            <WorkspacePlaceholder
              summary={summary.data}
              first={items[0]}
              today={meta.today}
              onOpen={selectLead}
            />
          )}
        </main>
      </div>
      <footer className="shrink-0 border-t px-4 py-1.5 text-center text-xs text-muted-foreground">
        Demo with fictional data. Please don&apos;t enter real customer information.
      </footer>
      <AddLeadDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        meta={meta}
        defaultRep={rep}
        onCreated={(id) => {
          setFocusWorkspace(true);
          select(id);
        }}
        onOpenExisting={(id) => {
          setAddOpen(false);
          selectLead(id);
        }}
      />
    </div>
  );
}

export function Dashboard() {
  return (
    <UnsavedGuardProvider>
      <Startup />
    </UnsavedGuardProvider>
  );
}
