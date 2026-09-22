import { XIcon } from "lucide-react";
import { Dialog as SheetPrimitive } from "radix-ui";
import type * as React from "react";
import { Button } from "@/components/ui/Button";
import { shouldIgnoreOverlayOutsideClick } from "@/components/ui/overlayOutsideClick";
import { cn } from "@/lib/classNames";

function Sheet({ ...props }: React.ComponentProps<typeof SheetPrimitive.Root>) {
  return <SheetPrimitive.Root data-slot="sheet" {...props} />;
}

function SheetTrigger({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Trigger>) {
  return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props} />;
}

function SheetClose({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Close>) {
  return <SheetPrimitive.Close data-slot="sheet-close" {...props} />;
}

function SheetPortal({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Portal>) {
  return <SheetPrimitive.Portal data-slot="sheet-portal" {...props} />;
}

function SheetOverlay({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Overlay>) {
  return (
    <SheetPrimitive.Overlay
      data-slot="sheet-overlay"
      className={cn(
        "fixed inset-0 z-50 bg-black/50 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0",
        className,
      )}
      {...props}
    />
  );
}

function SheetContent({
  className,
  children,
  side = "right",
  showCloseButton = true,
  showOverlay = true,
  onInteractOutside,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & {
  side?: "top" | "right" | "bottom" | "left";
  showCloseButton?: boolean;
  showOverlay?: boolean;
}) {
  return (
    <SheetPortal>
      {showOverlay ? <SheetOverlay /> : null}
      <SheetPrimitive.Content
        data-slot="sheet-content"
        data-side={side}
        className={cn(
          "fixed z-50 flex flex-col gap-4 overflow-hidden border border-border/60 bg-background/96 text-sm text-foreground shadow-2xl outline-none backdrop-blur transition ease-in-out data-open:animate-in data-closed:animate-out data-closed:duration-300 data-open:duration-500",
          side === "right" &&
            "inset-y-3 right-3 h-[calc(100dvh-1.5rem)] w-[calc(100vw-1.5rem)] rounded-3xl data-open:slide-in-from-right data-closed:slide-out-to-right sm:max-w-sm",
          side === "left" &&
            "inset-y-3 left-3 h-[calc(100dvh-1.5rem)] w-[calc(100vw-1.5rem)] rounded-3xl data-open:slide-in-from-left data-closed:slide-out-to-left sm:max-w-sm",
          side === "top" &&
            "inset-x-3 top-3 h-auto rounded-3xl data-open:slide-in-from-top data-closed:slide-out-to-top",
          side === "bottom" &&
            "inset-x-3 bottom-3 h-auto rounded-3xl data-open:slide-in-from-bottom data-closed:slide-out-to-bottom",
          className,
        )}
        onInteractOutside={(event) => {
          if (shouldIgnoreOverlayOutsideClick(event.target)) {
            event.preventDefault();
            return;
          }
          onInteractOutside?.(event);
        }}
        {...props}
      >
        {children}
        {showCloseButton ? (
          <SheetPrimitive.Close data-slot="sheet-close" asChild>
            <Button
              variant="ghost"
              className="absolute top-6 right-6 size-8 opacity-70 hover:opacity-100"
              size="icon-sm"
            >
              <XIcon className="size-4" />
              <span className="sr-only">Close</span>
            </Button>
          </SheetPrimitive.Close>
        ) : null}
      </SheetPrimitive.Content>
    </SheetPortal>
  );
}

function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-header"
      className={cn("flex flex-col gap-1.5 px-6 pt-6 pb-4", className)}
      {...props}
    />
  );
}

function SheetFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-footer"
      className={cn(
        "mt-auto flex flex-row justify-end gap-2 rounded-b-3xl border-t bg-background/96 px-6 py-4 [&_[data-slot=button][data-size=default]]:h-7",
        className,
      )}
      {...props}
    />
  );
}

function SheetTitle({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Title>) {
  return (
    <SheetPrimitive.Title
      data-slot="sheet-title"
      className={cn("text-sm font-semibold text-foreground", className)}
      {...props}
    />
  );
}

function SheetDescription({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Description>) {
  return (
    <SheetPrimitive.Description
      data-slot="sheet-description"
      className={cn("text-xs text-muted-foreground", className)}
      {...props}
    />
  );
}

export {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
};
