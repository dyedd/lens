"use client";

import { Badge } from "@/components/ui/Badge";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/Sidebar";
import {
  DASHBOARD_ROUTES,
  type DashboardView,
} from "@/components/shell/dashboardRoutes";
import type { Locale } from "@/lib/I18nContext";
import { cn } from "@/lib/utils";
import Image from "next/image";
import Link from "next/link";

const GITHUB_REPO_URL = "https://github.com/dyedd/lens";

export interface DashboardSidebarNavItem {
  key: DashboardView;
  href: string;
  label: string;
  icon: React.ComponentType;
}

export interface DashboardSidebarNavGroup {
  label: string;
  items: DashboardSidebarNavItem[];
}

interface DashboardSidebarProps {
  navGroups: DashboardSidebarNavGroup[];
  activeView: DashboardView;
  siteName: string;
  logoUrl: string;
  currentVersion?: string;
  versionLabel: string;
  compactVersionLabel: string;
  hasUpdate: boolean;
  updateLabel: string;
  updateTitle: string;
  updateReleaseUrl?: string;
  locale: Locale;
  onViewIntent: (href: string) => void;
}

function GitHubMark(props: React.ComponentProps<"svg">) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M12 .5a12 12 0 0 0-3.79 23.39c.6.1.82-.26.82-.58v-2.03c-3.34.73-4.04-1.42-4.04-1.42-.55-1.38-1.34-1.75-1.34-1.75-1.1-.74.08-.72.08-.72 1.2.09 1.84 1.22 1.84 1.22 1.08 1.8 2.82 1.28 3.5.98.1-.76.42-1.28.76-1.58-2.67-.3-5.47-1.31-5.47-5.86 0-1.3.47-2.36 1.23-3.19-.12-.3-.53-1.5.12-3.13 0 0 1.01-.32 3.3 1.22a11.6 11.6 0 0 1 6 0c2.28-1.54 3.29-1.22 3.29-1.22.65 1.63.24 2.83.12 3.13.77.83 1.23 1.88 1.23 3.19 0 4.56-2.8 5.55-5.48 5.85.43.36.82 1.08.82 2.18v3.23c0 .32.22.69.83.58A12 12 0 0 0 12 .5Z" />
    </svg>
  );
}

function ShellNavItem({
  item,
  activeView,
  onIntent,
}: {
  item: DashboardSidebarNavItem;
  activeView: DashboardView;
  onIntent: (href: string) => void;
}) {
  const { isMobile, setOpenMobile } = useSidebar();
  const Icon = item.icon;
  const apiKeyParts =
    item.key === "apiKeys" && item.label.includes("API")
      ? item.label.split("API")
      : null;

  function handleNavigate() {
    if (isMobile) {
      setOpenMobile(false);
    }
  }

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={activeView === item.key}
        tooltip={item.label}
        onMouseEnter={() => onIntent(item.href)}
        onFocus={() => onIntent(item.href)}
        className={cn(
          "w-40 max-w-full data-active:!bg-transparent data-active:!text-sidebar-foreground data-active:hover:!bg-transparent data-active:active:!bg-transparent",
          activeView === item.key && "font-medium",
        )}
      >
        <Link href={item.href} scroll={false} onClick={handleNavigate}>
          <Icon />
          {apiKeyParts ? (
            <span>
              {apiKeyParts[0]}
              <span className="brand-times-italic">API</span>
              {apiKeyParts.slice(1).join("API")}
            </span>
          ) : (
            <span>{item.label}</span>
          )}
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

/** Renders the dashboard navigation sidebar. */
export function DashboardSidebar({
  navGroups,
  activeView,
  siteName,
  logoUrl,
  currentVersion,
  versionLabel,
  compactVersionLabel,
  hasUpdate,
  updateLabel,
  updateTitle,
  updateReleaseUrl,
  locale,
  onViewIntent,
}: DashboardSidebarProps) {
  const versionText = locale === "zh-CN" ? "版本号" : "Version";

  return (
    <Sidebar collapsible="icon" className="z-20 bg-sidebar">
      <SidebarHeader>
        <div className="flex w-full items-center gap-1.5 group-data-[collapsible=icon]:justify-center">
          <SidebarMenu className="min-w-0 flex-1">
            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                tooltip={siteName}
                className="data-[slot=sidebar-menu-button]:!p-1.5"
              >
                <Link
                  href={DASHBOARD_ROUTES.overview}
                  scroll={false}
                  onMouseEnter={() => onViewIntent(DASHBOARD_ROUTES.overview)}
                  onFocus={() => onViewIntent(DASHBOARD_ROUTES.overview)}
                >
                  <Image
                    src={logoUrl}
                    alt={siteName}
                    width={24}
                    height={24}
                    loading="eager"
                    className="size-6 shrink-0 object-contain"
                    unoptimized={logoUrl !== "/logo.svg"}
                  />
                  <span className="brand-times-italic truncate text-base font-semibold">
                    {siteName}
                  </span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </div>
      </SidebarHeader>
      <SidebarContent>
        {navGroups.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarMenu>
              {group.items.map((item) => (
                <ShellNavItem
                  key={item.key}
                  item={item}
                  activeView={activeView}
                  onIntent={onViewIntent}
                />
              ))}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter className="px-3 py-3 group-data-[collapsible=icon]:px-2">
        <SidebarSeparator />
        <div className="flex flex-col gap-2 px-2 pt-2 group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0">
          <div
            className="whitespace-nowrap text-center text-sm font-medium text-sidebar-foreground/90 group-data-[collapsible=icon]:text-xs"
            title={versionLabel}
          >
            {currentVersion ? (
              <span className="group-data-[collapsible=icon]:hidden">
                {versionText}{" "}
                <span className="brand-times-italic">{currentVersion}</span>
              </span>
            ) : (
              <span className="group-data-[collapsible=icon]:hidden">
                {versionLabel}
              </span>
            )}
            <span className="hidden group-data-[collapsible=icon]:inline">
              {compactVersionLabel}
            </span>
          </div>
          {hasUpdate ? (
            updateReleaseUrl ? (
              <Badge
                asChild
                variant="destructive"
                className="mx-auto max-w-full group-data-[collapsible=icon]:size-5 group-data-[collapsible=icon]:px-0"
                title={updateTitle}
              >
                <a href={updateReleaseUrl} target="_blank" rel="noreferrer">
                  <span className="group-data-[collapsible=icon]:hidden">
                    {updateLabel}
                  </span>
                  <span className="hidden group-data-[collapsible=icon]:inline">
                    !
                  </span>
                </a>
              </Badge>
            ) : (
              <Badge
                variant="destructive"
                className="mx-auto max-w-full group-data-[collapsible=icon]:size-5 group-data-[collapsible=icon]:px-0"
                title={updateTitle}
              >
                <span className="group-data-[collapsible=icon]:hidden">
                  {updateLabel}
                </span>
                <span className="hidden group-data-[collapsible=icon]:inline">
                  !
                </span>
              </Badge>
            )
          ) : null}
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                tooltip="GitHub"
                className="justify-center group-data-[collapsible=icon]:justify-center"
              >
                <a
                  href={GITHUB_REPO_URL}
                  target="_blank"
                  rel="noreferrer"
                  aria-label="GitHub"
                >
                  <GitHubMark />
                  <span className="brand-times-italic">GitHub</span>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
