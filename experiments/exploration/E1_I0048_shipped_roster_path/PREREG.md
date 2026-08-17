# PREREG — E1_I0048_shipped_roster_path

**Screen.** Characterise, and quantify the shipped damage of, the roster construction at
`daily_forecast.py:647-665` — the only defect found in the last twenty-four hours of this programme
that sits on the critical scheduled path.

**Registered before any statistic was computed.** Written after reading code and file *schemas*
only. No count, rate, or comparison in this document was known when it was written.

**Nothing will be enacted. No production file will be modified.** Not a line, not a comment, not a
formatting change. This screen writes only inside
`experiments/exploration/E1_I0048_shipped_roster_path/`.

---

## 0. The partition boundary, declared first because it governs everything below

`forecasts/forecast_log.jsonl` is the shipped artifact this screen is asked to quantify. **Every
record in it carries a `forecast_cutoff` in 2026.** 2025/26 is the SEALED confirmation holdout.

The brief distinguishes two activities, and this screen does exactly one of them:

* **PERMITTED, and what this screen does:** reading the shipped log and the box-score master to
  characterise how a production code path constructs a roster — an engineering-defect
  characterisation. Counts of rows, names, and keys are descriptions of the *code's output*, not
  measurements of forecast quality.
* **PROHIBITED, and what this screen will not do:** any skill statistic on sealed-season output.
  No Brier, log-loss, AUC, MAE, calibration, hit rate, CLV, or realised-vs-predicted comparison of
  any kind will be computed on any 2025 or 2026 row. No game outcome column
  (`pts`, final scores, `appeared` as a realised label used to score a forecast) will be joined to
  any shipped forecast.

**Registered assertion, to be enforced in code and printed:** the analysis frame for shipped
reconstruction is restricted to columns on an explicit allowlist that contains no outcome field,
and the script asserts that no skill-statistic function is called. Any number this screen reports
from a 2026 row is a **count of rows or names emitted by the code**, and is labelled
`SEALED-PARTITION / DESCRIPTIVE ONLY`.

**Consequence, stated in advance so it cannot be presented later as a discovery:** because the
shipped log exists only inside the sealed window, this screen **cannot** report how the defect
affected forecast accuracy, and will not estimate it. It can report how many rows the defect
produced. That is the question asked.

---

## 1. Anchors — reproduced EXACTLY before any new statistic

No new number is generated until every anchor below is confirmed. Each is **recomputed** from the
prior screen's stored frame, never transcribed from its prose.

| id | anchor | published value | source |
|---|---|---|---|
| A1 | RS1P champion rows | 20,084 | E1_I0045 `_PF.parquet`, UNIVERSE_CONSTRUCTION.md §4 |
| A2 | tier-B rows admitted by S2 | 3,266 | `tier_b_by_admitting_source.csv` |
| A3 | tier-B rows admitted by S_TX only | 506 | same |
| A4 | S2 rows by seasons-since-club | 1,765 / 991 / 432 / 78 | `S2_rows_by_seasons_since_club.csv` |
| A5 | S2 departed / not departed | 1,489 / 1,777 | UNIVERSE_CONSTRUCTION.md §4 |
| A6 | RS1P rows in the decision stratum | 4,964 | `scripts/s07_findings.py:57` |
| A7 | `p_active` references in each named production file | **0** | E1_I0035 via E1_I0045 REACH.md §1 |

A7 is the direct analogue of this screen's task 3 and is recounted, not assumed.

**Stop rule.** If any anchor fails to reproduce, the discrepancy is reported and this screen's
own numbers are held as provisional until it is explained. Anchors are reported at their exact
computed value with the absolute difference shown.

---

## 2. Fidelity gate — my reconstruction must BE the shipped code path

The shipped log records aggregates (`n_roster`, `n_out`, `sum_min_ewma_available`,
`vacated_min_ewma`, `n_cold_start`) and the names of OUT players only. **The roster name list
itself is not in the log.** To count phantom pairings I must re-execute the roster rule.

I therefore re-implement `daily_forecast.py:647-665` and `:673-693` line for line against
`data/masters/master_player.parquet`, at each shipped record's own `forecast_cutoff` and slate
date, and **require it to reproduce the shipped aggregates exactly**:

* `n_roster` — exact integer match required.
* `n_out` and the `out_home` / `out_away` name lists — exact set match required.
* `sum_min_ewma_available`, `vacated_min_ewma` — match to 1e-9.

**Registered in advance:** a team-slot whose aggregates do not reproduce is marked
`NOT_REPRODUCED` and **may back no damage number**. Damage is quantified only over reproduced
slots, and the reproduced fraction is reported as the headline denominator. This is the gate that
converts "I reconstructed something roster-shaped" into "this is the shipped roster".

Known reason reproduction may fail: the master is rebuilt continuously, so a backfill or repair of
a game earlier than the slate would change the reconstruction. That is exactly what the gate
detects.

**Manifest status, declared now.**
* `.claude/worktrees/player-model-program/data/masters/master_player.parquet` — manifest present,
  `asof_granularity: "row"`, `fit_through_date 2026-08-01T12:00Z`. **Usable** (`row` granularity).
* `C:\Users\jgallagher\wnba-betting-model\data\masters\master_player.parquet` (the live main
  worktree — the file the shipped job actually reads) — **NO MANIFEST FOUND**. Per the standing
  rule, MISSING = UNVERIFIABLE and **may back no number**.

Therefore: numbers reconstructed for slates covered by the manifest-verified copy are **VERIFIED**;
numbers that can only come from the unmanifested live copy are reported separately and labelled
**UNVERIFIABLE**. The two files' agreement on their overlapping rows is tested and reported; if
they agree byte-for-value on the overlap, that is stated as agreement, not as a manifest.

---

## 3. Definitions, fixed now

Ported unchanged from E1_I0045 `scripts/s01_build_and_anchor.py` so the two screens are commensurable:

* **`departed`** — the player has appeared for a *different* club since her last appearance for
  this club, strictly before the cutoff. `last_any_team != team_id`. Requires no post-cutoff data.
* **`n_prior_app_season`** — appearances (`minutes > 0`) for anyone, this season, strictly before
  the slate date.
* **`trail5_min`** — mean minutes over her last ≤5 appearances, strictly before the slate date.
* **DECISION STRATUM** — `n_prior_app_season >= 8` AND `trail5_min >= 24`. Reported for every
  damage estimate, per the brief, and **led with, not buried**.
* **PHANTOM PAIRING** — a roster member emitted for club X who is `departed` as of the cutoff.
  This is the strictly-pre-cutoff, no-outcome-data definition. It is a statement about the
  evidence available to the job at run time, not about what later happened.

---

## 4. Hypotheses, registered with their falsifiers

| # | hypothesis | falsifier |
|---|---|---|
| H1 | The shipped roster admits at least one departed player-club pairing | zero departed roster members across all reproduced slots |
| H2 | `player_name` collides with itself — ≥1 name maps to ≥2 `player_id` within the frame the code reads | every `player_name` maps to exactly one `player_id` |
| H3 | A stable `player_id` is present in the very frame read at line 647 | `player_id` absent from `master_player.parquet` |
| H4 | Re-keying the roster on `player_id` changes ≥1 emitted row | the two keys produce identical roster sets on every reproduced slot |
| H5 | The emitted roster rows reach a product surface (props edge / odds comparison / leaderboard) | zero readers of `player_layer_informational`, `out_home`, `out_away`, `n_roster` outside the writer |

**H5 is the one that decides whether this defect matters.** The brief is explicit that
"it is cosmetic and reaches nothing" is a genuinely valuable outcome. It is registered here as a
fully acceptable result and will not be inflated if found.

---

## 5. Consumer trace — method fixed in advance

E1_I0035 verified zero `p_active` references. The equivalent question for the **roster rows
themselves** has not been asked. Method:

1. Enumerate every reader of `forecasts/forecast_log.jsonl` repository-wide (both worktrees).
2. Within those readers, count references to the five player-layer field names by **explicit
   allowlist of literal field names** — `player_layer_informational`, `out_home`, `out_away`,
   `n_roster`, `n_out`, `sum_min_ewma_available`, `vacated_min_ewma`, `n_cold_start`.
3. Separately trace `props_edge.py`, `conditional_edge.py`, `calibrated_prob_edge.py`,
   `wnba-prediction-engine/`, `wnba_odds_system/`, `wnba-odds-aggregator/`, `leaderboards/`,
   `daily_certify.py`, `daily_refresh.py` for any read of the forecast log or of the player layer.
4. Enumerate the scheduled-task inventory and check which of these files it runs.

**Anti-substring rule (binding).** This programme has lost six findings to name matching, most
recently inside an audit sent to find methodological errors. This screen audits a name-keyed join
and will not commit one:

* every column is resolved by **explicit allowlist**, printed, and asserted present;
* every player identity comparison is on `player_id`, never on a name substring;
* name-collision analysis groups by the **exact** `player_name` value, with no normalisation,
  casefold, `str.contains`, or fuzzy match anywhere;
* row counts are asserted at every merge (`validate=` on every join);
* the resolved column list and every assertion result are printed to the run log.

---

## 6. Fix cost — to be reported, NOT paid

Blast radius only: files, tests, downstream artifacts, and scheduled tasks a hypothetical repair
would touch, counted the same way E1_I0045 counted the contract-side radius (~32
`player_program` files, the cbs_v12–v15 stack, the contract tests). **No fix will be written.**
A repair to a production file requires the user's explicit authorisation and several already await
it.

---

## 7. Deliverables

`PREREG.md` + `PREREG.sha256` · `PATH_ANATOMY.md` · `SHIPPED_DAMAGE.csv` · `CONSUMERS.md` ·
`NAME_KEY.md` · `FIX_COST.md` · `FINDINGS.json` · `NOTES.md` · `DEFECTS.md`.

**Standard adopted.** The result that most weakens this screen's own conclusion is reported in the
same document as the conclusion. No champion is fitted. Nothing is enacted.
