// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { Tabs } from "@/components/ui/Tabs";
import { defaultPrivacyConfig } from "@/lib/api/privacy";
import { PrivacySettingsSection } from "./PrivacySettingsSection";
import { useSettingsDraft } from "./useSettingsDraft";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

function Harness() {
  const settings = useSettingsDraft("en-US");
  return (
    <Tabs defaultValue="privacy">
      <PrivacySettingsSection locale="en-US" settings={settings} />
    </Tabs>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("previews current form text and saves valid rules after blur", async () => {
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
  const settings = [
    { key: "auth_access_token_minutes", value: "60" },
    { key: "max_request_body_bytes", value: "1048576" },
    {
      key: "privacy_config",
      value: JSON.stringify({ ...defaultPrivacyConfig(), enabled: true }),
    },
  ];
  const fetchMock = vi.fn(async (path: string, _init?: RequestInit) => {
    if (path.endsWith("/privacy/preview"))
      return Response.json({ text: "redacted", hits: [], blocked: false });
    return Response.json(settings);
  });
  vi.stubGlobal("fetch", fetchMock);
  const queryClient = new QueryClient();
  queryClient.setQueryData(["settings"], settings);
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  try {
    await act(async () =>
      root.render(
        <QueryClientProvider client={queryClient}>
          <Harness />
        </QueryClientProvider>,
      ),
    );
    const words = container.querySelector<HTMLTextAreaElement>(
      'textarea[name="words"]',
    );
    const form = container.querySelector("form");
    expect(words).not.toBeNull();
    if (!words || !form) throw new Error("Privacy form missing");
    words.value = "private-project";
    await act(async () => {
      words.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(fetchMock).not.toHaveBeenCalled();
    await act(async () => {
      form.dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true }),
      );
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/admin/settings/privacy/preview",
      expect.objectContaining({
        body: expect.stringContaining('"words":["private-project"]'),
      }),
    );
    await act(async () => {
      words.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    const save = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "PUT",
    );
    expect(save?.[1]?.body).toContain("private-project");
    expect(container.textContent).toContain("redacted");
  } finally {
    await act(async () => root.unmount());
    container.remove();
    queryClient.clear();
  }
});
