#!/usr/bin/env python3
"""E1_I0045 s01 -- build the frames, REPRODUCE THE ANCHORS, and derive the currency features.

ANCHOR FIRST, by an independent path.  Nothing is imported from E1_I0035.  Four published values
must reproduce before any new statistic is computed:

  * D076's 13,879 appeared player-games (the programme's standing anchor)
  * E1_I0033/E1_I0035's 14.4282 universe rows and 9.4016 realised roster per team-game
  * E1_I0035's champion bottom-up team MAE 18.263037
  * E1_I0035's champion player Brier 0.1302 / AUC 0.9026 on RS1P

The currency features are then derived from `master_player` ONLY, admitted through the same
availability bound the contract uses (+36h after tip), and every one is compared to the row's own
`forecast_cutoff` with a STRICT inequality.  No transaction wire, no bios, no roster_asof: those
are UNVERIFIABLE (no manifest) or artifact-granular and may not back a number.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rc_base as rb  # noqa: E402

pd.set_option("display.width", 240)
F = {}

# =========================================================================================
rb.hdr("1. LOAD  (2021-2024 ONLY; 2025/2026 never enumerated)")
tm = rb.load_team_master()
pm = rb.load_player_master()
print("  master_team rows   = %d   seasons %s" % (len(tm), sorted(tm["season"].unique())))
print("  master_player rows = %d   seasons %s" % (len(pm), sorted(pm["season"].unique())))
F["input_sha256"] = {
    "master_player.parquet": rb.sha256_file(rb.MASTER_PLAYER),
    "master_team.parquet": rb.sha256_file(rb.MASTER_TEAM),
    "prediction_contract_v5.py": rb.sha256_file(os.path.join(rb.ROOT,
                                                             "prediction_contract_v5.py")),
    "cbs_generator.py": rb.sha256_file(os.path.join(rb.ROOT, "cbs_generator.py")),
}

PRED_COLS = ("row_uid", "season", "pred_point", "is_fallback", "fallback_level",
             "component_id", "is_cold_start", "n_prior_games", "forecast_cutoff")
pa = rb.pick(rb.load_arm(rb.PLAYER_ARM, "p_active"), PRED_COLS, "arm/p_active")
psd = rb.pick(rb.load_arm(rb.PLAYER_ARM, "player_scoring_distribution"), PRED_COLS,
              "arm/player_scoring_distribution")
emin = rb.pick(rb.load_arm(rb.PLAYER_ARM, "e_minutes_given_active"), PRED_COLS,
               "arm/e_minutes_given_active")
tp = rb.pick(rb.load_arm(rb.TEAM_ARM, "team_game_distribution"),
             ("row_uid", "season", "pred_point", "is_fallback", "fallback_level",
              "component_id", "n_prior_games"), "arm/team")
print("  champion p_active rows 2021-2024 = %d" % len(pa))
print("  team arm rows 2021-2024          = %d" % len(tp))

v4p = pd.read_parquet(os.path.join(rb.CV4, "player_game.parquet"))
v4p = v4p[v4p["season"].isin(rb.EXPLORATION_SEASONS)].copy()
rb.assert_partition(v4p, "cv4/player_game")
v4p = rb.pick(v4p, ("row_uid", "game_id", "team_id", "player_id", "season",
                    "candidate_at_cutoff", "appeared", "minutes", "pts"), "cv4/player_game")
v4t = pd.read_parquet(os.path.join(rb.CV4, "team_game.parquet"))
v4t = v4t[v4t["season"].isin(rb.EXPLORATION_SEASONS)].copy()
v4t = rb.pick(v4t, ("row_uid", "game_id", "team_id", "season"), "cv4/team_game")
print("  contract v4 player rows 2021-2024 = %d" % len(v4p))

# =========================================================================================
rb.hdr("2. IDENTITY MAP, RECONSTRUCTED FROM cbs_obligation_key/1")
IDM = rb.reconstruct_identity(tm, pm)
x = v4p.merge(IDM, on="row_uid", how="left", suffixes=("", "_r"))
n_res = int(x["player_id_r"].notna().sum())
agree = int(((x["player_id"] == x["player_id_r"]) & (x["game_id"] == x["game_id_r"])
             & (x["team_id"] == x["team_id_r"])).sum())
print("  v4 rows %d | reconstructed %d | agree on all three fields %d" % (len(v4p), n_res, agree))
assert agree == n_res == len(v4p), "identity reconstruction is not exact on contract v4"
print("  EXACT on every shared row.")
F["identity_crosscheck"] = {"n_v4_rows": len(v4p), "n_agree": agree, "exact": True}

# =========================================================================================
rb.hdr("3. CHAMPION PLAYER FRAME")
pf = pa.rename(columns={"pred_point": "p_active_hat", "is_fallback": "pa_is_fallback",
                        "fallback_level": "pa_fallback_level", "component_id": "pa_component",
                        "is_cold_start": "pa_is_cold", "n_prior_games": "pa_n_prior"})
pf = pf.merge(psd.rename(columns={"pred_point": "pts_hat", "is_fallback": "pts_is_fallback",
                                  "fallback_level": "pts_fallback_level",
                                  "component_id": "pts_component", "is_cold_start": "pts_is_cold",
                                  "n_prior_games": "pts_n_prior"})
              .drop(columns=["season", "forecast_cutoff"]), on="row_uid", how="inner")
pf = pf.merge(emin.rename(columns={"pred_point": "min_hat"})[["row_uid", "min_hat"]],
              on="row_uid", how="left")
pf = pf.merge(IDM, on="row_uid", how="left")
n_unres = int(pf["player_id"].isna().sum())
print("  rows with both p_active and pts_hat = %d ; unresolved row_uid = %d" % (len(pf), n_unres))
F["unresolved_row_uids"] = n_unres
pf = pf[pf["player_id"].notna()].copy()
pf["player_id"] = pf["player_id"].astype(int)
pf["team_id"] = pf["team_id"].astype(int)

box = pm[["game_id", "team_id", "player_id", "player_name", "position", "starter_flag",
          "dnp_reason", "minutes", "pts", "appeared", "game_date"]].copy()
pf = pf.merge(box, on=["game_id", "team_id", "player_id"], how="left")
pf["appeared"] = pf["appeared"].fillna(0).astype(int)
for c in ("minutes", "pts"):
    pf[c] = pf[c].fillna(0.0)

inv4 = set(v4p["row_uid"])
pf["tier_A"] = pf["row_uid"].isin(inv4)
print("  tier A (in contract v4) = %d   tier B = %d"
      % (int(pf["tier_A"].sum()), int((~pf["tier_A"]).sum())))

# game_date for rows with no box row: take it from the team schedule
gdates = tm[["game_id", "game_date"]].drop_duplicates().rename(columns={"game_date": "_gd"})
pf = pf.merge(gdates, on="game_id", how="left")
pf["game_date"] = pf["game_date"].fillna(pf["_gd"])
pf = pf.drop(columns=["_gd"])
assert pf["game_date"].notna().all(), "a champion row has no game date"

# =========================================================================================
rb.hdr("4. ANCHOR 1 -- D076's 13,879 APPEARED PLAYER-GAMES, BEFORE ANY NEW NUMBER")
a2 = int(((pf["season"].isin(rb.SCORED_SEASONS)) & (pf["appeared"] == 1) & pf["tier_A"]).sum())
print("  reproduced (tier-A obligation set, 2022-2024) = %d   published = 13879" % a2)
assert a2 == 13879, "D076 anchor did NOT reproduce -- halting"
print("  EXACT.")
F["anchor_D076"] = {"published": 13879, "reproduced": a2, "exact": True}

# =========================================================================================
rb.hdr("5. ROW SETS RS1 / RS1P  (D101: identical to E1_I0035)")
tg = tm.merge(v4t[["row_uid", "game_id", "team_id"]], on=["game_id", "team_id"], how="left")
tg = tg.merge(tp.rename(columns={"pred_point": "A_TEAM"})[["row_uid", "A_TEAM"]],
              on="row_uid", how="left")
npl = pf.groupby(["game_id", "team_id"]).size().rename("n_champion_rows").reset_index()
tg = tg.merge(npl, on=["game_id", "team_id"], how="left")
tg["n_champion_rows"] = tg["n_champion_rows"].fillna(0).astype(int)
rs1 = ((tg["season"].isin(rb.SCORED_SEASONS)) & (tg["season_type"] == "Regular Season")
       & tg["A_TEAM"].notna() & (tg["n_champion_rows"] >= 1))
TF = tg[rs1].copy().reset_index(drop=True)
assert len(TF) == 1392, "RS1 did not rebuild to 1392 team-games (got %d)" % len(TF)
SST = rb.sst_of(TF["pts"].to_numpy())
print("  RS1 team-games = %d  (E1_I0035: 1392)   SST = %.4f  (E1_I0035: 168710.4073)"
      % (len(TF), SST))
print("  by season: %s" % TF["season"].value_counts().sort_index().to_dict())
key = TF[["game_id", "team_id"]].assign(_rs1=True)
PF = pf.merge(key, on=["game_id", "team_id"], how="inner")
assert len(PF) == 20084, "RS1P is %d, expected 20084" % len(PF)
assert int(PF["tier_A"].sum()) == 16312 and int((~PF["tier_A"]).sum()) == 3772
print("  RS1P = %d   RS1P-A = %d   RS1P-B = %d"
      % (len(PF), int(PF["tier_A"].sum()), int((~PF["tier_A"]).sum())))
F["RS1"] = {"n_team_games": int(len(TF)), "SST": SST,
            "by_season": {int(k): int(v) for k, v in
                          TF["season"].value_counts().sort_index().items()}}

# =========================================================================================
rb.hdr("6. ANCHORS 2-4 -- E1_I0033 / E1_I0035 DESCRIPTIVE AND HEADLINE VALUES")
n_tg = len(TF)
uni = len(PF) / n_tg
ros = float(PF.groupby(["game_id", "team_id"])["appeared"].sum().mean())
sump = float(PF.groupby(["game_id", "team_id"])["p_active_hat"].sum().mean())
b1 = PF.assign(c=PF["p_active_hat"] * PF["pts_hat"]).groupby(["game_id", "team_id"])["c"].sum()
TF = TF.merge(b1.rename("B1").reset_index(), on=["game_id", "team_id"], how="left")
B1_MAE = rb.mae(TF["pts"], TF["B1"])
lvl = float((TF["B1"] - TF["pts"]).mean())
y = PF["appeared"].to_numpy(float); p = PF["p_active_hat"].to_numpy(float)
BR = rb.brier(y, p); AU = rb.auc(y, p); LL = rb.logloss(y, p)
mA = PF["tier_A"].to_numpy(bool)
BRA = rb.brier(y[mA], p[mA])

checks = [
    ("universe rows per team-game", uni, 14.4282, 5e-4),
    ("realised roster per team-game", ros, 9.4016, 5e-4),
    ("sum p_active per team-game", sump, 10.3381, 5e-4),
    ("B1 level bias", lvl, 8.1389, 5e-3),
    ("B1 (bottom-up) team MAE", B1_MAE, 18.263037, 1e-5),
    ("A_TEAM (top-down) team MAE", rb.mae(TF["pts"], TF["A_TEAM"]), 8.685506, 1e-5),
    ("player Brier, all RS1P", BR, 0.1302, 5e-4),
    ("player Brier, tier A", BRA, 0.0932, 5e-4),
    ("player AUC, all RS1P", AU, 0.9026, 5e-4),
    ("player log-loss, all RS1P", LL, 0.4056, 5e-4),
]
print("\n  %-34s %14s %14s %13s  %s" % ("quantity", "MINE", "PUBLISHED", "abs diff", "verdict"))
rec = []
allok = True
for nm, mine, pub, tol in checks:
    ok = abs(mine - pub) <= tol
    allok &= ok
    print("  %-34s %14.6f %14.6f %13.6f  %s"
          % (nm, mine, pub, abs(mine - pub), "CONFIRMED" if ok else "*** DISCREPANCY ***"))
    rec.append({"quantity": nm, "mine": mine, "published": pub, "abs_diff": abs(mine - pub),
                "tolerance": tol, "confirmed": bool(ok)})
pd.DataFrame(rec).to_csv(os.path.join(rb.OUT, "ANCHOR_REPRODUCTION.csv"), index=False)
F["anchors"] = rec
assert allok, "an anchor did not reproduce -- halting before any new statistic"
print("\n  ALL ANCHORS CONFIRMED.  New statistics may now be computed.")

# =========================================================================================
rb.hdr("7. CURRENCY FEATURES -- from master_player ONLY, strictly pre-cutoff")
print("  admission bound: a game's box is observable at game_date + %dh (the contract's own"
      % rb.AVAIL_LAG_HOURS)
print("  availability_bound policy).  Every feature uses a STRICT '<' against forecast_cutoff.")

cut = pd.to_datetime(pf["forecast_cutoff"], utc=True)
pf["cutoff_utc"] = cut

app = pm.loc[pm["appeared"] == 1, ["player_id", "team_id", "season", "game_date",
                                   "minutes"]].copy()
app["avail"] = (pd.to_datetime(app["game_date"]).dt.tz_localize("UTC")
                + pd.Timedelta(hours=rb.AVAIL_LAG_HOURS))
app = app.sort_values(["player_id", "avail"], kind="stable").reset_index(drop=True)
print("  admitted appearance records (minutes>0, 2021-2024) = %d" % len(app))

# per-player and per-(player,team) sorted arrays
by_p = {}
for pid, grp in app.groupby("player_id", sort=False):
    by_p[int(pid)] = (grp["avail"].to_numpy(), grp["team_id"].to_numpy(),
                      pd.to_datetime(grp["game_date"]).to_numpy(),
                      grp["season"].to_numpy(), grp["minutes"].to_numpy(float))
by_pt = {}
for (pid, tid), grp in app.groupby(["player_id", "team_id"], sort=False):
    by_pt[(int(pid), int(tid))] = (grp["avail"].to_numpy(),
                                   pd.to_datetime(grp["game_date"]).to_numpy(),
                                   grp["season"].to_numpy())
by_ps = {}
for (pid, sea), grp in app.groupby(["player_id", "season"], sort=False):
    by_ps[(int(pid), int(sea))] = (grp["avail"].to_numpy(), grp["minutes"].to_numpy(float))

n = len(pf)
last_club_date = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
last_club_season = np.full(n, -1, dtype=np.int64)
last_any_date = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
last_any_team = np.full(n, -1, dtype=np.int64)
n_prior_app_season = np.zeros(n, dtype=np.int64)
trail5_min = np.full(n, np.nan)

cuts = pf["cutoff_utc"].to_numpy()
pids = pf["player_id"].to_numpy()
tids = pf["team_id"].to_numpy()
seas = pf["season"].to_numpy()
for i in range(n):
    c = cuts[i]; pid = int(pids[i]); tid = int(tids[i]); s = int(seas[i])
    e = by_pt.get((pid, tid))
    if e is not None:
        k = int(np.searchsorted(e[0], c, side="left"))
        if k > 0:
            last_club_date[i] = e[1][k - 1]
            last_club_season[i] = int(e[2][k - 1])
    e = by_p.get(pid)
    if e is not None:
        k = int(np.searchsorted(e[0], c, side="left"))
        if k > 0:
            last_any_date[i] = e[2][k - 1]
            last_any_team[i] = int(e[1][k - 1])
    e = by_ps.get((pid, s))
    if e is not None:
        k = int(np.searchsorted(e[0], c, side="left"))
        n_prior_app_season[i] = k
        if k > 0:
            trail5_min[i] = float(e[1][max(0, k - 5):k].mean())

pf["last_club_date"] = last_club_date
pf["last_club_season"] = last_club_season
pf["last_any_date"] = last_any_date
pf["last_any_team"] = last_any_team
pf["n_prior_app_season"] = n_prior_app_season
pf["trail5_min"] = trail5_min

gd = pd.to_datetime(pf["game_date"])
pf["days_since_club"] = (gd - pd.to_datetime(pf["last_club_date"])).dt.total_seconds() / 86400.0
pf["days_since_any"] = (gd - pd.to_datetime(pf["last_any_date"])).dt.total_seconds() / 86400.0
pf["never_played_club"] = pf["last_club_date"].isna()
pf["never_played_anywhere"] = pf["last_any_date"].isna()
pf["seasons_since_club"] = np.where(pf["last_club_season"] > 0,
                                    pf["season"] - pf["last_club_season"], 99)

# THE DEPARTURE SIGNAL: she has played for somebody else since she last played for you.
lad = pd.to_datetime(pf["last_any_date"])
lcd = pd.to_datetime(pf["last_club_date"])
pf["departed"] = (lad.notna() & (pf["last_any_team"] != pf["team_id"])
                  & (lcd.isna() | (lad > lcd)))

print("\n  currency feature summary on the champion's 2021-2024 rows (n=%d):" % len(pf))
for c, lbl in (("never_played_club", "never played for this club (admitted)"),
               ("never_played_anywhere", "never played anywhere (admitted)"),
               ("departed", "DEPARTED: played elsewhere since last game for this club")):
    print("    %-58s %6d  (%.2f%%)" % (lbl, int(pf[c].sum()), 100.0 * pf[c].mean()))
print("    %-58s %s" % ("seasons_since_club distribution",
                        pf["seasons_since_club"].value_counts().sort_index().to_dict()))

# =========================================================================================
rb.hdr("8. PERSIST")
PF = pf.merge(key, on=["game_id", "team_id"], how="inner")
assert len(PF) == 20084
PF.to_parquet(os.path.join(rb.OUT, "_PF.parquet"), index=False)
TF.to_parquet(os.path.join(rb.OUT, "_TF.parquet"), index=False)
pf.to_parquet(os.path.join(rb.OUT, "_pf_all_seasons.parquet"), index=False)
rb.dump(F, "_s01.json")
print("  wrote _PF.parquet (%d), _TF.parquet (%d), _pf_all_seasons.parquet (%d)"
      % (len(PF), len(TF), len(pf)))
print("\nDONE s01")
