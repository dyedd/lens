"use client"

import { FormEvent, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest, GatewayKey } from '@/lib/api'

export function KeysScreen() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('default-client')
  const { data } = useQuery({ queryKey: ['gateway-keys'], queryFn: () => apiRequest<GatewayKey[]>('/gateway-keys') })

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await apiRequest('/gateway-keys', {
      method: 'POST',
      body: JSON.stringify({ name, enabled: true })
    })
    setName('default-client')
    await queryClient.invalidateQueries({ queryKey: ['gateway-keys'] })
  }

  return (
    <section className="grid gap-4">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">API Keys</p>
        <h2 className="mt-2 text-4xl font-semibold">Keys used by downstream clients to access the Lens gateway</h2>
      </div>
      <form className="grid gap-3 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5" onSubmit={submit}>
        <input className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3" placeholder="Key name" value={name} onChange={(event) => setName(event.target.value)} />
        <button className="w-fit rounded-full bg-[var(--accent)] px-5 py-3 text-white" type="submit">Create key</button>
      </form>
      <div className="grid gap-3">
        {data?.map((item) => (
          <div key={item.id} className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
            <strong>{item.name}</strong>
            <p className="mt-2 font-mono text-sm text-[var(--muted)]">{item.secret}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
