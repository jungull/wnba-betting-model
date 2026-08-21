"""diagnose.py -- E0-STYLE DIAGNOSTIC, NON-CLAIMING. Where does the market beat us?

The programme knows THAT the market wins: points MAE 5.32 against 4.90 on the benchmark frame
(D141), all ten conditional slices negative (D150), over/under accuracy 0.494 against 0.527
(D169). It has never decomposed WHY.

Points are minutes x rate. The market's edge could be in either, and the two imply completely
different work: if it is MINUTES, the market knows who plays and how long -- rotations, late
scratches, blowout risk -- and the fix is information, not modelling. If it is RATE, the market
prices scoring efficiency better than we do, and the fix is a better model.

THE ORACLE ARMS BELOW ARE NOT IMPLEMENTABLE AND ARE NOT MEANT TO BE. Handing the model the
realised minutes is cheating by construction. It is a measuring instrument: it partitions our
error into the part minutes would fix and the part it would not, and locates the deficit. No
number here is a forecast, a claim, or usable for anything but that partition.

NO PREREGISTRATION IS SOUGHT AND NO EVIDENCE-LADDER LABEL IS HELD. E0, non-claiming.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MP = HERE.parent
sys.path.insert(0, str(MP / "M11_CONSENSUS_MODEL"))
sys.path.insert(0, str(MP / "MODEL_VS_MARKET"))
sys.path.insert(0, str(MP / "M14_MODEL_MARKET_RESIDUAL"))
sys.path.insert(0, str(MP / "MARKET_IMPLIED_PROJECTIONS"))
sys.path.insert(0, str(MP.parent.parent))

import compute_model_vs_market as mvm            # noqa: E402
import implied_mean as mip                       # noqa: E402  -- point-scale inversion DELEGATED

ARM = MP.parent / "cbs_v15_player_oof_v5" / "attempt_002"
SEED, DRAWS = 20260821, 2000


def implied_mean(line, p_over):
    try:
        mu, _, _ = mip.implied_mean_from_probability(
            market_key="player_points", line=float(line), vig_free_over_prob=float(p_over))
        return mu
    except Exception:                                       # noqa: BLE001
        return np.nan


def build():
    ev = pd.read_parquet(MP / "M13_PLAYER_VALUE_TRANSLATION" / "translation_rows.parquet")
    outc, _, _ = mvm.load_outcomes()
    outc = outc[["game_id", "player_id", "minutes"]].rename(columns={"minutes": "min_actual"})
    ev["game_id"] = ev["game_id"].astype(str)
    outc["game_id"] = outc["game_id"].astype(str)
    d = ev.merge(outc, on=["game_id", "player_id"], how="left")

    mins = []
    for s in sorted(d["season"].unique()):
        p = ARM / f"predictions__e_minutes_given_active__{s}.parquet"
        mins.append(pd.read_parquet(p)[["row_uid", "pred_point"]]
                    .rename(columns={"pred_point": "min_hat"}))
    d = d.merge(pd.concat(mins, ignore_index=True), on="row_uid", how="left")

    d["mkt_mean"] = [implied_mean(l, p) for l, p in
                     zip(d["consensus_line"], d["p_over_market_devig"])]
    d = d[d["min_actual"].notna() & d["min_hat"].notna()
          & d["mkt_mean"].notna() & d["pts"].notna()].copy()
    d = d[d["min_actual"] > 0].copy()
    d["rate_hat"] = d["pred_point"] / d["min_hat"].clip(lower=0.5)
    d["rate_actual"] = d["pts"] / d["min_actual"]
    return d


def boot(err, dates, rng):
    g = pd.DataFrame({"e": np.abs(err), "d": dates}).groupby("d")["e"]
    sums, cnts = g.sum().to_numpy(), g.count().to_numpy()
    k = len(sums)
    acc = np.empty(DRAWS)
    for b in range(DRAWS):
        i = rng.integers(0, k, k)
        acc[b] = sums[i].sum() / cnts[i].sum()
    acc.sort()
    return float(np.mean(np.abs(err))), float(acc[int(.025 * DRAWS)]), float(acc[int(.975 * DRAWS)])


def main():
    rng = np.random.default_rng(SEED)
    d = build()
    y = d["pts"].to_numpy(float)
    dates = d["game_date"].to_numpy()
    print("=" * 94)
    print("M33 -- WHERE IS THE GAP? Oracle decomposition. NON-CLAIMING; the oracle arms cheat.")
    print("=" * 94)
    print("%d matched player-games that were actually played, seasons %s, %d game dates\n"
          % (len(d), sorted(d["season"].unique()), d["game_date"].nunique()))

    arms = {
        "MARKET (implied mean from the line)": d["mkt_mean"].to_numpy(float),
        "OUR MODEL as shipped": d["pred_point"].to_numpy(float),
        "ours + ORACLE MINUTES (our rate)": (d["rate_hat"] * d["min_actual"]).to_numpy(float),
        "ours + ORACLE RATE (our minutes)": (d["rate_actual"] * d["min_hat"]).to_numpy(float),
        "ORACLE BOTH (= perfect)": (d["rate_actual"] * d["min_actual"]).to_numpy(float),
    }
    res = {}
    print("%-38s %8s %20s" % ("forecast", "MAE", "95% CI"))
    for nm, v in arms.items():
        m, lo, hi = boot(v - y, dates, rng)
        res[nm] = m
        print("%-38s %8.4f   [%7.4f, %7.4f]" % (nm, m, lo, hi))

    mkt = res["MARKET (implied mean from the line)"]
    ours = res["OUR MODEL as shipped"]
    om = res["ours + ORACLE MINUTES (our rate)"]
    orr = res["ours + ORACLE RATE (our minutes)"]
    gap = ours - mkt
    print()
    print("THE GAP, AND WHAT CLOSES IT")
    print("  model minus market                       %+.4f points of MAE" % gap)
    print("  gap remaining if we knew MINUTES exactly %+.4f   (closes %+.0f%% of it)"
          % (om - mkt, (gap - (om - mkt)) / gap * 100 if gap else float("nan")))
    print("  gap remaining if we knew RATE exactly    %+.4f   (closes %+.0f%% of it)"
          % (orr - mkt, (gap - (orr - mkt)) / gap * 100 if gap else float("nan")))

    print()
    print("HOW WRONG IS EACH INPUT?")
    for nm, a, b in (("minutes", d["min_hat"], d["min_actual"]),
                     ("points-per-minute", d["rate_hat"], d["rate_actual"])):
        e = (a - b).to_numpy(float)
        print("  %-18s MAE %7.4f   bias %+7.4f   sd(actual) %7.4f   MAE/sd %5.3f"
              % (nm, np.mean(np.abs(e)), np.mean(e), np.std(b.to_numpy(float)),
                 np.mean(np.abs(e)) / np.std(b.to_numpy(float))))

    print()
    print("WHERE THE MARKET'S EDGE LIVES, by how much the player actually played")
    d["_bin"] = pd.cut(d["min_actual"], [0, 12, 20, 28, 48],
                       labels=["<12 min", "12-20", "20-28", "28+"])
    print("  %-10s %6s %9s %9s %9s" % ("played", "n", "market", "ours", "ours-market"))
    for b, sub in d.groupby("_bin", observed=True):
        yy = sub["pts"].to_numpy(float)
        mm = float(np.mean(np.abs(sub["mkt_mean"].to_numpy(float) - yy)))
        oo = float(np.mean(np.abs(sub["pred_point"].to_numpy(float) - yy)))
        print("  %-10s %6d %9.4f %9.4f %+9.4f" % (b, len(sub), mm, oo, oo - mm))


if __name__ == "__main__":
    main()
