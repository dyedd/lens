"use client"

import { Globe2, LockKeyhole, User } from 'lucide-react'
import Image from 'next/image'
import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { FormEvent, useState } from 'react'
import { ApiError, apiRequest, type PublicBranding } from '@/lib/api'
import { setStoredToken } from '@/lib/auth'
import { useI18n } from '@/lib/i18n'

type LoginResponse = {
  access_token: string
  token_type: string
  expires_in: number
}

function inputClassName() {
  return 'h-11 w-full rounded-2xl border border-[var(--line)] bg-[var(--panel-strong)] px-4 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

export function LoginScreen() {
  const router = useRouter()
  const { locale, setLocale, t } = useI18n()
  const { data: branding } = useQuery({ queryKey: ['public-branding'], queryFn: () => apiRequest<PublicBranding>('/public/branding') })
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const siteName = branding?.site_name?.trim() || 'Lens'
  const logoUrl = branding?.logo_url?.trim() || '/logo.svg'

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError('')

    try {
      const data = await apiRequest<LoginResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      })
      setStoredToken(data.access_token)
      router.push('/dashboard')
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-6 py-10">
      <div className="w-full max-w-sm space-y-7">
        <div className="flex justify-end">
          <button
            type="button"
            className="inline-flex h-9 items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 text-sm text-[var(--muted)] transition-colors hover:text-[var(--text)]"
            onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
          >
            <Globe2 size={15} />
            <span>{locale === 'zh-CN' ? 'English' : '中文'}</span>
          </button>
        </div>

        <header className="flex flex-col items-center gap-2 text-center">
          <Image src={logoUrl} alt={siteName} width={108} height={108} className="h-24 w-24 rounded-[28px] object-cover" unoptimized={logoUrl !== '/logo.svg'} />
          <h1 className="text-lg font-semibold text-[var(--text)]">{siteName}</h1>
        </header>

        <form onSubmit={submit} className="space-y-5 rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-6 shadow-[var(--shadow-sm)]">
          <h2 className="text-base font-semibold text-[var(--text)]">{t.signIn}</h2>

          <label className="grid gap-2">
            <span className="text-xs font-medium text-[var(--muted)]">{t.username}</span>
            <div className="relative">
              <User className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
              <input
                className={inputClassName() + ' pl-10'}
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder={t.username}
                autoComplete="username"
              />
            </div>
          </label>

          <label className="grid gap-2">
            <span className="text-xs font-medium text-[var(--muted)]">{t.password}</span>
            <div className="relative">
              <LockKeyhole className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
              <input
                className={inputClassName() + ' pl-10'}
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={t.password}
                autoComplete="current-password"
              />
            </div>
          </label>

          {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}

          <button
            className="inline-flex h-11 w-full items-center justify-center rounded-2xl bg-[var(--accent)] px-4 text-sm font-medium text-white transition-colors hover:opacity-92 disabled:opacity-60"
            type="submit"
            disabled={submitting}
          >
            {submitting ? t.signingIn : t.signIn}
          </button>
        </form>
      </div>
    </div>
  )
}
