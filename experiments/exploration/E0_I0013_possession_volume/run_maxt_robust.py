"""
E0 I0013 stage 2.

A. FAMILY-WISE max-T randomization null across all 27 cells.  A 27-test sweep at nominal
   frac_ge_real of 0.00-0.03 predicts about one false positive per 40 tests at p=0.025, so no cell
   can be kept on its own nominal placebo alone.  The null here is JOINT: for each draw a single
   opponent-side team relabelling per season is applied to EVERY opponent candidate and to EVERY
   target simultaneously, and a single own-side relabelling to every own-team candidate.  That
   reproduces the real correlation structure between cells instead of pretending they are
   independent, so the max-T null is neither too wide nor too narrow.

B. MECHANISM ROBUSTNESS on the cells that clear the family-wise bar (and on the near misses):
   R1  add ACTUAL MINUTES PLAYED to the base.  Actual minutes is NOT pregame-observable; this rung
       is a MECHANISM DIAGNOSTIC, not a forecasting model, and is labelled as such.  Prediction: a
       possession-VOLUME effect should survive, because a fast game does not lengthen the game --
       it packs more possessions into the same 40 minutes.
   R2  add ACTUAL PLAYER POSSESSIONS to the base (also not pregame-observable; also a diagnostic).
       Prediction: a possession-volume effect should be LARGELY ABSORBED, because realised
       possessions is the mediator the pregame instrument is supposed to be forecasting.  If a
       candidate survives R2 it is NOT a possession-volume channel and its story is wrong.
   R3  SUM vs DIFFERENCE.  exp_gposs is exactly 0.5*(opp_pace48 + own_pace48), so putting all three
       in one model is rank-deficient -- exactly the void rung I0012 recorded.  The estimable
       reparameterisation is {sum, difference}: test the 2-df joint increment of the two sides
       against the 1-df increment of the sum, and then the 1-df increment of (opp - own) GIVEN the
       sum.  If the difference is dead, the sum is the right one-number summary and the effect is
       symmetric game tempo, NOT an opponent matchup.

Run:  python run_maxt_robust.py    (stdout captured to run_log_maxt_robust.txt)
"""
import json
import os
import time

import numpy as np
import pandas as pd

import pv_base as P
import base as B
from run_screen_defs import CANDS, DIRECTION_LABEL          # candidate registry, shared

t0 = time.time()
rng = np.random.default_rng(P.SEED + 1)
NDRAW_MAXT = 400

prior = json.load(open(os.path.join(P.OUT, "screen_results.json"), "r", encoding="utf-8"))
CELLS = {(c["target"], c["candidate"]): c for c in prior["cells"]}


def prep_fast(y, basecols):
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in basecols])
    Q, _ = np.linalg.qr(X)
    return Q, y - Q @ (Q.T @ y), float(((y - y.mean()) ** 2).sum())


def incr(Q, ry, sst, m):
    """Identical to run_screen.incr, including the non-finite guard.  Non-finite entries can
    appear ONLY in a permuted draw: a permutation can hand a row an opponent whose pregame value
    was still undefined at that date (fewer than 300 prior possessions).  Those entries are set to
    the season mean by center_within, exactly as in stage 1."""
    m = np.asarray(m, float)
    if not np.all(np.isfinite(m)):
        m = np.where(np.isfinite(m), m, np.nanmean(m[np.isfinite(m)]))
    rm = m - Q @ (Q.T @ m)
    den = float(rm @ rm)
    return 0.0 if den <= 1e-12 else float((ry @ rm) ** 2 / den) / sst


def center_within(v, seas):
    v = np.asarray(v, float)
    out = np.empty_like(v)
    for s in np.unique(seas):
        m = seas == s
        out[m] = np.where(np.isfinite(v[m]), v[m] - np.nanmean(v[m]), 0.0)
    return out


class TeamPanel:
    def __init__(self, teampre, field):
        self.teams, self.dates, self.vals = {}, {}, {}
        for s, g in teampre.groupby("season"):
            piv = (g.pivot_table(index="gdate", columns="team_id", values=field, aggfunc="first")
                     .sort_index().ffill())
            self.teams[s] = piv.columns.to_numpy()
            self.dates[s] = piv.index.to_numpy()
            self.vals[s] = piv.to_numpy(dtype=float)

    def bind(self, frame, keycol):
        n = len(frame)
        A = np.full((n, 12), np.nan)
        col0 = np.zeros(n, dtype=int)
        seas, gd, key = (frame["season"].to_numpy(), frame["gdate"].to_numpy(),
                         frame[keycol].to_numpy())
        for s in np.unique(seas):
            m = seas == s
            pos = np.searchsorted(self.dates[s], gd[m], side="right") - 1
            A[m, :] = self.vals[s][pos, :]
            tmap = {t: i for i, t in enumerate(self.teams[s])}
            col0[m] = [tmap[k] for k in key[m]]
        return A, col0, seas


def apply_perm(A, col0, seas, perms):
    out = np.empty(len(col0))
    for s in np.unique(seas):
        idx = np.where(seas == s)[0]
        out[idx] = A[idx, perms[s][col0[idx]]]
    return out


def block_clusters(frame, keycol):
    df = pd.DataFrame({"i": np.arange(len(frame)), "s": frame["season"].to_numpy(),
                       "k": frame[keycol].to_numpy(), "d": frame["gdate"].to_numpy()})
    df = df.sort_values(["s", "k", "d"])
    g = {}
    for (s, k), gg in df.groupby(["s", "k"], sort=False):
        g.setdefault(s, []).append(gg["i"].to_numpy())
    return g


def perm_block(groups, v, rng):
    out = np.empty(len(v))
    for s, blocks in groups.items():
        order = rng.permutation(len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[order[i]]
            out[b] = v[don[np.arange(len(b)) % len(don)]]
    return out


# =============================================================================== rebuild frames
P.hdr("REBUILD FRAMES (identical to run_screen.py; R2_base is asserted to reproduce)")
mp = B.load_player()
mt = B.load_team()
TEAM = P.build_team_pre(mt)
PANEL = {f: TeamPanel(TEAM, f) for f in P.TEAM_FIELDS}
cand_cols = [c["name"] for c in CANDS if c["side"] in ("opp", "own")]

F = {}
for T in P.TARGETS:
    W = P.build_analysis_frame(mp, TEAM, T, cand_cols)
    y = W["s"].to_numpy(float)
    basecols = [W["O"].values, W["D"].values, W["OD"].values, W["ME"].values, W["OME"].values]
    Q, ry, sst = prep_fast(y, basecols)
    r2b = P.r2(y, basecols)
    ref = CELLS[(T, "opp_pace48")]["R2_base"]
    assert abs(r2b - ref) < 1e-12, "frame mismatch for %s: %.12f vs %.12f" % (T, r2b, ref)
    print("  %s  n=%d  R2_base=%.10f  (reproduces run_screen.py exactly)" % (T, len(W), r2b))
    F[T] = dict(W=W, y=y, basecols=basecols, Q=Q, ry=ry, sst=sst,
                seas=W["season"].to_numpy())

# =============================================================================== A. max-T
P.hdr("A. FAMILY-WISE max-T RANDOMIZATION NULL over all 27 cells (%d draws)" % NDRAW_MAXT)
BIND = {}
for T in P.TARGETS:
    W = F[T]["W"]
    for cd in CANDS:
        if cd["side"] in ("opp", "both"):
            BIND[(T, cd["name"], "opp")] = PANEL[cd["field"]].bind(W, "opp_team_id")
        if cd["side"] in ("own", "both"):
            BIND[(T, cd["name"], "own")] = PANEL[cd["field"]].bind(W, "team_id")
    BIND[(T, "ppm", "blk")] = block_clusters(W, "player_id")

real_z, moments = {}, {}
for (T, nm), c in CELLS.items():
    mu, sd = c["placebo"]["mean"], c["placebo"]["sd"]
    moments[(T, nm)] = (mu, sd)
    real_z[(T, nm)] = (c["dR2_M"] - mu) / sd

maxz = []
allz = {k: [] for k in CELLS}
for it in range(NDRAW_MAXT):
    perm_opp = {s: rng.permutation(12) for s in P.PARTITION}
    perm_own = {s: rng.permutation(12) for s in P.PARTITION}
    zs = []
    for T in P.TARGETS:
        f = F[T]
        for cd in CANDS:
            nm = cd["name"]
            if cd["side"] == "opp":
                A, c0, sq = BIND[(T, nm, "opp")]
                v = apply_perm(A, c0, sq, perm_opp)
            elif cd["side"] == "own":
                A, c0, sq = BIND[(T, nm, "own")]
                v = apply_perm(A, c0, sq, perm_own)
            elif cd["side"] == "both":
                A, c0, sq = BIND[(T, nm, "opp")]
                A2, c02, _ = BIND[(T, nm, "own")]
                v = 0.5 * (apply_perm(A, c0, sq, perm_opp) + apply_perm(A2, c02, sq, perm_own))
            else:
                sq = f["seas"]
                v = perm_block(BIND[(T, "ppm", "blk")], f["W"]["ppm"].to_numpy(float), rng)
            d = incr(f["Q"], f["ry"], f["sst"], center_within(v, sq))
            mu, sd = moments[(T, nm)]
            z = (d - mu) / sd
            allz[(T, nm)].append(z)
            zs.append(z)
    assert np.all(np.isfinite(zs)), "non-finite z in max-T draw %d" % it
    maxz.append(max(zs))

maxz = np.array(maxz)
assert np.all(np.isfinite(maxz)), "max-T null contains non-finite values"
print("  max-T null: mean=%.2f sd=%.2f p50=%.2f p95=%.2f p99=%.2f max=%.2f"
      % (maxz.mean(), maxz.std(ddof=1), np.percentile(maxz, 50), np.percentile(maxz, 95),
         np.percentile(maxz, 99), maxz.max()))
print("\n  %-5s %-13s %10s %8s %10s %12s  %s"
      % ("tgt", "candidate", "dR2_M", "z", "nominal", "familywise_p", "family-wise verdict"))
fw = {}
for (T, nm), c in sorted(CELLS.items(), key=lambda kv: -kv[1]["dR2_M"]):
    z = real_z[(T, nm)]
    p = float((maxz >= z).mean())
    fw[(T, nm)] = dict(z=float(z), familywise_p=p,
                       nominal_frac_ge_real=c["placebo"]["frac_ge_real"])
    print("  %-5s %-13s %10.6f %8.2f %10.3f %12.3f  %s"
          % (T, nm, c["dR2_M"], z, c["placebo"]["frac_ge_real"], p,
             "SURVIVES family-wise" if p <= 0.05 else "killed on multiplicity"))
pd.DataFrame({"maxT_null_z": maxz}).to_csv(os.path.join(P.OUT, "maxt_null_draws.csv"), index=False)

# =============================================================================== B. robustness
P.hdr("B. MECHANISM ROBUSTNESS")
ROB = []
FOCUS = [("ast", "exp_gposs"), ("pts", "exp_gposs"), ("reb", "exp_gposs"),
         ("reb", "opp_pace48"), ("pts", "opp_fgaA48"), ("ast", "opp_pace48"),
         ("pts", "opp_orebA100"), ("pts", "ppm"), ("ast", "ppm")]
print("  R1 = + ACTUAL MINUTES (post-hoc control, mechanism diagnostic only, NOT pregame)")
print("  R2 = + ACTUAL PLAYER POSSESSIONS (post-hoc mediator, mechanism diagnostic only)")
print("\n  %-5s %-13s %10s %10s %8s %10s %8s"
      % ("tgt", "candidate", "dR2_base", "dR2_R1", "keep%", "dR2_R2", "keep%"))
for (T, nm) in FOCUS:
    f = F[T]
    W, y, bc = f["W"], f["y"], f["basecols"]
    Mz = B.zwithin(W, nm).to_numpy(float)
    Mres = P.residualize_and_scale(Mz, W["D"].values, W["OD"].values)
    d0 = incr(f["Q"], f["ry"], f["sst"], Mres)
    amin = W["minutes"].to_numpy(float)
    aposs = W["possessions"].to_numpy(float)
    q1 = prep_fast(y, bc + [amin, W["O"].values * amin])
    q2 = prep_fast(y, bc + [aposs, W["O"].values * aposs])
    d1, d2 = incr(*q1, Mres), incr(*q2, Mres)
    print("  %-5s %-13s %10.6f %10.6f %7.0f%% %10.6f %7.0f%%"
          % (T, nm, d0, d1, 100 * d1 / d0 if d0 else np.nan, d2,
             100 * d2 / d0 if d0 else np.nan))
    ROB.append(dict(target=T, candidate=nm, dR2_base=float(d0),
                    dR2_given_actual_minutes=float(d1), dR2_given_actual_possessions=float(d2),
                    retained_vs_minutes=float(d1 / d0) if d0 else None,
                    retained_vs_possessions=float(d2 / d0) if d0 else None))

P.hdr("B2. SUM vs DIFFERENCE (the estimable reparameterisation; avoids I0012's void rank-deficient rung)")
print("  exp_gposs = 0.5*(opp_pace48 + own_pace48).  {sum, diff} spans the same 2-d space as")
print("  {opp, own} and is FULL RANK, so both increments below are estimable.\n")
print("  %-5s %10s %10s %10s %10s   %s"
      % ("tgt", "dR2_sum", "dR2_joint2", "dR2_diff|sum", "beta_diff", "reading"))
SUMDIFF = []
for T in P.TARGETS:
    f = F[T]
    W, y, bc = f["W"], f["y"], f["basecols"]
    zsum = B.zwithin(W, "exp_gposs").to_numpy(float)
    zdif = B.zwithin(W, "opp_pace48").to_numpy(float) - B.zwithin(W, "own_pace48").to_numpy(float)
    rs = P.residualize_and_scale(zsum, W["D"].values, W["OD"].values)
    rd = P.residualize_and_scale(zdif, W["D"].values, W["OD"].values)
    r_b = P.r2(y, bc)
    d_sum = P.r2(y, bc + [rs]) - r_b
    d_joint = P.r2(y, bc + [rs, rd]) - r_b
    d_dif = d_joint - d_sum
    b_dif = float(P.ols(y, bc + [rs, rd])[0][-1])
    reading = ("symmetric game tempo (difference dead) -> NOT an opponent matchup"
               if d_dif < 0.15 * d_sum else "asymmetric -> opponent-specific component present")
    print("  %-5s %10.6f %10.6f %10.6f %10.4f   %s" % (T, d_sum, d_joint, d_dif, b_dif, reading))
    SUMDIFF.append(dict(target=T, dR2_sum=float(d_sum), dR2_joint_2df=float(d_joint),
                        dR2_diff_given_sum=float(d_dif), beta_diff=b_dif, reading=reading))

out = dict(maxt=dict(n_draws=NDRAW_MAXT,
                     null_p50=float(np.percentile(maxz, 50)),
                     null_p95=float(np.percentile(maxz, 95)),
                     null_max=float(maxz.max()),
                     per_cell={"%s|%s" % k: v for k, v in fw.items()}),
           robustness=ROB, sum_vs_diff=SUMDIFF,
           elapsed_sec=round(time.time() - t0, 1))
with open(os.path.join(P.OUT, "maxt_robust_results.json"), "w", encoding="utf-8") as fjs:
    json.dump(out, fjs, indent=1, default=float)
print("\n  wrote maxt_robust_results.json  (%.1fs)" % (time.time() - t0))
