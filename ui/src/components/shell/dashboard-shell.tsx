"use client"

import type { DashboardView } from '@/components/shell/dashboard-view-shell'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  useSidebar,
} from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { apiRequest, type PublicBranding } from '@/lib/api'
import { clearStoredToken } from '@/lib/auth'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { useQuery } from '@tanstack/react-query'
import { Activity, DollarSign, Globe2, Layers3, LayoutDashboard, LogOut, PanelLeftClose, Settings2, Waypoints } from 'lucide-react'
import Image from 'next/image'
import { useEffect, useMemo } from 'react'

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

export function DashboardShell({
  children,
  activeView,
  onViewChange,
  onViewIntent,
}: {
  children: React.ReactNode
  activeView: DashboardView
  onViewChange: (view: DashboardView) => void
  onViewIntent?: (view: DashboardView) => void
}) {
  const { locale, setLocale, t } = useI18n()
  const { data: branding } = useQuery({
    queryKey: ['public-branding'],
    queryFn: () => apiRequest<PublicBranding>('/public/branding'),
  })
  const siteName = branding?.site_name?.trim() || 'Lens'
  const logoUrl = branding?.logo_url?.trim() || '/logo.svg'

  const navGroups = useMemo(() => [
    {
      label: locale === 'zh-CN' ? '监控' : 'Monitor',
      items: [
        { key: 'overview' as DashboardView, label: t.dashboard, icon: LayoutDashboard },
        { key: 'requests' as DashboardView, label: t.requests, icon: Activity },
      ],
    },
    {
      label: locale === 'zh-CN' ? '管理' : 'Manage',
      items: [
        { key: 'channels' as DashboardView, label: t.channels, icon: Waypoints },
        { key: 'groups' as DashboardView, label: t.groups, icon: Layers3 },
        { key: 'model-prices' as DashboardView, label: t.modelPrices, icon: DollarSign },
      ],
    },
    {
      label: locale === 'zh-CN' ? '系统' : 'System',
      items: [
        { key: 'settings' as DashboardView, label: t.settings, icon: Settings2 },
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

  return (
    <SidebarProvider className="h-dvh">
      <Sidebar collapsible="icon" className="z-20">
        <SidebarHeader className="h-14 px-3">
          <div className="flex w-full items-center justify-between gap-2 group-data-[collapsible=icon]:justify-center">
            <div className="flex min-w-0 items-center gap-2 group-data-[collapsible=icon]:hidden">
              <Image
                src={logoUrl}
                alt={siteName}
                width={48}
                height={48}
                loading="eager"
                className="size-10 shrink-0 object-contain"
                unoptimized={logoUrl !== '/logo.svg'}
              />
              <span className="truncate text-sm font-semibold text-sidebar-foreground">
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
                        isActive={activeView === item.key}
                        tooltip={item.label}
                        onClick={() => onViewChange(item.key)}
                        onMouseEnter={() => onViewIntent?.(item.key)}
                        className={cn(activeView === item.key && 'font-medium')}
                      >
                        <Icon />
                        <span>{item.label}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroup>
          ))}
        </SidebarContent>
      </Sidebar>

      <SidebarInset className="min-h-0 flex-1">
        <header className="flex h-14 shrink-0 items-center justify-end gap-3 border-b bg-card px-4">
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

        <div className="hide-scrollbar h-full overflow-y-auto overscroll-contain bg-muted p-6 pb-8">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
