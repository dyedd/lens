import { ChevronLeft, LogOut, PanelLeft } from "lucide-react";
import { Link } from "react-router";
import {
  DASHBOARD_ROUTES,
  type DashboardView,
} from "@/components/shell/dashboardRoutes";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useSidebar } from "@/components/ui/SidebarContext";
import { SidebarGroup } from "@/components/ui/SidebarGroup";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/SidebarLayout";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/SidebarMenu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { Locale } from "@/lib/I18nContext";

export interface DashboardSidebarNavItem {
  key: DashboardView;
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  activeViews?: readonly DashboardView[];
}

interface DashboardSidebarProps {
  navItems: DashboardSidebarNavItem[];
  activeView: DashboardView;
  siteName: string;
  logoUrl: string;
  currentVersion?: string;
  hasUpdate: boolean;
  updateTitle: string;
  updateReleaseUrl?: string;
  locale: Locale;
  onSignOut: () => void;
}

function ShellNavItem({
  item,
  activeView,
}: {
  item: DashboardSidebarNavItem;
  activeView: DashboardView;
}) {
  const { isMobile, setOpenMobile } = useSidebar();
  const Icon = item.icon;
  const active =
    item.activeViews?.includes(activeView) ?? activeView === item.key;

  function handleNavigate() {
    if (isMobile) {
      setOpenMobile(false);
    }
  }

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={active}
        tooltip={item.label}
        className="h-11 w-full max-w-full rounded-md px-3.5 text-base font-medium text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-active:bg-sidebar-accent data-active:text-sidebar-accent-foreground data-active:shadow-none group-data-[collapsible=icon]:mx-auto"
      >
        <Link to={item.href} onClick={handleNavigate}>
          <Icon className="sidebar-nav-icon size-5!" />
          <span>{item.label}</span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

/** Renders the dashboard navigation sidebar. */
export function DashboardSidebar({
  navItems,
  activeView,
  siteName,
  logoUrl,
  currentVersion,
  hasUpdate,
  updateTitle,
  updateReleaseUrl,
  locale,
  onSignOut,
}: DashboardSidebarProps) {
  const { state } = useSidebar();
  const signOutLabel = locale === "zh-CN" ? "退出登录" : "Sign out";
  const versionText = currentVersion
    ? `v${currentVersion.replace(/^v/i, "")}`
    : null;
  const versionTitle = currentVersion
    ? `${locale === "zh-CN" ? "版本号" : "Version"} ${currentVersion}`
    : undefined;
  const updateBadge = locale === "zh-CN" ? "新" : "New";
  const updateBadgeClassName = "shrink-0 group-data-[collapsible=icon]:hidden";

  return (
    <Sidebar
      collapsible="icon"
      className="relative z-20 border-r border-sidebar-border/60 bg-sidebar"
    >
      <SidebarHeader className="h-[60px] shrink-0 px-6 py-0 group-data-[collapsible=icon]:px-1">
        <div className="flex h-full w-full items-center gap-2.5 group-data-[collapsible=icon]:justify-center">
          <SidebarMenu className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                tooltip={siteName}
                className="h-full rounded-lg px-0 hover:bg-transparent"
              >
                <Link to={DASHBOARD_ROUTES.overview}>
                  <span className="min-w-0 truncate text-2xl font-semibold tracking-tight">
                    {siteName}
                  </span>
                  {versionText ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="shrink-0 text-xs font-normal text-muted-foreground">
                          {versionText}
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="bottom">
                        {versionTitle}
                      </TooltipContent>
                    </Tooltip>
                  ) : null}
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
          <Link
            to={DASHBOARD_ROUTES.overview}
            aria-label={siteName}
            className="hidden size-8 shrink-0 items-center justify-center rounded-lg group-data-[collapsible=icon]:flex"
          >
            <img
              src={logoUrl}
              alt=""
              width={32}
              height={32}
              loading="eager"
              className="size-8 rounded-lg object-contain"
            />
          </Link>
          {hasUpdate ? (
            <Tooltip>
              <TooltipTrigger asChild>
                {updateReleaseUrl ? (
                  <Badge
                    asChild
                    variant="default"
                    className={updateBadgeClassName}
                  >
                    <a href={updateReleaseUrl} target="_blank" rel="noreferrer">
                      {updateBadge}
                    </a>
                  </Badge>
                ) : (
                  <Badge
                    variant="default"
                    className={updateBadgeClassName}
                    tabIndex={0}
                  >
                    {updateBadge}
                  </Badge>
                )}
              </TooltipTrigger>
              <TooltipContent side="bottom">{updateTitle}</TooltipContent>
            </Tooltip>
          ) : null}
          <SidebarTrigger
            aria-label={locale === "zh-CN" ? "打开导航" : "Open navigation"}
            className="size-8 shrink-0 rounded-lg text-sidebar-foreground/50 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground md:hidden"
          >
            <PanelLeft />
          </SidebarTrigger>
        </div>
      </SidebarHeader>
      <SidebarContent className="gap-0 px-3 py-0 group-data-[collapsible=icon]:px-0">
        <SidebarGroup className="px-0 py-2">
          <SidebarMenu>
            {navItems.map((item) => (
              <ShellNavItem
                key={item.key}
                item={item}
                activeView={activeView}
              />
            ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="px-3 pb-3 pt-2 group-data-[collapsible=icon]:px-2">
        <SidebarSeparator className="mb-3" />
        <div className="flex h-10 items-center px-1 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={signOutLabel}
                onClick={onSignOut}
                className="h-10 w-full justify-start gap-3 px-3 text-sm font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground group-data-[collapsible=icon]:size-10 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
              >
                <LogOut className="size-5" />
                <span className="group-data-[collapsible=icon]:hidden">
                  {signOutLabel}
                </span>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top" align="end">
              {signOutLabel}
            </TooltipContent>
          </Tooltip>
        </div>
      </SidebarFooter>
      <SidebarTrigger
        aria-label={
          state === "collapsed"
            ? locale === "zh-CN"
              ? "展开导航"
              : "Expand navigation"
            : locale === "zh-CN"
              ? "收起导航"
              : "Collapse navigation"
        }
        className="absolute top-1/2 right-[-14px] z-30 hidden h-11 w-3.5 -translate-y-1/2 rounded-r-md rounded-l-none border border-l-0 border-sidebar-border bg-sidebar p-0 text-sidebar-foreground/55 shadow-none hover:bg-sidebar-accent hover:text-sidebar-accent-foreground md:flex [&_svg]:size-3"
      >
        <ChevronLeft
          className={
            state === "collapsed"
              ? "rotate-180 transition-transform"
              : "transition-transform"
          }
        />
      </SidebarTrigger>
    </Sidebar>
  );
}
