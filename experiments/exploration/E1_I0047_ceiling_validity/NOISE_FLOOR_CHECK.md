# NOISE_FLOOR_CHECK — independent verification of E1_I0043 D-01

Screen `E1_I0047_ceiling_validity` · PREREG sha256
`abbf0077ceb179b076646aeef5eda6ae2efeeced931fe87c69801ce6fc9b4994`
Evidence: `scripts/run_log_s06.txt`, `scripts/_s06.json`, `NOISE_FLOOR_TABLES.csv`.
Source artifact read read-only: `E1_I0023_usage_defence_interaction/arithmetic_ceiling.csv`
(64 rows, 16 flagged `is_negative_control`) and that screen's `NOTES.md` item 7.

---

## VERDICT

**E1_I0043's D-01 is CONFIRMED at 11× under the scope the disclosed sentence is used in, and is
1.44× under the sentence's literal first clause. Both readings are quoted here because E1_I0043
quoted one where two are needed. The substance stands: the disclosure understates its own artifact,
and it does so on exactly the stratum/tier/contrast/fit combination D098 headlined.**

---

## THE SENTENCE, VERBATIM

`E1_I0023/NOTES.md`, item 7:

> **THE CEILING STATISTIC HAS A NOISE FLOOR AND IT IS DISCLOSED.** The pure-noise interaction
> control returns a walk-forward ceiling of up to 3.98e-04 purely from estimation noise in its own
> coefficient. Ceilings below roughly 4e-04 here are not distinguishable from that floor. Two of
> this screen's own interaction ceilings sit under it.

Two clauses with two different scopes. The first is about the **interaction** control. The second —
*"Ceilings below roughly 4e-04 **here**"* — is a claim about every ceiling in the screen.

## THE THREE SCOPES, MEASURED

| scope | n control rows | max `ceiling_1sd_form` | max `ceiling_D084_form` | × 3.98e-04 (1sd) | × (D084) |
|---|---|---|---|---|---|
| **1 LITERAL** — interaction + walk-forward | 4 | 5.732328e-04 | 6.513851e-04 | **1.44×** | 1.64× |
| **2 WALK-FORWARD** — both contrasts | 8 | 4.375669e-03 | 4.162570e-03 | **10.99×** | 10.46× |
| **3 WHOLE TABLE** — every control row | 16 | 4.375669e-03 | 4.162570e-03 | **10.99×** | 10.46× |

Argmax under scope 1: `POOLED / T3_high_usage / INTERACTION / walk_forward`.
Argmax under scopes 2 and 3: **`DECISION / T3_high_usage / MAIN_EFFECT / walk_forward`** — the exact
stratum, tier, contrast and fit of D098's headline.

The disclosed 3.98e-04 is `DECISION / ALL_TIERS / INTERACTION / walk_forward` (reproduced at
3.979894e-04, |diff| 3.972e-11). **Even inside its own literal scope the sentence understates by
1.44×** — the maximum interaction walk-forward control is 5.732e-04, not 3.98e-04.

## THE MATCHED FLOOR FOR D098's HEADLINE CELL

`A10_opp_defrtg / DECISION / T3_high_usage / MAIN_EFFECT / walk_forward`, n = 1,687:

| | value |
|---|---|
| ceiling (D084 form) | 0.01280821 |
| **matched** pure-noise control, same stratum/tier/contrast/fit | **0.00416257** |
| ratio | **3.077×** |
| ratio implied by the disclosed 3.98e-04 floor | 32.18× |

E1_I0043 reported 3.08× against 4.163e-03. **Reproduced here at 3.077× against 4.162570e-03.**

## AND THE SAME CELL FAILS IN THE OTHER DIRECTION TOO

Established independently in `BOUND_OR_NOT.md` §4 from the same table's own columns: that cell's
**realised** statistic is 0.01870281 against its published ceiling of 0.01280821 — the "ceiling" is
exceeded by 46%, with `c* = 1.230`. So the number D098 headlined was wrong twice at once: too small
to be an upper bound, and quoted against a floor eleven times too low. D099 withdrew it for a third
reason (a subset SST). **Three independent defects on one number.**

---

## DOES THE PATTERN APPEAR ELSEWHERE?

Discovery by **column presence, never by candidate name**: every `.csv` under
`experiments/exploration/` carrying both a column matching `ceiling` and a column matching
`negative_control`. Three tables qualify.

| table | ceiling column | controls | min | median | **max** | max/median |
|---|---|---|---|---|---|---|
| `E1_I0023/arithmetic_ceiling.csv` | `ceiling_1sd_form` | 16 | 1.4028e-07 | 1.7372e-04 | **4.3757e-03** | **25.2×** |
| `E1_I0023/arithmetic_ceiling.csv` | `ceiling_D084_form_var_share` | 16 | 2.0494e-07 | 2.0184e-04 | **4.1626e-03** | **20.6×** |
| `E1_I0043/CEILING.csv` | `ceiling_1sd_form` | 6 | 1.4441e-04 | 5.2207e-04 | 9.1451e-04 | 1.8× |
| `E1_I0043/CEILING.csv` | `ceiling_D084_form` | 6 | 1.5429e-04 | 5.2980e-04 | 9.2087e-04 | 1.7× |

**The general finding, which is larger than D-01: the ceiling statistic's noise floor is not one
number.** Within a single screen it varies by stratum, tier, contrast and fit by up to **25×**. Any
screen quoting "the noise floor" as a scalar is quoting a summary of a distribution and will
understate it somewhere. The correct disclosure is per stratum; the correct comparison for a given
cell is the control row **matched** to that cell.

### Which screens quote a scalar noise floor in prose

Text search of every `.md` under `experiments/exploration/` for a line containing "noise floor" in a
ceiling context — 14 distinct lines across 5 screens:

- **`E1_I0023/NOTES.md`** — quotes a scalar. **This is the defect.**
- `E1_I0043/CEILING.md`, `DEFECTS.md`, `PREREG.md` — quotes its own matched control beside the real
  ceiling (0.00020 against 0.01094, computed on the same rows in the same run). **Correct practice**,
  and its own spread is only 1.8×, so a scalar there would have been nearly harmless anyway.
- `E1_I0046_allocation/CEILING.md`, `PREREG.md` — quotes **per-cell matched** noise floors
  ("154× / 314× / 231× their own matched noise floors"). **Correct practice.**

**No second instance of the D-01 defect exists in the current record.** The practice that produced
it was superseded by E1_I0043 and is not repeated by E1_I0046. The recommendation is therefore
narrow: repair the one sentence in `E1_I0023/NOTES.md` (outside this screen's write scope — not
touched), and make per-stratum matched-control disclosure the standing convention rather than an
emergent one.

---

## WHAT WEAKENS THIS PAGE

- Scope 1 gives 1.44×, not 11×. Someone reading `E1_I0043` D-01's headline "understated by 11×"
  against the sentence's first clause alone would find the claim overstated by 7.6×. E1_I0043's
  number is right for the scope that matters and its supporting table names the right row; the
  headline sentence is nonetheless doing more work than one scope supports.
- The cross-screen sweep found only **two** tables besides this screen's own output that carry both a
  ceiling and a control flag. Most ceiling tables in the programme record **no negative control at
  all** (`CEILING_FORMS_CENSUS.csv`: 33 tables carry a ceiling column, 2 carry a control flag). The
  statement "no second instance exists" is therefore a statement about a very thin sample. The
  absence of a disclosed floor elsewhere is not evidence that those ceilings are clear of one.
