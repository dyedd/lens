import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useLocation } from "react-router";
import { DashboardHeader } from "@/components/shell/DashboardHeader";
import {
  DashboardSidebar,
  type DashboardSidebarNavItem,
} from "@/components/shell/DashboardSidebar";
import {
  DashboardHeaderActionsContext,
  useDashboardHeaderActionsState,
} from "@/components/shell/dashboardHeaderActions";
import {
  DASHBOARD_ROUTES,
  getDashboardViewFromPathname,
} from "@/components/shell/dashboardRoutes";
import { SidebarProvider } from "@/components/ui/SidebarContext";
import { SidebarInset } from "@/components/ui/SidebarLayout";
import type { AdminProfile, AppInfo, VersionCheckResult } from "@/lib/api/app";
import { apiRequest } from "@/lib/api/client";
import { clearStoredToken } from "@/lib/auth";
import { useI18n } from "@/lib/I18nContext";
import {
  BillingIcon,
  ChannelsIcon,
  GroupsIcon,
  HealthIcon,
  OverviewIcon,
  RequestsIcon,
  SettingsIcon,
} from "./SidebarNavIcons";

/** Renders the authenticated dashboard navigation and content shell. */
export function DashboardShell({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const { locale, setLocale, t } = useI18n();
  const { data: appInfo } = useQuery({
    queryKey: ["app-info"],
    queryFn: () => apiRequest<AppInfo>("/admin/app-info"),
    staleTime: 5 * 60_000,
  });
  const { data: profile } = useQuery({
    queryKey: ["auth-me"],
    queryFn: () => apiRequest<AdminProfile>("/admin/session"),
    staleTime: 60_000,
  });
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

  const navItems = useMemo<DashboardSidebarNavItem[]>(
    () => [
      {
        key: "overview",
        href: DASHBOARD_ROUTES.overview,
        label: t.overview,
        icon: OverviewIcon,
      },
      {
        key: "modelHealth",
        href: DASHBOARD_ROUTES.modelHealth,
        label: t.modelHealth,
        icon: HealthIcon,
      },
      {
        key: "requests",
        href: DASHBOARD_ROUTES.requests,
        label: t.requests,
        icon: RequestsIcon,
      },
      {
        key: "channels",
        href: DASHBOARD_ROUTES.channels,
        label: t.channels,
        icon: ChannelsIcon,
      },
      {
        key: "groups",
        href: DASHBOARD_ROUTES.groups,
        label: t.groups,
        icon: GroupsIcon,
      },
      {
        key: "billing",
        href: DASHBOARD_ROUTES.billing,
        label: t.billing,
        icon: BillingIcon,
      },
      {
        key: "settings",
        href: DASHBOARD_ROUTES.settings,
        label: t.settings,
        icon: SettingsIcon,
        activeViews: ["settings", "apiKeys", "cronjobs", "backups"],
      },
    ],
    [t],
  );

  const activeLabel =
    navItems.find(
      (item) =>
        item.activeViews?.includes(activeView) || item.key === activeView,
    )?.label ?? t.dashboard;

  useEffect(() => {
    document.title = `${activeLabel} - ${siteName}`;
  }, [activeLabel, siteName]);

  function handleSignOut() {
    clearStoredToken();
    window.location.href = "/login";
  }

  return (
    <DashboardHeaderActionsContext.Provider value={headerActionsContext}>
      <SidebarProvider className="h-dvh max-h-dvh overflow-hidden bg-background">
        <DashboardSidebar
          navItems={navItems}
          activeView={activeView}
          siteName={siteName}
          logoUrl={logoUrl}
          currentVersion={currentVersion}
          hasUpdate={Boolean(versionCheck?.has_update)}
          updateTitle={updateTitle}
          updateReleaseUrl={versionCheck?.release_url}
          locale={locale}
          username={profile?.username ?? ""}
          onSignOut={handleSignOut}
        />

        <SidebarInset className="min-h-0 min-w-0 flex-1 overflow-hidden bg-background">
          <DashboardHeader
            locale={locale}
            labels={{ activeView: activeLabel }}
            headerActions={headerActions}
            language={{
              label: languageActionLabel,
              onClick: () => setLocale(nextLocale),
            }}
          />

          <div className="hide-scrollbar min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain bg-background px-4 py-4 pb-10 sm:px-6 lg:px-8">
            <div
              key={pathname}
              className="mx-auto min-h-[calc(100vh-10rem)] min-w-0 max-w-[1230px] animate-[fadeIn_.16s_ease-out]"
            >
              {children}
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </DashboardHeaderActionsContext.Provider>
  );
}
