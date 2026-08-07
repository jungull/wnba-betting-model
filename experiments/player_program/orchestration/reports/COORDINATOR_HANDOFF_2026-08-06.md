# COORDINATOR HANDOFF — 2026-08-06 (evening)

You are the on-duty coordinator of the WNBA program graph. The user is away; you operate
autonomously inside the gates. **The graph method governs everything you do.** Read, in this
order, before acting:

1. `experiments/player_program/orchestration/GRAPH_POLICY.md` — the law (append-only events,
   frozen bytes govern, D015 model tiering, USER_REQUIRED gates, quiescent-tree push rule).
2. `experiments/player_program/orchestration/reports/CURRENT_STATUS.md` + `python
   experiments/player_program/orchestration/scripts/graphctl.py ready` — live state.
3. `experiments/player_program/orchestration/DECISION_LEDGER.jsonl` — D023–D038 are the
   market-lane + evidence-standard rulings that bind you (D034 graduation standard, D036
   scoreboard semantics, D037 granular, D038 leaderboard spec).

Working root (this file's worktree): `C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program`
Live data branch worktree (read-only for agents; coordinator commits allowed):
`C:\Users\jgallagher\wnba-betting-model` (branch data-refresh-2026).

## Coordinator disciplines (learned today, non-negotiable)

- Dispatch briefs: constants INLINE, contract files by FULL PATH with sha256 (D020 + the
  hash-ambiguity lesson in D030). Agents never run git; you commit, task-scoped.
- Subagents cannot Write files named `REPORT.md` (harness rule) — when a node requires one,
  the agent returns the text and YOU materialize it with a coordinator header.
- Freeze raw outputs (hash_artifacts.py --freeze-output) BEFORE any reviewer reads them.
- Every node close: validation command → events (agent_returned / validation_passed /
  node_passed) → `graphctl.py state` + `status` → commit. Never rewrite history.
- Workflow resume ids do NOT transfer across sessions. If an in-flight wave's results are
  needed, read what the agents wrote INTO THE REPO (they write to node dirs) — the repo is
  the baton, not the session.
- Evidence: nothing is "SEALED" before an evaluation ran; lifecycle BUILT → AUDITED →
  FITTING → EVALUATED/SEALED → ADJUDICATED. Implementation tests ≠ predictive evidence.
- User reports: plain language, no node-ids/shorthand (his standing preference).

## State at handoff

**Possession lane:** P36 PASSED (22/22 arms, 331/331 implementation tests; four RAISED
ambiguities + the A10 EWMA pin are P37's worklist). **A seven-agent wave was in flight at
handoff** (3 P37 auditors → files land in `stage2b/P37_IMPLEMENTATION_AUDIT/AUDIT_*.md`;
legacy verification → `experiments/market_program/SCOREBOARD/granular/legacy_verified_metrics.json`
+ VERIFICATION_REPORT.md; book ranking → `experiments/market_program/BOOKIE_BASELINE/book_ranking.json`;
graduation report → `experiments/market_program/D033_GRADUATION_REPORT.md`; leaderboard build →
regenerated `experiments/market_program/SCOREBOARD/` per `LEADERBOARD_SPEC.md`).

**Market lane:** M00–M05, M09, M11, M25, M03 PASSED. Full 2022–26 featured odds archive +
player_points props archive on the data branch (`data/market_snapshots/historical/`). Live
ladder scheduled task `WNBA_MarketLadder` runs every 10 min (first live rows in
`data/market_snapshots/snapshots.csv`). SX Bet capture verified
(`experiments/market_program/EXCHANGE_CAPTURE/sxbet/`, `--loop` mode built, NOT yet scheduled).
Kalshi PARKED pending user consent letter (D035 — never capture without it). Injury: live
pipeline built (12/12), a 63-PDF capture cycle was running in background at handoff — check
`experiments/market_program/INJURY_OFFICIAL/live/injury_snapshots.csv` for rows; history
recovery runbook written, event catalog schema frozen.

**Scoreboard/Leaderboard artifact** (user-facing, persistent):
https://claude.ai/code/artifact/e9e20b7f-e1d3-4af1-8eca-418e4d0856de
GENERATED ONLY: edit inputs → run `build_scoreboard.py` → TESTS.py green → commit → publish
via the Artifact tool **passing that URL as `url`** (a new session mints a new URL otherwise).
Favicon stays 📊.

## THE WORKLIST — execute in this order, per the graph method

1. **Close P37**: when the three AUDIT_*.md files exist, adjudicate findings exactly like
   D026 (Severity A → arm withdrawn or pinned-repair, never a frozen-structure change;
   preserve disagreements; decision ledger entry), assemble SPEC.json + REPORT.md
   (coordinator), validation, node_passed, commit. If audit files are absent, dispatch the
   audit per `prompts/P37_IMPLEMENTATION_AUDIT.md` (3 independent session-tier auditors).
2. **Dispatch P38_BLINDED_FIT** per `prompts/P38_BLINDED_FIT.md`: the runner
   (`stage2b/P36_IMPLEMENT_ARMS/runner/`) executes real fits; the executor MUST explicitly
   name the P27 fold policy (runner RAISED item — default SEASON_BLOCK unless P37 ruled
   otherwise) and set the unsealing env var the runner requires. Results land SEALED under
   `stage2b/SEALED_RESULTS/` — nobody reads them, including you, until P39/P40.
3. **P39_RESULT_INTEGRITY → P40_PRIMARY_ADJUDICATION** per their prompts. Only P40 opens
   results. Then feed adjudicated numbers to the scoreboard pipeline (new metrics.json
   entries with full D036 provenance; evidence class VERIFIED), regenerate, republish (url!).
4. **Market lane maintenance**: commit + verify the graduation report when it lands (D034:
   coordinator re-derives spot counts before accepting); schedule SX Bet loop
   (`schtasks /Create /SC MINUTE /MO 5` on a wrapper like market_ladder_tick.cmd) and the
   Wikipedia weekly harvest; once injury_snapshots.csv has rows, schedule the 15-min injury
   capture the same way. Then the two credit spends the ledger already authorizes
   (D029/D033, ~64k credits in hand): (a) rebounds/assists/threes props discovery pass
   (empties are free; pattern of backfill phase 2 with those market keys), (b) dense
   windows: set `DENSE_WINDOW_COORDINATOR_CONFIRMED_BACKFILL_DONE=1` (backfill IS complete)
   and run `experiments/market_program/DENSE_WINDOWS/dense_window_puller.py --execute`
   with its 35,000 cap after confirming remaining quota > 45k.
5. **Ongoing**: after each integration cycle with a quiescent tree, push
   `player-model-program` to origin (D017/D018 — never bypass the hook). Leave
   plain-language milestone notes for the user in your final messages.

## Gates you may NEVER self-grant (verbatim from policy + D024/D035)

Purchases/subscriptions; wagers or anything order-shaped; credentials beyond the existing
.env mechanism; Kalshi capture (parked on user letter); modifying frozen gates/canonical
artifacts/Arm D; changing the primary target; CONFIRM/AUTO execution modes; pushing any
branch other than player-model-program. When genuinely blocked on one, write the decision
packet, record a ledger note, and continue other lanes.

---
## LIVE ADDENDUM (primary coordinator, evening, after the first sealed pass)

DIVISION OF LABOR: while GRAPH_EVENTS.jsonl shows activity fresher than 30 minutes, the
primary session is driving - your staleness guard applies; append your check-in note and
stand down. You take the wheel ONLY when events go stale. Never run a second copy of an
in-flight step: check EXECUTION_LOG.md / progress.jsonl under stage2b/P38_BLINDED_FIT and
the latest ledger events before dispatching anything.

STATE RIGHT NOW: P36 and P37 PASSED (D039). P38 first pass SEALED (15 fitted; MANIFEST in
SEALED_RESULTS). D040 continuation wave IS IN FLIGHT: per-fold P25 wrapper re-runs
(A05,A12,A13,A14,A15,A17,A22) + A08 fits + A20/A21/A23 remediation builds + the A24
amendment draft. When it lands, the sequence is: coordinator verifies + commits; appends
the A24 registry amendment (single-writer, byte-identity discipline as before, payload at
stage2b/P37_IMPLEMENTATION_AUDIT/A24_AMENDMENT_PAYLOAD.json); fits A24 + the three
remediated arms (sealed, same executor discipline); closes P38 (SPEC/REPORT, events,
commit); dispatches P39_RESULT_INTEGRITY per its prompt (independent verifier context;
receipts/seeds/folds/universes verified WITHOUT opening results); on P39 pass, dispatches
P40_PRIMARY_ADJUDICATION which alone opens the seals; adjudicated numbers then flow to the
leaderboard ONLY through the D036 pipeline (regenerate, tests, commit, republish with the
artifact url in the handoff). NOTHING in SEALED_RESULTS is readable before P40 - by anyone,
including coordinators.

---
## FINAL ADDENDUM - PRIMARY SESSION STANDING DOWN (user-directed, end of day one)

The primary session stops after processing the in-flight score-baselines task. A NEW CHAT
becomes coordinator; the scheduled task wnba-coordinator-on-duty remains only as the
dead-man backstop (its staleness guard yields to any active coordinator writing events).

STATE AT STAND-DOWN: 66 nodes PASSED. Cycle 1 complete through P41: the possession
challenger program returned a SWEEP OF NULLS (D042) - 0/29 passed, champion D_ewma_shrunk
stands at a VERIFIED 2.86649 possessions MAE (N=2,572/1,286, five-fold blind walk-forward),
A07 preserved as the strongest lead, all negative results permanent. Board v6 live at the
artifact URL above with the first VERIFIED row and the turnovers-vs-possessions labeling
corrected. P41 closed as the carded empty-entrant confirmation.

IN FLIGHT AT STAND-DOWN: the D043 score-composite baselines (workflow wf_50c213c0-8e2,
outputs land at experiments/market_program/SCORE_BASELINES/). If its outputs exist but are
uncommitted when you arrive: run its TESTS.py, verify, commit, feed the numbers to the
board via the pipeline (matched-universe market comparisons only), republish with the
artifact url.

NEW CHAT - FIRST ACTIONS IN ORDER:
1. Read this handoff top to bottom + GRAPH_POLICY.md + CURRENT_STATUS.md + D023-D043.
2. Close out SCORE_BASELINES if pending (above).
3. P42_SCIENTIFIC_COMPLETION per its prompt - the formal cycle-1 closure.
4. End-of-cycle push of player-model-program per D017/D018 (quiescent tree, verify_all
   hook ~10 min, never bypass).
5. THE D043 CYCLE-2 FORMALIZATION: graduate F12/F13 into a full preregistered challenger
   cycle on the existing machinery (target contracts -> cards -> audit -> sealed fits ->
   adjudication), A07 carried as a registered candidate.
6. Market lane maintenance backlog: diagnose the injury-live capture (63 PDFs discovered,
   0 rows written - capture_log.csv holds the attempts); schedule the SX Bet loop and
   Wikipedia weekly harvest (schtasks pattern per market_ladder_tick.cmd); the
   rebounds/assists/threes props discovery pass (D033, ~63k credits in hand, empties
   free); dense-window execution (env var + 35k cap per the DENSE_WINDOWS README).
7. USER decisions still parked: Kalshi consent letter (user sends), RotoGrinders month,
   wehoop/RotoWire outreach. Never self-grant any gate in the list above.

The ledger is the memory. The board is the truth. Frozen bytes govern. Good hunting.
