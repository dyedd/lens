import type { ComponentProps } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/classNames";

/** Ghost control used in list toolbars. */
export function ToolbarButton({
  className,
  ...props
}: ComponentProps<typeof Button>) {
  return (
    <Button
      type="button"
      size="sm"
      variant="ghost"
      className={cn(
        "h-8 gap-1.5 px-2 text-xs text-muted-foreground shadow-none hover:bg-muted hover:text-foreground data-[state=open]:bg-muted data-[state=open]:text-foreground",
        className,
      )}
      {...props}
    />
  );
}
