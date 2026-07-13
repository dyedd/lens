"use client";

import { Field, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/ToggleGroup";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { RoutingStrategy } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatMoney, metricLabel, STRATEGY_OPTIONS } from "./modelGroupUtils";

export { CandidateRow, FoldedMemberRow } from "./ModelGroupMemberRows";

/** Render a compact summary of model token prices. */
export function CompactPriceSummary({
  locale,
  inputPrice,
  outputPrice,
  cacheReadPrice,
  cacheWritePrice,
}: {
  locale: "zh-CN" | "en-US";
  inputPrice: number;
  outputPrice: number;
  cacheReadPrice: number;
  cacheWritePrice: number;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="mt-2 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          <span>
            {metricLabel("input", locale)} ${formatMoney(inputPrice)}
          </span>
          <span>
            {metricLabel("output", locale)} ${formatMoney(outputPrice)}
          </span>
          <span>
            {metricLabel("cache_read", locale)} ${formatMoney(cacheReadPrice)}
          </span>
          <span>
            {metricLabel("cache_write", locale)} ${formatMoney(cacheWritePrice)}
          </span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top" align="start">
        <div className="grid gap-1">
          <div>
            {metricLabel("input", locale)}: ${formatMoney(inputPrice)} / 1M
            tokens
          </div>
          <div>
            {metricLabel("output", locale)}: ${formatMoney(outputPrice)} / 1M
            tokens
          </div>
          <div>
            {metricLabel("cache_read", locale)}: ${formatMoney(cacheReadPrice)}{" "}
            / 1M tokens
          </div>
          <div>
            {metricLabel("cache_write", locale)}: $
            {formatMoney(cacheWritePrice)} / 1M tokens
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

/** Render paired editable model price inputs. */
export function EditablePriceRow({
  locale,
  primaryLabel,
  primaryValue,
  secondaryLabel,
  secondaryValue,
  onPrimaryChange,
  onSecondaryChange,
}: {
  locale: "zh-CN" | "en-US";
  primaryLabel: "input" | "output";
  primaryValue: string;
  secondaryLabel: "cache_read" | "cache_write";
  secondaryValue: string;
  onPrimaryChange: (value: string) => void;
  onSecondaryChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field className="min-w-0">
        <FieldLabel>${metricLabel(primaryLabel, locale)}</FieldLabel>
        <Input
          className="mt-2"
          value={primaryValue}
          onChange={(event) => onPrimaryChange(event.target.value)}
        />
      </Field>

      <Field className="min-w-0">
        <FieldLabel>${metricLabel(secondaryLabel, locale)}</FieldLabel>
        <Input
          className="mt-2"
          value={secondaryValue}
          onChange={(event) => onSecondaryChange(event.target.value)}
        />
      </Field>
    </div>
  );
}

/** Render the routing strategy selector for a model group. */
export function StrategyToggle({
  value,
  locale,
  disabled = false,
  size = "default",
  className,
  onChange,
}: {
  value: RoutingStrategy;
  locale: "zh-CN" | "en-US";
  disabled?: boolean;
  size?: "default" | "sm";
  className?: string;
  onChange: (value: RoutingStrategy) => void;
}) {
  return (
    <ToggleGroup
      type="single"
      value={value}
      onValueChange={(nextValue) => {
        if (nextValue) {
          onChange(nextValue as RoutingStrategy);
        }
      }}
      variant="outline"
      size={size}
      spacing={1}
      className={cn("max-w-full flex-wrap", className)}
    >
      {STRATEGY_OPTIONS.map((option) => (
        <ToggleGroupItem
          key={option.value}
          value={option.value}
          disabled={disabled}
          className="max-w-full"
        >
          {locale === "zh-CN" ? option.zh : option.en}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
