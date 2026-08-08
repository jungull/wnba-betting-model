"""E1_I0020 STEP 3 -- BUILD AND COMPARE PLACEHOLDERS FOR THE DATA-POOR TIER.

  THE TIER, as derived in s02/s02b: the champion's own `pts__is_fallback` flag.  It is a strict
  superset of "fewer than 3 prior same-season appearances" (999 rows) plus 62 returning-from-absence
  rows, and there are ZERO rows with <3 priors that are not flagged.  1,061 rows, 7.64%.

  WHAT THE CHAMPION EMITS THERE, measured in s02b: a CONSTANT.  8.705 points (sd 0.013) and 21.62
  minutes (sd 0.09) for every data-poor row in three seasons.  That is the "filler score" the user
  is proposing to replace, and it currently carries no information about who the player is.

  PLACEHOLDERS (targets: pts, minutes, ppm = pts/minutes)
    P0  champion as-is                       -- the thing to beat.  SCORED, NEVER REFITTED.
    P1  running mean of the player's OWN prior same-season games, league-mean cold fallback
                                             -- D076's ref_*, the crude baseline D081 spliced.
    P1c career running mean (prior games across seasons inside the 2021-2024 window)
    P2  POSITION prior      -- shrunk mean by listed position, PRIOR SEASONS ONLY
    P3  DRAFT prior         -- shrunk mean by draft bucket + a 3-parameter OLS on log(pick),
                               PRIOR SEASONS ONLY.  The user's specific proposal, and the only
                               placeholder available to a player with LITERALLY ZERO games.
    P4  TEAM-ROLE prior     -- shrunk mean by point-in-time depth-chart bucket, PRIOR SEASONS ONLY
    P5a draft x depth cross prior
    P5b position x draft cross prior
    P5c additive main effects: league + pos_dev + draft_dev + depth_dev
    P5d SHRINKAGE BLEND     -- lam(n)*own_running_mean + (1-lam(n))*P5c,  lam(n) = n/(n+k)

  WALK-FORWARD.  Every prior for season S is estimated on appeared player-games of seasons < S
  inside 2021-2024.  S=2022 -> {2021};  S=2023 -> {2021,2022};  S=2024 -> {2021,2022,2023}.
  Asserted per fold.  Nothing reads season S or later.

  INFERENCE.  screenkit.paired_forecast_comparison, clustered at (season, player_id), 2000 draws.
  The naive row-level null is reported beside it with its inflation factor, for contrast only.
"""
import os

import numpy as np
import pandas as pd

import ct_base as B
import screenkit as sk

OUT = {}
w = pd.read_parquet(os.path.join(B.OUT, "tier_frame.parquet"))
# idempotence: drop anything a previous run of THIS script attached, so the merges below cannot
# silently produce _x/_y suffixed duplicates.
w = w.drop(columns=[c for c in w.columns
                    if c.startswith(("own_season_", "own_career_", "lg_", "p1full_"))
                    or c == "tier_poor"], errors="ignore")
pool_all = pd.read_parquet(os.path.join(B.OUT, "prior_pool.parquet"))
B.assert_partition_adjudicated(w, where="s03 tier_frame")
B.guard(pool_all, "s03 prior pool")

# ============================================================ 3.0 player-own running means
B.hdr("STEP 3.0 -- THE PLAYER'S OWN PRIOR-GAMES RUNNING MEANS (strictly prior, NaN when none)")
mp = B.load_master()
d = mp.sort_values(["season", "player_id", "gdate", "game_id"]).copy()
d["_ap"] = d["appeared"].astype(float)
d["r_ppm"] = np.where(d["minutes"] > 0, d["pts"] / d["minutes"].replace(0, np.nan), np.nan)
app = d[d["appeared"]].copy()
for t, col in [("pts", "pts"), ("minutes", "minutes"), ("ppm", "r_ppm")]:
    app["own_season_" + t] = app.groupby(["season", "player_id"], sort=False)[col].transform(
        lambda x: x.shift(1).expanding().mean())
    app["own_career_" + t] = app.groupby(["player_id"], sort=False)[col].transform(
        lambda x: x.shift(1).expanding().mean())
# same-season expanding LEAGUE mean over games strictly earlier in the season -- the cold fallback,
# built exactly as D076 built its own, but over the COMPLETE appeared record.
appd = app.sort_values(["season", "gdate", "game_id"], kind="stable")
for t, col in [("pts", "pts"), ("minutes", "minutes"), ("ppm", "r_ppm")]:
    appd["lg_" + t] = appd.groupby("season", sort=False)[col].transform(
        lambda x: x.shift(1).expanding().mean())
app = app.merge(appd[["game_id", "team_id", "player_id", "lg_pts", "lg_minutes", "lg_ppm"]],
                on=["game_id", "team_id", "player_id"], how="left")
key = ["game_id", "team_id", "player_id"]
app["game_id"] = app["game_id"].astype(str)
w["game_id"] = w["game_id"].astype(str)
w = w.merge(app[key + ["own_season_pts", "own_season_minutes", "own_season_ppm",
                       "own_career_pts", "own_career_minutes", "own_career_ppm",
                       "lg_pts", "lg_minutes", "lg_ppm"]],
            on=key, how="left")
for t in B.TARGETS:
    w["p1full_" + t] = w["own_season_" + t].fillna(w["lg_" + t]).fillna(
        float(w["t_" + t].mean()))
print("  own_season_pts   defined on %d of %d rows (NaN exactly where prior appearances == 0)"
      % (int(w["own_season_pts"].notna().sum()), len(w)))
chk = (w["own_season_pts"].isna() == (w["pl_games_prior"] == 0))
print("  NaN pattern matches pl_games_prior==0 on %d of %d rows" % (int(chk.sum()), len(w)))
assert chk.all(), "own running mean NaN pattern disagrees with the frozen prior-game count"

# --------------------------------------------------------------------------------------------
# D087 -- REFERENCE INCOMPLETENESS.  THIS IS THE TRAP, AND IT IS LIVE HERE.
# --------------------------------------------------------------------------------------------
B.hdr("STEP 3.0b -- D076's REFERENCE IS BLIND ON EXACTLY THE ROWS THIS SCREEN IS ABOUT")
mm = w["own_season_pts"].notna()
delta = float((w.loc[mm, "own_season_pts"] - w.loc[mm, "ref_pts"]).abs().max())
print("  max |own_season_pts - D076 ref_pts| where the player mean is defined: %.4f" % delta)
print("""
  THEY DO NOT AGREE, AND THE REASON MATTERS MORE THAN THE NUMBER.
  D076 built ref_* as an expanding mean over THE ROWS IN ITS OWN FRAME -- the champion's scored
  rows.  s02b measured that the champion scores only 71 of 479 true first appearances (14.8%), so
  for 404 of 475 player-seasons the FIRST SCORED ROW is the player's SECOND appearance.  On that
  row D076's reference has seen NO prior row of its own frame and falls back to the league mean,
  even though the player's actual first game HAPPENED and is in master_player.

  So the crude baseline the briefing calls "the running mean of the player's own prior games" is,
  on the data-poor tier, largely NOT that.  It is the league mean wearing that name.
""")
for n in [0, 1, 2, 3]:
    m = (w["pl_games_prior"] == n)
    print("   n_prior=%d  n=%4d | D076 ref_pts sd=%6.3f | complete own-mean sd=%6.3f | "
          "rows where |diff|>0.01: %4d (%5.1f%%)"
          % (n, m.sum(), w.loc[m, "ref_pts"].std(),
             w.loc[m, "own_season_pts"].std() if n > 0 else float("nan"),
             int((w.loc[m, "own_season_pts"] - w.loc[m, "ref_pts"]).abs().gt(0.01).sum()),
             100.0 * float((w.loc[m, "own_season_pts"] - w.loc[m, "ref_pts"]).abs().gt(0.01).mean())))
OUT["ref_incompleteness"] = {
    "max_abs_delta_own_vs_ref": delta,
    "first_appearance_coverage": 71.0 / 479.0,
    "n_player_seasons_first_scored_row_is_not_first_appearance": 404,
}
print("""
  CONSEQUENCE, AND IT IS THE WHOLE POINT OF D087.  Any placeholder built on the COMPLETE prior-
  appearance record would beat D076's ref partly or wholly because the reference is BLIND, not
  because the placeholder is smart.  That increment would be large, significant and non-random, and
  it would survive a permutation null -- exactly D087's signature.  This screen therefore carries
  BOTH baselines and reports every contrast against BOTH:
      P1_ref_D076   the frozen, INCOMPLETE reference -- kept only for continuity with D076/D081
      P1full_running_mean   the player's own prior same-season appearances from master_player,
                    COMPLETE, league-mean cold fallback.  *** THIS IS THE CRUDE BASELINE TO BEAT. ***
""")

# ============================================================ 3.1 walk-forward priors
B.hdr("STEP 3.1 -- WALK-FORWARD PRIOR ESTIMATION (season S uses seasons < S ONLY)")
pool_all["t_ppm"] = pool_all["t_pts"] / pool_all["t_minutes"]
priors = {}
for S in B.SCREEN_SEASONS:
    pool = pool_all[pool_all["season"] < S]
    assert len(pool) and int(pool["season"].max()) < S
    priors[S] = B.fit_priors_for_season(pool, S, k=B.SHRINK_K, verbose=True)
    print("      pool seasons=%s rows=%d   league means: pts=%.3f minutes=%.3f ppm=%.4f"
          % (priors[S]["pool_seasons"], priors[S]["pool_rows"],
             priors[S]["pts"]["league_mean"], priors[S]["minutes"]["league_mean"],
             priors[S]["ppm"]["league_mean"]))
OUT["prior_pool_by_season"] = {str(S): {"pool_seasons": priors[S]["pool_seasons"],
                                        "pool_rows": priors[S]["pool_rows"],
                                        "league_mean_pts": priors[S]["pts"]["league_mean"]}
                               for S in B.SCREEN_SEASONS}

print("\n  DRAFT-BUCKET PRIOR VALUES BY FOLD (points), to show they are estimated, not assumed:")
for S in B.SCREEN_SEASONS:
    db = priors[S]["pts"]["draft_bucket"]
    print("     %d: %s" % (S, {k: round(v, 3) for k, v in sorted(db.items())}))
print("\n  DEPTH-BUCKET PRIOR VALUES BY FOLD (minutes):")
for S in B.SCREEN_SEASONS:
    db = priors[S]["minutes"]["depth_bucket"]
    print("     %d: %s" % (S, {int(k): round(v, 2) for k, v in sorted(db.items())}))
print("\n  POSITION PRIOR VALUES BY FOLD (points):")
for S in B.SCREEN_SEASONS:
    print("     %d: %s" % (S, {k: round(v, 3) for k, v in sorted(priors[S]["pts"]["pos_group"].items())}))


def cross_prior(pool, keycols, valcol, mu, k=B.SHRINK_K):
    est, cnt = B._shrunk_group_mean(pool, keycols, valcol, mu, k)
    return est


def build_placeholders(frame, priors, t):
    """Attach every placeholder for target `t` to `frame`, fold by fold.  Returns a DataFrame."""
    out = pd.DataFrame(index=frame.index)
    out["P0_champion"] = frame["champ_" + t].to_numpy(float)
    out["P1_ref_D076"] = frame["p1_" + t].to_numpy(float)
    own_s = frame["own_season_" + t].to_numpy(float)
    own_c = frame["own_career_" + t].to_numpy(float)
    for nm in ["P2_position", "P3_draft_bin", "P3_draft_ols", "P4_teamrole", "P5a_draft_x_depth",
               "P5b_pos_x_draft", "P5c_additive", "league"]:
        out[nm] = np.nan
    for S in B.SCREEN_SEASONS:
        m = (frame["season"] == S).to_numpy()
        rows = frame[m]
        P = priors[S]
        v = B.apply_priors(rows, P, t)
        mu = P[t]["league_mean"]
        out.loc[m, "league"] = mu
        out.loc[m, "P2_position"] = v["pos"]
        out.loc[m, "P3_draft_bin"] = v["draft_bin"]
        out.loc[m, "P3_draft_ols"] = v["draft_ols"]
        out.loc[m, "P4_teamrole"] = v["depth"]
        pool = pool_all[pool_all["season"] < S]
        cx1 = cross_prior(pool, ["draft_bucket", "depth_bucket"], "t_" + t, mu)
        cx2 = cross_prior(pool, ["pos_group", "draft_bucket"], "t_" + t, mu)
        i1 = pd.MultiIndex.from_arrays([rows["draft_bucket"], rows["depth_bucket"]])
        i2 = pd.MultiIndex.from_arrays([rows["pos_group"], rows["draft_bucket"]])
        out.loc[m, "P5a_draft_x_depth"] = cx1.reindex(i1).to_numpy(float)
        out.loc[m, "P5b_pos_x_draft"] = cx2.reindex(i2).to_numpy(float)
        out.loc[m, "P5c_additive"] = (mu + (v["pos"] - mu) + (v["draft_bin"] - mu)
                                      + (v["depth"] - mu))
    for c in ["P5a_draft_x_depth", "P5b_pos_x_draft"]:
        out[c] = out[c].fillna(out["league"])
    # *** the COMPLETE crude baseline -- the thing that actually has to be beaten (D087) ***
    out["P1full_running_mean"] = frame["p1full_" + t].to_numpy(float)
    # ---- P5d shrinkage blends: lam(n)*own mean + (1-lam(n))*structural ----
    n_season = frame["pl_games_prior"].to_numpy(float)
    n_career = frame["pl_career_games_prior"].to_numpy(float)
    struct = out["P5c_additive"].to_numpy(float)
    for k in [1.0, 2.0, 3.0, 5.0, 10.0]:
        lam = n_season / (n_season + k)
        own = np.where(np.isfinite(own_s), own_s, struct)
        out["P5d_blend_k%g" % k] = lam * own + (1 - lam) * struct
        lamc = n_career / (n_career + k)
        ownc = np.where(np.isfinite(own_c), own_c, struct)
        out["P5e_careerblend_k%g" % k] = lamc * ownc + (1 - lamc) * struct
    out["P1c_career_mean"] = np.where(np.isfinite(own_c), own_c, out["league"])
    return out


# ============================================================ 3.2 the data-poor tier
B.hdr("STEP 3.2 -- THE DATA-POOR TIER AND ITS SUB-CELLS")
w["tier_poor"] = w["pts__is_fallback"].to_numpy(bool)
cells = {
    "TIER_DATA_POOR (fallback)": w["tier_poor"].to_numpy(),
    "  sub: 0 prior appearances": (w["pl_games_prior"] == 0).to_numpy(),
    "  sub: 1-2 prior appearances": ((w["pl_games_prior"] >= 1) & (w["pl_games_prior"] <= 2)).to_numpy(),
    "  sub: fallback with >=3 priors": (w["tier_poor"] & (w["pl_games_prior"] >= 3)).to_numpy(),
    "TIER_DATA_RICH (non-fallback)": (~w["tier_poor"]).to_numpy(),
}
for lbl, m in cells.items():
    print("  %-34s n=%5d  players=%4d  clusters=%4d"
          % (lbl, m.sum(), w[m]["player_id"].nunique(),
             w[m].groupby(["season", "player_id"]).ngroups))

PH = {t: build_placeholders(w, priors, t) for t in B.TARGETS}
for t in B.TARGETS:
    PH[t].to_csv(os.path.join(B.OUT, "placeholders_%s.csv" % t), index=False)
print("\n  wrote placeholders_{pts,minutes,ppm}.csv")

# ============================================================ 3.3 the comparison
B.hdr("STEP 3.3 -- PLACEHOLDER COMPARISON ON THE DATA-POOR TIER (paired_forecast_comparison)")
NAMES = ["P0_champion", "P1_ref_D076", "P1full_running_mean", "P1c_career_mean", "P2_position",
         "P3_draft_bin", "P3_draft_ols", "P4_teamrole", "P5a_draft_x_depth", "P5b_pos_x_draft",
         "P5c_additive", "P5d_blend_k1", "P5d_blend_k2", "P5d_blend_k3", "P5d_blend_k5",
         "P5d_blend_k10", "P5e_careerblend_k2", "P5e_careerblend_k3", "P5e_careerblend_k5",
         "league"]

res_rows = []
draws_store = {}
for cell_lbl, m in cells.items():
    if m.sum() < 40:
        continue
    sub = w[m]
    groups = B.block_codes(sub)
    for t in B.TARGETS:
        y = sub["t_" + t].to_numpy(float)
        ph = PH[t][m]
        champ = ph["P0_champion"].to_numpy(float)
        p1 = ph["P1_ref_D076"].to_numpy(float)
        p1f = ph["P1full_running_mean"].to_numpy(float)
        for nm in NAMES:
            a = ph[nm].to_numpy(float)
            if not np.isfinite(a).any():
                continue
            r_vs_champ, dr = B.paired(y, a, champ, groups, name_a=nm, name_b="P0_champion")
            r_vs_p1, _ = B.paired(y, a, p1, groups, name_a=nm, name_b="P1_ref_D076")
            r_vs_p1f, _ = B.paired(y, a, p1f, groups, name_a=nm, name_b="P1full_running_mean")
            rec = dict(cell=cell_lbl.strip(), target=t, placeholder=nm, n=int(m.sum()),
                       n_clusters=int(r_vs_champ["n_groups"]),
                       r2_placeholder=r_vs_champ["r2_a"], r2_champion=r_vs_champ["r2_b"],
                       dr2_vs_champion=r_vs_champ["dr2_a_minus_b"],
                       p_cluster_vs_champion=r_vs_champ["p"],
                       p_row_NAIVE_vs_champion=r_vs_champ["p_row_level_NAIVE"],
                       inflation_vs_champion=r_vs_champ["inflation"],
                       dr2_vs_P1refD076=r_vs_p1["dr2_a_minus_b"],
                       p_cluster_vs_P1refD076=r_vs_p1["p"],
                       dr2_vs_P1full=r_vs_p1f["dr2_a_minus_b"],
                       p_cluster_vs_P1full=r_vs_p1f["p"],
                       p_row_NAIVE_vs_P1full=r_vs_p1f["p_row_level_NAIVE"],
                       inflation_vs_P1full=r_vs_p1f["inflation"],
                       mae=B.mae(y, a), mae_champion=B.mae(y, champ),
                       mae_P1refD076=B.mae(y, p1), mae_P1full=B.mae(y, p1f),
                       skill_mae_vs_P1full=1.0 - B.mae(y, a) / B.mae(y, p1f))
            res_rows.append(rec)
            if cell_lbl.startswith("TIER_DATA_POOR") and t == "pts" and dr is not None:
                draws_store[nm] = dr
R = pd.DataFrame(res_rows)
R.to_csv(os.path.join(B.OUT, "placeholder_comparison.csv"), index=False)
pd.DataFrame(draws_store).to_csv(os.path.join(B.OUT, "permutation_draws_datapoor_pts.csv"),
                                 index=False)
print("  wrote placeholder_comparison.csv and permutation_draws_datapoor_pts.csv")

for cell_lbl in [c.strip() for c in cells if c.strip().startswith("TIER_DATA_POOR")]:
    for t in B.TARGETS:
        sl = R[(R["cell"] == cell_lbl) & (R["target"] == t)].sort_values(
            "dr2_vs_champion", ascending=False)
        print("\n  --- %s | target=%s | n=%d  clusters=%d"
              % (cell_lbl, t, sl["n"].iloc[0], sl["n_clusters"].iloc[0]))
        print(sl[["placeholder", "mae", "r2_placeholder", "dr2_vs_champion",
                  "p_cluster_vs_champion", "dr2_vs_P1refD076", "dr2_vs_P1full",
                  "p_cluster_vs_P1full", "p_row_NAIVE_vs_P1full", "inflation_vs_P1full",
                  "skill_mae_vs_P1full"]].to_string(
            index=False, float_format=lambda v: "%+.4f" % v))

B.hdr("STEP 3.4 -- THE SUB-CELLS")
for cell_lbl in ["sub: 0 prior appearances", "sub: 1-2 prior appearances",
                 "sub: fallback with >=3 priors"]:
    for t in ["pts", "minutes"]:
        sl = R[(R["cell"] == cell_lbl) & (R["target"] == t)].sort_values(
            "dr2_vs_champion", ascending=False)
        if not len(sl):
            continue
        print("\n  --- %s | target=%s | n=%d clusters=%d"
              % (cell_lbl, t, sl["n"].iloc[0], sl["n_clusters"].iloc[0]))
        print(sl[["placeholder", "mae", "dr2_vs_champion", "p_cluster_vs_champion",
                  "dr2_vs_P1full", "p_cluster_vs_P1full"]].to_string(
            index=False, float_format=lambda v: "%+.4f" % v))

B.hdr("STEP 3.5 -- SHRINKAGE-K SENSITIVITY (preregistered k=200 for group means)")
sens = []
for k in [0.0, 50.0, 200.0, 1000.0]:
    pr = {S: B.fit_priors_for_season(pool_all[pool_all["season"] < S], S, k=k) for S in B.SCREEN_SEASONS}
    ph = build_placeholders(w, pr, "pts")
    m = cells["TIER_DATA_POOR (fallback)"]
    sub = w[m]
    y = sub["t_pts"].to_numpy(float)
    groups = B.block_codes(sub)
    for nm in ["P3_draft_bin", "P4_teamrole", "P5c_additive", "P5d_blend_k3"]:
        a = ph[m][nm].to_numpy(float)
        r, _ = B.paired(y, a, sub["p1full_pts"].to_numpy(float), groups, n_draws=500)
        sens.append(dict(shrink_k=k, placeholder=nm, dr2_vs_P1full=r["dr2_a_minus_b"], p=r["p"]))
SEN = pd.DataFrame(sens)
print(SEN.to_string(index=False, float_format=lambda v: "%+.5f" % v))
SEN.to_csv(os.path.join(B.OUT, "shrinkage_sensitivity.csv"), index=False)

OUT["comparison_rows"] = len(R)
B.jdump(OUT, "_s03.json")
# written to a SEPARATE file so s02's tier_frame.parquet stays the canonical, unenriched artifact
B.assert_partition_adjudicated(w, where="placeholder_frame write")
w.to_parquet(os.path.join(B.OUT, "placeholder_frame.parquet"), index=False)
print("  wrote placeholder_frame.parquet  shape=%s" % (w.shape,))
print("\nSTEP 3 COMPLETE.")
