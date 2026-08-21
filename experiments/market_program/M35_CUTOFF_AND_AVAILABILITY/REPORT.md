# M35 — the cutoff, the availability wiring, and the capture

**E0-style diagnostic, NON-CLAIMING.** 701 player-game rows over 10 game dates. Ten dates is a
feasibility measurement, not evidence.

Three questions were authorised together. All three are answered, and the first **corrects
M34**.

---

## 1. Can the forecast cutoff move? Yes — and 28% of rows already did

The contract does not apply one cutoff policy. It applies two:

| policy | rows | cutoff |
|---|---|---|
| `date_only_prior_day_cutoff` | 32,243 (71.9%) | 18:00 UTC the day before |
| **`exact_tip_T-90m`** | **12,608 (28.1%)** | **90 minutes before tip, on game day** |

**This corrects M34.** Its finding that the injury tape is visible on 0.0% of rows is correct
for the date-only policy and wrong as a blanket statement — M34 could not reach the contract
(its outcome snapshot ends 2026-07-31, before the capture begins) and applied the documented
fallback to every row.

**What decides which policy a game gets is not permission — it is evidence.**
`resolve_tip_times` admits a tip only from an observation recorded strictly before that
observation's *own* reported tip minus 90 minutes: point-in-time, fail-closed. Its only sources
today are `odds_extension` (12,550 rows) and `props_historical` (58). Everything else falls
back, not because a later cutoff is disallowed, but because no qualifying tip observation
exists.

### The injury capture is itself a qualifying tip-time source

Each capture records `game_time_et` alongside `retrieval_ts_utc` — exactly the shape the rule
wants.

| | |
|---|---|
| matchup-dates in the tape | 31 |
| **with a qualifying tip observation** | **26 (83.9%)** |
| median lead of the first capture | **22.8 hours before tip** |

The captures arrive nearly a day ahead, clearing the 90-minute rule comfortably. **The tape does
not merely need a later cutoff — it supplies the evidence that would make one legal.**

## 2. Wire it into availability, not minutes — it works

Status visible under each policy, on the same 701 rows:

| cutoff | status visible |
|---|---|
| date_only (18:00 UTC day before) | **0.0%** |
| **exact_tip_T-90m** | **9.3%** |

Appearance by status at T-90m:

| status | n | appeared |
|---|---|---|
| **Out** | 33 | **6.1%** |
| Doubtful | 1 | 0.0% |
| Questionable | 11 | 63.6% |
| Probable | 17 | 94.1% |
| Available | 3 | 100.0% |
| *(not listed)* | 636 | 85.1% |

**Walk-forward Brier on appearance**, per-status rates fitted on strictly earlier game dates
only, scored on the 627 rows after the first date:

| | Brier |
|---|---|
| walk-forward base rate only | 0.15090 |
| **+ status at T-90m** | **0.12801** |
| | **+15.2%** |

A first pass used hand-chosen constants and returned +16.7%. Refitting walk-forward removes
that in-sample flattery and the finding survives at **+15.2%**.

For orientation, not comparison: E1_I0062 measured the shipped `p_active` as worth 17.8% on a
prop-shaped threshold question. Different baseline, different response — the two numbers must
not be added or ranked against each other.

## 3. Keep capturing — already running

| | |
|---|---|
| captures in the log | 903 |
| window | 2026-08-06 19:41 → 2026-08-21 17:57 UTC |
| captures in the last 48 hours | 192 |
| scheduled tasks | `WNBA_InjuryCapture`, `WNBA_InjuryLive` — both **Ready** |

Nothing was needed. The known risk is unchanged and is not a capture-configuration problem:
coverage depends on the machine being awake (D154), and the 08-10 → 08-14 blackout sits inside
this very window.

---

## What this adds up to

The route is now specific rather than aspirational:

1. **Admit injury captures as a tip-time observation source.** They already qualify for 83.9%
   of matchup-dates at a 22.8-hour median lead. That lifts games from date-only to T-90m.
2. **At T-90m the tape becomes legible**, and it is worth +15.2% on appearance Brier.
3. **Consume it in `p_active`, not in minutes.** M34 showed it does nothing for
   minutes-given-played, which is M33's actual market gap.

**It does not close the market gap.** M33's deficit is minutes among players who play, and
nothing here touches that.

## What this cannot establish

- **Ten game dates, 701 rows, `Out` at n=33.** Nothing generalises.
- **The 83.9% tip-observation figure is over matchup-dates the injury tape covers**, which are
  by construction game-days with reports. Whether it extends to the full schedule is untested.
- **Moving the cutoff is not free.** Every existing receipted figure was computed under the
  current policy mix; changing it changes what those numbers mean, and it would need a contract
  revision, not a patch.
- **The ET→UTC conversion is a fixed −4 offset**, correct for this August window and wrong in
  general.
- **This does not use the shipped arm** — the outcome snapshot and the capture do not overlap.
- **No wager-shaped claim.** S42 untouched; no fitted scoring model appears here.
