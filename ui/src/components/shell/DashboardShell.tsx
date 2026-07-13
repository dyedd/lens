"use client";

import { SidebarInset, SidebarProvider } from "@/components/ui/Sidebar";
import {
  DASHBOARD_ROUTES,
  getDashboardViewFromPathname,
  type DashboardView,
} from "@/components/shell/dashboardRoutes";
import {
  DashboardHeaderActionsContext,
  useDashboardHeaderActionsState,
} from "@/components/shell/dashboardHeaderActions";
import { DashboardHeader } from "@/components/shell/DashboardHeader";
import { DashboardSidebar } from "@/components/shell/DashboardSidebar";
import {
  apiRequest,
  hydrateProtocolConversions,
  type AppInfo,
  type VersionCheckResult,
} from "@/lib/api";
import { clearStoredToken } from "@/lib/auth";
import { useI18n } from "@/lib/I18nContext";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArchiveRestore,
  CalendarClock,
  KeyRound,
  Layers3,
  LayoutDashboard,
  Settings2,
  Waypoints,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";

/** Renders the authenticated dashboard navigation and content shell. */
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
    if (appInfo?.protocol_conversions) {
      hydrateProtocolConversions(appInfo.protocol_conversions);
    }
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
        <DashboardSidebar
          navGroups={navGroups}
          activeView={activeView}
          siteName={siteName}
          logoUrl={logoUrl}
          currentVersion={currentVersion}
          versionLabel={versionLabel}
          compactVersionLabel={compactVersionLabel}
          hasUpdate={Boolean(versionCheck?.has_update)}
          updateLabel={updateLabel}
          updateTitle={updateTitle}
          updateReleaseUrl={versionCheck?.release_url}
          locale={locale}
          onViewIntent={handleViewIntent}
        />

        <SidebarInset className="min-h-0 min-w-0 flex-1 overflow-hidden bg-muted">
          <DashboardHeader
            locale={locale}
            labels={{ activeView: activeLabel }}
            group={activeGroupLabel}
            headerActions={headerActions}
            language={{
              label: languageActionLabel,
              onClick: () => setLocale(nextLocale),
            }}
            signOut={{ label: t.signOut, onClick: handleSignOut }}
          />

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
