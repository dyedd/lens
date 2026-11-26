import { ToggleGroup as ToggleGroupPrimitive } from "radix-ui";
import type * as React from "react";
import { buttonVariants } from "@/components/ui/Button";
import { cn } from "@/lib/classNames";

function ToggleGroup({
  className,
  ...props
}: React.ComponentProps<typeof ToggleGroupPrimitive.Root>) {
  return (
    <ToggleGroupPrimitive.Root
      data-slot="toggle-group"
      className={cn(
        "inline-flex w-fit flex-wrap items-center gap-1",
        className,
      )}
      {...props}
    />
  );
}

function ToggleGroupItem({
  className,
  ...props
}: React.ComponentProps<typeof ToggleGroupPrimitive.Item>) {
  return (
    <ToggleGroupPrimitive.Item
      data-slot="toggle-group-item"
      className={cn(
        buttonVariants({ variant: "ghost", size: "sm" }),
        "h-7 rounded-lg px-2.5 text-[13px] font-medium text-muted-foreground hover:bg-muted/50 hover:text-foreground data-[state=on]:bg-muted data-[state=on]:text-foreground",
        className,
      )}
      {...props}
    />
  );
}

export { ToggleGroup, ToggleGroupItem };
