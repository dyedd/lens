// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, type ComponentProps } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { OVERVIEW_DAILY_QUERY_KEY } from "@/lib/api/overview";
import type { RequestLogDetail } from "@/lib/api/requests";
import { I18nProvider } from "@/lib/I18nContext";
import { RequestsScreen } from "./RequestsScreen";
import type { RequestLogDetailSheet } from "./requests/RequestLogDetailSheet";
import type { RequestsOverview } from "./requests/RequestsOverview";

vi.mock("./requests/RequestsOverview", () => ({
  RequestsOverview: (props: ComponentProps<typeof RequestsOverview>) => (
    <>
      <button type="button" onClick={() => props.onPageChange(props.page + 1)}>
        Next page
      </button>
      <button type="button" onClick={() => props.onStatusChange("failed")}>
        Failed requests
      </button>
      <button type="button" onClick={() => props.onStatusChange("all")}>
        All requests
      </button>
      <button
        type="button"
        onClick={(event) => props.onOpenDetail(42, event.currentTarget)}
      >
        Open detail
      </button>
      <button type="button" onClick={props.onClear}>
        Clear logs
      </button>
    </>
  ),
}));

vi.mock("./requests/RequestLogDetailSheet", () => ({
  RequestLogDetailSheet: (
    props: ComponentProps<typeof RequestLogDetailSheet>,
  ) => {
    const detail = props.detail;
    return detail ? (
      <>
        <output>{detail.lifecycle_status}</output>
        <button type="button" onClick={() => props.onCancel(detail.id)}>
          Cancel request
        </button>
      </>
    ) : null;
  },
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("resets filtered pagination, refreshes cancellation, and invalidates cleared statistics", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  let detail: RequestLogDetail = {
    id: 42,
    protocol: "openai_chat",
    user_agent: "test-client",
    credential_name: "Primary",
    credential_number: 1,
    channel_has_multiple_credentials: false,
    gateway_has_multiple_keys: false,
    success: false,
    lifecycle_status: "streaming",
    can_cancel: true,
    is_stream: true,
    first_token_latency_ms: 1,
    latency_ms: 10,
    input_tokens: 3,
    image_input_tokens: 0,
    cache_read_input_tokens: 0,
    cache_write_input_tokens: 0,
    output_tokens: 1,
    total_tokens: 4,
    input_cost_usd: 0,
    output_cost_usd: 0,
    total_cost_usd: 0,
    rate_multiplier: null,
    billing_mode: "free",
    billing_units: 0,
    attempt_count: 1,
    created_at: "2026-11-23T00:00:00Z",
    attempts: [],
  };
  const listRequests: URLSearchParams[] = [];
  let detailRequests = 0;
  let cleared = false;
  const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    const url = new URL(path, "https://lens.test");
    if (url.pathname === "/api/admin/app-info") {
      return Response.json({ time_zone: "UTC" });
    }
    if (url.pathname === "/api/admin/settings") return Response.json([]);
    if (url.pathname === "/api/admin/request-logs/42/cancel") {
      expect(init?.method).toBe("POST");
      detail = { ...detail, lifecycle_status: "cancelled", can_cancel: false };
      return new Response(null, { status: 204 });
    }
    if (url.pathname === "/api/admin/request-logs/42") {
      detailRequests += 1;
      return Response.json(detail);
    }
    if (url.pathname === "/api/admin/request-logs") {
      expect(init?.method).toBe("DELETE");
      cleared = true;
      return new Response(null, { status: 204 });
    }
    if (url.pathname === "/api/admin/request-logs/page") {
      listRequests.push(url.searchParams);
      return Response.json({
        items: cleared ? [] : [detail],
        total: cleared ? 0 : 100,
        limit: Number(url.searchParams.get("limit")),
        offset: Number(url.searchParams.get("offset")),
        channels: [],
        gateway_keys: [],
        gateway_has_multiple_keys: false,
        model_names: [],
      });
    }
    throw new Error(`Unexpected request ${path}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const dailyKeys = [
    [...OVERVIEW_DAILY_QUERY_KEY, 7, "UTC"],
    [...OVERVIEW_DAILY_QUERY_KEY, 371, "UTC"],
    [...OVERVIEW_DAILY_QUERY_KEY, -1, "UTC", "hourly"],
  ];
  for (const key of dailyKeys) queryClient.setQueryData(key, []);
  const container = document.createElement("div");
  const root = createRoot(container);

  async function click(label: string) {
    const button = Array.from(container.querySelectorAll("button")).find(
      (candidate) => candidate.textContent === label,
    );
    expect(button).toBeDefined();
    await act(async () => button?.click());
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
              <RequestsScreen />
            </MemoryRouter>
          </I18nProvider>
        </QueryClientProvider>,
      );
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    await click("Next page");
    expect(listRequests.at(-1)?.get("offset")).toBe("25");
    await click("Failed requests");
    expect(listRequests.at(-1)?.get("offset")).toBe("0");
    expect(listRequests.at(-1)?.get("status")).toBe("failed");
    await click("All requests");
    await click("Open detail");
    expect(container.querySelector("output")?.textContent).toBe("streaming");
    const listCount = listRequests.length;
    const detailCount = detailRequests;
    await click("Cancel request");
    expect(listRequests.length).toBeGreaterThan(listCount);
    expect(detailRequests).toBeGreaterThan(detailCount);
    expect(container.querySelector("output")?.textContent).toBe("cancelled");
    await click("Clear logs");
    expect(cleared).toBe(true);
    expect(container.querySelector("output")).toBeNull();
    for (const key of dailyKeys) {
      expect(queryClient.getQueryState(key)?.isInvalidated).toBe(true);
    }
  } finally {
    await act(async () => root.unmount());
    queryClient.clear();
  }
});
