// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { ADMIN_PROFILE_QUERY_KEY } from "@/lib/api/app";
import { ADMIN_TOKEN_KEY } from "@/lib/auth";
import { useAccountSettings } from "./useAccountSettings";

let mounted: { root: Root; container: HTMLDivElement } | undefined;

afterEach(() => {
  if (mounted) {
    const { root, container } = mounted;
    act(() => root.unmount());
    container.remove();
    mounted = undefined;
  }
  localStorage.clear();
  vi.unstubAllGlobals();
});

function renderAccountSettings(queryClient: QueryClient) {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  let account: ReturnType<typeof useAccountSettings>;
  function Harness() {
    account = useAccountSettings("en-US");
    return null;
  }

  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  mounted = { root, container };
  act(() => {
    root.render(
      <QueryClientProvider client={queryClient}>
        <Harness />
      </QueryClientProvider>,
    );
  });
  return () => account;
}

it.each([
  { accessToken: " ", adminId: 1, updates: false },
  { accessToken: "replacement-token", adminId: "1", updates: false },
  { accessToken: "replacement-token", adminId: 2, updates: false },
  { accessToken: "replacement-token", adminId: 1, updates: true },
])(
  "accepts an account update only with a verified replacement session ($#)",
  async ({ accessToken, adminId, updates }) => {
    localStorage.setItem(ADMIN_TOKEN_KEY, "current-token");
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json({
        access_token: accessToken,
        profile: { id: adminId, username: "new-admin" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient();
    queryClient.setQueryData(ADMIN_PROFILE_QUERY_KEY, {
      id: 1,
      username: "admin",
    });
    const getAccount = renderAccountSettings(queryClient);

    act(() => getAccount().setUsername("new-admin"));
    await act(async () => {
      expect(await getAccount().submitAccount("")).toBe(updates);
    });

    expect(localStorage.getItem(ADMIN_TOKEN_KEY)).toBe(
      updates ? "replacement-token" : "current-token",
    );
    expect(queryClient.getQueryData(ADMIN_PROFILE_QUERY_KEY)).toEqual({
      id: 1,
      username: updates ? "new-admin" : "admin",
    });
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/admin/profile",
      expect.objectContaining({ method: "PUT" }),
    );
  },
);
