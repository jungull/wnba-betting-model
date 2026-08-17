# How the forecast universe is built, and why a player stays on a club she has left

**E1_I0045_roster_currency.** Partition 2021–2024. 2025 and 2026 were never opened.
**No change was enacted. Every model change is the user's decision.**

Everything below is read out of `prediction_contract_v5.py` and re-executed over the
manifest-verified `data/masters/master_player.parquet`. Nothing here is inferred from behaviour.
The re-execution is checkable: my reconstruction of the tier-A rule reproduces the
manifest-verified contract-v4 membership on **20,084 of 20,084 rows, exactly**.

---

## 1. The one-paragraph version

Before each game the model needs a list of players who might play for a team. There is **no roster
feed anywhere in this repository** — the contract says so itself, and a dedicated audit
(`experiments/player_program/audit_roster_sources.py`) checked every candidate source and found
none that can be reconstructed as of a historical cutoff. So the list is assembled from box
scores. The main rule is sound: *whoever appeared in this club's box score in its last five games*.
But that rule produces nothing at all for a team's first five games of a season, so a second rule
is bolted on for exactly that window: **anyone who ever played for this club, in any prior season,
ever.** That second rule has no expiry, no departure check and no release check. It is why Liz
Cambage is on Las Vegas's opening-night list a year after she left, and it is the whole mechanism.

---

## 2. The four sources, as registered

`prediction_contract_v5.py:112-128` declares them. The constants are read out of the source by AST
in `scripts/s02_universe.py`, not transcribed.

| id | tier | what it is | constant |
|---|---|---|---|
| **S1** | A | box membership (**DNP rows included**) in the club's latest ≤5 *admitted* prior same-season games | `ROSTER_LOOKBACK = 5` |
| **S3** | A | a captured pregame availability report naming her for that club | `REPORT_ERA_START = 2026-07-30` |
| **S_TX** | B | a transaction-wire acquisition, effective-dated, within 3 team games | `S_TX_HORIZON = 3` |
| **S2** | B | **prior-season franchise affiliation** | `S2_HORIZON = 5` |
| S4 | A | "official roster/transaction feed with provable publication times" | **`available: False`** |

Two of those five lines decide everything.

**S3 cannot fire in this partition.** Its era begins 2026-07-30; the latest forecast cutoff in
2021–2024 is 2024-09-18. Asserted in `s02_universe.py`, not assumed. So for the whole of
2021–2024, **Tier A is S1 and nothing else** — the only way to be a verified candidate for a club
is to have already appeared in that club's box score.

**S4 is declared and declared unavailable.** The contract names the source it would need and
records that it does not exist, so that a later implementation cannot quietly substitute something
weaker. That is good practice and it is also the finding: **there is no roster snapshot.**

---

## 3. The mechanism, in the four lines that cause it

`prediction_contract_v5.py:449-459`:

```python
            # ---- S2 : Tier B, weak, early-season only ------------------------
            if gidx < s2_horizon:
                for (t2, pid), seasons_seen in s2_all.items():
                    if t2 != team_id:
                        continue
                    if any(s < season for s in seasons_seen):
```

Read `any(s < season for s in seasons_seen)`. The set `seasons_seen` is *every season in which
that player appeared in that club's box score*, built once over the whole partition
(`s2_seasons`, `:281-286`). The test is satisfied by **any** prior season. There is no comparison
against `season - 1`, no date arithmetic, no bound of any kind. A player who last wore a club's
uniform in 2021 satisfies this test for that club in 2022, 2023, 2024 and every season after,
for the first five games of each.

Three things this rule never asks:

1. **Has she played for anybody else since?** Nothing in the S2 branch looks at other clubs.
2. **Has she been released?** The transaction wire's `RELEASE` categories are read
   (`:432`) but only inside the **S_TX** branch, to cancel an S_TX acquisition. A release is never
   applied to an S2 row.
3. **How long ago was it?** The evidence time S2 stamps on the row is
   `pd.Timestamp(f"{season}-01-01T00:00:00Z")` (`:459`) — the season boundary, not the last
   appearance. The contract labels this honestly ("the last admitted game of the prior season is
   not tracked per row, so the season boundary is used and labelled as such"), but the effect is
   that the row carries no recency information at all.

**The contract is not hiding this.** Its own docstring says prior-season affiliation "is not proof
of current roster membership: a prior-season player may have been traded, waived, left unsigned,
retired, suspended or replaced before opening night", and it labels every such row
`team_assignment_confidence = "weak"`. It does its job. **The availability arm then reads the rows
and ignores the label** — E1_I0035 established that nothing in the emission path looks at
`universe_tier` at all.

---

## 4. What that produces, measured

RS1P: 20,084 champion rows on 1,392 team-games, 2022–2024 regular season. Tier is contract-v4
membership (the manifest-verified definition E1_I0035 used).

**Where the tier-B rows come from** (`tier_b_by_admitting_source.csv`):

| admitted by | rows | share of tier B | mean `p_active` | realised appearance rate | surplus players / team-game |
|---|---:|---:|---:|---:|---:|
| **S2, prior-season affiliation** | **3,266** | **86.6 %** | 0.514 | **0.0609** | **+1.064** |
| neither S1 nor S2 (⇒ S_TX only) | 506 | 13.4 % | 0.593 | 0.364 | +0.083 |

**98.5 % of tier-B rows sit at team-game index 0–4** — S2's five-game window. This is not a
season-long leak; it is a season-opening one, concentrated and structural.

**How stale the S2 rows are** (`S2_rows_by_seasons_since_club.csv`) — seasons since her last
*admitted appearance* for this club:

| seasons since | rows | mean `p_active` | realised appearance rate |
|---:|---:|---:|---:|
| 1 | 1,765 | 0.536 | **0.1088** |
| 2 | 991 | 0.486 | **0.0030** |
| 3 | 432 | 0.491 | **0.0023** |
| never appeared for this club | 78 | 0.522 | 0.0385 |

**The departure signal** — has she played for *somebody else* since she last played for you?

| | rows | mean `p_active` | realised appearance rate |
|---|---:|---:|---:|
| S2 rows, not departed | 1,777 | 0.569 | 0.1103 |
| **S2 rows, departed** | **1,489** | **0.449** | **0.0020** |

Three appearances in 1,489 rows. The model says 45 %.

This is a cleaner separation than E1_I0035's 7-day-elsewhere probe (which found 0.0068) because it
does not depend on a window: *any* subsequent appearance for another club, at any distance, is the
signal. It is also strictly pre-cutoff, because it is built only from box scores admitted through
the contract's own +36 h availability bound.

**Tier A is different and should be left alone.** 248 tier-A rows also carry the departure signal —
mid-season trades, where the old club's five-game lookback still names her. Their realised
appearance rate is **0.145**, not 0.002, and the arm already prices them at a mean `p_active` of
**0.212**. The fitted model handles these; a currency rule that deletes them is doing harm. That is
measured in `CURRENCY_RULE.md` as the R4 arm, and it is why every rule that carries a verdict here
is scoped to S2 rows only.

---

## 5. What sources exist, and why none of them is a roster

`audit_roster_sources.py` asked six questions of every source in the repository. Its verdicts, and
my check of the manifest status that governs whether a source may back a number:

| source | present | manifest | verdict |
|---|---|---|---|
| prior box membership (S1) | yes | **yes** (`master_player.parquet.manifest.json`, `asof_granularity: row`) | Tier A, and the only one |
| `data/injury_history/injury_history.csv` (the transaction wire) | yes | **NO MANIFEST** | Regime B; effective dates real, **observation time is one retrospective scrape (2026-07-30 17:42 Z) for all 8,340 rows** |
| `data/injury_capture/injury_log.csv` (pregame reports) | yes | — | Tier A, **2026-07-30 onward only** — nothing in this partition |
| `data/w1_truth/roster_asof.csv` | yes | `asof_granularity: artifact` | **unusable** — it is *derived from box scores*; its `first_game_date` is the information that arrives too late |
| `data/reference/player_bios.csv` | yes | none | **unusable** — no team column at all |
| official WNBA transaction log / archived roster endpoints | **no** | — | not present; a live roster endpoint returns the *current* roster, which is a retrospective baseline |

**Consequence for this screen.** The transaction wire is the strongest affiliation evidence in the
repository and it is still not usable for a rule that carries a verdict, for two independent
reasons: it has no manifest (UNVERIFIABLE ⇒ may not back a number), and its observation time is not
provably pre-cutoff for any 2021–2024 row. **Every rule measured here is built from
`master_player` alone.** The wire appears in this screen exactly once, as labelled colour in
`s02_universe.py` §5, and no conclusion rests on it.

That constraint is not a limitation of the measurement — it is the finding. **A roster-currency
repair in this partition can only be built out of who has played, for whom, and when.** Fortunately
that turns out to be enough: the departure signal separates a 0.002 appearance rate from a 0.110
one using nothing else.

---

## 6. The thing nobody had noticed: the same defect exists in the shipped code, independently

`daily_forecast.py` — which is on the scheduler as `WNBA_DailyForecast_AM/_PM` — does **not** read
the contract universe. It builds its own list (`daily_forecast.py:647-665`):

```python
        recent = set(tgames[-RECENCY_GAMES:])
        roster = tp[tp.game_id.isin(recent)].player_name.unique()
```

with `RECENCY_GAMES = 3`. That is S1 with a three-game window instead of five, keyed on
**`player_name` rather than `player_id`**, and with no departure check either. A player traded
yesterday stays on her old club's shipped roster for three games.

So the roster-currency defect exists in two places, in two independent code paths, and **fixing the
contract would not touch the shipped one.** That is reported in `REACH.md` and it is the single
most useful thing this screen found for anyone deciding what to do next.
