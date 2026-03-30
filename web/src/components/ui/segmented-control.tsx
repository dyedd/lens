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
    <div className="inline-flex rounded-full border border-white/70 bg-[rgba(255,255,255,0.72)] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)] backdrop-blur-xl">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onValueChange(option.value)}
          className={cn(
            'rounded-full px-4 py-2 text-sm font-medium transition',
            option.value === value
              ? 'bg-white text-[var(--text)] shadow-[0_10px_24px_rgba(24,46,79,0.14)]'
              : 'text-[var(--muted)] hover:text-[var(--text)]'
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
