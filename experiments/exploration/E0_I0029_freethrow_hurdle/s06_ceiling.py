"""E0_I0029 s06 -- STEP 3: DOES IT REACH POINTS, AND WHAT IS THE CEILING?

CEILING FORM (D084/D089, as used by D097 and E0_I0024):

    CEILING_dR2 = (|beta| * sd_candidate / sd_y)^2

i.e. the share of the response's variance reachable if 1 sd of the signal moves the response by
beta*sd.  The BASE-RESIDUALISED variant, using the sd of the candidate AFTER the base is projected
out, is reported alongside -- it is the honest one when the candidate is correlated with the base,
and it is always the smaller of the two.

BENCHMARKS
    0.002057   D089, the largest ceiling measured anywhere in this programme, and ALIVE
    0.001127   D079, shot mix -- DEAD on this arithmetic
    0.000129   D084, opponent conversion -- DEAD on this arithmetic

THE CHANNEL IS ALSO PROPAGATED AS A WHOLE, not only candidate by candidate.  A per-candidate
ceiling can understate a channel whose value is in the COMPOSITION.  So the composed honest
free-throw-points forecast (s04's all-HONEST composition) is itself carried onto points as a
single signal, walk-forward, and an ORACLE variant -- perfect knowledge of realised ftm -- is
reported as the channel's absolute upper bound.  If even the ORACLE bound is small, the channel is
closed regardless of how well any particular feature works.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ft_base import (BaseFit, HEADLINE_SEASONS, OUT, TARGET_SPECIFIC, assert_partition,
                     basecols_for, hdr, jsonable, r2_plain, safe_div)
from s01_prereg import BASES, CANDIDATES

BENCH = {"D089_alive_largest": 0.002057, "D079_dead": 0.001127, "D084_dead": 0.000129}
rep = {}

F = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F)
F = F.sort_values(["season", "game_date", "game_id"], kind="stable").reset_index(drop=True)

# ---- rebuild s04's composed forecasts (same code path, so the two files cannot drift)
def league_prior(col, mask=None):
    v = F[col].astype(float).copy()
    if mask is not None:
        v = v.where(mask)
    out = v.groupby(F["season"], sort=False).transform(lambda x: x.shift(1).expanding().mean())
    return out.groupby(F["season"], sort=False).transform(lambda x: x.ffill().bfill())


cond = F["COND"] == 1
F["ft_pct_given"] = safe_div(F["ftm"], F["fta"])
F["LG_A"], F["LG_G"] = league_prior("y_any_fta"), league_prior("fta", mask=cond)
F["LG_C"] = league_prior("ft_pct_given", mask=cond)
F["HON_A"] = F["ref_mean__y_any_fta"].fillna(F["LG_A"])
F["HON_G"] = F["ref_mean__y_fta_given"].fillna(F["LG_G"])
F["HON_C"] = F["F03_prior_ft_pct"].fillna(F["LG_C"])
F["FT_HONEST_COMPOSED"] = F["HON_A"] * F["HON_G"] * F["HON_C"]
F["FT_ORACLE_REALISED"] = F["y_ftm"].astype(float)
F["FT_HONEST_SIMPLE"] = F["ref_mean__y_ftm"]

STRATA = {
    "POOLED": F["season"].isin(HEADLINE_SEASONS).to_numpy(),
    "DECISION": (F["season"].isin(HEADLINE_SEASONS) & (F["DECISION"] == 1)).to_numpy(),
}


def resolve(base_name, target):
    return [c + "__" + target if c in TARGET_SPECIFIC else c for c in BASES[base_name]["cols"]]


# =====================================================================================
hdr("1. ARITHMETIC CEILING -- every candidate, carried onto POINTS and onto FT POINTS")
# =====================================================================================
SIGNALS = [c["name"] for c in CANDIDATES if c["family"] != "G"] + \
          ["FT_HONEST_COMPOSED", "FT_HONEST_SIMPLE", "FT_ORACLE_REALISED", "G01_noise",
           "G02_placebo_noop", "G03_placebo_perturbed"]
TARGET_SPECIFIC_CANDIDATES = {"G02_placebo_noop", "G03_placebo_perturbed"}
rows = []
for sname, smask in STRATA.items():
    for tgt in ["y_pts", "y_ftm"]:
        bcols = resolve("B_COMPLETE", tgt)
        for sig0 in SIGNALS:
            sig = sig0 + "__" + tgt if sig0 in TARGET_SPECIFIC_CANDIDATES else sig0
            ok = smask & np.isfinite(F[tgt].to_numpy(float)) & np.isfinite(F[sig].to_numpy(float))
            for c in bcols:
                ok = ok & np.isfinite(F[c].to_numpy(float))
            if ok.sum() < 300:
                continue
            d = F.loc[ok]
            y = d[tgt].to_numpy(float)
            x = d[sig].to_numpy(float)
            bf = BaseFit(y, d[bcols].to_numpy(float))
            beta = bf.beta(x)
            sd_x = float(np.std(x, ddof=1))
            sd_xr = bf.resid_sd(x)
            sd_y = float(np.std(y, ddof=1))
            ceil_raw = (abs(beta) * sd_x / sd_y) ** 2
            ceil_res = (abs(beta) * sd_xr / sd_y) ** 2
            rows.append(dict(
                stratum=sname, response=tgt, signal=sig0, signal_column=sig, n=int(ok.sum()),
                is_oracle=bool(sig == "FT_ORACLE_REALISED"),
                r2_base=bf.r2_base, dR2_over_B_COMPLETE=bf.dr2(x), beta=beta,
                sd_signal=sd_x, sd_signal_resid_of_base=sd_xr, sd_response=sd_y,
                move_per_1sd_natural_units=abs(beta) * sd_x,
                move_per_1sd_as_frac_of_sd_y=abs(beta) * sd_x / sd_y,
                move_per_1sd_resid_natural_units=abs(beta) * sd_xr,
                CEILING_dR2_raw=ceil_raw, CEILING_dR2_base_residualised=ceil_res,
                ratio_to_D089_alive=ceil_res / BENCH["D089_alive_largest"],
                ratio_to_D079_dead=ceil_res / BENCH["D079_dead"],
                ratio_to_D084_dead=ceil_res / BENCH["D084_dead"],
                verdict_vs_benchmarks=(
                    "ABOVE the largest measured (0.002057)" if ceil_res > BENCH["D089_alive_largest"]
                    else "between the dead benchmarks and the live one"
                    if ceil_res > BENCH["D079_dead"] else
                    "BELOW BOTH DEAD BENCHMARKS" if ceil_res < BENCH["D084_dead"] else
                    "below the dead shot-mix benchmark (0.001127)")))
C = pd.DataFrame(rows)
C.to_csv(os.path.join(OUT, "arithmetic_ceiling.csv"), index=False)

for sname in STRATA:
    for tgt in ["y_pts", "y_ftm"]:
        s = C[(C["stratum"] == sname) & (C["response"] == tgt)].sort_values(
            "CEILING_dR2_base_residualised", ascending=False)
        if not len(s):
            continue
        print("\n  ---- %s | response %s | sd_y=%.4f | n=%d ----"
              % (sname, tgt, s["sd_response"].iloc[0], s["n"].iloc[0]))
        print("   %-24s %11s %11s %11s %9s %s"
              % ("signal", "CEIL raw", "CEIL resid", "x D089", "1sd move", "verdict"))
        for _, r in s.iterrows():
            print("   %-24s %11.3e %11.3e %11.4f %9.4f %s"
                  % (r["signal"] + (" [ORACLE]" if r["is_oracle"] else ""), r["CEILING_dR2_raw"],
                     r["CEILING_dR2_base_residualised"], r["ratio_to_D089_alive"],
                     r["move_per_1sd_resid_natural_units"], r["verdict_vs_benchmarks"]))

# =====================================================================================
hdr("2. PROPAGATION TO A POINTS FORECAST -- WALK-FORWARD, THE WHOLE CHANNEL AT ONCE")
# =====================================================================================
print("  A per-candidate ceiling can understate a channel whose value is in the COMPOSITION, so")
print("  the composed honest FT-points forecast is carried onto points as a single signal and an")
print("  ORACLE variant (perfect knowledge of realised ftm) bounds the channel absolutely.")


def wf_r2(d, target, cols):
    yhat = np.full(len(d), np.nan)
    X = d[cols].to_numpy(float)
    y = d[target].to_numpy(float)
    ss = d["season"].to_numpy()
    for s in sorted(set(ss.tolist())):
        tr, te = ss < s, ss == s
        if tr.sum() < 200:
            continue
        Xtr = np.column_stack([np.ones(int(tr.sum())), X[tr]])
        ok = np.isfinite(Xtr).all(axis=1) & np.isfinite(y[tr])
        if ok.sum() < 200:
            continue
        b, *_ = np.linalg.lstsq(Xtr[ok], y[tr][ok], rcond=None)
        yhat[te] = np.column_stack([np.ones(int(te.sum())), X[te]]) @ b
    m = np.isfinite(y) & np.isfinite(yhat)
    return r2_plain(y[m], yhat[m]), int(m.sum())


# ---------------------------------------------------------------------------------------------
# AN EXACT IDENTITY, WHICH IS ITSELF ONE OF THIS SCREEN'S FINDINGS.
#
# The composed honest forecast is ALGEBRAICALLY THE SAME NUMBER as the simple prior mean of ftm.
# With n prior games, k of them with fta>0, S_fta = sum of prior fta and S_ftm = sum of prior ftm:
#
#     HON_A * HON_G * HON_C = (k/n) * (S_fta/k) * (S_ftm/S_fta) = S_ftm/n = prior mean of ftm
#
# So DECOMPOSING THE HURDLE BUYS EXACTLY NOTHING FOR A POINT FORECAST.  The three stage estimators
# multiply straight back into the aggregate estimator.  Whatever the hurdle is worth, it is worth
# it in the SHAPE OF THE DISTRIBUTION -- the 46.4% mass at zero -- and not in the conditional mean.
# Asserted rather than asserted-in-prose, so it cannot quietly stop being true.
_m = np.isfinite(F["FT_HONEST_COMPOSED"]) & np.isfinite(F["FT_HONEST_SIMPLE"])
_maxdiff = float(np.abs(F.loc[_m, "FT_HONEST_COMPOSED"] - F.loc[_m, "FT_HONEST_SIMPLE"]).max())
print("\n  IDENTITY CHECK: max |composed - simple prior mean| over %d rows = %.3e" % (_m.sum(), _maxdiff))
print("  -> the hurdle decomposition is EXACTLY MEAN-PRESERVING.  It can only pay in distributional")
print("     shape, never in the point forecast.  This is asserted, not asserted-in-prose.")
assert _maxdiff < 1e-12, "the composition identity does not hold -- one of the stages is misbuilt"
rep["hurdle_decomposition_is_exactly_mean_preserving"] = dict(
    max_abs_difference=_maxdiff, n=int(_m.sum()),
    algebra="(k/n)*(S_fta/k)*(S_ftm/S_fta) = S_ftm/n")

prop = []
for sname, smask in STRATA.items():
    bcols = resolve("B_COMPLETE", "y_pts")
    ok = smask & np.isfinite(F["y_pts"].to_numpy(float))
    for c in bcols + ["FT_HONEST_COMPOSED", "FT_HONEST_SIMPLE", "M02_opp_allowed_fta_pg",
                      "M03_opp_allowed_ftm_pg"]:
        ok = ok & np.isfinite(F[c].to_numpy(float))
    d = F.loc[ok]
    r2b, nb = wf_r2(d, "y_pts", bcols)
    for add, label in [(["FT_HONEST_COMPOSED"], "+ composed honest FT forecast"),
                       (["FT_HONEST_SIMPLE"], "+ simple prior-mean FT forecast"),
                       (["FT_HONEST_COMPOSED", "FT_HONEST_SIMPLE"], "+ both FT forecasts"),
                       (["M03_opp_allowed_ftm_pg"], "+ OPPONENT prior FTM-allowed per game"),
                       (["M02_opp_allowed_fta_pg"], "+ OPPONENT prior FTA-allowed per game"),
                       (["M02_opp_allowed_fta_pg", "M03_opp_allowed_ftm_pg"],
                        "+ BOTH opponent FT-allowance terms"),
                       (["FT_HONEST_SIMPLE", "M03_opp_allowed_ftm_pg"],
                        "+ own FT forecast AND opponent FT-allowance"),
                       (["FT_ORACLE_REALISED"], "+ REALISED ftm [ORACLE UPPER BOUND]")]:
        r2a, na = wf_r2(d, "y_pts", bcols + add)
        prop.append(dict(stratum=sname, n=nb, walkforward=True, addition=label,
                         r2_points_base=r2b, r2_points_with=r2a, delta_r2=r2a - r2b,
                         is_oracle="ORACLE" in label))
        print("   %-9s n=%-6d  R2(points) base %.5f -> %.5f   dR2 = %+.6f   %s"
              % (sname, nb, r2b, r2a, r2a - r2b, label))
P = pd.DataFrame(prop)
P.to_csv(os.path.join(OUT, "propagation_walkforward.csv"), index=False)

# =====================================================================================
hdr("3. PER-SEASON CONSISTENCY OF THE HEADLINE STAGE RESULT")
# =====================================================================================
cons = []
for s in sorted(F["season"].unique()):
    for sname, base_mask in [("POOLED", np.ones(len(F), bool)),
                             ("DECISION", (F["DECISION"] == 1).to_numpy())]:
        m = (F["season"] == s).to_numpy() & base_mask
        d = F.loc[m]
        y = d["y_ftm"].to_numpy(float)
        rows_ok = np.isfinite(y)
        def r2of(col):
            p = d[col].to_numpy(float)
            k = rows_ok & np.isfinite(p)
            return r2_plain(y[k], p[k]), int(k.sum())
        a, na = r2of("HON_A")            # stage A alone, scaled -- reported as a correlation proxy
        r2c, nc = r2of("FT_HONEST_COMPOSED")
        r2s, ns = r2of("FT_HONEST_SIMPLE")
        # THE HEADLINE CLAIM, SEASON BY SEASON.  A result that lives in one season is not a
        # result.  M03 (opponent prior FTM-allowed per game) is carried onto POINTS over
        # B_COMPLETE within each season separately.  Single-season n is small, so these are
        # reported as a DIRECTION-AND-STABILITY check, not as four independent tests.
        row = dict(season=int(s), stratum=sname, n=int(m.sum()),
                   r2_ftm_composed_honest=r2c, r2_ftm_simple_prior_mean=r2s,
                   corr_stageA_prior_with_ftm=float(np.corrcoef(
                       d.loc[rows_ok, "HON_A"], y[rows_ok])[0, 1]))
        bc = resolve("B_COMPLETE", "y_pts")
        kk = m.copy()
        for cc in bc + ["y_pts", "M03_opp_allowed_ftm_pg", "M02_opp_allowed_fta_pg"]:
            kk = kk & np.isfinite(F[cc].to_numpy(float))
        dd = F.loc[kk]
        if len(dd) > 300:
            bf = BaseFit(dd["y_pts"].to_numpy(float), dd[bc].to_numpy(float))
            for cn, tag in [("M03_opp_allowed_ftm_pg", "M03"), ("M02_opp_allowed_fta_pg", "M02")]:
                xv = dd[cn].to_numpy(float)
                row["dR2_points_" + tag] = bf.dr2(xv)
                row["beta_points_" + tag] = bf.beta(xv)
            row["n_points_cells"] = int(len(dd))
        cons.append(row)
CS = pd.DataFrame(cons)
CS.to_csv(os.path.join(OUT, "per_season_consistency.csv"), index=False)
print(CS.to_string(index=False))

# =====================================================================================
hdr("4. HISTORY-FLOOR SENSITIVITY (floor applied to the HISTORY only, never the response)")
# =====================================================================================
from ft_base import MP_PATH, SEASONS, prior_sum
mp = pd.read_parquet(MP_PATH)
mp["game_date"] = pd.to_datetime(mp["game_date"], errors="coerce")
mp = mp[mp["season"].isin(SEASONS)].copy()
assert_partition(mp)
for c in ["minutes", "fta", "ftm", "pts"]:
    mp[c] = pd.to_numeric(mp[c], errors="coerce").astype(float)
mp["player_id"] = pd.to_numeric(mp["player_id"], errors="coerce").astype("int64")
mp = mp[mp["minutes"] > 0].sort_values(["season", "player_id", "game_date", "game_id"],
                                       kind="stable").reset_index(drop=True)
mp["y_any_fta"] = (mp["fta"] > 0).astype(float)
mp["ref_mean_minutes"] = mp.groupby(["season", "player_id"], sort=False)["minutes"].transform(
    lambda x: x.shift(1).expanding().mean())
fl_rows = []
for floor in [0.0, 5.0, 10.0, 15.0, 20.0]:
    mp["_f"] = (mp["minutes"] >= floor).astype(float)
    for tgt in ["y_any_fta", "ftm"]:
        tmp = mp[["season", "player_id"]].copy()
        tmp["_n"] = mp[tgt] * mp["_f"]
        tmp["_d"] = mp["minutes"] * mp["_f"]
        rate = safe_div(prior_sum(tmp, ["season", "player_id"], "_n"),
                        prior_sum(tmp, ["season", "player_id"], "_d"))
        pred = rate * mp["ref_mean_minutes"].to_numpy(float)
        m = mp["season"].isin(HEADLINE_SEASONS).to_numpy()
        y = mp.loc[m, tgt].to_numpy(float)
        p = pred[m]
        k = np.isfinite(y) & np.isfinite(p)
        fl_rows.append(dict(history_minutes_floor=floor, target=tgt, n=int(k.sum()),
                            r2_H3_rate_x_minutes=r2_plain(y[k], p[k])))
FL = pd.DataFrame(fl_rows)
FL.to_csv(os.path.join(OUT, "history_floor_curve.csv"), index=False)
print(FL.to_string(index=False))

rep["ceiling_top"] = C.sort_values("CEILING_dR2_base_residualised", ascending=False).head(20).to_dict("records")
rep["propagation"] = prop
rep["per_season"] = cons
rep["floor_curve"] = fl_rows
json.dump(jsonable(rep), open(os.path.join(OUT, "_s06.json"), "w"), indent=2)
print("\n  WROTE arithmetic_ceiling.csv, propagation_walkforward.csv, per_season_consistency.csv, "
      "history_floor_curve.csv, _s06.json")
