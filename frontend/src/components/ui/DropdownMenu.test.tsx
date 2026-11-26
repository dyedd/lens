// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "./DropdownMenu";
import { isPointerInSubmenuSafeTriangle } from "./submenuSafeTriangle";

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

it("detects points inside and outside the submenu aim safe triangle", () => {
  const origin = { x: 100, y: 120 };
  const submenuRect = { left: 220, right: 360, top: 100, bottom: 260 };
  const triggerRect = { left: 20, right: 210, top: 105, bottom: 135 };

  // Moving diagonally down-right across sibling item toward submenu bottom edge.
  expect(
    isPointerInSubmenuSafeTriangle(
      { x: 170, y: 175 },
      origin,
      submenuRect,
      triggerRect,
    ),
  ).toBe(true);

  // Moving straight down on parent column outside the triangle.
  expect(
    isPointerInSubmenuSafeTriangle(
      { x: 90, y: 210 },
      origin,
      submenuRect,
      triggerRect,
    ),
  ).toBe(false);
});

it("applies open delay, close delay, and safe-triangle submenu retention", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);

  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);

  await act(async () => {
    root.render(
      <DropdownMenu open>
        <DropdownMenuTrigger asChild>
          <button type="button">Menu</button>
        </DropdownMenuTrigger>
        <DropdownMenuContent subOpenDelayMs={120} subCloseDelayMs={180}>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>Parent A</DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuItem>Child B1</DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
          <DropdownMenuItem>Sibling C</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
  });

  const triggerA = Array.from(
    document.querySelectorAll('[role="menuitem"]'),
  ).find((node) => node.textContent?.includes("Parent A")) as HTMLElement;
  const siblingC = Array.from(
    document.querySelectorAll('[role="menuitem"]'),
  ).find((node) => node.textContent?.includes("Sibling C")) as HTMLElement;

  expect(triggerA).toBeDefined();
  expect(siblingC).toBeDefined();

  vi.spyOn(triggerA, "getBoundingClientRect").mockReturnValue({
    left: 20,
    right: 200,
    top: 40,
    bottom: 70,
    width: 180,
    height: 30,
    x: 20,
    y: 40,
    toJSON: () => ({}),
  });

  await act(async () => {
    triggerA.dispatchEvent(
      new MouseEvent("mouseover", {
        bubbles: true,
        clientX: 110,
        clientY: 55,
      }),
    );
  });

  // Should NOT open immediately before openDelayMs (120ms).
  expect(document.body.textContent).not.toContain("Child B1");

  await act(async () => {
    await vi.advanceTimersByTimeAsync(120);
  });
  expect(document.body.textContent).toContain("Child B1");

  const subContent = document.querySelector(
    '[data-slot="dropdown-menu-sub-content"]',
  ) as HTMLElement;
  vi.spyOn(subContent, "getBoundingClientRect").mockReturnValue({
    left: 210,
    right: 340,
    top: 40,
    bottom: 200,
    width: 130,
    height: 160,
    x: 210,
    y: 40,
    toJSON: () => ({}),
  });

  // Move pointer inside the safe triangle while crossing Sibling C toward Submenu B.
  await act(async () => {
    triggerA.dispatchEvent(
      new MouseEvent("mouseout", {
        bubbles: true,
        clientX: 170,
        clientY: 95,
      }),
    );
    siblingC.dispatchEvent(
      new MouseEvent("mouseover", {
        bubbles: true,
        clientX: 170,
        clientY: 95,
      }),
    );
  });

  // Still inside closeDelay window & safe triangle: Submenu B remains open.
  await act(async () => {
    await vi.advanceTimersByTimeAsync(80);
  });
  expect(document.body.textContent).toContain("Child B1");

  // Finish moving cursor outside the triangle and wait closeDelayMs -> closes cleanly.
  await act(async () => {
    document.dispatchEvent(
      new MouseEvent("mousemove", { clientX: 80, clientY: 160 }),
    );
    await vi.advanceTimersByTimeAsync(180);
  });
  expect(document.body.textContent).not.toContain("Child B1");

  await act(async () => root.unmount());
});
