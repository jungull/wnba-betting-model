# NOTES -- E1_I0036_level_artefact_sweep

Working notes: what was run, in what order, what each step decided, and what a successor needs
to know to re-open any of it.

Preregistration frozen at sha256
`639efba016152c8917a113e6a55f156dbae451d267da32e94aa10a0d62b19d79` before the triage rule was
applied and before any new statistic was generated.

---

## 1. SCOPE AND PARTITION

- Exploration partition **2021–2024 only**. Asserted in every build step (`A_PARTITION`).
  2025 and 2026 were never opened. No file under a 2025/2026 path appears anywhere in the
  scripts.
- Headline row sets are 2022–2024, matching the source screens (D097's `HEADLINE_SEASONS`);
  2021 is present in the frames and excluded by the source screens' own convention, not by me.
- Write scope: `experiments/exploration/E1_I0036_level_artefact_sweep/` only. Nothing outside
  was created, modified, staged or committed. No `git` command was run.
- Environment: Python 3.13, numpy 2.5.1, pandas 3.0.5. **No scipy, no sklearn, no
  statsmodels** — all statistics implemented directly (OLS via `numpy.linalg`, permutation
  nulls, empirical power). This is a constraint of the machine, not a choice; it means every
  number here is auditable line by line.

## 2. ANCHOR REPRODUCTION (required before new statistics)

Two anchors, both exact:

1. **D111's six bottom-up penalties**, recomputed from
   `E1_I0033_aggregation_level/which_level_wins.csv` as
   `NORM_MAE_advantage_TEAM_over_PLAYER / MAE_LEVEL_TEAM_<q>`:
   fga 0.4954 (49.6%), pts 0.2726 (27.3%), reb 0.1572 (15.7%), ast 0.1096 (11.0%),
   fta 0.0728 (7.3%), ftm 0.0656 (6.6%). All six match. Recorded in PREREG section 9.
2. **D097's `dR2 = 0.006488`** reproduced from raw data at 0.0064881160 on the exact 13,784-row
   set, and cross-checked against a literal two-fit R² difference (agreement 8.9e-17).

## 3. STEP LOG

| script | what it did |
|---|---|
| `dump_ledger.py` | read all 110 DECISION_LEDGER entries; D097/D103/D108/D111 in full |
| `s00`–`s06` | read-only reconnaissance: D103's power census, D097's record, D108's degeneracy evidence, frame schemas, column inventories |
| `s07_census.py` | built `CENSUS.csv` (1,999 cells, 8 screens) and `TRIAGE_RANKING.csv` |
| `s09_d097_reexam.py` | D097 debt: anchor gate, ceiling, variance decomposition, 3 nulls + preregistered injection |
| `s10_d097_components.py` | **added, disclosed post-hoc:** component-targeted injection; DECISION stratum |
| `s11_level_rerun.py` | first pass at the 4 team-level re-runs (**superseded**, defect D-06) |
| `s12_level_fairtest.py` | the 4 re-runs under two matched-strength team references + K=4 family-wise |
| `s13_d097_relevel.py` | PREREG 6.6: R08 levelled up to the roster against team offensive rebounds |
| `s14_summary.py` | census summary numbers used verbatim in the write-ups |

## 4. THE CENSUS — HOW IT WAS BUILT AND WHAT IT CANNOT SEE

Harvested from **eight** screens' own per-cell result files, each named explicitly in a python
literal with its column mapping — no file discovery, no name matching. Power joined from D103's
`s08_cell_verdicts.csv`: per-cell for 1,415 of 1,999 (70.8%), screen-median for the rest.

**Level is taken only from a source screen's own recorded level column.** Where none exists the
cell is `NOT_RECORDED` and ineligible. I did not infer level from candidate names — five
findings in this programme have died to name-based selection, and inferring "this sounds like
an opponent quantity" is the same error wearing a different hat.

Blind spots, all in DEFECTS.md: 436 cells with no recorded level (D-01); ceiling kills
detectable in only one screen (D-03); 381 cells whose power was never assessed but which the
frozen rule labels `POWERED_NULL` (D-02).

## 5. WHY THESE FOUR RE-RUNS

The frozen EV formula (PREREG 4.4) ranked 33 distinct eligible (candidate, target) pairs. The
top four were all `opp_team_season` candidates from D108's free-throw screen:

1. `M06_opp_pace → y_fta` (dR2 0.003493)
2. `M06_opp_pace → y_ftm` (0.003267)
3. `M04_opp_allowed_ft_rate → y_pts` (0.001566)
4. `M01_opp_pf_pg → y_pts` (0.001465)

**The mechanism-level argument, stated before measuring:** each of these is the *same number*
for all ~9.4 teammates in a team-game. An opponent that fouls more, or plays faster, or concedes
free throws at a higher rate, does so against the whole roster at once. Its effect on the team
total is undivided; its effect on any one player's row is that effect divided across the roster
and buried in that player's own game-to-game noise. **That is the only configuration in which a
player-level measurement mechanically understates a real effect**, which is why the eligibility
rule (T2) is exactly that condition and nothing looser.

`A_CONSTANT` was asserted, not assumed: all three candidates have exactly one distinct value
per team-game.

## 6. WHY THE FIRST PASS WAS THROWN AWAY

`s11` gave the team level a 3-column reference while the player screens being answered used a
10-column `B_COMPLETE`. Under that thin reference the candidates looked alive (L4 `p` 0.0050).
That is D087 reference incompleteness pointing in the candidate's favour, and it would have
produced a false positive — the mirror image of the false negative this screen was sent to
investigate.

`s12` rebuilt the reference twice over:

- `B_TEAM_COMPLETE` (7 col) — the team's own expanding / EWMA / trailing-5 history of the
  response, its own prior pace and prior shot volume, cold-start count, venue
- `B_TEAM_PLUS_OPP` (8 col) — the above plus the closest prior **opponent** measurement of the
  same target, the team-level analogue of D097's `B_COMPLETE_PLUS_R10`

Adding that single opponent column shrank the increments 2.2x–8.3x. Three of four cells died
outright; the fourth's verdict flipped depending on which reference was used. `s11` is retained
for the record and superseded.

## 7. NULLS AND POWER — WHAT WAS ACTUALLY VERIFIED

Five nulls defined in `lab.py`, each matched to a level:

| null | construction | used for |
|---|---|---|
| `N_ROW` | free permutation across rows | contrast only, never a verdict |
| `N_CYCLIC` | within-player-season cyclic shift | D097's kill, re-examined |
| `N_PSWAP` | swap whole player-season series within season | D097's matched null |
| `N_ESWAP` | swap whole opponent-season series within season | the four team-level re-runs |
| `N_TSWAP` | swap whole team-season series within season | the C1 level-up control |

R = 601 draws throughout (minimum attainable p = 1/601 = 0.001661, matching the screens being
re-examined). **Every p in every output file is published with its `null_mean` and `null_sd`**
(D103 ruling 2). Every null draw set is saved to `nulls/*.npz`.

**Every null carries an injection result. No verdict rests on a null that has not detected a
planted signal.** The injection machinery is vectorised: the carrier's null realisations are
residualised on the base once (they do not depend on the response), so 601 draws × 60–100
replicates × 6 deltas is a handful of matrix products.

Type-I rates at delta = 0 ranged 0.02–0.10 across all nulls and cells — no null was
anticonservative.

## 8. THE NUMBER THAT DECIDES THE HEADLINE

```
MDE80, injection-verified, 80% power:
  player-game level, n = 13,784      4.24e-04
  team-game   level, n =  1,486      3.51e-03 to 3.95e-03
  ratio                              8.3x to 9.3x
```

Roster size averages 9.39 players per team-game in this data. **The dilution factor you gain by
going to team level is almost exactly the detection floor you lose.** That is why re-levelling
does not rescue diluted effects at this sample size, and it is a general statement about a
16-team, ~40-game league, not a fact about these four candidates.

Anyone proposing a team-level screen in this programme should compute both sides of that
trade first. It is cheap and it is decisive.

## 9. WHAT I DELIBERATELY DID NOT DO

- **Did not resurrect any ceiling kill.** 213 of them, named in the verdict document.
- **Did not quote a single cross-level dR2 comparison.** D101 forbids it and it is the category
  error a prior coordinator made repeatedly. Every claim in this screen is a *survival* claim
  within a level, against a level-matched reference and a level-matched null.
- **Did not fit a champion, propose a production change, or enact one.**
- **Did not manufacture a survivor.** L1's `p_fw = 0.0498` is reported as what it is: 30 draws
  out of 601, flipping to 0.0532 under an equally defensible reference.
- **Did not recompute D097's 250-cell family.** One cell was re-run. The family-wise question
  for `R08` at DECISION is open and is flagged as such wherever the result appears.

## 10. FOR A SUCCESSOR — THE THREE THINGS WORTH DOING NEXT

1. **Audit the within-entity nulls.** 213 killed cells at `player_season` level and 337 at
   `opp_team_season` level — 550 of 1,580 kills. Flag every one where a within-entity null
   decided the verdict AND
   the candidate's between-entity variance share exceeds ~0.5, OR where the recorded
   `null_mean` exceeds the observed statistic. Several screens already recorded both columns,
   so this is a query, not a re-run. It is the highest-value follow-up available and it is
   larger in scope than the debt this screen discharged.
2. **Amend the injection convention** per DEFECTS.md D-04: inject component-wise, and flag
   `null_mean > observed`. The current convention passed a null that was blind to 98% of the
   effect it was judging.
3. **Season-stability and walk-forward on `R08_player_ra_share`** before it is ranked against
   anything. Everything in this screen is in-sample.
