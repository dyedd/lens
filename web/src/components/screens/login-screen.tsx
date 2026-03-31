"use client"

import { Globe2, LockKeyhole, User } from 'lucide-react'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { FormEvent, useState } from 'react'
import { ApiError, apiRequest } from '@/lib/api'
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
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

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

        <header className="flex flex-col items-center gap-3 text-center">
          <Image src="/logo.svg" alt="Lens" width={52} height={52} className="h-13 w-13" />
          <div className="space-y-1">
            <h1 className="text-[28px] font-bold tracking-tight text-[var(--text)]">Lens</h1>
            <p className="text-sm text-[var(--muted)]">{t.loginSubtitle}</p>
          </div>
        </header>

        <form onSubmit={submit} className="space-y-5 rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-6 shadow-[var(--shadow-sm)]">
          <div className="space-y-1">
            <h2 className="text-base font-semibold text-[var(--text)]">{t.signIn}</h2>
            <p className="text-sm text-[var(--muted)]">{t.loginTitle}</p>
          </div>

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

          <div className="rounded-2xl bg-[var(--panel)] px-4 py-3 text-xs leading-6 text-[var(--muted)]">
            <div>OpenAI Chat / OpenAI Responses / Anthropic / Gemini</div>
            <div>{locale === 'zh-CN' ? '默认账号：admin / admin' : 'Default account: admin / admin'}</div>
          </div>
        </form>
      </div>
    </div>
  )
}
