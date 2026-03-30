export function ChannelsScreen() {
  return (
    <section className="grid gap-4">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Channels</p>
        <h2 className="mt-2 text-4xl font-semibold">Provider channels, upstream keys, model patterns, and health state</h2>
      </div>
      <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 text-[var(--muted)]">
        Channel management UI will bind to `/api/providers`.
      </div>
    </section>
  )
}
