import {
  DatabaseBackup,
  EyeOff,
  type LucideIcon,
  Palette,
  ServerCog,
  ShieldAlert,
  TimerReset,
  UserRound,
} from "lucide-react";

import { TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

export interface SettingsTabDefinition {
  value:
    | "general"
    | "gateway"
    | "privacy"
    | "circuit-breaker"
    | "api-keys"
    | "cronjobs"
    | "backups";
  label: string;
  icon: LucideIcon;
}

/** Create localized settings tab definitions in display order. */
export function createSettingsTabs(
  locale: Locale,
): readonly SettingsTabDefinition[] {
  return [
    {
      value: "general",
      label: titleForLocale(locale, "常规", "General"),
      icon: Palette,
    },
    {
      value: "gateway",
      label: titleForLocale(locale, "网关", "Gateway"),
      icon: ServerCog,
    },
    {
      value: "privacy",
      label: titleForLocale(locale, "隐私", "Privacy"),
      icon: EyeOff,
    },
    {
      value: "circuit-breaker",
      label: titleForLocale(locale, "故障转移", "Failover"),
      icon: ShieldAlert,
    },
    {
      value: "api-keys",
      label: titleForLocale(locale, "网关密钥", "Gateway Keys"),
      icon: UserRound,
    },
    {
      value: "cronjobs",
      label: titleForLocale(locale, "计划任务", "Scheduled Tasks"),
      icon: TimerReset,
    },
    {
      value: "backups",
      label: titleForLocale(locale, "备份与迁移", "Backup & Migration"),
      icon: DatabaseBackup,
    },
  ];
}

/** Render the horizontal workspace tab strip for settings. */
export function SettingsNavigation({
  tabs,
}: {
  tabs: readonly SettingsTabDefinition[];
}) {
  return (
    <TabsList className="flex h-auto w-full flex-row justify-start gap-1 overflow-x-auto rounded-none border-b border-border/60 bg-transparent p-0 text-foreground">
      {tabs.map((item) => {
        const Icon = item.icon;
        return (
          <TabsTrigger
            key={item.value}
            value={item.value}
            className="h-9 shrink-0 justify-start gap-1.5 rounded-none border-b-2 border-transparent px-3 text-[13px] font-normal text-muted-foreground shadow-none transition-colors hover:text-foreground data-[state=active]:border-foreground data-[state=active]:bg-transparent data-[state=active]:font-medium data-[state=active]:text-foreground data-[state=active]:ring-0 data-[state=active]:shadow-none"
          >
            <Icon className="size-3.5 shrink-0 opacity-75" />
            <span>{item.label}</span>
          </TabsTrigger>
        );
      })}
    </TabsList>
  );
}
