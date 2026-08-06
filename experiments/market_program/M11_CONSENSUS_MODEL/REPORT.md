# M11_CONSENSUS_MODEL — Report

## Epistemic status (verbatim, per contract §0.1 / node mandate)

> MARKET-REACTION SYSTEM COMPONENT under the four-system separation. Estimates a consensus fair
> line from multi-book quotes. It models the market, not the game; its output is never a
> fundamental prediction and is labelled per the M00 ladder.

This bounds every citation of this node's output. `consensus.py` writes this line verbatim into
every object it emits (`epistemic_status` field), and `evidence_ladder_labels_held` is always `[]`
- this module is machinery, never a preregistered family-endpoint result, and never claims a §3
ladder label.

Ladder-off honesty rule observed: the high-frequency tape does not exist yet. Everything below is
tested machinery over synthetic fixtures plus the existing coarse (T2) tape samples, with the
book-reliability weighting hook built and enforced but never invoked on real data. Nothing here is
a finding about market behavior; the one genuine empirical result reported below (§4) is a null
result about the demo's own coverage, not a market claim.

---

## 1. What was verified before any work began

* `MARKET_PROGRAM_CONTRACT.md` sha256 measured as
  `1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de` - matches the value in the
  node prompt exactly. Command: `Get-FileHash ... -Algorithm SHA256`.
* `TAXONOMY.json` sha256 measured as
  `c83e25e783a4ee8642a26dd416362e46c2c34196ff8f8354977c28b72940a12c` - matches exactly.
* Both hash constants are also asserted at runtime by `TESTS.py::T13` against `consensus.py`'s
  `CONTRACT_SHA256` / `TAXONOMY_SHA256` module constants, so drift in either frozen document would
  fail the suite, not just this one-time check.
* §3 (evidence ladder), §4 (point-in-time integrity), §5 (bounded final-state archive uses, C.1/C.2
  verbatim ruling), §6 (amendment-4 timestamp-uncertainty discipline), §9 (USER_REQUIRED boundary),
  and §11 (enforcement) were read in full before touching code.

## 2. What exists in this node's write scope

`experiments/market_program/M11_CONSENSUS_MODEL/` contained, at the start of this session:

* `consensus.py` - the machinery (no-vig conversion, consensus fair value, book-vs-consensus
  residual, book-reliability weight-fitting hook).
* `fixtures.py` - synthetic (year-2030, fictional book names) fixtures, M00-U5 use class.
* `coarse_tape_demo.py` - a bounded, read-only demo against the live main worktree's
  `data/drive_masters/master_odds.csv` and `data/masters/master_team.csv`, M00-U2 use class.
* `TESTS.py` - 15-case validation suite.

`REPORT.md` (this file) was the only required output missing. No other file was created; no file
outside this node's write scope (`experiments/market_program/M11_CONSENSUS_MODEL/`) was touched.
The live main worktree (`C:/Users/jgallagher/wnba-betting-model/data/...`) was read only, never
written.

## 3. What was measured

**Command:** `python experiments/market_program/M11_CONSENSUS_MODEL/TESTS.py`, run from this
node's directory.

**Result:** all 15 non-skipped cases pass; the live-worktree-dependent `T15` ran (not skipped,
since `data/drive_masters` and `data/masters` are present in this environment):

```
PASS  T01_no_vig_arithmetic_all_methods
PASS  T02_preregistration_frozen_and_hashed
PASS  T03_symmetric_consensus_exact
PASS  T04_disagreement_and_residuals
PASS  T05_weighted_consensus_and_missing_weight_refused
PASS  T06_t2_only_tier_insufficient_vendor_asserted
PASS  T07_mixed_tier_weakest_tier_inheritance
PASS  T08_mismatched_outcome_refused
PASS  T09_determinism_and_order_invariance
PASS  T10_book_vs_consensus_residual_definition
PASS  T11_weight_fit_train_eval_separation_enforced
PASS  T12_weight_fit_insufficient_data_fallback
PASS  T13_cited_contract_hashes_match
PASS  T14_fixture_m00u5_caveat_hash_matches
PASS  T15_coarse_tape_demo_m00u2_labelled_correctly
{"suite": "M11_CONSENSUS_MODEL/TESTS.py", "n_pass": 15, "n_fail": 0, "n_skip": 0}
```

**Caveat-hash cross-check (independent of the suite):** `TAXONOMY.json`'s `permitted_uses` array
carries `caveat_sha256` values at lines 190
(`39b8dbde2fc3407e5563752775c18e61f161946b216cbd0194c8d0c110997e7b`, M00-U2) and 208
(`f2d6cfbc2f135d7e053da799217b44a8d686078ecf598a7c22286a26bdd53f7a`, M00-U5). I grepped
`TAXONOMY.json` directly and diffed both hashes by hand against the constants
`coarse_tape_demo.M00_U2_CAVEAT_SHA256` and `fixtures.M00_U5_CAVEAT_SHA256`; both match exactly,
and both are independently re-derived at runtime (`verify_caveat_hash()` /
`T14_fixture_m00u5_caveat_hash_matches`) rather than only asserted as literals.

**Coarse-tape demo, run standalone:** `python coarse_tape_demo.py`, 60-game cap, against the live
`data/drive_masters/master_odds.csv` and `data/masters/master_team.csv`. Output written to
`demo_output.json` (172 KB, 60 `per_game` entries) and printed summary:

```json
{
  "m00_use_class": "M00-U2",
  "m00_caveat_hash_match": true,
  "vig_method": "multiplicative_proportional",
  "sampling": {
    "max_games_cap": 60,
    "n_games_sampled_from_odds_file": 60,
    "n_games_with_resolvable_book_pairs_and_result": 60,
    "n_games_push_excluded_from_calibration": 1,
    "n_games_used_in_calibration": 0
  },
  "calibration_buckets_of_consensus_prob_home_covers_spread": {},
  "brier_score": null
}
```

## 4. What could not be established, and why (measured, not asserted)

The demo's stated purpose is M00-U2, "no-vig calibration against realized outcomes, unknown-time,"
applied to real (T2) spread-market rows. Inspecting `per_game[0]` directly:

```
game_id=1022200034  n_books=5  consensus_fair_prob_home_covers=None  realized_cover_home=1
consensus_object: n_trusted=0  n_excluded=5  tier=T2  channel=VENDOR_ASSERTED
                   exclusion_reasons={'TIER_INSUFFICIENT': 5}
```

This is not an isolated case: across all 60 sampled games, `n_games_used_in_calibration` is `0` and
`calibration_buckets_of_consensus_prob_home_covers_spread` is `{}` - **no no-vig probability was
ever computed from real archive data in this demo run.**

**Root cause, traced in code:** `consensus_fair_value()`'s tier gate (`consensus.py`, the
`trusted_quotes` loop) excludes any quote with `tier >= "T2"` unconditionally - there is no
parameter to admit T2 quotes into the "trusted" set that `no_vig()` is actually run against. Every
quote `coarse_tape_demo.py` builds from `master_odds.csv` is tagged `tier="T2"` (correctly - it is
T2 data), so `per_book` is empty for every game, `consensus_fair_prob` is `None` for every game,
and the demo's calibration step has nothing to bucket.

**Why this is a genuine contradiction, not a stop-condition trip:** M00-U2 (contract §5, C.1)
explicitly *permits* "no-vig calibration against realized outcomes, unknown-time" as a bounded use
of exactly this T2 archive - it is not a timing claim, and §5's enumeration governs archive *use*,
not tier-admission mechanics inside this module. But `consensus_fair_value()`'s tier gate was built
to the general (and, for any timing-adjacent use, correct) discipline of §4.3 - "a derived quantity
inherits the weakest tier of any input," T2 "never supports a timing claim" - and applied that
discipline to a use class (M00-U2) that the contract itself carves out as a non-timing exception.
The result is internally consistent and safe (nothing timing-flavored leaks out of a T2 quote;
every consensus object built from T2 rows is honestly labelled `channel: VENDOR_ASSERTED`,
`tier: T2`, `tier_admissible: false`, exactly as `T06`/`T07`/`T15` require), but it means **the
M00-U2 "calibration" half of the demo's stated purpose does not actually run.** What the demo does
successfully and verifiably demonstrate against real bytes is: real CSV parsing and book-pair
construction, the tier-exclusion and `VENDOR_ASSERTED`-labelling machinery, the caveat-hash
self-check, and the game-outcome join (margins, ATS cover computation, push exclusion) - all
correctly, per `T15`'s assertions, which check exactly these fields and deliberately do **not**
assert a non-null `consensus_fair_prob_home_covers` or a non-empty calibration bucket anywhere.

I did not alter `consensus_fair_value()`'s tier gate to make the calibration numbers non-null.
Loosening a tier-admission rule that is elsewhere load-bearing for keeping T2 data out of anything
timing-adjacent is a design decision with contract implications (exactly the kind of thing §6.3's
"a vendor without a sourced latency bound is `UNBOUNDED` and inherits inadmissibility" discipline
guards), and the acceptance criteria for this node do not require the demo to produce a non-null
calibration figure - they require preregistration-before-evaluation, train/eval separation on any
fitted weighting, per-quote capture timestamps, and honest ladder labelling, all of which hold
regardless of this gap. This is reported as a null result and an architecture note for whoever next
touches the M00-U2 calibration use, not silently patched and not presented as a working demo of
calibration it does not perform.

## 5. Acceptance criteria - evaluated against measured behavior

| Criterion | Status | Evidence |
|---|---|---|
| Vig-removal method preregistered before evaluation, not tuned on results | **Met** | `PREREGISTRATION` dict in `consensus.py` is frozen module-level state, hashed (`PREREGISTRATION_HASH`), selected (multiplicative-proportional) *because* it has no free parameter to tune; `T02` asserts the hash and the registry contents; `coarse_tape_demo.py` and `TESTS.py` never override `method=`. |
| Any book weighting fitted only on data strictly before the evaluation window | **Met, enforced in code** | `fit_book_weights()` raises `WeightFittingViolation` if `fit_window_end_ts > evaluation_window_start_ts`, and again if any individual observation's `capture_ts >= fit_window_end_ts`. `T11` exercises both violation paths and the success path. The hook is never invoked by the demo (no tape exists to fit on honestly), consistent with the ladder-off rule. |
| Consensus output carries the capture timestamps of every contributing quote | **Met** | `capture_timestamps_all_contributing_quotes` on every consensus object lists **all** supplied quotes' timestamps, including tier-excluded ones (verified by `T06`/`T07`, which check the count includes excluded rows, not just trusted ones). |
| Output labelled with its M00 evidence-ladder status, never presented as a fundamental prediction | **Met** | Every object carries `evidence_ladder_labels_held: []`, `not_a_fundamental_prediction: true`, and the verbatim `epistemic_status` line; `assert_am4()` in `TESTS.py` checks all three on every consensus object under test. |

## 6. Amendment-4 field set

Every consensus object carries the full §6.1 field set (`t_lower`, `t_upper`,
`poll_interval_event`, `poll_interval_quote`, `vendor_latency_bound`, `clock_skew_bound`,
`censor_type`, `tier`, `n_trusted`/`n_excluded` with `exclusion_reasons`), even though a consensus
snapshot is explicitly *not* a reaction-time claim (`is_reaction_time_claim: false`). Where a field
does not apply to a non-reaction-time object, it is set to an explicit sentinel
(`"NOT_A_REACTION_TIME_CLAIM"`, `"N/A_NO_EVENT_STREAM"`, `"N/A"`) rather than omitted or left null,
so the schema is uniform and a missing-field check elsewhere in the program cannot silently pass on
this module's output. This is a documented interpretive choice (see `consensus.py`'s module
docstring), not a claim that this module produces reaction-time results.

## 7. Stop conditions - none tripped

No finding here requires spending money, placing a wager, entering credentials, accepting
scraping/licensing risk, or reading sealed possession results. No timing claim is made at all by
this module (`is_reaction_time_claim` is always `False`), so the UNSUPPORTABLE timing-claim
condition does not apply. The one archive use exercised (`M00-U2`, in `coarse_tape_demo.py`) is
within the §5 enumeration, its caveat hash is verified against `TAXONOMY.json` at runtime, and it
is not stretched to cover a use class it does not hold (§4 is unaffected by §5, per §4.3's own
scoping - the demo never treats `odds_snapshot_timestamp` as witnessed, and every consensus object
built from it is explicitly `channel: VENDOR_ASSERTED`).

## 8. Contradictions found

One, detailed in full in §4: the demo's stated M00-U2 purpose (no-vig calibration against realized
outcomes) does not actually execute, because `consensus_fair_value()`'s tier gate - built to the
general §4.3 discipline - has no admission path for the T2 tier that M00-U2 specifically licenses
for this use. This is a gap in what the demo *demonstrates*, not a violation of anything frozen; it
is reported rather than silently patched, per the node's "measure, do not assert" and "preserve
nulls" standing rules.

No other contradiction was found between `MARKET_PROGRAM_CONTRACT.md`, `TAXONOMY.json`, and the
bytes in this node's scope.
