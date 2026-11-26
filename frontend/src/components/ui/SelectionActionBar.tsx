import { X } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/classNames";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

type SelectionActionBarProps = {
  locale: Locale;
  count: number;
  onClear?: () => void;
  children?: ReactNode;
  className?: string;
};

/** Contextual horizontal action bar displayed when table or card rows are selected. */
export function SelectionActionBar({
  locale,
  count,
  onClear,
  children,
  className,
}: SelectionActionBarProps) {
  if (count <= 0) return null;

  return (
    <div
      role="region"
      aria-label={titleForLocale(locale, "已选操作", "Selected actions")}
      className={cn(
        "flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border/80 bg-muted/70 px-3 py-1.5 text-[13px]",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-md bg-primary px-1.5 font-mono text-xs font-medium tabular-nums text-primary-foreground">
          {count}
        </span>
        <span className="font-medium text-foreground">
          {titleForLocale(locale, `已选 ${count} 项`, `${count} selected`)}
        </span>
        {onClear ? (
          <Button
            type="button"
            variant="ghost"
            size="xs"
            className="h-6 gap-1 px-1.5 text-xs text-muted-foreground hover:text-foreground"
            onClick={onClear}
          >
            <X className="size-3" />
            {titleForLocale(locale, "取消选择", "Clear")}
          </Button>
        ) : null}
      </div>
      {children ? (
        <div className="flex flex-wrap items-center gap-1">{children}</div>
      ) : null}
    </div>
  );
}
