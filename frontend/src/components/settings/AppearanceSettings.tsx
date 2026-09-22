import { ImageIcon } from "lucide-react";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import { Input } from "@/components/ui/Input";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { titleForLocale, useI18n } from "@/lib/I18nContext";
import { TIME_ZONE_OPTIONS } from "./settingsDraft";
import { SettingsFieldList, SettingsFieldRow } from "./settingsLayout";

interface AppearanceSettingsProps {
  siteName: string;
  siteLogoUrl: string;
  onSiteNameChange: (value: string) => void;
  onSiteLogoUrlChange: (value: string) => void;
  timeZone: string;
  onTimeZoneChange: (value: string) => void;
}

/** Renders localization and branding settings. */
export function AppearanceSettings({
  siteName,
  siteLogoUrl,
  onSiteNameChange,
  onSiteLogoUrlChange,
  timeZone,
  onTimeZoneChange,
}: AppearanceSettingsProps) {
  const { locale, setLocale } = useI18n();

  return (
    <SettingsFieldList>
      <SettingsFieldRow title={titleForLocale(locale, "语言", "Language")}>
        <SegmentedControl
          className="!w-fit"
          value={locale}
          onValueChange={(value) => setLocale(value)}
          options={[
            { value: "zh-CN", label: "简体中文" },
            { value: "en-US", label: "English" },
          ]}
        />
      </SettingsFieldRow>
      <SettingsFieldRow title={titleForLocale(locale, "时区", "Time zone")}>
        <Combobox
          className="w-full"
          value={timeZone || "Asia/Shanghai"}
          onChange={(event) => onTimeZoneChange(event.target.value)}
        >
          {TIME_ZONE_OPTIONS.map((option) => (
            <ComboboxOption key={option.value} value={option.value}>
              {option.label}
            </ComboboxOption>
          ))}
        </Combobox>
      </SettingsFieldRow>
      <SettingsFieldRow title={titleForLocale(locale, "站点名称", "Site name")}>
        <Input
          className="w-full"
          value={siteName}
          onChange={(event) => onSiteNameChange(event.target.value)}
          placeholder="Lens"
        />
      </SettingsFieldRow>
      <SettingsFieldRow title={titleForLocale(locale, "Logo 地址", "Logo URL")}>
        <Input
          className="w-full"
          value={siteLogoUrl}
          onChange={(event) => onSiteLogoUrlChange(event.target.value)}
          placeholder="https://example.com/logo.svg"
        />
      </SettingsFieldRow>
      <div className="flex items-center gap-3 rounded-md bg-muted/35 px-3 py-2.5">
        <span className="flex size-10 items-center justify-center overflow-hidden rounded-md border border-border/60 bg-background">
          {siteLogoUrl.trim() ? (
            <img
              src={siteLogoUrl.trim()}
              alt={siteName || "logo"}
              width={40}
              height={40}
              className="size-10 object-contain"
            />
          ) : (
            <ImageIcon className="size-4 text-muted-foreground" />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-foreground">
            {siteName.trim() || "Lens"}
          </div>
          <div className="truncate text-xs text-muted-foreground">
            {siteLogoUrl.trim() ||
              titleForLocale(locale, "未设置 Logo", "No logo configured")}
          </div>
        </div>
      </div>
    </SettingsFieldList>
  );
}
