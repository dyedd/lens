// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { ThemeProvider } from "./ThemeContext";

let mounted: { root: Root; container: HTMLDivElement } | undefined;

afterEach(() => {
  if (mounted) {
    const { root, container } = mounted;
    act(() => root.unmount());
    container.remove();
    mounted = undefined;
  }
  document.documentElement.classList.remove("dark");
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
});

it("applies the system theme when persisted preferences cannot be read", () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("matchMedia", () => ({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new DOMException("Storage unavailable", "SecurityError");
  });

  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  mounted = { root, container };

  act(() => root.render(<ThemeProvider>Dashboard</ThemeProvider>));

  expect(document.documentElement.classList.contains("dark")).toBe(true);
});
