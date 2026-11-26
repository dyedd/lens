import { LogOut, PanelLeft } from "lucide-react";
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
        className="h-9 w-full max-w-full rounded-lg px-2.5 text-[13px] font-normal text-sidebar-foreground transition-colors hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground data-active:bg-sidebar-accent data-active:font-medium data-active:text-sidebar-accent-foreground data-active:shadow-none group-data-[collapsible=icon]:mx-auto"
      >
        <Link to={item.href} onClick={handleNavigate}>
          <Icon className="sidebar-nav-icon size-4!" />
          <span className="flex-1 truncate">{item.label}</span>
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
  const { isMobile, state } = useSidebar();
  const signOutLabel = locale === "zh-CN" ? "退出登录" : "Sign out";
  const versionText = currentVersion
    ? `v${currentVersion.replace(/^v/i, "")}`
    : null;
  const updateBadge = locale === "zh-CN" ? "新" : "New";
  const updateBadgeClassName = "shrink-0 group-data-[collapsible=icon]:hidden";

  return (
    <Sidebar
      collapsible="icon"
      className="relative z-20 border-r border-sidebar-border/80 bg-sidebar"
    >
      <SidebarHeader className="h-12 shrink-0 px-3 py-0 group-data-[collapsible=icon]:px-1">
        <div className="flex h-full w-full items-center gap-2 group-data-[collapsible=icon]:justify-center">
          <SidebarMenu className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                className="h-9 rounded-lg px-1.5 hover:bg-transparent"
              >
                <Link
                  to={DASHBOARD_ROUTES.overview}
                  className="flex items-center gap-2"
                >
                  <img
                    src={logoUrl}
                    alt=""
                    width={22}
                    height={22}
                    loading="eager"
                    className="size-5.5 shrink-0 rounded-md object-contain"
                  />
                  <span className="min-w-0 truncate text-[15px] font-semibold tracking-tight text-card-foreground">
                    {siteName}
                  </span>
                  {versionText ? (
                    <span className="shrink-0 font-mono text-[11px] leading-none text-muted-foreground">
                      {versionText}
                    </span>
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
              width={24}
              height={24}
              loading="eager"
              className="size-6 rounded-md object-contain"
            />
          </Link>
          {hasUpdate ? (
            <Tooltip>
              <TooltipTrigger asChild>
                {updateReleaseUrl ? (
                  <Badge
                    asChild
                    variant="secondary"
                    className={updateBadgeClassName}
                  >
                    <a href={updateReleaseUrl} target="_blank" rel="noreferrer">
                      {updateBadge}
                    </a>
                  </Badge>
                ) : (
                  <Badge
                    variant="secondary"
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
            className="size-8 shrink-0 rounded-lg text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground md:hidden"
          >
            <PanelLeft />
          </SidebarTrigger>
        </div>
      </SidebarHeader>
      <SidebarContent className="gap-2 px-2.5 py-2.5 group-data-[collapsible=icon]:px-0">
        {(
          [
            {
              label: locale === "zh-CN" ? "观测" : "Observe",
              keys: new Set<DashboardView>([
                "overview",
                "modelHealth",
                "requests",
              ]),
            },
            {
              label: locale === "zh-CN" ? "路由" : "Routing",
              keys: new Set<DashboardView>(["channels", "groups", "billing"]),
            },
            {
              label: locale === "zh-CN" ? "系统" : "System",
              keys: new Set<DashboardView>([
                "settings",
                "apiKeys",
                "cronjobs",
                "backups",
              ]),
            },
          ] as const
        ).map((group) => {
          const groupItems = navItems.filter((item) =>
            group.keys.has(item.key),
          );
          if (!groupItems.length) return null;
          return (
            <SidebarGroup key={group.label} className="px-0 py-0.5">
              <div className="px-2.5 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground/75 uppercase group-data-[collapsible=icon]:hidden">
                {group.label}
              </div>
              <SidebarMenu className="gap-0.5">
                {groupItems.map((item) => (
                  <ShellNavItem
                    key={item.key}
                    item={item}
                    activeView={activeView}
                  />
                ))}
              </SidebarMenu>
            </SidebarGroup>
          );
        })}
      </SidebarContent>
      <SidebarFooter className="px-2.5 pb-3 pt-1 group-data-[collapsible=icon]:px-2">
        <SidebarSeparator className="mb-2 bg-sidebar-border/60" />
        <div className="flex h-9 items-center group-data-[collapsible=icon]:justify-center">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={signOutLabel}
                onClick={onSignOut}
                className="h-9 w-full justify-start gap-2.5 rounded-lg px-2.5 text-[13px] font-normal text-sidebar-foreground hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground group-data-[collapsible=icon]:size-9 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
              >
                <LogOut className="size-4" />
                <span className="group-data-[collapsible=icon]:hidden">
                  {signOutLabel}
                </span>
              </Button>
            </TooltipTrigger>
            {state === "collapsed" && !isMobile ? (
              <TooltipContent side="right" align="center">
                {signOutLabel}
              </TooltipContent>
            ) : null}
          </Tooltip>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
