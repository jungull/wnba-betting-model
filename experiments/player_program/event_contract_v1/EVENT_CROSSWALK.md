# `canonical_player_events/1` — crosswalk and limitations

589,130 events over 1,495 games. **18/18 validation checks pass.** Nothing is fitted, nothing is
scored, no possession is linked, no denominator is chosen.

## Source partition

| store | schema | games | events | which games |
|---|---|---|---|---|
| `data/playbyplay/` | legacy `PlayByPlayV2` | 996 | 383,377 | regular season 2021–2024 in full, plus 2025 RS through 2025-06-29 |
| `data/refresh_2026/pbp/` | modern CDN | 499 | 205,753 | **every playoff game 2021–2025** (106), 2025 RS from 2025-07-03 (178), all of 2026 (215) |

`996 + 499 + 0 both + 0 neither = 1495`. The partition is exact and disjoint.

**The boundary is two-dimensional, not a single date.** An earlier summary of mine called it "a hard
mid-2025 changeover"; that was wrong. The CDN span begins 2021-09-23 because playoffs were
backfilled from the CDN source for every season. A global first/last-date test is misleading — the
boundary is only clean when tested stratified by season and season type.

## Family crosswalk

| canonical family | legacy `EVENTMSGTYPE` | CDN `actionType` | legacy rows | CDN rows |
|---|---|---|---|---|
| `made_field_goal` | 1 | `Made Shot` | 59,447 | 30,449 |
| `missed_field_goal` | 2 | `Missed Shot` | 76,230 | 37,692 |
| `free_throw` | 3 | `Free Throw` | 36,354 | 18,717 |
| `rebound` | 4 | `Rebound` | 83,707 | 41,602 |
| `turnover` | 5 | `Turnover` | 28,484 | 13,599 |
| `foul` | 6 | `Foul` | 36,099 | 18,383 |
| `violation` | 7 | `Violation` | 1,174 | 712 |
| `substitution` | 8 | `Substitution` | 39,421 | 21,692 |
| `timeout` | 9 | `Timeout` | 9,819 | 4,971 |
| `jump_ball` | 10 | `Jump Ball` | 2,584 | 1,324 |
| `ejection` | 11 | `Ejection` | 24 | 14 |
| `period_start` | 12 | `period` + subType `start` | 4,032 | 2,022 |
| `period_end` | 13 | `period` + subType `end` | 4,032 | 2,022 |
| `replay_or_administrative` | 18 | `Instant Replay` | 1,970 | 1,303 |
| `steal` | — (attribution) | empty `actionType`, `STEAL` in description | 0 | 7,230 |
| `block` | — (attribution) | empty `actionType`, `BLOCK` in description | 0 | 4,021 |

**Zero unmapped rows.** `source_subtype_raw` is preserved on every row, so no source distinction is
lost. 11,251 rows are typed from description text (the CDN steal/block rows, which carry an empty
`actionType`); they are flagged `taxonomy_from_text` with `field_origin = parsed`.

## Information asymmetries — where the two schemas genuinely differ

These are recorded, not papered over. **A canonical null is preferred to an inferred value
presented as observed.**

| capability | legacy | CDN | canonical treatment |
|---|---|---|---|
| steals / blocks | **attributions** (`PLAYER2` on turnover, `PLAYER3` on missed shot) | **standalone rows** with empty `actionType` | both preserved as-is; `steal_block_form` records which. Neither is converted into the other. |
| assists | `PLAYER2` on made shot — observed | description text only | `assist_player_id` populated for legacy, NULL for CDN; `assist_supported` records it |
| substitution — player IN | `PLAYER2` — observed | **not structurally supplied**; text only | `sub_player_in_id` NULL for CDN; `substitution_in_supported = False` |
| shot coordinates | **none** | `xLegacy`/`yLegacy` | NULL for legacy; CDN coordinates kept only where `isFieldGoal == 1` |
| shot value | not structural | `shotValue` | NULL for legacy |
| score fields | not parsed in v1 | `scoreHome`/`scoreAway` | CDN only |
| free-throw outcome | **none** | `shotResult` is **empty on every free throw** | `shot_made` NULL on all free throws; `free_throw_result_supported = False` |

**Consequence:** steal, block and assist counts are **not directly comparable across the two
stores** in v1. Any channel using them must restrict to one store or first register an explicit
linkage rule.

## Coordinates

- 205,753 rows carry `coordinates_supported`; **68,141 rows carry actual shot coordinates**.
- `xLegacy`/`yLegacy` are populated on *every* CDN row, with `(0,0)` on non-shot events. In a
  40-game sample, **0 of 5,447 field-goal rows sit at (0,0)** while every sampled non-shot row does.
  `(0,0)` is therefore a null sentinel and is dropped to NULL on non-shot rows.
- No reorientation or re-origin is applied; the system is `nba_legacy_xy`.
- v1 does **not** backfill legacy coordinates from `data/shotcharts/`. That would break
  one-raw-source-per-row traceability. Registered as a possible later enrichment.
- Six 2026 games (2026-07-30/31) are absent from the shot-chart store but **do** carry coordinates
  in the CDN event stream, so the event artifact covers them.

## Known v1 gaps

1. **`rebound_type` is `unresolved` on all 125,309 rebound rows.** Offensive-versus-defensive type
   is not a structural field in either store — legacy uses action type 0 on 80,005 rebound rows and
   CDN uses subType `Unknown` on the large majority. The distinction survives only in description
   text (`REBOUND (Off:0 Def:1)`).
   The registered `team` branch never fires either, because both stores place a **team id** in the
   person field for a team rebound rather than a null. *Next step:* compare the person id against
   `master_team` ids to separate team rebounds, then register a derivation for off/def.
2. **Free-throw outcome unavailable** (see above). The scoring gate therefore tests a bound —
   `0 ≤ (final total − made-FG points) ≤ free-throw attempts` — which holds for **100% of CDN
   games**, rather than an equality that would require inventing outcomes.
3. **26 degraded rows** out of 589,130: 14 from the key fallback (7 of 996 legacy files carry one
   duplicate `EVENTNUM` each) and 12 flagged `score_out_of_sequence`.
4. **Score regressions are a source property, preserved and labelled.** Replay rows carry a
   post-correction score snapshot, and technical free throws at a period boundary are emitted
   before the `period_start` row that carries the pre-technical score. v1 preserves source order
   and flags the rows rather than reordering them.
5. **No possession linkage.** `player_possessions/2` remains canonical for realised possessions;
   this artifact is canonical for events. Structural comparison only — no contradictions found.

## Opportunity-denominator boundary

| status | quantities |
|---|---|
| **directly observed** | shot attempts, makes/misses (field goals), free-throw *attempts*, rebound events, turnovers and subtype, fouls and subtype, the player leaving the floor on a substitution, legacy steal/assist/block attributions, CDN standalone steal/block rows |
| **deterministically derivable** | elapsed time, period structure, score progression where score fields exist |
| **heuristically reconstructed — NOT done in v1** | CDN incoming substitute, offensive-vs-defensive rebound type, CDN assist attribution, linking a CDN steal/block row to its parent event, free-throw outcome |
| **not currently supportable** | potential assists, rebound chances in the tracking sense, touches, drives, defender proximity, blockable attempts, substitution intentions |

The contract supports later construction of defensible denominators. It does not pre-decide or
fabricate them.
