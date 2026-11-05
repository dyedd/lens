import { Check, ChevronDownIcon } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { ProtocolKind } from "@/lib/api/protocols";
import { cn } from "@/lib/classNames";
import { PROTOCOL_LIST, protocolLabel } from "@/lib/protocols";
import type { Locale } from "./channelTypes";

type Props = {
  value: ProtocolKind[];
  locale: Locale;
  disabled?: boolean;
  className?: string;
  onChange: (protocols: ProtocolKind[]) => void;
};

export function ProtocolDropdown({
  value,
  locale,
  disabled = false,
  className,
  onChange,
}: Props) {
  const selected = new Set(value);
  const selectedLabel = PROTOCOL_LIST.filter((protocol) =>
    selected.has(protocol),
  )
    .map((protocol) => protocolLabel(protocol, locale))
    .join(", ");

  function toggle(protocol: ProtocolKind) {
    if (selected.has(protocol)) {
      onChange(value.filter((item) => item !== protocol));
      return;
    }
    onChange([...value, protocol]);
  }

  return (
    <Popover modal={false}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          aria-label={
            selectedLabel ||
            (locale === "zh-CN" ? "选择上游协议" : "Select upstream protocols")
          }
          className={cn(
            "h-auto min-h-8 min-w-0 w-full max-w-72 justify-between gap-2 border-input/40 bg-transparent px-3 py-1 text-sm font-normal text-muted-foreground shadow-none hover:bg-transparent focus-visible:border-ring/60 focus-visible:ring-[1px] focus-visible:ring-ring/40 has-[>svg]:px-3",
            className,
          )}
        >
          <Tooltip>
            <TooltipTrigger asChild>
              <span
                className={cn(
                  "min-w-0 flex-1 truncate text-left",
                  selectedLabel && "text-foreground/75",
                )}
              >
                {selectedLabel ||
                  (locale === "zh-CN" ? "选择协议" : "Select protocols")}
              </span>
            </TooltipTrigger>
            {selectedLabel ? (
              <TooltipContent className="z-[110] max-w-sm break-words">
                {selectedLabel}
              </TooltipContent>
            ) : null}
          </Tooltip>
          <ChevronDownIcon className="size-3.5 shrink-0 text-muted-foreground opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="z-[100] w-72 gap-0 p-1">
        {PROTOCOL_LIST.map((protocol) => (
          <Button
            key={protocol}
            type="button"
            variant="ghost"
            size="sm"
            aria-pressed={selected.has(protocol)}
            onClick={() => toggle(protocol)}
            className="relative h-auto min-h-7 w-full justify-start rounded-md py-1 pr-8 pl-2 font-normal"
          >
            <span className="min-w-0 flex-1 truncate text-left">
              {protocolLabel(protocol, locale)}
            </span>
            {selected.has(protocol) ? (
              <Check className="absolute right-2" />
            ) : null}
          </Button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
