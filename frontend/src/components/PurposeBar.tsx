/** The persistent reminder of what this assistant was told to do — the one
 *  place the connection's purpose surfaces once you're past setup.
 *
 *  The purpose is passed in rather than fetched: it belongs to the connection,
 *  and a fetch on mount showed the previous database's purpose after a switch. */
export function PurposeBar({ purpose }: { purpose: string }) {
  if (!purpose) return null

  return (
    <div className="border-b border-rule bg-sunken px-4 py-2.5 md:px-8">
      <p className="mx-auto flex max-w-3xl items-baseline gap-2 truncate">
        <span className="t-label shrink-0 text-accent">Acting as</span>
        <span className="t-secondary truncate text-ink-soft">{purpose}</span>
      </p>
    </div>
  )
}
