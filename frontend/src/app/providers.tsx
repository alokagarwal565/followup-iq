"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

let browserQueryClient: QueryClient | undefined;

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Analysis status changes server-side; refetch on focus so a returning rep sees fresh state.
        refetchOnWindowFocus: true,
        staleTime: 10_000,
        retry: 1,
      },
      mutations: { retry: 0 },
    },
  });
}

function getQueryClient() {
  // Server renders get an isolated client; the browser keeps one cache across renders.
  if (typeof window === "undefined") return makeQueryClient();
  browserQueryClient ??= makeQueryClient();
  return browserQueryClient;
}

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={getQueryClient()}>
      <TooltipProvider delayDuration={300}>
        {children}
        {/* Top placement: the composer bar is pinned to the bottom and must never be covered. */}
        <Toaster position="top-center" />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
