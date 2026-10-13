"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { LeadDetail, LeadFilters, LeadList } from "@/lib/types";

const POLL_MS = 2_000;

export function useMeta() {
  return useQuery({
    queryKey: queryKeys.meta,
    // A sleeping free-tier server can take close to a minute to wake, so the first call waits longer.
    queryFn: () => api.meta({ timeoutMs: 60_000 }),
    staleTime: 5 * 60_000,
  });
}

export function useLeads(filters: LeadFilters) {
  return useQuery({
    queryKey: queryKeys.leads(filters),
    queryFn: () => api.leads(filters),
    // Keep polling while any visible lead is being re-analysed, then stop.
    refetchInterval: (query) =>
      (query.state.data as LeadList | undefined)?.items.some((i) => i.analysis_status === "pending")
        ? POLL_MS
        : false,
    refetchIntervalInBackground: false,
    placeholderData: (previous) => previous,
  });
}

export function useSummary(rep?: string) {
  return useQuery({ queryKey: queryKeys.summary(rep), queryFn: () => api.summary(rep) });
}

export function useLead(id: string | null) {
  return useQuery({
    queryKey: queryKeys.lead(id ?? ""),
    queryFn: () => api.lead(id as string),
    enabled: Boolean(id),
    refetchInterval: (query) =>
      (query.state.data as LeadDetail | undefined)?.lead.analysis_status === "pending"
        ? POLL_MS
        : false,
    refetchIntervalInBackground: false,
  });
}
