# IDEATION QUEUE — ranked candidate hypotheses for future screening

Built 2026-08-08 by the IDEATION agent. Ranked by **expected value = plausibility x ceiling x feasibility / cost**.

- **Generated: 101. Cut: 57. Queued: 44.** Cuts with reasons are in `CUT_LIST.md` so nobody re-proposes them.
- **Structural / methodological: 33 of 44 (75%). Feature: 11 of 44 (25%).**
- Every entry is checked against `TRAP_CHECKLIST.md` and against `CLOSED_SURFACES.md`.
- Machine-readable form: `QUEUE.json`.

**The premise of this queue.** ~1,000 candidate cells have been screened, all of the form *"does
variable X predict outcome Y"*, and they correctly kept reporting that there are no more variables.
The two things that actually worked were **structural**: the champion **emits a constant** (8.704
points, sd 0.013) for players with fewer than 3 prior appearances, and **declining to forecast a
definable subpopulation roughly doubles skill on minutes**. Neither could have been found by a
feature screen. This queue is weighted accordingly.

**Read `CLOSED_SURFACES.md` before dispatching anything from here.** Several entries below deliberately
sit next to a closed surface and argue their way past it; those arguments are in the
`why_not_dead` field and a coordinator should check them rather than take them on trust.

---

# THE TOP 5 — dispatch-ready

## Q1. The measurement regime is confounded with the exploration/holdout partition
**STRUCTURAL · target: all · cost: cheap · ceiling: not a dR2 — this is a validity ceiling on every E2 the program will ever run**

**Statement.** The `era` column in `master_player.parquet` records which source regime produced each
row. The exploration partition (2021–2024) is ~92% `gamelog_old`; the confirmation holdout
(2025–2026) is **100% `gamelog_new`, with zero `gamelog_old` rows**. Discovery and confirmation are
therefore run on two different measurement regimes, and the boundary between them is exactly the
partition boundary.

**Mechanism.** D063 made E2 the deployment-authorising standard, and its strongest evidence is folds
4 and 5 — precisely the `gamelog_new` seasons. If any feature's construction, coverage, rounding or
definition differs across the regime boundary, a failure to replicate at E2 is **uninterpretable**:
nobody could distinguish "the signal is not real" from "the data changed underneath it". Because the
program's headline results are kills, the risk runs the other way too — a lead that *does* replicate
might be replicating a source artefact. This is the reference-incompleteness trap (T4) promoted from
the feature level to the partition level, and it is the one trap that would corrupt every future
confirmation simultaneously.

**Verified on bytes.** `era` x `season` cross-tab: 2021 = 3,565 old / 320 new; 2022 = 4,096 / 423;
2023 = 4,544 / 354; 2024 = 4,515 / 399; **2025 = 0 / 5,853; 2026 = 0 / 4,259**. (The third value,
`v3` = 5,384, is exactly the DNP rows; `minutes_source` is `none` on all of them and `misc` on all
28,328 played rows.)

**How I would screen it.** Purely a measurement exercise, no model. (1) For every column consumed by
any live lead and by the champion, compute its distribution **within the 2021–2024 overlap region
where both eras coexist** — this is the clean comparison, because season is held fixed and only the
source varies (320–423 `gamelog_new` rows per exploration season). (2) Test each column for a
regime shift with a two-sample comparison at the right level (T2 — most of these are player-game
rows, so a row-level test is fine for a *measurement* claim but not for a skill claim). (3)
Separately, check **definitional** equality: does `minutes` mean the same thing, are `possessions`
computed the same way, do the `estimated_*` columns exist in both. (4) Report a per-column verdict:
SAFE / SHIFTED / UNDEFINED-IN-ONE-ERA. (5) The deliverable is a **column-level admissibility list for
E2**: any column marked SHIFTED cannot carry a confirmation claim without a re-derivation.
Guard against T5 throughout — decide on values, never on the column name.

**Why not already dead.** Nothing in D001–D093 mentions `era`. D063 designed the walk-forward ladder
and D062 defined the partition; neither checked whether the partition boundary coincides with a
source boundary. This is a genuine blind spot, it is cheap, and it gates everything downstream.

---

## Q2. Sweep every champion output for degeneracy, not just the cold-start region
**STRUCTURAL · target: points, minutes, FGA, p_active · cost: cheap · ceiling: the one known instance was worth +1.36% pooled points skill on 7.2% of rows, free**

**Statement.** D092 found that the champion emits a **constant** (8.704 points, sd 0.013) for players
with fewer than 3 prior appearances — it was not modelling them at all. That was found by looking at
one population for one reason. Nobody has asked the general question: **where else is the champion
emitting something degenerate?**

**Mechanism.** A forecast that is constant, near-constant, clipped, saturated, or identical across
distinct inputs is not a forecast — it is a fallback that the aggregate metrics silently absorb.
Because the program centres on pooled MAE and pooled dR2, a degenerate region of any size below a few
percent is invisible. The cold-start constant was invisible for the entire life of the program until
someone looked directly at the emitted values. The obvious inference is that nobody has looked
anywhere else, and the fix, when found, was **free** — no new data, no refit.

**How I would screen it.** Score-only, no fitting, so it is coordinator-scoped. For each forecast
column in the arm D076/D088 inventoried (`pts__pred_point`, minutes, FGA, `p_active`): (1) compute the
**local standard deviation of the prediction** within fine bins of every available pre-game state
variable — prior-appearance depth, prior minutes, team, season, position from bios, starter status,
roster depth — and flag any bin where prediction sd collapses relative to the pooled prediction sd;
(2) count **exact duplicate prediction values** and the population attached to each modal value;
(3) check for **clipping** at the empirical min/max and for **monotone saturation** (prediction stops
responding to a regressor beyond a threshold); (4) check whether the prediction ever equals a simple
constant such as a league or team mean to within float tolerance. Report every degenerate region with
its row count, its share of the partition, and the champion's skill inside it versus a strictly-prior
reference facing the same rows (T8 — skill, never raw MAE). Any region found becomes a candidate
splice of exactly the D092 shape.

**Why not already dead.** D092 closed the cold-start region only. D076's abstention screen conditioned
on pre-game state to find where skill is low, which is a related but different question — it looked at
*skill*, not at *the emitted values*. Degeneracy is a property of the output distribution and has
never been audited.

---

## Q3. Build one canonical reference ladder and re-price every recorded lead against it
**METHODOLOGICAL · target: all · cost: cheap–medium · ceiling: re-prices the entire ledger; the two known instances moved the same result by 6.5x and 4.6x**

**Statement.** Every screen chose its own reference. D093 ranks **reference/increment dependence as
the #1 explanation for the program's nulls**, and there are now two confirmed instances where the
reference alone changed the answer: D090 (the same forecast scored **+46.4% or +7.1%**) and D093 (the
same forecast on the same rows scored **+0.22% or +4.24%**). There is no canonical reference ladder.

**Mechanism.** dR2 and skill are *relative* statistics. If reference choice varies across screens,
then the ~1,000 recorded cells are not on a common scale, the kills are not comparable to each other,
and a lead can be manufactured or destroyed by a defensible-looking choice. D072 ruling 4 already
records that **dR2 is not scale-free across screens** and that a cross-screen ordering is fragile
"even after a convention is imposed". A ladder is the mechanism that actually fixes it, and D093
demonstrated the failure mode concretely: a mean-of-prior-ratios estimator wins at minutes floor 0
and a ratio-of-prior-sums estimator wins from floor 10 upward, so **which reference is strongest
changes with the filter**.

**How I would screen it.** (1) Define a frozen, documented ladder of strictly-prior references for
each target — league mean; team mean; player's own prior mean; player's prior mean shrunk toward team
and league with a stated shrinkage; ratio-of-prior-sums; mean-of-prior-ratios; minutes-conditioned
variants; and a prior-appearance-depth-tiered variant reflecting D092. (2) Freeze it as a module with
tests, hash it, and record the hash. (3) Re-score **every currently live lead** — teammate volume
(D089), cold-start tiering (D092), shot-mix-on-attempts (D079), I0009 at its corrected 0.000413
(D072) — against **all** rungs, and report the **spread**, not a single number. (4) Report which rung
is strongest per target and per stratum, because D093 shows this is not constant. Deliverable is a
table of `lead x reference-rung -> skill`, plus a standing rule that a screen reports the spread.
**Do not overlap with `E1_I0022_optimal_simple_estimator`**, which asks whether the champion beats a
tuned prior-history estimator; this asks a different question — whether the program's *recorded
numbers* are comparable — and should consume Q22's output rather than duplicate it.

**Why not already dead.** D069 adopted a *convention* (plain unweighted OLS R2) but explicitly ruled
that **past numbers cannot be rescued by a multiplier** and must be re-run. Nobody has re-run them.
D072 identified the limitation and stopped there.

---

## Q4. Measure the program's detection floor before screening anything else
**METHODOLOGICAL · target: all · cost: cheap · ceiling: determines whether ~1,000 recorded nulls are findings or power failures**

**Statement.** The exploration partition is **18,216 played player-rows across 265 players and 966
team-games**. Nobody has computed the **minimum detectable effect** at that sample size under the
program's own null machinery. If the detection floor sits above the ceilings the program is chasing,
then the ~1,000 nulls are **power failures reported as science**.

**Mechanism.** D093 ranked sample size #3 among reasons the nulls may be artefacts and made the only
direct measurement of it — the single-player ceiling, which found that with maximum data on the
best-sampled players a fitted model **loses to that player's own running average** (walk-forward R2
−0.052 to −0.197 on all ten cells, against in-sample +0.04 to +0.18). That is a power statement.
Meanwhile the program's best-ever measured lead is dR2 **+0.0023** with a ceiling of 0.0021 (D089),
and the killing ceilings have been 0.001127 and 0.000129. **If the minimum detectable dR2 at n=18,216
under a cyclic-shift null with family-wise correction over 40 candidates is, say, 0.002, then every
kill in the ledger below that value is uninformative** — and so is most of this queue.

**How I would screen it.** Pure simulation on the real design matrix, no new data. (1) Take the actual
exploration frame and the actual reference. (2) Inject a **synthetic signal of known dR2** into the
response at a grid of sizes (1e-4, 3e-4, 1e-3, 3e-3, 1e-2), with realistic serial structure — build
the injected regressor as a `.shift(1).expanding()` construction so it carries the same autocorrelation
the real candidates do (T3). (3) Run the program's own screening pipeline, including the cyclic-shift
null and family-wise correction over a realistic candidate count. (4) Report **power at each effect
size**, for pooled rows and for the strata the program actually decides on. (5) Repeat under the
plain within-shuffle null to quantify how much the T3 anticonservatism inflated historical power.
Deliverable: a power curve and a single number — the **smallest dR2 this program can reliably detect**
— which becomes the standing screening bar and replaces the current informal ~0.001 rule of thumb.

**Why not already dead.** Never attempted. D093's single-player ceiling is the closest thing and it
addresses per-player fitting, not the pooled screening design. This is the cheapest entry in the queue
and it is the one that tells the user whether to keep funding screens at all.

---

## Q5. The free-throw and foul-draw channel — the largest untested points surface
**FEATURE · target: points (via ftm), fta, fouls_drawn · cost: medium · ceiling: FT is 17.4% of points; perfect-ftm bound R2 0.435; realistic target ~0.002–0.005 dR2**

**Statement.** Points decompose as 2PT + 3PT + FT. The program has screened shot **mix** (killed on
points, D079) and **conversion** (killed on points, D084) — both field-goal channels. **The free-throw
channel has never been screened at all**, and D084 ruling 2 names it explicitly as one of the two
remaining untested routes.

**Mechanism.** Free throws are a *different process* from field goals: they are generated by drawing
fouls (a contact/aggression/role property) and converted at a rate that is far more stable
within-player than field-goal percentage. That combination — volume driven by an unstable opportunity
process, conversion driven by a stable player trait — is exactly the opportunity x conversion
decomposition the T1 thesis (D060) says to look for, and it is the decomposition that has *not* been
tested. Critically, the two field-goal channels died on **ceilings**, not on statistics; the FT
channel's ceiling is roughly an order of magnitude larger, so the reason they died does not transfer.

**Verified on bytes** (exploration partition, 18,216 played rows): FT points are **17.37%** of all
points. `ftm` corr with points **+0.6595** (perfect-forecast R2 bound **0.4350**); `fouls_drawn` corr
**+0.6749** (bound **0.4555**); `fta` corr +0.6548. `fouls_drawn`, `fta`, `ftm` are **100% covered in
all six seasons**. **`fta == 0` on 46.4% of played rows and `fouls_drawn == 0` on 30.5%** — this is a
hurdle process, not a continuous rate, which is why an EWMA of FT rate would be the wrong estimator
and may be why nobody found anything here by accident.

**How I would screen it.** (1) Preregister and hash the candidate list (D085/D087 practice).
(2) Build the target as a **hurdle**: `P(fta > 0)` and `E[fta | fta > 0]` as separate responses, plus
`ftm | fta` as a near-stable conversion rate — do **not** screen a single continuous FT rate.
(3) Candidate regressors, all strictly prior: own prior foul-draw rate per minute; own prior FT rate;
prior share of attempts at the rim (from shotcharts, which cover all seasons); opponent prior fouls
committed per possession; own prior `pf` (foul trouble limits exposure — see Q39); role/usage terms.
(4) Score against the **full Q3 reference ladder**, not one reference (T4). (5) Null at the player
level with a **cyclic shift**, because every regressor is a shift-expanding construction (T3).
(6) Then the decisive step, and it is the one that killed the other two channels: **propagate to
points** and compute the arithmetic ceiling directly — how much does the FT component's forecastable
variance move `pts` — before claiming anything (T7). (7) Report the component-vs-product comparison
(D093's cancellation finding, ranked #5) so a gain in `ftm` that cancels against field points is not
reported as a points gain.

**Why not already dead.** D084 ruling 2 explicitly lists "zone mix feeding foul-draw and free-throw
rates" as untested. D085 killed **foul-draw matchup** — that is the *opponent interaction*, ruled
`REDUNDANT` as a repackaged main effect — which is a different claim from the player's own foul-draw
and FT process being unforecastable. The main effect has never been tested as an opportunity x
conversion decomposition against a complete reference.

---

# THE REST OF THE QUEUE, RANKED

Format: **ID. Statement** — mechanism | type | target | feasibility & provenance | trap check |
ceiling | cost | why not dead.

### Q6. Injury **type** conditions the return hazard, and that is why `p_active` mis-shapes long absences
Return-to-play timelines differ enormously by injury: an ACL is a season, a concussion protocol is
days, an illness is a game. `p_active` treats absence duration as a single curve, which is exactly the
observed defect — it is **11.5 pp too pessimistic** about returns from long absence and **mis-shapes
the duration curve rather than being uniformly biased** (D090). A single curve fitted across mixed
injury types would produce precisely that signature. | **STRUCTURAL, extends a live lead** | availability |
`data/injury_history/injury_history.csv`: 8,340 rows, 2021-01-07 to 2026-07-29, **2,242
`missed_game_injury`** with **184 distinct body-part notes** (KNEE INJURY 179, RIGHT KNEE INJURY 152,
CONCUSSION PROTOCOL 57, ACL 53, ACHILLES 36, ILLNESS 42), 3,262 missed-game rows in 2021–2024; joins to
356 distinct players. Corroborated by `master_player.dnp_reason`, 100% populated on all 5,384 DNP rows
with 22 values. **Provenance: no manifest on either file** — resolve on values (D087 method) and record
it. | T1: absence spells are strictly prior *by construction* if you only use spells that closed before
the forecast date — this must be enforced, not asserted. T5: injury type must be parsed from note
**values**, and the free-text taxonomy must be frozen and hashed before screening. T4: score against the
Q3 ladder. | Bounded by the 11.5 pp defect on the long-absence stratum; that stratum is small but the
error is large and one-directional. | medium | D090 characterised `p_active` and ruled it should not be
rebuilt, but the **one actionable defect it named** was the long-absence curve, and it recommended a
targeted recalibration. Injury type is the obvious missing conditioner and was never joined.

### Q7. Recover part of the 49.2% same-day-news fraction of the teammate-volume channel from **prior absence spells**
D089 established the program's best lead and recorded that ~49.2% (elsewhere ~60%) of the channel is
same-day news nobody can have, and that a real pre-game injury feed is "the single highest-value data
acquisition the program has identified". But a teammate who has **missed the last four games with an
ACL** is overwhelmingly likely to be out tonight, and that inference is **strictly prior**. The
unavailable part is genuinely same-day (a scratch at shootaround); the *persistent* part is not. |
**STRUCTURAL, extends the program's best lead** | points, minutes | `injury_history.csv` +
`master_player.dnp_reason`; team-games with >=1 DNP = **78.5%**, >=2 = 56.1%, >=3 = 30.8%, mean 1.80
DNPs per team-game across 2,990 team-games. | T1: use only spells whose observations closed strictly
before the game date. T2: null at team-game level. T4: measure against the prior-only variant of the
lead, which is the honest incumbent. | The tip-time variant is 0.0078 and the prior-only variant is
0.0023; **the gap is 0.0055 and this proposal targets a fraction of it**. Even a third would exceed
every other lead in the program. | medium | D089 ruling 3 frames the whole gap as an acquisition
question. It is partly an acquisition question and partly a **construction** question, and the
construction half has never been attempted.

### Q8. Test whether the cold-start rule and the teammate-volume lead are additive
D089 ruling 4 says this explicitly and it has not been done: "This lead should first be tested against
the cold-start tiering work now running, because **both act on the same rows and their gains may not be
additive**." | **STRUCTURAL, extends two live leads** | points | Both leads' frames exist:
`E1_I0018_teammate_volume_channel/screen_frame.parquet` and `E1_I0020_coldstart_tiering/tier_frame.parquet`.
Score-only. | T4: one shared reference for both. T8: skill, not MAE. | Bounded by the smaller of the two
gains; the question is whether the sum 0.0023 + (cold-start gain) overstates the joint gain. | cheap |
Directed by D089 ruling 4 and never dispatched.

### Q9. Re-audit every shift-expanding screen under the cyclic-shift null
D093 ruling 4 states that any prior screen using a within-block scheme on a shift-expanding regressor
"may carry an anticonservative p" and that it "should be checked rather than assumed". The coordinator's
own belief is that this does not overturn any verdict — because the headline results are kills and an
anticonservative null makes a kill *harder* — but **"any surviving lead measured that way needs
re-checking"**, and that check has not happened. | **METHODOLOGICAL** | all | All frozen screen
directories are readable; permutation draws are stored (`permutation_draws.npz`, `maxt_null_draws.csv`,
etc.). | T3 is the subject. T6: verify the cyclic null itself can fire, using the iid noise controls
D093 built. | Does not create a lead; it protects every surviving one and could **withdraw** one. | cheap |
Directed by D093 and undone.

### Q10. `master_player.position` is blank on every non-starter — re-test position from `player_bios`
Verified on values: `position` non-blank on exactly 14,950 rows = exactly `starter_flag == 1`;
**55.65% of rows are blank**. Any feature keyed on this column silently conditions on starter status,
which is itself an outcome-adjacent quantity. D092 dropped listed position from the cold-start rule on
p 0.783 / permutation null 0.1996. **If that test read `master_player.position`, it was run on a
variable missing for over half the rows** and the null is uninformative. | **STRUCTURAL** | points,
minutes | `player_bios.csv:position_raw` at **99.81%** coverage of 1,058 player-seasons (Guard 482,
Forward 305, Center 122, plus 147 hyphenated); `master_player` rows join to a bios (player_id, season)
row at **100%**. Provenance: bios has no manifest. | T5: I nominated by name and **convicted on values**
(cross-tab, perfect separation) — a re-test must do the same. T6: the blank-position case is a live
example of a control that cannot fail. | Restores an axis D092 discarded; bounded by whatever the
cold-start rule's position term would have been worth. | cheap | D092's null may be an artefact of the
wrong column. First step is a **five-minute check of which column D092 actually read** — if it read
bios, this entry collapses to a cut and should be moved to `CUT_LIST.md`.

### Q11. Apply D073's level-vs-updating decomposition to every live lead
D073 produced the program's best methodological result: when a market comparison is blocked by missing
prices, ask which **component** of the feature a posted line must already contain, and test whether the
effect lives there. It killed the possession-volume family by showing ~99% of the effect sat in the
team-season pace **level** and ~0% in within-season updating. **It has never been applied to the leads
that are still alive.** | **METHODOLOGICAL, tests live leads** | points, minutes, attempts | Score-only
on existing frames; no market data needed — that is the point of the technique. | T4: this *is* a
reference-completeness test in disguise. | Could kill the teammate-volume lead the same way it killed
I0013, which is worth knowing before it consumes holdout at E2. | cheap | D073 generalised the technique
explicitly and nobody carried it forward.

### Q12. Decompose the one forecast that works — where does **minutes** skill live?
The program has spent ~1,000 cells on the target where skill is absent (efficiency) and almost nothing
on understanding the target where skill is present. Minutes skill is **+3.55%** (D076) and roughly
doubles under the abstention rule. Nobody has asked what it is made of. | **STRUCTURAL** | minutes |
`master_player.minutes` 100% on played rows; `starter_flag` 100%; `derived/stints.parquet` gives
121,629 per-player per-period stints with `stint_sec` and `player_game_sec`. | T4: decompose against
the Q3 ladder. T2: null at player level. | Not a new lead — it is the map of the only thing that works,
and it tells every future proposal what a working signal looks like here. | cheap–medium | Never
attempted. D081 decomposed **points** to find where skill is lost; the mirror-image question about
minutes was never asked.

### Q13. Size the void-risk under-estimate as an expected-value quantity
D090 ruling 3 calls this "the most directly monetisable finding of the session": `p_active` **under-
estimates void risk by 7.7 pp**, concentrated in the 0.50–0.80 band, **running in the costly
direction**, on **9.5% of rows**, and requires "no new signal and no new data — only using the observed
rate rather than the predicted one in that band". It was surfaced for the user and never quantified in
money-shaped terms. | **STRUCTURAL, extends a live lead** | availability | `E0_I0019_availability_forecast/void_risk_bands.csv`
already exists. | T8: this is a calibration claim, not a skill claim, and must be labelled as such. | The
finding is already measured; this entry converts it into a decision quantity. | cheap | Not dead —
surfaced and parked. Note the model change itself is a **user decision**; the sizing is not.

### Q14. Overtime inflates the target on 4.2% of rows and is unforecastable at tip-off
Verified: **66 of 1,495 games** reach period >=5; player-rows in OT games mean minutes **21.068 vs
25.147 (+19.4%)** and mean points **8.652 vs 10.224 (+18.2%)**. No pre-game information predicts
whether a game goes to overtime. The model is therefore charged for variance that is structurally
unforecastable, on 4.23% of played rows. | **STRUCTURAL** | points, minutes, all counts | `possessions.parquet`
period field, all 1,495 games. | T7: the ceiling is the variance removed, which is small in aggregate —
this must be computed before the idea is believed. T1: OT status is a *post-game* fact, so it may be
used to **define an evaluation stratum**, never as a feature. | Removing 4.2% of rows carrying ~19%
inflation is a small variance effect; it may fall below the Q4 detection floor, which is the honest
risk. | cheap | D021/A12/A16/A26 recorded an OT-handling divergence as a preserved disagreement at the
team level; it has never been examined at player level.

### Q15. Excise garbage-time **possessions** from the response — this is not D093's minutes floor
D091/D093 tested a **realised-minutes floor** and found the skill curve flat. That filter drops whole
rows on the basis of total minutes. A garbage-time filter is a different operation: it removes the
**possessions** played at a large margin while keeping the row. `possessions.parquet` carries
`home_pts_before`/`away_pts_before` per possession, so margin-by-time is exact. | **STRUCTURAL** | points-per-minute,
rates | Verified: **7.02%** of all possessions and **14.88%** of period->=4 possessions run at
|margin| >= 20; 15.63% at >= 15. Full 1,495-game coverage. Provenance: `possessions.parquet` has **no
manifest** and its coverage exceeds raw pbp — see Q30, which gates this. | T1: margin is a within-game
retrospective fact; legitimate for defining an evaluation response, **never** as a feature. T3: the
resulting response is still autocorrelated. | D093 found the minutes floor removes 39.3% of
points-per-minute variance and 44.7% of the within-player component — the noise is real and large; the
question is whether a sharper instrument reaches it. | medium | D093 closed the **minutes-floor**
construction, explicitly on the strongest-reference comparison. It did not test possession-level
excision, and its own finding that the noise "had already been priced into the reference" is a
statement about that construction.

### Q16. Every count target is over-dispersed and zero-inflated, and OLS is an unexamined choice
Verified on the exploration partition: variance/mean is **`reb` 2.93, `ast` 2.40, `oreb` 1.74 (53.0%
zeros), `blk` 1.51 (70.9% zeros), `fg3m` 1.79 (56.6% zeros), `ftm` 2.87 (49.3% zeros), `tov` 1.39,
`pts` 6.45**. Poisson would give 1.0 throughout. The whole program measures dR2 under a Gaussian/OLS
convention (D069) that nobody has justified against the response's actual distribution. | **STRUCTURAL** |
rebounds, assists, 3PM, FT, all counts | All columns 100% covered on played rows. | T7: the ceiling here
is not a new signal but a **re-ranking** — the question is whether any already-killed candidate would
survive a correct link. T4: must hold the reference fixed while varying only the link. | Does not create
signal; may reveal that a kill was a link artefact. Bounded and honest about it. | medium | D069 adopted
a metric convention; it never asked whether the response's scale suits it. This is squarely "which
target is measured on the wrong scale".

### Q17. The champion cannot score 15.97% of its own universe — what happens to those rows?
`master_player` carries a row for every rostered player including DNPs: **5,384 of 33,712 rows (15.97%)
have null minutes**, and `dnp_reason` is populated on 100% of them and on 0% of played rows. A points
forecast is only evaluable where the player played, so the response is **observed conditionally on
selection**. If those rows are silently dropped, every coverage and skill figure is computed on a
survivor population. | **STRUCTURAL** | points, minutes, availability | 100% verified on bytes. | T1:
`dnp_reason` is post-game and may define a stratum, never a feature. T6: "we drop DNP rows" is exactly
the kind of step that cannot fail and is never reported. | This is the D010 finding — "every cold-start
coverage figure is flattered by construction because the hardest cold-start day was already removed" —
one level down and 15.97% wide. | cheap | Never examined. D090 characterised `p_active` as a
*forecast*; this asks how the **evaluation universe** is constructed, which is a different question.

### Q18. Abstention has only ever been measured one variable at a time
D076 screened 348 cells of single conditioning variables and found four usable leads; D090 consolidated
on prior-appearance depth and ruled against combining it with `p_active`. But the decision surface is
**joint**: the question a bettor faces is "given everything observable pre-game, is my skill here
positive?", not "is depth low?". | **STRUCTURAL** | points, minutes | Score-only on existing scored
frames (`E0_I0015`, `E0_I0019`). | T8: the response must be **skill against a reference facing the same
rows**, which is the failure D076 demonstrated twice. T2: null at the level the abstention rule
operates. T6: include a random-abstention control that can fail — D092 built one
(`negative_control_random_tier.csv`). | D076's single best rule roughly **doubles** minutes skill at
~60% coverage. A joint surface can only match or beat the best single rule, and the interesting number
is how much. | medium | D090 ruled against **one specific combination** (`p_active` + depth) on
evidence. That is not a ruling against joint conditioning generally.

### Q19. Audit every control in every screen for whether it **can fail**
D093 found the natural per-player control is a **literal no-op, observed sd 5.207e-17**, and that it
"returns a clean bill of health while testing nothing". It also found its own precision-weighted
statistic let a noise control through at p 0.0076 because the weights were the one player-attached
quantity a covariate permutation does not permute. | **METHODOLOGICAL** | all | All frozen screens
readable; several ship `noop_placebo_draws.csv` explicitly. | T6 is the subject. | Protects the ledger;
could withdraw an assurance rather than a result. | cheap | D093 found one instance and named the class.
The sweep was never run.

### Q20. Nothing accounts for multiplicity **across** screens
Each screen applies family-wise correction **within** itself. Roughly 1,000 cells have been fired across
the program with no program-level accounting. Some kept leads survived their own family-wise correction
"thinly" (D074, on the conversion channel). | **METHODOLOGICAL** | all | Screen results are stored as CSVs
(`screen_results.csv` in several directories). | T4 interacts: cells scored against different references
are not exchangeable, so a naive pooled FDR would itself be wrong — this must be handled, not ignored. |
Changes the interpretation of every thin survivor. | cheap | Never attempted.

### Q21. Does the player model beat "team total x prior usage share"?
A top-down reference: forecast the team's points, then allocate by the player's strictly-prior usage
share. If the champion cannot beat that, the entire player layer is questionable — and if it can, the
margin is the player layer's actual contribution. | **STRUCTURAL** | points | `master_team.parquet`
(2,990 rows, full `opp_*` columns, has a manifest); `usage_percentage` and `estimated_usage_percentage`
100% covered on played rows. | T4: this **is** a reference-completeness probe and belongs on the Q3
ladder. T1: usage share must be strictly prior. | Does not add signal; it bounds the player layer's
value and may reveal the champion's skill is inherited from the team model. | cheap–medium | The four-
system separation (D061) freezes market/basketball separation but says nothing about top-down vs
bottom-up references. D061 records layer 4 (bottom-up aggregation) as VIABLE_BUT_UNVALIDATED; this is
the *reference* question, not the aggregation rebuild, so the P3 guard does not bind.

### Q22. Possession-level **defender identity**, not team-aggregate defensive rating
D085 fired 12 constructions and 36 cells at opponent defensive matchup and found nothing — **all of
them built from team-level aggregates**. `possessions.parquet` carries `def_p1..def_p5` on every one
of 238,563 possessions. | **FEATURE** | points-per-minute, efficiency, attempts | Verified: shots join to
possessions on **100%** of `shots_2023_regular` GAME_IDs and **5,515 of 5,515 shots (100%)** fall inside
a possession window on a 40-game sample under the cumulative-game-seconds convention; **46% are
boundary-ambiguous** and need tie-breaking by `offense_team_id`. 2026 shots also match 100%, so this is
**confirmable at E2** — unlike anything built on raw pbp (Q33). Provenance: neither `possessions.parquet`
nor `data/shotcharts/*` has a manifest; Q30 gates this. | T4: **score against the Q3 ladder** — D085's
kill mechanism was aggregation, but reference weakness is the more likely reason a re-run would appear
to succeed. T7: the ceiling must be stated **before** screening, and the honest prior is that it is small
— D087 closed the central question and this sits next to it. T2: null at the matchup level, not the row. |
The efficiency surface is closed at dR2 ~0; this must clear the Q4 detection floor to be worth anything,
and a proposer should expect it not to. | expensive | **This is the most likely entry in the queue to be
a re-proposal of dead ground, and it is queued with that stated.** It survives only because the kill
mechanism was aggregation and the construction is genuinely different. **Do not dispatch it before Q4
and Q30.**

### Q23. Rebound opportunity is downstream of shot location, and no rebound forecast exists
D087 ruling 3 names this as "the honest next frontier": rebounds and assists have never been screened,
"shot quality predicts conversion robustly, and rebounding opportunity is downstream of shot location".
Where shots come from determines where misses land. | **FEATURE** | rebounds (oreb/dreb separately) |
`data/shotcharts/` covers all six seasons (26k–38k shots/season) with `SHOT_ZONE_BASIC` (7 zones),
`SHOT_DISTANCE`, `LOC_X/LOC_Y`; `oreb`/`dreb` 100% covered. | T7: `oreb` perfect-forecast bound on
**points** is only 0.0763 — but the target here is **rebounds**, where the relevant variance is its own
(`reb` var 10.75, 14.6% zeros; `oreb` var 1.51, **53.0% zeros**). T4/T16: zero-inflation makes the link
choice load-bearing. | Real but must be stated against the rebound target, not points. | medium |
**GATED**: D088 ruling 1 settled that generating a rebound forecast "requires generating forecasts...
no coordinator work can discharge it". `E0_I0024_reb_ast_characterisation` is **currently running** —
this entry must be re-scoped against its output before dispatch and may be superseded by it.

### Q24. Points decompose into four channels at player level, and none has been used
`master_player` carries `points_paint`, `points_fast_break`, `points_second_chance`,
`points_off_turnovers` — plus the four `opp_*` mirrors — at **100% coverage in all six seasons**. These
are four distinct generating processes summed into one target. | **FEATURE** | points | 100% verified. |
T7: the ceiling is the sum of the channels' forecastable variance, and D093's cancellation finding is
the specific risk — components can each carry skill while the product carries less (FGA/min +1.055% and
pts/FGA +0.826% gave a product of only +0.443%). T4: Q3 ladder. | Unknown; must be computed per channel
before screening. | medium | Never screened. Distinct from shot **location** (D079, killed on points) —
`points_fast_break` is a transition-context channel, not a location channel. Note **pace and transition
are closed** (D085) as *opponent/context* features; this is the player's own channel mix.

### Q25. Starter/bench is a regime switch, and the champion may be averaging across it
`starter_flag` is 100% populated and splits the panel 14,950 / 18,762. A player's minutes distribution
either side of that boundary is close to bimodal. A model emitting a conditional mean across a mixture
produces a value that is wrong for both regimes. | **STRUCTURAL** | minutes, points | 100% covered.
Note `starter_flag` for *tonight* is not strictly known pre-game — prior-game starter status is. | T1:
**tonight's** starter flag is post-lineup and may not be a feature; prior starter status may. This
distinction is the whole proposal. T8: skill, not MAE. | Bounded by the size of the regime-transition
population — players changing role — which must be counted first. | cheap | Related to but distinct from
the killed "starting-five stability" (D076), which was a *team* churn variable. This is the player's own
regime.

### Q26. Replace cross-screen dR2 with a common-currency metric
D072 ruling 4 established that **dR2 is not scale-free across screens** and that a cross-screen ordering
is fragile "even after a convention is imposed", recommending comparison on a common target. No common
currency was defined, so the program still ranks leads by dR2. | **METHODOLOGICAL** | all | Score-only. |
T4/T7 both bear on it. | Changes which lead is "best" and therefore what gets promoted to E2. | cheap |
Identified and not acted on.

### Q27. Establish the irreducible-noise floor of the minutes forecast from realised game margin
Minutes depend on game script — blowouts truncate starters' minutes and inflate bench minutes — and game
script is unforecastable at tip-off. Decomposing minutes error by **realised** margin separates the
forecastable part of minutes from the part no model can reach. | **STRUCTURAL** | minutes | `possessions.parquet`
margin-by-time on all games; `master_player.minutes` 100% on played rows. Verified: 7.02% of possessions
run at |margin| >= 20. | T1: realised margin defines an evaluation stratum, **never** a feature. T8:
skill against a reference facing the same rows. | Bounds the only target with skill — tells the program
how much of the remaining minutes error is even addressable. | cheap | Never attempted.

### Q28. Age and career stage as a prior, especially where history is thin
`player_bios.csv` carries `age` (98.2% coverage), `birthdate` (100%), `draft_year`/`draft_number`
(86.1%). Aging curves are among the most robust effects in team sports and have never been screened
here. Age is constant within a season so it cannot help within-player, but it is exactly the kind of
prior that helps where the model currently emits a constant. | **FEATURE, extends a live lead** | points,
minutes | Bios joins to `master_player` at 100% on (player_id, season). No manifest. | T1: age is fixed
pre-season, so it is a clean Tier-1 provenance case under D065. T2: null at player-season level — a
row-level null here is the classic wrong-null error. | Small on the pooled panel; potentially material on
the 1,115 rows with <=2 prior appearances (3.94%), which is D092's validated target population. | cheap |
D092 validated draft slot and depth-chart rank and dropped listed position. Age was not in that
candidate set.

### Q29. Walk-forward RAPM artifacts exist, carry manifests, and may be unused
`data/rapm/` holds `rapm_v0.csv`, `rapm_walkforward.csv`, `rapm_walkforward_seasons.csv` — **all three
with sibling manifests**, which makes them among the few gate-passing artifacts in the repository. A
walk-forward RAPM is a per-player quality estimate built to be point-in-time valid. | **STRUCTURAL** |
points, minutes | Manifests present (3 of 6 files). | T1: the walk-forward construction must be verified
on values, not on the filename (T5) — "walkforward" in a name is a nomination, not a conviction. | If it
is valid and unused, it is a free player-quality prior; if it is used, this closes in an hour. | cheap |
Never referenced in D001–D093. First step is to determine whether anything consumes it.

### Q30. Resolve the provenance of `possessions.parquet` — it gates several entries
`possessions.parquet` covers **all 1,495 games including 215 games in 2026**, but `data/playbyplay/`
holds only **996 files and zero for 2026**. An artifact cannot straightforwardly have more coverage than
its apparent source. It has **no manifest**. | **METHODOLOGICAL / infrastructure** | n/a — a gate |
Verified counts above. | T1: if part of it was built retrospectively from a season-complete source, it is
a retrospective-baseline hazard exactly like `data/lineups/`. T5: resolve on values. | Gates Q15, Q22,
Q23 and any possession-level work. | cheap | D080 verified two *other* high-priority artifacts as
ROW-granular and clean; `possessions.parquet` was not among them. D075/D080 rank the manifest backlog as
the highest-value infrastructure work available, and D085/D090 record two occasions where the manifest
gap **blocked science**.

### Q31. Cumulative season **load** is a different mechanism from schedule **state**
The schedule family is closed across four screens and three targets (D090 ruling 5: "No fifth attempt
without a new mechanism"). Rest days, B2B and 3-in-4 are all *schedule state* — properties of the
calendar. Cumulative minutes played to date is *accumulated exposure* — a property of the player's
season — and was in none of those screens. | **FEATURE** | minutes, efficiency | `minutes` 100% on
played rows; trivially cumulative. | T3: a cumulative sum is maximally autocorrelated, so **only a
cyclic-shift null is admissible** — this is the single most T3-exposed candidate in the queue. T4: it
correlates mechanically with games played, so the reference must already contain prior-appearance depth
or the "signal" is just depth. | Modest; and the honest prior after four schedule kills is low. | medium |
Queued **with the explicit warning** that it sits next to a family closed with a "new mechanism"
requirement, and that the new-mechanism argument above is the whole justification. A coordinator may
reasonably reject it on that basis.

### Q32. Is the minutes forecast E[minutes] or E[minutes | active]?
If the champion forecasts minutes conditional on playing, then multiplying by a points-per-minute rate
gives E[points | active], not E[points]. Combining that with `p_active` requires knowing which quantity
each component is. Nobody has written down the joint decomposition. | **STRUCTURAL** | minutes, points,
availability | Score-only; `p_active` exists in both arms (D088). | T6: "we assume the model forecasts
the conditional mean" is an assumption that cannot fail unless tested against emitted values. | Not a
signal; a correctness question whose answer changes how every downstream product is formed. | cheap |
D090 ruled `p_active` adds nothing **to abstention**. That is a different question from whether the
minutes and availability forecasts compose correctly.

### Q33. Gate every candidate on **holdout constructibility** before screening it
Verified: raw pbp covers 91.5% of exploration games (888/970) but **20.6% of holdout games** (108/525),
and **0 of 215 games in 2026**. A lead built on raw pbp can be discovered and can **never be
confirmed**. `possessions.parquet` and `data/shotcharts/` do **not** have this gap (100% and all-season
respectively), so the constraint is source-specific and checkable. | **METHODOLOGICAL** | all | Verified
counts above. | T4: this is reference-incompleteness in the *time* dimension. | Prevents spending an
entire screen on something unconfirmable. | cheap | Not recorded anywhere. Should become a standing
line in every screen's feasibility section, alongside the manifest gate.

### Q34. Model free throws as a hurdle, not a rate
`fta == 0` on **46.4%** of played rows and `fouls_drawn == 0` on **30.5%**; `ftm` variance/mean is 2.87
with **49.3% zeros**. An EWMA of "FT rate" over a series that is zero half the time estimates a quantity
that does not exist for half the sample. | **FEATURE** | free throws, points | 100% covered all seasons. |
T7: carries Q5's ceiling. T2/T3: player-level cyclic null. | Sub-component of Q5's ceiling; queued
separately because the hurdle framing is the part most likely to be skipped. | medium | Never screened
(see Q5). Kept distinct from Q5 so that a screener who takes Q5 cannot quietly implement a continuous
rate.

### Q35. The program centres on MAE and dR2 and has never looked at the error **distribution**
D057 demoted global MAE as the psychological centre in favour of conditional edge plus abstention, and
D090 showed `p_active`'s error is 98% discrimination and 2% miscalibration. But for the continuous
targets, nobody has characterised the residual's tails, skew or heteroskedasticity. A bettor is exposed
to the tail, not the mean. | **STRUCTURAL** | points, minutes | Scored frames exist
(`E0_I0015/decomp_frame.parquet`, `E0_I0019/scored_frame.parquet`). | T8: a distributional improvement
is not a skill improvement and must not be reported as one — this trap is the entry's main risk. | Does
not raise dR2; changes what the forecast can be used for. | cheap | D057 pointed at conditional edge and
abstention; the distributional half was never picked up.

### Q36. Teammate absence **type** should moderate usage redistribution
D089's channel measures teammate volume. But usage vacated by a player out with a **season-ending ACL**
redistributes differently from usage vacated by a **one-game coach's decision** — the first triggers a
role change, the second does not. `dnp_reason` separates these on 100% of the 5,384 DNP rows. |
**FEATURE, extends the best lead** | points, minutes | `dnp_reason` 22 values, 100% populated on DNP rows;
`injury_history.csv` gives dated spells with type. **Strictly-prior use only** — the teammate's *prior*
absence spells, not tonight's. | T1: this is the trap that would kill the entry — tonight's `dnp_reason`
is post-game. T4: must be measured as an increment over the prior-only volume variant, not over a naive
reference. | A moderator on a channel whose usable ceiling is 0.0021; realistically a fraction of that. |
medium | I0006 ("usage redistribution conditional on teammate composition") was proposed and screened as
composition; **absence type** was never a dimension of it.

### Q37. What does the champion shrink toward, and is that target itself degenerate?
The cold-start constant (D092) is the visible symptom of a shrinkage target. Every hierarchical estimator
has one, and if the target is a pooled mean computed over a population that does not resemble the row
being scored, the shrinkage does harm that grows as history thins. | **STRUCTURAL** | points, minutes |
Score-only, plus reading the champion's emitted values. | T6: "the model shrinks toward the league mean"
is an assumption; it must be recovered from emitted values. | Directly generalises the finding that
produced the program's largest free gain. Closely related to Q2 and should be dispatched with it. | cheap |
D092 found the constant; it did not ask what mechanism produces it or where else that mechanism applies.

### Q38. Does a lead measured on 2021–2024 hold **across seasons within** the partition?
Every lead is currently a pooled 2021–2024 number. Per-season stability is the cheapest available
robustness evidence and does not touch the holdout. Some screens computed it
(`E1_I0020/per_season_stability.csv`, `E0_I0019/per_season_metrics.csv`); it is not standard. |
**METHODOLOGICAL** | all | Score-only; 4 seasons, 209/239/260/262 games. | T2: 4 seasons is a small
number of clusters and a season-level null has almost no power — this must be reported as descriptive,
not as a test. | Protects against a lead driven by one season. | cheap | Not standard practice; should be.

### Q39. Foul trouble truncates exposure and is a distinct channel from minutes
`pf` and `pf_misc` are 100% covered. A player in foul trouble is removed regardless of role or game
script — a truncation mechanism separate from both blowout truncation (Q27) and rotation role (Q12). |
**FEATURE** | minutes | 100% covered all seasons; `possessions.parquet` gives the timing to distinguish
early fouls from late. | T1: **tonight's** fouls are post-game; only the player's prior foul rate and the
opponent's prior foul-drawing rate are admissible. T4: prior foul rate correlates with minutes, so the
reference must contain prior minutes. | Small; a moderator on the one target with skill. | medium |
Not in D076's 348 cells (which covered schedule, churn, unfamiliarity, role volatility) and not in
D085's basketball-specific set (which targeted **efficiency**, not minutes).

### Q40. Separate "the coach removed them" from "that is their role"
Two players averaging 20 minutes are different if one plays 20 every night and the other alternates 32
and 8. D076 screened `pl_min_sd5` and `pl_min_cv5` and found large abs(t) with **negative** skill gain at
every coverage, concluding they are volume proxies. That is a finding about those two constructions, not
about the underlying distinction, which is *why* the variance occurs — game script and foul trouble
(exogenous) versus rotation change (persistent). | **STRUCTURAL** | minutes | `possessions.parquet` margin
and `stints.parquet` give the mechanism; `master_player.minutes` gives the outcome. | T1: mechanism
attribution uses realised within-game facts, so it can define a **prior-game** feature only after the
prior game is complete — which is legitimate. T8: D076's failure here was exactly T8 and must not be
repeated. | Bounded by the minutes target; the honest prior is low given D076's result. | medium |
Queued with D076's negative stated up front. The argument is that the kill mechanism was
`CONSTRUCTION` (volume proxies), not a real null on the distinction.

### Q41. Opponent possession supply may matter for **rebounds** even though it is dead for points and assists
The possession-volume family is closed — all 27 constructions — but it was closed on **assists** (D073)
and on points-adjacent targets. Rebound opportunity is more mechanically tied to possession count than
any other box quantity: more possessions means more missed shots means more rebound chances. |
**FEATURE** | rebounds | `master_team.parquet` and `possessions.parquet`; `oreb`/`dreb` 100% covered. |
T4: **the D073 decomposition (Q11) must be run first** — if the effect sits in the team-season pace level,
it is the same dead thing wearing a rebound label. T7: `oreb` perfect-forecast bound on points is 0.0763,
but the target is rebounds. | Modest, and the D073 precedent is genuinely discouraging. | medium |
**GATED** by `E0_I0024_reb_ast_characterisation` (running) and by Q11. Queued low deliberately: D073
closed the family with "Do not re-screen it", and the only thing distinguishing this is the target.

### Q42. Price the acquisition: what would a real pre-game inactives feed be worth?
D089 ruling 3 names a pre-game injury/inactives feed as "the single highest-value data acquisition the
program has identified", and D023's amendment (1) shows the user wants acquisition questions answered
with verification rather than assumption. The value is **already bounded by measurement**: the tip-time
variant of the volume channel scores 0.0078 and the prior-only variant 0.0023. | **METHODOLOGICAL /
ACQUISITION** | points, minutes, availability | The bound already exists in
`E1_I0018_teammate_volume_channel/tiptime_loss_ladder.csv`. | T1: the tip-time variant **may never be
quoted as a result** (D089 ruling 2) — it is an upper bound only, and this entry exists precisely to use
it as one. | Not a screen; a decision packet. | cheap | **ACQUISITION FLAG: a pre-game injury report /
inactives feed for 2021–2024.** Also worth naming: **historical odds for 2021–2024**, absent per D071/D073
(`bookie_totals_per_game.csv` has zero in-partition rows; `totals_head/game_level_totals.csv` has 229
rows dated 2024 with `bookie_consensus_total` **100% NULL**), which is what currently makes market
comparison impossible on the exploration partition. Q7 should be run **first**, since it may recover part
of the gap for free and would change what the acquisition is worth.

### Q43. Does the 2021 opening-day exclusion still flatter every cold-start figure?
D010 confirmed the possession universe excludes the four games of 2021-05-14 — the single hardest
cold-start day — and ruled that "every cold-start coverage figure computed on this universe is FLATTERED
BY CONSTRUCTION". The cold-start work (D092) is now the program's most actionable finding. | **STRUCTURAL** |
points, minutes | `master_player` holds 1,495 games; `possessions.parquet` also holds 1,495. The
1,491-game universe is a *derived* frame — this entry checks which frame the cold-start screens actually
used. | T5: settle on values, not on a filename. | If the cold-start tier rule was measured on the
flattered universe, its validated gain is a slight over-statement. Small, but it touches the one rule
headed for production. | cheap | D010 recorded the consequence and no screen has confirmed which universe
it used.

### Q44. College and country as a zero-history prior
`player_bios.csv` carries `college` (87.7%) and `country` (99.2%). For a player with no WNBA history,
college programme and international background are the only signals available beyond draft slot. |
**FEATURE** | points, minutes | Bios 100% joinable. | T2: null at player level. T7: **the population is
384 rows (1.36%)** — this is very close to unable to clear the bar. | Very small, and D092 already ruled
the debut population is "small, already largely abstained on, and mostly veterans". | cheap |
**Ranked last deliberately.** D092 ruling 3 directs cold-start effort at 1–2 prior appearances rather
than debuts, which is precisely where this entry does *not* apply. Included only because it is cheap and
completes the bios surface; a coordinator should feel free to move it to `CUT_LIST.md`.

---

## Dispatch notes for the coordinator

**Run these first, in this order** — each one changes how the rest should be read:
1. **Q4 (detection floor)** — tells you whether any of the small-ceiling entries are worth screening.
2. **Q1 (era confound)** — tells you whether E2 confirmation means anything.
3. **Q30 (possessions provenance)** — gates Q15, Q22, Q23, Q41.
4. **Q3 (reference ladder)** — every subsequent screen should consume it rather than choosing its own.
5. **Q9 + Q19 (cyclic re-audit, control audit)** — protect what is already recorded.

**Cheap and independent, good for unattended running:** Q8, Q10, Q13, Q17, Q26, Q29, Q32, Q33, Q38, Q43.

**Do not dispatch without re-scoping against a running screen:** Q23 and Q41 (vs
`E0_I0024_reb_ast_characterisation`); Q3 (vs `E1_I0022_optimal_simple_estimator`).

**Highest risk of re-screening dead ground:** Q22, Q31, Q40, Q41 — each is queued with its
closed-surface neighbour named and its escape argument stated, so the argument can be rejected on
inspection rather than after a screen.
