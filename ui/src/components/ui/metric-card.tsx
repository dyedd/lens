import { LucideIcon } from 'lucide-react'

export function MetricCard({
  icon: Icon,
  label,
  value,
  tone = 'default',
}: {
  icon: LucideIcon
  label: string
  value: React.ReactNode
  tone?: 'default' | 'accent'
}) {
  return (
    <div className="rounded-[28px] border border-white/70 bg-[rgba(255,255,255,0.78)] p-5 shadow-[0_18px_40px_rgba(24,46,79,0.08)] backdrop-blur-[18px]">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-[var(--muted)]">{label}</p>
        <span className={tone === 'accent' ? 'rounded-2xl bg-[rgba(47,111,237,0.12)] p-3 text-[var(--accent)]' : 'rounded-2xl bg-[rgba(22,34,53,0.05)] p-3 text-[var(--text)]'}>
          <Icon size={18} />
        </span>
      </div>
      <div className="mt-6 text-3xl font-semibold tracking-[-0.04em] text-[var(--text)] md:text-4xl">{value}</div>
    </div>
  )
}
