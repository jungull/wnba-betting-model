"""
E0 I0013 -- POSSESSION VOLUME as a driver of player production, at PLAYER level.

Shared base for this screen. Imports E0_I0012_layer3_noncollinear/base.py READ-ONLY for its
loader / partition gate / manifest gate / shift discipline, and IMMEDIATELY RE-POINTS its OUT
constant into THIS directory so no reused helper can ever write outside our write scope.

WHAT IS DIFFERENT FROM I0012
----------------------------
I0012 modelled y = per-100-POSSESSION rate.  That divides possession volume out of the outcome
by construction, so it could only ever see volume as an interaction.  This screen models the
RAW COUNTING STAT and asks whether possession volume is an EXPOSURE channel:

    count  =  rate  x  minutes  x  possessions-per-minute

The base model therefore already contains the naive prediction (rate x expected minutes), and
every candidate is asked for an increment OVER that.

BASE MODEL (all five terms pregame-observable):
    y_count ~ O + D + O*D + Mexp + O*Mexp
      O    = player's pregame expanding per-100-possession rate of the target stat
      D    = opponent's pregame expanding OVERALL allowance of the target stat per 100 poss,
             computed EXCLUDING this player's own prior contribution to it
      O*D  = the base matchup interaction (I0012's base model, carried forward)
      Mexp = player's pregame expanding minutes per game
      O*Mexp = rate x exposure, i.e. the naive counting-stat prediction

COSTUME RULE (trap 1), inherited from I0012 unchanged:
    every candidate M is centered within season and then residualized on [D, O*D] BEFORE it is
    allowed near the outcome.  Only the residual Mres is tested.  Raw within-season collinearity
    of M against D is reported for every candidate.

RETROSPECTIVE-BASELINE RULE (trap 2):
    every constructed quantity on BOTH sides uses base.prior_expanding, which aggregates to date
    level and then takes a strict cumulative-minus-self within (season, key).  A value serving a
    target game comes only from rows STRICTLY BEFORE that game's date, in the SAME season.  No
    leave-one-out, no leave-one-season-out, no full-season baseline appears anywhere.

ANTICONSERVATIVE-t RULE (trap 3):
    seven of the nine candidates are opponent- or own-TEAM-season aggregates: 12 teams per season,
    48 team-season clusters over the partition, value shared across every row facing that team.
    Classical OLS t is NOT trusted anywhere.  Every cell gets (a) a CLUSTER-LEVEL permutation null
    at the team-season level, (b) the naive row-level permutation reported ALONGSIDE it purely to
    show how much narrower the wrong null is, and (c) a cluster-robust sandwich SE with the cluster
    count printed.

NO-OP PLACEBO RULE (trap 4):
    the defective control -- permute the grouping KEY and RECOMPUTE the aggregate from the permuted
    key -- is run ON PURPOSE in noop_diagnostic() to show its sd-exactly-0.000000 signature.  The
    real controls permute the ASSIGNMENT of an ALREADY-COMPUTED value to rows.

PARTITION (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY, enforced by base.load_player/load_team
    and re-asserted at every write.  # FILTER-POINT markers below.

R2 CONVENTION (D069): plain unweighted OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean.
    base.r2 is exactly that.  No weighted regression anywhere in this screen; the defective
    wls_r2 helper in older screens is NOT imported and NOT used.

HAZARDS: master_player.pace / pace_per40 / estimated_pace are corrupt (verified in recon) and are
    NOT read.  master_player.possessions is clean (verified) and is used.  master_player.position
    is a lineup-slot label and is not used.  observed_time is dropped at load.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0013_possession_volume")
I0012 = os.path.join(ROOT, r"experiments\exploration\E0_I0012_layer3_noncollinear")

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
if I0012 not in sys.path:
    sys.path.insert(0, I0012)

import base as B  # noqa: E402  READ-ONLY import from E0_I0012

# >>> re-point every write target of the imported helper into OUR directory <<<
B.OUT = OUT

PARTITION = [2021, 2022, 2023, 2024]
HOLDOUT = {2025, 2026}
TARGETS = ["pts", "reb", "ast"]
MIN_MIN_ANALYSIS = 10.0
MIN_PRIOR_POSS_TEAM = 300.0     # >= 3 games of team possessions before a team value is usable
SHRINK_MIN = 30.0               # minutes of shrinkage on player possessions-per-minute
SHRINK_G = 2.0                  # games of shrinkage on expected minutes
SEED = 20260807
NDRAW = 200

pd.set_option("display.width", 250)
np.seterr(divide="ignore", invalid="ignore")


def hdr(s):
    print("\n" + "=" * 88)
    print(s)
    print("=" * 88)


def guard(df, where):
    """# FILTER-POINT assertion + run-log print required by GRAPH_POLICY 13.2."""
    ss = sorted(int(x) for x in pd.unique(df["season"]))
    print("  [PARTITION] %-46s seasons=%s  n=%d" % (where, ss, len(df)))
    assert set(ss) <= set(PARTITION), "PARTITION VIOLATION at %s: %s" % (where, ss)
    assert not (set(ss) & HOLDOUT), "HOLDOUT TOUCHED at %s: %s" % (where, ss)
    return df


def safe_write(df, name):
    """Drop banned cols, re-assert partition, write INTO OUR DIRECTORY ONLY."""
    d = df.drop(columns=[c for c in B.BANNED_COLS if c in df.columns]).copy()
    if "season" in d.columns:
        guard(d, "pre-write " + name)
    p = os.path.join(OUT, name)
    assert os.path.abspath(p).startswith(os.path.abspath(OUT)), "WRITE SCOPE VIOLATION: %s" % p
    d.to_csv(p, index=False)
    print("  wrote %s  shape=%s" % (name, d.shape))
    return p


# --------------------------------------------------------------------- team-side pregame table
def build_team_pre(mt):
    """Strictly-prior, in-season expanding team quantities.

    Every field below is a cumulative sum over the team's games STRICTLY BEFORE the row's date
    (base.prior_expanding), divided by a matching strictly-prior denominator.  Nothing reads the
    target game or any later game, and nothing reads any other season.

    Fields, from the perspective of the OPPONENT team Z that a player is facing:
      pace48   Z's possessions per 48 min                       (tempo -> total game possessions)
      fgaA48   FGA Z allows per 48 min                          (supply of shots for the player)
      missA48  missed FG Z allows per 48                         (OREB supply for the player)
      missO48  Z's OWN missed FG per 48                          (DREB supply for the player)
      orebA100 OREB Z allows per 100 poss                        (layer-2 OREB allowance)
      orebR100 Z's OWN OREB per 100 poss                         (used on the OWN-team join)
    """
    tp = B.team_possessions(mt)
    t = mt.merge(tp[["game_id", "team_id", "team_poss"]], on=["game_id", "team_id"], how="left")
    for c in ["fga", "fgm", "fta", "tov", "oreb", "minutes",
              "opp_fga", "opp_fgm", "opp_oreb", "opp_pts"]:
        t[c] = pd.to_numeric(t[c], errors="coerce").astype("float64")
    t["n_poss"] = t["team_poss"]
    t["n_min"] = t["minutes"]
    t["n_ofga"] = t["opp_fga"]
    t["n_omiss"] = t["opp_fga"] - t["opp_fgm"]     # misses BY the team facing Z  -> OREB supply
    t["n_smiss"] = t["fga"] - t["fgm"]             # Z's OWN misses               -> DREB supply
    t["n_ooreb"] = t["opp_oreb"]                   # OREB Z allows
    t["n_oreb"] = t["oreb"]                        # Z's own OREB
    t["n_g"] = 1.0
    nums = ["n_poss", "n_min", "n_ofga", "n_omiss", "n_smiss", "n_ooreb", "n_oreb", "n_g"]

    p = B.prior_expanding(t, ["season", "team_id"], nums, "pr_")
    gm = p["pr_n_min"] / 5.0                       # prior GAME minutes (team minutes / 5 on court)
    per48 = np.where(gm > 0, 48.0 / gm, np.nan)
    u = p["pr_n_poss"] / 100.0

    out = p[["season", "team_id", "game_id", "gdate"]].copy()
    out["pace48"] = p["pr_n_poss"] * per48
    out["fgaA48"] = p["pr_n_ofga"] * per48
    out["missA48"] = p["pr_n_omiss"] * per48
    out["missO48"] = p["pr_n_smiss"] * per48
    out["orebA100"] = np.where(u > 0, p["pr_n_ooreb"] / u, np.nan)
    out["orebR100"] = np.where(u > 0, p["pr_n_oreb"] / u, np.nan)
    ok = p["pr_n_poss"] >= MIN_PRIOR_POSS_TEAM
    out.loc[~ok, ["pace48", "fgaA48", "missA48", "missO48", "orebA100", "orebR100"]] = np.nan
    out["prior_poss"] = p["pr_n_poss"]
    return guard(out, "team pregame table")


TEAM_FIELDS = ["pace48", "fgaA48", "missA48", "missO48", "orebA100", "orebR100"]


# --------------------------------------------------------------------- player-side pregame extras
def add_player_pregame(d):
    """Add strictly-prior player exposure quantities to base.build_base's frame.

    Mexp   pregame expanding MINUTES PER GAME, shrunk toward the expanding league mean.
    ppm    pregame expanding POSSESSIONS PER MINUTE, shrunk toward the expanding league mean.
           This is the second exposure component: minutes says how long you are out there,
           ppm says how many possessions a minute of your floor time is worth.
    usg    pregame expanding usage proxy (FGA + 0.44*FTA + TOV) per 100 poss, for heterogeneity.

    All three come from base.prior_expanding -> strictly prior, same season, date-aggregated.
    League means are themselves strictly-prior expanding (with a previous-season fallback), so no
    quantity anywhere reads the target game or any later game.
    """
    d = d.copy()
    d["_g"] = 1.0
    d["_min"] = d["minutes"].astype(float)
    d["_poss"] = d["possessions"].astype(float)
    d["_usgn"] = (d["fga"].fillna(0) + 0.44 * d["fta"].fillna(0) + d["tov"].fillna(0)).astype(float)

    d = B.prior_expanding(d, ["season", "player_id"], ["_min", "_poss", "_g", "_usgn"], "pp_")
    la = B.prior_expanding(d[["season", "gdate", "_min", "_poss", "_g", "_usgn"]].copy(),
                           ["season"], ["_min", "_poss", "_g", "_usgn"], "lg_")
    lg_ppm = np.where(la["lg__min"].values > 0, la["lg__poss"].values / la["lg__min"].values, np.nan)
    lg_mpg = np.where(la["lg__g"].values > 0, la["lg__min"].values / la["lg__g"].values, np.nan)

    prev = d.groupby("season")[["_min", "_poss", "_g"]].sum().reset_index()
    prev["pv_ppm"] = prev["_poss"] / prev["_min"]
    prev["pv_mpg"] = prev["_min"] / prev["_g"]
    prev["season"] += 1                                      # prior-season fallback only
    d = d.merge(prev[["season", "pv_ppm", "pv_mpg"]], on="season", how="left")
    d["lg_ppm"] = pd.Series(lg_ppm, index=d.index).fillna(d["pv_ppm"])
    d["lg_mpg"] = pd.Series(lg_mpg, index=d.index).fillna(d["pv_mpg"])
    d["lg_ppm"] = d["lg_ppm"].fillna(d["_poss"].sum() / d["_min"].sum())
    d["lg_mpg"] = d["lg_mpg"].fillna(d["_min"].sum() / d["_g"].sum())

    d["ppm"] = (d["pp__poss"] + SHRINK_MIN * d["lg_ppm"]) / (d["pp__min"] + SHRINK_MIN)
    d.loc[d["pp__min"] < SHRINK_MIN, "ppm"] = np.nan
    d["Mexp"] = (d["pp__min"] + SHRINK_G * d["lg_mpg"]) / (d["pp__g"] + SHRINK_G)
    d.loc[d["pp__g"] < 2, "Mexp"] = np.nan
    d["usg_pre"] = np.where(d["pp__poss"] > 0, d["pp__usgn"] / (d["pp__poss"] / 100.0), np.nan)
    d.loc[d["pp__poss"] < 300, "usg_pre"] = np.nan
    return d


# --------------------------------------------------------------------- regression machinery
def _design(cols):
    return np.column_stack([np.ones(len(cols[0]))] + [np.asarray(c, float) for c in cols])


def ols(y, cols):
    X = _design(cols)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    sse = float(r @ r)
    sst = float(((y - y.mean()) ** 2).sum())     # D069: unweighted SST about the unweighted mean
    return b, r, 1.0 - sse / sst, X


def r2(y, cols):
    return ols(y, cols)[2]


def cluster_se(y, cols, clusters):
    """CR1 cluster-robust sandwich SE.  Returns (beta_last, se_last, t_last, n_clusters,
    se_classical_last, t_classical_last)."""
    b, r, _, X = ols(y, cols)
    n, k = X.shape
    XtXi = np.linalg.pinv(X.T @ X)
    cl = pd.Series(clusters).values
    uq = pd.unique(cl)
    meat = np.zeros((k, k))
    for c in uq:
        m = cl == c
        Xc = X[m]
        uc = Xc.T @ r[m]
        meat += np.outer(uc, uc)
    G = len(uq)
    adj = (G / max(G - 1, 1)) * ((n - 1) / max(n - k, 1))
    V = XtXi @ (adj * meat) @ XtXi
    se_cl = float(np.sqrt(max(V[-1, -1], 0.0)))
    s2 = float(r @ r) / max(n - k, 1)
    se_ols = float(np.sqrt(max(s2 * XtXi[-1, -1], 0.0)))
    beta = float(b[-1])
    return dict(beta=beta, se_cluster=se_cl, t_cluster=beta / se_cl if se_cl > 0 else np.nan,
                n_clusters=int(G), se_classical=se_ols,
                t_classical=beta / se_ols if se_ols > 0 else np.nan)


def residualize_and_scale(Mz, D, OD):
    """Costume rule.  Residualize the candidate on overall opponent defence AND the base O*D
    interaction, then unit-scale.  A candidate carrying nothing after this is overall strength
    renamed."""
    Mr = B.resid_on(Mz, [D, OD])
    sd = Mr.std()
    return Mr / sd if sd > 0 else Mr


def build_analysis_frame(mp, TEAM, T, cand_cols):
    """The exact frame run_screen.py analyses, factored out so the max-T / robustness stage can
    rebuild it identically instead of re-deriving it.  run_maxt_robust.py asserts that the
    resulting R2_base reproduces run_screen.py's to 1e-12."""
    d = B.build_base(mp, T)
    d = add_player_pregame(d)
    guard(d, "player frame target=%s" % T)                                     # FILTER-POINT
    opp_ren = {f: "opp_" + f for f in TEAM_FIELDS}
    own_ren = {f: "own_" + f for f in TEAM_FIELDS}
    d = d.merge(TEAM[["season", "game_id", "team_id"] + TEAM_FIELDS]
                .rename(columns={"team_id": "opp_team_id", **opp_ren}),
                on=["season", "game_id", "opp_team_id"], how="left")
    d = d.merge(TEAM[["season", "game_id", "team_id"] + TEAM_FIELDS].rename(columns=own_ren),
                on=["season", "game_id", "team_id"], how="left")
    d["exp_gposs"] = 0.5 * (d["opp_pace48"] + d["own_pace48"])
    need = ["own_pre", "def_pre", "Mexp", "ppm", "usg_pre", "exp_gposs"] + list(cand_cols)
    W = d[d["is_analysis"]].dropna(subset=need + ["s"]).copy().reset_index(drop=True)
    guard(W, "analysis frame target=%s" % T)                                   # FILTER-POINT
    W["O"] = B.zwithin(W, "own_pre")
    W["D"] = B.zwithin(W, "def_pre")
    W["OD"] = W["O"] * W["D"]
    W["ME"] = B.zwithin(W, "Mexp")
    W["OME"] = W["O"] * W["ME"]
    return W


def pct_ge(draws, real):
    draws = np.asarray(draws, float)
    draws = draws[np.isfinite(draws)]
    return float((draws >= real).mean()) if len(draws) else np.nan
