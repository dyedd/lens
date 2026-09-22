import { Loader2Icon } from "lucide-react";
import type { ComponentProps } from "react";
import { cn } from "@/lib/classNames";

function Spinner({
  className,
  label,
  ...props
}: ComponentProps<"svg"> & { label?: string }) {
  const accessibleLabel = label ?? props["aria-label"];
  return (
    <Loader2Icon
      role={accessibleLabel ? "status" : undefined}
      aria-label={accessibleLabel}
      aria-hidden={accessibleLabel ? undefined : true}
      className={cn("size-4 animate-spin text-muted-foreground", className)}
      {...props}
    />
  );
}

export { Spinner };
