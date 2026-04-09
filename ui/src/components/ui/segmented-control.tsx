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
    <div className="inline-flex rounded-xl bg-[var(--panel-soft)] p-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onValueChange(option.value)}
          className={cn(
            'rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200',
            option.value === value
              ? 'bg-[var(--panel-strong)] text-[var(--text)] shadow-sm'
              : 'text-[var(--muted)] hover:text-[var(--text)]'
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
