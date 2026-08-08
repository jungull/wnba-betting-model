"""E0_I0019 -- s02: build the point-in-time REFERENCES and the pre-game CANDIDATE list, then
HASH THE CANDIDATE LIST BEFORE ANY STATISTIC IS COMPUTED (constraint 7).

Everything here is a STRICTLY-PRIOR window: sort by date, .shift(1), then cumsum/rolling.  The
history frame spans 2021-2024 so that a 2022 row can see 2021, exactly as the arm's own
walk-forward does; only 2022-2024 rows are ever scored.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

import av_base as B
import screenkit as sk

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 120)
OUT = B.OUT
rng = np.random.default_rng(20190019)

B.hdr("s02A -- HISTORY FRAME (contract v4 obligations 2021-2024 + box-membership outcome)")
con = B.load_contract()
mp = B.load_master()
box = (mp.groupby(["game_id", "team_id", "player_id"], as_index=False)
         .agg(box_minutes=("minutes", "max"), box_fga=("fga", "max"), box_pts=("pts", "max"),
              box_starter=("starter_flag", "max"), box_usg=("usage_percentage", "max")))
box["appeared_box"] = box["box_minutes"] > 0

H = con[["row_uid", "game_id", "team_id", "player_id", "season", "gdate"]].copy()
H = H.merge(box, on=["game_id", "team_id", "player_id"], how="left")
H["appeared_box"] = H["appeared_box"].fillna(False)
H["y"] = H["appeared_box"].astype(float)
H["box_minutes"] = pd.to_numeric(H["box_minutes"], errors="coerce").fillna(0.0)
H["box_starter"] = pd.to_numeric(H["box_starter"], errors="coerce").fillna(0.0)
H["box_usg"] = pd.to_numeric(H["box_usg"], errors="coerce")
H = H.sort_values(["player_id", "gdate", "game_id"]).reset_index(drop=True)
B.guard(H, "history frame")
print("  history rows=%d  seasons=%s  appearance rate=%.4f"
      % (len(H), sorted(H["season"].unique()), H["y"].mean()))

# ---------------------------------------------------------------- team pre-game state
B.hdr("s02B -- TEAM PRE-GAME STATE (strictly prior team games, same season)")
mt_path = os.path.join(B.ROOT, r"data\masters\master_team.parquet")
r = sk.check_manifest(mt_path)
print("  master_team manifest status = %s" % r.get("status"))
assert r.get("status") == "USABLE_IF_FILTERED"
mt = pd.read_parquet(mt_path)
mt = mt[mt["season"].isin(B.PARTITION)].copy()
mt["gdate"] = pd.to_datetime(mt["game_date"])
B.guard(mt, "master_team after load")
tg = mt[["season", "team_id", "game_id", "gdate", "opp_team_id", "is_home", "wl"]].copy()
tg["win"] = (tg["wl"].astype(str).str.upper() == "W").astype(float)
tg = tg.sort_values(["season", "team_id", "gdate", "game_id"]).reset_index(drop=True)
g = tg.groupby(["season", "team_id"], sort=False)
tg["tm_game_idx"] = g.cumcount().astype(float)
tg["tm_win_pct_prior"] = g["win"].transform(lambda x: x.shift(1).expanding().mean())
tg["tm_rest_days"] = g["gdate"].transform(lambda x: (x - x.shift(1)).dt.days).astype(float)
tg["tm_b2b"] = (tg["tm_rest_days"] == 1).astype(float)


def _n_in_window(dates, days):
    d = dates.to_numpy()
    out = np.zeros(len(d))
    for i in range(len(d)):
        if i == 0:
            continue
        w = d[i] - d[:i]
        out[i] = float((w <= np.timedelta64(days, "D")).sum())
    return out


parts = []
for (s, t), gg in tg.groupby(["season", "team_id"], sort=False):
    gg = gg.sort_values("gdate").copy()
    gg["tm_n_prior3d"] = _n_in_window(gg["gdate"], 3)
    gg["tm_games_prior7d"] = _n_in_window(gg["gdate"], 7)
    parts.append(gg)
tg = pd.concat(parts, ignore_index=True)
tg["tm_3in4"] = (tg["tm_n_prior3d"] >= 2).astype(float)
tg["tm_season_progress"] = tg["tm_game_idx"] / 40.0
tg["tm_is_home"] = pd.to_numeric(tg["is_home"], errors="coerce").astype(float)
# league mean prior win pct per (season, date) -- strictly prior by construction of the inputs
lg = tg.groupby(["season", "gdate"])["tm_win_pct_prior"].transform("mean")
tg["tm_win_pct_vs_league"] = tg["tm_win_pct_prior"] - lg
tg["tm_late_out_of_contention"] = ((tg["tm_season_progress"] > 0.75) &
                                   (tg["tm_win_pct_vs_league"] < 0)).astype(float)

# roster churn / size / starting-five stability, from PRIOR games only
rost = (mp[mp["minutes"] > 0].groupby(["season", "team_id", "game_id"])["player_id"]
        .apply(frozenset).rename("roster").reset_index())
five = (mp[pd.to_numeric(mp["starter_flag"], errors="coerce").fillna(0) == 1.0]
        .groupby(["season", "team_id", "game_id"])["player_id"].apply(frozenset)
        .rename("five").reset_index())
tg = tg.merge(rost, on=["season", "team_id", "game_id"], how="left")
tg = tg.merge(five, on=["season", "team_id", "game_id"], how="left")
rows = []
for (s, t), gg in tg.groupby(["season", "team_id"], sort=False):
    gg = gg.sort_values(["gdate", "game_id"]).reset_index(drop=True)
    rosters = list(gg["roster"])
    fives = list(gg["five"])
    seen, seen_lag = set(), set()
    five_run, prev_five = 0, None
    for i in range(len(gg)):
        churn = np.nan
        if i >= 2 and rosters[i - 1] is not None and rosters[i - 2] is not None:
            a, b = rosters[i - 1], rosters[i - 2]
            churn = 1.0 - len(a & b) / max(len(a | b), 1)
        newf = float(len([p for p in rosters[i - 1] if p not in seen_lag])) \
            if (i >= 1 and rosters[i - 1] is not None) else np.nan
        rsize = float(len(rosters[i - 1])) if (i >= 1 and rosters[i - 1] is not None) else np.nan
        ften = float(five_run) if i >= 1 else np.nan
        fchg = (1.0 if (i >= 2 and fives[i - 1] is not None and fives[i - 2] is not None
                        and fives[i - 1] != fives[i - 2]) else (0.0 if i >= 2 else np.nan))
        rows.append((s, t, gg["game_id"].iloc[i], churn, newf, rsize, ften, fchg))
        seen_lag = set(seen)
        if rosters[i] is not None:
            seen |= rosters[i]
        if fives[i] is not None:
            five_run = five_run + 1 if (prev_five is not None and fives[i] == prev_five) else 1
            prev_five = fives[i]
R = pd.DataFrame(rows, columns=["season", "team_id", "game_id", "tm_roster_churn_prior",
                                "tm_newfaces_prior", "tm_roster_size_prior",
                                "tm_five_tenure_prior", "tm_five_changed_prior"])
tg = tg.merge(R, on=["season", "team_id", "game_id"], how="left")
TEAMCOLS = ["tm_game_idx", "tm_season_progress", "tm_win_pct_prior", "tm_win_pct_vs_league",
            "tm_late_out_of_contention", "tm_rest_days", "tm_b2b", "tm_3in4",
            "tm_games_prior7d", "tm_is_home", "tm_roster_churn_prior", "tm_newfaces_prior",
            "tm_roster_size_prior", "tm_five_tenure_prior", "tm_five_changed_prior"]
print("  team pre-game cols:", TEAMCOLS)

H = H.merge(tg[["season", "team_id", "game_id"] + TEAMCOLS],
            on=["season", "team_id", "game_id"], how="left")

# ---------------------------------------------------------------- player pre-game state
B.hdr("s02C -- PLAYER PRE-GAME STATE (strictly prior, over the player's own OBLIGATION rows)")
H = H.sort_values(["player_id", "season", "gdate", "game_id"]).reset_index(drop=True)
gs = H.groupby(["season", "player_id"], sort=False)
gc = H.groupby(["player_id"], sort=False)

H["pl_opps_prior"] = gs.cumcount().astype(float)                       # prior obligation rows
H["pl_games_prior"] = gs["y"].transform(lambda x: x.shift(1).cumsum()).fillna(0.0)
H["pl_prior_rate_inseason"] = gs["y"].transform(lambda x: x.shift(1).expanding().mean())
H["pl_career_opps_prior"] = gc.cumcount().astype(float)
H["pl_career_games_prior"] = gc["y"].transform(lambda x: x.shift(1).cumsum()).fillna(0.0)
H["pl_prior_rate_career"] = gc["y"].transform(lambda x: x.shift(1).expanding().mean())
H["pl_prior_season_games"] = H["pl_career_games_prior"] - H["pl_games_prior"]
H["pl_is_rookie_window"] = (H["pl_prior_season_games"] <= 0).astype(float)
H["pl_minutes_prior"] = gs["box_minutes"].transform(lambda x: x.shift(1).cumsum()).fillna(0.0)
H["pl_min_per_opp_prior"] = H["pl_minutes_prior"] / H["pl_opps_prior"].replace(0, np.nan)

miss = 1.0 - H["y"]
H["_miss"] = miss
H["pl_missed_last"] = gs["_miss"].shift(1)
H["pl_missed_any_last3"] = gs["_miss"].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).max())
H["pl_dnp_frac5"] = gs["_miss"].transform(lambda x: x.shift(1).rolling(5, min_periods=2).mean())
H["pl_dnp_frac10"] = gs["_miss"].transform(lambda x: x.shift(1).rolling(10, min_periods=3).mean())


def _consec_and_runs(v):
    """v = miss indicator, already date-ordered inside the group.  Returns, for each row and
    reading ONLY rows strictly before it: (consecutive misses immediately prior, length of the
    current identical-status run, number of status switches so far, number of absence spells)."""
    n = len(v)
    consec = np.zeros(n)
    runlen = np.zeros(n)
    switches = np.zeros(n)
    spells = np.zeros(n)
    c = 0
    rl = 0
    sw = 0
    sp = 0
    prev = None
    for i in range(n):
        consec[i] = c
        runlen[i] = rl
        switches[i] = sw
        spells[i] = sp
        x = v[i]
        if x == 1.0:
            c += 1
            if prev != 1.0:
                sp += 1
        else:
            c = 0
        if prev is None or x == prev:
            rl += 1
        else:
            rl = 1
            sw += 1
        prev = x
    return consec, runlen, switches, spells


cc, rl_, sw_, sp_ = [], [], [], []
for _, gg in H.groupby(["season", "player_id"], sort=False):
    a, b, c_, d_ = _consec_and_runs(gg["_miss"].to_numpy(float))
    cc.append(pd.Series(a, index=gg.index))
    rl_.append(pd.Series(b, index=gg.index))
    sw_.append(pd.Series(c_, index=gg.index))
    sp_.append(pd.Series(d_, index=gg.index))
H["pl_consec_absences"] = pd.concat(cc).reindex(H.index)
H["pl_run_length"] = pd.concat(rl_).reindex(H.index)
H["pl_switches"] = pd.concat(sw_).reindex(H.index)
H["pl_absence_spells"] = pd.concat(sp_).reindex(H.index)
H["pl_switch_rate"] = H["pl_switches"] / H["pl_opps_prior"].replace(0, np.nan)
H["pl_switches5"] = gs["_miss"].transform(
    lambda x: x.shift(1).diff().abs().rolling(5, min_periods=2).sum())
r_ = H["pl_prior_rate_inseason"]
H["pl_boundary_score"] = 4.0 * r_ * (1.0 - r_)          # peaks at r = 0.5, the "sometimes" players
rc = H["pl_prior_rate_career"]
H["pl_boundary_score_career"] = 4.0 * rc * (1.0 - rc)

# role / volume over PRIOR APPEARANCES only
app = H[H["y"] == 1.0].copy()
ga = app.groupby(["season", "player_id"], sort=False)
for src, tag in [("box_minutes", "min"), ("box_starter", "start"), ("box_usg", "usg")]:
    v = pd.to_numeric(app[src], errors="coerce")
    app["_v"] = v
    gv = app.groupby(["season", "player_id"], sort=False)["_v"]
    app["pl_%s_mean5" % tag] = gv.transform(lambda x: x.shift(1).rolling(5, min_periods=2).mean())
    app["pl_%s_sd5" % tag] = gv.transform(lambda x: x.shift(1).rolling(5, min_periods=3).std())
app["pl_min_cv5"] = app["pl_min_sd5"] / app["pl_min_mean5"].replace(0, np.nan)
gmn = app.groupby(["season", "player_id"], sort=False)["box_minutes"]
app["pl_min_trend5"] = (gmn.transform(lambda x: x.shift(1).rolling(2, min_periods=2).mean()) -
                        gmn.transform(lambda x: x.shift(3).rolling(3, min_periods=3).mean()))
app["pl_days_since_appear"] = app.groupby(["season", "player_id"], sort=False)["gdate"].transform(
    lambda x: (x - x.shift(1)).dt.days).astype(float)
ROLE = ["pl_min_mean5", "pl_min_sd5", "pl_start_mean5", "pl_usg_mean5", "pl_min_cv5",
        "pl_min_trend5", "pl_days_since_appear"]
H = H.merge(app[["row_uid"] + ROLE], on="row_uid", how="left")
# forward-fill the role columns down the player's OWN season so a DNP row carries the state as of
# its last appearance -- ffill only ever copies from EARLIER rows, never later ones.
H = H.sort_values(["season", "player_id", "gdate", "game_id"])
for c in ROLE:
    H[c] = H.groupby(["season", "player_id"], sort=False)[c].ffill()
H = H.drop(columns=["_miss"])
print("  player pre-game cols built:", len([c for c in H.columns if c.startswith("pl_")]))

# ---------------------------------------------------------------- REFERENCES
B.hdr("s02D -- POINT-IN-TIME REFERENCE FORECASTS (constructed, never fitted on scored rows)")
# R0: expanding league appearance rate over games STRICTLY EARLIER in the same season
Hd = H.sort_values(["season", "gdate", "game_id"]).copy()
day = Hd.groupby(["season", "gdate"], as_index=False).agg(ds=("y", "sum"), dn=("y", "size"))
day = day.sort_values(["season", "gdate"])
day["cs"] = day.groupby("season")["ds"].transform(lambda x: x.shift(1).cumsum())
day["cn"] = day.groupby("season")["dn"].transform(lambda x: x.shift(1).cumsum())
day["R0"] = day["cs"] / day["cn"]
H = H.merge(day[["season", "gdate", "R0"]], on=["season", "gdate"], how="left")
GLOBAL_PRIOR = 0.78                       # declared a priori, not tuned; only fills the first day
H["R0"] = H["R0"].fillna(GLOBAL_PRIOR)

# R1: strictly-prior per-player in-season rate, backing off to R0
H["R1"] = H["pl_prior_rate_inseason"].fillna(H["R0"])

# R2: Beta(k)-shrunk CAREER-to-date prior rate toward R0 -- "every available prior measurement of
#     the target" that a mean-type reference can carry (constraint 4)
H["R2"] = ((H["pl_career_games_prior"] + B.PSEUDO_K * H["R0"]) /
           (H["pl_career_opps_prior"] + B.PSEUDO_K))

print("  R0 expanding in-season league rate, R1 per-player prior rate, R2 Beta(k=%.0f)-shrunk"
      % B.PSEUDO_K)

# R3: RICH non-parametric WALK-FORWARD lookup.  For season S the table is estimated on seasons
#     < S ONLY, exactly the arm's own discipline.  It is a CONSTRUCTED REFERENCE, not a retrained
#     model: no coefficients, no optimisation, only cell means of the target over prior seasons.
BINS_RATE = [-0.01, 0.35, 0.65, 0.85, 0.95, 1.01]
BINS_CONS = [-0.5, 0.5, 1.5, 3.5, 1e9]
BINS_DEPTH = [-0.5, 3.5, 10.5, 25.5, 1e9]
H["_b_rate"] = pd.cut(H["pl_prior_rate_career"].fillna(-1.0), BINS_RATE, labels=False)
H["_b_cons"] = pd.cut(H["pl_consec_absences"].fillna(0.0), BINS_CONS, labels=False)
H["_b_depth"] = pd.cut(H["pl_career_opps_prior"].fillna(0.0), BINS_DEPTH, labels=False)
H["_cell"] = (H["_b_rate"].astype("Int64").astype(str) + "|" +
              H["_b_cons"].astype("Int64").astype(str) + "|" +
              H["_b_depth"].astype("Int64").astype(str))
H["R3"] = np.nan
r3_tables = {}
for s in B.SCREEN_SEASONS:
    tr = H[H["season"] < s]
    tab = tr.groupby("_cell")["y"].agg(["sum", "size"])
    prior_mean = float(tr["y"].mean())
    lut = ((tab["sum"] + B.PSEUDO_K * prior_mean) / (tab["size"] + B.PSEUDO_K)).to_dict()
    m = H["season"] == s
    H.loc[m, "R3"] = H.loc[m, "_cell"].map(lut)
    H.loc[m & H["R3"].isna(), "R3"] = prior_mean
    r3_tables[s] = dict(n_train_rows=int(len(tr)), train_seasons=sorted(tr["season"].unique()),
                        n_cells=int(len(tab)), prior_mean=prior_mean)
    print("  R3 season %d: table built on seasons %s (n=%d), %d cells, backoff %.4f"
          % (s, sorted(tr["season"].unique()), len(tr), len(tab), prior_mean))
H = H.drop(columns=["_b_rate", "_b_cons", "_b_depth"])
json.dump(r3_tables, open(os.path.join(OUT, "r3_walkforward_tables.json"), "w"), indent=2,
          default=str)

# ---------------------------------------------------------------- attach to the scored frame
B.hdr("s02E -- ATTACH TO THE SCORED FRAME AND ADD MODEL-STATE + NEGATIVE-CONTROL CANDIDATES")
sf = pd.read_parquet(os.path.join(OUT, "scored_frame.parquet"))
featcols = [c for c in H.columns if c.startswith(("pl_", "tm_"))] + ["R0", "R1", "R2", "R3", "_cell"]
F = sf.merge(H[["row_uid"] + featcols], on="row_uid", how="left")
assert len(F) == len(sf)

F["mdl_is_fallback"] = F["v15__is_fallback"].astype(float)
F["mdl_fallback_level"] = pd.to_numeric(F["v15__fallback_level"], errors="coerce").astype(float)
F["mdl_is_cold_start"] = F["v15__is_cold_start"].astype(float)
F["mdl_n_prior_games"] = pd.to_numeric(F["v15__n_prior_games"], errors="coerce").astype(float)
p = pd.to_numeric(F["v15__pred_point"], errors="coerce").astype(float)
F["mdl_pred_point"] = p
pc = np.clip(p, B.EPS, 1 - B.EPS)
F["mdl_pred_entropy"] = -(pc * np.log(pc) + (1 - pc) * np.log(1 - pc))
F["mdl_pred_dist_from_half"] = (p - 0.5).abs()

F = F.sort_values(["season", "player_id", "gdate", "game_id"]).reset_index(drop=True)
F["neg_ctrl_row_noise"] = rng.random(len(F))
ps = F[["season", "player_id"]].drop_duplicates().copy()
ps["neg_ctrl_player_noise"] = rng.random(len(ps))
F = F.merge(ps, on=["season", "player_id"], how="left")

B.guard(F, "candidate frame")
sk.assert_partition(F, verbose=True)
F.to_parquet(os.path.join(OUT, "analysis_frame.parquet"), index=False)
print("  wrote analysis_frame.parquet shape=%s" % (F.shape,))

# ---------------------------------------------------------------- THE CANDIDATE LIST + HASH
B.hdr("s02F -- CANDIDATE LIST, HASHED BEFORE ANY STATISTIC IS COMPUTED")
FAMILIES = {
    "A_depth_experience": ["pl_opps_prior", "pl_games_prior", "pl_prior_rate_inseason",
                           "pl_career_opps_prior", "pl_career_games_prior",
                           "pl_prior_rate_career", "pl_prior_season_games",
                           "pl_is_rookie_window", "pl_minutes_prior", "pl_min_per_opp_prior"],
    "B_absence_return": ["pl_missed_last", "pl_missed_any_last3", "pl_dnp_frac5",
                         "pl_dnp_frac10", "pl_consec_absences", "pl_absence_spells",
                         "pl_days_since_appear"],
    "C_boundary_intermittency": ["pl_boundary_score", "pl_boundary_score_career",
                                 "pl_switches", "pl_switch_rate", "pl_switches5",
                                 "pl_run_length"],
    "D_role_volume": ["pl_min_mean5", "pl_min_sd5", "pl_min_cv5", "pl_start_mean5",
                      "pl_usg_mean5", "pl_min_trend5"],
    "E_roster_churn": ["tm_roster_churn_prior", "tm_newfaces_prior", "tm_roster_size_prior",
                       "tm_five_tenure_prior", "tm_five_changed_prior"],
    "F_schedule": ["tm_rest_days", "tm_b2b", "tm_3in4", "tm_games_prior7d", "tm_is_home"],
    "G_season_phase_contention": ["tm_game_idx", "tm_season_progress", "tm_win_pct_prior",
                                  "tm_win_pct_vs_league", "tm_late_out_of_contention"],
    "H_model_own_state": ["mdl_is_fallback", "mdl_fallback_level", "mdl_is_cold_start",
                          "mdl_n_prior_games", "mdl_pred_point", "mdl_pred_entropy",
                          "mdl_pred_dist_from_half"],
    "Z_negative_control": ["neg_ctrl_row_noise", "neg_ctrl_player_noise"],
}
CANDS = [c for fam in sorted(FAMILIES) for c in FAMILIES[fam]]
missing = [c for c in CANDS if c not in F.columns]
assert not missing, "candidates not built: %s" % missing
payload = json.dumps({k: FAMILIES[k] for k in sorted(FAMILIES)}, sort_keys=True)
CHASH = hashlib.sha256(payload.encode("utf-8")).hexdigest()
print("  %d candidates in %d families" % (len(CANDS), len(FAMILIES)))
print("  CANDIDATE LIST SHA256 = %s" % CHASH)

DEPENDENTS = {
    "signed_err": "y - p          (SIGNED calibration error; sign = direction of miscalibration)",
    "brier": "(y - p)^2      (ERROR, NOT an edge -- D076: predicting error != predicting skill)",
    "skill_vs_R1": "(y-R1)^2 - (y-p)^2   differential skill vs the per-player prior rate",
    "skill_vs_R2": "(y-R2)^2 - (y-p)^2   differential skill vs the Beta-shrunk career prior rate",
    "skill_vs_R3": "(y-R3)^2 - (y-p)^2   differential skill vs the RICH walk-forward lookup",
    "llskill_vs_R3": "logloss(R3) - logloss(p)   the same contrast on the log-loss scale",
}
DHASH = hashlib.sha256(json.dumps(DEPENDENTS, sort_keys=True).encode("utf-8")).hexdigest()
print("  %d dependents.  DEPENDENT LIST SHA256 = %s" % (len(DEPENDENTS), DHASH))
print("  TOTAL CELLS = %d" % (len(CANDS) * len(DEPENDENTS)))

lines = ["# CANDIDATES PRESELECTED -- E0_I0019 availability forecast (`p_active`)", "",
         "Written and hashed BEFORE any statistic was computed (constraint 7). The hash covers",
         "the family -> candidate mapping exactly as serialised in `s02_build_candidates.py`.", "",
         "**CANDIDATE LIST SHA256 = `%s`**" % CHASH, "",
         "**DEPENDENT LIST SHA256 = `%s`**" % DHASH, "",
         "%d candidates x %d dependents = **%d cells**." % (len(CANDS), len(DEPENDENTS),
                                                            len(CANDS) * len(DEPENDENTS)), "",
         "## Dependents", ""]
for k, v in DEPENDENTS.items():
    lines.append("- `%s` --- %s" % (k, v))
lines += ["", "## Candidates by family", ""]
for fam in sorted(FAMILIES):
    lines.append("### %s (%d)" % (fam, len(FAMILIES[fam])))
    lines.append("")
    for c in FAMILIES[fam]:
        lines.append("- `%s`" % c)
    lines.append("")
lines += ["## Added / dropped versus the pre-registration",
          "",
          "This is the FIRST and ONLY candidate list for this screen. Added since hashing: **0**.",
          "Dropped since hashing: **0**. Any later change would require a new hash and would be",
          "recorded here with both hashes.", "",
          "## Notes on specific choices", "",
          "- `F_schedule` is included **knowing the family is dead for points and rates** (D081:",
          "  0 of 330 rate cells; D085: 0 of 12; D076: 18 cells, best |t| 7.46, all decile ratios",
          "  0.94-1.25). Availability is a different target and rest decisions plausibly respond",
          "  to back-to-backs, so it is tested rather than assumed. If it dies again the screen",
          "  says so plainly.",
          "- `H_model_own_state` conditions on the model's OWN declared state. `mdl_pred_point`",
          "  and `mdl_pred_entropy` are the model's own uncertainty; a well-behaved forecast",
          "  should NOT have differential skill against its own probability level.",
          "- `Z_negative_control` carries two controls, one varying by ROW and one constant",
          "  WITHIN a player-season. The second exists to show the block permutation null is",
          "  doing work: a player-season-constant noise column must die under the player-level",
          "  null even when it survives the row-level one.",
          ]
open(os.path.join(OUT, "CANDIDATES_PRESELECTED.md"), "w", encoding="utf-8").write("\n".join(lines))
json.dump(dict(candidate_hash=CHASH, dependent_hash=DHASH, families=FAMILIES,
               candidates=CANDS, dependents=DEPENDENTS, n_cells=len(CANDS) * len(DEPENDENTS),
               added_since_hash=0, dropped_since_hash=0),
          open(os.path.join(OUT, "candidates.json"), "w"), indent=2)
print("  wrote CANDIDATES_PRESELECTED.md and candidates.json")
print("\nDONE")
