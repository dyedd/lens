// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { ADMIN_TOKEN_KEY, setStoredToken } from "@/lib/auth";
import { I18nProvider } from "@/lib/I18nContext";
import { AuthGuard } from "./AuthGuard";

let mountedGuard: { root: Root; container: HTMLDivElement } | undefined;

afterEach(() => {
  if (mountedGuard) {
    const { root, container } = mountedGuard;
    act(() => root.unmount());
    container.remove();
    mountedGuard = undefined;
  }
  localStorage.clear();
  sessionStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

async function renderGuard() {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  mountedGuard = { root, container };
  await act(async () => {
    root.render(
      <MemoryRouter>
        <I18nProvider>
          <AuthGuard>
            {() => (
              <>
                <p>Protected content</p>
                <input aria-label="Draft" defaultValue="saved" />
              </>
            )}
          </AuthGuard>
        </I18nProvider>
      </MemoryRouter>,
    );
  });
  return container;
}

it("validates the token present at mount even when an old profile cache exists", async () => {
  localStorage.setItem(ADMIN_TOKEN_KEY, "token-B");
  sessionStorage.setItem(
    "lens_admin_profile_cache",
    JSON.stringify({
      version: 1,
      profile: { id: 1, username: "old-admin" },
      expiresAt: Date.now() + 60_000,
    }),
  );
  const session = Promise.withResolvers<Response>();
  const fetchMock = vi.fn<typeof fetch>().mockReturnValue(session.promise);
  vi.stubGlobal("fetch", fetchMock);
  const container = await renderGuard();

  expect(fetchMock).toHaveBeenCalledOnce();
  expect(
    new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("authorization"),
  ).toBe("Bearer token-B");
  expect(container.textContent).not.toContain("Protected content");

  await act(async () => {
    session.resolve(Response.json({ id: 2, username: "new-admin" }));
    await session.promise;
  });

  expect(container.textContent).toContain("Protected content");
});

it("reads the current token after registering the storage listener", async () => {
  localStorage.setItem(ADMIN_TOKEN_KEY, "token-A");
  const addEventListener = window.addEventListener.bind(window);
  vi.spyOn(window, "addEventListener").mockImplementation(
    (type, listener, options) => {
      addEventListener(type, listener, options);
      if (type === "storage") {
        localStorage.setItem(ADMIN_TOKEN_KEY, "token-B");
        (listener as EventListener)(
          new StorageEvent("storage", {
            key: ADMIN_TOKEN_KEY,
            oldValue: "token-A",
            newValue: "token-B",
            storageArea: localStorage,
          }),
        );
      }
    },
  );
  const fetchMock = vi
    .fn<typeof fetch>()
    .mockImplementation(async () =>
      Response.json({ id: 2, username: "new-admin" }),
    );
  vi.stubGlobal("fetch", fetchMock);

  const container = await renderGuard();

  expect(fetchMock).toHaveBeenCalledOnce();
  expect(
    new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("authorization"),
  ).toBe("Bearer token-B");
  expect(container.textContent).toContain("Protected content");
});

it("ignores an old token's late 401 after a cross-tab token replacement", async () => {
  localStorage.setItem(ADMIN_TOKEN_KEY, "token-A");
  const oldSession = Promise.withResolvers<Response>();
  const newSession = Promise.withResolvers<Response>();
  const fetchMock = vi
    .fn<typeof fetch>()
    .mockReturnValueOnce(oldSession.promise)
    .mockReturnValueOnce(newSession.promise);
  vi.stubGlobal("fetch", fetchMock);
  const container = await renderGuard();
  expect(fetchMock).toHaveBeenCalledOnce();

  await act(async () => {
    localStorage.setItem(ADMIN_TOKEN_KEY, "token-B");
    window.dispatchEvent(
      new StorageEvent("storage", {
        key: ADMIN_TOKEN_KEY,
        oldValue: "token-A",
        newValue: "token-B",
        storageArea: localStorage,
      }),
    );
  });
  expect(fetchMock).toHaveBeenCalledTimes(2);

  await act(async () => {
    oldSession.resolve(new Response(null, { status: 401 }));
    await oldSession.promise;
  });
  expect(localStorage.getItem(ADMIN_TOKEN_KEY)).toBe("token-B");
  expect(container.textContent).not.toContain("Protected content");

  await act(async () => {
    newSession.resolve(Response.json({ id: 2, username: "new-admin" }));
    await newSession.promise;
  });

  expect(container.textContent).toContain("Protected content");
  expect(localStorage.getItem(ADMIN_TOKEN_KEY)).toBe("token-B");
});

it("rechecks an unverified token change in the same tab", async () => {
  localStorage.setItem(ADMIN_TOKEN_KEY, "token-A");
  const oldSession = Promise.withResolvers<Response>();
  const newSession = Promise.withResolvers<Response>();
  const fetchMock = vi
    .fn<typeof fetch>()
    .mockReturnValueOnce(oldSession.promise)
    .mockReturnValueOnce(newSession.promise);
  vi.stubGlobal("fetch", fetchMock);
  const container = await renderGuard();

  await act(async () => {
    setStoredToken("token-B");
  });
  expect(fetchMock).toHaveBeenCalledTimes(2);

  await act(async () => {
    newSession.resolve(Response.json({ id: 2, username: "new-admin" }));
    await newSession.promise;
  });
  expect(container.textContent).toContain("Protected content");
  expect(localStorage.getItem(ADMIN_TOKEN_KEY)).toBe("token-B");

  await act(async () => {
    oldSession.resolve(new Response(null, { status: 401 }));
    await oldSession.promise;
  });
  expect(localStorage.getItem(ADMIN_TOKEN_KEY)).toBe("token-B");
});

it("keeps the dashboard draft when an account update rotates its token", async () => {
  localStorage.setItem(ADMIN_TOKEN_KEY, "token-A");
  const fetchMock = vi
    .fn<typeof fetch>()
    .mockResolvedValue(Response.json({ id: 1, username: "admin" }));
  vi.stubGlobal("fetch", fetchMock);
  const container = await renderGuard();
  const draft = container.querySelector("input");
  if (!draft) throw new Error("Expected dashboard draft");
  draft.value = "unsaved";

  act(() => setStoredToken("token-B", 1));

  expect(fetchMock).toHaveBeenCalledOnce();
  expect(container.querySelector("input")).toBe(draft);
  expect(draft.value).toBe("unsaved");
  expect(localStorage.getItem(ADMIN_TOKEN_KEY)).toBe("token-B");
});
