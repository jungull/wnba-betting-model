"""S05 -- STEP 5.  DOES HOME/AWAY AFFECT PLAYERS DIFFERENTLY?  With the CORRECT null.

D093's warning is the design constraint here: it found an apparent per-player heterogeneity that was
ENTIRELY an artefact of a within-player SHUFFLE destroying serial structure.  It vanished under a
CYCLIC SHIFT, and the shuffle-versus-cyclic gap tracked regressor autocorrelation at +0.83.  The kit
now refuses the unsafe path.  This stage therefore uses `screenkit.per_entity_control`, whose
default scheme IS the cyclic shift, and it runs the VACUOUS relabel arm beside it (K7) and reports
it as vacuous rather than as a clean bill of health.

STATISTIC: the spread (sd, and IQR) of the per-player home-minus-away mean difference, over players
with at least 20 home and 20 away appearances in 2021-2024 regular season.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import ha_base as hb
import s00_prereg
import screenkit as sk

MIN_PER_VENUE = 20
N_DRAWS = 2000


def main():
    hb.hdr("S05 PER-PLAYER HETEROGENEITY")
    prereg = s00_prereg.assert_prereg_unchanged()
    FIND = {"prereg_sha256": prereg["prereg_sha256"], "min_per_venue": MIN_PER_VENUE}

    p = pd.read_parquet(os.path.join(hb.OUT, "_player_frame.parquet"))
    sk.assert_partition(p[["season", "game_date"]], verbose=False)
    f = p[(p["season_type"] == "Regular Season") & (p["appeared"] == 1)].copy()
    f["ppm"] = f["pts"] / f["minutes"]
    f["fta_pm"] = f["fta"] / f["minutes"]
    # rows MUST be sorted by entity then DATE for the cyclic shift to preserve serial structure
    f = f.sort_values(["player_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)

    cnt = f.groupby(["player_id", "is_home"]).size().unstack(fill_value=0)
    keep = cnt.index[(cnt.get(1, 0) >= MIN_PER_VENUE) & (cnt.get(0, 0) >= MIN_PER_VENUE)]
    g = f[f["player_id"].isin(keep)].copy().reset_index(drop=True)
    print("  players with >=%d home AND >=%d away appearances: %d of %d  (%d rows)"
          % (MIN_PER_VENUE, MIN_PER_VENUE, len(keep), f["player_id"].nunique(), len(g)))
    FIND["n_players_kept"] = int(len(keep))
    FIND["n_rows"] = int(len(g))

    # the K6 diagnostic: is is_home serially structured inside a player's career?
    acf = sk.within_group_acf1(g, "is_home", "player_id", order_col="game_date")
    print("  within-player acf1(is_home) = %s over %s pairs, %s groups"
          % (round(acf["acf1"], 5) if acf["acf1"] is not None else None,
             acf["n_pairs"], acf["n_groups"]))
    FIND["within_player_acf1_is_home"] = {k: v for k, v in acf.items()}
    print("  (home stands and road trips come in RUNS, so this is not zero -- which is exactly why")
    print("   the cyclic shift, not the shuffle, is the admissible null here.)")

    res = {}
    for tgt in ["pts", "ppm", "fta", "fta_pm"]:
        hb.hdr("TARGET: %s" % tgt)

        def make_stat(col):
            def stat(d):
                sub = d[["player_id", "is_home", col]].dropna()
                m = (sub.groupby(["player_id", "is_home"])[col].mean()
                        .unstack())
                if 0 not in m.columns or 1 not in m.columns:
                    return float("nan")
                diff = (m[1] - m[0]).dropna()
                return float(diff.std(ddof=1))
            return stat

        stat = make_stat(tgt)
        real = stat(g)
        m = (g.groupby(["player_id", "is_home"])[tgt].mean().unstack())
        diff = (m[1] - m[0]).dropna()
        print("  per-player home-minus-away %s: mean=%+.5f  sd=%.5f  IQR=%.5f  n=%d"
              % (tgt, diff.mean(), diff.std(ddof=1),
                 diff.quantile(.75) - diff.quantile(.25), len(diff)))

        ctl = sk.per_entity_control(stat, g, "player_id", feature_col="is_home",
                                    n_draws=N_DRAWS, seed=hb.SEED,
                                    scheme=sk.SCHEME_WITHIN_CYCLIC, order_col="game_date",
                                    alternative="greater", verbose=True)
        gen = ctl["genuine"]
        rel = ctl["relabel"]
        print("  ARM 1 relabel (VACUOUS by construction): is_noop=%s sd=%.3g"
              % (rel.get("is_noop"), rel.get("sd")))
        print("  ARM 2 cyclic  (can fail): real sd=%.5f  null mean=%.5f  null sd=%.5f  p=%.4f"
              % (real, gen["mean"], gen["sd"], gen["p"]))
        print("  controls_are_informative = %s" % ctl.get("controls_are_informative"))

        # AND the unsafe arm, run ONLY to publish the gap D093 warned about
        try:
            unsafe = sk.permutation_null(stat, g, "player_id", N_DRAWS, hb.SEED,
                                         feature_col="is_home", scheme=sk.SCHEME_WITHIN,
                                         order_col="game_date", alternative="greater",
                                         accept_serial_structure_destroyed=True)
            print("  UNSAFE within-SHUFFLE arm (D093's trap, reported for the gap only): "
                  "null sd=%.5f  p=%.4f" % (unsafe["sd"], unsafe["p"]))
            gap = {"shuffle_null_sd": unsafe["sd"], "shuffle_p": unsafe["p"],
                   "cyclic_null_sd": gen["sd"], "cyclic_p": gen["p"],
                   "sd_ratio_shuffle_over_cyclic": unsafe["sd"] / gen["sd"] if gen["sd"] else None}
        except Exception as e:                                     # noqa: BLE001
            gap = {"error": str(e)}
            print("  UNSAFE arm refused by the kit: %s" % e)

        res[tgt] = {
            "real_sd_of_per_player_diff": real,
            "mean_per_player_diff": float(diff.mean()),
            "iqr_per_player_diff": float(diff.quantile(.75) - diff.quantile(.25)),
            "n_players": int(len(diff)),
            "cyclic_null": {k: v for k, v in gen.items() if k != "draws"},
            "relabel_arm_vacuous": {k: v for k, v in rel.items() if k != "draws"},
            "controls_are_informative": ctl.get("controls_are_informative"),
            "shuffle_vs_cyclic": gap,
        }
        pd.DataFrame({"cyclic_draws": gen["draws"]}).to_csv(
            os.path.join(hb.OUT, "permutation_draws_heterogeneity_%s.csv" % tgt), index=False)

    FIND["heterogeneity"] = res
    pd.DataFrame([
        dict(target=k, real_sd=v["real_sd_of_per_player_diff"],
             mean_diff=v["mean_per_player_diff"], iqr=v["iqr_per_player_diff"],
             n_players=v["n_players"], cyclic_null_mean=v["cyclic_null"]["mean"],
             cyclic_null_sd=v["cyclic_null"]["sd"], p_cyclic=v["cyclic_null"]["p"],
             relabel_is_noop=v["relabel_arm_vacuous"].get("is_noop"),
             shuffle_p=v["shuffle_vs_cyclic"].get("shuffle_p"))
        for k, v in res.items()]).to_csv(os.path.join(hb.OUT, "heterogeneity.csv"), index=False)

    with open(os.path.join(hb.OUT, "_s05.json"), "w", encoding="utf-8") as fh:
        json.dump(hb.jsonable(FIND), fh, indent=2)
    print("\n  wrote heterogeneity.csv, permutation_draws_heterogeneity_*.csv, _s05.json")


if __name__ == "__main__":
    main()
