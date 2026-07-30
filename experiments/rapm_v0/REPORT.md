# RAPM v0 — possession attribution + first ridge fit (ROADMAP Phase 2b)

*2026-07-30. Infrastructure + diagnostics only. **No promotion claim is made and no
registry entry exists for this build** — the registered promotion experiment comes later,
when minute-weighted aggregation challenges the team chains under the harness. Per ROADMAP
§2b, "known stars rank sensibly" is a smoke test for broken data, never a criterion.*

Code: `build_possessions.py`, `build_rapm.py` (repo root). Console log: `build_log.md`
(this dir). Runtime: possession build 181s over 1,424 games; RAPM fit + all diagnostics 12s.

---

## Stage 1 — possession attribution (`data/possessions/possessions.parquet`)

One row per possession for **all 1,424 PBP games** (996 V2 + 428 V3, everything
`wnba_schema.normalize_pbp` can see; master_team covers all of them): 2021–2026 regular
seasons + 2021/2025 playoffs (2022–24 playoff pbp is not on disk — noted, not hidden).
**227,385 possessions**, 27 columns including per-side five-player lineups joined from
`data/derived/stints.parquet`, per-possession running score, era, and `end_reason`.

### Rules (uniform across eras)
- Ball-indicator events (shots, non-technical FTs, turnovers, rebounds) are segmented into
  maximal same-team runs; each run is one possession. This yields the standard rules with
  no lookahead: and-one FT bundles stay one possession; flagrant/clear-path retained-ball
  sequences stay one possession; offensive rebounds (incl. team rebounds off dead balls
  after non-final missed FTs — verified credited to the shooting team in both eras)
  continue the possession; defensive rebounds / turnovers / made final FTs / period end
  close it. Each period's opening offense is inferred from its first indicator (no
  possession-arrow model).
- **Technical FTs never flip possession.** Made technical points are folded into the
  current possession when the shooter's team is on offense (380 cases), else land in a
  zero-duration `technical_ft` row (571 rows) so per-team totals stay exact. Dead-ball
  rebound rows trailing missed technical FTs are skipped (187).
- **Lineup rule (documented, applied uniformly):** possessions are **not split** at
  substitutions. Each side gets the five players with the largest time-overlap with the
  possession interval (majority-time; half-open intervals so boundary subs credit the
  incoming player; ties by player id). 99.97% of possessions have full 5v5 lineups
  (128 `lineup_underfull` instances).
- **Source-defect guard:** six V2 games (2021/2023) double-log one made shot (identical
  clock + description, and the source's own running-score column does not advance on the
  copy). Rows are dropped only under that two-part proof (`dup_scoring_row_dropped`: 6 —
  exactly games 1022100151, 1022300119, 1022300136, 1022300137, 1022300142, 1022300238).

### Reconciliation — the gate
Per game, possession points summed per offense team vs `master_team` final scores:

| metric | value |
|---|---|
| **Exact per-team score match** | **1,424 / 1,424 = 100.00%** (target ≥ 99.5%) |
| by season | 2021–2026 all 100.00% |
| non-exact games | none (before the dup-scoring-row guard: 6 games, residuals +2/+3, all the duplicated-shot defect above) |

Residual anomaly counters (kept, all benign to scoring): `inferred_flip` 200 (held-ball /
away-from-play flips with no classifiable ending event), `miss_flip_no_rebound` 8,
`made_ft_nonfinal_flip` 2, `indicator_no_team` 2, `period_opens_with_rebound` 1.

### Pace sanity + independent cross-check
- Possessions per team per 40 min (technical rows excluded): **mean 79.16, sd 3.87,
  p5 73.0, p50 79.0, p95 85.2**, min 66 / max 94; 99.1% inside [70, 90]. Matches the known
  WNBA ~75–85 band.
- Cross-check vs V3 advanced boxscore (`possessions` = sum of player possessions / 5),
  100-game random sample (seed 20260730), 200 team-games: **corr 0.9656, mean |diff| 1.92,
  bias −1.91** (mine lower). The deficit is consistent with event-less trailing possessions
  (inbound with no shot/TO/rebound before the horn) that an event-derived count cannot
  see, while the league's counted metric includes them; a systematic ~2.4% level offset,
  not noise.

### Standing certification
`daily_certify.py` now runs **possession reconciliation** as check 6 (the former TODO
hook): re-derives the 8 most recent games from raw pbp via
`build_possessions.reconcile_sample` and requires exact per-team score matches
(PASS = all exact; WARN = any non-exact; FAIL = >3 non-exact or errors). Current run:
PASS, 8/8 exact, ~8s. Full-history evidence: `data/possessions/reconciliation.csv`.

---

## Stage 2 — RAPM v0 (`data/rapm/rapm_v0.csv`)

Ridge on possessions: target = points scored on the possession; unpenalized intercept +
unpenalized home-offense indicator; +1 offense dummy and +1 defense dummy per player;
closed-form numpy solve (house convention). λ in **possessions-equivalent** units, swept
{500, 1000, 2000, 5000}. Rows used: non-technical, full 5v5 lineups (226,750 = 99.72% of
table). **Train 2021–2024:** 144,537 possessions / 905 games / 265 players. **Held out
2025–2026:** 82,213 / 519 games. Train points-per-possession 1.0230; home coefficient
+0.0125–0.0132 pts/poss (≈ +1.0 pt/game — offense-side only; defense-side home effect is
not separately modeled in v0).

Output conventions: `orapm_100` (+ = good offense), `drapm_100` (+ = good defense,
sign-flipped defense beta), `net_100` = sum, at λ=5000, plus `net_100_lam{500,1000,2000,5000}`.
Per-season fits: `rapm_by_season.csv`; stint-level eval rows: `stint_eval.csv`.

### Diagnostic 1 — predictive stint error (2025–26, never touched in training)
Stints = maximal lineup-constant possession runs (15,147 stints, mean 5.4 possessions).
Predicted vs actual home-minus-away points per stint, MAE:

| model | stint MAE |
|---|---|
| zero baseline (predict 0) | 2.1531 |
| team-strength baseline (2021–24 team off/def PPP from master_team + reconciled counts) | 2.1096 |
| RAPM λ=500 | 2.1045 |
| RAPM λ=1000 | 2.1001 |
| RAPM λ=2000 | 2.0965 |
| **RAPM λ=5000 (chosen)** | **2.0934** |

RAPM beats the team-strength baseline at every λ, by a small margin (best −0.016 vs team,
−0.060 vs zero). Context that keeps this honest: **22.4% of 2025–26 player-slots are
players unseen in 2021–24** (rookie classes + expansion GSV/POR/TOR) — both models predict
league-average there. MAE decreases monotonically in λ, so the argmin sits at the sweep
boundary; the true optimum may lie above 5000 (heavier shrinkage travels better across
roster turnover). λ=5000 is the v0 choice, not a tuned claim.

### Diagnostic 2 — year-over-year stability (single-season fits, λ=5000, ≥1000 poss both years)
- net r(2022 vs 2023) = **0.456** (n = 82)
- net r(2023 vs 2024) = **0.366** (n = 90)

Moderate at best — a single WNBA season is ~36k possessions, and single-season RAPM is
known to be noisy at that size. The multi-year fit is the usable object; per-season fits
exist for exactly this diagnostic.

### Diagnostic 3 — λ sensitivity (top-50 by net; Spearman on union of top-50 sets)
| pair | Spearman | top-50 overlap |
|---|---|---|
| 500 vs 1000 | 0.969 | 47/50 |
| 1000 vs 2000 | 0.952 | 49/50 |
| 2000 vs 5000 | 0.936 | 46/50 |
| 500 vs 2000 | 0.885 | 46/50 |
| 1000 vs 5000 | 0.844 | 45/50 |
| 500 vs 5000 | 0.753 | 43/50 |

Adjacent penalties agree strongly; the extremes (10x apart) still share 43/50 of the
top-50. Ordering is reasonably ridge-stable.

### Diagnostic 4 — garbage-time sensitivity
Garbage = period ≥ 4 and |margin before possession| ≥ 15: 9,854 of 144,537 train
possessions (6.82%). Refit at λ=5000 without them: net-rating r vs full fit = **0.9786**
(players ≥ 500 poss, n = 215). Ratings are insensitive to garbage time.

### Diagnostic 5 — replacement-level behavior
- players < 300 poss (n=35): mean net **−0.069**, min −0.54, max +0.38 (per 100)
- players ≥ 1000 poss (n=198): mean net **+0.121**
- all players: mean net −0.000

Low-sample players sit below the rotation-player average and are shrunk to sub-1-per-100
magnitudes — below average, not zero-noise extremes. Sane.

### Smoke test ONLY (orchestrator eyeball for broken data — never a gate)
Players ≥ 1500 possessions 2021–24, λ=5000. Top-15 offense: Stewart +4.13, Plum +4.06,
Young +3.27, J. Jones +3.20, Diggins +3.08, Boston +2.96, Sabally +2.96, Ionescu +2.92,
Quigley +2.88, C. Gray +2.75, McCowan +2.69, A. Wilson +2.46, Mabrey +2.31, B. Jones
+2.20, Bonner +2.12. Top-15 defense: J. Jones +2.70, B. Jones +2.65, Vandersloot +2.64,
Parker +2.46, Diggins +2.12, Bonner +1.93, Loyd +1.89, Carleton +1.87, A. Thomas +1.85,
Al. Smith +1.81, Delle Donne +1.79, Al. Clark +1.76, Stewart +1.75, Austin +1.73, Fiebich
+1.67. (Minutes for each are in `build_log.md` / the CSV.) Nothing absurd: MVP-tier names
at the top with 3,000–4,800 minutes; no low-minute noise entries.

---

## Known limitations (carry forward to the promotion experiment)
1. 2022–2024 playoff pbp is absent from disk, so those possessions don't exist here.
2. Event-derived possession counts miss event-less trailing possessions (~2 per team-game
   vs the league's counted metric); scoring reconciliation is unaffected.
3. Home effect is offense-side only (single indicator).
4. The λ sweep's held-out argmin is at the boundary (5000) — widen the sweep before any
   promotion-facing use.
5. Stint-level margin MAE differences are small in absolute terms; the decision-grade
   comparison is the ROADMAP one — minute-weighted aggregation vs team chains under the
   harness with a preregistered gate. This build claims nothing.
