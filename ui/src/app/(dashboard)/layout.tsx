import { AuthGuard } from "@/components/auth/AuthGuard";
import { DashboardShell } from "@/components/shell/DashboardShell";

export default function DashboardLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <AuthGuard>
      <DashboardShell>{children}</DashboardShell>
    </AuthGuard>
  );
}
