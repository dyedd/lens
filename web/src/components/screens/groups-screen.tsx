export function GroupsScreen() {
  return (
    <section className="grid gap-4">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Groups</p>
        <h2 className="mt-2 text-4xl font-semibold">External model names mapped to internal channel pools</h2>
      </div>
      <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 text-[var(--muted)]">
        Model group UI will bind to `/api/model-groups`.
      </div>
    </section>
  )
}
