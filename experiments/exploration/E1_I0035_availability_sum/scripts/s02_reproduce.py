#!/usr/bin/env python3
"""E1_I0035 s02 -- INDEPENDENT REPRODUCTION of E1_I0033's roster-arithmetic numbers.

Nothing here is taken from E1_I0033.  The frame is rebuilt from:
  * the champion arm's stored per-fold prediction parquets (the objects being described),
  * the manifest-verified contract v4 (identity cross-check + the tier-A definition),
  * the manifest-verified masters (outcomes),
  * the canonical obligation key, re-derived (contract v5 is UNVERIFIABLE and backs nothing).

ANCHOR FIRST.  D076's 13,879 appeared player-games (2022-2024, tier-A obligation set) must
reproduce EXACTLY before any new statistic is computed.  The script halts otherwise.

Then the four disputed quantities are recomputed and printed BESIDE E1_I0033's published values.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import av_base as ab  # noqa: E402

pd.set_option("display.width", 220)
F = {}

# ==========================================================================================
ab.hdr("0. THE DECLARED CONSTANT, READ FROM THE IMPLEMENTATION")
DECL = ab.declared_p_active_constant()
print("  cbs_generator.DECLARED['p_active']['point'] = %.6f" % DECL)
print("  cbs_generator.py sha256 = %s" % ab.sha256_file(os.path.join(ab.ROOT, "cbs_generator.py")))
print("  cbs_v7.py        sha256 = %s" % ab.sha256_file(os.path.join(ab.ROOT, "cbs_v7.py")))
F["declared_p_active_constant"] = DECL

# ==========================================================================================
ab.hdr("1. LOAD  (2021-2024 ONLY)")
tm = ab.load_team_master()
pm = ab.load_player_master()
print("  master_team rows   = %d   seasons %s" % (len(tm), sorted(tm['season'].unique())))
print("  master_player rows = %d   seasons %s" % (len(pm), sorted(pm['season'].unique())))

PRED_COLS = ("row_uid", "season", "pred_point", "is_fallback", "fallback_level",
             "component_id", "is_cold_start", "n_prior_games", "forecast_cutoff")
pa = ab.pick(ab.load_arm(ab.PLAYER_ARM, "p_active"), PRED_COLS, "arm/p_active")
psd = ab.pick(ab.load_arm(ab.PLAYER_ARM, "player_scoring_distribution"), PRED_COLS,
              "arm/player_scoring_distribution")
emin = ab.pick(ab.load_arm(ab.PLAYER_ARM, "e_minutes_given_active"), PRED_COLS,
               "arm/e_minutes_given_active")
print("  champion p_active rows 2021-2024 = %d" % len(pa))
print("  champion pts_hat  rows 2021-2024 = %d" % len(psd))

tp = ab.pick(ab.load_arm(ab.TEAM_ARM, "team_game_distribution"),
             ("row_uid", "season", "pred_point", "is_fallback", "fallback_level",
              "component_id", "n_prior_games"), "arm/team")
print("  team arm rows 2021-2024 = %d" % len(tp))

v4p = pd.read_parquet(os.path.join(ab.CV4, "player_game.parquet"))
v4p = v4p[v4p["season"].isin(ab.EXPLORATION_SEASONS)].copy()
ab.assert_partition(v4p, "cv4/player_game")
v4p = ab.pick(v4p, ("row_uid", "game_id", "team_id", "player_id", "season",
                    "candidate_at_cutoff", "appeared", "minutes", "pts"), "cv4/player_game")
v4t = pd.read_parquet(os.path.join(ab.CV4, "team_game.parquet"))
v4t = v4t[v4t["season"].isin(ab.EXPLORATION_SEASONS)].copy()
v4t = ab.pick(v4t, ("row_uid", "game_id", "team_id", "season"), "cv4/team_game")
print("  contract v4 player rows 2021-2024 = %d" % len(v4p))

# ==========================================================================================
ab.hdr("2. IDENTITY MAP, RECONSTRUCTED FROM cbs_obligation_key/1")
IDM = ab.reconstruct_identity(tm, pm)
xchk = v4p.merge(IDM, on="row_uid", how="left", suffixes=("", "_rec"))
n_res = int(xchk["player_id_rec"].notna().sum())
agree = int(((xchk["player_id"] == xchk["player_id_rec"])
             & (xchk["game_id"] == xchk["game_id_rec"])
             & (xchk["team_id"] == xchk["team_id_rec"])).sum())
print("  contract v4 rows                : %d" % len(v4p))
print("  reconstructed                   : %d" % n_res)
print("  agree on all three fields       : %d" % agree)
assert agree == n_res == len(v4p), "identity reconstruction is not exact on contract v4"
print("  EXACT on every shared row.")
F["identity_crosscheck"] = {"n_v4_rows": len(v4p), "n_reconstructed": n_res, "n_agree": agree,
                            "exact": True}

# ==========================================================================================
ab.hdr("3. BUILD THE CHAMPION PLAYER FRAME")
pf = pa.rename(columns={"pred_point": "p_active_hat",
                        "is_fallback": "pa_is_fallback",
                        "fallback_level": "pa_fallback_level",
                        "component_id": "pa_component",
                        "is_cold_start": "pa_is_cold",
                        "n_prior_games": "pa_n_prior"})
pf = pf.merge(psd.rename(columns={"pred_point": "pts_hat",
                                  "is_fallback": "pts_is_fallback",
                                  "fallback_level": "pts_fallback_level",
                                  "component_id": "pts_component",
                                  "is_cold_start": "pts_is_cold",
                                  "n_prior_games": "pts_n_prior"})
              .drop(columns=["season", "forecast_cutoff"]), on="row_uid", how="inner")
pf = pf.merge(emin.rename(columns={"pred_point": "min_hat"})[["row_uid", "min_hat"]],
              on="row_uid", how="left")
print("  champion rows with BOTH p_active and pts_hat: %d" % len(pf))

pf = pf.merge(IDM, on="row_uid", how="left")
n_unres = int(pf["player_id"].isna().sum())
print("  unresolved row_uid (dropped, reported): %d  (%.2f%%)"
      % (n_unres, 100.0 * n_unres / len(pf)))
F["unresolved_row_uids"] = n_unres
pf = pf[pf["player_id"].notna()].copy()
pf["player_id"] = pf["player_id"].astype(int)
pf["team_id"] = pf["team_id"].astype(int)

# realised outcomes
box = pm[["game_id", "team_id", "player_id", "player_name", "position", "starter_flag",
          "dnp_reason", "minutes", "pts", "appeared"]].copy()
pf = pf.merge(box, on=["game_id", "team_id", "player_id"], how="left")
pf["appeared"] = pf["appeared"].fillna(0).astype(int)
for c in ("minutes", "pts"):
    pf[c] = pf[c].fillna(0.0)
print("  champion rows with a realised box row: %d of %d"
      % (int(pf["minutes"].gt(0).sum()), len(pf)))

# ---- tier: EXACTLY E1_I0033's definition -- membership in the manifest-verified v4 universe
inv4 = set(v4p["row_uid"])
pf["tier_A"] = pf["row_uid"].isin(inv4)
print("  tier A rows (in contract v4) = %d" % int(pf["tier_A"].sum()))
print("  tier B rows (not in v4)      = %d" % int((~pf["tier_A"]).sum()))

# ==========================================================================================
ab.hdr("4. ANCHOR -- D076's 13,879 APPEARED PLAYER-GAMES, REPRODUCED BEFORE ANY NEW NUMBER")
a2 = int(((pf["season"].isin(ab.SCORED_SEASONS)) & (pf["appeared"] == 1)
          & pf["tier_A"]).sum())
print("  reproduced (tier-A obligation set, 2022-2024) = %d" % a2)
print("  published                                     = 13879")
assert a2 == 13879, "D076 anchor did NOT reproduce -- halting"
print("  EXACT.")
F["anchor_D076_appeared"] = {"published": 13879, "reproduced": a2, "exact": True}

# ==========================================================================================
ab.hdr("5. ROW SET RS1 -- rebuilt to E1_I0033's declared recipe")
tg = tm.merge(v4t[["row_uid", "game_id", "team_id"]], on=["game_id", "team_id"], how="left")
tg = tg.merge(tp.rename(columns={"pred_point": "A_TEAM"})[["row_uid", "A_TEAM"]],
              on="row_uid", how="left")
npl = pf.groupby(["game_id", "team_id"]).size().rename("n_champion_rows").reset_index()
tg = tg.merge(npl, on=["game_id", "team_id"], how="left")
tg["n_champion_rows"] = tg["n_champion_rows"].fillna(0).astype(int)

rs1 = ((tg["season"].isin(ab.SCORED_SEASONS))
       & (tg["season_type"] == "Regular Season")
       & tg["A_TEAM"].notna()
       & (tg["n_champion_rows"] >= 1))
TF = tg[rs1].copy().reset_index(drop=True)
print("  RS1 team-games = %d      (E1_I0033: 1392)" % len(TF))
print("  by season: %s" % TF["season"].value_counts().sort_index().to_dict())
assert len(TF) == 1392, "RS1 did not rebuild to 1392 team-games"
F["RS1"] = {"n_team_games": int(len(TF)),
            "by_season": {int(k): int(v) for k, v in
                          TF["season"].value_counts().sort_index().items()},
            "response_mean": float(TF["pts"].mean()), "response_sd": float(TF["pts"].std()),
            "SST": ab.sst_of(TF["pts"].to_numpy())}
print("  response mean %.4f  sd %.4f  SST %.4f"
      % (F["RS1"]["response_mean"], F["RS1"]["response_sd"], F["RS1"]["SST"]))

key = TF[["game_id", "team_id"]].assign(_rs1=True)
PF = pf.merge(key, on=["game_id", "team_id"], how="inner")
print("  champion rows on RS1 team-games = %d" % len(PF))

# ==========================================================================================
ab.hdr("6. THE FOUR DISPUTED NUMBERS -- MINE vs E1_I0033's")
n_tg = len(TF)
universe_per_tg = len(PF) / n_tg
realised_roster = float(PF.groupby(["game_id", "team_id"])["appeared"].sum().mean())
sum_pactive = float(PF.groupby(["game_id", "team_id"])["p_active_hat"].sum().mean())

comp = (PF.groupby("tier_A")
        .agg(n=("pts_hat", "size"),
             mean_p_active=("p_active_hat", "mean"),
             mean_pts_hat=("pts_hat", "mean"),
             appear_rate=("appeared", "mean"),
             mean_realised_pts=("pts", "mean"),
             sum_p_active=("p_active_hat", "sum"),
             sum_appeared=("appeared", "sum")).reset_index())
print(comp.to_string(index=False))

tb = comp.loc[~comp["tier_A"]].iloc[0]
ta = comp.loc[comp["tier_A"]].iloc[0]

rows = [
    ("universe rows per team-game", universe_per_tg, 14.428),
    ("realised roster per team-game", realised_roster, 9.4016),
    ("sum p_active_hat per team-game", sum_pactive, 10.3381),
    ("tier-B mean p_active_hat", float(tb["mean_p_active"]), 0.5249),
    ("tier-B realised appearance rate", float(tb["appear_rate"]), 0.1015),
    ("tier-B n rows", float(tb["n"]), 3772.0),
    ("tier-B mean pts_hat", float(tb["mean_pts_hat"]), 8.561),
    ("tier-A mean p_active_hat", float(ta["mean_p_active"]), 0.7608),
    ("tier-A realised appearance rate", float(ta["appear_rate"]), 0.7788),
    ("tier-A n rows", float(ta["n"]), 16312.0),
    ("tier-A mean pts_hat", float(ta["mean_pts_hat"]), 8.088),
]
print("\n  %-36s %14s %14s %12s" % ("quantity", "MINE", "E1_I0033", "abs diff"))
rec = []
for name, mine, theirs in rows:
    print("  %-36s %14.4f %14.4f %12.4f" % (name, mine, theirs, abs(mine - theirs)))
    rec.append({"quantity": name, "E1_I0035_mine": mine, "E1_I0033_published": theirs,
                "abs_diff": abs(mine - theirs)})
pd.DataFrame(rec).to_csv(os.path.join(ab.OUT, "reproduction_vs_E1_I0033.csv"), index=False)
F["reproduction"] = rec

# the level-bias arithmetic
excess_players = sum_pactive - realised_roster
b1 = PF.assign(c=PF["p_active_hat"] * PF["pts_hat"]).groupby(["game_id", "team_id"])["c"].sum()
TF = TF.merge(b1.rename("B1").reset_index(), on=["game_id", "team_id"], how="left")
lvl_bias = float((TF["B1"] - TF["pts"]).mean())
cond_pts = float(np.average(PF["pts_hat"], weights=PF["p_active_hat"]))
print("\n  excess p_active mass per team-game       = %.4f players" % excess_players)
print("  p_active-weighted mean pts_hat           = %.4f points" % cond_pts)
print("  excess x conditional points              = %.4f" % (excess_players * cond_pts))
print("  ACTUAL B1 level bias (mean B1 - mean pts)= %.4f   (E1_I0033: +8.139)" % lvl_bias)
print("  B1 MAE = %.6f   (E1_I0033: 18.263037)" % ab.mae(TF["pts"], TF["B1"]))
print("  A_TEAM MAE = %.6f (E1_I0033: 8.685506)" % ab.mae(TF["pts"], TF["A_TEAM"]))
F["level_bias"] = {"excess_p_active_players": excess_players,
                   "p_active_weighted_mean_pts_hat": cond_pts,
                   "product": excess_players * cond_pts,
                   "actual_B1_bias": lvl_bias,
                   "B1_MAE": ab.mae(TF["pts"], TF["B1"]),
                   "A_TEAM_MAE": ab.mae(TF["pts"], TF["A_TEAM"]),
                   "published_B1_bias": 8.139, "published_B1_MAE": 18.263037,
                   "published_A_TEAM_MAE": 8.685506}

# ==========================================================================================
ab.hdr("7. THE 0.80 QUESTION -- WHERE DOES THE DECLARED CONSTANT ACTUALLY LAND?")
PF["is_declared_const"] = (PF["pa_component"] == "p_active/declared_constant")
PF["p_active_eq_decl"] = np.isclose(PF["p_active_hat"], DECL, atol=1e-9)
print("  rows on component 'p_active/declared_constant' : %d" % int(PF["is_declared_const"].sum()))
print("  rows with p_active EXACTLY == %.3f            : %d"
      % (DECL, int(PF["p_active_eq_decl"].sum())))
print("  the two agree on every row                     : %s"
      % bool((PF["is_declared_const"] == PF["p_active_eq_decl"]).all()))

xt = pd.crosstab(PF["tier_A"], PF["is_declared_const"])
print("\n  tier_A x is_declared_constant:")
print(xt.to_string())

lv = (PF.groupby(["tier_A", "pa_fallback_level"])
      .agg(n=("p_active_hat", "size"), mean_p_active=("p_active_hat", "mean"),
           appear_rate=("appeared", "mean"), mean_pts_hat=("pts_hat", "mean"),
           sum_p_active=("p_active_hat", "sum"), sum_appeared=("appeared", "sum")).reset_index())
lv["excess_players"] = lv["sum_p_active"] - lv["sum_appeared"]
lv["excess_per_team_game"] = lv["excess_players"] / n_tg
print("\n  by tier x p_active fallback level (RS1 rows):")
print(lv.to_string(index=False))
lv.to_csv(os.path.join(ab.OUT, "p_active_by_tier_and_fallback_level.csv"), index=False)
F["by_tier_and_level"] = lv.to_dict("records")

print("\n  E1_I0033's WHICH_LEVEL_WINS.md says tier-B rows receive 'a declared-constant")
print("  p_active of 0.80'.  Its own NOTES.md says the tier-B MEAN is 0.5249.  Both cannot")
print("  describe the same rows.  Resolved above: %.1f%% of tier-B rows carry the 0.80"
      % (100.0 * PF.loc[~PF["tier_A"], "is_declared_const"].mean()))
print("  constant; the rest carry a FITTED logistic value.")
F["tier_B_share_declared_constant"] = float(PF.loc[~PF["tier_A"], "is_declared_const"].mean())
F["tier_A_share_declared_constant"] = float(PF.loc[PF["tier_A"], "is_declared_const"].mean())

# where the excess mass actually sits
grp = PF.assign(band=np.where(PF["is_declared_const"], "declared_constant_0.80",
                              "fitted_logistic"))
exc = (grp.groupby(["tier_A", "band"])
       .agg(n=("p_active_hat", "size"), sum_p_active=("p_active_hat", "sum"),
            sum_appeared=("appeared", "sum"), mean_p=("p_active_hat", "mean"),
            appear_rate=("appeared", "mean")).reset_index())
exc["excess_per_team_game"] = (exc["sum_p_active"] - exc["sum_appeared"]) / n_tg
tot_exc = float(exc["excess_per_team_game"].sum())
exc["share_of_excess"] = exc["excess_per_team_game"] / tot_exc
print("\n  WHERE THE EXCESS AVAILABILITY MASS SITS (total %.4f players/team-game):" % tot_exc)
print(exc.to_string(index=False))
exc.to_csv(os.path.join(ab.OUT, "excess_mass_attribution.csv"), index=False)
F["excess_attribution"] = exc.to_dict("records")

# ==========================================================================================
ab.hdr("8. D090's PER-PLAYER VERDICT -- RECOMPUTED ON THE SAME ROWS")
for lbl, sub in (("ALL RS1 rows", PF), ("tier A only", PF[PF["tier_A"]]),
                 ("tier B only", PF[~PF["tier_A"]])):
    y = sub["appeared"].to_numpy(float); p = sub["p_active_hat"].to_numpy(float)
    print("  %-14s n=%6d  base=%.4f  mean_p=%.4f  AUC=%.4f  Brier=%.4f  logloss=%.4f"
          % (lbl, len(sub), y.mean(), p.mean(), ab.auc(y, p), ab.brier(y, p), ab.logloss(y, p)))
    F.setdefault("per_player_calibration", {})[lbl] = {
        "n": int(len(sub)), "base_rate": float(y.mean()), "mean_p": float(p.mean()),
        "AUC": ab.auc(y, p), "brier": ab.brier(y, p), "logloss": ab.logloss(y, p)}

print("\n  D090 published AUC 0.9016 on the per-player screen.  The AUC on ALL RS1 rows above")
print("  is the discrimination number; the mean_p vs base gap is the LEVEL number.  A model")
print("  can have both.")

# ==========================================================================================
ab.hdr("9. PERSIST")
PF.to_parquet(os.path.join(ab.OUT, "_player_frame.parquet"), index=False)
TF.to_parquet(os.path.join(ab.OUT, "_team_frame.parquet"), index=False)
pf.to_parquet(os.path.join(ab.OUT, "_player_frame_all_seasons.parquet"), index=False)
open(os.path.join(ab.OUT, "_s02.json"), "w", encoding="utf-8").write(
    json.dumps(ab.jsonable(F), indent=2))
print("  wrote _player_frame.parquet (%d rows), _team_frame.parquet (%d rows), _s02.json"
      % (len(PF), len(TF)))
print("\nDONE s02")
