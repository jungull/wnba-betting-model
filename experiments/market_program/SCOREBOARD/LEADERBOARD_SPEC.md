# Prediction Leaderboard — frozen build spec (user directive, 2026-08-06, verbatim in substance; D038)

Update the persistent scoreboard into a user-facing Prediction Leaderboard. Preserve the current generated, hash-manifested pipeline and all audit rigor, but redesign the visible experience for an intelligent outsider who does not know statistical terminology.

## Product goal
Within ten seconds, the dashboard should answer: 1. What do we predict best? 2. How close are our predictions to reality? 3. How much better are we than a simple baseline? 4. Where do we outperform the market? 5. How strong is the evidence?
Showcase the strongest verified work first. Methodology, uncertainty, raw metrics and limitations remain available through hover, expandable rows and the detailed evidence layer. Do not reduce backend rigor. Reduce front-end cognitive load.

## Primary leaderboard
One sortable and filterable table, one row per prediction target.
Default sorting: 1. Verified results before preliminary. 2. Highest Prediction Score first. 3. Unevaluated targets afterward.
Visible columns: Prediction target · Prediction Score · Typical Miss · Within Target Range · Improvement vs Basic Model · Market Advantage · Sample · Evidence · Last Updated. Every column sortable both directions.
Filters: All/player/team/game targets · Verified only · Market-covered only · Regular season/playoffs · Season · Prediction cutoff where meaningful. Mobile-readable; horizontal scroll only if necessary.

## Prediction Score
One prominent comparable 0–100 score per target; higher always better. Bands: 90–100 Exceptional · 80–89 Strong · 70–79 Useful · 60–69 Modest skill · 50–59 ≈ basic-baseline quality · <50 No demonstrated improvement.
The score = predictive skill relative to a DECLARED appropriate baseline on the EXACT same evaluation universe. Never a normalization of raw MAE across unrelated units. Evidence strength and market edge stay OUT of the score (separate axes: accuracy / beats-market / certainty). Design and FREEZE the scoring transformation before exposing additional model results; store formula+version in structured data; expose in methodology. No attractive placeholder scores — unevaluated targets remain TBD.

## Plain-English subtext
Under every score: "Usually within X units of the actual result" (properly computed typical absolute error, readable rounding); e.g. correct winner in 69% of games. Also a declared target-range success rate where meaningful. Initial tolerance bands (freeze before viewing model results; store in config; never change to improve presentation): points ±5 · rebounds ±2 · assists ±2 · minutes ±5 · game total ±10 · margin ±8.

## Improvement vs Basic Model
Plain language vs the declared naive baseline on the identical universe ("11% more accurate than a season-average prediction" / "Roughly equal" / "No demonstrated improvement"). Hover identifies exact baseline, metric, universe, CI. Never compare unmatched universes.

## Market Advantage
Separate sortable column answering: on directly comparable, timestamp-matched observations, does our model add predictive information beyond market consensus? Labels: Strong / Meaningful / Slight advantage · Market-level · Market currently better · Not comparable · Pending. Show numeric improvement when defensible (+6.2% lower error than market consensus; +0.018 Brier). Never collapse MAE/Brier/log-loss/ROI into one number — target-appropriate metric translated to common direction (positive = we did better); methodology layer shows the raw comparison. Only calculable when: same target, same games/player-games, same declared cutoff, documented consensus method, no hindsight best-book-per-outcome.

## Evidence badges
VERIFIED (audited blind walk-forward or adequate prospective) · PROMISING (positive retrospective, unconfirmed) · PRELIMINARY (small sample / exploratory / legacy-receiptable) · PENDING (implementation exists, evaluation not completed) · NOT CAPTURED (data does not exist). Never SEALED before an evaluation ran. Lifecycle: BUILT → AUDITED → FITTING → EVALUATED/SEALED → ADJUDICATED. Implementation test counts live in operational progress only.

## Top summary cards
Best Prediction (target, score, typical miss) · Largest Market Advantage (or "Not yet demonstrated") · Most Reliable Result (target, N, evidence class) · Betting Edge (prospective executable edge status only — never substitute predictive accuracy for betting profitability: "Not yet demonstrated — prospective sample accumulating" / "Promising — not yet confirmed" / "Verified — see betting performance").

## Hover / expansion
Default page simple. Hover: model/version, raw metric, baseline result, market result, improvement %, cutoff, N, date range, evidence class, CI, source artifact, commit SHA. Expanded rows: season-by-season, error distribution, model vs baseline, model vs market, coverage/missingness, calibration, known limitations, provenance links. An outsider never needs these to understand the headline.

## Player-level leaderboard — future-ready
Schema+interface ready to rank players-we-model-best, largest-market-advantage players, stable-vs-volatile roles, stat families. Do NOT publish player rankings until minimum-sample and shrinkage requirements pass; show locked state: "Player-level leaderboards are collecting sufficient verified samples." Future rankings must account for min sample, player-specific baseline difficulty, market-matched universe, role stability, uncertainty/shrinkage, team changes, minute volatility. Never rank players by raw MAE alone.

## Existing granular numbers
Preserve granular baseline calculations; never describe cross-stat predictability from raw MAE alone (blocks' small errors ≠ predictability). Raw natural-unit MAE = Typical Miss; the Score = normalized skill vs appropriate baseline. Keep visible in methodology: prediction error ≠ threshold distance ≠ probability quality ≠ market advantage ≠ betting profitability. A prop line is a threshold, not automatically a point projection.

## Data architecture
Generated from committed structured inputs; no hand-editing. Retain/extend: metrics.json · data_coverage.json · lifecycle.json · score_config.json (NEW) · build_scoreboard.py · scoreboard.html · scoreboard_manifest.json. score_config.json holds: Prediction Score formula+version · interpretation bands · target tolerance bands · baseline identity per target · market comparison metric per target · minimum evidence requirements · default sorting and filters. Every displayed number traceable to: model version, target, cutoff, universe, date range, N, metric, estimate, CI, evidence class, source artifact/hash, commit SHA, computation timestamp.

## Acceptance checks (deterministic tests)
1 every visible score generated from structured inputs · 2 higher score always = better skill · 3 no score for unevaluated targets · 4 Market Advantage uses matched universes+cutoffs · 5 best/worst book never re-selected after outcomes · 6 tolerance bands fixed in config · 7 default sorting = strongest verified first · 8 all columns sort both ways · 9 filters never alter metric values · 10 hover values match source JSON · 11 byte-identical regeneration from unchanged inputs · 12 dropped-cells honesty log visible in methodology layer.

Preserve the existing artifact link. Regenerate, verify manifest hashes, commit, republish. Report exactly which cells changed, which remained pending, which claims were removed.
