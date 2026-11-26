import { Tooltip as TooltipPrimitive } from "radix-ui";
import {
  type ComponentProps,
  type ReactElement,
  type ReactNode,
  useState,
} from "react";

import { cn } from "@/lib/classNames";

function TooltipProvider({
  delayDuration = 350,
  ...props
}: ComponentProps<typeof TooltipPrimitive.Provider>) {
  return (
    <TooltipPrimitive.Provider
      data-slot="tooltip-provider"
      delayDuration={delayDuration}
      {...props}
    />
  );
}

function Tooltip({ ...props }: ComponentProps<typeof TooltipPrimitive.Root>) {
  return <TooltipPrimitive.Root data-slot="tooltip" {...props} />;
}

function TooltipTrigger({
  ...props
}: ComponentProps<typeof TooltipPrimitive.Trigger>) {
  return <TooltipPrimitive.Trigger data-slot="tooltip-trigger" {...props} />;
}

function TooltipContent({
  className,
  sideOffset = 0,
  children,
  ...props
}: ComponentProps<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        data-slot="tooltip-content"
        sideOffset={sideOffset}
        className={cn(
          "z-50 inline-flex w-fit max-w-xs origin-(--radix-tooltip-content-transform-origin) items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs text-background has-data-[slot=kbd]:pr-1.5 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 **:data-[slot=kbd]:relative **:data-[slot=kbd]:isolate **:data-[slot=kbd]:z-50 **:data-[slot=kbd]:rounded-md data-[state=delayed-open]:animate-in data-[state=delayed-open]:fade-in-0 data-[state=delayed-open]:zoom-in-95 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
          className,
        )}
        {...props}
      >
        {children}
        <TooltipPrimitive.Arrow className="z-50 size-2.5 translate-y-[calc(-50%_-_2px)] rotate-45 rounded-[2px] bg-foreground fill-foreground" />
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  );
}

function measureElementOverflow(element: HTMLElement) {
  const measured = element.classList.contains("truncate")
    ? element
    : (element.querySelector<HTMLElement>(".truncate") ?? element);
  return measured.scrollWidth > measured.clientWidth + 1;
}

/** Shows tooltip only when the child or its truncated text descendant actually overflows. */
function TruncatedTooltip({
  content,
  contentClassName,
  side,
  children,
}: {
  content: ReactNode;
  contentClassName?: string;
  side?: ComponentProps<typeof TooltipContent>["side"];
  children: ReactElement;
}) {
  const [isOverflowing, setIsOverflowing] = useState(false);

  if (!content) return children;

  return (
    <Tooltip
      onOpenChange={(open) => {
        if (!open) setIsOverflowing(false);
      }}
    >
      <TooltipTrigger
        asChild
        onPointerEnter={(event) => {
          setIsOverflowing(measureElementOverflow(event.currentTarget));
        }}
        onFocus={(event) => {
          setIsOverflowing(measureElementOverflow(event.currentTarget));
        }}
      >
        {children}
      </TooltipTrigger>
      {isOverflowing ? (
        <TooltipContent side={side} className={contentClassName}>
          {content}
        </TooltipContent>
      ) : null}
    </Tooltip>
  );
}

export {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
  TruncatedTooltip,
};
