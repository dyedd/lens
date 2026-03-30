export function SettingsScreen() {
  return (
    <section className="grid gap-4">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Settings</p>
        <h2 className="mt-2 text-4xl font-semibold">Backend runtime knobs, admin-facing system values, and operational defaults</h2>
      </div>
      <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 text-[var(--muted)]">
        Settings UI will bind to `/api/settings`.
      </div>
    </section>
  )
}
