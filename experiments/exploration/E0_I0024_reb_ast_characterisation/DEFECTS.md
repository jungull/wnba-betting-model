# E0_I0024 -- SELF-IDENTIFIED DEFECTS

Written incrementally, at the moment of discovery, per the screen's own standing constraint.
Nothing here is discovered by a reviewer after the fact.

---

## D-01 (s02, leakage probe P4) -- THE A01 PROBE AS WRITTEN IS VACUOUS. **FIXED in s03 (P4b).**

**Found:** immediately after the first successful `s02_build_frame.py` run, on reading my own probe
output rather than trusting the `[PASS]`.

**What is wrong.** Probe P4, labelled
`"A01 uses PREVIOUS game membership (tip-time variant never built)"`, calls
`probe(..., True, checked, ...)` with a hard-coded `True`. It walks the frame, computes the
previous game's box membership and today's box membership, and then **asserts nothing about
`A01`**. It cannot fail. It reports `[PASS] n=192` and that PASS carries no information.

**Why it matters.** This is precisely the check that separates this screen's assist candidate from
the one D089 disqualified. `T01_c04_tiptime` is computed from `minutes > 0` in *today's* box and is
therefore a POST-GAME observation; `A01_c04_prevgame` must read only the team's *previous* game.
A vacuous probe on exactly that distinction is the worst place in this screen to have one, and a
green PASS is actively misleading — it is the same failure mode as the retrospective baseline that
entered this programme through the inference machinery.

**Severity.** No effect on any number: the *construction* in s02 section 7 is correct (`prev_present`
is assigned only after every row of the current game is written, and `A01` is read from
`prev_present`). The defect is in the *evidence for* the construction, not the construction. But
"the code looks right" is not the standard this screen holds itself to anywhere else.

**Fix.** `s03` adds **P4b**, a brute-force recomputation on a random sample: for each sampled row,
independently locate the team's previous game by date, take that game's box membership, take each
member's usage accumulated over games strictly earlier than the *current* game, sum over members
other than the player, and assert exact equality with the stored `A01_c04_prevgame`. It also adds
**P4c**, a discrimination check: it constructs the forbidden tip-time quantity's *membership set*
only (never the feature), confirms that it differs from the previous game's membership on a
material fraction of rows, and confirms `A01` matches the previous-game recomputation and **not**
the today's-box recomputation. If `A01` had been silently built from today's box, P4c fails.

**Status:** FIXED. See `run_log_s03.txt` for the P4b / P4c results and `leakage_probes.csv` for the
merged table. The original vacuous P4 row is retained in `leakage_probes.csv` and **relabelled
`P4_VACUOUS_SUPERSEDED`** so the record shows what was actually run rather than a tidied history.

---

## D-02 (s02) -- COVERAGE LOSS AT THE SEASON'S FIRST TEAM GAME IS 2.56%, AND IT IS NOT RANDOM.

**Found:** on reading the coverage line `R01..R10, A01..A05 coverage=0.9744` in the s02 log.

**What it is.** Every opponent-allowance and teammate-availability candidate is undefined for a
team's *first* game of a season, because there is no strictly-prior team history. That is correct
behaviour, not a bug. But the missing rows are systematically the **first game of each team-season**
(12 teams x 4 seasons x ~2 team-slots), which is disproportionately cold-start players.

**Why it matters.** If a candidate were screened on the 97.44% of rows where it is defined and the
reference on 100%, the comparison would be contaminated. Constraint 7 of this screen
("measure skill against a reference facing the same rows") forbids that.

**Handling.** Every dR2, every null draw and every ceiling in `s04` is computed on the
**intersection of finite rows for `y`, the full base, and the candidate** — the model and the
reference always face an identical row set, and the realised `n` is reported per cell. No
imputation is used for any candidate. This is not a residual risk; it is closed.

---

## D-03 (s03) -- THE ORACLE LADDER'S O-RUNGS CONDITION ON REALISED MINUTES, WHICH IS AN OUTCOME.

**Found:** while specifying the ladder, before running it.

**What it is.** Rungs O2, O3 and O4 use each row's **realised** minutes. Realised minutes are an
outcome of the game, not a pre-game quantity. A forecast cannot have them.

**Why it is nevertheless the right measurement.** This is deliberate and is the entire point of the
ladder: it is D081's construction, and it answers "how much of this target is irreducible *even to
an estimator handed the answer to the minutes sub-problem*". It is a **measurement of a ceiling,
not a candidate forecast**.

**Handling.** Every O-rung is labelled `ORACLE` in `oracle_ladder.csv`'s `kind` column and is never
compared to a market, never promoted, and never described as reachable. The honest rungs (`REF`,
`H1`-`H3`) are the only ones that are pre-game attainable. Any sentence in `FINDINGS.json` quoting
an O-rung carries the qualifier inline. **The gap between the best honest rung and O2 is the only
quantity in this screen that should ever be called "headroom", and it is still an upper bound.**
