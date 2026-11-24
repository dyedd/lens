// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, type ComponentProps } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/Tooltip";
import {
  OVERVIEW_DAILY_QUERY_KEY,
  type OverviewAttribution,
  type OverviewDailyPoint,
  type OverviewSummary,
} from "@/lib/api/overview";
import { I18nProvider } from "@/lib/I18nContext";
import { OverviewScreen } from "./OverviewScreen";
import type { ActivityTrendCard } from "./overview/ActivityTrendCard";

vi.mock("./overview/ActivityTrendCard", () => ({
  ActivityTrendCard: (props: ComponentProps<typeof ActivityTrendCard>) => (
    <output data-testid="activity-points">
      {JSON.stringify(props.points)}
    </output>
  ),
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("uses completed requests for success rate and shares daily data with chart navigation", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  localStorage.setItem("lens_locale", "en-US");
  const summary: OverviewSummary = {
    request_count: { value: 25, delta: 0 },
    wait_time_ms: { value: 1000, delta: 0 },
    total_tokens: { value: 100, delta: 0 },
    total_cost_usd: { value: 0.1, delta: 0 },
    input_tokens: { value: 80, delta: 0 },
    cache_read_input_tokens: { value: 40, delta: 0 },
    cache_write_input_tokens: { value: 20, delta: 0 },
    input_cost_usd: { value: 0.08, delta: 0 },
    output_tokens: { value: 20, delta: 0 },
    output_cost_usd: { value: 0.02, delta: 0 },
  };
  const daily: OverviewDailyPoint[] = [
    {
      date: "20261123",
      request_count: 25,
      input_tokens: 80,
      output_tokens: 20,
      total_tokens: 100,
      total_cost_usd: 0.1,
      wait_time_ms: 1000,
      successful_requests: 16,
      failed_requests: 4,
    },
  ];
  const attribution: OverviewAttribution = {
    items: [
      {
        key: "provider/model",
        label: "provider/model",
        is_deleted: false,
        requests: 25,
        successful_requests: 16,
        failed_requests: 4,
        input_tokens: 80,
        cache_read_input_tokens: 40,
        cache_write_input_tokens: 20,
        output_tokens: 20,
        total_tokens: 100,
        total_cost_usd: 0.1,
        wait_time_ms: 1000,
        cache_hit_rate: 0.5,
      },
    ],
    trend: [],
    dimension: "model",
    metric: "cache",
    filter_key: null,
    filter_label: null,
    filters: [],
    coverage: { has_dimension_history: true, has_hourly_history: true },
  };
  const dailyRequests: URLSearchParams[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      const url = new URL(path, "https://lens.test");
      if (url.pathname === "/api/admin/app-info") {
        return Response.json({ time_zone: "UTC" });
      }
      if (url.pathname === "/api/admin/overview-summary")
        return Response.json(summary);
      if (url.pathname === "/api/admin/overview-attribution")
        return Response.json(attribution);
      if (url.pathname === "/api/admin/overview-daily") {
        dailyRequests.push(url.searchParams);
        return Response.json(url.searchParams.has("granularity") ? [] : daily);
      }
      throw new Error(`Unexpected request ${path}`);
    }),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  queryClient.setQueryData(["app-info"], { time_zone: "UTC" });
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);

  async function flush() {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
  }

  try {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <I18nProvider>
            <MemoryRouter>
              <TooltipProvider>
                <OverviewScreen />
              </TooltipProvider>
            </MemoryRouter>
          </I18nProvider>
        </QueryClientProvider>,
      );
    });
    await flush();
    const successLabel = Array.from(container.querySelectorAll("span")).find(
      (node) => node.textContent === "Success rate",
    );
    expect(
      successLabel?.parentElement?.parentElement?.querySelector("p")
        ?.textContent,
    ).toBe("80%");
    expect(
      dailyRequests.filter((params) => params.get("granularity") === "hourly"),
    ).toHaveLength(1);
    await act(async () => {
      container
        .querySelector<HTMLButtonElement>(
          'button[aria-label="Select time range"]',
        )
        ?.click();
    });
    const weekButton = Array.from(document.querySelectorAll("button")).find(
      (button) => button.textContent === "Last 7 days",
    );
    expect(weekButton).toBeDefined();
    await act(async () => weekButton?.click());
    await flush();
    expect(
      dailyRequests.filter((params) => params.get("days") === "7"),
    ).toHaveLength(1);
    expect(
      container.querySelector('[data-testid="activity-points"]')?.textContent,
    ).toContain('"requests":25');
    expect(
      container.querySelector('a[aria-label="Failed 4"]')?.getAttribute("href"),
    ).toBe("/requests?days=7&status=failed");
    await act(async () => {
      container
        .querySelector<HTMLButtonElement>(
          'button[aria-label="Toggle details provider/model"]',
        )
        ?.click();
    });
    const failedLink = Array.from(container.querySelectorAll("a")).find(
      (link) => link.textContent === "View failed requests",
    );
    expect(failedLink?.getAttribute("href")).toBe(
      "/requests?days=7&status=failed&upstream_model=provider%2Fmodel",
    );

    await act(async () => {
      await queryClient.invalidateQueries({
        queryKey: OVERVIEW_DAILY_QUERY_KEY,
      });
    });
    await flush();
    expect(
      dailyRequests.filter((params) => params.get("days") === "7"),
    ).toHaveLength(2);
    expect(
      dailyRequests.filter((params) => params.get("days") === "371"),
    ).toHaveLength(2);
    expect(
      dailyRequests.filter((params) => params.get("granularity") === "hourly"),
    ).toHaveLength(1);
    expect(
      queryClient.getQueryState([
        ...OVERVIEW_DAILY_QUERY_KEY,
        -1,
        "UTC",
        "hourly",
      ])?.isInvalidated,
    ).toBe(true);
  } finally {
    await act(async () => root.unmount());
    container.remove();
    queryClient.clear();
  }
});
