import {
  Field,
  FieldContent,
  FieldDescription,
  FieldLabel,
} from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

type GatewayApiKeyBasicFieldsProps = {
  locale: Locale;
  remark: string;
  enabled: boolean;
  maxCostUsd: string;
  onRemarkChange: (value: string) => void;
  onEnabledChange: (value: boolean) => void;
  onMaxCostUsdChange: (value: string) => void;
};

/** Renders the gateway key identity, enabled state, and balance fields. */
export function GatewayApiKeyBasicFields({
  locale,
  remark,
  enabled,
  maxCostUsd,
  onRemarkChange,
  onEnabledChange,
  onMaxCostUsdChange,
}: GatewayApiKeyBasicFieldsProps) {
  return (
    <>
      <Field>
        <FieldLabel htmlFor="gateway-key-remark">
          {titleForLocale(locale, "密钥名称", "Key name")}
        </FieldLabel>
        <Input
          id="gateway-key-remark"
          value={remark}
          onChange={(event) => onRemarkChange(event.target.value)}
          placeholder={titleForLocale(locale, "可留空", "Optional")}
        />
      </Field>

      <Field
        orientation="horizontal"
        className="items-center justify-between rounded-lg border bg-muted/20 px-3 py-3"
      >
        <FieldContent>
          <FieldLabel className="w-auto">
            {titleForLocale(locale, "启用", "Enabled")}
          </FieldLabel>
          <FieldDescription>
            {titleForLocale(
              locale,
              "关闭后立即拒绝该密钥请求",
              "Reject requests immediately when disabled",
            )}
          </FieldDescription>
        </FieldContent>
        <Switch checked={enabled} onCheckedChange={onEnabledChange} />
      </Field>

      <Field>
        <FieldLabel htmlFor="gateway-key-limit">
          {titleForLocale(locale, "最大余额 (USD)", "Max balance (USD)")}
        </FieldLabel>
        <Input
          id="gateway-key-limit"
          type="number"
          min="0"
          step="0.0001"
          value={maxCostUsd}
          onChange={(event) => onMaxCostUsdChange(event.target.value)}
        />
        <FieldDescription>
          {titleForLocale(locale, "填 0 表示不限制", "Use 0 for unlimited")}
        </FieldDescription>
      </Field>
    </>
  );
}
