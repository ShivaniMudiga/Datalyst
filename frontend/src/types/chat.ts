export type MessageRole = 'user' | 'assistant' | 'error'

export interface QueryRow {
  [key: string]: string | number | boolean | null
}

/** One tool call, seen twice: `running` when the model asks, then its outcome. */
export interface TraceStep {
  id: string
  tool: string
  sql: string | null
  status: 'running' | 'ok' | 'failed'
  detail: string | null
}

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  sql?: string
  data?: QueryRow[]
  trace?: TraceStep[]
  ms?: number
  /** True while the turn is still streaming. */
  pending?: boolean
}

export interface ChatSummary {
  id: string
  title: string
  createdAt?: string
}

export type StreamEvent =
  | { event: 'start'; chat_id: string }
  | ({ event: 'step' } & TraceStep)
  | { event: 'done'; response: string; sql: string | null; data: QueryRow[] | null; ms: number }
  | { event: 'error'; message: string }
