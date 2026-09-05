# Datalyst — settlement reconciliation

**In one sentence:** a payment company's records and its bank's records never
quite agree, and this finds every disagreement — using ordinary rules for 99% of
it, and an AI for the small part rules genuinely cannot do.

---

## The problem, for anyone

Imagine you run an online shop.

Every time a customer pays, your system writes down: *"we took ₹2,612 from
order 59794."* That's **your book**.

A few days later, the payment company (Razorpay, PayU, Cashfree) actually sends
you the money — and a file listing what they sent. That's **their book**.

The two books never match exactly. Real reasons:

| What went wrong | What it looks like |
|---|---|
| They kept their fee | You expected ₹2,612, you got ₹2,557 |
| The reference got mangled | Your `ORD-59794` comes back as `ord no 59794` |
| It arrived late | You captured it Monday, it settled Thursday |
| One payment, three transfers | Your ₹9,000 arrives as ₹3,000 × 3 |
| They said nothing at all | ₹15,833 arrives labelled `neft/kartly/65527/06` |

Somebody has to sit down and work out which line means which payment. At a real
company, that person spends a week a month doing it, and the money that can't be
matched just sits there — unexplained.

**That's what this project does automatically.**

## How it works — three steps

**1. Rules do almost all of it.**
Five layers of ordinary matching logic — exact reference, fuzzy reference,
date-shifted, split payments, fee and currency differences. No AI. Just
comparisons. This handles **98.95%** of the lines.

**2. The AI gets only what's left.**
A few dozen lines have no reference at all — just a sentence a human would have
to read. *That* is the only thing the AI is asked to do: read the sentence, look
up the ledger, and say which payment it thinks this is.

**3. A person decides.**
The AI **cannot change anything**. It can only suggest. A human reviews the
suggestion — along with the exact evidence behind it — and clicks Approve. Only
then does a separate piece of code write the result down.

## Why you can trust it with money

This is the part that matters, and every line of it is enforced by the database
or by an automated test, not by good intentions:

- **The AI physically cannot write.** It connects to the database with an
  account that has no permission to change anything.
- **Approving is not applying.** Two separate buttons, two separate steps.
- **Evidence is re-checked before anything is written.** If the underlying data
  changed since the suggestion was made, applying it fails on purpose.
- **Doing it twice does nothing twice.** Loading the same file again, or
  applying the same decision again, is safely ignored.
- **Everything is logged, permanently.** The record of who decided what cannot
  be edited or deleted by anyone, including an administrator.
- **Every applied decision can be reversed.**

There is a test suite that tries **eleven different ways** to sneak a change
into the ledger without a human approving it. All eleven are refused.

## What you actually see

A queue. Each row is one unexplained line: what the bank said, why it's stuck,
how much money it is, and — if the AI has a suggestion — what it proposes and
why. You open a row, read the evidence, and approve or reject it.

There is also a chat box. You can ask the same database questions in plain
English — *"what is the total value of open exceptions by gateway?"* — and it
writes the query for you. It's read-only, so it can look but never touch.

---

## The numbers

These are measured, not claimed. The test data is generated *from* the ledger,
so the correct answer for every single line is known in advance — which means
accuracy can be calculated rather than estimated. The matching code is never
allowed to see those answers; a database permission and a test both enforce it.

Regenerate this section any time with `python -m packs.recon.eval --write-readme`.

<!-- eval:start -->
### Coverage

|  | Lines | Value (INR) |
|---|---:|---:|
| Settled in the period | 4,636 | 12,408,981 |
| Matched by rule | 4,582 | 12,267,473 |
| Matched by an approved proposal | 1 |  |
| **Match rate** | **98.86%** |  |
| Still in the queue | 130 | 361,046 |

### The rules, per tier

Precision is how many of a tier's claims name the payment that truly issued the
line. Recall is how much of the work that tier is responsible for it actually
did.

| Tier | Responsible for | Present | Claimed | Precision | Recall |
|---|---|---:|---:|---:|---:|
| T0 | clean | 4,090 | 4,090 | 1.000 | 1.000 |
| T1 | ref_drift, date_skew | 231 | 231 | 1.000 | 1.000 |
| T1b | ref_missing | 83 | 46 | 1.000 | 0.554 |
| T2 | split | 149 | 149 | 1.000 | 1.000 |
| T3 | fee_residual, fx | 66 | 66 | 1.000 | 1.000 |

### The agent, on what the rules cannot reach

Every one of these lines has a real counterpart; the gateway simply did not name
it. Declining is safe but not correct - it leaves the line in the queue.

|  | Count |  |
|---|---:|---|
| Nameless lines no rule can reach | 37 |  |
| Proposed a link | 20 |  |
| ...correct | 20 |  |
| ...**wrong - a false positive** | **0** |  |
| Declined to link (escalate / write-off) | 9 | safe, not correct |
| **Precision** | **1.000** | of the links it proposed · 95% CI ≥ 0.839 at n=20 |
| **Recall** | **0.541** | of the residual it resolved |
| Steps per proposal (median) | 3 |  |
| Validator corrections | 9 | caught mid-investigation |
| Latency p50 / p95 | 32.9s / 68.2s |  |

### If proposals were applied without review

Nothing is applied without review today. This is what it would cost if it were,
and it is the honest answer to "what is your false-positive rate".

The curve is flat because there are no errors to trade off yet. At this sample
size that is a statement about the sample, not a claim of perfection - the
interval column is the honest reading, and the bar to raise is *recall*, not
precision.

| Auto-apply at ≥ | Applied | Correct | False positives | Precision | 95% CI ≥ | Recall |
|---|---:|---:|---:|---:|---:|---:|
| 0.50 | 20 | 20 | **0** | 1.000 | 0.839 | 0.541 |
| 0.60 | 20 | 20 | **0** | 1.000 | 0.839 | 0.541 |
| 0.70 | 20 | 20 | **0** | 1.000 | 0.839 | 0.541 |
| 0.80 | 19 | 19 | **0** | 1.000 | 0.832 | 0.514 |
| 0.90 | 17 | 17 | **0** | 1.000 | 0.816 | 0.459 |
| 0.95 | 14 | 14 | **0** | 1.000 | 0.785 | 0.378 |
| 0.99 | 6 | 6 | **0** | 1.000 | 0.610 | 0.162 |
| 1.00 | 4 | 4 | **0** | 1.000 | 0.510 | 0.108 |
<!-- eval:end -->

---

# Running it on your own machine

Allow about 20 minutes the first time. Every command below is copy-pasteable.

## What you need first

| | | |
|---|---|---|
| **PostgreSQL 14+** | the database | [Postgres.app](https://postgresapp.com) on Mac, or `brew install postgresql` |
| **Python 3.11+** | the backend | `python3 --version` to check |
| **Node 18+** | the frontend | `node --version` to check |
| **An AI API key** | the one AI step | free from [Google AI Studio](https://aistudio.google.com/api-keys) |

> **On a Mac with Postgres.app**, `psql` is not on your PATH. Run this once per
> terminal, or add it to your `~/.zshrc`:
> ```bash
> export PATH="/Applications/Postgres.app/Contents/Versions/latest/bin:$PATH"
> ```

## Step 1 — Get the code

```bash
git clone <this-repo>
cd TalkToMyDataV3
```

## Step 2 — Create the two databases

There are two, and they do different jobs:

- **`talk_to_my_data_v2`** — the application's own store: user accounts, saved
  connections, chat history.
- **`kartly`** — the business data being reconciled: orders, payments, and the
  settlement files.

```bash
createdb talk_to_my_data_v2
createdb kartly

# the application's own tables
psql -d talk_to_my_data_v2 -f database/01_creating_database.sql \
                           -f database/02_create_tables.sql \
                           -f database/04_indexes.sql \
                           -f database/12_readonly_role.sql \
                           -f database/15_accounts.sql

# the business data, then the reconciliation tables on top of it
psql -d kartly -f database/kartly/01_schema.sql \
               -f database/kartly/02_seed_core.sql \
               -f database/kartly/03_seed_transactions.sql \
               -f database/kartly/04_grants.sql \
               -f database/kartly/05_reconciliation.sql \
               -f database/kartly/06_matching.sql \
               -f database/kartly/07_resolutions.sql
```

## Step 3 — Set up the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

Now open `backend/.env` and fill in three things:

```bash
# 1. Your database username (on a Mac with Postgres.app this is your login name)
DB_USER=your-username

# 2. Your AI key from Google AI Studio
ZEN_API_KEY=AIza...

# 3. An encryption key for saved database passwords. Generate it with:
#    python -m src.db.secrets --new-key
CREDENTIAL_KEY=...
```

Leave `ZEN_MODEL` and `ZEN_BASE_URL` as they come — they are already set for
Google's free tier.

## Step 4 — Build the reconciliation data

This creates three months of realistic settlement files, loads them, and runs
the matching rules.

```bash
# still in backend/, with .venv active

python -m packs.recon.generate --month 2026-05
python -m packs.recon.generate --month 2026-06
python -m packs.recon.generate --month 2026-07

python -m packs.recon.ingest --reset ../payouts/*.csv   # load the files
python -m packs.recon.match --reset                     # run the rules
python -m packs.recon.agent --limit 5                   # let the AI propose on a few
```

The `agent` step is the only one that costs API calls, and it is slow —
roughly 30 seconds per suggestion. Five is plenty to see it working.

## Step 5 — Start it

Two terminals.

**Terminal 1 — the backend:**
```bash
cd backend
source .venv/bin/activate
RECON_WRITE_DSN=postgresql://YOUR-USERNAME@localhost:5432/kartly \
  python -m uvicorn api:app --port 8020
```

> `RECON_WRITE_DSN` is what grants this instance permission to *apply* an
> approved decision. Without it the app still runs, but Approve works and Apply
> returns "not permitted" — which is the intended behaviour for a read-only
> deployment.

**Terminal 2 — the frontend:**
```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8020 npm run dev
```

## Step 6 — Use it

1. Open **http://localhost:5173**
2. Create an account (any email and password — it's your local machine)
3. When asked to connect a database, enter:

   | Field | Value |
   |---|---|
   | Host | `localhost` |
   | Port | `5432` |
   | Database | `kartly` |
   | Username | your database username |
   | Password | *leave blank locally* |
   | Type | PostgreSQL |
   | Permission | Read only |

4. You'll land on the exception queue. Click any row with a proposal, read the
   evidence, and approve it.

---

## If something goes wrong

| Symptom | Cause and fix |
|---|---|
| `No module named 'packs'` | You're in the project root. `cd backend` first — the payout paths are written relative to it. |
| `psql: command not found` | Postgres.app isn't on your PATH. See the note in *What you need first*. |
| The page loads but is blank | The frontend is pointing at the wrong port. Make sure you started it with `VITE_API_URL=http://localhost:8020`. |
| "The database assistant could not complete this request" | Almost always the AI key. If you just edited `.env`, **restart the backend** — it reads that file once at startup. |
| Apply returns 403 / "not permitted" | The backend was started without `RECON_WRITE_DSN`. See Step 5. |
| The matcher reports zeros | Everything is already matched. That's success, not failure. |

**One command tells you whether everything is wired up correctly:**

```bash
cd backend && source .venv/bin/activate
python -m packs.recon.demo status
```

It checks ten things — files loaded, rules run, suggestions waiting, the API
responding, the AI key working — and prints the exact command to fix each one
that isn't ready.

---

# For engineers

## The shape of it

```
payout CSV ──ingest──► settlement_lines ──┐
                                          ├──► match.py   T0 · T1 · T1b · T2 · T3
kartly.payments (the ledger) ─────────────┘         │
                                                    ├──► matches      (accounted for)
                                                    └──► exceptions   (the queue)
                                                              │
                                        no rule can name it ──┤
                                                              ▼
                                                   agent.py  reads the narration,
                                                             queries read-only,
                                                             proposes  ─┐
                                                                        │
                                            a person approves ──────────┤
                                                                        ▼
                                                              commit.py  applies
                                                              once, verified,
                                                              audited, reversible
```

## The layering

The runtime under `backend/src/` knows nothing about payments — it is a generic,
safe way to point a language model at any database. The reconciliation lives in
a **pack** at `backend/packs/recon/`, which is allowed to say "settlement" and
"payout".

That boundary is a build-time check, not a convention: `test_phase2` fails if an
industry word appears under `backend/src`, and
`database/14_domain_leakage_check.sql` proves the same runtime answers questions
about two unrelated databases. Reframing this project from a generic tool into a
reconciliation product changed the runtime by **17 lines**.

| | Lines | May name a domain |
|---|---:|---|
| `backend/src` — the runtime | 2,799 | no |
| `backend/packs/recon` — the pack | 1,893 | yes |

## Where each guarantee lives

| Guarantee | Enforced by |
|---|---|
| The model cannot write | `data_runtime_reader` has no write grant; queries run inside `SET TRANSACTION READ ONLY` |
| Applying twice is safe | unique constraint on `matches.line_id`, plus a state machine on `resolutions` |
| No double-counting a file | `settlement_batches.file_hash` is unique |
| Evidence can't go stale | `commit.py` re-runs and re-hashes the proposal's SQL before writing |
| Nothing is quietly undone | `audit_log` has no update or delete grant |
| The measurement is honest | `recon_labels` (the answer key) is not granted to the reader role |
| The runtime stays domain-blind | `test_phase2`, `database/14_domain_leakage_check.sql` |

## Tests

```bash
cd backend && source .venv/bin/activate

python test_recon_r1.py   # the planted defects are real; the reader cannot see the answer key
python test_recon_r2.py   # every match names the payment that truly issued the line
python test_recon_r3.py   # eleven attempts to write without a person, all refused
python test_degraded.py   # twelve degraded paths behave as documented
```

Plus the runtime's own suite: `test_phase1.py`, `test_phase2.py`,
`test_phase3.py`, `test_accounts.py`, `test_connection_scoping.py`,
`test_credential_encryption.py`, `test_pipeline_validator.py`.

## Swapping the AI provider

Any OpenAI-compatible endpoint works — set two environment variables, change no
code:

```bash
ZEN_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
ZEN_MODEL=gemini-2.5-flash-lite
ZEN_API_KEY=...
```

> **Note on model choice:** the agent makes several tool calls in one
> conversation. Gemini 3.x thinking models require an opaque `thought_signature`
> to be echoed back with each call, which the OpenAI compatibility layer drops —
> so they fail on the *second* tool call. `gemini-2.5-flash-lite` predates that
> mechanism and works.

## Demo tooling

```bash
python -m packs.recon.demo status   # is this machine ready to demonstrate?
python -m packs.recon.demo prep     # hold one payout file back, to load it live
python -m packs.recon.demo one      # work a single exception, printing every step
```
