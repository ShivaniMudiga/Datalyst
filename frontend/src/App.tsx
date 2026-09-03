import { useCallback, useEffect, useState } from 'react'
import { Auth } from './pages/Auth'
import { Home } from './pages/Home'
import { Landing } from './pages/Landing'
import { Schema } from './pages/Schema'
import { Setup } from './pages/Setup'
import { Unauthorized, api, token } from './services/api'
import type { AuthUser } from './types/auth'
import type { Connection, Snapshot } from './types/setup'

type Screen = 'landing' | 'loading' | 'auth' | 'setup' | 'schema' | 'conversation'
type Theme = 'dark' | 'light'

export default function App() {
  const [screen, setScreen] = useState<Screen>('landing')
  // Where Back goes. A stack rather than a single previous screen, so setup →
  // schema → conversation → back → back returns the way you came.
  const [history, setHistory] = useState<Screen[]>([])
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [connection, setConnection] = useState<Connection | null>(null)
  const [connections, setConnections] = useState<Connection[]>([])
  const [user, setUser] = useState<AuthUser | null>(null)
  const [theme, setTheme] = useState<Theme>(
    () => (window.localStorage.getItem('data-runtime-theme') === 'dark' ? 'dark' : 'light'),
  )

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem('data-runtime-theme', theme)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
  }, [])

  const go = useCallback((next: Screen) => {
    setScreen((current) => {
      // 'loading' is a moment, not a place: never go back to it.
      if (current !== 'loading') setHistory((stack) => [...stack, current])
      return next
    })
  }, [])

  const back = useCallback(() => {
    setHistory((stack) => {
      if (stack.length === 0) return stack
      setScreen(stack[stack.length - 1])
      return stack.slice(0, -1)
    })
  }, [])

  const signOut = useCallback(() => {
    void api.logOut().catch(() => {})
    token.clear()
    setUser(null)
    setConnection(null)
    setConnections([])
    setSnapshot(null)
    setHistory([])
    setScreen('landing')
  }, [])

  /** Where a signed-in user belongs: their conversation if they have connected
   *  a database and read its schema, otherwise setup. */
  const resume = useCallback(async () => {
    try {
      const state = await api.getConnection()
      setConnection(state.connection)
      void api.getConnections().then(setConnections).catch(() => setConnections([]))
      if (!state.connection || !state.has_snapshot) return go('setup')
      setSnapshot(await api.getSchema())
      go('conversation')
    } catch (error) {
      if (error instanceof Unauthorized) {
        token.clear()
        setUser(null)
        return go('auth')
      }
      go('setup')
    }
  }, [go])

  const enterApp = useCallback(() => {
    go('loading')
    if (!token.get()) return go('auth')
    api
      .me()
      .then((signedIn) => {
        setUser(signedIn)
        return resume()
      })
      .catch(() => {
        token.clear()
        go('auth')
      })
  }, [go, resume])

  const onSignedIn = useCallback(
    (signedIn: AuthUser) => {
      setUser(signedIn)
      setHistory([])
      void resume()
    },
    [resume],
  )

  const onAnalysed = useCallback(
    async (result: Snapshot) => {
      setSnapshot(result)
      // The schema map and the sidebar name the engine, which lives on the
      // connection rather than on the snapshot.
      setConnection(await api.getConnection().then((state) => state.connection).catch(() => null))
      setConnections(await api.getConnections().catch(() => []))
      go('schema')
    },
    [go],
  )

  // Switching database swaps the schema, the purpose and the chat history
  // together: all three hang off the connection, so all three are re-read.
  const switchConnection = async (id: string) => {
    const next = await api.activateConnection(id)
    setConnection(next)
    setConnections(await api.getConnections().catch(() => []))
    setSnapshot(await api.getSchema().catch(() => null))
  }

  if (screen === 'landing') {
    return <Landing theme={theme} onToggleTheme={toggleTheme} onTry={enterApp} />
  }

  if (screen === 'loading') {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-ground">
        <span className="pulse-dot size-2 rounded-full bg-accent" />
      </div>
    )
  }

  if (screen === 'auth') {
    return <Auth onDone={onSignedIn} onBack={() => setScreen('landing')} />
  }

  if (screen === 'setup') return <Setup onDone={onAnalysed} onBack={back} />

  if (screen === 'schema' && snapshot) {
    return (
      <Schema
        snapshot={snapshot}
        connection={connection}
        onBack={back}
        onRefresh={() => go('setup')}
        onConnectNew={() => go('setup')}
        onStart={() => go('conversation')}
      />
    )
  }

  return (
    <Home
      theme={theme}
      user={user}
      connection={connection}
      connections={connections}
      onSwitchConnection={(id) => void switchConnection(id)}
      canGoBack={history.length > 0}
      onBack={back}
      onSignOut={signOut}
      onToggleTheme={toggleTheme}
      onOpenSchema={() => snapshot && go('schema')}
      onConnectNew={() => go('setup')}
    />
  )
}
