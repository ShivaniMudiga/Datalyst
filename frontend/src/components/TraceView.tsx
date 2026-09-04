import { AlertCircle, Check, ChevronDown } from 'lucide-react'
import { useState } from 'react'
import type { TraceStep } from '../types/chat'

/** What the agent did, one row per tool call.
 *
 *  Collapsed to a single line once the answer arrives: the trace is there to
 *  make a forty-second wait legible, not to be read afterwards. A correction is
 *  the interesting part, so the count of them stays on the collapsed row.
 */
export function TraceView({ steps, ms, pending }: { steps: TraceStep[]; ms?: number; pending?: boolean }) {
  const [isOpen, setIsOpen] = useState(false)
  const running = steps.find((step) => step.status === 'running')
  const corrections = steps.filter((step) => step.status === 'failed').length
  const settled = steps.filter((step) => step.status !== 'running').length

  const summary = pending
    ? running
      ? labelOf(running)
      : 'Thinking…'
    : [
        `${settled} step${settled === 1 ? '' : 's'}`,
        corrections && `${corrections} correction${corrections === 1 ? '' : 's'}`,
        ms !== undefined && `${(ms / 1000).toFixed(1)}s`,
      ]
        .filter(Boolean)
        .join(' · ')

  return (
    <section className="rounded-card border border-rule bg-surface">
      <button
        className="t-label flex w-full items-center gap-2 px-4 py-2 text-left text-ink-faint"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        {pending ? (
          <span className="pulse-dot size-1.5 shrink-0 rounded-full bg-accent" />
        ) : (
          <ChevronDown className={`size-3.5 shrink-0 transition-transform ${isOpen ? '' : '-rotate-90'}`} />
        )}
        <span className="truncate">{summary}</span>
      </button>

      {(isOpen || pending) && steps.length > 0 && (
        <ol className="space-y-2 border-t border-rule px-4 py-3">
          {steps.map((step) => (
            <li key={step.id} className="space-y-1">
              <div className="t-label flex items-center gap-2 text-ink-mid">
                <StatusMark status={step.status} />
                <span>{labelOf(step)}</span>
                {step.detail && <span className="truncate text-ink-faint">{step.detail}</span>}
              </div>
              {step.sql && (
                <pre className="t-data overflow-x-auto rounded-card bg-sunken px-3 py-2 text-ink-mid">
                  <code>{step.sql}</code>
                </pre>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function StatusMark({ status }: { status: TraceStep['status'] }) {
  if (status === 'running') return <span className="pulse-dot size-1.5 shrink-0 rounded-full bg-accent" />
  if (status === 'failed') return <AlertCircle className="size-3.5 shrink-0 text-critical" />
  return <Check className="size-3.5 shrink-0 text-accent" />
}

function labelOf(step: TraceStep) {
  return step.tool === 'run_query' ? 'Query' : 'Reading the schema'
}
