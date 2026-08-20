"""s01_run.py -- implements PREREG.md d53637d0fbe9971e2051316003af05cbc9dff64c58f318a8ff9d21194e4e1b7c

Nothing here was chosen after seeing a number. Channels, base, statistic, nulls, permutation
count, detection floor and five predictions were all frozen first.

EXPLORATION PARTITION 2021-2024 ONLY.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

SEED = 20260820
DRAWS = 2000
CHANNELS = ["C1_opp_def", "C2_zone_match", "C3a_usage_x_def",
            "C3b_3rate_x_opp3", "C3c_fta_x_oppfta", "C4_opp_pace"]
BASE_PPM = ["prior_ppm", "prior_min", "ln_n_prior", "is_home"]
BASE_PTS = ["prior_pts", "prior_min", "ln_n_prior", "is_home"]


def ols_fit(X, y):
    X = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def ols_pred(X, beta):
    return np.column_stack([np.ones(len(X)), X]) @ beta


def walk_forward_r2(df, base_cols, extra_cols, response):
    """Fit on strictly earlier seasons, score the held season. Returns (r2, n, preds, idx)."""
    seasons = sorted(df["season"].unique())
    preds, ys, idxs = [], [], []
    for s in seasons[1:]:
        tr = df[df["season"] < s]
        te = df[df["season"] == s]
        if len(tr) < 200 or not len(te):
            continue
        cols = base_cols + list(extra_cols)
        beta = ols_fit(tr[cols].to_numpy(float), tr[response].to_numpy(float))
        preds.append(ols_pred(te[cols].to_numpy(float), beta))
        ys.append(te[response].to_numpy(float))
        idxs.append(te.index.to_numpy())
    if not preds:
        return np.nan, 0, None, None
    yhat = np.concatenate(preds)
    y = np.concatenate(ys)
    idx = np.concatenate(idxs)
    sse = float(np.sum((y - yhat) ** 2))
    sst = float(np.sum((y - y.mean()) ** 2))
    return 1.0 - sse / sst, len(y), yhat, idx


def delta_r2(df, base_cols, ch, response):
    r0, n, _, _ = walk_forward_r2(df, base_cols, [], response)
    r1, _, _, _ = walk_forward_r2(df, base_cols, [ch], response)
    return r1 - r0, n, r0, r1


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    rng = np.random.default_rng(SEED)
    d = pd.read_parquet("frame.parquet")
    assert not ({2025, 2026} & set(d["season"].unique())), "PARTITION VIOLATION"
    d = d[d["complete"]].copy().reset_index(drop=True)
    d["ln_n_prior"] = np.log1p(d["n_prior"])
    d["is_home"] = d["is_home"].astype(float)
    d["opp_season"] = d["opp_team_id"].astype(str) + "_" + d["season"].astype(str)

    out = {"prereg_sha256": open("PREREG.sha256").read().split()[0],
           "n_rows": int(len(d)), "n_players": int(d["player_id"].nunique()),
           "n_games": int(d["game_id"].nunique()),
           "n_opp_team_seasons": int(d["opp_season"].nunique()),
           "seasons": sorted(int(x) for x in d["season"].unique())}
    print("=" * 92)
    print("E1_I0060 -- the matchup family on RATE. Exploration 2021-2024. No outcome beyond it.")
    print("=" * 92)
    print("rows %d | players %d | games %d | opp-team-seasons %d"
          % (len(d), d["player_id"].nunique(), d["game_id"].nunique(), d["opp_season"].nunique()))

    r0_ppm, n_scored, _, _ = walk_forward_r2(d, BASE_PPM, [], "ppm")
    r0_pts, _, _, _ = walk_forward_r2(d, BASE_PTS, [], "pts")
    print("scored rows (2021 unscored, no prior season): %d" % n_scored)
    print("base R2  ppm %.6f   pts %.6f" % (r0_ppm, r0_pts))
    out["base_r2_ppm"], out["base_r2_pts"], out["n_scored"] = r0_ppm, r0_pts, n_scored

    # ---------------------------------------------------------------- detection floor
    print()
    print("DETECTION FLOOR (injection, per PREREG) -- what size can this pipeline even see?")
    floor_rows = []
    y = d["ppm"].to_numpy(float)
    sd_y = y.std()
    probe = d["C1_opp_def"].to_numpy(float)
    probe = (probe - probe.mean()) / probe.std()
    for target in (0.001, 0.003, 0.010):
        amp = sd_y * np.sqrt(target)
        dd = d.copy()
        dd["ppm"] = y + amp * probe
        got, _, _, _ = delta_r2(dd, BASE_PPM, "C1_opp_def", "ppm")
        floor_rows.append({"injected": target, "recovered": float(got)})
        print("   injected dR2 %.4f  ->  recovered %+.6f" % (target, got))
    out["injection"] = floor_rows

    # ---------------------------------------------------------------- real increments
    print()
    print("SIGNED dR2 PER CHANNEL, walk-forward, base = B_HONEST")
    res = {}
    for ch in CHANNELS:
        dr_ppm, _, _, _ = delta_r2(d, BASE_PPM, ch, "ppm")
        dr_pts, _, _, _ = delta_r2(d, BASE_PTS, ch, "pts")
        ratio = (dr_ppm / dr_pts) if (dr_pts not in (0.0,) and np.isfinite(dr_pts)
                                      and abs(dr_pts) > 1e-12) else np.nan
        res[ch] = {"dr2_ppm": float(dr_ppm), "dr2_pts": float(dr_pts), "ratio": float(ratio)}
        print("   %-18s ppm %+.6f    pts %+.6f    ratio %s"
              % (ch, dr_ppm, dr_pts, ("%.2f" % ratio) if np.isfinite(ratio) else "n/a"))

    # ---------------------------------------------------------------- permutation null
    print()
    print("PERMUTATION NULL -- opponent-team-season labels reshuffled within season, %d draws"
          % DRAWS)
    opp_cols = ["C1_opp_def", "C2_zone_match", "C3a_usage_x_def",
                "C3b_3rate_x_opp3", "C3c_fta_x_oppfta", "C4_opp_pace"]
    # map each opponent-season to its rows; permuting the LABEL moves the whole feature vector
    key = d[["opp_season", "season"]].copy()
    by_season = {s: np.array(sorted(key.loc[key["season"] == s, "opp_season"].unique()))
                 for s in key["season"].unique()}
    lut = {}
    for os_ in d["opp_season"].unique():
        rows = d.index[d["opp_season"] == os_]
        lut[os_] = d.loc[rows, opp_cols].mean().to_numpy(float)

    null = {ch: np.empty(DRAWS) for ch in CHANNELS}
    maxt = np.empty(DRAWS)
    for b in range(DRAWS):
        dd = d.copy()
        newvals = np.empty((len(d), len(opp_cols)))
        for s, arr in by_season.items():
            perm = rng.permutation(arr)
            mapping = dict(zip(arr, perm))
            m = (d["season"] == s).to_numpy()
            src = d.loc[m, "opp_season"].map(mapping)
            newvals[m] = np.vstack([lut[x] for x in src])
        for j, c in enumerate(opp_cols):
            dd[c] = newvals[:, j]
        ts = []
        for ch in CHANNELS:
            v, _, _, _ = delta_r2(dd, BASE_PPM, ch, "ppm")
            null[ch][b] = v
            ts.append(v)
        maxt[b] = max(ts)
        if (b + 1) % 250 == 0:
            print("   ... %d/%d" % (b + 1, DRAWS))

    floor = None
    f95 = np.percentile(null["C1_opp_def"], 95)
    for row in floor_rows:
        if row["recovered"] > f95:
            floor = row["injected"]
            break
    out["detection_floor"] = floor
    print("   permutation 95th pct for a single channel: %+.6f  -> detection floor %s"
          % (f95, floor))

    print()
    print("VERDICTS  (p_perm = one-sided; p_fwe = max-t family-wise over the six)")
    ps = {}
    for ch in CHANNELS:
        obs = res[ch]["dr2_ppm"]
        p = float((np.sum(null[ch] >= obs) + 1) / (DRAWS + 1))
        pf = float((np.sum(maxt >= obs) + 1) / (DRAWS + 1))
        ps[ch] = (p, pf)
        res[ch].update({"p_perm": p, "p_fwe": pf,
                        "null_p95": float(np.percentile(null[ch], 95)),
                        "below_floor": bool(floor is not None and abs(obs) < floor)})
        flag = ("CLEARS FWE" if pf <= 0.05 else
                "unresolved (below floor)" if res[ch]["below_floor"] else "not cleared")
        print("   %-18s dR2 %+.6f   p_perm %.4f   p_fwe %.4f   %s"
              % (ch, obs, p, pf, flag))

    # BH at 10%
    order = sorted(CHANNELS, key=lambda c: ps[c][0])
    m = len(CHANNELS)
    bh = []
    for k, ch in enumerate(order, start=1):
        thr = (k / m) * 0.10
        bh.append((ch, ps[ch][0], thr, ps[ch][0] <= thr))
    kmax = max([k for k, (_, p, thr, ok) in enumerate(bh, 1) if ok], default=0)
    survivors = [bh[i][0] for i in range(kmax)]
    out["bh_survivors"] = survivors
    print("   BH(10%%) survivors: %s" % (survivors or "none"))

    # ---------------------------------------------------------------- re-multiplication
    print()
    print("THE HONEST RE-MULTIPLICATION -- does a rate gain become a points gain?")
    best = max(CHANNELS, key=lambda c: res[c]["dr2_ppm"])
    _, _, _, _ = delta_r2(d, BASE_PPM, best, "ppm")
    r_no, n1, yhat_no, idx_no = walk_forward_r2(d, BASE_PPM, [], "ppm")
    r_ch, n2, yhat_ch, idx_ch = walk_forward_r2(d, BASE_PPM, [best], "ppm")
    mins = d.loc[idx_no, "prior_min"].to_numpy(float)
    ytrue = d.loc[idx_no, "pts"].to_numpy(float)
    sst = float(np.sum((ytrue - ytrue.mean()) ** 2))

    def r2_of(pred):
        return 1.0 - float(np.sum((ytrue - pred) ** 2)) / sst

    two_no = r2_of(yhat_no * mins)
    two_ch = r2_of(yhat_ch * mins)
    dr_direct, _, _, _ = delta_r2(d, BASE_PTS, best, "pts")
    out["remultiplication"] = {
        "best_channel": best, "two_stage_r2_without": two_no, "two_stage_r2_with": two_ch,
        "two_stage_gain": two_ch - two_no, "direct_points_gain": float(dr_direct)}
    print("   best rate channel: %s" % best)
    print("   two-stage (rate x prior minutes) points R2 without channel: %.6f" % two_no)
    print("   two-stage points R2 WITH channel                          : %.6f" % two_ch)
    print("   => gain on POINTS via the rate route : %+.6f" % (two_ch - two_no))
    print("   => gain on POINTS measured directly  : %+.6f" % dr_direct)

    out["channels"] = res
    with open("FINDINGS.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    print()
    print("wrote FINDINGS.json")


if __name__ == "__main__":
    main()
