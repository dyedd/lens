// @vitest-environment jsdom

import { QueryClient } from "@tanstack/react-query";
import { act, type FormEvent, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Site } from "@/lib/api/sites";
import { emptyForm } from "./channelForm";
import { useChannelSave } from "./useChannelSave";

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

const savedSite: Site = {
  id: "site-1",
  name: "Primary",
  enabled: true,
  supports_model_listing: true,
  tags: [],
  proxy_mode: "inherit",
  channel_proxy: "",
  headers: [],
  param_override: [],
  base_urls: [],
  credentials: [],
  protocols: [],
};

function ChannelSaveWorkflow({
  queryClient,
  onCreated,
}: {
  queryClient: QueryClient;
  onCreated: (site: Site) => void;
}) {
  const [form] = useState(() => {
    const next = emptyForm();
    next.name = "Primary";
    next.base_urls[0].url = "https://api.example.com/v1";
    next.newApiKeysLines = "test-key";
    return next;
  });
  const [isDialogOpen, setIsDialogOpen] = useState(true);
  const [editingSiteId, setEditingSiteId] = useState<string | null>(null);
  const save = useChannelSave({
    locale: "en-US",
    queryClient,
    invalidateChannelData: async () => {},
    editor: {
      form,
      editingSiteId,
      setEditingSiteId,
      setIsDialogOpen,
      validateSiteForm: () => true,
    },
    onCreated: (site) => {
      setEditingSiteId(site.id);
      onCreated(site);
    },
  });

  return (
    <>
      <output data-testid="dialog-open">{String(isDialogOpen)}</output>
      <output data-testid="editing-site-id">{editingSiteId ?? "new"}</output>
      <output data-testid="saving">{String(save.isSaving)}</output>
      <button
        type="button"
        disabled={save.isSaving}
        onClick={() =>
          void save.submit({
            preventDefault: vi.fn(),
          } as unknown as FormEvent<HTMLFormElement>)
        }
      >
        Save channel
      </button>
    </>
  );
}

let root: Root | undefined;
let container: HTMLDivElement | undefined;

async function clickSave() {
  const button = document.querySelector("button");
  expect(button).toBeDefined();
  await act(async () => {
    button?.click();
  });
}

async function waitFor(condition: () => boolean) {
  await act(async () => {
    const deadline = Date.now() + 3_000;
    while (!condition() && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
  });
  expect(condition()).toBe(true);
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
});

afterEach(async () => {
  if (root) {
    await act(async () => root?.unmount());
  }
  root = undefined;
  container?.remove();
  container = undefined;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("channel save workflow", () => {
  it("keeps a failed create open and allows retrying it", async () => {
    let attempts = 0;
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => {
      attempts += 1;
      if (attempts === 1) {
        return new Response(
          JSON.stringify({ error: { message: "Temporary failure" } }),
          {
            status: 503,
            headers: { "content-type": "application/json" },
          },
        );
      }
      return new Response(JSON.stringify(savedSite), {
        status: 201,
        headers: { "content-type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const queryClient = new QueryClient();
    const onCreated = vi.fn();
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(
        <ChannelSaveWorkflow queryClient={queryClient} onCreated={onCreated} />,
      );
    });

    await clickSave();
    await waitFor(() => screenText("saving") === "false");
    expect(screenText("dialog-open")).toBe("true");
    expect(screenText("editing-site-id")).toBe("new");
    expect(onCreated).not.toHaveBeenCalled();

    await clickSave();
    await waitFor(() => onCreated.mock.calls.length === 1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/admin/sites");
    expect(queryClient.getQueryData<Site[]>(["sites"])).toEqual([savedSite]);
    expect(screenText("dialog-open")).toBe("true");
    expect(screenText("editing-site-id")).toBe(savedSite.id);
    expect(onCreated).toHaveBeenCalledWith(savedSite);
    queryClient.clear();
  });
});

function screenText(testId: string) {
  return document.querySelector(`[data-testid="${testId}"]`)?.textContent;
}
