# NOTES — E1_I0051_constraint_sweep

`PREREG.md` sha256 `05b1e7ec055eb7f1442baf13aa76da760d0f78be6ba71bdda85b956489ca8c5f`, 21,909
bytes. Read `VERDICT.md` first, then `CONSTRAINT_CENSUS.csv`, then `DEFECTS.md`. This file is the
audit trail.

---

## 1. WHAT CHANGED AFTER THE HASH, AND WHICH WAY IT PUSHED

**0 preregistered cells dropped. 2 additions and 2 demotions.**

| change | why | direction |
|---|---|---|
| **A11 DEMOTED** from a halt-anchor to a disclosed non-reproduction | the preregistration named the anchor **without its row set**, which is a D101 violation inside a prereg whose §5.7 makes D101 mandatory. Six explicit row-set variants were enumerated and none matched; the search was **stopped** rather than continued. | **NEUTRAL on the headline, WEAKENING on the discipline record.** `DEFECTS.md` D-01. |
| **A13 DEMOTED** from "the load-bearing one" to a qualitative corroboration | `E1_I0034` defines `ESTABLISHED` over the **champion's obligation universe**, which is not reachable from `master_player`. The reconstruction's `none` bucket is badly wrong (133.07 against 198.96). | **WEAKENING.** The census entry it was meant to support now rests on a direct quotation instead. `DEFECTS.md` D-03. |
| **`E1_I0004_shot_selection` RECLASSIFIED** `NOT-DETERMINABLE → VIOLATED` | resolved by reading the **source** rather than the documents. See §4. | **STRENGTHENS the exposure count and WEAKENS the "nothing changes" headline.** It is the one exposed live lead, and it was **not re-measured**. |
| **`E1_I0052` and `E1_I0053` ADDED to the census** | they **did not exist** when the sweep began. Created by sibling agents mid-run and caught only because `s04_census.py` **enumerates the directory** with a halting assertion. | **WEAKENING.** `E1_I0053_minutes` is a direct duplication of this screen's re-measurement. `DEFECTS.md` D-02. |

**Fixed after the hash, not added:** the candidate prior halflife is **5**, fixed and never tuned,
identical to `E1_I0046`'s so its published `R2_s_min` cells remain reachable.

---

## 2. WHY THE RESPONSE IS WHAT IT IS, AND WHY MOST SCREENS ARE NOT EXPOSED

The whole screen turns on one distinction, fixed in `PREREG.md` §2 **before the census**:

> A response is constrained only if its components sum to something **fixed at a higher level** —
> determined independently of the components themselves.

`E1_I0046` demonstrated sign reversal on a **share** response. But that screen *created* its own
constraint: it chose `s_i = y_i / Σ_j y_j` and conditioned on the realised team total, which is why
its `DEFECTS.md` D-07 grants two oracles and why the screen says eleven times that no number in it
is an achievable live increment.

**Player points sum to the team's points, but the team's points are the outcome.** Modelling ten
players separately implies a team total; it does not break a budget. The same is true of attempts
and rebounds. **Player minutes are different, and the difference is arithmetic rather than
rhetorical**: 200 in regulation, +25 per overtime, set by the rules before anyone tips off.

Measured, `out/s00.txt`, and this is the gate:

* `T_min` lands within **0.066667** minutes of a multiple of 25 on **1,776 of 1,776** team-games —
  four seconds, the minute:second rounding artefact `E1_I0046` also records at `max |diff| 0.066667`
  against the box.
* **95.2703 %** are at exactly 200.
* Asserting 200 for every team-game costs **MAE 1.26984 minutes = 0.631 %** of the budget.
* The same assertion on points costs **10.686 %**, on attempts **7.256 %**.

**That order-of-magnitude gap is the census.** Minutes passes; nothing else does.

### The two uses of a realised quantity, kept apart

| use | status |
|---|---|
| `B_live = 200` as the projection target | **LEGITIMATE AND LIVE.** No game information. |
| `B_rules = 25·round(T_min/25)` — the overtime count | **ORACLE**, carried only as `PROJ_ORACLE`'s upper bound and never as a headline. |
| `C(g)`, the appeared roster, as the projection denominator | **ORACLE.** `DEFECTS.md` D-05. **This is the screen's largest limitation.** |
| any base or candidate column reading a same-game quantity | **FORBIDDEN, and none does.** Every feature is an explicit `.shift(1)`. |

---

## 3. THE PROJECTION — WHAT WAS ACTUALLY DONE

* `ŷ_i ← B_g · max(ŷ_i,0) / Σ_{j∈C(g)} max(ŷ_j,0)`, with `B_g = 200` (`PROJ_BUDGET`) or the
  realised `T_min(g)` (`PROJ_ORACLE`). Fallback to `B_g/|C(g)|` if a team-game's projected sum is
  zero; this never fired.
* Applied **identically** to the base arm, the augmented arm and **every one of the 2,000 null
  draws**, so it can advantage neither side.
* Blocking is always at the **team-game**, never the row.
* The **RAW arm is reported beside every cell** — the "model them separately" construction — and the
  difference is the deliverable.

**Both arms fit in RAW space and the projection is applied afterwards.** That is deliberate: it is
exactly the construction the eleven violating screens used, which makes it the right thing to
measure. It is also why the UNFROZEN arm goes negative under projection while the FROZEN arm goes
strongly positive — the unfrozen refit is optimising RAW SSE and the projection is applied on top of
an objective that did not know about it (`DEFECTS.md` D-04). **A model compositional by construction
would not lose that, and no number here should be read as the best achievable projected forecast.**

**A log-ratio transform was available here and was still not used.** Minutes has **zero** exact
zeros among appeared player-games (measured, `out/s00.txt`), unlike points (2,506) and attempts
(1,020), so `alr` was genuinely open. Projection was chosen anyway because it has **no free
parameter** and the comparison had to be identical across arms and draws. **Recorded as a choice,
not a necessity.**

---

## 4. THE RECLASSIFICATION OF `E1_I0004_shot_selection`

Its `share_z` response is a genuine five-zone simplex inside every player-game. Its documents do not
say whether the *forecast* respects it, and this screen first recorded it `NOT-DETERMINABLE`.
Reading the source settles it:

* `analyze.py:200` — `for z in ZONES:` → a separate degree-1 `np.polyfit` per zone.
* `dr2_playergame.py:69` — `for z in ZONES:` → five separate `lstsq` fits of `z_att` on
  `1 + S1·fga (+ fga·OS)`. **Nothing ties the five predicted attempt counts to `fga`.**
* A case-insensitive search of the whole directory for
  `softmax|multinomial|dirichlet|simplex|renorm|normalis|normaliz|"sum to 1"|jointly|compositional`
  returns **one hit**: the word *compositional* in `NOTES.md:167`, used to motivate a **confound
  test**, not a constraint.
* `NOTES.md:149–155` reports the result as a five-row table with a different `beta` and `R²` per
  zone.

**And the violation is provable rather than merely unchecked.** `OS_z` is built at
`build_frames.py:463,476` as `pre_z/pre_tot − lg_share_prior_z`. Both terms sum to 1 across zones,
so **`Σ_z OS_z = 0` by construction**. The fitted increment to the share vector is `Σ_z b_z·OS_z`,
identically zero **only if all five `b_z` are equal**. The five are
`+0.774 / +0.653 / +0.556 / +0.325 / +0.563` — spread by more than 2×. **The five fitted shares
provably do not sum to 1, and the screen never checks it and never mentions it.**

**Its null is valid on the regressor side and never exercises the response simplex.** The headline
null permutes **team labels within season**, carrying the whole five-zone allowance vector with the
team (`analyze.py:171-178`), which preserves the regressor's cross-zone correlation deliberately.
**The response `y` is never permuted anywhere in that experiment.** The row-shuffled contrast null
scatters the five `OS_z` of one player-game to five unrelated player-games, destroying the
`Σ_z OS_z = 0` structure; it is labelled *"NAIVE, KNOWN-TOO-NARROW"* there and carries no p-value.

**IT WAS NOT RE-MEASURED HERE.** The preregistered §4 selection rule sent the re-measurement budget
to the response that passed a **measured** gate. Re-measuring `share_z` under projection needs the
132,558-shot frame and a different construction. **This is a flag. Nothing here says the lead is
wrong**, and the direction the constraint would push it is not predictable from the RAW number —
which is the whole point of the exercise.

---

## 5. THE DRIFT IN THE BRIEF, TRACED TO THE LEDGER

The brief said *"**possessions** — D104 established these are IDENTICAL for both teams in 970 of 970
games."*

**D104 does not say that**, and neither does `E1_I0030`, the screen behind it. Both keep two claims
apart: **minutes** are identical in 970 of 970 games with the gap exactly zero; **possessions** are
*"a shared game property"* with a gap of **+0.135 at p 0.165** and `corr = 0.816`. `E1_I0030`'s own
code says *"THIS IS AN ESTIMATE, NOT THE IDENTITY."*

**The drift is in D111's ledger text and it is still live:**

> *"Shot attempts come out of 200 shared team minutes and a possession count D104 established is
> IDENTICAL FOR BOTH TEAMS IN 970 OF 970 GAMES — modelling players separately DISCARDS THAT
> CONSTRAINT, and that is why attempts pay the largest penalty."*

The `970 of 970` figure was borrowed from the minutes result on the same page. The same sentence is
in `GRAPH_EVENTS.jsonl` and in two verbatim ledger copies inside other screens' directories.

**Measured here**: the box possessions estimator differs between the two sides of the same game by
**mean 2.2771, sd 1.7433, max 10.12**, exactly equal in **0.45 %** of 888 regular-season games.
**That refutes the estimator being an identity; it does not refute D104**, whose actual claim —
equal to within one — is almost certainly right. **The error is one of strength, not direction.**

**D111's ruling is not overturned**: it rests on two supports and the 200-minute one is a genuine
hard identity. But a screen taking the brief at its word would have projected possessions, which
**fail the §3 budget gate** on their own measured cv of 0.0546, and found nothing. **No ledger file
was modified. That is not this screen's write scope.**

---

## 6. NULLS — WHAT EACH TESTS AND WHAT IT DOES NOT

| null | exchangeability tested | blocks | valid for | NOT valid for |
|---|---|---:|---|---|
| **`N_TGSWAP`** | which player *in this roster* holds which candidate value | 1,776 team-games | the five between-player candidates | anything team-game-constant — it is the **identity** there |
| **`N_PSWAP`** | which player owns a whole candidate **series**, inside the team-season | 48 team-seasons, 634 series | the same five, preserving serial structure | the same exclusion |
| `N_TGBLOCK` | which opponent this roster faced, calendar fixed | 335 dates | `A5_opp_defrtg` only | between-player candidates |
| `N_WITHIN_PLAYER` | — | 634 player-seasons | **nothing. CONTRAST ONLY.** | everything here |

**Every between-player verdict requires both `N_TGSWAP` and `N_PSWAP`.** D120 is satisfied by
construction: the family-wise max-z is computed from **one shared draw stream** — a single
permutation per draw applied to all five candidates simultaneously — so cross-candidate correlation
is preserved.

**The vacuous control fired exactly as preregistered.** `N_TGSWAP` on `A5_opp_defrtg` is the literal
identity: measured null sd **6.513e-19**, **2.171e-19**, and **exactly 0.000e+00** in one of four
cells. Reported as a control that cannot fail, not as a clean bill of health.

**The blind-null demonstration points the opposite way to `E1_I0046`'s**, which is the stronger
form of the point. There, a within-player null applied to a between-player candidate **manufactured**
a survivor at p 0.0020 with the sign reversed. Here it **destroys** one: `A1_pts_share_prior`
FROZEN/PROJ_BUDGET is +0.021110 with a correct-null z of **+30.48** and p 0.0025, and the blind
null returns **p 1.0000, z −3.19**, because its own null mean (**+0.030311**) sits *above* the
observed value. **A blind null is not conservatively wrong; it is arbitrarily wrong, in whichever
direction its own centre falls.**

---

## 7. FROZEN AND UNFROZEN — BOTH, EVERYWHERE, AND THEY DISAGREE

* **FROZEN**: intercept **and** base slope held at the base-only fit; only the candidate coefficient
  estimated, on the base's **training** residual, against a **train-mean-centred** candidate.
* **UNFROZEN**: all coefficients refit.

The mandate for the freeze was a prior component that *"scored +0.0287 at p 0.00005 on rows where it
substituted nothing"*, and `E1_I0046`'s surviving candidate running +0.005487 unfrozen against
−0.004696 frozen.

**Here the two arms disagree systematically and the disagreement is the finding**: under projection
every candidate is strongly positive frozen (`A1` +0.021110, z +28.49) and negative unfrozen (`A1`
−0.005456, z −4.92). **Three of five flip sign RAW→PROJ in the unfrozen arm; zero of five flip in
the frozen arm.** Both counts are in `VERDICT.md` §3 and in `SIGN_FLIPS.csv`, and the structural
reason is in `DEFECTS.md` D-04.

---

## 8. THE POWER PICTURE, HONESTLY

For the three flipped cells (`M_level_min` / UNFROZEN / DECISION × CLEAN, n = 3,167, 764 blocks):

| candidate | PROJ_BUDGET | permutation z | **bootstrap t** | MDE80 boot | **|obs| ÷ floor** |
|---|---:|---:|---:|---:|---:|
| `A4_vac_x_own` | −0.018404 | −5.90 | **−8.24** | 0.006253 | **2.94×** |
| `A1_pts_share_prior` | −0.005456 | −4.92 | −2.94 | 0.005193 | 1.05× |
| `A2_fga_share_prior` | −0.004702 | −4.11 | −2.62 | 0.005021 | **0.94×** |

**`A2`'s flip does not clear its own preregistered bootstrap floor.** The permutation null and the
block bootstrap disagree here as they did in `E1_I0046` (8.07× there). The two answer different
questions — the permutation asks whether the assignment carries information, the bootstrap asks
whether the *number* would replicate — and the direct evidence on replication is the season split,
where **all three are negative in every evaluation season** including the disclosed 2022 contrast.

**Block counts are never marginal.** The smallest is 48 (`N_PSWAP` team-seasons); the sign-flip and
projection contrasts carry 764 and 960.

**The programme constant `0.002057` is used nowhere.** `E1_I0049` established it is an in-sample
transported ceiling with no recorded bound. Every floor here is computed on this screen's own row
set and labelled `analytic` or `bootstrap`.

---

## 9. WHAT WAS NOT DONE, DELIBERATELY

* **No champion was fitted and no production change is proposed. No repair to `p_active` is enacted
  or recommended** — three options are already before the user and this screen adds no fourth.
* **The shared screen kit was not imported and not modified.** Sibling agents hold it open.
  Everything is reimplemented in `scripts/cs_base.py`, which credits
  `E1_I0046_allocation/scripts/al_base.py` as the source of its frame construction, projection, swap
  classes and `Cell`. That closeness is deliberate: it is what makes the anchors meaningful.
* **No name-based column selection anywhere.** Every list is an explicit literal with its length
  asserted against a literal (`RESPONSES` 2, `CANDIDATES` 6, `BETWEEN_PLAYER_CANDIDATES` 5,
  `ARMS_PROJ` 3, `MP_COLS` 14, `MT_COLS` 13). The census screen list is asserted against the
  filesystem **in both directions**, which is how two mid-run sibling screens were caught.
* **`E1_I0004_shot_selection` was flagged and not re-measured.** Stated in `VERDICT.md` §1.2 rather
  than buried.
* **2021 was never evaluated. 2025 and 2026 were never read, joined, merged or described.**
* **No process outside this screen was touched.** Two PIDs were launched and recorded
  (`scripts/_s03_pid.txt`, `scripts/_s05_pid.txt`); both exited on their own. **No
  `Get-Process | Stop-Process`, no `taskkill`, no blanket kill of any kind.** No `git` write command
  was issued.

---

## 10. WHAT WOULD MOVE THIS RESULT

1. **Re-measuring `E1_I0004_shot_selection` under a simplex-respecting fit.** It is the only
   violated screen with a live positive lead, the violation is provable, and the direction the
   constraint would push it is unknown. **This is the highest-value follow-up in the census.**
2. **An availability forecast that sums to a basketball team.** The projection's budget is live; its
   denominator set is not. Same rate-limiting input D089, D112 and `E1_I0046` all identified.
3. **`E1_I0053_minutes`.** The dedicated minutes screen was running concurrently with this one and
   covers the same response with more comparators. **Its numbers are the check on §3 of
   `VERDICT.md`, and where the two disagree, prefer it.**
4. **A minutes model that is compositional by construction.** The projection here is applied after a
   fit that did not know about it, which is why the two arms disagree. A model fitted under the
   constraint would not lose that, and given that the projection alone is worth +0.020020 pooled,
   that is where the next increment most plausibly lives.

---

## 11. FILE MAP

| file | what |
|---|---|
| `PREREG.md` / `PREREG.sha256` | the frozen design, including the §2 classification rule and the §4 selection rule |
| **`VERDICT.md`** | the exposure count and whether any published verdict changes, in the first three sentences |
| **`CONSTRAINT_CENSUS.csv`** | every response in every screen, its constraint, and its classification with verbatim evidence |
| **`SIGN_FLIPS.csv`** | before and after projection for everything re-measured, with both nulls, family-wise p, bootstrap floors and the season split |
| **`AVAILABILITY_AS_CONSTRAINT.md`** | D112 read as a constraint problem; P1 and P2 |
| `ANCHORS.csv` / `A11_ROWSET_DIAGNOSTIC.csv` | 13 anchors, 12 reproduced, 1 disclosed non-reproduction |
| `BUDGET_VIOLATION.csv` | what an independently-modelled minutes forecast actually sums to |
| `Q1_PROJECTION_EFFECT.csv` / `PROJECTION_SIGNFLIP.csv` | is the projection itself an improvement |
| `CEILING.csv` | the arithmetic ceiling per candidate per projection arm |
| `PRIMARY_CELLS.csv` | every response × candidate × arm × projection × population |
| `NULLS.csv` / `FAMILYWISE.csv` / `BLIND_NULL_DEMO.csv` | both matched nulls, the max-z family correction, the blind-null demonstration |
| `PLACEBOS.csv` / `RESPONSE_PLACEBO.csv` / `SEASON_STABILITY.csv` / `BOOTSTRAP_VARIANCE.csv` | controls |
| `A13_TRAILING_FORM_ACCOUNTING.csv` | the demoted A13 reconstruction, published including the bucket that fails |
| `AVAILABILITY_P1_TIGHTNESS.csv` / `AVAILABILITY_P2_CANCELLATION.csv` | the two preregistered predictions |
| `nulls/*.npz` | **raw, unstandardised, signed** draws; absolute values are never stored |
| `DEFECTS.md` | ten defects, including the one that most weakens the headline |
| `FINDINGS.json` | machine-readable, with sha256 of every `.md` and `.csv` in the directory |
| `scripts/` | `cs_base.py` + `s00`–`s06`, with the full captured `run_log_*.txt` for each |
