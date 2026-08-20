"""s01_run.py -- implements PREREG.md e44c46a5f2b83da6f3834ddcb7b7816b8abe0419bad74c4d74c2478c0f99244a

Every arm shares the SAME point forecast. Only the distribution around it varies, so any
difference in CRPS is attributable to the distribution and to nothing else.

EXPLORATION PARTITION 2021-2024 ONLY.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np
import pandas as pd

FR = (r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
      r"\experiments\exploration\E1_I0030_home_advantage_accounting\_player_frame.parquet")
GRID = np.arange(0.0, 48.0001, 0.25)
QS = np.array([0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95])
THRESHOLDS = [15, 20, 25, 30, 35]
SEED, DRAWS = 20260820, 2000
MIN_BIN = 50


def ncdf(x, mu, sd):
    return 0.5 * (1.0 + np.vectorize(math.erf)((x - mu) / (sd * math.sqrt(2.0))))


def build():
    p = pd.read_parquet(FR)
    assert set(p["season"].unique()) <= {2021, 2022, 2023, 2024}, "PARTITION VIOLATION"
    p = p.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)
    g = p.groupby(["player_id", "season"], sort=False)
    p["n_prior"] = g.cumcount()
    # point forecast: EWMA half-life 2 of PLAYED minutes, strictly prior
    mp = p["minutes"].where(p["appeared"] == 1)
    p["_m"] = mp
    p["m_hat"] = p.groupby(["player_id", "season"], sort=False)["_m"].transform(
        lambda s: s.ewm(halflife=2.0, adjust=True, ignore_na=True).mean().shift(1))
    # prior residual dispersion and prior play rate, strictly prior
    p["_absres"] = (p["_m"] - p["m_hat"]).abs()
    p["prior_absres"] = p.groupby(["player_id", "season"], sort=False)["_absres"].transform(
        lambda s: s.ewm(halflife=5.0, adjust=True, ignore_na=True).mean().shift(1))
    p["prior_play"] = p.groupby(["player_id", "season"], sort=False)["appeared"].transform(
        lambda s: s.ewm(halflife=8.0, adjust=True).mean().shift(1))
    p["ok"] = p["m_hat"].notna() & p["prior_absres"].notna() & p["prior_play"].notna() \
        & (p["n_prior"] >= 5)
    return p


def crps_from_cdf(F, y):
    """F: (n, len(GRID)) CDF values. Numerical CRPS on the frozen grid."""
    ind = (GRID[None, :] >= y[:, None]).astype(float)
    return np.trapezoid((F - ind) ** 2, GRID, axis=1)


def cdf_gauss(mu, sd):
    sd = np.clip(sd, 0.5, None)
    F = np.empty((len(mu), len(GRID)))
    for i in range(len(mu)):
        F[i] = ncdf(GRID, mu[i], sd[i])
    lo, hi = F[:, :1].copy(), F[:, -1:].copy()
    return np.clip((F - lo) / np.clip(hi - lo, 1e-9, None), 0.0, 1.0)   # renormalise onto [0,48]


def cdf_from_quantiles(mu, qgrid):
    """qgrid: (n, len(QS)) residual quantiles added to mu -> step CDF on GRID."""
    pts = np.clip(mu[:, None] + qgrid, 0.0, 48.0)
    F = np.empty((len(mu), len(GRID)))
    for i in range(len(mu)):
        F[i] = np.interp(GRID, pts[i], QS, left=0.0, right=1.0)
    return np.clip(F, 0.0, 1.0)


def pit(F, y):
    idx = np.clip(np.searchsorted(GRID, y), 0, len(GRID) - 1)
    return F[np.arange(len(y)), idx]


def interval(F, lo=0.1, hi=0.9):
    a = GRID[np.argmax(F >= lo, axis=1)]
    b = GRID[np.argmax(F >= hi, axis=1)]
    return a, b


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    rng = np.random.default_rng(SEED)
    p = build()
    seasons = sorted(p["season"].unique())
    out = {"prereg_sha256": open("PREREG.sha256").read().split()[0], "arms": {}}

    rows_played, rows_dressed = [], []
    fallback_n = fallback_d = 0
    for s in seasons[1:]:
        tr = p[(p["season"] < s) & p["ok"] & (p["appeared"] == 1)]
        te_pl = p[(p["season"] == s) & p["ok"] & (p["appeared"] == 1)]
        te_dr = p[(p["season"] == s) & p["ok"]]
        if len(tr) < 300 or not len(te_pl):
            continue
        res_tr = (tr["minutes"] - tr["m_hat"]).to_numpy(float)

        # --- A0: one sd for the whole season, fitted on earlier seasons
        sd_const = float(res_tr.std())
        # --- A1: per-row sd from the player's own prior |residual| (scaled to an sd)
        k = sd_const / max(float(np.abs(res_tr).mean()), 1e-9)
        # --- A2: pooled empirical residual quantiles
        q_glob = np.quantile(res_tr, QS)
        # --- A3: conditional on predicted-level decile x prior-volatility tercile
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

        for te, bucket, dressed in ((te_pl, rows_played, False), (te_dr, rows_dressed, True)):
            mu = te["m_hat"].to_numpy(float)
            y = te["minutes"].to_numpy(float)
            n = len(mu)
            sd1 = np.clip(te["prior_absres"].to_numpy(float) * k, 0.5, None)
            lev = np.digitize(mu, lev_edges)
            vol = np.digitize(te["prior_absres"], vol_edges)
            qc = np.empty((n, len(QS)))
            for i in range(n):
                key = (lev[i], vol[i])
                if key in cond:
                    qc[i] = cond[key]
                else:
                    qc[i] = q_glob
                    if dressed:
                        globals()["_fb_d"] = globals().get("_fb_d", 0) + 1
                    else:
                        globals()["_fb_p"] = globals().get("_fb_p", 0) + 1
            arms = {
                "A0_SHIPPED_STYLE": cdf_gauss(mu, np.full(n, sd_const)),
                "A1_PERROW_GAUSS": cdf_gauss(mu, sd1),
                "A2_EMPIRICAL_GLOBAL": cdf_from_quantiles(mu, np.tile(q_glob, (n, 1))),
                "A3_EMPIRICAL_COND": cdf_from_quantiles(mu, qc),
            }
            if dressed:
                pplay = np.clip(te["prior_play"].to_numpy(float), 0.01, 0.999)
                F = arms["A3_EMPIRICAL_COND"].copy()
                # mixture: point mass (1-pplay) at zero, then the played branch
                arms["A4_MIXTURE"] = np.clip((1 - pplay)[:, None] + pplay[:, None] * F, 0, 1)
            rec = {"season": s, "y": y, "pid": (te["player_id"].astype(str) + "_"
                                                + te["season"].astype(str)).to_numpy()}
            for a, F in arms.items():
                rec[a] = F
            bucket.append(rec)

    def collect(bucket, arm_names):
        y = np.concatenate([r["y"] for r in bucket])
        pid = np.concatenate([r["pid"] for r in bucket])
        Fs = {a: np.vstack([r[a] for r in bucket]) for a in arm_names}
        return y, pid, Fs

    print("=" * 92)
    print("E1_I0061 -- minutes as a DISTRIBUTION. Exploration 2021-2024. Same point forecast in")
    print("every arm, so every difference below is the shape of the distribution and nothing else.")
    print("=" * 92)

    y, pid, Fs = collect(rows_played, ["A0_SHIPPED_STYLE", "A1_PERROW_GAUSS",
                                       "A2_EMPIRICAL_GLOBAL", "A3_EMPIRICAL_COND"])
    print("U_PLAYED scored rows: %d over %d player-seasons" % (len(y), len(set(pid))))
    out["n_played"] = int(len(y))
    out["fallback_rate_played"] = float(globals().get("_fb_p", 0) / max(len(y), 1))
    print("A3 conditional-bin fallback rate: %.4f" % out["fallback_rate_played"])
    print()

    def cluster_ci(vals, groups, draws=DRAWS):
        gs = pd.Series(vals).groupby(pd.Series(groups))
        sums, cnts = gs.sum().to_numpy(), gs.count().to_numpy()
        k = len(sums)
        acc = np.empty(draws)
        for b in range(draws):
            i = rng.integers(0, k, k)
            acc[b] = sums[i].sum() / cnts[i].sum()
        acc.sort()
        return acc[int(0.025 * draws)], acc[int(0.975 * draws)]

    print("PRIMARY -- CRPS (lower is better), and the metrics around it")
    base = None
    for a in ["A0_SHIPPED_STYLE", "A1_PERROW_GAUSS", "A2_EMPIRICAL_GLOBAL", "A3_EMPIRICAL_COND"]:
        F = Fs[a]
        c = crps_from_cdf(F, y)
        m = float(c.mean())
        lo, hi = cluster_ci(c, pid)
        base = m if base is None else base
        u = pit(F, y)
        hist = np.histogram(u, bins=10, range=(0, 1))[0] / len(u)
        chi = float(np.sum((hist - 0.1) ** 2) / 0.1 * len(u))
        a10, b90 = interval(F)
        cov = float(((y >= a10) & (y <= b90)).mean())
        w = float((b90 - a10).mean())
        pin = float(np.mean([np.mean(np.maximum(q * (y - GRID[np.argmax(F >= q, axis=1)]),
                                                (q - 1) * (y - GRID[np.argmax(F >= q, axis=1)])))
                             for q in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]]))
        out["arms"][a] = {"crps": m, "crps_ci95": [lo, hi], "vs_A0_pct": (base - m) / base * 100,
                          "pit_chi2": chi, "pit_outer_mass": float(hist[0] + hist[-1]),
                          "cov80": cov, "width80": w, "pinball": pin}
        print("  %-22s CRPS %.5f [%.5f,%.5f]  %+6.2f%%   80%%cov %.4f  width %5.2f  pinball %.4f"
              % (a, m, lo, hi, (base - m) / base * 100, cov, w, pin))

    print()
    print("PIT CALIBRATION -- outer-bin mass should be 0.20 if the shape is right")
    for a in out["arms"]:
        print("  %-22s outer mass %.4f   chi2 %.1f" %
              (a, out["arms"][a]["pit_outer_mass"], out["arms"][a]["pit_chi2"]))

    print()
    print("THE THESIS (P2) -- is SHAPE worth more than SCALE?")
    g_scale = out["arms"]["A1_PERROW_GAUSS"]["vs_A0_pct"]
    g_shape = out["arms"]["A3_EMPIRICAL_COND"]["vs_A0_pct"]
    print("  scale only (A1 over A0) : %+.3f%%" % g_scale)
    print("  shape      (A3 over A0) : %+.3f%%" % g_shape)
    print("  ratio shape/scale       : %s" %
          (("%.2f" % (g_shape / g_scale)) if abs(g_scale) > 1e-9 else "n/a"))
    out["thesis"] = {"scale_gain_pct": g_scale, "shape_gain_pct": g_shape}

    print()
    print("THRESHOLD BRIER -- P(minutes > t), the prop-shaped question")
    yd, pidd, Fd = collect(rows_dressed, ["A0_SHIPPED_STYLE", "A3_EMPIRICAL_COND", "A4_MIXTURE"])
    out["n_dressed"] = int(len(yd))
    print("  U_DRESSED scored rows: %d (DNP rows included, minutes 0)" % len(yd))
    tb = {}
    for a in ["A0_SHIPPED_STYLE", "A3_EMPIRICAL_COND", "A4_MIXTURE"]:
        row = []
        for t in THRESHOLDS:
            j = int(np.argmin(np.abs(GRID - t)))
            phat = 1.0 - Fd[a][:, j]
            row.append(float(np.mean((phat - (yd > t).astype(float)) ** 2)))
        tb[a] = row
        print("  %-22s " % a + "  ".join("t>%d %.4f" % (t, v) for t, v in zip(THRESHOLDS, row)))
    out["threshold_brier"] = tb
    print("  A4 vs A3 relative improvement: " +
          "  ".join("t>%d %+.1f%%" % (t, (tb["A3_EMPIRICAL_COND"][i] - tb["A4_MIXTURE"][i])
                                      / tb["A3_EMPIRICAL_COND"][i] * 100)
                    for i, t in enumerate(THRESHOLDS)))

    with open("FINDINGS.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, default=float)
    print("\nwrote FINDINGS.json")


if __name__ == "__main__":
    main()
