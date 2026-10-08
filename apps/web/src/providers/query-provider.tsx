"use client";

import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode, useState } from "react";

export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(() => {
    // Every successful action refreshes all cached data, so the UI never needs
    // a manual tab reload to reflect a change. Individual mutations may still
    // invalidate their own keys; this is the safety net that keeps shared,
    // cross-page data (dashboards, summaries, lists) in sync after any action.
    const queryClient: QueryClient = new QueryClient({
      // Invalidate every cached query once an action succeeds. Active queries
      // refetch immediately; inactive ones refresh when they are next used.
      mutationCache: new MutationCache({
        onSuccess: () => {
          void queryClient.invalidateQueries();
        },
      }),
      defaultOptions: {
        queries: {
          retry: 1,
          staleTime: 15_000,
          refetchOnWindowFocus: false,
        },
      },
    });
    return queryClient;
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}