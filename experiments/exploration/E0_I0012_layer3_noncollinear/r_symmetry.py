"""
E0 I0012 -- R4: THE DECISIVE TEST FOR THE ONE SURVIVOR.

R3's last control rung was RANK-DEFICIENT by construction: I formed total game pace as the
exact sum (opp pace + own-team pace), so O x total is an exact linear combination of
O x opp and O x own. The resulting dR2 collapse and exploding beta are a linear-algebra
artifact, NOT evidence of absorption. That rung is void; this script replaces it.

The real question separating LAYER 3 from LAYER 1/2:

    Does the interaction load on the OPPONENT's pace specifically (a matchup asymmetry,
    genuinely layer 3), or equally on BOTH teams' pace (in which case it is a game-VOLUME
    effect -- the player's rebound rate scales with how many shots go up, which is a
    possession/tempo channel that belongs to layer 1/2 and is not a matchup at all)?

Test: fit y ~ base + O*oppPace + O*ownPace, both standardised, and compare the two
coefficients directly with a permutation test on their DIFFERENCE.
  * beta_opp >> beta_own  -> asymmetric -> a real opponent matchup interaction (LAYER 3 lead)
  * beta_opp ~= beta_own  -> symmetric  -> game tempo volume, MISFILED as layer 3 (kill as
                                           a layer-3 finding; it is a layer-1/2 restatement)

PARTITION: 2021-2024 only. R2 convention: plain unweighted OLS.
"""
import os
import json
import numpy as np
import pandas as pd

import base as B
import f34_style_rest as F34

T = "reb"
N_PERM = 2000


def run():
    B.hdr("R4 -- OPPONENT-SPECIFIC OR SYMMETRIC GAME TEMPO?")
    mp = B.load_player()
    mt = B.load_team()
    played = mp[(mp["minutes"].fillna(0) > 0) & (mp["possessions"] > 0)].copy()

    STY, _ = F34.build_team_style(mt)
    opp_sty = STY.rename(columns={"team_id": "opp_team_id"})[["season", "opp_team_id", "gdate", "dpace", "dstrength"]]
    own_sty = STY.rename(columns={"dpace": "own_dpace"})[["season", "team_id", "gdate", "own_dpace"]]

    d = B.build_base(played, T)
    d = d.merge(opp_sty, on=["season", "opp_team_id", "gdate"], how="left")
    d = d.merge(own_sty, on=["season", "team_id", "gdate"], how="left")
    w = B.prep_frame(d, extra_required=["dpace", "own_dpace"])
    print("  n=%d   corr(opp pace, own-team pace) = %+.4f" % (len(w), w[["dpace", "own_dpace"]].corr().iloc[0, 1]))

    # both paces are the SAME measure applied to the two sides, standardised identically
    # within season, and each residualized on overall opponent defence so the comparison is
    # like-for-like with the headline test.
    w["Aopp"] = B.zwithin(w, "dpace")
    w["Aown"] = B.zwithin(w, "own_dpace")
    for c in ["Aopp", "Aown"]:
        r = B.resid_on(w[c].values, [w["D"].values, w["OD"].values])
        w[c] = r / r.std()
    w["Iopp"] = w["O"] * w["Aopp"]
    w["Iown"] = w["O"] * w["Aown"]

    y = w["y"].values
    X = B.base_terms(w) + [w["Aopp"].values, w["Aown"].values, w["Iopp"].values, w["Iown"].values]
    b = B.fit_beta(y, X)
    b_opp, b_own = float(b[-2]), float(b[-1])
    print("\n  POOLED  beta(O x OPPONENT pace) = %+.4f" % b_opp)
    print("          beta(O x OWN-TEAM pace)  = %+.4f" % b_own)
    print("          difference               = %+.4f" % (b_opp - b_own))

    print("\n  %-8s %8s %14s %14s %12s" % ("season", "n", "beta_O x OPP", "beta_O x OWN", "difference"))
    rows = []
    for s in B.PARTITION:
        g = w[w["season"] == s]
        if len(g) < 200:
            continue
        bb = B.fit_beta(g["y"].values, B.base_terms(g) + [g["Aopp"].values, g["Aown"].values,
                                                          g["Iopp"].values, g["Iown"].values])
        print("  %-8d %8d %14.4f %14.4f %12.4f" % (s, len(g), bb[-2], bb[-1], bb[-2] - bb[-1]))
        rows.append({"season": int(s), "n": int(len(g)), "beta_opp": float(bb[-2]),
                     "beta_own": float(bb[-1]), "diff": float(bb[-2] - bb[-1])})

    # incremental R2 of each interaction over a model containing the other
    Xb_opp = B.base_terms(w) + [w["Aopp"].values, w["Aown"].values, w["Iown"].values]
    Xb_own = B.base_terms(w) + [w["Aopp"].values, w["Aown"].values, w["Iopp"].values]
    d_opp = B.r2(y, Xb_opp + [w["Iopp"].values]) - B.r2(y, Xb_opp)
    d_own = B.r2(y, Xb_own + [w["Iown"].values]) - B.r2(y, Xb_own)
    print("\n  dR2 of O x OPPONENT pace, GIVEN O x own-team pace already in the model: %.6f" % d_opp)
    print("  dR2 of O x OWN-TEAM pace, GIVEN O x opponent pace already in the model: %.6f" % d_own)

    # ---- permutation test on the DIFFERENCE of the two betas ----
    # Placebo form: the two interaction COLUMNS are already computed; we permute WHICH SIDE
    # each row's pair of pace values is assigned to (a coin flip swapping Aopp/Aown per row).
    # Under the null of symmetry the two sides are exchangeable, so the observed difference
    # should sit inside this distribution.
    rng = np.random.default_rng(B.SEED)
    O = w["O"].values
    Ao, Aw = w["Aopp"].values.copy(), w["Aown"].values.copy()
    base = B.base_terms(w)
    diffs = np.empty(N_PERM)
    for i in range(N_PERM):
        flip = rng.random(len(w)) < 0.5
        a1 = np.where(flip, Aw, Ao)
        a2 = np.where(flip, Ao, Aw)
        bb = B.fit_beta(y, base + [a1, a2, O * a1, O * a2])
        diffs[i] = bb[-2] - bb[-1]
    obs = b_opp - b_own
    print("\n  SIDE-EXCHANGEABILITY PLACEBO (%d flips): mean=%+.6f  SD=%.6f  frac>=obs=%.4f"
          % (N_PERM, diffs.mean(), diffs.std(), float((diffs >= obs).mean())))
    if diffs.std() == 0.0:
        print("  *** DEGENERATE PLACEBO (sd exactly 0). ***")

    verdict = ("ASYMMETRIC -> genuine opponent matchup" if float((diffs >= obs).mean()) < 0.05
               else "SYMMETRIC -> game-tempo volume, not a matchup")
    print("\n  VERDICT: %s" % verdict)

    out = {"n": int(len(w)), "beta_O_x_opp_pace": b_opp, "beta_O_x_own_pace": b_own,
           "difference": obs, "per_season": rows,
           "dR2_opp_given_own": d_opp, "dR2_own_given_opp": d_own,
           "placebo_side_exchange": {"n_perm": N_PERM, "mean": float(diffs.mean()),
                                     "sd": float(diffs.std()),
                                     "frac_ge_obs": float((diffs >= obs).mean())},
           "verdict": verdict}
    B.safe_write(w[["game_id", "season", "game_date", "team_id", "opp_team_id", "player_id",
                    "minutes", "possessions", "y", "own_pre", "def_pre", "dpace", "own_dpace"]],
                 "r4_symmetry_features_reb.csv")
    return out


if __name__ == "__main__":
    r = run()
    with open(os.path.join(B.OUT, "r4_symmetry_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2, default=float)
    print("\nR4 done.")
