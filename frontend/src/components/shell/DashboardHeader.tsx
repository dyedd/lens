import { Globe2 } from "lucide-react";
import type { ReactNode } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button, buttonVariants } from "@/components/ui/Button";
import { SidebarTrigger } from "@/components/ui/SidebarLayout";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { cn } from "@/lib/classNames";
import type { Locale } from "@/lib/I18nContext";

const GITHUB_REPO_URL = "https://github.com/dyedd/lens";

type DashboardHeaderLabels = {
  activeView: string;
};

type DashboardHeaderAction = {
  label: string;
  onClick: () => void;
};

type DashboardHeaderProps = {
  locale: Locale;
  labels: DashboardHeaderLabels;
  headerActions?: ReactNode;
  language: DashboardHeaderAction;
};

function GitHubMark(props: React.ComponentProps<"svg">) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M12 .5a12 12 0 0 0-3.79 23.39c.6.1.82-.26.82-.58v-2.03c-3.34.73-4.04-1.42-4.04-1.42-.55-1.38-1.34-1.75-1.34-1.75-1.1-.74.08-.72.08-.72 1.2.09 1.84 1.22 1.84 1.22 1.08 1.8 2.82 1.28 3.5.98.1-.76.42-1.28.76-1.58-2.67-.3-5.47-1.31-5.47-5.86 0-1.3.47-2.36 1.23-3.19-.12-.3-.53-1.5.12-3.13 0 0 1.01-.32 3.3 1.22a11.6 11.6 0 0 1 6 0c2.28-1.54 3.29-1.22 3.29-1.22.65 1.63.24 2.83.12 3.13.77.83 1.23 1.88 1.23 3.19 0 4.56-2.8 5.55-5.48 5.85.43.36.82 1.08.82 2.18v3.23c0 .32.22.69.83.58A12 12 0 0 0 12 .5Z" />
    </svg>
  );
}

/** Renders dashboard navigation context and global header actions. */
export function DashboardHeader({
  locale,
  labels,
  headerActions,
  language,
}: DashboardHeaderProps) {
  const isChinese = locale === "zh-CN";

  return (
    <header className="flex min-h-12 min-w-0 shrink-0 items-center justify-between gap-2 bg-background px-4 py-2 sm:px-6 lg:px-8">
      <div className="flex min-w-0 items-center gap-2 md:hidden">
        <SidebarTrigger
          aria-label={isChinese ? "打开导航" : "Open navigation"}
        />
        <span className="truncate text-sm font-medium text-foreground">
          {labels.activeView}
        </span>
      </div>
      <div className="ml-auto flex min-w-0 items-center justify-end gap-2">
        {headerActions ? (
          <div className="flex min-w-0 shrink items-center justify-end gap-2">
            {headerActions}
          </div>
        ) : null}
        <div className="flex shrink-0 items-center justify-end gap-1.5">
          <Tooltip>
            <TooltipTrigger asChild>
              <a
                href={GITHUB_REPO_URL}
                target="_blank"
                rel="noreferrer"
                aria-label="GitHub"
                className={cn(
                  buttonVariants({ variant: "ghost", size: "icon-sm" }),
                )}
              >
                <GitHubMark className="size-4" />
              </a>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              GitHub
            </TooltipContent>
          </Tooltip>
          <ThemeToggle />
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={language.label}
                onClick={language.onClick}
              >
                <Globe2 />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {language.label}
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
    </header>
  );
}
