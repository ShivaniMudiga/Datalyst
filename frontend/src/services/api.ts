import type { AnalyseStep, Connection, ConnectionInput, ConnectionState, Snapshot } from '../types/setup'
import type { ChatMessage, ChatSummary, StreamEvent } from '../types/chat'
import type { AuthUser } from '../types/auth'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'data-runtime-token'

/** The session token. In localStorage so a reload stays signed in; sent as a
 *  bearer header rather than a cookie, so nothing rides along on cross-site
 *  requests and there is no CSRF surface to defend. */
export const token = {
  get: () => window.localStorage.getItem(TOKEN_KEY),
  set: (value: string) => window.localStorage.setItem(TOKEN_KEY, value),
  clear: () => window.localStorage.removeItem(TOKEN_KEY),
}

export class Unauthorized extends Error {}

function headers(extra?: HeadersInit): HeadersInit {
  const current = token.get()
  return {
    'Content-Type': 'application/json',
    ...(current ? { Authorization: `Bearer ${current}` } : {}),
    ...extra,
  }
}

/** The API answers a failure with `{detail: "..."}`; that sentence is written
 *  for the person reading it, so it is what the UI shows. */
async function failure(response: Response): Promise<Error> {
  const body = await response.text().catch(() => '')
  let detail = body
  try {
    detail = (JSON.parse(body) as { detail?: string }).detail ?? body
  } catch {
    /* not JSON; use the body as-is */
  }
  if (response.status === 401) return new Unauthorized(detail || 'Sign in to continue.')
  return new Error(detail || `Request failed (${response.status})`)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: headers(init?.headers) })
  if (!response.ok) throw await failure(response)
  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>)
}

/** Reads a server-sent-event body off a POST.
 *
 *  EventSource can only GET and cannot set an Authorization header, and a token
 *  has no business in a URL, so both streams in this app are read this way.
 */
async function stream<T>(path: string, body: unknown, onEvent: (event: T) => void): Promise<void> {
  const response = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body ?? {}),
  })
  if (!response.ok || !response.body) throw await failure(response)

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += value
    // Frames are separated by a blank line; the tail is an incomplete one.
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const payload = frame.replace(/^data: /, '').trim()
      if (payload) onEvent(JSON.parse(payload) as T)
    }
  }
}

export const api = {
  signUp: (email: string, password: string) =>
    request<{ token: string; user: AuthUser }>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  logIn: (email: string, password: string) =>
    request<{ token: string; user: AuthUser }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  logOut: () => request<void>('/auth/logout', { method: 'POST' }),
  me: () => request<AuthUser>('/auth/me'),

  streamMessage: (message: string, chatId: string | undefined, onEvent: (event: StreamEvent) => void) =>
    stream<StreamEvent>('/chat/stream', { message, chat_id: chatId }, onEvent),
  getChatHistory: () => request<ChatSummary[]>('/chats'),
  getChatMessages: (chatId: string) => request<ChatMessage[]>(`/chats/${chatId}/messages`),

  getConnection: () => request<ConnectionState>('/connection'),
  getConnections: () => request<Connection[]>('/connections'),
  /** Switch to a database already connected: its schema, purpose and chats come back with it. */
  activateConnection: (id: string) =>
    request<Connection>(`/connections/${id}/activate`, { method: 'POST' }),
  testConnection: (input: ConnectionInput) =>
    request<{ ok: boolean; message: string }>('/connection/test', { method: 'POST', body: JSON.stringify(input) }),
  saveConnection: (input: ConnectionInput) =>
    request<Connection>('/connection', { method: 'POST', body: JSON.stringify(input) }),
  updatePurpose: (purpose: string) =>
    request<{ purpose: string }>('/connection/purpose', { method: 'PATCH', body: JSON.stringify({ purpose }) }),
  previewPurpose: (purpose: string) =>
    request<{ questions: string[] }>('/purpose/preview', { method: 'POST', body: JSON.stringify({ purpose }) }),
  getQuestions: () => request<{ questions: string[] }>('/questions'),
  getSchema: () => request<Snapshot>('/schema'),

  /** The schema read streams a step at a time; a spinner over 15s reads as a hang. */
  analyse: (onEvent: (event: AnalyseStep) => void) => stream<AnalyseStep>('/schema/analyse', {}, onEvent),
}
