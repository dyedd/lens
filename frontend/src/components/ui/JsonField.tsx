import type * as React from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/classNames";

type Props = {
  id?: string;
  value: string;
  placeholder?: string;
  disabled?: boolean;
  height?: number;
  className?: string;
  actions?: React.ReactNode;
  formatLabel: string;
  invalidFormatMessage: string;
  onChange: (value: string) => void;
};

function formatJson(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return "";
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2);
  } catch {
    return null;
  }
}

/** Renders a JSON textarea with a format action and optional toolbar. */
export function JsonField({
  id,
  value,
  placeholder,
  disabled = false,
  height = 220,
  className,
  actions,
  formatLabel,
  invalidFormatMessage,
  onChange,
}: Props) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-md border border-input/40 bg-transparent text-xs shadow-none transition-[color,box-shadow] focus-within:border-ring/60 focus-within:ring-[1px] focus-within:ring-ring/40 dark:bg-input/30",
        disabled && "opacity-60",
        className,
      )}
      style={{ height }}
    >
      <div className="flex h-8 items-center justify-between border-b border-input/40 bg-muted/35 px-2">
        <span className="font-mono text-[11px] text-muted-foreground">
          JSON
        </span>
        <div className="flex items-center gap-2">
          {actions}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[11px]"
            disabled={disabled}
            onClick={() => {
              const next = formatJson(value);
              if (next === null) {
                toast.error(invalidFormatMessage);
                return;
              }
              onChange(next);
            }}
          >
            {formatLabel}
          </Button>
        </div>
      </div>
      <textarea
        id={id}
        spellCheck={false}
        disabled={disabled}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-[calc(100%-2rem)] w-full resize-none border-0 bg-transparent px-3 py-2 font-mono text-xs leading-5 outline-none placeholder:font-sans placeholder:text-muted-foreground"
      />
    </div>
  );
}
