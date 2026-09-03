import { Loader2 } from 'lucide-react'
import { useState } from 'react'
import { BackButton } from '../components/BackButton'
import { Logo } from '../components/Logo'
import { api, token } from '../services/api'
import type { AuthUser } from '../types/auth'

const MIN_PASSWORD = 8

/** Sign in and sign up are the same form with a different verb, so they are one
 *  component: two screens would be two copies of the same field validation. */
export function Auth({ onDone, onBack }: { onDone: (user: AuthUser) => void; onBack: () => void }) {
  const [mode, setMode] = useState<'in' | 'up'>('in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const isSignUp = mode === 'up'
  const tooShort = isSignUp && password.length > 0 && password.length < MIN_PASSWORD
  const ready = email.includes('@') && password.length > 0 && !tooShort

  const submit = async () => {
    if (!ready || busy) return
    setBusy(true)
    setError('')
    try {
      const result = isSignUp
        ? await api.signUp(email.trim(), password)
        : await api.logIn(email.trim(), password)
      token.set(result.token)
      onDone(result.user)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not reach the server.')
    } finally {
      setBusy(false)
    }
  }

  const switchMode = () => {
    setMode(isSignUp ? 'in' : 'up')
    setError('')
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-ground px-5 py-12">
      <div className="mb-10">
        <Logo size={26} withWordmark wordmarkClassName="text-[15px]" />
      </div>

      <div className="w-full max-w-[420px]">
        <div className="mb-3">
          <BackButton onBack={onBack} />
        </div>

        <div className="rounded-card border border-rule bg-surface p-6">
          <header className="mb-6">
            <h1 className="t-page-title text-ink">{isSignUp ? 'Create your account' : 'Welcome back'}</h1>
            <p className="t-secondary measure mt-2 text-ink-soft">
              {isSignUp
                ? 'Your database connection and your conversations are private to your account.'
                : 'Sign in to reach the database you connected.'}
            </p>
          </header>

          <form
            className="flex flex-col gap-5"
            onSubmit={(event) => {
              event.preventDefault()
              void submit()
            }}
          >
            <div>
              <label htmlFor="email" className="t-secondary mb-2 block font-medium text-ink-mid">
                Email
              </label>
              <input
                id="email"
                className="field"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>

            <div>
              <label htmlFor="password" className="t-secondary mb-2 block font-medium text-ink-mid">
                Password
              </label>
              <input
                id="password"
                className="field"
                type="password"
                autoComplete={isSignUp ? 'new-password' : 'current-password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              {isSignUp && (
                <p className={`t-secondary mt-2 ${tooShort ? 'text-critical' : 'text-ink-faint'}`}>
                  At least {MIN_PASSWORD} characters.
                </p>
              )}
            </div>

            {error && (
              <div className="border-l-[3px] border-critical bg-critical-soft p-4">
                <p className="t-secondary text-critical">{error}</p>
              </div>
            )}

            <button className="btn btn-primary w-full" type="submit" disabled={!ready || busy}>
              {busy && <Loader2 className="size-3.5 animate-spin" />}
              {isSignUp ? 'Create account' : 'Sign in'}
            </button>
          </form>

          <p className="t-secondary mt-6 text-center text-ink-faint">
            {isSignUp ? 'Already have an account?' : 'New here?'}{' '}
            <button className="font-medium text-accent hover:underline" onClick={switchMode}>
              {isSignUp ? 'Sign in' : 'Create one'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
