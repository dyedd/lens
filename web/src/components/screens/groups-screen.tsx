"use client"

import { FormEvent, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, ModelGroup, ModelGroupPayload, ProtocolKind, Provider, RoutingStrategy, apiRequest } from '@/lib/api'

type GroupFormState = {
  name: string
  protocol: ProtocolKind
  strategy: RoutingStrategy
  provider_ids: string[]
  enabled: boolean
}

const emptyForm: GroupFormState = {
  name: '',
  protocol: 'openai_chat',
  strategy: 'round_robin',
  provider_ids: [],
  enabled: true
}

function toForm(group: ModelGroup): GroupFormState {
  return {
    name: group.name,
    protocol: group.protocol,
    strategy: group.strategy,
    provider_ids: group.provider_ids,
    enabled: group.enabled
  }
}

function toPayload(form: GroupFormState): ModelGroupPayload {
  return {
    name: form.name.trim(),
    protocol: form.protocol,
    strategy: form.strategy,
    provider_ids: form.provider_ids,
    enabled: form.enabled
  }
}

export function GroupsScreen() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<GroupFormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const { data: groups, isLoading } = useQuery({ queryKey: ['groups'], queryFn: () => apiRequest<ModelGroup[]>('/model-groups') })
  const { data: providers } = useQuery({ queryKey: ['providers'], queryFn: () => apiRequest<Provider[]>('/providers') })

  const filteredProviders = useMemo(
    () => (providers ?? []).filter((provider) => provider.protocol === form.protocol),
    [form.protocol, providers]
  )

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['groups'] }),
      queryClient.invalidateQueries({ queryKey: ['providers'] })
    ])
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    try {
      if (editingId) {
        await apiRequest<ModelGroup>('/model-groups/' + editingId, {
          method: 'PUT',
          body: JSON.stringify(toPayload(form))
        })
      } else {
        await apiRequest<ModelGroup>('/model-groups', {
          method: 'POST',
          body: JSON.stringify(toPayload(form))
        })
      }
      setEditingId(null)
      setForm(emptyForm)
      await refresh()
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Failed to save group')
    }
  }

  async function remove(groupId: string) {
    setBusyId(groupId)
    setError('')
    try {
      await apiRequest<void>('/model-groups/' + groupId, { method: 'DELETE' })
      if (editingId === groupId) {
        setEditingId(null)
        setForm(emptyForm)
      }
      await refresh()
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Failed to delete group')
    } finally {
      setBusyId(null)
    }
  }

  function toggleProvider(providerId: string) {
    setForm((current) => {
      const exists = current.provider_ids.includes(providerId)
      return {
        ...current,
        provider_ids: exists ? current.provider_ids.filter((id) => id !== providerId) : [...current.provider_ids, providerId]
      }
    })
  }

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Groups</p>
          <h2 className="mt-2 text-4xl font-semibold">External model names mapped to internal channel pools</h2>
        </div>
        <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm text-[var(--muted)] hover:bg-[var(--panel-strong)]" type="button" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>
      <form className="grid gap-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5" onSubmit={submit}>
        <div className="flex items-center justify-between gap-3">
          <strong>{editingId ? 'Edit model group' : 'Create model group'}</strong>
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
          <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="External model name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          <select className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" value={form.protocol} onChange={(event) => setForm({ ...form, protocol: event.target.value as ProtocolKind, provider_ids: [] })}>
            <option value="openai_chat">OpenAI Chat</option>
            <option value="openai_responses">OpenAI Responses</option>
            <option value="anthropic">Anthropic</option>
            <option value="gemini">Gemini</option>
          </select>
          <select className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" value={form.strategy} onChange={(event) => setForm({ ...form, strategy: event.target.value as RoutingStrategy })}>
            <option value="round_robin">Round Robin</option>
            <option value="weighted">Weighted</option>
            <option value="failover">Failover</option>
          </select>
          <label className="flex items-center gap-3 rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3 text-sm text-[var(--muted)]">
            <input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />
            Enabled
          </label>
        </div>
        <div className="grid gap-3 rounded-2xl border border-[var(--line)] bg-white/60 p-4">
          <p className="text-sm text-[var(--muted)]">Selectable providers for {form.protocol}</p>
          <div className="grid gap-2 md:grid-cols-2">
            {filteredProviders.map((provider) => (
              <label key={provider.id} className="flex items-center gap-3 rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3 text-sm">
                <input type="checkbox" checked={form.provider_ids.includes(provider.id)} onChange={() => toggleProvider(provider.id)} />
                <span>{provider.id} · {provider.name}</span>
              </label>
            ))}
            {filteredProviders.length === 0 ? <p className="text-sm text-[var(--muted)]">No providers for this protocol.</p> : null}
          </div>
        </div>
        {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
        <button className="w-fit rounded-full bg-[var(--accent)] px-5 py-3 text-white" type="submit">{editingId ? 'Save group' : 'Create group'}</button>
      </form>
      <div className="grid gap-3">
        {isLoading ? <p className="text-sm text-[var(--muted)]">Loading groups...</p> : null}
        {groups?.map((group) => (
          <div key={group.id} className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <strong>{group.name}</strong>
                <p className="mt-2 text-sm text-[var(--muted)]">{group.protocol} · {group.strategy} · {group.enabled ? 'enabled' : 'disabled'}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">{group.provider_ids.join(' -> ') || 'no providers'}</p>
              </div>
              <div className="flex gap-2">
                <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm hover:bg-white/70" type="button" onClick={() => { setEditingId(group.id); setForm(toForm(group)); setError('') }}>
                  Edit
                </button>
                <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm text-[var(--danger)] hover:bg-white/70" type="button" onClick={() => void remove(group.id)} disabled={busyId === group.id}>
                  {busyId === group.id ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
