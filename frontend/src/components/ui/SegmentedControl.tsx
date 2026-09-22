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
        "inline-flex h-8 w-fit max-w-full items-center gap-1 rounded-full bg-muted/40 p-1",
        className,
      )}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={cn(
            "h-6 min-w-0 truncate rounded-full px-2.5 text-[11px] font-medium whitespace-nowrap transition-colors",
            option.value === value
              ? "bg-pure text-pure-foreground shadow-xs"
              : "bg-transparent text-foreground/60 hover:text-foreground",
          )}
          onClick={() => onValueChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
