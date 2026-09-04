import { Check, Loader2, Shield } from 'lucide-react'
import { BackButton } from '../components/BackButton'
import { Logo } from '../components/Logo'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import { DATABASES } from '../lib/databases'
import type { AnalyseStep, ConnectionInput, Snapshot } from '../types/setup'

const STEPS = ['Database', 'Connection', 'Access', 'Purpose'] as const

const STARTING_POINTS = [
  {
    title: 'Analytics',
    hint: 'Understand trends, compare groups, spot outliers',
    text: 'You are an analytics assistant. Analyse trends over time, compare performance across groups, and surface the outliers worth a closer look.',
  },
  {
    title: 'Operations',
    hint: 'Monitor throughput, delays and bottlenecks',
    text: 'You are an operations analyst. Monitor throughput and delays, identify bottlenecks, and flag anything running outside its normal range.',
  },
  {
    title: 'Customers and revenue',
    hint: 'Track usage, growth and churn',
    text: 'You are a commercial analyst. Track usage, growth and retention, and identify accounts whose activity is rising or falling.',
  },
  { title: 'Start from scratch', hint: 'Write your own', text: '' },
]

/* rule1-exempt:start - These are a menu spanning four unrelated industries,
   shown so someone can see the tool is not built for any one of them. They are
   the deliberate exception to Rule 1: the point of the strings *is* that no
   single domain owns them. Nothing outside this block may name an industry. */
const EXAMPLES = [
  {
    tag: 'PAYMENTS',
    text: 'You are an analytics assistant for a payments platform. Analyse transaction volume, settlement delays and refund patterns.',
  },
  {
    tag: 'TRANSIT',
    text: 'You are a network analyst for a metro system. Analyse passenger journeys by station and hour, and identify overcrowded routes.',
  },
  {
    tag: 'HEALTHCARE',
    text: 'You are an operations analyst for a care provider. Track admissions, average length of stay and occupancy by ward.',
  },
  {
    tag: 'LOGISTICS',
    text: 'You are a fleet analyst. Track delivery times by region, identify routes with recurring delays, and flag carriers below SLA.',
  },
]
/* rule1-exempt:end */

const BLANK: ConnectionInput = {
  host: 'localhost',
  port: '5432',
  database: '',
  username: '',
  password: '',
  db_type: 'postgresql',
  permission: 'read_only',
  purpose: '',
}

export function Setup({
  onDone,
  onBack,
}: {
  onDone: (snapshot: Snapshot) => void
  onBack: () => void
}) {
  const [step, setStep] = useState(0)
  const [input, setInput] = useState<ConnectionInput>(BLANK)
  const set = (patch: Partial<ConnectionInput>) => setInput((current) => ({ ...current, ...patch }))

  // Back within the wizard until the first step, then out of it. Choosing the
  // wrong engine on step 1 used to mean reloading the page.
  const goBack = () => (step === 0 ? onBack() : setStep(step - 1))

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-ground px-5 py-12">
      <Wordmark />
      {step < 4 && <Progress current={step} />}
      <div className={`w-full ${step >= 3 ? 'max-w-[620px]' : 'max-w-[520px]'}`}>
        {step < 4 && (
          <div className="mb-3">
            <BackButton onBack={goBack} label={step === 0 ? 'Back' : STEPS[step - 1]} />
          </div>
        )}
        {step === 0 && <ChooseDatabase input={input} set={set} onContinue={() => setStep(1)} />}
        {step === 1 && (
          <ConnectionDetails input={input} set={set} onContinue={() => setStep(2)} />
        )}
        {step === 2 && (
          <AccessLevel isMongo={input.db_type === 'mongodb'} onContinue={() => setStep(3)} />
        )}
        {step === 3 && (
          <Purpose
            input={input}
            set={set}
            onContinue={() => setStep(4)}
          />
        )}
        {step === 4 && <Analysing input={input} onDone={onDone} />}
      </div>
    </div>
  )
}

function Wordmark() {
  return (
    <div className="mb-10">
      <Logo size={26} withWordmark wordmarkClassName="text-[15px]" />
    </div>
  )
}

function Progress({ current }: { current: number }) {
  return (
    <ol className="mb-6 flex items-center gap-6">
      {STEPS.map((label, index) => (
        <li key={label} className="flex items-center gap-2">
          <span
            className={`t-label ${index === current ? 'text-accent' : index < current ? 'text-ink-soft' : 'text-ink-faint'}`}
          >
            {index < current ? <Check className="inline size-3" /> : `0${index + 1}`}
          </span>
          <span
            className={`t-label ${index === current ? 'text-accent' : 'text-ink-faint'}`}
          >
            {label}
          </span>
        </li>
      ))}
    </ol>
  )
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-card border border-rule bg-surface p-6">{children}</div>
  )
}

function Title({ children, sub }: { children: React.ReactNode; sub?: string }) {
  return (
    <header className="mb-6">
      <h1 className="t-page-title text-ink">{children}</h1>
      {sub && <p className="t-secondary measure mt-2 text-ink-soft">{sub}</p>}
    </header>
  )
}

/* 1 -------------------------------------------------------------------- */

function ChooseDatabase({
  input,
  set,
  onContinue,
}: {
  input: ConnectionInput
  set: (patch: Partial<ConnectionInput>) => void
  onContinue: () => void
}) {
  return (
    <Card>
      <Title sub="Datalyst reads your schema once, then answers questions about your data.">
        Connect your database
      </Title>
      <div className="grid grid-cols-2 gap-6">
        {DATABASES.map((database) => {
          const selected = input.db_type === database.id
          return (
            <button
              key={database.id}
              type="button"
              aria-pressed={selected}
              onClick={() => set({ db_type: database.id, port: database.port })}
              className={`relative rounded-card p-6 text-left ${
                selected
                  ? 'border-2 border-accent bg-accent-soft'
                  : 'border border-rule bg-surface'
              }`}
            >
              {selected && <Check className="absolute right-3 top-3 size-4 text-accent" />}
              <p className="t-card-title text-ink">{database.name}</p>
              <p className="t-secondary mt-1 text-ink-soft">{database.hint}</p>
            </button>
          )
        })}
      </div>
      <button className="btn btn-primary mt-6 w-full" onClick={onContinue}>
        Continue
      </button>
    </Card>
  )
}

/* 2 -------------------------------------------------------------------- */

const FIELDS = [
  { key: 'host', label: 'Host' },
  { key: 'port', label: 'Port' },
  { key: 'database', label: 'Database' },
  { key: 'username', label: 'User' },
  { key: 'password', label: 'Password', type: 'password' },
] as const

const HOST_HELPER: Record<string, string> = {
  postgresql: 'localhost for a database on this machine',
  // Atlas and replica sets cannot be described by a host and a port, so a full
  // URI pasted here is used as-is and the other boxes are ignored.
  mongodb: 'localhost, or paste a full mongodb+srv:// URI for Atlas',
}

function ConnectionDetails({
  input,
  set,
  onContinue,
}: {
  input: ConnectionInput
  set: (patch: Partial<ConnectionInput>) => void
  onContinue: () => void
}) {
  const [state, setState] = useState<'idle' | 'testing' | 'passed' | 'failed'>('idle')
  const [message, setMessage] = useState('')

  const test = async () => {
    setState('testing')
    try {
      const result = await api.testConnection(input)
      setMessage(result.message)
      if (!result.ok) return setState('failed')
      // The credentials work, so store them now: the purpose screen previews
      // its suggestions against the real database before the user commits.
      await api.saveConnection(input)
      setState('passed')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not reach the server.')
      setState('failed')
    }
  }

  return (
    <Card>
      <Title>Connection details</Title>
      <div className="flex flex-col gap-5">
        {FIELDS.map((field) => (
          <div key={field.key}>
            <label htmlFor={field.key} className="t-secondary mb-2 block font-medium text-ink-mid">
              {field.label}
            </label>
            <input
              id={field.key}
              className="field"
              type={'type' in field ? field.type : 'text'}
              value={input[field.key]}
              onChange={(event) => {
                set({ [field.key]: event.target.value })
                setState('idle')
              }}
            />
            {field.key === 'host' && (
              <p className="t-secondary mt-2 text-ink-faint">
                {HOST_HELPER[input.db_type] ?? HOST_HELPER.postgresql}
              </p>
            )}
          </div>
        ))}
      </div>

      {state === 'failed' && (
        <div className="mt-5 border-l-[3px] border-critical bg-critical-soft p-4">
          {/* A refusal can carry the command that fixes it, over several lines. */}
          <p className="t-data whitespace-pre-line text-critical">{message}</p>
          <p className="t-secondary mt-2 text-ink-mid">
            Nothing has been saved. Fix the details above, or check that{' '}
            {DATABASES.find((item) => item.id === input.db_type)?.name ?? 'the database'} is running,
            then test again.
          </p>
        </div>
      )}
      {state === 'passed' && (
        <p className="t-secondary mt-5 text-accent">{message}</p>
      )}

      <div className="mt-6 flex items-center gap-4">
        <button
          className="btn btn-secondary"
          onClick={test}
          disabled={state === 'testing' || !input.database || !input.username}
        >
          {state === 'testing' && <Loader2 className="size-3.5 animate-spin" />}
          {state === 'testing' ? 'Testing…' : 'Test connection'}
        </button>
        <button className="btn btn-primary" onClick={onContinue} disabled={state !== 'passed'}>
          Continue
        </button>
        {state !== 'passed' && (
          <span className="t-label text-ink-faint">Test the connection first</span>
        )}
      </div>
    </Card>
  )
}

/* 3 -------------------------------------------------------------------- */

function AccessLevel({ isMongo, onContinue }: { isMongo: boolean; onContinue: () => void }) {
  return (
    <Card>
      <Title>What should Datalyst be allowed to do?</Title>
      <div className="flex flex-col gap-4">
        <div className="rounded-card border-2 border-accent bg-accent-soft p-6">
          <div className="flex items-center gap-3">
            <p className="t-card-title text-ink">Read only</p>
            <span className="t-label rounded-chip bg-surface px-1.5 py-0.5 text-accent">
              Recommended
            </span>
          </div>
          <p className="t-secondary measure mt-2 text-ink-mid">
            Datalyst can query your data but can never change it. Enforced by your database,
            not just by the app.
          </p>
        </div>
        <div className="cursor-not-allowed rounded-card border border-rule p-6 opacity-45">
          <div className="flex items-center gap-3">
            <p className="t-card-title text-ink">Read and write</p>
            <span className="t-label rounded-chip bg-sunken px-1.5 py-0.5 text-ink-faint">
              Coming soon
            </span>
          </div>
          <p className="t-secondary measure mt-2 text-ink-mid">
            Allow the assistant to insert, update and delete rows.
          </p>
        </div>
      </div>
      {/* How read-only is enforced differs by engine, and MongoDB needs
          something of the user, so the claim above has to name the mechanism. */}
      <p className="t-secondary mt-6 flex gap-2 text-ink-faint">
        <Shield className="mt-0.5 size-4 shrink-0" />
        {isMongo
          ? 'MongoDB has no read-only connection, so the role is the gate: connect as a user granted only the read role, and Datalyst will refuse credentials that can write. Queries are capped at 15 seconds.'
          : 'Read-only connections use a restricted database role, a read-only transaction and a 15-second query timeout.'}
      </p>
      <button className="btn btn-primary mt-6 w-full" onClick={onContinue}>
        Continue
      </button>
    </Card>
  )
}

/* 4 -------------------------------------------------------------------- */

const MAX_PURPOSE = 2000

function Purpose({
  input,
  set,
  onContinue,
}: {
  input: ConnectionInput
  set: (patch: Partial<ConnectionInput>) => void
  onContinue: () => void
}) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const start = async () => {
    setSaving(true)
    setError('')
    try {
      await api.saveConnection(input)
      onContinue()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the connection.')
      setSaving(false)
    }
  }

  return (
    <Card>
      <Title sub="Describe the job in your own words. This shapes which questions it suggests, what it looks for, and how it writes every answer.">
        What should this assistant do?
      </Title>

      <div className="grid grid-cols-2 gap-3">
        {STARTING_POINTS.map((point) => (
          <button
            key={point.title}
            type="button"
            onClick={() => set({ purpose: point.text })}
            className={`rounded-card border p-4 text-left ${
              input.purpose === point.text && point.text
                ? 'border-accent bg-accent-soft'
                : 'border-rule bg-surface hover:bg-sunken'
            }`}
          >
            <p className="t-card-title text-ink">{point.title}</p>
            <p className="t-secondary mt-1 text-ink-soft">{point.hint}</p>
          </button>
        ))}
      </div>

      <textarea
        className="field mt-5 min-h-[160px] resize-y py-4"
        style={{ height: 'auto' }}
        maxLength={MAX_PURPOSE}
        value={input.purpose}
        onChange={(event) => set({ purpose: event.target.value })}
        placeholder="You are a … assistant. Analyse … and identify …"
      />
      <p className="t-label mt-2 text-right text-ink-faint">
        {input.purpose.length} / {MAX_PURPOSE}
      </p>

      <div className="mt-5 rounded-card bg-sunken p-4">
        <p className="t-label mb-3 text-ink-faint">Examples from other users</p>
        <div className="flex flex-col gap-3">
          {EXAMPLES.map((example) => (
            <button
              key={example.tag}
              type="button"
              onClick={() => set({ purpose: example.text })}
              className="text-left"
            >
              <span className="t-label mr-2 text-ink-faint">{example.tag}</span>
              <span className="t-secondary text-ink-soft">{example.text}</span>
            </button>
          ))}
        </div>
      </div>

      <PurposePreview purpose={input.purpose} />

      {error && <p className="t-secondary mt-4 text-critical">{error}</p>}

      <button className="btn btn-primary mt-6 w-full" onClick={start} disabled={saving}>
        {saving && <Loader2 className="size-3.5 animate-spin" />}
        Connect and analyse
      </button>
    </Card>
  )
}

/** Closes the loop: the user sees their words change something before committing. */
function PurposePreview({ purpose }: { purpose: string }) {
  const [questions, setQuestions] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const timer = setTimeout(() => {
      api
        .previewPurpose(purpose)
        .then((result) => setQuestions(result.questions))
        .catch(() => setQuestions([]))
        .finally(() => setLoading(false))
    }, 800)
    return () => clearTimeout(timer)
  }, [purpose])

  return (
    <div className="mt-4 rounded-card border border-rule bg-surface p-5">
      <p className="t-label mb-3 text-accent">What it will suggest</p>
      {loading ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((index) => (
            <div key={index} className="skeleton h-4" style={{ width: `${75 - index * 8}%` }} />
          ))}
        </div>
      ) : questions.length ? (
        <ul className="flex flex-col gap-2">
          {questions.map((question) => (
            <li key={question} className="t-secondary text-ink-mid">
              {question}
            </li>
          ))}
        </ul>
      ) : (
        <p className="t-secondary text-ink-faint">
          Suggestions appear once your database has been read.
        </p>
      )}
    </div>
  )
}

/* 5 -------------------------------------------------------------------- */

function Analysing({
  input,
  onDone,
}: {
  input: ConnectionInput
  onDone: (snapshot: Snapshot) => void
}) {
  const [steps, setSteps] = useState<AnalyseStep[]>([])
  const [error, setError] = useState('')
  const started = useRef(false)

  const run = useCallback(() => {
    api
      .analyse((parsed) => {
        if (parsed.event === 'step') setSteps((current) => [...current, parsed])
        if (parsed.event === 'error') setError(parsed.message ?? 'The schema could not be read.')
        if (parsed.event === 'done' && parsed.snapshot) onDone(parsed.snapshot)
      })
      .catch(() => setError('Lost the connection while reading the schema.'))
  }, [onDone])

  useEffect(() => {
    if (started.current) return
    started.current = true
    run()
  }, [run])

  const total = 5
  const done = steps.length

  return (
    <Card>
      <div className="mb-6 h-0.5 w-full bg-sunken">
        <div
          className="h-0.5 bg-accent transition-[width]"
          style={{ width: `${(done / total) * 100}%` }}
        />
      </div>
      <Title sub="This happens once. Every conversation reuses it.">Reading your database</Title>

      <ol className="flex flex-col gap-4">
        {['Connecting', 'Reading tables', 'Reading columns', 'Mapping foreign keys', 'Sampling row counts'].map(
          (label, index) => {
            const step = steps[index]
            const active = index === done && !error
            return (
              <li key={label} className="flex items-center gap-3">
                {step ? (
                  <Check className="size-3.5 text-accent" />
                ) : active ? (
                  <span className="pulse-dot size-1.5 rounded-full bg-accent" />
                ) : (
                  <span className="size-1.5 rounded-full border border-ink-faint" />
                )}
                <span className={`t-data flex-1 ${step || active ? 'text-ink' : 'text-ink-faint opacity-40'}`}>
                  {label}
                  {index === 0 && step ? ` to ${input.database}` : ''}
                </span>
                {step && <span className="t-data text-ink-faint">{step.result}</span>}
              </li>
            )
          },
        )}
      </ol>

      {error && (
        <div className="mt-6 border-l-[3px] border-critical bg-critical-soft p-4">
          <p className="t-data text-critical">{error}</p>
        </div>
      )}
    </Card>
  )
}
