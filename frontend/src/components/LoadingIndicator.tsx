export function LoadingIndicator() {
  return (
    <div className="flex items-center gap-2.5 py-2" aria-live="polite">
      <span className="pulse-dot size-1.5 rounded-full bg-accent" />
      <span className="t-secondary text-ink-faint">Thinking…</span>
    </div>
  )
}
