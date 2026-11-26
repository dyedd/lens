import { cn } from "@/lib/classNames";

/** Render a compact pill segmented control. */
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
        "inline-flex w-fit max-w-full flex-wrap items-center gap-1",
        className,
      )}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          className={cn(
            "inline-flex h-7 min-w-0 items-center justify-center rounded-lg px-2.5 text-[13px] font-medium whitespace-nowrap transition-colors",
            option.value === value
              ? "bg-muted text-foreground"
              : "bg-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground",
          )}
          onClick={() => onValueChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
