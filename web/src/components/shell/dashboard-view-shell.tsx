"use client"

import { Suspense, useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Activity, KeyRound, Layers3, Settings2, Waypoints } from 'lucide-react'
import { OverviewScreen } from '@/components/screens/overview-screen'
import { RequestsScreen } from '@/components/screens/requests-screen'
import { ChannelsScreen } from '@/components/screens/channels-screen'
import { GroupsScreen } from '@/components/screens/groups-screen'
import { KeysScreen } from '@/components/screens/keys-screen'
import { SettingsScreen } from '@/components/screens/settings-screen'
import { DashboardShell } from '@/components/shell/dashboard-shell'

export type DashboardView = 'overview' | 'requests' | 'channels' | 'groups' | 'keys' | 'settings'

export const DASHBOARD_VIEWS: Array<{ key: DashboardView; label: string; icon: React.ComponentType<{ size?: number; className?: string }> }> = [
  { key: 'overview', label: 'overview', icon: Layers3 },
  { key: 'requests', label: 'requests', icon: Activity },
  { key: 'channels', label: 'channels', icon: Waypoints },
  { key: 'groups', label: 'groups', icon: Layers3 },
  { key: 'keys', label: 'keys', icon: KeyRound },
  { key: 'settings', label: 'settings', icon: Settings2 },
]

function isDashboardView(value: string | null): value is DashboardView {
  return value === 'overview' || value === 'requests' || value === 'channels' || value === 'groups' || value === 'keys' || value === 'settings'
}

function ScreenContent({ view }: { view: DashboardView }) {
  switch (view) {
    case 'requests':
      return <RequestsScreen />
    case 'channels':
      return <ChannelsScreen />
    case 'groups':
      return <GroupsScreen />
    case 'keys':
      return <KeysScreen />
    case 'settings':
      return <SettingsScreen />
    case 'overview':
    default:
      return <OverviewScreen />
  }
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

  function handleViewChange(nextView: DashboardView) {
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

  return (
    <DashboardShell activeView={activeView} onViewChange={handleViewChange}>
      <ScreenContent view={activeView} />
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
