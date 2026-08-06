# P34 — Independent adversarial review: TARGET-UNIT CONSISTENCY

**Reviewer dimension:** target-unit consistency (one of seven independent reviewers)
**Object under review:** `stage2b/P33_PREREGISTRATION_DRAFT/` (SPEC.json + REPORT.md), frozen bytes
**Verdict: ACCEPT_WITH_REQUIRED_CHANGES** (two Severity B findings; no Severity A)

ADVERSARIAL REVIEW. Reviewers are independent of the preregistration author. A clean review does not make an arm true; it makes it fittable.

## Stop conditions — stated at the top, per mandate

**None tripped by my findings as filed.** Nothing below changes the primary target, the K0
structure, the inference structure, the candidate universe, the cutoff-valid feature set, or the
leakage status. One conditional is stated plainly rather than hidden: Finding B1 documents an
unacknowledged tension between the P33 response-family freeze (quasi-Poisson IRLS) and the
V2_STOP_CONDITION retired-families sentence. My resolution is documentary (the retirement bounded
challenger *accuracy families*, not shared scoring machinery, and is marked "NOT verified by the
coordinator"), so no halt. **If the adjudicator instead reads that retirement as binding on the
estimation machinery, that is a change to the inference structure and MUST be raised as a halt,
not resolved inside this node.** I flag the fork; I do not resolve it beyond my documentary
required change.

## Blindness and scope attestation

I did not read any other reviewer's file, nothing under `SEALED_RESULTS/` (its existence was not
probed), and no comparative historical performance of any challenger. Nothing was fitted. No
projection was compared against any realised value: no residual, error, accuracy or skill
statistic was computed anywhere in this review. This file is the only file I wrote.

## Hash verification (stop-on-mismatch — all matched)

`Get-FileHash -Algorithm SHA256` over raw bytes, before any content read:

| file | expected | match |
|---|---|---|
| P33_PREREGISTRATION_DRAFT/SPEC.json | `066b2a04…d347d093` | YES |
| P33_PREREGISTRATION_DRAFT/REPORT.md | `6d945b86…1681248ab` (full: `6d945b8663323526ba29fc74cdf963c800ff26d12bac846e12ef69d1681248ab`) | YES |
| P32_CANDIDATE_SYNTHESIS/SPEC.json | `1dc25981…9198c2138c` | YES |
| P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json | `95d2412c…950875e75` | YES |

## What I measured, and how

One script, run once: `python <scratchpad>/p34_target_units_measurements.py` (schema/identity/unit
checks only; reproduced in full at the end of this file). It loads the universe via the frozen
`possession_features.load_universe()` and reads the frozen `possessions_raw_v2.parquet` and the
P33 SPEC bytes. Headline numbers, each from that run:

1. **Target unit construction re-derived exactly.** The target
   `realised_team_off_possessions_reg_equiv` equals `n_off_poss * 40 / (40 + 5*max(0, max_period - 4))`
   — a **period-count-based** regulation-equivalent rescale (`possession_features.py` lines
   197–212). Re-derived from the frozen possessions parquet: max abs deviation vs the universe
   column = **0.0** on all 2,982 rows.
2. **Offset unit identity.** `exp(log_exposure)` vs `projected_team_off_possessions`: max abs
   deviation **4.26e-14** (pure float round-trip; consistent with P33's measured
   `offset == log(projection)` at 0.0). The offset therefore exponentiates to the incumbent's
   regulation-equivalent projection — same unit as the target. Projection range [73.725, 84.35].
3. **Target support.** min = 66.0, max = 94.0, zero non-positive, zero NaN → the log link and the
   quasi-Poisson deviance (`y*log(y/mu) - (y-mu)`) are defined on every row.
4. **Target integrality.** 2,862 integer rows; **120 non-integer rows (4.02%)** — exactly the OT
   rows whose rescale is non-integral. The response is genuinely continuous-ish.
5. **OT prevalence (bounds the A26 channel and the dispersion caveat).** 66 of 1,491 games
   (4.43%) exceeded 4 periods; max_period histogram {4: 1425, 5: 60, 6: 5, 8: 1}; rescale factors
   attained {1, 8/9, 4/5, 2/3}; per test fold: 12/11/10/8/9 OT games. Per season: 16/12/11/10/8/9
   (2021–2026).
6. **Notation census over the 26 frozen formula fields** (programmatic, from the frozen SPEC
   bytes): `eta =` in 11 arms (A01–A07, A12–A15); `log E[y] =` in 4 (A08–A11);
   `y ~ offset(log_exposure)` in 3 (A16, A23, A25); **no linear-predictor statement at all in 8
   (A17, A18, A19, A20, A21, A22, A24, A26)**. `mu = exp(eta)` is stated in exactly one arm (A01).

Also verified by code read (not by execution): `k0_input()` **is** `incumbent_input()`
(`possession_features.py` lines 409–417) — identical target column, identical offset, so every
K0 is in the target's units by construction; `parity_report()` digests target and offset across
incumbent/K0/challenger and raises on divergence.

## Findings

### B1 — The response-family freeze cites, without reporting, the very sentence that retired its family (SEVERITY B)

`SPEC.json.inference_spec_gap_resolution.estimation_objective_frozen_here` freezes "Poisson
quasi-likelihood IRLS (log link…)" and cites "the target's measured under-dispersion (0.193,
V2_STOP_CONDITION retired-families note)". The cited sentence (`stage2a/V2_STOP_CONDITION.json`
line 189) reads: *"retired_families_with_bounds: count/Poisson GLMs (target dispersion ratio
0.193 -- UNDER-dispersed…), … log transforms (CV 4.93%) … NOT verified by the coordinator."* The
frozen program record thus **retires "count/Poisson GLMs" and "log transforms" as families**, and
the P33 draft freezes a Poisson-quasi-likelihood log-link estimator while citing half of that
sentence and never mentioning the other half. Standing rule 1 requires contradictions to be
reported, never silently reconciled — P33's REPORT section 5 lists four contradictions and this
is not among them.

Substantively I believe the freeze survives: the V2 retirement bounded *challenger hypothesis
families* (routes to beating the incumbent on accuracy), whereas P33's quasi-likelihood IRLS is
shared scoring machinery applied identically to every arm and its K0_MATCHED null; the constant
dispersion cancels from the quasi-score, so point estimates are unaffected and no
likelihood-based SE is ever used (all inference is cluster bootstrap). And the note itself is
flagged "NOT verified by the coordinator". But that reconciliation is currently **my** prose, not
the frozen record's. A preregistration whose estimator sits, unacknowledged, inside a family its
own cited source retired is an audit defect.

**Required change (before P35 freeze):** add to the frozen preregistration record an explicit
reconciliation: quote the retired-families sentence in full, state that the retirement bounded
challenger accuracy families and does not bind the shared estimation objective, and state the
scope of the 0.193 citation (constant-dispersion cancellation in the quasi-score only). If the
adjudicator disagrees with that reading, HALT (see stop-condition note above).

### B2 — The regulation-equivalent rescale of lagged realized pace is formula-free for A08–A11 and ambiguous for A12/A16 (SEVERITY B)

The target and the archived projection are in **period-based** regulation-equivalent units
(measured: normalizer `40/(40 + 5*max(0, max_period-4))`, re-derivation dev 0.0). Six arms build
treatments from "prior-game realized regulation-equivalent pace/possessions", but the rescale
formula is pinned nowhere:

* **A08, A09, A10, A11** — `pace(j)` / `d_t` / `dcur_t` / `dprev_t` are all defined as
  "realized regulation-equivalent pace" of strictly earlier games, with **no construction formula
  anywhere in the arm records**. D9's disposition freezes OT conventions for exactly three arms
  (A12, A16, A26) and is silent on these four. P32's Review A (F8) flagged precisely this fifth
  divergence "so the preregistration node cannot silently harmonize the units" — P33 recorded D9
  but left the TS arms' convention as a name without a formula.
* **A16** — the D9 convention reads "normalization by **regulation-equivalent duration from
  lagged duration_sec/period aggregates**". Two non-equivalent readings: (a) period-based
  (matches the target and the archived projection it is differenced against); (b)
  duration_sec-based (sum of possession clock-seconds ≠ 2400s in regulation games in general).
  Under reading (b), `dev_team = realized_reg_equiv − archived_projection` mixes two conventions
  and the "residual" carries a systematic convention artifact concentrated on lagged-OT games —
  a unit-incoherent treatment sold as a residual.
* **A12** — "OT rescaled using that game's OWN lagged duration/overtime columns" has the same
  duration-vs-period ambiguity.

This is not leakage (all constructions strictly lagged; lagged OT/duration columns are
LAGGED_USE_ONLY-licensed, and the same-game prohibition is untouched) and not a K0-parity break
(arm and null share whichever reading lands). But it leaves a **unit-construction judgment call
to the P36 implementer after the preregistration freeze**, which is exactly the discretion this
program forbids, and it was the P32 review's explicit instruction to close.

**Required change (before/at P35 task-card freeze):** pin, per arm (A08, A09, A10, A11, A12,
A16), that prior-game realized regulation-equivalent possessions/pace := the lagged value of the
frozen target construction itself — `n_off_poss * 40 / (40 + 5*max(0, max_period - 4))`,
i.e. the lagged `realised_team_off_possessions_reg_equiv` — and strike the duration_sec reading
of the A16/A12 wording. A26 stays raw per D9; pinning the other five is completing a
specification, not harmonizing D9 (the three frozen conventions remain distinct).

### C1 — Quasi-Poisson coherence for a continuous-ish target: VERIFIED, with a recorded dispersion-heterogeneity caveat (SEVERITY C)

The known self-frozen convention holds up on the unit question. The quasi-likelihood score
`sum_i x_i (y_i − mu_i)` and the quasi-Poisson deviance are defined for non-integer y > 0;
measured min(target) = 66 > 0, no NaN; 120/2,982 rows (4.02%) are non-integer; IRLS with a
1e-10 deviance tolerance is well-posed on every row. The constant dispersion cancels from the
score, so the draft's "dispersion biases only likelihood-based SEs, which are never used" is
correct as far as it goes. **Caveat to record:** the regulation-equivalent rescale makes the
mean–variance relation per-row heterogeneous — if raw counts satisfy var ∝ mean with dispersion
φ, the rescaled target satisfies var(y) = (40/g)·φ·mean(y), so OT rows carry effective dispersion
φ·{8/9, 4/5, 2/3} vs φ on regulation rows. IRLS weights (∝ mu under constant φ) are therefore
mildly mis-specified on the 4.4% OT rows. This is identical in arm and null, touches no promotion
decision, and bootstrap inference is immune; but "dispersion is irrelevant" should be read as
"the constant-φ factor cancels", not "the variance model is right". Record; no change required.

### C2 — Notation unification incomplete: three notations persist and eight arms state no predictor equation (SEVERITY C)

P32's Review K0/identifiability (F6) found three incompatible notations; its mandated fix
(name the frozen inference spec by path+hash; pin the centered-offset scale for A01/A02/A04)
**was** executed by P33 — `inference_spec_gap_resolution` carries the path, sha256 and line
numbers, and `centered_offset_treatment_scale` pins A01/A04 (log scale) and A02 (natural scale)
with measured identities. But the notations themselves were not unified: measured census —
`eta =` (11 arms), `log E[y] =` (4), `y ~ offset(log_exposure)` (3), and **no linear-predictor
statement at all in A17, A18, A19, A20, A21, A22, A24, A26** (their formula fields define only the
feature). Only A01 states `mu = exp(eta)`. Every arm is nevertheless determined in substance:
`shared_arm_invariants.link = log`, offset = log_exposure, and each `k0_matched` block names the
exact treatment term, so the model is `mu = exp(log_exposure + nuisance + coef·x)` everywhere,
and the three notations are mutually consistent under that reading. Recommend (not require): P35
task cards render the full `eta` and `mu = exp(eta)` for each arm mechanically, so no implementer
ever infers a predictor from a feature definition.

### C3 — A26 raw-count convention: preregistered honestly; prevalence bound now measured (SEVERITY C)

The mandate asked whether A26's D9-preserved raw-count trailing pace is preregistered honestly
and bounded by P28. **Honest: yes.** The arm record states the OT symmetric-cancellation
assertion is "UNMEASURED and preserved as such", forbids reinterpretation, and declares that any
OT adjustment would be a separate (unproposed) arm; D9 explicitly bars harmonization. **Bounded
by P28: yes** — A26 runs the shared primary gate, whose clause (d) freezes the possession verdict
before any downstream turnover number and bars rescue; A26's value channel is the possession
target itself. New bound from this review: 66/1,491 games (4.43%) are OT; a raw prior-game count
overstates the regulation-equivalent scale by factors up to 1.5× (one 8-period game), so with the
E=3 minimum window a single OT prior game can move `raw_t` by several possessions, and own vs
LOO-opponent OT histories need not match — the cancellation is approximate, exactly as P32's F8
said. The mismatch is a noise/attenuation channel that can only hurt A26 against its own null,
and a kill is interpretable as mechanism-as-constructed-on-this-convention. Optional improvement:
copy the measured prevalence bound (66/1,491; factors {8/9, 4/5, 2/3}) into the arm record so the
"unmeasured" assertion is at least bracketed in the frozen bytes. No required change.

### C4 — Citation (3) of the link derivation is cross-lane and does not describe the possession design (SEVERITY C)

`inference_spec_gap_resolution` cites GATE_INVOCATION_CONTRACT §3.1 (line 117): "every
**turnover** arm carries log(exposure) **(and log(D))** in the offset". That sentence describes
the turnover lane, whose offset includes a log-duration term; no possession arm carries log(D) —
duration is *prohibited* from the possession prediction path. As a tertiary "program-wide
convention" gloss it is harmless, and citations (1) and (2) (the receipted log-offset object plus
exact incumbent recovery at zero treatment) fix the link on their own — I verified the recovery
identity numerically (measurement 2). But the frozen record should not lean on §3.1 as if it
described this design; if quoted, quote it as the *turnover-lane* instance of the log-offset
convention. Record; wording-level fix at most.

### C5 — A02's blend-weight gloss is a natural-scale story tested by a multiplicative model (SEVERITY C)

A02's mechanism reads "the optimal blend weight on own_est exceeds one half". A reweighted blend
is natural-scale additive: `mu = proj + w·gap`. The frozen model is multiplicative:
`mu = proj·exp(gamma·gap)`; the two coincide only to first order (`gamma ≈ w/proj`), and gamma's
unit is 1/possessions — it is not a blend weight. K0 nesting is exact, incumbent recovery at
gamma = 0 is exact, and the scale of the contrast is correctly pinned NATURAL with measured
orthogonality to the offset, so nothing is unfair; but a promotion of A02 licenses "the
log-linear gap coefficient is positive", not "the blend weight exceeds one half" in the additive
sense. Same first-order reading applies to every natural-scale covariate under the log link
(gap, dev, rest days, seconds, shares) — standard GLM practice, coherent, recorded here once.

## Explicitly verified clean (so silence is not read as omission)

* Offset ↔ target unit coherence: exp(offset) is the regulation-equivalent projection; target is
  regulation-equivalent by the identical period-based normalizer (dev 0.0). The primary MAE gate
  is computed in target units for arm and null alike.
* K0 unit parity: K0_MATCHED shares the target column and offset by construction
  (`k0_input == incumbent_input`); every per-arm null in the SPEC carries `log_exposure` and
  "identical machinery".
* A01/A04 centered-offset treatment on the log scale and A02 on the natural scale: pinned in the
  draft, derivations sound, identities measured at 0.0 by P33 and re-checked here.
* Zero-treatment incumbent recovery under the log link: exact (measurement 2) — the link
  derivation's central claim holds on the bytes.
* Mixed covariate units across arms (possessions, seconds, days, dimensionless shares/indicators)
  beside a log-scale offset: coherent per-arm as GLM covariates; no arm adds a log-scale quantity
  to a natural-scale quantity inside one term.
* A16's dev differencing realized against the ARCHIVED projection: both sides regulation-
  equivalent **provided B2's pin lands**; archive retrievability was already resolved by P33.

## What I could NOT establish

* The **net** OT contamination of A26's `z5` (and the truth of the symmetric-cancellation
  assertion): requires building the lagged LOO feature, which is P36 implementation scope. I
  measured only the prevalence bound (66/1,491 games; inflation factors ≤ 1.5×).
* Whether P36 would in fact have implemented A08–A11/A16 with the period-based convention absent
  B2: unknowable from the frozen bytes — which is the finding.
* Whether the V2 retired-families note's scope ("challenger families" vs "any Poisson-family
  estimator") has an authoritative prior adjudication anywhere in the program record: I searched
  the P33 inputs and found none; hence B1 demands the reconciliation be written rather than
  assumed.

## Contradictions found (documents vs documents/bytes)

1. **P33 SPEC/REPORT vs V2_STOP_CONDITION.json line 189** (Finding B1): the estimation-objective
   freeze cites the retired-families sentence for 0.193 while that sentence retires count/Poisson
   GLMs and log transforms; the tension is nowhere reported in P33's contradiction list.
2. **P33 D9 disposition vs P32 Review A F8** (Finding B2): F8 identified the raw-vs-regulation-
   equivalent divergence as touching "the TS arms and A16"; P33's D9 freeze covers A12/A16/A26
   only, leaving A08–A11's convention named but not constructed.
3. **GATE_INVOCATION_CONTRACT §3.1 vs the possession design** (Finding C4): the cited offset
   convention sentence describes turnover arms with a log(D) term the possession lane prohibits.

## Verdict

**ACCEPT_WITH_REQUIRED_CHANGES.** No finding invalidates an arm, admits leakage, or breaks
K0/target unit parity (no Severity A). Two changes are required before the P35 task-card freeze:

1. (B1) Write the reconciliation of the quasi-Poisson IRLS freeze with the V2 retired-families
   sentence into the frozen record — or, if the adjudicator reads the retirement as binding,
   HALT (inference-structure stop condition).
2. (B2) Pin the period-based regulation-equivalent construction (lagged
   `realised_team_off_possessions_reg_equiv`, i.e. `n_off * 40 / (40 + 5*max(0, max_period-4))`)
   for every lagged realized-pace quantity in A08, A09, A10, A11, A12 and A16; strike the
   duration_sec reading. A26 remains raw per D9.

---

## Appendix — measurement script (run once, verbatim)

```python
"""P34 target-unit reviewer measurements.

Schema / identity / unit checks ONLY:
- no model is fitted
- no projection is ever compared against any realised value (no residual, no MAE,
  no accuracy statistic of any kind is computed)
- nothing under SEALED_RESULTS is read
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program")
PP = ROOT / "experiments" / "player_program"
sys.path.insert(0, str(PP))

import possession_features as pf  # noqa: E402

out = {}

u = pf.load_universe()
F = u.frame
out["universe"] = {"rows": int(len(F)), "clusters": int(F["game_id"].nunique())}

t = F[pf.TARGET_COLUMN].to_numpy(dtype=float)

# 1. target positivity / support (log-link + quasi-Poisson deviance definedness)
out["target_support"] = {
    "min": float(t.min()), "max": float(t.max()),
    "n_nonpositive": int((t <= 0).sum()),
    "n_nan": int(np.isnan(t).sum()),
}

# 2. integer vs non-integer target values (family-coherence question)
frac = np.abs(t - np.round(t))
is_integer = frac < 1e-9
out["target_integrality"] = {
    "n_integer": int(is_integer.sum()),
    "n_noninteger": int((~is_integer).sum()),
    "share_noninteger": float((~is_integer).mean()),
}

# 3. re-derive the target from the frozen possessions artifact with the exact
#    period-based formula and confirm the universe column IS that construction
p = pd.read_parquet(pf.POSSESSIONS_PARQUET, columns=["game_id", "period", "offense_team_id"])
n_off = (p.groupby(["game_id", "offense_team_id"]).size().rename("n_off")
         .reset_index().rename(columns={"offense_team_id": "team_id"}))
max_period = p.groupby("game_id")["period"].max().rename("max_period").reset_index()
n_off = n_off.merge(max_period, on="game_id", how="left")
gm = 40.0 + 5.0 * np.maximum(0, n_off["max_period"] - 4)
n_off["re_target"] = n_off["n_off"] * 40.0 / gm
m = F.reset_index(drop=True).merge(n_off, on=["game_id", "team_id"], how="left", validate="1:1")
out["target_rederivation"] = {
    "max_abs_dev_vs_universe_target":
        float(np.max(np.abs(m["re_target"].to_numpy() - m[pf.TARGET_COLUMN].to_numpy()))),
    "normalizer": "40 / (40 + 5*max(0, max_period - 4)) -- PERIOD-count based, not duration_sec",
}

# 4. OT prevalence in the universe (per season) and the per-row rescale factor set.
mp = m.drop_duplicates("game_id")
ot = mp[mp["max_period"] > 4]
out["ot_prevalence"] = {
    "n_games": int(len(mp)),
    "n_ot_games": int(len(ot)),
    "share_ot_games": float(len(ot) / len(mp)),
    "ot_games_by_season": {int(k): int(v)
                           for k, v in ot.groupby(mp.loc[ot.index, "season"]).size().items()},
    "max_period_histogram": {int(k): int(v)
                             for k, v in mp["max_period"].value_counts().sort_index().items()},
    "rescale_factor_values": sorted(set((40.0 / (40.0 + 5.0 * np.maximum(0, mp["max_period"] - 4))).round(6))),
}

# 5. offset unit identity: exp(offset) == projected_team_off_possessions exactly
off = F[pf.OFFSET_COLUMN].to_numpy(dtype=float)
proj = F["projected_team_off_possessions"].to_numpy(dtype=float)
out["offset_identity"] = {
    "max_abs_dev_exp_offset_vs_projection": float(np.max(np.abs(np.exp(off) - proj))),
    "projection_min": float(proj.min()), "projection_max": float(proj.max()),
}

# 6. per-fold OT counts in TEST sets (unit-heterogeneity exposure by fold)
folds = pf.chronological_folds(u)
fold_ot = {}
ot_ids = set(ot["game_id"])
for f in folds:
    test = F.loc[f.test_index]
    test_games = test["game_id"].drop_duplicates()
    fold_ot[f.fold_id] = {"test_games": int(len(test_games)),
                          "test_ot_games": int(test_games.isin(ot_ids).sum())}
out["ot_by_fold_test"] = fold_ot

# 7. notation census over the P33 SPEC formula fields (document measurement)
spec = json.loads((PP / "stage2b" / "P33_PREREGISTRATION_DRAFT" / "SPEC.json").read_text(encoding="utf-8"))
census = {"eta =": [], "log E[y]": [], "y ~ offset(": [], "no_predictor_statement": []}
for arm in spec["arms"]:
    fml = arm["formula"]
    aid = arm["arm_id"].split("_")[0]
    if "log E[y]" in fml:
        census["log E[y]"].append(aid)
    elif "y ~ offset(" in fml:
        census["y ~ offset("].append(aid)
    elif "eta =" in fml or "eta=" in fml:
        census["eta ="].append(aid)
    else:
        census["no_predictor_statement"].append(aid)
out["notation_census"] = census
out["mu_exp_eta_stated"] = [a["arm_id"].split("_")[0] for a in spec["arms"]
                            if "exp(eta)" in a["formula"]]

print(json.dumps(out, indent=2))
```

Complete output of that run (verbatim):

```json
{
  "universe": {"rows": 2982, "clusters": 1491},
  "target_support": {"min": 66.0, "max": 94.0, "n_nonpositive": 0, "n_nan": 0},
  "target_integrality": {"n_integer": 2862, "n_noninteger": 120, "share_noninteger": 0.04024144869215292},
  "target_rederivation": {"max_abs_dev_vs_universe_target": 0.0,
    "normalizer": "40 / (40 + 5*max(0, max_period - 4)) -- PERIOD-count based, not duration_sec"},
  "ot_prevalence": {"n_games": 1491, "n_ot_games": 66, "share_ot_games": 0.04426559356136821,
    "ot_games_by_season": {"2021": 16, "2022": 12, "2023": 11, "2024": 10, "2025": 8, "2026": 9},
    "max_period_histogram": {"4": 1425, "5": 60, "6": 5, "8": 1},
    "rescale_factor_values": [0.666667, 0.8, 0.888889, 1.0]},
  "offset_identity": {"max_abs_dev_exp_offset_vs_projection": 4.263256414560601e-14,
    "projection_min": 73.725, "projection_max": 84.35},
  "ot_by_fold_test": {
    "train_lt_2022": {"test_games": 239, "test_ot_games": 12},
    "train_lt_2023": {"test_games": 260, "test_ot_games": 11},
    "train_lt_2024": {"test_games": 262, "test_ot_games": 10},
    "train_lt_2025": {"test_games": 310, "test_ot_games": 8},
    "train_lt_2026": {"test_games": 215, "test_ot_games": 9}},
  "notation_census": {
    "eta =": ["A01", "A02", "A03", "A04", "A05", "A06", "A07", "A12", "A13", "A14", "A15"],
    "log E[y]": ["A08", "A09", "A10", "A11"],
    "y ~ offset(": ["A16", "A23", "A25"],
    "no_predictor_statement": ["A17", "A18", "A19", "A20", "A21", "A22", "A24", "A26"]},
  "mu_exp_eta_stated": ["A01"]
}
```
