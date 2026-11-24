// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { I18nProvider, useI18n } from "./I18nContext";

function I18nHarness() {
  const { locale, setLocale, t } = useI18n();
  return (
    <>
      <button type="button" onClick={() => setLocale("en-US")}>
        Switch to English
      </button>
      <span>{locale}</span>
      <span>{t.username}</span>
    </>
  );
}

async function renderI18n() {
  const container = document.createElement("div");
  const root = createRoot(container);
  await act(async () => {
    root.render(
      <I18nProvider>
        <I18nHarness />
      </I18nProvider>,
    );
  });
  return { container, root };
}

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
});

it("uses Chinese by default", async () => {
  const { container, root } = await renderI18n();
  try {
    expect(container.textContent).toContain("zh-CN用户名");
  } finally {
    await act(async () => root.unmount());
  }
});

it("restores a supported saved locale", async () => {
  localStorage.setItem("lens_locale", "en-US");
  const { container, root } = await renderI18n();
  try {
    expect(container.textContent).toContain("en-USUsername");
  } finally {
    await act(async () => root.unmount());
  }
});

it("persists the locale when switching languages", async () => {
  const { container, root } = await renderI18n();
  try {
    await act(async () => {
      container.querySelector("button")?.click();
    });

    expect(container.textContent).toContain("en-USUsername");
    expect(document.documentElement.lang).toBe("en-US");
    expect(localStorage.getItem("lens_locale")).toBe("en-US");
  } finally {
    await act(async () => root.unmount());
  }
});

it("switches language when local storage is unavailable", async () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("Storage unavailable", "SecurityError");
  });
  const container = document.createElement("div");
  const root = createRoot(container);

  try {
    await act(async () => {
      root.render(
        <I18nProvider>
          <I18nHarness />
        </I18nProvider>,
      );
    });
    await act(async () => {
      container.querySelector("button")?.click();
    });

    expect(container.textContent).toContain("en-USUsername");
    expect(document.documentElement.lang).toBe("en-US");
    expect(window.localStorage.setItem).toHaveBeenCalledWith(
      "lens_locale",
      "en-US",
    );
  } finally {
    await act(async () => root.unmount());
  }
});
