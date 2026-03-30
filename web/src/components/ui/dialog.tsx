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
      <Dialog.Overlay className="fixed inset-0 z-50 bg-[rgba(18,24,38,0.28)] backdrop-blur-[10px] data-[state=open]:animate-[fadeIn_.18s_ease-out]" />
      <Dialog.Content
        className={cn(
          'fixed left-1/2 top-1/2 z-50 w-[calc(100vw-1.5rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 rounded-[32px] border border-white/60 bg-[rgba(255,255,255,0.88)] p-6 shadow-[0_30px_80px_rgba(31,41,55,0.18)] backdrop-blur-[26px] outline-none data-[state=open]:animate-[dialogIn_.22s_ease-out]',
          className
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <Dialog.Title className="text-xl font-semibold text-[var(--text)]">{title}</Dialog.Title>
            {description ? <Dialog.Description className="mt-2 text-sm leading-6 text-[var(--muted)]">{description}</Dialog.Description> : null}
          </div>
          <Dialog.Close className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--line-strong)] bg-white/72 text-[var(--muted)] transition hover:bg-white">
            <X size={18} />
          </Dialog.Close>
        </div>
        <div className="mt-6">{children}</div>
      </Dialog.Content>
    </Dialog.Portal>
  )
}
