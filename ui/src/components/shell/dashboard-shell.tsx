"use client";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import {
  DASHBOARD_ROUTES,
  getDashboardViewFromPathname,
  type DashboardView,
} from "@/components/shell/dashboard-routes";
import {
  DashboardHeaderActionsContext,
  useDashboardHeaderActionsState,
} from "@/components/shell/dashboard-header-actions";
import {
  apiRequest,
  hydrateProtocolConversions,
  type AppInfo,
  type VersionCheckResult,
} from "@/lib/api";
import { clearStoredToken } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArchiveRestore,
  CalendarClock,
  Globe2,
  KeyRound,
  Layers3,
  LayoutDashboard,
  LogOut,
  PanelLeftClose,
  Settings2,
  Waypoints,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";

const GITHUB_REPO_URL = "https://github.com/dyedd/lens";

function GitHubMark(props: React.ComponentProps<"svg">) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M12 .5a12 12 0 0 0-3.79 23.39c.6.1.82-.26.82-.58v-2.03c-3.34.73-4.04-1.42-4.04-1.42-.55-1.38-1.34-1.75-1.34-1.75-1.1-.74.08-.72.08-.72 1.2.09 1.84 1.22 1.84 1.22 1.08 1.8 2.82 1.28 3.5.98.1-.76.42-1.28.76-1.58-2.67-.3-5.47-1.31-5.47-5.86 0-1.3.47-2.36 1.23-3.19-.12-.3-.53-1.5.12-3.13 0 0 1.01-.32 3.3 1.22a11.6 11.6 0 0 1 6 0c2.28-1.54 3.29-1.22 3.29-1.22.65 1.63.24 2.83.12 3.13.77.83 1.23 1.88 1.23 3.19 0 4.56-2.8 5.55-5.48 5.85.43.36.82 1.08.82 2.18v3.23c0 .32.22.69.83.58A12 12 0 0 0 12 .5Z" />
    </svg>
  );
}

function CollapseButton({
  expandedLabel,
  collapsedLabel,
  iconOnly = false,
}: {
  expandedLabel: string;
  collapsedLabel: string;
  iconOnly?: boolean;
}) {
  const { toggleSidebar, state } = useSidebar();
  const label = state === "collapsed" ? collapsedLabel : expandedLabel;
  return (
    <SidebarMenuButton
      tooltip={label}
      onClick={toggleSidebar}
      className={cn("text-muted-foreground", iconOnly && "size-8 p-2")}
    >
      <PanelLeftClose
        className={cn(
          "transition-transform",
          state === "collapsed" && "rotate-180",
        )}
      />
      <span className={cn(iconOnly && "sr-only")}>{label}</span>
    </SidebarMenuButton>
  );
}

function ShellNavItem({
  item,
  activeView,
  onIntent,
}: {
  item: {
    key: DashboardView;
    href: string;
    label: string;
    icon: React.ComponentType;
  };
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

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { locale, setLocale, t } = useI18n();
  const { data: appInfo } = useQuery({
    queryKey: ["app-info"],
    queryFn: () => apiRequest<AppInfo>("/admin/app-info"),
    staleTime: 5 * 60_000,
  });
  useEffect(() => {
    hydrateProtocolConversions(appInfo?.protocol_conversions);
  }, [appInfo?.protocol_conversions]);
  const { data: versionCheck } = useQuery({
    queryKey: ["version-check"],
    queryFn: () => apiRequest<VersionCheckResult>("/admin/version-check"),
    staleTime: 5 * 60_000,
    refetchInterval: 60 * 60_000,
  });
  const siteName = appInfo?.site_name.trim() || "Lens";
  const logoUrl = appInfo?.logo_url.trim() || "/logo.svg";
  const activeView = useMemo(
    () => getDashboardViewFromPathname(pathname),
    [pathname],
  );
  const currentVersion = appInfo?.system_version.trim();
  const versionText = locale === "zh-CN" ? "版本号" : "Version";
  const versionLabel = currentVersion
    ? `${versionText} ${currentVersion}`
    : appInfo
      ? locale === "zh-CN"
        ? "版本未获取"
        : "Unavailable"
      : locale === "zh-CN"
        ? "加载中..."
        : "Loading...";
  const compactVersionLabel = currentVersion || (appInfo ? "-" : "...");
  const updateLabel = versionCheck?.latest_version
    ? `${locale === "zh-CN" ? "有新版本" : "Update"} ${versionCheck.latest_version}`
    : locale === "zh-CN"
      ? "有新版本"
      : "Update available";
  const updateTitle = versionCheck?.release_url
    ? updateLabel
    : `${updateLabel} (${locale === "zh-CN" ? "暂无发布链接" : "No release link"})`;
  const nextLocale = locale === "zh-CN" ? "en-US" : "zh-CN";
  const languageActionLabel =
    locale === "zh-CN" ? "切换到 English" : "Switch to 中文";
  const { actions: headerActions, value: headerActionsContext } =
    useDashboardHeaderActionsState();

  const navGroups = useMemo(
    () => [
      {
        label: locale === "zh-CN" ? "监控" : "Monitor",
        items: [
          {
            key: "overview" as DashboardView,
            href: DASHBOARD_ROUTES.overview,
            label: t.dashboard,
            icon: LayoutDashboard,
          },
          {
            key: "requests" as DashboardView,
            href: DASHBOARD_ROUTES.requests,
            label: t.requests,
            icon: Activity,
          },
        ],
      },
      {
        label: locale === "zh-CN" ? "管理" : "Manage",
        items: [
          {
            key: "channels" as DashboardView,
            href: DASHBOARD_ROUTES.channels,
            label: t.channels,
            icon: Waypoints,
          },
          {
            key: "groups" as DashboardView,
            href: DASHBOARD_ROUTES.groups,
            label: t.groups,
            icon: Layers3,
          },
        ],
      },
      {
        label: locale === "zh-CN" ? "系统" : "System",
        items: [
          {
            key: "settings" as DashboardView,
            href: DASHBOARD_ROUTES.settings,
            label: t.settings,
            icon: Settings2,
          },
          {
            key: "apiKeys" as DashboardView,
            href: DASHBOARD_ROUTES.apiKeys,
            label: t.apiKeys,
            icon: KeyRound,
          },
          {
            key: "cronjobs" as DashboardView,
            href: DASHBOARD_ROUTES.cronjobs,
            label: t.cronjobs,
            icon: CalendarClock,
          },
          {
            key: "backups" as DashboardView,
            href: DASHBOARD_ROUTES.backups,
            label: t.backups,
            icon: ArchiveRestore,
          },
        ],
      },
    ],
    [locale, t],
  );

  const allItems = useMemo(
    () => navGroups.flatMap((g) => g.items),
    [navGroups],
  );
  const activeLabel =
    allItems.find((i) => i.key === activeView)?.label ?? t.dashboard;
  const activeGroupLabel = navGroups.find((group) =>
    group.items.some((item) => item.key === activeView),
  )?.label;

  useEffect(() => {
    document.title = `${activeLabel} - ${siteName}`;
  }, [activeLabel, siteName]);

  function handleSignOut() {
    clearStoredToken();
    window.location.href = "/login";
  }

  function handleViewIntent(href: string) {
    router.prefetch(href);
  }

  return (
    <DashboardHeaderActionsContext.Provider value={headerActionsContext}>
      <SidebarProvider className="h-dvh max-h-dvh overflow-hidden bg-muted">
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
                      onMouseEnter={() =>
                        handleViewIntent(DASHBOARD_ROUTES.overview)
                      }
                      onFocus={() =>
                        handleViewIntent(DASHBOARD_ROUTES.overview)
                      }
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
                      onIntent={handleViewIntent}
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
              {versionCheck?.has_update ? (
                versionCheck.release_url ? (
                  <Badge
                    asChild
                    variant="destructive"
                    className="mx-auto max-w-full group-data-[collapsible=icon]:size-5 group-data-[collapsible=icon]:px-0"
                    title={updateTitle}
                  >
                    <a
                      href={versionCheck.release_url}
                      target="_blank"
                      rel="noreferrer"
                    >
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

        <SidebarInset className="min-h-0 min-w-0 flex-1 overflow-hidden bg-muted">
          <header className="flex min-h-14 min-w-0 shrink-0 items-center justify-between gap-2 bg-muted px-3 py-2 sm:px-4">
            <div className="flex min-w-0 items-center gap-2">
              <div className="hidden md:block">
                <CollapseButton
                  expandedLabel={locale === "zh-CN" ? "收起侧边栏" : "Collapse"}
                  collapsedLabel={locale === "zh-CN" ? "展开侧边栏" : "Expand"}
                  iconOnly
                />
              </div>
              <div className="flex min-w-0 items-center gap-2 md:hidden">
                <SidebarTrigger
                  aria-label={
                    locale === "zh-CN" ? "打开导航" : "Open navigation"
                  }
                />
                <span className="truncate text-sm font-medium text-foreground">
                  {activeLabel}
                </span>
              </div>
              <Breadcrumb className="hidden min-w-0 md:block">
                <BreadcrumbList className="min-w-0 flex-nowrap text-sm">
                  {activeGroupLabel ? (
                    <>
                      <BreadcrumbItem className="shrink-0">
                        <span>{activeGroupLabel}</span>
                      </BreadcrumbItem>
                      <BreadcrumbSeparator />
                    </>
                  ) : null}
                  <BreadcrumbItem className="min-w-0">
                    <BreadcrumbPage className="truncate text-base font-semibold">
                      {activeLabel}
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
                      aria-label={languageActionLabel}
                      onClick={() => setLocale(nextLocale)}
                    >
                      <Globe2 />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" align="end">
                    {languageActionLabel}
                  </TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label={t.signOut}
                      onClick={handleSignOut}
                    >
                      <LogOut />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" align="end">
                    {t.signOut}
                  </TooltipContent>
                </Tooltip>
              </div>
            </div>
          </header>

          <div className="hide-scrollbar min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain bg-muted p-3 pb-6 sm:p-4 sm:pb-7 lg:p-6 lg:pb-8">
            <div
              key={pathname}
              className="min-h-[calc(100vh-10rem)] min-w-0 animate-[fadeIn_.16s_ease-out]"
            >
              {children}
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </DashboardHeaderActionsContext.Provider>
  );
}
