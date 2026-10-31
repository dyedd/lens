import { type KeyboardEvent, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
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
import {
  formatContextWindow,
  parseContextWindowInput,
} from "@/lib/contextWindow";
import type { AggregatedModel, Locale } from "./channelTypes";

type Props = {
  model: AggregatedModel;
  locale: Locale;
  onCommit: (contextWindow: number | null) => void;
};

/**
 * Shows where a model's context window comes from and lets the admin change it.
 * The detected size (this upstream's, else the catalog's) applies until a
 * preset or typed value stores an override.
 */
export function ModelCapabilityPopover({ model, locale, onCommit }: Props) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [customMode, setCustomMode] = useState(false);
  const isZh = locale === "zh-CN";
  const fieldId = `context-window-${model.key.replace(/[^a-zA-Z0-9_-]/g, "-")}`;

  const override = model.contextWindow;
  const detected = model.autoContextWindow;

  function select(value: number | null) {
    onCommit(value);
    setOpen(false);
  }

  function applyDraft() {
    const parsed = parseContextWindowInput(draft);
    if (parsed === undefined) {
      toast.error(
        isZh
          ? "上下文格式无效，示例：200K、1M、128000"
          : "Invalid context window. Examples: 200K, 1M, 128000",
      );
      return;
    }
    setDraft("");
    select(parsed);
  }

  function handleDraftKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      applyDraft();
    }
  }

  const displayValue =
    override !== null
      ? formatContextWindow(override)
      : detected !== null
        ? formatContextWindow(detected)
        : isZh
          ? "未识别"
          : "Unknown";
  const selectedMode = customMode
    ? "custom"
    : override === null
      ? "auto"
      : "custom";

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setDraft("");
          setCustomMode(false);
        }
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={
            isZh
              ? `${model.modelName} 上下文窗口`
              : `${model.modelName} context window`
          }
          className="flex h-7 w-full min-w-0 items-center justify-end rounded-md border border-input/40 bg-transparent px-2 py-1 text-right font-mono text-xs tabular-nums shadow-none transition-[color,box-shadow,background-color] outline-none hover:bg-transparent focus-visible:border-primary/60 focus-visible:ring-[1px] focus-visible:ring-primary/40 data-[state=open]:border-primary/60 data-[state=open]:bg-transparent"
        >
          <span
            className={
              override !== null
                ? "text-foreground"
                : detected !== null
                  ? "text-muted-foreground"
                  : "font-sans text-muted-foreground"
            }
          >
            {displayValue}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="z-[100] w-[300px] gap-3 p-3">
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor={`${fieldId}-mode`}
            className="text-xs leading-5 font-normal text-muted-foreground"
          >
            {isZh ? "上下文窗口" : "Context window"}
          </label>
          <Select
            value={selectedMode}
            onValueChange={(value) => {
              if (value === "auto") {
                setCustomMode(false);
                select(null);
                return;
              }
              if (value === "custom") {
                setCustomMode(true);
                setDraft(override === null ? "" : String(override));
                return;
              }
              setCustomMode(false);
              const parsed = Number(value);
              if (Number.isInteger(parsed)) select(parsed);
            }}
          >
            <SelectTrigger id={`${fieldId}-mode`} className="h-8 w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="z-[110]">
              <SelectItem value="auto">
                {detected === null
                  ? isZh
                    ? "自动识别"
                    : "Detect automatically"
                  : isZh
                    ? `自动识别 · ${formatContextWindow(detected)}`
                    : `Detect automatically · ${formatContextWindow(detected)}`}
              </SelectItem>
              <SelectItem value="custom">
                {isZh ? "自定义" : "Custom"}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        {selectedMode === "custom" ? (
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={`${fieldId}-custom`}
              className="text-xs leading-5 font-normal text-muted-foreground"
            >
              {isZh ? "自定义值" : "Custom value"}
            </label>
            <div className="flex items-center gap-1.5">
              <Input
                id={`${fieldId}-custom`}
                value={draft}
                inputMode="numeric"
                placeholder={isZh ? "如 1M" : "e.g. 1M"}
                aria-label={isZh ? "自定义上下文窗口" : "Custom context window"}
                className="h-8 flex-1 px-2 font-mono text-xs placeholder:font-sans"
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleDraftKeyDown}
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-8 px-2 text-xs"
                disabled={!draft.trim()}
                onClick={applyDraft}
              >
                {isZh ? "应用" : "Apply"}
              </Button>
            </div>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
