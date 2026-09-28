import { ListChecks, ToggleLeft, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Button } from "@/components/ui/Button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { ToolbarButton } from "@/components/ui/ToolbarButton";
import { cn } from "@/lib/classNames";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

type Props = {
  locale: Locale;
  count: number;
  isBusy?: boolean;
  /** `toolbar` sits in a list toolbar; `section` sits in a settings header. */
  placement?: "toolbar" | "section";
  /** Layers the popover above an open dialog. */
  isInDialog?: boolean;
  onSetEnabled?: (enabled: boolean) => void;
  onDelete?: () => void;
  children?: ReactNode;
};

const ACTION_CLASS =
  "mt-1 h-7 w-full justify-start gap-2 px-2 text-[11px] text-foreground/70 shadow-none hover:bg-muted hover:text-foreground";

/** Renders the shared "bulk" popover for selected rows. */
export function BulkActionsPopover({
  locale,
  count,
  isBusy = false,
  placement = "toolbar",
  isInDialog = false,
  onSetEnabled,
  onDelete,
  children,
}: Props) {
  const [enabledChoice, setEnabledChoice] = useState<
    "enabled" | "disabled" | ""
  >("");
  const label = titleForLocale(locale, "批量", "Bulk");
  const isTriggerDisabled = count === 0 || isBusy;

  return (
    <Popover modal={isInDialog ? false : undefined}>
      <PopoverTrigger asChild>
        {placement === "toolbar" ? (
          <ToolbarButton disabled={isTriggerDisabled} aria-label={label}>
            <ListChecks className="size-3.5" />
            <span className="hidden sm:inline">{label}</span>
          </ToolbarButton>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-8 gap-1.5 px-2 text-xs text-muted-foreground shadow-none hover:bg-muted hover:text-foreground data-[state=open]:bg-muted data-[state=open]:text-foreground"
            disabled={isTriggerDisabled}
            aria-label={label}
          >
            <ListChecks className="size-3.5" />
            {label}
          </Button>
        )}
      </PopoverTrigger>
      <PopoverContent
        align={placement === "toolbar" ? "start" : "end"}
        className={cn("w-[240px] p-2", isInDialog && "z-[100]")}
      >
        <p className="flex h-7 items-center px-2 text-[11px] text-muted-foreground">
          {titleForLocale(locale, `已选 ${count} 项`, `${count} selected`)}
        </p>
        {onSetEnabled ? (
          <div className="flex h-7 w-full items-center gap-1.5">
            <Button
              type="button"
              variant="ghost"
              className="h-7 w-16 shrink-0 justify-start gap-2 px-2 text-[11px] text-foreground/70 shadow-none hover:bg-muted"
              disabled={!enabledChoice || isBusy}
              onClick={() => onSetEnabled(enabledChoice === "enabled")}
            >
              <ToggleLeft className="size-3" />
              {titleForLocale(locale, "应用", "Apply")}
            </Button>
            <Select
              value={enabledChoice || undefined}
              onValueChange={(value) =>
                setEnabledChoice(value as "enabled" | "disabled")
              }
            >
              <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                <SelectValue
                  placeholder={titleForLocale(locale, "状态", "Status")}
                />
              </SelectTrigger>
              <SelectContent className={isInDialog ? "z-[100]" : undefined}>
                <SelectItem value="enabled">
                  {titleForLocale(locale, "启用", "Enable")}
                </SelectItem>
                <SelectItem value="disabled">
                  {titleForLocale(locale, "停用", "Disable")}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        ) : null}
        {children}
        {onDelete ? (
          <BulkActionButton
            icon={<Trash2 className="size-3.5" />}
            label={titleForLocale(locale, "批量删除", "Delete selected")}
            isBusy={isBusy}
            onClick={onDelete}
          />
        ) : null}
      </PopoverContent>
    </Popover>
  );
}

/** Extra action row inside `BulkActionsPopover`. */
export function BulkActionButton({
  icon,
  label,
  isBusy = false,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  isBusy?: boolean;
  onClick: () => void;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      className={ACTION_CLASS}
      disabled={isBusy}
      onClick={onClick}
    >
      {icon}
      {label}
    </Button>
  );
}
