"use client";

import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { useI18n } from "@/lib/I18nContext";
import { useTheme } from "@/lib/ThemeContext";

/** Renders the control for switching between light and dark themes. */
export function ThemeToggle() {
  const { locale } = useI18n();
  const { toggleTheme } = useTheme();
  const label = locale === "zh-CN" ? "切换明暗模式" : "Toggle theme";

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={label}
          onClick={toggleTheme}
        >
          <Moon className="dark:hidden" />
          <Sun className="hidden dark:block" />
        </Button>
      </TooltipTrigger>
      <TooltipContent side="bottom">{label}</TooltipContent>
    </Tooltip>
  );
}
