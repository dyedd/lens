"use client";

import { cn } from "@/lib/utils";

/** Render a generic single-value segmented control. */
export function SegmentedControl<T extends string>({
  value,
  onValueChange,
  options,
  className,
}: {
  value: T;
  onValueChange: (value: T) => void;
  options: Array<{ value: T; label: string }>;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex w-fit max-w-full self-start items-center gap-1 overflow-x-auto rounded-xl border bg-muted p-0.5",
        className,
      )}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={cn(
            "h-7 min-w-0 max-w-[6.75rem] truncate rounded-lg px-3 text-sm font-medium leading-none transition-colors",
            option.value === value
              ? "bg-background text-foreground shadow-sm"
              : "bg-transparent text-muted-foreground hover:text-foreground",
          )}
          onClick={() => onValueChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
