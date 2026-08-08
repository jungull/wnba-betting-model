# LEVEL ARTEFACT SWEEP -- VERDICT

Screen `E1_I0036_level_artefact_sweep` · preregistration `PREREG.md`
sha256 `639efba016152c8917a113e6a55f156dbae451d267da32e94aa10a0d62b19d79`
Partition: 2021-2024 exploration only. 2025/26 never opened.

---

## HEADLINE

**The level-artefact hypothesis is NOT SUPPORTED. The negative record survives the D111
challenge. It does not survive the D108 challenge intact — one specific kill was a false
negative, and the cause was the null, not the level.**

Four preregistered opponent-level candidates, killed at player level, were re-measured at
team-game level against a level-matched, strictly-prior reference and an injection-verified
level-matched null. Under the stronger of the two level-matched references, **one of four**
clears family-wise, at `p_fw = 0.0498` — thirty draws out of 601, against a 0.05 threshold —
and the same cell reads `p_fw = 0.0532` under the other, equally defensible reference. **A
verdict that flips on the choice of reference is not a finding.** The other three die.

## THE COUNTERWEIGHT, IN THE SAME DOCUMENT

**Re-levelling upward is not a free move, and this screen quantifies its price for the first
time.** Aggregating player-games to team-games concentrates a roster-constant effect, but it
destroys rows faster than it concentrates signal:

| level | rows | MDE80 (injection-verified, 80% power) |
|---|---|---|
| player-game (D097 rowset) | 13,784 | 4.24e-04 (`N_PSWAP`) |
| team-game | 1,486 | 3.51e-03 – 3.95e-03 (`N_ESWAP`) |

The detection floor rises **8.3x to 9.3x**. The programme's largest live effect, 0.002057, is
**below the team-level detection floor entirely** — every team-level null in this screen has
power 0.10–0.25 against it, and only reaches 80% power somewhere between 0.004 and 0.006.

So the escape hatch D111 opened is much narrower than it looked. An effect diluted across a
roster has to be roughly **nine times larger** at team level to be detectable there than it
would have needed to be at player level. Dilution across ~9.4 teammates buys back about that
much and no more. **The two effects very nearly cancel.** That is the quantitative reason the
level-artefact hypothesis fails here, and it is a general result, not a fact about these four
candidates.

---

## WHAT WAS ACTUALLY RUN

### The census

`CENSUS.csv` — **1,999 recorded cells** across **8 screens** (D078/D082, D085, D087, D089,
D090, D097, D098/D099, D108). Of these **1,580 are kills**:

| kill reason (frozen rule, PREREG 4.2) | cells |
|---|---|
| POWERED_NULL | 688 (of which 381 are corrected to POWER_NOT_ASSESSED, defect D-02) |
| UNINFORMATIVE_NULL | 679 |
| CEILING | 213 |

**807 of the 1,580 killed cells (51.1%) are flagged blind to the programme's own best live
effect.** Median `mde80_fw` over killed cells is 0.002523 — above 0.002057. This corroborates
D103 on an independently assembled census.

### Triage

Frozen rule (PREREG 4.3): eligible iff **not a ceiling kill**, **the candidate is constant
across the roster** (`team_season` / `opp_team_season` / `team_game` / `matchup`), and **a
level-matched summable response exists**.

- **118 of 1,580 killed cells (7.5%) are eligible.** The level-artefact hypothesis can, at
  most, be about 7.5% of the negative record — and that ceiling is set before any statistic.
- **591 killed cells are at `player_season` or `row` level.** Re-levelling upward cannot help
  them: their mechanism is a property of a player, and summing to team destroys the variation
  rather than recovering it.
- **436 killed cells (27.6%) never recorded a level at all.** Per PREREG 4.3 they are
  ineligible, because I will not infer a level from a candidate's name. This is a hole in the
  programme's record, not a result — see DEFECTS.md D-01.

### CEILING KILLS WERE NOT RESURRECTED — EXPLICITLY

**213 cells were killed on arithmetic ceiling. A ceiling kill is arithmetic and survives
re-levelling. Not one of them was re-run, and none is resurrected anywhere in this screen.**

The distinct candidates so killed, listed so the exclusion is auditable:
`A01_c04_prevgame`, `A02_n_present_prevgame`, `A03_absent_usg_prevgame`,
`A05_teammate_prior_fgpct`, `G01_noise`, `G02_placebo_noop`, `R01_opp_allowed_miss_pg`,
`R02_opp_allowed_ra_share`, `R03_opp_allowed_atb3_share`, `R04_opp_allowed_mid_share`,
`R05_opp_allowed_long_miss_pg`, `R06_own_atb3_share`, `R07_own_miss_pg`,
`R08_player_ra_share` (its `y_reb` cells only), `R09_opp_allowed_paint_share`,
`R10_opp_allowed_oreb_pg`.

Caveat recorded rather than hidden: **only D097 ever wrote an arithmetic ceiling to disk**, so
the CEILING label can only fire in that screen. Ceiling kills certainly exist elsewhere and
are invisible to this census (DEFECTS.md D-03).

---

## THE FOUR RE-RUNS

Selected by the frozen EV formula from `TRIAGE_RANKING.csv`. All four are opponent-team-season
quantities — the same number for all ~9.4 teammates in a team-game, which is the exact and only
configuration in which a player-level response dilutes a real effect.

Level: team-game, n = 1,486. Null: `N_ESWAP` (reassign opponent identity among team-games
within season, preserving each opponent's own trajectory). Every null injection-verified;
`null_mean` and `null_sd` published beside every p.

| cell | candidate → response | base | dR2 | p per-cell | **p family-wise (K=4, max-z)** | verdict |
|---|---|---|---|---|---|---|
| L1 | M06_opp_pace → team FTA | B_TEAM_COMPLETE | 0.011610 | 0.0116 | **0.0532** | killed |
| L1 | M06_opp_pace → team FTA | B_TEAM_PLUS_OPP | 0.005330 | 0.0116 | **0.0498** | *clears, barely* |
| L2 | M06_opp_pace → team FTM | B_TEAM_COMPLETE | 0.010429 | 0.0199 | **0.0748** | killed |
| L2 | M06_opp_pace → team FTM | B_TEAM_PLUS_OPP | 0.004375 | 0.0266 | **0.0997** | killed |
| L3 | M04_opp_allowed_ft_rate → team PTS | B_TEAM_COMPLETE | 0.007601 | 0.0714 | **0.2475** | killed |
| L3 | M04_opp_allowed_ft_rate → team PTS | B_TEAM_PLUS_OPP | 0.000912 | 0.2957 | **0.7542** | killed, below floor |
| L4 | M01_opp_pf_pg → team PTS | B_TEAM_COMPLETE | 0.017504 | 0.0066 | **0.0166** | *clears* |
| L4 | M01_opp_pf_pg → team PTS | B_TEAM_PLUS_OPP | 0.003287 | 0.0565 | **0.2159** | killed |

`B_TEAM_COMPLETE` = the team's own expanding / EWMA / trailing-5 history of the response, its
own prior pace and prior shot volume, cold-start count, venue (7 columns).
`B_TEAM_PLUS_OPP` = the above plus **the closest prior OPPONENT measurement of the same
target** — the team-level analogue of D097's `B_COMPLETE_PLUS_R10` (8 columns).

### The two things this table actually shows

**1. D087 reference incompleteness, caught in the act.** Adding one column — the opponent's own
prior allowed total of the very quantity being predicted — shrinks the increments by
**2.2x (L1), 2.4x (L2), 8.3x (L3), 5.3x (L4)**. Most of what looked like an opponent-matchup
signal at team level was the opponent's own prior allowed total, which the thinner reference
had omitted. L3 falls from 0.0076 to 0.00091, *below the single-cell floor of 0.00102 and below
its own MDE80*.

**2. D101 reference dependence, caught in the act.** L4 clears under `B_TEAM_COMPLETE`
(`p_fw` 0.0166) and dies under `B_TEAM_PLUS_OPP` (0.2159). L1 does the opposite: 0.0532 → 0.0498.
**Which candidate "survives" is decided entirely by which of two equally defensible
level-matched references you pick.** Reference dependence remains this programme's top-ranked
source of wrong answers, and it is not fixed by moving level — it is if anything worse at team
level, where fewer rows make the reference choice bite harder.

**No candidate is resurrected by re-levelling. I am not proposing L1 or L4 as leads.**

---

## THE ONE THING THAT DID CHANGE: D097

Full detail in `D097_REBOUND_REEXAMINATION.md`. In summary:

- D097's strongest rebound candidate, `R08_player_ra_share → y_oreb`, was killed by the
  within-player cyclic null at `p = 0.9967`.
- The recorded `dR2 = 0.006488` **reproduced exactly** (0.0064881160 vs 0.006488) on D097's
  exact 13,784 rows.
- **79.75% of R08's variance and 98.19% of its measured effect are BETWEEN players.**
- **`N_CYCLIC` has power 0.00 against a signal planted in the between-player component**, at
  the programme's largest live effect size, in both strata. It is structurally blind to
  exactly the thing D097 was testing, because a cyclic shift within a player leaves that
  player's mean untouched.
- Under the correctly matched, injection-verified null `N_PSWAP` (power 1.00 on all three
  components, type-I 0.05): **`p = 0.001661` POOLED, `p = 0.003322` DECISION.**

**The kill was a false negative. The cause was the null, not the level.** `R08` is a
`player_season` candidate; it fails T2 and was never a re-levelling candidate.

Counterweight, stated in the same breath: the effect shrinks **5.7x** from POOLED (0.006488) to
the betting-relevant DECISION stratum (0.001146), where it sits at **1.12x the single-cell
floor and 0.49x the 132-cell floor** — in D097's 250-cell family it would very likely not clear
family-wise, and I did not recompute that family. It is a lead, not a champion.

---

## DOES THE NEGATIVE RECORD SURVIVE?

**Against D111 (level): yes.** At most 7.5% of the killed record was ever eligible for
re-levelling; none of the four highest-EV candidates is robustly resurrected; and the arithmetic
of the level change — a 9x rise in the detection floor against a ~9x dilution gain — explains
why not, in a way that generalises beyond these four.

**Against D103 (power): unchanged and confirmed.** 51.1% of killed cells in an independently
assembled census are blind to the programme's own best result. Those kills remain
uninformative rather than negative. That was already the ruling; this screen adds a second
count of it.

**Against D108 (nulls): no, not intact.** One documented kill was a false negative, and the
mechanism is general — **any null that permutes WITHIN an entity is blind to a candidate whose
variance is BETWEEN entities.** The census records **213 killed cells at `player_season` level
and 337 at `opp_team_season` level** — 550 of the 1,580 kills (299 and 427 respectively if
surviving cells are counted too). Every one of them is exposed to this failure mode wherever
a within-entity null was used, and the programme has not audited which. That is the outstanding
debt this screen leaves behind, and it is larger than the one it discharged.

## WHAT WOULD CHANGE THIS VERDICT

- Re-running D097's full 250-cell family under matched nulls, to see whether `R08` clears
  family-wise at DECISION. Not done here; one cell was re-run, not a family.
- A season-stability and walk-forward test on `R08`. Every number here is in-sample.
- An audit of which of the programme's ~1,349 recorded cells used a within-entity null on a
  between-entity candidate. That is a cheap query against the recorded `var_share_between_*`
  columns, and it is the highest-value follow-up this screen can name.
