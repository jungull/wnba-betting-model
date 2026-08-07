"""
E0 I0012 -- ROBUSTNESS on the one candidate that cleared its own placebo floor:

    target = REB, M = opponent PACE (dpace) residualized on overall opponent defence,
    tested as an INTERACTION with the player's own pregame rebound rate (O x M).
    Pooled dR2_OxM = 0.001071, placebo mean 0.000079 sd 0.0000928, 0/200 perms >= real,
    per-season betas +0.356 / +0.335 / +0.167 / +0.064 (4/4 same sign).

Before that can be called a LEAD rather than a lucky cell in a ~48-test sweep, three things
must be checked, because each of them would explain the result away:

  R1  NORMALISATION ARTIFACT. y is reb per 100 PLAYER possessions. If master_player
      `possessions` is mis-scaled with respect to team pace (its sibling `pace` column is
      known-corrupt on this partition), then "opponent pace x own rate" could be an artifact
      of the denominator rather than a matchup effect. Re-run per 36 MINUTES, a denominator
      that does not involve possessions at all. A real effect survives; an artifact does not.

  R2  FAMILY-WISE ERROR. This sweep ran ~48 (formulation x target x statistic) tests. A
      single cell at p<0.005 is not remarkable on its own. Compute a randomization-based
      max-statistic family-wise p using the pooled placebo draws from every F3/F4 test as
      exchangeable null draws.

  R3  IS IT JUST GAME VOLUME? Add the player's OWN team's pregame pace and the opponent's
      allowed-DREB style as controls, and add O x (own team pace). If the effect is really
      "more shots go up, and the good rebounder takes his share", it should be absorbed by
      total game pace rather than being specific to the OPPONENT.

PARTITION: 2021-2024 only.
R2 convention note: all R2 in this sweep is PLAIN UNWEIGHTED OLS R2 (SSE / SST of y about
its unweighted mean). No weighted-least-squares helper is used anywhere, so the ~8%
understatement in the wls_r2 denominator convention reported by the concurrent E1 screen
does NOT apply to any number in this directory.
"""
import os
import glob
import json
import numpy as np
import pandas as pd

import base as B
import f34_style_rest as F34

N_PERM = 400
T = "reb"


def run():
    B.hdr("ROBUSTNESS -- reb x opponent pace x own rate")
    mp = B.load_player()
    mt = B.load_team()
    played = mp[(mp["minutes"].fillna(0) > 0) & (mp["possessions"] > 0)].copy()

    # ---- sanity on the possessions denominator (its sibling `pace` is corrupt) ----
    tp = B.team_possessions(mt)
    chk = played.groupby(["game_id", "team_id"])["possessions"].sum().reset_index()
    chk = chk.merge(tp[["game_id", "team_id", "team_poss"]], on=["game_id", "team_id"])
    chk["ratio"] = chk["possessions"] / (5 * chk["team_poss"])
    print("  DENOMINATOR SANITY: sum(player possessions) vs 5 x team possessions")
    print("    ratio med=%.3f  p05=%.3f  p95=%.3f  corr(player-sum, team)=%.4f"
          % (chk["ratio"].median(), chk["ratio"].quantile(.05), chk["ratio"].quantile(.95),
             chk[["possessions", "team_poss"]].corr().iloc[0, 1]))
    r_pm = played[["possessions", "minutes"]].corr().iloc[0, 1]
    print("    corr(player possessions, player minutes) = %.4f  "
          "(near 1 = possessions is essentially a minutes rescale)" % r_pm)

    STY, tteam = F34.build_team_style(mt)
    opp_sty = STY.rename(columns={"team_id": "opp_team_id"}).drop(columns=["game_id"])
    own_sty = STY.rename(columns={c: "own_" + c for c in F34.STYLE_DIMS + ["dstrength"]}).drop(columns=["game_id"])
    PS = F34.player_style(played)

    rng = np.random.default_rng(B.SEED + 1)
    out = {}

    # ================================================================= R1
    B.hdr("R1 -- NORMALISATION: per-100-possessions vs per-36-minutes")
    for unit_name in ["per100poss", "per36min"]:
        pl = played.copy()
        if unit_name == "per36min":
            # swap the denominator: build_base divides by possessions/100, so feed it a
            # `possessions` column that encodes minutes/36 on the same scale.
            pl["possessions"] = pl["minutes"] * 100.0 / 36.0
        d = B.build_base(pl, T)
        d = d.merge(opp_sty, on=["season", "opp_team_id", "gdate"], how="left")
        d = d.merge(own_sty, on=["season", "team_id", "gdate"], how="left")
        d = d.merge(PS, on=["season", "game_id", "player_id"], how="left")
        w = B.prep_frame(d, extra_required=["dpace"])
        print("\n  [%s] n=%d   corr(dpace, def_pre)=%+.4f"
              % (unit_name, len(w), B.collinearity(w, "dpace")[0]))
        eff = B.screen_increment(w, "dpace", "R1_" + unit_name)
        plc, V = F34.placebo(w, "dpace", rng, n=N_PERM)
        V.assign(unit=unit_name).to_csv(os.path.join(B.OUT, "r1_placebo_%s.csv" % unit_name), index=False)
        out["R1_" + unit_name] = {"n": int(len(w)), "effect": eff["rows"], "placebo": plc,
                                  "collinearity": float(B.collinearity(w, "dpace")[0])}
        if unit_name == "per100poss":
            keep_w = w

    # ================================================================= R3
    B.hdr("R3 -- IS IT THE OPPONENT, OR JUST GAME VOLUME?")
    w = keep_w.dropna(subset=["own_dpace", "dorebA"]).copy()
    w["Mz"] = B.zwithin(w, "dpace")
    w["Mres"] = B.resid_on(w["Mz"].values, [w["D"].values, w["OD"].values])
    w["Mres"] /= w["Mres"].std()
    w["P"] = B.zwithin(w, "own_dpace")          # the player's OWN team's pregame pace
    w["G"] = B.zwithin(w, "dorebA")             # opponent's allowed-OREB style
    w["gamepace"] = w["Mz"] + w["P"]
    w["GP"] = B.zwithin(w, "gamepace")
    print("  corr(opponent pace, own team pace) = %+.4f" % w[["Mz", "P"]].corr().iloc[0, 1])
    ladders = [
        ("base only",                       lambda g: B.base_terms(g)),
        ("+ opp pace main",                 lambda g: B.base_terms(g) + [g["Mres"].values]),
        ("+ own-team pace main & O x own",  lambda g: B.base_terms(g) + [g["Mres"].values, g["P"].values,
                                                                        (g["O"] * g["P"]).values]),
        ("+ opp OREB-allowed & O x that",   lambda g: B.base_terms(g) + [g["Mres"].values, g["P"].values,
                                                                        (g["O"] * g["P"]).values,
                                                                        g["G"].values, (g["O"] * g["G"]).values]),
        ("+ TOTAL game pace & O x total",   lambda g: B.base_terms(g) + [g["Mres"].values, g["P"].values,
                                                                        (g["O"] * g["P"]).values,
                                                                        g["G"].values, (g["O"] * g["G"]).values,
                                                                        g["GP"].values, (g["O"] * g["GP"]).values]),
    ]
    print("  %-34s %10s %14s %11s" % ("control set", "R2", "dR2_OxOppPace", "beta"))
    lad = []
    for name, f in ladders:
        Xb = f(w)
        y = w["y"].values
        rb = B.r2(y, Xb)
        rf = B.r2(y, Xb + [(w["O"] * w["Mres"]).values])
        bb = float(B.fit_beta(y, Xb + [(w["O"] * w["Mres"]).values])[-1])
        print("  %-34s %10.5f %14.6f %11.4f" % (name, rb, rf - rb, bb))
        lad.append({"controls": name, "R2_base": rb, "dR2_OxOppPace": rf - rb, "beta": bb})
    out["R3_control_ladder"] = lad

    # per-season sign consistency of the surviving term under the fullest control set
    print("\n  per-season, under the FULLEST control set:")
    print("  %-8s %8s %14s %11s" % ("season", "n", "dR2_OxOppPace", "beta"))
    sgn = []
    for s in B.PARTITION:
        g = w[w["season"] == s]
        if len(g) < 200:
            continue
        Xb = ladders[-1][1](g)
        y = g["y"].values
        rb = B.r2(y, Xb)
        rf = B.r2(y, Xb + [(g["O"] * g["Mres"]).values])
        bb = float(B.fit_beta(y, Xb + [(g["O"] * g["Mres"]).values])[-1])
        print("  %-8d %8d %14.6f %11.4f" % (s, len(g), rf - rb, bb))
        sgn.append({"season": int(s), "n": int(len(g)), "dR2": rf - rb, "beta": bb})
    out["R3_per_season_full_controls"] = sgn

    # ================================================================= R2
    B.hdr("R2 -- FAMILY-WISE ERROR ACROSS THE WHOLE SWEEP")
    files = sorted(glob.glob(os.path.join(B.OUT, "f*_placebo_draws_*.csv")))
    cols = []
    for f in files:
        v = pd.read_csv(f)
        for stat in ["dR2_M", "dR2_OxM"]:
            if stat in v.columns:
                cols.append(v[stat].values[:200])
    Vall = np.column_stack(cols)
    print("  pooled null draws from %d shipped placebo columns x %d perms" % (Vall.shape[1], Vall.shape[0]))
    # standardise each null column, then take the per-permutation MAX -> max-T null
    mu, sd = Vall.mean(0), Vall.std(0)
    Z = (Vall - mu) / np.where(sd > 0, sd, 1)
    maxT = Z.max(1)
    real_z = (0.0010713 - 0.0000790) / 0.0000928
    fw = float((maxT >= real_z).mean())
    print("  candidate standardised statistic z = %.2f (real %.6f, null mean %.6f, null sd %.6f)"
          % (real_z, 0.0010713, 0.0000790, 0.0000928))
    print("  max-T null: mean=%.2f p95=%.2f max=%.2f" % (maxT.mean(), np.quantile(maxT, .95), maxT.max()))
    print("  FAMILY-WISE p (fraction of permutations whose BEST-of-%d exceeds the candidate) = %.4f"
          % (Vall.shape[1], fw))
    # how many tests in the sweep beat their own floor, vs expectation
    print("  (context) with %d tests at a nominal 0.05 floor you expect %.1f false positives"
          % (Vall.shape[1], 0.05 * Vall.shape[1]))
    out["R2_family_wise"] = {"n_tests": int(Vall.shape[1]), "candidate_z": float(real_z),
                             "family_wise_p": fw,
                             "maxT_p95": float(np.quantile(maxT, .95)),
                             "expected_false_positives_at_05": 0.05 * Vall.shape[1]}
    return out


if __name__ == "__main__":
    r = run()
    with open(os.path.join(B.OUT, "robustness_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2, default=float)
    print("\nRobustness done.")
