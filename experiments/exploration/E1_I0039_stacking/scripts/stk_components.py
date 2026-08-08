"""E1_I0039 -- the three components, built ONCE and imported by s05 (lattice) and s06 (controls),
so the two steps cannot drift apart.  Building nothing here evaluates a cell.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import stk_base as B  # noqa: E402
from stk_base import wf_arm, MIN_TRAIN_STRUCT  # noqa: E402

RESP = {"minutes": "min_hat", "pts": "pts_hat"}     # explicit dict, 2 entries
assert len(RESP) == 2
ARMS = ["base", "A", "B", "C", "AB", "AC", "BC", "ABC"]
MIN_GROUP = 20


def load():
    f = pd.read_parquet(os.path.join(B.OUT, "_fit.parquet"))
    B.assert_partition(f, "fit")
    return f


def build(f, verbose=True):
    season = pd.to_numeric(f["season"]).to_numpy()
    SCORED = np.isin(season, np.array(B.SCORED_W2))
    TA = f["TA"].to_numpy(bool)
    TB = f["TB"].to_numpy(bool)
    TC = f["TC"].to_numpy(bool)

    # ---------------- A: cold-start structural placeholder, walk-forward, prior seasons only.
    # lambda(n) = n/(n+2); own running mean = trailing-5 of PRIOR appearances (identical to the
    # running mean while n <= 5, which covers every A row -- max n_prior on A is 2).
    # LISTED POSITION IS DELIBERATELY ABSENT: D092 ruling 2 dropped it (p 0.783, null 0.1996).
    FIT_TIER = TB                       # the data-poor tier, D092's fit population
    A_hat, A_diag = {}, []
    for t in RESP:
        y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
        n = pd.to_numeric(f["n_prior_games"], errors="coerce").to_numpy(float)
        own = pd.to_numeric(f["base5_" + t], errors="coerce").to_numpy(float)
        lam = np.where(np.isfinite(own), n / (n + 2.0), 0.0)
        own = np.where(np.isfinite(own), own, 0.0)
        struct = np.full(len(f), np.nan)
        for s in (2022,) + tuple(B.SCORED_W2):
            tr = FIT_TIER & (season < s) & (season >= MIN_TRAIN_STRUCT) & np.isfinite(y)
            te = (season == s)
            if tr.sum() < 50:
                continue
            league = float(y[tr].mean())
            dev = {}
            for col in ("depth_bucket", "draft_bucket"):
                g = f[col].to_numpy()
                d = {}
                for lev in pd.unique(g[tr]):
                    if pd.isna(lev):
                        continue
                    m = tr & (g == lev)
                    d[lev] = float(y[m].mean() - league) if m.sum() >= MIN_GROUP else 0.0
                dev[col] = d
            sv = np.full(int(te.sum()), league)
            for col in ("depth_bucket", "draft_bucket"):
                g = f[col].to_numpy()[te]
                sv = sv + np.array([dev[col].get(v, 0.0) if not pd.isna(v) else 0.0 for v in g])
            struct[te] = sv
            A_diag.append(dict(response=t, scored_season=s, n_train=int(tr.sum()),
                               league=league, n_depth_levels=len(dev["depth_bucket"]),
                               n_draft_levels=len(dev["draft_bucket"])))
        A_hat[t] = lam * own + (1.0 - lam) * struct
        if verbose:
            print("  A %-8s finite on %d/%d A rows in U"
                  % (t, int((np.isfinite(A_hat[t]) & TA & SCORED).sum()),
                     int((TA & SCORED).sum())))

    # ---------------- B: the tuned simple estimator, IMPORTED from D094 via E1_I0032.
    B_hat = {t: pd.to_numeric(f["e_full_" + t], errors="coerce").to_numpy(float) for t in RESP}
    if verbose:
        for t in RESP:
            print("  B %-8s e_full finite on %d/%d B rows in U"
                  % (t, int((np.isfinite(B_hat[t]) & TB & SCORED).sum()),
                     int((TB & SCORED).sum())))

    # ---------------- C: even redistribution term, IDENTICALLY ZERO outside its treated rows.
    Cu, Cuz = {}, {}
    for t in RESP:
        u = np.nan_to_num(pd.to_numeric(f["u_" + t], errors="coerce").to_numpy(float))
        z = np.nan_to_num(pd.to_numeric(f["z_" + t], errors="coerce").to_numpy(float))
        Cu[t] = np.where(TC, u, 0.0)
        Cuz[t] = np.where(TC, u * z, 0.0)
        if verbose:
            print("  C %-8s u nonzero on %d rows of U (TC=%d)"
                  % (t, int(((Cu[t] != 0) & SCORED).sum()), int((TC & SCORED).sum())))
    return A_hat, B_hat, Cu, Cuz, pd.DataFrame(A_diag)


def make_arms(f, A_hat, B_hat, Cu, Cuz):
    """COMPOSITION RULE (preregistered): A is a STRICT SUBSET of B, so in AB/ABC
    A takes precedence on fallback_level == 2 and B covers fallback_level == 3.
    A declared sensitivity, `*_Bwins`, gives B the whole of its own row set."""
    season = pd.to_numeric(f["season"]).to_numpy()
    TA = f["TA"].to_numpy(bool)
    TB = f["TB"].to_numpy(bool)

    def pre_arm(t, comps, b_wins=False):
        p = pd.to_numeric(f[RESP[t]], errors="coerce").to_numpy(float).copy()
        if "A" in comps and "B" in comps and not b_wins:
            mA = TA & np.isfinite(A_hat[t])
            mB = TB & (~TA) & np.isfinite(B_hat[t])
            p[mA] = A_hat[t][mA]
            p[mB] = B_hat[t][mB]
        elif "A" in comps and "B" in comps and b_wins:
            mB = TB & np.isfinite(B_hat[t])
            p[mB] = B_hat[t][mB]
        elif "A" in comps:
            mA = TA & np.isfinite(A_hat[t])
            p[mA] = A_hat[t][mA]
        elif "B" in comps:
            mB = TB & np.isfinite(B_hat[t])
            p[mB] = B_hat[t][mB]
        return p

    def arm_forecast(t, comps, b_wins=False):
        y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
        p = pre_arm(t, comps, b_wins)
        X = [Cu[t], Cuz[t]] if "C" in comps else []
        return wf_arm(p, X, y, season)

    FC = {}
    for t in RESP:
        for a in ARMS:
            FC[(t, a)] = arm_forecast(t, set() if a == "base" else set(a))
        FC[(t, "AB_Bwins")] = arm_forecast(t, {"A", "B"}, b_wins=True)
        FC[(t, "ABC_Bwins")] = arm_forecast(t, {"A", "B", "C"}, b_wins=True)
    return FC, pre_arm, arm_forecast
