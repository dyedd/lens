"use client"

import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '@/lib/cn'

export { Dialog }

export function AppDialogContent({
  children,
  className,
  title,
  description,
}: {
  children: React.ReactNode
  className?: string
  title: string
  description?: string
}) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-50 bg-[rgba(34,31,25,0.22)] data-[state=open]:animate-[fadeIn_.18s_ease-out]" />
      <Dialog.Content
        className={cn(
          'fixed left-1/2 top-1/2 z-50 flex max-h-[88vh] w-[calc(100vw-1.5rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-6 shadow-[0_20px_48px_rgba(63,53,40,0.12)] outline-none data-[state=open]:animate-[dialogIn_.22s_ease-out]',
          className
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <Dialog.Title className="text-xl font-semibold text-[var(--text)]">{title}</Dialog.Title>
            {description ? <Dialog.Description className="mt-2 text-sm leading-6 text-[var(--muted)]">{description}</Dialog.Description> : null}
          </div>
          <Dialog.Close className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel)] text-[var(--muted)] transition hover:text-[var(--text)]">
            <X size={18} />
          </Dialog.Close>
        </div>
        <div className="hide-scrollbar mt-6 min-h-0 flex-1 overflow-y-auto pr-1">{children}</div>
      </Dialog.Content>
    </Dialog.Portal>
  )
}
