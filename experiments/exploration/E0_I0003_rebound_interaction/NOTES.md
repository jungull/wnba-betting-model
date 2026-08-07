# E0 I0003 -- rebound OPPORTUNITY x SECURE RATE, interacted with opponent context

Tier: E0 exploration. Non-claiming. Not a result. Partition: seasons 2021-2024 only
(`EXPLORATION_PARTITION/1`). 2025/2026 were never read -- `possessions.parquet` was
filtered on `season` to `{2021,2022,2023,2024}` as the very first line of processing,
before any other derivation touched it, and every downstream table inherits that filter.

## 1. Can opportunity be built as distinct from secured rebounds?

Yes, from data that already exists in this repo -- no new capture needed.

- `data/possessions/possessions.parquet` already carries the 10 on-court players
  (`off_p1..5`, `def_p1..5`) for every possession segment, 2021-2024: 155,149 rows,
  970 games.
- `data/playbyplay/pbp_*.parquet` carries individually-credited rebound events
  (`EVENTMSGTYPE==4`, `PERSON1TYPE` in {4,5}) with the description literally encoding
  `REBOUND (Off:X Def:Y)` -- offensive vs defensive is a direct parse, not inferred.
- Matching a rebound event's (period, clock time) to the possession row whose
  `[start_sec, end_sec]` window contains it gives the 10-player opportunity set for
  that event: +1 ORB opportunity to the 5 offense players, +1 DRB opportunity to the
  5 defense players, and +1 "secured" to whichever specific player the event credits.

Built this over 888 games (of 970 in-partition; 82 had no matching pbp file on disk --
not investigated further, time-boxed) -> 61,135 individually-credited rebound events,
covering 633 player-seasons.

**Caveat, measured not assumed:** clock-string-derived elapsed time and the
possession-builder's second boundaries disagree by a second or two often enough that
row-matching is noisy at the edges. Diagnostic: the credited rebounder was found
*somewhere* among the 10 on-court players in 99.4% of events, but on the *correct*
side (matching the Off/Def flag) in only ~72% overall -- **84% for defensive
rebounds, only ~43% for offensive rebounds**. Offensive-rebound events happen
mid-possession where nearby events can share a clock second, which appears to be
the main source of the extra noise; defensive rebounds sit cleanly on a possession
boundary and matched much better. **Treat every ORB number below as materially
noisier than the DRB numbers.** This is a fixable engineering problem (e.g. deriving
on-court lineups directly from substitution-event order rather than clock-time
join), not a fundamental data-availability gap -- but fixing it was out of the E0
time-box.

## 2. Does the decomposition look more stable across time than a single rate?

Year-over-year Pearson r, consecutive in-partition seasons, players with >=300
minutes in both seasons (n=242 player-season pairs):

| quantity | r | note |
|---|---|---|
| naive fused REB/min (real box score) | **0.917** | the thing we're trying to beat |
| DRB secure rate (secured/DRB opportunity) | 0.769 | cleaner-matched side |
| DRB opportunity rate (opportunities/min) | 0.275 | |
| ORB secure rate (secured/ORB opportunity) | 0.786 | noisier-matched side, caution |
| ORB opportunity rate (opportunities/min) | 0.419 | |

Restricting to a higher-volume subsample (DRB opportunities >=300 in both seasons,
n=219) doesn't change the picture: DRB secure rate r=0.781 vs naive REB/min r=0.922
on the same players.

**Reading:** the single fused box rate was *more* year-over-year stable than either
decomposed half, not less. This is the opposite of what the T1 worked example
implicitly expects ("a rate that fuses them hides which half moved" suggests the
components should be at least as informative). The secure-rate components did show
real persistence (0.77-0.79, not nothing), which is worth keeping in mind -- a
noisy-but-real signal survived construction noise that should have been attenuating
it toward zero. But the opportunity-rate components were weak (0.28-0.42), and given
the row-matching noise documented in §1 also touches the opportunity denominator
(a mismatched row assigns the wrong 5 players, not just the wrong individual
credit), I can't rule out that the low opportunity-rate stability is partly a
measurement artifact rather than a real property. Did not have time to separate
those two explanations.

## 3. Does secure rate interact with opponent context?

Tested one of the three suggested axes (opponent shot profile), given the time-box.
Proxy: team-season FG3A/FGA rate, median-split into "high-3PT opponent" vs
"low-3PT opponent" per season (305,675 DRB-opportunity events with a resolved
opponent).

| bucket | pooled DRB secure rate | player-demeaned residual* |
|---|---|---|
| low-3PT opponent | 0.1159 | -0.0020 |
| high-3PT opponent | 0.1193 | +0.0020 |

*residual = event outcome minus that player-season's own average secure rate,
averaged within bucket -- a crude within-player check for whether the opponent
context moves a player off their own baseline.

**Reading:** essentially null. A ~0.3pp pooled gap and a ~0.4pp player-demeaned gap
on an ~11-12% base rate, with ~150K events per bucket (so this isn't underpowered
in the pooled sense) -- there is no visible effect of this specific, crude
opponent-shot-profile proxy on defensive rebound secure rate. Did not reach the
other two suggested axes (lineup size, opponent rebounding strength) inside the
time-box.

## 4. Bottom line

- The construction is feasible from existing repo data and doesn't need new
  capture -- that part of I0003 is a real "yes."
- The two things that would justify iterating did not show up in this pass: the
  decomposition was not more stable than the fused rate (it was less stable,
  though possibly noise-confounded on the opportunity side), and the one interaction
  proxy tested came back null.
- The row-matching precision issue is real and would need real engineering time
  (deriving lineups from substitution-event order rather than clock-time join) to
  trust the ORB numbers or to cleanly separate "opportunity is genuinely less
  stable" from "opportunity is measured noisily." That fix is out of scope for a
  cheap re-test and is why this isn't a request to simply "rerun it."

## Scripts

- `build_events.py` -- partition-filters possessions.parquet, scans 2021-2024 pbp
  files for individually-credited rebound events, nearest-interval-matches each to
  its on-court lineup, writes `events.pkl`.
- `aggregate_and_test.py` -- aggregates `events.pkl` to player-season opportunity/
  secure counts (`player_season.csv`), runs the year-over-year stability comparison
  (`stability_pairs.csv`), and the opponent-3PT-rate interaction probe.
