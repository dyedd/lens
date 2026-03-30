export function OverviewScreen() {
  return (
    <section className="grid gap-6">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Overview</p>
        <h2 className="mt-2 text-4xl font-semibold">Gateway status, load balance state, and operating surface</h2>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {['Requests', 'Active channels', 'Model groups'].map((title) => (
          <div key={title} className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
            <p className="text-sm text-[var(--muted)]">{title}</p>
            <strong className="mt-3 block text-4xl">-</strong>
          </div>
        ))}
      </div>
    </section>
  )
}
