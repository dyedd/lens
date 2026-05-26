"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangleIcon, RefreshCwIcon } from "lucide-react";
import { usePathname } from "next/navigation";

import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

type ErrorBoundaryState = {
  error: Error | null;
};

type ErrorBoundaryProps = {
  children: ReactNode;
};

class RenderErrorBoundary extends Component<
  ErrorBoundaryProps,
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
    if (this.state.error) {
      return (
        <main className="flex min-h-screen items-center justify-center bg-background p-6">
          <Alert variant="destructive" className="max-w-lg">
            <AlertTriangleIcon aria-hidden="true" />
            <AlertTitle>页面渲染失败</AlertTitle>
            <AlertDescription className="flex flex-col gap-3">
              <span>{this.state.error.message || "未知错误"}</span>
              <span>
                <Button type="button" variant="outline" onClick={this.reset}>
                  <RefreshCwIcon data-icon="inline-start" />
                  重试
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

export function ErrorBoundary({ children }: ErrorBoundaryProps) {
  const pathname = usePathname();

  return (
    <RenderErrorBoundary key={pathname}>{children}</RenderErrorBoundary>
  );
}
