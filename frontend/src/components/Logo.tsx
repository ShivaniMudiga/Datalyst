/** The one mark used everywhere: nav, sidebar, setup wordmark. Ascending bars
 *  read as "growth from data" and work as a flat fill in either theme. */
export function Logo({
  size = 28,
  withWordmark = false,
  wordmarkClassName = '',
  className = '',
}: {
  size?: number
  withWordmark?: boolean
  wordmarkClassName?: string
  className?: string
}) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <span
        className="inline-flex shrink-0 items-center justify-center rounded-[8px]"
        style={{ width: size, height: size, background: 'var(--accent)' }}
      >
        <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 20 20" fill="none" aria-hidden>
          <rect x="1.5" y="11" width="3.4" height="7" rx="1" fill="white" fillOpacity="0.5" />
          <rect x="8.3" y="6" width="3.4" height="12" rx="1" fill="white" fillOpacity="0.78" />
          <rect x="15.1" y="1.5" width="3.4" height="16.5" rx="1" fill="white" />
        </svg>
      </span>
      {withWordmark && (
        <span className={`text-[17px] font-semibold tracking-tight text-ink ${wordmarkClassName}`}>
          Datalyst
        </span>
      )}
    </span>
  )
}
