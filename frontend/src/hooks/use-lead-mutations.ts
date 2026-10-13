"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type {
  DraftSave,
  DraftSend,
  LeadCreate,
  LeadDetail,
  LeadUpdate,
  MessagesCreate,
} from "@/lib/types";

/** Every write refreshes the queue, the counts and the lead itself; no optimistic updates. */
function useRefresh() {
  const client = useQueryClient();
  return (id?: string, detail?: LeadDetail) => {
    if (id && detail) client.setQueryData(queryKeys.lead(id), detail);
    if (id) void client.invalidateQueries({ queryKey: queryKeys.lead(id) });
    void client.invalidateQueries({ queryKey: queryKeys.allLeads });
    void client.invalidateQueries({ queryKey: queryKeys.allSummaries });
  };
}

export function useCreateLead() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: LeadCreate) => api.createLead(body),
    onSuccess: (detail) => refresh(detail.lead.id, detail),
  });
}

export function useUpdateLead(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: LeadUpdate) => api.updateLead(id, body),
    onSuccess: (detail) => refresh(id, detail),
  });
}

export function useLogMessages(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: MessagesCreate) => api.logMessages(id, body),
    onSuccess: (detail) => refresh(id, detail),
  });
}

export function useSaveDraft(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: DraftSave) => api.saveDraft(id, body),
    onSuccess: () => refresh(id),
  });
}

export function useAcceptSuggestion(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (version: number) => api.acceptSuggestion(id, version),
    onSuccess: () => refresh(id),
  });
}

export function useSendDraft(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: DraftSend) => api.sendDraft(id, body),
    onSuccess: (detail) => refresh(id, detail),
  });
}

export function useUndoSend(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: () => api.undoSend(id),
    onSuccess: (detail) => refresh(id, detail),
  });
}

export function useReanalyze(id: string) {
  const refresh = useRefresh();
  return useMutation({ mutationFn: () => api.analyze(id), onSuccess: () => refresh(id) });
}
