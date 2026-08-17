"""E1_I0046 s01 -- ANCHORS FIRST, then the frame.  The run HALTS if any anchor fails."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import al_base as A

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 200)

A.hdr("E1_I0046_allocation  --  s01  ANCHORS AND FRAME")
print("PREREG.md sha256 = %s" % A.prereg_sha())

rows = []


def anchor(aid, what, repro, recorded, tol, source):
    ok = abs(float(repro) - float(recorded)) <= tol
    rows.append(dict(anchor=aid, what=what, reproduced=repro, recorded=recorded,
                     abs_diff=abs(float(repro) - float(recorded)), tol=tol, PASS=bool(ok),
                     source=source))
    print("  %-5s %-62s repro=%-22s rec=%-22s |d|=%.3e  %s"
          % (aid, what[:62], repro, recorded, abs(float(repro) - float(recorded)),
             "PASS" if ok else "*** FAIL ***"))
    return ok


A.hdr("1. ANCHORS -- reproduced on bytes BEFORE any new statistic")

mt = pd.read_parquet(A.MT, columns=["game_id", "season", "season_type", "team_id", "is_home", "pts"])
mt = mt[(mt["season"].isin([2021, 2022, 2023, 2024])) & (mt["season_type"] == "Regular Season")]
anchor("A1a", "D104 regular-season game count 2021-2024", int(mt["game_id"].nunique()), 888, 0,
       "master_team")
hd = mt[mt.is_home == 1]["pts"].mean() - mt[mt.is_home == 0]["pts"].mean()
anchor("A1b", "D104 home advantage on those 888 games", round(float(hd), 6), 0.965090, 5e-7,
       "master_team")

fa = pd.read_parquet(os.path.join(A.EXP, r"E0_I0016_efficiency_predictors\screen_frame.parquet"))
fb = pd.read_parquet(os.path.join(A.EXP, r"E1_I0018_teammate_volume_channel\screen_frame.parquet"))
anchor("A2a", "E0_I0016 screen_frame row count", len(fa), 14852, 0, "parquet")
anchor("A2b", "E1_I0018 screen_frame row count", len(fb), 14852, 0, "parquet")
k = ["season", "player_id", "game_id"]
mg = fa.merge(fb[k + ["prior5_minutes", "y_pts", "minutes", "pts"]], on=k, how="inner",
              suffixes=("", "_tv"))
anchor("A2c", "inner merge row count", len(mg), 14852, 0, "inner merge")
dec = (pd.to_numeric(mg["n_prior"], errors="coerce").to_numpy(float) >= 8.0) & \
      (pd.to_numeric(mg["prior5_minutes"], errors="coerce").to_numpy(float) >= 24.0)
anchor("A3a", "E1_I0043 DECISION stratum rows", int(dec.sum()), 5673, 0,
       "E1_I0043/DECISION_STRATUM.csv")
anchor("A3b", "E1_I0043 DECISION distinct players", int(mg.loc[dec, "player_id"].nunique()), 149, 0,
       "same")
anchor("A3c", "E1_I0043 DECISION distinct games", int(mg.loc[dec, "game_id"].nunique()), 708, 0,
       "same")
anchor("A3d", "E1_I0043 DECISION rows in 2023-24",
       int((dec & mg["season"].isin([2023, 2024]).to_numpy()).sum()), 3167, 0, "same")


def dr2_pooled(y, xb, xd):
    ok = np.isfinite(y) & np.isfinite(xb) & np.isfinite(xd)
    yy = y[ok]
    Xb = np.column_stack([np.ones(int(ok.sum())), xb[ok]])
    Xf = np.column_stack([Xb, xd[ok]])
    sst = float(((yy - yy.mean()) ** 2).sum())
    s1 = float(((yy - Xb @ np.linalg.lstsq(Xb, yy, rcond=None)[0]) ** 2).sum())
    s2 = float(((yy - Xf @ np.linalg.lstsq(Xf, yy, rcond=None)[0]) ** 2).sum())
    return (s1 - s2) / sst, int(ok.sum())


v, n = dr2_pooled(mg["y_ppm"].to_numpy(float), mg["refB_ppm"].to_numpy(float),
                  mg["A10_opp_defrtg"].to_numpy(float))
anchor("A4a", "D085 A10_opp_defrtg -> y_ppm dR2 over refB (RECOMPUTED)", v, 0.0014430974149688,
       5e-13, "E0_I0016/screen_results.csv")
anchor("A4b", "  its n", n, 14852, 0, "same")
v2, _ = dr2_pooled(mg["y_ppm"].to_numpy(float), mg["refA_ppm"].to_numpy(float),
                   mg["A10_opp_defrtg"].to_numpy(float))
anchor("A4c", "D085 same cell over refA (RECOMPUTED)", v2, 0.0015087657892969, 5e-13, "same")

A.hdr("2. FRAME -- appeared-roster composition, 2021-2024 regular season")
d, tg, closure = A.build_frame(verbose=True)

# A5: this screen's own from-scratch priors must reproduce E1_I0018's on all shared rows
j = fb[["season", "player_id", "game_id", "n_prior", "prior5_minutes", "minutes", "pts"]].merge(
    d[["season", "player_id", "game_id", "n_prior", "prior5_minutes", "minutes", "pts"]],
    on=["season", "player_id", "game_id"], how="left", suffixes=("_ref", "_mine"))
anchor("A5a", "E1_I0018 rows located in this screen's appeared universe",
       int(j["n_prior_mine"].notna().sum()), 14852, 0, "join")
anchor("A5b", "n_prior exact matches", int((np.abs(j["n_prior_ref"] - j["n_prior_mine"]) < 1e-12).sum()),
       14852, 0, "join")
both = j["prior5_minutes_ref"].notna() & j["prior5_minutes_mine"].notna()
anchor("A5c", "prior5_minutes max|diff| where both present",
       float(np.max(np.abs((j["prior5_minutes_ref"] - j["prior5_minutes_mine"])[both]))), 0.0, 1e-12,
       "join")
anchor("A5d", "minutes max|diff|", float(np.max(np.abs(j["minutes_ref"] - j["minutes_mine"]))), 0.0,
       1e-12, "join")
anchor("A5e", "pts max|diff|", float(np.max(np.abs(j["pts_ref"] - j["pts_mine"]))), 0.0, 1e-12,
       "join")

anchor("A6a", "composition closure: nonzero points diffs over 1,776 team-games",
       closure["n_nonzero_pts"], 0, 0, "master_team identity")
anchor("A6b", "composition closure: nonzero attempts diffs", closure["n_nonzero_fga"], 0, 0, "same")
anchor("A6c", "E1_I0033 realised roster size (2 dp)", round(closure["mean_roster"], 2), 9.41, 0.011,
       "E1_I0033 WHICH_LEVEL_WINS.md 2(b)")

an = pd.DataFrame(rows)
an.to_csv(os.path.join(A.OUT, "ANCHORS.csv"), index=False)
print("\n  ANCHORS: %d/%d PASS" % (int(an["PASS"].sum()), len(an)))
assert bool(an["PASS"].all()), "ANCHOR FAILURE -- run halted"

A.hdr("3. FRAME CENSUS")
dm = A.decision_mask(d)
d["is_decision"] = dm
cen = []
for lab, m in [("ALL_APPEARED", np.ones(len(d), bool)),
               ("DECISION", dm),
               ("DECISION_CLEAN_2023_24", dm & d["season"].isin([2023, 2024]).to_numpy()),
               ("DECISION_DISCLOSED_2022", dm & (d["season"].to_numpy() == 2022)),
               ("DECISION_TRAIN_le2022", dm & (d["season"].to_numpy() <= 2022)),
               ("ALL_CLEAN_2023_24", d["season"].isin([2023, 2024]).to_numpy())]:
    cen.append(dict(population=lab, n_rows=int(m.sum()),
                    n_players=int(d.loc[m, "player_id"].nunique()),
                    n_team_games=int(d.loc[m, "tg"].nunique()),
                    n_dates=int(d.loc[m, "game_date"].nunique()),
                    n_seasons=int(d.loc[m, "season"].nunique()),
                    pct_of_frame=100.0 * m.sum() / len(d),
                    mean_decision_per_team_game=float(
                        d.loc[m].groupby("tg").size().mean()) if m.sum() else np.nan))
    print("  %-26s rows=%6d players=%4d team-games=%5d dates=%4d  %.2f%% of frame  "
          "mean rows/team-game %.3f"
          % (cen[-1]["population"], cen[-1]["n_rows"], cen[-1]["n_players"],
             cen[-1]["n_team_games"], cen[-1]["n_dates"], cen[-1]["pct_of_frame"],
             cen[-1]["mean_decision_per_team_game"]))
pd.DataFrame(cen).to_csv(os.path.join(A.OUT, "DECISION_STRATUM.csv"), index=False)

d.to_parquet(os.path.join(A.SCR, "_frame.parquet"), index=False)
tg.to_parquet(os.path.join(A.SCR, "_tg.parquet"), index=False)
A.dump("s01", dict(prereg_sha=A.prereg_sha(), closure=closure,
                   anchors=an.to_dict("records"), census=cen,
                   n_rows=int(len(d)), n_team_games=int(d["tg"].nunique())))
print("\n  s01 OK.  frame written to scripts/_frame.parquet")
