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
