import { useState } from "react";

import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Switch } from "@/components/ui/Switch";
import type { PluginItem, PluginSetting } from "@/lib/api/plugins";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

type PluginSettingsProps = {
  locale: Locale;
  plugin: PluginItem;
  disabled: boolean;
  onChange: (key: string, value: string | number | boolean) => void;
};

type SettingControlProps = {
  setting: PluginSetting;
  disabled: boolean;
  onChange: (value: string | number | boolean) => void;
};

/** 与服务端一致：有限数，int 须为整数，并落在声明的上下限内。 */
function isValidNumberSetting(setting: PluginSetting, value: number) {
  if (!Number.isFinite(value)) return false;
  if (setting.type === "int" && !Number.isInteger(value)) return false;
  return (
    value >= (setting.min_value ?? -Infinity) &&
    value <= (setting.max_value ?? Infinity)
  );
}

function NumberSettingInput({
  setting,
  disabled,
  onChange,
}: SettingControlProps) {
  const [isInvalid, setIsInvalid] = useState(false);
  return (
    <Input
      type="number"
      step={setting.type === "float" ? "any" : 1}
      min={setting.min_value ?? undefined}
      max={setting.max_value ?? undefined}
      defaultValue={String(setting.value)}
      disabled={disabled}
      aria-label={setting.label}
      aria-invalid={isInvalid || undefined}
      className="h-8 w-28 text-xs"
      onChange={(event) =>
        setIsInvalid(
          !isValidNumberSetting(setting, event.currentTarget.valueAsNumber),
        )
      }
      onBlur={(event) => {
        const next = event.currentTarget.valueAsNumber;
        if (isValidNumberSetting(setting, next) && next !== setting.value) {
          onChange(next);
        }
      }}
    />
  );
}

function SecretSettingInput({
  locale,
  setting,
  disabled,
  onChange,
}: SettingControlProps & { locale: Locale }) {
  return (
    <Input
      type="password"
      autoComplete="new-password"
      disabled={disabled}
      aria-label={setting.label}
      placeholder={
        setting.is_set
          ? titleForLocale(locale, "已设置", "Set")
          : titleForLocale(locale, "未设置", "Not set")
      }
      className="h-8 w-52 text-xs"
      onBlur={(event) => {
        // 留空表示保持服务端已存的值；提交后清空，密钥不留在页面上。
        const next = event.currentTarget.value;
        if (!next) return;
        event.currentTarget.value = "";
        onChange(next);
      }}
    />
  );
}

function SettingControl({
  locale,
  setting,
  disabled,
  onChange,
}: SettingControlProps & { locale: Locale }) {
  if (setting.type === "bool") {
    return (
      <Switch
        checked={Boolean(setting.value)}
        disabled={disabled}
        onCheckedChange={(checked) => onChange(checked)}
        aria-label={setting.label}
      />
    );
  }
  if (setting.secret) {
    return (
      <SecretSettingInput
        locale={locale}
        setting={setting}
        disabled={disabled}
        onChange={onChange}
      />
    );
  }
  if (setting.type === "enum") {
    return (
      <Select
        value={String(setting.value)}
        onValueChange={(value) => onChange(value)}
        disabled={disabled}
      >
        <SelectTrigger className="h-8 w-44 text-xs" aria-label={setting.label}>
          <SelectValue placeholder={setting.label} />
        </SelectTrigger>
        <SelectContent>
          {setting.options.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  if (setting.type === "int" || setting.type === "float") {
    return (
      <NumberSettingInput
        setting={setting}
        disabled={disabled}
        onChange={onChange}
      />
    );
  }
  return (
    <Input
      defaultValue={String(setting.value)}
      disabled={disabled}
      aria-label={setting.label}
      placeholder={setting.label}
      className="h-8 w-52 text-xs"
      onBlur={(event) => {
        const next = event.currentTarget.value;
        if (next !== setting.value) onChange(next);
      }}
    />
  );
}

/** Render a plugin's declared settings as rows of its detail well. */
export function PluginSettingsForm({
  locale,
  plugin,
  disabled,
  onChange,
}: PluginSettingsProps) {
  return plugin.settings.map((setting) => (
    <div
      key={setting.key}
      className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between md:gap-4"
    >
      <div className="min-w-0">
        <Label className="text-xs font-normal text-muted-foreground">
          {setting.label}
        </Label>
        {setting.description ? (
          <p className="text-[11px] text-muted-foreground/80">
            {setting.description}
          </p>
        ) : null}
      </div>
      <SettingControl
        locale={locale}
        setting={setting}
        disabled={disabled}
        onChange={(value) => onChange(setting.key, value)}
      />
    </div>
  ));
}
