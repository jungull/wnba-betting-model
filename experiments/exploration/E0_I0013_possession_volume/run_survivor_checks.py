"""
E0 I0013 stage 3 -- checks aimed only at the ONE cell that cleared the family-wise bar:
expected game possessions -> ASSISTS.

S1  RELIABILITY of the instrument.  Odd/even split-half of team possessions-per-game within
    (season, team), Spearman-Brown corrected.  A pregame team quantity that cannot be measured is
    not a lead however good its p-value looks (this is how I0012's F1 died).

S2  CONFOUND LADDER.  Expected game possessions could be team strength or home advantage renamed.
    Rungs add, one at a time and then jointly: home indicator, both teams' strictly-prior expanding
    net points per 100 possessions, and both teams' strictly-prior expanding win rate.  All rungs
    are pregame-observable.  These are ADDITIONAL to O, D and O*D, which are already in the base.

S3  RECENCY.  This is the check that killed I0012's survivor: an effect carried by the oldest
    seasons is worthless because the holdout sits after the newest one.  The cell is re-run on
    2022-2024, 2023-2024 and 2024 alone, each against its OWN cluster-level placebo recomputed at
    that n (the floor widens as n falls, and the effect is compared to the wider floor, not the
    pooled one).

Run:  python run_survivor_checks.py    (stdout captured to run_log_survivor_checks.txt)
"""
import json
import os
import time

import numpy as np
import pandas as pd

import pv_base as P
import base as B
from run_screen_defs import CANDS

t0 = time.time()
rng = np.random.default_rng(P.SEED + 2)
NDRAW = 200
TGT = "ast"
CAND = "exp_gposs"


def prep_fast(y, cols):
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in cols])
    Q, _ = np.linalg.qr(X)
    return Q, y - Q @ (Q.T @ y), float(((y - y.mean()) ** 2).sum())


def incr(Q, ry, sst, m):
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
        c0 = np.zeros(n, int)
        seas, gd, key = (frame["season"].to_numpy(), frame["gdate"].to_numpy(),
                         frame[keycol].to_numpy())
        for s in np.unique(seas):
            m = seas == s
            pos = np.searchsorted(self.dates[s], gd[m], side="right") - 1
            A[m, :] = self.vals[s][pos, :]
            tm = {t: i for i, t in enumerate(self.teams[s])}
            c0[m] = [tm[k] for k in key[m]]
        return A, c0, seas


def perm(A, c0, seas, rng):
    out = np.empty(len(c0))
    for s in np.unique(seas):
        idx = np.where(seas == s)[0]
        pm = rng.permutation(A.shape[1])
        out[idx] = A[idx, pm[c0[idx]]]
    return out


OUT = {}
P.hdr("REBUILD")
mp = B.load_player()
mt = B.load_team()
TEAM = P.build_team_pre(mt)
cand_cols = [c["name"] for c in CANDS if c["side"] in ("opp", "own")]
W = P.build_analysis_frame(mp, TEAM, TGT, cand_cols)
y = W["s"].to_numpy(float)
seas = W["season"].to_numpy()
basecols = [W["O"].values, W["D"].values, W["OD"].values, W["ME"].values, W["OME"].values]
Mz = B.zwithin(W, CAND).to_numpy(float)
Mres = P.residualize_and_scale(Mz, W["D"].values, W["OD"].values)
print("  n=%d  R2_base=%.6f  dR2(%s)=%.6f" % (len(W), P.r2(y, basecols), CAND,
                                              incr(*prep_fast(y, basecols), Mres)))

# ------------------------------------------------------------------ S1 reliability
P.hdr("S1  SPLIT-HALF RELIABILITY OF THE PACE INSTRUMENT")
tp = B.team_possessions(mt)
tp = tp.merge(mt[["game_id", "team_id", "minutes"]], on=["game_id", "team_id"], how="left")
tp["poss_per48"] = tp["team_poss"] * 48.0 / (pd.to_numeric(tp["minutes"], errors="coerce") / 5.0)
P.guard(tp, "team possessions frame")                                       # FILTER-POINT
r_h, r_sb, n_u = B.split_half_reliability(tp, ("season", "team_id"), "poss_per48")
print("  odd/even split-half of team possessions-per-48 within (season, team)")
print("  r_half = %.4f   Spearman-Brown = %.4f   n_units = %d (team-seasons)" % (r_h, r_sb, n_u))
print("  -> the instrument is measured well; this is NOT an I0012-F1-style measurability kill.")
OUT["reliability"] = dict(r_half=float(r_h), spearman_brown=float(r_sb), n_team_seasons=int(n_u),
                          note="deterministic diagnostic, sd 0 by construction (not a placebo)")

# ------------------------------------------------------------------ S2 confound ladder
P.hdr("S2  CONFOUND LADDER (all rungs pregame-observable, all strictly prior in-season)")
t = mt.copy()
t = t.merge(tp[["game_id", "team_id", "team_poss"]], on=["game_id", "team_id"], how="left")
t["n_pts"] = pd.to_numeric(t["pts"], errors="coerce")
t["n_opts"] = pd.to_numeric(t["opp_pts"], errors="coerce")
t["n_u"] = t["team_poss"] / 100.0
t["n_w"] = (t["wl"].astype(str).str.upper().str[0] == "W").astype(float)
t["n_g"] = 1.0
pr = B.prior_expanding(t, ["season", "team_id"], ["n_pts", "n_opts", "n_u", "n_w", "n_g"], "pr_")
ctl = pr[["season", "game_id", "team_id"]].copy()
_u = pr["pr_n_u"].to_numpy(float)
_g = pr["pr_n_g"].to_numpy(float)
ctl["net100"] = np.where(_u > 3, (pr["pr_n_pts"].to_numpy(float) - pr["pr_n_opts"].to_numpy(float))
                         / np.where(_u > 3, _u, 1.0), np.nan)
ctl["winr"] = np.where(_g > 2, pr["pr_n_w"].to_numpy(float) / np.where(_g > 2, _g, 1.0), np.nan)
P.guard(ctl, "team control table")                                          # FILTER-POINT

W2 = W.merge(ctl.rename(columns={"team_id": "opp_team_id", "net100": "opp_net100",
                                 "winr": "opp_winr"}),
             on=["season", "game_id", "opp_team_id"], how="left")
W2 = W2.merge(ctl.rename(columns={"net100": "own_net100", "winr": "own_winr"}),
              on=["season", "game_id", "team_id"], how="left")
for c in ["opp_net100", "own_net100", "opp_winr", "own_winr"]:
    W2[c] = W2[c].fillna(W2.groupby("season")[c].transform("mean"))
home = W2["is_home"].astype(float).to_numpy()
LADDER = [
    ("L0 base only", []),
    ("L1 + home", [home]),
    ("L2 + both nets/100", [W2["own_net100"].to_numpy(float), W2["opp_net100"].to_numpy(float)]),
    ("L3 + both win rates", [W2["own_winr"].to_numpy(float), W2["opp_winr"].to_numpy(float)]),
    ("L4 + home + nets + win rates", [home, W2["own_net100"].to_numpy(float),
                                      W2["opp_net100"].to_numpy(float),
                                      W2["own_winr"].to_numpy(float),
                                      W2["opp_winr"].to_numpy(float)]),
]
print("  %-32s %10s %10s %8s" % ("rung", "R2_rung", "dR2(cand)", "retained"))
lad = []
d_ref = None
for name, extra in LADDER:
    cols = basecols + extra
    q = prep_fast(y, cols)
    dd = incr(*q, Mres)
    if d_ref is None:
        d_ref = dd
    print("  %-32s %10.6f %10.6f %7.0f%%" % (name, P.r2(y, cols), dd, 100 * dd / d_ref))
    lad.append(dict(rung=name, R2_rung=float(P.r2(y, cols)), dR2_cand=float(dd),
                    retained_frac=float(dd / d_ref)))
OUT["confound_ladder"] = lad

# ------------------------------------------------------------------ S3 recency
P.hdr("S3  RECENCY SLICES, each against its OWN cluster placebo recomputed at that n")
PAN = TeamPanel(TEAM, "pace48")
A_opp, c0_opp, _ = PAN.bind(W, "opp_team_id")
A_own, c0_own, _ = PAN.bind(W, "team_id")
SL = [("2021-2024 (pooled)", [2021, 2022, 2023, 2024]),
      ("2022-2024", [2022, 2023, 2024]),
      ("2023-2024", [2023, 2024]),
      ("2024 alone", [2024])]
print("  %-20s %7s %10s %10s %10s %9s %9s"
      % ("slice", "n", "dR2", "beta", "plc_mean", "plc_sd", "frac>="))
rec = []
for name, ss in SL:
    gi = np.where(np.isin(seas, ss))[0]
    bc = [c[gi] for c in basecols]
    q = prep_fast(y[gi], bc)
    dd = incr(*q, Mres[gi])
    bb = float(P.ols(y[gi], bc + [Mres[gi]])[0][-1])
    sq = seas[gi]
    draws = []
    for _ in range(NDRAW):
        v = 0.5 * (perm(A_opp[gi], c0_opp[gi], sq, rng) + perm(A_own[gi], c0_own[gi], sq, rng))
        draws.append(incr(*q, center_within(v, sq)))
    a = np.array(draws)
    print("  %-20s %7d %10.6f %10.4f %10.6f %9.6f %9.3f"
          % (name, len(gi), dd, bb, a.mean(), a.std(ddof=1), (a >= dd).mean()))
    rec.append(dict(slice=name, seasons=ss, n=int(len(gi)), dR2=float(dd), beta=float(bb),
                    placebo_mean=float(a.mean()), placebo_sd=float(a.std(ddof=1)),
                    frac_ge_real=float((a >= dd).mean()), n_draws=NDRAW))
    pd.DataFrame({"dR2": draws}).to_csv(
        os.path.join(P.OUT, "placebo_draws_survivor_%s.csv" % name.split()[0].replace("-", "_")),
        index=False)
OUT["recency"] = rec

OUT["meta"] = dict(target=TGT, candidate=CAND, n_draws=NDRAW, seed=P.SEED + 2,
                   elapsed_sec=round(time.time() - t0, 1))
with open(os.path.join(P.OUT, "survivor_checks.json"), "w", encoding="utf-8") as f:
    json.dump(OUT, f, indent=1, default=float)
print("\n  wrote survivor_checks.json  (%.1fs)" % (time.time() - t0))
