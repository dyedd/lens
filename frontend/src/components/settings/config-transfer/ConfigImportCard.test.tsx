// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { ConfigImportCard } from "./ConfigImportCard";

vi.mock("@/hooks/useAppTimeZone", () => ({ useAppTimeZone: () => undefined }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

let root: Root | null = null;
let container: HTMLDivElement | null = null;

afterEach(() => {
  if (root) act(() => root?.unmount());
  container?.remove();
  root = null;
  container = null;
  vi.unstubAllGlobals();
});

it.each([
  {
    name: "file read failures",
    text: vi.fn().mockRejectedValue(new Error("read failed")),
    expectedMessage: "Could not read backup file",
  },
  {
    name: "invalid backup data",
    text: vi.fn().mockResolvedValue("{"),
    expectedMessage: "Invalid backup file",
  },
])("shows the correct message for $name", async ({ text, expectedMessage }) => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  container = document.createElement("div");
  document.body.append(container);
  const queryClient = new QueryClient();
  root = createRoot(container);

  await act(async () => {
    root?.render(
      <QueryClientProvider client={queryClient}>
        <ConfigImportCard locale="en-US" />
      </QueryClientProvider>,
    );
  });

  const file = new File(["backup"], "backup.json", {
    type: "application/json",
  });
  Object.defineProperty(file, "text", { value: text });
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("Expected the backup file input");
  Object.defineProperty(input, "files", { value: [file] });

  await act(async () => {
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await Promise.resolve();
  });

  expect(container.querySelector('[role="alert"]')?.textContent).toBe(
    expectedMessage,
  );
});

it("keeps the newer file preview pending when an older read finishes late", async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  await act(async () => {
    root?.render(
      <QueryClientProvider client={new QueryClient()}>
        <ConfigImportCard locale="en-US" />
      </QueryClientProvider>,
    );
  });

  const oldRead = Promise.withResolvers<string>();
  const firstFile = new File(["first"], "first.json", {
    type: "application/json",
  });
  Object.defineProperty(firstFile, "text", { value: () => oldRead.promise });
  const newRead = Promise.withResolvers<string>();
  const secondFile = new File(["{}"], "second.json", {
    type: "application/json",
  });
  Object.defineProperty(secondFile, "text", { value: () => newRead.promise });
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("Expected the backup file input");

  Object.defineProperty(input, "files", {
    configurable: true,
    value: [firstFile],
  });
  await act(async () => {
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  Object.defineProperty(input, "files", {
    configurable: true,
    value: [secondFile],
  });
  await act(async () => {
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });

  await act(async () => {
    oldRead.resolve("{}");
    await oldRead.promise;
  });
  expect(container.textContent).toContain("Parsing backup file...");
  expect(container.textContent).toContain("second.json");

  await act(async () => {
    newRead.resolve("{}");
    await newRead.promise;
  });
  expect(container.textContent).not.toContain("Parsing backup file...");
  expect(container.querySelector('[role="alert"]')).toBeNull();
});
