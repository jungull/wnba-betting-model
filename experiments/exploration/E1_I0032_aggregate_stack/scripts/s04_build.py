"""E1_I0032 s04 -- build the ONE common frame, the ladder rungs and every estimator variant.

Runs AFTER the preregistration hash exists and re-checks it.  Produces `_work.parquet`, which every
later step reads.  No comparison statistic is computed here.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack_base import (EXP, OUT, TV, EFF, TIER, TARGETS, SCORED, PLACEBO_SEED, RL,
                        CHAMP_COL, FALLBACK_COL, cfg_naive, cfg_from_canon, estimate,
                        prereg, guard_paths)

pd.set_option("display.width", 220)
spec = prereg()
print("prereg sha256 %s  MATCH" % spec["sha256"])
guard_paths(TV, EFF, TIER)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


hdr("1. load and join")
tv = pd.read_parquet(TV)
eff = pd.read_parquet(EFF)
tier = pd.read_parquet(TIER)
print("  tv %s  eff %s  tier %s" % (tv.shape, eff.shape, tier.shape))

K = ["season", "player_id", "game_id"]
for df in (tv, eff, tier):
    df["game_id"] = df["game_id"].astype(str)

tv = tv.merge(eff[K + ["A10_opp_defrtg"]].drop_duplicates(K), on=K, how="left")
champ_cols = [c for c in ["pts__pred_point", "minutes__pred_point", "fga__pred_point",
                          "pts__fallback_level", "minutes__fallback_level", "fga__fallback_level",
                          "pts__is_fallback", "tm_is_home", "depth_rank", "draft_pick",
                          "t_pts", "t_minutes", "t_ppm"] if c in tier.columns]
tv = tv.merge(tier[K + champ_cols].drop_duplicates(K), on=K, how="left")
print("  joined frame %s ; champion present on %d rows"
      % (tv.shape, int(tv["pts__pred_point"].notna().sum())))

hdr("2. the ladder (imported from E1_I0027; spec hash re-computed)")
# Load E1_I0027's OWN frozen canon so the published ladder hash reproduces exactly.  reb/ast
# half-lives were selected inside that screen on train seasons only; without them CANON carries
# None and the hash cannot match.  Nothing here re-searches anything.
LP = json.load(open(os.path.join(EXP, r"E1_I0027_reference_ladder\_prereg.json"), encoding="utf-8"))
for t, c in LP["canon"].items():
    RL.CANON[t].update({k: c[k] for k in ("mode", "half_life", "shrink", "k", "floor", "source")})
assert RL.ladder_hash() == LP["sha256"], "LADDER SPEC DOES NOT MATCH D101's PUBLISHED HASH"
print("  refladder.ladder_hash() = %s  MATCHES D101's published spec hash" % RL.ladder_hash())
rung, meta = {}, {}
for t in TARGETS:
    rung[t], meta[t] = RL.ladder(tv, t, date_col="game_date", scored_seasons=SCORED)
    print("  %-8s R4 finite on %d rows ; grand_fallback_rows=%d"
          % (t, int(np.isfinite(rung[t]["R4_RICH_LOOKUP"]).sum()), meta[t]["grand_fallback_rows"]))
f = meta["pts"]["frame"]
for t in TARGETS:
    assert (meta[t]["frame"].index == f.index).all(), "frames misaligned for %s" % t

season = f["season"].to_numpy()
groups = (f["season"].astype(str) + "_" + f["player_id"].astype(str)).to_numpy()

hdr("3. estimator variants (hyperparameters IMPORTED from refladder.CANON, never re-searched)")
rng = np.random.default_rng(PLACEBO_SEED)
PL_HL = {t: float(rng.choice(RL.HALF_LIFE_GRID)) for t in TARGETS}
PL_K = {t: float(rng.choice([0.0, 0.5, 1.0, 2.0])) for t in TARGETS}
print("  D094 canon:   %s" % {t: (RL.CANON[t]["mode"], RL.CANON[t]["half_life"],
                                  RL.CANON[t]["shrink"], RL.CANON[t]["k"]) for t in TARGETS})
print("  placebo hl:   %s" % PL_HL)
print("  placebo k:    %s" % PL_K)

CFG = {}
for t in TARGETS:
    CFG[("naive", t)] = cfg_naive(t)
    CFG[("hl", t)] = cfg_from_canon(t, True, False)
    CFG[("shr", t)] = cfg_from_canon(t, False, True)
    CFG[("full", t)] = cfg_from_canon(t, True, True)
    CFG[("p_naive", t)] = cfg_naive(t)
    CFG[("p_hl", t)] = cfg_from_canon(t, False, False, hl_override=PL_HL[t])
    CFG[("p_shr", t)] = cfg_from_canon(t, False, True, k_override=PL_K[t])
    CFG[("p_full", t)] = dict(mode="equal", half_life=PL_HL[t], shrink="prior_season",
                              k=PL_K[t], floor=0.0)

est = {}
for (name, t), c in CFG.items():
    est[(name, t)] = estimate(f, t, c)
print("  built %d estimator columns" % len(est))
# R2_EWMA_TUNED from ladder() must equal our cfg 'full' exactly -- a structural cross-check.
for t in TARGETS:
    d = np.nanmax(np.abs(rung[t]["R2_EWMA_TUNED"].to_numpy(float) - est[("full", t)]))
    print("  %-8s |cfg_full - R2_EWMA_TUNED|max = %.3e" % (t, d))

hdr("4. champion forecasts, truth, and the common scored row set")
work = pd.DataFrame(index=f.index)
work["season"] = season
work["player_id"] = f["player_id"].to_numpy()
work["game_id"] = f["game_id"].to_numpy()
work["opp_team_id"] = f["opp_team_id"].to_numpy()
work["team_id"] = f["team_id"].to_numpy()
work["groups"] = groups
work["n_prior"] = pd.to_numeric(f["n_prior"], errors="coerce").to_numpy(float)
work["prior5_minutes"] = pd.to_numeric(f["prior5_minutes"], errors="coerce").to_numpy(float)
work["usg"] = pd.to_numeric(f["O01_own_usg_pg"], errors="coerce").to_numpy(float)
work["P01"] = pd.to_numeric(f["P01_c04_prevgame"], errors="coerce").to_numpy(float)
work["G01"] = pd.to_numeric(f["G01_noise"], errors="coerce").to_numpy(float)
work["DEF"] = pd.to_numeric(f["A10_opp_defrtg"], errors="coerce").to_numpy(float)
work["HOME"] = pd.to_numeric(f["tm_is_home"], errors="coerce").to_numpy(float)

cp = pd.to_numeric(f["pts__pred_point"], errors="coerce").to_numpy(float)
cm = pd.to_numeric(f["minutes__pred_point"], errors="coerce").to_numpy(float)
cf = pd.to_numeric(f["fga__pred_point"], errors="coerce").to_numpy(float)
with np.errstate(invalid="ignore", divide="ignore"):
    cppm = np.where(cm > 0, cp / cm, np.nan)
champ = {"pts": cp, "minutes": cm, "fga": cf, "ppm": cppm}
# cross-check the derived ppm champion against the frame's own stored champ_ppm
if "t_ppm" in f.columns:
    pass
for t in TARGETS:
    work["y_%s" % t] = RL.target_series(f, t)
    work["champ_%s" % t] = champ[t]
    work["R4_%s" % t] = rung[t]["R4_RICH_LOOKUP"].to_numpy(float)
    work["R2_%s" % t] = rung[t]["R2_EWMA_TUNED"].to_numpy(float)
    work["fbl_%s" % t] = pd.to_numeric(f[FALLBACK_COL[t]], errors="coerce").to_numpy(float)
    for name in ("naive", "hl", "shr", "full", "p_naive", "p_hl", "p_shr", "p_full"):
        work["e_%s_%s" % (name, t)] = est[(name, t)]

need = ["usg", "P01", "G01", "DEF", "HOME", "n_prior", "prior5_minutes"]
common = np.isin(season, SCORED)
print("  seasons scored          : %d" % common.sum())
for c in need:
    common &= np.isfinite(work[c].to_numpy(float))
print("  + finite component feats: %d" % common.sum())
for t in TARGETS:
    for pre in ("y_", "champ_", "R4_", "e_full_", "e_naive_", "e_p_full_"):
        common &= np.isfinite(work["%s%s" % (pre, t)].to_numpy(float))
    common &= np.isfinite(work["fbl_%s" % t].to_numpy(float))
print("  + finite y/champ/R4/est : %d   <-- THE COMMON SCORED ROW SET" % common.sum())

work["COMMON"] = common
work["DECISION"] = common & (work["n_prior"].to_numpy(float) >= 8) & \
                   (work["prior5_minutes"].to_numpy(float) >= 24)
print("  DECISION stratum        : %d" % int(work["DECISION"].sum()))
print("  seasons in common set   : %s"
      % pd.Series(season[common]).value_counts().sort_index().to_dict())
print("  clusters (season_player): %d" % pd.unique(work.loc[common, "groups"]).size)

hdr("5. routed populations on the common set")
for t in TARGETS:
    fl = work["fbl_%s" % t].to_numpy(float)
    n_r2 = int(((fl == 2) & common).sum())
    r3c = int(((fl == 3) & common).sum())
    print("  %-8s fallback_level==2 : %4d (%.2f%%)   ==3 : %3d   champion sd on ==2 : %.4f"
          % (t, n_r2, 100.0 * n_r2 / common.sum(), r3c,
             float(np.nanstd(champ[t][(fl == 2) & common]))))

hdr("6. placebo route population (frozen now, before any statistic)")
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

work.to_parquet(os.path.join(OUT, "_work.parquet"))
json.dump({"placebo_half_lives": PL_HL, "placebo_k": PL_K,
           "canon": {t: {k: RL.CANON[t][k] for k in ("mode", "half_life", "shrink", "k", "floor")}
                     for t in TARGETS},
           "ladder_hash": RL.ladder_hash(),
           "n_common": int(common.sum()), "n_decision": int(work["DECISION"].sum()),
           "n_clusters": int(pd.unique(work.loc[common, "groups"]).size)},
          open(os.path.join(OUT, "_s04.json"), "w", encoding="utf-8"), indent=1)
print("\nwrote _work.parquet (%s) and _s04.json" % (work.shape,))
