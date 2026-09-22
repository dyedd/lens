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
  username: string;
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
        className="h-9 w-full max-w-full rounded-md px-3.5 text-sm font-medium text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-active:bg-sidebar-accent data-active:text-sidebar-accent-foreground data-active:shadow-none group-data-[collapsible=icon]:mx-auto"
      >
        <Link to={item.href} onClick={handleNavigate}>
          <Icon className="sidebar-nav-icon" />
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
  username,
  onSignOut,
}: DashboardSidebarProps) {
  const accountName = username || siteName;
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
      className="z-20 border-r border-sidebar-border/60 bg-sidebar"
    >
      <SidebarHeader className="px-3 py-4 group-data-[collapsible=icon]:px-2">
        <div className="flex w-full items-center gap-2 group-data-[collapsible=icon]:justify-center">
          <SidebarMenu className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                tooltip={siteName}
                className="h-10 rounded-lg px-2 hover:bg-transparent group-data-[collapsible=icon]:justify-center"
              >
                <Link to={DASHBOARD_ROUTES.overview}>
                  <img
                    src={logoUrl}
                    alt={siteName}
                    width={24}
                    height={24}
                    loading="eager"
                    className="size-7 shrink-0 rounded-md object-contain"
                  />
                  <span className="min-w-0 truncate text-[15px] font-semibold tracking-tight">
                    {siteName}
                  </span>
                  {versionText ? (
                    <span
                      className="shrink-0 text-xs font-normal text-muted-foreground"
                      title={versionTitle}
                    >
                      {versionText}
                    </span>
                  ) : null}
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
          {hasUpdate ? (
            updateReleaseUrl ? (
              <Badge
                asChild
                variant="destructive"
                className={updateBadgeClassName}
                title={updateTitle}
              >
                <a href={updateReleaseUrl} target="_blank" rel="noreferrer">
                  {updateBadge}
                </a>
              </Badge>
            ) : (
              <Badge
                variant="destructive"
                className={updateBadgeClassName}
                title={updateTitle}
              >
                {updateBadge}
              </Badge>
            )
          ) : null}
          <SidebarTrigger
            aria-label="Toggle sidebar"
            className="size-8 shrink-0 rounded-lg text-sidebar-foreground/50 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground group-data-[collapsible=icon]:mx-auto"
          >
            <PanelLeft />
          </SidebarTrigger>
        </div>
      </SidebarHeader>
      <SidebarContent className="gap-0 px-3 py-2 group-data-[collapsible=icon]:px-0">
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
        <div className="flex h-9 items-center gap-1 px-1 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
          <span className="min-w-0 flex-1 truncate px-2 text-sm font-medium text-sidebar-foreground group-data-[collapsible=icon]:hidden">
            {accountName}
          </span>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={signOutLabel}
                onClick={onSignOut}
                className="size-8 shrink-0 text-sidebar-foreground/50 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              >
                <LogOut />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top" align="end">
              {signOutLabel}
            </TooltipContent>
          </Tooltip>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
