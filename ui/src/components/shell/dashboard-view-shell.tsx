"use client"

import { Suspense, useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { DashboardShell } from '@/components/shell/dashboard-shell'
import { lazyWithPreload } from '@/lib/lazy-with-preload'

export type DashboardView = 'overview' | 'requests' | 'channels' | 'groups' | 'model-prices' | 'settings'

type LazyScreen = ReturnType<typeof lazyWithPreload>

const OverviewModule = lazyWithPreload(() => import('@/components/screens/overview-screen').then((m) => ({ default: m.OverviewScreen })))
const RequestsModule = lazyWithPreload(() => import('@/components/screens/requests-screen').then((m) => ({ default: m.RequestsScreen })))
const ChannelsModule = lazyWithPreload(() => import('@/components/screens/channels-screen').then((m) => ({ default: m.ChannelsScreen })))
const GroupsModule = lazyWithPreload(() => import('@/components/screens/groups-screen').then((m) => ({ default: m.GroupsScreen })))
const ModelPricesModule = lazyWithPreload(() => import('@/components/screens/model-prices-screen').then((m) => ({ default: m.ModelPricesScreen })))
const SettingsModule = lazyWithPreload(() => import('@/components/screens/settings-screen').then((m) => ({ default: m.SettingsScreen })))

const VIEW_COMPONENTS: Record<DashboardView, LazyScreen> = {
  overview: OverviewModule,
  requests: RequestsModule,
  channels: ChannelsModule,
  groups: GroupsModule,
  'model-prices': ModelPricesModule,
  settings: SettingsModule,
}

function isDashboardView(value: string | null): value is DashboardView {
  return value === 'overview' || value === 'requests' || value === 'channels' || value === 'groups' || value === 'model-prices' || value === 'settings'
}

function DashboardViewShellInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialView = useMemo<DashboardView>(() => {
    const queryView = searchParams.get('view')
    return isDashboardView(queryView) ? queryView : 'overview'
  }, [searchParams])
  const [activeView, setActiveView] = useState<DashboardView>(initialView)

  useEffect(() => {
    setActiveView(initialView)
  }, [initialView])

  useEffect(() => {
    VIEW_COMPONENTS.overview.preload()
    VIEW_COMPONENTS.channels.preload()
    VIEW_COMPONENTS.groups.preload()
    VIEW_COMPONENTS['model-prices'].preload()
    VIEW_COMPONENTS.requests.preload()
  }, [])

  const ActiveScreen = VIEW_COMPONENTS[activeView]

  function handleViewChange(nextView: DashboardView) {
    VIEW_COMPONENTS[nextView].preload()
    setActiveView(nextView)
    const nextParams = new URLSearchParams(searchParams.toString())
    if (nextView === 'overview') {
      nextParams.delete('view')
    } else {
      nextParams.set('view', nextView)
    }
    const query = nextParams.toString()
    router.replace(query ? '/dashboard?' + query : '/dashboard', { scroll: false })
  }

  function handleViewIntent(nextView: DashboardView) {
    VIEW_COMPONENTS[nextView].preload()
  }

  return (
    <DashboardShell activeView={activeView} onViewChange={handleViewChange} onViewIntent={handleViewIntent}>
      <div key={activeView} className="min-h-[calc(100vh-10rem)] animate-[fadeIn_.16s_ease-out]">
        <Suspense fallback={<div className="py-10 text-sm text-[var(--muted)]">Loading...</div>}>
          <ActiveScreen />
        </Suspense>
      </div>
    </DashboardShell>
  )
}

export function DashboardViewShell() {
  return (
    <Suspense fallback={null}>
      <DashboardViewShellInner />
    </Suspense>
  )
}
