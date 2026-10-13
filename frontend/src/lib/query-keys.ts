import type { LeadFilters } from "./types";

export const queryKeys = {
  meta: ["meta"] as const,
  leads: (filters: LeadFilters) => ["leads", filters] as const,
  allLeads: ["leads"] as const,
  summary: (rep?: string) => ["summary", rep ?? "all"] as const,
  allSummaries: ["summary"] as const,
  lead: (id: string) => ["lead", id] as const,
};
