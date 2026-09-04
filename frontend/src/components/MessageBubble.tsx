import { AlertTriangle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage } from '../types/chat'
import { QueryResult } from './QueryResult'
import { SqlViewer } from './SqlViewer'
import { TraceView } from './TraceView'

interface MessageBubbleProps {
  message: ChatMessage
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isError = message.role === 'error'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <p className="t-secondary max-w-[80%] rounded-card bg-accent-soft px-4 py-2.5 text-ink">
          {message.content}
        </p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex items-start gap-3 rounded-card border-l-[3px] border-critical bg-critical-soft px-4 py-3">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-critical" />
        <p className="t-secondary text-critical">{message.content}</p>
      </div>
    )
  }

  return (
    <article className="space-y-3">
      {message.content && (
        <div className="markdown-content text-ink">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
      )}
      {message.trace && <TraceView steps={message.trace} ms={message.ms} pending={message.pending} />}
      {/* The trace already shows every query. A reloaded conversation has no
          trace, so the standalone viewer is what shows the SQL there. */}
      {message.sql && !message.trace && <SqlViewer sql={message.sql} />}
      {message.data && <QueryResult rows={message.data} />}
    </article>
  )
}
