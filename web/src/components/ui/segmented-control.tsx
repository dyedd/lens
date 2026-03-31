"use client"

import { cn } from '@/lib/cn'

export function SegmentedControl<T extends string>({
  value,
  onValueChange,
  options,
}: {
  value: T
  onValueChange: (value: T) => void
  options: Array<{ value: T; label: string }>
}) {
  return (
    <div className="inline-flex rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] p-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onValueChange(option.value)}
          className={cn(
            'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
            option.value === value
              ? 'bg-[var(--accent)] text-white'
              : 'text-[var(--muted)] hover:text-[var(--text)]'
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
