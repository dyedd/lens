"use client"

import { FormEvent, useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, SettingItem, apiRequest } from '@/lib/api'

type SettingDraft = {
  key: string
  value: string
}

export function SettingsScreen() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['settings'], queryFn: () => apiRequest<SettingItem[]>('/settings') })
  const [drafts, setDrafts] = useState<SettingDraft[]>([])
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')

  useEffect(() => {
    setDrafts((data ?? []).map((item) => ({ key: item.key, value: item.value })))
  }, [data])

  function updateRow(index: number, patch: Partial<SettingDraft>) {
    setDrafts((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)))
  }

  function addRow() {
    setDrafts((current) => [...current, { key: '', value: '' }])
  }

  function removeRow(index: number) {
    setDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index))
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSaved('')

    const items = drafts
      .map((item) => ({ key: item.key.trim(), value: item.value.trim() }))
      .filter((item) => item.key)

    try {
      await apiRequest<SettingItem[]>('/settings', {
        method: 'PUT',
        body: JSON.stringify({ items })
      })
      setSaved('Settings saved')
      await queryClient.invalidateQueries({ queryKey: ['settings'] })
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Failed to save settings')
    }
  }

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Settings</p>
          <h2 className="mt-2 text-4xl font-semibold">Backend runtime knobs, admin-facing system values, and operational defaults</h2>
        </div>
        <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm text-[var(--muted)] hover:bg-[var(--panel-strong)]" type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ['settings'] })}>
          Refresh
        </button>
      </div>
      <form className="grid gap-3 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5" onSubmit={submit}>
        <div className="flex items-center justify-between gap-3">
          <strong>System settings</strong>
          <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm text-[var(--muted)] hover:bg-white/70" type="button" onClick={addRow}>
            Add row
          </button>
        </div>
        <div className="grid gap-3">
          {drafts.map((item, index) => (
            <div key={item.key + '-' + index} className="grid gap-3 rounded-2xl border border-[var(--line)] bg-white/70 p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]">
              <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="key" value={item.key} onChange={(event) => updateRow(index, { key: event.target.value })} />
              <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="value" value={item.value} onChange={(event) => updateRow(index, { value: event.target.value })} />
              <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm text-[var(--danger)] hover:bg-white/70" type="button" onClick={() => removeRow(index)}>
                Remove
              </button>
            </div>
          ))}
          {!isLoading && drafts.length === 0 ? <p className="text-sm text-[var(--muted)]">No settings yet. Add the first row.</p> : null}
        </div>
        {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
        {saved ? <p className="text-sm text-[var(--accent-2)]">{saved}</p> : null}
        <button className="w-fit rounded-full bg-[var(--accent)] px-5 py-3 text-white" type="submit">Save settings</button>
      </form>
    </section>
  )
}
