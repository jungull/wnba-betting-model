"""STEP 3(c) -- THE CHEAP EMPIRICAL PROBE, applied to every reachable suspect baseline.

Question: does the suspect baseline predict the entity's OWN STRICTLY-AFTER-DATE future rate
better than a legitimately-pregame baseline does? If yes, it predicts the future because it
CONTAINS the future.

Reported per suspect:
  corr(suspect,  entity's own strictly-after-date future rate)
  corr(clean,    the same future rate)
  dR2 of adding the suspect on top of the clean baseline, TARGET = that future rate.

PARTITION: 2021-2024 ONLY. Every input frame is asserted to contain no other season before use.
No 2025/2026 row is read, joined, described or summarised anywhere in this file.
"""
import io, json, os
import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")
OUT = os.path.join(EXP, "AUDIT_baseline_provenance")
PARTITION = {2021, 2022, 2023, 2024}

res = {}


def guard(df, label):
    s = set(int(x) for x in pd.unique(df["season"]))
    assert s <= PARTITION, "PARTITION VIOLATION in %s: %s" % (label, sorted(s))
    print("[partition-check] %s: seasons=%s rows=%d" % (label, sorted(s), len(df)))
    return df


def r2p(X, y):
    """R2 of OLS of y on columns X (with intercept)."""
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    return 1.0 - float(r @ r) / float(((y - y.mean()) ** 2).sum())


def future_rate(df, ent, num, den, datecol="_d"):
    """Entity's own rate over games STRICTLY AFTER this row's date, within season.
    Built by total-minus-prefix so it is unambiguously the *unplayed* remainder."""
    d = df.sort_values([ent, "season", datecol]).copy()
    g = d.groupby([ent, "season"], sort=False)
    tot_n = g[num].transform("sum")
    tot_d = g[den].transform("sum")
    # cumulative INCLUDING every row on this date (aggregate to date level so same-day
    # games cannot be counted as "future" for each other)
    day = d.groupby([ent, "season", datecol], as_index=False)[[num, den]].sum()
    day = day.sort_values([ent, "season", datecol])
    day["cn"] = day.groupby([ent, "season"], sort=False)[num].cumsum()
    day["cd"] = day.groupby([ent, "season"], sort=False)[den].cumsum()
    d = d.merge(day[[ent, "season", datecol, "cn", "cd"]], on=[ent, "season", datecol], how="left")
    fut_n = tot_n.values - d["cn"].values
    fut_d = tot_d.values - d["cd"].values
    out = np.where(fut_d > 0, 100.0 * fut_n / fut_d, np.nan)
    return pd.Series(out, index=d.index), d


def probe(name, d, suspect, clean, fut, min_future_den=None):
    m = d[[suspect, clean]].notna().all(axis=1) & pd.Series(fut, index=d.index).notna()
    x_s = d.loc[m, suspect].to_numpy(float)
    x_c = d.loc[m, clean].to_numpy(float)
    yf = np.asarray(fut, float)[m.to_numpy()]
    c_s = float(np.corrcoef(x_s, yf)[0, 1])
    c_c = float(np.corrcoef(x_c, yf)[0, 1])
    dr2 = r2p([x_c, x_s], yf) - r2p([x_c], yf)
    rec = {"n": int(m.sum()),
           "corr_SUSPECT_with_own_future": round(c_s, 4),
           "corr_CLEAN_with_own_future": round(c_c, 4),
           "dR2_suspect_over_clean_predicting_the_future": round(dr2, 6),
           "suspect_col": suspect, "clean_col": clean}
    res[name] = rec
    print("\n### %s" % name)
    print("   suspect = %-32s clean = %s" % (suspect, clean))
    print("   n = %d" % rec["n"])
    print("   corr(SUSPECT, entity's own STRICTLY-AFTER-DATE future rate) = %+.4f" % c_s)
    print("   corr(CLEAN,   same future rate)                            = %+.4f" % c_c)
    print("   dR2 of SUSPECT over CLEAN in predicting that future        = %.6f" % dr2)
    return rec


# =====================================================================
# SUBSTRATE A -- E1 I0009 frozen frame: carries BOTH the loo and the pregame
# variants of player tendency, opponent pressure and opponent def-rating over
# the same 2021-2024 universe. This is the frame the E1 headline was computed on.
# =====================================================================
A = pd.read_csv(os.path.join(EXP, "E1_I0009_additive_pressure", "player_game_analysis.csv"))
A["season"] = A["season"].astype(int)
guard(A, "E1_I0009 player_game_analysis.csv")
A["_d"] = pd.to_datetime(A["game_date"])
assert A["_d"].dt.year.between(2021, 2024).all(), "PARTITION VIOLATION (dates)"

# --- A1. player_tendency_loo  (KNOWN instance 4 -- reproduced as a method control)
fut_p, Ap = future_rate(A, "player_id", "turnovers", "realised_off_possessions")
probe("A1_player_tendency_loo_vs_pregame [KNOWN instance 4 - method control]",
      Ap, "player_tendency_loo", "player_tendency_pregame", fut_p)

# --- A2. opponent_pressure_loo  (the quantity I0005 and I0009-rung-1 actually TESTED)
tg = pd.read_csv(os.path.join(EXP, "E1_I0009_additive_pressure", "team_game_defense.csv"))
tg["season"] = tg["season"].astype(int)
guard(tg, "E1_I0009 team_game_defense.csv")
tg["_d"] = pd.to_datetime(tg["game_date"])
fut_t, Tg = future_rate(tg, "team_id", "def_tov", "def_poss")
probe("A2_opponent_pressure_loo_vs_pregame  [E0 I0005 signal / E0 I0009 rung-1 baseline]",
      Tg, "pressure_loo", "pressure_pregame", fut_t)

# --- A3. opponent_defrtg_loo (the E0 I0009 'D_LOO' control)
fut_r, Tg2 = future_rate(tg, "team_id", "def_pts_allowed", "def_poss")
probe("A3_opponent_defrtg_loo_vs_pregame    [E0 I0009 control variable D_LOO]",
      Tg2, "defrtg_loo", "defrtg_pregame", fut_r)

# =====================================================================
# SUBSTRATE B -- E0 I0004 shot-level LOO file (KNOWN instances 2 and 3).
# The opponent zone allowance is a leave-one-GAME-out over a FULL-SEASON team
# rate; the clean comparator here is the opponent's strictly-prior expanding
# zone rate, which we build from the same file (dates are present).
# =====================================================================
try:
    B = pd.read_csv(os.path.join(EXP, "E0_I0004_shot_location_allowance",
                                 "shot_level_residuals_LOO_2021_2024.csv"),
                    low_memory=False)
    B["season"] = B["season"].astype(int)
    guard(B, "E0_I0004 shot_level_residuals_LOO")
    # GAME_DATE is an int YYYYMMDD -- must give the format explicitly or pandas
    # reads it as a nanosecond epoch and silently produces 1970 dates.
    B["_d"] = pd.to_datetime(B["GAME_DATE"].astype(str), format="%Y%m%d")
    assert B["_d"].dt.year.between(2021, 2024).all(), "PARTITION VIOLATION (I0004 dates)"

    # collapse to (opponent, season, zone, date): shots faced and made
    B["_att"] = 1.0
    B["_mk"] = B["made"].astype(float)
    key = ["OPP_TEAM_ID", "season", "zone"]
    day = (B.groupby(key + ["_d"], as_index=False)[["_att", "_mk"]].sum()
             .sort_values(key + ["_d"]).reset_index(drop=True))
    g = day.groupby(key, sort=False)
    day["c_att"] = g["_att"].cumsum()
    day["c_mk"] = g["_mk"].cumsum()
    # strictly-prior expanding opponent zone conversion allowed = CLEAN comparator
    day["pre_att"] = day["c_att"] - day["_att"]
    day["pre_mk"] = day["c_mk"] - day["_mk"]
    day["opp_zone_pre"] = np.where(day["pre_att"] >= 20, day["pre_mk"] / day["pre_att"], np.nan)
    # strictly-AFTER-date opponent zone conversion allowed = the FUTURE target
    tot_att = g["_att"].transform("sum")
    tot_mk = g["_mk"].transform("sum")
    day["fut_att"] = tot_att.values - day["c_att"].values
    day["fut_mk"] = tot_mk.values - day["c_mk"].values
    day["opp_zone_future"] = np.where(day["fut_att"] >= 20, day["fut_mk"] / day["fut_att"], np.nan)

    Bd = B.merge(day[key + ["_d", "opp_zone_pre", "opp_zone_future"]],
                 on=key + ["_d"], how="left")
    Bd = Bd.dropna(subset=["loo_zone_rate", "opp_zone_pre", "opp_zone_future"])
    Bd = Bd[Bd["loo_att"] >= 20]
    probe("B1_opponent_zone_LOO_vs_pregame_expanding [KNOWN instance 3 - opponent allowance]",
          Bd.reset_index(drop=True), "loo_zone_rate", "opp_zone_pre",
          Bd["opp_zone_future"].to_numpy(float) * 100.0)

    # --- B2. the PLAYER x ZONE baseline (KNOWN instance 2, leave-one-SEASON-out).
    # Clean comparator: the player's own strictly-prior expanding zone conversion.
    pk = ["PLAYER_ID", "season", "zone"]
    pday = (B.groupby(pk + ["_d"], as_index=False)[["_att", "_mk"]].sum()
              .sort_values(pk + ["_d"]).reset_index(drop=True))
    pg = pday.groupby(pk, sort=False)
    pday["c_att"] = pg["_att"].cumsum()
    pday["c_mk"] = pg["_mk"].cumsum()
    pday["pre_att"] = pday["c_att"] - pday["_att"]
    pday["pre_mk"] = pday["c_mk"] - pday["_mk"]
    pday["own_zone_pre"] = np.where(pday["pre_att"] >= 10,
                                    pday["pre_mk"] / pday["pre_att"], np.nan)
    t_att = pg["_att"].transform("sum")
    t_mk = pg["_mk"].transform("sum")
    pday["fut_att"] = t_att.values - pday["c_att"].values
    pday["fut_mk"] = t_mk.values - pday["c_mk"].values
    pday["own_zone_future"] = np.where(pday["fut_att"] >= 10,
                                       pday["fut_mk"] / pday["fut_att"], np.nan)
    Bp = B.merge(pday[pk + ["_d", "own_zone_pre", "own_zone_future"]], on=pk + ["_d"], how="left")
    Bp = Bp.dropna(subset=["player_zone_baseline", "own_zone_pre", "own_zone_future"])
    probe("B2_player_zone_baseline_vs_pregame_expanding [KNOWN instance 2 - player x zone rate]",
          Bp.reset_index(drop=True), "player_zone_baseline", "own_zone_pre",
          Bp["own_zone_future"].to_numpy(float) * 100.0)
except Exception as e:
    res["B_I0004_probes"] = {"ERROR": repr(e)}
    print("\n### B I0004 probes FAILED:", repr(e))

with io.open(os.path.join(OUT, "probe_results.json"), "w", encoding="utf-8") as f:
    json.dump({"partition": "2021-2024 only; asserted on every input frame",
               "definition": ("future rate = entity's own numerator/denominator summed over "
                              "games STRICTLY AFTER this row's date within the same season "
                              "(total minus date-inclusive prefix), i.e. the UNPLAYED remainder"),
               "probes": res}, f, indent=1)
print("\nwrote probe_results.json")
