import { cn } from '@/lib/cn'

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string
  title: string
  description?: string
  actions?: React.ReactNode
}) {
  return (
    <div className="rounded-[34px] border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.82),rgba(245,248,252,0.72))] p-6 shadow-[0_24px_60px_rgba(24,46,79,0.08)] backdrop-blur-[22px] md:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[var(--accent)]">{eyebrow}</p>
          <h2 className="mt-3 text-3xl font-semibold leading-tight text-[var(--text)] md:text-4xl">{title}</h2>
          {description ? <p className="mt-4 text-sm leading-7 text-[var(--muted)] md:text-[15px]">{description}</p> : null}
        </div>
        {actions ? <div className={cn('flex flex-wrap items-center gap-3')}>{actions}</div> : null}
      </div>
    </div>
  )
}
