import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useLocation } from "react-router";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Toaster as SonnerToaster } from "@/components/ui/Sonner";
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

/** Provides shared query, localization, theme, and error contexts. */
export function AppProviders({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const [queryClient] = useState(createQueryClient);

  useEffect(() => {
    const canonical = document.querySelector<HTMLLinkElement>(
      'link[rel="canonical"]',
    );
    if (canonical) {
      canonical.href = window.location.origin + pathname;
    }
  }, [pathname]);

  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <ThemeProvider>
          <ErrorBoundary>{children}</ErrorBoundary>
          <SonnerToaster />
        </ThemeProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
