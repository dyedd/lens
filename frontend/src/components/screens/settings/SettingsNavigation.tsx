import {
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
    | "appearance"
    | "account"
    | "time"
    | "gateway"
    | "model-test"
    | "circuit-breaker";
  label: string;
  icon: LucideIcon;
}

/** Create localized settings tab definitions in display order. */
export function createSettingsTabs(
  locale: Locale,
): readonly SettingsTabDefinition[] {
  return [
    {
      value: "appearance",
      label: titleForLocale(locale, "站点外观", "Appearance"),
      icon: Palette,
    },
    {
      value: "account",
      label: titleForLocale(locale, "账号", "Account"),
      icon: UserRound,
    },
    {
      value: "time",
      label: titleForLocale(locale, "时间", "Time"),
      icon: TimerReset,
    },
    {
      value: "gateway",
      label: titleForLocale(locale, "网关", "Gateway"),
      icon: ServerCog,
    },
    {
      value: "model-test",
      label: titleForLocale(locale, "模型测试", "Model test"),
      icon: TestTubeDiagonal,
    },
    {
      value: "circuit-breaker",
      label: titleForLocale(locale, "冷却与健康", "Cooldown and health"),
      icon: ShieldAlert,
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
        const Icon = item.icon;
        return (
          <TabsTrigger
            key={item.value}
            value={item.value}
            className="h-9 w-40 shrink-0 justify-start gap-2 rounded-md px-3 text-sm data-[state=active]:bg-sidebar-accent data-[state=active]:shadow-none"
          >
            <Icon className="size-4" />
            <span>{item.label}</span>
          </TabsTrigger>
        );
      })}
    </TabsList>
  );
}
