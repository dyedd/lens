import {
  BookMarked,
  type LucideIcon,
  Palette,
  ServerCog,
  ShieldAlert,
  TestTubeDiagonal,
  TimerReset,
  UserRound,
} from "lucide-react";

import { TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

export interface SettingsTabDefinition {
  value:
    | "general"
    | "gateway"
    | "model-test"
    | "circuit-breaker"
    | "regex-rules"
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
      value: "model-test",
      label: titleForLocale(locale, "模型测试", "Model Testing"),
      icon: TestTubeDiagonal,
    },
    {
      value: "circuit-breaker",
      label: titleForLocale(locale, "故障转移", "Failover"),
      icon: ShieldAlert,
    },
    {
      value: "regex-rules",
      label: titleForLocale(locale, "规则", "Rules"),
      icon: BookMarked,
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
      icon: ServerCog,
    },
  ];
}

/** Render the responsive settings tab navigation. */
export function SettingsNavigation({
  tabs,
}: {
  tabs: readonly SettingsTabDefinition[];
}) {
  return (
    <TabsList className="flex h-auto w-full flex-row justify-start gap-1 overflow-x-auto rounded-none bg-transparent p-0 text-foreground lg:sticky lg:top-4 lg:flex-col lg:items-start lg:overflow-visible">
      {tabs.map((item) => {
        return (
          <TabsTrigger
            key={item.value}
            value={item.value}
            className="h-9 w-40 shrink-0 justify-start rounded-md px-3.5 text-sm font-medium text-sidebar-foreground shadow-none lg:w-full data-[state=active]:bg-sidebar-accent data-[state=active]:text-sidebar-accent-foreground data-[state=active]:shadow-none"
          >
            <span>{item.label}</span>
          </TabsTrigger>
        );
      })}
    </TabsList>
  );
}
