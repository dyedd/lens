import { enUS, zhCN } from "date-fns/locale";
import { ChevronsUpDown } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Calendar } from "@/components/ui/Calendar";
import { Field, FieldLabel } from "@/components/ui/Field";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import { cn } from "@/lib/classNames";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

import { formatDateLabel } from "./gatewayDateTime";

type GatewayApiKeyExpiryFieldProps = {
  locale: Locale;
  expiresOn?: Date;
  onChange: (value?: Date) => void;
};

/** Renders the time-zone-aware gateway key expiry date picker. */
export function GatewayApiKeyExpiryField({
  locale,
  expiresOn,
  onChange,
}: GatewayApiKeyExpiryFieldProps) {
  return (
    <Field>
      <FieldLabel>
        {titleForLocale(locale, "过期日期", "Expires on")}
      </FieldLabel>
      <div className="flex flex-col gap-3 md:flex-row">
        <Popover>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              className={cn(
                "w-full justify-between md:flex-1",
                !expiresOn && "text-muted-foreground",
              )}
            >
              <span>{formatDateLabel(locale, expiresOn)}</span>
              <ChevronsUpDown className="text-muted-foreground" />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-auto overflow-hidden p-0">
            <Calendar
              mode="single"
              selected={expiresOn}
              defaultMonth={expiresOn}
              onSelect={(value) => onChange(value ?? undefined)}
              locale={locale === "zh-CN" ? zhCN : enUS}
              captionLayout="dropdown"
            />
          </PopoverContent>
        </Popover>

        <Button type="button" variant="outline" onClick={() => onChange()}>
          {titleForLocale(locale, "清空", "Clear")}
        </Button>
      </div>
    </Field>
  );
}
