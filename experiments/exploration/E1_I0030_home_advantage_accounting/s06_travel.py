"""S06 -- STEP 6.  EASTBOUND TIME-ZONE TRAVEL, AS A PREREGISTERED DIRECTIONAL HYPOTHESIS.

The direction was fixed in `CANDIDATES_PRESELECTED.md` and hashed before any statistic:
    EASTBOUND crossings (tz_delta >= +1) HURT the travelling team -- NEGATIVE on team points and on
    team points per possession -- because an eastward shift demands a circadian PHASE ADVANCE.
WESTBOUND and SAME-ZONE TRAVEL are internal controls: if the effect appears equally in all three
arms it is travel or schedule, not circadian, and the mechanism is REFUTED.

THE KNOWN TRAP, DISCLOSED UP FRONT.  Rest and schedule state have died in four screens across three
targets in this programme.  Eastbound travel is correlated with rest days and with road-trip
position, so an "effect" that disappears once rest and venue are held fixed is that dead family in
new clothes.  Both the raw and the adjusted contrasts are reported and the screen says which.

THE NULL.  tz_delta varies WITHIN a team-season and is not balanced within a game, so neither the
paired game sign-flip (s02) nor a between-group permutation applies.  The null is a CYCLIC SHIFT of
the travel indicator inside each (season, team_id) date-ordered series: it preserves the marginal
distribution AND the schedule's serial structure (road trips come in runs) and destroys only the
alignment to the outcome.  The within-group SHUFFLE is the K6 defect and is not used for any verdict.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import ha_base as hb
import s00_prereg
import screenkit as sk

N_DRAWS = 4000
ARMS = ["eastbound", "westbound", "same_zone_travel"]     # no_travel is the reference arm


def prior_only_baseline(t, col):
    """Team's expanding mean of `col` over its STRICTLY PRIOR same-season games, plus the
    opponent's expanding mean of what it ALLOWED.  Both are strictly prior; both are used only to
    remove team strength from the outcome so the travel arm is not a strength contrast."""
    t = t.sort_values(["season", "team_id", "game_date", "game_id"], kind="stable").reset_index(
        drop=True)
    _, st, ns = hb.group_bounds(t, ["season", "team_id"])
    v = t[col].to_numpy(float)
    own = np.full(len(t), np.nan)
    for a, n in zip(st, ns):
        c = np.r_[0.0, np.cumsum(v[a:a + n])]
        k = np.arange(n, dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            own[a:a + n] = np.where(k > 0, c[:n] / np.where(k > 0, k, 1.0), np.nan)
    t["own_pre_" + col] = own
    # opponent's prior mean ALLOWED = the opponent's prior mean of opp_<col>
    ocol = "opp_" + col
    if ocol in t.columns:
        t2 = t.sort_values(["season", "team_id", "game_date", "game_id"], kind="stable")
        _, st2, ns2 = hb.group_bounds(t2, ["season", "team_id"])
        w = t2[ocol].to_numpy(float)
        allowed = np.full(len(t2), np.nan)
        for a, n in zip(st2, ns2):
            c = np.r_[0.0, np.cumsum(w[a:a + n])]
            k = np.arange(n, dtype=float)
            with np.errstate(invalid="ignore", divide="ignore"):
                allowed[a:a + n] = np.where(k > 0, c[:n] / np.where(k > 0, k, 1.0), np.nan)
        lut = pd.Series(allowed, index=pd.MultiIndex.from_arrays(
            [t2["season"], t2["team_id"], t2["game_id"]]))
        key = pd.MultiIndex.from_arrays([t["season"], t["opp_team_id"], t["game_id"]])
        t["opp_pre_allowed_" + col] = lut.reindex(key).to_numpy()
    return t


def main():
    hb.hdr("S06 EASTBOUND TRAVEL -- PREREGISTERED DIRECTIONAL TEST")
    prereg = s00_prereg.assert_prereg_unchanged()
    FIND = {"prereg_sha256": prereg["prereg_sha256"],
            "PREREGISTERED_DIRECTION": prereg["travel_prereg"]["DIRECTIONAL_HYPOTHESIS"]}
    print("  PREREGISTERED (hash %s): eastbound HURTS -- NEGATIVE on pts and ppp."
          % prereg["prereg_sha256"][:12])

    t = pd.read_parquet(os.path.join(hb.OUT, "_team_frame.parquet"))
    sk.assert_partition(t[["season", "game_date"]], verbose=False)
    t = t[t["season_type"] == "Regular Season"].copy()
    t = prior_only_baseline(t, "pts")
    t["ppp"] = t["pts"] / t["poss"]
    t = prior_only_baseline(t, "ppp") if "opp_ppp" in t.columns else t
    _, st, ns = hb.group_bounds(
        t.sort_values(["season", "team_id", "game_date", "game_id"], kind="stable"),
        ["season", "team_id"])

    g = t[t["tz_delta"].notna()].copy()
    g = g.sort_values(["season", "team_id", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    print("  team-games with a strictly-prior previous game: %d" % len(g))
    print("  arm counts: %s"
          % {a: int(g[a].sum()) for a in ARMS + ["no_travel"]})
    FIND["arm_counts"] = {a: int(g[a].sum()) for a in ARMS + ["no_travel"]}

    # ---- THE TRAP CHECK, RUN FIRST: how confounded ARE the arms with rest and venue?
    hb.hdr("A. THE CONFOUND CHECK -- is this the dead rest/schedule family in new clothes?")
    conf = (g.assign(arm=np.select([g[a] == 1 for a in ARMS], ARMS, default="no_travel"))
             .groupby("arm")
             .agg(n=("pts", "size"), rest_days=("rest_days", "mean"),
                  is_home=("is_home", "mean"), own_pre_pts=("own_pre_pts", "mean"),
                  pts=("pts", "mean"), ppp=("ppp", "mean"), poss=("poss", "mean")))
    print(conf.round(4).to_string())
    print("  -> eastbound and westbound are almost entirely AWAY-team states (is_home near 0 for")
    print("     the crossing arms) and 'no_travel' is mostly a home stand.  Any raw contrast")
    print("     between them is therefore MOSTLY THE HOME EFFECT, not travel.  The adjusted arm")
    print("     below holds is_home and rest fixed; the raw arm is reported to expose the size of")
    print("     the confound rather than to be believed.")
    FIND["confound_table"] = conf.reset_index().to_dict("records")

    rows = []
    # ---- B. RAW arm means (confounded, reported for the contrast)
    hb.hdr("B. RAW ARM CONTRASTS (confounded -- reported, not believed)")
    for tgt in ["pts", "ppp", "poss", "fta", "fg_pct"]:
        base = float(g.loc[g["no_travel"] == 1, tgt].mean())
        for a in ARMS:
            v = float(g.loc[g[a] == 1, tgt].mean())
            rows.append(dict(analysis="RAW", target=tgt, arm=a, n=int(g[a].sum()),
                             arm_mean=v, reference_mean=base, diff_vs_no_travel=v - base,
                             p_cyclic=np.nan, note="CONFOUNDED with is_home and rest"))
            print("    %-8s %-18s mean=%8.4f   vs no_travel %8.4f   diff=%+.4f"
                  % (tgt, a, v, base, v - base))

    # ---- C. ADJUSTED: partial out is_home, rest, and prior-only team/opponent strength
    hb.hdr("C. ADJUSTED CONTRASTS, with the cyclic-shift null")
    COV = ["is_home", "rest_days", "own_pre_pts", "opp_pre_allowed_pts"]
    gg = g.dropna(subset=COV + ["pts", "ppp"]).copy().reset_index(drop=True)
    gg = gg.sort_values(["season", "team_id", "game_date", "game_id"],
                        kind="stable").reset_index(drop=True)
    print("  rows after dropping any missing covariate: %d (from %d)" % (len(gg), len(g)))

    acf_rows = {}
    for a in ARMS:
        acf = sk.within_group_acf1(gg, a, ["season", "team_id"], order_col="game_date")
        acf_rows[a] = acf["acf1"]
        print("  within-(season,team) acf1(%s) = %s  -- non-zero, so the SHUFFLE is inadmissible "
              "(K6) and the CYCLIC shift is used" % (a, round(acf["acf1"], 5)
                                                     if acf["acf1"] is not None else None))
    FIND["within_team_season_acf1"] = acf_rows

    def make_stat(target, arm):
        cols = COV + [arm]
        def stat(d):
            y = d[target].to_numpy(float)
            Xb = d[COV].to_numpy(float)
            Xf = d[cols].to_numpy(float)
            return sk.delta_r2_plain(y, Xb, Xf)
        return stat

    def coef_of(d, target, arm):
        X = np.column_stack([np.ones(len(d)), d[COV].to_numpy(float),
                             d[arm].to_numpy(float)])
        c, *_ = np.linalg.lstsq(X, d[target].to_numpy(float), rcond=None)
        return float(c[-1])

    for tgt in ["pts", "ppp"]:
        for a in ARMS:
            stat = make_stat(tgt, a)
            real = stat(gg)
            beta = coef_of(gg, tgt, a)
            nl = sk.permutation_null(stat, gg, ["season", "team_id"], N_DRAWS, hb.SEED,
                                     feature_col=a, scheme=sk.SCHEME_WITHIN_CYCLIC,
                                     order_col="game_date", alternative="greater")
            # the SIGNED test the preregistration actually commits to
            bd = np.empty(N_DRAWS)
            rng = np.random.default_rng(hb.SEED)
            _, starts, nsz = hb.group_bounds(gg, ["season", "team_id"])
            xv = gg[a].to_numpy(float)
            work = gg.copy()
            for i in range(N_DRAWS):
                work[a] = hb.cyclic_shift_within_groups(xv, starts, nsz, rng)
                bd[i] = coef_of(work, tgt, a)
            p_signed = (1.0 + int((bd <= beta + 1e-15).sum())) / (N_DRAWS + 1.0)
            rows.append(dict(analysis="ADJUSTED", target=tgt, arm=a, n=int(gg[a].sum()),
                             beta=beta, dR2=real, null_mean_dR2=nl["mean"],
                             null_sd_dR2=nl["sd"], p_cyclic_dR2=nl["p"],
                             null_sd_beta=float(bd.std(ddof=1)),
                             p_cyclic_beta_LOWER_TAIL_prereg=p_signed,
                             covariates="+".join(COV)))
            print("    %-4s %-18s beta=%+.5f (null sd %.5f)  dR2=%.3e  p(dR2)=%.4f  "
                  "p(beta<=obs, PREREGISTERED lower tail)=%.4f"
                  % (tgt, a, beta, bd.std(ddof=1), real, nl["p"], p_signed))
            if a == "eastbound":
                pd.DataFrame({"beta_draws": bd, "dr2_draws": nl["draws"]}).to_csv(
                    os.path.join(hb.OUT, "permutation_draws_travel_%s.csv" % tgt), index=False)

    # ---- D. the sharpest version: eastbound vs westbound, ROAD GAMES ONLY
    hb.hdr("D. THE SHARPEST TEST -- eastbound vs westbound, ROAD GAMES ONLY")
    print("  Restricting to away games removes the is_home confound entirely and compares the two")
    print("  crossing directions against each other.  If circadian phase advance is the mechanism,")
    print("  eastbound must be WORSE than westbound here.  If they are the same, it is not.")
    road = gg[(gg["is_home"] == 0) & ((gg["eastbound"] == 1) | (gg["westbound"] == 1))].copy()
    road = road.sort_values(["season", "team_id", "game_date", "game_id"],
                            kind="stable").reset_index(drop=True)
    print("  road crossing games: eastbound n=%d, westbound n=%d"
          % (int(road["eastbound"].sum()), int(road["westbound"].sum())))
    COV2 = ["rest_days", "own_pre_pts", "opp_pre_allowed_pts"]
    for tgt in ["pts", "ppp"]:
        X = np.column_stack([np.ones(len(road)), road[COV2].to_numpy(float),
                             road["eastbound"].to_numpy(float)])
        c, *_ = np.linalg.lstsq(X, road[tgt].to_numpy(float), rcond=None)
        beta = float(c[-1])
        raw = float(road.loc[road.eastbound == 1, tgt].mean()
                    - road.loc[road.westbound == 1, tgt].mean())
        rng = np.random.default_rng(hb.SEED)
        _, s2, n2 = hb.group_bounds(road, ["season", "team_id"])
        xv = road["eastbound"].to_numpy(float)
        bd = np.empty(N_DRAWS)
        for i in range(N_DRAWS):
            xx = hb.cyclic_shift_within_groups(xv, s2, n2, rng)
            Xp = np.column_stack([np.ones(len(road)), road[COV2].to_numpy(float), xx])
            cc, *_ = np.linalg.lstsq(Xp, road[tgt].to_numpy(float), rcond=None)
            bd[i] = float(cc[-1])
        p_signed = (1.0 + int((bd <= beta + 1e-15).sum())) / (N_DRAWS + 1.0)
        rows.append(dict(analysis="ROAD_ONLY_EAST_vs_WEST", target=tgt, arm="eastbound",
                         n=int(road["eastbound"].sum()), beta=beta,
                         raw_east_minus_west=raw, null_sd_beta=float(bd.std(ddof=1)),
                         p_cyclic_beta_LOWER_TAIL_prereg=p_signed, covariates="+".join(COV2)))
        print("    %-4s raw east-minus-west = %+.4f   adjusted beta = %+.5f (null sd %.5f)   "
              "p(PREREGISTERED lower tail) = %.4f" % (tgt, raw, beta, bd.std(ddof=1), p_signed))

    # ---- E. dose response: |tz_delta| as a continuous eastbound magnitude
    hb.hdr("E. DOSE RESPONSE -- does the size of the crossing matter?")
    dose = (gg[gg["is_home"] == 0]
            .groupby("tz_delta")
            .agg(n=("pts", "size"), pts=("pts", "mean"), ppp=("ppp", "mean"),
                 rest=("rest_days", "mean")))
    print(dose.round(4).to_string())
    FIND["dose_response_road_only"] = dose.reset_index().to_dict("records")

    td = pd.DataFrame(rows)
    td.to_csv(os.path.join(hb.OUT, "travel_directional.csv"), index=False)
    FIND["travel_rows"] = td.to_dict("records")
    with open(os.path.join(hb.OUT, "_s06.json"), "w", encoding="utf-8") as fh:
        json.dump(hb.jsonable(FIND), fh, indent=2)
    print("\n  wrote travel_directional.csv, permutation_draws_travel_*.csv, _s06.json")


if __name__ == "__main__":
    main()
