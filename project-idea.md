# Data Runtime

> The project in plain terms — what it is, how the backend works, how the frontend works.
> Companion docs: `design-brief.md` (visual spec, 18 artboards) and the technical
> assessment (defects, risks, phased plan).

---

## 1. What it is

You connect Data Runtime to your database and tell it, in your own words, what you want it
to do. It reads your database, works out how everything fits together, and then you just
ask it questions. It investigates, checks its own work, and answers with charts and
numbers rendered directly in the chat.

**In one line:** connect your database, describe the job, ask questions, get answers
built out of real UI instead of paragraphs.

The important part is that **nothing about it is built for a specific industry.** Point it
at a college database and it talks about students and attendance. Point it at a payments
platform and it talks about merchants and settlements. Point it at a metro network and it
talks about stations and passenger footfall. The system has no idea what business you are
in until you tell it — and the only two things that tell it are **your database schema**
and **the description you wrote at setup**.

## 2. What makes it different from "chat with SQL"

Four things, and the product is the combination of all four. Any one alone is a demo.

**It understands your database once.** Most tools re-read the schema on every question.
This one reads it at setup, stores it, and shows it back to you as a map so you can
confirm it got it right before you trust a single answer.

**It investigates instead of translating.** A hard question doesn't become one query. The
agent looks at the trend, compares groups, drills into the worst one, and then concludes —
several queries, in sequence, each informed by the last.

**It checks its work before touching your data.** Every generated query is validated
first. When validation fails, the error goes back to the model, which fixes the query and
tries again. You see the correction happen in the trace, which is far more convincing than
a system that never appears to fail.

**It builds the answer's interface.** Rather than writing a paragraph, the AI chooses from
a fixed set of components — KPI, chart, ranking, insight — and the frontend renders them
inline in the conversation.

## 3. What a user actually does

1. **Connect.** Pick PostgreSQL, enter local database credentials, test the connection, choose read-only.
2. **Describe the job.** *"You are an academic analytics assistant. Analyse student performance and attendance, and identify students who may need attention."* The screen immediately shows what it will suggest, so you can see your words landed.
3. **Watch it read the database.** Five to fifteen seconds, once. It ends on a map of your tables and how they connect.
4. **Ask questions.** *"Compare attendance across departments."* A trace appears and ticks forward while it works.
5. **Get an answer built from components.** A lead sentence, KPIs, a chart, and the key finding — all inside the chat message.

## 4. The two rules that hold everything together

**Rule 1 — Only two things know your domain.** The schema snapshot and your purpose text.
No prompt, no example, no fixture, no UI label anywhere else may mention students,
merchants or anything domain-specific. If a string in the interface couldn't survive
swapping the database for a hospital's, it's a bug.

**Rule 2 — The database enforces permissions, not Python.** Read-only means connecting as
a Postgres role that only has SELECT, inside a read-only transaction, with a query
timeout. The validator still checks permissions, but only to give the model fast feedback
so it can correct itself — it is not the thing standing between the AI and your data.

---

# BACKEND

## 5. Stack

| Piece | Choice | Why |
|---|---|---|
| API | FastAPI | Already in use; async handlers and SSE come free |
| Agent loop | LangGraph | Already in use; the loop shape is correct |
| Database driver | psycopg (pooled) | Replacing the current single shared connection |
| SQL parsing | sqlglot | Already in use for validation, pinned to the postgres dialect |
| Agent model | Claude Sonnet 5 | Multi-step tool use, reliable corrections |
| UI-spec model | Claude Haiku 4.5 | One small structured-output call per answer; cheap and fast |
| App storage | PostgreSQL | Conversations, snapshots, connections |

## 6. What happens when someone asks a question

```
1. Build context      history + stored schema snapshot + purpose
                      ← no database hit
2. Pick tables        from the snapshot, not by querying information_schema
3. Write a query      the model emits it as a tool call
4. Validate           syntax → semantic → permission → safety
                      ✗ → the error goes back to the model → return to 3  (max 3 tries)
5. Execute            read-only transaction · 15s timeout · 500-row cap
                      ✗ → the database error also goes back → return to 3
6. Read results       needs another angle? → return to 3.  Done? → continue
7. Compose UI spec    a SECOND model call, JSON-schema'd
8. Bind and check     spec columns verified against the real result columns
9. Persist and stream message + ui_spec + trace
```

**Steps 3–6 are a loop, not a line.** Two loops share the same machinery:
- the **correction** loop — validation failed, fix and retry
- the **investigation** loop — results came back but the question needs another step

Total steps are capped at ~8 so a confused model can't spin forever.

## 7. Modules

```
backend/src/
  datasource/        the database boundary
    base.py            protocol: introspect() / validate() / execute()
    postgres.py        the one implementation for the MVP
  knowledge/
    snapshot.py        tables, columns, PKs, FKs, row counts → JSONB, stored once
    questions.py       snapshot + purpose → four suggested questions
  validator/         syntax · semantic · permission · safety, each returning error_type
  agent/
    tools.py           the three tools the model can call
    trace.py           structured step records for the UI
  genui/
    spec.py            second model call producing the UI specification
    bind.py            validates the spec against real result columns
  graph/             the LangGraph loop: call_llm ↔ execute_tools
  db/chat_store.py   conversations, messages, connections, snapshots
  llm/client.py      model client
api.py               /setup · /schema · /chats · SSE /chat/stream
```

Deleted from the current codebase: `mcp_server.py` (an MCP wrapper nothing speaks MCP
to), `main.py` (a superseded CLI), the root `api.py` shim, and `config/permissions.json`
(a global file that can't express per-connection permissions).

## 8. Data model

| Table | Holds |
|---|---|
| `users` | email and a scrypt password hash |
| `auth_sessions` | session tokens, stored hashed, with an expiry |
| `connections` | database details, permission level, **and the purpose text** |
| `schema_snapshots` | the understood schema as JSONB, one per connection, timestamped |
| `chat_sessions` | conversation id, **user id**, title, timestamps |
| `chat_messages` | role, content, sql, data, **ui_spec**, **trace** |
| LangGraph checkpoints | agent working state, managed by the library |

The purpose lives on the **connection**, not the conversation — every chat against that
database inherits it.

**One connection per user, and `connection_id` *is* the user's id.** That single decision
is what makes the rest per-user for free: the snapshot and the purpose already hung off the
connection, so they came along. Only `chat_sessions` needed a column of its own.

The signed-in user reaches deep code - the snapshot reader, the tools, the prompt builder -
so it travels in a ContextVar set by one middleware rather than as an argument threaded
through every call site. `ConnectionStore()` still means "this user's connection".

Two caches that used to be process-wide are now keyed per user, because users connect to
different databases: the data source, and the system prompt. The psycopg pool is keyed by
DSN for the same reason - a shared pool would hand one user's query to another user's
database.

## 9. The three tools the model has

- `get_schema()` — returns the stored snapshot. Never queries the database.
- `run_query(sql)` — validates, then executes. Returns rows, or a structured error.
- `finish(summary)` — the model signals it has enough to answer.

`run_query` returning an error is not a failure — it is the mechanism. The error carries
an `error_type` (`syntax` / `semantic` / `permission` / `safety`) so the model knows
whether to fix and retry or to stop and explain.

## 10. Validation, in plain terms

Four checks, in order, before anything reaches the database:

1. **Syntax** — is this valid PostgreSQL? (sqlglot, pinned to the postgres dialect)
2. **Semantic** — do these tables and columns actually exist in the snapshot? Must handle CTEs and joins correctly; the current implementation rejects every CTE, which breaks exactly the analytical queries this product needs.
3. **Permission** — is this operation allowed here? Fast feedback only; the real gate is the database role.
4. **Safety** — no DROP, no TRUNCATE, no ALTER, no DELETE or UPDATE without a WHERE.

## 11. Generative UI, in plain terms

After the data comes back, a second small model call decides how to show it. It returns a
JSON specification, not code and not React.

**The specification must never contain the data.**

```jsonc
// ✗ wrong — the model retypes the numbers and will eventually get one wrong
{ "type": "bar_chart", "data": [ { "dept": "CSE", "v": 86 } ] }

// ✓ right — the model chooses shape and columns; the rows never left the server
{ "type": "bar_chart", "source": "step_5", "x": "dept_name", "y": "avg_attendance" }
```

The server then checks that `source`, `x` and `y` actually exist in that step's results
and silently drops any component that doesn't bind. That is self-healing for the UI layer,
and it costs about thirty lines.

**The eight components:** `kpi`, `kpi_group`, `table`, `bar_chart`, `line_chart`,
`ranking`, `insight`, `alert`. No more for the MVP — each extra type adds prompt tokens
and gives the model another way to choose wrongly.

## 12. Security model

The validator is fast feedback for the model. The gate is the database, and it
has to be a real one on both engines — a validator bug must not be the only
thing between the model and the data.

**PostgreSQL** — two independent layers:

- Read-only connections use a Postgres role granted only SELECT.
- Every query runs inside `SET TRANSACTION READ ONLY`, set on the pooled connection.
- `statement_timeout = 15s`, enforced by the database.

A write that slipped past the validator still dies at the server. `test_phase1.py`
asserts this by bypassing the validator entirely.

**MongoDB** — one layer, so setup has to protect it:

- There is no read-only connection in MongoDB; nothing corresponds to
  `default_transaction_read_only`. **The user's role is the only gate.**
- So `check_connection` refuses credentials that can write, and says how to fix
  it. Anything but `read` / `readAnyDatabase` counts as writable, and a server
  with no access control at all is refused too. Connect as:
  `db.createUser({user: "reader", pwd: "…", roles: [{role: "read", db: "<database>"}]})`
- `maxTimeMS = 15s` and the row cap are passed per operation rather than
  configured on the connection, so a new call site must remember them.

**Both:**

- Results capped at 500 rows; the model is told when a cap was applied.
- Write mode is **not** in the MVP. The `permission` field stored on a connection
  is display-only — nothing branches on it yet.
- Row data flows into the model's context, so a value could contain instructions. Read-only mode is what makes this survivable.
- The application's own tables - `users` and `auth_sessions` among them - are stripped from
  every snapshot. In local development the app database and the user's database are the same
  one, so without that the model would be handed a table of password hashes.

Every collection a pipeline touches is checked against the snapshot, not just the
one it runs on: a `$lookup` or `$graphLookup` reads its `from` collection just as
directly, at any nesting depth.

---

# FRONTEND

## 13. Stack

React 19 · Vite · TypeScript · Tailwind v4 · lucide-react · react-markdown.
All already in the project and all staying.

**No chart library.** With only bar and line charts in the MVP, bars are CSS divs and a
line chart is about sixty lines of SVG. That avoids a dependency, a theming fight, and a
bundle — and gives exact control over the two-colour palette. Reach for Recharts only if
the component set grows.

## 14. Screens

| Screen | Purpose |
|---|---|
| Setup wizard (4 steps) | database type → credentials → access level → **purpose** |
| Analysing | live progress while the schema is read, once |
| Schema map | tables as nodes, foreign keys as labelled edges — the trust screen |
| Conversation | the main product; sidebar + chat + composer |
| Connection panel | connection details, permission badge, editable purpose |

There is **no dashboard and no side canvas**. Generated UI appears inside the chat message.

## 15. Structure

```
frontend/src/
  pages/
    Setup.tsx          the four-step wizard
    Schema.tsx         the schema map
    Home.tsx           the conversation (exists today)
  components/
    Sidebar.tsx        conversations + connection row      (exists)
    ChatWindow.tsx     message list + composer             (exists)
    MessageBubble.tsx  renders one turn                    (exists, extended)
    PurposeBar.tsx     the persistent "Acting as …" strip  (new)
    TraceView.tsx      execution steps, collapsed by default (new)
    SqlViewer.tsx      collapsible SQL                     (exists)
    genui/
      Renderer.tsx     switch on spec.type → component     (new)
      Kpi · KpiGroup · Table · BarChart · LineChart · Ranking · Insight · Alert
      skeletons/       one per component                   (new)
  hooks/useChat.ts     conversation state, SSE             (exists, extended)
  services/api.ts      fetch wrappers                      (exists)
```

`QueryResult.tsx` becomes the GenUI `table` component. `SqlViewer` moves inside the trace.

## 16. How a message renders

The backend sends a message carrying `content`, `trace`, `ui_spec` and the result sets.
`MessageBubble` renders, in this order:

1. **Lead sentence** — one or two lines of text, never a wall
2. **Trace** — collapsed to a single row: `6 steps · 1 correction · 2.4s`
3. **Components** — `ui_spec.components.map(spec => <Renderer spec={spec} />)`
4. **Follow-up chips**

`Renderer` is a switch on `spec.type`. It looks up the rows by `spec.source`, reads the
columns named by `spec.x` / `spec.y`, and renders. **The frontend never receives arbitrary
code** — only a spec naming one of eight known types.

This composition already exists today: `MessageBubble` currently renders text, then
`SqlViewer`, then `QueryResult`. We are extending a working pattern, not inventing one.

## 17. Streaming

The answer takes 3–40 seconds, so `/chat/stream` is Server-Sent Events and the UI builds
up as events arrive:

```
step      → append a row to the trace
step      → …
result    → a result set is ready
spec      → render the components
done      → collapse the trace, show follow-up chips
```

Without this, a correct forty-second answer looks like a hung app. Streaming is not
polish here; it is the difference between "thinking" and "broken".

## 18. Loading states

Nothing renders without a loading state first. Four kinds, and only four:

- **Skeleton** — shape-matched shimmer, for content whose shape is known (KPIs, tables, charts)
- **Inline spinner** — inside the button that triggered it; the button keeps its width so nothing shifts
- **Pulsing dot** — the current trace step, and the current step while the schema is read
- **Progress bar** — only on the schema-reading screen, where the total is known

Never a full-page spinner. Never a layout that jumps when content arrives.

---

## 19. Not in the MVP

Write mode · more than eight components · a bespoke planner · cross-conversation memory ·
saved dashboards · cloud databases · a separate canvas · per-conversation purpose override ·
more than one saved connection per account · a domain picker or industry templates ·
domain classification.

Delivered since, out of the original order: MongoDB, and accounts. Accounts were listed
here as out of scope and were built anyway, on request - so the two rules in section 4 now
have a third companion: **a user sees only what hangs off their own account.** Nothing
else about the product changed.

## 20. Build order

| Phase | Work |
|---|---|
| **0** | Repair — send the system prompt, add `rollback()`, pin the dialect, rotate the leaked key, delete dead files |
| **1** | Foundation — connection pool, read-only role, timeouts, row cap, CTE and join validation, seed data (plus two throwaway schemas from unrelated domains as a domain-leakage check) |
| **2** | Understanding and purpose — `DataSource`, snapshot, setup wizard, schema map, purpose capture and threading, suggested questions |
| **3** | Streaming and trace — SSE, structured steps, step budget |
| **4** | Generative UI — spec call, binding validation, eight components, renderer |
| **5** | Polish — the *Acting as* bar, error surfaces, connection panel, both themes |
| **6** | MongoDB — only if 4 and 5 are genuinely finished |

Phase 0 exists because three things are currently broken in ways that block everything
else: the system prompt never reaches the model, a failed query poisons the shared
connection so retries can't work, and every CTE is rejected by the semantic validator.
