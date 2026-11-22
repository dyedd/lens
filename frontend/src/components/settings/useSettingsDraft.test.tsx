// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { useSettingsDraft } from "./useSettingsDraft";

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

function SettingsDraftHarness() {
  const settings = useSettingsDraft("en-US");

  return (
    <>
      <button
        type="button"
        onClick={() => settings.setDraftValue("siteName", "Lens Admin")}
      >
        Change site name
      </button>
      {settings.hasSaveError ? (
        <button
          type="button"
          aria-label="Retry saving"
          disabled={settings.isSaving}
          onClick={settings.retrySettings}
        >
          Retry saving
        </button>
      ) : null}
    </>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("only resends the failed settings draft after clicking retry", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  let savedSettings = [
    { key: "auth_access_token_minutes", value: "60" },
    { key: "max_request_body_bytes", value: "1048576" },
  ];
  const putRequests: { path: string; body: string }[] = [];
  const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    if (init?.method === "PUT" && typeof init.body === "string") {
      putRequests.push({ path, body: init.body });
      if (putRequests.length === 1) {
        return new Response("Temporary failure", { status: 503 });
      }
      savedSettings = [
        ...savedSettings,
        { key: "site_name", value: "Lens Admin" },
      ];
    }
    return Response.json(savedSettings);
  });
  vi.stubGlobal("fetch", fetchMock);

  const queryClient = new QueryClient();
  queryClient.setQueryData(["settings"], savedSettings);
  const container = document.createElement("div");
  const root = createRoot(container);
  const retryButton = () =>
    container.querySelector<HTMLButtonElement>(
      'button[aria-label="Retry saving"]',
    );

  try {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SettingsDraftHarness />
        </QueryClientProvider>,
      );
    });
    await act(async () => {
      container.querySelector("button")?.click();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(putRequests).toEqual([
      {
        path: "/api/admin/settings",
        body: expect.stringContaining('"key":"site_name","value":"Lens Admin"'),
      },
    ]);
    expect(retryButton()).not.toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });
    expect(putRequests).toHaveLength(1);

    await act(async () => retryButton()?.click());
    expect(putRequests).toHaveLength(2);
    expect(putRequests[1]).toEqual(putRequests[0]);
    expect(retryButton()).toBeNull();
  } finally {
    await act(async () => root.unmount());
    queryClient.clear();
  }
});
