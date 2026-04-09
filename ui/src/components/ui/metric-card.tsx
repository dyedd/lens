import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/cn'

export function MetricCard({
  icon: Icon,
  label,
  value,
  tone = 'default',
  className,
}: {
  icon: LucideIcon
  label: string
  value: React.ReactNode
  tone?: 'default' | 'accent' | 'danger'
  className?: string
}) {
  return (
    <div className={cn("group relative overflow-hidden rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--panel)] p-6 shadow-sm hover:shadow-md transition-shadow duration-200 transition-all hover:shadow-[var(--shadow-lg)]", className)}>
      <div className="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-[var(--accent)] opacity-5 blur-2xl transition-transform group-hover:scale-150" />
      <div className="relative flex items-center justify-between gap-4">
        <p className="text-[13px] font-medium tracking-wide text-[var(--muted)]">{label}</p>
        <span className={cn(
          'flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] transition-colors',
          tone === 'accent' ? 'bg-[var(--accent-2)] text-[var(--accent)]' : 
          tone === 'danger' ? 'bg-red-50 text-[var(--danger)]' : 
          'bg-[var(--panel-soft)] text-[var(--text)]'
        )}>
          <Icon size={18} strokeWidth={2.5} />
        </span>
      </div>
      <div className={cn(
        "relative mt-4 text-3xl font-semibold tracking-tight",
        tone === 'accent' ? 'text-[var(--accent)]' :
        tone === 'danger' ? 'text-[var(--danger)]' :
        'text-[var(--text)]'
      )}>{value}</div>
    </div>
  )
}
