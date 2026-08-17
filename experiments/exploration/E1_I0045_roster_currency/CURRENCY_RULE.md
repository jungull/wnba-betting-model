# The roster-currency rule, measured against Xa at both levels

**E1_I0045_roster_currency.** Preregistration hash
`1695920776dcab1d1630baf0a3cafc5c6530fc37144ffd84296df3f8a2d6f909` — read `PREREG.md` §0 first, it
declares which parts of this were fixed in advance and which were not.
Regular season, 1,392 team-games, 20,084 player forecasts. 2025 and 2026 were never opened.
**No change was enacted. Every model change is the user's decision.**

---

## 0. THE DECISION-STRATUM INTERSECTION, FIRST

The commercially relevant stratum is ≥8 prior same-season appearances **and** trailing-5 mean
minutes ≥24 — rotation players with a track record, the ones a props market actually prices.

| | rows |
|---|---:|
| RS1P in the decision stratum | 4,964 of 20,084 (24.7 %) |
| of which **tier A** | 4,962 |
| of which **tier B** | **2** |
| **rows the currency rules R1–R3 remove from the decision stratum** | **0** |

**Say it plainly: this work is model hygiene, not a commercial gain.** The rows a roster-currency
rule touches are almost perfectly disjoint from the rows anyone would bet on. Two tier-B rows reach
the stratum and neither is removed by any rule that carries a verdict. Measured directly, the
decision-stratum Brier moves by **+0.000110** (full window) and **+0.000155** (clean) for both the
stratifying and the removing arm — against an injection-verified floor of 0.0005, with p = 1.0000.
**NOT ESTABLISHED, and it could not have been.**

This is the same shape as the prior screen that reported a headline gain and was later found to have
zero cold-start rows in the stratum. The difference is that this is stated before the headline, not
after someone checked.

---

## 1. What the rules are

Built from `master_player` alone, admitted through the contract's own +36 h availability bound,
compared to each row's own `forecast_cutoff` with a strict `<`. No transaction wire, no bios, no
`roster_asof` — see `PREREG.md` §3 for why each is excluded by rule rather than by preference.

* **`departed`** — she has an admitted appearance for **another** club later than her last admitted
  appearance for this one. *She has played for somebody else since she last played for you.*
* **`seasons_since_club ≥ 2`** — she has not appeared for this club since before last season.

| rule | drops | rows dropped | tier A | that appeared | appearance rate of dropped | Σ`p_active` removed / team-game |
|---|---|---:|---:|---:|---:|---:|
| **R1** | tier-B S2 rows, `departed` | 1,489 | 0 | **3** | **0.0020** | 0.480 |
| **R2** | tier-B S2 rows, ≥2 seasons stale | 1,501 | 0 | 7 | 0.0047 | 0.527 |
| **R3** | tier-B S2 rows, either | 2,054 | 0 | 7 | 0.0034 | 0.703 |
| **R4** | *every* `departed` row, tier A included — the over-reach arm | 2,080 | **248** | **151** | 0.0726 | 0.651 |

Removal precision: **99.66 %** for R3 (2,047 of 2,054 removed rows never appeared). R4 collapses to
92.7 % — that is the whole point of carrying it.

Every rule is scoped to S2-admitted tier-B rows because `UNIVERSE_CONSTRUCTION.md` §4 measured that
tier-A departed rows (mid-season trades still inside the five-game lookback) appear at **0.145** and
are already priced at a mean `p_active` of **0.212**. The fitted model handles them. R4 exists to
demonstrate that deleting them is harm rather than to assert it.

**τ was not fitted.** The full recency curve is published (`recency_tau_curve.csv`) so the absence
of τ-shopping is auditable; no τ-selected arm carries a verdict. It shows the cliff plainly: at
τ = 200 days the rule drops 3,266 rows of which 199 appeared; at τ = 400 it drops 1,501 of which 7
appeared. The signal is a season boundary, not a continuum.

---

## 2. The table that decides it — CLEAN WINDOW 2023–2024

**This is the headline window.** 2021 is degenerate (4,997 of 4,997 `p_active` rows at fallback
level 4 — a single constant, verified from the arm's own parquet) and 2022 trains on nothing else,
so 2023–2024 is the only window in which a walk-forward recalibration sees a fitted training pool.
RS1-C n = 960 team-games, 14,293 player rows.

| | **Xa** (benchmark) | **Z_R3** remove rows | **Xa+** stratify, remove nothing *(post hoc)* |
|---|---:|---:|---:|
| **Team MAE** (X0 = 19.916) | 10.386 | **9.948** | **9.915** |
| Δ vs Xa | — | +0.438 | **+0.471** |
| injection floor 80 % | — | 0.60 → **NOT ESTABLISHED** | 0.40 → **ESTABLISHED** |
| team bias | +0.900 | −0.541 | −0.398 |
| corr. with response | 0.105 | 0.141 | 0.139 |
| **Player Brier, all** | 0.088416 | **0.084858** | **0.084877** |
| Δ vs Xa | — | +0.003558 | +0.003539 |
| injection floor 80 % | — | 0.0010 → **ESTABLISHED** (3.6×) | 0.0010 → **ESTABLISHED** (3.5×) |
| **Player Brier, tier A** | 0.092028 | **0.092028** | **0.092028** |
| Δ vs Xa, tier A | — | **exactly 0.000000** | **exactly 0.000000** |
| Player Brier, tier B | 0.074855 | 0.057937 | 0.058028 |
| Δ vs Xa, tier B | — | +0.016919, floor 0.004 → **ESTABLISHED** (4.2×) | +0.016827, floor 0.004 → **ESTABLISHED** (4.2×) |
| Player AUC | 0.9366 | 0.9421 | 0.9421 |
| Unconditional E[pts] MAE | 3.304 | 3.198 | 3.207 |
| Conditional `pts_hat` MAE | identical | identical | identical |
| **Appeared player-games left with NO forecast** | 0 | **5** | **0** |
| Exposure misallocation, *full window* (X0 = 8.912 min) | 4.005 | **2.438** | 3.171 |
| **Decision stratum Δ Brier** | — | +0.000155, p 1.0000, NOT ESTABLISHED | +0.000155, p 1.0000, NOT ESTABLISHED |

One row above is a full-window number and is labelled so: the exposure-misallocation metric is
computed on all 1,392 team-games, because it reproduces E1_I0035's published X0 anchor of
**8.912455** exactly (`exposure_shape.csv`) and that anchor is defined on the full window. Every
other row is clean-window only.

Full-window (2022–2024) figures are in `HEAD_TO_HEAD.csv` and are reported beside these throughout,
never instead of them. There, Z_R3 does beat Xa+ (team 10.296 vs 10.697, Brier 0.090347 vs
0.092888, both ESTABLISHED) — **but that window's 2022 fold is fitted on a constant, and the
advantage does not survive into the clean window.** I do not carry it.

---

## 3. Does a currency rule beat Xa? Three answers, in order of confidence

**(a) At the player level — the actual product — YES, and it is established.**
Brier 0.088416 → 0.084858 (Z_R3) or 0.084877 (Xa+), p < 0.0001, 3.5–3.6× the injection-verified
floor, 512 player-season blocks. AUC 0.9366 → 0.9421. Unconditional E[pts] MAE 3.304 → ~3.20. The
whole gain is on tier B, where the appearance-rate separation the rule keys on (0.002 vs 0.110) is
simply information Xa's four strata do not contain.

**(b) Tier A is untouched — and this is stronger than Xa's own claim.**
Δ tier-A Brier is **exactly 0.000000**, bit-identical weights, on both arms. That is not a failure
to detect: the rules remove no tier-A row, the `stale` flag is false on every tier-A row by
construction, so the tier-A recalibration strata and their fits are unchanged. **E1_I0035 had to
report Xa's tier-A safety as "no harm detected, and none could have been detected at that
magnitude" (−0.000148, 0.06× its floor). Here it is structural.** That distinction is worth having
and it is the one thing this screen offers that Xa cannot.

**(c) At the team level — NO for the removing rule, and the whole team-level story is a level
effect anyway.**
Z_R3's +0.438 sits **below** its own injection-verified 80 % floor of 0.60 on the clean window:
**NOT ESTABLISHED**. Xa+'s +0.471 clears its floor of 0.40 and is ESTABLISHED. But **freeze the
intercept and every team-level difference in this screen evaporates**:

| clean window, team MAE | unfrozen | **frozen to Xa's per-team-game Σw** |
|---|---:|---:|
| X0 (the unrepaired champion) | 19.916 | **10.324** |
| Xa | 10.386 | 10.386 |
| Xa+ | 9.915 | 10.395 |
| Z_R3 | 9.948 | 10.395 |

Rescale every arm's availability mass to the same per-team-game total and the unrepaired champion is
**the best of the four**. Every team-level number in this document, and Xa's own +9.53 over X0, is
**shared-level movement and nothing else.** E1_I0035 established that a uniform per-team-game
rescaling cancels exactly in the only downstream consumer — that is why its Xb changed the team sum
and changed the allocation by literally zero. The same argument applies with full force here.
**Do not buy the team-level number.**

At the player level the picture is the opposite, and that is the finding: freezing a single global
intercept onto every arm leaves Z_R3 at Brier 0.09038 against Xa's 0.09398 (full window) — the gain
is **0.0036 frozen against 0.0043 unfrozen**. **The player-level gain is shape. The team-level gain
is level.** Only the first is worth anything.

---

## 4. The coverage cost, by name

R3 removes **7** appeared player-games out of 13,087 (**0.053 %**). For scale, E1_I0035's Xc lost
684 (5.23 %) — a hundred times as many. All seven, with what they actually did
(`COVERAGE_COST.csv` carries the full record including game ids and opponents):

| season | date | player | minutes | pts | `p_active` | seasons since club | departed |
|---|---|---|---:|---:|---:|---:|---|
| 2022 | 05-07 | Jocelyn Willoughby | 28.6 | 13 | 0.800 | never | no |
| 2022 | 05-10 | Rennia Davis | 2.7 | 2 | 0.800 | never | no |
| **2023** | **05-19** | **Brittney Griner** | **25.4** | **18** | 0.800 | 2 | no |
| 2023 | 05-19 | Karlie Samuelson | 26.3 | 13 | 0.800 | 2 | yes |
| 2024 | 05-14 | Kiana Williams | 4.2 | 0 | 0.800 | 2 | yes |
| 2024 | 05-15 | Lou Lopez Sénéchal | 5.7 | 0 | 0.800 | never | no |
| 2024 | 05-15 | Diamond DeShields | 18.3 | 14 | 0.800 | 3 | yes |

**Brittney Griner is the case that should decide how anyone feels about this.** She did not play in
2022 — she was detained in Russia — so on 19 May 2023 her last appearance for Phoenix was two
seasons old and R2 deletes her from Phoenix's opening-night universe. She played 25 minutes and
scored 18. A pure recency rule cannot distinguish "gone" from "away", and this is what that costs.
Note that **R1, the departure rule, keeps her** (she had played for nobody else), and that **Xa+
keeps all seven** because it never removes a row at all.

**R4, the over-reach arm, loses 151 appeared player-games (1.15 %)** and the list reads like a
transfer window: Breanna Stewart and Courtney Vandersloot on New York's 2023 opener, Candace Parker
and Alysha Clark on Las Vegas's, Nneka Ogwumike and Skylar Diggins-Smith on Seattle's 2024 opener,
Kahleah Copper and Natasha Cloud on Phoenix's. Every one had genuinely joined the club she was
deleted from. That is what happens when a departure signal built from box scores is applied to rows
whose only evidence of *arrival* is a transaction wire this partition may not use. It is a real
limit, not a tuning failure, and it is why every rule carrying a verdict is scoped to S2 rows.

---

## 5. The one that matters for the decision: removing vs stratifying

Z_R3 does two separable things — it uses the currency **signal**, and it changes the **row set**.
Only the second is a contract change; only the second costs coverage; only the second invalidates
every cached research frame and receipt keyed on the row set (`REACH.md` §2). `Xa+` isolates the
first: the identical signal, admitted as a recalibration stratum, removing nothing.

**On the clean window they are indistinguishable.**

| Z_R3 vs Xa+, clean window | Δ | p | injection floor | verdict |
|---|---:|---:|---:|---|
| Team MAE | **−0.033** (Xa+ better) | 0.0923 | 0.10 | **NOT ESTABLISHED** |
| Player Brier, all | **+0.000019** | 0.0650 | 0.00025 | **NOT ESTABLISHED** |
| Player Brier, tier A | 0.000000 | 1.0000 | 0.00025 | NOT ESTABLISHED |
| Player Brier, tier B | **+0.000092** | 0.0663 | 0.0010 | **NOT ESTABLISHED** |
| Decision stratum | 0.000000 | 1.0000 | 0.0005 | NOT ESTABLISHED |
| Appeared player-games lost | **5** | **0** | | |

**Nineteen millionths of a Brier point, and five named women who played, in exchange for a change
that moves ~32 research files and every receipt keyed on the row set.** On the one clean window,
deleting the rows buys nothing over pricing them correctly.

**So the honest conclusion is narrower and more useful than "prune the universe":**

> **The roster-currency signal is real and is worth having. Removing the rows is not what makes it
> work.** The information is `departed` and `seasons_since_club`; whether you spend it by deleting a
> row or by recalibrating it is, on this evidence, a free choice — and the recalibrating version is
> cheaper, safer, loses no coverage, and keeps Brittney Griner.

That said, `Xa+` is **POST HOC** (`PREREG.md` §0). It was built to attack my own positive result and
it succeeded, which is the direction of evidence that should be trusted most — but the Xa+ vs Z_R3
contrast is a hypothesis for a fresh screen, not a settled finding.

---

## 6. What most weakens all of this

Listed here rather than at the end, because that is the standard.

1. **The team level is a level effect and I would delete every team number in §2 if I could.**
   Frozen to a common Σw, the unrepaired champion beats all three repairs. The team-level column
   exists because D101 requires it, not because it means anything.
2. **The commercial answer is zero.** Zero decision-stratum rows are touched; the decision-stratum
   Brier delta is +0.000155 at p = 1.0000. Nobody should fund this on the expectation of edge.
3. **Xa+ is post hoc and it is the arm the recommendation rests on.**
4. **The clean window is 960 team-games and 24 team-season blocks.** Above the six-block floor, but
   the team-level injection floors (0.40–0.60 MAE) are coarse relative to the effects (0.44–0.47).
   Two of the three team verdicts sit within a factor of 1.5 of their floor.
5. **Every rule is a threshold on box-score history, and box-score history cannot see arrivals.**
   R4's 151 false removals are the visible face of this; it is why the rules are scoped to S2, and
   the scoping is itself a choice made after seeing the population.
6. **The transaction wire would probably beat all of this and may not be used.** It explains 84.5 %
   of the candidacy gap against prior-season affiliation's 43.3 %. It has no manifest and a single
   retrospective observation time. **The best available repair is unmeasurable in this partition,
   and that has not changed since E1_I0035 said so.**
7. **`Xa+` inherits Xa's registration problem unchanged.** The arm's registration forbids retuning
   declared constants after seeing outcomes. Xa+ is still a recalibration of `p_active`, so enacting
   it is a re-registration, not an edit — exactly as E1_I0035 said of Xa.
8. **Nothing here reaches production and a row-set change would not either** (`REACH.md`). The
   shipped roster is built by a different code path that has its own copy of this defect (`DEFECTS.md`
   D-2). Repairing the contract would not change one line of shipped output.
9. **The type-I rate is 0.0675 at nominal 0.05.** Mildly anticonservative. No verdict rests on p
   alone, but it is there.
10. **My own harness mislabelled its tier-B power cells** and I found it only because the numbers
    looked wrong (`DEFECTS.md` D-1). The tier-B verdicts here come from the re-swept floors.

---

## 7. If the user wants a recommendation

**Nothing should be enacted from this screen, and three items already await authorisation.** But if
the availability arm is ever repaired, the measured ordering on the clean window is:

1. **Xa+** — Xa's recalibration with the currency flag as an extra stratum. Beats Xa at the player
   level by 3.5× the injection floor, provably cannot touch tier A, removes no row, loses no
   coverage, and needs no contract change. **Post hoc; verify it in a fresh screen before trusting
   it.**
2. **Xa** — E1_I0035's benchmark, still the only *preregistered* option that improves both levels.
3. **Z_R3** — indistinguishable from Xa+ on the clean window and strictly more expensive.
4. **Nothing at all** — entirely defensible. The defect reaches no shipped output, and the rows it
   corrupts are not rows anyone prices.

**And one thing that is not a model change at all and is worth more than any of them:** stamp the
S2 rows' actual last-appearance date instead of 1 January (`DEFECTS.md` D-3). It changes no row and
no probability, and it puts the currency information where any future consumer can reach it without
rebuilding this screen's machinery.
