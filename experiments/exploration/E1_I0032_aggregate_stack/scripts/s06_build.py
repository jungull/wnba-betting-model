"""E1_I0032 s06 -- build the ONE common frame on the AMENDED universe.

Re-checks both hashes.  Produces `_work.parquet`.  No comparison statistic is computed here.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack_base import (EXP, OUT, TV, EFF, TIER, TARGETS, SCORED, PLACEBO_SEED, RL,
                        FALLBACK_COL, cfg_naive, cfg_from_canon, estimate, prereg, guard_paths)

pd.set_option("display.width", 220)
spec = prereg()
amend = json.load(open(os.path.join(OUT, "_prereg_amendment.json"), encoding="utf-8"))
print("prereg  sha256 %s  MATCH" % spec["sha256"])
print("amend 1 sha256 %s" % amend["sha256"])

BASE = os.path.join(EXP, r"E0_I0024_reb_ast_characterisation\screen_frame.parquet")
guard_paths(BASE, TV, EFF, TIER)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


hdr("1. base universe = E0_I0024 (strictly contains the champion's universe)")
ba = pd.read_parquet(BASE)
tier = pd.read_parquet(TIER)
tv = pd.read_parquet(TV)
eff = pd.read_parquet(EFF)
for df in (ba, tier, tv, eff):
    df["game_id"] = df["game_id"].astype(str)
K = ["season", "player_id", "game_id"]
print("  base %s  by season %s" % (ba.shape, ba["season"].value_counts().sort_index().to_dict()))

champ_cols = ["pts__pred_point", "minutes__pred_point", "fga__pred_point",
              "pts__fallback_level", "minutes__fallback_level", "fga__fallback_level",
              "tm_is_home", "pl_games_prior", "pl_min_mean5", "depth_rank", "draft_pick"]
ba = ba.merge(tier[K + champ_cols].drop_duplicates(K), on=K, how="left")
print("  champion present on %d rows" % int(ba["pts__pred_point"].notna().sum()))

# defence: A10 is a TEAM-GAME property -> join on (season, game_id, opp_team_id)
dmap = eff[["season", "game_id", "opp_team_id", "A10_opp_defrtg"]].dropna().drop_duplicates(
    ["season", "game_id", "opp_team_id"])
before = ba.merge(eff[K + ["A10_opp_defrtg"]].drop_duplicates(K), on=K,
                  how="left").rename(columns={"A10_opp_defrtg": "_A10_playerjoin"})
ba = ba.merge(dmap, on=["season", "game_id", "opp_team_id"], how="left")
both = np.isfinite(pd.to_numeric(before["_A10_playerjoin"], errors="coerce").to_numpy(float)) & \
       np.isfinite(pd.to_numeric(ba["A10_opp_defrtg"], errors="coerce").to_numpy(float))
d = np.nanmax(np.abs(pd.to_numeric(before["_A10_playerjoin"], errors="coerce").to_numpy(float)[both]
                     - pd.to_numeric(ba["A10_opp_defrtg"], errors="coerce").to_numpy(float)[both]))
print("  A10 team-game join: finite on %d rows ; agrees with the player-row join on %d rows at "
      "|max diff| = %.3e" % (int(ba["A10_opp_defrtg"].notna().sum()), int(both.sum()), d))

ba = ba.merge(tv[K + ["P01_c04_prevgame", "O01_own_usg_pg"]].drop_duplicates(K), on=K, how="left")
print("  P01 finite on %d rows ; O01 usage finite on %d rows"
      % (int(ba["P01_c04_prevgame"].notna().sum()), int(ba["O01_own_usg_pg"].notna().sum())))
print("  G01_noise (E0_I0024's own) finite on %d rows" % int(ba["G01_noise"].notna().sum()))
# HOME provenance: the flag used is the champion frame's tm_is_home.  It is verified IDENTICAL to
# D104's own venue determination (E1_I0030/_player_frame.parquet) on all 13,879 champion rows, and
# E0_I0024's is_home is identical to both.  Exactly one team is flagged home in each of 743 games.
_d104 = pd.read_parquet(os.path.join(EXP, r"E1_I0030_home_advantage_accounting\_player_frame.parquet"))
_d104["game_id"] = _d104["game_id"].astype(str)
_h = _d104[K + ["is_home"]].rename(columns={"is_home": "_d104_home"}).merge(
    ba[K + ["is_home", "tm_is_home"]], on=K, how="inner")
_hc = _h[_h["tm_is_home"].notna()]
print("  HOME provenance: tm_is_home present on %d rows and == D104's is_home on %.6f of them ; "
      "E0_I0024 is_home == D104 on %.6f of all %d rows"
      % (len(_hc),
         float((_hc["_d104_home"].astype(float) == _hc["tm_is_home"].astype(float)).mean()),
         float((_h["_d104_home"].astype(float) == _h["is_home"].astype(float)).mean()), len(_h)))

hdr("2. ladder on the base universe")
LP = json.load(open(os.path.join(EXP, r"E1_I0027_reference_ladder\_prereg.json"), encoding="utf-8"))
for t, c in LP["canon"].items():
    RL.CANON[t].update({k: c[k] for k in ("mode", "half_life", "shrink", "k", "floor", "source")})
assert RL.ladder_hash() == LP["sha256"], "LADDER SPEC DOES NOT MATCH D101's PUBLISHED HASH"
print("  refladder.ladder_hash() = %s  MATCHES D101" % RL.ladder_hash())

rung, meta = {}, {}
for t in TARGETS:
    rung[t], meta[t] = RL.ladder(ba, t, date_col="game_date", scored_seasons=SCORED)
    print("  %-8s R4 finite on %d rows ; grand_fallback_rows=%d"
          % (t, int(np.isfinite(rung[t]["R4_RICH_LOOKUP"]).sum()), meta[t]["grand_fallback_rows"]))
f = meta["pts"]["frame"]
for t in TARGETS:
    assert (meta[t]["frame"].index == f.index).all()

season = f["season"].to_numpy()

hdr("3. estimator variants (hyperparameters IMPORTED from refladder.CANON)")
rng = np.random.default_rng(PLACEBO_SEED)
PL_HL = {t: float(rng.choice(RL.HALF_LIFE_GRID)) for t in TARGETS}
PL_K = {t: float(rng.choice([0.0, 0.5, 1.0, 2.0])) for t in TARGETS}
print("  placebo hl %s ; placebo k %s" % (PL_HL, PL_K))
CFG = {}
for t in TARGETS:
    CFG[("naive", t)] = cfg_naive(t)
    CFG[("hl", t)] = cfg_from_canon(t, True, False)
    CFG[("shr", t)] = cfg_from_canon(t, False, True)
    CFG[("full", t)] = cfg_from_canon(t, True, True)
    CFG[("p_hl", t)] = cfg_from_canon(t, False, False, hl_override=PL_HL[t])
    CFG[("p_shr", t)] = cfg_from_canon(t, False, True, k_override=PL_K[t])
    CFG[("p_full", t)] = dict(mode="equal", half_life=PL_HL[t], shrink="prior_season",
                              k=PL_K[t], floor=0.0)
est = {kv: estimate(f, kv[1], c) for kv, c in CFG.items()}
for t in TARGETS:
    d = np.nanmax(np.abs(rung[t]["R2_EWMA_TUNED"].to_numpy(float) - est[("full", t)]))
    print("  %-8s |cfg_full - R2_EWMA_TUNED|max = %.3e" % (t, d))

hdr("4. assemble")
work = pd.DataFrame(index=f.index)
for c, src in (("season", season), ("player_id", f["player_id"].to_numpy()),
               ("game_id", f["game_id"].to_numpy()), ("team_id", f["team_id"].to_numpy()),
               ("opp_team_id", f["opp_team_id"].to_numpy())):
    work[c] = src
work["groups"] = (f["season"].astype(str) + "_" + f["player_id"].astype(str)).to_numpy()
work["game_key"] = (f["season"].astype(str) + "_" + f["game_id"].astype(str)).to_numpy()
for c, out_c in (("pl_games_prior", "n_prior"), ("pl_min_mean5", "min5"),
                 ("O01_own_usg_pg", "usg"), ("P01_c04_prevgame", "P01"), ("G01_noise", "G01"),
                 ("A10_opp_defrtg", "DEF"), ("is_home", "HOME")):
    work[out_c] = pd.to_numeric(f[c], errors="coerce").to_numpy(float)

cp = pd.to_numeric(f["pts__pred_point"], errors="coerce").to_numpy(float)
cm = pd.to_numeric(f["minutes__pred_point"], errors="coerce").to_numpy(float)
cf_ = pd.to_numeric(f["fga__pred_point"], errors="coerce").to_numpy(float)
with np.errstate(invalid="ignore", divide="ignore"):
    cppm = np.where(cm > 0, cp / cm, np.nan)
champ = {"pts": cp, "minutes": cm, "fga": cf_, "ppm": cppm}
for t in TARGETS:
    work["y_%s" % t] = RL.target_series(f, t)
    work["champ_%s" % t] = champ[t]
    work["R4_%s" % t] = rung[t]["R4_RICH_LOOKUP"].to_numpy(float)
    work["fbl_%s" % t] = pd.to_numeric(f[FALLBACK_COL[t]], errors="coerce").to_numpy(float)
    for name in ("naive", "hl", "shr", "full", "p_hl", "p_shr", "p_full"):
        work["e_%s_%s" % (name, t)] = est[(name, t)]

common = np.isin(season, SCORED)
print("  seasons scored           : %d" % common.sum())
for t in TARGETS:
    for pre in ("y_", "champ_", "R4_", "e_full_", "e_naive_", "e_p_full_", "fbl_"):
        common &= np.isfinite(work["%s%s" % (pre, t)].to_numpy(float))
print("  + finite y/champ/R4/est  : %d   <-- THE COMMON SCORED ROW SET" % common.sum())
work["COMMON"] = common
work["DECISION"] = common & (work["n_prior"].to_numpy(float) >= 8) & \
                   (work["min5"].to_numpy(float) >= 24)
print("  DECISION stratum         : %d" % int(work["DECISION"].sum()))
print("  by season                : %s"
      % pd.Series(season[common]).value_counts().sort_index().to_dict())
print("  clusters (season_player) : %d" % pd.unique(work.loc[common, "groups"]).size)
print("\n  FEATURE COVERAGE inside the common set (zero-correction rule applies elsewhere):")
for c in ("usg", "P01", "DEF", "HOME", "G01"):
    v = work[c].to_numpy(float)
    print("    %-5s finite %5d / %5d (%.1f%%)"
          % (c, int((np.isfinite(v) & common).sum()), int(common.sum()),
             100.0 * (np.isfinite(v) & common).sum() / common.sum()))

hdr("5. routed populations")
for t in TARGETS:
    fl = work["fbl_%s" % t].to_numpy(float)
    n2 = int(((fl == 2) & common).sum())
    n3 = int(((fl == 3) & common).sum())
    sd = float(np.nanstd(champ[t][(fl == 2) & common])) if n2 else float("nan")
    p01 = int((np.isfinite(work["P01"].to_numpy(float)) & (fl == 2) & common).sum())
    dfn = int((np.isfinite(work["DEF"].to_numpy(float)) & (fl == 2) & common).sum())
    print("  %-8s fbl==2 %4d (%.2f%%)  fbl==3 %3d  champ sd on fbl==2 %.4f  "
          "P01 there %d  DEF there %d" % (t, n2, 100.0 * n2 / common.sum(), n3, sd, p01, dfn))

hdr("6. placebo route population, frozen before any statistic")
prng = np.random.default_rng(PLACEBO_SEED + 7)
for t in TARGETS:
    fl = work["fbl_%s" % t].to_numpy(float)
    real = (fl == 2) & common
    pool = np.flatnonzero(common & (fl == 0))
    pick = prng.choice(pool, size=int(real.sum()), replace=False)
    m = np.zeros(len(work), bool)
    m[pick] = True
    work["proute_%s" % t] = m
    print("  %-8s placebo-routed %d random NON-fallback rows" % (t, int(m.sum())))

hdr("7. placebo defence (entity swap across opponents within season) and placebo home")
prng2 = np.random.default_rng(PLACEBO_SEED + 11)
pdef = np.full(len(work), np.nan)
for s in SCORED:
    ms = (season == s) & np.isfinite(work["DEF"].to_numpy(float))
    opp = work.loc[ms, "opp_team_id"].astype(str).to_numpy()
    uo = pd.unique(opp)
    perm = prng2.permutation(len(uo))
    mapping = dict(zip(uo, uo[perm]))
    # value of the SWAPPED opponent for the same game where available, else that opponent's mean
    src = work.loc[ms].assign(_o=opp)
    means = src.groupby("_o")["DEF"].mean()
    pdef[np.flatnonzero(ms)] = [means.get(mapping[o], np.nan) for o in opp]
work["pDEF"] = pdef
print("  placebo DEF finite on %d rows ; corr with real DEF = %.6f"
      % (int(np.isfinite(pdef).sum()),
         float(pd.Series(pdef).corr(work["DEF"]))))

prng3 = np.random.default_rng(PLACEBO_SEED + 13)
phome = np.full(len(work), np.nan)
gk = work["game_key"].to_numpy()
tm = work["team_id"].astype(str).to_numpy()
for g in pd.unique(gk):
    idx = np.flatnonzero(gk == g)
    teams = pd.unique(tm[idx])
    pick = teams[prng3.integers(0, len(teams))]
    phome[idx] = (tm[idx] == pick).astype(float)
work["pHOME"] = phome
print("  placebo HOME: mean %.4f (real %.4f) ; agreement with real %.4f"
      % (float(np.nanmean(phome)), float(np.nanmean(work["HOME"].to_numpy(float))),
         float(np.nanmean((phome == work["HOME"].to_numpy(float)).astype(float)))))

work.to_parquet(os.path.join(OUT, "_work.parquet"))
json.dump({"placebo_half_lives": PL_HL, "placebo_k": PL_K,
           "canon": {t: {k: RL.CANON[t][k] for k in ("mode", "half_life", "shrink", "k", "floor")}
                     for t in TARGETS},
           "ladder_hash": RL.ladder_hash(),
           "n_base_universe": int(len(work)),
           "n_common": int(common.sum()), "n_decision": int(work["DECISION"].sum()),
           "n_clusters": int(pd.unique(work.loc[common, "groups"]).size),
           "a10_teamgame_join_max_abs_diff_vs_playerjoin": float(d),
           "feature_coverage": {c: int((np.isfinite(work[c].to_numpy(float)) & common).sum())
                                for c in ("usg", "P01", "DEF", "HOME", "G01")},
           "routed_counts": {t: int(((work["fbl_%s" % t].to_numpy(float) == 2) & common).sum())
                             for t in TARGETS}},
          open(os.path.join(OUT, "_s06.json"), "w", encoding="utf-8"), indent=1)
print("\nwrote _work.parquet %s and _s06.json" % (work.shape,))
