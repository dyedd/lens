"use client";

import { useEffect } from "react";

/** Protects unsaved edits and focuses a newly added protocol configuration. */
export function useChannelFormEffects({
  isDialogOpen,
  hasUnsavedChanges,
  shouldFocusAddedConfig,
  protocolConfigCount,
  finishAddedConfigFocus,
}: {
  isDialogOpen: boolean;
  hasUnsavedChanges: boolean;
  shouldFocusAddedConfig: boolean;
  protocolConfigCount: number;
  finishAddedConfigFocus: () => void;
}) {
  useEffect(() => {
    if (!isDialogOpen) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges, isDialogOpen]);

  useEffect(() => {
    if (!shouldFocusAddedConfig || !isDialogOpen) return;
    const index = protocolConfigCount - 1;
    if (index < 0) return;
    const section = document.querySelector<HTMLElement>(
      `[data-protocol-config-index="${index}"]`,
    );
    if (!section) return;
    section.scrollIntoView({ behavior: "smooth", block: "center" });
    (section.querySelector<HTMLInputElement>("input") ?? section).focus({
      preventScroll: true,
    });
    finishAddedConfigFocus();
  }, [
    finishAddedConfigFocus,
    isDialogOpen,
    protocolConfigCount,
    shouldFocusAddedConfig,
  ]);
}
