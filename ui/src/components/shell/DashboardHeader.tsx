"use client";

import { ThemeToggle } from "@/components/ThemeToggle";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/Breadcrumb";
import { Button } from "@/components/ui/Button";
import {
  SidebarMenuButton,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/Sidebar";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { Locale } from "@/lib/I18nContext";
import { cn } from "@/lib/utils";
import { Globe2, LogOut, PanelLeftClose } from "lucide-react";
import type { ReactNode } from "react";

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
  group?: string;
  headerActions?: ReactNode;
  language: DashboardHeaderAction;
  signOut: DashboardHeaderAction;
};

function CollapseButton({
  expandedLabel,
  collapsedLabel,
  isIconOnly = false,
}: {
  expandedLabel: string;
  collapsedLabel: string;
  isIconOnly?: boolean;
}) {
  const { toggleSidebar, state } = useSidebar();
  const label = state === "collapsed" ? collapsedLabel : expandedLabel;

  return (
    <SidebarMenuButton
      tooltip={label}
      onClick={toggleSidebar}
      className={cn("text-muted-foreground", isIconOnly && "size-8 p-2")}
    >
      <PanelLeftClose
        className={cn(
          "transition-transform",
          state === "collapsed" && "rotate-180",
        )}
      />
      <span className={cn(isIconOnly && "sr-only")}>{label}</span>
    </SidebarMenuButton>
  );
}

/** Renders dashboard navigation context and global header actions. */
export function DashboardHeader({
  locale,
  labels,
  group,
  headerActions,
  language,
  signOut,
}: DashboardHeaderProps) {
  const isChinese = locale === "zh-CN";

  return (
    <header className="flex min-h-14 min-w-0 shrink-0 items-center justify-between gap-2 bg-muted px-3 py-2 sm:px-4">
      <div className="flex min-w-0 items-center gap-2">
        <div className="hidden md:block">
          <CollapseButton
            expandedLabel={isChinese ? "收起侧边栏" : "Collapse"}
            collapsedLabel={isChinese ? "展开侧边栏" : "Expand"}
            isIconOnly
          />
        </div>
        <div className="flex min-w-0 items-center gap-2 md:hidden">
          <SidebarTrigger
            aria-label={isChinese ? "打开导航" : "Open navigation"}
          />
          <span className="truncate text-sm font-medium text-foreground">
            {labels.activeView}
          </span>
        </div>
        <Breadcrumb className="hidden min-w-0 md:block">
          <BreadcrumbList className="min-w-0 flex-nowrap text-sm">
            {group ? (
              <>
                <BreadcrumbItem className="shrink-0">
                  <span>{group}</span>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
              </>
            ) : null}
            <BreadcrumbItem className="min-w-0">
              <BreadcrumbPage className="truncate text-base font-semibold">
                {labels.activeView}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </div>
      <div className="ml-auto flex min-w-0 items-center justify-end gap-2">
        {headerActions ? (
          <div className="flex min-w-0 shrink items-center justify-end gap-2">
            {headerActions}
          </div>
        ) : null}
        <div className="flex shrink-0 items-center justify-end gap-2">
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
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={signOut.label}
                onClick={signOut.onClick}
              >
                <LogOut />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {signOut.label}
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
    </header>
  );
}
