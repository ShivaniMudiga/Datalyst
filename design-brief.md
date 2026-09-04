# Data Runtime — UI Design Brief

> Paste this whole document into Claude Design. It describes one product, end to end.

## What to produce

**Nothing exists yet — build all 18 artboards from scratch.** A single design canvas with **18 artboards** laid out in the order below, grouped into four bands:
**Setup** (1–4) · **Understanding** (5–7) · **Conversation** (8–13) · **System** (14–18).

This is a **visual reference**, not a coded app. Every artboard should be a finished, pixel-accurate
screen with real content — never lorem, never placeholder boxes labelled "chart goes here".

---

## 1. The product in one paragraph

Data Runtime connects to a user's database, reads and understands its structure once, then lets them
investigate their data by asking questions in plain language. The AI generates database-native queries,
validates them, corrects itself when it gets something wrong, and answers by **assembling an interface**
— KPIs, charts, rankings, findings — rendered inline inside the conversation. There is no separate
dashboard and no side canvas. The conversation *is* the workspace.

**The product is configured, not hardcoded.** At setup the user writes a *purpose* — a description of
what they want this AI to do. That single input is what turns a generic query engine into a specific
assistant, and it changes the suggested questions, the vocabulary of every answer, which findings the
AI volunteers, and what it considers worth flagging.

Two users get completely different products from the same codebase:

- A college registrar writes *"analyse student performance and attendance, and identify students who may need attention"* — and gets at-risk students, department comparisons, attendance trends.
- A payments company writes *"analyse transaction volume and merchant activity, and surface merchants whose usage is growing or declining"* — and gets merchant growth, settlement delays, refund patterns.

**There is no list of supported domains.** The system reads whatever schema it is pointed at and
whatever description it is given, and adapts. A college. A payments platform. A metro network counting
passenger journeys. A hospital tracking admissions. A courier fleet, a retailer, a gym, a law firm.
The product has no opinion about which, and **the interface must contain no vocabulary of its own** —
every noun on screen comes from the user's schema, their column names, or their purpose.

**Because of this, the canvas shows several unrelated domains, and the variety is the message.**
Artboards 1–13 use a college database because a walkthrough needs one concrete example. Artboards 16–18
then show the identical product against completely unrelated data. If every artboard shows students,
the design reads as a college analytics tool and the entire product concept is lost.

**The samples are illustrations, never a supported-domain list.** Do not design a domain picker, an
industry template gallery, or any vertical-specific screen. The user types a sentence; that is the
entire configuration surface.

Walkthrough database (artboards 1–13): a fictional college — students, departments, courses,
attendance, exams, fees, placements, projects.

---

## 2. Non-negotiable design principles

These are the acceptance criteria. A beautiful screen that violates one of these is a failed screen.

**Spacious.** Congestion is the primary failure mode to avoid. When in doubt, add space and remove
elements — never shrink type to fit more in.

**Two colours plus neutrals. That is the entire palette.** One accent, one semantic-critical, and a
neutral ramp. Charts do **not** introduce new hues — multi-series charts use tints of the single
accent (specified below). A rainbow chart palette fails this brief.

**Self-explanatory.** A first-time user must never wonder what something is or what to do next:
- Every icon is paired with a text label. Icon-only buttons exist only in dense toolbars, and always carry a tooltip.
- Every number carries a unit and a label. `78.7%` alone is not acceptable; `78.7% — Average attendance` is.
- Every empty state names the next action and shows an example of it.
- Every error says what went wrong *and* what to do about it.
- Trace steps use plain language ("Checked the query against your schema"), never internal jargon ("semantic_validator passed").

**Loading state for everything that renders.** No element ever pops in from nothing. See §6.

**Nothing in the interface is domain-specific.** No graduation caps, no credit cards, no industry
illustration, no fixed nouns in any label, empty state, button or placeholder. Icons are neutral
geometry only. Every domain word visible on any screen must be traceable to a table name, a column
name, a query result, or the user's purpose text. If a string in the chrome could not survive the
database being swapped for a metro network's, it is a bug in the design.

**The purpose is always visible.** The user configured this AI to do a job; the interface must show
that it is doing that job. The purpose appears in the setup, persistently above the conversation, and
in the connection panel. A user must never have to guess what stance the assistant is taking.

**Quiet by default.** Colour, weight and borders are earned. Most of the interface is neutral text on a
neutral ground, with the accent appearing only where something is interactive or important.

---

## 3. Design tokens

### Colour — light theme

| Token | Hex | Use |
|---|---|---|
| `ground` | `#F7F8FA` | Page background |
| `surface` | `#FFFFFF` | Cards, panels, message blocks |
| `sunken` | `#EEF0F4` | Table headers, inset areas, skeleton base |
| `ink` | `#141922` | Primary text, headings |
| `ink-mid` | `#3F4856` | Body text |
| `ink-soft` | `#606B7D` | Secondary text, captions |
| `ink-faint` | `#8A93A3` | Labels, timestamps, disabled |
| `rule` | `#E2E5EB` | Hairlines, card borders |
| `rule-strong` | `#C9CFD9` | Section dividers, emphasised borders |
| **`accent`** | **`#3A6EA5`** | The one accent — links, active state, primary button, chart fill, focus ring |
| `accent-soft` | `#E9F0F8` | Accent backgrounds, selected rows, insight cards |
| `accent-line` | `#B6CCE4` | Accent borders, chart gridline emphasis |
| **`critical`** | **`#B3453F`** | The one semantic colour — errors, at-risk, failed validation, declining trend |
| `critical-soft` | `#FBECEB` | Error backgrounds |

### Colour — dark theme

| Token | Hex |
|---|---|
| `ground` | `#0E1116` |
| `surface` | `#161A22` |
| `sunken` | `#1C212B` |
| `ink` | `#E7EAF0` |
| `ink-mid` | `#BFC6D2` |
| `ink-soft` | `#8D96A6` |
| `ink-faint` | `#6C7686` |
| `rule` | `#242A36` |
| `rule-strong` | `#343C4A` |
| **`accent`** | **`#8AB4E8`** |
| `accent-soft` | `#182436` |
| `accent-line` | `#2E4463` |
| **`critical`** | **`#E08A84`** |
| `critical-soft` | `#2C1917` |

Design **both themes**. Show the light theme on artboards 1–13 and the dark theme on at least
artboards 10 and 15 so the pairing is verifiable.

### Chart series — tints of the accent, never new hues

Light: `#3A6EA5` → `#5A87B7` → `#7BA0C9` → `#9DBADB` → `#BFD3ED`
Dark: `#8AB4E8` → `#7099CB` → `#577EAE` → `#3F6491` → `#2A4B74`

A single-series chart uses `accent` at full strength. A bar that needs to be called out as a problem
uses `critical` — that is the *only* time a second hue appears in a chart.

### Type

- **UI, headings, body:** IBM Plex Sans — 400 / 500 / 600. Never 700 except the product wordmark.
- **Data, SQL, numbers, labels, trace:** IBM Plex Mono — 400 / 500.
- All aligned numerals use `tabular-nums`.

| Role | Size / line-height / weight / tracking |
|---|---|
| Page title | 26px / 1.25 / 600 / −0.02em |
| Section heading | 17px / 1.35 / 600 / −0.01em |
| Card title | 14px / 1.4 / 600 |
| Body | 15px / **1.65** / 400 |
| Secondary | 13.5px / 1.55 / 400 |
| Label (mono, uppercase) | 10.5px / 1.4 / 500 / **+0.09em** |
| KPI value | 30px / 1.15 / 600 / −0.02em / tabular |
| Data cell (mono) | 12.5px / 1.5 / 400 |

Body text never exceeds **68 characters** per line.

### Spacing — 8px grid, generous end of it

These are minimums. Going below any of them counts as congestion.

| Context | Value |
|---|---|
| Page gutter (desktop) | 48px |
| Page gutter (mobile) | 20px |
| Space between sections | 40px |
| Padding inside any card or panel | 24px |
| Gap between stacked cards | 16px |
| Table cell padding | 14px vertical / 18px horizontal |
| Gap between form fields | 20px |
| Gap between a label and its input | 8px |
| Space above a section heading | 40px, below it 20px |
| Chat message vertical rhythm | 32px between turns |

### Shape and depth

- Corner radius: **6px** on cards, inputs, buttons. **4px** on chips and small controls. Nothing is pill-shaped except status dots. Avoid heavy rounding — it reads consumer, not professional.
- Elevation: one shadow only — `0 1px 2px rgba(20,25,34,.05), 0 8px 24px −12px rgba(20,25,34,.12)`. Used on modals, the composer, and the connection panel. Cards use a 1px `rule` border and **no** shadow.
- Borders do the structural work; shadows are almost absent. This is what makes it read as a developer tool rather than a marketing site.

### Focus and interaction

- Focus ring: 2px `accent`, 2px offset, on every interactive element. Visible on keyboard focus.
- Hover on a row or list item: background shifts to `sunken`. No transform, no scale.
- Transitions: 140ms ease on colour only. Nothing moves on hover.

---

## 4. Layout skeleton

Two shells.

**Setup shell** (artboards 1–5): no sidebar. A single centred column, **max-width 520px**, vertically
centred on `ground`. A 4-step progress indicator sits above the card — small mono numerals with the
current step in `accent` and completed steps marked with a check. The product wordmark sits 40px above
that, small and quiet.

**App shell** (artboards 6–14 and 16): a fixed **280px** left sidebar on `surface` with a 1px right border,
and a main area on `ground`. The sidebar never collapses on desktop. Main content is centred with
**max-width 820px** for the conversation column, full-width for the schema map.

---

## 5. Artboards

### 1 — Setup: choose your database

Centred card. Title **"Connect your database"**, one line of secondary text beneath:
*"Data Runtime reads your schema once, then answers questions about your data."*

Two large selectable tiles side by side, 24px gap:
- **PostgreSQL** — selected. Accent border, `accent-soft` background, a small check in the top-right corner.
- **MongoDB** — disabled. 45% opacity, a mono chip reading `COMING SOON`, cursor not-allowed. Do not hide it; showing the disabled option communicates the roadmap.

Each tile: 24px padding, the database name at card-title size, and one line of secondary text
("Relational — tables, columns, foreign keys" / "Document — collections and fields").

Primary button, full width, at the bottom: **"Continue"**.

### 2 — Setup: connection details

Same card. Title **"Connection details"**.

Five fields, 20px apart, each with a label above and helper text below where it earns its place:
`Host` (helper: *"localhost for a database on this machine"*), `Port` (prefilled `5432`),
`Database`, `User`, `Password`.

Inputs: 44px tall, 1px `rule` border, 12px horizontal padding, `surface` background. Focused input
takes an `accent` border plus the focus ring.

Below the fields, a **secondary** button: **"Test connection"** — and this is important, it sits *left*,
with the primary **"Continue"** disabled until the test passes. The user must not be able to advance
into a failure.

**Draw three variants of this artboard, stacked vertically as 2a / 2b / 2c:**
- **2a Idle** — Continue disabled, greyed, with a mono hint beside it: `Test the connection first`.
- **2b Testing** — the Test button shows an inline 14px spinner and reads **"Testing…"**, disabled.
- **2c Failed** — a `critical-soft` block below the button, 16px padding, `critical` 1px left border 3px wide. It shows the real driver message in mono at 12.5px: `could not connect to server: Connection refused — is the server running on host "localhost" and accepting connections on port 5432?` and, below it in body text, **"Check that PostgreSQL is running, then test again."**

### 3 — Setup: access level

Title **"What should Data Runtime be allowed to do?"**

Two stacked radio cards, full width, 16px apart, 24px padding each:
- **Read only** — selected, accent border. Body text: *"Data Runtime can query your data but can never change it. Enforced by your database, not just by the app."* A small mono chip: `RECOMMENDED`.
- **Read and write** — disabled at 45% opacity, chip `COMING SOON`. Body text: *"Allow the AI to insert, update and delete rows."*

Below both, a quiet note in `ink-faint` secondary text with a small shield icon:
*"Read-only connections use a restricted database role, a read-only transaction and a 15-second query timeout."*

### 4 — Setup: purpose

**This is the screen that defines the product for this user. It should feel like the most important
step in the setup, not a footnote.** The card grows to **max-width 620px** here.

Title **"What should this assistant do?"**
Secondary line: *"Describe the job in your own words. This shapes which questions it suggests, what it
looks for, and how it writes every answer."*

**a. Four starting points** — a 2×2 grid of selectable cards, 12px gap, 16px padding each. These are
domain-agnostic on purpose; the product is not a college tool.
- **Analytics** *(active)* — "Understand trends, compare groups, spot outliers"
- **Operations** — "Monitor throughput, delays and bottlenecks"
- **Customers and revenue** — "Track usage, growth and churn"
- **Start from scratch** — "Write your own"

Selecting one rewrites the textarea below it. The textarea is always editable — the cards are a head
start, never a constraint.

**b. The textarea** — min-height **160px**, 16px padding, body font 15px / 1.65. Prefilled from the
selected card and fully editable:

> You are an academic analytics assistant. Analyse student performance, attendance, department statistics, and identify students who may require attention.

Below the textarea, a right-aligned mono 10.5px `ink-faint` character count: `184 / 2000`.

**c. Worked examples**, in a `sunken` block with 16px padding, mono 10.5px label `EXAMPLES FROM OTHER
USERS`, then **four** greyed sample purposes at 13px in `ink-soft`, each preceded by a small mono
`ink-faint` domain tag. **Draw all four, and make them maximally unrelated — this block is where the
user learns the field has no boundaries:**
- `PAYMENTS` — *"You are a merchant analytics assistant for a payments platform. Analyse transaction volume, settlement delays and refund patterns, and surface merchants whose usage is growing or declining."*
- `TRANSIT` — *"You are a network analyst for a metro system. Analyse passenger journeys by station and hour, identify overcrowded routes, and flag stations where footfall is falling."*
- `HEALTHCARE` — *"You are a hospital operations analyst. Track admissions, average length of stay and bed occupancy by ward, and flag wards running above capacity."*
- `LOGISTICS` — *"You are a fleet analyst. Track delivery times by region, identify routes with recurring delays, and flag carriers falling below SLA."*

**d. A live preview of the effect.** Beneath everything, a `surface` block with a 1px `rule` border and
20px padding, headed by a mono 10.5px `accent` label `WHAT IT WILL SUGGEST`. Inside, four small
question rows in `ink-mid`, matching the current purpose:
`Which students are at risk?` · `Compare attendance across departments` · `Which departments have declining performance?` · `Give me an overview of the college`

**This block is the whole point of the screen** — it closes the loop by showing the user that their
words changed something, before they commit. When the purpose text is edited, this block shows the
skeleton state from §6 for ~800ms, then refreshes.

Primary button: **"Connect and analyse"**.

### 5 — Understanding: analysing

Still the setup shell, but the card grows to **max-width 620px**.

Title **"Reading your database"**, secondary: *"This happens once. Every conversation reuses it."*

A vertical list of five steps, 16px apart, mono 12.5px. Steps that are done show a small `accent` check
and a result count on the right in `ink-faint`. The in-progress step shows a **pulsing 6px dot** in
`accent` and its text in `ink`. Pending steps sit at 40% opacity with a hollow circle.

```
✓  Connected to college_db                    32 ms
✓  Reading tables                            8 found
✓  Reading columns                          64 found
●  Mapping foreign keys                   ← in progress
○  Sampling row counts
```

A thin 2px progress bar sits at the top edge of the card, `accent` on `sunken`, at ~65%.

### 6 — Understanding: schema map

**This is the trust screen. Give it real care — it is where the user decides the product works.**

App shell. Full-width main area, `ground` background.

Header row: title **"Your database"**, and on the right two controls — a mono timestamp
`Last read 2 minutes ago` in `ink-faint`, and a secondary button **"Refresh schema"** with a refresh icon.

Below, a summary strip of four plain stats, no cards, separated by 48px, each a mono label above a
600-weight number: `8 TABLES` `64 COLUMNS` `9 RELATIONSHIPS` `12,480 ROWS`.

Then the map itself, on a `surface` panel with a `rule` border, min-height 480px, generous internal
padding (32px), with a faint 24px dot-grid background at 4% ink opacity.

Table nodes: `surface` cards, 1px `rule` border, 6px radius, **200px wide**, 16px padding.
- Header: table name at card-title size, and a mono row count on the right in `ink-faint`.
- A 1px divider.
- Up to 5 column rows, mono 11.5px: column name left in `ink-mid`, type right in `ink-faint`. A small `PK` or `FK` chip where relevant, in `accent` on `accent-soft`.
- If more columns exist: a final row reading `+ 6 more` in `accent`.

Draw **8 nodes** with real college tables — `students`, `departments`, `courses`, `enrollments`,
`attendance`, `exams`, `fees`, `placements` — arranged so edges do not cross.

Relationship edges: 1.5px `rule-strong` orthogonal lines (right angles, not curves) with a small
arrowhead at the foreign-key end, and a mono 10px label on the line itself:
`student_id`, `department_id`. **Never an unlabelled edge.**

Bottom-right of the panel, a floating legend on `surface` with the shadow: `PK primary key` ·
`FK foreign key` · `→ references`.

Primary button, bottom-right of the page: **"Start asking questions"**.

### 7 — Schema map: table selected

Same as 6, with `students` selected — its node takes an `accent` 2px border, and every edge connected
to it is drawn in `accent` while unconnected edges drop to 30% opacity.

A **360px right panel** slides in on `surface` with a left `rule` border and 24px padding:
- Table name as page title, mono row count beneath.
- Section label `COLUMNS`, then a full column list: name (mono, `ink`), type (mono, `ink-faint`), and chips for `PK` / `NOT NULL`.
- Section label `RELATIONSHIPS`, then plain-language sentences, not diagrams: *"Each student belongs to one department."* · *"A student has many attendance records."* — this is the self-explanatory rule applied to schema.
- A close X at the top right with a tooltip.

### 8 — Conversation: empty state

App shell.

**Sidebar** (280px, `surface`):
- Top: wordmark **Data Runtime** — a 26px accent square with a white glyph, then the name at 15px/600. 24px padding.
- **"New conversation"** button, full width, 40px tall, secondary style with a plus icon and a text label.
- Section label `CONVERSATIONS`, then list items at 36px tall, 10px horizontal padding, 6px radius. Each: a small message icon, a truncated title, and on hover a `sunken` background. The active one takes `accent-soft` with `accent` text.
- Bottom, above a `rule` divider: a **connection row** — a database icon, `college_db` in 13.5px, a `READ ONLY` mono chip, and a 6px green status dot with the label `Connected`. The whole row is clickable (artboard 14).

**Purpose bar** — a persistent strip across the top of the main area, 44px tall, `surface`, bottom
`rule` border, 24px horizontal padding. Left: mono 10.5px `ink-faint` label `ACTING AS`, then in 13.5px
`ink-mid` the first clause of the purpose, truncated with an ellipsis:
*"An academic analytics assistant analysing student performance and attendance…"*. Right: a text link
**"Edit"** in `accent`. **This bar appears on artboards 8–13 and 16.** It is how the user always knows
what stance the AI is taking, and it is the single most important expression of customization in the
running product.

**Main area**, centred, max-width 640px, vertically centred:
- A 44px `accent-soft` square with an `accent` glyph.
- Title, 24px/600: **"Ask anything about college_db"**
- Secondary line, max 60ch: *"I've read your 8 tables and how they connect. Ask a question and I'll investigate, then show you the answer."*
- **Four** suggestion cards in a 2×2 grid, 12px gap, each 20px padding, `surface`, 1px `rule`, hover to `accent-line` border. Each card: the question in 14px `ink`, and beneath it in mono 10.5px `ink-faint` the tables it will touch.
  - *"Give me an overview of the college"* — `students · departments · attendance`
  - *"Compare attendance across departments"* — `attendance · departments`
  - *"Which students are at risk?"* — `students · attendance · exams`
  - *"Show me placement statistics"* — `placements · students`
- **Note for the designer:** these are generated from **the schema *and* the purpose together** — not from a fixed list. The same database configured as a fees-administration assistant would suggest *"Which students have outstanding fees?"* instead. Never draw generic examples like "Show all employees"; purpose-derived questions are the clearest proof that the user's configuration took effect.

**Composer**, pinned to the bottom of the main area, max-width 820px, 24px above the bottom edge:
- `surface`, 1px `rule` border, 6px radius, the one shadow, 8px padding.
- Textarea, min 48px tall, placeholder *"Ask a question about your data…"*.
- Below, a row: left, mono 10.5px `ink-faint` `Enter to send · Shift+Enter for a new line`; right, a 32px square send button, `accent` background, white arrow, disabled to `sunken` when empty.

### 9 — Conversation: thinking

The hero of the loading story. The user has asked *"Compare attendance across departments."*

- The user turn sits right-aligned, `sunken` background, 1px `rule`, 12px/16px padding, max-width 70%, 6px radius.
- 32px below, the assistant turn begins with **only the trace** — no answer yet.

**Trace component**, full width of the column, `surface`, 1px `rule`, 6px radius:
- Header, 12px/16px padding, `sunken` background, bottom `rule`: left, a pulsing 6px `accent` dot and mono 11px **`Investigating`**; right, mono 11px `ink-faint` `4 of 6 · 1.8s`.
- Body, 16px padding, steps 10px apart, mono 11.5px, in a three-column grid — status glyph (14px) / description / duration right-aligned in `ink-faint`.

```
✓   Understood the question — compare one metric across a group      40 ms
✓   Chose 3 of 8 tables — attendance, students, departments          12 ms
✕   Checked the query — column "dept_name" doesn't exist. Fixing.      8 ms
✓   Checked the query — syntax, schema and read-only permission      11 ms
●   Running the query…                                          ← spinner
○   Building the answer
```

The failed step's text is `critical`. **Do not hide it.** A visible self-correction is the single most
persuasive thing on this screen.

Below the trace, **skeletons** for what is about to render: a 4-up KPI skeleton row and a chart
skeleton. See §6 for skeleton style.

### 10 — Conversation: the complete answer ★

**The most important artboard. Draw it in both light and dark.**

Assistant turn, stacked with **16px** between blocks, in this exact order:

**a. One lead sentence** — body 15px, `ink`, never more than two lines:
*"Average attendance is 78.7% across four departments, and the spread is wide — 15 points between the highest and lowest."*

**b. The trace, collapsed.** Now a single 40px row: `surface`, 1px `rule`, 12px/16px padding. Left, a
small chevron pointing right and mono 11px `ink-soft` **`Execution trace`**. Right, mono 11px
`ink-faint` `6 steps · 1 correction · 2.4s`. Clicking expands it to the artboard-9 form. The collapsed
state is the default — the detail is available, not imposed.

**c. KPI group** — four KPIs in one row, joined as a single bordered strip divided by 1px `rule` lines
(not four separate floating cards). Each cell 20px padding:
- `78.7%` / label `AVERAGE ATTENDANCE`
- `4` / label `DEPARTMENTS`
- `512` / label `STUDENTS`
- `71%` / label `LOWEST — EEE` / and a delta line in mono 11px `critical`: `▼ 15 pts below CSE`

**d. Bar chart** — `surface`, 1px `rule`, 20px padding.
- Card title: **"Average attendance by department"**, and beneath it a mono 10.5px `ink-faint` subtitle: `Spring term 2026 · 512 students`.
- Horizontal bars, 20px tall, 12px apart. Each row is a three-column grid: category label (mono 11.5px, 60px wide, right-aligned), the bar track (`sunken`), and the value (mono 12px, `ink`, tabular, right-aligned, 48px).
- Bars use `accent`. **EEE uses `critical`** because it is the finding. No other colour appears.
- A faint vertical gridline at 25/50/75/100 in `rule` at 50% opacity, behind the bars. No axis box, no legend — the labels are on the rows.
- CSE 86% · IT 82% · ECE 76% · EEE 71%.

**e. Insight card** — `accent-soft` background, 1px `accent-line` border, 16px/20px padding.
Mono 10.5px `accent` label `KEY FINDING`, then body 14px `ink-mid`:
*"EEE has the lowest average attendance at 71%, trailing CSE by 15 points. IT is second-highest overall but is the only department trending downward across the last three terms."*

**f. Follow-up chips** — a row of three small secondary chips, 32px tall: *"Why is IT declining?"* ·
*"Which EEE students are worst affected?"* · *"Show this by month"*.

Then the composer, as in artboard 8.

### 11 — Conversation: multi-step investigation

Question: *"Why is attendance dropping in IT?"* Same structure as 10, but demonstrating depth:

- An **expanded** trace with **11** steps across four labelled phases. Insert mono 10px `ink-faint`
  phase separators between groups: `TREND`, `COMPARISON`, `BREAKDOWN`, `CONCLUSION`. Each phase's
  steps are indented 16px beneath it.
- Then a **line chart** — six months on the x-axis, two series: `IT` in full-strength `accent` with
  visible 4px endpoint dots, and `All departments` in the third chart tint, 1px dashed. A faint
  horizontal gridline every 5 points. Axis labels in mono 10.5px `ink-faint`. A minimal two-item
  legend above the plot, left-aligned, using 8px squares.
- Then a **ranking** component — five affected courses, each row: rank numeral in mono `ink-faint`,
  course name, a thin 4px inline bar, and the value. 12px row padding.
- Then the insight card carrying the conclusion.

### 12 — Conversation: failure states

One artboard, three stacked variants with 32px between them. Each is an assistant turn.

**12a — Not answerable.** No chart, no table. A short trace showing two green steps, then body text:
*"I looked at students, attendance and courses. There's no table recording tuition payments, so I can't answer this from your current database."* Below, a mono 11px `ink-faint` line: `Tables checked: students · attendance · courses`.

**12b — Timeout.** An **alert** component: `critical-soft` background, 3px `critical` left border, 16px/20px padding. Mono label `QUERY TIMED OUT` in `critical`, then body: *"That query ran longer than 15 seconds and was stopped. Try narrowing it to a single term or department."* Beneath, a collapsed SQL viewer so the user can see and adapt what was attempted.

**12c — Row cap.** A normal table component, but with a `sunken` banner across its top edge, 10px/16px padding, mono 11px: `Showing the first 500 of 12,480 rows` and, on the right, a text link **"Download full CSV"**.

### 13 — Conversation: sidebar populated

Same as 8 but with **seven** conversations in the sidebar, real titles derived from first questions
(*"Overview of the college"*, *"Attendance by department"*, *"Students at risk"*, *"Why IT is declining"*,
*"Placement statistics"*, *"Fee collection by term"*, *"Top projects by department"*), grouped under two
mono section labels: `TODAY` and `EARLIER`. The fourth item is active.

### 14 — Connection panel

Triggered from the sidebar's connection row. A **420px** right-side panel on `surface`, left `rule`
border, the one shadow, 24px padding, sections 32px apart.

- Title **"Connection"**, close X top-right with tooltip.
- `DATABASE` — `college_db` in 15px, with `localhost:5432` in mono `ink-faint` beneath. A green dot and `Connected`.
- `ACCESS` — a `READ ONLY` chip and a plain-language line: *"Data Runtime can query your data but can never change it."*
- `PURPOSE` — **the most prominent section in this panel.** The prompt in an editable textarea, min-height 140px, with a character count beneath. A **"Save"** button, enabled only once the text changes. Below it, the same `WHAT IT WILL SUGGEST` preview block from artboard 4, so editing the purpose visibly changes something before the user commits. A mono 10.5px `ink-faint` note: `Applies to every conversation on this connection.`
- `SCHEMA` — `8 tables · 64 columns · read 2 minutes ago`, a **"Refresh schema"** secondary button, and a **"View schema map"** text link.
- Bottom, separated by a `rule`: a **"Disconnect"** button in `critical` text on transparent, with a bordered `critical` outline. Never a filled red button — destructive actions should be findable, not inviting.

### 15 — Component library

A reference sheet, not a screen. A dark-theme artboard on `ground`, arranged in a 3-column grid with
40px gutters and mono section labels above each group.

**Row 1 — GenUI registry (the 8 components).** Each rendered at real size with real college data and
its `type` name in mono beneath it:
`kpi` · `kpi_group` · `table` · `bar_chart` · `line_chart` · `ranking` · `insight` · `alert`

**Row 2 — Chat chrome.** `trace` collapsed · `trace` expanded · `sql_viewer` (collapsed and expanded,
SQL in mono 12.5px with a copy button) · user message · composer · suggestion card · follow-up chip.

**Row 3 — Loading states.** Every skeleton from §6, side by side with the component it stands in for.

**Row 4 — Atoms.** Buttons (primary / secondary / ghost / destructive, each in default, hover, focus,
disabled and loading), inputs (default, focused, error, disabled), chips (`PK`, `FK`, `READ ONLY`,
`RECOMMENDED`, `COMING SOON`), status dots, and the full colour ramp as labelled swatches.

### 16 — The same product, unrelated data ★

**Draw this immediately after artboard 10 in the canvas layout, side by side if the space allows. The
pair is the argument: identical components, identical layout, a completely different product.**

A payments company has connected their database and written a different purpose. Everything structural
is byte-for-byte the same as artboard 10 — only the content changes.

**Purpose bar:** `ACTING AS` — *"A merchant analytics assistant tracking transaction volume, settlement delays and merchant growth…"*

**Sidebar:** connection reads `payments_prod`, `READ ONLY` chip, `Connected`. Conversations are titled
*"Merchant growth this quarter"*, *"Settlement delays by bank"*, *"Refund spike investigation"*,
*"Top merchants by volume"*.

**User turn:** *"Which merchants are growing fastest this quarter?"*

**Assistant turn**, same six blocks in the same order:

**a. Lead sentence** — *"Transaction volume grew 12.4% quarter over quarter, but the growth is concentrated — the top 20 merchants account for 61% of it."*

**b. Collapsed trace** — `7 steps · 2.9s`. When drawn expanded elsewhere, its steps read in the domain's
own language: *"Chose 4 of 6 tables — merchants, transactions, settlements, refunds"*.

**c. KPI group**, four cells:
- `₹4.2 Cr` / `TOTAL VOLUME — Q1`
- `1,284` / `ACTIVE MERCHANTS`
- `12.4%` / `QOQ GROWTH`
- `47` / `MERCHANTS DECLINING` / delta in `critical`: `▼ 8% avg volume drop`

**d. Bar chart** — *"Volume growth by merchant category"*, subtitle `Q1 2026 · 1,284 merchants`.
Quick commerce 34% · Travel 21% · Education 14% · SaaS 9% · Subscriptions −8%.
The negative bar is `critical` and extends left of a zero baseline. Everything else is `accent`.

**e. Insight card** — *"Quick-commerce merchants grew 34% quarter over quarter while subscription merchants declined 8%. The decline is concentrated in 47 accounts, all still on the legacy weekly settlement schedule."*

**f. Follow-up chips** — *"Why are subscription merchants declining?"* · *"Show settlement delays for those 47"* · *"Break this down by month"*

**Nothing about the interface was rebuilt for this customer.** The components, spacing, palette and
loading states are identical. Only the schema and the purpose differ. Make that unmistakable — if a
viewer can tell artboards 10 and 16 came from the same system at a glance, this artboard has done its job.

### 17 — Six domains, one product ★

**The artboard that carries the core product claim.** A reference sheet on `ground`, not a screen.
A 3×2 grid of tiles, 32px gutters, each tile on `surface` with a 1px `rule` border and 24px padding.

Six unrelated businesses, drawn side by side. **No two should look like they belong to the same
industry** — the visual shock of the variety is the entire point, and it is what communicates that the
list is illustrative rather than exhaustive.

Each tile contains, stacked with 16px gaps:
1. A mono 10.5px `ink-faint` domain tag and, beneath it, the database name in mono 12px `ink`.
2. The purpose in 13px `ink-mid`, italic, two lines maximum.
3. Mono 10.5px `accent` label `SUGGESTS`, then three generated questions as small rows in `ink-mid`.
4. A compact insight card at real size, holding the one finding that purpose would lead with.

| Tag | Database | Purpose | Suggests | Leads with |
|---|---|---|---|---|
| `EDUCATION` | `college_db` | *"Analyse student performance and attendance, and identify students who may need attention."* | Which students are at risk? · Compare attendance across departments · Why is IT attendance dropping? | *"23 students have attendance below 60% and at least one failed exam. 14 are in EEE."* |
| `PAYMENTS` | `payments_prod` | *"Analyse transaction volume and merchant activity, and surface merchants whose usage is growing or declining."* | Which merchants are growing fastest? · Settlement delays by bank · Where are refunds spiking? | *"Quick-commerce merchants grew 34% QoQ while subscriptions fell 8%, concentrated in 47 accounts."* |
| `TRANSIT` | `metro_ops` | *"Analyse passenger journeys by station and hour, identify overcrowded routes, and flag stations where footfall is falling."* | Which stations are busiest at peak? · Which line is most crowded? · Where is footfall declining? | *"Line 2 runs at 118% of seated capacity between 08:00 and 09:30, worst at Central."* |
| `HEALTHCARE` | `hospital_db` | *"Track admissions, length of stay and bed occupancy by ward, and flag wards running above capacity."* | Which wards are over capacity? · Average length of stay by ward · Readmissions this quarter | *"Cardiology has run above 95% occupancy for 19 consecutive days."* |
| `LOGISTICS` | `fleet_db` | *"Track delivery times by region, identify routes with recurring delays, and flag carriers below SLA."* | Which routes are slowest? · Which carriers miss SLA? · Delivery times by region | *"Three carriers are below the 95% SLA, all on the western corridor."* |
| `RETAIL` | `store_ops` | *"Analyse sales by category and store, track returns, and surface products whose sales are falling."* | Which categories are declining? · Return rate by product · Best performing stores | *"Returns on footwear reached 14%, triple the catalogue average."* |

Render these as six real designed tiles. The table above is the content brief only.

Beneath the grid, a single line of body text, centred, `ink-soft`, max 60ch:
*"Same components. Same layout. Nothing was built for any of these."*

### 18 — One database, three purposes

The companion claim to artboard 17. Where 17 shows that **any schema** works, this shows that the
**purpose alone** reshapes the product even when the schema is held fixed. A reference sheet on
`ground`, not a screen. Three columns, 40px gutters, each headed by a mono `ink-faint` label. All three
run against the same college database.

Each column contains, stacked with 24px gaps:

1. A `sunken` block, 16px padding, holding the purpose text at 13px in `ink-mid`.
2. Mono 10.5px `accent` label `SUGGESTS`, then the four generated questions as small rows.
3. Mono 10.5px `accent` label `LEADS WITH`, then one insight card rendered at real size.

| | **Registrar** | **Finance office** | **Placement cell** |
|---|---|---|---|
| **Purpose** | *"Analyse student performance and attendance, and identify students who may need attention."* | *"Track fee collection, outstanding balances and payment delays by department and term."* | *"Analyse placement rates, recruiter activity and which courses lead to the best outcomes."* |
| **Suggests** | Which students are at risk? · Compare attendance across departments · Why is IT attendance dropping? · Overview of the college | Which departments have the most outstanding fees? · Fee collection by term · Which students are overdue? · Total collected this year | What is the placement rate by department? · Which recruiters hire the most? · Which courses lead to the best offers? · Placement trend over three years |
| **Leads with** | *"23 students have attendance below 60% and at least one failed exam this term. 14 of them are in EEE."* | *"₹18.4 lakh remains outstanding across 312 students, 61% of it more than 60 days overdue."* | *"78% of CSE students were placed this year against a 61% college average. IT placements fell 9 points."* |

Render the table above as three real designed columns, not as a table. The table here is the content
brief only.

---

## 6. Loading states — required, specified

Nothing renders without a loading state that precedes it. Four kinds, and only four.

**Skeleton** — for content whose shape is known in advance. This is the default.
- `sunken` fill, 4px radius, matching the exact dimensions of the real element.
- A slow shimmer: a 20%-opacity `surface` gradient band sweeping left to right over **1.6s**, ease-in-out, infinite.
- Skeletons match the real thing's geometry. A KPI skeleton is a 30px-tall bar over a 10px label bar. A table skeleton is a real header row plus five rows of varied-width bars (never all the same width — uniform bars read as a broken layout). A bar-chart skeleton is four horizontal bars of different lengths on a real track.

**Inline spinner** — for a user-initiated action in progress. A 14px, 2px-stroke ring, 270° arc, `accent`, rotating at 700ms linear. It sits **inside** the button that triggered it, and the button's text changes to the present participle: "Test connection" → "Testing…". The button stays the same width — reserve the space so nothing shifts.

**Pulsing dot** — for a live step in a sequence. A 6px `accent` circle, opacity 1 → 0.35 → 1 over 1.4s. Used only for the current trace step and the current discovery step.

**Progress bar** — for a bounded multi-step process with a known total. A 2px bar, `accent` on `sunken`, only on the discovery screen.

**Forbidden:** a full-page spinner, a blocking overlay, a bare "Loading…" with no shape, a layout that jumps when content arrives. Reserve the final dimensions in every skeleton.

Under `prefers-reduced-motion`, every animation above becomes a static 60%-opacity state.

---

## 7. Content rules

Write every string on these artboards as production copy.

- **Active voice, present tense.** "Reading your database", not "Database is being read".
- **Buttons name their outcome.** "Connect and analyse", not "Submit". "Refresh schema", not "Refresh".
- **Never apologise in an error.** State the fact and the fix.
- **Numbers always carry a unit and a label.**
- **Plain language in the trace.** "Checked the query against your schema" — never a function name, never a stack trace, never a raw `error_type`.
- **No emoji anywhere in the interface.**
- **Vocabulary follows the purpose, always.** The interface has no fixed nouns of its own. An answer for a registrar says *students*, *attendance*, *at risk*; the same components for a payments company say *merchants*, *volume*, *declining*. Never write domain-neutral filler like "Records" or "Items" — the whole point is that the product speaks the user's language.
- Real college data on artboards 1–13: departments are CSE, IT, ECE and EEE; the term is Spring 2026; there are 512 students across 8 tables.
- Real payments data on artboard 16: 1,284 merchants, ₹4.2 crore quarterly volume, Q1 2026, 6 tables.
- Artboards 17–18 carry their own domain data as specified. Every figure on them should read as if it came from a real query — never round numbers, never `123`.

---

## 8. What not to design

- No separate canvas, dashboard page, or split chat/results view. Generated UI is **inline in the conversation**, always.
- No settings page — connection settings and the purpose editor live in the panel on artboard 14.
- **No per-conversation purpose.** The purpose belongs to the connection and applies to every conversation on it. A user who wants a different angle just asks a different question — do not design a second, per-chat configuration surface.
- No multi-database switching. One connection at a time in the MVP; the sidebar connection row is the affordance for it later, not a switcher now.
- No authentication, no user profile, no billing, no onboarding tour, no notifications.
- **No domain picker, no industry template gallery, no vertical-specific screen.** The user types a sentence describing their job; that sentence is the entire configuration surface. A dropdown of industries would turn an open system into a closed one.
- No component types beyond the eight listed. No heatmaps, no timelines, no gauges, no donut charts.
- No gradients, no glassmorphism, no glow, no decorative illustration, no hero imagery.
- No third or fourth accent colour anywhere, including in charts.
