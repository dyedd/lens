import { CheckIcon, ChevronRightIcon } from "lucide-react";
import { DropdownMenu as DropdownMenuPrimitive } from "radix-ui";
import * as React from "react";
import { cn } from "@/lib/classNames";
import {
  isPointerInSubmenuSafeTriangle,
  type Point,
} from "./submenuSafeTriangle";

const DEFAULT_SUB_OPEN_DELAY_MS = 120;
const DEFAULT_SUB_CLOSE_DELAY_MS = 180;

type SubmenuCoordinator = {
  activeSubId: string | null;
  openDelayMs: number;
  closeDelayMs: number;
  registerTrigger: (id: string, node: HTMLElement | null) => void;
  registerContent: (id: string, node: HTMLElement | null) => void;
  handleTriggerEnter: (id: string, point: Point) => void;
  handleTriggerLeave: (id: string, point: Point) => void;
  handleSubContentEnter: (id: string) => void;
  handleSubContentLeave: (id: string, point: Point) => void;
  handleSiblingItemEnter: (point: Point) => void;
  setSubOpen: (id: string, open: boolean) => void;
};

const MenuCoordinatorContext = React.createContext<SubmenuCoordinator | null>(
  null,
);
const SubmenuIdContext = React.createContext<string | null>(null);

function DropdownMenu({
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Root>) {
  return <DropdownMenuPrimitive.Root data-slot="dropdown-menu" {...props} />;
}

function DropdownMenuPortal({
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Portal>) {
  return (
    <DropdownMenuPrimitive.Portal data-slot="dropdown-menu-portal" {...props} />
  );
}

function DropdownMenuTrigger({
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Trigger>) {
  return (
    <DropdownMenuPrimitive.Trigger
      data-slot="dropdown-menu-trigger"
      {...props}
    />
  );
}

function DropdownMenuContent({
  className,
  align = "start",
  sideOffset = 4,
  subOpenDelayMs = DEFAULT_SUB_OPEN_DELAY_MS,
  subCloseDelayMs = DEFAULT_SUB_CLOSE_DELAY_MS,
  onPointerMove,
  onMouseMove,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Content> & {
  subOpenDelayMs?: number;
  subCloseDelayMs?: number;
}) {
  const [activeSubId, setActiveSubId] = React.useState<string | null>(null);
  const activeSubIdRef = React.useRef<string | null>(null);
  const triggersRef = React.useRef(new Map<string, HTMLElement>());
  const contentsRef = React.useRef(new Map<string, HTMLElement>());
  const pointerRef = React.useRef<Point | null>(null);
  const originRef = React.useRef<Point | null>(null);
  const openTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const deferredSwitchRef = React.useRef<(() => void) | null>(null);

  const clearTimers = React.useCallback(() => {
    if (openTimerRef.current !== null) {
      clearTimeout(openTimerRef.current);
      openTimerRef.current = null;
    }
    if (closeTimerRef.current !== null) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }, []);

  React.useEffect(() => () => clearTimers(), [clearTimers]);

  const setActive = React.useCallback((nextId: string | null) => {
    activeSubIdRef.current = nextId;
    setActiveSubId(nextId);
  }, []);

  const isInsideSafeTriangle = React.useCallback((point: Point) => {
    const currentId = activeSubIdRef.current;
    const origin = originRef.current;
    if (!currentId || !origin) return false;
    const subEl = contentsRef.current.get(currentId);
    if (!subEl) return false;
    const subRect = subEl.getBoundingClientRect();
    const triggerEl = triggersRef.current.get(currentId);
    const triggerRect = triggerEl ? triggerEl.getBoundingClientRect() : null;
    return isPointerInSubmenuSafeTriangle(point, origin, subRect, triggerRect);
  }, []);

  const scheduleClose = React.useCallback(
    (delayMs: number) => {
      if (closeTimerRef.current !== null) {
        clearTimeout(closeTimerRef.current);
      }
      closeTimerRef.current = setTimeout(() => {
        closeTimerRef.current = null;
        const deferred = deferredSwitchRef.current;
        deferredSwitchRef.current = null;
        setActive(null);
        originRef.current = null;
        if (deferred) deferred();
      }, delayMs);
    },
    [setActive],
  );

  const trackPointer = React.useCallback(
    (point: Point) => {
      pointerRef.current = point;
      const currentId = activeSubIdRef.current;
      if (!currentId) return;
      const triggerEl = triggersRef.current.get(currentId);
      if (triggerEl) {
        const rect = triggerEl.getBoundingClientRect();
        if (
          point.x >= rect.left &&
          point.x <= rect.right &&
          point.y >= rect.top &&
          point.y <= rect.bottom
        ) {
          originRef.current = point;
        }
      }
      if (deferredSwitchRef.current) {
        if (isInsideSafeTriangle(point)) {
          scheduleClose(subCloseDelayMs);
        } else {
          const deferred = deferredSwitchRef.current;
          deferredSwitchRef.current = null;
          clearTimers();
          deferred();
        }
      }
    },
    [clearTimers, isInsideSafeTriangle, scheduleClose, subCloseDelayMs],
  );

  React.useEffect(() => {
    if (!activeSubId) return;
    function handleDocumentMove(event: MouseEvent) {
      trackPointer({ x: event.clientX, y: event.clientY });
    }
    document.addEventListener("mousemove", handleDocumentMove);
    return () => document.removeEventListener("mousemove", handleDocumentMove);
  }, [activeSubId, trackPointer]);

  const coordinator = React.useMemo<SubmenuCoordinator>(
    () => ({
      activeSubId,
      openDelayMs: subOpenDelayMs,
      closeDelayMs: subCloseDelayMs,
      registerTrigger: (id, node) => {
        if (node) triggersRef.current.set(id, node);
        else triggersRef.current.delete(id);
      },
      registerContent: (id, node) => {
        if (node) contentsRef.current.set(id, node);
        else contentsRef.current.delete(id);
      },
      handleTriggerEnter: (id, point) => {
        pointerRef.current = point;
        const currentId = activeSubIdRef.current;
        if (currentId === id) {
          originRef.current = point;
          deferredSwitchRef.current = null;
          if (closeTimerRef.current !== null) {
            clearTimeout(closeTimerRef.current);
            closeTimerRef.current = null;
          }
          return;
        }

        const openTarget = () => {
          if (openTimerRef.current !== null) {
            clearTimeout(openTimerRef.current);
          }
          openTimerRef.current = setTimeout(() => {
            openTimerRef.current = null;
            originRef.current = pointerRef.current ?? point;
            setActive(id);
          }, subOpenDelayMs);
        };

        if (currentId && isInsideSafeTriangle(point)) {
          deferredSwitchRef.current = openTarget;
          scheduleClose(subCloseDelayMs);
          return;
        }

        clearTimers();
        deferredSwitchRef.current = null;
        if (currentId) setActive(null);
        openTarget();
      },
      handleTriggerLeave: (id, point) => {
        pointerRef.current = point;
        if (activeSubIdRef.current !== id) {
          if (openTimerRef.current !== null) {
            clearTimeout(openTimerRef.current);
            openTimerRef.current = null;
          }
          return;
        }
        originRef.current = originRef.current ?? point;
        scheduleClose(subCloseDelayMs);
      },
      handleSubContentEnter: (id) => {
        if (activeSubIdRef.current !== id) return;
        deferredSwitchRef.current = null;
        if (closeTimerRef.current !== null) {
          clearTimeout(closeTimerRef.current);
          closeTimerRef.current = null;
        }
      },
      handleSubContentLeave: (id, point) => {
        pointerRef.current = point;
        if (activeSubIdRef.current !== id) return;
        scheduleClose(subCloseDelayMs);
      },
      handleSiblingItemEnter: (point) => {
        pointerRef.current = point;
        const currentId = activeSubIdRef.current;
        if (!currentId) return;
        if (isInsideSafeTriangle(point)) {
          deferredSwitchRef.current = () => {
            setActive(null);
            originRef.current = null;
          };
          scheduleClose(subCloseDelayMs);
          return;
        }
        deferredSwitchRef.current = null;
        scheduleClose(subCloseDelayMs);
      },
      setSubOpen: (id, open) => {
        clearTimers();
        deferredSwitchRef.current = null;
        if (open) {
          setActive(id);
        } else if (activeSubIdRef.current === id) {
          setActive(null);
          originRef.current = null;
        }
      },
    }),
    [
      activeSubId,
      clearTimers,
      isInsideSafeTriangle,
      scheduleClose,
      setActive,
      subCloseDelayMs,
      subOpenDelayMs,
    ],
  );

  return (
    <MenuCoordinatorContext.Provider value={coordinator}>
      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content
          data-slot="dropdown-menu-content"
          sideOffset={sideOffset}
          align={align}
          onPointerMove={(event) => {
            trackPointer({ x: event.clientX, y: event.clientY });
            onPointerMove?.(event);
          }}
          onMouseMove={(event) => {
            trackPointer({ x: event.clientX, y: event.clientY });
            onMouseMove?.(event);
          }}
          className={cn(
            "z-50 max-h-(--radix-dropdown-menu-content-available-height) min-w-32 origin-(--radix-dropdown-menu-content-transform-origin) overflow-x-hidden overflow-y-auto rounded-xl border-[0.5px] border-border bg-popover p-1.5 text-popover-foreground shadow-xs duration-100 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 data-[state=closed]:overflow-hidden data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
            className,
          )}
          {...props}
        />
      </DropdownMenuPrimitive.Portal>
    </MenuCoordinatorContext.Provider>
  );
}

function DropdownMenuGroup({
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Group>) {
  return (
    <DropdownMenuPrimitive.Group data-slot="dropdown-menu-group" {...props} />
  );
}

function DropdownMenuItem({
  className,
  inset,
  variant = "default",
  onMouseEnter,
  onPointerEnter,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Item> & {
  inset?: boolean;
  variant?: "default" | "destructive";
}) {
  const coordinator = React.useContext(MenuCoordinatorContext);
  return (
    <DropdownMenuPrimitive.Item
      data-slot="dropdown-menu-item"
      data-inset={inset}
      data-variant={variant}
      onMouseEnter={(event) => {
        coordinator?.handleSiblingItemEnter({
          x: event.clientX,
          y: event.clientY,
        });
        onMouseEnter?.(event);
      }}
      onPointerEnter={(event) => {
        coordinator?.handleSiblingItemEnter({
          x: event.clientX,
          y: event.clientY,
        });
        onPointerEnter?.(event);
      }}
      className={cn(
        "group/dropdown-menu-item relative flex cursor-default items-center gap-1.5 rounded-md px-1.5 py-1 text-[13px] outline-hidden select-none focus:bg-accent focus:text-accent-foreground not-data-[variant=destructive]:focus:**:text-accent-foreground data-inset:pl-7 data-[variant=destructive]:text-destructive data-[variant=destructive]:focus:bg-destructive/10 data-[variant=destructive]:focus:text-destructive dark:data-[variant=destructive]:focus:bg-destructive/20 data-disabled:pointer-events-none data-disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4 data-[variant=destructive]:*:[svg]:text-destructive",
        className,
      )}
      {...props}
    />
  );
}

function DropdownMenuCheckboxItem({
  className,
  children,
  checked,
  inset,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.CheckboxItem> & {
  inset?: boolean;
}) {
  return (
    <DropdownMenuPrimitive.CheckboxItem
      data-slot="dropdown-menu-checkbox-item"
      data-inset={inset}
      className={cn(
        "relative flex cursor-default items-center gap-1.5 rounded-md py-1 pr-8 pl-1.5 text-[13px] outline-hidden select-none focus:bg-accent focus:text-accent-foreground focus:**:text-accent-foreground data-inset:pl-7 data-disabled:pointer-events-none data-disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className,
      )}
      checked={checked}
      {...props}
    >
      <span
        className="pointer-events-none absolute right-2 flex items-center justify-center"
        data-slot="dropdown-menu-checkbox-item-indicator"
      >
        <DropdownMenuPrimitive.ItemIndicator>
          <CheckIcon />
        </DropdownMenuPrimitive.ItemIndicator>
      </span>
      {children}
    </DropdownMenuPrimitive.CheckboxItem>
  );
}

function DropdownMenuRadioGroup({
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.RadioGroup>) {
  return (
    <DropdownMenuPrimitive.RadioGroup
      data-slot="dropdown-menu-radio-group"
      {...props}
    />
  );
}

function DropdownMenuRadioItem({
  className,
  children,
  inset,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.RadioItem> & {
  inset?: boolean;
}) {
  return (
    <DropdownMenuPrimitive.RadioItem
      data-slot="dropdown-menu-radio-item"
      data-inset={inset}
      className={cn(
        "relative flex cursor-default items-center gap-1.5 rounded-md py-1 pr-8 pl-1.5 text-[13px] outline-hidden select-none focus:bg-accent focus:text-accent-foreground focus:**:text-accent-foreground data-inset:pl-7 data-disabled:pointer-events-none data-disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className,
      )}
      {...props}
    >
      <span
        className="pointer-events-none absolute right-2 flex items-center justify-center"
        data-slot="dropdown-menu-radio-item-indicator"
      >
        <DropdownMenuPrimitive.ItemIndicator>
          <CheckIcon />
        </DropdownMenuPrimitive.ItemIndicator>
      </span>
      {children}
    </DropdownMenuPrimitive.RadioItem>
  );
}

function DropdownMenuLabel({
  className,
  inset,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Label> & {
  inset?: boolean;
}) {
  return (
    <DropdownMenuPrimitive.Label
      data-slot="dropdown-menu-label"
      data-inset={inset}
      className={cn(
        "px-1.5 py-1 text-xs font-medium text-muted-foreground data-inset:pl-7",
        className,
      )}
      {...props}
    />
  );
}

function DropdownMenuSeparator({
  className,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Separator>) {
  return (
    <DropdownMenuPrimitive.Separator
      data-slot="dropdown-menu-separator"
      className={cn("-mx-1 my-1 h-px bg-border", className)}
      {...props}
    />
  );
}

function DropdownMenuShortcut({
  className,
  ...props
}: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="dropdown-menu-shortcut"
      className={cn(
        "ml-auto text-xs tracking-widest text-muted-foreground group-focus/dropdown-menu-item:text-accent-foreground",
        className,
      )}
      {...props}
    />
  );
}

function DropdownMenuSub({
  open,
  onOpenChange,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Sub>) {
  const id = React.useId();
  const coordinator = React.useContext(MenuCoordinatorContext);
  const resolvedOpen =
    open !== undefined
      ? open
      : coordinator
        ? coordinator.activeSubId === id
        : undefined;

  return (
    <SubmenuIdContext.Provider value={id}>
      <DropdownMenuPrimitive.Sub
        data-slot="dropdown-menu-sub"
        open={resolvedOpen}
        onOpenChange={(nextOpen) => {
          coordinator?.setSubOpen(id, nextOpen);
          onOpenChange?.(nextOpen);
        }}
        {...props}
      />
    </SubmenuIdContext.Provider>
  );
}

function DropdownMenuSubTrigger({
  className,
  inset,
  children,
  onMouseEnter,
  onMouseLeave,
  onPointerEnter,
  onPointerLeave,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.SubTrigger> & {
  inset?: boolean;
}) {
  const subId = React.useContext(SubmenuIdContext);
  const coordinator = React.useContext(MenuCoordinatorContext);
  const registerTrigger = coordinator?.registerTrigger;
  const triggerRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!subId || !registerTrigger) return;
    registerTrigger(subId, triggerRef.current);
    return () => registerTrigger(subId, null);
  }, [registerTrigger, subId]);

  return (
    <DropdownMenuPrimitive.SubTrigger
      ref={triggerRef}
      data-slot="dropdown-menu-sub-trigger"
      data-inset={inset}
      onMouseEnter={(event) => {
        if (subId && coordinator) {
          coordinator.handleTriggerEnter(subId, {
            x: event.clientX,
            y: event.clientY,
          });
        }
        onMouseEnter?.(event);
      }}
      onPointerEnter={(event) => {
        if (subId && coordinator) {
          coordinator.handleTriggerEnter(subId, {
            x: event.clientX,
            y: event.clientY,
          });
        }
        onPointerEnter?.(event);
      }}
      onMouseLeave={(event) => {
        if (subId && coordinator) {
          coordinator.handleTriggerLeave(subId, {
            x: event.clientX,
            y: event.clientY,
          });
        }
        onMouseLeave?.(event);
      }}
      onPointerLeave={(event) => {
        if (subId && coordinator) {
          coordinator.handleTriggerLeave(subId, {
            x: event.clientX,
            y: event.clientY,
          });
        }
        onPointerLeave?.(event);
      }}
      className={cn(
        "flex cursor-default items-center gap-1.5 rounded-md px-1.5 py-1 text-[13px] outline-hidden select-none focus:bg-accent focus:text-accent-foreground not-data-[variant=destructive]:focus:**:text-accent-foreground data-inset:pl-7 data-open:bg-accent data-open:text-accent-foreground [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className,
      )}
      {...props}
    >
      {children}
      <ChevronRightIcon className="ml-auto" />
    </DropdownMenuPrimitive.SubTrigger>
  );
}

function DropdownMenuSubContent({
  className,
  onMouseEnter,
  onMouseLeave,
  onPointerEnter,
  onPointerLeave,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.SubContent>) {
  const subId = React.useContext(SubmenuIdContext);
  const coordinator = React.useContext(MenuCoordinatorContext);
  const registerContent = coordinator?.registerContent;
  const contentRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!subId || !registerContent) return;
    registerContent(subId, contentRef.current);
    return () => registerContent(subId, null);
  }, [registerContent, subId]);

  return (
    <DropdownMenuPrimitive.SubContent
      ref={contentRef}
      data-slot="dropdown-menu-sub-content"
      onMouseEnter={(event) => {
        if (subId && coordinator) coordinator.handleSubContentEnter(subId);
        onMouseEnter?.(event);
      }}
      onPointerEnter={(event) => {
        if (subId && coordinator) coordinator.handleSubContentEnter(subId);
        onPointerEnter?.(event);
      }}
      onMouseLeave={(event) => {
        if (subId && coordinator) {
          coordinator.handleSubContentLeave(subId, {
            x: event.clientX,
            y: event.clientY,
          });
        }
        onMouseLeave?.(event);
      }}
      onPointerLeave={(event) => {
        if (subId && coordinator) {
          coordinator.handleSubContentLeave(subId, {
            x: event.clientX,
            y: event.clientY,
          });
        }
        onPointerLeave?.(event);
      }}
      className={cn(
        "z-50 min-w-[96px] origin-(--radix-dropdown-menu-content-transform-origin) overflow-hidden rounded-xl border-[0.5px] border-border bg-popover p-1.5 text-popover-foreground shadow-xs duration-100 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
        className,
      )}
      {...props}
    />
  );
}

export {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
};
