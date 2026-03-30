"use client"

import { useRouter } from 'next/navigation'
import { FormEvent, useState } from 'react'
import { ApiError, apiRequest } from '@/lib/api'
import { setStoredToken } from '@/lib/auth'

type LoginResponse = {
  access_token: string
  token_type: string
  expires_in: number
}

export function LoginScreen() {
  const router = useRouter()
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
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md rounded-[32px] border border-[var(--line)] bg-[var(--panel)] p-8 shadow-[0_24px_80px_rgba(0,0,0,0.08)] backdrop-blur">
        <p className="text-xs uppercase tracking-[0.24em] text-[var(--accent-2)]">Lens Gateway</p>
        <h1 className="mt-4 text-4xl font-semibold leading-tight">Admin login for channels, groups, keys, and gateway settings</h1>
        <form className="mt-8 grid gap-4" onSubmit={submit}>
          <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Username" />
          <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" />
          <button className="rounded-full bg-[var(--accent)] px-5 py-3 text-white disabled:opacity-60" type="submit" disabled={submitting}>
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
          {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
        </form>
      </div>
    </div>
  )
}
