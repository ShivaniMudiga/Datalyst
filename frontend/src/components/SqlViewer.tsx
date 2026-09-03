import { Check, ChevronDown, Copy } from 'lucide-react'
import { useState } from 'react'

interface SqlViewerProps {
  sql: string
}

// A MongoDB pipeline arrives through the same field as SQL. It is always a
// JSON object and SQL never is, so the first character tells them apart.
function readable(query: string): { label: string; text: string } {
  if (!query.trimStart().startsWith('{')) return { label: 'Generated SQL', text: query }
  try {
    return { label: 'Generated query', text: JSON.stringify(JSON.parse(query), null, 2) }
  } catch {
    return { label: 'Generated query', text: query }
  }
}

export function SqlViewer({ sql }: SqlViewerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const { label, text } = readable(sql)

  const copySql = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <section className="overflow-hidden rounded-card border border-rule bg-surface">
      <div className="flex items-center justify-between border-b border-rule bg-sunken px-4 py-2">
        <button
          className="t-label flex items-center gap-2 text-ink-faint"
          onClick={() => setIsOpen(!isOpen)}
          aria-expanded={isOpen}
        >
          <ChevronDown className={`size-3.5 transition-transform ${isOpen ? '' : '-rotate-90'}`} />
          {label}
        </button>
        <button className="icon-button" onClick={copySql} aria-label={`Copy ${label}`} title={`Copy ${label}`}>
          {copied ? <Check className="size-3.5 text-accent" /> : <Copy className="size-3.5" />}
        </button>
      </div>
      {isOpen && (
        <pre className="t-data overflow-x-auto p-4 text-ink-mid">
          <code>{text}</code>
        </pre>
      )}
    </section>
  )
}
