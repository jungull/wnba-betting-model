#!/usr/bin/env python3
"""Emit REPORT.md for the totals groundwork recon (mirrors the per-experiment
write_report.py convention, e.g. experiments/channel_reval/write_report.py).
Content is static — the numbers were produced and verified by
run_totals_groundwork.py in this folder; rerun that script first if data moved.
"""
from pathlib import Path

REPORT = r"""# Totals-Market Groundwork — Inventory, Benchmarks, Diagnosis

*2026-07-30 · RECONNAISSANCE ONLY — not a registered experiment. Nothing here touches the
ledger, leaderboards, or any data file; every number is exploratory and re-derivable from
`run_totals_groundwork.py` in this folder (read-only on all inputs, writes only here).
Conventions deliberately mirror the registered margin benchmark
(`oracle_bracket.build_bookie_margins`: latest snapshot with `snap <= commence` per
(game, book), mean across books; that code reproduces the ledger's `bookie_gap.csv` exactly).*

---

## 1. Inventory — what totals data we actually have

**THE key fact: we already capture totals. No capture-config change is needed.**

- `odds_capture_daily.py` (hourly live, task `WNBA_OddsCapture`) requests
  `MARKETS = "spreads,totals,h2h"` — line 25.
- `odds_backfill_2025_26.py` (the 292-snapshot July-2025→now backfill) requested the same
  three markets — line 32.
- Scan of **all 299 raw snapshot JSONs on disk** (292 `historical/hist_*.json` + 7
  `live_*.json`): **1,503 of 1,503 event-sightings quote totals** in at least one book —
  every file, every event (`raw_snapshot_market_inventory.csv`).
- `build_odds_master_extension.py` already flattens totals + h2h into
  `data/odds_capture/master_odds_extension_other_markets.csv` (totals live in the
  `market_key/outcome_name/outcome_point` columns).

### Coverage by season (`inventory_by_season.csv`)

| Era | Source | Season | Totals rows | Games w/ totals | Books |
|---|---|---|---|---|---|
| Old (2022 → 2025-07-04) | `data/drive_masters/master_odds.csv` | 2022 | **0** | 0 of 180 odds-covered | — |
| | | 2023 | **0** | 0 of 259 | — |
| | | 2024 | **0** | 0 of 261 | — |
| | | 2025 (≤ Jul 4) | **0** | 0 of 113 | — |
| New (2025-07-05 → now) | `master_odds_extension_other_markets.csv` | 2025 | 12,486 | **197** | 11 |
| | | 2026 (thru Jul 29) | 15,334 | **209** | 11 |

The old master is structurally spread-only (columns `team / odds_spread / odds_price`, no
market dimension). Exhaustive search found no other odds tables, databases, or totals columns
anywhere on disk (legacy `wnba_odds_system` logs are empty failed-scrape artifacts;
`wnba-odds-aggregator` fixtures are samples). **So: zero totals for 2022, 2023, 2024, and
2025 before Jul 5; full totals coverage from 2025-07-05 onward, accumulating hourly.**

Data quality: Over/Under points are perfectly symmetric — 13,910 (event, book, snapshot)
pairs, 0 mismatches, 0 nulls. 94 in-play rows (snapshot > commence) identified and excluded
by timestamp, per the extension's documented convention.

**Recoverable, unverified:** Google Drive `historical_odds/` (the raw multi-snapshot JSONs
behind the old master — HANDOFF §1). The legacy aggregator client requested
`h2h,spreads,totals` (`wnba-odds-aggregator/src/api/odds_api_client.py:33`), so the archive
*may* contain 2022–2025 totals — but the fetcher that built the old master was named
`fetch_historical_wnba_spreads.py` (not in this repo), so it may equally be spreads-only.
Unknowable until John downloads the folder; treat pre-2025 totals as absent until proven
otherwise.

## 2. Bookie totals accuracy (the market benchmark we would chase)

Consensus = mean across books of each book's last pre-tip total; actual = sum of final
scores from `data/masters/master_team.parquet` (406/406 mapped games matched; row-level
evidence `bookie_totals_per_game.csv`, summary `bookie_totals_mae_by_season.csv`).

| Season | n games | Bookie totals MAE | RMSE | Bias (line − actual) | Mean actual total | SD actual |
|---|---|---|---|---|---|---|
| 2025 (from Jul 5) | 197 | **13.255** | 16.39 | −0.51 | 163.6 | 17.5 |
| 2026 (thru Jul 29) | 209 | **16.468** | 20.53 | **−3.48** | 174.2 | 21.8 |
| Pooled | 406 | **14.909** | 18.64 | −2.04 | 169.1 | 20.5 |

Context: totals are an intrinsically harder target than margins — on these same games the
bookie *margin* MAE is ~10.2. Note the 2026 environment: actual totals are up ~10.5 points
on 2025 and **even the market is under by 3.5 points on average** — books are trailing the
2026 scoring surge too. Where totals lines don't exist (2022–2024, early 2025) there is
nothing to benchmark against; those seasons are simply out of scope for any market-relative
totals claim.

## 3. Our model vs the bookie totals, paired same-games

Our totals prediction: `str_total_cal` from `experiments/channel_reval/predictions_v2.csv`
(= calibrated home + calibrated away score; the gate-4 joint-forecast component). Full-673
sanity check reproduces the registered REPORT.md figures exactly (str 14.2236 / raw 14.7630).

**Full 673-game test set** (`model_totals_mae_by_season_full673.csv`):
2024 **13.068** (n=229) · 2025 **13.364** (n=276) · 2026 **17.212** (n=168) · pooled **14.224**.

**Paired subset — the 365 test games that also have a pre-tip consensus total**
(197/197 covered 2025 games are eligible test games; 168 of 209 covered 2026 games are —
the other 41 fall under the early-season 5-game eligibility floor; 2024 pairs: zero, no
totals lines exist). Row evidence `model_vs_bookie_totals_paired.csv`, summary
`paired_summary_by_season.csv`:

| Season | n | Model MAE | Bookie MAE | Gap (model−bookie) | 90% CI on paired Δ* | Model closer |
|---|---|---|---|---|---|---|
| 2025 | 197 | 13.491 | 13.255 | +0.236 | [−0.72, +0.26] | 42.6% |
| 2026 | 168 | 17.212 | 16.849 | +0.363 | [−0.79, +0.07] | 45.2% |
| Pooled | 365 | **15.203** | **14.909** | **+0.295** | [−0.62, +0.03] | 43.8% |

*Δ = |bookie err| − |model err|, positive = model better; date-clustered bootstrap, seed 42,
4,000 reps — exploratory, ungated.*

**The reference point that matters:** on these same 365 games the *margin* model trails the
bookie by **+0.364** (10.565 vs 10.201). Our totals forecast stands relative to its market
almost exactly where our margin forecast stands relative to its market (+0.295 vs +0.364).
Totals are not a weak limb of the model — they are simply a higher-variance target on which
model and market degrade together (model↔bookie totals correlation 0.88).

## 4. Diagnosis — is the totals error structure different from margin? (exploratory)

Evidence: `totals_error_decomposition.csv`, `home_away_error_covariance.csv`,
`totals_bias_by_month.csv`, `paired_bias_comparison.csv`, `exploratory_bias_fix_summary.csv`.

1. **The totals/margin MAE gap is structural, not a modeling defect.** Home-side and
   away-side errors are positively correlated (pooled cov +40.8, r = 0.334): shared
   game-environment error (pace, officiating, shooting variance) **adds** in the total and
   **cancels** in the margin — var(total err) 326 vs var(margin err) 163 from the *same*
   chains. The same physics binds the bookie (totals MAE ~15 vs margin ~10).
2. **Season-level bias, concentrated in 2026.** Bias (pred − true): 2024 −0.03, 2025 +0.28,
   2026 **−4.97**. The model under-predicts the hot 2026 environment every month
   (June −6.9, July −5.6). The bookie shares the direction (−3.4 on paired 2026) but adapts
   faster. Margin bias, by contrast, is ≤1.4 in every season — margin is immune to
   environment level shifts, totals are maximally exposed.
3. **Under-dispersion.** SD(pred total) 5.4 vs SD(actual total) 19.4; OLS slope of true on
   pred 1.33 pooled (>1 = predictions too compressed). Expected for a
   conditional-mean forecast, but with slope persistently >1 the totals signal is being
   under-used: `str_total_cal` is the sum of two per-side calibrations fit on 2021–2023
   (`run_reval.py:260-263`) — **no dedicated totals calibration exists**, and a 2021–23
   line fit cannot track a 2026 level shift.
4. **How much would trivial fixes buy? (exploratory sensitivity, walk-forward-safe)** A
   same-season trailing mean-residual correction cuts 2026 MAE 17.21 → 16.91 (vs bookie
   16.85 — i.e., closes ~84% of the 2026 gap-to-market) but slightly hurts 2024/2025 and is
   pooled-neutral (14.22 → 14.28). An environment-only floor (expanding same-season league
   mean total) scores 14.88 pooled — our model beats "just track the environment" by only
   0.65. Real headroom therefore sits in (a) faster environment/level tracking and
   (b) an explicit totals head, not in more margin-style structure.

## 5. Verdict — is a registered totals experiment worth running now?

**Yes — a modest, well-scoped regime-A experiment is justified now; no data capture is
blocking.** The market-relative position (+0.295, CI already spanning zero on 365 paired
games) is close enough that a dedicated totals treatment has a realistic shot at parity,
and the diagnosis identifies concrete, cheap mechanisms (2026 level bias −4.97;
no totals-specific calibration; slope 1.33). Expectations must stay modest: the intrinsic
error floor is high (~15), and this serves the **forecasting** leaderboard
(`leaderboards/FORECASTING.md` already scopes "score/margin/total") and gate-4 joint
coherence — *not* a betting-edge claim (43.8% closer-than-market is nowhere near
over/under bet territory; system-3 questions stay in Phase 3).

**Suggested registration sketch (orchestrator's call):**
- **Incumbent:** `str_total_cal` as produced by the promoted `chanreval_2026` architecture —
  pooled 14.224 on the 673-game test set (2024 13.068 / 2025 13.364 / 2026 17.212).
- **Challenger family (one registered hypothesis):** a dedicated totals head on top of the
  frozen structural chains — explicit totals calibration + walk-forward environment/level
  tracking (e.g., expanding same-season league-total term); optionally a pace proxy from
  possessions data. Odds stay banned (regime A, basketball system).
- **Gates (standard 5-gate template, thresholds preregistered):** primary metric
  `total_mae`; min pooled improvement scaled to the totals error magnitude (~0.15–0.20 pts
  rather than the margin default 0.10); per-season non-inferiority; **gate 4 in reverse** —
  margin/home/away must not degrade (do not let a totals head contaminate the margin
  forecast); coverage unchanged. Market benchmark rows (new-era consensus totals, n stated)
  reported alongside, never gated on — 2024 has no totals market to benchmark against.
- **Bench reference floors for the registration:** league-mean environment floor 14.88;
  bookie consensus 14.91 on the 406-game covered slice.

**Capture actions:**
1. **None required today — flag defused.** Live hourly capture already requests totals and
   has since day one; every raw snapshot on disk carries them. The totals benchmark
   thickens by itself from here (~197 games/season-half so far).
2. **Drive `historical_odds/` download (John, existing backlog item)** doubles in value:
   *verify on arrival whether the old-era raw JSONs carry totals* (aggregator code says
   maybe; the `fetch_historical_wnba_spreads.py` name says maybe not). If yes, 2022–2024
   totals benchmarks come free.
3. **Optional, John's budget call:** The Odds API historical endpoint could backfill 2024
   totals at ~60 credits/game-date (~110–130 dates/season ≈ 7–8K credits; ~11.2K remain,
   paid month ends ~Aug 30). Not needed for a regime-A experiment — the 673-game truth set
   needs no odds — only for extending the *market benchmark* to 2024.

## Files

- `run_totals_groundwork.py` — regenerates everything below (read-only on all data)
- `write_report.py` — emits this report
- `raw_snapshot_market_inventory.csv` — per-snapshot-file market presence (299 files)
- `inventory_by_season.csv` — totals coverage by era/season/table
- `bookie_totals_per_game.csv` (406 rows) · `bookie_totals_mae_by_season.csv`
- `model_totals_mae_by_season_full673.csv` — our totals MAE, full test set
- `model_vs_bookie_totals_paired.csv` (365 rows) · `paired_summary_by_season.csv`
- `totals_error_decomposition.csv` · `home_away_error_covariance.csv` ·
  `totals_bias_by_month.csv` · `paired_bias_comparison.csv`
- `exploratory_bias_fix_per_game.csv` · `exploratory_bias_fix_summary.csv` — sensitivity
  runs behind §4.4
"""

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "REPORT.md"
    out.write_text(REPORT, encoding="utf-8")
    print(f"wrote {out} ({len(REPORT.splitlines())} lines)")
