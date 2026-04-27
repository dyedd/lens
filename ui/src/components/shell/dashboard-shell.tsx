"use client"

import { Button } from '@/components/ui/button'
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
  useSidebar,
} from '@/components/ui/sidebar'
import { DASHBOARD_ROUTES, getDashboardViewFromPathname, type DashboardView } from '@/components/shell/dashboard-routes'
import { apiRequest, type AppInfo } from '@/lib/api'
import { clearStoredToken } from '@/lib/auth'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { useQuery } from '@tanstack/react-query'
import { Activity, ArchiveRestore, CalendarClock, Globe2, KeyRound, Layers3, LayoutDashboard, LogOut, PanelLeftClose, Settings2, Waypoints } from 'lucide-react'
import Image from 'next/image'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useMemo } from 'react'

const GITHUB_REPO_URL = 'https://github.com/dyedd/lens'

function GitHubMark(props: React.ComponentProps<'svg'>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M12 .5a12 12 0 0 0-3.79 23.39c.6.1.82-.26.82-.58v-2.03c-3.34.73-4.04-1.42-4.04-1.42-.55-1.38-1.34-1.75-1.34-1.75-1.1-.74.08-.72.08-.72 1.2.09 1.84 1.22 1.84 1.22 1.08 1.8 2.82 1.28 3.5.98.1-.76.42-1.28.76-1.58-2.67-.3-5.47-1.31-5.47-5.86 0-1.3.47-2.36 1.23-3.19-.12-.3-.53-1.5.12-3.13 0 0 1.01-.32 3.3 1.22a11.6 11.6 0 0 1 6 0c2.28-1.54 3.29-1.22 3.29-1.22.65 1.63.24 2.83.12 3.13.77.83 1.23 1.88 1.23 3.19 0 4.56-2.8 5.55-5.48 5.85.43.36.82 1.08.82 2.18v3.23c0 .32.22.69.83.58A12 12 0 0 0 12 .5Z" />
    </svg>
  )
}

function CollapseButton({ label, iconOnly = false }: { label: string; iconOnly?: boolean }) {
  const { toggleSidebar, state } = useSidebar()
  return (
    <SidebarMenuButton
      tooltip={label}
      onClick={toggleSidebar}
      className={cn("text-muted-foreground", iconOnly && "size-8 p-2")}
    >
      <PanelLeftClose className={cn("transition-transform", state === 'collapsed' && "rotate-180")} />
      <span className={cn(iconOnly && "sr-only")}>{label}</span>
    </SidebarMenuButton>
  )
}

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { locale, setLocale, t } = useI18n()
  const { data: appInfo } = useQuery({
    queryKey: ['app-info'],
    queryFn: () => apiRequest<AppInfo>('/admin/app-info'),
    staleTime: 5 * 60_000,
  })
  const siteName = appInfo?.site_name?.trim() || 'Lens'
  const logoUrl = appInfo?.logo_url?.trim() || '/logo.svg'
  const activeView = useMemo(() => getDashboardViewFromPathname(pathname), [pathname])
  const currentVersion = appInfo?.system_version?.trim()
  const versionLabel = currentVersion
    ? `${locale === 'zh-CN' ? '版本号' : 'Version'} ${currentVersion}`
    : (appInfo ? (locale === 'zh-CN' ? '版本未获取' : 'Unavailable') : (locale === 'zh-CN' ? '加载中...' : 'Loading...'))

  const navGroups = useMemo(() => [
    {
      label: locale === 'zh-CN' ? '监控' : 'Monitor',
      items: [
        { key: 'overview' as DashboardView, href: DASHBOARD_ROUTES.overview, label: t.dashboard, icon: LayoutDashboard },
        { key: 'requests' as DashboardView, href: DASHBOARD_ROUTES.requests, label: t.requests, icon: Activity },
      ],
    },
    {
      label: locale === 'zh-CN' ? '管理' : 'Manage',
      items: [
        { key: 'channels' as DashboardView, href: DASHBOARD_ROUTES.channels, label: t.channels, icon: Waypoints },
        { key: 'groups' as DashboardView, href: DASHBOARD_ROUTES.groups, label: t.groups, icon: Layers3 },
      ],
    },
    {
      label: locale === 'zh-CN' ? '系统' : 'System',
      items: [
        { key: 'settings' as DashboardView, href: DASHBOARD_ROUTES.settings, label: t.settings, icon: Settings2 },
        { key: 'apiKeys' as DashboardView, href: DASHBOARD_ROUTES.apiKeys, label: t.apiKeys, icon: KeyRound },
        { key: 'cronjobs' as DashboardView, href: DASHBOARD_ROUTES.cronjobs, label: t.cronjobs, icon: CalendarClock },
        { key: 'backups' as DashboardView, href: DASHBOARD_ROUTES.backups, label: t.backups, icon: ArchiveRestore },
      ],
    },
  ], [locale, t])

  const allItems = useMemo(() => navGroups.flatMap(g => g.items), [navGroups])
  const activeLabel = allItems.find(i => i.key === activeView)?.label ?? t.dashboard

  useEffect(() => {
    document.title = `${activeLabel} - ${siteName}`
  }, [activeLabel, siteName])

  function handleSignOut() {
    clearStoredToken()
    window.location.href = '/login'
  }

  function handleViewIntent(href: string) {
    router.prefetch(href)
  }

  return (
    <SidebarProvider className="h-dvh max-h-dvh overflow-hidden">
      <Sidebar collapsible="icon" className="z-20">
        <SidebarHeader className="min-h-[4.5rem] px-4 py-3">
          <div className="flex w-full items-center justify-between gap-2 group-data-[collapsible=icon]:justify-center">
            <div className="flex min-w-0 items-center gap-2 group-data-[collapsible=icon]:hidden">
              <Image
                src={logoUrl}
                alt={siteName}
                width={36}
                height={36}
                loading="eager"
                className="shrink-0 object-contain"
                unoptimized={logoUrl !== '/logo.svg'}
              />
              <span className="truncate text-base font-semibold text-sidebar-foreground">
                {siteName}
              </span>
            </div>
            <div className="group-data-[collapsible=icon]:hidden">
              <CollapseButton label={locale === 'zh-CN' ? '收起侧边栏' : 'Collapse'} iconOnly />
            </div>
            <div className="hidden group-data-[collapsible=icon]:block">
              <CollapseButton label={locale === 'zh-CN' ? '展开侧边栏' : 'Expand'} iconOnly />
            </div>
          </div>
        </SidebarHeader>
        <SidebarContent className="py-2">
          {navGroups.map((group) => (
            <SidebarGroup key={group.label}>
              <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
              <SidebarMenu>
                {group.items.map((item) => {
                  const Icon = item.icon
                  return (
                    <SidebarMenuItem key={item.key}>
                      <SidebarMenuButton
                        asChild
                        isActive={activeView === item.key}
                        tooltip={item.label}
                        onMouseEnter={() => handleViewIntent(item.href)}
                        onFocus={() => handleViewIntent(item.href)}
                        className={cn(activeView === item.key && 'font-medium')}
                      >
                        <Link href={item.href} scroll={false}>
                          <Icon />
                          <span>{item.label}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroup>
          ))}
        </SidebarContent>
        <SidebarFooter className="px-3 py-3 group-data-[collapsible=icon]:px-2">
          <SidebarSeparator />
          <div className="flex flex-col gap-2 px-2 pt-2 group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0">
            <div
              className="text-center text-sm font-medium text-sidebar-foreground/90 group-data-[collapsible=icon]:text-xs"
              title={versionLabel}
            >
              {versionLabel}
            </div>
            <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton asChild tooltip="GitHub" className="justify-center group-data-[collapsible=icon]:justify-center">
                <a href={GITHUB_REPO_URL} target="_blank" rel="noreferrer" aria-label="GitHub">
                  <GitHubMark />
                  <span>GitHub</span>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
            </SidebarMenu>
          </div>
        </SidebarFooter>
      </Sidebar>

      <SidebarInset className="min-h-0 min-w-0 flex-1 overflow-hidden">
        <header className="flex h-14 min-w-0 shrink-0 items-center justify-end gap-3 border-b bg-card px-4">
          <div className="flex shrink-0 items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
            >
              <Globe2 data-icon="inline-start" />
              {locale === 'zh-CN' ? 'English' : '中文'}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={handleSignOut}>
              <LogOut data-icon="inline-start" />
              {t.signOut}
            </Button>
          </div>
        </header>

        <div className="hide-scrollbar min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain bg-muted p-6 pb-8">
          <div key={pathname} className="min-h-[calc(100vh-10rem)] min-w-0 animate-[fadeIn_.16s_ease-out]">
            {children}
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
