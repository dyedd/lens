export function KeysScreen() {
  return (
    <section className="grid gap-4">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">API Keys</p>
        <h2 className="mt-2 text-4xl font-semibold">Keys used by downstream clients to access the Lens gateway</h2>
      </div>
      <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 text-[var(--muted)]">
        Gateway key UI will bind to `/api/gateway-keys`.
      </div>
    </section>
  )
}
