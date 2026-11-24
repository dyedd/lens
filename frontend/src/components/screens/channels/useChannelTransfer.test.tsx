// @vitest-environment jsdom

import type { ChangeEvent } from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { useChannelTransfer } from "./useChannelCommands";

let mounted: { root: Root; container: HTMLDivElement } | undefined;
let transfer: ReturnType<typeof useChannelTransfer>;

afterEach(() => {
  if (mounted) {
    const { root, container } = mounted;
    act(() => root.unmount());
    container.remove();
    mounted = undefined;
  }
  vi.unstubAllGlobals();
});

function renderTransfer() {
  function Harness() {
    transfer = useChannelTransfer({
      locale: "en-US",
      invalidateChannelData: async () => {},
    });
    return (
      <>
        <output data-testid="text">{transfer.batchImportText}</output>
        <output data-testid="error">{transfer.batchImportError}</output>
      </>
    );
  }

  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  mounted = { root, container };
  act(() => root.render(<Harness />));
  return container;
}

function readFileEvent(read: Promise<string>) {
  return {
    target: {
      files: [{ text: () => read }],
      value: "selected.json",
    },
  } as unknown as ChangeEvent<HTMLInputElement>;
}

it("ignores a file read that finishes after the import text is edited", async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const container = renderTransfer();
  const read = Promise.withResolvers<string>();
  let pendingRead: Promise<void>;
  act(() => {
    pendingRead = transfer.handleBatchImportFile(readFileEvent(read.promise));
  });
  act(() => transfer.updateBatchImportText("newer manual text"));

  await act(async () => {
    read.resolve("older file text");
    await pendingRead;
  });

  expect(container.querySelector('[data-testid="text"]')?.textContent).toBe(
    "newer manual text",
  );
  expect(container.querySelector('[data-testid="error"]')?.textContent).toBe(
    "",
  );
});

it("ignores a file read error after the import text is edited", async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const container = renderTransfer();
  const read = Promise.withResolvers<string>();
  let pendingRead: Promise<void>;
  act(() => {
    pendingRead = transfer.handleBatchImportFile(readFileEvent(read.promise));
  });
  act(() => transfer.updateBatchImportText("newer manual text"));

  await act(async () => {
    read.reject(new Error("old file read failed"));
    await pendingRead;
  });

  expect(container.querySelector('[data-testid="text"]')?.textContent).toBe(
    "newer manual text",
  );
  expect(container.querySelector('[data-testid="error"]')?.textContent).toBe(
    "",
  );
});
