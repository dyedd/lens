import { DashboardShell } from '@/components/shell/dashboard-shell'
import { AuthGuard } from '@/components/auth/auth-guard'

export default function DashboardLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <AuthGuard>
      {children}
    </AuthGuard>
  )
}
