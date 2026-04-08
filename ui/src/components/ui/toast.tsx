"use client"

import { createContext, useContext, useMemo, useRef, useState } from 'react'
import { CheckCircle2, CircleAlert, X } from 'lucide-react'

type ToastKind = 'success' | 'error'

type ToastItem = {
  id: number
  kind: ToastKind
  message: string
}

type ToastContextValue = {
  success: (message: string) => void
  error: (message: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

function toastTone(kind: ToastKind) {
  if (kind === 'success') {
    return {
      icon: CheckCircle2,
      iconClassName: 'text-[var(--success)]',
      borderClassName: 'border-[rgba(34,197,94,0.18)]',
    }
  }

  return {
    icon: CircleAlert,
    iconClassName: 'text-[var(--danger)]',
    borderClassName: 'border-[rgba(217,111,93,0.18)]',
  }
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const nextIdRef = useRef(1)
  const [items, setItems] = useState<ToastItem[]>([])

  function remove(id: number) {
    setItems((current) => current.filter((item) => item.id !== id))
  }

  function push(kind: ToastKind, message: string) {
    const id = nextIdRef.current++
    setItems((current) => [...current, { id, kind, message }])
    window.setTimeout(() => remove(id), 2200)
  }

  const value = useMemo<ToastContextValue>(() => ({
    success: (message) => push('success', message),
    error: (message) => push('error', message),
  }), [])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-[80] flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2">
        {items.map((item) => {
          const tone = toastTone(item.kind)
          const Icon = tone.icon
          return (
            <div key={item.id} className={`pointer-events-auto flex items-start gap-3 rounded-2xl border bg-[var(--panel-strong)] px-4 py-3 shadow-[var(--shadow-lg)] ${tone.borderClassName}`}>
              <Icon size={18} className={`mt-0.5 shrink-0 ${tone.iconClassName}`} />
              <div className="min-w-0 flex-1 text-sm leading-6 text-[var(--text)]">{item.message}</div>
              <button
                type="button"
                className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[var(--muted)] transition-colors hover:bg-[var(--panel)] hover:text-[var(--text)]"
                onClick={() => remove(item.id)}
              >
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const value = useContext(ToastContext)
  if (!value) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return value
}
