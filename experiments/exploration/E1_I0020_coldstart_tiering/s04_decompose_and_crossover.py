"""E1_I0020 STEP 3(cont) / 4 / 5 -- THE D087 DECOMPOSITION, THE ZERO-GAMES CASE, THE CROSSOVER.

  THE QUESTION THIS SCRIPT EXISTS TO ANSWER.  s03 found that a shrinkage blend
      BLEND_STRUCT(k) = lam(n)*own_running_mean + (1-lam(n))*STRUCTURAL_PRIOR,  lam(n)=n/(n+k)
  beats the COMPLETE running mean on the data-poor tier (points dR2 +0.110, p=0.0005).  That is a
  large, significant, non-random increment -- and D087 is the finding that such an increment can be
  nothing but the reference's blind spot, or some other mechanism entirely, re-entering under a new
  name.  Two mechanisms are confounded in BLEND_STRUCT:
      (a) SHRINKAGE.  A 1- or 2-game running mean is extremely noisy; pulling it toward ANY sensible
          constant will help, and the league mean is a sensible constant.
      (b) STRUCTURE.  The player's listed position, draft slot and depth-chart rank say something
          about them specifically that the league mean does not.
  The user's proposal is (b).  The control that separates them is BLEND_LEAGUE, identical in every
  respect except that it shrinks toward the plain league mean:
      BLEND_LEAGUE(k) = lam(n)*own_running_mean + (1-lam(n))*LEAGUE_MEAN
  If BLEND_STRUCT does not beat BLEND_LEAGUE, the structural prior contributes NOTHING and the whole
  effect is shrinkage.  Everything else in this screen is downstream of that one contrast.
"""
import os

import numpy as np
import pandas as pd

import ct_base as B
import screenkit as sk

OUT = {}
w = pd.read_parquet(os.path.join(B.OUT, "placeholder_frame.parquet"))
pool_all = pd.read_parquet(os.path.join(B.OUT, "prior_pool.parquet"))
B.assert_partition_adjudicated(w, where="s04 placeholder_frame")
PH = {t: pd.read_csv(os.path.join(B.OUT, "placeholders_%s.csv" % t)) for t in B.TARGETS}
w["tier_poor"] = w["pts__is_fallback"].to_numpy(bool)

CELLS = {
    "TIER_DATA_POOR": w["tier_poor"].to_numpy(),
    "sub_0_priors": (w["pl_games_prior"] == 0).to_numpy(),
    "sub_1_2_priors": ((w["pl_games_prior"] >= 1) & (w["pl_games_prior"] <= 2)).to_numpy(),
}


def blends(t, k):
    """Return (BLEND_STRUCT, BLEND_LEAGUE) for target t and shrinkage constant k.

    IDENTICAL construction, IDENTICAL lam(n), IDENTICAL own-mean.  The ONLY difference is what the
    blend shrinks TOWARD.  That is what makes this a decomposition and not another horse race.
    """
    n = w["pl_games_prior"].to_numpy(float)
    lam = n / (n + k)
    own = w["own_season_" + t].to_numpy(float)
    struct = PH[t]["P5c_additive"].to_numpy(float)
    league = PH[t]["league"].to_numpy(float)
    bs = lam * np.where(np.isfinite(own), own, struct) + (1 - lam) * struct
    bl = lam * np.where(np.isfinite(own), own, league) + (1 - lam) * league
    return bs, bl


# ================================================================ 4.1 THE DECOMPOSITION
B.hdr("STEP 4.1 -- D087 DECOMPOSITION: IS THE GAIN STRUCTURE, OR IS IT JUST SHRINKAGE?")
rows = []
for cell, m in CELLS.items():
    sub = w[m]
    g = B.block_codes(sub)
    for t in ["pts", "minutes", "ppm"]:
        y = sub["t_" + t].to_numpy(float)
        p1f = sub["p1full_" + t].to_numpy(float)
        for k in [1.0, 2.0, 3.0, 5.0, 10.0]:
            bs, bl = blends(t, k)
            bs, bl = bs[m], bl[m]
            r_sl, _ = B.paired(y, bs, bl, g, name_a="BLEND_STRUCT", name_b="BLEND_LEAGUE")
            r_sp, _ = B.paired(y, bs, p1f, g, name_a="BLEND_STRUCT", name_b="P1full")
            r_lp, _ = B.paired(y, bl, p1f, g, name_a="BLEND_LEAGUE", name_b="P1full")
            rows.append(dict(cell=cell, target=t, k=k, n=int(m.sum()),
                             n_clusters=int(r_sl["n_groups"]),
                             dr2_STRUCT_vs_LEAGUE=r_sl["dr2_a_minus_b"],
                             p_cluster_STRUCT_vs_LEAGUE=r_sl["p"],
                             p_row_NAIVE_STRUCT_vs_LEAGUE=r_sl["p_row_level_NAIVE"],
                             inflation=r_sl["inflation"],
                             dr2_STRUCT_vs_P1full=r_sp["dr2_a_minus_b"],
                             p_STRUCT_vs_P1full=r_sp["p"],
                             dr2_LEAGUE_vs_P1full=r_lp["dr2_a_minus_b"],
                             p_LEAGUE_vs_P1full=r_lp["p"],
                             share_of_gain_from_structure=(
                                 r_sl["dr2_a_minus_b"] / r_sp["dr2_a_minus_b"]
                                 if abs(r_sp["dr2_a_minus_b"]) > 1e-12 else np.nan)))
DEC = pd.DataFrame(rows)
DEC.to_csv(os.path.join(B.OUT, "d087_decomposition.csv"), index=False)
for cell in CELLS:
    for t in ["pts", "minutes"]:
        sl = DEC[(DEC["cell"] == cell) & (DEC["target"] == t)]
        print("\n  --- %s | target=%s | n=%d clusters=%d"
              % (cell, t, sl["n"].iloc[0], sl["n_clusters"].iloc[0]))
        print(sl[["k", "dr2_STRUCT_vs_P1full", "p_STRUCT_vs_P1full",
                  "dr2_LEAGUE_vs_P1full", "p_LEAGUE_vs_P1full",
                  "dr2_STRUCT_vs_LEAGUE", "p_cluster_STRUCT_vs_LEAGUE",
                  "p_row_NAIVE_STRUCT_vs_LEAGUE", "inflation",
                  "share_of_gain_from_structure"]].to_string(
            index=False, float_format=lambda v: "%+.4f" % v))
print("""
  READING THE TABLE.  `dr2_LEAGUE_vs_P1full` is the gain from SHRINKAGE ALONE -- the blend that
  knows nothing about the player except how many games they have played.  `dr2_STRUCT_vs_LEAGUE` is
  everything the position / draft / depth-chart prior adds ON TOP of that.  If the second column is
  a large fraction of the first, the user's proposal is doing real work; if it is a small residue
  with a p above 0.05, the honest answer is that shrinkage is the whole effect.
""")
OUT["d087_decomposition"] = DEC.to_dict("records")

# ---------------------------------------------------------------- nested component decomposition
B.hdr("STEP 4.2 -- NESTED DECOMPOSITION OF THE STRUCTURAL PRIOR INTO ITS OWN COMPONENTS")
print("  Every prior measurement of the target that exists is in the base, per D087.\n")
comp_rows = []
for cell, m in CELLS.items():
    sub = w[m]
    g = B.block_codes(sub)
    for t in ["pts", "minutes"]:
        y = sub["t_" + t].to_numpy(float)
        ph = PH[t][m]
        mu = ph["league"].to_numpy(float)
        pos = ph["P2_position"].to_numpy(float)
        drf = ph["P3_draft_bin"].to_numpy(float)
        dep = ph["P4_teamrole"].to_numpy(float)
        ladder = [("league", mu),
                  ("league+depth", mu + (dep - mu)),
                  ("league+depth+draft", mu + (dep - mu) + (drf - mu)),
                  ("league+depth+draft+pos", mu + (dep - mu) + (drf - mu) + (pos - mu))]
        prev = None
        for nm, v in ladder:
            r2 = B.r2f(y, v)
            rec = dict(cell=cell, target=t, step=nm, r2_of_forecast=r2, mae=B.mae(y, v))
            if prev is not None:
                rr, _ = B.paired(y, v, prev[1], g, name_a=nm, name_b=prev[0])
                rec["dr2_vs_previous_step"] = rr["dr2_a_minus_b"]
                rec["p_cluster_vs_previous"] = rr["p"]
            comp_rows.append(rec)
            prev = (nm, v)
CMP = pd.DataFrame(comp_rows)
CMP.to_csv(os.path.join(B.OUT, "component_decomposition.csv"), index=False)
for cell in CELLS:
    for t in ["pts", "minutes"]:
        sl = CMP[(CMP["cell"] == cell) & (CMP["target"] == t)]
        print("  --- %s | %s" % (cell, t))
        print(sl[["step", "r2_of_forecast", "mae", "dr2_vs_previous_step",
                  "p_cluster_vs_previous"]].to_string(index=False,
                                                      float_format=lambda v: "%+.4f" % v))
        print("")
OUT["component_decomposition"] = CMP.to_dict("records")

# ================================================================ 4.3 permutation nulls
B.hdr("STEP 4.3 -- PERMUTATION NULLS AT THE CORRECT GROUPING LEVEL (constraint 6)")
w["ps_block"] = ["%d_%d" % (s, p) for s, p in zip(w["season"], w["player_id"])]
w["gt_block"] = w["game_id"].astype(str) + "_" + w["team_id"].astype(str)

# KIT USAGE NOTE (reported in NOTES.md, NOT a defect): permutation_null refuses a string/categorical
# feature outright -- "the kit will not guess an encoding for you" -- which is the safe behaviour and
# the message names the fix.  DECLARED ENCODING, as it asks: each categorical is mapped to a dense
# integer code by a FIXED dictionary built once from the sorted distinct labels, and stat_fn maps the
# integer back to its label before any lookup.  The encoding is a pure relabelling: it is bijective,
# it is applied identically to the real frame and to every draw, and no arithmetic is ever done on
# the codes, so no ordering is implied by the integers.
CODEBOOKS = {}
for feat in ["draft_bucket", "pos_group"]:
    labs = sorted(w[feat].astype(str).unique())
    CODEBOOKS[feat] = {lab: i for i, lab in enumerate(labs)}
    w[feat + "_code"] = w[feat].astype(str).map(CODEBOOKS[feat]).astype(float)
    print("  encoding %-14s -> %s" % (feat, CODEBOOKS[feat]))
OUT["categorical_codebooks"] = CODEBOOKS

for feat in ["draft_bucket", "pos_group", "depth_bucket"]:
    lvl = sk.detect_grouping_level(
        w, feat, candidate_keys={"player_season": ["season", "player_id"],
                                 "player": ["player_id"],
                                 "game_team": ["game_id", "team_id"],
                                 "season": ["season"]}, verbose=False)
    vsb_ps = sk.var_share_between(w, feat, "ps_block") if feat == "depth_bucket" else None
    print("  %-14s status=%-52s recommended=%s"
          % (feat, lvl["status"], lvl.get("recommended_permutation_level")))
    if vsb_ps is not None:
        print("                 var_share_between(player_season) = %.4f" % vsb_ps)
    OUT.setdefault("grouping_levels", {})[feat] = {
        "status": lvl["status"], "recommended": lvl.get("recommended_permutation_level"),
        "recommended_key_cols": lvl.get("recommended_key_cols")}

m_poor = CELLS["TIER_DATA_POOR"]
idx_poor = np.where(m_poor)[0]


def make_stat(t, permcol, lookupcol, inverse=None):
    """r2_of_forecast of the structural prior on the DATA-POOR rows, rebuilt from `permcol`.

    `permcol` is what permutation_null shuffles (numeric); `inverse` maps its values back to the
    label the prior is keyed on.  The prior VALUES themselves are estimated once, on strictly prior
    seasons, and are NEVER recomputed inside a draw -- only the ASSIGNMENT of an already-computed
    value to a row is permuted, which is the kit's stated requirement and what noop_placebo exists
    to police.
    """
    priors_by_season = {}
    for S in B.SCREEN_SEASONS:
        pool = pool_all[pool_all["season"] < S]
        mu = float(pool["t_" + t].mean())
        est, _ = B._shrunk_group_mean(pool, [lookupcol], "t_" + t, mu, B.SHRINK_K)
        priors_by_season[S] = (est, mu)

    def stat(frame):
        v = np.empty(len(frame), float)
        lab = frame[permcol]
        if inverse is not None:
            lab = lab.map(inverse)
        for S in B.SCREEN_SEASONS:
            mm = (frame["season"] == S).to_numpy()
            est, mu = priors_by_season[S]
            v[mm] = lab[mm].map(est).astype(float).fillna(mu).to_numpy()
        sub = frame["tier_poor"].to_numpy(bool)
        y = frame.loc[sub, "t_" + t].to_numpy(float)
        return B.r2f(y, v[sub])
    return stat


perm_rows = []
PERM_SPEC = [
    ("draft_bucket_code", "draft_bucket", "ps_block",
     "player-season: draft slot is constant within a player; reassigns WHOSE draft slot a player "
     "gets, inside the same season"),
    ("pos_group_code", "pos_group", "ps_block",
     "player-season: listed position is constant within a player"),
    ("depth_bucket", "depth_bucket", "gt_block",
     "game-team: reshuffles WHO occupies which depth slot on the same roster on the same night, "
     "preserving that night's depth-slot marginal exactly"),
]
for permcol, lookupcol, lvlcol, why in PERM_SPEC:
    inv = None
    if permcol.endswith("_code"):
        inv = {float(v): k for k, v in CODEBOOKS[lookupcol].items()}
    for t in ["pts", "minutes"]:
        stat = make_stat(t, permcol, lookupcol, inv)
        real = stat(w)
        try:
            r = sk.permutation_null(stat, w, lvlcol, 500, B.SEED, feature_col=permcol,
                                    block_col="season", scheme=sk.SCHEME_BETWEEN,
                                    allow_nonconstant=(permcol == "depth_bucket"))
            pc, sdc = r["p"], float(np.std(r["draws"], ddof=1))
            draws_c = r["draws"]
        except Exception as e:                                     # pragma: no cover
            pc, sdc, draws_c = float("nan"), float("nan"), None
            print("     permutation_null raised for %s: %r" % (permcol, e))
        rr = sk.permutation_null(stat, w, sk.ROW_LEVEL, 500, B.SEED, feature_col=permcol,
                                 block_col="season", scheme=sk.SCHEME_BETWEEN,
                                 allow_nonconstant=True)
        feat = lookupcol
        sdr = float(np.std(rr["draws"], ddof=1))
        perm_rows.append(dict(feature=feat, target=t, level=lvlcol, rationale=why,
                              real_r2=real, p_correct_level=pc, null_sd_correct=sdc,
                              p_row_level_NAIVE=rr["p"], null_sd_row=sdr,
                              inflation_correct_over_row=(sdc / sdr) if sdr > 0 else np.nan))
        if draws_c is not None and t == "pts":
            pd.DataFrame({"draw": draws_c}).to_csv(
                os.path.join(B.OUT, "perm_draws_%s_pts.csv" % feat), index=False)
PN = pd.DataFrame(perm_rows)
PN.to_csv(os.path.join(B.OUT, "permutation_nulls.csv"), index=False)
print("\n" + PN[["feature", "target", "level", "real_r2", "p_correct_level", "null_sd_correct",
                 "p_row_level_NAIVE", "null_sd_row", "inflation_correct_over_row"]].to_string(
    index=False, float_format=lambda v: "%+.5f" % v))
OUT["permutation_nulls"] = PN.to_dict("records")

# ================================================================ 5. THE ZERO-GAMES CASE
B.hdr("STEP 5 -- THE ZERO-GAMES CASE, REPORTED SEPARATELY WITH ITS OWN NUMBERS")
print("""
  DEFINITIONS, and why there are two.
    ZERO SAME-SEASON: pl_games_prior == 0.  The player has not appeared yet THIS season.  71 rows.
                      P1 (a same-season running mean) is UNDEFINED and falls back to a league mean.
    ZERO CAREER     : pl_career_games_prior == 0.  No appearance anywhere in the 2021-2024 window.
                      22 rows.  This is the true no-information case and the only one where the
                      user's draft-position proposal has literally no competitor.
  SELECTION CAVEAT, measured in s02b and repeated here because it bounds every number below: the
  champion scores only 71 of the 479 true first appearances in 2022-2024 (14.8%).  These results are
  conditional on that selection.
""")
zrows = []
for lbl, m in [("zero_same_season", (w["pl_games_prior"] == 0).to_numpy()),
               ("zero_career", (w["pl_career_games_prior"] == 0).to_numpy()),
               ("zero_same_season_but_has_career",
                ((w["pl_games_prior"] == 0) & (w["pl_career_games_prior"] > 0)).to_numpy())]:
    sub = w[m]
    g = B.block_codes(sub)
    for t in ["pts", "minutes"]:
        y = sub["t_" + t].to_numpy(float)
        ph = PH[t][m]
        base = ph["league"].to_numpy(float)
        for nm in ["P0_champion", "P1full_running_mean", "P2_position", "P3_draft_bin",
                   "P3_draft_ols", "P4_teamrole", "P5c_additive", "P1c_career_mean",
                   "P5e_careerblend_k3"]:
            a = ph[nm].to_numpy(float)
            r, _ = B.paired(y, a, base, g, name_a=nm, name_b="league_mean", n_draws=2000)
            zrows.append(dict(population=lbl, n=int(m.sum()), n_clusters=int(r["n_groups"]),
                              target=t, placeholder=nm, mae=B.mae(y, a),
                              r2_of_forecast=r["r2_a"], r2_league=r["r2_b"],
                              dr2_vs_league_mean=r["dr2_a_minus_b"], p_cluster=r["p"],
                              p_row_NAIVE=r["p_row_level_NAIVE"]))
Z = pd.DataFrame(zrows)
Z.to_csv(os.path.join(B.OUT, "zero_games_case.csv"), index=False)
for lbl in Z["population"].unique():
    for t in ["pts", "minutes"]:
        sl = Z[(Z["population"] == lbl) & (Z["target"] == t)].sort_values(
            "dr2_vs_league_mean", ascending=False)
        print("\n  --- %s | target=%s | n=%d clusters=%d   (contrast: vs the LEAGUE MEAN, which is"
              " what a system with no player information can do)"
              % (lbl, t, sl["n"].iloc[0], sl["n_clusters"].iloc[0]))
        print(sl[["placeholder", "mae", "r2_of_forecast", "dr2_vs_league_mean",
                  "p_cluster", "p_row_NAIVE"]].to_string(index=False,
                                                         float_format=lambda v: "%+.4f" % v))
OUT["zero_games_case"] = Z.to_dict("records")

# ================================================================ 6. THE CROSSOVER
B.hdr("STEP 6 -- THE HANDOVER CURVE: WHERE DOES THE CHAMPION OVERTAKE THE BEST PLACEHOLDER?")
print("""
  Statistic per cell: dR2(champion) - dR2(placeholder) = r2_of_forecast(y, champ)
  - r2_of_forecast(y, placeholder), on the rows with exactly n prior same-season appearances.
  POSITIVE means the champion is ahead.  Uncertainty is a CLUSTER BOOTSTRAP over (season,
  player_id) blocks -- 2000 resamples -- because the rows are not independent.
""")
BEST = "P5d_blend_k2"
rng = np.random.default_rng(B.SEED)
cross_rows = []
BINS = [(0, 1, "0"), (1, 2, "1"), (2, 3, "2"), (3, 4, "3"), (4, 5, "4"), (5, 6, "5"),
        (6, 8, "6-7"), (8, 11, "8-10"), (11, 16, "11-15"), (16, 25, "16-24"), (25, 999, "25+")]
for t in ["pts", "minutes"]:
    y_all = w["t_" + t].to_numpy(float)
    champ_all = w["champ_" + t].to_numpy(float)
    best_all = PH[t][BEST].to_numpy(float)
    for lo, hi, lab in BINS:
        m = ((w["pl_games_prior"] >= lo) & (w["pl_games_prior"] < hi)).to_numpy()
        if m.sum() < 30:
            continue
        y, c, b = y_all[m], champ_all[m], best_all[m]
        codes = B.block_codes(w[m])
        real = B.r2f(y, c) - B.r2f(y, b)
        uq = np.unique(codes)
        idx_by = {u: np.where(codes == u)[0] for u in uq}
        boots = np.empty(2000, float)
        for i in range(2000):
            pick = rng.choice(uq, size=len(uq), replace=True)
            sel = np.concatenate([idx_by[u] for u in pick])
            boots[i] = B.r2f(y[sel], c[sel]) - B.r2f(y[sel], b[sel])
        lo_ci, hi_ci = np.percentile(boots, [2.5, 97.5])
        cross_rows.append(dict(target=t, bin=lab, lo=lo, hi=hi, n=int(m.sum()),
                               n_clusters=int(len(uq)),
                               dr2_champion_minus_placeholder=real,
                               ci95_lo=float(lo_ci), ci95_hi=float(hi_ci),
                               champion_ahead=bool(lo_ci > 0),
                               placeholder_ahead=bool(hi_ci < 0)))
CR = pd.DataFrame(cross_rows)
CR.to_csv(os.path.join(B.OUT, "handover_curve.csv"), index=False)
for t in ["pts", "minutes"]:
    print("\n  --- target=%s   placeholder = %s" % (t, BEST))
    print(CR[CR["target"] == t][["bin", "n", "n_clusters", "dr2_champion_minus_placeholder",
                                 "ci95_lo", "ci95_hi", "champion_ahead",
                                 "placeholder_ahead"]].to_string(
        index=False, float_format=lambda v: "%+.4f" % v))
    sl = CR[CR["target"] == t]
    first = sl[sl["champion_ahead"]]
    print("     FIRST BIN WHERE THE CHAMPION IS AHEAD WITH THE WHOLE 95%% CI ABOVE ZERO: %s"
          % (first["bin"].iloc[0] if len(first) else "NONE in the observed range"))
OUT["handover_curve"] = CR.to_dict("records")

B.jdump(OUT, "_s04.json")
print("\nSTEP 4/5/6 COMPLETE.")
