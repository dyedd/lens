"use client"

import { FormEvent, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, GatewayKey, GatewayKeyPayload, apiRequest } from '@/lib/api'

type KeyFormState = {
  name: string
  enabled: boolean
}

const emptyForm: KeyFormState = {
  name: 'default-client',
  enabled: true
}

function toForm(item: GatewayKey): KeyFormState {
  return {
    name: item.name,
    enabled: item.enabled
  }
}

function toPayload(form: KeyFormState): GatewayKeyPayload {
  return {
    name: form.name.trim(),
    enabled: form.enabled
  }
}

export function KeysScreen() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<KeyFormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({ queryKey: ['gateway-keys'], queryFn: () => apiRequest<GatewayKey[]>('/gateway-keys') })

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['gateway-keys'] })
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    try {
      if (editingId) {
        await apiRequest<GatewayKey>('/gateway-keys/' + editingId, {
          method: 'PUT',
          body: JSON.stringify(toPayload(form))
        })
      } else {
        await apiRequest<GatewayKey>('/gateway-keys', {
          method: 'POST',
          body: JSON.stringify(toPayload(form))
        })
      }
      setEditingId(null)
      setForm(emptyForm)
      await refresh()
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Failed to save key')
    }
  }

  async function remove(keyId: string) {
    setBusyId(keyId)
    setError('')
    try {
      await apiRequest<void>('/gateway-keys/' + keyId, { method: 'DELETE' })
      if (editingId === keyId) {
        setEditingId(null)
        setForm(emptyForm)
      }
      await refresh()
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Failed to delete key')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">API Keys</p>
          <h2 className="mt-2 text-4xl font-semibold">Keys used by downstream clients to access the Lens gateway</h2>
        </div>
        <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm text-[var(--muted)] hover:bg-[var(--panel-strong)]" type="button" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>
      <form className="grid gap-3 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5" onSubmit={submit}>
        <div className="flex items-center justify-between gap-3">
          <strong>{editingId ? 'Edit gateway key' : 'Create gateway key'}</strong>
          {editingId ? (
            <button
              className="rounded-full border border-[var(--line)] px-4 py-2 text-sm text-[var(--muted)] hover:bg-white/70"
              type="button"
              onClick={() => {
                setEditingId(null)
                setForm(emptyForm)
                setError('')
              }}
            >
              Cancel editing
            </button>
          ) : null}
        </div>
        <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="Key name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <label className="flex items-center gap-3 rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3 text-sm text-[var(--muted)]">
          <input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />
          Enabled
        </label>
        {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
        <button className="w-fit rounded-full bg-[var(--accent)] px-5 py-3 text-white" type="submit">{editingId ? 'Save key' : 'Create key'}</button>
      </form>
      <div className="grid gap-3">
        {isLoading ? <p className="text-sm text-[var(--muted)]">Loading keys...</p> : null}
        {data?.map((item) => (
          <div key={item.id} className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <strong>{item.name}</strong>
                <p className="mt-2 text-sm text-[var(--muted)]">{item.enabled ? 'enabled' : 'disabled'}</p>
                <p className="mt-2 font-mono text-sm text-[var(--muted)] break-all">{item.secret}</p>
              </div>
              <div className="flex gap-2">
                <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm hover:bg-white/70" type="button" onClick={() => { setEditingId(item.id); setForm(toForm(item)); setError('') }}>
                  Edit
                </button>
                <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm text-[var(--danger)] hover:bg-white/70" type="button" onClick={() => void remove(item.id)} disabled={busyId === item.id}>
                  {busyId === item.id ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
