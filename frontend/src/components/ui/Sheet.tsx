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
        "fixed inset-0 z-50 bg-black/45 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0",
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
          "fixed z-50 flex flex-col gap-0 overflow-hidden border-border/75 bg-background text-[13px] text-foreground shadow-2xl outline-none transition ease-in-out data-open:animate-in data-closed:animate-out data-closed:duration-250 data-open:duration-350",
          side === "right" &&
            "inset-y-0 right-0 h-dvh w-full border-l data-open:slide-in-from-right data-closed:slide-out-to-right sm:max-w-[480px]",
          side === "left" &&
            "inset-y-0 left-0 h-dvh w-full border-r data-open:slide-in-from-left data-closed:slide-out-to-left sm:max-w-[480px]",
          side === "top" &&
            "inset-x-0 top-0 h-auto border-b data-open:slide-in-from-top data-closed:slide-out-to-top",
          side === "bottom" &&
            "inset-x-0 bottom-0 h-auto border-t data-open:slide-in-from-bottom data-closed:slide-out-to-bottom",
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
              className="absolute top-3.5 right-4 size-8 text-muted-foreground hover:text-foreground"
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
      className={cn(
        "flex flex-col gap-1 border-b border-border/60 px-6 py-4 pr-14",
        className,
      )}
      {...props}
    />
  );
}

function SheetFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-footer"
      className={cn(
        "mt-auto flex flex-row items-center justify-end gap-2 border-t border-border/60 bg-background px-6 py-3.5",
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
      className={cn(
        "text-base font-semibold tracking-tight text-card-foreground",
        className,
      )}
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
      className={cn("text-[13px] leading-5 text-muted-foreground", className)}
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
