# `contract_baseline_suite_v14` — the prior-obligation count, defined by cutoff

**Status:** registered; corrected; awaiting supervisory review. Not validated, not confirmed,
not replicated.

**Evidence label:** correction and executability only. **No real fitted player output exists**,
and none is authorized before review of this pushed unit. The real 2021 fold traverses the
complete boundary and fits nothing — 2021's training window is empty and a runtime sentinel
asserts it. Nothing computes or inspects a score, accuracy, calibration, threshold, edge, return
or profitability figure. "Coverage" means **obligation completeness** throughout.

**Authorised by:** Codex supervisor reply `20260803T002715462Z`.

**Immutable:** `cbs_generator.py`, `cbs_v8.py`, `cbs_v12.py`, `cbs_v13.py`,
`cbs_obligation_order.py`, `cbs_player_runner_v13.py` and every artifact under
`experiments/prediction_contract_v4/` are byte-untouched. **No module's globals were rebound.**
Registry 94 → 96, append-only. Nothing deleted.

---

## 1. The ruling

v13 corrected the obligation *order* and opened the real player path. It also measured a defect it
was not permitted to repair. The supervisor ruled that measuring was not enough:

> The remaining count defect changes an actual decision for two 2022 obligations. […] Add a new
> prior-count component that defines `n_prior_candidate_games` precisely as the number of
> candidate obligations in the same `(player_id, season)` whose `forecast_cutoff` is strictly
> earlier than the current cutoff. It is not a count of distinct game IDs. Widen the player fork
> by exactly this one history seam.

## 2. `cbs_player_history/14`

    n_prior_candidate_games(row) = the number of candidate OBLIGATIONS in the same
                                   (player_id, season) whose forecast_cutoff is
                                   STRICTLY EARLIER than this row's forecast_cutoff.

Two things it is not. **Not a count of distinct game ids**: two obligations owed for one earlier
contest contribute two, because the quantity the fallback ladder reads is how many forecasts this
player has already owed this season. **Not availability-gated**: it is a scheduling fact, exactly
as the inherited docstring says, and the availability-gated quantities are `cbs_v8`'s and are
untouched.

`searchsorted(side="left")` counts strictly-earlier cutoffs only, which is what makes both members
of an equal-cutoff group receive the same count and neither count the other.

**The seam is confined, and checked.** `player_history_v14` calls
`cbs_v8.player_history_walk_forward` and replaces exactly two of its seven columns —
`n_prior_candidate_games` and the flag derived from it. `assert_only_the_count_moved` re-runs the
inherited function and diffs column by column, and additionally refuses any row whose corrected
count *exceeds* the positional one, which is impossible.

## 3. What the correction actually moves

| | |
|---|---|
| equal-cutoff groups in the contract | **55**, all of size 2 |
| rows overcounted by the positional prefix | **55** — one per group, each by exactly one |
| rows where the corrected count exceeds the positional one | **0** |
| `p_active` fallback-band decisions corrected | **2** — `ob_a8c6201e99f29bba`, `ob_f2e6b1c4373894ac`, both 2022, each `long` → `short` as 3 prior became 2 |

### The 55 are two phenomena, and only one was ever visible

The ruling described the 55 as *"including the 28 collision rows"*. The truth is narrower in one
direction and considerably wider in the other:

| kind | groups | rows overcounted | was it visible? |
|---|---|---|---|
| **dual-team, one game** — one player, one game, one cutoff, two clubs | 14 | 14 | yes: the inherited ORDER refused these outright. Only the 14 *second* members were overcounted, not all 28 collision rows. |
| **two games, one cutoff** — one player, one season, one cutoff, two *different* games | **41** | **41** | **no.** Differing `game_id` distinguishes them in the inherited tie key, so nothing ever refused them, and the positional prefix miscounted them silently in every arm from v5 onward. |

The second kind happens around a trade: the player is a candidate for both his old and his new
club, and both clubs play on the same date, so the date-only cutoff policy gives both obligations
the same cutoff. It spans 2021-2025, 82 rows.

**One of the two corrected decisions comes from each kind.** The previously invisible phenomenon
accounts for half the corrected decisions, which is why it is registered rather than noted in
passing.

## 4. `cbs_player_runner/14` and `cbs_obligation_order/3`

The fork is **generated from `inspect.getsource(cbs_v8.run_player_fold)`**, so the copy is exact
by construction. Exactly **three** lines differ — the two ordering calls, now bound to `/3`, plus
the one history seam. Section 8 of the suite re-derives the diff against the **live** inherited
source and fails on any fourth differing line, and asserts object identity for fifteen imported
names. `plan_all` is still built by `cbs_v7.build_walk_forward_plan`, and `plan_tr` and the
conditional chain are the inherited ones: the seam is the history *frame*, not the plan.

`cbs_obligation_order/3` makes true two claims v13's `/2` made about itself:

* **`/2` validated its input.** It called `assert_total_order(df)` and then returned
  `df.sort_values(...)`, while its docstring and test said it re-asserted totality *after*
  sorting — and the test meant to prove it searched the docstring for the word "after". The
  verdict is the same either way, so the claim was harmless and still false. `/3` sorts first and
  validates the returned frame, and section 9 proves it by **observing the call** — spying on
  `assert_total_order` and comparing the frame it received against the frame returned.
* **`/2`'s `row_set_unchanged` compared row counts.** `bool(len(before) == len(after))` under the
  name of a row-set proof. `/3` compares canonical-key sets and reports the symmetric difference;
  section 9 constructs a same-length frame with a substituted key, shows `/2` calls it unchanged,
  and shows `/3` catches it. The count equality is still reported, under `row_count_unchanged`.

## 5. The team branch: `cbs_v12_team_oof/2`

`/1`'s **output** survived independent review in full. Its **production** did not: it ran at
`0225f6a` with **97 dirty paths** and bound neither the diff nor the producing source bytes, so
the code behind the artifacts is not reconstructible; and its resume path was **fail-open**,
checking rebuilt frame digests and the five inputs and nothing about the outputs.

`/2` corrects all three points:

1. **Refuses a dirty producer tree** before any frame is built, and digests all 19 producing
   source files into a `producer_source_set_digest` recorded in every receipt. Recording a
   problem is not the same as declining to create it.
2. **Resume is fail-closed and complete.** A season is reused only when every artifact exists,
   hashes to its manifest, carries a valid manifest and the right arm/config/snapshot/season, the
   sidecar digest recomputes, and the strict prediction validator *and* the provenance-sidecar
   validator both pass again **on the artifacts as read back**. Twelve failure modes are
   enumerated; `tests/test_run_team_oof_v12_2.py` section 4 damages a real fold in each way and
   asserts the validator names that reason — including a **substituted** prediction file whose
   manifest was rewritten to match, which only the re-run validators catch.
3. **Attempts are immutable.** An existing attempt directory is never written into.

**The scope claim is stated at its actual width.** `/1`'s AST scan covered its own wrapper and was
allowed to read as a proof that the run reads no outcome. It is not, and could not be: the run
*legitimately* consumes historically available prior outcomes, because that is what a walk-forward
feature is. `/2` claims only: no target row's own outcome informed its forecast (enforced by
`require_own_outcome_unavailable` and the `availability < cutoff` admission rule); no forecast was
scored against its outcome; no evaluation metric was calculated.

`/1` is **retained intact** and labelled provisional — see
`experiments/cbs_v12_team_oof/PROVISIONAL_SUPERSEDED.md`. Nothing was deleted or overwritten.

## 6. Two commits, in the order the ruling requires

**Code commit 1** carries everything above and nothing generated. **Artifact commit 2** carries
the `/2` generation, produced *from a clean checkout of commit 1* — which is precisely the
guarantee `/1` could not offer. The generation receipt names commit 1; the post-push gate
certifies commit 2.

The attestation glob for `/2`'s outputs is added in commit 2, with the artifacts: a glob matching
no file is reported `GONE` by the scan, so declaring it in commit 1 would turn commit 1's own gate
red on an artifact nobody had produced yet.

## 7. Gate

Three new standing checks: `test_cbs_v14` (126), `test_cbs_real_integration_v14` (70),
`test_run_team_oof_v12_2` (49). 31 → 34 checks.

## 8. What remains unperformed and unauthorised

Real fitted **player** output beyond the 2021 zero-fit smoke, chronological player OOF, scoring,
accuracy or coverage-quality inspection, and profitability evaluation.
