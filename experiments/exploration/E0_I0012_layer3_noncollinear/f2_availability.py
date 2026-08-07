"""
E0 I0012 -- FORMULATION 2: AVAILABILITY-CONDITIONED MATCHUP.

Question: when the OPPONENT'S primary defensive specialist for a given skill is absent
tonight, does a player's production shift beyond what the opponent's OVERALL pregame
defensive strength predicts -- and does that shift depend on the player's own orientation
toward the skill in question?

Target-matched specialist (defensive skill that plausibly suppresses that target):
    pts -> blk per 100 (rim protection)
    reb -> dreb per 100 (defensive glass)
    ast -> stl per 100 (passing-lane disruption)

Construction (all pregame given TONIGHT'S ROSTER, i.e. conditional on KNOWN lineups):
  spec_it   = player's prior-expanding specialist rate per 100 possessions (strict shift,
              shrunk to league, prior-season fallback)
  nominal   = max spec over the opponent's ROSTER POOL as of this date (players with >=
              MIN_PRIOR_POSS prior possessions for that team this season)
  available = max spec over the opponent's players who ACTUALLY APPEAR tonight
  DELTA     = nominal - available      >= 0.  Large DELTA = the opponent's best specialist
                                       is missing tonight.

DELTA is an availability SHOCK. def_pre was computed from games strictly before tonight,
so it embeds the specialist's PRESENCE, not his absence -- which is exactly why DELTA has a
shot at being non-collinear with overall defence. That is checked, not assumed.

The player-side interaction term is the player's own prior orientation toward the skill
(paint-points share for pts, oreb+dreb share for reb, assist rate for ast).

PARTITION: 2021-2024 only.

CAVEAT recorded in FINDINGS: this feature is only pregame-observable if tonight's inactives
are known pregame. At E0 that is the same KNOWN-LINEUP framing under which this program
previously found real intrinsic player signal. It is NOT a blind-forecast feature.
"""
import os
import json
import numpy as np
import pandas as pd

import base as B

MIN_PRIOR_POSS = 200.0   # prior possessions for a player to count as "on the roster pool"
N_PERM = 200

SPEC = {"pts": "blk", "reb": "dreb", "ast": "stl"}
ORIENT = {"pts": "points_paint", "reb": "reb", "ast": "ast"}


def prior_rate(d, col):
    """Player's prior-expanding per-100 rate of `col`, strictly before this date, within season,
    shrunk toward the expanding league rate with a prior-season own-rate anchor."""
    d = d.copy()
    d["_v"] = pd.to_numeric(d[col], errors="coerce").astype(float)
    d["_u"] = d["possessions"].astype(float) / 100.0
    d = B.prior_expanding(d, ["season", "player_id"], ["_v", "_u"], "pv_")
    la = B.prior_expanding(d[["season", "gdate", "_v", "_u"]].copy(), ["season"], ["_v", "_u"], "la_")
    lg = np.where(la["la__u"].values > 1.0, la["la__v"].values / la["la__u"].values, np.nan)
    tot = d["_v"].sum() / max(d["_u"].sum(), 1e-9)
    lg = pd.Series(lg, index=d.index).fillna(tot)
    r = (d["pv__v"] + B.SHRINK_K * lg) / (d["pv__u"] + B.SHRINK_K)
    return r.where(d["pv__u"] >= B.MIN_PRIOR_UNITS), d["pv__u"]


def run():
    B.hdr("F2 -- AVAILABILITY-CONDITIONED MATCHUP")
    mp = B.load_player()
    print("  dnp_reason non-empty rows: %d ; minutes==0 or null: %d"
          % (mp["dnp_reason"].astype(str).str.strip().replace("nan", "").ne("").sum(),
             (mp["minutes"].isna() | (mp["minutes"] <= 0)).sum()))

    # APPEARED tonight = has a row for this game with positive minutes.
    mp["appeared"] = (mp["minutes"].fillna(0) > 0).astype(int)
    print("  appeared=1 rows: %d / %d" % (mp["appeared"].sum(), len(mp)))

    played = mp[(mp["appeared"] == 1) & (mp["possessions"] > 0)].copy()
    results = {}
    rng = np.random.default_rng(B.SEED)

    for T in B.TARGETS:
        S = SPEC[T]
        B.hdr("F2 / target = %s   (opponent specialist skill = %s)" % (T, S))

        # ---- specialist rate for EVERY player-game row (defence side) ----
        spec, prior_u = prior_rate(played, S)
        pl = played.copy()
        pl["spec"] = spec.values
        pl["prior_poss"] = prior_u.values * 100.0
        pl["elig"] = pl["prior_poss"] >= MIN_PRIOR_POSS

        # ---- roster POOL as of each (team, date): who has ever played for this team this
        #      season strictly before tonight, with enough prior possessions.
        #      Built by forward-filling each player's LAST OBSERVED spec/prior_poss to the
        #      team's game dates -- all values are strictly-prior by construction.
        pl = pl.sort_values(["season", "team_id", "gdate"]).reset_index(drop=True)
        appearances = pl[["season", "team_id", "player_id", "gdate", "spec", "prior_poss", "elig"]].copy()

        team_dates = (pl[["season", "team_id", "game_id", "gdate"]].drop_duplicates()
                      .sort_values(["season", "team_id", "gdate"]).reset_index(drop=True))

        # nominal: for each (season, team, date) the max spec over players who appeared for the
        # team at some point STRICTLY BEFORE this date and were eligible at their last appearance.
        nom_rows = []
        for (s, t), g in appearances.groupby(["season", "team_id"], sort=False):
            g = g.sort_values("gdate")
            dates = team_dates[(team_dates["season"] == s) & (team_dates["team_id"] == t)]["gdate"].values
            last = {}
            gi = 0
            garr = g[["gdate", "player_id", "spec", "elig"]].to_numpy(object)
            for dt in dates:
                while gi < len(garr) and garr[gi][0] < dt:
                    pid, sp, el = garr[gi][1], garr[gi][2], garr[gi][3]
                    if el and np.isfinite(float(sp) if sp is not None else np.nan):
                        last[pid] = float(sp)
                    gi += 1
                if last:
                    best_pid = max(last, key=last.get)
                    nom_rows.append((s, t, dt, last[best_pid], best_pid, len(last)))
                else:
                    nom_rows.append((s, t, dt, np.nan, -1, 0))
        NOM = pd.DataFrame(nom_rows, columns=["season", "team_id", "gdate",
                                              "nominal", "nominal_pid", "pool_n"])

        # available: max spec among players who ACTUALLY APPEAR tonight for that team
        avail = (pl[pl["elig"]].groupby(["season", "team_id", "gdate"])["spec"]
                 .max().reset_index().rename(columns={"spec": "available"}))
        DEF = NOM.merge(avail, on=["season", "team_id", "gdate"], how="left")
        DEF["available"] = DEF["available"].fillna(DEF["nominal"])
        # nominal is an upper bound over a superset of tonight's eligible players; clip to >=0
        DEF["delta"] = (DEF["nominal"] - DEF["available"]).clip(lower=0)
        DEF["spec_out"] = (DEF["delta"] > 0.5).astype(int)
        print("  roster pool size per (team,date): med=%.0f | delta: mean=%.4f sd=%.4f "
              "frac>0=%.3f frac>0.5=%.3f max=%.2f"
              % (DEF["pool_n"].median(), DEF["delta"].mean(), DEF["delta"].std(),
                 (DEF["delta"] > 0).mean(), DEF["spec_out"].mean(), DEF["delta"].max()))

        # ---- offence side: base model + own orientation ----
        d = B.build_base(played, T)
        orient, _ = prior_rate(played, ORIENT[T])
        d["orient"] = orient.values

        d = d.merge(DEF.rename(columns={"team_id": "opp_team_id",
                                        "nominal": "opp_nominal",
                                        "available": "opp_available",
                                        "delta": "M_delta",
                                        "spec_out": "opp_spec_out",
                                        "pool_n": "opp_pool_n"}),
                    on=["season", "opp_team_id", "gdate"], how="left")

        w = B.prep_frame(d, extra_required=["M_delta", "orient"])
        print("  analysis rows: %d | rows where opp specialist degraded (delta>0.5): %d (%.3f)"
              % (len(w), int(w["opp_spec_out"].sum()), w["opp_spec_out"].mean()))

        # ---- (a) collinearity with OVERALL opponent defence ----
        r_all, per = B.collinearity(w, "M_delta")
        r_nom, _ = B.collinearity(w, "opp_nominal")
        print("  (a) COLLINEARITY corr(M_delta, def_pre) within season = %+.4f | per season %s"
              % (r_all, {k: round(v, 3) for k, v in per.items()}))
        print("      (reference) corr(opp_nominal_specialist, def_pre) = %+.4f  "
              "<- the LEVEL is the costume-prone part; the DELTA is the shock" % r_nom)

        # ---- (b) between/within variance decomposition ----
        bo, wo, ngo, mgo = B.var_decomp(w, "M_delta", "opp_team_id")
        bs, ws, ngs, _ = B.var_decomp(w, "M_delta", "game_id")
        print("  (b) VAR DECOMP of M_delta: between-OPPONENT %.3f / within %.3f (%d opponents)"
              % (bo, wo, ngo))
        print("      VAR DECOMP of M_delta: between-GAME %.3f / within %.3f  "
              "(near 1.0 is EXPECTED: delta is a team-night quantity)" % (bs, ws))

        # ---- (c) split-half reliability of the specialist-rate instrument ----
        rr = played[["player_id", S, "possessions", "gdate"]].copy()
        rr["_v"] = pd.to_numeric(rr[S], errors="coerce")
        rr["_u"] = rr["possessions"] / 100.0
        rr["_rate"] = rr["_v"] / rr["_u"]
        cnt = rr.groupby("player_id").size()
        rr = rr[rr["player_id"].isin(cnt[cnt >= 20].index)]
        rh, sb, nu = B.split_half_reliability(rr, ["player_id"], "_rate", weight_col="_u")
        print("  (c) SPLIT-HALF RELIABILITY of the %s/100 specialist instrument "
              "(players with >=20 games): r_half=%.4f  spearman-brown=%.4f  n=%d"
              % (S, rh, sb, nu))

        # ---- (d) effect ----
        print("  (d) EFFECT -- M_delta residualized on overall defence, main + own-rate interaction:")
        eff = B.screen_increment(w, "M_delta", "F2_delta")

        # explicit orientation interaction: does the shock matter MORE for players oriented
        # toward the skill the missing specialist suppresses?
        wo_ = w.dropna(subset=["orient"]).copy()
        wo_["R"] = B.zwithin(wo_, "orient")
        wo_["Md"] = B.zwithin(wo_, "M_delta")
        wo_["Mres"] = B.resid_on(wo_["Md"].values, [wo_["D"].values, wo_["OD"].values])
        wo_["Mres"] /= wo_["Mres"].std()
        print("  (d2) EFFECT -- orientation interaction (own %s-share x opponent shock):" % ORIENT[T])
        print("  %-8s %8s %11s %11s %11s" % ("scope", "n", "dR2_M", "dR2_RxM", "beta_RxM"))
        orows = []
        for seas in B.PARTITION + ["POOLED"]:
            g = wo_ if seas == "POOLED" else wo_[wo_["season"] == seas]
            if len(g) < 200:
                continue
            y = g["y"].values
            Bs = B.base_terms(g) + [g["R"].values]
            rb = B.r2(y, Bs)
            rm = B.r2(y, Bs + [g["Mres"].values])
            ri = B.r2(y, Bs + [g["Mres"].values, (g["R"] * g["Mres"]).values])
            bb = B.fit_beta(y, Bs + [g["Mres"].values, (g["R"] * g["Mres"]).values])[-1]
            print("  %-8s %8d %11.6f %11.6f %11.4f" % (seas, len(g), rm - rb, ri - rm, bb))
            orows.append({"scope": str(seas), "n": int(len(g)), "dR2_M": rm - rb,
                          "dR2_RxM": ri - rm, "beta_RxM": float(bb)})

        # simple contrast, for interpretability
        hi = w[w["opp_spec_out"] == 1]
        lo = w[w["opp_spec_out"] == 0]
        yr_hi = (hi["y"] - hi["own_pre"] * hi["def_pre"] / hi["lg_rate"]).mean()
        yr_lo = (lo["y"] - lo["own_pre"] * lo["def_pre"] / lo["lg_rate"]).mean()
        print("  (d3) CONTRAST mean pregame surprise per-100: specialist-degraded %+.4f (n=%d) "
              "vs intact %+.4f (n=%d) -> gap %+.4f" % (yr_hi, len(hi), yr_lo, len(lo), yr_hi - yr_lo))

        # ---- (e) PLACEBO: permute the ASSIGNMENT of computed delta values to rows ----
        vals = []
        for it in range(N_PERM):
            p = w.copy()
            perm = np.empty(len(p))
            for s in sorted(p["season"].unique()):
                k = (p["season"] == s).values
                v = p.loc[k, "M_delta"].values.copy()
                rng.shuffle(v)
                perm[k] = v
            p["M_perm"] = perm
            vals.append(B.screen_increment_quiet(p, "M_perm"))
        V = pd.DataFrame(vals)
        real = B.screen_increment_quiet(w, "M_delta")
        print("  (e) PLACEBO (%d perms, value-assignment permutation within season):" % N_PERM)
        print("      %-10s %11s %11s %11s %11s" % ("stat", "REAL", "plc_mean", "plc_SD", "frac>=real"))
        plc = {}
        for stat in ["dR2_M", "dR2_OxM"]:
            v = V[stat].values
            print("      %-10s %11.7f %11.7f %11.7f %11.3f"
                  % (stat, real[stat], v.mean(), v.std(), float((v >= real[stat]).mean())))
            plc[stat] = {"real": float(real[stat]), "mean": float(v.mean()), "sd": float(v.std()),
                         "frac_ge": float((v >= real[stat]).mean())}
            if v.std() == 0.0:
                print("      *** DEGENERATE PLACEBO (sd exactly 0) -- no-op signature. ***")
        V.assign(target=T).to_csv(os.path.join(B.OUT, "f2_placebo_draws_%s.csv" % T), index=False)

        results[T] = {
            "specialist": S, "orientation": ORIENT[T],
            "collinearity_vs_overall_def": r_all, "collinearity_per_season": per,
            "collinearity_nominal_level_vs_def": r_nom,
            "var_between_opponent": bo, "var_within_opponent": wo,
            "var_between_game": bs,
            "reliability_specialist_half": rh, "reliability_specialist_sb": sb,
            "n_rows": int(len(w)), "frac_rows_specialist_degraded": float(w["opp_spec_out"].mean()),
            "effect": eff["rows"], "effect_orientation": orows,
            "contrast_surprise_gap_per100": float(yr_hi - yr_lo),
            "placebo": plc,
        }
        B.safe_write(w[["game_id", "season", "game_date", "team_id", "opp_team_id", "player_id",
                        "minutes", "possessions", "y", "own_pre", "def_pre", "orient",
                        "opp_nominal", "opp_available", "M_delta", "opp_spec_out", "opp_pool_n"]],
                     "f2_features_%s.csv" % T)

    return results


if __name__ == "__main__":
    r = run()
    with open(os.path.join(B.OUT, "f2_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2, default=float)
    print("\nF2 done.")
