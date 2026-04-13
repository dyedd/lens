"use client"

import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { CheckCircle2, CircleAlert, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type ToastTone = 'success' | 'error'

type ToastItem = {
  id: string
  tone: ToastTone
  message: string
}

type ToastContextValue = {
  success: (message: string) => void
  error: (message: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

function ToastViewport({
  items,
  onDismiss,
}: {
  items: ToastItem[]
  onDismiss: (id: string) => void
}) {
  return (
    <div className="pointer-events-none fixed right-4 top-4 z-[80] flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2">
      {items.map((item) => {
        const danger = item.tone === 'error'
        return (
          <div
            key={item.id}
            className={cn(
              'pointer-events-auto flex items-start gap-3 rounded-lg border bg-white px-4 py-3 shadow-sm',
              danger ? 'border-red-200' : 'border-border'
            )}
          >
            <span className={cn('mt-0.5', danger ? 'text-red-500' : 'text-emerald-500')}>
              {danger ? <CircleAlert size={16} /> : <CheckCircle2 size={16} />}
            </span>
            <div className="min-w-0 flex-1 text-sm text-slate-800">{item.message}</div>
            <button type="button" className="text-slate-400 transition hover:text-slate-700" onClick={() => onDismiss(item.id)}>
              <X size={14} />
            </button>
          </div>
        )
      })}
    </div>
  )
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const timers = useRef<Record<string, number>>({})

  const dismiss = useCallback((id: string) => {
    window.clearTimeout(timers.current[id])
    delete timers.current[id]
    setItems((current) => current.filter((item) => item.id !== id))
  }, [])

  const push = useCallback((tone: ToastTone, message: string) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    setItems((current) => [...current, { id, tone, message }])
    timers.current[id] = window.setTimeout(() => dismiss(id), 2200)
  }, [dismiss])

  const value = useMemo<ToastContextValue>(() => ({
    success: (message) => push('success', message),
    error: (message) => push('error', message),
  }), [push])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport items={items} onDismiss={dismiss} />
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
