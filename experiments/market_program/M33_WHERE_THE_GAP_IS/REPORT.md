# M33 — where the model-vs-market gap actually is

**E0-style diagnostic, NON-CLAIMING.** The oracle arms cheat by construction; they are a
measuring instrument for locating the deficit, not forecasts. 5,889 matched player-games that
were actually played, seasons 2024–2026, 260 game dates. Cluster bootstrap by game date.

---

## The answer in one line

**It is minutes, not scoring. Our rate model given correct minutes already beats the market;
our minutes forecast is what loses to it.**

| forecast | points MAE | 95% CI |
|---|---|---|
| **MARKET** (implied mean from the line) | **4.9168** | [4.816, 5.011] |
| **OUR MODEL** as shipped | **5.2261** | [5.113, 5.347] |
| ours **+ oracle minutes**, our own rate model | **4.5907** | [4.493, 4.692] |
| ours + oracle rate, our own minutes | 1.8888 | [1.812, 1.968] |

The gap is **+0.3093 points of MAE**. Hand the model the realised minutes and keep its existing
rate model, and it lands at **4.5907 — 0.326 ahead of the market.**

So the scoring-rate model is not the problem. **Minutes uncertainty costs us more than the
entire deficit.**

## How much better do minutes have to get?

Shrinking our minutes error toward the truth by a factor, keeping the rate model untouched:

| shrink | minutes MAE | points MAE | vs market |
|---|---|---|---|
| 1.0 (as shipped) | 4.2070 | 5.2261 | +0.3093 |
| 0.8 | 3.3656 | 5.0471 | +0.1303 |
| 0.7 | 2.9449 | 4.9647 | +0.0479 |
| **0.6** | **2.5242** | **4.8895** | **−0.0273 ← parity** |
| 0.4 | 1.6828 | 4.7589 | −0.1579 |
| 0.0 (oracle) | 0.0000 | 4.5907 | −0.3261 |

**To match the market, minutes MAE must fall from 4.21 to about 2.52 — a 40% reduction.**

## That will not come from modelling, and the record says so

- The whole reference ladder moved minutes MAE from **5.272** (player average) to **4.860**
  (tuned EWMA) — about **8%**, and the richer blend was no better at 4.870.
- E1_I0053 tested eight context candidates on minutes: **seven were null**, and the eighth was a
  return-from-absence effect on 3.8% of rows. Tuning the estimator beat every candidate by
  2.5–7.6×.
- E1_I0061 found per-row scale modelling of minutes uncertainty is **negative**, twice.

**40% is roughly five times everything the modelling programme has ever achieved on minutes.**
Another feature sweep will not produce it.

## What the market has that we do not

Our minutes MAE is 4.21 against an actual spread of 6.43 — we explain roughly a third of the
variation. The market prices the same players better, and the plausible reason is not a better
estimator. It is knowing **who is playing tonight and in what role**: injury designations,
late scratches, minute restrictions, rotation changes, rest.

**The production arm has never read an injury report.** Its registered feature sources are
`src_asof_gamelog`, `src_asof_roster`, `src_asof_schedule`. The string "injury" does not appear
in the runner or its core modules — zero occurrences in `cbs_player_runner_v14.py`, `cbs_v7.py`,
`cbs_v8.py`.

Meanwhile `data/injury_official_live` holds **841 files, 86.2 MB** — official league
quarter-hour injury reports, `injury_snapshots.csv`, `status_transitions.csv`, and the captured
source PDFs. It is being collected and is not wired into anything that forecasts.

That is the single largest identified gap, and it is an **information** gap rather than a
modelling one.

## Where the loss is concentrated

By how much the player actually played:

| played | n | market MAE | ours | ours − market |
|---|---|---|---|---|
| <12 min | 102 | 7.2895 | 7.2629 | **−0.0266** |
| 12–20 | 499 | 5.1585 | 5.3828 | +0.2242 |
| 20–28 | 1,812 | 4.4620 | 4.7810 | +0.3190 |
| 28+ | 3,472 | 5.0444 | 5.3711 | +0.3266 |

We are **level with the market on players who barely played** and lose most on rotation regulars
— which is where minutes are largest and a minutes error is most expensive in points.

## What this does NOT establish

- **The oracle arms cheat.** They locate our deficit; they are not achievable and not forecasts.
- **This does not show our rate model beats the market's rate model.** The market carries its own
  minutes uncertainty inside its 4.9168. What it shows is that minutes uncertainty costs *us*
  more than the whole gap.
- **The minutes-played table conditions on a realised quantity** and is descriptive only.
- **Wiring injuries in is not free and is not authorised here.** It would add a registered
  feature source to a byte-locked arm, and every row would need point-in-time discipline — an
  injury file that reflects current status rather than status at the forecast cutoff is a leak,
  and this programme has already been bitten by exactly that class (D138, the `last_update`
  re-stamping in D151).
- **No wager-shaped claim.** S42 untouched; SHADOW unchanged.
