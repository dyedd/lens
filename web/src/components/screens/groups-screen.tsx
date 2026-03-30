"use client"

import { FormEvent, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest, ModelGroup, ProtocolKind, Provider } from '@/lib/api'

export function GroupsScreen() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ name: '', protocol: 'openai_chat' as ProtocolKind, strategy: 'round_robin', provider_ids: '' })
  const { data } = useQuery({ queryKey: ['groups'], queryFn: () => apiRequest<ModelGroup[]>('/model-groups') })
  const { data: providers } = useQuery({ queryKey: ['providers'], queryFn: () => apiRequest<Provider[]>('/providers') })

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await apiRequest('/model-groups', {
      method: 'POST',
      body: JSON.stringify({
        ...form,
        provider_ids: form.provider_ids.split(',').map((item) => item.trim()).filter(Boolean),
        enabled: true
      })
    })
    setForm({ name: '', protocol: 'openai_chat', strategy: 'round_robin', provider_ids: '' })
    await queryClient.invalidateQueries({ queryKey: ['groups'] })
  }

  return (
    <section className="grid gap-4">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Groups</p>
        <h2 className="mt-2 text-4xl font-semibold">External model names mapped to internal channel pools</h2>
      </div>
      <form className="grid gap-3 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5" onSubmit={submit}>
        <div className="grid gap-3 md:grid-cols-2">
          <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="External model name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          <select className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" value={form.protocol} onChange={(event) => setForm({ ...form, protocol: event.target.value as ProtocolKind })}>
            <option value="openai_chat">OpenAI Chat</option>
            <option value="openai_responses">OpenAI Responses</option>
            <option value="anthropic">Anthropic</option>
            <option value="gemini">Gemini</option>
          </select>
          <select className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" value={form.strategy} onChange={(event) => setForm({ ...form, strategy: event.target.value })}>
            <option value="round_robin">Round Robin</option>
            <option value="weighted">Weighted</option>
            <option value="failover">Failover</option>
          </select>
          <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="provider-1, provider-2" value={form.provider_ids} onChange={(event) => setForm({ ...form, provider_ids: event.target.value })} />
        </div>
        <button className="w-fit rounded-full bg-[var(--accent)] px-5 py-3 text-white" type="submit">Create group</button>
      </form>
      <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
        <p className="text-sm text-[var(--muted)]">Available providers</p>
        <p className="mt-2 text-sm text-[var(--muted)]">{providers?.map((item) => item.id).join(', ') || 'none'}</p>
      </div>
      <div className="grid gap-3">
        {data?.map((group) => (
          <div key={group.id} className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
            <strong>{group.name}</strong>
            <p className="mt-2 text-sm text-[var(--muted)]">{group.protocol} · {group.strategy}</p>
            <p className="mt-1 text-sm text-[var(--muted)]">{group.provider_ids.join(' -> ') || 'no providers'}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
