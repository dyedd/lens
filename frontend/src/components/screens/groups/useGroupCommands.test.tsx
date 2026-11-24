// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { toast } from "sonner";
import { afterEach, expect, it, vi } from "vitest";
import { apiFetch, apiRequest } from "@/lib/api/client";
import type { ModelGroup } from "@/lib/api/groups";
import { EMPTY_FORM } from "./groupTypes";
import { useGroupCommands } from "./useGroupCommands";

vi.mock("@/lib/api/client", () => ({
  apiFetch: vi.fn(),
  apiRequest: vi.fn(),
  isRecord: (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null && !Array.isArray(value),
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

let mounted: { root: Root; container: HTMLDivElement } | undefined;

afterEach(() => {
  if (mounted) {
    const { root, container } = mounted;
    act(() => root.unmount());
    container.remove();
    mounted = undefined;
  }
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

it("reports completed deletes and refreshes after a later delete fails", async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.mocked(apiFetch)
    .mockResolvedValueOnce(new Response(null, { status: 204 }))
    .mockRejectedValueOnce(new Error("second delete failed"));
  const invalidateGroupData = vi.fn(async () => {});
  let commands: ReturnType<typeof useGroupCommands>;

  function Harness() {
    commands = useGroupCommands({
      editingId: null,
      form: EMPTY_FORM,
      groups: [],
      invalidateGroupData,
      locale: "en-US",
      setDialogOpen: vi.fn(),
      setEditingId: vi.fn(),
      setForm: vi.fn(),
    });
    return null;
  }

  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  mounted = { root, container };
  act(() => {
    root.render(
      <QueryClientProvider client={new QueryClient()}>
        <Harness />
      </QueryClientProvider>,
    );
  });

  await act(async () => {
    await commands.removeGroups([
      { id: "first" },
      { id: "second" },
    ] as ModelGroup[]);
  });

  expect(apiFetch).toHaveBeenNthCalledWith(1, "/admin/model-groups/first", {
    method: "DELETE",
  });
  expect(apiFetch).toHaveBeenNthCalledWith(2, "/admin/model-groups/second", {
    method: "DELETE",
  });
  expect(invalidateGroupData).toHaveBeenCalledOnce();
  expect(toast.error).toHaveBeenCalledWith(
    expect.stringContaining("Completed 1 of 2 operations"),
  );
  expect(toast.error).toHaveBeenCalledWith(
    expect.stringContaining("second delete failed"),
  );
});

it("reports a create failure and a failed refresh after partial completion", async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.mocked(apiRequest)
    .mockResolvedValueOnce({ id: "created-group" })
    .mockRejectedValueOnce(new Error("second create failed"));
  const invalidateGroupData = vi.fn(async () => {
    throw new Error("group refresh failed");
  });
  let commands!: ReturnType<typeof useGroupCommands>;
  let result: boolean | undefined;

  function Harness() {
    commands = useGroupCommands({
      editingId: null,
      form: EMPTY_FORM,
      groups: [],
      invalidateGroupData,
      locale: "en-US",
      setDialogOpen: vi.fn(),
      setEditingId: vi.fn(),
      setForm: vi.fn(),
    });
    return null;
  }

  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  mounted = { root, container };
  act(() => {
    root.render(
      <QueryClientProvider client={new QueryClient()}>
        <Harness />
      </QueryClientProvider>,
    );
  });

  await act(async () => {
    result = await commands.createOwnGroups(["first model", "second model"]);
  });

  expect(apiRequest).toHaveBeenCalledTimes(2);
  expect(invalidateGroupData).toHaveBeenCalledOnce();
  expect(result).toBe(false);
  expect(commands.busyId).toBeNull();
  expect(toast.error).toHaveBeenCalledOnce();
  expect(toast.error).toHaveBeenCalledWith(
    expect.stringContaining("Completed 1 of 2 operations"),
  );
  expect(toast.error).toHaveBeenCalledWith(
    expect.stringContaining("group refresh failed"),
  );
  expect(toast.error).toHaveBeenCalledWith(
    expect.stringContaining("second create failed"),
  );
});
