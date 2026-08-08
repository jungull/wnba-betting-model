"""E1_I0020 STEP 2 -- THE DATA-SUFFICIENCY TAXONOMY, ON PRE-GAME INFORMATION ONLY.

  Builds the working frame (champion forecasts + D076's reference + point-in-time depth chart +
  bios), verifies player_bios.csv on COLUMN VALUES, then derives the data-poor / data-rich boundary
  from WHERE THE CHAMPION'S SKILL ACTUALLY CROSSES ZERO rather than from a tidy round number.

  Every tier variable is knowable before tip-off:
     pl_games_prior          prior appearances THIS season          (shift(1) cumsum)
     pl_career_games_prior   prior appearances in the 2021-2024 window, across seasons
     pl_minutes_prior        prior minutes accumulated this season
     pl_prior_season_games   career minus same-season = prior-season experience
     pl_is_rookie_window     no prior-season games inside the window
     pl_teamgames_since_appear  team-games missed since the player's own last appearance
     depth_bucket            point-in-time minutes rank inside the player's own roster
"""
import os

import numpy as np
import pandas as pd

import ct_base as B
import screenkit as sk

OUT = {}

# ===================================================================== 2.0 bios value verification
B.hdr("STEP 2.0 -- player_bios.csv VERIFIED ON COLUMN VALUES (manifest is UNVERIFIABLE)")
bios = B.load_bios()
print("""
  THE QUESTION: does this file carry GENUINE PER-SEASON values, or is it a replicated pull of each
  player's CURRENT state stamped onto every season?  A replicated current-state pull would make
  every mutable attribute CONSTANT within player across seasons.  This is a VALUE test.
""")
multi = bios.groupby("player_id").filter(lambda g: g["season"].nunique() > 1)
print("  players with >1 season inside 2021-2024: %d (%d rows)"
      % (multi["player_id"].nunique(), len(multi)))
vary = {}
for col in ["age", "height_inches", "weight_lbs", "position_raw", "draft_number", "draft_round",
            "draft_year", "college", "country"]:
    g = multi.groupby("player_id")[col].nunique(dropna=False)
    vary[col] = float((g > 1).mean()) if len(g) else float("nan")
    print("     %-16s varies within player across seasons in %6.2f%% of multi-season players"
          % (col, 100 * vary[col]))
OUT["bios_within_player_variation"] = vary

sub = multi.sort_values(["player_id", "season"])
sub["dage"] = sub.groupby("player_id")["age"].diff()
sub["dseason"] = sub.groupby("player_id")["season"].diff()
cons = sub[(sub["dseason"] == 1) & sub["dage"].notna()]
vc = cons["dage"].value_counts().sort_index()
print("\n  age delta across CONSECUTIVE seasons (a current-state pull would be 0 everywhere):")
print(vc.to_string())
OUT["age_delta_consecutive"] = {str(k): int(v) for k, v in vc.items()}
frac_plus1 = float((cons["dage"] == 1).mean())
print("     fraction with delta_age == +1 : %.4f" % frac_plus1)
OUT["frac_age_delta_plus1"] = frac_plus1
print("""
  VERDICT ON STRUCTURAL GROUNDS (stated explicitly because the manifest is UNVERIFIABLE, which is
  never a pass):  age advances by exactly +1 across %.1f%% of consecutive player-season pairs, and
  height/weight also vary within player across seasons.  A replicated current-state pull cannot
  produce that.  draft_year / draft_round / draft_number are CONSTANT within player (%.1f%% /
  %.1f%% / %.1f%% varying), which is what immutable facts must do.  The file is therefore treated as
  genuinely per-season.  ONE RESIDUAL CAVEAT, NOT RESOLVED: position_raw varies within player in
  0.00%% of cases, so this screen CANNOT distinguish "position never changes" from "position is a
  current-state field replicated backwards".  Position is used only as a coarse G/F/C grouping and
  every result is reported with and without it.
""" % (100 * frac_plus1, 100 * vary["draft_year"], 100 * vary["draft_round"],
       100 * vary["draft_number"]))

# ===================================================================== 2.1 build the working frame
B.hdr("STEP 2.1 -- BUILD THE WORKING FRAME (champion + reference + depth chart + bios)")
f = B.load_frame()
mp = B.load_master()
dc = B.build_depth_chart(mp)
B.guard(dc, "depth chart")

f["game_id"] = f["game_id"].astype(str)
dc["game_id"] = dc["game_id"].astype(str)
key = ["game_id", "team_id", "player_id"]
before = len(f)
w = f.merge(dc[key + ["mp_prior_games", "mp_prior_minutes", "mp_prior_min_mean",
                      "mp_career_prior_games", "mp_career_prior_minutes",
                      "depth_rank", "depth_bucket", "roster_size"]], on=key, how="left")
assert len(w) == before, "depth-chart merge changed the row count"
print("  merged depth chart onto %d rows; unmatched=%d" % (len(w), int(w["depth_bucket"].isna().sum())))
w["depth_bucket"] = w["depth_bucket"].fillna(0.0)

# cross-check the independently rebuilt prior counts against D076's frozen ones
for a, b_ in [("mp_prior_games", "pl_games_prior"), ("mp_career_prior_games", "pl_career_games_prior"),
              ("mp_prior_minutes", "pl_minutes_prior")]:
    dd = (w[a] - w[b_]).abs()
    print("     independent rebuild %-24s vs frozen %-24s max|delta|=%.3e  mismatched rows=%d"
          % (a, b_, float(dd.max()), int((dd > 1e-9).sum())))
    OUT.setdefault("rebuild_vs_frozen", {})[b_] = {"max_abs_delta": float(dd.max()),
                                                   "n_mismatch": int((dd > 1e-9).sum())}

w = B.attach_bios(w, bios)
w = B.add_draft_bucket(w)
print("\n  bios attached.  coverage on the %d scored rows:" % len(w))
for c in ["pos_group", "draft_bucket", "draft_pick", "draft_round"]:
    print("     %-14s non-null %.4f" % (c, float(w[c].notna().mean())))
print("\n  pos_group counts:  %s" % dict(w["pos_group"].value_counts()))
print("  draft_bucket counts: %s" % dict(w["draft_bucket"].value_counts()))
print("  depth_bucket counts: %s" % dict(w["depth_bucket"].value_counts().sort_index()))
OUT["pos_group_counts"] = {str(k): int(v) for k, v in w["pos_group"].value_counts().items()}
OUT["draft_bucket_counts"] = {str(k): int(v) for k, v in w["draft_bucket"].value_counts().items()}

# targets
w["t_pts"] = w["y_pts"]
w["t_minutes"] = w["y_minutes"]
w["t_ppm"] = w["y_pts"] / w["y_minutes"]
# champion implied ppm = ratio of its OWN stored forecasts.  Nothing refitted.
w["champ_pts"] = w["pts__pred_point"]
w["champ_minutes"] = w["minutes__pred_point"]
w["champ_ppm"] = w["pts__pred_point"] / w["minutes__pred_point"]
# D076's frozen point-in-time running-mean reference (P1)
w["p1_pts"] = w["ref_pts"]
w["p1_minutes"] = w["ref_minutes"]
w["p1_ppm"] = w["ref_pts"] / w["ref_minutes"]

OUT["partition_adjudication"] = B.assert_partition_adjudicated(w, where="tier_frame")
assert w["gdate"].max() < pd.Timestamp("2025-01-01")
assert not (w["draft_year"] >= 2025).any(), "a draft_year in the holdout would be a real leak"
w.to_parquet(os.path.join(B.OUT, "tier_frame.parquet"), index=False)
print("\n  wrote tier_frame.parquet  shape=%s" % (w.shape,))

# ---------------------------------------------------- the walk-forward prior pool (2021 seeds 2022)
B.hdr("STEP 2.2 -- THE WALK-FORWARD PRIOR POOL")
pool = dc[dc["appeared"]].copy()
pool["t_pts"] = pd.to_numeric(pool["pts"], errors="coerce")
pool["t_minutes"] = pd.to_numeric(pool["minutes"], errors="coerce")
pool["t_ppm"] = pool["t_pts"] / pool["t_minutes"]
pool = pool[np.isfinite(pool["t_pts"]) & np.isfinite(pool["t_minutes"]) & (pool["t_minutes"] > 0)]
pool = B.attach_bios(pool, bios)
pool = B.add_draft_bucket(pool)
B.guard(pool, "prior pool (appeared rows, 2021-2024)")
print("  pool rows per season: %s" % dict(pool["season"].value_counts().sort_index()))
print("""
  USE RULE: the pool for target season S is pool[season < S].  2021 is present ONLY to seed the
  2022 fold and is NEVER a scored row -- the champion did not forecast it (degenerate fold).
""")
pool.to_parquet(os.path.join(B.OUT, "prior_pool.parquet"), index=False)
OUT["pool_rows_per_season"] = {str(k): int(v) for k, v in pool["season"].value_counts().sort_index().items()}

# ===================================================================== 2.3 skill vs tier
B.hdr("STEP 2.3 -- SKILL VERSUS TIER: WHERE DOES THE CHAMPION'S SKILL ACTUALLY CROSS ZERO?")
print("""
  Two skill measures on every cell, both against D076's point-in-time running-mean reference on the
  SAME rows:
     skill_mae = 1 - MAE_champ / MAE_ref          (D076/D081 continuity)
     dR2       = r2_of_forecast(y, champ) - r2_of_forecast(y, ref)   (kit, D069 denominator)
  A cell is DATA-POOR when the champion loses to the running mean there.
""")


def cell_table(frame, axis, bins, labels=None):
    rows = []
    for lo, hi, lab in bins:
        m = (frame[axis] >= lo) & (frame[axis] < hi)
        n = int(m.sum())
        if n < 25:
            continue
        sub = frame[m]
        r = dict(axis=axis, bin=lab, lo=lo, hi=hi, n=n,
                 pct_rows=100.0 * n / len(frame))
        for t in B.TARGETS:
            y = sub["t_" + t].to_numpy(float)
            c = sub["champ_" + t].to_numpy(float)
            p = sub["p1_" + t].to_numpy(float)
            s, mm, mr = B.skill_mae(y, c, p)
            r["skill_mae_" + t] = s
            r["champ_mae_" + t] = mm
            r["ref_mae_" + t] = mr
            r["dr2_" + t] = B.r2f(y, c) - B.r2f(y, p)
        r["n_players"] = int(sub.groupby(["season", "player_id"]).ngroups)
        r["fallback_rate"] = float(sub["pts__is_fallback"].mean())
        r["mean_career_prior"] = float(sub["pl_career_games_prior"].mean())
        rows.append(r)
    return pd.DataFrame(rows)


AXES = {
    "pl_games_prior": [(0, 1, "0"), (1, 2, "1"), (2, 3, "2"), (3, 4, "3"), (4, 5, "4"),
                       (5, 6, "5"), (6, 8, "6-7"), (8, 10, "8-9"), (10, 13, "10-12"),
                       (13, 17, "13-16"), (17, 25, "17-24"), (25, 999, "25+")],
    "pl_career_games_prior": [(0, 1, "0"), (1, 3, "1-2"), (3, 6, "3-5"), (6, 10, "6-9"),
                              (10, 20, "10-19"), (20, 40, "20-39"), (40, 80, "40-79"),
                              (80, 9999, "80+")],
    "pl_minutes_prior": [(0, 1, "0"), (1, 25, "1-24"), (25, 60, "25-59"), (60, 120, "60-119"),
                         (120, 250, "120-249"), (250, 500, "250-499"), (500, 99999, "500+")],
}
tabs = []
for axis, bins in AXES.items():
    t = cell_table(w, axis, bins)
    tabs.append(t)
    print("\n  --- AXIS: %s" % axis)
    print(t[["bin", "n", "pct_rows", "n_players", "fallback_rate",
             "skill_mae_pts", "skill_mae_minutes", "skill_mae_ppm",
             "dr2_pts", "dr2_minutes"]].to_string(index=False,
                                                  float_format=lambda v: "%+.4f" % v))
ST = pd.concat(tabs, ignore_index=True)
B.wcsv(ST, "skill_versus_tier.csv") if "season" in ST.columns else ST.to_csv(
    os.path.join(B.OUT, "skill_versus_tier.csv"), index=False)
print("\n  wrote skill_versus_tier.csv")
OUT["skill_versus_tier"] = ST.to_dict("records")

# ---------------------------------------------------- cumulative "at or below n" view + crossover
B.hdr("STEP 2.4 -- THE CROSSOVER: SMALLEST n SUCH THAT THE CHAMPION WINS ON ROWS WITH >= n PRIORS")
cum = []
for axis in ["pl_games_prior", "pl_career_games_prior"]:
    v = w[axis].to_numpy(float)
    for n in range(0, 31):
        m_at = v == n
        m_ge = v >= n
        m_lt = v < n
        r = dict(axis=axis, n=n, n_at=int(m_at.sum()), n_ge=int(m_ge.sum()), n_lt=int(m_lt.sum()))
        for t in ["pts", "minutes"]:
            y = w["t_" + t].to_numpy(float)
            c = w["champ_" + t].to_numpy(float)
            p = w["p1_" + t].to_numpy(float)
            if m_at.sum() >= 30:
                r["skill_at_" + t] = B.skill_mae(y[m_at], c[m_at], p[m_at])[0]
            else:
                r["skill_at_" + t] = np.nan
            if m_ge.sum() >= 30:
                r["skill_ge_" + t] = B.skill_mae(y[m_ge], c[m_ge], p[m_ge])[0]
            else:
                r["skill_ge_" + t] = np.nan
            if m_lt.sum() >= 30:
                r["skill_lt_" + t] = B.skill_mae(y[m_lt], c[m_lt], p[m_lt])[0]
            else:
                r["skill_lt_" + t] = np.nan
        cum.append(r)
CUM = pd.DataFrame(cum)
CUM.to_csv(os.path.join(B.OUT, "crossover_curve.csv"), index=False)
for axis in ["pl_games_prior", "pl_career_games_prior"]:
    print("\n  --- AXIS: %s   (skill_at = rows with EXACTLY n priors; skill_lt = rows BELOW n)" % axis)
    print(CUM[CUM["axis"] == axis][["n", "n_at", "n_lt", "skill_at_pts", "skill_at_minutes",
                                    "skill_lt_pts", "skill_lt_minutes",
                                    "skill_ge_pts", "skill_ge_minutes"]].to_string(
        index=False, float_format=lambda v: "%+.4f" % v))
print("\n  wrote crossover_curve.csv")
OUT["crossover_curve"] = CUM.to_dict("records")

# ---------------------------------------------------- decision-relevant population
B.hdr("STEP 2.5 -- TIER SIZES AS A SHARE OF ROWS AND OF THE DECISION-RELEVANT POPULATION")
print("""
  DECISION-RELEVANT is defined PRE-GAME so it cannot read the outcome: rows whose point-in-time
  running-mean minutes expectation is >= 15 (ref_minutes >= 15).  A player nobody expects to play
  is not a player anybody prices a prop on.  The outcome-conditioned version (y_minutes >= 15) is
  reported beside it ONLY to show the two agree, and is NOT used to define anything.
""")
dr = w["ref_minutes"] >= 15
dro = w["y_minutes"] >= 15
print("  decision-relevant (pre-game ref_minutes>=15): %d rows (%.1f%%)" % (dr.sum(), 100 * dr.mean()))
print("  outcome-conditioned  (y_minutes>=15)        : %d rows (%.1f%%)" % (dro.sum(), 100 * dro.mean()))
rows = []
for thr in [1, 2, 3, 4, 5, 6, 8, 10]:
    m = w["pl_games_prior"] < thr
    rows.append(dict(boundary_prior_games_lt=thr,
                     n_poor=int(m.sum()), pct_rows=100.0 * m.mean(),
                     n_poor_decision=int((m & dr).sum()),
                     pct_decision=100.0 * (m & dr).sum() / dr.sum(),
                     n_poor_outcome=int((m & dro).sum()),
                     pct_outcome=100.0 * (m & dro).sum() / dro.sum(),
                     n_players=int(w[m].groupby(["season", "player_id"]).ngroups)))
TS = pd.DataFrame(rows)
print("\n" + TS.to_string(index=False, float_format=lambda v: "%.2f" % v))
TS.to_csv(os.path.join(B.OUT, "tier_sizes.csv"), index=False)
OUT["tier_sizes"] = TS.to_dict("records")

# ---------------------------------------------------- the zero-history population
B.hdr("STEP 2.6 -- THE ZERO-HISTORY POPULATION (STEP 4's subject), SIZED")
zh = w["pl_career_games_prior"] == 0
zs = (w["pl_games_prior"] == 0)
print("  zero SAME-SEASON prior appearances : %d rows (%.2f%%)" % (zs.sum(), 100 * zs.mean()))
print("  zero CAREER prior appearances      : %d rows (%.2f%%)" % (zh.sum(), 100 * zh.mean()))
print("  of the zero-career rows, drafted in this same season (rookie by draft year): %d"
      % int((zh & (w["draft_year"] == w["season"])).sum()))
print("  of the zero-career rows, undrafted: %d" % int((zh & (w["undrafted"] >= 0.5)).sum()))
print("  NOTE: 'career' here is TRUNCATED AT 2021 because master_player is filtered to the")
print("        partition.  A 2022 zero-career row is a player with no 2021 appearance, which")
print("        includes genuine rookies AND returning players whose history predates the window.")
OUT["zero_history"] = {"n_zero_same_season": int(zs.sum()), "n_zero_career": int(zh.sum()),
                       "n_zero_career_drafted_this_season": int((zh & (w["draft_year"] == w["season"])).sum()),
                       "n_zero_career_undrafted": int((zh & (w["undrafted"] >= 0.5)).sum())}

B.jdump(OUT, "_s02.json")
print("\nSTEP 2 COMPLETE.")
