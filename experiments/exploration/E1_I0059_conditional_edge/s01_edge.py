"""s01_edge.py -- is there an observable pre-game state where our model beats the market?

Executes the frozen PREREG. Seeds, splits, conditioners and thresholds are read from it and
are not parameters of this script.

ONE PREREG DEFECT IS HANDLED EXPLICITLY RATHER THAN SILENTLY (see DEFECTS.md D1). PREREG
section 5.2 says the subgroup label is reassigned "at the game level (whole games move
together)". That is ill-defined for four of the five conditioners, because n_prior_games,
min_hat, M1 and line_sd vary BETWEEN PLAYERS INSIDE THE SAME GAME -- there is no single label
for a game to carry. Rather than pick a reading quietly, this script computes TWO nulls that
bracket the intent and reports the MORE CONSERVATIVE (larger) p-value as the headline:

  PERM_WITHIN_GAME  -- labels permuted inside each game, so every game keeps its own label
                       composition and every d value is untouched. This is the closest
                       faithful reading of "preserving d's within-game structure".
  PERM_WITHIN_PLAYER-- labels permuted inside each player, preserving player-level structure,
                       which matters because the strongest conditioner (C1) is a player
                       property and a game-only null would leave player effects free to drive
                       the result.

Neither is anticonservative in the way a plain row-level shuffle would be (D093/D115/D117).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FRAME = HERE.parent / "E1_I0058_market_benchmark" / "out" / "analysis_frame.csv"
FRAME_SHA = "8605a559fc66076990055a35c3b932c9f242d665656d795e018ce2b9a547b7c8"

# ---- FROZEN BY PREREG ------------------------------------------------------------------
SEED_BOOT, SEED_PERM, N_BOOT, N_PERM = 20260819, 20260820, 5000, 5000
ALPHA_FAMILY = 0.05
N_CONDITIONERS = 5
ALPHA = ALPHA_FAMILY / N_CONDITIONERS          # 0.01, Bonferroni
CI_PCT = (0.5 * ALPHA * 100, 100 - 0.5 * ALPHA * 100)   # 99% interval
MATERIALITY = 0.10
POWER_K = 2.802

PREREG_SHA = open(HERE / "PREREG.sha256").read().split()[0]
assert hashlib.sha256((HERE / "PREREG.md").read_bytes()).hexdigest() == PREREG_SHA, \
    "PREREG.md does not match its frozen hash -- refusing to run"

log_lines: list[str] = []


def L(s=""):
    print(s)
    log_lines.append(s)


# ---- FRAME ------------------------------------------------------------------------------
got = hashlib.sha256(FRAME.read_bytes()).hexdigest()
assert got == FRAME_SHA, f"analysis frame hash moved: {got}"
A = pd.read_csv(FRAME)
assert set(A.season.unique()) == {2024}, "PARTITION"

L("=" * 96)
L("E1_I0059_conditional_edge -- where, if anywhere, does the model beat the market?")
L("=" * 96)
L(f"  PREREG   {PREREG_SHA}")
L(f"  frame    {got}")
L(f"  n={len(A)}  players={A.player_id.nunique()}  games={A.gid.nunique()}  season 2024 only")
L(f"  seeds boot={SEED_BOOT} perm={SEED_PERM}; draws {N_BOOT}/{N_PERM}")
L(f"  Bonferroni alpha = {ALPHA_FAMILY}/{N_CONDITIONERS} = {ALPHA}; intervals are "
  f"{100 - ALPHA * 100:.0f}%")
L("  POPULATION: book-priced player-games only (40.2% of played rows). Every number is")
L("              conditional on that selection.")

# ---- RESPONSE ---------------------------------------------------------------------------
y = A.pts.values.astype(float)
d = np.abs(A.M2.values - y) - np.abs(A.F1.values - y)   # >0 => model closer than market
A["d"] = d

L("")
L(f"  response d = |M2-pts| - |F1-pts|;  d>0 means THE MODEL WAS CLOSER")
L(f"  pooled mean(d) = {d.mean():+.4f}   (D141 reported -0.4189; this re-derives it)")

# ---- CONDITIONERS, exactly as frozen ----------------------------------------------------
CONDS = [
    ("C1", "n_prior_games", "median", "thin history (D076)"),
    ("C2", "min_hat", "median", "expected role size (D131)"),
    ("C3", "M1", "median", "volume tier (D134)"),
    ("C4", "line_sd", "gt0", "books disagree at all"),
    ("C5", "is_fallback", "bool", "cold-start path (D092/D139)"),
]


def make_labels(col: str, how: str):
    v = A[col]
    if how == "median":
        cut = float(v.median())
        return (v > cut).values, f"{col} > {cut:g}", f"{col} <= {cut:g}"
    if how == "gt0":
        return (v > 0).values, f"{col} > 0", f"{col} == 0"
    if how == "bool":
        return v.astype(bool).values, f"{col} is True", f"{col} is False"
    raise ValueError(how)


# ---- INFERENCE MACHINERY ----------------------------------------------------------------
def cluster_boot_mean(vals, clusters, seed, ndraw):
    """Bootstrap the mean of `vals`, resampling whole clusters."""
    codes, uniq = pd.factorize(clusters)
    members = [np.where(codes == i)[0] for i in range(len(uniq))]
    rng = np.random.default_rng(seed)
    G = len(uniq)
    out = np.empty(ndraw)
    for i in range(ndraw):
        sel = np.concatenate([members[j] for j in rng.integers(0, G, G)])
        out[i] = vals[sel].mean() if sel.size else np.nan
    return out


def perm_within(labels, dvals, groups, seed, ndraw):
    """Permute the subgroup label INSIDE each group; d is never moved."""
    codes, uniq = pd.factorize(groups)
    members = [np.where(codes == i)[0] for i in range(len(uniq))]
    rng = np.random.default_rng(seed)
    out = np.empty(ndraw)
    lab = labels.copy()
    for i in range(ndraw):
        perm = lab.copy()
        for mm in members:
            if mm.size > 1:
                perm[mm] = rng.permutation(lab[mm])
        a, b = dvals[perm], dvals[~perm]
        out[i] = (a.mean() if a.size else np.nan) - (b.mean() if b.size else np.nan)
    return out


results = []
L("")
L("-" * 96)
L("  PER-SUBGROUP RESULT.  'edge' requires ALL THREE: mean(d)>0, interval excludes 0, mean(d)>=0.10")
L("-" * 96)

for cid, col, how, why in CONDS:
    lab, name_hi, name_lo = make_labels(col, how)
    for side, mask, nm in ((f"{cid}a", lab, name_hi), (f"{cid}b", ~lab, name_lo)):
        sub = A[mask]
        dv = d[mask]
        if len(sub) < 30:
            L(f"  {side:<5} {nm:<26} n={len(sub):<5} SKIPPED (fewer than 30 rows)")
            continue
        bg = cluster_boot_mean(dv, sub.gid.values, SEED_BOOT, N_BOOT)
        bp = cluster_boot_mean(dv, sub.player_id.values, SEED_BOOT, N_BOOT)
        gi = (np.nanpercentile(bg, CI_PCT[0]), np.nanpercentile(bg, CI_PCT[1]))
        pi = (np.nanpercentile(bp, CI_PCT[0]), np.nanpercentile(bp, CI_PCT[1]))
        wide = gi if (gi[1] - gi[0]) >= (pi[1] - pi[0]) else pi
        which = "GAME" if wide is gi else "PLAYER"
        sd = max(float(np.nanstd(bg)), float(np.nanstd(bp)))
        mde = POWER_K * sd
        m = float(dv.mean())
        excl = not (wide[0] <= 0 <= wide[1])
        is_edge = bool(m > 0 and excl and m >= MATERIALITY)
        results.append(dict(id=side, cond=cid, name=nm, why=why, n=int(len(sub)),
                            mean_d=m, ci=[float(wide[0]), float(wide[1])], ci_level=which,
                            sd=sd, mde=float(mde), excludes_zero=bool(excl),
                            material=bool(m >= MATERIALITY), is_edge=is_edge,
                            powered=bool(mde < MATERIALITY)))
        flag = "EDGE" if is_edge else ("real but immaterial" if (m > 0 and excl) else "")
        L(f"  {side:<5} {nm:<26} n={len(sub):<5} mean(d)={m:+.4f}  "
          f"{100 - ALPHA * 100:.0f}% CI [{wide[0]:+.4f}, {wide[1]:+.4f}] ({which})  "
          f"MDE={mde:.4f}  {flag}")

# ---- PERMUTATION NULLS ------------------------------------------------------------------
L("")
L("-" * 96)
L("  PERMUTATION NULLS -- two readings, the MORE CONSERVATIVE is the headline (DEFECTS D1)")
L("-" * 96)
perms = {}
for cid, col, how, why in CONDS:
    lab, name_hi, name_lo = make_labels(col, how)
    obs = d[lab].mean() - d[~lab].mean()
    ng = perm_within(lab, d, A.gid.values, SEED_PERM, N_PERM)
    np_ = perm_within(lab, d, A.player_id.values, SEED_PERM, N_PERM)
    pg = (1 + (np.abs(ng) >= abs(obs)).sum()) / (1 + N_PERM)
    pp = (1 + (np.abs(np_) >= abs(obs)).sum()) / (1 + N_PERM)
    head = max(pg, pp)
    perms[cid] = dict(observed_diff=float(obs), p_within_game=float(pg),
                      p_within_player=float(pp), p_headline=float(head),
                      significant_at_bonferroni=bool(head < ALPHA))
    L(f"  {cid}  obs diff (hi-lo) = {obs:+.4f}   p_game={pg:.4f}  p_player={pp:.4f}  "
      f"-> headline p={head:.4f}  {'SIGNIF' if head < ALPHA else ''}")

# ---- PREDICTIONS ------------------------------------------------------------------------
edges = [r for r in results if r["is_edge"]]
c1a = next(r for r in results if r["id"] == "C1a")   # high n_prior_games
c1b = next(r for r in results if r["id"] == "C1b")   # low  n_prior_games
n_powered = sum(1 for cid, _, _, _ in CONDS
                if all(r["powered"] for r in results if r["cond"] == cid))
spread = max(r["mean_d"] for r in results) - min(r["mean_d"] for r in results)

P = {
    "P1_model_beats_market_nowhere": {
        "prediction": "no subgroup meets all three section-4 criteria",
        "n_qualifying": len(edges),
        "verdict": "PASS" if not edges else "FAIL",
    },
    "P2_thin_history_is_relatively_worse": {
        "prediction": "mean(d) lower in the LOW n_prior_games half (D076)",
        "mean_d_low": c1b["mean_d"], "mean_d_high": c1a["mean_d"],
        "verdict": "PASS" if c1b["mean_d"] < c1a["mean_d"] else "FAIL",
    },
    "P3_screen_is_powered": {
        "prediction": "MDE < 0.10 in at least 3 of 5 conditioners (both halves)",
        "n_conditioners_fully_powered": int(n_powered),
        "verdict": "PASS" if n_powered >= 3 else "FAIL",
    },
    "P4_disadvantage_is_broad": {
        "prediction": "spread of subgroup mean(d) across all subgroups < 0.40",
        "observed_spread": float(spread),
        "verdict": "PASS" if spread < 0.40 else "FAIL",
    },
}

L("")
L("-" * 96)
L("  PREREGISTERED PREDICTIONS")
L("-" * 96)
for k, v in P.items():
    L(f"  {v['verdict']:<5} {k}")
    for kk, vv in v.items():
        if kk not in ("verdict", "prediction"):
            L(f"          {kk} = {vv}")

L("")
L("-" * 96)
if edges:
    L("  AN EDGE SURVIVED. It is a LEAD, NOT A RESULT (GRAPH_POLICY 13.1). It may not be cited,")
    L("  may not size a bet, and requires a preregistered E2 this screen does not request.")
    for r in edges:
        L(f"    {r['id']} {r['name']}  mean(d)={r['mean_d']:+.4f}  n={r['n']}")
else:
    L("  NO SUBGROUP QUALIFIES. The model does not beat the market anywhere this screen looked.")
    L("  Read with the MDE column: where MDE < 0.10 the null is informative; where it is not,")
    L("  that subgroup is UNINFORMATIVE rather than evidence of no edge.")
L("-" * 96)

out = {
    "screen": "E1_I0059_conditional_edge",
    "prereg_sha256": PREREG_SHA,
    "frame_sha256": got,
    "n": int(len(A)),
    "pooled_mean_d": float(d.mean()),
    "alpha_bonferroni": ALPHA,
    "materiality": MATERIALITY,
    "subgroups": results,
    "permutation": perms,
    "predictions": P,
    "n_edges": len(edges),
}
(HERE / "FINDINGS.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
(HERE / "run_log_s01.txt").write_text("\n".join(log_lines), encoding="utf-8")
print(f"\nwrote FINDINGS.json and run_log_s01.txt")
