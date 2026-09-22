import { Info } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { SettingsSection } from "./settingsLayout";

export function SettingsHint({ description }: { description: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          className="text-muted-foreground hover:text-foreground"
          aria-label={description}
        >
          <Info />
        </Button>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm">{description}</TooltipContent>
    </Tooltip>
  );
}

/** Render a settings tab section with a title row. */
export function SettingsSectionCard({
  title,
  actions,
  className,
  children,
}: {
  title: string;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <SettingsSection title={title} actions={actions} className={className}>
      {children}
    </SettingsSection>
  );
}
