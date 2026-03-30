import { FormEvent, useEffect, useState } from 'react'

type ProtocolKind = 'openai_chat' | 'openai_responses' | 'anthropic' | 'gemini'
type ProviderStatus = 'enabled' | 'disabled'

type Provider = {
  id: string
  name: string
  protocol: ProtocolKind
  base_url: string
  api_key: string
  model_name?: string | null
  status: ProviderStatus
  weight: number
  priority: number
  headers: Record<string, string>
  model_patterns: string[]
}

type RouteState = {
  protocol: ProtocolKind
  next_index: number
  provider_ids: string[]
  requested_model?: string | null
}

type HealthState = {
  provider_id: string
  consecutive_failures: number
  last_error?: string | null
}

type RouterSnapshot = {
  routes: RouteState[]
  health: HealthState[]
}

type RoutePreview = {
  protocol: ProtocolKind
  requested_model?: string | null
  matched_provider_ids: string[]
}

const emptyForm = {
  name: '',
  protocol: 'openai_chat' as ProtocolKind,
  base_url: '',
  api_key: '',
  model_name: '',
  model_patterns: '',
  status: 'enabled' as ProviderStatus,
  weight: 1,
  priority: 100
}

const protocolLabels: Record<ProtocolKind, string> = {
  openai_chat: 'OpenAI Chat',
  openai_responses: 'OpenAI Responses',
  anthropic: 'Anthropic',
  gemini: 'Gemini'
}

export function App() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [router, setRouter] = useState<RouterSnapshot>({ routes: [], health: [] })
  const [preview, setPreview] = useState<RoutePreview | null>(null)
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState<string>('')
  const [previewModel, setPreviewModel] = useState<string>('claude-opus-4-6')
  const [previewProtocol, setPreviewProtocol] = useState<ProtocolKind>('anthropic')

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => {
      void loadRouter()
    }, 3000)
    return () => window.clearInterval(timer)
  }, [])

  async function refresh() {
    await Promise.all([loadProviders(), loadRouter()])
    await loadPreview(previewProtocol, previewModel)
  }

  async function loadProviders() {
    const response = await fetch('/api/providers')
    const data = (await response.json()) as Provider[]
    setProviders(data)
  }

  async function loadRouter() {
    const response = await fetch('/api/router')
    const data = (await response.json()) as RouterSnapshot
    setRouter(data)
  }

  async function loadPreview(protocol: ProtocolKind, model: string) {
    const response = await fetch('/api/router/preview', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ protocol, model })
    })
    const data = (await response.json()) as RoutePreview
    setPreview(data)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    const response = await fetch('/api/providers', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        ...form,
        model_name: form.model_name || null,
        headers: {},
        model_patterns: form.model_patterns
          .split('\n')
          .map((item) => item.trim())
          .filter(Boolean)
      })
    })

    if (!response.ok) {
      setError(await response.text())
      return
    }

    setForm(emptyForm)
    await refresh()
  }

  async function removeProvider(providerId: string) {
    await fetch(`/api/providers/${providerId}`, { method: 'DELETE' })
    await refresh()
  }

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">Lens Gateway</p>
        <h1>One Python gateway for four native LLM protocols.</h1>
        <p className="lede">
          Keep OpenAI Chat, OpenAI Responses, Anthropic, and Gemini as-is. Route requests with weighted round robin,
          transparent streaming, and failover.
        </p>
      </section>

      <section className="grid">
        <article className="panel form-panel">
          <div className="panel-head">
            <h2>Add upstream</h2>
            <span>Persisted to <code>data/lens.db</code></span>
          </div>
          <form onSubmit={submit} className="provider-form">
            <label>
              <span>Name</span>
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
            </label>
            <label>
              <span>Protocol</span>
              <select value={form.protocol} onChange={(event) => setForm({ ...form, protocol: event.target.value as ProtocolKind })}>
                {Object.entries(protocolLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Base URL</span>
              <input value={form.base_url} onChange={(event) => setForm({ ...form, base_url: event.target.value })} required />
            </label>
            <label>
              <span>API key</span>
              <input value={form.api_key} onChange={(event) => setForm({ ...form, api_key: event.target.value })} required />
            </label>
            <label>
              <span>Model override</span>
              <input value={form.model_name} onChange={(event) => setForm({ ...form, model_name: event.target.value })} />
            </label>
            <label>
              <span>Model regex patterns, one per line</span>
              <textarea value={form.model_patterns} onChange={(event) => setForm({ ...form, model_patterns: event.target.value })} rows={4} />
            </label>
            <div className="row">
              <label>
                <span>Weight</span>
                <input type="number" min={1} value={form.weight} onChange={(event) => setForm({ ...form, weight: Number(event.target.value) })} required />
              </label>
              <label>
                <span>Priority</span>
                <input type="number" min={1} value={form.priority} onChange={(event) => setForm({ ...form, priority: Number(event.target.value) })} required />
              </label>
            </div>
            <button type="submit">Create provider</button>
            {error ? <pre className="error-box">{error}</pre> : null}
          </form>
        </article>

        <article className="panel">
          <div className="panel-head">
            <h2>Routing state</h2>
            <span>refreshes every 3s</span>
          </div>
          <div className="route-list">
            {router.routes.map((route) => (
              <div key={route.protocol} className="route-card">
                <strong>{protocolLabels[route.protocol]}</strong>
                <span>next index: {route.next_index}</span>
                <code>{route.provider_ids.join(' -> ') || 'no providers'}</code>
              </div>
            ))}
          </div>
          <div className="preview-box">
            <div className="row preview-row">
              <label>
                <span>Preview protocol</span>
                <select value={previewProtocol} onChange={(event) => setPreviewProtocol(event.target.value as ProtocolKind)}>
                  {Object.entries(protocolLabels).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Preview model</span>
                <input value={previewModel} onChange={(event) => setPreviewModel(event.target.value)} />
              </label>
            </div>
            <button type="button" onClick={() => void loadPreview(previewProtocol, previewModel)}>Preview route</button>
            <code>{preview?.matched_provider_ids.join(' -> ') || 'no providers matched'}</code>
          </div>
        </article>
      </section>

      <section className="panel table-panel">
        <div className="panel-head">
          <h2>Providers</h2>
          <span>{providers.length} configured</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Protocol</th>
                <th>Model</th>
                <th>Base URL</th>
                <th>Failures</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {providers.map((provider) => {
                const health = router.health.find((item) => item.provider_id === provider.id)
                return (
                  <tr key={provider.id}>
                    <td>
                      <strong>{provider.name}</strong>
                      <small>{provider.id}</small>
                    </td>
                    <td>{protocolLabels[provider.protocol]}</td>
                    <td>
                      <strong>{provider.model_name || '-'}</strong>
                      <small>{provider.model_patterns.join(' | ') || 'exact model only'}</small>
                    </td>
                    <td className="mono">{provider.base_url}</td>
                    <td>
                      <strong>{health?.consecutive_failures ?? 0}</strong>
                      <small>{health?.last_error || 'healthy'}</small>
                    </td>
                    <td>
                      <button className="danger" onClick={() => void removeProvider(provider.id)}>Delete</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}
