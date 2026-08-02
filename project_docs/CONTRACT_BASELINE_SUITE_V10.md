# `contract_baseline_suite_v10` + `prediction_contract_v3` — registered specification

**Status: DEFINITION + A CAUSAL ROW UNIVERSE. No real MODEL result.** No fit, prediction,
score, accuracy/coverage result, profitability result, or model output exists or was inspected.
Real artifacts *are* read and written — `prediction_contract_v3` regenerates the contract tables
and `cbs_real_frames/2` builds and hashes real fold frames — and **neither is ever handed to a
model.** That phrasing replaces v9's `computed_nothing_on_real_data`, which was false.

Registry lines **88** (v9 erratum) and **89** (v10); v1–v9 byte-identical.
Authorised by the Codex reply `20260802T015625584Z`. Built as one bounded three-branch diamond
under a single coordinator, fanned in once.

---

## 1. `prediction_contract_v3` — the row universe is now availability-causal

v2's `build_candidates` took the **positional** five prior same-season team games without asking
whether their appearance data was knowable at the cutoff. The registered v3 rule:

> A candidate for (team, game) is a player who appeared in one of the **latest five prior
> same-season team games whose appearance source bound is strictly earlier than the row's
> forecast cutoff**. Latest five **admitted**, not latest five scheduled. The bound is
> `floor_to_day(game_date) + 36h`. Admission is **strict**: a bound *equal* to the cutoff is not
> admitted. The window never crosses a season boundary.

**Measured diff — the supervisor's numbers reproduced exactly:** 6 v2-only, 18 causal-only, 21
team-games, **35,615 → 35,627**. Receipt:
`experiments/prediction_contract_v3/row_diff_vs_v2.json`.

### The 18 are compound, and that is disclosed rather than buried

Diffing on `row_uid` alone gives **6 out / 4 in**. The other **14** are obligations v2 had
**deleted without a receipt**: v2 ends `build_candidates` with `drop_duplicates("row_uid")`, and
`row_uid = pg_uid(player_id, game_id)` **carries no team** — so a player traded mid-season who is
a recency-roster candidate for *both* clubs in their head-to-head game collided, and one
obligation vanished. v3 emits one row per `(team_id, game_id, player_id)`, keeps `row_uid`
verbatim, and adds `obligation_uid` and `row_uid_shared_with_other_team`. **4 genuine
availability-causal additions + 14 recovered obligations = 18.** The receipt reports both
granularities side by side.

### A guard that prevented a fabricated diff

`data/odds_capture/` is gitignored and absent from every worktree. Run naively, v2's tip
resolver finds **2** exact tips instead of 407 and flips 1,086 games to the date-only policy —
which would have produced a **fabricated** diff of 30/4 attributed to the lookback rule. v3
resolves tip sources explicitly, records the resolved path and sha256, and **refuses to emit**
unless every game's `forecast_cutoff` and `cutoff_policy` equal v2's registered `game.parquet`
exactly (**1,495/1,495**). That is what makes the diff attributable to the lookback rule alone.

Also: 55 team-games have an unadmitted prior inside v2's positional five — **all 55 date-only
back-to-backs**; under exact-tip the same game *is* admitted, a fact about knowability, tested
both ways. 76 zero-candidate season openers stay visible. Labels now join on
`(game_id, team_id, player_id)`; 11 rows change `appeared` (a traded player who played for the
other club), recorded as `appeared_for_other_team`.

## 2. Frame identity — `cbs_frame_identity/3`

`/2` collided three ways, and **(a) was worse than aliasing**: it stringified the column list
then reindexed on the stringified names, so an **integer-labelled column was dropped** and
replaced by all-NaN — its values never entered the hash at all. Dict keys `1`/`"1"` collided, as
did list/tuple/ndarray cells.

`/3` **rejects before hashing**: string-only column labels, scalar-only cells. A frame outside
the domain gets **no identity**, not a weak one. An opt-in strict-container mode tags container
kinds and mapping keys, and the mode is inside the hashed payload so the digests cannot be
confused.

## 3. Exactly five artifacts, of the **v3** contract

`build_snapshot_manifest(artifacts=(PLAYER_GAME,))` used to build a one-artifact manifest that
`cbs_v9.snapshot_identity` accepted. `require_exact_artifact_set` now enforces key equality in
**both** directions, at construction **and again at the runner** — a manifest can reach the
runner without passing through the builder. The test-only escape needs two independent tokens
(`_test_artifacts=` *and* `synthetic=True`), each inert alone; the real entry point has no
artifact parameter at all; and the escape stamps its output so it cannot be laundered
downstream.

**The required set moved to the v3 contract** at fan-in. Enforcing "exactly five" against the
superseded universe would have passed while binding the wrong contract. `MUST_BE_ATTESTED`
tracks it — a mismatch the fan-in suite caught.

## 4. The freshest source actually consumed

Player features read **both** player-obligation history and team-game history, but
`src_asof_gamelog` came from the player's own obligations and `src_asof_roster` copied it.

| defect | before | after |
|---|---|---|
| team source newer than reported | **185** | **0** |
| newer than the reported maximum | **23** | **0** |
| false `no_prior_game_admitted` | **1,060** | **0** |

The 23 are exactly the `exact_tip_T-90m` rows; the composite moved by up to **24 hours**. Bounds
are now per-source over the records actually read, with `src_asof_roster` over the candidacy
window, and `feature_asof` is their maximum.

**An honest limit:** because availability is monotone in `game_date`, the roster and team bounds
**coincide numerically** whenever candidacy read anything (35,615/35,615). They remain distinct
sources — different record sets on 25,498 rows, independent labels, `n_roster_games_consumed`
per row. What is *not* true, and what v9 asserted, is roster == the **player** bound; those now
differ on 881 rows.

## 5. Bound harmonization

`player_game.parquet.manifest.json`: `2026-07-31T00:00:00Z` → `2026-08-01T12:00:00Z`. A bare
`game_date` parses to 00:00 UTC — *before* the games played that day — so the artifact would
have passed an as-of check against a noon forecast while already containing that evening's
final. `content_sha256` unchanged. A new `bound_convention_status` recomputes each bound from
the bytes: declared **earlier** than `bound_from_dates` is a hard blocker; declared **later** is
reported but not blocking, since over-caution is never wrong in the unsafe direction.

## 6. A semantic DNP taxonomy, frozen while no result exists

The prefix rule knowingly mapped 82 rows against their own text. Frozen now as an explicit
22-string table: coach's-decision → CD, NWT prefix → NWT,
injury/illness/concussion/health-and-safety/reconditioning → INJ, **anything unmatched →
UNKNOWN**.

**107 rows change class** (INJ→CD 57, CD→INJ 42, INJ→UNKNOWN 7, CD→UNKNOWN 1). Downstream:
`prev_dnp_cd` moves on 368 rows, `prev_dnp_inj` on 424, `returning_flag` on 146. **No parity
with the prefix rule is claimed.**

Judgement calls: `DND - Personal` → UNKNOWN (neither health nor rotation; INJ manufactures a
health signal); `NWT - Personal` → NWT (the prefix *is* the observation); suspensions → NWT;
rest → CD (load management on a healthy player); `DND_INELIGIBLE_TO_PLAY` → UNKNOWN. UNKNOWN is
not invisible: it stops the carry-forward but sets none of the three flags, so a diagnostic
`prev_dnp_unknown` column carries it. `P_ACTIVE_FEATURES` stays frozen at twelve.

## 7. Evidence labels and a persisted receipt

v9's erratum (registry line 88, **appended, not mutated**, with a distinct `experiment_id` so it
cannot shadow the record it corrects) fixes: "84 assertions" stated twice against an actual 85;
`computed_nothing_on_real_data` and `synthetic_implementation_only` both true and both false;
and **the Layer-A total recorded as 988 when its own addends sum to 989** — an arithmetic slip
that had propagated into the v9 handoff and the supervisory reply quoting it. Found by the
receipt tool on its first run.

`gate_receipt.py` persists `verify_all --json` stamped with commit and tree state, parsing each
suite's own final line rather than trusting a typed total, and distinguishing a
**producer-tree** receipt from a **post-push clean-checkout** receipt — only the latter
certifies a commit.

## 8. Framing, as directed

The availability-admitted history rule is **ported transforms over a new causal
history-admission rule**, *not* output parity with `minutes_twostage_availability_v1`. Any later
comparison against the positional incumbent combines a history-admission change with the
estimator comparison, and **must not attribute the whole difference to model class.**

## 9. What is still blocked

No real fitting, OOF prediction, scoring, model coverage/accuracy inspection, profitability
evaluation, or hierarchical arm. Per the supervisor, the next action after review is
**immediately the incumbent chronological OOF run** — no further speculative infrastructure.
