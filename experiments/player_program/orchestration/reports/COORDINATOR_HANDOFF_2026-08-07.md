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
