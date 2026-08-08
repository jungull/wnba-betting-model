"""S09 -- STEP 3.  THE FREE-THROW COMPOSITION.  P07 and P08.

D104: the venue effect is 97.6% free throws and specifically +1.087 ATTEMPTS, with accuracy worth
only +0.4 percentage points.  So the POINTS value of the venue edge depends on who is shooting
them.  This builds that composition at team level and asks whether it beats a flat home constant.

D108 IS HONOURED FROM THE START: the free-throw main effects (the team's prior FT% and its prior
free-throw rate) ARE IN THE BASE BEFORE the composition is tested, so the composition cannot win
by smuggling in a main effect.  D108 measured 43 of 44 opponent cells dying once the main effect
was in the base; this screen puts it there first rather than discovering it afterwards.

THE ARITHMETIC CEILING IS COMPUTED BEFORE ANYTHING IS FITTED, exactly as D104 did.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agg_base as ab
import refs
import s04_prereg

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
NDRAW = 20000
D104_FTA_DIFFERENTIAL = 1.087    # home minus away free-throw ATTEMPTS, D104
D104_FT_SHARE_OF_VENUE = 0.976   # free throws are 97.6% of the venue effect, D104


def main():
    ab.hdr("S09 FREE-THROW COMPOSITION")
    pre = s04_prereg.assert_unchanged()
    print("  prereg hash verified: %s" % pre["prereg_sha256"])
    F = {"prereg_sha256": pre["prereg_sha256"]}

    tf = pd.read_parquet(os.path.join(ab.OUT, "_team_frame_scored.parquet"))
    tf = tf.sort_values(["game_date", "game_id", "team_id"], kind="stable").reset_index(drop=True)

    # ------------------------------------------------------------------ prior FT quantities
    ab.hdr("1. STRICTLY-PRIOR TEAM FREE-THROW STATE")
    lg_ftm = refs.expanding_league_by_date(tf["game_date"], tf["ftm"])
    lg_fta = refs.expanding_league_by_date(tf["game_date"], tf["fta"])
    tf["LEAGUE_FT_PCT_PRIOR"] = lg_ftm / lg_fta
    Sn, Sd, Sw, Np = refs.prior_prefix(tf, ["season", "team_id"], "ftm", "fta", None)
    K_FT = 40.0     # pseudo-attempts; shrinks a team with few prior games to the league rate
    tf["FT_PCT_PRIOR"] = ((np.where(Sd > 0, Sn, 0.0) + K_FT * tf["LEAGUE_FT_PCT_PRIOR"])
                          / (np.where(Sd > 0, Sd, 0.0) + K_FT))
    Sn2, Sd2, Sw2, Np2 = refs.prior_prefix(tf, ["season", "team_id"], "fta", None, None)
    lg_ftarate = refs.expanding_league_by_date(tf["game_date"], tf["fta"])
    tf["FTA_RATE_PRIOR"] = ((np.where(Sw2 > 0, Sn2, 0.0) + 8.0 * lg_ftarate)
                            / (np.where(Sw2 > 0, Sw2, 0.0) + 8.0))
    rs1 = tf["RS1"].to_numpy()
    print("  league prior FT%%: mean %.4f" % tf.loc[rs1, "LEAGUE_FT_PCT_PRIOR"].mean())
    print("  team prior FT%% on RS1: mean %.4f  sd %.4f  min %.4f  max %.4f"
          % (tf.loc[rs1, "FT_PCT_PRIOR"].mean(), tf.loc[rs1, "FT_PCT_PRIOR"].std(ddof=1),
             tf.loc[rs1, "FT_PCT_PRIOR"].min(), tf.loc[rs1, "FT_PCT_PRIOR"].max()))

    # the spread the user asked to see, per team-season, on REALISED FT% (descriptive)
    ts = (tf[rs1].groupby(["season", "team_id"])
          .agg(ftm=("ftm", "sum"), fta=("fta", "sum"),
               prior_ftpct_mean=("FT_PCT_PRIOR", "mean"), n=("pts", "size")).reset_index())
    ts["realised_ft_pct"] = ts["ftm"] / ts["fta"]
    ts = ts.sort_values("realised_ft_pct")
    print("\n  REALISED team-season FT%% spread (descriptive, the user's question):")
    print("    lowest  %.4f   highest %.4f   spread %.4f (%.1f percentage points)"
          % (ts["realised_ft_pct"].min(), ts["realised_ft_pct"].max(),
             ts["realised_ft_pct"].max() - ts["realised_ft_pct"].min(),
             100 * (ts["realised_ft_pct"].max() - ts["realised_ft_pct"].min())))
    print("    sd across the %d team-seasons: %.4f" % (len(ts), ts["realised_ft_pct"].std(ddof=1)))
    ts.to_csv(os.path.join(ab.OUT, "ft_team_season_spread.csv"), index=False)

    # ------------------------------------------------------------------ ARITHMETIC CEILING FIRST
    ab.hdr("2. THE ARITHMETIC CEILING -- computed BEFORE anything is fitted (D104's discipline)")
    y = tf.loc[rs1, "pts"].to_numpy(float)
    sd_y = float(y.std(ddof=1))
    edge = (2.0 * tf.loc[rs1, "is_home"].to_numpy(float) - 1.0) * 0.5 * D104_FTA_DIFFERENTIAL
    ftp = tf.loc[rs1, "FT_PCT_PRIOR"].to_numpy(float)
    ftl = tf.loc[rs1, "LEAGUE_FT_PCT_PRIOR"].to_numpy(float)
    composed = edge * ftp
    flat = edge * ftl
    delta = composed - flat          # ALL the composition adds beyond a flat home constant
    print("  venue FTA edge per team-game        : %+.4f attempts (home) / %+.4f (away)"
          % (0.5 * D104_FTA_DIFFERENTIAL, -0.5 * D104_FTA_DIFFERENTIAL))
    print("  venue POINTS edge at the league rate: %.4f points" % float(np.abs(flat).mean()))
    print("  composed minus flat: mean %+.6f  sd %.6f  min %+.6f  max %+.6f points"
          % (delta.mean(), delta.std(ddof=1), delta.min(), delta.max()))
    print("  response sd                         : %.4f points" % sd_y)
    ceiling = float((delta.std(ddof=1) / sd_y) ** 2)
    print("\n  LARGEST dR2 A PERFECT COMPOSITION TERM COULD ADD OVER A FLAT ONE: %.4e" % ceiling)
    print("  for comparison: D103's detection floor is ~1.0e-03 at ONE preregistered cell,")
    print("                  D104's PLAYER-level home ceiling was 4.63e-05,")
    print("                  and D108's own resolution bound was ~5e-04.")
    print("  -> the team-level FT COMPOSITION is %.0fx BELOW D104's player-level home ceiling and"
          % (4.63e-05 / ceiling))
    print("     %.0fx below D103's single-cell detection floor.  IT IS UNMEASURABLE BY"
          % (1.02e-03 / ceiling))
    print("     CONSTRUCTION, AND THAT WAS KNOWABLE WITHOUT FITTING ANYTHING.")
    F["arithmetic_ceiling"] = {
        "d104_fta_differential_used": D104_FTA_DIFFERENTIAL,
        "venue_points_edge_at_league_rate": float(np.abs(flat).mean()),
        "composed_minus_flat_sd_points": float(delta.std(ddof=1)),
        "composed_minus_flat_range_points": [float(delta.min()), float(delta.max())],
        "response_sd": sd_y,
        "max_dR2_of_composition_over_flat": ceiling,
        "d103_single_cell_floor": 1.02e-03,
        "d104_player_level_home_ceiling": 4.63e-05,
        "ratio_below_d103_floor": float(1.02e-03 / ceiling),
        "ratio_below_d104_player_ceiling": float(4.63e-05 / ceiling),
        "verdict": ("the composition is unmeasurable at this sample size BY ARITHMETIC. it is "
                    "computed anyway below so the measurement can be checked against its own "
                    "a-priori ceiling, exactly as D104 did.")}

    # ------------------------------------------------------------------ base with main effects
    ab.hdr("3. BASE CARRYING THE FREE-THROW MAIN EFFECTS FROM THE START (D108)")
    tf["_resid_R2"] = tf["pts"] - tf["R2_TEAM_EWMA"]
    for c, src in [("_ftpct_c", "FT_PCT_PRIOR"), ("_ftarate_c", "FTA_RATE_PRIOR")]:
        m = tf.loc[rs1, src].mean()
        tf[c] = tf[src] - m
    tf["_edge"] = (2.0 * tf["is_home"] - 1.0) * 0.5 * D104_FTA_DIFFERENTIAL
    tf["_flat_term"] = tf["_edge"] * tf["LEAGUE_FT_PCT_PRIOR"]
    tf["_composed_term"] = tf["_edge"] * tf["FT_PCT_PRIOR"]
    tf["_delta_term"] = tf["_composed_term"] - tf["_flat_term"]

    def wf_multi(cols):
        """OLS of the R2 residual on `cols`, fitted on STRICTLY EARLIER SEASONS ONLY."""
        yv = tf["_resid_R2"].to_numpy(float)
        X = tf[cols].to_numpy(float)
        season = tf["season"].to_numpy()
        out = np.full(len(tf), np.nan); coef = {}
        for s in ab.SCORED_SEASONS:
            m = np.isin(season, [v for v in sorted(set(season.tolist())) if v < s]) \
                & np.isfinite(yv) & np.all(np.isfinite(X), axis=1)
            if m.sum() < 30:
                b = np.zeros(len(cols))
            else:
                b, *_ = np.linalg.lstsq(X[m], yv[m], rcond=None)
            coef[str(s)] = {c: float(v) for c, v in zip(cols, b)}
            sm = season == s
            out[sm] = X[sm] @ b
        return out, coef

    add_base, cb = wf_multi(["_ftpct_c", "_ftarate_c"])
    tf["BASE_NO_VENUE"] = tf["R2_TEAM_EWMA"] + add_base
    print("  BASE_NO_VENUE coefficients by season: %s" % cb)

    add_flat, cf = wf_multi(["_ftpct_c", "_ftarate_c", "_flat_term"])
    tf["FT_FLAT"] = tf["R2_TEAM_EWMA"] + add_flat
    print("  FT_FLAT coefficients by season      : %s" % cf)

    add_comp, cc = wf_multi(["_ftpct_c", "_ftarate_c", "_composed_term"])
    tf["FT_COMPOSED"] = tf["R2_TEAM_EWMA"] + add_comp
    print("  FT_COMPOSED coefficients by season   : %s" % cc)

    # the D108-correct incremental form: composition ONLY as a deviation from flat, over a base
    # that ALREADY carries the flat venue term
    add_inc, ci = wf_multi(["_ftpct_c", "_ftarate_c", "_flat_term", "_delta_term"])
    tf["FT_COMPOSED_OVER_FLAT"] = tf["R2_TEAM_EWMA"] + add_inc
    print("  FT_COMPOSED_OVER_FLAT coefficients   : %s" % ci)
    F["walk_forward_coefficients"] = {"BASE_NO_VENUE": cb, "FT_FLAT": cf,
                                      "FT_COMPOSED": cc, "FT_COMPOSED_OVER_FLAT": ci}

    # ------------------------------------------------------------------ score
    ab.hdr("4. SCORED -- same response, same rows, same SST")
    sst = ab.sst_of(y)
    arms = ["R2_TEAM_EWMA", "BASE_NO_VENUE", "FT_FLAT", "FT_COMPOSED", "FT_COMPOSED_OVER_FLAT"]
    rows = []
    for a in arms:
        v = tf.loc[rs1, a].to_numpy(float)
        rows.append(dict(arm=a, n=int(rs1.sum()), MAE=ab.mae(y, v),
                         R2_common_SST=ab.r2_common(y, v, sst),
                         bias=float(np.mean(v - y))))
    ftab = pd.DataFrame(rows)
    ftab["dR2_vs_BASE_NO_VENUE"] = (ftab["R2_common_SST"]
                                    - float(ftab.loc[ftab["arm"] == "BASE_NO_VENUE",
                                                     "R2_common_SST"].iloc[0]))
    print(ftab.to_string(index=False))
    ftab.to_csv(os.path.join(ab.OUT, "ft_composition.csv"), index=False)
    F["ft_composition_table"] = ftab.to_dict("records")

    tsb = (tf["season"].astype(str) + "_" + tf["team_id"].astype(str)).to_numpy()[rs1]
    cells = {}
    for cid, a, b in [("P07", "FT_COMPOSED", "FT_FLAT"),
                      ("P08", "FT_COMPOSED", "BASE_NO_VENUE"),
                      ("P07b_EXPLORATORY", "FT_COMPOSED_OVER_FLAT", "FT_FLAT")]:
        la = np.abs(y - tf.loc[rs1, a].to_numpy(float))
        lb = np.abs(y - tf.loc[rs1, b].to_numpy(float))
        n1 = ab.paired_signflip_block(la, lb, tsb, NDRAW, ab.SEED + 51)
        cells[cid] = {"cell": cid, "arm_A": a, "arm_B": b,
                      "MAE_A": float(np.mean(la)), "MAE_B": float(np.mean(lb)),
                      "MAE_advantage_A_over_B": n1["real"], "N1_p": n1["p"],
                      "N1_null_mean": n1["null_mean"], "N1_null_sd": n1["null_sd"],
                      "MDE80_MAE": float(2.80 * n1["null_sd"]),
                      "exploratory": bool("EXPLORATORY" in cid)}
        print("  %s %-22s vs %-16s dMAE %+.6f p %.4f (null_mean %+.2e sd %.6f) MDE80 %.5f"
              % (cid, a, b, n1["real"], n1["p"], n1["null_mean"], n1["null_sd"],
                 2.80 * n1["null_sd"]))
    F["ft_cells"] = cells
    pd.DataFrame(list(cells.values())).to_csv(os.path.join(ab.OUT, "ft_cells.csv"), index=False)

    # ------------------------------------------------------------------ the spread, in points
    ab.hdr("5. THE SPREAD ACROSS TEAMS, IN POINTS -- what the user actually asked for")
    lo = float(ts["realised_ft_pct"].min()); hi = float(ts["realised_ft_pct"].max())
    print("  a team shooting %.1f%% and a team shooting %.1f%% convert the SAME +%.3f attempt"
          % (100 * lo, 100 * hi, D104_FTA_DIFFERENTIAL))
    print("  venue edge into %.4f and %.4f points respectively -- a difference of %.4f points"
          % (lo * D104_FTA_DIFFERENTIAL, hi * D104_FTA_DIFFERENTIAL,
             (hi - lo) * D104_FTA_DIFFERENTIAL))
    print("  per game.  Against a team-points sd of %.2f that is %.4f standard deviations,"
          % (sd_y, (hi - lo) * D104_FTA_DIFFERENTIAL / sd_y))
    print("  and against the +0.965 point home advantage itself it is %.1f%% of the effect."
          % (100 * (hi - lo) * D104_FTA_DIFFERENTIAL / 0.965090))
    F["spread_in_points"] = {
        "lowest_team_season_ft_pct": lo, "highest_team_season_ft_pct": hi,
        "points_from_venue_edge_at_lowest": float(lo * D104_FTA_DIFFERENTIAL),
        "points_from_venue_edge_at_highest": float(hi * D104_FTA_DIFFERENTIAL),
        "spread_points_per_game": float((hi - lo) * D104_FTA_DIFFERENTIAL),
        "spread_in_response_sds": float((hi - lo) * D104_FTA_DIFFERENTIAL / sd_y),
        "spread_as_pct_of_the_0.965_home_advantage":
            float(100 * (hi - lo) * D104_FTA_DIFFERENTIAL / 0.965090)}

    tf.to_parquet(os.path.join(ab.OUT, "_team_frame_scored.parquet"), index=False)
    with open(os.path.join(ab.OUT, "_s09.json"), "w", encoding="utf-8") as fh:
        json.dump(ab.jsonable(F), fh, indent=1)
    print("\n  wrote ft_composition.csv, ft_cells.csv, ft_team_season_spread.csv, _s09.json")


if __name__ == "__main__":
    main()
