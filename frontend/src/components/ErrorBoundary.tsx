import { AlertTriangleIcon, RefreshCwIcon } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { useLocation } from "react-router";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { type Locale, titleForLocale, useI18n } from "@/lib/I18nContext";

type ErrorBoundaryState = {
  error: Error | null;
};

type ErrorBoundaryProps = {
  children: ReactNode;
};

class RenderErrorBoundary extends Component<
  ErrorBoundaryProps & { locale: Locale },
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Render error captured by ErrorBoundary", error, info);
  }

  private reset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (error) {
      const { locale } = this.props;
      return (
        <main className="flex min-h-screen items-center justify-center bg-background p-6">
          <Alert variant="destructive" className="max-w-lg">
            <AlertTriangleIcon aria-hidden="true" />
            <AlertTitle>
              {titleForLocale(
                locale,
                "页面无法显示",
                "Page could not be displayed",
              )}
            </AlertTitle>
            <AlertDescription className="flex flex-col gap-3">
              <span>
                {error.message ||
                  titleForLocale(
                    locale,
                    "发生未知错误",
                    "An unknown error occurred",
                  )}
              </span>
              <span>
                <Button type="button" variant="outline" onClick={this.reset}>
                  <RefreshCwIcon data-icon="inline-start" />
                  {titleForLocale(locale, "重试", "Retry")}
                </Button>
              </span>
            </AlertDescription>
          </Alert>
        </main>
      );
    }

    return this.props.children;
  }
}

/** Resets the application render error boundary when the route changes. */
export function ErrorBoundary({ children }: ErrorBoundaryProps) {
  const pathname = useLocation().pathname;
  const { locale } = useI18n();

  return (
    <RenderErrorBoundary key={pathname} locale={locale}>
      {children}
    </RenderErrorBoundary>
  );
}
