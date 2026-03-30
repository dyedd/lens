"use client"

import { Globe2, ShieldCheck } from 'lucide-react'
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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(47,111,237,0.18),transparent_22%),radial-gradient(circle_at_80%_10%,rgba(19,162,168,0.14),transparent_22%)]" />
      <div className="relative grid w-full max-w-6xl gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="rounded-[36px] border border-[var(--line)] bg-[linear-gradient(180deg,rgba(20,47,89,0.92),rgba(11,26,52,0.96))] p-8 text-white shadow-[var(--shadow-lg)] md:p-10">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-white/60">Lens Gateway</p>
              <h1 className="mt-4 max-w-xl text-4xl font-semibold leading-tight md:text-5xl">
                {locale === 'zh-CN' ? '统一管理渠道、模型组与网关调用。' : 'Run your provider channels and model groups from one control plane.'}
              </h1>
            </div>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-4 py-2 text-sm text-white/80 transition hover:bg-white/16"
              onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
            >
              <Globe2 size={16} />
              <span>{locale === 'zh-CN' ? 'English' : '中文'}</span>
            </button>
          </div>
          <p className="mt-6 max-w-xl text-base leading-7 text-white/70">
            {locale === 'zh-CN'
              ? '默认中文，支持中英切换。后台聚合 OpenAI Chat、OpenAI Responses、Anthropic、Gemini 四类原生协议，并提供渠道管理、模型组路由、请求观测与密钥控制。'
              : 'Chinese by default with English switch. Manage OpenAI Chat, OpenAI Responses, Anthropic, and Gemini native channels with routing, keys, and request observability.'}
          </p>
          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {[
              locale === 'zh-CN' ? ['渠道池', '25 条已导入'] : ['Channels', '25 imported'],
              locale === 'zh-CN' ? ['模型组', '8 组已导入'] : ['Groups', '8 imported'],
              locale === 'zh-CN' ? ['协议族', '4 类原生协议'] : ['Protocols', '4 native families']
            ].map(([label, value]) => (
              <div key={label} className="rounded-3xl border border-white/10 bg-white/8 p-5 backdrop-blur">
                <p className="text-sm text-white/55">{label}</p>
                <strong className="mt-3 block text-2xl text-white">{value}</strong>
              </div>
            ))}
          </div>
        </section>
        <section className="rounded-[36px] border border-[var(--line)] bg-[var(--panel)] p-8 shadow-[var(--shadow-lg)] backdrop-blur md:p-10">
          <div className="inline-flex items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--panel-soft)] px-4 py-2 text-sm text-[var(--accent)]">
            <ShieldCheck size={16} />
            <span>{t.loginSubtitle}</span>
          </div>
          <h2 className="mt-6 text-3xl font-semibold leading-tight">{t.loginTitle}</h2>
          <form className="mt-10 grid gap-4" onSubmit={submit}>
            <label className="grid gap-2">
              <span className="text-sm text-[var(--muted)]">{t.username}</span>
              <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3 shadow-[var(--shadow-sm)] outline-none transition focus:border-[var(--accent)]" value={username} onChange={(event) => setUsername(event.target.value)} placeholder={t.username} />
            </label>
            <label className="grid gap-2">
              <span className="text-sm text-[var(--muted)]">{t.password}</span>
              <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3 shadow-[var(--shadow-sm)] outline-none transition focus:border-[var(--accent)]" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={t.password} />
            </label>
            <button className="mt-2 rounded-2xl bg-[linear-gradient(135deg,#2f6fed,#1958d7)] px-5 py-3 text-white shadow-[0_16px_30px_rgba(47,111,237,0.28)] transition hover:translate-y-[-1px] disabled:opacity-60" type="submit" disabled={submitting}>
              {submitting ? t.signingIn : t.signIn}
            </button>
            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
          </form>
        </section>
      </div>
    </div>
  )
}
