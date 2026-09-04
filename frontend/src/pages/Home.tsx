import { useState } from 'react'
import { ChatWindow } from '../components/ChatWindow'
import { Sidebar } from '../components/Sidebar'
import { useChat } from '../hooks/useChat'
import type { AuthUser } from '../types/auth'
import type { Connection } from '../types/setup'

interface HomeProps {
  theme: 'dark' | 'light'
  user: AuthUser | null
  connection: Connection | null
  connections: Connection[]
  onSwitchConnection: (id: string) => void
  canGoBack: boolean
  onBack: () => void
  onSignOut: () => void
  onToggleTheme: () => void
  onOpenSchema: () => void
  onConnectNew: () => void
}

export function Home({
  theme,
  user,
  connection,
  connections,
  onSwitchConnection,
  canGoBack,
  onBack,
  onSignOut,
  onToggleTheme,
  onOpenSchema,
  onConnectNew,
}: HomeProps) {
  const { chats, isLoading, messages, sendMessage, startNewChat, openChat } = useChat(connection?.id)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)

  const newChat = () => {
    void startNewChat()
    if (window.innerWidth < 768) setIsSidebarOpen(false)
  }

  return (
    <div className="flex h-dvh overflow-hidden bg-ground text-ink">
      {isSidebarOpen && (
        <button
          className="fixed inset-0 z-20 bg-ink/40 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
          aria-label="Close sidebar overlay"
        />
      )}
      {/* Reserves the sidebar's column on desktop so nothing overlaps; on
          mobile it collapses and the sidebar becomes an overlay drawer. */}
      <div className={`shrink-0 transition-[width] duration-200 ease-out ${isSidebarOpen ? 'w-0 md:w-[268px]' : 'w-0'}`} />
      <Sidebar
        onOpenSchema={onOpenSchema}
        onConnectNew={onConnectNew}
        onSignOut={onSignOut}
        user={user}
        connection={connection}
        connections={connections}
        onSwitchConnection={onSwitchConnection}
        chats={chats}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onNewChat={newChat}
        onSelectChat={(chatId) => {
          openChat(chatId)
          if (window.innerWidth < 768) setIsSidebarOpen(false)
        }}
      />
      <ChatWindow
        canGoBack={canGoBack}
        onBack={onBack}
        connection={connection}
        isSidebarOpen={isSidebarOpen}
        theme={theme}
        onToggleTheme={onToggleTheme}
        isLoading={isLoading}
        messages={messages}
        onOpenSidebar={() => setIsSidebarOpen(true)}
        onSendMessage={(message) => void sendMessage(message)}
      />
    </div>
  )
}
