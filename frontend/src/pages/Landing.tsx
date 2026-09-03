import {
  ArrowRight,
  CheckCircle2,
  Gauge,
  Layers,
  Map,
  MessageSquare,
  Moon,
  ShieldCheck,
  Sparkles,
  Sun,
} from 'lucide-react'
import { Logo } from '../components/Logo'

const DIFFERENTIATORS = [
  {
    icon: Map,
    title: 'Understands your database once',
    body: 'Most tools re-read your schema on every question. Datalyst reads it once at setup, stores it, and shows it back to you as a map — so you can confirm it got it right before you trust a single answer.',
  },
  {
    icon: Layers,
    title: 'Investigates instead of translating',
    body: "A hard question doesn't become one query. Datalyst looks at the trend, compares groups, drills into the worst one, and then concludes — several queries in sequence, each informed by the last.",
  },
  {
    icon: ShieldCheck,
    title: 'Checks its work before touching your data',
    body: 'Every generated query is validated first. When validation fails, the error goes back to the model, which fixes it and tries again — right in front of you.',
  },
  {
    icon: Gauge,
    title: "Builds the answer's interface",
    body: 'Rather than writing a paragraph, Datalyst chooses from a fixed set of components — a KPI, a chart, a ranking, a finding — rendered inline in the conversation.',
  },
]

const STEPS = [
  { title: 'Connect', body: 'Point Datalyst at a PostgreSQL database and choose read-only access.' },
  { title: 'Describe the job', body: 'Tell it what it should look for, in your own words. This is the only place your domain is ever named.' },
  { title: 'Watch it read your database', body: 'Once, in ten to fifteen seconds. It ends on a map of your tables and how they connect.' },
  { title: 'Ask questions', body: 'A trace ticks forward while it writes, checks, and corrects real SQL.' },
  { title: 'Get an answer built from components', body: 'A lead sentence, KPIs, a chart, and the key finding — not a wall of text.' },
]

const DOMAINS = ['Payments', 'Transit', 'Healthcare', 'Logistics', 'Academic', 'HR & operations']

export function Landing({
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
        <div className="flex items-center gap-3">
          <button type="button" className="icon-button" onClick={onToggleTheme} aria-label="Toggle theme">
            {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
          <button className="btn btn-primary" onClick={onTry}>
            Try Datalyst <ArrowRight className="size-4" />
          </button>
        </div>
      </header>

      <Hero onTry={onTry} />
      <TrustStrip />
      <Differentiators />
      <HowItWorks />
      <DomainStrip />
      <FinalCta onTry={onTry} />
      <Footer />
    </div>
  )
}

/* ------------------------------------------------------------------ */

function Hero({ onTry }: { onTry: () => void }) {
  return (
    <section className="landing-glow relative overflow-hidden px-5 pb-20 pt-10 md:px-12 md:pb-28 md:pt-16">
      <div className="mx-auto grid max-w-6xl items-center gap-16 lg:grid-cols-[1.05fr_1fr]">
        <div>
          <span className="t-label mb-5 inline-flex items-center gap-1.5 rounded-chip border border-rule-strong bg-surface px-2 py-1 text-ink-soft">
            <Sparkles className="size-3" /> Now speaking PostgreSQL
          </span>
          <h1 className="hero-title text-ink">
            Talk to your database.
            <br />
            Get answers, not paragraphs.
          </h1>
          <p className="t-secondary measure mt-6 text-[16px] text-ink-soft md:text-[18px]">
            Connect your database and describe the job in plain English. Datalyst investigates like
            an analyst — checking its own work — and answers with real KPIs, charts and rankings,
            rendered directly in the conversation.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-4">
            <button className="btn btn-primary" onClick={onTry}>
              Try Datalyst — it&apos;s free <ArrowRight className="size-4" />
            </button>
            <a href="#how-it-works" className="btn btn-secondary">
              See how it works
            </a>
          </div>
          <p className="t-label mt-6 text-ink-faint">Free to start · Read-only by default</p>
        </div>

        <AnswerMock />
      </div>
    </section>
  )
}

/** A miniature of a real Datalyst answer: lead sentence, KPIs, a bar chart,
 *  a collapsed trace. Shows the product's actual output shape, not a stock photo. */
function AnswerMock() {
  const bars = [38, 62, 45, 90, 58]
  return (
    <div className="elevated rounded-card border border-rule bg-surface p-6">
      <div className="mb-5 flex items-center gap-2">
        <div className="flex size-6 items-center justify-center rounded-card bg-accent-soft text-accent">
          <MessageSquare className="size-3.5" />
        </div>
        <span className="t-secondary text-ink-soft">Which regions are falling behind on delivery time?</span>
      </div>

      <p className="t-secondary text-ink">
        <strong className="text-ink">Northeast and Gulf Coast</strong> are both running above their
        SLA window, and the gap has widened over the last two months.
      </p>

      <div className="mt-5 grid grid-cols-2 gap-4">
        <div className="rounded-card border border-rule p-4">
          <p className="t-label text-ink-faint">Avg. delivery time</p>
          <p className="t-kpi mt-1 text-ink">
            3.4<span className="text-[16px] font-normal text-ink-faint"> days</span>
          </p>
        </div>
        <div className="rounded-card border border-critical bg-critical-soft p-4">
          <p className="t-label text-critical">Regions above SLA</p>
          <p className="t-kpi mt-1 text-critical">2</p>
        </div>
      </div>

      <div className="mt-5 flex h-24 items-end gap-3 border-b border-rule pb-0">
        {bars.map((height, index) => (
          <div key={index} className="flex-1 rounded-t-[3px]" style={{ height: `${height}%`, background: `var(--series-${index + 1})` }} />
        ))}
      </div>

      <div className="mt-4 flex items-center gap-2 text-ink-faint">
        <CheckCircle2 className="size-3.5 text-accent" />
        <span className="t-data">6 steps · 1 correction · 2.4s</span>
      </div>
    </div>
  )
}

function TrustStrip() {
  const items = [
    'Read-only, enforced by your database — not just the app',
    'Every query validated before it runs',
    'Nothing about it is built for one industry',
  ]
  return (
    <section className="border-y border-rule bg-surface px-5 py-6 md:px-12">
      <div className="mx-auto flex max-w-6xl flex-col flex-wrap items-start gap-4 text-ink-soft sm:flex-row sm:items-center sm:justify-between">
        {items.map((item) => (
          <span key={item} className="t-secondary flex items-center gap-2">
            <ShieldCheck className="size-4 shrink-0 text-accent" />
            {item}
          </span>
        ))}
      </div>
    </section>
  )
}

function Differentiators() {
  return (
    <section className="px-5 py-20 md:px-12 md:py-28">
      <div className="mx-auto max-w-6xl">
        <SectionHeading
          eyebrow="Why not just chat with SQL"
          title="Four things, and the product is the combination of all four"
        />
        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          {DIFFERENTIATORS.map(({ icon: Icon, title, body }) => (
            <div key={title} className="rounded-card border border-rule bg-surface p-6">
              <div className="mb-4 flex size-9 items-center justify-center rounded-card bg-accent-soft text-accent">
                <Icon className="size-4.5" />
              </div>
              <h3 className="t-section text-ink">{title}</h3>
              <p className="t-secondary measure mt-2 text-ink-soft">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function HowItWorks() {
  return (
    <section id="how-it-works" className="border-y border-rule bg-surface px-5 py-20 md:px-12 md:py-28">
      <div className="mx-auto max-w-6xl">
        <SectionHeading eyebrow="How it works" title="Five steps, and the first one only happens once" />
        <ol className="mt-12 grid gap-8 md:grid-cols-5 md:gap-6">
          {STEPS.map((step, index) => (
            <li key={step.title} className="relative">
              <span className="t-kpi text-accent-line">{String(index + 1).padStart(2, '0')}</span>
              <h3 className="t-card-title mt-2 text-ink">{step.title}</h3>
              <p className="t-secondary mt-2 text-ink-soft">{step.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

function DomainStrip() {
  return (
    <section className="px-5 py-20 md:px-12 md:py-28">
      <div className="mx-auto max-w-6xl text-center">
        <SectionHeading
          eyebrow="One product, no industry"
          title="Point it at any database and it talks about your data"
          centered
        />
        <p className="t-secondary measure mx-auto mt-5 text-ink-soft">
          Only two things ever tell Datalyst what business you&apos;re in: your schema, and the
          description you write at setup. Nothing else — not a prompt, not a label — is allowed to
          know.
        </p>
        <div className="mt-9 flex flex-wrap justify-center gap-3">
          {DOMAINS.map((domain) => (
            <span key={domain} className="t-label rounded-chip border border-rule-strong bg-surface px-3 py-2 text-ink-soft">
              {domain}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}

function FinalCta({ onTry }: { onTry: () => void }) {
  return (
    <section className="px-5 pb-24 md:px-12">
      <div className="landing-glow mx-auto max-w-6xl rounded-card border border-rule bg-surface px-8 py-16 text-center md:py-20">
        <h2 className="t-page-title text-ink">Connect your database and start asking questions</h2>
        <p className="t-secondary measure mx-auto mt-3 text-ink-soft">
          Setup takes about a minute. Reading your schema takes ten to fifteen seconds — once.
        </p>
        <button className="btn btn-primary mt-8" onClick={onTry}>
          Try Datalyst <ArrowRight className="size-4" />
        </button>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="border-t border-rule px-5 py-10 md:px-12">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
        <Logo size={22} withWordmark wordmarkClassName="text-[14px]" />
        <p className="t-label text-ink-faint">PostgreSQL today. Built to grow.</p>
      </div>
    </footer>
  )
}

function SectionHeading({
  eyebrow,
  title,
  centered = false,
}: {
  eyebrow: string
  title: string
  centered?: boolean
}) {
  return (
    <div className={centered ? 'mx-auto max-w-2xl' : 'max-w-2xl'}>
      <p className="t-label text-accent">{eyebrow}</p>
      <h2 className="t-page-title mt-3 text-ink">{title}</h2>
    </div>
  )
}
