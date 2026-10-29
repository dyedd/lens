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

type PluginSettingsProps = {
  plugin: PluginItem;
  disabled: boolean;
  onChange: (key: string, value: string | number | boolean) => void;
};

function SettingControl({
  setting,
  disabled,
  onChange,
}: {
  setting: PluginSetting;
  disabled: boolean;
  onChange: (value: string | number | boolean) => void;
}) {
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
  if (setting.type === "enum") {
    return (
      <Select
        value={String(setting.value)}
        onValueChange={(value) => onChange(value)}
        disabled={disabled}
      >
        <SelectTrigger className="h-8 w-44 text-xs">
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
  if (setting.type === "int") {
    return (
      <Input
        type="number"
        defaultValue={String(setting.value)}
        disabled={disabled}
        aria-label={setting.label}
        className="h-8 w-28 text-xs"
        onBlur={(event) => {
          const next = Number(event.currentTarget.value);
          if (Number.isFinite(next) && next !== setting.value) onChange(next);
        }}
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

/** Render a plugin's declared settings under its row. */
export function PluginSettingsForm({
  plugin,
  disabled,
  onChange,
}: PluginSettingsProps) {
  if (!plugin.settings.length) return null;
  return (
    <div className="space-y-2 rounded-md bg-muted/35 px-3 py-2">
      {plugin.settings.map((setting) => (
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
            setting={setting}
            disabled={disabled}
            onChange={(value) => onChange(setting.key, value)}
          />
        </div>
      ))}
    </div>
  );
}
