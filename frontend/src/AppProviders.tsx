import { useEffect } from "react";
import { useLocation } from "react-router";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Toaster as SonnerToaster } from "@/components/ui/Sonner";
import { I18nProvider } from "@/lib/I18nContext";
import { ThemeProvider } from "@/lib/ThemeContext";

/** Provides shared localization, theme, and error contexts. */
export function AppProviders({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();

  useEffect(() => {
    const canonical = document.querySelector<HTMLLinkElement>(
      'link[rel="canonical"]',
    );
    if (canonical) {
      canonical.href = window.location.origin + pathname;
    }
  }, [pathname]);

  return (
    <I18nProvider>
      <ThemeProvider>
        <ErrorBoundary>{children}</ErrorBoundary>
        <SonnerToaster />
      </ThemeProvider>
    </I18nProvider>
  );
}
