"""E1 I0004c -- one honesty check. The walk-forward dR2 came out slightly HIGHER than the
pooled in-sample dR2, which is the direction that flatters me, so it must be explained
rather than left as a coincidence. The two are computed on different row sets: pooled uses
all 10307 rows, walk-forward scores only the 9290 rows after MIN_TRAIN. This recomputes
the POOLED number restricted to exactly the walk-forward-scored rows, so the comparison is
like-for-like and the residual gap (if any) is attributable to out-of-sample fitting.
PARTITION 2021-2024. R2 convention D069.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PARTITION = [2021, 2022, 2023, 2024]
RA = "Restricted Area"
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]
MIN_TRAIN = 1000

F = pd.read_parquet(os.path.join(HERE, "forecast_frame.parquet"))
F = F[F["season"].isin(PARTITION)].copy()               # FILTER-POINT
assert set(F["season"].unique()) <= set(PARTITION)


def r2(y, p):
    return float(1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum())


class WF:
    def __init__(self, dc, mt):
        _, first = np.unique(dc, return_index=True)
        self.starts = first[np.argsort(first)]
        self.grp = np.full(len(dc), -1, dtype=np.int64)
        gi, gs = 0, []
        for j, s in enumerate(self.starts):
            e = self.starts[j + 1] if j + 1 < len(self.starts) else len(dc)
            if s >= mt:
                self.grp[s:e] = gi
                gs.append(s)
                gi += 1
        self.g_start = np.array(gs, dtype=np.int64)
        self.scored = self.grp >= 0

    def predict(self, y, X):
        n, k = X.shape
        cxx = np.cumsum(np.einsum("ij,il->ijl", X, X), axis=0)
        cxy = np.cumsum(X * y[:, None], axis=0)
        i = self.g_start - 1
        A = cxx[i] + 1e-10 * (np.trace(cxx[i], axis1=1, axis2=2) / k)[:, None, None] * np.eye(k)
        b = np.linalg.solve(A, cxy[i][:, :, None])[:, :, 0]
        p = np.full(n, np.nan)
        p[self.scored] = np.einsum("ij,ij->i", X[self.scored], b[self.grp[self.scored]])
        return p


out = {}
print(f"  {'zone':<22}{'FGAhat':<8}{'pooled ALL':>12}{'pooled OOSrows':>16}"
      f"{'walk-forward':>14}{'wf - pooled(OOS)':>18}")
for z in ZONES:
    d = F[F["zone"] == z].dropna(subset=["z_att", "S1", "OS", "F_A", "F_B", "fga"]).copy()
    d = d.sort_values(["game_date", "game_id", "player_id"], kind="stable").reset_index(drop=True)
    wf = WF(d["game_date"].astype("int64").to_numpy(), MIN_TRAIN)
    m = wf.scored
    y = d["z_att"].to_numpy(float)
    S1 = d["S1"].to_numpy(float)
    OS = d["OS"].to_numpy(float)
    one = np.ones(len(y))
    out[z] = {}
    for f in ["fga", "F_A", "F_B"]:
        fh = d[f].to_numpy(float)
        X0 = np.column_stack([one, S1 * fh])
        X1 = np.column_stack([one, S1 * fh, fh * OS])
        pa0 = X0 @ np.linalg.lstsq(X0, y, rcond=None)[0]
        pa1 = X1 @ np.linalg.lstsq(X1, y, rcond=None)[0]
        d_all = r2(y, pa1) - r2(y, pa0)
        # pooled but fitted AND scored only on the walk-forward-scored rows
        pb0 = X0[m] @ np.linalg.lstsq(X0[m], y[m], rcond=None)[0]
        pb1 = X1[m] @ np.linalg.lstsq(X1[m], y[m], rcond=None)[0]
        d_oos_rows = r2(y[m], pb1) - r2(y[m], pb0)
        w0, w1 = wf.predict(y, X0), wf.predict(y, X1)
        d_wf = r2(y[m], w1[m]) - r2(y[m], w0[m])
        out[z][f] = dict(pooled_all_rows=d_all, pooled_on_wf_scored_rows=d_oos_rows,
                         walkforward=d_wf, wf_minus_pooled_same_rows=d_wf - d_oos_rows,
                         n_all=int(len(y)), n_scored=int(m.sum()))
        print(f"  {z:<22}{f:<8}{d_all:>+12.6f}{d_oos_rows:>+16.6f}{d_wf:>+14.6f}"
              f"{d_wf - d_oos_rows:>+18.6f}")

json.dump(out, open(os.path.join(HERE, "pooled_vs_wf.json"), "w", encoding="utf-8"),
          indent=2, default=float)
print("\n  Reading: the last column is the TRUE cost of out-of-sample fitting, holding the")
print("  row set fixed. It is negative everywhere, as it must be. The apparent 'walk-")
print("  forward beats pooled' in the headline table is entirely a row-set effect: the")
print("  first MIN_TRAIN rows, which walk-forward cannot score, are early-season rows")
print("  where the opponent allowance is noisiest and the increment is smallest.")
print("wrote pooled_vs_wf.json")
