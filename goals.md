# Goals — the path to 9/10

> The target is a 9/10 at a builder-first hackathon whose panel rejects thin wrappers.
> Companion docs: `project-idea.md` (what exists), `design-brief.md` (visual spec).
>
> **The one-line change:** Data Runtime stops being the product and becomes the
> substrate. The product is one named thing in Finance Operations & Control —
> settlement reconciliation with multi-source exception matching.

---

## 0. Why the current build caps at 7

Four rubric columns, weighted roughly evenly. Two of them are capped by *what the
project is*, not by how well it is built.

| Column | Today | Ceiling as-is | Why |
|---|---|---|---|
| Problem relevance & track alignment | 3 | **4** | Domain-neutral reads as *no* answer to "which of these five domains", not as five answers. |
| Skin in the game (safety & guardrails) | 4 | **4** | The test opens with "*if* an agent takes an action touching money, data, or outreach". Read-only means no action, so no score. |
| Engineering signal | 8 | 9 | The strongest column. Real pool, real read-only enforcement, real validator, real correction loop. |
| Measurable proof & demo viability | 2 | 9 | 39 behavioural tests, zero accuracy numbers. Fixable. |

Two columns hard-capped at 4 means the whole thing caps at ~7 no matter how much
more gets built. **The fix is a reframe, not more features.** Nothing in
`backend/src/` gets rewritten — it all carries over.

## 1. Rule 4

`project-idea.md` §4 has three rules. Add a fourth, first, before any code:

> **Rule 4 — Packs may know a domain. The runtime may not.**

Everything under `backend/src/` stays domain-blind and Rule 1 keeps applying to it,
enforced by `test_phase2.py:114` and `database/14_domain_leakage_check.sql`. The
vertical lives in `backend/packs/recon/` and is allowed to say "settlement",
"ledger", "payout". This makes the neutrality a defended boundary instead of a rule
we quietly broke.

## 2. Definition of done for 9/10

Nine things. If all nine are true, the score is there.

- [ ] A judge can state the problem in one sentence and it contains a track keyword.
- [ ] Rules clear >95% of a real settlement file with zero LLM involvement.
- [ ] The agent touches only the residual, and **proposes** — it never applies.
- [ ] Applying is deterministic, idempotent, audited, and reversible.
- [ ] A held-out labelled month yields real precision/recall, published.
- [ ] A confidence-threshold sweep answers "what is your false-positive rate?".
- [ ] Degraded-path behaviour is asserted by tests, not described in prose.
- [ ] The 90-second demo runs end to end without a manual step.
- [ ] `git log` shows the work happening.

---

# The phases

Ordered by rubric points per hour. **Truncate from the bottom** if time runs out —
every phase leaves the project demo-able.

---

## Phase R0 — Credibility repairs — **DONE**

Cheap, and each one is something a judge finds by opening a single file.

- [x] `git init`, commit the current state, commit from here on. First commit
      `4653480`, 98 files, branch `main`. There was no repo history before this,
      and in a builder-first hackathon that history *is* the execution signal.
- [x] Verified no key material is committed. `.gitignore`'s `.env` pattern has no
      leading slash, so it catches `backend/.env` and `frontend/.env` at any depth;
      both `.env.example` files carry names with empty values.
- [x] Dead files were already gone — `mcp_server.py`, `main.py`, the root `api.py`
      shim and `config/permissions.json` do not exist. §7 of `project-idea.md`
      describes work already done. Cleared 11 stale `__pycache__` trees.
- [x] **Model mismatch resolved: keep the free gateway, fix the doc.** It was a
      three-way disagreement — code default `north-mini-code-free`, `.env` and
      `.env.example` `laguna-s-2.1-free`, doc "Claude Sonnet 5 + Haiku 4.5". All
      three now say `laguna-s-2.1-free` on opencode zen, and §5 names the gateway
      as a row of its own so the swap is one env var if the tier ever matters.

**Decision recorded:** the model is free-tier and the doc says so. The defensible
line is that the *architecture* carries the reliability — the four-stage validator,
the correction loop and the step budget are what make a weaker model safe, and R2
puts the matching in SQL where no model can get it wrong. That is a stronger answer
to a judge than a better model would have been. Revisit only if R4's eval shows the
model, not the rules, is the accuracy ceiling.

## Phase R1 — The two sources — **DONE**

**Goal:** a settlement file is just another source. Kartly is the internal
ledger; the gateway sends a payout file that disagrees with it.

- [x] `database/kartly/05_reconciliation.sql` — `payments.gateway_reference`
      (deterministic, unique, captured non-COD only), `settlement_batches`,
      `settlement_lines`, `recon_labels`, indexes and grants. Money is integer
      minor units throughout; `recon_labels` is deliberately **not** granted to
      `data_runtime_reader`, so the model cannot read the answer key.
- [x] `packs/recon/defects.py` — the defect model, rates in one visible dict.
- [x] `packs/recon/generate.py` — builds the payout CSV from captured payments
      and writes ground truth per line as it goes.
- [x] `packs/recon/ingest.py` — CSV → tables, `sha256` of the file bytes unique
      on the batch, so a replay is a no-op that says so. `--reset` for dev.
- [x] `test_recon_r1.py` — the self-check below.

**COD is out of scope on both sides.** A courier collects it and remits
separately; it never reaches a gateway payout file. That removes 13,998
payments that would otherwise be noise.

### What one month looks like — 2026-07, all three gateways

4,645 settlement lines from 4,579 captured payments across three files,
₹12,483,330 net settled.

| Class | Lines | Share | Aimed at |
|---|---|---|---|
| `clean` | 4,182 | 89.4% | T0 exact |
| `split` | 149 | 3.2% | T2 subset-sum |
| `ref_drift` | 146 | 3.1% | T1 normalised |
| `date_skew` | 85 | 1.8% | T1 window |
| `fee_residual` | 50 | 1.1% | T3 tolerance |
| `orphan_ledger` | 32 | 0.7% | **a real exception** |
| `orphan_gateway` | 17 | 0.4% | **a real exception** |
| `fx` | 16 | 0.3% | T3 currency |

So R2 has ~446 lines that the rules must earn, and ~49 that are genuinely
unmatchable and belong in the exception queue. **The exception queue is the
demo**, and 49 is an honest number rather than an inflated one — if it needs to
be bigger for R7, generate a quarter rather than raising the orphan rate.

### Two bugs the self-check caught

- **`drift()` was a no-op on payu references.** Two of its four variants only
  change a reference that contains `_` or `-`; payu's has neither, so half of
  payu's `ref_drift` lines were labelled drifted but matched exactly. R4 would
  have scored those as T0 misses that never happened. It now always returns
  something different, and the test asserts zero `ref_drift` lines match exactly.
- **`orphan_ledger` labels desynchronised every label after them.** They were
  appended to the list running parallel to `rows` while writing no row, shifting
  31 lines onto the wrong label. Found by asserting every line carries a label.

Both were silent, and both would have surfaced in R4 as a matcher that looked
worse than it was.

### Audit — R0 and R1 re-verified after the fact

Both phases were checked independently rather than taken on trust.

**R0 — clean.** 3 commits on `main`, working tree clean, no `.env`/key file ever
committed and no key-shaped string in any committed blob. All four places that
name the model now agree on `laguna-s-2.1-free`. All four dead files confirmed
absent. **The whole existing suite passes under `backend/.venv`** — 8 of 8,
including `test_phase2` and `test_phase3`, which make real model calls, so the
default swap is exercised end to end and not just read.

**R1 — one real hole, now closed.** `recon_labels` was readable by
`data_runtime_reader`: both `12_readonly_role.sql` and `kartly/04_grants.sql`
carry `ALTER DEFAULT PRIVILEGES ... GRANT SELECT ON TABLES`, so the table was
granted to the reader the instant it was created. The file said "deliberately
NOT granted" in a comment, and the comment was simply wrong — **the model could
read the answer key.** Fixed with an explicit `REVOKE` on the table and its
sequence, and the test now connects *as the reader* and asserts it: it fails
before the revoke and passes after. Verified again on a database built only
from the SQL file, so a fresh machine gets the revoke too.

Also verified, and correct: the generator is deterministic (a full regeneration
is byte-identical and matches the `file_hash` stored at ingest); a complete
rebuild from a pre-R1 copy of kartly reproduces every count exactly; `INSERT` as
the reader dies in a read-only transaction; and eleven cross-checks the self-test
does *not* make all pass — fee residuals really differ from the ledger fee, skewed
dates really fall outside T+2, clean lines sit exactly on it, FX lines are the
only non-INR rows, every split has 2-3 parts, and batch `line_count` ties to the
lines actually stored.

**Known and deliberate:** 28 of the 50 `fee_residual` lines sit on a zero-fee UPI
capture, so T3's tolerance band has to handle an *expected* fee of zero rather
than a percentage drift. That is realistic — a PSP levying an unexpected UPI fee
is a genuine exception — but R2 must not assume a non-zero baseline.

**Carried into R3:** the five stored schema snapshots are stale. None mention
`settlement_lines`, so the agent cannot see the settlement tables until the
connection is re-analysed.

**Done when:** ✅ `python test_recon_r1.py` → *ok - 4645 settlement lines across
3 payouts, every defect class present and honest* / *ok - the reader role can see
settlements and cannot see the answer key*. It asserts labels and lines
agree in both directions, every class is present, clean lines match exactly,
drifted ones do not, splits sum back to the paisa, orphans are orphans on both
sides, `net = gross - fee` on every row, and a replay changes nothing.

### Running it

```bash
psql -d kartly -f database/kartly/05_reconciliation.sql
cd backend
python -m packs.recon.generate --month 2026-07
python -m packs.recon.ingest --reset ../payouts/*.csv
python test_recon_r1.py
```

`payouts/` is gitignored — `generate.py` is deterministic, so the files rebuild
byte-identically from the seed.

## Phase R2 — The deterministic matcher — **DONE**

**Goal:** rules do the work. No model appears anywhere in this phase, and
`test_recon_r2.py` asserts the matcher's source does not even mention the labels
table.

- [x] `database/kartly/06_matching.sql` — `matches`, `exceptions`, and
      `recon_core()` with expression indexes on both sides.
- [x] `packs/recon/match.py` — the four tiers, one SQL statement each.
- [x] `test_recon_r2.py` — eight assertions, below.

### The tiers, and what each one earns

| Tier | Rule | Confidence | Caught |
|---|---|---|---|
| T0 | reference exact · gross and fee tie to the paisa · settled by T+2 | 1.000 | 4,090 |
| T1 | reference normalised, or late — money still ties exactly | 0.950 | 231 |
| T1b | no gateway reference; the merchant's order id carried it | 0.880 | 46 |
| T2 | 2–3 lines sharing a reference sum to one capture, gross *and* fee | 0.900 | 149 |
| T3 | fee inside a 25bp band (0.850), or settled in USD (0.800) | 0.850 / 0.800 | 66 |
| — | no counterpart, or no name at all | — | **132 exceptions** |

**Match rate 98.84% — 4,582 of 4,636 lines — in 0.6s**, including interpreter
start, over 60,072 candidate captures.

**Normalisation is one rule.** Every reference here is a per-gateway prefix plus
a 14-character hex core, and every way a payout file mangles one — case,
separators, padding, a stripped prefix — leaves that core intact. `recon_core()`
takes the last 14 alphanumerics, which collapses all four drift variants and
still yields 60,072 distinct cores from 60,072 payments. No collisions.

**Ordering is what makes the tiers mean anything.** T1 demands the money tie
exactly, so a fee residual falls through it to T3 rather than being quietly
absorbed at 0.950 confidence. T0 requires arrival by T+2, so a late payout drops
to T1 instead of being scored as a clean tie. Each tier only sees what the tier
above left.

### The bug that mattered

**Scope was defined by the wrong thing.** The first version asked which captures
had a settlement date inside the span the file's lines cover — and accused **236
payments of never being settled when only 32 were**, dragging in 204 captures
from the months either side. A file's date span is not the period it reconciles.

The rule now: a gateway-month is covered when the file plainly accounts for it —
at least half that month's captures matched by these lines. Below that the file
is only brushing the period and its silence about the rest says nothing. Exactly
32 now, all in the month being reconciled.

**Done when:** ✅ `python test_recon_r2.py` → *ok - 4582/4636 lines matched
(98.84%), every match on the right payment* / *ok - 132 exceptions, 37 of them
nameless and left for the agent*. Verified again on a database rebuilt from the
SQL files alone, and the whole suite — 9 of 9 — passes.

The eight assertions, in order: the matcher never reads the labels · every match
names the payment that truly issued that line · each tier caught only its own
defect classes · nothing with a counterpart went unmatched · no payment claimed
twice outside T2 · exact tiers tie to the paisa and split groups sum back · the
queue holds only genuine orphans, in both directions · and no line is left
neither matched nor queued. Re-running over its own output changes nothing.

### Making the residual real — `ref_missing` and the narration field

The first pass scored precision and recall of 1.000, which is a warning rather
than a victory: the tiers were built against defects built to be caught, so
nothing was genuinely ambiguous and R3's agent had nothing to do but
rubber-stamp orphans. Fixed here, and the fix changed shape once on contact with
the data.

**The obvious fix did not work.** Dropping the gateway reference from ~2% of
lines left them resolvable by amount and date alone — measured, and every one of
the 37 had *exactly one* candidate capture. Kartly's order totals are
fine-grained enough that only 6 payments in the whole month share an amount with
a peer within five days. **No amount-based defect can ever justify an agent
here**, and a judge would rightly say the residual should be an algorithm.

**Where a model actually beats a rule is unstructured text.** So a payout line
now carries `narration` — the gateway's free text, exactly as written. A
reference-less line's narration is the only clue to what it is, in seven human
shapes:

```
KARTLY SETTLEMENT ORD 68854 BATCH 952959     order id, plus a decoy number
neft/kartly/68318/07                          order id in the third field
kartly ord no 70571 - net of charges          order id in prose
SETTLE KARTLY REF 68948/156205                order id first, batch second
CONSOLIDATED PAYOUT KARTLY BATCH 495628       no order id at all - a false lead
SETTLEMENT BATCH 735287 MERCHANT KARTLY       no order id at all - a false lead
```

Of the 37 nameless lines, **18 carry an order id somewhere and 19 carry only a
batch number.** A regex that grabs the first integer proposes a wrong link on
the second group — which is the point. Extraction is probabilistic, so it must
be *proposed and verified*, never applied by a rule. That is R3's architecture
in one sentence, and `test_recon_r2.py` now asserts no rule ever matches a
nameless line.

Rules that *can* be written still are: T1b resolves the 46 reference-less lines
whose order id survived in a structured field, at 0.880 rather than 0.950
because an order id names an order, not an attempt.

The queue now separates the two problems it holds — `no_ledger_counterpart` (17
lines with a name and no counterpart) and `no_reference` (37 with a counterpart
and no name) — because they need different work.

### Superseded — why 1.000 was a problem

Precision and recall are both 1.000, which is a *warning*, not a victory. The
tiers were designed against defects the generator was designed to plant, and
every reference is unique and present, so nothing is genuinely ambiguous. Two
consequences:

- **R4's numbers will look fabricated.** A perfect table invites the one
  question there is no good answer to. The threshold sweep saves it only if
  there is something for a threshold to trade off.
- **R3's agent has nothing to investigate.** All 49 exceptions are pure orphans;
  the only honest proposals are `escalate` and `write_off`. Rubber-stamping is
  not a demo of bounded agency.

Both were fixed by the section above. The headline match rate fell from 99.63%
to 98.84% — a more credible number, not a worse one.

## Phase R3 — Proposal and gate — **DONE**

**Goal:** the agent proposes; a deterministic committer applies. This is the
whole safety score, and it replaces §19's "write mode is not in the MVP".

- [x] `database/kartly/07_resolutions.sql` — `resolutions`, `audit_log`, the
      state machine as a trigger, the append-only triggers, grants.
- [x] `packs/recon/propose.py` — the one action the agent has.
- [x] `packs/recon/commit.py` — the only code that changes what is settled.
- [x] `packs/recon/agent.py` — the agent working the nameless queue.
- [x] `test_recon_r3.py` — eleven attempts to get a change in without a person.

### The shape of it

**The agent's whole reach is two tools:** a read-only `query` and
`propose_resolution`. A proposal records what it thinks, what it read, and how
sure it is — and stops. `test_recon_r3.py` asserts the agent module does not so
much as *name* the committer, and that the tool list it is handed is exactly
those two.

**The evidence is not taken from the model.** `propose.py` recomputes it from
the database in a canonical query stored beside the proposal, and hashes the
result. At apply time it is recomputed and re-hashed: if the ledger moved
underneath, the apply is refused rather than applied to a world that no longer
exists.

**The state machine lives in the database**, so code that forgets the rule still
obeys it. `proposed → approved | rejected → applied → reversed`, and nothing
else; an approval without a decider raises; an apply without an idempotency key
raises.

**Applying needs `RECON_WRITE_DSN` set explicitly.** A process meant only to read
and propose never holds credentials that can apply. Locally that is the same
owner role; in anything real it is a role with `INSERT` on `matches` and nothing
else.

**The audit log cannot be edited, deleted or truncated** — by anyone, the table
owner included, because it is enforced by triggers rather than by a `REVOKE`.

### The agent, on real exceptions

Five nameless lines worked end to end against the live model, **five correct
links.** Its own reasoning, verbatim from `resolutions.reason`:

> *"Narration contains order id 68584; verified a captured razorpay payment for
> the exact amount (1583360 paise), before settlement date, not already
> matched."*

> *"Narration contained no order ID or verifiable reference (only a batch
> number), but the settlement amount of 374112 paise exactly matches a single
> captured payment…"*

The second is the interesting one: it says plainly that the narration named
nothing, and rests the proposal on the amount instead — at lower confidence.
That is the sentence a reviewer needs in order to disagree with it.

An earlier run, before the query tool was wired correctly, produced three
`escalate` proposals reading *"could not verify… due to access restrictions"*.
The tool was broken and the agent refused to guess. That is the behaviour the
architecture is for, observed by accident.

### Three bugs, all found by trying to break it

- **The append-only trigger did not cover `TRUNCATE`.** A row-level trigger
  never sees it, so the entire log could have been erased by a statement that
  fired nothing. A second statement-level trigger now catches it, and the test
  asserts all three of update, delete and truncate.
- **`match --reset` would have discarded human decisions.** R3's foreign key
  from `resolutions` to `exceptions` broke the truncate outright; cascading
  would have silently deleted approved proposals. It now refuses while any
  resolution is live and says which.
- **The pack could not validate SQL.** `PostgresDataSource.validate` loads the
  *signed-in user's* snapshot, and a pack script has no session. The pack builds
  the same `SQLValidator` from a fresh introspection instead — same four stages,
  different source of schema.

### Left out, deliberately

- **Three kinds, not five.** `link`, `write_off` and `escalate` are what this
  residual produces. `split_link` and `fee_adjustment` were in the plan; T2 and
  T3 already resolve those deterministically, so a proposal kind for them would
  be an enum value nothing can reach.
- **The `permission` field on a connection is still display-only.** Wiring the
  app's per-connection permission into a pack's committer would be decoration:
  the real controls here are the state machine, the separate write DSN, and the
  fact that the model's only database access is the runtime's read-only role.
  Noted rather than faked.

**Done when:** ✅ `python test_recon_r3.py` → *ok - proposed, refused, approved,
refused again on stale evidence, applied once, applied twice with no second
effect, reversed* / *ok - the agent holds no route to the committer, and the log
cannot be edited, deleted or truncated*. The whole suite — 10 of 10 — passes, and
a database rebuilt from the three SQL files alone reproduces all of it.

## Phase R4 — The numbers — **DONE**

**Goal:** answer *"how often is it right?"* and *"what is your false-positive
rate?"* with a table instead of a demo.

- [x] `packs/recon/eval.py`, measured against the labels the generator wrote as
      it built the files. Nothing hand-labelled, and neither the matcher nor the
      agent can read that table.
- [x] `--write-readme` regenerates the block between markers in `README.md`, so
      published numbers are always the numbers the script produced.
- [x] A full agent pass over all 37 nameless exceptions.

### What it says

**4,636 lines · ₹12,408,981 settled · match rate 98.86% · 130 in the queue,
₹361,046 at risk.** Every rule tier: precision 1.000. T1b's recall is 0.554 —
it resolves only the reference-less lines that kept an order id.

**The agent, on the 37 lines no rule can reach:** 20 links proposed, **20
correct, 0 false positives**, 9 declined, 8 out of steps. Median 3 steps,
9 validator corrections caught mid-investigation, p50 33s / p95 68s.

Precision is reported as **1.000, 95% CI ≥ 0.839 at n=20** rather than as a bare
`1.000`. Twenty out of twenty is not the same claim as two thousand out of two
thousand, and reporting either as a flat 1.000 invites the one question with no
good answer. Wilson, because the normal approximation gives a zero-width
interval at exactly 1 — the case this exists to describe.

### Three honest readings a judge will want

- **The threshold sweep is a flat line.** There are no errors to trade off, so
  the curve shows nothing yet. At n=20 that is a statement about the sample, not
  a claim of perfection. The bar to raise here is **recall, not precision**.
- **8 of the 20 correct links sat on `batch only` narrations** — the decoys. The
  agent did not fall for the batch number; it resolved them by amount instead,
  and in this data amount plus window is a unique key. So those 8 demonstrate
  arithmetic a rule could have done, not text reading. **The 12 links on
  narrations that carried an order id are the genuine wins.**
- **Recall 0.541 is capped by the step budget, not by the model.** 8 of the 37
  exhausted a budget of 6 while the median proposal took 3. Raising it to 8-10
  and re-running is the obvious next experiment, and is likely worth several
  points of recall.

### Dropped from the plan, with a reason

Running this eval against the two `14_domain_leakage_check.sql` schemas was
written when the eval was the *runtime's*. Those databases have no settlements,
so a reconciliation eval cannot run against them. Rule 1 is proved instead by
`test_no_domain_words_in_the_product`, which R6 tightened to ban this pack's own
vocabulary from the runtime, and by the 15 seconds at the end of the demo.

**Done when:** ✅ `python -m packs.recon.eval --write-readme` and the README
carries the table it produced.

## Phase R5 — Degraded paths — **DONE**

**Goal:** the answer to *"what broke and how did you architect out of it"* is a
test file, not a story. `backend/test_degraded.py`, twelve assertions, all green.

```
ok  malformed tool arguments
ok  unknown tool name
ok  prose where a tool call was required
ok  a model that never stops is stopped
ok  a transient upstream failure is retried
ok  our own bad request is not retried into a wall
ok  a slow query is killed and the pool survives
ok  a replayed file changes nothing
ok  a truncated or malformed file is refused
ok  a payout dated before its capture never matches
ok  currencies are never compared
ok  an instruction in the data achieves nothing even if obeyed
```

### The injection test is framed deliberately

It does **not** ask whether the model resists an instruction hidden in a row.
It assumes the model obeys — the scripted model dutifully emits `DROP TABLE
users` — and asserts that obeying gets it nowhere: the validator refuses the
statement, a stacked `SELECT 1; DROP TABLE users` is refused too, the role the
model reads as cannot create a table inside its read-only transaction, and the
only write it has is a closed enum that rejects an invented kind.

*"We do not test that the model behaves. We test that it does not matter."*
That is a better answer to a judge than any amount of prompt hardening.

### The bug this phase found

**Every tier's settlement window was one-sided.** `settled_at <= captured_at +
N days` has no lower bound, so a payout line dated *before* the capture it
claims to settle satisfied every rule — clock skew on a gateway, or a
mislabelled file, and money appears to have been settled before it was taken.
All five windows are now `BETWEEN`, and T2's group is bounded at both ends
rather than only at its last line.

The test was then checked the way the R1 revoke was: the one-sided window was
put back, and the assertion fails — *"a payout dated before its capture was
matched"* — so it is catching the bug rather than passing by luck.

Also cleaned: the read-only pool is a background thread pool, and every pack run
was ending in four `couldn't stop thread` warnings that read like a fault.

**Done when:** ✅ `python test_degraded.py` → *12 degraded paths held*.

## Phase R6 — The surface — **DONE**

**Goal:** one screen where a reviewer works down a list, with the evidence and
the two buttons in the same place. Verified in a browser, not only by a
typechecker.

- [x] `packs/recon/api.py` — six endpoints, all behind the runtime's own auth.
- [x] A generic pack loader in `api.py` — `pkgutil` finds every pack offering a
      router and mounts it at `/packs/<name>`. The runtime learns that packs
      exist, never what any of them is for.
- [x] `frontend/src/packs/recon/` — the page and its own HTTP client, borrowing
      only the runtime's session token.
- [x] `frontend/src/packs/index.ts` — the registry, and the single seam the
      runtime imports. Reached at `#pack/<name>`.
- [x] KPI row · reason filters · exception table · expandable proposal with the
      agent's reasoning, its cost, and the evidence · approve / reject / apply /
      reverse · the append-only audit log.

### Verified by using it

Signed in, opened `#pack/recon`, expanded a proposal, approved it, applied it,
and watched the numbers move: **match rate 98.84% → 98.86%**, *4,582 by rule ·
1 approved*, the queue **132 → 130** because applying closed *both* sides of the
gap, and money at risk ₹392,713 → ₹361,046. The audit log then showed
`proposed` by `agent` and `approved`/`applied` by the signed-in person.

### Rule 4, enforced rather than asserted

`test_no_domain_words_in_the_product` was tightened rather than bypassed. The
banned list now also carries this pack's vocabulary — *settlement, payout,
reconcil\*, gateway, ledger* — so the runtime cannot pick up a domain from the
pack living beside it, and `packs/` is skipped because that is where a domain is
allowed to be named.

It found two things immediately:

- **A real leak of my own:** a docstring in `zen_client.py` describing "the
  gateway's" failures, meaning the model provider. Reworded.
- **A pre-existing string** in `Setup.tsx`: an example purpose naming a payments
  platform and settlement delays. On inspection it is one of four examples
  spanning payments, transit, healthcare and logistics — a menu whose *point* is
  that no single domain owns it. Marked with a `rule1-exempt` block that states
  why, and the test now honours the marker. The exemption is narrow, visible in
  the source, and has to justify itself.

### Two smaller fixes

- The pack route was gated on `user`, which is resolved a moment after the first
  render, so the page fell through to the landing screen. Gated on the session
  token instead.
- `sum()` over a bigint column returns `numeric`, which FastAPI serialises as a
  string; the KPI tiles were doing arithmetic on `"1240898109"`. Cast to
  `bigint` in the query.

**Done when:** ✅ the page renders live data, a proposal can be approved and
applied from it, the KPIs move, and the audit log records who did it.

## Phase R7 — The demo — **script and tooling done, one prep step pending**

- [x] `DEMO.md` — the ninety seconds beat by beat, with what to run, what to
      say, the five questions a judge will ask with answers that point at files,
      and what to do when something breaks.
- [x] `packs/recon/demo.py` — `status`, `prep`, `one`.
- [x] The transit database, which the closing fifteen seconds needs and which
      had never actually been created.
- [ ] A full agent pass at the raised budget, still running.

### `demo status` exists because demos fail for boring reasons

Eight checks — files ingested, matcher run, proposals waiting, something left
unworked for the live moment, one file held back, the second database present —
each printing the command that fixes it. It refuses to say **ready** otherwise.

### The restructure that made the demo work

The first draft ran the matcher on stage and it printed **a column of zeros** —
everything was already matched, so the tier histogram, which is the whole visual,
had nothing to count. `demo prep` now withdraws one payout file: its batch,
lines, matches and exceptions are deleted while the other eight keep the
proposals the queue needs. On stage that file arrives in front of the audience
and the rules run on it live.

### The transit database did not exist

`database/14_domain_leakage_check.sql` had never been run, so the closing move —
point the same runtime at an unrelated database and ask about station footfall —
would have failed on stage. Loaded, and the file amended: it had no grants for
`data_runtime_reader`, so it created two databases the product could not open,
and it was not re-runnable. Both fixed.

### The two experiments, done

- **Step budget 6 → 10.** Eight of the first 37 exhausted a budget of 6 while the
  median proposal took 3 steps, so recall was capped by the ceiling rather than
  by the model.
- **A month → a quarter.** 2026-05 through 2026-07: **10,677 lines, 98.94%
  matched, 277 exceptions, 75 of them nameless** — a queue with enough in it to
  look like a working day, and enough proposals for the sweep to have a chance
  of bending.

The pass at the new budget is slow — roughly five minutes per three exceptions —
so the final agent numbers and a regenerated README block are still to come. The
demo itself only needs three proposals and has them.

**Done when:** `demo status` says *ready* and the ninety seconds has been run end
to end without a manual rescue.

# What gets cut

Protecting the schedule matters as much as the plan.

| Cut | Why |
|---|---|
| GenUI components 5–8 | Prompt tokens and failure modes. Four is the demo. |
| MongoDB | **Freeze it.** The code stays — it proves `DataSource` is a real abstraction. Zero further hours, and keep it out of the demo. |
| `Landing.tsx` polish (295 lines) | Zero rubric points. |
| Multi-connection UI, theme work, per-conversation purpose | §19 already deferred these. Keep them deferred. |
| A bespoke planner | The LangGraph loop plus the step budget is already the right shape. |

---

# Carry-over — what is already done and stays untouched

This is why the reframe is affordable. Roughly zero rewrite:

`auth.py` + `auth_sessions` · per-user connection scoping
(`test_connection_scoping.py`) · Fernet credential encryption with rotation
(`test_credential_encryption.py`) · pooled psycopg keyed by DSN · read-only role +
`SET TRANSACTION READ ONLY` + DB-enforced 15s timeout + 500-row cap
(`test_phase1.py:68-99`) · the four-stage validator · the Mongo pipeline validator
that walks `$lookup`/`$graphLookup` at any depth · the LangGraph loop with a
**per-question** step budget (`nodes.py:96-122`) · SSE streaming and the trace ·
app tables stripped from every snapshot · the two domain-leakage databases.

---

# Rubric map — where each phase scores

| Phase | Track fit | Skin in the game | Engineering | Proof |
|---|---|---|---|---|
| R0 credibility | – | – | ✓ | – |
| R1 two sources | ✓✓ | – | ✓ | – |
| R2 matcher | ✓✓ | – | ✓✓✓ | ✓ |
| R3 proposal + gate | ✓ | ✓✓✓ | ✓✓ | – |
| R4 numbers | ✓ | – | ✓ | ✓✓✓ |
| R5 degraded paths | – | ✓✓ | ✓✓ | ✓ |
| R6 surface | ✓ | ✓ | – | ✓ |
| R7 demo | ✓ | ✓ | – | ✓✓ |

**Minimum viable 9:** R0 → R2 → R3 → R4 → R7. R1 is a prerequisite for R2. R5 and
R6 are what separate 8.5 from 9.

---

# Honest risks

- **The labelling in R4 is the bottleneck**, and it is unglamorous. Start it during
  R2 rather than after R3, in parallel.
- **T2 subset-sum can hang.** Bound the candidate window before writing the loop,
  not after it hangs.
- **9/10 also depends on the field**, which is not knowable from here. This plan
  removes the reasons to score *below* 9; it cannot guarantee the ceiling.
- **The demo breaking on stage** is a rehearsal problem, not an architecture one.
  R7 gets its half day.
