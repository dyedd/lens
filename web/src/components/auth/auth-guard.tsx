"use client"

import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { getStoredToken } from '@/lib/auth'

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!getStoredToken()) {
      router.replace('/login')
      return
    }
    setReady(true)
  }, [router])

  if (!ready) {
    return <div className="p-6 text-[var(--muted)]">Loading...</div>
  }

  return <>{children}</>
}
