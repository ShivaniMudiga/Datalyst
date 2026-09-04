import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api'
import type { ChatMessage, ChatSummary, TraceStep } from '../types/chat'

const newId = () => crypto.randomUUID()

/** A step arrives twice - `running`, then its outcome - under the same id. */
const upsert = (steps: TraceStep[], step: TraceStep) =>
  steps.some((existing) => existing.id === step.id)
    ? steps.map((existing) => (existing.id === step.id ? step : existing))
    : [...steps, step]

/** @param connectionId - the database in view. Conversations belong to one,
 *  so switching database replaces the history rather than appending to it. */
export function useChat(connectionId: string | undefined) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [chats, setChats] = useState<ChatSummary[]>([])
  const [activeChatId, setActiveChatId] = useState<string | undefined>()
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    setMessages([])
    setActiveChatId(undefined)
    if (!connectionId) return setChats([])
    api.getChatHistory().then(setChats).catch(() => setChats([]))
  }, [connectionId])

  const openChat = useCallback((chatId: string) => {
    setActiveChatId(chatId)
    setIsLoading(true)
    api.getChatMessages(chatId)
      .then((history) => setMessages(history))
      .catch(() => setMessages([]))
      .finally(() => setIsLoading(false))
  }, [])

  const sendMessage = useCallback(async (content: string) => {
    const trimmed = content.trim()
    if (!trimmed || isLoading) return

    // The assistant's message is in the list before the answer exists: it is
    // what carries the trace while the agent works.
    const turnId = newId()
    const patch = (change: Partial<ChatMessage>) =>
      setMessages((current) =>
        current.map((message) => (message.id === turnId ? { ...message, ...change } : message)),
      )

    setMessages((current) => [
      ...current,
      { id: newId(), role: 'user', content: trimmed },
      { id: turnId, role: 'assistant', content: '', trace: [], pending: true },
    ])
    setIsLoading(true)

    try {
      await api.streamMessage(trimmed, activeChatId, (event) => {
        if (event.event === 'start') {
          setActiveChatId(event.chat_id)
          setChats((current) =>
            current.some((chat) => chat.id === event.chat_id)
              ? current
              : [{ id: event.chat_id, title: trimmed.slice(0, 64) }, ...current],
          )
        } else if (event.event === 'step') {
          const { event: _, ...step } = event
          setMessages((current) =>
            current.map((message) =>
              message.id === turnId ? { ...message, trace: upsert(message.trace ?? [], step) } : message,
            ),
          )
        } else if (event.event === 'done') {
          patch({
            content: event.response,
            sql: event.sql ?? undefined,
            data: event.data ?? undefined,
            ms: event.ms,
            pending: false,
          })
        } else {
          patch({ role: 'error', content: event.message, trace: undefined, pending: false })
        }
      })
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Unable to reach the database assistant.'
      patch({ role: 'error', content: detail, trace: undefined, pending: false })
    } finally {
      setIsLoading(false)
    }
  }, [activeChatId, isLoading])

  const startNewChat = useCallback(() => {
  setActiveChatId(undefined)
  setMessages([])
}, [])

  return { chats, isLoading, messages, sendMessage, startNewChat, openChat }
}
