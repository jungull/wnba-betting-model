"""E1_I0030 HOME-ADVANTAGE ACCOUNTING -- local machinery.

WHAT THIS SCREEN IS.  The user's argument is an ACCOUNTING IDENTITY, not a hypothesis:
team points are the sum of player points, so if home teams score measurably more, the increment
is somewhere at player level BY CONSTRUCTION.  A null is therefore not an available answer; the
deliverable is a RECONCILIATION that says where the arithmetic puts it.

INPUTS.  `data/masters/master_team.parquet` and `data/masters/master_player.parquet`, both of
which carry a sibling manifest with asof_granularity == "row" (USABLE_IF_FILTERED).  Filtered to
seasons 2021-2024 on COLUMN VALUES.  `data/reference/team_cities.csv` supplies venue time zones.

WHY NOT `data/possessions/possessions.parquet`.  It has NO sibling manifest -> UNVERIFIABLE under
check_manifest, which is explicitly NOT a pass.  Possessions are therefore derived here from the
box score in master_team by the standard estimator, so their as-of bound is inherited from a
manifest-verified, row-granular artifact.

THE TWO STRUCTURAL FACTS THAT DRIVE EVERYTHING (both verified numerically in s02/s03, not assumed):
  F1  MINUTES ARE A SHARED, FIXED BUDGET.  Both teams in a game play the same number of team
      minutes (200, plus 25 per overtime, and overtime is by definition shared).  So the home
      effect CANNOT be "the home team plays more minutes".
  F2  POSSESSIONS ARE A SHARED GAME PROPERTY.  Real possessions are equal between the two teams to
      within one.  So the home effect CANNOT be "the home team gets more possessions" either --
      pace is a property of the GAME, not of the home team.
Both facts are consequences of the within-game paired design and neither has ever been checked in
this programme.

THE NULL.  `is_home` is PERFECTLY BALANCED WITHIN A GAME: exactly one of the two team-game rows
carries it.  `detect_grouping_level` therefore finds NO coarser constant level (status
NO_COARSER_LEVEL) and a row-level permutation is anticonservative in the usual way.  The EXACT
randomisation test for this design is the one the design itself suggests: randomly RELABEL WHICH OF
THE TWO TEAMS IN EACH GAME IS THE HOME TEAM -- a per-game sign flip on the paired difference.  It
preserves each game's total exactly and destroys only the venue attribution.  This is the same
construction `screenkit.paired_forecast_comparison` uses for paired forecasts, applied to a paired
outcome.  The naive row-level permutation of `is_home` (which does not even preserve one-home-
per-game) is computed for CONTRAST ONLY and never carries a verdict.
"""
from __future__ import annotations

import hashlib
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, "experiments", "exploration", "_screen_kit")
OUT = os.path.join(ROOT, "experiments", "exploration", "E1_I0030_home_advantage_accounting")

sys.dont_write_bytecode = True
if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

SEED = 20260808
EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)

TEAM_PARQUET = os.path.join(ROOT, "data", "masters", "master_team.parquet")
PLAYER_PARQUET = os.path.join(ROOT, "data", "masters", "master_player.parquet")
CITIES_CSV = os.path.join(ROOT, "data", "reference", "team_cities.csv")


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------- possessions
def possessions(fga, oreb, tov, fta):
    """Standard box estimator: FGA - OREB + TOV + 0.44*FTA.

    THIS IS AN ESTIMATE, NOT THE IDENTITY.  Real possessions are equal between the two teams in a
    game to within one; this estimator is not, because the 0.44 coefficient and the OREB term are
    approximations.  Any home-minus-away difference it reports is therefore an upper bound on the
    true possession asymmetry plus estimator noise, and s02 says so.
    """
    return (np.asarray(fga, float) - np.asarray(oreb, float) + np.asarray(tov, float)
            + 0.44 * np.asarray(fta, float))


# ---------------------------------------------------------------------------- loading
def load_team(verbose=True):
    t = pd.read_parquet(TEAM_PARQUET)
    t = t[t["season"].isin(EXPLORATION_SEASONS)].copy()
    t["game_date"] = pd.to_datetime(t["game_date"])
    t["is_home"] = t["is_home"].astype(int)
    for c in ["fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast",
              "stl", "blk", "tov", "pf", "pts", "minutes"]:
        t[c] = pd.to_numeric(t[c], errors="coerce").astype(float)
    t["poss"] = possessions(t["fga"], t["oreb"], t["tov"], t["fta"])
    t["fg2m"] = t["fgm"] - t["fg3m"]
    t["fg2a"] = t["fga"] - t["fg3a"]
    t = t.sort_values(["season", "team_id", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    if verbose:
        print("  team frame %s  games=%d  seasons=%s"
              % (t.shape, t["game_id"].nunique(), sorted(t["season"].unique())))
    return t


def load_player(verbose=True):
    p = pd.read_parquet(PLAYER_PARQUET)
    p = p[p["season"].isin(EXPLORATION_SEASONS)].copy()
    p["game_date"] = pd.to_datetime(p["game_date"])
    p["is_home"] = p["is_home"].astype(int)
    for c in ["fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast",
              "stl", "blk", "tov", "pf", "pts", "minutes"]:
        p[c] = pd.to_numeric(p[c], errors="coerce").astype(float)
    # DNP rows carry NaN minutes and 0 counting stats.  Keep them for the SUM reconciliation
    # (they contribute exactly 0 points) but flag them out of every RATE.
    p["appeared"] = (p["minutes"].fillna(0.0) > 0.0).astype(int)
    p["minutes"] = p["minutes"].fillna(0.0)
    for c in ["fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "tov", "pts"]:
        p[c] = p[c].fillna(0.0)
    p["fg2m"] = p["fgm"] - p["fg3m"]
    p["fg2a"] = p["fga"] - p["fg3a"]
    p = p.sort_values(["season", "player_id", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    if verbose:
        print("  player frame %s  appeared=%d  dnp=%d"
              % (p.shape, int(p["appeared"].sum()), int((1 - p["appeared"]).sum())))
    return p


# ---------------------------------------------------------------------------- venue time zones
# WNBA regular seasons run mid-May to early October: EVERY game in 2021-2024 falls inside US
# daylight-saving time.  The clock offset of each venue is therefore CONSTANT across the partition
# and is hardcoded here rather than computed, so it can be read and checked.  Two consequences that
# matter and are reported rather than buried:
#   * America/Phoenix does not observe DST, so in season Phoenix's clock EQUALS Pacific's.  A
#     PHO<->LAS/LVA/SEA trip is a SAME-ZONE trip for circadian purposes even though the tz strings
#     differ.  Treating the tz string as the zone would manufacture crossings that do not exist.
#   * America/Indiana/Indianapolis observes DST and equals Eastern in season.
TZ_UTC_OFFSET_IN_SEASON = {
    "America/New_York": -4,
    "America/Indiana/Indianapolis": -4,
    "America/Chicago": -5,
    "America/Denver": -6,
    "America/Phoenix": -7,
    "America/Los_Angeles": -7,
    "America/Toronto": -4,
}


def venue_table(verbose=True):
    c = pd.read_csv(CITIES_CSV)
    c = c[["team_id", "abbreviation", "city", "arena", "lat", "lon", "timezone"]].copy()
    c["utc_offset"] = c["timezone"].map(TZ_UTC_OFFSET_IN_SEASON)
    assert c["utc_offset"].notna().all(), "unmapped timezone in team_cities.csv"
    # one row per team_id; PHO/PHX share a team_id across eras with identical venue
    c = c.drop_duplicates(subset=["team_id"], keep="first").set_index("team_id")
    if verbose:
        print("  venue table: %d teams, offsets %s"
              % (len(c), sorted(c["utc_offset"].unique().tolist())))
    return c


# ---------------------------------------------------------------------------- paired null
def paired_game_signflip(diff, n_draws, seed, alternative="two_sided"):
    """EXACT randomisation test for a WITHIN-GAME PAIRED contrast.

    `diff` is one number per GAME: (home value) - (away value).  Under the null that the venue label
    carries no information, relabelling which of the two teams in a game is "home" negates that
    game's whole contribution and leaves the joint distribution unchanged.  So the null is generated
    by flipping the SIGN OF EACH GAME independently -- not each team-game row.

    This is the correct-level null for `is_home`, and it is not optional: `is_home` is perfectly
    balanced inside a game, so it has no coarser constant level and any row-level permutation is
    anticonservative for the usual reason.  It also does not even respect the design -- a row-level
    shuffle of `is_home` produces games with two home teams or none.
    """
    d = np.asarray(diff, float)
    d = d[np.isfinite(d)]
    n = len(d)
    real = float(d.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, n))
    draws = (signs * d[None, :]).mean(axis=1)
    if alternative == "two_sided":
        hit = int((np.abs(draws) >= abs(real) - 1e-15).sum())
    elif alternative == "greater":
        hit = int((draws >= real - 1e-15).sum())
    else:
        hit = int((draws <= real + 1e-15).sum())
    return {"real": real, "n_games": int(n), "n_draws": int(n_draws),
            "null_mean": float(draws.mean()), "null_sd": float(draws.std(ddof=1)),
            "p": float((1.0 + hit) / (n_draws + 1.0)),
            "ci95_lo": float(real - 1.96 * draws.std(ddof=1)),
            "ci95_hi": float(real + 1.96 * draws.std(ddof=1)),
            "alternative": alternative, "draws": draws}


def rowlevel_ishome_null(values_home, values_away, n_draws, seed, alternative="two_sided"):
    """THE NAIVE CONTRAST, COMPUTED ONLY TO PUBLISH THE INFLATION FACTOR.

    Pools all 2n team-game values and reassigns the `is_home` label to a random half of the ROWS,
    ignoring the one-home-per-game constraint entirely.  This is what a screen that treats
    team-games as exchangeable rows would do.  Its p NEVER carries a verdict here.
    """
    a = np.asarray(values_home, float)
    b = np.asarray(values_away, float)
    pool = np.concatenate([a, b])
    pool = pool[np.isfinite(pool)]
    n = len(pool)
    k = n // 2
    real = float(a[np.isfinite(a)].mean() - b[np.isfinite(b)].mean())
    rng = np.random.default_rng(seed)
    draws = np.empty(n_draws)
    for i in range(n_draws):
        idx = rng.permutation(n)
        draws[i] = pool[idx[:k]].mean() - pool[idx[k:2 * k]].mean()
    if alternative == "two_sided":
        hit = int((np.abs(draws) >= abs(real) - 1e-15).sum())
    else:
        hit = int((draws >= real - 1e-15).sum())
    return {"real": real, "n_rows": int(n), "n_draws": int(n_draws),
            "null_sd": float(draws.std(ddof=1)),
            "p_row_level_NAIVE": float((1.0 + hit) / (n_draws + 1.0)), "draws": draws}


# ---------------------------------------------------------------------------- misc
def cyclic_shift_within_groups(x, starts, ns, rng):
    """Rotate each group's series by a random offset.  Rows MUST be sorted by group then DATE.

    CREDIT: E1_I0021_heterogeneity_diagnostic/hd_base.py (D093), via
    E1_I0022_optimal_simple_estimator/ose_base.py.  D093 measured that a within-group SHUFFLE is
    anticonservative for a serially structured regressor -- it returned p=0.0015 where the honest
    null returned p=0.39.  A cyclic shift preserves each group's marginal distribution AND its
    serial structure and destroys only the alignment to the response.
    """
    out = np.empty_like(x)
    for a, n in zip(starts, ns):
        if n <= 1:
            out[a:a + n] = x[a:a + n]
            continue
        k = int(rng.integers(0, n))
        out[a:a + n] = np.roll(x[a:a + n], k)
    return out


def group_bounds(f, keys):
    codes = f.groupby(list(keys), sort=False).ngroup().to_numpy()
    change = np.flatnonzero(np.r_[True, codes[1:] != codes[:-1]])
    ns = np.diff(np.r_[change, len(codes)])
    return codes, change, ns


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items() if k != "draws"}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return [jsonable(v) for v in o.tolist()]
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    return o
