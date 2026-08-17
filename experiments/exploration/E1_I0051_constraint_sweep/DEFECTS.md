# DEFECTS — E1_I0051_constraint_sweep

Self-reported. Every defect found in this screen's own machinery or reasoning, including the ones
that weaken its headline. `PREREG.md` sha256
`05b1e7ec055eb7f1442baf13aa76da760d0f78be6ba71bdda85b956489ca8c5f`.

---

## D-01 — this screen's own preregistration named an anchor WITHOUT ITS ROW SET · **DISCLOSED, ANCHOR DEMOTED, NOT REPAIRED BY SEARCHING**

`PREREG.md` §7 anchor **A11** required *"median `Σ` player possessions ÷ (5 × team possessions) =
**0.992**"* from `E0_I0012`. It did not state the row set.

**That is a D101 violation inside a preregistration whose §5.7 makes D101 mandatory for every
number.** The programme has been caught by exactly this four times in one day, including a case
where pure noise reached 0.987× the floor in use because a six-column statistic met a one-column
floor.

**Measured.** On all 1,776 regular-season team-games 2021–2024: median **0.993217**, p05 **0.947**,
p95 **1.031**, against `E0_I0012`'s **0.992 / 0.960 / 1.023**. `E0_I0012`'s spread is **narrower
than any unfiltered construction can produce**, which is the signature of a filtered analysis frame
(theirs is ~10,167 analysis rows against my 16,717 appeared player-games).

**Six explicit row-set and estimator variants were enumerated in `s01b_a11.py` and NONE matches**
(`A11_ROWSET_DIAGNOSTIC.csv`). **The search was stopped there.** Continuing would have been fitting
a construction to a target, which is the failure mode the anchor exists to prevent.

**Effect on this screen: none, and the reason is checkable.** Possessions **fail the §3 budget gate**
(team-game sum cv 0.0546, no rules lattice) and are re-measured nowhere. **12 of the other 13
anchors reproduce, two at exactly `0.000e+00` and D104's home advantage at `|d| = 9.01e-08`.**

**A11 is recorded as a NON-REPRODUCTION, not as a pass and not as a failure of `E0_I0012`.**

---

## D-02 — a SIBLING SCREEN ON THE SAME RESPONSE WAS RUNNING CONCURRENTLY AND THIS SCREEN DID NOT KNOW · **DISCLOSED; the collision is the finding's own corroboration and its own duplication**

`E1_I0053_minutes` did not exist when this screen's census sweep began. It was created by a sibling
agent **while `s03` was running**, and it was caught **only because `s04_census.py` enumerates the
directory rather than trusting a typed list** — the assertion fired and halted the census.

`E1_I0053_minutes/PREREG.md` is hashed and carries: minutes as **both** a level (`R1_min`) and a
share (`R2_smin`), **RAW and PROJ arms**, a tuned walk-forward reference, the **same** 2023–24 clean
window and the **same** 3,167-row decision stratum. **That is this screen's §5 re-measurement.**

**Both readings are true and both are reported:**

* **Corroboration.** Two agents, working independently with different briefs, both selected
  **minutes** as the response worth projecting. This screen selected it by a preregistered measured
  gate; the sibling selected it because every positive result in the programme points there. That
  is convergent evidence that the gate is picking the right response.
* **Duplication.** `E1_I0053` is the **dedicated** minutes screen. It tunes the reference against
  more comparators (`TUNED_vs_NAIVE`, `TUNED_vs_TRAIL5`, `TUNED_vs_UNIFORM`) and is more thorough on
  that response than this sweep is. **Where the two disagree, prefer `E1_I0053`.**

**This screen's distinctive axis is the one `E1_I0053`'s prereg does not carry: the separation of
`PROJ_BUDGET` (200, live-available before tip-off) from `PROJ_ORACLE` (the realised total).** That
distinction is what makes the projection here an implementable operation rather than an oracle
ceiling, and it is the part worth keeping if the two screens are ever merged.

**No file of `E1_I0053` was written, moved or modified. It was read only, and only its `PREREG.md`
header and its file listing.**

---

## D-03 — A13, the load-bearing anchor, DID NOT REPRODUCE QUANTITATIVELY · **DISCLOSED; demoted to a qualitative corroboration**

`PREREG.md` §7 called A13 *"the load-bearing one"*: `E1_I0034`/`E1_I0042`'s published finding that a
team's remaining players' trailing-form minutes sum to **198.96 / 201.08 / 201.50 / 191.44 /
184.02** across five absence buckets, i.e. to **250 against a 200-minute budget** in heavy-absence
games.

**It cannot be reproduced from `master_player`.** `E1_I0034` defines `ESTABLISHED` over the
**champion's obligation universe** — *"champion candidate rows for `g` with ≥3 strictly-prior
same-season appearances and a `base5`"* — and that universe lives in the `cbs_*` artifacts, not in
the masters. This screen's closest available reconstruction gives:

| bucket | team-games | Σ trailing-5 (mine) | Σ trailing-5 (**published**) | slack (mine) | realised gain (mine) | realised gain (**published**) |
|---|---:|---:|---:|---:|---:|---:|
| none | 274 | **133.07** | *198.96* | +66.93 | −6.60 | *−3.24* |
| 0–15 | 223 | 202.36 | *201.08* | −2.36 | −4.40 | *−2.59* |
| 15–30 | 201 | 194.51 | *201.50* | +5.49 | +1.05 | *−3.01* |
| 30–45 | 140 | 184.15 | *191.44* | +15.85 | +11.02 | *+6.36* |
| 45+ | 122 | 172.88 | *184.02* | +27.12 | **+16.75** | *+15.47* |

**The `none` bucket is badly wrong** (133.07 against 198.96) and the reason is identified: my
`ESTABLISHED` requires ≥3 prior appearances *for this team* **and** a last appearance within the
previous 5 team-games, so early-season team-games enter the `none` bucket with a mean of only
**6.30** established players against `E1_I0034`'s **10.51**. That is a construction difference, not
a contradiction.

**The qualitative gradient does reproduce, and it is the part this screen relies on:** slack against
the 200-minute budget rises monotonically with absence (−2.36 → +5.49 → +15.85 → +27.12) and
realised gain rises with it (−4.40 → +1.05 → +11.02 → +16.75), with the top bucket's realised gain
landing at **+16.75 against a published +15.47**.

**Consequence, and it is the conservative direction: A13 is quoted nowhere as a reproduction.** The
census entry for `E1_I0034` rests on that screen's **own published sentence** — *"a team's
trailing-form minutes do not sum to 200 — they sum to 199 when everyone is healthy and to 250 when
three rotation players are out"* — which is a direct quotation and needs no reproduction.

---

## D-04 — the projection is applied AFTER the fit, not inside it · **NOT A BUG; it is what makes the comparison fair, and it caps what the result can claim**

Both arms fit in **RAW** space and the projection is applied to the resulting forecast. A model that
were compositional *by construction* would fit under the constraint and would not lose anything to a
post-hoc projection step.

This matters in two directions and both are stated:

* **It is what makes the RAW-vs-PROJ contrast a clean one.** The base arm, the augmented arm and
  **every one of the 2,000 null draws** pass through the identical projection, so the projection can
  advantage neither side. Nothing in the sign-flip table is an artefact of one arm being projected
  and another not.
* **It means the UNFROZEN arm is optimising the wrong objective.** The refit minimises RAW SSE and
  the projection is then applied on top. That is exactly the construction every violating screen in
  the census used, so it is the right thing to measure — but it is **not** the best achievable
  projected forecast, and no number here should be read as one. `E1_I0046`'s `NOTES.md` §9 makes the
  same point about its own projection.

---

## D-05 — the projection needs the REALISED ROSTER, which is not available before tip-off · **DECLARED IN THE PREREG, restated here, and it is the single largest limitation**

`PROJ_BUDGET` needs two things: the budget (**200 — live-available, MAE 0.63091 % of the total**)
and the denominator set `C(g)`, **the roster that actually appears**. The second is an oracle.

`E1_I0046`'s `DEFECTS.md` D-07 grants **two** oracles and says eleven times that no number in it is
an achievable live increment. **This screen grants one.** That is a genuine improvement and it is
not a clean bill of health: **a live projection would have to run over a forecast roster, and this
programme's own availability forecast sums to 10.34 players where 9.40 play.**

**The honest statement is: the budget half of the constraint is implementable today and the roster
half is not.** Every projected number in `VERDICT.md` carries that qualification.

---

## D-06 — the RAW arm's team-game sums are unbiased in the MEAN, which is why nobody caught this · **NOT A DEFECT OF THIS SCREEN; recorded because it explains the whole census**

An independently-modelled minutes forecast summed over the appeared roster has **mean 201.55**
against a budget of 200 — apparently fine. Its **MAE against the budget is 13.09 minutes** and it
lands within 5 minutes of the budget on only **28.5 %** of team-games (`BUDGET_VIOLATION.csv`, base
`h=3, k=0`).

**The errors cancel in the mean and nobody checked the dispersion.** This is the same shape as
D112's finding that `p_active` was checked one player at a time and never summed, and the same shape
as `E1_I0035`'s invariant that *"AUC is never sufficient for a forecast that will be summed"*. It is
recorded here because it is the reason eleven screens modelled minutes against a hard budget without
noticing.

---

## D-07 — the census classification is a JUDGEMENT, and two rows could not be settled · **DISCLOSED**

`CONSTRAINT_CENSUS.csv` carries 85 response rows over 67 screen directories. Each classification is
a judgement recorded with the verbatim evidence that supports it, and the **screen list is
enumerated from the filesystem with a halting assertion in both directions**, so no screen can be
silently omitted — which is how D-02 was caught.

**One row was NOT-DETERMINABLE from the documents and was RESOLVED BY READING THE SOURCE**, which is
how this programme's sibling audits have resolved most such cases:

* **`E1_I0004_shot_selection`** — `NOT-DETERMINABLE → VIOLATED`. Its `share_z` response is a genuine
  5-zone simplex within each player-game, and its documents do not say whether the forecast respects
  it. The code does: `analyze.py:200` and `dr2_playergame.py:69` both loop `for z in ZONES:` and fit
  **five independent per-zone regressions** with nothing tying the predictions to 1. **And it is
  provable rather than merely unchecked** — the regressor `OS_z` is built so that `Σ_z OS_z = 0`,
  making the fitted increment `Σ_z b_z·OS_z` identically zero only if all five `b_z` are equal;
  they are `+0.774 / +0.653 / +0.556 / +0.325 / +0.563`, spread by more than 2×. **The five fitted
  shares provably do not sum to 1.** See `NOTES.md` §4. **It was not re-measured here.**

**One row remains NOT-DETERMINABLE and is reported as such rather than guessed:**

* **`E1_I0050_queue_typeI`** — the screen is at `s00` only, contains no markdown at all, and states
  no response. NOT-DETERMINABLE because it is **incomplete**, not because the evidence is ambiguous.

`E1_I0004_efficiency_transfer` is **excluded from every count** because its own `ABANDONED.md`
declares that *"any number, any contrast, any p-value, any verdict"* must not be reused.

---

## D-08 — a factual drift is LIVE IN THE DECISION LEDGER at D111, and this screen was handed it · **TRACED AND CORRECTED; see `NOTES.md` §5**

The commissioning brief stated: *"**possessions** — D104 established these are IDENTICAL for both
teams in 970 of 970 games."* **D104 does not say that.** It is a drift, and it did not originate in
the brief.

**D104 itself keeps the two claims strictly separate** (`DECISION_LEDGER.jsonl`, D104):

* minutes — *"TEAM MINUTES ARE IDENTICAL FOR BOTH TEAMS IN 970 OF 970 GAMES (200, plus 25 per
  SHARED overtime). The gap is exactly zero."*
* possessions — *"**POSSESSIONS ARE A SHARED GAME PROPERTY.** The gap is **+0.135 at p 0.165**, and
  corr(home possessions, away possessions) is 0.816."*

The source screen's own code is even more careful — `E1_I0030/ha_base.py`: *"**THIS IS AN ESTIMATE,
NOT THE IDENTITY.** Real possessions are equal between the two teams in a game **to within one**;
this estimator is not, because the 0.44 coefficient and the OREB term are approximations."*

**Where the drift is.** It first appears in **D111's own ledger text**, and it is still there:

> `DECISION_LEDGER.jsonl`, D111: *"Shot attempts come out of 200 shared team minutes and **a
> possession count D104 established is IDENTICAL FOR BOTH TEAMS IN 970 OF 970 GAMES** — modelling
> players separately DISCARDS THAT CONSTRAINT, and that is why attempts pay the largest penalty."*

The same sentence is in `GRAPH_EVENTS.jsonl` and in two verbatim copies inside
`E1_I0034_redistribution/_ledger_extract.json` and
`E1_I0038_within_entity_null_audit/scripts/_ledger_dump.txt`. **Anything reading D111 forward reads
it**, and there it is *load-bearing*: it is the stated mechanism for why field-goal attempts carry
the largest bottom-up penalty (49.6 %).

**Measured here, and stated at its true strength.** The standard box possessions estimator differs
between the two sides of the same game by **mean 2.2771, sd 1.7433, max 10.12**, and is exactly
equal in only **0.45 %** of the 888 regular-season games (`out/s00.txt`).

**What that does and does not establish, carefully.** It shows the *estimator* is not an identity;
it does **not** show that true possessions differ, because possessions alternate and D104's own
finding — equal *to within one* — is almost certainly right. **The error is one of strength, not of
direction: "a shared game property, equal to within one" became "IDENTICAL in 970 of 970 games",
and the 970/970 figure was borrowed from the minutes result on the same page.**

**D111's ruling is not overturned.** Its conclusion rests on two supports and only one is
overstated: the 200-minute budget is genuinely a hard identity, and possessions are genuinely
shared. **But a screen that took the brief at its word would have spent its effort projecting
possessions, which fail the §3 budget gate on their own measured cv (0.0546, no rules lattice), and
would have found nothing.** That is how close this screen came to measuring the wrong quantity.

**Recorded as a correction to the ledger's restatement, not as a finding against D104 or
`E1_I0030`, both of which are precise. No ledger file was modified — that is not this screen's
write scope.**

---

## D-09 — the sign flip is NOT uniformly established, and the bootstrap says so · **THE HEADLINE'S OWN COUNTERWEIGHT**

Three of five candidates flip sign under projection. **They are not equally solid**, and the block
bootstrap over 764 team-game blocks (`BOOTSTRAP_VARIANCE.csv`) separates them:

| candidate, `M_level_min` UNFROZEN, DECISION × CLEAN | RAW | PROJ_BUDGET | boot sd | **t** | MDE80 boot | **|obs| ÷ floor** |
|---|---:|---:|---:|---:|---:|---:|
| `A4_vac_x_own` | +0.000877 | **−0.018404** | 0.002233 | **−8.24** | 0.006253 | **2.94×** |
| `A1_pts_share_prior` | +0.004501 | **−0.005456** | 0.001855 | −2.94 | 0.005193 | **1.05×** |
| `A2_fga_share_prior` | +0.004210 | **−0.004702** | 0.001793 | −2.62 | 0.005021 | **0.94× — BELOW ITS OWN FLOOR** |

**`A2`'s flip does not clear its own bootstrap floor and is NOT ESTABLISHED under that variance
estimate. `A1`'s clears it by 5 %.** Only `A4`'s is comfortable. The headline "three of five flip"
is therefore **one established flip, one marginal, and one that a preregistered bootstrap does not
support** — and `VERDICT.md` says so in the same table as the headline.

---

## D-10 — `A4_vac_x_own` shares a construction with the base, and the RAW arm is where that matters · **DISCLOSED**

`A4_vac_x_own` is built as `own prior points share × vacated prior points share`. On the **minutes**
response the candidate is not the base's own channel (the base is a prior minutes EWMA), so the
same-channel trap `E1_I0046` recorded as its D-02 does not fire here.

But `A4` is a **product of a level and a team-game quantity**, so its within-team-game variation is
driven partly by `own prior share`, which is correlated with the base. In the **RAW** arm the
unfrozen refit can absorb most of it — which is exactly what the numbers show: RAW UNFROZEN
**+0.000877 with a bootstrap `t` of +0.19**, i.e. nothing at all. **`A4` measured RAW is not an
effect; it becomes one only under projection, and with the opposite sign.** That is the finding, and
it is also the reason the cell deserves the extra scrutiny D-09 gives it.
