# PREREG — E1_I0045_roster_currency

Seed **20260811**. Partition **2021–2024**. 2025 and 2026 are sealed and are never enumerated by
any loader; `rc_base.assert_partition` raises on their presence.

**No change is enacted.** Nothing in this screen writes to any arm, contract, registry or
production path. Every model change requires the user's authorisation, and three items already
await it.

---

## 0. PROVENANCE OF THIS PREREGISTRATION — read this before trusting anything below

This programme's standard is that a preregistration is worth exactly what its timestamp is worth.
Mine is partial and I am stating precisely how.

**Fixed before any computation, by the task brief:** the benchmark (Xa, not doing nothing); the
requirement to report both levels always; the requirement to report the decision-stratum
intersection first; frozen *and* unfrozen intercept; injection-verified power floors preferred over
analytic ones with the kind labelled; the coverage cost reported as named cases; the 2023–2024
clean window; D101 comparability; no name-based selection; "no currency rule beats Xa" as a fully
acceptable outcome. **None of the decision rules below were chosen by me after seeing a result.**

**Computed before this file was written, and legitimately so:** the anchor reproductions (§1) —
reproductions of published values, carrying no hypothesis, no null and no verdict — and the
universe reconstruction and population characterisation (§2, `s02_universe.py`), which is
descriptive and produces no test. E1_I0035 did the same in the same order.

**Chosen after seeing §2, and therefore design-informed, not blind:** the specific rule family
R1–R4. They are the operationalisations of the three candidates the brief named (last-appearance
recency; appearance elsewhere since; season boundaries) against the population that §2 measured.
This is the same status as E1_I0035's four Xa strata, which were also chosen after its mechanism
analysis.

**POST HOC, and the one that changes the conclusion: `Xa+` (`s05_stratify_not_remove.py`).** It was
designed *after* seeing that Z_R3 beat Xa, specifically to try to explain that result away — it
uses the identical currency signal as a recalibration stratum instead of as a deletion, so it
removes no row and costs no coverage. It is a sceptical arm aimed at my own positive finding, but
it is post hoc and **it is labelled as such everywhere it appears.** Anyone re-running this should
treat the Xa+ vs Z_R3 contrast as the hypothesis a fresh screen should test, not as a settled one.

---

## 1. Anchors, which run before any new statistic

`s01_build_and_anchor.py` halts unless all ten reproduce. Independent path: nothing is imported
from E1_I0035; `rc_base.py` is a separate implementation, and the identity map is rebuilt from
`cbs_obligation_key/1` over the cross product and cross-checked to exact agreement against the
manifest-verified contract v4.

| anchor | published | tolerance |
|---|---:|---:|
| D076 appeared player-games, tier-A, 2022–24 | 13,879 | exact |
| universe rows per team-game | 14.4282 | 5e-4 |
| realised roster per team-game | 9.4016 | 5e-4 |
| Σ`p_active` per team-game | 10.3381 | 5e-4 |
| B1 level bias | +8.1389 | 5e-3 |
| **B1 bottom-up team MAE** | **18.263037** | **1e-5** |
| **top-down team MAE** | **8.685506** | **1e-5** |
| player Brier / tier-A Brier / AUC / log-loss | 0.1302 / 0.0932 / 0.9026 / 0.4056 | 5e-4 |
| **exposure misallocation, X0** (`s04`) | **8.912455** | 5e-4 |
| **Xa's own headlines** (`s03`, before any currency arm is scored) | MAE 10.957, Brier 0.0947 / 0.0933, AUC 0.9285, Σw 9.561 | 5e-3 / 5e-4 |

---

## 2. Row sets and denominators (D101)

Identical to E1_I0035 so that every number here is comparable with every number there.

| id | definition | n |
|---|---|---:|
| **RS1** | team-games: season ∈ {2022,2023,2024}, `season_type == "Regular Season"`, team-arm forecast present, ≥1 champion player row | **1,392** |
| **RS1-C** | RS1 ∩ {2023, 2024} — **the clean window** | **960** |
| **RS1P** | champion player rows on RS1 team-games | **20,084** |
| **RS1P-A** | RS1P ∩ contract-v4 universe (tier A) | **16,312** |
| **RS1P-B** | RS1P \ contract-v4 universe (tier B) | **3,772** |
| **DEC** | RS1P ∩ (≥8 prior same-season appearances AND trailing-5 mean minutes ≥24) | **4,964** |

Team response `master_team.pts`, SST 168 710.4073 on RS1, no weighting, no base. Player responses
`appeared` and `pts`, declared per table. **No team-level quantity is compared with a player-level
one.**

`tier_A` is membership in the manifest-verified `prediction_contract_v4` row-uid set and nothing
else. `prediction_contract_v5` carries the arm's real `universe_tier` but **has no sibling manifest
→ UNVERIFIABLE → may not back a number**; it appears only as labelled colour.

**Why the clean window.** 2021's `p_active` is 4,997 of 4,997 rows at fallback level 4, a single
declared constant with no usable residual — verified directly from the arm's parquet, not taken on
trust. The 2022 fold therefore trains on a constant, and E1_I0035's own `Xa_walkforward_fits.csv`
shows both *fitted* strata empty in 2022. **2023–2024 is the only window in which a walk-forward
recalibration sees a fitted training pool.** Every headline is stated on it; the full 2022–2024
window is reported beside it for comparability with E1_I0035 and never instead of it.

---

## 3. Every input to every rule is strictly pre-cutoff

Derived in `s01` from `master_player` alone, admitted through the contract's own availability bound
(`game_date + 36 h`) and compared to the row's own `forecast_cutoff` with a **strict** `<`.

* `last_club_date`, `seasons_since_club`, `days_since_club` — her last admitted appearance for
  **this** club.
* `last_any_date`, `last_any_team` — her last admitted appearance **anywhere**.
* `departed` = she has an admitted appearance for another club that is **later** than her last
  admitted appearance for this one (or she has never appeared for this one).
* `n_prior_app_season`, `trail5_min` — for the decision stratum.

**Excluded by rule, not by preference:** `injury_history.csv` (no manifest ⇒ UNVERIFIABLE, and its
observation time is a single retrospective scrape dated after every row in this partition);
`roster_asof.csv` (`asof_granularity: artifact`, and it is derived from box scores);
`player_bios.csv` (no manifest, no team column); the pregame report capture (begins 2026-07-30).
**A retrospective baseline is the trap this programme has fallen into six times. None of these four
is used to build any rule that carries a verdict.**

---

## 4. The arms

`w` is the availability weight in the bottom-up sum; the champion emits `w = p_active_hat`.
**A row a rule removes keeps its row and takes `w = 0`** — exactly E1_I0035's Xc convention — so
every arm is scored on the identical RS1/RS1P rows and D101 holds. Removal's real cost is charged
separately, by name, in `COVERAGE_COST.csv`.

| arm | what it does | fitted on |
|---|---|---|
| **X0** | the champion as emitted | — |
| **Xa** | **the benchmark.** Per-stratum logistic recalibration, 4 strata (tier × declared-constant/fitted) | strictly earlier seasons |
| **Y_R1** | drop tier-B S2 rows where `departed` | — (no fitting) |
| **Y_R2** | drop tier-B S2 rows where `seasons_since_club ≥ 2` | — |
| **Y_R3** | drop tier-B S2 rows where either | — |
| **Y_R4** | drop **every** row where `departed`, tier A included — the over-reach arm | — |
| **Z_R\*** | the same removal, then Xa's recalibration fitted on the **surviving** rows of strictly earlier seasons | strictly earlier seasons |
| **Xa+** | *POST HOC.* Xa with the R3 currency flag as a **fifth/sixth stratum split** (8 strata), removing **no** row | strictly earlier seasons |

Where a training stratum is empty the row is left unrecalibrated and that is printed
(`walkforward_recalibration_fits.csv`), not hidden. No ORACLE/in-sample arm carries a verdict.

**Rules are scoped to S2-admitted tier-B rows** because §2 measured that tier-A departed rows
appear at 0.145 and are already priced at 0.212 — deleting them is harm, and R4 exists to
demonstrate that rather than to assert it. S2 admissibility is recomputed from `master_player`,
never read from the unverifiable contract.

---

## 5. Nulls, power, and which floor carries the verdict

**N1 — paired block sign-flip on the per-row loss difference.** Team cells block at **team-season**
(36 blocks full, 24 clean — both above the six-block floor below which a two-sided sign-flip cannot
reject). Player cells block at **player-season**, the level a `p_active` repair varies at.

**The verdict-carrying floor is INJECTION-VERIFIED and is computed from each comparison's own
centred per-row loss difference.** The analytic MDE80 = 2.8016 × null_sd is printed beside it and
labelled, and where the two disagree **the injection floor wins**. `null_mean` and `null_sd` are
printed beside every p (D103 ruling 2).

**FREEZE THE INTERCEPT.** Reported for every arm, both ways.
*Team:* each arm's per-team-game Σ`w` is rescaled to Xa's, so the arm can then differ from Xa only
in **shape** — which players carry the weight.
*Player:* every arm receives one global intercept-only recalibration fitted walk-forward, so all
arms share a fitted global level and any residual Brier difference is shape.

**Type-I check:** 400 synthetic no-effect datasets through the full N1 path.

### Decision rules, fixed by the brief

* **DR1** TEAM-BENEFICIAL: MAE improvement over the stated reference is significant under N1 **and**
  exceeds that comparison's **injection-verified** floor.
* **DR2** PLAYER-SAFE: does not significantly worsen Brier on RS1P **or** on RS1P-A, and leaves the
  conditional `pts_hat` MAE bit-identical.
* **DR3** BEATS Xa only if DR1 and DR2 both hold **against Xa**, on the clean window.
* **DR4** underpowered ⇒ **NOT ESTABLISHED**, never "no effect" (D103).
* **DR5** a rule whose gain disappears when the intercept is frozen has produced a **level** effect,
  and E1_I0035 established that a level effect cancels exactly in the only downstream consumer.

---

## 6. Where this screen could cheat, declared

* **C-1 — building a rule from realised appearance rates and scoring it on the same rows.** The
  rules are *thresholds on pre-cutoff appearance history*, not fits to the response; every
  recalibration attached to them is walk-forward on strictly earlier seasons.
* **C-2 — pruning rows and scoring only the survivors.** Removed rows keep their row at `w = 0`;
  the coverage loss is charged by name.
* **C-3 — reporting only the team level.** Both, in the same table, always.
* **C-4 — a level effect dressed as a repair.** DR5 and the frozen-intercept tables.
* **C-5 — using the unverifiable v5 tier column or the transaction wire.** Neither backs a number.
* **C-6 — τ shopping.** The recency curve is published whole (`recency_tau_curve.csv`); no τ is
  fitted and no τ-selected arm carries a verdict.
* **C-7 — presenting a post-hoc arm as preregistered.** §0 names Xa+ as post hoc.
* **C-8 — reporting the decision stratum only if it helps.** It is reported **first**, before any
  headline, whatever it says.

---

## 7. Deliverables

`PREREG.md` (+ sha256) · `UNIVERSE_CONSTRUCTION.md` · `CURRENCY_RULE.md` · `COVERAGE_COST.csv` ·
`REACH.md` · `FINDINGS.json` · `NOTES.md` · `DEFECTS.md` · a CSV for every published number ·
`nulls/*.npz`.
