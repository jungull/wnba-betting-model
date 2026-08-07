"""
E0 I0010 / F_POSITIONAL_MATCHUP -- build player-game feature frame.

Hypothesis: opponent defensive allowance TO A PLAYER'S POSITION GROUP interacts with
that player's own context-normalized tendency, beyond the two additive main effects,
for points / rebounds / assists separately.

PARTITION (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY. Filter applied immediately after
load, before any other computation. Marked # FILTER-POINT. Asserted.

Manifest check: data/masters/master_player.parquet.manifest.json says
  "asof_granularity": "row"  -> filtering to 2021-2024 is SUFFICIENT (artifact is safe).
(It also says fit_through_season 2026 / fit_seasons 2021..2026, which is exactly the case
 the row-granularity rule covers.)

Deterministic. No randomness in this script.
"""
import numpy as np
import pandas as pd
import os

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0010_positional_matchup")
PARTITION = [2021, 2022, 2023, 2024]
TARGETS = ["pts", "reb", "ast"]
MIN_MINUTES_ANALYSIS = 10.0   # analysis rows
MIN_MINUTES_POOL = 1.0        # rows that count toward an opponent's "allowance"
SHRINK_K = 5.0                # pseudo-units of 100-possessions for pregame shrinkage
MIN_PRIOR_UNITS = 3.0         # require >=300 prior possessions faced/played

pd.set_option("display.width", 220)


def hdr(s):
    print("\n" + "=" * 78)
    print(s)
    print("=" * 78)


# ---------------------------------------------------------------- load + filter
hdr("LOAD + PARTITION FILTER")
mp = pd.read_parquet(os.path.join(ROOT, r"data\masters\master_player.parquet"))
print("raw shape:", mp.shape, "raw seasons:", sorted(mp["season"].unique()))
# FILTER-POINT  <<< exploration partition applied here, before anything else
mp = mp[mp["season"].isin(PARTITION)].copy()
assert set(mp["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
print("post-filter shape:", mp.shape, "seasons:", sorted(mp["season"].unique()))
print("max game_date in frame:", mp["game_date"].max())

mp = mp[mp["season_type"] == "Regular Season"].copy()
print("regular season only:", mp.shape)

for c in ["pts", "reb", "ast", "oreb", "dreb", "fga", "fg3a"]:
    mp[c] = mp[c].astype("float64")
mp["minutes"] = mp["minutes"].astype("float64")
mp["possessions"] = mp["possessions"].astype("float64")
mp["team_id"] = mp["team_id"].astype("int64")
mp["opp_team_id"] = mp["opp_team_id"].astype("int64")
mp["player_id"] = mp["player_id"].astype("int64")

mp = mp[(mp["minutes"] >= MIN_MINUTES_POOL) & (mp["possessions"] > 0)].copy()
mp = mp.sort_values(["game_date", "game_id", "team_id", "player_id"]).reset_index(drop=True)
print("after minutes>=%.0f & possessions>0:" % MIN_MINUTES_POOL, mp.shape)
mp["unit"] = mp["possessions"] / 100.0   # "opportunity units" = per-100-possessions denominator

# ------------------------------------------------------- position group derivation
hdr("POSITION GROUP DERIVATION")
raw_pos = mp["position"].fillna("").astype(str).str.strip()
print("raw `position` label counts:", raw_pos.value_counts().to_dict())
print("labelled rows: %d / %d (%.3f)" % ((raw_pos != "").sum(), len(raw_pos), (raw_pos != "").mean()))
print("starter_flag==1 rows: %d ; labelled&starter: %d ; labelled&non-starter: %d"
      % ((mp["starter_flag"] == 1).sum(),
         ((raw_pos != "") & (mp["starter_flag"] == 1)).sum(),
         ((raw_pos != "") & (mp["starter_flag"] != 1)).sum()))
print("-> `position` is populated ONLY for starters: it is a STARTING-LINEUP SLOT label,")
print("   not a scouting position. 5 slots per team-game (2 G, 2 F, 1 C).")

# Expanding modal slot label over games STRICTLY BEFORE the current game date.
# A player plays at most one game per date, so a within-player shift(1) is exact.
mp["_G"] = (raw_pos == "G").astype(float)
mp["_F"] = (raw_pos == "F").astype(float)
mp["_C"] = (raw_pos == "C").astype(float)
g = mp.groupby("player_id", sort=False)
prior_counts = g[["_G", "_F", "_C"]].cumsum() - mp[["_G", "_F", "_C"]].values
pc = prior_counts.to_numpy()
tot = pc.sum(axis=1)
lab = np.array(["G", "F", "C"])
pos_group = np.where(tot > 0, lab[np.argmax(pc, axis=1)], "U")
mp["pos_group"] = pos_group
mp["pos_prior_n"] = tot

print("\npos_group counts (all pooled rows):", pd.Series(pos_group).value_counts().to_dict())
print("coverage (non-U) of pooled rows: %.3f" % (mp["pos_group"] != "U").mean())
an_mask = mp["minutes"] >= MIN_MINUTES_ANALYSIS
print("coverage (non-U) of minutes>=%.0f rows: %.3f"
      % (MIN_MINUTES_ANALYSIS, (mp.loc[an_mask, "pos_group"] != "U").mean()))
print("\ncoverage by season (minutes>=10):")
print(mp[an_mask].assign(k=(mp.loc[an_mask, "pos_group"] != "U")).groupby("season")["k"].agg(["mean", "size"]).to_string())

# what the derived group looks like statistically (sanity, NOT used to build it)
print("\nsanity -- mean per-100-poss profile by derived group (descriptive only):")
tmp = mp[mp["pos_group"] != "U"].copy()
for t in TARGETS:
    tmp[t + "_r"] = tmp[t] / tmp["unit"]
print(tmp.groupby("pos_group")[[t + "_r" for t in TARGETS]].mean().round(2).to_string())
print("group n:", tmp["pos_group"].value_counts().to_dict())

# stability: does a player's derived group flip within a season?
st = mp[mp["pos_group"] != "U"].groupby(["player_id", "season"])["pos_group"].nunique()
print("\nplayer-seasons whose derived group flips mid-season: %d / %d (%.3f)"
      % ((st > 1).sum(), len(st), (st > 1).mean()))

# Restrict everything downstream to rows with a known group.
POOL = mp[mp["pos_group"] != "U"].copy().reset_index(drop=True)
print("\npooled frame used for allowances:", POOL.shape)


# ---------------------------------------------------------------- helpers
def prior_expanding(df, keys, valcols, prefix):
    """Cumulative sum of valcols over rows STRICTLY BEFORE the row's game_date, within `keys`.
    Date-level aggregation so same-day games are excluded from each other."""
    daily = df.groupby(keys + ["game_date"], as_index=False)[valcols].sum()
    daily = daily.sort_values(keys + ["game_date"]).reset_index(drop=True)
    cum = daily.groupby(keys, sort=False)[valcols].cumsum()
    prior = cum.to_numpy() - daily[valcols].to_numpy()
    out = daily[keys + ["game_date"]].copy()
    for i, c in enumerate(valcols):
        out[prefix + c] = prior[:, i]
    return df.merge(out, on=keys + ["game_date"], how="left")


def ols_r2(y, X):
    X = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return 1.0 - ss_res / ss_tot


# ---------------------------------------------------------------- feature build
hdr("FEATURE BUILD (per target)")
frames = {}
for T in TARGETS:
    print("\n---- target: %s ----" % T)
    d = POOL.copy()
    d["s"] = d[T]
    d["u"] = d["unit"]

    # ============ STEP 1+2: within-season LEAVE-ONE-OUT positional allowance ============
    # cell = (season, opp_team_id, pos_group). Strict LOO: drop the whole game being
    # explained AND every row belonging to this player in that cell.
    cell = ["season", "opp_team_id", "pos_group"]
    Tt = d.groupby(cell)[["s", "u"]].transform("sum")
    Gg = d.groupby(cell + ["game_id"])[["s", "u"]].transform("sum")
    Pp = d.groupby(cell + ["player_id"])[["s", "u"]].transform("sum")
    # inclusion-exclusion: player's rows within this game == this single row
    num = Tt["s"] - Gg["s"] - Pp["s"] + d["s"]
    den = Tt["u"] - Gg["u"] - Pp["u"] + d["u"]
    d["allow_loo"] = np.where(den > 1e-9, num / den, np.nan)

    # naive (no LOO) version, to show what the correction is worth
    d["allow_naive"] = Tt["s"] / Tt["u"]

    # ============ STEP 3: PREGAME-OBSERVABLE positional allowance ============
    # expanding within season, strictly before game_date, minus this player's own prior rows,
    # shrunk toward the expanding league mean for that position group.
    d = prior_expanding(d, cell, ["s", "u"], "cel_")
    d = prior_expanding(d, cell + ["player_id"], ["s", "u"], "cpl_")
    d = prior_expanding(d, ["season", "pos_group"], ["s", "u"], "lg_")
    d = prior_expanding(d, ["season", "player_id"], ["s", "u"], "own_")
    d = prior_expanding(d, ["season", "opp_team_id"], ["s", "u"], "def_")           # overall D
    d = prior_expanding(d, ["season", "opp_team_id", "player_id"], ["s", "u"], "dpl_")

    # league mean rate for the group, expanding; prior-season fallback for opening days
    lg_rate = np.where(d["lg_u"] > 1.0, d["lg_s"] / d["lg_u"], np.nan)
    ps = (d.groupby(["season", "pos_group"])[["s", "u"]].sum().reset_index())
    ps["prev_rate"] = ps["s"] / ps["u"]
    ps["season"] = ps["season"] + 1     # becomes the PRIOR-season fallback for season+1
    d = d.merge(ps[["season", "pos_group", "prev_rate"]], on=["season", "pos_group"], how="left")
    lg_rate = pd.Series(lg_rate, index=d.index).fillna(d["prev_rate"])
    d["lg_rate"] = lg_rate

    # opponent's prior allowance to this group, excluding this player's own prior contribution
    pn = d["cel_s"] - d["cpl_s"]
    pu = d["cel_u"] - d["cpl_u"]
    d["prior_units_pos"] = pu
    d["allow_pre"] = (pn + SHRINK_K * d["lg_rate"]) / (pu + SHRINK_K)
    d.loc[pu < MIN_PRIOR_UNITS, "allow_pre"] = np.nan

    # overall opponent defensive allowance (ALL position groups), same discipline -- STEP 5 control
    on = d["def_s"] - d["dpl_s"]
    ou = d["def_u"] - d["dpl_u"]
    lg_all = prior_expanding(d[["season", "game_date", "s", "u"]].copy(), ["season"], ["s", "u"], "all_")
    d["all_s"] = lg_all["all_s"].values
    d["all_u"] = lg_all["all_u"].values
    lg_all_rate = np.where(d["all_u"] > 1.0, d["all_s"] / d["all_u"], np.nan)
    d["lg_all_rate"] = pd.Series(lg_all_rate, index=d.index).fillna(d["lg_rate"])
    d["def_pre"] = (on + SHRINK_K * d["lg_all_rate"]) / (ou + SHRINK_K)
    d.loc[ou < MIN_PRIOR_UNITS, "def_pre"] = np.nan

    # ============ own tendency (both disciplines) ============
    OwnT = d.groupby(["season", "player_id"])[["s", "u"]].transform("sum")
    d["own_loo"] = np.where((OwnT["u"] - d["u"]) > 1e-9,
                            (OwnT["s"] - d["s"]) / (OwnT["u"] - d["u"]), np.nan)
    # pregame own rate: expanding within season, shrunk to prior-season own rate then league group rate
    prev_own = d.groupby(["season", "player_id"])[["s", "u"]].sum().reset_index()
    prev_own["prev_own_rate"] = prev_own["s"] / prev_own["u"]
    prev_own["season"] = prev_own["season"] + 1
    d = d.merge(prev_own[["season", "player_id", "prev_own_rate"]], on=["season", "player_id"], how="left")
    own_anchor = d["prev_own_rate"].fillna(d["lg_rate"])
    d["own_pre"] = (d["own_s"] + SHRINK_K * own_anchor) / (d["own_u"] + SHRINK_K)
    d.loc[d["own_u"] < MIN_PRIOR_UNITS, "own_pre"] = np.nan

    # ============ outcome ============
    d["y"] = d["s"] / d["u"]     # player-game rate per 100 possessions

    d["is_analysis"] = (d["minutes"] >= MIN_MINUTES_ANALYSIS)
    # NB: `observed_time` (a LOCAL FILE MTIME, a mid-2026 build stamp, per the manifest -- explicitly
    # NOT an as-of bound) is deliberately excluded so it never reaches this experiment's bytes.
    keep = ["game_id", "season", "game_date", "team_id", "opp_team_id", "player_id",
            "player_name", "pos_group", "minutes", "possessions", "unit", "s", "y",
            "allow_loo", "allow_naive", "allow_pre", "def_pre", "own_loo", "own_pre",
            "prior_units_pos", "is_analysis"]
    d = d[keep].copy()
    d["target"] = T
    assert set(d["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION in feature frame"

    a = d[d["is_analysis"]]
    print("analysis rows (minutes>=10): %d" % len(a))
    print("  non-null allow_loo %d | allow_pre %d | own_loo %d | own_pre %d | def_pre %d"
          % (a["allow_loo"].notna().sum(), a["allow_pre"].notna().sum(),
             a["own_loo"].notna().sum(), a["own_pre"].notna().sum(), a["def_pre"].notna().sum()))
    both = a.dropna(subset=["allow_pre", "own_pre", "def_pre"])
    print("  complete pregame rows: %d (%.3f of analysis rows)" % (len(both), len(both) / len(a)))
    print("  allowance spread: LOO sd=%.3f mean=%.3f | PRE sd=%.3f mean=%.3f | naive sd=%.3f"
          % (a["allow_loo"].std(), a["allow_loo"].mean(),
             a["allow_pre"].std(), a["allow_pre"].mean(), a["allow_naive"].std()))
    print("  corr(own_loo, allow_loo)=%.4f   corr(own_loo, allow_naive)=%.4f  [LOO must shrink this]"
          % (a[["own_loo", "allow_loo"]].corr().iloc[0, 1],
             a[["own_loo", "allow_naive"]].corr().iloc[0, 1]))
    print("  corr(allow_pre, def_pre)=%.4f  [step-5 confound: positional vs overall defence]"
          % (a[["allow_pre", "def_pre"]].corr().iloc[0, 1]))
    frames[T] = d

allf = pd.concat(frames.values(), ignore_index=True)
assert set(allf["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION before write"
outp = os.path.join(OUT, "player_game_features.csv")
allf.to_csv(outp, index=False)
print("\nwrote %s  shape=%s  seasons=%s" % (outp, allf.shape, sorted(allf["season"].unique())))
