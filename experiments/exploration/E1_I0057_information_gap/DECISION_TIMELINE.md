# DECISION_TIMELINE — when the information actually lands, and where the program's cutoff sits

E1_I0057, 2026-08-17. Evidence level **E0/E1 — audit, not a screen.** Nothing here is a measured
effect and nothing here licenses a claim that any of it predicts anything.

Every figure was computed from bytes by the scripts named. All timestamps UTC.

---

## 1. The one-line answer

The program's features are as-of **the end of the player's previous game — a median 3.0 days
(72 hours) before tip**. The official injury designation that decides whether that player is
available lands a **median 1.0 hour before tip**, and every observed *change* of designation
landed inside **T-3h, median 30 minutes before tip**.

**The gap is roughly 71 hours.** It is not a gap in what the program can obtain — it is a gap in
what the program has ever looked at.

---

## 2. The program's own cutoff, read from the construction

`features/common.py` is explicit and disciplined about it (`features/common.py:10-11`):

> converted to an as-of value via `groupby(player_id, season).shift(1)`
> (played-frame rows: `shift(1)` == value entering this game)

Every family in `features/` is built from `.shift(1)`, `.expanding().mean().shift(1)`,
`.cumsum().shift(1)` or `ewm(...).shift(1)` over prior **games**. `league_asof_by_date` and
`league_asof_std_by_date` shift by prior **dates**. There is no code path anywhere in `features/`
that admits a same-day observation. `asof_invariant.py` polices the same rule for fitted artifacts
("EVERY fitted artifact feeding that row must prove that its latest source observation STRICTLY
predates that row's forecast timestamp").

This is a correct and well-enforced rule. It is also strictly stronger than the rule a bettor
faces, and that is the finding. The invariant forbids the *future*; the feature library
additionally forbids **today**, and nothing forced it to.

### Staleness of that cutoff, measured
`scripts/s03_regime_and_staleness.py`, on 27,283 played rows with a prior same-season game:

| statistic | days between the player's previous game and this one |
|---|---|
| mean | 3.66 |
| median | **3.0** |
| p25 / p75 | 2 / 4 |
| p90 | 6 |
| max | 93 |
| share ≥3 days | **50.9%** |
| share ≥5 days | 16.2% |
| share ≥7 days | 7.3% |

A further **1,039 rows** are a player's first appearance of a season and carry no prior state at all.

---

## 3. When the official injury designation actually lands

Source: `data/injury_capture/injury_log.csv` (2,401 rows, 157 captures, 2026-07-30 → 2026-08-17),
joined to real per-team tip times taken from `commence_time` in
`data/odds_capture/capture_log.csv` (98.0% of injury rows matched a real tip).
Script: `scripts/s12_lead_v3.py`. Restricted to captures **strictly before tip** — 1,491 of 2,315
rows (64.4%); the hourly capture keeps running after tip and those rows are excluded.

**169 player-gamedate designation series over 14 game days.**

| | hours before that team's tip |
|---|---|
| **First** appearance on the report — median | 19.5 (p10 0.50, p90 26.0) |
| share of first appearances inside T-24h | 65.1% |
| share inside T-12h | 39.1% |
| share inside T-6h | 29.0% |
| **Last pre-tip designation** — median | **1.00** (p10 0.10, p90 13.5) |
| share of last designations inside T-12h | 88.8% |
| share inside T-6h | 86.4% |
| share inside T-1h | **82.2%** |

Final pre-tip status: Out 123, Available 28, Questionable 13, Probable 5.

### The part a professional is waiting for

**38 of the 169 series (22.5%) changed designation before tip. 100% of those resolutions landed
inside T-3h; the median resolution landed 0.50 h — 30 minutes — before tip.**

| pre-tip resolution | n |
|---|---|
| Probable → Available | 16 |
| Questionable → Available | 11 |
| Questionable → Out | 7 |
| Doubtful → Out | 2 |
| Out → Available | 1 |
| Probable → Out | 1 |

Ten of these are a player going from "maybe" to **not playing**, and 28 from "maybe" to **playing** —
all inside the last three hours, none of it visible to a feature set cut at the previous game.

### Independent confirmation from the higher-provenance feed
`data/injury_official_live/injury_snapshots.csv` (6,178 rows, PT15M polling of the league's
quarter-hour PDF grid, 2026-08-07 → 2026-08-17). `scripts/s01_injury_timeline.py` measures the
publication lead of the report carrying each status, against a crude 19:00-ET tip proxy:

| status | n | p10 | median | p90 |
|---|---|---|---|---|
| Out | 3,996 | −4.75 h | 3.50 h | 18.50 h |
| Questionable | 1,041 | 3.75 h | 13.00 h | 21.75 h |
| Probable | 692 | 2.75 h | 12.25 h | 21.75 h |
| Available | 429 | −5.50 h | −1.75 h | 0.75 h |

`Available` is published a median 1.75 hours **after** the proxy tip, which is the same fact from
the other side: availability is confirmed at the last moment.

---

## 4. What the report does and does not cover

`scripts/s09_resolution.py`, over the 9 game days (2026-07-30 → 2026-08-07) where the designation
capture overlaps observed outcomes in `master_player.parquet` — **636 player-game rows, 130 of them
DNPs**:

- **47 of 130 DNPs (36.2%) were designated `Out` on the report before tip.**
- **83 of 130 (63.8%) carried no designation. All 83 are Coach's Decision** (82 `DNP - Coach's
  Decision`, 1 `DND - Coach's Decision`).
- Of the 47 designated rows, the realised reasons were `DND - Injury/Illness` 25, `DND - Coach's
  Decision` 8, `NWT - Personal` 5, `NWT - Not With Team` 3, `NWT_CONCUSSION_PROTOCOL` 3, other 3.
- **47 of 47 rows designated `Out` before tip did not play. 25 of 25 designated `Available` played.**

That last line is a **coverage-and-reliability statistic, not a predictive result.** It is close to
definitional — the league enforces the designation — and the sample is nine game days. It says the
feed is clean and joinable. It does not say a model would gain from it, and this audit did not test
that.

The honest decomposition: the official report handles the **injury** channel of unavailability
essentially completely and the **coach's-decision** channel not at all. Any use of it is a partial
solution to availability, not a whole one.

---

## 5. When the market moves

`scripts/s02_odds_timeline.py`, on `data/odds_capture/capture_log.csv` (44,658 rows, 153 hourly
snapshots, 11 books, 2026-07-30 → 2026-08-17). Consensus game total across books; 44 games have ≥3
pre-tip snapshots.

Movement first-observation → close: median **1.28** points, p90 2.60, max 4.66.

Mean absolute distance from the eventual closing consensus total, by time to tip:

| time to tip | n snapshot-games | mean \|residual to close\| | p90 |
|---|---|---|---|
| >24 h | 311 | 1.395 pts | 2.66 |
| 12–24 h | 177 | 1.026 | 2.27 |
| 6–12 h | 96 | 0.555 | 1.18 |
| 3–6 h | 71 | 0.539 | 1.00 |
| 1–3 h | 63 | 0.223 | 0.50 |
| <1 h | 28 | 0.000 | 0.00 |

Roughly **60% of the market's total movement is still ahead of it at T-24h, and ~40% at T-12h** —
the same window in which the designations resolve. The market is being told something in the final
half-day, and the program's feature cutoff sits three days earlier.

An independently-recorded corroboration already in the repository, from
`experiments/player_program/ops_lane/O11_OBLIGATION_DISCOVERY_LEAD_WINDOW/DISCOVERY_LAG.json`
(84 obligations, 21 games): **49 of 84 obligations were NOT discoverable before their cutoff**, and
at a T-24h label **0 of 21** were.

---

## 6. Rows affected

| population | size | note |
|---|---|---|
| played rows whose feature state is ≥3 days stale | **50.9%** of 27,283 | scripts/s03 |
| played rows whose feature state is ≥5 days stale | 16.2% | scripts/s03 |
| rows with no prior state at all | 1,039 | first appearance of a season |
| 2026 master rows that are DNP/inactive | **17.78%** (921 of 5,179) | scripts/s05 |
| DNPs in the overlap window pre-announced on the report | 36.2% (47 of 130) | scripts/s09 |
| designation series resolving inside T-3h | 22.5% (38 of 169) | scripts/s12 |

---

## 7. What I could NOT determine

- **Whether closing any part of this gap improves any forecast.** Not tested. This is an audit.
- **Anything about seasons before 2026.** Every point-in-time designation and odds capture in this
  repository starts 2026-07-30 or later. The historical decision timeline is unmeasured and, from
  these sources, unmeasurable.
- **Real tip times for the injury window from `tip_times.csv`** — it stops before 2026-07-30, so
  §3 uses `commence_time` from the odds tape instead. That is a vendor-asserted scheduled start,
  not a witnessed tip.
- **Whether the hourly `injury_capture` cadence misses intra-hour changes.** It certainly can; the
  PT15M `injury_official_live` feed exists precisely to fix that but only starts 2026-08-07.
- **Any latency between a designation changing at the league and the capture seeing it.** The
  `injury_snapshots.csv` vendor note is explicit that no vendor SLA exists and the 15-minute grid is
  observed, not guaranteed — "treat as UNBOUNDED for anything sharper than the 15-minute grid".
