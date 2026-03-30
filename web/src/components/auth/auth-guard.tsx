"use client"

import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { ApiError, AdminProfile, apiRequest } from '@/lib/api'
import { clearStoredToken, getStoredToken } from '@/lib/auth'
import { useI18n } from '@/lib/i18n'

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { locale } = useI18n()
  const [state, setState] = useState<{ ready: boolean; profile: AdminProfile | null }>({ ready: false, profile: null })

  useEffect(() => {
    let cancelled = false

    async function verify() {
      if (!getStoredToken()) {
        router.replace('/login')
        return
      }

      try {
        const profile = await apiRequest<AdminProfile>('/auth/me')
        if (!cancelled) {
          setState({ ready: true, profile })
        }
      } catch (error) {
        if (cancelled) {
          return
        }
        if (error instanceof ApiError && error.status === 401) {
          clearStoredToken()
        }
        router.replace('/login')
      }
    }

    void verify()

    return () => {
      cancelled = true
    }
  }, [router])

  if (!state.ready) {
    return <div className="p-6 text-[var(--muted)]">{locale === 'zh-CN' ? '正在校验后台登录状态...' : 'Checking admin session...'}</div>
  }

  return <>{children}</>
}
