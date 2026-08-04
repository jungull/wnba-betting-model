# Stage 2A Hypotheses — Source: BASKETBALL PACE AND COACHING

**Task:** TEAM_POSSESSION_PRIOR_V2 Stage 2A
**Source mandate:** basketball pace and coaching
**Lane:** IDEATION ONLY. Nothing in this document was fitted, tuned, selected or scored.
**Evidence:** `experiments/player_program/stage2a/EVIDENCE_PACKET.json`
(sha256 `f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e`), plus read-only schema and
coverage inspection of frozen artifacts, plus `build_projected_exposure.py` (read only).

---

## 0. What the evidence forces, before any hypothesis

Three facts from the packet constrain everything below, and a fourth I established by read-only
inspection.

**0.1 The error is variance, not level.** `squared_bias / MSE = 0.0019`. Overall bias is `+0.159`
against an MAE of `2.903` and a target SD of `3.908`. The incumbent explains `11.6%` of target
variance. Any hypothesis whose only effect is to re-centre the projection is dead on arrival at the
aggregate level. A hypothesis earns its place by **reducing dispersion**, or by correcting bias
*inside a named stratum* where bias is large even though it nets out globally. The packet supplies
exactly such strata: `team_window_prior_season` (bias `-2.845`), `game_no_in_season 1-3`
(bias `-2.175`), `game_no_in_season 4-6` and `7-10` (bias `+1.115`, `+1.142`), `days_rest 7+`
(bias `-1.435`).

**0.2 The incumbent's aggregation has a specific, nameable structural gap.** From
`build_projected_exposure.py::build_pace`, `game_pace` is a property of the *game*, and a team's
estimate is the unweighted mean of its own last 10 `game_pace` values. A team's own trailing window
is therefore **contaminated by the identity of the opponents it happened to face**, and the
projection for a matchup is the arithmetic mean of two such contaminated quantities. The packet's
assumption list states this plainly: "no opponent adjustment: the opponent's own pace tendency
never enters."

**0.3 The residual tails are wide.** `p05 = -5.875`, `p95 = +6.147` on a target with SD `3.908`.
Roughly a tenth of team-games miss by six or more possessions. Whatever generates those tails is
not a small perturbation of the mean, and a mechanism that only nudges the centre will not touch
them.

**0.4 (Established here) The possession count is an exact reciprocal of possession duration.**
I summed `duration_sec` over regulation periods (`period <= 4`) in
`possessions_v2/possessions_raw_v2.parquet`:

```
sum(duration_sec) per game, regulation only, n = 1495 games
  mean 2400.0   std 0.0   min 2400.0   max 2400.0
```

The possession durations **partition the regulation game clock exactly**, for every game, with zero
variance. There is no unattributed dead time in this artifact. Therefore, as an identity and not a
model:

```
N_regulation_possessions  x  mean_possession_duration  ==  2400 seconds     (EXACT)
```

This is the single most consequential fact I found, and Section A1 is built on it. It means
projecting a possession count and projecting a mean possession duration are the *same problem
viewed through a reciprocal*, and that the incumbent is averaging in the wrong domain.

**0.5 A cutoff-validity caution I am obliged to record.** The packet warns that its availability
table "records AVAILABILITY and COVERAGE... It does NOT prove cutoff validity". I checked the one
place this bites hardest. `data/masters/master_team.parquet` carries `observed_time` on all 2990
rows, but it takes only **two distinct calendar values, 2026-07-31 and 2026-08-01**, and zero rows
have `observed_time < game_date`. This is a retrospective bulk scrape, not a point-in-time capture.
`possessions_raw_v2.parquet` is worse in one respect: it carries **no capture timestamp column at
all**.

The honest reading is not that these are disqualified — it is that *the incumbent already rests on
exactly this basis*. `team_possession_prior/1` consumes `possessions_raw_v2`, whose cutoff validity
is an argument from **lag semantics** ("a completed game's result was knowable before the next game
tipped"), never an argument from **capture evidence**. Every hypothesis below inherits that same
standing, no better and no worse. Two consequences I will not paper over:

- Any hypothesis using `master_team` box aggregates carries **revision risk** that the possession
  stream does not: a retrospective scrape captures the *corrected* box score, not the one available
  on the night. This is mild for `tov`/`oreb`/`fta` and material for derived "misc" fields such as
  `points_fast_break`, which is 100% populated back to 2021 and was therefore almost certainly
  backfilled under a current methodology.
- Nothing here should be registered on the strength of the packet's `cutoff_valid: true` labels
  alone. Each arm needs the lag-semantics argument stated explicitly and reviewed.

---

## CATEGORY A — IMMEDIATELY TESTABLE

Inputs historically available, cutoff-valid on lag semantics, sufficiently complete, operationally
reproducible.

---

### A1 — Project in the duration domain, and combine two teams by summing durations, not averaging counts

**FLAGSHIP.** This is the hypothesis I would fund first.

**Source.** Basketball pace and coaching — offensive system, shot-clock usage, early offense versus
milking the clock.

**Mechanism.** A coach controls *how long his own team's possessions last*. He does not control the
possession count, because possessions alternate: the count is jointly produced by both teams. From
0.4, the clock budget is exact:

```
n_A * d_A  +  n_B * d_B  ==  2400        and     n_A ~ n_B ~ N/2
  =>   N  ~  4800 / (d_A + d_B)
```

where `d_T` is team `T`'s mean offensive possession duration. **Durations are the additive,
team-attributable, coach-determined quantity. Counts are neither additive nor team-attributable.**

The incumbent estimates each team's *game-level count* history and takes an arithmetic mean of the
two. Two errors compound:

1. **Wrong domain.** Because `N = 2400/d` is convex in `d`, averaging in the count domain and
   averaging in the duration domain give different answers, and by Jensen the count-domain average
   is the larger. The gap grows with the dispersion of the two teams' tempos. The incumbent's
   overall bias is `+0.159` — small, positive, and of exactly the sign this predicts.
2. **Wrong quantity.** Team `A`'s historical `game_pace` values encode `d_A` *and* the durations of
   whichever opponents `A` happened to face. Averaging two such quantities is right only when each
   team's trailing-schedule average opponent happens to equal its actual opponent tonight. It is
   systematically wrong for extreme matchups and for teams with unrepresentative recent schedules.

**Exact expected direction.** Estimate `d_A` and `d_B` separately from each team's own lagged
offensive possessions, then project `N = 4800 / (d_A + d_B)`. Relative to the incumbent this
**lowers** the projection for matchups where the two teams' tempos are dispersed, and leaves it
essentially unchanged where they are similar. Sign of the correction is `-sign(spread)`, magnitude
increasing in `|d_A - d_B|`. Separately, it **raises** the projection when tonight's opponent is
faster than the team's trailing-schedule average opponent, and **lowers** it when slower.

**Refinement, from the same evidence.** Not all possessions are tempo. From the `end_reason`
inspection, `period_end` possessions have median duration `7.0s` against `13-18s` for live
terminations — they are truncated by the period buzzer, not chosen. And `2365` regulation
possessions have `duration_sec == 0` (technical free throws, dead-ball sequences: `possession_kind`
is `zero_duration_sequence` n=1799, `technical_free_throw_sequence` n=588). So `d_T` should be
estimated over **live, non-truncated** possessions only, and the count decomposes as
`N = (clock-consuming possessions) + (zero-duration possessions)`, the second term being an
officiating/foul property rather than a tempo property. Lumping them, as the incumbent does, mixes
two generating processes with different persistence.

**Affected error stratum.** The high-spread matchups, which is where the `p05 = -5.875` /
`p95 = +6.147` tails live. Also `team_window_same_season` (n=2762, MAE 2.838), i.e. the bulk of the
data — this is not a niche fix. Expect the largest gains in the top decile of `|d_A - d_B|` and in
the top decile of trailing-schedule opponent-tempo skew.

**Cutoff-valid inputs required.** `duration_sec`, `offense_team_id`, `period`, `end_reason`,
`possession_kind`, `game_id` from `possessions_raw_v2`, aggregated over **strictly earlier games
only**; schedule identity for the opponent from the contract.

**Do the inputs exist?** Yes. All fields present, `duration_sec` and `end_reason` fully non-null
across 238,563 possession rows. Opponent identity is `cutoff_valid: true` in the packet with
2990/2990 coverage.

**Overlap risk with another hypothesis.** Moderate-to-high with any source proposing a generic
"opponent adjustment" or an additive own/opponent decomposition of `game_pace`. I regard those as a
*coarser operationalisation of the same insight*: they fix the contamination but keep the wrong
(count) domain, so they capture the second error above and not the first. If a competing arm
proposes additive residualisation of `game_pace`, the two should be run as a **nested pair**, not
as independent arms, and the duration-domain version should be required to beat the count-domain
version, not merely to beat the incumbent.

**Leakage risk.** Low, but not zero, and concentrated in one place: `d_T` must be computed from
strictly-earlier games under the same date ordering the incumbent already uses. The trap is that
`duration_sec` is a *possession-level* field, so an accidental join on `game_id` without the date
filter would pull the target game's own durations in. The producer's existing
`d < r.game_date` pattern is the guard.

**Expected information gain.** Highest of anything I propose. It replaces an aggregation that is
provably the wrong functional form for the quantity with one that follows from an exact identity,
and it applies to essentially all 2982 scored team-games rather than a stratum.

**Implementation complexity.** Moderate. One new lagged aggregate per team-game
(mean live possession duration) plus a changed combination rule. No new data source, no new
artifact, no fitting required for the deterministic version.

**Falsifier.** Stratify team-games by `|d_A - d_B|` estimated from lagged data. If the duration-domain
projection does **not** reduce MAE in the top decile of that spread relative to the incumbent, the
Jensen mechanism is not operative at WNBA-realistic tempo dispersions and A1's first limb is dead.
Independently: if a team's own lagged live-possession duration has no year-to-year or within-season
persistence beyond its `game_pace`, then `d_T` is not a team property and the whole hypothesis
fails. A cheap pre-test: the split-half persistence of `d_T` versus the split-half persistence of
`game_pace`. If `d_T` is not the more persistent of the two, stop.

**What it changes.** The **possession total**, and its **calibration** (dispersion). It does not
change subgroup allocation — the projection stays symmetric across the two sides.

---

### A2 — Use the realised pace of prior head-to-head meetings this season

**Source.** Basketball pace and coaching — style mismatch, playoff series adaptation, coach-versus-coach
familiarity.

**Mechanism.** A1 assumes the matchup combines *additively* from two separable team tempos. Real
basketball has interaction that no additive rule reproduces: a team presses full-court only against
opponents whose ball-handling invites it; a coach shortens the game against a superior transition
team by walking it up; a zone defence induces long possessions against one opponent and not
another. The realised pace of a **previous meeting between these exact two teams** is a direct
observation of the joint quantity being projected — the residual after A1's additive part is
precisely the mismatch interaction. The incumbent discards it by averaging over all ten trailing
games regardless of who they were against.

**Feasibility (established here).** I counted prior same-season meetings from schedule identity
alone:

```
prior same-season head-to-head meetings available at cutoff, 2990 team-games
  0 meetings : 890  (29.8%)
  1 meeting  : 836  (28.0%)
  2 meetings : 746  (24.9%)
  3 meetings : 336  (11.2%)
  4+         : 182  ( 6.1%)
  >= 1       : 2100 (70.2%)

by season_type:  Playoffs  n=212   100.0% have >=1,  99.1% have >=3
                 Regular   n=2778   68.0% have >=1,  11.1% have >=3
```

**70.2% coverage. This is a broad lever, not a niche one.** The WNBA's short season and 12-13 team
league is what makes it work — teams meet 3-4 times a year, which is dense enough for head-to-head
history to carry information while a 30-team league's would not.

**Exact expected direction.** Blend the prior meetings' realised `game_pace` (or, under A1, the
prior meetings' realised duration sum) toward the projection, with weight rising in the number of
prior meetings and falling with elapsed time since them. Where prior meetings ran faster than both
teams' separate window estimates predict, project **upward**; slower, **downward**. Weight zero at
0 meetings, so the 29.8% with no history are untouched.

**Affected error stratum.** `season_type = Playoffs` (n=212, MAE 2.422) where 99.1% have three or
more prior meetings — the single most informative stratum in the dataset and currently the one
where the incumbent leaves the most on the table relative to what is knowable. Also late-season
regular games and the `game_no_in_season 21+` stratum (n=1462, MAE 2.867).

**Cutoff-valid inputs required.** Schedule identity (`game_id`, `team_id`, `opp_team_id`,
`game_date`, `season`) plus realised `game_pace` of strictly earlier games. Both already in use.

**Do the inputs exist?** Yes, entirely. No new source. The head-to-head index is derivable from
fields the incumbent already loads.

**Overlap risk.** **Low.** This is the one mechanism I propose that is explicitly *non-additive* and
therefore orthogonal to A1 by construction — A1 models the matchup as separable, A2 targets the
residual that separability leaves behind. They should be tested jointly (A2 conditioned on A1)
rather than as substitutes. Low overlap with schedule/context or estimator-shrinkage sources.

**Leakage risk.** Low but with one sharp edge: **the "prior meeting" filter must be on strictly
earlier `game_date`, never on a series-game index or a schedule position**, since a series game
number can be known only once earlier games are played and any off-by-one admits the target game
itself. Same-day double-headers between the same clubs (rare, check) must be excluded, not
tie-broken.

**Expected information gain.** High, and highest per unit of implementation effort of anything
here. It uses only data already loaded.

**Implementation complexity.** Low. A cumulative count and a lagged group-mean on
`(season, unordered team pair)`.

**Falsifier.** Compute, for team-games with at least one prior meeting, the prior-meeting pace
residual (prior meeting's realised pace minus what the two sides' separate window estimates would
have predicted for it). If that residual has no relationship with the target game's residual, the
style-mismatch interaction does not persist across meetings and A2 is dead. Secondary falsifier: if
the relationship exists only in playoffs, A2 is a 212-row fix and should be scoped as such rather
than promoted league-wide.

**What it changes.** The **possession total** for 70.2% of team-games, and **calibration** in the
strata where meetings are dense. Symmetric, so no allocation change.

---

### A3 — Season-onset tempo profile: early-season games are genuinely faster, and the window over-corrects

**Source.** Basketball pace and coaching — training-camp installation, uninstalled defensive
schemes, unsettled rotations.

**Mechanism.** The packet contains a striking sign flip that a purely statistical reading would
miss:

```
game_no_in_season   1-3 : bias -2.175  (UNDER-projection)   n=228
                    4-6 : bias +1.115  (OVER-projection)    n=228
                   7-10 : bias +1.142  (OVER-projection)    n=304
                  11-20 : bias -0.050                       n=760
                    21+ : bias +0.279                       n=1462
```

The basketball story that produces exactly this shape: WNBA training camps are short and rosters
turn over heavily, so the opening games of a season are played with defensive schemes not yet
installed and rotations not yet settled. Those games are sloppy and fast — more live-ball
turnovers, more transition, fewer controlled half-court possessions. The incumbent under-projects
them (`-2.175`) because it is falling back on prior-season or league history that reflects
*settled* basketball. Then, by games 4-10, the window is built from three to nine of those
abnormally fast opening games and the incumbent **over-projects the games that have since settled
down** (`+1.115`, `+1.142`). The bias decays to roughly zero by games 11-20 as the fast openers age
out of the ten-game window.

This is a single mechanism generating both signs, which is why I find it more credible than a
generic "early season is different" adjustment.

**Exact expected direction.** A decaying additive season-phase term: **positive** for games 1-3
(roughly `+2`), **negative** for games 4-10 (roughly `-1.1`), approaching zero by game 11 and
beyond. Equivalently and preferably, deflate the contribution of a team's first few games of a
season when they appear in a later window.

**Affected error stratum.** `game_no_in_season` 1-3, 4-6, 7-10 — 760 team-games, 25% of the
dataset, and the three worst-biased phase strata. Overlaps the `support_bucket 3-4` (bias `+1.342`)
and `5-9` (bias `+1.147`) strata, which is the same games seen through a different cut.

**Cutoff-valid inputs required.** `game_no_in_season`, derived from schedule dates only. The packet
lists it at 2990/2990 with `cutoff_valid: true`.

**Do the inputs exist?** Yes, trivially.

**Overlap risk.** **High with A4, and I want that stated loudly.** Games 1-3 are exactly where the
level-2 (`team_window_prior_season`, bias `-2.845`) fallback fires. The `-2.175` at games 1-3 and
the `-2.845` at level 2 may be the *same 183-228 rows described twice*. A3 and A4 must not both be
credited for that correction. The disambiguation is games 4-6: those use level 1
(`team_window_same_season`) and still show `+1.115`, which no fallback-staleness story explains.
Also overlaps `support_bucket`, which any estimator-shrinkage source will likely claim — see A5.

**Leakage risk.** Effectively zero. Game number within season is a schedule fact.

**Expected information gain.** Moderate and *conditional*. If the effect is real, it is worth
roughly 1-2 possessions on a quarter of the data. If it is a fallback artifact, A4 and A5 already
capture it and A3 adds nothing.

**Implementation complexity.** Very low.

**Falsifier — and this is the one that matters most in this document.** Compute the **realised**
league-mean `game_pace` as a function of `game_no_in_season`, pooled across seasons. This touches
only the target and no projection.
- If realised pace genuinely declines from game 1 to roughly game 10 and then flattens, the
  season-onset mechanism is **real** and A3 is a legitimate independent arm.
- If realised pace is **flat** in game number, then the observed bias profile is entirely an
  artifact of the estimator's fallback and window composition, A3 is **dead**, and the correction
  belongs wholly to A4 and A5.

I genuinely do not know which of these will happen, and I am not permitted to check. This is the
highest-value single diagnostic in Stage 2B from my lane.

**What it changes.** The **possession total** in early-season strata, and **calibration** there.
Symmetric.

---

### A4 — Re-base the cross-season fallback on relative tempo, and replace the cumulative league prior with a recent one

**Source.** Basketball pace and coaching — era and rule-emphasis drift, offseason roster overhaul,
the distinction between a team's tempo *identity* and the league's tempo *level*.

**Mechanism.** Two defects, one root cause: the incumbent treats a pace number from a prior season
as directly comparable to this season's, when league-wide tempo drifts year to year with rule
emphasis, three-point volume and transition play.

- **Level 2** (`team_window_prior_season`, n=183) carries bias `-2.845` — by far the largest bias
  in the packet, and it is a genuine *level* error, not variance (`|bias|` 2.845 against SD 3.714).
  The incumbent under-projects because it imports last season's absolute pace into a faster present.
- **Level 3** (`league_prior_all`, n=37, MAE 3.902) uses, in the producer's own words and code, a
  *cumulative all-history* mean via `cumsum().shift(1)`. By 2026 that average is dominated by
  2021-2023 basketball. The packet's assumption list already flags it: "the league prior is a
  cumulative all-history mean, not a recent-window mean."

The basketball decomposition: a team's pace is `(league level this season) + (this team's tempo
relative to the league)`. The *relative* part is coach-determined and persists across a season
boundary. The *level* part does not. The incumbent carries both across the boundary, when it should
carry only the first.

**Exact expected direction.** For level 2, carry the team's **prior-season pace minus prior-season
league mean**, and add the **current season's emerging league mean**. Given the observed `-2.845`,
this should move level-2 projections **upward** by roughly that amount — i.e. WNBA pace has been
trending up across 2021-2026, which the season-by-season bias column is consistent with but does
not prove. For level 3, replace the cumulative mean with a trailing-window league mean, which
should move projections **upward** in later seasons and **downward** in 2021-2022 if the trend is
genuinely monotone.

**Affected error stratum.** `pace_source = team_window_prior_season` (n=183, MAE 3.693, bias
`-2.845`) and `league_prior_all` (n=37, MAE 3.902). Together 220 team-games — only 7.4% of the
data, but they contain the two largest MAEs and the largest bias in the entire packet. Also touches
the 8 unresolved level-4 team-games, which a recent-window league prior could resolve.

**Cutoff-valid inputs required.** Realised `game_pace` over strictly earlier games, already in use;
season identity, already in use. Nothing new.

**Do the inputs exist?** Yes. This is a change to the estimator's arithmetic, not a data request.

**Overlap risk.** **High with A3** (see A3's overlap note — same rows, two stories) and **moderate
with A5** (shrinkage would also damp the stale prior-season estimate, though it would not re-base
the level). Must be arbitrated: run A4 alone first, since it is the cleanest and cheapest of the
three and its stratum is the most sharply identified.

**Leakage risk.** Low, with one real trap: "the current season's emerging league mean" must be
computed over **strictly earlier dates in the current season only**. Early in a season that mean
rests on very few games and is itself unstable; it must be shrunk toward the prior season's level
rather than used raw, or A4 will import variance while removing bias.

**Expected information gain.** Moderate in aggregate (7.4% of rows) but **high per row**, and it is
the most defensible correction here because the target bias is unambiguous, large, and the packet
already names the cause. Note that a `-2.845` bias on 183 rows is worth roughly `0.17` of overall
MAE at best — worth having, not transformative.

**Implementation complexity.** Low. Two arithmetic changes inside `build_pace`.

**Falsifier.** If a team's prior-season pace *relative to that season's league mean* has no
year-over-year persistence, then there is nothing worth carrying across the boundary, the re-basing
limb fails, and only the recentring limb survives (which would then reduce to "use the current
league mean and ignore the team"). Separately: if league mean `game_pace` by season is flat across
2021-2026, the entire drift premise is wrong and A4 collapses to A5.

**What it changes.** The **possession total** in cold-start strata, and **calibration** there.
Symmetric.

---

### A5 — Support-scaled shrinkage and a longer window, justified by tempo being a coaching constant

**Source.** Basketball pace and coaching — tempo as a stable, coach-installed team identity rather
than a game-to-game variable.

**Mechanism.** The basketball claim comes first and the statistics follow from it. A team's tempo
is set in training camp by a coach's system and does not meaningfully change from game to game
within a season. If that is true, then almost all of the game-to-game variation in a team's
observed `game_pace` is **opponent effect plus noise**, not signal about the team. An unweighted,
unshrunk 10-game mean of a mostly-noise series is under-smoothed: it chases noise and passes that
noise into the projection. The packet's diagnostic is consistent — the estimator explains 11.6% of
target variance and its error is 99.8% variance.

The support strata make the case concretely: bias runs `+1.342` at 3-4 games of support, `+1.147`
at 5-9, and `-0.065` at the full window — a monotone decay in exactly the pattern a
shrinkage-toward-prior term is designed to remove.

**Exact expected direction.** (a) Lengthen the effective window beyond `WINDOW_K = 10`, or weight
it with a slow decay rather than a hard cutoff — this **reduces dispersion** with little effect on
the mean. (b) Shrink each team's window estimate toward the league (or the team's prior-season
relative) level with weight `~ 1/(n_history + c)`, which **pulls low-support estimates toward the
centre**, reducing the `+1.34` and `+1.15` biases at 3-4 and 5-9 support. Both effects are
variance-reducing, which is what 0.1 demands.

Note the `support_bucket > 10` row (n=23, MAE 4.538, SD 5.504): support above the nominal window
cap can only arise from the level-3 cumulative league prior's `n`, so this bucket is a *label
artifact*, not a real high-support stratum. It should not be used as evidence that more support is
worse.

**Affected error stratum.** `support_bucket 3-4` (n=156) and `5-9` (n=390) for the shrinkage limb;
`support_bucket 10` (n=2413, MAE 2.846) for the window-length limb — i.e. the bulk of the data.

**Cutoff-valid inputs required.** None beyond what the incumbent already uses.

**Do the inputs exist?** Yes.

**Overlap risk.** **Very high.** This is the most obvious hypothesis in the problem and I fully
expect at least one other source to propose it, probably in more developed statistical form. I
include it because my mandate supplies the *basketball justification* for the specific choice —
namely that shrinkage is warranted **because tempo is a coaching constant**, which predicts that
the optimal window is long and the optimal shrinkage target is the team's own multi-season relative
tempo rather than the league mean. That prediction is testable and distinguishes it from generic
regularisation. Also overlaps A4 (both damp the low-support strata) and A3 (same rows again).

**Leakage risk.** Low. The one trap is that any shrinkage *strength* chosen by looking at outcomes
is a fitted quantity and belongs to the fitting stage under proper chronological validation, not to
a hand-set constant justified post hoc.

**Expected information gain.** Moderate. It attacks the right thing (variance) across the whole
dataset, but it is a smoothing of the existing signal rather than the introduction of new
information, so its ceiling is bounded by what the current signal contains. A1 and A2 add
information; A5 only cleans it.

**Implementation complexity.** Low, but it introduces **tunable constants**, which is a governance
cost the deterministic hypotheses (A1, A8) do not carry.

**Falsifier.** If a team's `game_pace` shows high game-to-game persistence after removing opponent
identity — that is, if tempo really does move within a season — then the "coaching constant"
premise is wrong, a longer window is harmful, and the correct direction is the opposite
(shorter window, more responsiveness). Concretely: if the lag-1 autocorrelation of opponent-adjusted
team pace exceeds its lag-5 autocorrelation by a wide margin, stop and reverse.

**What it changes.** **Calibration** primarily (dispersion), and the **possession total** modestly
in low-support strata. Symmetric.

---

### A6 — Build the count from possession-composition rates, which are more stable than pace itself

**Source.** Basketball pace and coaching — offensive rebounding aggression, forced-turnover
philosophy, foul-and-free-throw pace, transition rate.

**Mechanism.** From the exact identity in 0.4, the possession count is fully determined by what
ends possessions and how long each type lasts. The `end_reason` inventory gives the mechanics
directly:

```
end_reason (regulation and OT, n=238,563)      median duration (regulation)
  defensive_rebound   84,647                     18.0s
  made_shot           82,738                     14.0s
  turnover            41,505                     13.0s
  made_ft_final       22,821                     12.0s
  period_end           6,054                      7.0s
  technical_ft            588                      0.0s
```

Each is a coaching lever with a *known sign*:
- **Offensive rebounds extend a possession without creating a new one.** Note that offensive
  rebound does not appear as an `end_reason` at all — confirming the possession continues through
  it. A team coached to crash the offensive glass therefore **reduces** the game's possession
  count while lengthening its own possessions. Available lagged as `oreb` / `opp_oreb`.
- **Live-ball turnovers end possessions early** (13.0s, second-shortest live category), **raising**
  the count. Available lagged as `tov` / `opp_tov`.
- **Free-throw and technical sequences consume little or no clock** (12.0s and 0.0s), so a
  high-foul team **raises** the count. Available lagged as `fta`, `pf`, `fouls_drawn`.
- **Transition play** shortens possessions directly. `points_fast_break` is the only direct measure
  available — see the caution below.

The statistical payoff: these component rates are **individually more stable across games than the
pace aggregate they combine to produce**, because each is a distinct coached behaviour with its own
persistence, while `game_pace` is their noisy convolution with the opponent. Decomposing a noisy
aggregate into stabler components and reassembling is a variance-reduction strategy, which is what
0.1 requires.

**Exact expected direction.** Higher lagged offensive-rebound rate → **lower** projected
possessions. Higher lagged turnover rate (either side) → **higher**. Higher lagged foul/FT rate →
**higher**. Higher lagged fast-break share → **higher**.

**Affected error stratum.** `team_window_same_season` (n=2762) — the bulk. Expected to help most
where a team's composition is extreme relative to its pace: heavy offensive-rebounding teams whose
raw `game_pace` understates their tempo identity, and high-foul teams whose count is inflated by
dead-ball possessions rather than tempo.

**Cutoff-valid inputs required.** Lagged `oreb`, `opp_oreb`, `tov`, `opp_tov`, `fta`, `opp_fta`,
`pf`, `fga`, `fg3a`, `points_fast_break` from `master_team`; and/or lagged `end_reason` /
`possession_kind` composition from `possessions_raw_v2`.

**Do the inputs exist?** Yes, and coverage is complete: I verified all of the above at **100%
non-null for all 2990 rows in every season 2021-2026**, with `in_misc = 1` on every row. **But see
0.5** — `master_team` is a retrospective bulk scrape with two distinct `observed_time` values, and
`points_fast_break` in particular is a derived "misc" statistic backfilled to 2021 under what is
probably a current methodology. **I would build the first version of A6 from `possessions_raw_v2`
`end_reason` composition alone**, which is the same source the incumbent already trusts, and treat
the `master_team` fields — especially `points_fast_break` — as a second, explicitly-flagged
extension.

**Overlap risk.** Moderate with A1 — both operate on the duration decomposition, but from opposite
ends: A1 projects the *mean* duration, A6 projects the *mixture weights* that produce it. If both
are run, A6 should be evaluated as an increment over A1, not over the incumbent. Low overlap with
A2, A3, A4.

**Leakage risk.** **Moderate — the highest in Category A, and the reason I rank it below A1 and A2
despite liking the mechanism.** Every one of these fields is a realised target-game outcome. They
are cutoff-valid *only* as lagged aggregates, and the packet says exactly that
(`cutoff_valid: "ONLY LAGGED"`). A single careless join on `game_id` imports the target game's own
turnover and rebound totals, which would produce a spectacular and entirely spurious improvement.
Any A6 arm needs an explicit assertion in the producer that no `master_team` row with
`game_date >= target game_date` entered the aggregate.

**Expected information gain.** Moderate-to-high if the stability premise holds, but discounted by
the leakage-surface and revision-risk costs.

**Implementation complexity.** Moderate-to-high — several new lagged aggregates, a new input
artifact (`master_team`) if the extension is used, and a new guard assertion.

**Falsifier.** Compare the split-half stability of each component rate against the split-half
stability of `game_pace` itself. If the components are **not** more stable than the aggregate, the
entire rationale evaporates and A6 is just a higher-variance re-parameterisation of the same
signal — reject it. Secondary: if an A6 arm beats the incumbent by a margin far larger than A1 and
A2 combined, **suspect leakage before celebrating**.

**What it changes.** The **possession total** and **calibration**. Symmetric.

---

### A7 — Projected competitiveness: close games manufacture possessions, blowouts suppress them

**Source.** Basketball pace and coaching — endgame clock management, intentional fouling, timeout
usage, garbage-time rotation.

**Mechanism.** The final minutes of a close game are played under a completely different possession
economy: the trailing team fouls intentionally to stop the clock, converting long possessions into
near-zero-duration free-throw trips, and both coaches spend timeouts to preserve clock. Under the
exact identity in 0.4, shortening possession durations mechanically **increases** the count. A
blowout does the opposite — no fouling, no urgency, and deep-bench lineups that walk the ball up.

The evidence supports a *conditional* rather than a constant effect. Regulation possessions by
period:

```
period 1: 61,052   period 2: 59,232   period 3: 59,266   period 4: 57,579
```

Q4 has **fewer** possessions than Q1, by about 3,500 across 1495 games. So the *average* fourth
quarter is slower, not faster — which is what you would expect if blowout-suppression outweighs
close-game inflation on average. But both effects are present and they point in opposite
directions, which is precisely why a term conditional on *expected* competitiveness should
outperform both the incumbent's implicit constant and any unconditional Q4 adjustment.

**Exact expected direction.** Games projected to be **close** → project **more** possessions.
Games projected to be **blowouts** → project **fewer**. The magnitude should be small at the median
and concentrated in the tails of projected margin.

**Affected error stratum.** The residual tails specifically (`p05 = -5.875`, `p95 = +6.147`) rather
than any labelled stratum — this is a tail hypothesis. It should also interact with `went_ot`
(n=132), since OT games are by definition maximally close.

**Cutoff-valid inputs required.** A projected margin built from **lagged** team strength: `pts`,
`opp_pts`, `plus_minus`, `wl` from `master_team` over strictly earlier games, plus `is_home`
(2990/2990, `cutoff_valid: true`).

**Do the inputs exist?** Yes, at 100% coverage — subject to the same 0.5 retrospective-scrape
caveat as A6.

**Overlap risk.** Moderate. A "team strength / expected margin" feature is an obvious candidate for
a general-purpose or context-oriented source. My contribution is the specific *mechanism and
functional form*: the effect should be **non-monotone in signed margin and monotone in absolute
margin**, and it should act through possession *duration*, not directly on the count. If a
competing arm proposes signed margin as a linear term, that is a different and, I would argue,
wrong specification.

**Leakage risk.** **Moderate-to-high.** Realised final margin is the most seductive leak in this
entire problem — it is enormously predictive of possession count and completely unavailable at
cutoff. The arm must use a *projected* margin from lagged strength only. `abs_score_diff_start`,
`score_diff_offense_start` and `non_competitive_conservative` exist in `possessions_raw_v2` (14,593
possessions flagged non-competitive) and are **strictly forbidden for the target game** — they are
usable only to characterise the mechanism retrospectively, never as an input.

**Expected information gain.** Uncertain, and I want to flag a specific way it fails: the mechanism
may be **real but not operationalisable**. Realised margin almost certainly relates to possession
count; projected margin from lagged strength is a much weaker signal, and the attenuation may take
the whole effect below usefulness. That is a genuine and likely outcome, not a hedge.

**Implementation complexity.** Moderate.

**Falsifier.** Two-stage, and the two-stage structure is the point.
1. Does realised possession residual vary monotonically with realised absolute final margin? If
   **no**, the mechanism does not exist — stop.
2. If yes, does a *lagged-strength projected* margin retain enough of that relationship to move
   MAE? If **no**, the mechanism is real but not usable at cutoff, and it should be recorded as
   such rather than registered as an arm.

**What it changes.** The **possession total** in the tails, and **calibration** (tail behaviour
specifically). Symmetric.

---

### A8 — Count regulation possessions directly instead of minute-scaling overtime games

**Source.** Basketball pace and coaching — period structure, and the fact that an overtime period
is not a scaled-down regulation game.

**Mechanism.** The incumbent computes `reg_equiv_off_poss = n_off_poss * 40.0 / game_minutes` with
`game_minutes = 40 + 5 * max(0, max_period - 4)`. This assumes possessions accrue **linearly in
elapsed minutes** and that an overtime minute is interchangeable with a regulation minute. Neither
holds. An overtime period begins from a jump ball, is played entirely under endgame conditions
(maximum urgency, heavy fouling, timeout-dense), and its final possession terminates the game the
instant it is decided. Its possession density is not the game's average density.

The packet shows the symptom: `went_ot = True` carries bias `+0.541` against `+0.141` for
non-overtime — overtime games are over-projected, meaning their minute-scaled regulation-equivalent
value comes out **below** what the projection expects.

**The leverage is far larger than the 132 overtime team-games suggest.** The distortion enters the
*history* as well as the target. With overtime in roughly 4.4% of games and `WINDOW_K = 10`,
**on the order of a third of all trailing windows contain at least one distorted value.** A
mis-normalised overtime game contaminates every window it sits in for the next ten games.

**Exact expected direction.** Replace minute-scaling with a direct count of possessions in
`period <= 4`. Given the `+0.541` overtime bias, this should **raise** the regulation-equivalent
value assigned to overtime games, removing the over-projection and — more importantly — removing a
downward contamination from roughly a third of all windows. Effect on the overall level: small.
Effect on dispersion: larger, because it removes a noise source rather than a bias.

**Cutoff-valid inputs required.** `period`, `is_overtime`, `offense_team_id`, `game_id` from
`possessions_raw_v2`, lagged. All already loaded by the producer.

**Do the inputs exist?** Yes, fully. I verified `period` takes values 1-8 (periods 5-8 present:
1285/114/17/18 possessions) and `is_overtime` is fully populated (1434 overtime possessions). The
regulation filter is exact and unambiguous.

**Overlap risk.** **Very low.** This is a definitional correction to the target and history
construction, largely orthogonal to every other hypothesis here. It should be applied as a
**baseline correction under all arms**, not as a competing arm.

**Leakage risk.** **None.** It strictly *removes* information (overtime periods) from a lagged
computation.

**Expected information gain.** Low-to-moderate in absolute terms, but with an unusually good
risk-to-effort ratio: it is deterministic, has no tunable constants, cannot leak, and cleans an
input that every other hypothesis depends on. I would apply it first, before evaluating anything
else, so that the other arms are measured against a clean baseline.

**Implementation complexity.** Very low — one filter in `build_pace`.

**Falsifier.** If regulation-only possession counts for overtime games are **not** systematically
higher than their minute-scaled equivalents, the normalisation is unbiased and A8 is unnecessary.
Directly checkable, no fitting, one comparison.

**Caveat I should state.** This changes the **target definition**, not merely the projection.
Comparing an A8-corrected challenger's MAE against the incumbent's `2.903` would be comparing
against a different target. The incumbent must be re-scored on the corrected target before any
comparison is meaningful. If that re-scoring is not acceptable within the program's freeze
discipline, A8 should be deferred rather than fudged.

---

### A9 — Post-break rust (INCLUDED THOUGH I EXPECT IT TO FAIL)

**Source.** Basketball pace and coaching — post-break rotation experimentation, timing loss,
conditioning after a layoff.

**Mechanism.** `days_rest 7+` carries MAE `3.527` and bias `-1.435` — the worst-fitting rest
stratum and a genuine under-projection. The basketball story: long layoffs in the WNBA are
league-wide breaks (Olympics, All-Star, Commissioner's Cup), and teams return from them with
degraded timing — more turnovers, looser defence, faster and sloppier games. Coaches also use the
first game back to look at rotations, which adds substitution churn and dead-ball time.

I confirmed the breaks are league-wide clusters rather than idiosyncratic gaps. Counting within-season
gaps of 7+ days:

```
2021 n=37, 12 in week of Aug 9   (Tokyo Olympic break)
2024 n=13, 12 in week of Aug 12  (Paris Olympic break)
2023 n=18,  9 in week of Jul 17  (All-Star break)
2025 n=12,  5 in week of Jul 21
2026 n=14,  6 in week of Jul 27
2022 n= 9,  no cluster above 2
total n=103
```

So the mechanism is correctly identified as *post-break*, not generic rest.

**Why I expect it to fail.** My within-season count is **103** team-games; the packet's `7+` stratum
is **162**. The ~59-game difference is almost certainly **season openers**, where the gap since the
previous game spans the entire offseason. If most of the `-1.435` bias is carried by those openers
rather than by mid-season breaks, then A9 is **A3 and A4 wearing a different label**, and crediting
it separately would double-count the same correction. Even in the best case, 103 team-games is 3.4%
of the data and a `-1.4` correction there is worth roughly `0.05` of overall MAE.

**Why I am including it anyway.** Two reasons. First, the packet contains very few genuine bias
signals — most strata are variance-dominated — and `-1.435` is one of them, so it deserves an
explicit disposition rather than silent omission. Second, and more usefully, **A9's disambiguation
is diagnostically valuable even if A9 itself is rejected**: splitting the `7+` stratum into openers
versus mid-season breaks is the cleanest available test of whether A3/A4's early-season correction
is real, and it costs almost nothing.

**Exact expected direction.** First game after a league-wide break of 7+ days → project
**upward** by roughly 1.4 possessions, decaying to zero by the second game back.

**Affected error stratum.** `days_rest 7+` (n=162 as the packet defines it; n=103 as within-season
breaks).

**Cutoff-valid inputs required.** `days_rest` from schedule dates. 2990/2990, `cutoff_valid: true`.

**Do the inputs exist?** Yes. Note that identifying a gap as a *league-wide break* rather than an
idiosyncratic one requires either a designation table (see B6) or an inference from the
simultaneous clustering of gaps across many teams — the latter is derivable from the schedule alone
and is cutoff-valid, since the full schedule is published in advance.

**Overlap risk.** **High and probably fatal** — with A3, A4, and with any schedule/rest/travel
source, which I expect exists and whose lane this partly is. I am not claiming the generic rest
effect; I am claiming only the post-break variant.

**Leakage risk.** Effectively zero.

**Expected information gain.** Low. Stated plainly: I would not register this as an arm on its own.
I would run its disambiguation as a diagnostic in service of A3 and A4.

**Implementation complexity.** Very low.

**Falsifier.** Split the `7+` stratum into (a) season openers and (b) mid-season breaks. If the
`-1.435` bias sits almost entirely in (a), A9 is dead and the signal belongs to A3/A4. If it sits
in (b), A9 is real but small.

**What it changes.** The **possession total** in a small stratum. Symmetric.

---

### Levers in my lane that I am deliberately NOT claiming

Recorded so the absence is a decision rather than an oversight.

- **Home/away pace effect.** `is_home` is available at 2990/2990 and cutoff-valid. A home crowd,
  home-friendly whistle and transition confidence could plausibly raise a game's tempo. I am not
  claiming it because the projection is symmetric at game level, so home/away can only shift the
  *game total* via a small constant, and I judge this to belong to a schedule/context lane.
- **Travel and time-zone burden.** The packet lists venue geocoding as ABSENT. Schedule-fatigue
  lane; see B7.
- **Player-level tempo attribution.** The possession stream carries `off_p1..off_p5` on-court
  identities, so a lineup-level tempo model is constructible retrospectively — but knowing *which
  lineup will play tonight* is not available pregame (packet: announced lineups UNAVAILABLE). This
  is Category B (B4), not A.

---

## CATEGORY B — HIGH-VALUE BUT UNAVAILABLE

These may **not** enter TEAM_POSSESSION_PRIOR_V2 as arms. They belong to a data and capability
roadmap.

---

### B1 — Coach identity and coaching-change events

**Missing input.** A coach-by-team-season table, with mid-season changes dated: head coach identity,
appointment date, interim flag, and prior-team history.

**Why it may matter.** Of everything in my mandate, this is the most direct. **Pace is the most
coach-determined property a basketball team has** — more than efficiency, more than shooting, more
than defence. A coaching change is a genuine *structural break* in tempo, and it is precisely the
kind of break a trailing window is guaranteed to miss: the window will keep projecting the old
coach's tempo for ten games after the new coach has installed a different system. This is not a
marginal effect; a coach who replaces a milk-the-clock system with an early-offense mandate can move
a team several possessions per game essentially overnight.

It also supplies the **prior** the entire cold-start problem lacks. The `team_window_prior_season`
stratum has bias `-2.845` and `league_prior_all` has MAE `3.902` — both are cases of "we do not know
this team's tempo yet." A coach's tempo at his *previous* team is a far better opening prior than the
league mean, and it is available at game 1 of a season when nothing else is. A5's premise that tempo
is a coaching constant is, in fact, untestable without this table.

I confirmed the absence independently of the packet: a `*coach*` sweep across `data/` and
`experiments/` returns nothing.

**Minimum viable collection.** A hand-maintained CSV: `season, team_id, coach_name, start_date,
end_date, is_interim`. The WNBA has 12-13 teams over 6 seasons — roughly **80-100 rows**, plus a
handful of mid-season changes. This is a few hours of work from public sources, and it is fully
**retrospective**: coaching appointments are public and dated, so history can be reconstructed
exactly rather than collected forward.

**Prospective-only validation required?** **No.** This is the key point and it matches the packet's
own assessment (`prospective_only_validation: false`). Unlike injuries, odds, and lineups, coaching
history is a matter of public record and can be backfilled to 2021 with high confidence. **B1 is the
only item in Category B that could become Category A with a bounded, one-off effort.**

**Expected value of closing the gap.** Highest in Category B by a wide margin, and disproportionate
to its cost. It would (a) supply a cold-start prior for the two worst strata, (b) enable structural-break
detection that no window can achieve, (c) make A5's central premise testable, and (d) cost on the
order of 100 hand-entered rows.

**Caution.** A hand-maintained table is a new canonical artifact with no automated provenance, which
sits awkwardly against this program's construction-receipt discipline. It would need explicit
provenance treatment — source URLs per row, a compilation date, and an integrity hash — before it
could back a registered arm. It must also be built **without reference to pace outcomes**, or it
becomes an outcome-informed feature by the back door.

---

### B2 — Referee crew assignment (a REPAIRABLE gap, not an absent one)

**Missing input.** The officiating crew assigned to each game, joined to `game_id`.

**Why it may matter.** Foul rate is the single largest driver of dead-ball possessions, and from the
identity in 0.4 dead-ball possessions enter the count directly: `made_ft_final` possessions run 12.0s
against 18.0s for `defensive_rebound`, and `technical_ft` possessions run 0.0s. A whistle-heavy crew
mechanically raises a game's possession count by shortening the average possession. Crew tendency is
one of the more replicable effects in basketball analytics, and crucially **crews are announced
before tip**, which makes this genuinely pregame information rather than an outcome — a property
almost nothing else in Category B shares.

**Why I classify it as repairable.** The packet reports `0 of 1495 contract games overlap` and notes
`officials_master.csv carries no game_id join at all`. I confirmed `data/ref_assignments/` exists and
contains `assignments_log.csv` and a `raw/` directory. **The data appears to be present; what is
missing is the join key.** This is a data-engineering defect, not a data-availability defect, and
those have very different costs.

**Minimum viable collection.** Establish a `game_id` join on the existing assignment log, most likely
by matching on `(game_date, home_team, away_team)`. If the raw captures carry a date and team names,
this is a mapping exercise against the contract schedule. Only if the log genuinely predates the
modelling span does this become a collection problem rather than a join problem. **Determining which
of those two situations obtains is a cheap, high-value first step** and I would rank it immediately
after B1.

**Prospective-only validation required?** **Unknown, and that is the question to resolve.** If the
existing log covers 2021-2026 historically, then no — this becomes retrospectively testable and
would move to Category A. If it begins in 2026, then yes.

**Expected value of closing the gap.** High if the log has historical depth; moderate otherwise.
Distinctly worthwhile because it is genuinely pregame, mechanistically tied to the possession count
through an exact identity, and possibly already paid for.

---

### B3 — Tactical scheme markers: press rate, zone rate, early-offense mandate

**Missing input.** Per-team-season (ideally per-game) measures of defensive scheme — full-court
press frequency, zone versus man rate, pick-up point — and offensive tempo mandate — seconds-per-touch,
share of possessions initiated in transition.

**Why it may matter.** These are the actual mechanisms behind A1 and A6. A full-court press directly
manufactures possessions by forcing early turnovers; a zone slows the opponent's entry and lengthens
possessions; an early-offense mandate shortens them. Knowing a coach *presses* is far more stable and
more forward-looking than observing the turnover rate that pressing happens to have produced against
a particular sequence of opponents. This is also the cleanest route to the **style-mismatch
interaction** that A2 can only observe indirectly through realised head-to-head results: with scheme
markers you could predict the mismatch for a matchup that has *not yet occurred*, covering the 29.8%
of team-games with no prior meeting.

`points_fast_break` in `master_team` is the only proxy currently available, and it is a weak one —
it is a *points* measure rather than a *frequency* measure, and per 0.5 it is a backfilled derived
statistic.

**Minimum viable collection.** No cheap version exists. Realistically this requires licensed tracking
or synergy-type play-type data. A crude partial substitute could be derived retrospectively from the
possession stream: possessions ending in turnover within the first 8 seconds are a reasonable press
proxy, and that *is* computable from `duration_sec` and `end_reason` — which is arguably a cheap
Category A feature rather than a Category B gap. I flag that as a lead worth pursuing under A6 rather
than waiting on B3.

**Prospective-only validation required?** For licensed tracking data, likely yes for genuine scheme
labels; no for the possession-stream-derived proxies.

**Expected value of closing the gap.** High in principle, poor in cost-effectiveness. **The derived
proxy is the sensible move; the licensed data is not worth it for this problem alone.**

---

### B4 — Announced starting lineup and pregame rest designations

**Missing input.** The pregame lineup posting and any load-management or rest designations.

**Why it may matter.** Tempo is partly personnel. A team missing its primary ball-handler plays
slower and more deliberately; a team resting starters plays deeper, sloppier, faster basketball. The
packet already flags this at team level; **my lane's specific version is narrower and stronger:
the availability of the team's primary tempo-setter — the initiating guard — rather than availability
in general.** A backup centre's absence should barely move pace; the starting point guard's absence
should move it materially. The current injury capture spans only `2026-07-30 .. 2026-08-04`, six days
of a five-season span.

**Minimum viable collection.** Persist the existing injury and lineup captures forward from
2026-07-30, and additionally capture pregame lineup postings, which are published roughly 30 minutes
before tip. Pair with a possession-stream-derived "tempo-setter" identification per team-season
(which player's on-court presence most changes team possession duration) — that part **is**
retrospectively computable from `off_p1..off_p5` and `duration_sec`, so half of this feature can be
built today while waiting for the other half.

**Prospective-only validation required?** **Yes**, unambiguously. There is no archival pregame
availability feed here, and the packet's own caution is explicit that pre-2026-07-30 availability is
"not a genuine captured pregame feed." Retrospective injury data would encode information that was
not known at the historical decision time — the same defect that disqualified the `tier_a_plus_tx_b`
regime in `build_projected_exposure.py`.

**Expected value of closing the gap.** Moderate for pace specifically. Note that pace is a *team
system* property more than an individual one — a coach's tempo tends to survive personnel changes
better than efficiency does — so I would rank this **below B1 and B2 for this particular target**,
even though it is likely more valuable than either for downstream player-level projections.

---

### B5 — Shot-clock state and possession start type

**Missing input.** Shot-clock seconds remaining at possession start and end, and the possession's
start type (made-basket inbound, live defensive rebound, dead-ball sideline, steal in the open floor).

**Why it may matter.** This separates *choice* from *circumstance*, which A1 cannot do. Two teams
with identical mean possession durations can be entirely different: one gets many live-rebound
transition starts and takes early shots, the other gets dead-ball starts and runs its offence into
the shot clock. The first team's tempo is fragile — it depends on generating stops — while the
second's is a stable coached property. Only the stable component should carry forward into a
projection, and without start-type data A1 must treat them identically.

It would also let end-of-period behaviour be measured properly: the `6,054` `period_end` possessions
at median `7.0s` include deliberate two-for-one hunting, which is a pure coaching decision worth
roughly one to two possessions per game to a team that pursues it systematically. Right now these are
indistinguishable from possessions that merely ran out of clock.

**Minimum viable collection.** Shot-clock state is not in `possessions_raw_v2`. Start type is
**partially derivable today** — the prior possession's `end_reason` implies the next possession's
start type (`made_shot` → dead-ball inbound, `defensive_rebound` → live start, `turnover` → live or
dead depending on type). That derivation needs no new data and belongs under A1/A6 as a refinement.
True shot-clock state would require a richer play-by-play source or a new canonical event artifact.

**Prospective-only validation required?** No for the derived start-type proxy. For genuine
shot-clock state, it depends on whether the upstream play-by-play carries it — worth one check
against `build_canonical_events.py` before assuming absence.

**Expected value of closing the gap.** Moderate. **The derivable portion is the good part and should
be pulled forward into Category A**; the licensed remainder is a lower priority.

---

### B6 — Game-designation table (Commissioner's Cup, All-Star break, international windows)

**Missing input.** A per-game designation flag and a league-calendar table of break windows.

**Why it may matter.** Two distinct effects. Commissioner's Cup games count in the regular-season
standings but are played with different stakes and, plausibly, different intensity and tempo — they
are currently indistinguishable from ordinary games in `season_type`, which takes only
`Regular Season` and `Playoffs`. Separately, a break-window table would let A9 be tested properly
instead of inferred from gap clustering.

**Minimum viable collection.** A small hand-maintained table: roughly 6 seasons x (a handful of Cup
games plus 1-2 break windows). Perhaps 50-80 rows, fully retrospective from public schedules.

**Prospective-only validation required?** **No.** Entirely reconstructible from published schedules.

**Expected value of closing the gap.** Low-to-moderate on its own, but very cheap, and it is a
**precondition for cleanly resolving A9 and part of A3**. Worth doing as a by-product of B1, since
both are small hand-built schedule-adjacent tables and would share provenance machinery.

---

### B7 — Venue and travel table

**Missing input.** Venue coordinates and time zone per team, for travel distance and time-zone-change
derivation. Packet lists this as ABSENT; a static 12-team table would suffice.

**Why it may matter (my lane's angle only).** I am largely ceding this to a schedule-fatigue source.
The one pace-specific angle worth recording: **altitude and arena-specific tempo effects**, and the
fact that a coach facing a heavy travel leg will often shorten his rotation, which changes the
possession economy through personnel rather than through fatigue directly.

**Minimum viable collection.** A static 12-13 row table with coordinates and time zones.

**Prospective-only validation required?** No.

**Expected value of closing the gap.** Low for possession projection specifically. Cheap enough that
it should be built anyway if another lane wants it.

---

## Summary and recommended ordering

If I had to rank my own hypotheses by expected value net of risk:

1. **A8** — apply first as a baseline correction under all arms. Deterministic, no constants, cannot
   leak, and it cleans an input every other hypothesis depends on. Carries a target-definition
   caveat that must be resolved before scoring.
2. **A1** — the flagship. Rests on an exact identity I verified (`sum(duration_sec) == 2400`, zero
   variance across 1495 games) and corrects a provably wrong aggregation domain across the whole
   dataset.
3. **A2** — highest gain per unit of effort. 70.2% coverage, no new data, and the only genuinely
   non-additive mechanism I propose.
4. **A4** — cleanest bias correction in the packet, smallest arithmetic change, sharply identified
   stratum. Modest ceiling (~0.17 MAE).
5. **A6** — good mechanism, real leakage surface and revision risk. Build from `end_reason` first,
   `master_team` second.
6. **A5** — right target (variance) but adds no new information, and I expect it to be proposed by
   another source in stronger form.
7. **A7** — best mechanism story of the lot; most likely to be real-but-unusable once margin is
   projected rather than realised.
8. **A3** — credible and cheap, but may be A4 in disguise. Its diagnostic is more valuable than its
   arm.
9. **A9** — expected to fail. Included for its disambiguating diagnostic value, not as an arm.

Category B ordering: **B1** (coaching table — retrospectively buildable, ~100 rows, would upgrade to
Category A), then **B2** (referee join — possibly already paid for, needs one cheap check to find
out), then **B6** (cheap, unblocks A9/A3), then **B5**/**B3** derived proxies pulled forward into A6,
then **B4**, then **B7**.

**Three cross-cutting cautions.**

- The strata in this packet overlap heavily. `game_no_in_season 1-3`, `support_bucket 3-4`,
  `pace_source = team_window_prior_season` and part of `days_rest 7+` are substantially **the same
  team-games described four ways**. A3, A4, A5 and A9 all claim territory there. They must be
  arbitrated against each other, not each credited against the incumbent independently, or the same
  200-odd rows will be fixed four times on paper and once in reality.
- Per 0.5, no arm here should be registered on the packet's `cutoff_valid` labels alone. `master_team`
  is a retrospective bulk scrape (two `observed_time` values), `possessions_raw_v2` carries no capture
  timestamp at all, and every cutoff-validity claim in this document — including the incumbent's own —
  rests on **lag semantics** rather than capture evidence. That argument is defensible but it must be
  made explicitly per arm and reviewed, not inherited silently.
- Given 0.1, any arm that improves MAE mainly by shifting the mean should be treated as suspect
  rather than successful. The incumbent's squared bias is 0.19% of its MSE. There is almost nothing
  to gain by re-centring, and an arm that appears to gain a lot that way is more likely to have found
  a leak than a mechanism. **A6 and A7 are where I would look first if a result looks too good.**
