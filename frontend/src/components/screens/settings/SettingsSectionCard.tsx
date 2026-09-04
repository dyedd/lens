import { Info } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { cn } from "@/lib/classNames";

interface SettingsSectionCardProps {
  title: string;
  className?: string;
  children: ReactNode;
}

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

/** Render the shared card shell used by a settings tab. */
export function SettingsSectionCard({
  title,
  className,
  children,
}: SettingsSectionCardProps) {
  return (
    <section
      className={cn(
        "min-w-0 rounded-2xl border bg-card px-4 py-4 shadow-sm sm:px-6 sm:py-5",
        className,
      )}
    >
      <header className="border-b pb-4">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
      </header>
      <div className="flex max-w-2xl flex-col gap-4 pt-5">{children}</div>
    </section>
  );
}
