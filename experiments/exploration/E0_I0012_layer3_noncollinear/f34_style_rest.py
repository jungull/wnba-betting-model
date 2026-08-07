"""
E0 I0012 -- FORMULATION 3 (opponent STYLE orthogonalized against strength)
            FORMULATION 4 (REST / TRAVEL x opponent, at player level)

F3. Opponent DEFENSIVE STYLE dimensions, built pregame from master_team, each one
    RESIDUALIZED against the opponent's overall pregame defensive strength before it is
    allowed near the outcome. Style is what an opponent makes you do; strength is how well
    they stop it. I0010 died because the candidate was strength in a costume, so here the
    strength component is removed by construction and then re-checked empirically.

    style dimensions (all "what this team's opponents did against them", prior-expanding):
      d3par   share of opponent FGA that were 3PA        (do they run you off the line?)
      dtovf   opponent turnovers forced per 100 poss     (do they gamble?)
      dorebA  opponent OREB per 100 poss allowed         (do they let you crash?)
      dpace   possessions per 48 minutes                 (tempo)
    matched player-side style (prior-expanding per player):
      d3par  <-> own 3PA share of FGA
      dtovf  <-> own TOV per 100
      dorebA <-> own OREB per 100
      dpace  <-> own usage proxy (FGA+0.44FTA+TOV per 100)

F4. Rest and travel are NOT built anywhere in this repo (confirmed: no rest/b2b/travel
    column exists in either master). They are constructed here from the schedule:
      rest      days since the team's previous regular-season game (capped at 7)
      b2b       rest <= 1
      rest_dif  own team rest - opponent rest
      travel    great-circle km from the team's previous VENUE to tonight's VENUE, using
                data/reference/team_cities.csv (lat/lon) and is_home to pick the venue
      tz_shift  timezone-offset change between previous and current venue
    Tested as a player-level matchup: main effect over the base model, and interacted with
    the player's own rate (does fatigue bite the high-usage player harder?) and with the
    opponent's overall defence (does a tired team get punished more by a good defence?).

PARTITION: 2021-2024 only. Both masters are asof_granularity="row" (checked programmatically).
"""
import os
import json
import numpy as np
import pandas as pd

import base as B

N_PERM = 200
EARTH_KM = 6371.0

STYLE_DIMS = ["d3par", "dtovf", "dorebA", "dpace"]
MATCH = {"d3par": "own_3par", "dtovf": "own_tovr", "dorebA": "own_orebr", "dpace": "own_usg"}


def haversine(lat1, lon1, lat2, lon2):
    p = np.pi / 180.0
    a = (np.sin((lat2 - lat1) * p / 2) ** 2
         + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * EARTH_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ------------------------------------------------------------------ team-side builds
def build_team_style(mt):
    tp = B.team_possessions(mt)
    t = mt.merge(tp[["game_id", "team_id", "team_poss"]], on=["game_id", "team_id"], how="left")
    t["u"] = t["team_poss"] / 100.0
    # numerators describing what this team's OPPONENTS did against them
    t["n_o3pa"] = t["opp_fg3a"].astype(float)
    t["n_ofga"] = t["opp_fga"].astype(float)
    t["n_otov"] = t["opp_tov"].astype(float)
    t["n_oreb"] = t["opp_oreb"].astype(float)
    t["n_opts"] = t["opp_pts"].astype(float)
    t["n_min"] = pd.to_numeric(t["minutes"], errors="coerce").astype(float)

    cols = ["n_o3pa", "n_ofga", "n_otov", "n_oreb", "n_opts", "n_min", "u"]
    p = B.prior_expanding(t, ["season", "team_id"], cols, "pr_")
    ok = p["pr_u"] >= 3.0            # >=300 prior possessions
    out = t[["season", "team_id", "game_id", "gdate"]].copy()
    out["d3par"] = np.where(p["pr_n_ofga"] > 0, p["pr_n_o3pa"] / p["pr_n_ofga"], np.nan)
    out["dtovf"] = np.where(p["pr_u"] > 0, p["pr_n_otov"] / p["pr_u"], np.nan)
    out["dorebA"] = np.where(p["pr_u"] > 0, p["pr_n_oreb"] / p["pr_u"], np.nan)
    out["dpace"] = np.where(p["pr_n_min"] > 0, p["pr_u"] * 100.0 / (p["pr_n_min"] / 5.0) * 48.0, np.nan)
    out["dstrength"] = np.where(p["pr_u"] > 0, p["pr_n_opts"] / p["pr_u"], np.nan)  # pts allowed /100
    out.loc[~ok, STYLE_DIMS + ["dstrength"]] = np.nan
    return out, t


def build_rest_travel(mt):
    cities = pd.read_csv(os.path.join(B.ROOT, r"data\reference\team_cities.csv"))
    cities["last_season"] = cities["last_season"].fillna(9999)
    tz_off = {"America/New_York": -5, "America/Chicago": -6, "America/Denver": -7,
              "America/Phoenix": -7, "America/Los_Angeles": -8, "America/Detroit": -5,
              "America/Indiana/Indianapolis": -5}
    cities["tzo"] = cities["timezone"].map(tz_off)
    print("  team_cities: %d rows, %d team_ids, tz mapped for %d"
          % (len(cities), cities["team_id"].nunique(), cities["tzo"].notna().sum()))

    def venue(row_team, season):
        pass  # replaced by vectorised merge below

    t = mt[["season", "game_id", "gdate", "team_id", "opp_team_id", "is_home"]].copy()
    c = cities[["team_id", "first_season", "last_season", "lat", "lon", "tzo"]]
    m = t.merge(c, on="team_id", how="left")
    m = m[(m["season"] >= m["first_season"]) & (m["season"] <= m["last_season"])]
    m = m.drop_duplicates(["season", "game_id", "team_id"])
    home = m.rename(columns={"lat": "h_lat", "lon": "h_lon", "tzo": "h_tzo"})[
        ["season", "game_id", "team_id", "h_lat", "h_lon", "h_tzo"]]
    o = t.merge(home.rename(columns={"team_id": "opp_team_id", "h_lat": "o_lat",
                                     "h_lon": "o_lon", "h_tzo": "o_tzo"}),
                on=["season", "game_id", "opp_team_id"], how="left")
    o = o.merge(home, on=["season", "game_id", "team_id"], how="left")
    o["v_lat"] = np.where(o["is_home"] == 1, o["h_lat"], o["o_lat"])
    o["v_lon"] = np.where(o["is_home"] == 1, o["h_lon"], o["o_lon"])
    o["v_tzo"] = np.where(o["is_home"] == 1, o["h_tzo"], o["o_tzo"])
    print("  venue coords resolved on %d / %d team-games (%.3f)"
          % (o["v_lat"].notna().sum(), len(o), o["v_lat"].notna().mean()))

    o = o.sort_values(["season", "team_id", "gdate"]).reset_index(drop=True)
    g = o.groupby(["season", "team_id"], sort=False)
    o["prev_date"] = g["gdate"].shift(1)
    o["prev_lat"] = g["v_lat"].shift(1)
    o["prev_lon"] = g["v_lon"].shift(1)
    o["prev_tzo"] = g["v_tzo"].shift(1)
    o["rest"] = (o["gdate"] - o["prev_date"]).dt.days.clip(upper=7)
    o["b2b"] = (o["rest"] <= 1).astype(float)
    o["travel_km"] = haversine(o["prev_lat"], o["prev_lon"], o["v_lat"], o["v_lon"])
    o["tz_shift"] = (o["v_tzo"] - o["prev_tzo"]).astype(float)
    print("  rest: med=%.1f | b2b share=%.3f | travel_km: med=%.0f p90=%.0f max=%.0f "
          "| tz_shift nonzero share=%.3f"
          % (o["rest"].median(), o["b2b"].mean(), o["travel_km"].median(),
             o["travel_km"].quantile(.9), o["travel_km"].max(),
             (o["tz_shift"].fillna(0) != 0).mean()))
    return o[["season", "game_id", "team_id", "rest", "b2b", "travel_km", "tz_shift"]]


def player_style(played):
    d = played.copy()
    d["u"] = d["possessions"] / 100.0
    for c, num in [("fga", "fga"), ("fg3a", "fg3a"), ("tov", "tov"), ("oreb", "oreb"),
                   ("fta", "fta")]:
        d["n_" + c] = pd.to_numeric(d[num], errors="coerce").astype(float)
    cols = ["n_fga", "n_fg3a", "n_tov", "n_oreb", "n_fta", "u"]
    p = B.prior_expanding(d, ["season", "player_id"], cols, "pp_")
    ok = p["pp_u"] >= B.MIN_PRIOR_UNITS
    out = d[["season", "game_id", "player_id"]].copy()
    out["own_3par"] = np.where(p["pp_n_fga"] > 0, p["pp_n_fg3a"] / p["pp_n_fga"], np.nan)
    out["own_tovr"] = np.where(p["pp_u"] > 0, p["pp_n_tov"] / p["pp_u"], np.nan)
    out["own_orebr"] = np.where(p["pp_u"] > 0, p["pp_n_oreb"] / p["pp_u"], np.nan)
    out["own_usg"] = np.where(p["pp_u"] > 0,
                              (p["pp_n_fga"] + 0.44 * p["pp_n_fta"] + p["pp_n_tov"]) / p["pp_u"], np.nan)
    out.loc[~ok.values, ["own_3par", "own_tovr", "own_orebr", "own_usg"]] = np.nan
    return out


# ------------------------------------------------------------------ generic screen
def placebo(w, mcol, rng, n=N_PERM, center_keys=("season",)):
    # Permute the ASSIGNMENT of already-computed values to rows, within season. This is the
    # correct construction: the value M is computed ONCE from true keys and then reshuffled
    # across rows. Permuting a grouping key and recomputing would be a no-op (sd exactly 0).
    p = w[list(set(list(center_keys) + ["season", "O", "D", "OD", "y", mcol]))].copy()
    masks = [(p["season"] == s).values for s in sorted(p["season"].unique())]
    src = p[mcol].values
    vals = []
    for _ in range(n):
        perm = np.empty(len(p))
        for k in masks:
            v = src[k].copy()
            rng.shuffle(v)
            perm[k] = v
        p["_perm"] = perm
        vals.append(B.screen_increment_quiet(p, "_perm", center_keys=center_keys))
    V = pd.DataFrame(vals)
    real = B.screen_increment_quiet(w, mcol, center_keys=center_keys)
    out = {}
    print("      %-10s %11s %11s %11s %11s" % ("stat", "REAL", "plc_mean", "plc_SD", "frac>=real"))
    for stat in ["dR2_M", "dR2_OxM"]:
        v = V[stat].values
        print("      %-10s %11.7f %11.7f %11.7f %11.3f"
              % (stat, real[stat], v.mean(), v.std(), float((v >= real[stat]).mean())))
        out[stat] = {"real": float(real[stat]), "mean": float(v.mean()), "sd": float(v.std()),
                     "frac_ge": float((v >= real[stat]).mean())}
        if v.std() == 0.0:
            print("      *** DEGENERATE PLACEBO (sd exactly 0) -- no-op signature. ***")
    return out, V


def matched_interaction(w, mcol, rcol):
    """Incremental R2 of (opponent style residual) x (player's own matched style)."""
    g0 = w.dropna(subset=[rcol]).copy()
    g0["R"] = B.zwithin(g0, rcol)
    g0["Mz"] = B.zwithin(g0, mcol)
    g0["Mres"] = B.resid_on(g0["Mz"].values, [g0["D"].values, g0["OD"].values])
    sd = g0["Mres"].std()
    if sd > 0:
        g0["Mres"] /= sd
    rows = []
    print("  %-8s %8s %11s %11s %11s" % ("scope", "n", "dR2_M", "dR2_RxM", "beta_RxM"))
    for seas in B.PARTITION + ["POOLED"]:
        g = g0 if seas == "POOLED" else g0[g0["season"] == seas]
        if len(g) < 200:
            continue
        y = g["y"].values
        Bs = B.base_terms(g) + [g["R"].values]
        rb = B.r2(y, Bs)
        rm = B.r2(y, Bs + [g["Mres"].values])
        ri = B.r2(y, Bs + [g["Mres"].values, (g["R"] * g["Mres"]).values])
        bb = float(B.fit_beta(y, Bs + [g["Mres"].values, (g["R"] * g["Mres"]).values])[-1])
        print("  %-8s %8d %11.6f %11.6f %11.4f" % (seas, len(g), rm - rb, ri - rm, bb))
        rows.append({"scope": str(seas), "n": int(len(g)), "dR2_M": rm - rb,
                     "dR2_RxM": ri - rm, "beta_RxM": bb})
    return rows


def run():
    B.hdr("F3 / F4 -- STYLE (orthogonalized) and REST/TRAVEL")
    mp = B.load_player()
    mt = B.load_team()
    played = mp[(mp["minutes"].fillna(0) > 0) & (mp["possessions"] > 0)].copy()

    STY, tteam = build_team_style(mt)
    print("  style coverage (non-null d3par): %.3f of team-games" % STY["d3par"].notna().mean())
    RT = build_rest_travel(mt)
    PS = player_style(played)

    # opponent-side style: attach the OPPONENT's style row for each player-game
    opp_sty = STY.rename(columns={"team_id": "opp_team_id"}).drop(columns=["game_id"])
    # rest for own team and for opponent
    own_rt = RT.rename(columns={"rest": "own_rest", "b2b": "own_b2b",
                                "travel_km": "own_travel", "tz_shift": "own_tz"})
    opp_rt = RT.rename(columns={"team_id": "opp_team_id", "rest": "opp_rest", "b2b": "opp_b2b",
                                "travel_km": "opp_travel", "tz_shift": "opp_tz"})

    rng = np.random.default_rng(B.SEED)
    results = {"F3": {}, "F4": {}}

    for T in B.TARGETS:
        B.hdr("target = %s" % T)
        d = B.build_base(played, T)
        d = d.merge(opp_sty, on=["season", "opp_team_id", "gdate"], how="left")
        d = d.merge(PS, on=["season", "game_id", "player_id"], how="left")
        d = d.merge(own_rt, on=["season", "game_id", "team_id"], how="left")
        d = d.merge(opp_rt, on=["season", "game_id", "opp_team_id"], how="left")
        d["rest_dif"] = d["own_rest"] - d["opp_rest"]

        # =================================================== F3
        print("\n--- F3 STYLE ---")
        for dim in STYLE_DIMS:
            w = B.prep_frame(d, extra_required=[dim])
            if len(w) < 500:
                print("  %s: too few rows (%d) -- skipped" % (dim, len(w)))
                continue
            r_all, per = B.collinearity(w, dim)
            r_str, _ = B.collinearity(w, dim, dcol="dstrength") if w["dstrength"].notna().any() else (np.nan, {})
            bo, wo, ngo, _ = B.var_decomp(w, dim, "opp_team_id")
            bg, wg, _, _ = B.var_decomp(w, dim, "game_id")
            # reliability of the team style measure: units = (season, team), odd/even games
            raw = tteam.copy()
            raw["_u"] = raw["u"]
            if dim == "d3par":
                raw["_val"] = raw["n_o3pa"] / raw["n_ofga"].replace(0, np.nan); wcol = "n_ofga"
            elif dim == "dtovf":
                raw["_val"] = raw["n_otov"] / raw["_u"]; wcol = "_u"
            elif dim == "dorebA":
                raw["_val"] = raw["n_oreb"] / raw["_u"]; wcol = "_u"
            else:
                raw["_val"] = raw["_u"] * 100.0 / (raw["n_min"] / 5.0) * 48.0; wcol = "_u"
            rh, sb, nu = B.split_half_reliability(raw, ["season", "team_id"], "_val", weight_col=wcol)

            print("\n  [%s]  n=%d" % (dim, len(w)))
            print("  (a) COLLINEARITY corr(%s, def_pre) within season = %+.4f | per season %s"
                  % (dim, r_all, {k: round(v, 3) for k, v in per.items()}))
            print("      corr(%s, opponent pts-allowed-per-100) = %+.4f" % (dim, r_str))
            print("  (b) VAR DECOMP: between-OPPONENT %.3f / within %.3f (%d opp) | between-GAME %.3f"
                  % (bo, wo, ngo, bg))
            print("  (c) SPLIT-HALF RELIABILITY (units=(season,team), odd/even games): "
                  "r_half=%.4f sb=%.4f n=%d" % (rh, sb, nu))
            print("  (d) EFFECT -- %s residualized on overall defence:" % dim)
            eff = B.screen_increment(w, dim, "F3_" + dim)
            print("  (d2) MATCHED interaction with player's own %s:" % MATCH[dim])
            mrows = matched_interaction(w, dim, MATCH[dim])
            print("  (e) PLACEBO (%d perms, value-assignment permutation within season):" % N_PERM)
            plc, V = placebo(w, dim, rng)
            V.assign(target=T, dim=dim).to_csv(
                os.path.join(B.OUT, "f3_placebo_draws_%s_%s.csv" % (T, dim)), index=False)
            results["F3"].setdefault(T, {})[dim] = {
                "collinearity_vs_overall_def": r_all, "collinearity_per_season": per,
                "collinearity_vs_pts_allowed_per100": r_str,
                "var_between_opponent": bo, "var_within_opponent": wo, "var_between_game": bg,
                "reliability_half": rh, "reliability_sb": sb, "n_units": nu,
                "n_rows": int(len(w)), "effect": eff["rows"],
                "effect_matched_interaction": mrows, "placebo": plc}

        # =================================================== F4
        print("\n--- F4 REST / TRAVEL ---")
        for var, ck in [("rest_dif", ("season",)), ("own_rest", ("season",)),
                        ("own_travel", ("season",)), ("own_b2b", ("season",))]:
            w = B.prep_frame(d, extra_required=[var])
            if len(w) < 500 or w[var].std() == 0:
                print("  %s: unusable (n=%d)" % (var, len(w)))
                continue
            r_all, per = B.collinearity(w, var)
            bo, wo, ngo, _ = B.var_decomp(w, var, "team_id")
            bg, _, _, _ = B.var_decomp(w, var, "game_id")
            # reliability: rest/travel are SCHEDULE FACTS, measured without error.
            # Split-half reliability is not the right instrument-quality question for them;
            # what matters is whether they vary within team. Reported as the within share.
            print("\n  [%s]  n=%d  mean=%.3f sd=%.3f" % (var, len(w), w[var].mean(), w[var].std()))
            print("  (a) COLLINEARITY corr(%s, def_pre) within season = %+.4f | per season %s"
                  % (var, r_all, {k: round(v, 3) for k, v in per.items()}))
            print("  (b) VAR DECOMP: between-TEAM %.3f / within %.3f (%d teams) | between-GAME %.3f"
                  % (bo, wo, ngo, bg))
            print("  (c) RELIABILITY: n/a -- schedule fact, observed without measurement error "
                  "(within-team share of variance = %.3f is the usable-variation number)" % wo)
            print("  (d) EFFECT -- %s residualized on overall defence:" % var)
            eff = B.screen_increment(w, var, "F4_" + var)
            print("  (e) PLACEBO (%d perms):" % N_PERM)
            plc, V = placebo(w, var, rng)
            V.assign(target=T, var=var).to_csv(
                os.path.join(B.OUT, "f4_placebo_draws_%s_%s.csv" % (T, var)), index=False)
            results["F4"].setdefault(T, {})[var] = {
                "collinearity_vs_overall_def": r_all, "collinearity_per_season": per,
                "var_between_team": bo, "var_within_team": wo, "var_between_game": bg,
                "reliability": "n/a - schedule fact, no measurement error",
                "n_rows": int(len(w)), "effect": eff["rows"], "placebo": plc}

        keep = ["game_id", "season", "game_date", "team_id", "opp_team_id", "player_id",
                "minutes", "possessions", "y", "own_pre", "def_pre", "dstrength"] + \
               STYLE_DIMS + list(MATCH.values()) + \
               ["own_rest", "opp_rest", "rest_dif", "own_b2b", "own_travel", "own_tz"]
        B.safe_write(d[d["is_analysis"]][[c for c in keep if c in d.columns]],
                     "f34_features_%s.csv" % T)

    return results


if __name__ == "__main__":
    r = run()
    with open(os.path.join(B.OUT, "f34_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2, default=float)
    print("\nF3/F4 done.")
