# MODEL_VS_MARKET.md -- legacy points model vs the props market (FIRST comparison)

Generated 2026-08-21T15:46:58.032250+00:00. Evidence class **PRELIMINARY**. Authority: D023 / D027 / D034 / D036 / D037. No evidence-ladder label is claimed or held.

## Headline (plain language)

**Does the legacy points model beat the market's over/under calls?** **No.** On the matched universe the legacy model's over/under calls are beaten by the market's own de-vigged majority calls; the clustered 95% CI on the paired difference excludes zero.

- Universe: **A_primary matched player-games, pooled 2024-2026** (strict intersection; matched player-games only)
- N = 5737 player-games; model OU accuracy **0.4940** vs market OU accuracy **0.5268**
- Paired difference (model - market): **-0.0328**, game-date-clustered 95% CI **[-0.0492, -0.0172]** (seed 20260806, 1000 draws)
- Market de-vigged Brier (P(over) vs outcome): **0.2488**. The model has NO Brier: it is a point prediction, not a probability.

**Timing honesty (read before using this number):** every timing aspect of the market side is **T1 / VENDOR_ASSERTED** (D027). The prop snapshot timestamps were never witnessed by this program; whether the legacy model's forecast cutoff truly preceded the market snapshot is **asserted, not witnessed**. In the vendor-asserted timeline the market snapshot (~T-65m) post-dates the model cutoff on all but 15 of the evaluable rows (median gap +0.34h, p95 +30.8h), i.e. the market saw later information than the model on those rows IF the vendor stamps are truthful. That asymmetry is advisory context (contract section 6.2 vendor-asserted channel), never a claim.

**Bounded-use compliance (D027 -> M00-U2, caveat verbatim):**

> Calibration is of a snapshot whose capture time is vendor-asserted and unwitnessed (P2B: CUTOFF_UNPROVEN). Results characterize an unknown-time pregame price level and must not be read as closing-line calibration, opening-line calibration, or calibration at T−64 minutes. No CLV, timing, or line-movement inference may be built on this result.

(caveat_hash `39b8dbde2fc3407e5563752775c18e61f161946b216cbd0194c8d0c110997e7b`; object: `master_props_historical.csv`, T1_VENDOR_ASSERTED. No CLV, timing, lead-lag, stale-window or executability claim is made.)

## 1. What was compared

| side | quantity | source |
|---|---|---|
| model | `pred_point` of `player_scoring_distribution`, RECEIPTED legacy run `cbs_v15_player_oof_v5/1` (7/7 verification, VERIFICATION_REPORT.md); generation-consistent rows only (per-row forecast_cutoff byte-equal to the contract) | `experiments/cbs_v15_player_oof_v5/attempt_002/` |
| market | de-vigged consensus threshold probability P(points > line) at the consensus line; vig removal DELEGATED to M11 `consensus.py` (preregistered multiplicative method, uniform weights) | `master_props_historical.csv` (T1) |
| outcomes | owned regular-season gamelogs (hashes in json) | `data/` |

Calls: model says OVER iff `pred_point > consensus_line`; the market says OVER iff de-vigged P(over) > 0.5. Consensus line = the line quoted two-sided by the most books (ties: nearest the median line, then lower); books at other lines are excluded and counted -- thresholds are never blended (D036 point 5). All lines are *.5 so no pushes exist (asserted in code).

## 2. OU-call accuracy, A_primary (headline universe)

| season | N | model OU acc | market OU acc | paired diff | diff 95% CI (clustered) | market Brier |
|---|---|---|---|---|---|---|
| 2024 | 1685 | 0.4831 | 0.5187 | -0.0356 | [-0.0657, -0.0049] | 0.2495 |
| 2025 | 2107 | 0.4964 | 0.5486 | -0.0522 | [-0.0780, -0.0259] | 0.2471 |
| 2026 | 1945 | 0.5008 | 0.5100 | -0.0093 | [-0.0355, +0.0196] | 0.2502 |
| pooled_2024_2026 | 5737 | 0.4940 | 0.5268 | -0.0328 | [-0.0492, -0.0172] | 0.2488 |

## 3. OU-call accuracy, all_tiers (labelled aggregate, never the headline)

| season | N | model OU acc | market OU acc | paired diff | diff 95% CI (clustered) | market Brier |
|---|---|---|---|---|---|---|
| 2024 | 1726 | 0.4832 | 0.5197 | -0.0365 | [-0.0663, -0.0058] | 0.2494 |
| 2025 | 2158 | 0.4954 | 0.5496 | -0.0542 | [-0.0784, -0.0298] | 0.2471 |
| 2026 | 2005 | 0.5017 | 0.5127 | -0.0110 | [-0.0388, +0.0162] | 0.2501 |
| pooled_2024_2026 | 5889 | 0.4940 | 0.5283 | -0.0343 | [-0.0510, -0.0173] | 0.2488 |

## 4. Threshold-distance comparison (NOT projection error)

Per D036 point 5 this framing is explicitly distinct from projection MAE: `|consensus_line - outcome|` measures how far the betting THRESHOLD sat from the outcome. The line is not the market's point projection (it is set with vig and flow considerations), so the column pair below is model-projection-distance vs threshold-distance -- related, paired on identical rows, but never read as two projection errors.

### A_primary

| season | N | mean \|pred-outcome\| | mean \|line-outcome\| | paired diff | diff 95% CI (clustered) |
|---|---|---|---|---|---|
| 2024 | 1685 | 5.1855 | 4.9427 | +0.2428 | [+0.1538, +0.3413] |
| 2025 | 2107 | 5.2062 | 4.9907 | +0.2154 | [+0.1292, +0.3033] |
| 2026 | 1945 | 5.1241 | 4.8861 | +0.2380 | [+0.1584, +0.3237] |
| pooled_2024_2026 | 5737 | 5.1723 | 4.9412 | +0.2311 | [+0.1784, +0.2825] |

### all_tiers

| season | N | mean \|pred-outcome\| | mean \|line-outcome\| | paired diff | diff 95% CI (clustered) |
|---|---|---|---|---|---|
| 2024 | 1726 | 5.2299 | 4.9368 | +0.2930 | [+0.1880, +0.4085] |
| 2025 | 2158 | 5.2524 | 4.9935 | +0.2589 | [+0.1597, +0.3675] |
| 2026 | 2005 | 5.1944 | 4.8885 | +0.3059 | [+0.1871, +0.4410] |
| pooled_2024_2026 | 5889 | 5.2261 | 4.9412 | +0.2849 | [+0.2212, +0.3590] |

## 5. Full join audit (no silent drops)

Market side (props archive -> consensus player-games):

- archive rows: 36946 over 784 games (sha256 `47983f8725e775aa...`, T1 per D027)
- in-play rows excluded (structural, contract 4.4): 0
- one-sided rows excluded (cannot de-vig): 5603 (by book: {"betrivers": 5591, "bovada": 6, "betmgm": 4, "betonlineag": 2})
- two-sided rows kept: 31343; same-book-same-line duplicates dropped: 0
- unresolved player names (O14 normalized-exact + alias table; excluded AND listed): 62 rows -- Cheyenne Parker (62 rows / 14 games)
- resolved two-sided prop player-games: 6529; book quotes excluded for sitting on a non-consensus line: 3463

Model side (RECEIPTED legacy artifacts -> scored points rows):

- prediction rows (all seasons): 44851; generation-inconsistent cutoff rows excluded: 0; producer-excluded rows: 0
- no gamelog outcome row: 18444; outcome-team mismatch (dual obligations): 231; zero-minute rows (conditional target): 32
- scored model rows: 26144

Intersection:

- matched player-games: **5966** across 738 games (market player-games with no matched model row: 563; market games with no matched row: 46 -- see `unmatched_market_note` in the json)
- by tier: {"A_primary": 5808, "B_transaction_sensitivity": 153, "B_s2_weak_fallback": 5}; by season: {"2024": 1768, "2025": 2186, "2026": 2012}
- pushes (outcome == line): 0; model no-call (pred == line): 0; market no-call (P(over) == 0.5): 77
- evaluable matched player-games: **5889** (headline A_primary pooled cell: 5737)

## 6. Provenance

- contract sha256 verified: `1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de`
- vig preregistration hash: `021dc75506a43a8a849f2d57a7b4aae1b6410e9bccb3a1a88f5f4412c1f60bc6` (method `multiplicative_proportional`, frozen in consensus.py before any evaluation)
- consensus.py sha256: `b94ce8a9467a37fd0d99de9ac889039ac56e44d1feea39e0adcd57abcc749dfa`
- prediction artifact sha256 (per season) and all input hashes: in `model_vs_market.json`
- commit: UNAVAILABLE: no git in this worktree per task constraints; the legacy producing run's clean-tree receipt asserts commit 0108ef86e9c085e1d701e40e53c24dcde177ac97 (reproduced, not independently verified); manifest content hashes are the verified anchors
- seed 20260806, 1000 bootstrap draws, clusters = game dates (same method as the granular scoreboard)

Epistemic status of the consensus machinery (verbatim, per M11): "MARKET-REACTION SYSTEM COMPONENT under the four-system separation. Estimates a consensus fair line from multi-book quotes. It models the market, not the game; its output is never a fundamental prediction and is labelled per the M00 ladder."

This number feeds the leaderboard **Market Advantage** column for the legacy points row, evidence class PRELIMINARY.
