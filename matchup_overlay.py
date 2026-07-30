#!/usr/bin/env python3
"""
matchup_overlay — zone-map aggregation + matchup differential functions (W2 data layer).

Importable core for the location-and-context expected-points tables built by
`build_zone_maps.py` (ROADMAP Phase 2c). This module owns:

  * the 6-zone modeling scheme (SHOT_ZONE_BASIC base taxonomy, corners merged),
  * team offense / team defense / league zone aggregation (with empirical-Bayes
    shrinkage of conversion AND attempt-share toward league rates),
  * `maps_before(cutoff_date)` — walk-forward-safe maps built from games strictly
    before a cutoff (same-day games excluded),
  * `matchup_differential(...)` — zone-level capability differentials for a
    team-A-offense vs team-B-defense pairing: the channel-chain inputs.

The five W2 components map onto these tables as follows (ROADMAP 2c):
  1. shot-location tendency                -> offense `share_shrunk` (+ player attempt_share)
  2. location-based conversion expectation -> league `fg_pct` per zone
  3. shooter over/under-performance        -> player `fg_pct_shrunk` - league (build_zone_maps)
  4. opponent allowed-location distribution-> defense `share_shrunk` (allowed)
  5. opponent conversion-allowed (shrunken)-> defense `fg_pct_shrunk` (allowed)

No model claims are made here; this is data infrastructure. The channel-integration
experiment consumes these tables later under the harness.

Shrinkage constants (K per zone x level) are estimated once from the full 2021-2026
sample by build_zone_maps.py (beta-binomial method-of-moments, see that file) and
stored in data/zone_maps/shrinkage_priors.csv. They are variance-ratio
hyperparameters, not outcome data; a strict walk-forward experiment may re-estimate
them on train years only and pass its own table via `k_table=`. All *rates* used
inside `maps_before` (league conversion, league shares) are computed from the
pre-cutoff slice itself — no future rates leak into shrinkage targets.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
ZONE_MAPS_DIR = ROOT / "data" / "zone_maps"
ENRICHED_PATH = ZONE_MAPS_DIR / "shots_enriched.parquet"
K_TABLE_PATH = ZONE_MAPS_DIR / "shrinkage_priors.csv"

# 6-zone modeling scheme: SHOT_ZONE_BASIC with the two corners merged.
# Justification (2021-2026, see RECONCILIATION.md): median player-season corner
# attempts are 4 (L) / 3 (R) with 76% / 87% of cells under 10 attempts, and the
# league L-vs-R conversion difference is insignificant (36.6% vs 37.4%, z=-0.79,
# sign flips across seasons). Backcourt stays separate: 431 attempts / 5 makes
# all-time — merging it into Above the Break 3 would bias that zone downward.
CORNER_MERGE = {"Left Corner 3": "Corner 3", "Right Corner 3": "Corner 3"}
ZONES = [
    "Restricted Area",
    "In The Paint (Non-RA)",
    "Mid-Range",
    "Corner 3",
    "Above the Break 3",
    "Backcourt",
]
ZONE_PTS = {
    "Restricted Area": 2,
    "In The Paint (Non-RA)": 2,
    "Mid-Range": 2,
    "Corner 3": 3,
    "Above the Break 3": 3,
    "Backcourt": 3,
}
# Paint flag consistent with the misc `pointsPaint` definition (validated exactly:
# 2978/2978 team-games reconcile, see RECONCILIATION.md).
PAINT_ZONES = {"Restricted Area", "In The Paint (Non-RA)"}

DEFAULT_K = 100.0  # fallback prior strength if no K table is available


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #

def load_enriched(path: str | Path | None = None) -> pd.DataFrame:
    """Load shots_enriched.parquet (built by build_zone_maps.py)."""
    df = pd.read_parquet(path or ENRICHED_PATH)
    df["game_date"] = pd.to_datetime(df["game_date"])
    return df


def load_k_table(path: str | Path | None = None) -> pd.DataFrame | None:
    """Load the stored shrinkage-prior table (zone x level -> K), if present."""
    p = Path(path or K_TABLE_PATH)
    if not p.exists():
        return None
    return pd.read_csv(p)


def _k_lookup(k_table: pd.DataFrame | None, level: str, metric: str) -> dict[str, float]:
    """{zone: K} for a given level ('team_off'|'team_def'|'player') and metric
    ('conversion'|'share'). Missing entries fall back to DEFAULT_K."""
    out = {z: DEFAULT_K for z in ZONES}
    if k_table is not None:
        sel = k_table[(k_table["level"] == level) & (k_table["metric"] == metric)]
        for _, r in sel.iterrows():
            out[r["zone"]] = float(r["k"])
    return out


# --------------------------------------------------------------------------- #
# aggregation core
# --------------------------------------------------------------------------- #

def league_zone(shots: pd.DataFrame, by: list[str] | tuple[str, ...] = ("season", "season_type")) -> pd.DataFrame:
    """League per-zone totals: fga, fgm, fg_pct, attempt share, pts, pps."""
    by = list(by)
    g = (
        shots.groupby(by + ["zone"], observed=True)
        .agg(fga=("pts_value", "size"), fgm=("shot_made", "sum"), pts=("pts_scored", "sum"))
        .reset_index()
    )
    tot = g.groupby(by, observed=True)["fga"].transform("sum") if by else g["fga"].sum()
    g["attempt_share"] = g["fga"] / tot
    g["fg_pct"] = g["fgm"] / g["fga"]
    g["pps"] = g["pts"] / g["fga"]
    g["pts_value"] = g["zone"].map(ZONE_PTS)
    return g


def _team_zone(
    shots: pd.DataFrame,
    team_col: str,
    abbr_col: str,
    by: list[str],
    league: pd.DataFrame,
    k_conv: dict[str, float],
    k_share: dict[str, float],
) -> pd.DataFrame:
    """Shared offense/defense aggregation. `team_col` is the attacking team for
    offense and the defending team for defense (shots allowed)."""
    keys = by + [team_col, "zone"]
    g = (
        shots.groupby(keys, observed=True)
        .agg(
            fga=("pts_value", "size"),
            fgm=("shot_made", "sum"),
            pts=("pts_scored", "sum"),
            games=("GAME_ID", "nunique"),
        )
        .reset_index()
    )
    # complete the (slice x team) x zone grid so 0-attempt zones are explicit
    units = shots.groupby(by + [team_col], observed=True)["GAME_ID"].nunique().rename("games_all").reset_index()
    grid = units.merge(pd.DataFrame({"zone": ZONES}), how="cross")
    g = grid.merge(g, on=by + [team_col, "zone"], how="left")
    g[["fga", "fgm", "pts"]] = g[["fga", "fgm", "pts"]].fillna(0).astype("int64")
    g["games"] = g["games_all"]
    g = g.drop(columns="games_all")

    # team abbreviation (modal within slice)
    abbr = (
        shots.groupby(by + [team_col], observed=True)[abbr_col]
        .agg(lambda s: s.mode().iat[0])
        .rename("team_abbr")
        .reset_index()
    )
    g = g.merge(abbr, on=by + [team_col], how="left")

    tot = g.groupby(by + [team_col], observed=True)["fga"].transform("sum")
    g["attempt_share"] = np.where(tot > 0, g["fga"] / tot, np.nan)
    g["fg_pct"] = np.where(g["fga"] > 0, g["fgm"] / np.where(g["fga"] > 0, g["fga"], 1), np.nan)
    g["pps"] = np.where(g["fga"] > 0, g["pts"] / np.where(g["fga"] > 0, g["fga"], 1), np.nan)

    # league targets for shrinkage (from the same slice — no external rates)
    lg = league.rename(columns={"fg_pct": "league_fg_pct", "attempt_share": "league_share"})
    g = g.merge(lg[by + ["zone", "league_fg_pct", "league_share"]], on=by + ["zone"], how="left")

    kc = g["zone"].map(k_conv).astype(float)
    ks = g["zone"].map(k_share).astype(float)
    g["k_conversion"] = kc
    g["k_share"] = ks
    # beta-binomial posterior means
    g["fg_pct_shrunk"] = (g["fgm"] + kc * g["league_fg_pct"]) / (g["fga"] + kc)
    g["share_shrunk"] = (g["fga"] + ks * g["league_share"]) / (tot + ks)
    # renormalize shrunk shares to sum to 1 within team-slice
    ssum = g.groupby(by + [team_col], observed=True)["share_shrunk"].transform("sum")
    g["share_shrunk"] = g["share_shrunk"] / ssum
    g["pts_value"] = g["zone"].map(ZONE_PTS)
    g["pps_shrunk"] = g["fg_pct_shrunk"] * g["pts_value"]
    g["zone"] = pd.Categorical(g["zone"], categories=ZONES, ordered=True)
    return g.sort_values(by + [team_col, "zone"]).reset_index(drop=True)


def team_zone_offense(
    shots: pd.DataFrame,
    by: list[str] | tuple[str, ...] = ("season", "season_type"),
    k_table: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Per (slice x team x zone): attempts, conversion, points per shot, shares —
    the team's own shot generation."""
    by = list(by)
    lg = league_zone(shots, by)
    return _team_zone(
        shots, "team_id", "team_abbr", by, lg,
        _k_lookup(k_table, "team_off", "conversion"), _k_lookup(k_table, "team_off", "share"),
    )


def team_zone_defense(
    shots: pd.DataFrame,
    by: list[str] | tuple[str, ...] = ("season", "season_type"),
    k_table: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Per (slice x team x zone): opponent shots ALLOWED vs that team."""
    by = list(by)
    lg = league_zone(shots, by)
    out = _team_zone(
        shots, "opp_team_id", "opp_team_abbr", by, lg,
        _k_lookup(k_table, "team_def", "conversion"), _k_lookup(k_table, "team_def", "share"),
    )
    return out.rename(columns={"opp_team_id": "team_id"})


# --------------------------------------------------------------------------- #
# walk-forward-safe maps
# --------------------------------------------------------------------------- #

def maps_before(
    cutoff_date: str | pd.Timestamp,
    shots: pd.DataFrame | None = None,
    season: int | None = None,
    season_types: list[str] | None = None,
    k_table: pd.DataFrame | None = None,
) -> dict:
    """Zone maps computed from games STRICTLY before `cutoff_date` (games played
    on the cutoff date itself are excluded — walk-forward safe).

    Parameters
    ----------
    cutoff_date : the decision date; only games with game_date < cutoff enter.
    shots       : optional pre-loaded enriched shots (else loads from disk).
    season      : optional single-season restriction (season-to-date maps).
    season_types: optional restriction, e.g. ["Regular Season"].
    k_table     : optional shrinkage-prior table override (walk-forward experiments
                  may pass K estimated on train years only). Defaults to the
                  stored full-sample table.

    Returns dict with keys: offense, defense, league, cutoff, season, n_shots,
    n_games, last_game_date.
    """
    cutoff = pd.Timestamp(cutoff_date)
    df = load_enriched() if shots is None else shots
    if not pd.api.types.is_datetime64_any_dtype(df["game_date"]):
        df = df.assign(game_date=pd.to_datetime(df["game_date"]))
    mask = df["game_date"] < cutoff
    if season is not None:
        mask &= df["season"] == season
    if season_types is not None:
        mask &= df["season_type"].isin(season_types)
    sl = df[mask]
    if k_table is None:
        k_table = load_k_table()
    by: list[str] = ["season"] if season is None else []
    return {
        "offense": team_zone_offense(sl, by, k_table) if len(sl) else None,
        "defense": team_zone_defense(sl, by, k_table) if len(sl) else None,
        "league": league_zone(sl, by) if len(sl) else None,
        "cutoff": cutoff,
        "season": season,
        "n_shots": int(len(sl)),
        "n_games": int(sl["GAME_ID"].nunique()) if len(sl) else 0,
        "last_game_date": sl["game_date"].max() if len(sl) else pd.NaT,
    }


# --------------------------------------------------------------------------- #
# matchup differentials (channel-chain inputs)
# --------------------------------------------------------------------------- #

def _team_slice(df: pd.DataFrame, team: int | str) -> pd.DataFrame:
    if isinstance(team, str):
        sel = df[df["team_abbr"] == team]
    else:
        sel = df[df["team_id"] == team]
    if sel.empty:
        # Explicit by design (no-imputation rule): a team with no games before the
        # cutoff has no map. The caller decides the fallback (league prior / no
        # prediction) — never silently filled here.
        raise KeyError(
            f"team {team!r} has no shots in this map slice (e.g. no games before "
            "the cutoff, or a season-scoped abbreviation such as PHO->PHX or "
            "Portland=PDX). Handle fallback explicitly - no silent imputation.")
    return sel


def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """num/den with den==0 -> 1.0 (neutral chain factor). Only occurs for zones
    with zero league activity in a slice (e.g. Backcourt before the first heave),
    where the shrunk team rates are also 0 and the neutral factor keeps the
    chain product at exactly 0 instead of NaN."""
    return pd.Series(np.where(den > 0, num / np.where(den > 0, den, 1.0), 1.0), index=num.index)


def matchup_differential(
    offense: pd.DataFrame,
    defense: pd.DataFrame,
    league: pd.DataFrame,
    team_a: int | str,
    team_b: int | str,
) -> pd.DataFrame:
    """Zone-level capability differentials: team A offense vs team B defense.

    Structural-chain form (HANDOFF §4): expected quantity =
    own tendency x (opponent allowed / league average), on SHRUNK rates.

      exp_share_z = off_share_a x (def_share_b / league_share_z), renormalized
      exp_conv_z  = off_conv_a  x (def_conv_b  / league_conv_z), clipped [0.01, 0.99]
      xp_contrib  = exp_share x exp_conv x zone value  (points per team shot)

    Differential columns (vs league baseline) are the channel-chain inputs:
      share_edge_off / share_edge_def / conv_edge_off / conv_edge_def / xp_edge.
    """
    a = _team_slice(offense, team_a).set_index("zone")
    b = _team_slice(defense, team_b).set_index("zone")
    lg = league.set_index("zone")
    out = pd.DataFrame(index=pd.Index(ZONES, name="zone"))
    out["pts_value"] = [ZONE_PTS[z] for z in out.index]
    out["off_share"] = a["share_shrunk"]
    out["def_share"] = b["share_shrunk"]
    out["league_share"] = lg["attempt_share"]
    out["off_conv"] = a["fg_pct_shrunk"]
    out["def_conv"] = b["fg_pct_shrunk"]
    out["league_conv"] = lg["fg_pct"]
    out["off_fga"] = a["fga"]
    out["def_fga"] = b["fga"]

    exp_share = out["off_share"] * _safe_ratio(out["def_share"], out["league_share"])
    out["exp_share"] = exp_share / exp_share.sum()
    exp_conv = out["off_conv"] * _safe_ratio(out["def_conv"], out["league_conv"])
    # clip only where the zone is live; a genuinely 0-conversion zone stays 0
    out["exp_conv"] = np.where(exp_conv > 0, exp_conv.clip(0.01, 0.99), 0.0)
    out["exp_pps"] = out["exp_conv"] * out["pts_value"]
    out["xp_contrib"] = out["exp_share"] * out["exp_pps"]

    out["share_edge_off"] = out["off_share"] - out["league_share"]
    out["share_edge_def"] = out["def_share"] - out["league_share"]
    out["conv_edge_off"] = out["off_conv"] - out["league_conv"]
    out["conv_edge_def"] = out["def_conv"] - out["league_conv"]
    out["xp_edge"] = out["xp_contrib"] - out["league_share"] * out["league_conv"] * out["pts_value"]
    return out.reset_index()


def expected_points_per_shot(diff: pd.DataFrame) -> float:
    """Overall expected points per field-goal attempt implied by a differential table."""
    return float(diff["xp_contrib"].sum())


def matchup_before(
    team_a: int | str,
    team_b: int | str,
    cutoff_date: str | pd.Timestamp,
    season: int | None = None,
    shots: pd.DataFrame | None = None,
    season_types: list[str] | None = None,
    k_table: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Convenience: season-to-date (strictly pre-cutoff) A-offense vs B-defense
    differential — the walk-forward-safe variant the future experiment consumes.
    """
    maps = maps_before(cutoff_date, shots=shots, season=season, season_types=season_types, k_table=k_table)
    if maps["offense"] is None:
        raise ValueError(f"no shots before {cutoff_date} in the requested slice")
    return matchup_differential(maps["offense"], maps["defense"], maps["league"], team_a, team_b)
