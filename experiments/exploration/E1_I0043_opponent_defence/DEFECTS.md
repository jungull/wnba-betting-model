# DEFECTS — E1_I0043

Defects this screen found, including the ones it committed itself. Ordered by consequence, not by
whose fault they are. Two of the six are this screen's own.

---

## D-01 — `E1_I0023`'s DISCLOSED CEILING NOISE FLOOR IS UNDERSTATED BY 11×, ON THE CELL IT HEADLINED

**Severity: material to a withdrawn claim; not material to any live number.**

D098's disclosure reads: *"The ceiling statistic is disclosed to have a noise floor — the pure-noise
control returns up to 3.98e-04."*

Read from that screen's own `arithmetic_ceiling.csv`, filtering `is_negative_control == True`:

| stratum | tier | contrast | fit | `ceiling_1sd_form` | `ceiling_D084_form_var_share` |
|---|---|---|---|---|---|
| DECISION | ALL_TIERS | INTERACTION | walk_forward | 3.979894e-04 | 3.960736e-04 |
| **DECISION** | **T3_high_usage** | **MAIN_EFFECT** | **walk_forward** | **4.375669e-03** | **4.162570e-03** |

The disclosed figure is the first row. **The maximum is the second row, 11.0× larger, and it is the
exact stratum/tier/contrast/fit combination of D098's headline** (`MAIN EFFECT, DECISION, TOP USAGE
TIER, walk-forward`).

Consequence: D098's ceiling of 0.012808 for that cell is **3.08×** its own matched noise floor, not
32× as the disclosed floor implies. D099 withdrew that ceiling claim for a different reason (it was
computed on a subset SST). The claim was wrong twice over and only one reason is on the record.

**Not repaired here** — `E1_I0023` is outside this screen's write scope and its artifact is
correct; only the sentence describing it is wrong. Recommended: the disclosure sentence in
`E1_I0023/NOTES.md` should quote the maximum over the negative-control rows, and the ceiling noise
floor should be quoted per stratum rather than as one number.

---

## D-02 — THIS SCREEN APPLIED A CEILING DERIVED ON ONE SCALE TO A STATISTIC ON ANOTHER (D101, self-inflicted)

**Severity: caught before it reached a verdict; corrected in-run.**

`scripts/s02_stratum_and_ceiling.py` computed the ceiling in D084/D089's form — a rate coefficient
times an estimated-minutes vector, scored against `y_pts` — because that is how `E1_I0023` computed
it and this screen copied the form. But this screen's *cells* fit `y_pts` directly, with no minutes
multiplication. Those are two different models, and the ceiling from one is not a bound on the
other.

It showed up immediately: the s03 cell `y_pts / B1_HONEST / CLEAN_2023_24 / UNFROZEN` returned
+0.00452 against an s02 "ceiling" of 0.00344. **An observed statistic above its own ceiling is the
signature of the D101 failure**, and it is exactly what D101 names: *a critical value must be
derived on the scale it is applied to.*

Corrected in `scripts/s04_ceiling_matched_and_controls.py`, which recomputes the ceiling from the
fitted cell's own forecast shift on the cell's own rows, response and SST. The uncorrected table is
kept on disk as `CEILING.csv` rather than deleted; the corrected one is `CEILING_MATCHED.csv`.

### The generalisation, which is not this screen's own

The correction exposed a convention problem in the programme, not just in this screen:
**`(d·d)/SST`, the statistic D084 and D089 both call "the ceiling", is not an upper bound on ΔR².**
`ΔR² = (2 d·e − d·d)/SST`, which exceeds `(d·d)/SST` whenever `d·e > d·d` — the normal case when the
fitted coefficient is shrunk relative to the optimal one. The strict arithmetic bound is the ORACLE
`(d·e)²/((d·d)·SST)`.

D084's kill and D079's kill both rest on this statistic. **Neither kill is thereby wrong** — both
were killed at ratios (0.000129 and 0.001127 against floors) where the distinction cannot matter,
and D084's is additionally an analytic argument. But "the ceiling" is being used in the ledger as
though it were a bound, and it is not one. Recommended: quote the oracle alongside it, or rename
the statistic.

---

## D-03 — TWO OF THE FOUR SIGHTINGS' ROW SETS CANNOT BE RECONSTRUCTED TO THE ROW (self-disclosed limitation)

**Severity: does not change any conclusion; limits an assertion.**

`INDEPENDENCE.md` reconstructs each sighting's row set. Two do not reproduce exactly:

| sighting | recorded n | reconstructed n | gap |
|---|---|---|---|
| S1 (D098) | 1,687 | 1,505 | −182 |
| S3 (D103) | 5,673 | 5,670 | −3 |
| S2 (D099) | 4,514 | 4,514 | **0** |
| S4 (D117) | 14,852 | 14,852 | **0** |

S1's gap is the usage-tercile cut: `E1_I0023` computes terciles against a first-training-fold
reference with a fallback rule, and the exact reference used is not recorded to the row. S3's gap
is a complete-case column list that its screen does not enumerate.

The containment conclusion is unaffected — the *recorded* counts 1,687 < 4,514 < 5,673 < 14,852 are
themselves nested, and the two that matter for the shared-upstream finding (S2, S4) reproduce
exactly. But the statement "S1 ⊂ S2" is verified on a reconstruction of S1, not on S1.

**General recommendation**: a screen should write its scored row keys, or a hash of them, beside its
headline. `E1_I0025` effectively did (its n reproduces exactly from the recorded stratum rule);
`E1_I0023` and `E1_I0026` did not.

---

## D-04 — D103's STATED GROUND FOR TREATING ITS SIGHTING AS NEW IS FACTUALLY WRONG

**Severity: removes the last claim to independence from sighting 3.**

`E1_I0026/NOTES.md` records the incidental sighting as being *"on an outcome D085 did not screen the
A-family against (D085 screened them against **efficiency**, not points-per-minute)"*.

`E0_I0016/screen_results.csv` contains the cell `ppm|A10_opp_defrtg`, n 14,852, dR² 0.001443, next
to `ts|A10_opp_defrtg` and `efg|A10_opp_defrtg`. D085's three outcomes are
{`ppm`, `ts`, `efg`}; 12 A-family constructions × 3 outcomes = the 36 cells its ruling names.

**Points-per-minute was screened.** D103's sighting was the same candidate, the same response and a
subset of the same rows as sighting 4, measured in-sample rather than pooled. The note was written
in good faith and the agent's decision not to raise it as a lead was correct anyway; the reason
given is simply not true.

---

## D-05 — "A WITHIN-PLAYER NULL IS BLIND TO OPPONENT DEFENCE" IS FALSE AS STATED; THE BLIND NULL IS THE WITHIN-**OPPONENT** ONE

**Severity: a framing error that would send a screen to the wrong control. Measured here.**

This screen's brief, and the general framing around D115/D117, describes a within-player null as
structurally blind to a team-season opponent quantity. Measured first-hand on this screen's own
primary cell (`BLIND_NULL_DEMO.csv`, 1,000 draws each, identical cell, identical rows):

| scheme | permutes within | blocks | corr(drawn, real) | z | **p** |
|---|---|---|---|---|---|
| `N_ESWAP` relabel opponent-team-seasons | — (between) | 48 | **−0.0231** | +9.016 | **0.000999** |
| `N_BLIND` shuffle **within opponent-team-season** | opponent-team-season | 48 | **+0.8221** | +0.908 | **0.186813** |
| `N_WITHIN_PLAYER` cyclic shift within player-season | player-season | 600 | +0.0301 | +18.820 | **0.000999** |

**The within-player null rejects at the draw floor. The within-opponent null does not reject at
all.** The within-opponent shuffle changes 97.0% of the values and still preserves 82.2% of the
correlation with the real column, because it preserves each opponent-team-season's mean and 77.1%
of this candidate's variance *is* that mean.

The correct statement of the invariant is: **a null is blind to a candidate when it permutes
*within the entity the candidate is (near-)constant in*.** Blindness is a property of the
match between the permuting entity and the candidate's constancy entity — not of "within-entity"
versus "between-entity" in the abstract, and not of the player level in particular. A player faces
many opponents, so shuffling opponent ratings across a player's games destroys the signal
completely; that null is a valid instrument here, not a blind one.

This matters operationally: a screen told "use a between-entity null because within-entity nulls are
blind to opponent quantities" could pick a within-player null believing it to be the blind one it
must avoid, or avoid it believing it to be blind when it is the sharpest instrument available.

**This also supplies, for the first time in this programme's record, a first-hand demonstration on a
live cell of the exact failure D115/D117 are about**: the same effect that the matched null calls
p = 0.000999 the blind null calls p = 0.187. D085's own recorded arms agree —
`p_N1_within_entity = 0.870216` against `p_N2_entity_swap = 0.001664`, reproduced here as anchors
A2c and A2a.

---

## D-06 — THE INJECTION'S WITHIN-COMPONENT ARM DID NOT REALISE ITS TARGET, SO ITS POWER CURVE IS NOT A POWER CURVE (self-inflicted)

**Severity: one of four injection arms is uninterpretable. Does not touch the verdict arm.**

`INJECTION_POWER.csv`. β for each planted δ is calibrated against the component's **in-sample**
partial sum of squares. For the BETWEEN component this realises well — target 0.0080 gives a
realised walk-forward ΔR² of +0.006805 (85%), and 0.0040 gives +0.003231 (81%). For the WITHIN
component it does not realise at all:

| target δ | BETWEEN realised | WITHIN realised |
|---|---|---|
| 0.0000 | −0.000383 | −0.000383 |
| 0.0020 | +0.001432 | **−0.000264** |
| 0.0080 | +0.006805 | **+0.000120** |

Planting δ = 0.0080 on the within-opponent-season deviation moves the walk-forward statistic by
0.00012. The reported "power" of `N_ESWAP` on the WITHIN component (0.056 → 0.244 across the grid)
is therefore **not** power at δ; it is power against an effect that was never actually planted at
the intended size, because the within component is only 10.4% of the candidate's variance on this
stratum and a walk-forward fit shrinks it almost to nothing.

**The correct reading of that arm is "the within-opponent component is not detectable at any δ this
calibration can plant", not "N_ESWAP is blind to it".** The two are different claims and only the
first is supported. The verdict arm — `N_ESWAP` on the BETWEEN component, which carries 89.6% of
the candidate's stratum variance and 117% of the observed effect — calibrates correctly, has
type-I 0.048, and has a null-centre ratio of +1.030, so the verdict's null validation stands.

Fix for a successor: calibrate β by bisection on the **realised walk-forward** statistic rather
than on the in-sample partial SS.

---

## D-07 — THIS SCREEN'S INJECTION SEEDS ARE NOT BIT-REPRODUCIBLE ACROSS PROCESSES (self-inflicted)

**Severity: reproducibility only; the estimates are valid.**

`scripts/s05_injection.py` derives per-replicate seeds as
`ob.SEED + 1000*r + hash(sname) % 97`. Python randomises `str.__hash__` per process unless
`PYTHONHASHSEED` is set, so re-running the script produces a different draw sequence. The power
estimates and the null-centre ratios are unaffected in expectation (their se is 0.025 at
nrep = 250), but the exact numbers in `INJECTION_POWER.csv` cannot be regenerated from the recorded
`SEED` alone.

The one-line fix is a literal per-scheme integer instead of `hash(sname)`. **Recorded rather than
repaired**, because repairing it costs a 22-minute re-run that would move the third decimal of
numbers whose standard error is already in the second. Every other null in this screen — all 32
`nulls/*.npz` archives and the family-wise max draws — uses `np.random.default_rng(ob.SEED)` and is
exactly reproducible.

---

## D-08 — `E1_I0038`'s FLIPS.md DOES NOT EXIST (brief-level, recorded for the next agent)

This screen was directed to "read that screen's FLIPS.md", meaning
`E1_I0038_within_entity_null_audit`. There is no `FLIPS.md` in that directory. The only `FLIPS.md`
in the worktree is in `E1_I0040_audit_extension`, and it is a companion to *that* screen's verdict —
it reports **0 flips across 32 exposed cells**, and it refers to E1_I0038's 52 per-cell and 11
family-wise flips rather than containing them. E1_I0038's flips live in its `VERDICT.md` and
`MATCHED_NULL_RECHECK.csv`.

No consequence beyond a minute of searching, recorded so the next brief points at the right file.
