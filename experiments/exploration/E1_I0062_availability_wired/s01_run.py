"""s01_run.py -- implements PREREG.md bfbd792b5180f1245efc732bf87ecb67682bcd0bcc96bc7745534a182c57f195

Identical minutes point forecast and identical played-branch distribution in every arm. The
ONLY thing that varies is the availability term, so every difference is that term and nothing
else.

EXPLORATION PARTITION ONLY -- the availability frame carries 2022-2024.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "E1_I0061_minutes_distribution"))
import s01_run as M  # noqa: E402

GRID = M.GRID
QS = M.QS
THRESHOLDS = [15, 20, 25, 30, 35]
SEED, DRAWS, MIN_BIN = 20260820, 2000, M.MIN_BIN
SF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "..", "E0_I0019_availability_forecast", "scored_frame.parquet")


def played_branch_cdfs(p):
    """Rebuild E1_I0061's A3_EMPIRICAL_COND played-branch CDF, walk-forward. Unchanged."""
    seasons = sorted(p["season"].unique())
    chunks = []
    for s in seasons[1:]:
        tr = p[(p["season"] < s) & p["ok"] & (p["appeared"] == 1)]
        te = p[(p["season"] == s) & p["ok"]]
        if len(tr) < 300 or not len(te):
            continue
        res_tr = (tr["minutes"] - tr["m_hat"]).to_numpy(float)
        q_glob = np.quantile(res_tr, QS)
        lev_edges = np.quantile(tr["m_hat"], np.linspace(0, 1, 11))[1:-1]
        vol_edges = np.quantile(tr["prior_absres"], [1 / 3, 2 / 3])
        tr_lev = np.digitize(tr["m_hat"], lev_edges)
        tr_vol = np.digitize(tr["prior_absres"], vol_edges)
        cond = {}
        for a in range(11):
            for b in range(3):
                m = (tr_lev == a) & (tr_vol == b)
                if m.sum() >= MIN_BIN:
                    cond[(a, b)] = np.quantile(res_tr[m], QS)
        mu = te["m_hat"].to_numpy(float)
        lev = np.digitize(mu, lev_edges)
        vol = np.digitize(te["prior_absres"], vol_edges)
        qc = np.vstack([cond.get((lev[i], vol[i]), q_glob) for i in range(len(mu))])
        F = M.cdf_from_quantiles(mu, qc)
        chunks.append((te.index.to_numpy(), F))
    idx = np.concatenate([c[0] for c in chunks])
    F = np.vstack([c[1] for c in chunks])
    return idx, F


def brier(phat, y):
    return float(np.mean((phat - y) ** 2))


def auc(phat, y):
    o = np.argsort(phat)
    r = np.empty(len(phat), float)
    r[o] = np.arange(1, len(phat) + 1)
    n1 = float(y.sum())
    n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def reliability(phat, y, bins=10):
    e = np.linspace(0, 1, bins + 1)
    b = np.clip(np.digitize(phat, e[1:-1]), 0, bins - 1)
    dev, rows = [], []
    for k in range(bins):
        m = b == k
        if m.sum() < 20:
            continue
        dev.append(abs(phat[m].mean() - y[m].mean()) * m.sum())
        rows.append({"bin": k, "n": int(m.sum()), "pred": float(phat[m].mean()),
                     "obs": float(y[m].mean())})
    return float(np.sum(dev) / max(len(phat), 1)), rows


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    rng = np.random.default_rng(SEED)

    p = M.build()
    idx, Fpl = played_branch_cdfs(p)
    base = p.loc[idx].copy()
    base["_row"] = np.arange(len(base))

    sf = pd.read_parquet(SF)
    assert set(sf["season"].unique()) <= {2022, 2023, 2024}, "PARTITION VIOLATION"
    for d in (base, sf):
        d["game_id"] = d["game_id"].astype(str)
        d["player_id"] = d["player_id"].astype(str)
    j = base.merge(sf[["game_id", "player_id", "v15__pred_point",
                       "prediction_required__p_active", "v15__is_fallback"]],
                   on=["game_id", "player_id"], how="inner")
    j = j[j["ok"] & j["prediction_required__p_active"]].copy()
    F = Fpl[j["_row"].to_numpy()]
    y = j["minutes"].to_numpy(float)
    played = j["appeared"].to_numpy(float)
    grp = (j["player_id"] + "_" + j["season"].astype(str)).to_numpy()

    pg = np.clip(j["v15__pred_point"].to_numpy(float), 0.001, 0.999)
    pw = np.clip(j["prior_play"].to_numpy(float), 0.001, 0.999)

    arms = {
        "N_NONE": F,
        "W_CRUDE": np.clip((1 - pw)[:, None] + pw[:, None] * F, 0, 1),
        "G_GOOD": np.clip((1 - pg)[:, None] + pg[:, None] * F, 0, 1),
    }

    out = {"prereg_sha256": open("PREREG.sha256").read().split()[0],
           "n": int(len(j)), "n_players": int(j["player_id"].nunique()),
           "seasons": sorted(int(x) for x in j["season"].unique()),
           "appeared_rate": float(played.mean())}

    print("=" * 92)
    print("E1_I0062 -- wiring the GOOD availability model into the minutes forecast")
    print("=" * 92)
    print("rows %d | players %d | seasons %s | appeared rate %.4f"
          % (len(j), j["player_id"].nunique(), sorted(j["season"].unique()), played.mean()))
    print("Same point forecast, same played-branch distribution, in every arm.")
    print()

    # ---- P5 first: is the good instrument actually the better instrument here?
    print("P5 SANITY -- instrument quality against `appeared` itself")
    inst = {}
    for nm, ph in (("W_CRUDE", pw), ("G_GOOD", pg)):
        mad, rows = reliability(ph, played)
        inst[nm] = {"brier": brier(ph, played), "auc": auc(ph, played), "cal_mad": mad,
                    "mean_pred": float(ph.mean())}
        print("  %-8s Brier %.5f   AUC %.4f   calib MAD %.5f   mean pred %.4f (actual %.4f)"
              % (nm, inst[nm]["brier"], inst[nm]["auc"], mad, ph.mean(), played.mean()))
    out["instrument"] = inst
    p5 = inst["G_GOOD"]["brier"] < inst["W_CRUDE"]["brier"]
    print("  P5 %s" % ("PASS" if p5 else "FAIL -- STOP, the join or the artifact is wrong"))
    if not p5:
        json.dump(out, open("FINDINGS.json", "w"), indent=1)
        return

    def cluster_ci(v, g, draws=DRAWS):
        s = pd.Series(v).groupby(pd.Series(g))
        sums, cnts = s.sum().to_numpy(), s.count().to_numpy()
        k = len(sums)
        acc = np.empty(draws)
        for b in range(draws):
            i = rng.integers(0, k, k)
            acc[b] = sums[i].sum() / cnts[i].sum()
        acc.sort()
        return acc[int(0.025 * draws)], acc[int(0.975 * draws)]

    print()
    print("PRIMARY -- Brier on P(minutes > t), all dressed rows, DNPs as zero minutes")
    tb = {}
    for a, Fa in arms.items():
        row = []
        for t in THRESHOLDS:
            k = int(np.argmin(np.abs(GRID - t)))
            row.append(brier(1.0 - Fa[:, k], (y > t).astype(float)))
        tb[a] = row
        print("  %-8s " % a + "  ".join("t>%d %.5f" % (t, v) for t, v in zip(THRESHOLDS, row)))
    out["threshold_brier"] = tb

    k15 = int(np.argmin(np.abs(GRID - 15)))
    se = {a: (1.0 - arms[a][:, k15] - (y > 15).astype(float)) ** 2 for a in arms}
    print()
    print("  at t=15, with cluster intervals by player-season:")
    for a in arms:
        lo, hi = cluster_ci(se[a], grp)
        out.setdefault("t15", {})[a] = {"brier": float(se[a].mean()), "ci95": [lo, hi]}
        print("    %-8s %.5f  [%.5f, %.5f]" % (a, se[a].mean(), lo, hi))
    d_wn = cluster_ci(se["N_NONE"] - se["W_CRUDE"], grp)
    d_gw = cluster_ci(se["W_CRUDE"] - se["G_GOOD"], grp)
    gain_wn = float((se["N_NONE"] - se["W_CRUDE"]).mean())
    gain_gw = float((se["W_CRUDE"] - se["G_GOOD"]).mean())
    print("    gain W over N : %+.5f  [%+.5f, %+.5f]" % (gain_wn, d_wn[0], d_wn[1]))
    print("    gain G over W : %+.5f  [%+.5f, %+.5f]" % (gain_gw, d_gw[0], d_gw[1]))
    out["gains_t15"] = {"W_over_N": [gain_wn, d_wn[0], d_wn[1]],
                        "G_over_W": [gain_gw, d_gw[0], d_gw[1]]}

    print()
    print("CRPS over the dressed distribution")
    for a, Fa in arms.items():
        c = M.crps_from_cdf(Fa, y)
        lo, hi = cluster_ci(c, grp)
        out.setdefault("crps", {})[a] = {"crps": float(c.mean()), "ci95": [lo, hi]}
        print("  %-8s CRPS %.5f  [%.5f, %.5f]" % (a, c.mean(), lo, hi))

    print()
    print("PREDICTIONS")
    p1 = tb["G_GOOD"][0] < tb["W_CRUDE"][0]
    p2 = gain_wn > gain_gw
    p3 = out["crps"]["G_GOOD"]["crps"] < out["crps"]["W_CRUDE"]["crps"]
    rel = {a: [(tb["N_NONE"][i] - tb[a][i]) / tb["N_NONE"][i] * 100 for i in range(5)]
           for a in ("W_CRUDE", "G_GOOD")}
    p4 = all(all(rel[a][i] >= rel[a][i + 1] - 1e-9 for i in range(4)) for a in rel)
    out["relative_gain_vs_none_pct"] = rel
    for nm, ok, txt in (("P1", p1, "G beats W on the primary"),
                        ("P2", p2, "most of the value is in HAVING a branch, not its quality"),
                        ("P3", p3, "G beats W on CRPS"),
                        ("P4", p4, "gain shrinks monotonically with threshold"),
                        ("P5", p5, "G is the better instrument")):
        print("  %s %-4s %s" % (nm, "PASS" if ok else "FAIL", txt))
    out["predictions"] = {"P1": bool(p1), "P2": bool(p2), "P3": bool(p3),
                          "P4": bool(p4), "P5": bool(p5)}
    print()
    print("  relative gain over N_NONE, by threshold:")
    for a in rel:
        print("    %-8s " % a + "  ".join("t>%d %+.1f%%" % (t, v)
                                          for t, v in zip(THRESHOLDS, rel[a])))

    json.dump(out, open("FINDINGS.json", "w", encoding="utf-8", newline="\n"),
              indent=1, default=float)
    print("\nwrote FINDINGS.json")


if __name__ == "__main__":
    main()
