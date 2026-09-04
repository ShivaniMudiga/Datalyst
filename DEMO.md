# The demo

Ninety seconds. Rehearse it until it is boring.

Everything below is real: the numbers come from the database, the agent call
happens live, and the refusals are the system refusing rather than a slide
saying it would.

---

## Before you stand up

```bash
cd backend
.venv/bin/python -m packs.recon.demo status
```

It checks the eight things that make a demo fail for boring reasons — files not
ingested, matcher not run, no proposals waiting, nothing left unworked for the
live moment, the second database missing — and prints the command that fixes
each. Do not start until it says **ready**.

Building that state from nothing:

```bash
.venv/bin/python -m packs.recon.generate --month 2026-05   # and 06, and 07
.venv/bin/python -m packs.recon.ingest --reset ../payouts/*.csv
.venv/bin/python -m packs.recon.match --reset
.venv/bin/python -m packs.recon.agent --all                # slow; leave it running
.venv/bin/python -m packs.recon.demo prep                  # withdraw one file
```

`prep` is the last step and the one that is easy to forget. **The most
convincing beat is the rules running on a file that arrives in front of the
audience** — and once everything is matched, running the matcher again prints a
column of zeros. So one payout file is withdrawn, and you ingest it on stage.

Two terminals and a browser:

```bash
# terminal 1 — the API, with permission to act.
# Port 8020, not 8000: 8000 is popular, and a container bound to *:8000 on IPv6
# alongside our own on 127.0.0.1:8000 both start happily while the browser
# resolves localhost to ::1 and talks to the wrong one. The page just goes blank.
RECON_WRITE_DSN=postgresql://apple@localhost:5432/kartly \
  .venv/bin/python -m uvicorn api:app --port 8020

# terminal 2 — the app, pointed at that API
cd frontend && VITE_API_URL=http://localhost:8020 npx vite --port 5173 --strictPort

# terminal 3 — kept clear, for the three commands you run on stage
```

`demo status` asks the API whether it is *ours* rather than whether something
answers, which is the only version of that check worth having.

Browser: sign in, then `http://localhost:5173/#pack/recon`. Leave it on the
queue, scrolled to the top.

---

## The ninety seconds

### 0:00 — the problem, in one sentence

> "A payment gateway sends a file saying what it paid out. Our ledger says what
> we captured. They disagree, and somebody reconciles them by hand."

### 0:05 — the file arrives *(terminal 3)*

```bash
.venv/bin/python -m packs.recon.ingest ../payouts/razorpay-2026-07.csv
```

> "This month's payout file from one gateway. Two and a half thousand lines."

### 0:15 — the rules do the work *(terminal 3)*

```bash
.venv/bin/python -m packs.recon.match
```

Point at the tier histogram as it prints — it is counting the file that just
arrived, not the whole quarter.

> "Four tiers of SQL. Exact reference. Normalised reference. Several lines
> summing to one capture. A fee inside a basis-point band. **No model anywhere
> in this** — 98.9% of the file, in under a second. A language model would only
> make this less predictable."

### 0:30 — what is left *(browser, refresh)*

> "Across the quarter that leaves a few hundred exceptions and about four hundred
> thousand rupees. Seventy-five of them the rules genuinely cannot touch: the
> gateway never echoed its reference, so all we have is free text."

Point at a row: `CONSOLIDATED PAYOUT KARTLY BATCH 495628`.

> "That number is a batch id. It identifies nothing. A regex would grab it and
> propose a wrong link."

### 0:40 — the agent, live *(terminal 3)*

```bash
.venv/bin/python -m packs.recon.demo one
```

It takes about thirty seconds. **Talk over it** — the steps print as they happen:

> "It reads the narration, queries read-only, and checks its story against the
> ledger: does that order have a captured payment, on this gateway, for this
> exact amount, before this settlement date, not already matched? If any of that
> fails it says so and escalates. Escalating is a correct answer here — a wrong
> link costs more than an escalation."

When it lands, read its reason aloud. That sentence is the product.

### 1:05 — a person decides *(browser, refresh, expand a proposal)*

**Reject** one. **Approve** and **Apply** another. Watch the KPIs move.

> "The agent proposes. It cannot apply. It holds no route to the code that can —
> that is a test, not a policy. Applying re-runs the evidence and re-hashes it:
> if the ledger moved since the proposal, it refuses."

Open the audit log.

> "Append-only. Not by a REVOKE — by triggers, against update, delete *and*
> truncate. The table owner cannot edit this."

### 1:20 — the same file, again *(terminal 3)*

```bash
.venv/bin/python -m packs.recon.ingest ../payouts/razorpay-2026-07.csv
```

> `skipped - identical file already ingested`

> "Hashed on the way in. Replaying a payout file is a no-op that says so, not a
> double count."

### 1:30 — the last fifteen seconds

Switch the connection to `leakage_check_transit` and ask:

> *"Which stations have the highest footfall?"*

> "Same runtime. It has never heard of payments. Reconciliation is a pack on
> top — the engine underneath knows nothing about any industry, and a test
> fails the build if a word from this domain leaks into it."

---

## What they will ask

**"Why is a model here at all?"**
It is not, for 98.9% of the work. It is used for the one thing rules provably
cannot do — reading free text a human wrote — and its output is a proposal, not
an action. `packs/recon/match.py` has no model in it, and the self-check asserts
it cannot even read the answer key.

**"What is your false-positive rate?"**
Twenty links proposed, twenty correct, zero false positives — but that is n=20,
so the honest number is the 95% lower bound of 0.839, which is in the README.
The threshold sweep is flat because there are no errors to trade off yet. The
bar to raise is recall, not precision.

**"What broke?"**
`backend/test_degraded.py`, twelve of them. The best: every tier's settlement
window was one-sided, so a payout dated *before* its capture matched — clock
skew and money appears settled before it was taken. Also a single 503 from the
model provider ended a whole 37-exception run; the retry went where every caller
routes through, including the app's own chat.

**"What about prompt injection?"**
We do not test that the model resists. The test assumes it obeys — the scripted
model emits `DROP TABLE users` — and asserts that obeying achieves nothing.

**"How do you know the accuracy is real?"**
The generator wrote the labels as it built the payout files, so the truth is
known by construction. The matcher and the agent are both blocked from reading
that table at the database level, and `test_recon_r1.py` connects as the
model's role to prove it.

---

## If something breaks

- **The model provider is out of quota.** `demo status` checks this with one
  token before you stand up, because the symptoms are all indirect: the batch
  prints `failed`, the app shows a generic error, and the live moment simply does
  not happen. A long agent pass will exhaust a free tier. **Only two beats need
  the model — 0:40 and 1:30.** Everything else is rules and the gate. If it is
  out: skip 0:40, open a proposal that already exists, and for 1:30 show the
  runtime *reading* the transit schema instead of answering a question about it.
- **The model call hangs or 503s.** It retries four times with backoff. If it
  still fails, say so and open a proposal that already exists. The failure is not
  fatal to the story: the agent refusing to guess *is* the story.
- **The queue looks empty.** The filter chips are sticky. Click *Everything*.
- **Apply returns 403.** `RECON_WRITE_DSN` is not set on the API process. That is
  the control working; restart terminal 1 with it.
- **The matcher prints zeros.** You forgot `demo prep`, so there was nothing new
  to match. `demo status` catches this before you stand up.
- **Anything else.** `demo status`, fix what it names, carry on.
