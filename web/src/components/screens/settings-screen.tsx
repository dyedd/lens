"use client"

import { FormEvent, useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest, SettingItem } from '@/lib/api'

export function SettingsScreen() {
  const queryClient = useQueryClient()
  const { data } = useQuery({ queryKey: ['settings'], queryFn: () => apiRequest<SettingItem[]>('/settings') })
  const [draft, setDraft] = useState('')

  useEffect(() => {
    setDraft((data ?? []).map((item) => `${item.key}=${item.value}`).join('\n'))
  }, [data])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const items = draft
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [key, ...rest] = line.split('=')
        return { key: key.trim(), value: rest.join('=').trim() }
      })

    await apiRequest('/settings', {
      method: 'PUT',
      body: JSON.stringify({ items })
    })
    await queryClient.invalidateQueries({ queryKey: ['settings'] })
  }

  return (
    <section className="grid gap-4">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Settings</p>
        <h2 className="mt-2 text-4xl font-semibold">Backend runtime knobs, admin-facing system values, and operational defaults</h2>
      </div>
      <form className="grid gap-3 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5" onSubmit={submit}>
        <textarea className="min-h-64 rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" value={draft} onChange={(event) => setDraft(event.target.value)} />
        <button className="w-fit rounded-full bg-[var(--accent)] px-5 py-3 text-white" type="submit">Save settings</button>
      </form>
    </section>
  )
}
