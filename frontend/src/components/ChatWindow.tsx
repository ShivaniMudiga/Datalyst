import { ArrowUp, Menu, Moon, Sparkles, Sun } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import type { ChatMessage } from '../types/chat'
import { BackButton } from './BackButton'
import { LoadingIndicator } from './LoadingIndicator'
import { Logo } from './Logo'
import { MessageBubble } from './MessageBubble'
import { PurposeBar } from './PurposeBar'
import type { Connection } from '../types/setup'

interface ChatWindowProps {
  connection: Connection | null
  canGoBack: boolean
  onBack: () => void
  isLoading: boolean
  isSidebarOpen: boolean
  messages: ChatMessage[]
  theme: 'dark' | 'light'
  onOpenSidebar: () => void
  onToggleTheme: () => void
  onSendMessage: (message: string) => void
}

export function ChatWindow({ connection, canGoBack, onBack, isLoading, isSidebarOpen, messages, theme, onOpenSidebar, onToggleTheme, onSendMessage }: ChatWindowProps) {
  const [draft, setDraft] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const submit = () => {
    if (!draft.trim() || isLoading) return
    onSendMessage(draft)
    setDraft('')
  }

  return (
    <main className="flex min-w-0 flex-1 flex-col bg-ground">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-rule px-3 md:px-5">
        {!isSidebarOpen && (
          <>
            <button className="icon-button" onClick={onOpenSidebar} aria-label="Open sidebar">
              <Menu className="size-4" />
            </button>
            <Logo size={22} withWordmark wordmarkClassName="text-[14px]" />
          </>
        )}
        {canGoBack && <BackButton onBack={onBack} />}
        <button className="icon-button ml-auto" onClick={onToggleTheme} aria-label="Toggle theme">
          {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>
      </header>

      <PurposeBar purpose={connection?.purpose ?? ''} />

      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <EmptyState onExample={setDraft} connectionId={connection?.id} />
        ) : (
          <div className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-4 py-8 md:px-6">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {/* A streaming turn shows its own trace; this is for loading history. */}
            {isLoading && !messages.some((message) => message.pending) && <LoadingIndicator />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className="bg-gradient-to-t from-ground via-ground to-transparent px-4 pb-5 pt-8 md:px-6">
        <div className="elevated mx-auto max-w-4xl rounded-[26px] border border-rule bg-surface px-2 py-1.5 focus-within:border-accent-line">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                submit()
              }
            }}
            placeholder="Ask a question about your database…"
            rows={1}
            disabled={isLoading}
            className="max-h-44 min-h-11 w-full resize-none bg-transparent px-2 py-2.5 text-[15px] text-ink outline-none placeholder:text-ink-faint disabled:cursor-not-allowed"
          />
          <div className="flex justify-between px-1 pb-0.5">
            <span className="t-label self-center text-ink-faint">Enter to send · Shift + Enter for new line</span>
            <button
              onClick={submit}
              disabled={!draft.trim() || isLoading}
              className="flex size-8 items-center justify-center rounded-full bg-accent text-white transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:bg-sunken disabled:text-ink-faint"
              aria-label="Send message"
            >
              <ArrowUp className="size-4" />
            </button>
          </div>
        </div>
      </div>
    </main>
  )
}

/** The suggestions come from the user's schema and their purpose. Nothing here
 *  names a table, so this screen reads correctly against any database. */
function EmptyState({
  onExample,
  connectionId,
}: {
  onExample: (example: string) => void
  connectionId: string | undefined
}) {
  const [questions, setQuestions] = useState<string[] | null>(null)

  // Keyed on the connection: the suggestions are drawn from that database's
  // schema and purpose, so they have to be re-read when it changes.
  useEffect(() => {
    setQuestions(null)
    api
      .getQuestions()
      .then((result) => setQuestions(result.questions))
      .catch(() => setQuestions([]))
  }, [connectionId])

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col items-center justify-center px-4 pb-16 text-center">
      <div className="mb-5 flex size-11 items-center justify-center rounded-card border border-accent-line bg-accent-soft text-accent">
        <Sparkles className="size-5" />
      </div>
      <h1 className="t-page-title text-ink">Ask questions about your database</h1>
      <p className="t-secondary measure mt-2 text-ink-soft">
        Every answer is built from queries that were validated before they ran.
      </p>
      <div className="mt-10 grid w-full gap-4 sm:grid-cols-2">
        {questions === null
          ? [0, 1, 2, 3].map((index) => <div key={index} className="skeleton h-[58px]" />)
          : questions.map((question) => (
              <button
                key={question}
                onClick={() => onExample(question)}
                className="rounded-card border border-rule bg-surface p-4 text-left text-ink-mid hover:bg-sunken hover:text-ink"
              >
                {question}
              </button>
            ))}
      </div>
    </div>
  )
}
