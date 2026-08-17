"""s01 -- ANCHORS.  Reproduced BEFORE any new statistic.  The run HALTS if any anchor fails.

The most load-bearing anchors are A5*: an EXACT reproduction, from an independent reimplementation
in this screen's own `mn_base.py`, of `E1_I0046_allocation`'s published TUNED and NAIVE
minutes-share reference R2.  If this screen's minutes reference is built differently from the
programme's, that is where it shows.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mn_base as A                                                    # noqa: E402

A.hdr("s01 ANCHORS   PREREG sha256 %s" % A.prereg_sha())
d = pd.read_parquet(os.path.join(A.SCR, "_frame.parquet"))
A.assert_partition(d, "cached frame", verbose=True)
season = d["season"].to_numpy()
dm = A.decision_mask(d)
tg_code = d["tg_code"].to_numpy()
n_tg = int(tg_code.max()) + 1
counts = np.bincount(tg_code, minlength=n_tg).astype(float)

rows = []


def anchor(tag, what, repro, recorded, tol, source):
    ok = abs(float(repro) - float(recorded)) <= tol
    rows.append(dict(anchor=tag, what=what, reproduced=float(repro), recorded=float(recorded),
                     abs_diff=abs(float(repro) - float(recorded)), tol=tol, PASS=bool(ok),
                     source=source))
    print("  %-5s %-62s repro %-22.14g rec %-22.14g |d| %-10.3g %s"
          % (tag, what[:62], float(repro), float(recorded),
             abs(float(repro) - float(recorded)), "PASS" if ok else "*** FAIL ***"))
    assert ok, "ANCHOR %s FAILED" % tag


# ---------------------------------------------------------------- A1  D104 home advantage
mt = pd.read_parquet(A.MT, columns=["game_id", "season", "season_type", "team_id", "is_home",
                                    "pts", "opp_pts", "game_date"])
mt["game_date"] = pd.to_datetime(mt["game_date"])
mt = mt[(mt["season"].isin(sorted(A.ALLOWED_SEASONS))) &
        (mt["season_type"] == "Regular Season")].copy()
A.assert_partition(mt, "master_team anchors")
home = mt[mt["is_home"] == 1]
anchor("A1a", "D104 regular-season game count 2021-2024", home["game_id"].nunique(), 888, 0.0,
       "master_team")
anchor("A1b", "D104 home advantage on those 888 games",
       float((home["pts"] - home["opp_pts"]).mean()), 0.96509, 5e-7, "master_team")

# ---------------------------------------------------------------- A2  frame universe
anchor("A2a", "E1_I0046 ALL_APPEARED rows", len(d), 16717, 0.0, "E1_I0046/DECISION_STRATUM.csv")
anchor("A2b", "E1_I0046 ALL_APPEARED team-games", d["tg"].nunique(), 1776, 0.0, "same")
anchor("A2c", "E1_I0046 ALL_APPEARED players", d["player_id"].nunique(), 265, 0.0, "same")
anchor("A2d", "E1_I0033 realised roster size (2 dp)", round(float(counts.mean()), 2), 9.41, 0.011,
       "E1_I0033 WHICH_LEVEL_WINS.md 2(b)")

# ---------------------------------------------------------------- A3  the decision stratum
anchor("A3a", "E1_I0043 DECISION stratum rows", int(dm.sum()), 5673, 0.0,
       "E1_I0043/DECISION_STRATUM.csv")
anchor("A3b", "E1_I0043 DECISION distinct players", d.loc[dm, "player_id"].nunique(), 149, 0.0,
       "same")
anchor("A3c", "E1_I0043 DECISION distinct games", d.loc[dm, "game_id"].nunique(), 708, 0.0, "same")
clean = np.isin(season, A.CLEAN_EVAL_SEASONS)
anchor("A3d", "E1_I0043 DECISION rows in 2023-24", int((dm & clean).sum()), 3167, 0.0, "same")
anchor("A3e", "E1_I0046 DECISION_CLEAN team-game blocks", d.loc[dm & clean, "tg"].nunique(), 764,
       0.0, "E1_I0046/DECISION_STRATUM.csv")
anchor("A3f", "E1_I0046 DECISION_TRAIN_le2022 rows", int((dm & (season <= 2022)).sum()), 2506, 0.0,
       "same")

# ---------------------------------------------------------------- A4  composition closure
mt2 = pd.read_parquet(A.MT, columns=["game_id", "season", "season_type", "team_id", "pts", "fga",
                                     "minutes"])
mt2 = mt2[(mt2["season"].isin(sorted(A.ALLOWED_SEASONS))) &
          (mt2["season_type"] == "Regular Season")].copy()
mt2["tg"] = mt2["game_id"].astype(str) + "|" + mt2["team_id"].astype(str)
agg = d.groupby("tg", sort=False).agg(T_pts=("pts", "sum"), T_fga=("fga", "sum"),
                                      T_min=("minutes", "sum")).reset_index()
chk = mt2.merge(agg, on="tg", how="inner")
anchor("A4a", "closure: nonzero points diffs over 1,776 team-games",
       int((np.abs(chk["T_pts"] - chk["pts"]) > 1e-9).sum()), 0, 0.0, "master_team identity")
anchor("A4b", "closure: nonzero attempts diffs",
       int((np.abs(chk["T_fga"] - chk["fga"]) > 1e-9).sum()), 0, 0.0, "same")
anchor("A4c", "closure: team-games matched", len(chk), 1776, 0.0, "same")

# ------------------------------------------- A5  EXACT reproduction of E1_I0046's minutes reference
# E1_I0046 tuned on DECISION rows from strictly earlier seasons, scored the PROJECTED forecast,
# and used naive = allocator(h=5, k=0) projected, uniform = 1/roster count.
y_sm = d["R2_smin"].to_numpy(float)
ones = np.ones(n_tg)
tune = []
for es in [2023, 2024, 2022]:
    tr = dm & (season < es)
    best = None
    for h in A.H_GRID:
        for kk in A.K_GRID:
            raw = A.allocator_raw(d, "R2_smin", h, kk)
            f = A.project_to_total(raw, tg_code, n_tg, counts, ones)
            sse = float(((y_sm[tr] - f[tr]) ** 2).sum())
            if best is None or sse < best[0]:
                best = (sse, h, kk, f)
    sse, h, kk, f = best
    naive = A.project_to_total(A.allocator_raw(d, "R2_smin", 5, 0.0), tg_code, n_tg, counts, ones)
    unif = 1.0 / counts[tg_code]
    te = dm & (season == es)
    tune.append(dict(eval_season=es, h=h, k=kk, train_sse=sse, n_train=int(tr.sum()),
                     n_eval=int(te.sum()),
                     r2_tuned=A.r2_of_forecast(y_sm[te], f[te]),
                     r2_naive=A.r2_of_forecast(y_sm[te], naive[te]),
                     r2_uniform=A.r2_of_forecast(y_sm[te], unif[te])))

REC = {2023: dict(h=3, k=1.0, tuned=0.27683141342060724, naive=0.2395715216025346,
                  uniform=-1.624584531848702, n_train=2506, n_eval=1596,
                  sse=1.8240008842569635),
       2024: dict(h=3, k=1.0, tuned=0.24552519662119843, naive=0.2059808964669676,
                  uniform=-1.5766055352658155, n_train=4102, n_eval=1571,
                  sse=2.9584976799082074),
       2022: dict(h=3, k=1.0, tuned=0.24205304356194202, naive=0.22352759131871003,
                  uniform=-1.3281374452306154, n_train=1156, n_eval=1350,
                  sse=0.8920187366889516)}
for t in tune:
    es = t["eval_season"]
    r = REC[es]
    anchor("A5h%d" % es, "E1_I0046 R2_s_min selected halflife, eval %d" % es, t["h"], r["h"], 0.0,
           "E1_I0046/REFERENCE_TUNING.csv")
    anchor("A5k%d" % es, "E1_I0046 R2_s_min selected shrinkage k, eval %d" % es, t["k"], r["k"],
           0.0, "same")
    anchor("A5n%d" % es, "E1_I0046 R2_s_min n_train_rows, eval %d" % es, t["n_train"], r["n_train"],
           0.0, "same")
    anchor("A5e%d" % es, "E1_I0046 R2_s_min n_eval_rows, eval %d" % es, t["n_eval"], r["n_eval"],
           0.0, "same")
    anchor("A5s%d" % es, "E1_I0046 R2_s_min train_sse, eval %d" % es, t["train_sse"], r["sse"],
           5e-13, "same")
    anchor("A5T%d" % es, "E1_I0046 R2_s_min TUNED eval R2, eval %d (RECOMPUTED)" % es,
           t["r2_tuned"], r["tuned"], 5e-13, "same")
    anchor("A5N%d" % es, "E1_I0046 R2_s_min NAIVE eval R2, eval %d (RECOMPUTED)" % es,
           t["r2_naive"], r["naive"], 5e-13, "same")
    anchor("A5U%d" % es, "E1_I0046 R2_s_min UNIFORM eval R2, eval %d (RECOMPUTED)" % es,
           t["r2_uniform"], r["uniform"], 5e-13, "same")

out = pd.DataFrame(rows)
out.to_csv(os.path.join(A.OUT, "ANCHORS.csv"), index=False)
n_exact = int((out["abs_diff"] == 0.0).sum())
A.hdr("ANCHORS: %d reproduced, %d at exactly 0.000e+00, 0 failures" % (len(out), n_exact))
A.dump("s01", dict(prereg_sha=A.prereg_sha(), n_anchors=int(len(out)), n_exact=n_exact,
                   all_pass=bool(out["PASS"].all()),
                   max_abs_diff=float(out["abs_diff"].max())))
