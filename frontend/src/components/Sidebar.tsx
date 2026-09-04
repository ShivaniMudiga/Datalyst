import { useState } from 'react'
import { Check, ChevronsUpDown, Database, LogOut, MessageSquare, PanelLeftClose, Plus, Repeat } from 'lucide-react'
import { Logo } from './Logo'
import { engineName } from '../lib/databases'
import type { AuthUser } from '../types/auth'
import type { ChatSummary } from '../types/chat'
import type { Connection } from '../types/setup'

interface SidebarProps {
  chats: ChatSummary[]
  connection: Connection | null
  connections: Connection[]
  onSwitchConnection: (id: string) => void
  user: AuthUser | null
  onOpenSchema: () => void
  onConnectNew: () => void
  onSignOut: () => void
  isOpen: boolean
  onClose: () => void
  onNewChat: () => void
  onSelectChat: (chatId: string) => void
}

export function Sidebar({
  chats,
  connection,
  connections,
  onSwitchConnection,
  user,
  onOpenSchema,
  onConnectNew,
  onSignOut,
  isOpen,
  onClose,
  onNewChat,
  onSelectChat,
}: SidebarProps) {
  const [isPickerOpen, setIsPickerOpen] = useState(false)
  // Only worth a picker once there is something to pick between.
  const others = connections.filter((each) => each.id !== connection?.id)

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-30 flex w-[268px] flex-col border-r border-rule bg-surface p-3 transition-transform duration-200 ease-out ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}
    >
      <div className="mb-6 flex items-center justify-between px-1">
        <Logo size={26} withWordmark wordmarkClassName="text-[15px]" />
        <button className="icon-button" onClick={onClose} aria-label="Close sidebar">
          <PanelLeftClose className="size-4" />
        </button>
      </div>

      <button
        onClick={onNewChat}
        className="flex h-10 items-center gap-2 rounded-card border border-rule px-3 text-[13.5px] font-medium text-ink hover:bg-sunken"
      >
        <Plus className="size-4" /> New chat
      </button>

      <div className="mt-7 min-h-0 flex-1 overflow-y-auto">
        <p className="t-label mb-2 px-1 text-ink-faint">Recent chats</p>
        {chats.length ? (
          <div className="space-y-0.5">
            {chats.map((chat) => (
              <button
                key={chat.id}
                onClick={() => onSelectChat(chat.id)}
                className="flex w-full items-center gap-2 rounded-chip px-2.5 py-2 text-left text-[13.5px] text-ink-soft hover:bg-sunken hover:text-ink"
              >
                <MessageSquare className="size-3.5 shrink-0" />
                <span className="truncate">{chat.title}</span>
              </button>
            ))}
          </div>
        ) : (
          <p className="t-secondary px-1 text-ink-faint">No conversations yet</p>
        )}
      </div>

      {/* Which database, which engine. Nothing here is domain-specific: both
          values come from the connection the user made. */}
      <div className="rounded-card border border-rule">
        {isPickerOpen && others.length > 0 && (
          <div className="max-h-56 overflow-y-auto border-b border-rule p-1">
            {others.map((each) => (
              <button
                key={each.id}
                onClick={() => {
                  setIsPickerOpen(false)
                  onSwitchConnection(each.id)
                }}
                className="flex w-full items-center gap-2 rounded-chip px-2 py-1.5 text-left hover:bg-sunken"
              >
                <Database className="size-3.5 shrink-0 text-ink-faint" />
                <span className="min-w-0 flex-1">
                  <span className="t-secondary block truncate text-ink-mid">{each.database}</span>
                  <span className="t-label block truncate text-ink-faint">
                    {engineName(each.db_type)}
                  </span>
                </span>
              </button>
            ))}
          </div>
        )}
        <button
          onClick={onOpenSchema}
          className="flex w-full items-center gap-2.5 rounded-card px-3 py-2.5 text-left hover:bg-sunken"
        >
          <Database className="size-4 shrink-0 text-ink-faint" />
          <span className="min-w-0 flex-1">
            <span className="t-secondary block truncate text-ink-mid">
              {connection?.database ?? 'Your database'}
            </span>
            <span className="t-label mt-0.5 flex items-center gap-1.5 text-ink-faint">
              <i className="size-1.5 shrink-0 rounded-full bg-accent" />
              <span className="truncate">
                {connection ? `${engineName(connection.db_type)} · Connected` : 'Connected'}
              </span>
            </span>
          </span>
        </button>
        <div className="flex border-t border-rule">
          <button
            onClick={onConnectNew}
            className="t-label flex flex-1 items-center gap-2 whitespace-nowrap px-3 py-2 text-ink-faint hover:bg-sunken hover:text-ink-mid"
          >
            <Repeat className="size-3.5 shrink-0" /> Change database
          </button>
          {others.length > 0 && (
            <button
              onClick={() => setIsPickerOpen((open) => !open)}
              className="t-label flex items-center gap-1 border-l border-rule px-2.5 text-ink-faint hover:bg-sunken hover:text-ink-mid"
              aria-label={`Switch between ${connections.length} connected databases`}
              title="Switch database"
            >
              {isPickerOpen ? <Check className="size-3.5" /> : <ChevronsUpDown className="size-3.5" />}
              {others.length}
            </button>
          )}
        </div>
      </div>

      {user && (
        <div className="mt-2 flex items-center gap-2 px-1">
          <span className="t-label min-w-0 flex-1 truncate text-ink-faint" title={user.email}>
            {user.email}
          </span>
          <button
            onClick={onSignOut}
            className="icon-button shrink-0"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut className="size-3.5" />
          </button>
        </div>
      )}
    </aside>
  )
}
