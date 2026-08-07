"""E0 I0011 -- F_TENDENCY_ESTIMATOR: build the shifted-estimator evaluation frame.

EXPLORATION PARTITION (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY.
Both masters have asof_granularity == "row" per their manifests, so filtering to
2021-2024 immediately after load is sufficient. FILTER-POINTs are marked below.

Outputs (all inside this experiment directory):
  frame.parquet          one row per player-game (minutes>0), 2021-2024, with
                         targets, context multipliers c_g, projected context c_t,
                         prior-season means, and role/slice keys.
"""
import numpy as np
import pandas as pd

SEED = 20260807
np.random.seed(SEED)

PARTITION = [2021, 2022, 2023, 2024]
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
HERE = ROOT + r"\experiments\exploration\E0_I0011_tendency_estimator"
SELECT_SEASONS = [2021, 2022]
SCORE_SEASONS = [2023, 2024]


def assert_partition(d, label):
    got = sorted(int(x) for x in pd.unique(d["season"]))
    assert set(got) <= set(PARTITION), f"{label}: PARTITION VIOLATION {got}"
    print(f"[partition-check] {label}: seasons={got} rows={len(d)}")


# ---------------------------------------------------------------- team context
tm = pd.read_parquet(ROOT + r"\data\masters\master_team.parquet")
tm = tm[tm["season"].isin(PARTITION)].copy()          # FILTER-POINT
assert_partition(tm, "master_team raw")

for c in ["fga", "fta", "tov", "oreb", "opp_fga", "opp_fta", "opp_tov", "opp_oreb",
          "pts", "reb", "ast", "opp_pts", "opp_reb", "opp_ast"]:
    tm[c] = pd.to_numeric(tm[c], errors="coerce").astype(float)

tm["poss_team"] = tm["fga"] - tm["oreb"] + tm["tov"] + 0.44 * tm["fta"]
tm["poss_opp"] = tm["opp_fga"] - tm["opp_oreb"] + tm["opp_tov"] + 0.44 * tm["opp_fta"]
tm["game_poss"] = 0.5 * (tm["poss_team"] + tm["poss_opp"])
tm = tm.sort_values(["season", "team_id", "game_date", "game_id"]).reset_index(drop=True)

g = tm.groupby(["season", "team_id"], sort=False)
# strictly-prior season-to-date team pace and opponent-allowed rates
for src, dst in [("game_poss", "std_game_poss"), ("opp_pts", "std_allow_pts"),
                 ("opp_reb", "std_allow_reb"), ("opp_ast", "std_allow_ast")]:
    sh = g[src].shift(1)
    tm[dst] = sh.groupby([tm["season"], tm["team_id"]], sort=False).transform(
        lambda s: s.expanding(min_periods=1).mean())
tm["n_prior_team"] = g.cumcount()

# league season-to-date means (strictly prior, by date) for normalisation
tm["gd"] = tm["game_date"]
lg = (tm.sort_values("gd").groupby("season", sort=False)
        .apply(lambda d: pd.Series(
            d["game_poss"].expanding(min_periods=1).mean().shift(1).values, index=d.index),
            include_groups=False))
tm["lg_poss"] = lg.reset_index(level=0, drop=True).sort_index()
for s in ["pts", "reb", "ast"]:
    lgs = (tm.sort_values("gd").groupby("season", sort=False)
             .apply(lambda d: pd.Series(
                 d[s].expanding(min_periods=1).mean().shift(1).values, index=d.index),
                 include_groups=False))
    tm["lg_" + s] = lgs.reset_index(level=0, drop=True).sort_index()

team_ctx = tm[["game_id", "team_id", "opp_team_id", "season", "game_poss",
               "std_game_poss", "std_allow_pts", "std_allow_reb", "std_allow_ast",
               "n_prior_team", "lg_poss", "lg_pts", "lg_reb", "lg_ast"]].copy()
assert_partition(team_ctx, "team_ctx")

# opponent view: what the OPPONENT allows, keyed by the opponent's own team row
opp_ctx = team_ctx[["game_id", "team_id", "std_allow_pts", "std_allow_reb",
                    "std_allow_ast", "std_game_poss", "n_prior_team"]].copy()
opp_ctx.columns = ["game_id", "opp_team_id", "opp_allow_pts", "opp_allow_reb",
                   "opp_allow_ast", "opp_std_poss", "opp_n_prior"]

# -------------------------------------------------------------- player master
mp = pd.read_parquet(ROOT + r"\data\masters\master_player.parquet")
mp = mp[mp["season"].isin(PARTITION)].copy()          # FILTER-POINT
assert_partition(mp, "master_player raw")

for c in ["minutes", "pts", "reb", "ast", "possessions", "usage_percentage", "starter_flag",
          "is_home"]:
    mp[c] = pd.to_numeric(mp[c], errors="coerce").astype(float)

mp = mp[mp["minutes"].fillna(0) > 0].copy()           # played rows only
mp = mp.sort_values(["player_id", "season", "game_date", "game_id"]).reset_index(drop=True)
assert_partition(mp, "master_player played rows")

df = mp.merge(team_ctx.drop(columns=["opp_team_id"]), on=["game_id", "team_id", "season"],
              how="left", validate="m:1")
df = df.merge(opp_ctx, on=["game_id", "opp_team_id"], how="left", validate="m:1")
assert_partition(df, "player+context merge")
print("merge nulls: game_poss", df["game_poss"].isna().sum(),
      "opp_allow_pts", df["opp_allow_pts"].isna().sum())

# ------------------------------------------------------------ context factors
# c_g : multiplicative context of the game that PRODUCED the observation
#       (realised pace of that game, home/away, opponent-allowed strength).
# c_t : the same quantity PROJECTED from strictly-pregame-observable info.
#
# Home coefficient is estimated on the SELECTION seasons only (2021-2022) and
# then frozen; the scored seasons never inform it.
sel = df[df["season"].isin(SELECT_SEASONS)]
HOME_MULT = {}
for s in ["pts", "reb", "ast", "minutes"]:
    h = sel.loc[sel["is_home"] == 1, s].mean()
    a = sel.loc[sel["is_home"] == 0, s].mean()
    o = sel[s].mean()
    HOME_MULT[s] = (h / o, a / o)
    print(f"[home-mult frozen on 2021-2022] {s}: home={h/o:.4f} away={a/o:.4f}")

MEAN_POSS = float(sel["game_poss"].mean())
print(f"[selection-season mean game possessions] {MEAN_POSS:.3f}")


def clip_ratio(x, lo=0.85, hi=1.15):
    return np.clip(x, lo, hi)


df["pace_g"] = clip_ratio(df["game_poss"] / MEAN_POSS, 0.80, 1.20)
# projected pace: strictly-prior season-to-date poss of both teams
proj_poss = 0.5 * (df["std_game_poss"].fillna(MEAN_POSS) + df["opp_std_poss"].fillna(MEAN_POSS))
df["pace_t"] = clip_ratio(proj_poss / MEAN_POSS, 0.80, 1.20)

MIN_TEAM_GAMES = 5
for s, allow, lgcol in [("pts", "opp_allow_pts", "lg_pts"), ("reb", "opp_allow_reb", "lg_reb"),
                        ("ast", "opp_allow_ast", "lg_ast")]:
    ratio = df[allow] / df[lgcol]
    ratio = ratio.where(df["opp_n_prior"] >= MIN_TEAM_GAMES, 1.0).fillna(1.0)
    df["opp_" + s] = clip_ratio(ratio)

df["home_pts"] = np.where(df["is_home"] == 1, HOME_MULT["pts"][0], HOME_MULT["pts"][1])
df["home_reb"] = np.where(df["is_home"] == 1, HOME_MULT["reb"][0], HOME_MULT["reb"][1])
df["home_ast"] = np.where(df["is_home"] == 1, HOME_MULT["ast"][0], HOME_MULT["ast"][1])
df["home_minutes"] = np.where(df["is_home"] == 1, HOME_MULT["minutes"][0],
                              HOME_MULT["minutes"][1])

# c_g uses REALISED pace (observable after the fact, for a past game);
# c_t uses PROJECTED pace (pregame-observable). Opponent factor is already
# strictly-prior/leave-one-out by construction on both sides.
for s in ["pts", "reb", "ast"]:
    df["c_g_" + s] = df["pace_g"] * df["home_" + s] * df["opp_" + s]
    df["c_t_" + s] = df["pace_t"] * df["home_" + s] * df["opp_" + s]
# minutes: pace/opponent are not credible minutes context; home only.
df["c_g_minutes"] = df["home_minutes"]
df["c_t_minutes"] = df["home_minutes"]

# ---------------------------------------------------------- prior-season mean
prior = (df.groupby(["player_id", "season"])[["pts", "reb", "ast", "minutes"]]
           .mean().reset_index())
prior["season"] = prior["season"] + 1
prior = prior.rename(columns={c: "prior_" + c for c in ["pts", "reb", "ast", "minutes"]})
df = df.merge(prior, on=["player_id", "season"], how="left", validate="m:1")
assert_partition(df, "after prior-season merge")
for s in ["pts", "reb", "ast", "minutes"]:
    # players with no prior season in the partition (incl. every 2021 row) fall
    # back to the SELECTION-season league mean of that stat. Documented choice.
    df["prior_" + s] = df["prior_" + s].fillna(float(sel[s].mean()))

# --------------------------------------------------------------- slice keys
df["n_prior"] = df.groupby(["player_id", "season"], sort=False).cumcount()
gk = [df["player_id"], df["season"]]
df["std_minutes"] = (df.groupby(["player_id", "season"], sort=False)["minutes"].shift(1)
                       .groupby(gk, sort=False).transform(lambda s: s.expanding(1).mean()))
df["std_usage"] = (df.groupby(["player_id", "season"], sort=False)["usage_percentage"].shift(1)
                     .groupby(gk, sort=False).transform(lambda s: s.expanding(1).mean()))

assert_partition(df, "FINAL frame")
keep = ["game_id", "season", "season_type", "game_date", "team_id", "opp_team_id", "is_home",
        "player_id", "player_name", "position", "starter_flag", "minutes", "pts", "reb", "ast",
        "possessions", "usage_percentage", "n_prior", "std_minutes", "std_usage",
        "pace_g", "pace_t", "opp_pts", "opp_reb", "opp_ast",
        "c_g_pts", "c_t_pts", "c_g_reb", "c_t_reb", "c_g_ast", "c_t_ast",
        "c_g_minutes", "c_t_minutes",
        "prior_pts", "prior_reb", "prior_ast", "prior_minutes"]
out = df[keep].copy()
out.to_parquet(HERE + r"\frame.parquet", index=False)
print("wrote frame.parquet", out.shape)
print("frame seasons:", sorted(out["season"].unique()))
print(out.groupby("season").size().to_dict())
