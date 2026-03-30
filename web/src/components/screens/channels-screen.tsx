"use client"

import { FormEvent, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest, Provider, ProtocolKind } from '@/lib/api'

export function ChannelsScreen() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({
    name: '',
    protocol: 'openai_chat' as ProtocolKind,
    base_url: '',
    api_key: '',
    model_name: '',
    weight: 1,
    priority: 100,
    model_patterns: ''
  })
  const { data } = useQuery({ queryKey: ['providers'], queryFn: () => apiRequest<Provider[]>('/providers') })

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await apiRequest('/providers', {
      method: 'POST',
      body: JSON.stringify({
        ...form,
        model_name: form.model_name || null,
        status: 'enabled',
        headers: {},
        model_patterns: form.model_patterns.split('\n').map((item) => item.trim()).filter(Boolean)
      })
    })
    setForm({ name: '', protocol: 'openai_chat', base_url: '', api_key: '', model_name: '', weight: 1, priority: 100, model_patterns: '' })
    await queryClient.invalidateQueries({ queryKey: ['providers'] })
  }

  return (
    <section className="grid gap-4">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Channels</p>
        <h2 className="mt-2 text-4xl font-semibold">Provider channels, upstream keys, model patterns, and health state</h2>
      </div>
      <form className="grid gap-3 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5" onSubmit={submit}>
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
          <textarea className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="Model regex patterns, one per line" value={form.model_patterns} onChange={(event) => setForm({ ...form, model_patterns: event.target.value })} />
        </div>
        <button className="w-fit rounded-full bg-[var(--accent)] px-5 py-3 text-white" type="submit">Create channel</button>
      </form>
      <div className="grid gap-3">
        {data?.map((provider) => (
          <div key={provider.id} className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
            <strong>{provider.name}</strong>
            <p className="mt-2 text-sm text-[var(--muted)]">{provider.protocol} · {provider.base_url}</p>
            <p className="mt-1 text-sm text-[var(--muted)]">{provider.model_patterns.join(' | ') || provider.model_name || 'no model selector'}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
