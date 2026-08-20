# E1_I0060 — defects, recorded not repaired

`PREREG.md` is frozen at `d53637d0fbe9971e2051316003af05cbc9dff64c58f318a8ff9d21194e4e1b7c`
and is not edited.

---

## DEFECT 1 — the coordinator's own motivating claim failed its own test

The screen exists because the coordinator told the user that matchup effects were being
diluted by measuring on points, citing **2.4×** from the programme's record (D099's
ΔR² 0.0113 on ppm against 0.0046 on points). P2 preregistered a threshold of 1.5× and
**the measured ratio is 1.21.**

The 2.4× figure was real but was quoted across incomparable settings: D099's pair came from
a *decision stratum* row set with a different base, and the ratio does not survive being
recomputed on one common frame with one common base. **This is the same error the reference
ladder screen recorded as the programme's larger defect — quantities that are not
commensurable being ordered anyway — committed again, by the coordinator, three messages
after summarising that finding.**

The recommendation to measure on rate survives, because a 1.21 ratio is still a real gain and
the negative control is clean. The reasoning offered for it did not.

## DEFECT 2 — the preregistered design over-counts channels, and did so here

Each channel was preregistered as an increment over a common base. `C3a` is **built from**
`C1` (it is `prior_usage × C1_opp_def`), so that design cannot distinguish an interaction
from the main effect it contains. Worse, `C3c_fta_x_oppfta` **cleared the family-wise
correction at p_fwe = 0.0490** and then contributed **−0.000169** once `C1` and `C3a` were in
the base — it was carrying shared variance, not its own.

Had the post-hoc stack not been run, this screen would have reported **three surviving
channels**. There is one. The nested increment should have been preregistered; it was not,
and the correction is labelled post-hoc in REPORT.md rather than folded silently into the
headline.

## DEFECT 3 — the injection calibration does not produce the nominal effect size

The detection floor was established by injecting effects of nominal ΔR² ∈ {0.001, 0.003,
0.010}. Recovered values were **+0.006890, +0.011298, +0.022766** — over-recovering by 6.9×,
3.8× and 2.3×. The injection adds an amplitude to the response and therefore moves SST as
well, so the nominal-to-realised mapping is wrong.

**What survives:** the smallest injection tried was recovered far above the permutation 95th
percentile (+0.000420), so the floor is **at most** 0.001, and `C2`/`C3b` are below it either
way. The floor is a valid upper bound and is used only as one. It is **not** the calibrated
figure the preregistration described, and no finer statement should be read from it.

## DEFECT 4 — one season is unscored and the walk-forward is short

2021 has no prior season and is never scored, leaving three scored seasons and 11,279 of
14,259 complete rows. Every coefficient in the earliest scored season is fitted on a single
prior season. Nothing here describes 2021.

## DEFECT 5 — the zone channel is closed only in the form built here

`C2` uses the player's **prior** zone attempt shares, because the earlier screen's strong
result conditioned on **realised** in-game attempts and is therefore not forecastable. The
null reported here belongs to that pregame-observable construction alone. A richer version —
zone-level rate forecasts rather than a single dot product, or shares conditioned on opponent
and minutes — is untested. `zone_cov` is 0.9908; the missing 0.9% are defence-zone cells with
zero prior attempts faced, counted and never imputed.
