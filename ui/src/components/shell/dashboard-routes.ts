export type DashboardView = 'overview' | 'requests' | 'channels' | 'groups' | 'settings'

export type DashboardHref =
  | '/'
  | '/requests'
  | '/channels'
  | '/groups'
  | '/settings'

export const DASHBOARD_ROUTES: Record<DashboardView, DashboardHref> = {
  overview: '/',
  requests: '/requests',
  channels: '/channels',
  groups: '/groups',
  settings: '/settings',
}

export function getDashboardViewFromPathname(pathname: string): DashboardView {
  if (pathname === DASHBOARD_ROUTES.requests || pathname.startsWith(`${DASHBOARD_ROUTES.requests}/`)) {
    return 'requests'
  }
  if (pathname === DASHBOARD_ROUTES.channels || pathname.startsWith(`${DASHBOARD_ROUTES.channels}/`)) {
    return 'channels'
  }
  if (pathname === DASHBOARD_ROUTES.groups || pathname.startsWith(`${DASHBOARD_ROUTES.groups}/`)) {
    return 'groups'
  }
  if (pathname === DASHBOARD_ROUTES.settings || pathname.startsWith(`${DASHBOARD_ROUTES.settings}/`)) {
    return 'settings'
  }
  return 'overview'
}
