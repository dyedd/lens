"use client"

import { FormEvent, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, Provider, ProtocolKind, ProviderPayload, apiRequest } from '@/lib/api'

type ChannelFormState = {
  name: string
  protocol: ProtocolKind
  base_url: string
  api_key: string
  model_name: string
  status: 'enabled' | 'disabled'
  weight: number
  priority: number
  model_patterns: string
}

const emptyForm: ChannelFormState = {
  name: '',
  protocol: 'openai_chat',
  base_url: '',
  api_key: '',
  model_name: '',
  status: 'enabled',
  weight: 1,
  priority: 100,
  model_patterns: ''
}

function toForm(provider: Provider): ChannelFormState {
  return {
    name: provider.name,
    protocol: provider.protocol,
    base_url: provider.base_url,
    api_key: provider.api_key,
    model_name: provider.model_name ?? '',
    status: provider.status,
    weight: provider.weight,
    priority: provider.priority,
    model_patterns: provider.model_patterns.join('\n')
  }
}

function toPayload(form: ChannelFormState): ProviderPayload {
  return {
    name: form.name.trim(),
    protocol: form.protocol,
    base_url: form.base_url.trim(),
    api_key: form.api_key.trim(),
    model_name: form.model_name.trim() || null,
    status: form.status,
    weight: Number(form.weight),
    priority: Number(form.priority),
    headers: {},
    model_patterns: form.model_patterns.split('\n').map((item) => item.trim()).filter(Boolean)
  }
}

export function ChannelsScreen() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<ChannelFormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({ queryKey: ['providers'], queryFn: () => apiRequest<Provider[]>('/providers') })

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['providers'] })
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    try {
      if (editingId) {
        await apiRequest<Provider>('/providers/' + editingId, {
          method: 'PUT',
          body: JSON.stringify(toPayload(form))
        })
      } else {
        await apiRequest<Provider>('/providers', {
          method: 'POST',
          body: JSON.stringify(toPayload(form))
        })
      }
      setForm(emptyForm)
      setEditingId(null)
      await refresh()
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Failed to save channel')
    }
  }

  async function remove(providerId: string) {
    setBusyId(providerId)
    setError('')
    try {
      await apiRequest<void>('/providers/' + providerId, { method: 'DELETE' })
      if (editingId === providerId) {
        setEditingId(null)
        setForm(emptyForm)
      }
      await refresh()
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Failed to delete channel')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Channels</p>
          <h2 className="mt-2 text-4xl font-semibold">Provider channels, upstream keys, model patterns, and health state</h2>
        </div>
        <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm text-[var(--muted)] hover:bg-[var(--panel-strong)]" type="button" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>
      <form className="grid gap-3 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5" onSubmit={submit}>
        <div className="flex items-center justify-between gap-3">
          <strong>{editingId ? 'Edit channel' : 'Create channel'}</strong>
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
        <div className="grid gap-3 md:grid-cols-2">
          <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="Name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          <select className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" value={form.protocol} onChange={(event) => setForm({ ...form, protocol: event.target.value as ProtocolKind })}>
            <option value="openai_chat">OpenAI Chat</option>
            <option value="openai_responses">OpenAI Responses</option>
            <option value="anthropic">Anthropic</option>
            <option value="gemini">Gemini</option>
          </select>
          <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="Base URL" value={form.base_url} onChange={(event) => setForm({ ...form, base_url: event.target.value })} />
          <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="API key" value={form.api_key} onChange={(event) => setForm({ ...form, api_key: event.target.value })} />
          <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="Model override" value={form.model_name} onChange={(event) => setForm({ ...form, model_name: event.target.value })} />
          <select className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as 'enabled' | 'disabled' })}>
            <option value="enabled">Enabled</option>
            <option value="disabled">Disabled</option>
          </select>
          <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="Weight" type="number" min={1} value={form.weight} onChange={(event) => setForm({ ...form, weight: Number(event.target.value) || 1 })} />
          <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="Priority" type="number" min={1} value={form.priority} onChange={(event) => setForm({ ...form, priority: Number(event.target.value) || 1 })} />
          <textarea className="min-h-32 rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3 md:col-span-2" placeholder="Model regex patterns, one per line" value={form.model_patterns} onChange={(event) => setForm({ ...form, model_patterns: event.target.value })} />
        </div>
        {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
        <button className="w-fit rounded-full bg-[var(--accent)] px-5 py-3 text-white" type="submit">{editingId ? 'Save channel' : 'Create channel'}</button>
      </form>
      <div className="grid gap-3">
        {isLoading ? <p className="text-sm text-[var(--muted)]">Loading channels...</p> : null}
        {data?.map((provider) => (
          <div key={provider.id} className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <strong>{provider.name}</strong>
                <p className="mt-2 text-sm text-[var(--muted)]">{provider.protocol} · {provider.base_url}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">{provider.model_patterns.join(' | ') || provider.model_name || 'no model selector'}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">{provider.status} · weight {provider.weight} · priority {provider.priority}</p>
              </div>
              <div className="flex gap-2">
                <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm hover:bg-white/70" type="button" onClick={() => { setEditingId(provider.id); setForm(toForm(provider)); setError('') }}>
                  Edit
                </button>
                <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm text-[var(--danger)] hover:bg-white/70" type="button" onClick={() => void remove(provider.id)} disabled={busyId === provider.id}>
                  {busyId === provider.id ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
