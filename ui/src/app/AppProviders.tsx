"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Toaster as SonnerToaster } from "@/components/ui/Sonner";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { I18nProvider } from "@/lib/I18nContext";
import { ThemeProvider } from "@/lib/ThemeContext";

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        refetchOnMount: false,
        retry: 1,
      },
    },
  });
}

/** Provides shared query, localization, theme, tooltip, and error contexts. */
export function AppProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <ThemeProvider>
          <TooltipProvider>
            <ErrorBoundary>{children}</ErrorBoundary>
            <SonnerToaster />
          </TooltipProvider>
        </ThemeProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
