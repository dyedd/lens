/** Keep popovers inside a dialog or sheet from counting as an outside click. */
export function shouldIgnoreOverlayOutsideClick(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  return Boolean(
    target.closest('[data-slot="combobox-content"]') ||
      target.closest('[data-slot="combobox-item"]') ||
      target.closest('[data-slot="select-content"]') ||
      target.closest('[data-slot="select-item"]') ||
      target.closest('[data-slot="popover-content"]') ||
      target.closest('[data-slot="dropdown-menu-content"]'),
  );
}
