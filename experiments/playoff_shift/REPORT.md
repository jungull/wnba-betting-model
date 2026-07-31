# Playoff-shift analysis — what changes from regular season to playoffs

*Evidence produced by `run_playoff_shift.py` (agent, 2026-07-31T15:13Z); this report written by
the orchestrator from `run_summary.json` + the evidence CSVs after the agent's session ended.
Read-only reconnaissance — no registration, no model fitting. Every number below is a paired
same-team-same-season comparison (40 team-season pairs) unless stated.*

## 1. Rotations tighten — sharply and consistently

| quantity | regular season | playoffs | change | t |
|---|---|---|---|---|
| top-5 minutes share | 0.738 | 0.782 | **+4.3 pts** | 6.41 |
| top-7 minutes share | 0.907 | 0.934 | +2.7 pts | 5.24 |
| starter minutes (avg) | 28.70 | 30.29 | **+1.59 min** | 4.51 |
| max minutes (best player) | 34.32 | 36.19 | +1.87 min | 6.02 |
| players ≥ 35 min per team-game | 0.74 | 1.37 | **+0.63** | 5.57 |
| bench share | 0.282 | 0.243 | −4.0 pts | −4.51 |
| DNP-coach's-decision per game | 0.91 | 1.53 | +0.62 | 5.07 |
| players used | 9.41 | 9.27 | −0.14 (n.s.) | −1.27 |

Context: a starter plays 40+ minutes in **37.3% of playoff team-games vs 11.8% in the regular
season**; overtime rate **9.4% vs 4.0%**. The roster does not shrink — the *distribution* does:
the same ~9 players appear, but minutes concentrate at the top and the last bench slots convert
into healthy scratches.

## 2. Minutes remain predictable — IF playoff games feed the trend

| variant (playoff player-games, n=1,940) | MAE |
|---|---|
| shifted EWMA carrying regular-season **+ prior playoff** games | **4.83** |
| shifted EWMA frozen on regular-season history only | 5.89 |
| same-seasons regular-season reference | 4.79 |
| carry-forward baseline (playoffs) | 5.80 |

Carrying playoff games into the trend is worth **−1.06 MAE** (90% CI [−1.28, −0.84]) and closes
essentially the entire gap to regular-season accuracy (4.83 vs 4.79). **But the errors are
biased by role**: starters are **under-predicted by 1.27 minutes**, bench players
**over-predicted by 1.57** — exactly the rotation tightening above, unmodelled.

## 3. The playoff whistle is the structural shift — free throws collapse

| channel (per team-game) | RS | PO | change | t |
|---|---|---|---|---|
| **FT points** | 14.53 | 11.94 | **−17.9%** | −6.15 |
| FT attempts | 18.08 | 15.26 | −15.6% | −6.32 |
| FT rate (FTA/FGA) | 0.269 | 0.223 | **−17.3%** | −6.79 |
| 3pt points | 24.56 | 23.56 | −4.1% (n.s.) | −1.22 |
| paint points | 35.52 | 35.16 | −1.0% (n.s.) | −0.45 |
| non-paint 2s | 8.75 | 8.70 | −0.6% (n.s.) | −0.12 |
| total points | 83.36 | 79.36 | −4.8% | −4.26 |
| possessions | 81.86 | 81.38 | −0.6% (n.s.) | −0.89 |

Per-100-possession figures move identically, so this is **not a pace effect** — it is officiating.
Fouls called barely change (−3.4%, n.s.) while free-throw *attempts* fall 15.6%: the whistle moves
on shooting fouls specifically. Shot mix shifts modestly toward the paint (+3.7% share) and away
from threes (−5.2% share). **Scoring falls ~4 points per team almost entirely through the FT
channel.**

## 4. Our margin model looks better in playoffs — but so does everything else

Playoff margin MAE **8.87** (n=46) vs **10.15** on regular-season games of the same seasons
(90% CI on the difference [−2.91, +0.51] — not significant at this sample). The naive baseline
improves too (9.26 vs 11.68), so the model's *edge over naive* actually **shrinks**: +0.39 in
playoffs vs +1.53 in the regular season. Playoff games are simply more predictable (better teams,
tighter rotations, less variance) — our model is not adding more; it is riding an easier sample.

## 5. The market question: our gap vs the books WIDENS in playoffs

| sample | model MAE | bookie MAE | **gap** |
|---|---|---|---|
| playoffs 2024–2025 (n=46) | 8.87 | 8.05 | **+0.81** |
| regular season 2024–2025 (n=458) | 10.16 | 9.73 | **+0.43** |

Books sharpen more than we do (their playoff MAE 8.71 across 2023–2025, n=66, vs 9.53 in the
regular season). **Our disadvantage roughly doubles in the playoffs.** This is the decisive
finding for betting policy: whatever edge exists in the regular season should not be assumed to
carry into October.

## 6. Series familiarity: no measurable carryover

Across 42 series-team pairs reaching game 3, channel errors in later series games vs earlier
show no significant improvement (all |t| < 1.4; 3pt −0.84 pts, paint +1.17 pts, both n.s.).
Repeated exposure to the same opponent does **not** make our forecasts better — the
opponent-specific information the model would need is not being learned within a series.

---

## Playoff-mode spec recommendation (for registration before September)

1. **FT channel needs an explicit playoff regime.** A −17% free-throw-rate shift is far larger
   than any feature effect in the entire feature lab. Proposal: a playoff FT multiplier estimated
   from prior postseasons only (2021–2024 available; 2025 as validation), applied to the FT chain
   for postseason games. The other three channels need no playoff treatment — their shifts are
   within noise.
2. **Minutes: extend the availability system to playoffs, with a role-aware correction.** The
   trend machinery already works (4.83 vs 4.79 RS) provided playoff games enter the EWMA — that
   is a one-line universe change from the current regular-season-only rule. Add a preregistered
   starter/bench playoff adjustment (+1.3/−1.6 minutes as measured, shrunk) to remove the
   documented role bias, and widen the minutes prior for the 9.4% overtime rate.
3. **Betting policy: treat playoffs as out-of-sample until proven otherwise.** The market gap
   doubles (0.43 → 0.81) while our edge over naive shrinks. The live paper-trade cells should
   record playoff games under a separate label from day one, and no pocket confirmed on
   regular-season games may be assumed to transfer.

## Files

`run_playoff_shift.py`, `run_summary.json`, `rotation_{summary,paired,teamgame}.csv`,
`minutes_{mae_summary,playoff_rows}.csv`, `channel_{summary,paired,teamgame}.csv`,
`margin_test_split.csv`, `market_summary.csv`, `bookie_game_rows.csv`,
`series_{summary,paired,game_rows}.csv`
