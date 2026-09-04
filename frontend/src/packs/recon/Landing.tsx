import { ArrowRight, Check, Moon, RotateCcw, ScrollText, Sun } from 'lucide-react'
import { Logo } from '../../components/Logo'

/** The pack's own front door.
 *
 *  The runtime's landing page cannot say what this ships as - Rule 1 keeps
 *  every industry word out of `src/`, and the test enforces it. So the pack
 *  brings its own, and the registry decides which one the app shows. The
 *  generic page is still there, and is what a runtime with no pack installed
 *  would show.
 *
 *  The figures below are the ones `packs/recon/eval.py` wrote into README.md.
 *  If they are regenerated, they change here too - they are the pitch. */

const STATS = [
  { value: '98.95%', label: 'matched by rule', note: 'no model involved, 0.6s over 10,677 lines' },
  { value: '₹33.4M', label: 'settled and accounted for', note: 'one quarter, three gateways' },
  { value: '275', label: 'exceptions surfaced', note: '₹903,824 a person has not seen yet' },
  { value: '0', label: 'false positives', note: '20 of 20 proposals correct, 95% CI ≥ 0.839' },
]

const PIPELINE = [
  {
    step: 'Rules first',
    body: 'Four tiers of SQL: an exact reference, a normalised one, several lines summing to one capture, a fee inside a basis-point band. This is 98.95% of the work, and a language model would only make it less predictable.',
  },
  {
    step: 'The model gets the remainder',
    body: 'The lines no rule can touch, because the free text is all there is to go on. Half of those carry a batch number that identifies nothing — a regex would grab it and propose a wrong link.',
  },
  {
    step: 'It proposes, and stops',
    body: 'Every proposal carries its reasoning, its confidence, and the evidence it rests on. It holds no route to the code that can apply anything, and a test asserts that rather than a policy claiming it.',
  },
  {
    step: 'A person decides',
    body: 'Approve or reject. Applying re-runs the evidence and re-hashes it: if the ledger moved since the proposal, it refuses rather than acting on a world that no longer exists.',
  },
]

const GUARANTEES = [
  { icon: Check, text: 'Gated — the state machine is a database trigger, not a convention' },
  { icon: ScrollText, text: 'Audited — append-only against update, delete and truncate, for the owner too' },
  { icon: RotateCcw, text: 'Reversible — every applied decision undoes exactly what it did' },
]

export function ReconLanding({
  theme,
  onToggleTheme,
  onTry,
}: {
  theme: 'dark' | 'light'
  onToggleTheme: () => void
  onTry: () => void
}) {
  return (
    <div className="min-h-dvh bg-ground text-ink">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-6 md:px-12">
        <Logo withWordmark />
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleTheme}
            aria-label="Switch theme"
            className="rounded-chip p-2 text-ink-faint hover:text-ink"
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <button
            onClick={onTry}
            className="inline-flex items-center gap-1.5 rounded-chip bg-accent px-4 py-2 text-sm font-medium text-white"
          >
            Open the queue <ArrowRight size={15} />
          </button>
        </div>
      </header>

      <section className="landing-glow relative overflow-hidden px-5 pb-20 pt-10 md:px-12 md:pb-24 md:pt-16">
        <div className="mx-auto max-w-6xl">
          <span className="t-label inline-block rounded-chip border border-rule bg-surface px-3 py-1 text-ink-faint">
            FINANCE OPERATIONS · MULTI-SOURCE EXCEPTION MATCHING
          </span>

          <h1 className="mt-6 max-w-3xl text-4xl font-semibold leading-[1.08] tracking-tight md:text-6xl">
            Reconciliation that
            <br />
            shows its working.
          </h1>

          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-mid">
            A payment gateway sends a file saying what it paid out. Your ledger says what you
            captured. They disagree, and somebody reconciles them by hand.
          </p>
          <p className="mt-4 max-w-2xl text-lg leading-relaxed text-ink-mid">
            Rules clear <strong className="text-ink">98.95%</strong> of the file in under a second,
            with no model anywhere near them. The agent is handed only the part rules provably
            cannot do — reading the free text a human wrote — and it can only{' '}
            <strong className="text-ink">propose</strong>. A person decides. A deterministic
            committer applies, once, against re-verified evidence, into a log nobody can edit.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <button
              onClick={onTry}
              className="inline-flex items-center gap-2 rounded-chip bg-accent px-5 py-3 font-medium text-white"
            >
              Open the queue <ArrowRight size={17} />
            </button>
            <a
              href="#how-it-works"
              className="rounded-chip border border-rule px-5 py-3 font-medium text-ink-mid hover:text-ink"
            >
              See how it works
            </a>
          </div>

          <p className="t-label mt-6 text-ink-faint">
            NOTHING IS APPLIED WITHOUT A PERSON · EVERY QUERY READ-ONLY AND VALIDATED
          </p>
        </div>
      </section>

      <section className="border-y border-rule bg-surface px-5 py-10 md:px-12">
        <div className="mx-auto grid max-w-6xl gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {STATS.map((stat) => (
            <div key={stat.label}>
              <p className="text-3xl font-semibold tabular-nums text-accent">{stat.value}</p>
              <p className="mt-1 font-medium text-ink">{stat.label}</p>
              <p className="mt-0.5 text-sm text-ink-faint">{stat.note}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="how-it-works" className="px-5 py-20 md:px-12 md:py-24">
        <div className="mx-auto max-w-6xl">
          <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">
            Rules do the work. The model does the part rules cannot.
          </h2>
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            {PIPELINE.map((entry, index) => (
              <div key={entry.step} className="rounded-card border border-rule bg-surface p-6">
                <span className="t-label text-ink-faint">STEP {index + 1}</span>
                <h3 className="mt-2 text-lg font-semibold text-ink">{entry.step}</h3>
                <p className="mt-2 leading-relaxed text-ink-mid">{entry.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-rule bg-surface px-5 py-12 md:px-12">
        <div className="mx-auto grid max-w-6xl gap-5 md:grid-cols-3">
          {GUARANTEES.map(({ icon: Icon, text }) => (
            <div key={text} className="flex items-start gap-2.5 text-ink-mid">
              <Icon size={17} className="mt-0.5 shrink-0 text-accent" />
              <span>{text}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="px-5 py-20 md:px-12 md:py-24">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">
            Built on an engine that has never heard of payments.
          </h2>
          <p className="mt-4 leading-relaxed text-ink-mid">
            Point the same runtime at a metro network and it talks about stations and footfall.
            Reconciliation is a pack on top of it, and a test fails the build if a single word from
            this domain leaks into the engine underneath. That is why the accuracy above is a
            measurement rather than a claim — the labels were generated with the data, and neither
            the rules nor the model can read them.
          </p>
          <button
            onClick={onTry}
            className="mt-8 inline-flex items-center gap-2 rounded-chip bg-accent px-5 py-3 font-medium text-white"
          >
            Open the queue <ArrowRight size={17} />
          </button>
        </div>
      </section>

      <footer className="border-t border-rule px-5 py-10 md:px-12">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 text-sm text-ink-faint">
          <Logo withWordmark />
          <span>Read-only by default · every figure generated by the evaluation harness</span>
        </div>
      </footer>
    </div>
  )
}
