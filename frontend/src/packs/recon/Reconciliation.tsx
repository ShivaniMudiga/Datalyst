import { AlertTriangle, Check, ChevronDown, RotateCcw, ScrollText, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import type { AuditRow, QueueRow, Summary } from './api'
import { money, recon } from './api'

/** The queue, the decision, and the log. One screen, because a reviewer works
 *  down a list and needs the evidence and the two buttons in the same place. */

const REASONS = [
  { key: 'all', label: 'Everything' },
  { key: 'no_reference', label: 'No name' },
  { key: 'no_ledger_counterpart', label: 'No counterpart' },
  { key: 'not_settled', label: 'Never settled' },
] as const

function Kpi({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: 'accent' | 'critical' }) {
  return (
    <div className="rounded-card border border-rule bg-surface px-4 py-3">
      <p className="t-label text-ink-faint">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${tone === 'critical' ? 'text-critical' : tone === 'accent' ? 'text-accent' : 'text-ink'}`}>
        {value}
      </p>
      {hint && <p className="mt-0.5 text-xs text-ink-faint">{hint}</p>}
    </div>
  )
}

function Proposal({ row, busy, onDecide, onApply, onReverse }: {
  row: QueueRow
  busy: boolean
  onDecide: (accept: boolean) => void
  onApply: () => void
  onReverse: () => void
}) {
  if (!row.resolution_id) {
    return (
      <p className="px-4 py-3 text-sm text-ink-faint">
        No proposal yet. Nothing here has been decided, and nothing will be until someone does.
      </p>
    )
  }

  const state = row.resolution_state ?? 'proposed'
  return (
    <div className="space-y-3 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-chip border border-accent-line bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent">
          {row.kind}
          {row.target_ids?.length ? ` → payment ${row.target_ids[0]}` : ''}
        </span>
        <span className="text-xs text-ink-faint">confidence {Number(row.confidence).toFixed(2)}</span>
        {row.steps != null && (
          <span className="text-xs text-ink-faint">
            · {row.steps} steps{row.corrections ? `, ${row.corrections} corrections` : ''}
            {row.latency_ms ? ` · ${(row.latency_ms / 1000).toFixed(1)}s` : ''}
          </span>
        )}
        <span className="ml-auto text-xs uppercase tracking-wide text-ink-faint">{state}</span>
      </div>

      <p className="text-sm leading-relaxed text-ink-mid">{row.reason}</p>

      {row.evidence_sql && (
        <details className="rounded-card border border-rule bg-sunken">
          <summary className="cursor-pointer px-3 py-2 text-xs text-ink-faint">
            The evidence this rests on — re-run and re-hashed before anything is applied
          </summary>
          <pre className="overflow-x-auto px-3 pb-3 text-xs text-ink-soft">{row.evidence_sql.trim()}</pre>
        </details>
      )}

      <div className="flex flex-wrap gap-2">
        {state === 'proposed' && (
          <>
            <button
              disabled={busy}
              onClick={() => onDecide(true)}
              className="inline-flex items-center gap-1.5 rounded-chip bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              <Check size={14} /> Approve
            </button>
            <button
              disabled={busy}
              onClick={() => onDecide(false)}
              className="inline-flex items-center gap-1.5 rounded-chip border border-rule px-3 py-1.5 text-sm text-ink-mid disabled:opacity-50"
            >
              <X size={14} /> Reject
            </button>
          </>
        )}
        {state === 'approved' && (
          <button
            disabled={busy}
            onClick={onApply}
            className="inline-flex items-center gap-1.5 rounded-chip bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            <Check size={14} /> Apply
          </button>
        )}
        {state === 'applied' && (
          <button
            disabled={busy}
            onClick={onReverse}
            className="inline-flex items-center gap-1.5 rounded-chip border border-critical px-3 py-1.5 text-sm text-critical disabled:opacity-50"
          >
            <RotateCcw size={14} /> Reverse
          </button>
        )}
      </div>
    </div>
  )
}

export function Reconciliation({ onBack }: { onBack: () => void }) {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [rows, setRows] = useState<QueueRow[]>([])
  const [audit, setAudit] = useState<AuditRow[]>([])
  const [reason, setReason] = useState<string>('all')
  const [open, setOpen] = useState<number | null>(null)
  const [busy, setBusy] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showAudit, setShowAudit] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [nextSummary, nextRows, nextAudit] = await Promise.all([
        recon.summary(), recon.queue('open', reason), recon.audit(),
      ])
      setSummary(nextSummary)
      setRows(nextRows)
      setAudit(nextAudit)
      setError(null)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    }
  }, [reason])

  useEffect(() => { void refresh() }, [refresh])

  const act = async (id: number, action: () => Promise<{ status: string; message?: string }>) => {
    setBusy(id)
    try {
      const result = await action()
      // `refused` is an answer, not a crash: the gate saying no is the product working.
      if (result.status === 'refused' || result.status === 'already_applied') {
        setError(result.message ?? result.status)
      }
      await refresh()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="min-h-dvh bg-ground">
      <header className="border-b border-rule bg-surface px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center gap-3">
          <button onClick={onBack} className="t-label text-ink-faint hover:text-ink">← Back</button>
          <h1 className="text-lg font-semibold text-ink">Reconciliation</h1>
          <button
            onClick={() => setShowAudit((current) => !current)}
            className="ml-auto inline-flex items-center gap-1.5 rounded-chip border border-rule px-3 py-1.5 text-sm text-ink-mid"
          >
            <ScrollText size={14} /> {showAudit ? 'Hide' : 'Show'} audit log
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-5 px-6 py-6">
        {error && (
          <div className="flex items-start gap-2 rounded-card border border-critical bg-critical-soft px-4 py-3 text-sm text-critical">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {summary && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Settled in the period" value={money(summary.settled_minor)} hint={`${summary.lines.toLocaleString()} lines`} />
            <Kpi label="Matched by rule" value={`${(summary.match_rate * 100).toFixed(2)}%`} tone="accent"
                 hint={`${summary.by_rule.toLocaleString()} by rule · ${summary.by_agent} approved`} />
            <Kpi label="In the queue" value={money(summary.at_risk_minor)} tone="critical"
                 hint={`${summary.open_exceptions} exceptions`} />
            <Kpi label="Awaiting a person" value={String(summary.awaiting_review)} hint="proposals, none applied" />
          </div>
        )}

        <div className="flex flex-wrap gap-1.5">
          {REASONS.map((option) => (
            <button
              key={option.key}
              onClick={() => setReason(option.key)}
              className={`rounded-chip border px-3 py-1 text-sm ${
                reason === option.key
                  ? 'border-accent-line bg-accent-soft text-accent'
                  : 'border-rule text-ink-mid hover:text-ink'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>

        <section className="overflow-hidden rounded-card border border-rule bg-surface">
          <table className="w-full text-sm">
            <thead className="bg-sunken text-left">
              <tr className="t-label text-ink-faint">
                <th className="px-4 py-2 font-medium">What the gateway said</th>
                <th className="px-4 py-2 font-medium">Why it is here</th>
                <th className="px-4 py-2 text-right font-medium">Amount</th>
                <th className="px-4 py-2 font-medium">Proposal</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <>
                  <tr
                    key={row.exception_id}
                    onClick={() => setOpen(open === row.exception_id ? null : row.exception_id)}
                    className="cursor-pointer border-t border-rule hover:bg-sunken"
                  >
                    <td className="px-4 py-2.5 font-mono text-xs text-ink">
                      {row.narration ?? <span className="text-ink-faint">— a capture with no payout —</span>}
                    </td>
                    <td className="px-4 py-2.5 text-ink-faint">{row.reason_code.replaceAll('_', ' ')}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-ink">
                      {money(row.amount_minor, row.currency ?? 'INR')}
                    </td>
                    <td className="px-4 py-2.5">
                      {row.resolution_id ? (
                        <span className="text-accent">{row.kind} · {row.resolution_state}</span>
                      ) : (
                        <span className="text-ink-faint">—</span>
                      )}
                    </td>
                    <td className="px-2 text-ink-faint">
                      <ChevronDown size={14} className={open === row.exception_id ? 'rotate-180' : ''} />
                    </td>
                  </tr>
                  {open === row.exception_id && (
                    <tr key={`${row.exception_id}-detail`} className="border-t border-rule bg-sunken">
                      <td colSpan={5}>
                        <Proposal
                          row={row}
                          busy={busy === row.resolution_id}
                          onDecide={(accept) => void act(row.resolution_id!, () => recon.decide(row.resolution_id!, accept))}
                          onApply={() => void act(row.resolution_id!, () => recon.apply(row.resolution_id!))}
                          onReverse={() => void act(row.resolution_id!, () => recon.reverse(row.resolution_id!))}
                        />
                      </td>
                    </tr>
                  )}
                </>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-ink-faint">Nothing in the queue.</td></tr>
              )}
            </tbody>
          </table>
        </section>

        {showAudit && (
          <section className="overflow-hidden rounded-card border border-rule bg-surface">
            <p className="border-b border-rule bg-sunken px-4 py-2 t-label text-ink-faint">
              Append-only. Nothing here can be edited, deleted or truncated — by anyone.
            </p>
            <table className="w-full text-sm">
              <tbody>
                {audit.map((entry) => (
                  <tr key={entry.audit_id} className="border-t border-rule">
                    <td className="px-4 py-2 text-ink-faint tabular-nums">{new Date(entry.at).toLocaleString()}</td>
                    <td className="px-4 py-2 text-ink">{entry.actor}</td>
                    <td className="px-4 py-2 font-medium text-ink">{entry.action.replaceAll('_', ' ')}</td>
                    <td className="px-4 py-2 text-ink-faint">
                      {entry.resolution_id ? `resolution ${entry.resolution_id}` : ''}
                    </td>
                  </tr>
                ))}
                {audit.length === 0 && (
                  <tr><td className="px-4 py-6 text-center text-ink-faint">Nothing has happened yet.</td></tr>
                )}
              </tbody>
            </table>
          </section>
        )}
      </main>
    </div>
  )
}
