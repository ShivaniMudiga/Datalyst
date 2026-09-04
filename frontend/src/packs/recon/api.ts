// The pack's own HTTP client. It borrows the runtime's session token and
// nothing else: the runtime's `services/api.ts` stays free of any word from
// this domain (Rule 4).
import { token } from '../../services/api'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const BASE = `${API_URL}/packs/recon`

export type Summary = {
  lines: number
  by_rule: number
  by_agent: number
  matched: number
  match_rate: number
  open_exceptions: number
  settled_minor: number
  at_risk_minor: number
  awaiting_review: number
}

export type QueueRow = {
  exception_id: number
  reason_code: string
  amount_minor: number
  status: string
  line_id: number | null
  settled_at: string | null
  narration: string | null
  currency: string | null
  gateway: string | null
  payout_id: string | null
  resolution_id: number | null
  kind: string | null
  target_ids: number[] | null
  confidence: string | null
  reason: string | null
  resolution_state: string | null
  steps: number | null
  corrections: number | null
  latency_ms: number | null
  evidence_sql: string | null
}

export type AuditRow = {
  audit_id: number
  actor: string
  action: string
  resolution_id: number | null
  exception_id: number | null
  after_state: Record<string, unknown> | null
  at: string
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const current = token.get()
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(current ? { Authorization: `Bearer ${current}` } : {}),
    },
  })
  if (!response.ok) {
    const body = await response.text().catch(() => '')
    let detail = body
    try {
      detail = (JSON.parse(body) as { detail?: string }).detail ?? body
    } catch {
      /* not JSON */
    }
    throw new Error(detail || `Request failed (${response.status})`)
  }
  return (await response.json()) as T
}

export const recon = {
  summary: () => call<Summary>('/summary'),
  queue: (status = 'open', reason = 'all') =>
    call<QueueRow[]>(`/exceptions?status=${status}&reason=${reason}`),
  audit: () => call<AuditRow[]>('/audit'),
  decide: (id: number, accept: boolean) =>
    call<{ status: string }>(`/resolutions/${id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ accept }),
    }),
  apply: (id: number) => call<{ status: string; message?: string }>(`/resolutions/${id}/apply`, { method: 'POST' }),
  reverse: (id: number) => call<{ status: string; message?: string }>(`/resolutions/${id}/reverse`, { method: 'POST' }),
}

export const money = (minor: number, currency = 'INR') =>
  `${currency === 'INR' ? '₹' : '$'}${(minor / 100).toLocaleString(undefined, {
    maximumFractionDigits: 0,
  })}`
