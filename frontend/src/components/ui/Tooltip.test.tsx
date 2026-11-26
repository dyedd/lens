// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardSidebar } from "@/components/shell/DashboardSidebar";
import { SidebarProvider } from "@/components/ui/SidebarContext";
import { TooltipProvider, TruncatedTooltip } from "./Tooltip";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function stubMatchMedia() {
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    media: "",
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }));
}

describe("TruncatedTooltip", () => {
  it("stays suppressed when text fits and opens only when truncated", async () => {
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
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(
          <TooltipProvider delayDuration={0}>
            <TruncatedTooltip content="very-long-model-name">
              <span data-testid="label" className="truncate">
                very-long-model-name
              </span>
            </TruncatedTooltip>
          </TooltipProvider>,
        );
      });

      const trigger = container.querySelector('[data-testid="label"]');
      expect(trigger).not.toBeNull();
      if (!trigger) throw new Error("Missing trigger");

      Object.defineProperty(trigger, "clientWidth", {
        value: 120,
        configurable: true,
      });
      Object.defineProperty(trigger, "scrollWidth", {
        value: 120,
        configurable: true,
      });

      await act(async () => {
        trigger.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
        await vi.runAllTimersAsync();
      });
      expect(document.body.textContent).not.toContain(
        "very-long-model-namevery-long-model-name",
      );
      expect(
        document.querySelector('[data-slot="tooltip-content"]'),
      ).toBeNull();

      Object.defineProperty(trigger, "scrollWidth", {
        value: 240,
        configurable: true,
      });
      await act(async () => {
        trigger.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
        trigger.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
        await vi.runAllTimersAsync();
      });

      const content = document.querySelector('[data-slot="tooltip-content"]');
      expect(content).not.toBeNull();
      expect(document.querySelector('[role="tooltip"]')?.textContent).toBe(
        "very-long-model-name",
      );
    } finally {
      await act(async () => root.unmount());
      container.remove();
    }
  });
});

describe("DashboardSidebar tooltips", () => {
  it("omits version tooltip and suppresses sign-out tooltip when sidebar is expanded", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    stubMatchMedia();
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(
          <MemoryRouter>
            <TooltipProvider delayDuration={0}>
              <SidebarProvider defaultOpen>
                <DashboardSidebar
                  navItems={[]}
                  activeView="overview"
                  siteName="Lens"
                  logoUrl="/logo.svg"
                  currentVersion="0.2.18"
                  hasUpdate={false}
                  updateTitle=""
                  locale="zh-CN"
                  onSignOut={() => {}}
                />
              </SidebarProvider>
            </TooltipProvider>
          </MemoryRouter>,
        );
      });

      const versionEl = [...container.querySelectorAll("span")].find(
        (el) => el.textContent === "v0.2.18",
      );
      expect(versionEl?.getAttribute("data-slot")).not.toBe("tooltip-trigger");

      const signOutBtn = container.querySelector<HTMLButtonElement>(
        'button[aria-label="退出登录"]',
      );
      expect(signOutBtn).not.toBeNull();
      await act(async () => {
        signOutBtn?.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
        await vi.runAllTimersAsync();
      });
      const signOutTooltip = document.querySelector(
        '[data-slot="tooltip-content"]',
      );
      expect(signOutTooltip).toBeNull();
    } finally {
      await act(async () => root.unmount());
      container.remove();
    }
  });
});
