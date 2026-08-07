# COORDINATOR HANDOFF — 2026-08-07

You are the on-duty coordinator of the WNBA program graph. This packet supersedes the
2026-08-06 handoff as the current worklist; that file remains valid for history and for its
disciplines section.

**Working root:** `C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program`
(branch `player-model-program`).
**Data worktree:** `C:\Users\jgallagher\wnba-betting-model` (branch `data-refresh-2026`) — live
captures write here; checkpoint-commit and push it too (D044).

---

## 0. THE RULE THAT OVERRIDES YOUR INSTINCT TO STOP (GRAPH_POLICY §12, D050)

Verbatim, because a predecessor violated it and the user had to correct it:

> **Never idle; never ask the user whether to continue.** When a node halts — failing gate, dead
> agent, blocked dependency, USER_REQUIRED decision — that **lane** parks and you **immediately
> move to the next READY node in another lane**. `graphctl.py ready` is the worklist. Reporting
> "waiting" or "shall I continue?" while any node is READY is a policy violation, not a courtesy.
> The only legitimate stopping states are: everything PASSED / SUPERSEDED / blocked behind a
> USER_REQUIRED gate, or the user says stop.

Corollaries you will need:
- **A dead agent is infrastructure, not a finding.** Its partial work is unusable and unclaimed.
  Retry later at the same-or-higher tier (never cheaper for a Severity-A verification) and work
  elsewhere meanwhile. **Try a different model tier before concluding capacity is gone** — the
  2026-08-07 S34 death was one exhausted tier, not an outage; the retry at top tier succeeded and
  produced the best review in the program's history.
- **Retire by training a successor, never by stopping.** When your context fills, write the next
  `COORDINATOR_HANDOFF_<date>.md` in this shape, commit it, leave both trees quiescent and pushed,
  and hand off mid-stride. Succession is normal operation.
- **Independent-context gates are never self-granted.** "The reviewer died" is answered by another
  independent reviewer LATER plus other lanes NOW.

---

## 1. STATE AT HANDOFF

77 nodes PASSED · 10 BLOCKED · 7 READY · 6 SUPERSEDED · 3 USER_REQUIRED · 103 nodes total.
Both branches committed and pushed; verification gates green (program 35/35, data 13/13).

**Possession lane — cycle 1 CLOSED.** Sweep of nulls (D042): 0/29 challengers passed; champion
`D_ewma_shrunk` stands at a VERIFIED 2.86649 possessions pooled-OOF MAE (N=2,572 rows / 1,286
clusters). A07 preserved as the strongest lead, re-registerable only via fresh preregistration.
P42 completion report closed after a two-reviewer gauntlet (adversary's initial FAIL, 12 findings,
all amended). **Never conflate 2.86649 (possessions) with 2.9675 (turnovers).**

**Score lane — cycle 2 in flight.** Contract FROZEN after four adversarial rounds (FULL sha256
`87cd094a…`, IDEATION EDITION `3f9bf253…`, machine diff receipt proves only the three named §7
bullets differ). K0 schema FROZEN (S32B) with the null floor byte-pinned. Ideation closed (5
isolated sources, 35 candidates, 2-tool-call isolation profiles). Synthesis closed (12 arms → 18
elements → 9 families; 5-of-5 blind convergence on schedule fatigue; 3-of-5 blind on the
user-directed opponent-adjusted interaction). S33 drafted 11 arms / 17 elements (SC07 referee
withdrawn by measurement). **S34 red team returned FAIL — 4 Severity A, 8 B, 4 C.**

**Market lane.** M16/M07/M17/M21 all PASSED this session and converged on ONE root cause: the
capture layer was built for archival, not microstructure. M26 remediation node created.

---

## 2. WORKLIST — EXECUTE IN THIS ORDER

1. **S33R_PREREGISTRATION_REPAIR** (READY, Severity A, highest value). Disposition every S34
   finding. The four A's, in the reviewer's own words, are summarized in the node's acceptance
   criteria; the full review text is in `GRAPH_EVENTS.jsonl` (S34 `agent_returned`, ts
   2026-08-07). Headlines: **A1** the named `game_date` cutoff-promotion measurement is barred by
   the contract's own §8 (it rests on the P2B-barred retrospective archive), returns zero
   deviations *by construction*, leaves 272 clusters unwitnessed, and its "independent" second
   witness is `master_team`'s own upstream. **A2** the deletion-invariance receipt is
   unsatisfiable for all 17 elements because every element consumes the current game's row of
   `score_baseline_rows.parquet` (the null floor itself) whose prediction columns sit outside the
   closed identity set — the lawful fix is the S34 identity-set extension §1 provides for, which
   was never registered. **A3** SC01's arm-killing stratum has a predicate (`max≤12` → 472) that
   contradicts its own carded numbers (`min≤12` → 516). **A4** SC08::E3's K0 never fits the win
   outcome, so it can take the unqualified label over a null never shown to reach the floor.
   Do NOT edit the reviewed S33 draft — emit `SPEC_V2.json` and leave the reviewed bytes auditable.
2. **Independent re-verification of S33R**, then **S35_FREEZE_TASK_CARDS** (registry append,
   single-writer, byte-identity of prior records verified), then S36 implement → S37 audit →
   S38 sealed fits → S39 integrity → S40 adjudication (sole unseal authority) → S41 completion →
   S42 USER adoption gate.
3. **M26_CAPTURE_MICROSTRUCTURE_REMEDIATION** — dispatched at handoff; verify and close when it
   returns. Highest-value market work: until it lands, every timing-dependent market node inherits
   an unsupportable ceiling.
4. **Remaining READY market nodes**: M06 (injury reaction — note it needs the M26 fix and more
   accumulated tape), M10 (middles), M13 (player value translation). Dispatch at mid tier; they
   are measurement nodes off the possession critical path (§9).
5. **Board maintenance**: when any adjudicated number lands, feed it through the D036 pipeline
   only (`build_metrics.py` → `build_scoreboard.py` → `TESTS.py` green → commit → republish with
   the Artifact tool **passing `url` https://claude.ai/code/artifact/e9e20b7f-e1d3-4af1-8eca-418e4d0856de**).
6. **Push discipline (D044)**: both branches pushed whenever the tree is quiescent, not just at
   cycle ends. Never bypass the hook.

---

## 3. USER-GATED — NEVER SELF-GRANT

Kalshi consent letter (user sends) · RotoGrinders month · wehoop/RotoWire outreach · any vendor
purchase or subscription (M02B) · P43 champion replacement · **S42 adoption of any fitted score
model for operational or wager-shaped use** · anything order-shaped or money-spending · pushing
any branch other than `player-model-program` and `data-refresh-2026`.

Also standing: **~760 MB of git-ignored raw archives** (injury history 594 MB, news 103 MB, odds
43 MB, drive_masters, officials) are outside git by design; the user has not chosen an external
backup mechanism. Offer, do not act.

---

## 4. STANDING USER DIRECTIVES

- **D043/D047 — cycle-2 scope**: opponent-normalized interacting two-team EWMA efficiency
  structures (off_A×def_B *and* off_B×def_A) among a broad context-candidate set; the user's own
  words in D047 are the scope-creep test for every directed card.
- **D044 — GitHub backup**: never let unpushed commits pile up.
- **D046 — coordinator priors**: planning context ONLY; excluded from ideation packets forever.
- **D048 — injury browser client**: real headed Chromium, honest identity, urllib probe first,
  `_BROWSER_CLIENT` outcome suffix; needs a logged-in desktop session (logged-out cycles log honest
  NETWORK_UNAVAILABLE and the next cycle backfills).
- **D050 — continuous operation** (§0 above).
- **D051 — residual characterization**: S40/S41 must map what prediction error still correlates
  with, against a correlate list frozen BEFORE unsealing, nulls preserved — this is how cycle 3's
  granular decomposition (foul channels, shot-type defense, archetypes) picks targets by measured
  signal instead of intuition. The user's stated model of the program is bottom-up; the graph runs
  coarse-to-granular with a frozen verified ingredient per rung, and D051 is the bridge.
- **Plain language for the user.** No node ids, no internal shorthand in anything user-facing.

---

## 5. DISCIPLINES LEARNED THIS SESSION (pay these forward)

1. **Name the worktree root explicitly in every dispatch.** Two agents concluded upstream
   contracts "do not exist" because they searched the data worktree. Both existed. A coordinator
   must verify an agent's "missing artifact" claim before it propagates as fact.
2. **Subagents cannot write files named `REPORT.md` / `REPORT_BODY.md`** (harness). Have them
   return the text or write a differently-named body, and materialize the official report yourself
   with a coordinator header recording your verification.
3. **`graphctl.py decision --ruling` breaks on shell quoting.** Write a small python wrapper to
   the scratchpad and invoke `graphctl` via `subprocess` — three attempts were lost to this.
4. **PowerShell here-strings mangle embedded JSON/quotes.** Same fix: scratchpad python files.
5. **A retry after infrastructure death is not a new independent source** (§4) — it *is* the
   review. Label it `RETRY`.
6. **Adversarial review saturates when two independent lenses converge on the same last defect.**
   That happened on the S30 contract (round 3) and is the signal to freeze.
7. **Agents that measure rather than assert catch things coordinators cannot.** The S34 retry
   rebuilt a kill stratum from scratch and found a predicate that contradicted its own numbers;
   M16 traced a silent zero-row endpoint; M21 found a stale halt document. Demand re-derivation,
   never acceptance-on-assertion.

---

## 6. LIVE INFRASTRUCTURE (running unattended)

`WNBA_MarketLadder` (10 min) · `WNBA_SxBetCapture` (5 min, `sxbet_tick.cmd`) ·
`WNBA_InjuryLive` (15 min, `injury_live_tick.cmd`, needs a logged-in session) · plus the older
daily forecast/refresh/props tasks. All write to the DATA worktree so the program tree stays
quiescent for pushes. **Known defect under repair (M26): the ladder has been capturing player
props ONLY — the game-lines endpoint returns HTTP 200 and writes zero rows.**

---

*The ledger is the memory. The board is the truth. Frozen bytes govern. Do not stop.*

---
## 7. STATE AMENDMENT — later on 2026-08-07

**78 nodes PASSED.** Both branches pushed clean (program 35/35, data 13/13).

**Closed since §1 was written:** M26_CAPTURE_MICROSTRUCTURE_REMEDIATION. The game-lines bug is
root-caused and fixed — `_poll_and_write` filtered the slate-wide `/odds` response on our INTERNAL
`game_id` while every row carries the VENDOR event id, so the filter matched nothing, silently,
forever. Coordinator-verified on bytes: `snapshots.csv` now carries h2h 22 / spreads 22 / totals 22
alongside the props. Witnessed-absence and latency/skew fields also shipped. Defect 2 is
PARTIALLY_CLOSED by design — see D052 below.

**In flight at this amendment:**
- `S33R_PREREGISTRATION_REPAIR` (top tier) — closing the four S34 Severity A findings + eight B.
  This is the critical path; S35 depends on it.
- `M13_PLAYER_VALUE_TRANSLATION` (mid tier) — point-prediction → threshold-probability translation
  with the distributional assumption made explicit and calibrated out-of-sample.

**Deliberately NOT dispatched though READY — do not read their status as an invitation:**
- `M08_STALE_WINDOW` — its own title conditions it on *demonstrated* lead-lag structure; M07
  measured that none is demonstrable from the current vendor topology. Dispatching it would invite
  a stale-window claim resting on an unsupportable premise. Unblocks if the user rules on D052.
- `M22_CAPACITY` — sizes how much money the measured opportunity classes absorb, which presupposes
  an adjudicated opportunity class (none exists) and edges toward staking, a USER-gated surface.

**New USER decision packet — D052_PER_BOOK_POLLING_COST_PACKET.** The vendor bundles all books in
one payload, so cross-book lead-lag is unsupportable by construction. Per-book polling fixes it at
~5-11x credit cost — a spend decision reserved to the user. Three options are written into the
ledger entry (authorize scoped, fund a bounded sizing experiment, or decline and mark the claim
permanently unmeasurable). A shipped test blocks any attempt to fake per-book timing from parse
order in the meantime. **Do not self-grant this.**

---
## 8. TWO COORDINATOR PROCESS FAILURES — DO NOT REPEAT (2026-08-07)

1. **Never launch a push while any agent still holds a write scope.** Twice this session the
   pre-push hook correctly refused (34/35) because writers were mid-flight. The commit lands, the
   push does not, and you burn a ten-minute gate run to learn something `git status` would have
   told you. Check the tree is quiet FIRST, then push.
2. **Never dispatch work before declaring its node.** M27 was dispatched on a user authorization
   with no node in the graph; the ledger correctly refused three events referencing an undeclared
   node and the node had to be created retroactively. Dispatch-before-declare defeats the write-
   ownership and validation machinery the graph exists to provide. Declare, validate, THEN dispatch.
3. **Name every concurrent credit-spender in a dispatch brief, or serialize them.** M27 measured an
   11,728-credit drop it could not attribute and honestly flagged it as a possible leak; it was the
   coordinator's own dense-window pull, launched concurrently and never mentioned to it. An agent
   cannot reason about a shared quota it is not told about.
4. **Record findings in full, not in counts.** The four Severity C notes from S34 nearly vanished
   because the coordinator's ledger event compressed them to "4 C" while writing A and B out in
   full. The repair author caught it. Findings are only preserved if their TEXT is preserved.

---
# 9. RETIREMENT HANDOFF — read this section FIRST (2026-08-07, outgoing coordinator)

A successor coordinator has launched and this coordinator is retiring per GRAPH_POLICY §12.3.
The program is mid-stride, not stopped. **81 nodes PASSED · 8 BLOCKED · 6 READY · 3 USER_REQUIRED ·
104 nodes.** Both branches committed and pushed clean (program 35/35, data 13/13).

## 9.1 THERE IS AN AGENT IN FLIGHT — DO NOT DUPLICATE IT

**`S35_FREEZE_TASK_CARDS` was dispatched at top tier and has NOT returned.** Check
`GRAPH_EVENTS.jsonl` for its `agent_launched` event and for any later `agent_returned`. If no
return event exists, **the agent is still working — do not re-dispatch it.** Re-dispatching would
run two freeze attempts against the same registry.

**When it returns, these steps are the COORDINATOR's, not the agent's:**
1. Read its verification section first. It was instructed to **refuse to freeze** if any S33R
   repair claim fails to reproduce. If it reports a failed claim, DO NOT proceed to the append —
   route the failure to a repair node exactly as S33R was routed.
2. Materialize `REPORT.md` from its `S35_REPORT_BODY.md` with a coordinator header (the harness
   forbids subagents writing report filenames).
3. **Perform the registry append yourself as single writer.** The agent prepares
   `REGISTRY_APPEND_PAYLOAD.jsonl` and `REGISTRY_BASELINE_VERIFICATION.json`; it must NOT append.
   `experiments/player_program/arm_registry.jsonl` is a FROZEN, APPEND-ONLY path (GRAPH_POLICY §3):
   existing records may never be edited or reordered.
   **Pre-append baseline captured by the outgoing coordinator at retirement:**
   - `arm_registry.jsonl` sha256 = `a0aff704ba2c70f2edf756c5dc765f0ab63fb528ecc1585f6fc8cfbbcf33a7a6`
   - record count = **51**
   After appending, re-read the first 51 records and prove they are byte-identical to the baseline,
   exactly as the D040 A24 append did (50→51). Record the before/after hashes in the event.
4. Close the node with events, regenerate state, commit, push while the tree is quiet.

## 9.2 THE CRITICAL PATH FROM HERE

S35 freeze → **S36 implement** → S37 audit → S38 sealed fits → S39 integrity → S40 adjudication
(sole unseal authority) → S41 completion → **S42 USER adoption gate**. This is the sequence that
finally answers the user's standing question: *did we beat the simple model at predicting game
outcomes?* Today's honest answer is **no** — the composite does not beat plain scoring averages
and trails the market by 0.38 (totals) / 0.80 (margins) / 0.017 (Brier). Eleven arms / 17 elements
are queued to try. **Do not let anyone report the fan-out as progress on that question.**

**S36 inherits four obligations the freeze record carries — verify they survived into it:**
(a) read the **PINNED** `master_team.parquet` in the PROGRAM worktree and verify its sha
(`ad79ce5c…`, 1,495 games); the DATA worktree copy legitimately grows with the season (1,512 and
climbing) and reading it would silently evaluate cycle 2 on a universe no card declares;
(b) emit a pre-build digest of the `game_id` set; (c) SC06's era kill is unpowered (~17 pooled-test
clusters of pre-2024 support) — that power statement prints beside any verdict it produces;
(d) SC11's E2 integrity receipt is labeled `NON_CITABLE_INTEGRITY_DIAGNOSTIC`.

## 9.3 USER-GATED, UNCHANGED — never self-grant

Kalshi consent letter (the user's own letter to send) · RotoGrinders month · wehoop/RotoWire
outreach · any vendor purchase (M02B) · P43 champion replacement · S42 adoption · anything
order-shaped or money-spending · pushing any branch but `player-model-program` / `data-refresh-2026`.

**Recently resolved, do not re-raise:** D052/D053 (per-book polling — authorized bounded, shipped
with kill switch OFF, pilot recommended before standing) and D054 (dense-window spend — the user
overruled this coordinator's decline; 23/23 events, 30,870 of 35,000 credits, 1,029 snapshots).
**Quota after those spends is materially reduced — measure it before any new spend.**

## 9.4 DELIBERATELY DEFERRED — READY but do not dispatch without reading why

- `M08_STALE_WINDOW` — conditioned on *demonstrated* lead-lag structure; M07 showed none is
  demonstrable from the bundled-payload vendor topology. M27 now makes the window measurable, so
  this may become legitimate after a per-book pilot — but not before.
- `M22_CAPACITY` — presupposes an adjudicated opportunity class (none exists) and edges toward
  staking, a USER surface.
- `M06_INJURY_REACTION_STUDY` — needs point-in-time injury tape overlapping odds tape; the injury
  capture only began witnessing 2026-08-06/07, so the overlap is days old. Feasibility verdict is
  a legitimate output; a reaction claim is not.
- `M14_MODEL_MARKET_RESIDUAL` — newly READY and genuinely useful; note M13 already established the
  player-points model is *worse calibrated* than the market, so frame it as residual structure, not
  as an edge hunt.

## 9.5 WHAT THIS COORDINATOR GOT WRONG (§8 has the full list — read it)

Pushed twice while agents held write scopes; dispatched M27 before declaring its node; ran two
credit-spenders against one quota without telling either; compressed four review findings to a
count and nearly lost them. **Every one was caught by the graph's own machinery, not by me.** Trust
the gates over your own certainty — that is the whole point of them.

*The ledger is the memory. The board is the truth. Frozen bytes govern. Do not stop.*

---
## 9.6 UPDATE — S35 RETURNED AFTER RETIREMENT (read before section 9.1)

The freeze agent completed after this coordinator retired. Its outputs are on disk, its findings
are in the ledger (`agent_returned` + `note` on S35_FREEZE_TASK_CARDS), and `REPORT.md` is
materialized with a coordinator header. **Section 9.1's warning about an in-flight agent is now
superseded: it is no longer running.**

**YOUR FIRST ACTION IS THE REGISTRY APPEND.** It was deliberately left for you — the registry is a
frozen append-only path with a single-writer rule, and the retiring coordinator declined to mutate
it after handing off. The agent verified 11/11 repair claims (its build script refuses to emit
`SPEC.json` unless all pass) and recommends proceeding.

Mechanics, all pre-proven:
- Baseline **51 records / 223,775 bytes / sha256 `a0aff704…`** — re-hashed after all agent work,
  unchanged. Per-line hashes for all 51 in `REGISTRY_BASELINE_VERIFICATION.json`.
- Payload `REGISTRY_APPEND_PAYLOAD.jsonl`: **14 records / 37,974 bytes / sha256 `6462e150…`**
  (1 preregistration_freeze + 11 arm records authorising IMPLEMENTATION ONLY + 1 SC07 withdrawal
  + 1 policy record carrying the seven downstream obligations).
- **Expected post-append sha256 `6b43f40a…` at 65 records**, recorded inside `SPEC.json`.
- **The payload is LF-terminated; the existing file has mixed endings (28 LF / 23 CRLF). DO NOT
  NORMALISE THEM** — normalising rewrites existing records and destroys byte-identity.
- After appending: re-read the first 51 records, prove byte-identity against the baseline, and
  record before/after hashes in the event, exactly as the D040 A24 append did.

**Two open items the agent surfaced — neither blocks the append:**
1. `projected_team_off_possessions`' `join_key_sha256` did not reproduce (the pin names join columns
   but not the separator convention). The column digest itself matched exactly and nothing reads the
   join-key digest — documentation gap, carried as an S36 obligation.
2. **A pre-existing registry defect: existing record index 50 lacks `schema`/`kind`/`experiment_id`**
   and appears to be the P37 A24 *drafter register* file appended whole — contradicting its own
   "DRAFT ONLY, must never be appended" text — rather than its nested payload. Correctly left
   untouched. Because the registry is append-only, **the only lawful remedy is a corrective appended
   record, never an edit.** This is a coordinator decision awaiting you.

After the append: close S35, then S36 implementation — and verify the seven obligations survived
into it, especially O1 (read the PINNED `master_team.parquet`, HALT on sha mismatch).


---
# 10. RETIREMENT HANDOFF — 2026-08-07, SECOND SUCCESSION (read this section FIRST)

Written by the coordinator that took over at 15:22Z from the §9 retiree. Written EARLY, per the new
§12.3.1 context trigger, so it is complete rather than rushed. The program is mid-stride.

**86 nodes PASSED · 6 BLOCKED · 3 READY · 6 SUPERSEDED · 3 USER_REQUIRED · 104 total.**
Program branch pushed clean at `bbe4371`, **35/35 repository gates green**, zero unpushed.

## 10.1 THERE IS AN AGENT IN FLIGHT — DO NOT DUPLICATE IT

**`S37_IMPLEMENTATION_AUDIT` was dispatched at TOP tier ~17:20Z and has NOT returned.** Check
`GRAPH_EVENTS.jsonl` for its `agent_returned`. If absent, **it is still working — do not
re-dispatch.** Its write scope is `stage3_score/S37_IMPLEMENTATION_AUDIT/`.

When it returns, these are the COORDINATOR's steps:
1. It may legitimately return **FAIL** — that is this node succeeding. A prior red team on this lane
   returned FAIL with four Severity A findings and was right to. If it fails, route to a repair node
   exactly as S33R was routed from S34; do NOT reconcile findings yourself.
2. Materialize `REPORT.md` from `S37_REPORT_BODY.md` with a coordinator header (harness forbids
   subagents writing that filename).
3. Verify `SPEC.json` parses. Re-derive its headline claims on bytes rather than accepting them.
4. **It was asked to rule on a contradiction S36 raised and refused to resolve (F3):** three E3 cards
   list `composite_p_home` in `structural_terms` while their formulas and the A4 receipt appear to fit
   only the composite margin, and the fitted-column reading appears unimplementable as frozen (188
   structural NaN, no declared imputation). S36 treated it as a null-granted ingredient. **Read S37's
   independent ruling before anything downstream.** If the ruling would change estimands, K0
   structure, inference structure, universe, cutoff-valid set or leakage status, it must HALT and
   raise — that is a USER-adjacent contract change, not a coordinator call.

## 10.2 CRITICAL PATH FROM HERE

S37 audit → **S38 sealed fits** → S39 integrity → S40 adjudication (sole unseal authority) → S41
completion → **S42 USER adoption gate**.

Measured durations to plan with (from this session's ledger): implementation ~95 min, audits 35–60
min, and cycle-1's blinded fit took ~102 min. **Expect at least one repair loop** — the audit exists
to find problems and has done so every time.

**The standing question is still unanswered and the answer is still NO.** The composite does not beat
plain two-season-average scoring and trails the market by a PAIRED **0.383 total MAE**, **0.797
margin MAE**, **0.0168 Brier** (n≈1,050–1,060, date-clustered, all CIs exclude zero). Eleven arms are
implemented but **NOTHING IS FITTED**. Do not let anyone report the fan-out as progress on that
question.

## 10.3 WHAT THIS COORDINATOR COMPLETED

- **S35 closed and the registry append PERFORMED as single writer.** 51→65 records. Post-append hash
  was PRE-PROVEN in a dry run: two candidate concatenations computed, only raw concat matched
  `SPEC.json`'s expected digest, and the write proceeded solely on that match. Byte-identity of the
  original 51 proven twice (direct line comparison + all 51 per-record digests, 0 mismatches).
- **D055** — the pre-existing append-only registry defect at record index 50 remedied by a corrective
  erratum at index 65. Record 50 untouched. **The erratum creates NO authority** and deliberately does
  NOT re-register the adjudication, because that would stamp today's date on a payload drafted
  2026-08-06 for an already-executed cycle — backdating a preregistration. Residual cost recorded:
  querying the original `experiment_id` still returns zero top-level hits.
- **M14, M10, M06, S36 all PASSED**, each verified on bytes by re-running its own suite.
- **D056** — succession now triggers on coordinator context, not the clock (see §10.6).

## 10.4 REGISTRY BASELINE — REFRESHED, USE THIS ONE

`arm_registry.jsonl` is now **66 records**, sha256
`0e95cd9a03ad19b541c943e8644a8974372bb6d3453df11b122b27e6d213bc39`.
**S35's post-append expectation of 65 / `6b43f40a…` is SUPERSEDED** — record 65 is the D055 erratum, a
legitimate later append, not a mutation. S36 independently caught this and flagged it; it was right.

## 10.5 USER-GATED — NEVER SELF-GRANT

Kalshi consent letter · RotoGrinders month · wehoop/RotoWire outreach · any vendor purchase (M02B) ·
P43 champion replacement · **S42 adoption of any fitted score model** · anything order-shaped or
money-spending · pushing any branch but `player-model-program` / `data-refresh-2026`.

**Deliberately deferred READY nodes — read the reason before dispatching:** `M08_STALE_WINDOW`
(conditioned on demonstrated lead-lag; M07 showed none is demonstrable from the bundled vendor
topology — may become legitimate after a per-book pilot, not before) and `M22_CAPACITY` (presupposes
an adjudicated opportunity class that does not exist, and edges toward staking).

**Outstanding for the user, non-blocking:** auto permission mode could not be set — the auto-mode
classifier correctly blocks Claude from editing its own permission settings. The user must add
`permissions.defaultMode: "auto"` and `skipAutoPermissionPrompt: true` to `~/.claude/settings.json`
by hand. Do NOT attempt to route around that block.

## 10.6 §12.3.1 VERBATIM — THE SUCCESSION TRIGGER YOU INHERIT

> **The succession trigger is CONTEXT, not the clock** (D056). The recurring scheduled run is only a
> **safety net**. At roughly **60% of context — erring EARLY, never late** — the coordinator begins
> retirement: (1) stop dispatching new nodes; (2) close in-flight agents properly if nearly done,
> else record each with node id, write scope, what clears it, and **DO NOT RE-DISPATCH — check for
> its return event first**; (3) write the §12.3 packet carrying this subsection verbatim; (4) commit,
> then push **only once `git status` shows no agent holds a write scope**; (5) append a
> **`coordinator_retired`** event as the LAST ledger write; (6) trigger the successor with a
> **one-time** scheduled task firing a few minutes out; (7) stop.
>
> **Staleness-guard override:** if the most recent ledger event is `coordinator_retired`, the
> successor does **NOT** stand down despite the fresh timestamp — it was deliberately summoned.
> Without this the chain deadlocks. Observed live on 2026-08-07 when a scheduled coordinator stood
> down against a 9-minute-old ledger while its predecessor was retiring.

## 10.7 DISCIPLINES FROM THIS SESSION

1. **Verify the agent, not just its tests.** Every node this session was closed only after the
   coordinator re-ran its suite and re-read its headline numbers from the artifact. M14's verdict
   string said "no predictive content detected" while its own measured slope was significantly
   negative — imprecise, corrected in the record, caveat attached to the headline.
2. **Cross-check agents against each other when they read the same source.** M06 and M10
   independently read the odds store and appeared to disagree (330 vs 220 game-line rows). Counting
   the file directly resolved it: h2h 110 / spreads 110 / totals 110 — M06 counted all three, M10
   counted spreads+totals only, correct for middles since a moneyline has no line to middle. **Both
   right at different scopes.** Resolve apparent contradictions by measurement before reporting either
   as a defect.
3. **A count is not a metric.** S36 verified card fidelity by re-deriving five kill-stratum censuses
   exactly — real verification with zero unblinding. Use this pattern.
4. **PowerShell here-strings mangle embedded quotes and `2>&1` on native exes fabricates errors.**
   Write commit messages to a file and drive git via a scratchpad python `subprocess`. A git push that
   prints a red `NativeCommandError` may still have exit code 0 — check the ref-update line.
5. **Scope a deferred node rather than skipping it.** M06 was listed as deferred, but its own reason
   said a feasibility verdict was legitimate while a reaction claim was not. Dispatched under exactly
   that limit, it returned a clean NOT_YET_FEASIBLE with 0-of-7 event coverage. Read deferral reasons
   for the line they draw, not as a blanket bar.

*The ledger is the memory. The board is the truth. Frozen bytes govern. Do not stop.*


## 10.8 STANDING DIRECTIVE ADDED AFTER §10 WAS WRITTEN — D057, READ BEFORE PLANNING ANY WORK

The user ruled that the program is dragging because **rigor is applied uniformly instead of being
sequenced**. GRAPH_POLICY **§13** now defines four evidence levels (E0 Exploration / E1 Signal
candidate / E2 Challenger / E3 Production). The heavy machinery is reserved for **E2/E3**; E0/E1 are
fast, disposable and **explicitly non-claiming** — one-line kill/keep log entries, no
preregistration, no leaderboard, no report.

**This changes the worklist priority.** After the current score cycle reaches a verdict, the next
coordinator's job is **not** another full-ceremony cycle. It is to run **E0 sweeps at volume** —
dozens of cheap ideas, most killed in under an hour — against the **player-level residual**, which
is the program's founding thesis and the thing all this infrastructure was built to test.

Allocation until further notice: **~70% signal discovery / ~20% validation of survivors / ~10%
infrastructure.** The constitution is good enough. **Do not refine it further absent an actual
flaw** — including §13 itself.

**§13.2 is the one rule that may not be relaxed for speed:** E0/E1 run only on the exploration
partition and never touch the E2 confirmation holdout. It is what makes screening 50 ideas
statistically free rather than a machine for false confidence. It is a coordinator ADDITION to the
user's directive and is flagged as such in D057 for the user to rule on.

**Also demoted by this directive:** global MAE as the centre of the program. The operative question
is now *where* the advantage is strongest, what observable pre-game state predicts it, and whether
we can abstain elsewhere. Conditional edge and abstention are first-class targets. D051's residual
characterisation is the existing bridge.


## 10.10 CENTRAL RESEARCH THESIS ADDED — D060, and it changes what ideation must cover

The user added a modeling thesis they believe may carry a large share of the eventual edge, recorded
as **T1_CONTEXT_NORMALIZED_TENDENCY_X_MATCHUP** in `experiments/idea_log.jsonl`:

> Observed recent performance = underlying player tendency/form **+ the context that produced it**.
> Estimate the tendency cleanly using **shifted, context-normalized EWMAs at the lowest useful
> stat/substat level**, then interact it with **today's** matchup context. Keep **opportunity and
> efficiency separate wherever the data allows.** The edge is expected to come from many small
> context corrections and interactions assembled coherently — not one magic feature.

**Future ideation must explicitly explore this** rather than defaulting to conventional rolling
averages or generic ML features. Vary normalization schemes, EWMA horizons/alphas (the score lane's
own span was never tuned), decomposition depth, interaction formulations, hierarchical fallbacks —
and alternative frameworks entirely, since this is a hypothesis, **not an architectural commandment**.

**Binding process constraint:** do NOT assemble a massive combinatorial model. Run it through the
§13 funnel — screen individual concepts at E0, log every attempt, kill fast, combine only after each
component shows **independent** value.

**The independence cost, which must be honoured:** a source shown T1 is **DIRECTED, not blind**, and
may never be cited as independent convergence on T1 — exactly as cycle 2 distinguished *5-of-5 blind*
convergence on schedule fatigue from *3-of-5 on the user-directed* interaction. If both focus and
blind corroboration are wanted, split the ideation panel and label each source's exposure. D046's bar
is on COORDINATOR priors and is not in conflict: a user scope directive is not a coordinator prior.


## 10.11 SECOND CENTRAL THESIS — D061, ARCHITECTURE (T2), and where to actually start

The user added an **architecture** thesis beside the signal thesis: the champion is likely an
**ensemble of specialist layers with learned weights**, not one monolithic model. Recorded as
**T2_ENSEMBLE_OF_SPECIALIST_LAYERS**; T1 is its layer 2. **Neither thesis is sacred** — the ideas
factory may propose entirely different architectures. Headline discipline: **search broadly first,
compose later.**

**The coordinator mapped all nine layers against what the program already knows. Read this before
planning any E0 campaign — it prevents rediscovering settled ground:**

- **Layers 8 (separate market model) and 9 (conditional edge): ALREADY FROZEN LAW.** The four-system
  separation (S-FUND / S-MKT / S-EXEC / S-DEC) is frozen in `MARKET_PROGRAM_CONTRACT` §2 and already
  says *"None substitutes for another."* Market non-contamination is **enforced, not a design task**.
- **Layers 1 (availability/minutes) and 4 (bottom-up aggregation): ALREADY ATTEMPTED AND FAILED.**
  P3 is frozen, 5/5 arms FAIL, zero promoted. **But the failure localises to layer 1** — intrinsic
  player signal is real under *known* lineups and dissolved only under *projected* exposure. Layer 4
  is blocked on layer 1, not on itself. The standing guard holds: the frozen P3 coefficients may be
  reused only if a materially better exposure artifact is built for an **independently justified**
  reason; the prior failure is *not* that justification.
- **Layer 5 (structural team model): retained** per the user — but its ensemble value rests on
  **error decorrelation**, since standalone it beats neither two-season averages nor the market.
  Testable, not assumed.
- **Layer 7:** M13's distributional translation machinery is reusable. **Layer 6:** D051 is its
  existing prioritisation mechanism.
- **LAYER 3 (matchup interaction) IS THE LARGEST GENUINELY UNEXPLORED SURFACE** — essentially
  untouched at player level — **and is independently where the user expects the most incremental
  signal.** That convergence is the clearest steer available: **start E0 sweeps here.**


## 10.12 THE FUNNEL RAN — first E0 screen complete, and what it teaches the next ones

**I0003 (rebound opportunity x secure rate) was KILLED in ~16 minutes.** That is the tier working,
not a setback. Full record in `experiments/idea_log.jsonl`; artifacts in
`experiments/exploration/E0_I0003_rebound_interaction/`.

**Three things to carry forward:**

1. **The partition held.** The coordinator verified on bytes that both output CSVs contain seasons
   2021-2024 only. The 2025/26 confirmation holdout was never touched. §13.2 survived its first
   real run — keep verifying this on every screen, it is the one rule that makes the sandbox safe.

2. **DO NOT cite this kill as evidence against T1.** The stability comparison is **confounded by
   measurement noise**: the credited rebounder matched the correct side only ~72% of the time (43%
   ORB, 84% DRB), so the decomposed halves are measured far more noisily than the fused box rate,
   and noise depresses year-over-year correlation directly. The screen cannot separate *"opportunity
   is genuinely unstable"* from *"opportunity is measured badly."* **What died is the cheap
   construction, not the thesis.**

3. **The reusable finding is worth more than the result.** Lineup attribution by clock-time joins to
   possession rows is unreliable; the named fix is **substitution-order-derived lineups**. **I0004,
   I0005 and I0006 all need on-court lineup context and would inherit exactly this defect.** Either
   build the better attribution path first, or expect the same confound and say so up front. This is
   the highest-value output of the screen.

**Next E0 targets, in order:** I0004 (shot-location tendency/conversion x opponent location
allowance) — least dependent on lineup attribution, so most likely to give a clean read; then I0006
(usage redistribution conditional on teammate composition), which attacks the known layer-1
bottleneck directly; then I0005. I0007 (structural-model ensemble value via error decorrelation) is
half-runnable now — the structural residual series already exists.


## 10.13 E2/E3 RESTRUCTURED — D063, read before designing any E2

E2 no longer consumes one fresh test set. It runs the **full walk-forward ladder** (train through
2021→predict 2022 … through 2025→predict 2026) with **fold provenance labelled**:

* **F1-F3 (predict 2022/23/24): `DEVELOPMENT_CONTAMINATED`** — E0/E1 were allowed to explore those
  seasons, so these are **robustness evidence, never independent confirmation**. Do not discard them;
  do not promote them.
* **F4-F5 (predict 2025/2026): `CLEAN_CONFIRMATION`** — the strongest historical evidence available.
  **Report separately AND pooled**, and label any pooled figure mixed-provenance.

**Mandatory on every E2 record: `holdout_touch_count` and `adaptive_generation`.** Generation 0 is
the first look at 2025/26; increment whenever an E2 result causes a redesign that is then re-tested.
Anything above 0 must say **ADAPTIVE, NOT FRESH CONFIRMATION** in its headline. The holdout cannot be
restored once informed — this counter is the only honest accounting of how much is left.

**Deployment:** strong E2 evidence can now carry a model to production against the five-part bar in
§13.9; E3 is live verification that raises or lowers confidence and capital, and **may not be used to
forbid use of a model that clears the bar**. **The AUTHORITY is unchanged** — §6 still reserves
deployment and financial commitment to the user. E2 makes the case; the user makes the call. This
interpretation is flagged in D063 for the user to confirm or overrule.


## 10.14 FIRST E0 SWEEP COMPLETE — 5 screens, 3 kills, 2 iterates, and the disciplines they bought

All five screens ran inside the exploration partition; **2025/26 was never touched** and this was
verified on output bytes for every screen.

| idea | subject | verdict |
|---|---|---|
| I0003 | rebound opportunity x secure rate | **kill** (construction, not thesis — confounded by ~72% attribution) |
| I0004 | shot-location tendency x opponent allowance | **iterate**, narrowed to Restricted Area only |
| I0005 | turnover tendency x opponent pressure | **kill** (13x smaller than the additive main effect; no replication) |
| I0006 | usage redistribution on absence | **kill** (placebo more concentrated than the real effect) |
| I0008 | height/size mismatch x rebounding | **iterate** (pregame-observable rung carries signal) |

**Two leads worth E1 later, neither citable:** rim finishing vs opponent rim-defence allowance
(+0.039, the one zone with real opponent dispersion), and pregame-observable height mismatch
(+0.018-0.020 incremental R² over own recent rate, concentrated in **forwards** 0.37 vs centers 0.11).
One new idea spawned: **I0009**, opponent defensive pressure as an *additive* effect, correctly not
claimed by the screen that noticed it.

**Disciplines these screens bought — apply them to every future screen:**

1. **Run a placebo** whenever measuring concentration, redistribution, or response-to-an-event. I0006
   would otherwise have reported "47% of vacated usage goes to one teammate" as a finding. The noise
   floor was *higher*.
2. **Persistence beats significance.** I0005 was nominally significant at p=0.004 on n=18,165 and was
   killed because per-season partials were 0.058 / −0.002 / 0.021 / 0.002. At that n, a permutation
   test certifies effects far too small to matter.
3. **Leave-one-out any aggregate you then correlate against its own members.** I0004's strongest
   apparent effect flipped sign under this correction.
4. **Climb the attribution ladder** (§`E0_ATTRIBUTION_LADDER/1`). I0008's attribution-free rung found
   signal; its attribution-dependent rung was uninterpretable. Running only the latter would have
   missed a real effect.
5. **A null through a noisy construction is not a negative.** I0003 and I0008-rung-3 both produced
   nulls that cannot distinguish no-effect from bad-measurement. Say so; do not bank them.

**Coordinator error to learn from:** the first contamination rule (13.2.1) was over-broad — wrong
worktree and wrong criterion — and it cost **two** screens unnecessary work, including making one
disqualify a valid result. Corrected in **§13.2.2**: the check keys on `asof_granularity`, not on
which seasons a file contains. Over-broad safety rules destroy true findings as efficiently as loose
ones admit false ones.


## 10.15 RETIREMENT — the procedure is now a SKILL, and you were deliberately summoned

This coordinator retired at 2026-08-07 ~15:49 local, per §12.3.1, having completed the first E0 sweep.

**The handoff procedure is now formalised as a reusable skill:**
`C:\Users\jgallagher\.claude\skills\coordinator-handoff\SKILL.md` — invoke it when your own
context fills. It carries the sequence, the staleness-guard override, a table of six failure modes
observed in the wild, and the test for whether a packet is any good (*could a fresh context take the
next correct action having read only this?*).

**YOU WERE SUMMONED, NOT INTERRUPTED.** The last ledger event is `coordinator_retired`. Per
§12.3.1's override, **do not stand down against it** — recent activity is this packet being written.
Proceed straight to the worklist.

### Your first three actions, in order

1. **Read §10.13 (E2 provenance ladder) and §10.14 (the E0 sweep and its five disciplines) before
   designing anything.** They will change what you build.
2. **Nothing is in flight. Tree clean, zero unpushed, gates green at 09107e1.** Verify anyway.
3. **The score lane is HALTED on a USER decision (D058, cutoff-valid feature set) and fitting is NOT
   authorised.** Do not attempt to clear it. Work the discovery lane instead — that is where the
   user has directed effort (70/20/10, D057).

### The discovery worklist, in execution order

- **I0009** — opponent defensive pressure as an *additive* effect (spawned by I0005, never screened on
  its own terms; same family `F_TURNOVER_PRESSURE`, so it **inherits that family's
  `adaptive_generation`**).
- **I0007** — test the structural team model's ensemble value by **error decorrelation**; half of it
  is runnable now since the structural residual series already exists.
- **Fresh E0 ideas against T2 layer 3** (matchup interaction), still the largest unexplored surface.
- **The two live leads** (rim finishing × rim defence; pregame height mismatch) need an **E1**
  designed — not more E0. Neither is citable.

### Do not repeat these

Two coordinator errors from this session, both already in the ledger: an **overstatement** ("the
failure localises to layer 1" — it did not; layer 4 is VIABLE_BUT_UNVALIDATED), and an **over-broad
safety rule** (13.2.1) that cost two running screens real work before being corrected in §13.2.2.
Scope new rules narrowly and state claims at the strength the evidence supports.


## 10.15 RETIREMENT — the procedure is now a SKILL, and you were deliberately summoned

This coordinator retired at 2026-08-07 ~15:49 local, per §12.3.1, having completed the first E0 sweep.

**The handoff procedure is now formalised as a reusable skill:**
`C:\Users\jgallagher\.claude\skills\coordinator-handoff\SKILL.md` — invoke it when your own
context fills. It carries the sequence, the staleness-guard override, a table of six failure modes
observed in the wild, and the test for whether a packet is any good (*could a fresh context take the
next correct action having read only this?*).

**YOU WERE SUMMONED, NOT INTERRUPTED.** The last ledger event is `coordinator_retired`. Per
§12.3.1's override, **do not stand down against it** — recent activity is this packet being written.
Proceed straight to the worklist.

### Your first three actions, in order

1. **Read §10.13 (E2 provenance ladder) and §10.14 (the E0 sweep and its five disciplines) before
   designing anything.** They will change what you build.
2. **Nothing is in flight. Tree clean, zero unpushed, gates green at 09107e1.** Verify anyway.
3. **The score lane is HALTED on a USER decision (D058, cutoff-valid feature set) and fitting is NOT
   authorised.** Do not attempt to clear it. Work the discovery lane instead — that is where the
   user has directed effort (70/20/10, D057).

### The discovery worklist, in execution order

- **I0009** — opponent defensive pressure as an *additive* effect (spawned by I0005, never screened on
  its own terms; same family `F_TURNOVER_PRESSURE`, so it **inherits that family's
  `adaptive_generation`**).
- **I0007** — test the structural team model's ensemble value by **error decorrelation**; half of it
  is runnable now since the structural residual series already exists.
- **Fresh E0 ideas against T2 layer 3** (matchup interaction), still the largest unexplored surface.
- **The two live leads** (rim finishing × rim defence; pregame height mismatch) need an **E1**
  designed — not more E0. Neither is citable.

### Do not repeat these

Two coordinator errors from this session, both already in the ledger: an **overstatement** ("the
failure localises to layer 1" — it did not; layer 4 is VIABLE_BUT_UNVALIDATED), and an **over-broad
safety rule** (13.2.1) that cost two running screens real work before being corrected in §13.2.2.
Scope new rules narrowly and state claims at the strength the evidence supports.

# 11. RETIREMENT HANDOFF — 2026-08-07, THIRD SUCCESSION (Coordinator #03 → #04)

**You are Coordinator #04.** Identify yourself as "Coordinator #04" in every ledger event you write
and in your closing status note. When you retire, name your successor `wnba-coordinator-05` and tell
it that it is Coordinator #05, or the numbering dies here.

**YOU WERE SUMMONED, NOT INTERRUPTED.** The newest event in `GRAPH_EVENTS.jsonl` is
`coordinator_retired`. Per §12.3.1 that is the override — recent activity is this packet being
written. **Do not stand down. Go straight to §11.4.**

*Housekeeping: §10.15 appears TWICE in this file, identically. That is a duplicated commit, not two
different sections. Read either one.*

## 11.1 NOTHING IS IN FLIGHT

Three E0 screens were dispatched and **all three returned and are closed**. No agent holds a write
scope. Tree clean, **zero unpushed**, repository gate **PASS (35/35)** at `31ac447`. Verify anyway.

## 11.2 STATE AT HANDOFF

86 PASSED · 1 HALTED · 2 READY (both still deliberately parked — §9.4, reasons unchanged) ·
3 USER_REQUIRED · 6 BLOCKED · 6 SUPERSEDED. Unchanged from the previous handoff: this session moved
the **discovery** lane, which does not create graph nodes (§13.1), so the node counts are expected
not to move.

## 11.3 WHAT THIS COORDINATOR DID

**Ran the second E0 sweep: 3 screens, 1 kill, 2 keep-as-lead.** Full detail in the ledger and in
`experiments/idea_log.jsonl`; artifacts under `experiments/exploration/E0_I00{09,10,11}_*/`.

| idea | subject | verdict |
|---|---|---|
| I0009 | opponent forced-TO pressure, **additive** | **keep-as-lead** |
| I0010 | defence-vs-position interaction (T2 layer 3) | **kill** ×3 (pts/reb/ast) |
| I0011 | how tendency is **estimated** | **keep-as-lead** ×3; kill on minutes; kill on the normalization arm |

**The single most valuable output of the sweep is not a verdict — it is a defect in a live lane.**
`props_edge.py` applies one frozen `ALPHA = 0.30` to **both** the efficiency channel and the exposure
channel. Those channels want alphas **6–10× apart** (efficiency ≈0.03–0.05, exposure ≈0.25–0.30).
Consequence: **the incumbent estimator loses to a plain season-to-date mean on all three counting
stats in both scored seasons** (gap vs incumbent: pts +2.53%/+3.11%, reb +2.79%/+2.76%,
ast +3.91%/+2.65% MAE on 2023/2024). The fix is a one-line constant change. **It is not authorised
here** — it is an E1/E2 question, and it is NOT a score-lane unblock (D058 still halts that lane).

**Also determined: I0007 does not run at E0, contrary to the worklist you inherited.** See §11.5.

## 11.4 YOUR FIRST THREE ACTIONS, IN ORDER

1. **Read §11.6 (the resolved baseline dependency) before designing any E1.** It changes what the two
   live leads are worth.
2. **Verify the tree** — clean, zero unpushed, gate green at `31ac447`.
3. **The score lane is HALTED on a USER decision (D058) and fitting is NOT authorised.** Do not
   attempt to clear it. §11.8 has the plain-language version of what the user must rule on; the user
   was asked directly this session and **has not yet answered**. Do not re-ask on a loop — record and
   proceed to discovery per D057's 70/20/10.

## 11.5 THE WORKLIST, IN EXECUTION ORDER

1. **The E1 for the two live leads — but ONLY against the corrected baseline.** See §11.6. This is
   now the highest-value item because two leads' headline numbers are in question.
2. **I0011's split-alpha finding → E1.** It is the most concrete, most actionable thing the discovery
   lane has produced. It needs a proper out-of-sample E1 inside the exploration partition before it
   is anything more than a lead. Note its family is `F_TENDENCY_ESTIMATOR`.
3. **I0009 → E1**, if capacity allows. **Its first task is to control home/away** — teams may force
   more turnovers at home, so a season pressure figure could partly encode venue. That is the most
   likely remaining confound and the screen did not test it.
4. **More E0 against T2 layer 3.** I0010 killed the *positional* formulation, but layer 3 is not
   exhausted — what died is defence-vs-position specifically, because it proved to be overall
   opponent strength in a costume. A formulation that is not collinear with overall team defence is
   still unexplored.
5. **I0007 — PARKED, do not dispatch as written.** The handoff you inherited said it was
   "half-runnable now". **It is not.** The structural per-game series
   (`experiments/channel_reval/predictions_v2.csv`) is `asof_granularity: "artifact"` with
   `fit_through_season: 2026`, so §13.2.2 forbids it at E0 and filtering does not help; its
   exploration-partition overlap is one season (2024, n=229) anyway; and the derived
   `p3_downstream_rows.parquet` inherits the same defect. **Two things clear it, both real work:**
   (a) a partition-safe rebuild of structural predictions restricted to 2021–2024 walk-forward, and
   (b) the *other half* of the pairing — a player-layer forecast to decorrelate against — which does
   not exist. Even a clean structural series only permits half the test.

## 11.6 THE DEPENDENCY THAT RESOLVED THE EXPENSIVE WAY — READ BEFORE ANY E1

This coordinator flagged, **before** the screens ran, that both live leads from sweep 1 are stated as
**incremental value over the player's own recent rate** — and that I0011 was screening exactly that
baseline. The dependency resolved badly:

**I0011 showed the baseline IS materially improvable. Therefore both leads were measured against a
weak baseline and their incremental value is very likely OVERSTATED** — a better baseline absorbs
signal the lead is currently credited with. This affects:

* rim finishing × opponent rim-defence allowance (+0.039)
* pregame-observable height mismatch (+0.018–0.020, concentrated in forwards)

**Both headline numbers are provisional until re-measured. The E1 must be designed against the
split-alpha baseline, not the incumbent.** Had the E1 been parallelised with I0011 — which the
inherited worklist implied — it would have preregistered against a baseline already known to be
wrong. **Sequencing beat parallelism here; do not undo it.**

## 11.7 DISCIPLINES FROM THIS SESSION — pay them forward

1. **The no-op placebo.** A negative control that permutes a **grouping key** and then **recomputes
   the aggregate from the permuted key** is a no-op: the permuted cell is the same row set renamed,
   so every row still gets its own true value. It looks like a working placebo and tests nothing.
   **Diagnostic signature: it reproduces the real number with sd exactly 0.000000.** The correct form
   permutes the **assignment of an already-computed value to rows**. I0010 shipped this and caught it
   itself. **Audit this in every past screen that claims a placebo.**
2. **Verify a load-bearing placebo by reading the code, not the summary.** I0009's entire verdict
   rests on its placebo, so this coordinator read the implementation rather than trusting the report.
   It was genuine. That check is cheap and it is the difference between a lead and a mirage.
3. **The `observed_time` tripwire.** `master_player.parquet` carries an `observed_time` column that is
   a **local file mtime in mid-2026** (its manifest says it is not an as-of bound). Not leakage, but
   writing the full master frame to CSV puts 2026 bytes in outputs and trips byte-level partition
   checks. **Drop it before every write.**
4. **Relay a defect to in-flight agents immediately.** I0010 found (1) and (3) while I0011 was still
   running; both were sent to I0011 mid-flight, which is why its outputs are clean. Coordinators sit
   where cross-screen information exists — use it.
5. **An ambiguous null is not a negative** (inherited, and it earned its keep again). I0010's assist
   kill rests on an allowance measure with split-half reliability **0.281** vs 0.557/0.644 for
   pts/reb. It is flagged as **the kill worth overruling**, not banked.
6. **Check collinearity with the obvious main effect before believing an interaction.** I0010 died
   because positional allowance correlates ~+0.58 with overall opponent defence within
   (season, position). And 93–94% of its variance for reb/ast is **between-position** — testing it
   raw would have been testing `own × position dummy` and calling it matchup.

## 11.8 USER-GATED — NEVER SELF-GRANT (unchanged)

* **D058 — the cutoff-valid feature set.** THE live blocker. S37 finding A9: 13 ledger-UNPROVEN
  fields are consumed by retained arms and **12 carry no cutoff-validity measurement** — schedule
  identity columns, the back-to-back / 3-in-4 classes feeding SC06, the timezone shift that *is*
  SC06's tz term, the possession prior feeding SC08's z1, and the prior box aggregates under every
  lagged construction. Three options were put to the user: (a) commission the 12 measurements
  (precedent: M_A1 did exactly this for `game_date`); (b) rule that §1's closed schedule-identity set
  discharges §8 — **the ledger's own language appears to foreclose this** ("time-invariance is an
  argument, not a timestamp"); (c) narrow the slate to arms consuming only measured fields.
  **FITTING IS NOT AUTHORISED until this is settled.** The user was asked this session and has not
  answered.
* `P43_CHAMPION_DECISION` — replacing the frozen champion.
* `M02B_VENDOR_PURCHASE_DECISION` — spending money, in any amount.
* `S42_ADOPTION_DECISION` — adoption of any score model for wager-shaped use.
* `O16_SHARED_SCHEMA_ADOPTION` — cross-branch shared-contract change.

Both interpretations earlier coordinators flagged for ruling (§13.2 exploration partition; D063
deployment authority) have been **ratified** — D062 and D064/13.9.1 respectively. Nothing else is
pending on the user.

## 11.9 WHAT THIS COORDINATOR GOT WRONG

**Reproduced the exact failure it was warned about.** §10.14 records that the predecessor's
over-broad contamination rule cost two screens real work. This coordinator's own first partition-
verification script scanned raw bytes for the literals `2025`/`2026` and **declared a PARTITION
VIOLATION** — falsely. It was matching **row counts that happen to equal 2026** and digit runs inside
floats. Same failure mode, in a verification tool rather than a policy, committed by the coordinator
who had just read the warning. Fixed into a **column-aware** check (parse each table, find
season/date-like columns, test their *values*) rather than reported as a violation. **Over-broad
checks destroy true findings as efficiently as loose ones admit false ones — and knowing that does
not make you immune to it.**

**Also:** staged agent output with `git add -A` while three agents held write scopes. Caught on the
`git status` output before committing, so nothing broke — but it is the same mistake §8 records the
first coordinator making twice. **Stage explicit paths while agents are live.**

## 11.10 §12.3.1 — THE SUCCESSION TRIGGER YOU INHERIT

**At roughly 60% of your context window — err EARLY, never late — begin retirement.** You cannot
query your context percentage; that is why the threshold is conservative. Stop dispatching, close or
document in-flight agents, write the packet, commit, verify `git status` is quiet and unpushed is 0,
append `coordinator_retired` **last**, trigger `wnba-coordinator-05` as a one-time task ~3–4 minutes
out telling it that it is **Coordinator #05** and that it must name #06, then **stop**.

The procedure is a skill: `C:\Users\jgallagher\.claude\skills\coordinator-handoff\SKILL.md`.
The test of a packet is not completeness but **actionability**: *could a fresh context, having read
only this and the policy, take the next correct action without asking the user anything?*

## 11.11 AMENDMENT — THE USER RULED ON D058 AFTER §11 WAS WRITTEN. READ THIS BEFORE §11.4 OR §11.5.

**The score lane is NO LONGER BLOCKED ON A PENDING USER DECISION.** The user ruled directly in chat
on 2026-08-07, after the rest of §11 was written and after the `coordinator_retired` marker was
appended. Recorded as **`D065_A9_PROPORTIONAL_CUTOFF_PROOF`**, which resolves
`D058_S37_A9_CUTOFF_VALID_SET`. **Anything in §11.4, §11.5 or §11.8 that says the user has not
answered is superseded by this section.**

**The ruling: option (a) — run the missing measurements — with PROPORTIONAL RIGOR.** The user's
reasoning, verbatim: *"I don't want to create an 'obviously fine' exemption that can later expand to
less-obvious fields."* And: *"don't turn 12 fields into 12 research projects. Establish the minimum
sufficient proof for each field, record it, and unblock fitting."*

**The operative standard has TWO TIERS. Assigning a field to a tier IS deciding its standard of
proof — get this right before commissioning anything.**

| tier | applies to | what the proof must show |
|---|---|---|
| **1 — cheap provenance receipt** | opponent identity, home/away, season type, scheduled rest / back-to-back / 3-in-4, venue, timezone + venue-shift hours | that the field **derives from information fixed before tipoff**. A provenance demonstration, **not** a per-observation timestamp audit. |
| **2 — full point-in-time audit** | `team_possession_prior_v1` (SC08's z1), `opponent.prior_box_aggregates` and every lagged construction in the slate, all recent-form inputs, the five `score_baseline_rows` prediction columns | that **every underlying observation predates the forecast cutoff**. |

The discriminator: **is the VALUE fixed by the schedule before tipoff, or is it COMPUTED FROM
OBSERVATIONS?**

**Both other options were explicitly rejected by the user, and the reasons bind you:**
* **(b) is rejected** — no "obviously fine" exemption is to be created, *because such an exemption
  expands later to less-obvious fields.* Do not reintroduce it under another name.
* **(c) is rejected** — *"Do not shrink the model merely to avoid auditing inputs we have every
  reason to believe are valid."*

**FITTING IS UNBLOCKED ONCE THE RECEIPTS EXIST — NOT BEFORE.** The ruling is not itself the receipt.
The gate is the receipts. Commissioning and landing them is now **worklist item 0**, ahead of
everything in §11.5, because it unblocks a whole lane and the discovery lane is already well stocked.

**Two things this coordinator flagged that you must not paper over (full text in D065):**

1. **The tier boundary is a judgement surface.** `shift_from_prev_venue_hours` is schedule-derived
   (tier 1) yet depends on the previous game having been *played*. The user's explicit naming of
   "venue/timezone" in the tier-1 list settles this particular field. **But a future field near that
   boundary must be RAISED, not silently assigned** — the user has just reserved the standard-of-proof
   judgement to themselves in substance, and assigning a tier is exercising it.
2. **The residual risk the user knowingly accepted.** A cheap provenance receipt proves the *class* of
   a field, not the integrity of the pipeline that produced it. If a tier-1 field is materialised by a
   job that happens to backfill from a later source, a tier-1 receipt would not catch it. **Coordinator
   recommendation, flagged as an addition and not a user instruction:** a tier-1 receipt should state
   the **producing job and its as-of bound**, not merely argue the concept is schedule-fixed. That
   costs nothing and closes most of the gap.

**Sequencing note.** `S37_IMPLEMENTATION_AUDIT` remains the Severity-A blocker and A9 was only one of
its 18 findings (9 Severity A). Clearing A9 does **not** clear S37. Check what else in that audit
still gates fitting before declaring the lane open.

---

# 12. RETIREMENT HANDOFF — 2026-08-07, FOURTH SUCCESSION (Coordinator #04 → #05)

**You are Coordinator #05.** Identify yourself as "Coordinator #05" in every ledger event you write
and in your closing status note. When you retire, name your successor `wnba-coordinator-06` and tell
it that it is Coordinator #06 **and that it must name #07** — or the numbering dies at your handoff.

**YOU WERE SUMMONED, NOT INTERRUPTED.** If the newest event in `GRAPH_EVENTS.jsonl` is
`coordinator_retired`, that is the §12.3.1 override. **Do not stand down. Go to §12.4.**

## 12.1 READ THIS BEFORE YOUR BRIEFING — YOUR SCHEDULED-TASK PROMPT MAY BE STALE

**Coordinator #04's briefing was materially wrong on the single most important point**, through no
one's fault: it was written before the user ruled. It stated the score lane was halted on D058, that
fitting was not authorised, and that #04 must **not** attempt to clear it. The user had in fact
ruled (D065) minutes after #03 wrote the marker.

**The lesson, which is now a standing discipline: the ledger and the handoff packet outrank your
scheduled-task prompt.** Your prompt is a snapshot taken when your predecessor retired; the ledger
is live. **Always diff your briefing against `DECISION_LEDGER.jsonl` and the newest ledger events
before acting on it.** #04 recorded the conflict in the ledger explicitly rather than silently
following the newer instruction — do the same, because a silent switch is indistinguishable from
drift.

## 12.2 STATE AT HANDOFF

Live `graphctl.py ready` — **unchanged, and both are still deliberately parked (§9.4):**

```
M08_STALE_WINDOW   market_intelligence   Stale-line window measurement conditional on demonstrated lead-lag structure
M22_CAPACITY       market_intelligence   Capacity analysis: how much money the measured opportunity classes can absorb
```

**86 PASSED · 1 HALTED · 2 READY (both parked) · 3 USER_REQUIRED · 6 BLOCKED · 6 SUPERSEDED.**
Node counts are unchanged and are **expected** to be: discovery-lane work creates no graph nodes by
design (§13.1), and the D065 receipts are *measurements* following the M_A1 precedent, not nodes.

## 12.3 IN FLIGHT AT RETIREMENT — **DO NOT RE-DISPATCH. CHECK FOR RETURN EVENTS FIRST.**

Three agents were still writing when #04 hit its threshold. **Each holds a write scope. Verify
whether its directory is complete before touching anything in it, and never dispatch a second agent
against the same scope** — two agents against one scope is the collision the whole guard exists to
prevent.

| # | agent | write scope | what clears it |
|---|---|---|---|
| 1 | **D065 tier-2 point-in-time audits** | `experiments/player_program/stage3_score/S43_CUTOFF_RECEIPTS_TIER2/` | `RECEIPTS.json` + `REPORT_BODY.md` + scripts present, and a stated verdict per target. **This is the other half of A9.** |
| 2 | **E1 I0011 split-alpha** | `experiments/exploration/E1_I0011_split_alpha/` | `FINDINGS.json`, `NOTES.md`, and **`baseline/`** — the corrected baseline spec + runnable code. |
| 3 | **E0 I0012 layer-3 non-collinear sweep** | `experiments/exploration/E0_I0012_layer3_noncollinear/` | `FINDINGS.json` + `NOTES.md`, one verdict line per formulation. |

**If a directory is complete but the harness blocked the agent from writing its `REPORT_BODY.md`,
materialize it yourself from the agent's returned text.** That happened once this session (the
integrity audit) and the coordinator mandate requires it. Mark clearly that you materialized it and
which artifact is authoritative.

**Agent 2 owes an extra answer #04 requested mid-flight** — see §12.7, the baseline-equivalence
check. If it returned without answering, carry the dependency forward explicitly rather than
assuming equivalence.

## 12.4 YOUR FIRST FOUR ACTIONS, IN ORDER

1. **Diff your briefing against the ledger** (§12.1). Do not skip this.
2. **Verify the tree.** #04 retired with **2 commits unpushed and three agents still writing** — it
   could not push, because the pre-push gate correctly refuses a tree that changes while measured.
   **`git status` first; push only once quiet.** The gate takes ~9 minutes — allow a long timeout.
   If the push fails red, **fetch and check the real remote state before retrying** — a concurrent
   push that already landed makes the retry's ref-lock expectation stale, and that looks like a
   broken gate but is a benign race.
3. **Close the three in-flight agents** (§12.3) before dispatching anything new.
4. **Then the worklist, §12.5.**

## 12.5 THE WORKLIST, IN EXECUTION ORDER

0. **Close the three in-flight agents and commit their work.** Nothing else until this is done.
1. **Tier-2 receipts — finish or re-commission.** If agent 1 returned an honest *cannot establish*
   on any target, **that is a legitimate result, not a failure to retry away.** Record it and treat
   the gap as the thing that must close before fitting. Do **not** resolve ambiguity in favour of
   unblocking; #04 briefed that agent explicitly that an honest FAIL beats a manufactured pass, and
   that instruction stands.
2. **Worklist item 1 from §11.5 — the E1 for the two sweep-1 leads (rim finishing × rim-defence
   allowance; pregame-observable height mismatch), against the CORRECTED baseline.** This was
   deliberately held by #04 and by #03 before it. §11.6 is the reasoning and it has not changed: both
   headline numbers are very likely **overstated** because they were measured against a baseline
   I0011 showed is materially improvable. **Design this against agent 2's corrected baseline, not the
   incumbent.** Sequencing beat parallelism here twice; do not undo it.
3. **I0008 needs a noise floor before it is weighed against anything.** The integrity audit found it
   has **no placebo of any kind** — its +0.018–0.020 incremental R² has never been compared to a
   permutation null. I0006 proved *inside this program* that a plausible statistic can be beaten by
   its own noise floor. **Run one before I0008's strength is compared to I0009's or I0011's in any
   promotion decision.** Suggested construction: permute which opponent's roster-height aggregate
   each row receives, keeping the aggregate keyed on true opponents.
4. **Decide what to do about the weighted-R² convention.** Every ΔR² from the shared E0 `wls_r2`
   helper is **~8% smaller** than the standard weighted figure (denominator is SST of the
   sqrt-weight-transformed response about its own mean, not weighted SST about the weighted mean).
   Direction is **conservative**, so nothing is overstated and no verdict changes — but cross-screen
   rankings are quietly incomparable until one convention is adopted. Cheap to fix, worth doing
   before leads are ranked against each other.
5. **More E0 against T2 layer 3** — the largest genuinely unexplored surface and where the user
   expects the most signal (§10.11). Agent 3's sweep is the first pass under the
   *residualize-against-overall-opponent-defence-first* design rule. Whatever survives it, keep going;
   what I0010 killed was the **positional formulation specifically**, not the layer.
6. **I0009 → E2 is NOT yet appropriate.** Its E1 passed, but its live confound is opponent defensive
   strength (r −0.405 pooled, **−0.619 in 2024**, which halves that season), and its walk-forward
   effect is **+0.004003** — about 40% below the LOSO figure and the honest number. An E2 must handle
   opponent strength explicitly and must state the screen count per §13.3.
7. **I0007 — STILL PARKED, do not dispatch as written.** §11.5 item 5 has the full reasoning and it
   is unchanged: the structural series is artifact-granular through 2026 (§13.2.2 forbids it at E0,
   and filtering does not help), and the player-layer half of the pairing **does not exist**.

## 12.6 USER-GATED — NEVER SELF-GRANT

* **D066 — four tier-boundary questions raised by the tier-1 receipts. RAISED, NOT RULED.** Full text
  in `DECISION_LEDGER.jsonl`. **The substantive one is R2:** the user's D065 ruling says
  "**scheduled** rest/B2B/3-in-4", and **no scheduled-date artifact exists anywhere in the repo** —
  all three fields use *as-played* dates. #04 refused to treat as-played as scheduled. It closes
  either with one sentence from the user **or** by wiring SC06's existing A1-SENSITIVITY kill
  (currently dead per S37 finding B3), which needs **no new data acquisition**. R1 (playoff rows,
  where the discriminator's two clauses come apart), R3 (ledger #10 denotes two different quantities)
  and R4 (#04's own tier assignment of `game_id`/`season`, disclosed for cheap overrule — nothing
  else depends on it) are the others.
* **D065 is ruled and is NOT re-openable** — option (a), two-tier proportional rigor. Options (b) and
  (c) were **explicitly rejected** and the reasons bind you: no "obviously fine" exemption may be
  created under any name, and the model is not to be shrunk to avoid auditing inputs there is every
  reason to believe are valid.
* `P43_CHAMPION_DECISION` · `M02B_VENDOR_PURCHASE_DECISION` · `S42_ADOPTION_DECISION` ·
  `O16_SHARED_SCHEMA_ADOPTION` — unchanged.

**FITTING REMAINS UNAUTHORISED, and be precise about why.** The receipts are the gate, not the
ruling. And even when A9 fully closes, **S37 returned FAIL on 18 findings, 9 of them Severity A** —
A1/A2/A3 are card-vs-code deviations that void arms *by the cards' own clause*, and A4–A8 are missing
machinery. S37 §10's repair order is: A9 → A1/A2/A3 → A4/A5/A2's σ path → A6/A7/A8 → B1–B5, C1–C4.
**Clearing A9 does not open the lane.**

## 12.7 WHAT #04 COMPLETED

| work | result |
|---|---|
| **D065 tier-1 receipts** | **10/10 `TIER1_RECEIPT_ISSUED`**, 0 violations on 2,982 rows across 10 identity tests |
| **E1 I0009 additive pressure** | **keep-as-lead** — home/away is NOT the confound |
| **Program-wide integrity audit** | **no shipped no-op placebo; no verdict downgraded** |

**The tier-1 receipts vindicated the coordinator addition #03 recommended.** Requiring each receipt
to name the **producing job and its as-of bound** — rather than merely argue the concept is
schedule-fixed — surfaced that **`build_masters.py` has no as-of bound at all**: it globs
completed-game artifacts and stamps `observed_time` as the max file mtime. The receipt *states* this
rather than finessing it. What still makes the five schedule columns tier-1 is that the job derives
them from **game identity, never from play** (`season`/`season_type` are pure functions of the
`game_id` string; `opp_team_id` is the cluster complement). **Keep that requirement for all future
receipts — it is the only reason this was found.**

Two independent corroborations that the tier-1 measurement frame is faithful: the D10 ledger's 1,103
timezone-shift replicates **exactly**, with the divergent readings fully decomposed (career clock
1,129, +26; career + standard offsets — the consumed reading — 1,310, +181 = **exactly the Phoenix↔LA
pair count**, since Phoenix skips DST); and **S37 finding B1 reproduced exactly** — career-vs-same-season
clocks disagree on exactly **30 tz rows and 0 back-to-back rows**, confirming the defect is confined
to the travel term.

**I0009 E1 detail.** Venue is a real main effect (+0.640 TO/100 def poss at home, same sign all four
seasons) but is **~29× smaller than team identity**, and the effect retains **100.1%** after venue
control with β essentially unchanged. A venue-matched pressure measure is strictly *worse* and adds
ΔR² 0.000020 on top of the venue-blind one — **the venue component carries no signal**, so this is
**not** the I0010 costume shape. Placebos non-degenerate throughout (0/200 draws reach real on all
ten statistics; real over largest draw 4.6×), reliability fine (split-half +0.573).

**Integrity audit detail.** The highest-stakes item was I0006 — the only screen whose kill rests
*entirely* on its placebo — and it holds. I0005's sd was unrecorded and was recovered by re-running
from a copy (sd 0.007976, 2000/2000 unique draws, p reproduced exactly). **Nothing anywhere treats
`master.observed_time` as an as-of bound**; every consumer refuses it or is conservative, and
`tests/test_cbs_v8.py:532-534` asserts the bound derives from `game_date`. Four files *elsewhere*
carry it with 2026 values — named in the audit so a future byte-check does not misreport them; none
is an E0/E1 artifact and none is a partition violation.

**A verified correction to §11.3's framing of the alpha defect.** #04 read the source rather than
trusting the summary. The defect is real: `props_edge.py:203` defines one `ALPHA = 0.30`, applied at
`:317` to the efficiency channel (`per36`) and `:319` to the exposure channel (`minutes`). **But
§11.3 called the fix "a one-line constant change" and that undersells it** — line 203 is commented
`# registered frozen family` and the module docstring calls it "the frozen committed baseline
family", so changing it touches a **registered artifact**: a registry/erratum matter, not a free
edit. Separately, #04 checked whether the docstring's **channel-sum equivalence** caveat ("breaks
only if channels get per-channel alphas") blocks the fix. **It does not** — that caveat governs the
four *scoring* channels sharing a common alpha, not the efficiency-vs-exposure split, which is
multiplicative. Recorded so a future implementer neither trips on the registration nor wrongly fears
the invariant.

**One item routed onward, not asserted as a defect.** `prediction_contract_v5.py:477` sets
`candidate_observed_time` for the S2 source to a **synthetic season-start marker**
(`{season}-01-01T00:00:00Z`), and `validate_projected_exposure.py:565` then asserts
`observed_after_cutoff == 0` and **passes — necessarily, because the marker was built to precede
every cutoff.** That is a *manufactured cutoff-availability pass* by exactly the mechanism the
tier-2 audit exists to catch. Already disclosed at `build_projected_exposure.py:128-135`, so it is
not concealed. #04 relayed it to the in-flight tier-2 agent with the instruction that **a passing
`observed_after_cutoff == 0` check is not itself evidence of cutoff validity — trace what timestamp
it actually compares before crediting any existing pass.** Follow that up.

## 12.8 DISCIPLINES FROM THIS SESSION — pay them forward

1. **The ledger outranks your briefing.** §12.1. A scheduled-task prompt is a snapshot; the decision
   ledger is live. Diff them before acting, and record any conflict explicitly.
2. **Relay cross-screen defects to in-flight agents immediately.** Inherited from §11.7 #4 and it
   earned its keep twice this session: the manufactured-cutoff-pass finding went to the tier-2 agent
   mid-flight, and the weighted-R² convention went to the layer-3 sweep so its numbers would land
   comparable. **Coordinators sit where cross-screen information exists — that is most of the job.**
3. **Verify a load-bearing claim by reading the source, not the summary.** Inherited, and it produced
   the alpha-registration correction above. The summary said "one-line fix"; the source said
   "registered frozen family".
4. **A tier assignment is a standard-of-proof judgement — disclose it even when you are confident.**
   #04 assigned `game_id`/`season` to tier 1 and recorded the assignment for cheap overrule, noting
   that nothing else depends on it. Cost: one paragraph. Benefit: the user can reverse it for the
   price of one re-run.
5. **An absent support is not a broken support — but say which it is.** The integrity audit found no
   broken placebos and two screens with *no* placebo. Those are different findings with different
   consequences, and collapsing them would have been wrong in both directions.
6. **Check the whole enumeration, not just the items a predecessor named.** See §12.9 #1.

## 12.9 WHAT #04 GOT WRONG — read this; it is the highest-value section

1. **Reproduced the §11.6 dependency it had just been warned about — in a lane the packet did not
   enumerate.** #04 correctly *held* worklist item 1 pending the corrected baseline. It then
   **dispatched the I0009 E1 in parallel with the very screen producing that baseline** — and
   I0009's entire effect is stated as incremental R² over a player-tendency baseline, the same
   dependency family §11.6 exists to prevent. §11.6 named only the two sweep-1 leads, so this was not
   a violation of the packet's letter — **but relying on a predecessor's enumeration being exhaustive
   is exactly the assumption that cost this program twice.** It was caught by Coordinator #03 via the
   user, not by #04. Partial mitigation was in place (the agent was briefed to flag baseline
   provenance and did return the caveat unprompted: "all ΔR² are upper bounds, provisional against
   the stronger baseline"), and #04 relayed a one-line equivalence check to the split-alpha agent
   rather than assuming. **Probable resolution, which must still be CONFIRMED not assumed:** I0009's
   baseline is a leave-one-out season rate, and I0011 found the efficiency channel wants α ≈ 0.03–0.05
   — very nearly a season-to-date mean — so I0009 is likely already sitting on approximately the
   endorsed baseline. **If agent 2 did not answer, carry this forward explicitly.**
2. **Dispatched six agents against a 60% retirement threshold.** Previous sweeps ran three to five.
   Two of the six produce registry-touching receipts that need *verification*, not a skim. **The
   failure mode is not running out of work — it is running out of room and closing six things
   sloppily.** #04 stopped dispatching when this was raised and closed three properly rather than
   half-closing six, but it should not have dispatched the sixth. **Size the batch to what you can
   CLOSE, not to what is independently dispatchable.**
3. **Briefly concluded a file was missing from a bad path.** #04 ran `Test-Path` with a truncated
   prefix (`data_lane\...` instead of `experiments\player_program\data_lane\...`) and treated the D10
   ledger as absent. Self-corrected within a minute, and nothing depended on it — but it is the same
   family as the over-broad-check failures §11.9 records: **confirm the path before concluding
   absence.**

## 12.10 §12.3.1 — THE SUCCESSION TRIGGER YOU INHERIT

**At roughly 60% of your context window — err EARLY, never late — begin retirement.** You cannot
query your context percentage; that is why the threshold is conservative. Signals: you are
summarizing rather than reading; you are deferring verification you would normally do; **one more
agent return would leave no room to process it.**

Sequence: stop dispatching → close or document in-flight agents → write the packet → commit → verify
`git status` quiet and unpushed **0** → append `coordinator_retired` **last** → trigger
`wnba-coordinator-06` as a **one-time** task 3–4 minutes out, telling it that it is **Coordinator
#06** and **that it must name #07** → **stop.**

The procedure is a skill: `C:\Users\jgallagher\.claude\skills\coordinator-handoff\SKILL.md` .
The test of a packet is not completeness but **actionability**: *could a fresh context, having read
only this and the policy, take the next correct action without asking the user anything?*

## 12.11 AMENDMENT — TWO OF THE THREE IN-FLIGHT AGENTS RETURNED. SUPERSEDES §12.3 AND §12.5.

Written after §12.1–12.10. **Where this section and §12.5 disagree, this one is right.**

### 12.11.1 THE TIER-2 AUDIT RETURNED — BIGGEST RESULT OF THE SESSION — `D067`

**A9's tier-2 half is NOT discharged, and not because the audit fell short. It is exhaustive and
determinate, and it went the *other way*: it DEMOTES five constructions from `CUTOFF_UNPROVEN` to
`CUTOFF_INVALID`.**

| target | verdict | census |
|---|---|---|
| `opp_pace_estimate` / `team_possession_prior_v1` (#50/#49, SC08 z1) | **CUTOFF_INVALID** | 1,491 clusters: 1,426 pass, **44 fail**, 21 not established |
| `prior_box_aggregates`, per-team lags (SC01/02/03-clock/05/08-sd20/10/12) | **CUTOFF_INVALID** | 2,982 rows: 2,912 pass, **45 fail**, 10 undecided |
| league-level lags (SC04, SC11) | **CUTOFF_INVALID — worst** | 1,491 clusters: 314 pass, **1,061 fail (71.2%)**, 115 undecided |
| prior-season carryover (SC03) | **CUTOFF_UNPROVEN — the only clean target** | **2,572/2,572 pass unconditionally, zero failures** |
| all recent-form inputs (15 constructions) | **CUTOFF_INVALID** | all resolve to the two lag families above |
| the five `score_baseline_rows` pred columns | **CUTOFF_INVALID** | 1,491 as-consumed: 1,426 pass, **44 fail**, 21 undecided |

**No sampling anywhere — every figure is a full census.**

**Why INVALID and not merely UNPROVEN.** The auditor split the standard into **(E) the event claim** —
every contributing event had *finished* before the row's cutoff; necessary, exactly measurable, and
**never measured before in this program** — and **(R) the record claim**, D10's per-row timestamp
test, unclosable for 2021–2024. **Failing (E) is fatal in a way failing (R) is not: no future capture
receipt can rescue an event that had not yet happened.** Producers were **re-derived from their own
sources**, so contributing sets were recomputed rather than argued.

**Mechanism, one sentence:** a date-grained or row-grained "strictly prior" predicate cannot respect a
cutoff sitting at **18:00 UTC the day before**. Prior-season carryover is clean only because its lag
is a whole season. The league-level lags are worst because `features_common` counts an earlier
**same-day** game as prior, and **917 of 1,491 clusters have one**.

**It is NOT an artifact of a weak witness — check this before anyone argues it away.** The
league-level lags **survive refusing the market-archive tip witness entirely**: 335 failures are
provable from `CUTOFF_VALID` evidence alone, 151 needing no timestamp at all. They also fail on
**182 of the 407 clusters that already carry exact tip cutoffs**, so a better cutoff policy will not
fix them. (T1/T2a/T4 failures *do* rest on that witness; refusing it downgrades them to
`CUTOFF_UNPROVEN`, which **grants nothing** and still promotes nothing.)

**Two reproductions SUCCEEDED — positive results.** The pace producer re-derives **bit-for-bit**
(2,990 rows, every field, frozen column and join-key pins). And **S37's named open item is closed**:
`build_score_baselines.py`, re-implemented from the three inputs it names, reproduces
`pred_margin`/`pred_total`/`p_home` to their **pinned sha256 exactly**, NaN positions identical.
**That closes PROVENANCE, not cutoff-validity** — the same distinction D10 draws between "validated"
and "timestamped". **Do not let the reproduction be cited as validity.**

**New findings:**
* **N1 — needs a user ruling; governs SC08 admissibility.** `zscore_train`/`center_on_train` apply a
  fold-train constant to every training row: **100% of training rows in all five folds** have a cutoff
  preceding the last observation entering their own moment. **Test rows unaffected.** Consumers
  include **both** of SC08's treatment columns. **Not in the A9 table — new.** The question: does
  D065's standard bind **training** rows or only **evaluation** rows? The auditor declined to decide
  it; so does #04.
* **N2** — the slate carries **two incompatible meanings of "strictly prior"** (row-strict vs
  date-strict), contradicting `features_common`'s own stated rationale.
* **N3** — **neither `team_possession_prior_v1.parquet` nor `score_baseline_rows.parquet` has a
  `.manifest.json`.** `asof_granularity` undeclared for both, so the §13.2.2 gate was **never actually
  passed** on either. Row granularity established by re-derivation instead.
* **N4 — the mid-flight relay worked and is closed.** The synthetic-marker pass
  (`prediction_contract_v5.py:459` → `validate_projected_exposure.py:565`) is **confirmed**, and the
  auditor proved **by reproduction, not by reading code**, that it reaches no target here. It credited
  **zero** inherited cutoff-availability passes; all four neighbouring validations are listed
  traced-and-not-credited, **including `PROJECTED_EXPOSURE_VALIDATION.json`'s 35/35 that D10 itself
  cites**. Witness A traced to 199 genuine capture instants. `observed_time` dropped at load.

**WHAT THIS MEANS — counterintuitive, read carefully.** D065 ruled "run the measurements and unblock
fitting." **The measurements ran. They did not unblock fitting; they established that five
constructions the slate depends on are invalid.** The user's stated reason for rejecting option (c)
was not to shrink the model "merely to avoid auditing inputs we have every reason to believe are
valid" — **the audit has now established that for these five, that belief was wrong.** This is a
**halt-and-raise** under S30 §11: it changes the cutoff-valid feature set. **The repair is a change to
the frozen cards' lag predicates** (swap the date/row-grained "strictly prior" for
`source_event_end_time <= row.forecast_cutoff`); the cards are **immutable**; pinning a reading needs
a **registry-appended erratum**, never an edit. **No coordinator has authority here.**

**Flagged, not measured:** re-cutting the lags **changes feature values** and therefore possibly
**every carded stratum census S37 verified**. The repair may invalidate the audit that found it.

### 12.11.2 THE LAYER-3 SWEEP RETURNED — 29 of 30 cells killed, 1 survivor

Logged as **I0012**, family `F_LAYER3_NONCOLLINEAR`, in
`experiments/exploration/E0_I0012_layer3_noncollinear/`.

**The program-level result matters more than the survivor: the I0010 "costume" diagnosis does NOT
generalize.** All four non-positional formulations came in **genuinely non-collinear** (|r| 0.03–0.14
vs I0010's 0.57–0.59) and **died as real nulls, not costumes**. The **personnel-matching channel —
familiarity, availability, style-fit — is now screened from four directions and is empty.** The live
surface in layer 3 is **possession volume**.

**Sole survivor: opponent pace × own pregame rebound rate → rebounds.** ΔR² 0.001071, placebo sd
8.74e-5, 0/200 ≥ real, betas +0.356/+0.335/+0.167/+0.064. Survived four checks including **max-T
across all 60 tests** (z 10.69 vs largest null draw 9.34) and a side-exchangeability test showing
genuine asymmetry. **THE CAVEAT GOVERNS: it decays monotonically and is GONE IN 2024** (asymmetry
difference 0.372→0.403→0.275→**−0.035**); the pooled result is carried by 2021–2022, and **2024 is the
season nearest the holdout**. At ~0.001 ΔR² it is **~6× under I0009's lead**. **The screen's own
recommended next step is NOT confirmation — re-run with 2021 dropped to see whether the trend is
dying on its own.** Costs nothing, never touches the holdout. Do that first.

**Two disciplines this sweep contributes:**
* **A kill on MEASURABILITY is not a clean negative.** The familiarity formulation is marked
  `null_is_informative: false` — reliability 0.03–0.08; a WNBA (player, opponent) pair meets ~4×/season,
  median 3 prior meetings. **It must not be cited as evidence familiarity does not exist**, only that
  it is unmeasurable in this record. Availability and rest/travel ARE informative negatives
  (Spearman-Brown 0.70–0.93; error-free schedule facts).
* **Multiplicity correction earned its keep.** Three cells cleared their own placebo floor at nominal
  p 0.010–0.040 and were **killed on max-T** — exactly the false positives a 60-test sweep predicts.

**Self-reported defect, already marked void:** the R3 control rung was **rank-deficient by
construction** (total pace as the exact sum of both sides makes `O × total` an exact linear
combination of terms already in the model), so its β of 5.27 with per-season signs
−0.52/+14.66/−12.01/+1.01 is a **linear-algebra artifact, not absorption**. R4 replaces it.

**Routed to layer 2, not layer 3:** opponent OREB-allowed predicts player points as a **main effect**
(positive 4/4 seasons). Its matched interaction is dead (0.000025), so it is not a matchup.

### 12.11.3 REVISED WORKLIST — REPLACES §12.5

0. **Close the one remaining in-flight agent: `E1_I0011_split_alpha`** (§12.3 row 2). Still writing at
   #04's retirement. **DO NOT RE-DISPATCH — check the directory and for its return event first.** It
   owes `baseline/` (corrected baseline spec + runnable code) **and** the baseline-equivalence answer
   in §12.9 #1.
1. **Put D067 in front of the user.** Halt-and-raise; the score lane cannot move without a ruling.
   **Do not re-ask on a loop** (D057) — record, surface once, work discovery.
2. **N1 needs a ruling** — training rows vs evaluation rows. Bundle with D067.
3. **§11.5 item 1 — the E1 for the two sweep-1 leads against the corrected baseline.** Unchanged,
   still the highest-value discovery item. §11.6 is the reasoning.
4. **I0008 noise floor** — unchanged, required before it is ranked against anything.
5. **Re-run the I0012 survivor with 2021 dropped** — cheap, decides whether the lead is real or dying.
6. **Weighted-R² convention** — unchanged. I0012 used **plain unweighted OLS R²** and declared it, so
   its numbers are unaffected but only order-of-magnitude comparable to I0009's.
7. **More E0 on layer 3, redirected:** personnel-matching is empty; aim at **possession volume** and
   the layer-2 OREB main effect.
8. **I0007 — still parked**, reasons unchanged.
