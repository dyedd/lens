import {
  Palette,
  ServerCog,
  ShieldAlert,
  TestTubeDiagonal,
  TimerReset,
  UserRound,
  type LucideIcon,
} from "lucide-react";

import { TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

export interface SettingsTabDefinition {
  value:
    | "appearance"
    | "account"
    | "time"
    | "gateway"
    | "model-test"
    | "circuit-breaker";
  label: string;
  description: string;
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
      description: titleForLocale(
        locale,
        "站点名称、Logo 和默认语言。",
        "Site name, logo, and default language.",
      ),
      icon: Palette,
    },
    {
      value: "account",
      label: titleForLocale(locale, "账号", "Account"),
      description: titleForLocale(
        locale,
        "管理员用户名和登录密码。",
        "Admin username and sign-in password.",
      ),
      icon: UserRound,
    },
    {
      value: "time",
      label: titleForLocale(locale, "时间", "Time"),
      description: titleForLocale(
        locale,
        "系统显示和统计使用的时区。",
        "Time zone used by display and statistics.",
      ),
      icon: TimerReset,
    },
    {
      value: "gateway",
      label: titleForLocale(locale, "网关", "Gateway"),
      description: titleForLocale(
        locale,
        "代理、跨域、日志和上游请求设置。",
        "Proxy, CORS, logs, and upstream request settings.",
      ),
      icon: ServerCog,
    },
    {
      value: "model-test",
      label: titleForLocale(locale, "模型测试", "Model test"),
      description: titleForLocale(
        locale,
        "批量测试模型时使用的预设问题。",
        "Preset prompts used when testing models.",
      ),
      icon: TestTubeDiagonal,
    },
    {
      value: "circuit-breaker",
      label: titleForLocale(locale, "冷却与健康", "Cooldown and health"),
      description: titleForLocale(
        locale,
        "模型与 Key 冷却、渠道可用性和健康排序参数。",
        "Model and key cooldown, channel availability, and health ranking parameters.",
      ),
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
