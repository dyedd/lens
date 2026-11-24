// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { toast } from "sonner";
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
      <button
        type="button"
        onClick={() => settings.setDraftValue("authAccessTokenMinutes", "0")}
      >
        Invalid token lifetime
      </button>
      <output>{settings.draft.siteName}</output>
      <button
        type="button"
        onClick={() => settings.updateGlobalHeader(0, { value: "test" })}
      >
        Unnamed header
      </button>
      <button
        type="button"
        onClick={() =>
          settings.updateGlobalParamOverride([
            { path: "model", action: "set", value: "replacement" },
          ])
        }
      >
        Model override
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
  vi.clearAllMocks();
});

it.each([
  [
    "Invalid token lifetime",
    "Access token lifetime must be between 1 and 525600.",
  ],
  ["Unnamed header", "Header names are required."],
  ["Model override", "Parameter rules cannot override model."],
])("blocks autosave for %s", async (buttonLabel, message) => {
  vi.useFakeTimers();
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const settings = [
    { key: "auth_access_token_minutes", value: "60" },
    { key: "max_request_body_bytes", value: "1048576" },
  ];
  const fetchMock = vi.fn(async () => Response.json(settings));
  vi.stubGlobal("fetch", fetchMock);
  const queryClient = new QueryClient();
  queryClient.setQueryData(["settings"], settings);
  const container = document.createElement("div");
  const root = createRoot(container);

  try {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SettingsDraftHarness />
        </QueryClientProvider>,
      );
    });
    expect(toast.error).not.toHaveBeenCalled();
    const button = Array.from(container.querySelectorAll("button")).find(
      (candidate) => candidate.textContent === buttonLabel,
    );
    expect(button).toBeDefined();
    await act(async () => button?.click());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(toast.error).toHaveBeenCalledWith(message);
    expect(fetchMock).not.toHaveBeenCalled();
  } finally {
    await act(async () => root.unmount());
    queryClient.clear();
  }
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

it("allows restoring the previously submitted value after a server refresh", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  let savedSettings = [
    { key: "auth_access_token_minutes", value: "60" },
    { key: "max_request_body_bytes", value: "1048576" },
    { key: "site_name", value: "Original name" },
  ];
  const putRequests: string[] = [];
  const fetchMock = vi.fn(async (_path: string, init?: RequestInit) => {
    if (init?.method === "PUT" && typeof init.body === "string") {
      putRequests.push(init.body);
      savedSettings = [
        ...savedSettings.filter((item) => item.key !== "site_name"),
        {
          key: "site_name",
          value:
            putRequests.length === 1 ? "Canonical server name" : "Lens Admin",
        },
      ];
    }
    return Response.json(savedSettings);
  });
  vi.stubGlobal("fetch", fetchMock);

  const queryClient = new QueryClient();
  queryClient.setQueryData(["settings"], savedSettings);
  const container = document.createElement("div");
  const root = createRoot(container);

  try {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SettingsDraftHarness />
        </QueryClientProvider>,
      );
    });
    await act(async () => container.querySelector("button")?.click());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(putRequests).toHaveLength(1);
    expect(container.querySelector("output")?.textContent).toBe(
      "Canonical server name",
    );

    await act(async () => container.querySelector("button")?.click());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });

    expect(putRequests).toHaveLength(2);
    expect(putRequests[1]).toContain('"key":"site_name","value":"Lens Admin"');
  } finally {
    await act(async () => root.unmount());
    queryClient.clear();
  }
});
