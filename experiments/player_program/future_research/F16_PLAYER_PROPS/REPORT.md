# F16_PLAYER_PROPS — REPORT

**Node:** `F16_PLAYER_PROPS` · **Lane:** future_research · **Type:** documentation
· **Written:** 2026-08-06 · **Branch:** `player-model-program` · **Retry:** 1 (first launch
died on a usage limit before producing output; this is the same node retrying).

## Epistemic status of this output

> DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to
> fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration
> and an independent gate review.

---

## What was found on entry

The write scope directory already contained two files from an earlier pass (or the same retried
attempt): `measure_props_evidence.py` and `MEASUREMENTS.json`. Both were read in full before any
new work. The script reads only files this node is permitted to read (`data/props_capture/*`,
`data/masters/master_player.parquet`, and two artifacts under
`experiments/player_program/turnover_targets_v1/`), fits nothing, joins no settlement, and does not
touch `stage2b/SEALED_RESULTS/`. It was re-run, unmodified, to confirm the numbers in
`MEASUREMENTS.json` reproduce live on this branch rather than trusting a possibly-stale file:

```
python experiments/player_program/future_research/F16_PLAYER_PROPS/measure_props_evidence.py
```

Output matched the existing `MEASUREMENTS.json` byte-for-byte on inspection (row counts, market
lists, join rates, all identical). The measurements in `TARGET_CONTRACT_DRAFT.md` are taken from
this confirmed-reproducible run, not carried forward on trust.

## What I measured, and how

* **Read scope check.** `git -C . rev-parse --abbrev-ref HEAD` -> `player-model-program`, confirmed
  before starting.
* **`ROADMAP_EXTRACTION.json`.** Loaded and searched for `F16` and `prop` (case-insensitive) across
  `items`, `already_modelled`. F16's only mapping is the single `already_modelled` entry quoted in
  section 1 of the draft. No `items[]` entry is keyed to F16 -- G04 did not catalogue player props
  as one of its 42 numbered items; it is carried only via the `already_modelled` cross-reference.
* **`DECISION_LEDGER.jsonl`.** Grepped for `prop` (case-sensitive matched nothing; case-insensitive
  found 3 lines). Read each in full. `D014_THIRTEEN_TRACKS_HAVE_NO_TARGET_CONTRACT` names `F16`
  explicitly and defines the estimand standard this draft applies.
* **`PROJECT_UPDATE_2026-08-04.md`.** Grepped case-insensitively for `player prop|props`; the only
  hit is line 284, quoted in full in the draft (section 1, E1). Read the surrounding section 7
  (lines 260-309) for context; nothing else in that section names player props.
* **`turnover_targets_v1/player_turnover_targets_v1.parquet`.** Loaded with pandas; shape
  (28,328, 32); column list enumerated and checked for any of `pts|points|reb|rebound|ast|assist|
  three` -- none present.
* **`data/masters/master_player.parquet`.** Loaded; confirmed `player_id` present (integer key,
  matching D14's stated convention) and computed the null-`pts`/`dnp_reason` figures in draft
  section 3.5.
* **`data_lane/D14_ENTITY_RESOLUTION_AND_COLD_START/IDENTITY_AND_COLD_START_CONTRACT.md`.** Grepped
  for `player_id`; line 18 ("The person key is an integer `player_id`...") is the citation used in
  draft section 3.4.
* **`PLAYER_MODEL_CAPABILITY_MATRIX.md`.** Grepped case-insensitively for `prop` -- zero hits (a
  proven-negative search: the same grep against `PROJECT_UPDATE_2026-08-04.md` returns a hit, so
  the tool and pattern are known to work; the absence in the capability matrix is a measured
  negative, not a failed search).
* **`ROADMAP_EXTRACTION.json` `items[]`, id `C11_REBOUND_CHANNEL`.** Read in full; the
  `rebound_type` unresolved-on-125,309-rows finding is quoted in draft section 1 and section 4
  (B10) because it is the closest documented sibling to a rebounds-market props estimand.
* **`stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/REPORT.md`.** Read sections 0-1.4 (lines 1-70) for the
  `K0_MATCHED` contract text quoted in draft section 2, including the `const`-pinned `target` field
  that is the basis for this draft's central K0 finding.
* **`stage2a/V2_STOP_CONDITION.json`.** Loaded per the brief's instruction to read it before
  writing. Findings S1-S9 are team-level (offensive-possession target) leakage, join-hazard,
  confound and identifiability findings; none names player props or a player-grain target. None is
  restated in the draft because none bears on this track beyond the general point (made in section
  6) that the K0 machinery they exercise was built and hardened on the team target.
* **`orchestration/GRAPH_STATE.json`.** Confirmed `F16_PLAYER_PROPS: RUNNING`,
  `retry_counts.F16_PLAYER_PROPS: 1`, and `P2B_MARKET_ODDS_ELIGIBILITY: RUNNING` (used in draft
  sections 1, 4, 7 to establish the shared open precondition with `F14`).

## What I could not establish

Listed in full in `TARGET_CONTRACT_DRAFT.md` section 8. Summary: whether the out-of-scope odds
archives (`data/odds_capture`, `data/drive_masters`) carry any player-prop-adjacent structure;
whether the 141 unmatched archive player-games are genuine non-matches or spelling variants; whether
the live capture pipeline will ever produce more than one decision-time label per game; and whether
any graded outcome for a props line exists anywhere downstream of this lane. None of these was
assumed in either direction.

## Contradictions found

None. This node found no disagreement between any two documents, or between a document and the
bytes, concerning player props specifically. (The inherited SC1 contradiction -- the market-odds
exclusion ground vs. the archive that predates it -- belongs to `F14`/`P29` and is restated in draft
section 7 only because E1 makes it a precondition for this track, not because this node re-derived
it.)

## Anything that trips a stop condition

Nothing found here changes the primary target, the K0 structure, the inference structure, the
candidate universe, the cutoff-valid feature set, or the leakage status. Two facts are recorded as
informational in draft section 7 (the K0 schema's `const`-pinned target field, and the C11
`rebound_type` dependency) because they are directly relevant to any future contract on this track,
but neither is a proposal to change anything and neither is treated as a stop-condition trigger.

## Outputs

* `experiments/player_program/future_research/F16_PLAYER_PROPS/TARGET_CONTRACT_DRAFT.md` (required)
* `experiments/player_program/future_research/F16_PLAYER_PROPS/REPORT.md` (this file)
* `experiments/player_program/future_research/F16_PLAYER_PROPS/FINDINGS.json`
* `experiments/player_program/future_research/F16_PLAYER_PROPS/measure_props_evidence.py` and
  `MEASUREMENTS.json` (pre-existing on entry; re-run and confirmed reproducible, not modified)

No git command was run. No frozen artifact was edited. Nothing under `stage2b/SEALED_RESULTS/` was
read. Nothing was written outside
`experiments/player_program/future_research/F16_PLAYER_PROPS/`.
