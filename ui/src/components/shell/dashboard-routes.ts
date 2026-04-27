export type DashboardView =
  | 'overview'
  | 'requests'
  | 'channels'
  | 'groups'
  | 'settings'
  | 'apiKeys'
  | 'cronjobs'
  | 'backups'

export type DashboardHref =
  | '/'
  | '/requests'
  | '/channels'
  | '/groups'
  | '/settings'
  | '/api-keys'
  | '/cronjobs'
  | '/backups'

export const DASHBOARD_ROUTES: Record<DashboardView, DashboardHref> = {
  overview: '/',
  requests: '/requests',
  channels: '/channels',
  groups: '/groups',
  settings: '/settings',
  apiKeys: '/api-keys',
  cronjobs: '/cronjobs',
  backups: '/backups',
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
  if (pathname === DASHBOARD_ROUTES.apiKeys || pathname.startsWith(`${DASHBOARD_ROUTES.apiKeys}/`)) {
    return 'apiKeys'
  }
  if (pathname === DASHBOARD_ROUTES.cronjobs || pathname.startsWith(`${DASHBOARD_ROUTES.cronjobs}/`)) {
    return 'cronjobs'
  }
  if (pathname === DASHBOARD_ROUTES.backups || pathname.startsWith(`${DASHBOARD_ROUTES.backups}/`)) {
    return 'backups'
  }
  return 'overview'
}
