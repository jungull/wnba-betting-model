#!/usr/bin/env python3
"""E1_I0035 s03 -- WHO ARE THE TIER-B ROWS?

The task's pivot: if the universe contains players who are no longer on the roster at all, that
is a DATA-FRESHNESS defect, not a calibration one, and the fix is different.

P01/P03 use `master_player.parquet` (manifest asof_granularity=row -> USABLE_IF_FILTERED).
P02 uses `data/reference/player_bios.csv`, which has NO SIBLING MANIFEST -> UNVERIFIABLE.
Every bios-derived figure is printed under an UNVERIFIABLE banner and backs no conclusion.

RETROSPECTIVE USE, DECLARED.  "Does this player ever appear for this team again this season"
looks FORWARD.  It is used ONLY to CHARACTERISE the population -- to answer the freshness
question -- and never to build or tune any repair.  No number in s04 depends on it.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import av_base as ab  # noqa: E402

pd.set_option("display.width", 240)
F = {}

PF = pd.read_parquet(os.path.join(ab.OUT, "_player_frame.parquet"))
pm = ab.load_player_master()
tm = ab.load_team_master()
# game_date is a SCHEDULE FACT, not an outcome; taken from master_team's team-game rows
PF = PF.merge(tm[["game_id", "team_id", "game_date"]].drop_duplicates(),
              on=["game_id", "team_id"], how="left")
assert PF["game_date"].notna().all(), "a champion row has no team-game date"
n_tg = 1392
print("  RS1P rows = %d   tier A %d   tier B %d"
      % (len(PF), int(PF["tier_A"].sum()), int((~PF["tier_A"]).sum())))

# =========================================================================================
ab.hdr("P01. REALISED CAREER FOOTPRINT  (master_player, manifest-verified, row granularity)")
app = pm[pm["appeared"] == 1].copy()

# per (player, team, season): the player's realised appearance calendar for that club
pts_team = (app.groupby(["season", "team_id", "player_id"])
            .agg(n_app_team_season=("appeared", "size"),
                 first_app=("game_date", "min"),
                 last_app=("game_date", "max"),
                 mean_min=("minutes", "mean"),
                 mean_pts=("pts", "mean")).reset_index())
# per (player, season) across all clubs
pts_seas = (app.groupby(["season", "player_id"])
            .agg(n_app_season_anywhere=("appeared", "size"),
                 n_teams_season=("team_id", "nunique")).reset_index())
# per player across the whole partition
pts_all = (app.groupby("player_id")
           .agg(n_app_partition=("appeared", "size"),
                first_app_ever=("game_date", "min"),
                last_app_ever=("game_date", "max")).reset_index())

X = PF.merge(pts_team, on=["season", "team_id", "player_id"], how="left")
X = X.merge(pts_seas, on=["season", "player_id"], how="left")
X = X.merge(pts_all, on="player_id", how="left")
for c in ("n_app_team_season", "n_app_season_anywhere", "n_app_partition", "n_teams_season"):
    X[c] = X[c].fillna(0).astype(int)
X["game_date"] = pd.to_datetime(X["game_date"])

foot = (X.groupby("tier_A")
        .agg(n=("row_uid", "size"),
             appear_rate=("appeared", "mean"),
             mean_p_active=("p_active_hat", "mean"),
             n_players=("player_id", "nunique"),
             mean_app_this_team_season=("n_app_team_season", "mean"),
             mean_app_anywhere_season=("n_app_season_anywhere", "mean"),
             mean_app_partition=("n_app_partition", "mean"),
             pct_never_played_this_team_this_season=("n_app_team_season",
                                                     lambda s: float((s == 0).mean())),
             pct_never_played_anywhere_this_season=("n_app_season_anywhere",
                                                    lambda s: float((s == 0).mean())),
             pct_never_played_at_all_2021_2024=("n_app_partition",
                                                lambda s: float((s == 0).mean()))
             ).reset_index())
print(foot.to_string(index=False))
foot.to_csv(os.path.join(ab.OUT, "population_footprint_by_tier.csv"), index=False)
F["P01_footprint_by_tier"] = foot.to_dict("records")

# =========================================================================================
ab.hdr("P03. STALENESS vs CALIBRATION -- the distinction the fix turns on")
# PRE-GAME KNOWABLE: days since this player's last appearance FOR THIS TEAM this season,
# strictly before this game's date.
last_prior = []
appidx = app[["season", "team_id", "player_id", "game_date"]].copy()
appidx = appidx.sort_values(["season", "team_id", "player_id", "game_date"], kind="stable")
key_app = {}
for (s, t, p), g in appidx.groupby(["season", "team_id", "player_id"], sort=False):
    key_app[(s, t, p)] = g["game_date"].to_numpy()

X = X.sort_values(["season", "team_id", "player_id", "game_date"], kind="stable")
dsl = np.full(len(X), np.nan)
nprior_app = np.zeros(len(X), dtype=int)
for i, (s, t, p, d) in enumerate(zip(X["season"].to_numpy(), X["team_id"].to_numpy(),
                                     X["player_id"].to_numpy(), X["game_date"].to_numpy())):
    arr = key_app.get((s, t, p))
    if arr is None:
        continue
    pr = arr[arr < d]
    nprior_app[i] = len(pr)
    if len(pr):
        dsl[i] = (d - pr[-1]) / np.timedelta64(1, "D")
X["days_since_last_app_this_team"] = dsl
X["n_prior_app_this_team_season"] = nprior_app

# RETROSPECTIVE, declared: does the player EVER appear for this team again this season?
future_any = np.zeros(len(X), dtype=int)
for i, (s, t, p, d) in enumerate(zip(X["season"].to_numpy(), X["team_id"].to_numpy(),
                                     X["player_id"].to_numpy(), X["game_date"].to_numpy())):
    arr = key_app.get((s, t, p))
    future_any[i] = 0 if arr is None else int((arr >= d).any())
X["ever_appears_for_this_team_from_now"] = future_any

# TIER B IS DEFINITIONALLY "no prior box row for THIS club", so a band built on
# days-since-last-appearance-for-this-team is degenerate there (verified below and reported).
# The informative axis for tier B is the player's last appearance ANYWHERE, strictly prior.
appany = app[["player_id", "game_date"]].sort_values(["player_id", "game_date"], kind="stable")
key_any = {p: g["game_date"].to_numpy() for p, g in appany.groupby("player_id", sort=False)}
dsl_any = np.full(len(X), np.nan)
nprior_any = np.zeros(len(X), dtype=int)
for i, (p, d) in enumerate(zip(X["player_id"].to_numpy(), X["game_date"].to_numpy())):
    arr = key_any.get(p)
    if arr is None:
        continue
    pr = arr[arr < d]
    nprior_any[i] = len(pr)
    if len(pr):
        dsl_any[i] = (d - pr[-1]) / np.timedelta64(1, "D")
X["days_since_last_app_anywhere"] = dsl_any
X["n_prior_app_anywhere"] = nprior_any


def band(r):
    if r["n_prior_app_this_team_season"] == 0:
        return "A_never_played_for_this_team_this_season"
    if not np.isfinite(r["days_since_last_app_this_team"]):
        return "A_never_played_for_this_team_this_season"
    d = r["days_since_last_app_this_team"]
    if d <= 7:
        return "B_played_within_7d"
    if d <= 21:
        return "C_played_8_21d_ago"
    if d <= 45:
        return "D_played_22_45d_ago"
    return "E_played_over_45d_ago"


def band_any(r):
    if r["n_prior_app_anywhere"] == 0:
        return "Z0_never_appeared_anywhere_before"
    d = r["days_since_last_app_anywhere"]
    if d <= 7:
        return "Z1_appeared_somewhere_within_7d"
    if d <= 30:
        return "Z2_appeared_8_30d_ago"
    if d <= 200:
        return "Z3_appeared_31_200d_ago"
    return "Z4_appeared_over_200d_ago_prior_season"


X["staleness_band"] = X.apply(band, axis=1)
X["staleness_band_anywhere"] = X.apply(band_any, axis=1)

for tier, lbl in ((False, "TIER B"), (True, "TIER A")):
    sub = X[X["tier_A"] == tier]
    t = (sub.groupby("staleness_band")
         .agg(n=("row_uid", "size"), mean_p_active=("p_active_hat", "mean"),
              appear_rate=("appeared", "mean"),
              pct_declared_const=("is_declared_const", "mean"),
              never_returns=("ever_appears_for_this_team_from_now",
                             lambda s: float(1.0 - s.mean()))).reset_index())
    t["share_of_tier"] = t["n"] / len(sub)
    t["excess_per_team_game"] = (sub.groupby("staleness_band")["p_active_hat"].sum()
                                 - sub.groupby("staleness_band")["appeared"].sum()
                                 ).reindex(t["staleness_band"]).to_numpy() / n_tg
    print("\n  %s  (n=%d)" % (lbl, len(sub)))
    print(t.to_string(index=False))
    F["P03_staleness_%s" % ("tierA" if tier else "tierB")] = t.to_dict("records")
    t.assign(tier="A" if tier else "B").to_csv(
        os.path.join(ab.OUT, "staleness_bands_tier_%s.csv" % ("A" if tier else "B")),
        index=False)

print("\n  NOTE: tier B is DEFINITIONALLY 'no prior admitted box row for this club', so the")
print("  this-team band above is degenerate there.  The informative axis for tier B is the")
print("  player's last appearance ANYWHERE, strictly prior:")
for tier, lbl in ((False, "TIER B"), (True, "TIER A")):
    sub = X[X["tier_A"] == tier]
    t2 = (sub.groupby("staleness_band_anywhere")
          .agg(n=("row_uid", "size"), mean_p_active=("p_active_hat", "mean"),
               appear_rate=("appeared", "mean"),
               pct_declared_const=("is_declared_const", "mean"),
               never_returns=("ever_appears_for_this_team_from_now",
                              lambda s: float(1.0 - s.mean())),
               sum_p=("p_active_hat", "sum"), sum_app=("appeared", "sum")).reset_index())
    t2["share_of_tier"] = t2["n"] / len(sub)
    t2["excess_per_team_game"] = (t2["sum_p"] - t2["sum_app"]) / n_tg
    print("\n  %s  (n=%d)  -- by LAST APPEARANCE ANYWHERE (strictly prior)" % (lbl, len(sub)))
    print(t2.to_string(index=False))
    F["P03b_anywhere_%s" % ("tierA" if tier else "tierB")] = t2.to_dict("records")
    t2.assign(tier="A" if tier else "B").to_csv(
        os.path.join(ab.OUT, "staleness_bands_anywhere_tier_%s.csv"
                     % ("A" if tier else "B")), index=False)

# the headline freshness number
tb = X[~X["tier_A"]]
never = float(1.0 - tb["ever_appears_for_this_team_from_now"].mean())
never_played = float((tb["n_prior_app_this_team_season"] == 0).mean())
print("\n  TIER-B HEADLINE")
print("    rows whose player NEVER plays for this team again this season : %.4f" % never)
print("    rows whose player had NEVER played for this team this season  : %.4f" % never_played)
print("    rows whose player never played ANYWHERE in 2021-2024          : %.4f"
      % float((tb["n_app_partition"] == 0).mean()))
mass_never = float(tb.loc[tb["ever_appears_for_this_team_from_now"] == 0,
                          "p_active_hat"].sum() / n_tg)
print("    p_active MASS carried by never-returning tier-B rows          : %.4f /team-game"
      % mass_never)
F["P03_headline"] = {"tierB_share_never_returns": never,
                     "tierB_share_never_played_this_team_this_season": never_played,
                     "tierB_share_never_played_in_partition":
                         float((tb["n_app_partition"] == 0).mean()),
                     "tierB_p_active_mass_never_returning_per_team_game": mass_never,
                     "total_excess_per_team_game": 0.9365,
                     "RETROSPECTIVE": "ever_appears_* looks forward; CHARACTERISATION ONLY, "
                                      "never used to build or tune any repair"}

# =========================================================================================
ab.hdr("P01b. THE TIER-B PLAYERS THEMSELVES  (top 25 by p_active mass carried)")
# `player_name` on X comes from the GAME box row and is NaN whenever the player has no box row
# for that game -- which is most of tier B.  groupby drops NaN keys, so grouping on it would
# silently discard ~90% of the tier.  A partition-wide name lookup is used instead.
namemap = (pm.sort_values(["player_id", "game_date"], kind="stable")
           .groupby("player_id")["player_name"].last().rename("name_lookup"))
XB = X[~X["tier_A"]].merge(namemap, on="player_id", how="left")
XB["name_lookup"] = XB["name_lookup"].fillna("<no box row anywhere 2021-2024>")
assert len(XB) == int((~X["tier_A"]).sum()), "tier-B rows lost in the name merge"
who = (XB.groupby(["player_id", "name_lookup"])
       .agg(n_rows=("row_uid", "size"), sum_p_active=("p_active_hat", "sum"),
            n_appeared=("appeared", "sum"), mean_p=("p_active_hat", "mean"),
            mean_pts_hat=("pts_hat", "mean"),
            app_partition=("n_app_partition", "max")).reset_index())
assert int(who["n_rows"].sum()) == len(XB), "player table does not partition the tier"
who["excess"] = who["sum_p_active"] - who["n_appeared"]
who = who.sort_values("excess", ascending=False)
print(who.head(25).to_string(index=False))
who.to_csv(os.path.join(ab.OUT, "tier_b_players.csv"), index=False)
print("\n  distinct tier-B players: %d   carrying %.1f excess p_active mass in total"
      % (len(who), who["excess"].sum()))
F["P01b_n_tier_b_players"] = int(len(who))

# =========================================================================================
ab.hdr("P02. BIOS CROSS-TAB  ***  UNVERIFIABLE -- NO MANIFEST -- BACKS NO NUMBER  ***")
if os.path.exists(ab.BIOS):
    b = pd.read_csv(ab.BIOS)
    b = b[b["season"].isin(ab.EXPLORATION_SEASONS)]
    bb = ab.pick(b, ("player_id", "season", "player_name", "age", "draft_year", "draft_round",
                     "draft_number", "position_raw", "country"), "bios")
    Y = X.merge(bb.drop(columns=["player_name"]), on=["player_id", "season"], how="left")
    print("  tier-B rows matched to a bios row: %d of %d"
          % (int(Y.loc[~Y["tier_A"], "age"].notna().sum()), int((~Y["tier_A"]).sum())))
    Y["undrafted"] = Y["draft_round"].isna()
    tab = (Y.groupby("tier_A")
           .agg(mean_age=("age", "mean"), pct_undrafted=("undrafted", "mean"),
                pct_no_bios_row=("age", lambda s: float(s.isna().mean())),
                mean_draft_number=("draft_number", "mean")).reset_index())
    print("\n  *** UNVERIFIABLE (player_bios.csv has no sibling manifest) ***")
    print(tab.to_string(index=False))
    tab.assign(MANIFEST_STATUS="UNVERIFIABLE").to_csv(
        os.path.join(ab.OUT, "UNVERIFIABLE_bios_crosstab.csv"), index=False)
    F["P02_bios_UNVERIFIABLE"] = {"status": "UNVERIFIABLE -- no sibling manifest; colour only, "
                                            "backs no conclusion",
                                 "table": tab.to_dict("records")}
else:
    print("  bios file absent")

X.to_parquet(os.path.join(ab.OUT, "_population_frame.parquet"), index=False)
open(os.path.join(ab.OUT, "_s03.json"), "w", encoding="utf-8").write(
    json.dumps(ab.jsonable(F), indent=2))
print("\nDONE s03")
