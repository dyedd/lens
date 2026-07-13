import { enUS, zhCN } from "date-fns/locale";
import { ChevronsUpDown } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Calendar } from "@/components/ui/Calendar";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/Field";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import { titleForLocale, type Locale } from "@/lib/I18nContext";
import { cn } from "@/lib/utils";

import { formatDateLabel } from "./gatewayApiKeyUtils";

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
      <FieldDescription>
        {titleForLocale(
          locale,
          "留空表示永不过期",
          "Leave blank to keep the key active forever",
        )}
      </FieldDescription>
    </Field>
  );
}
