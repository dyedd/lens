"use client"

import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { ApiError, AdminProfile, apiRequest } from '@/lib/api'
import { clearStoredToken, getStoredToken } from '@/lib/auth'
import { useI18n } from '@/lib/i18n'

const SESSION_CACHE_KEY = 'lens_admin_profile_cache'
const SESSION_CACHE_TTL_MS = 60_000

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { locale } = useI18n()
  const [state, setState] = useState<{ ready: boolean; profile: AdminProfile | null }>({ ready: false, profile: null })

  useEffect(() => {
    let cancelled = false

    function readCachedProfile() {
      try {
        const raw = window.sessionStorage.getItem(SESSION_CACHE_KEY)
        if (!raw) return null
        const parsed = JSON.parse(raw) as { profile: AdminProfile; expiresAt: number }
        if (!parsed?.profile || typeof parsed.expiresAt !== 'number' || parsed.expiresAt < Date.now()) {
          window.sessionStorage.removeItem(SESSION_CACHE_KEY)
          return null
        }
        return parsed.profile
      } catch {
        window.sessionStorage.removeItem(SESSION_CACHE_KEY)
        return null
      }
    }

    function writeCachedProfile(profile: AdminProfile) {
      window.sessionStorage.setItem(SESSION_CACHE_KEY, JSON.stringify({
        profile,
        expiresAt: Date.now() + SESSION_CACHE_TTL_MS,
      }))
    }

    async function verify() {
      if (!getStoredToken()) {
        router.replace('/login')
        return
      }

      const cachedProfile = readCachedProfile()
      if (cachedProfile) {
        setState({ ready: true, profile: cachedProfile })
        return
      }

      try {
        const profile = await apiRequest<AdminProfile>('/auth/me')
        if (!cancelled) {
          writeCachedProfile(profile)
          setState({ ready: true, profile })
        }
      } catch (error) {
        if (cancelled) {
          return
        }
        if (error instanceof ApiError && error.status === 401) {
          clearStoredToken()
          window.sessionStorage.removeItem(SESSION_CACHE_KEY)
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
