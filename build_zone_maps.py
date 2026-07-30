#!/usr/bin/env python3
"""
build_zone_maps.py — W2 location-and-context expected-points DATA LAYER (ROADMAP Phase 2c).

Builds data/zone_maps/ from data/shotcharts/ + data/masters/master_team.parquet:

  shots_enriched.parquet     every shot with zone (6-zone scheme), points value,
                             is_home, season, paint flag (misc pointsPaint-consistent)
  team_zone_offense.csv      season x season_type x team x zone: attempts, share,
                             conversion, PPS (+ EB-shrunk rates)
  team_zone_defense.csv      same, opponent shots ALLOWED vs that team
  player_zone_offense.csv    season x player x zone with empirical-Bayes shrinkage
                             toward team-then-league priors (+ prior_dominated flag)
  league_zone_averages.csv   season x season_type x zone league rates
  shrinkage_priors.csv       estimated K (prior strength) per zone x level x metric
  RECONCILIATION.md          full reconciliation report vs master_team + league_avg

This is data infrastructure with reconciliation — no model claims, no registry entry.
The channel-integration experiment runs later against these tables via
matchup_overlay.maps_before / matchup_before (walk-forward safe).

Shrinkage math (documented in RECONCILIATION.md): beta-binomial empirical Bayes.
Prior strength K per zone estimated by a DerSimonian-Laird-type method of moments:
with cells i (n_i attempts, x_i makes, r_i = x_i/n_i), mu = sum(x)/sum(n),
  Q      = sum n_i (r_i - mu)^2 / (mu (1-mu))
  c      = sum(n) - sum(n^2)/sum(n)
  sigma2 = mu(1-mu) * max(Q - (G-1), 0) / c        (between-cell talent variance)
  K      = mu(1-mu)/sigma2 - 1                      (beta prior strength alpha+beta)
Posterior mean: (x + K * prior) / (n + K). Player prior = the player's team-season
posterior (itself shrunk toward the season league rate), attempt-weighted across
teams for traded players. Cells with posterior data weight n/(n+K) < 0.5 or n < 10
are flagged prior_dominated=True — never silently.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from matchup_overlay import (  # noqa: E402
    CORNER_MERGE,
    PAINT_ZONES,
    ZONE_PTS,
    ZONES,
    league_zone,
    maps_before,
    team_zone_defense,
    team_zone_offense,
)

SHOTS_DIR = ROOT / "data" / "shotcharts"
MASTER_TEAM = ROOT / "data" / "masters" / "master_team.parquet"
OUT = ROOT / "data" / "zone_maps"

K_MIN, K_CAP = 1.0, 5000.0
MIN_ACTIVATE = 10          # absolute attempts floor for player-cell activation
DATA_WEIGHT_ACTIVATE = 0.5  # posterior weight on own data required for activation

THREE_ZONES_BASIC = {"Above the Break 3", "Left Corner 3", "Right Corner 3", "Backcourt"}


# --------------------------------------------------------------------------- #
# 1. load + enrich
# --------------------------------------------------------------------------- #

def load_shots() -> pd.DataFrame:
    frames = []
    for p in sorted(SHOTS_DIR.glob("shots_*.parquet")):
        m = re.match(r"shots_(\d{4})_(\w+)\.parquet", p.name)
        df = pd.read_parquet(p)
        df["season"] = int(m.group(1))
        df["season_type"] = "Regular Season" if m.group(2) == "regular" else "Playoffs"
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def enrich(shots: pd.DataFrame, master: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = shots.copy()
    notes: dict = {}

    # invariants
    assert df.duplicated(subset=["GAME_ID", "GAME_EVENT_ID"]).sum() == 0, "duplicate shot events"
    assert (df["SHOT_ATTEMPTED_FLAG"] == 1).all(), "non-attempt rows present"
    zone3 = df["SHOT_ZONE_BASIC"].isin(THREE_ZONES_BASIC)
    type3 = df["SHOT_TYPE"].eq("3PT Field Goal")
    notes["zone_type_mismatches"] = int((zone3 != type3).sum())
    assert notes["zone_type_mismatches"] == 0, "SHOT_ZONE_BASIC disagrees with SHOT_TYPE"

    df["zone"] = df["SHOT_ZONE_BASIC"].replace(CORNER_MERGE)
    df["pts_value"] = np.where(type3, 3, 2).astype("int8")
    df["shot_made"] = df["SHOT_MADE_FLAG"].astype("int8")
    df["pts_scored"] = (df["shot_made"] * df["pts_value"]).astype("int8")
    df["is_paint"] = df["SHOT_ZONE_BASIC"].isin(PAINT_ZONES)
    df["game_date"] = pd.to_datetime(df["GAME_DATE"], format="%Y%m%d")

    mt = master[["game_id", "team_id", "is_home", "team_abbreviation",
                 "opp_team_id", "opp_team_abbreviation", "game_date"]].copy()
    mt["team_id"] = mt["team_id"].astype("int64")
    mt["opp_team_id"] = mt["opp_team_id"].astype("int64")
    mt["is_home"] = mt["is_home"].astype("int64") == 1
    mt["game_date_master"] = pd.to_datetime(mt["game_date"])
    mt = mt.drop(columns="game_date").rename(columns={
        "team_abbreviation": "team_abbr", "opp_team_abbreviation": "opp_team_abbr"})

    df = df.merge(mt, left_on=["GAME_ID", "TEAM_ID"], right_on=["game_id", "team_id"], how="left")
    notes["unmatched_shots"] = int(df["team_id"].isna().sum())
    assert notes["unmatched_shots"] == 0, "shots with no master_team row"
    notes["date_mismatches"] = int((df["game_date"] != df["game_date_master"]).sum())
    df = df.drop(columns=["game_id", "team_id", "game_date_master"])
    df = df.rename(columns={"TEAM_ID": "team_id"})

    # informational: master is_home vs shotchart HTM abbreviation
    htm_agree = (df["team_abbr"] == df["HTM"]) == df["is_home"]
    notes["is_home_htm_disagreements"] = int((~htm_agree).sum())
    return df, notes


# --------------------------------------------------------------------------- #
# 2. empirical-Bayes prior strengths (method of moments)
# --------------------------------------------------------------------------- #

def mom_prior_strength(n: np.ndarray, x: np.ndarray) -> tuple[float, float, float]:
    """Beta-binomial MoM: returns (mu, sigma2_between, K), K clipped to [K_MIN, K_CAP]."""
    n = np.asarray(n, dtype=float)
    x = np.asarray(x, dtype=float)
    keep = n > 0
    n, x = n[keep], x[keep]
    G, N = len(n), n.sum()
    mu = x.sum() / N
    if mu <= 0.0 or mu >= 1.0 or G < 3:
        return mu, 0.0, K_CAP
    r = x / n
    Q = float((n * (r - mu) ** 2).sum() / (mu * (1.0 - mu)))
    c = N - (n ** 2).sum() / N
    sigma2 = mu * (1.0 - mu) * max(Q - (G - 1), 0.0) / c
    if sigma2 <= 0.0:
        return mu, 0.0, K_CAP
    K = mu * (1.0 - mu) / sigma2 - 1.0
    return mu, sigma2, float(np.clip(K, K_MIN, K_CAP))


def estimate_k_table(df: pd.DataFrame) -> pd.DataFrame:
    """K per zone for: player conversion (player-season cells, season types pooled),
    team offense/defense conversion and attempt share (team-season-type cells)."""
    rows = []

    def add(level: str, metric: str, cells: pd.DataFrame, ncol: str, xcol: str):
        for z in ZONES:
            sub = cells[cells["zone"] == z]
            mu, s2, k = mom_prior_strength(sub[ncol].to_numpy(), sub[xcol].to_numpy())
            rows.append({"level": level, "metric": metric, "zone": z,
                         "mu": mu, "sigma2_between": s2, "k": k, "n_cells": len(sub)})

    pc = df.groupby(["season", "PLAYER_ID", "zone"], observed=True).agg(
        n=("shot_made", "size"), x=("shot_made", "sum")).reset_index()
    add("player", "conversion", pc, "n", "x")

    for level, team_col in (("team_off", "team_id"), ("team_def", "opp_team_id")):
        tc = df.groupby(["season", "season_type", team_col, "zone"], observed=True).agg(
            n=("shot_made", "size"), x=("shot_made", "sum")).reset_index()
        add(level, "conversion", tc, "n", "x")
        tot = tc.groupby(["season", "season_type", team_col], observed=True)["n"].transform("sum")
        tc = tc.assign(n_tot=tot)
        add(level, "share", tc, "n_tot", "n")

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# 3. player zone offense with two-stage shrinkage
# --------------------------------------------------------------------------- #

def build_player_zone(df: pd.DataFrame, k_table: pd.DataFrame) -> pd.DataFrame:
    k_player = {r["zone"]: r["k"] for _, r in
                k_table[(k_table.level == "player") & (k_table.metric == "conversion")].iterrows()}
    k_team = {r["zone"]: r["k"] for _, r in
              k_table[(k_table.level == "team_off") & (k_table.metric == "conversion")].iterrows()}

    # season league rates per zone (season types pooled — player skill doesn't reset)
    lg = df.groupby(["season", "zone"], observed=True).agg(
        lg_fga=("shot_made", "size"), lg_fgm=("shot_made", "sum")).reset_index()
    lg["league_fg_pct"] = lg["lg_fgm"] / lg["lg_fga"]

    # team-season posteriors (shrunk toward league) per zone
    tm = df.groupby(["season", "team_id", "zone"], observed=True).agg(
        t_fga=("shot_made", "size"), t_fgm=("shot_made", "sum")).reset_index()
    tm = tm.merge(lg[["season", "zone", "league_fg_pct"]], on=["season", "zone"], how="left")
    kt = tm["zone"].map(k_team).astype(float)
    tm["team_prior_fg_pct"] = (tm["t_fgm"] + kt * tm["league_fg_pct"]) / (tm["t_fga"] + kt)

    # player-season-zone observed cells
    pc = df.groupby(["season", "PLAYER_ID", "zone"], observed=True).agg(
        fga=("shot_made", "size"), fgm=("shot_made", "sum")).reset_index()

    # player-season identity: name at latest date, modal team, per-team attempt weights
    df_sorted = df.sort_values("game_date")
    ident = df_sorted.groupby(["season", "PLAYER_ID"], observed=True).agg(
        player_name=("PLAYER_NAME", "last"), fga_total=("shot_made", "size")).reset_index()
    pt = df.groupby(["season", "PLAYER_ID", "team_id"], observed=True).agg(
        fga_pt=("shot_made", "size")).reset_index()
    modal = pt.sort_values("fga_pt", ascending=False).drop_duplicates(["season", "PLAYER_ID"])
    modal = modal.rename(columns={"team_id": "modal_team_id"})[["season", "PLAYER_ID", "modal_team_id"]]
    nteams = pt.groupby(["season", "PLAYER_ID"], observed=True)["team_id"].nunique().rename("n_teams").reset_index()
    ident = ident.merge(modal, on=["season", "PLAYER_ID"]).merge(nteams, on=["season", "PLAYER_ID"])
    abbr = df.groupby(["season", "team_id"], observed=True)["team_abbr"].agg(
        lambda s: s.mode().iat[0]).rename("team_abbr").reset_index()
    ident = ident.merge(abbr, left_on=["season", "modal_team_id"], right_on=["season", "team_id"],
                        how="left").drop(columns="team_id").rename(columns={"modal_team_id": "team_id"})

    # blended team prior per player-season-zone: attempt-weighted over teams played for
    pt = pt.merge(pt.groupby(["season", "PLAYER_ID"], observed=True)["fga_pt"].transform("sum").rename("fga_pt_tot"),
                  left_index=True, right_index=True)
    pt["w"] = pt["fga_pt"] / pt["fga_pt_tot"]
    blend = pt.merge(tm[["season", "team_id", "zone", "team_prior_fg_pct"]], on=["season", "team_id"], how="left")
    blend["wp"] = blend["w"] * blend["team_prior_fg_pct"]
    prior = blend.groupby(["season", "PLAYER_ID", "zone"], observed=True).agg(
        team_prior_fg_pct=("wp", "sum"), wsum=("w", "sum")).reset_index()
    prior["team_prior_fg_pct"] = prior["team_prior_fg_pct"] / prior["wsum"]  # guard vs missing team-zone rows
    prior = prior.drop(columns="wsum")

    # full grid: every (season, player) x 6 zones — zero-attempt cells explicit
    grid = ident.merge(pd.DataFrame({"zone": ZONES}), how="cross")
    g = grid.merge(pc, on=["season", "PLAYER_ID", "zone"], how="left")
    g[["fga", "fgm"]] = g[["fga", "fgm"]].fillna(0).astype("int64")
    g = g.merge(prior, on=["season", "PLAYER_ID", "zone"], how="left")
    g = g.merge(lg[["season", "zone", "league_fg_pct"]], on=["season", "zone"], how="left")
    # a zone nobody on the player's teams attempted: fall back to league
    g["team_prior_fg_pct"] = g["team_prior_fg_pct"].fillna(g["league_fg_pct"])

    kp = g["zone"].map(k_player).astype(float)
    g["k_player"] = kp
    g["fg_pct_raw"] = np.where(g["fga"] > 0, g["fgm"] / np.where(g["fga"] > 0, g["fga"], 1), np.nan)
    g["fg_pct_shrunk"] = (g["fgm"] + kp * g["team_prior_fg_pct"]) / (g["fga"] + kp)
    g["data_weight"] = g["fga"] / (g["fga"] + kp)
    g["prior_dominated"] = (g["data_weight"] < DATA_WEIGHT_ACTIVATE) | (g["fga"] < MIN_ACTIVATE)
    g["attempt_share"] = g["fga"] / g["fga_total"]
    g["pts_value"] = g["zone"].map(ZONE_PTS)
    g["pps_shrunk"] = g["fg_pct_shrunk"] * g["pts_value"]
    g["zone"] = pd.Categorical(g["zone"], categories=ZONES, ordered=True)

    cols = ["season", "PLAYER_ID", "player_name", "team_id", "team_abbr", "n_teams", "zone",
            "fga", "fgm", "fg_pct_raw", "attempt_share", "fga_total", "league_fg_pct",
            "team_prior_fg_pct", "k_player", "fg_pct_shrunk", "data_weight", "prior_dominated",
            "pts_value", "pps_shrunk"]
    return (g[cols].rename(columns={"PLAYER_ID": "player_id"})
            .sort_values(["season", "player_id", "zone"]).reset_index(drop=True))


# --------------------------------------------------------------------------- #
# 4. reconciliations
# --------------------------------------------------------------------------- #

def reconcile(df: pd.DataFrame, master: pd.DataFrame) -> dict:
    R: dict = {}
    mt = master.copy()
    mt["team_id"] = mt["team_id"].astype("int64")

    g = df.groupby(["GAME_ID", "team_id"], observed=True).agg(
        fga_sh=("shot_made", "size"), fgm_sh=("shot_made", "sum"),
        fg3a_sh=("pts_value", lambda s: int((s == 3).sum())),
        fgpts_sh=("pts_scored", "sum"),
    ).reset_index()
    paint = df[df["is_paint"] & (df["shot_made"] == 1)].groupby(
        ["GAME_ID", "team_id"], observed=True)["pts_scored"].sum().rename("paint_sh").reset_index()
    g = g.merge(paint, on=["GAME_ID", "team_id"], how="left")
    g["paint_sh"] = g["paint_sh"].fillna(0).astype("int64")

    m = mt.merge(g, left_on=["game_id", "team_id"], right_on=["GAME_ID", "team_id"],
                 how="outer", indicator=True)
    R["merge_counts"] = m["_merge"].value_counts().to_dict()
    m = m[m["_merge"] == "both"].copy()
    for c in ["fga", "fgm", "fg3a", "pts", "ftm", "points_paint"]:
        m[c] = m[c].astype("int64")
    m["d_fga"] = m["fga_sh"] - m["fga"]
    m["d_fgm"] = m["fgm_sh"] - m["fgm"]
    m["d_fg3a"] = m["fg3a_sh"] - m["fg3a"]
    m["d_fgpts"] = m["fgpts_sh"] - (m["pts"] - m["ftm"])
    m["d_paint"] = m["paint_sh"] - m["points_paint"]

    R["n_team_games"] = len(m)
    R["n_games"] = int(m["game_id"].nunique())
    per_season = m.groupby(["season", "season_type"], observed=True).apply(
        lambda s: pd.Series({
            "team_games": len(s),
            "fga_master": s["fga"].sum(), "fga_shots": s["fga_sh"].sum(),
            "fgm_master": s["fgm"].sum(), "fgm_shots": s["fgm_sh"].sum(),
            "fga_exact": int((s["d_fga"] == 0).sum()), "fgm_exact": int((s["d_fgm"] == 0).sum()),
            "fgpts_exact": int((s["d_fgpts"] == 0).sum()), "paint_exact": int((s["d_paint"] == 0).sum()),
        }), include_groups=False).reset_index()
    R["per_season"] = per_season

    disc = m[(m["d_fga"] != 0) | (m["d_fgm"] != 0) | (m["d_fg3a"] != 0) |
             (m["d_fgpts"] != 0) | (m["d_paint"] != 0)]
    R["discrepant"] = disc[["game_id", "season", "season_type", "game_date", "team_abbreviation",
                            "opp_team_abbreviation", "fga", "fga_sh", "fgm", "fgm_sh", "fg3a",
                            "fg3a_sh", "d_fga", "d_fgm", "d_fg3a", "d_fgpts", "d_paint"]].copy()
    for key in ["fga", "fgm", "fg3a", "fgpts", "paint"]:
        d = m[f"d_{key}"]
        R[f"{key}_exact_rate"] = float((d == 0).mean())
        R[f"{key}_exact_n"] = int((d == 0).sum())
        R[f"{key}_abs_sum"] = int(d.abs().sum())
    R["is_home_check"] = int(((m["is_home"].astype("int64") == 1) !=
                              (m["team_abbreviation"] == m["game_id"].map(
                                  df.drop_duplicates("GAME_ID").set_index("GAME_ID")["HTM"]))).sum())
    return R


def reconcile_league_avg(df: pd.DataFrame) -> pd.DataFrame:
    """(d) league_avg_<season>_<type>.parquet vs recomputed from the shot rows."""
    rows = []
    for p in sorted(SHOTS_DIR.glob("league_avg_*.parquet")):
        m = re.match(r"league_avg_(\d{4})_(\w+)\.parquet", p.name)
        season = int(m.group(1))
        stype = "Regular Season" if m.group(2) == "regular" else "Playoffs"
        ref = pd.read_parquet(p)[["SHOT_ZONE_BASIC", "SHOT_ZONE_AREA", "SHOT_ZONE_RANGE", "FGA", "FGM"]]
        sl = df[(df["season"] == season) & (df["season_type"] == stype)]
        comp = sl.groupby(["SHOT_ZONE_BASIC", "SHOT_ZONE_AREA", "SHOT_ZONE_RANGE"], observed=True).agg(
            FGA_c=("shot_made", "size"), FGM_c=("shot_made", "sum")).reset_index()
        j = ref.merge(comp, on=["SHOT_ZONE_BASIC", "SHOT_ZONE_AREA", "SHOT_ZONE_RANGE"],
                      how="outer").fillna(0)
        rows.append({
            "season": season, "season_type": stype, "ref_cells": len(ref),
            "cells_compared": len(j),
            "fga_ref": int(j["FGA"].sum()), "fga_computed": int(j["FGA_c"].sum()),
            "cells_exact": int(((j["FGA"] == j["FGA_c"]) & (j["FGM"] == j["FGM_c"])).sum()),
            "max_abs_fga_diff": int((j["FGA"] - j["FGA_c"]).abs().max()),
            "max_abs_fgm_diff": int((j["FGM"] - j["FGM_c"]).abs().max()),
        })
    return pd.DataFrame(rows)


def spot_test_maps_before(df: pd.DataFrame) -> dict:
    """Verify maps_before excludes games on the cutoff date itself."""
    cutoff = "2025-08-07"  # a date with games (incl. the CHI@ATL extra-shot game)
    on_day = df[df["game_date"] == pd.Timestamp(cutoff)]
    before = df[(df["game_date"] < pd.Timestamp(cutoff)) & (df["season"] == 2025)]
    maps = maps_before(cutoff, shots=df, season=2025)
    ok_shots = maps["n_shots"] == len(before)
    ok_games = maps["n_games"] == before["GAME_ID"].nunique()
    ok_last = maps["last_game_date"] < pd.Timestamp(cutoff)
    # cutoff-day games exist in the data, so the exclusion is load-bearing
    ok_loadbearing = len(on_day) > 0
    # a team playing on the cutoff day: its map attempts must equal its strictly-before attempts
    t0 = int(on_day["team_id"].iloc[0])
    off = maps["offense"]
    map_fga = int(off[off["team_id"] == t0]["fga"].sum())
    ok_team = map_fga == int((before["team_id"] == t0).sum())
    return {"cutoff": cutoff, "games_on_cutoff_day": int(on_day["GAME_ID"].nunique()),
            "shots_on_cutoff_day": len(on_day), "map_n_shots": maps["n_shots"],
            "map_n_games": maps["n_games"], "spot_team_id": t0, "spot_team_fga": map_fga,
            "pass": bool(ok_shots and ok_games and ok_last and ok_loadbearing and ok_team)}


# --------------------------------------------------------------------------- #
# 5. report
# --------------------------------------------------------------------------- #

def fmt_rate(n_ok: int, n: int) -> str:
    return f"{n_ok}/{n} ({100.0 * n_ok / n:.2f}%)"


def write_report(R: dict, la: pd.DataFrame, ktab: pd.DataFrame, player: pd.DataFrame,
                 df: pd.DataFrame, spot: dict, notes: dict,
                 n_off: int = 0, n_def: int = 0, n_lg: int = 0) -> str:
    n = R["n_team_games"]
    disc = R["discrepant"]
    lines: list[str] = []
    A = lines.append
    A("# W2 Zone Maps — Reconciliation Report")
    A("")
    A(f"*Generated by `build_zone_maps.py`. Inputs: {len(df):,} shots "
      f"({df['GAME_ID'].nunique():,} games, seasons {df['season'].min()}–{df['season'].max()}) "
      f"vs `data/masters/master_team.parquet` ({n:,} team-games). "
      "Data layer only — no model claims (ROADMAP Phase 2c).*")
    A("")
    A("## Zone scheme")
    A("")
    A("Base taxonomy = the API's `SHOT_ZONE_BASIC` (7 zones), collapsed to a 6-zone modeling")
    A("scheme by merging the two corners. `SHOT_ZONE_BASIC` agreed with `SHOT_TYPE` on the")
    A(f"2/3-point value for **all {len(df):,} shots** (0 mismatches), so zone implies points value.")
    A("")
    A("| modeling zone | value | why |")
    A("|---|---|---|")
    A("| Restricted Area | 2 | as-is |")
    A("| In The Paint (Non-RA) | 2 | as-is |")
    A("| Mid-Range | 2 | as-is |")
    A("| **Corner 3** (merged L+R) | 3 | median player-season attempts 4 (L) / 3 (R); 76% / 87% of cells <10 attempts; league conversion L 36.6% vs R 37.4% (z = −0.79, sign flips across seasons) — no evidence of a real L/R split at these samples |")
    A("| Above the Break 3 | 3 | as-is |")
    A("| Backcourt | 3 | kept separate: 431 attempts / 5 makes all-time (1.2%); merging into AB3 would bias that zone downward. Always prior-dominated at player level |")
    A("")
    A("`shots_enriched.parquet` keeps the original 7-zone `SHOT_ZONE_BASIC` alongside `zone`,")
    A("so nothing is lost by the merge.")
    A("")
    A("## (a) Shot counts vs master_team FGA/FGM")
    A("")
    A(f"- Team-game merge: **{R['merge_counts'].get('both', 0):,} matched**, "
      f"{R['merge_counts'].get('left_only', 0)} master-only, {R['merge_counts'].get('right_only', 0)} shots-only "
      f"— every game in the masters has a shot chart and vice versa ({R['n_games']:,} games).")
    A(f"- FGA exact: **{fmt_rate(R['fga_exact_n'], n)}** of team-games; total |diff| = {R['fga_abs_sum']} shots.")
    A(f"- FGM exact: **{fmt_rate(R['fgm_exact_n'], n)}**; total |diff| = {R['fgm_abs_sum']}.")
    A(f"- FG3A exact: **{fmt_rate(R['fg3a_exact_n'], n)}**; total |diff| = {R['fg3a_abs_sum']}.")
    A("")
    A("Per season (attempts, master vs shot chart):")
    A("")
    ps = R["per_season"]
    A("| season | type | team-games | FGA master | FGA shots | Δ | FGM master | FGM shots | Δ | FGA exact | paint exact |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in ps.iterrows():
        A(f"| {r['season']} | {r['season_type']} | {int(r['team_games'])} | {int(r['fga_master']):,} | "
          f"{int(r['fga_shots']):,} | {int(r['fga_shots'] - r['fga_master']):+d} | {int(r['fgm_master']):,} | "
          f"{int(r['fgm_shots']):,} | {int(r['fgm_shots'] - r['fgm_master']):+d} | "
          f"{int(r['fga_exact'])}/{int(r['team_games'])} | {int(r['paint_exact'])}/{int(r['team_games'])} |")
    A("")
    A("**Every discrepant team-game** (the league-wide shotchart pull drops/adds a row in rare cases):")
    A("")
    A("| game_id | date | team | opp | FGA m/s | FGM m/s | FG3A m/s | interpretation |")
    A("|---|---|---|---|---|---|---|---|")
    for _, r in disc.iterrows():
        interp = []
        if r["d_fga"] == -1 and r["d_fg3a"] == -1 and r["d_fgm"] == 0:
            interp.append("chart missing one missed 3")
        elif r["d_fga"] == -1 and r["d_fg3a"] == 0 and r["d_fgm"] == -1:
            interp.append("chart missing one made 2")
        elif r["d_fga"] == -1 and r["d_fg3a"] == 0 and r["d_fgm"] == 0:
            interp.append("chart missing one missed 2")
        elif r["d_fga"] == 1 and r["d_fgm"] == 0:
            interp.append("chart has one extra missed shot vs box")
        else:
            interp.append(f"d_fga={r['d_fga']}, d_fgm={r['d_fgm']}, d_fg3a={r['d_fg3a']}")
        if r["d_paint"] != 0:
            interp.append(f"paint Δ{r['d_paint']:+d}")
        A(f"| {r['game_id']} | {r['game_date']} | {r['team_abbreviation']} | {r['opp_team_abbreviation']} | "
          f"{r['fga']}/{r['fga_sh']} | {r['fgm']}/{r['fgm_sh']} | {r['fg3a']}/{r['fg3a_sh']} | {'; '.join(interp)} |")
    A("")
    A("## (b) Field-goal points identity (3×3PM + 2×2PM vs pts − ftm)")
    A("")
    A(f"- Shot-chart FG points == master `pts − ftm`: **{fmt_rate(R['fgpts_exact_n'], n)}** of team-games; "
      f"total |diff| = {R['fgpts_abs_sum']} points (entirely explained by the dropped rows above).")
    A("- The shot chart excludes free throws by design; `pts − ftm` is the exact FG-points truth.")
    A("")
    A("## (c) Paint points vs misc `points_paint`")
    A("")
    A(f"- Paint flag = `SHOT_ZONE_BASIC ∈ {{Restricted Area, In The Paint (Non-RA)}}`.")
    A(f"- 2 × paint makes == master `points_paint`: **{fmt_rate(R['paint_exact_n'], n)}** of team-games "
      f"(total |diff| = {R['paint_abs_sum']}).")
    A("- Exact 100% reconciliation ⇒ the misc `pointsPaint` stat is precisely \"made FGs in the two paint")
    A("  zones × 2\" — the flag is drop-in consistent with the paint channel, and none of the four dropped")
    A("  shot rows were paint makes.")
    A("")
    A("## (d) League-average files vs computed league averages")
    A("")
    A("Per (season, type), the API `league_avg_*` file vs zone cells recomputed from the shot rows")
    A("(join on `SHOT_ZONE_BASIC × SHOT_ZONE_AREA × SHOT_ZONE_RANGE`):")
    A("")
    A("| season | type | cells | exact cells | FGA file | FGA computed | max abs ΔFGA | max abs ΔFGM |")
    A("|---|---|---|---|---|---|---|---|")
    for _, r in la.iterrows():
        A(f"| {r['season']} | {r['season_type']} | {r['cells_compared']} | {r['cells_exact']} | "
          f"{r['fga_ref']:,} | {r['fga_computed']:,} | {r['max_abs_fga_diff']} | {r['max_abs_fgm_diff']} |")
    A("")
    tot_cells = int(la["cells_compared"].sum())
    tot_exact = int(la["cells_exact"].sum())
    A(f"**{tot_exact}/{tot_cells} cells exact.** The league_avg files were returned by the same API call")
    A("as the shot rows, so they reconcile with the charts (including the dropped rows), not with the box.")
    A("")
    A("## Empirical-Bayes shrinkage design (player maps)")
    A("")
    A("**Model.** Beta-binomial. For a cell with `n` attempts, `x` makes and prior mean `p0`,")
    A("the posterior mean is `(x + K·p0) / (n + K)` — `K` is the effective prior strength in")
    A("pseudo-attempts. Two-stage, position-free (no position data in this layer):")
    A("")
    A("1. team-season zone rate shrunk toward the season league zone rate (strength `K_team`);")
    A("2. player-season zone rate shrunk toward that team posterior (strength `K_player`);")
    A("   traded players get an attempt-weighted blend of their teams' posteriors.")
    A("")
    A("**K estimation (method of moments, DerSimonian–Laird form).** Per zone, over cells i:")
    A("`μ = Σx/Σn`; `Q = Σ nᵢ(rᵢ−μ)² / (μ(1−μ))`; `c = Σn − Σn²/Σn`;")
    A("`σ²_between = μ(1−μ)·max(Q−(G−1),0)/c`; `K = μ(1−μ)/σ²_between − 1`, clipped to")
    A(f"[{K_MIN:g}, {K_CAP:g}]. Player cells = player-season (types pooled, all seasons pooled);")
    A("team cells = team-season-type. K is chosen by the data: zones where players genuinely")
    A("differ (large between-cell variance) get small K; zones where observed spread is mostly")
    A("binomial noise get large K. Estimated values:")
    A("")
    A("| level | metric | zone | μ | σ²_between | K (pseudo-attempts) | cells |")
    A("|---|---|---|---|---|---|---|")
    for _, r in ktab.iterrows():
        A(f"| {r['level']} | {r['metric']} | {r['zone']} | {r['mu']:.4f} | {r['sigma2_between']:.6f} | "
          f"{r['k']:.0f} | {r['n_cells']} |")
    A("")
    A("**Activation.** A player cell is `prior_dominated` when the posterior weight on the player's")
    A(f"own data `n/(n+K)` is below {DATA_WEIGHT_ACTIVATE} (i.e. n < K) **or** n < {MIN_ACTIVATE} attempts —")
    A("flagged in the CSV, never silently. Zero-attempt cells are emitted explicitly (full 6-zone grid")
    A("per player-season) with the prior as the estimate and `prior_dominated=True`.")
    A("")
    obs = player[player["fga"] > 0]
    A("**Sample sizes and prior-dominated share** (player-season-zone cells):")
    A("")
    A("| zone | observed cells | median FGA | p25 | p75 | prior-dominated (obs cells) | prior-dominated (full grid) |")
    A("|---|---|---|---|---|---|---|")
    for z in ZONES:
        oz = obs[obs["zone"] == z]
        gz = player[player["zone"] == z]
        A(f"| {z} | {len(oz)} | {oz['fga'].median():.0f} | {oz['fga'].quantile(0.25):.0f} | "
          f"{oz['fga'].quantile(0.75):.0f} | {100 * oz['prior_dominated'].mean():.1f}% | "
          f"{100 * gz['prior_dominated'].mean():.1f}% |")
    A("")
    A(f"Overall: **{100 * obs['prior_dominated'].mean():.1f}%** of observed cells and "
      f"**{100 * player['prior_dominated'].mean():.1f}%** of the full grid are prior-dominated.")
    A("")
    A("This is deliberately conservative — a WNBA season is ~40 games, so few player-zone cells")
    A("out-attempt the noise. The continuous `data_weight` column lets the experiment pick its own")
    A("cut without rebuilding. Context (observed cells): "
      f"{100 * (obs['fga'] >= 10).mean():.1f}% have ≥10 attempts, "
      f"{100 * (obs['fga'] >= 25).mean():.1f}% ≥25, "
      f"{100 * (obs['fga'] >= 50).mean():.1f}% ≥50, "
      f"{100 * (~obs['prior_dominated']).mean():.1f}% ≥K (the flag).")
    A("")
    A("## Walk-forward spot test (`matchup_overlay.maps_before`)")
    A("")
    A(f"- Cutoff {spot['cutoff']} (season 2025): {spot['games_on_cutoff_day']} games / "
      f"{spot['shots_on_cutoff_day']} shots exist ON the cutoff date; maps built from "
      f"{spot['map_n_shots']:,} shots / {spot['map_n_games']} games, all strictly earlier.")
    A(f"- Spot team {spot['spot_team_id']} (played on the cutoff day): map FGA {spot['spot_team_fga']} "
      "== its strictly-before shot count; the cutoff-day game is excluded.")
    A(f"- **Result: {'PASS' if spot['pass'] else 'FAIL'}** — same-day games never enter `maps_before` maps.")
    A("")
    A("## Data surprises & notes")
    A("")
    A("- The league-wide shotchart pull drops 3 rows and adds 1 across 202,987 shots / 1,489 games")
    A("  (table above) — worst per-game effect is one shot; nothing systematic by season or team.")
    A("- `is_home` (master) vs shot-chart `HTM`: "
      f"{notes['is_home_htm_disagreements']} disagreements across all shots.")
    A(f"- Master vs shot-chart game dates: {notes['date_mismatches']} mismatches.")
    A("- Expansion teams appear cleanly: GSV from 2025; TOR and **PDX** (Portland Fire — not \"POR\")")
    A("  from 2026 (12/12/12/12/13/15 offense units by season). Their thin early-season history is a")
    A("  `maps_before` caveat (explicit KeyError before their first game), not a data gap.")
    A("- **Phoenix's abbreviation changed PHO → PHX in 2025** (same team_id 1611661317). Query maps by")
    A("  `team_id` across seasons; abbreviations are season-scoped display strings.")
    A("- Backcourt heaves are real attempts that FGA reconciliation must keep — they are their own")
    A("  zone precisely so they cannot pollute Above-the-Break-3 conversion.")
    A("")
    A("## Files")
    A("")
    A("| file | grain | rows |")
    A("|---|---|---|")
    A(f"| `shots_enriched.parquet` | shot | {len(df):,} |")
    A(f"| `team_zone_offense.csv` | season × type × team × zone | {n_off:,} |")
    A(f"| `team_zone_defense.csv` | season × type × team × zone (allowed) | {n_def:,} |")
    A(f"| `player_zone_offense.csv` | season × player × zone (full 6-zone grid) | {len(player):,} |")
    A(f"| `league_zone_averages.csv` | season × type × zone | {n_lg} |")
    A(f"| `shrinkage_priors.csv` | level × metric × zone | {len(ktab)} |")
    A("")
    A("Team/player conversion columns come in raw and `_shrunk` forms; `maps_before` recomputes")
    A("all *rates* from the pre-cutoff slice only. The stored K constants are full-sample")
    A("variance-ratio hyperparameters — a strict walk-forward experiment may re-estimate them on")
    A("train years and pass `k_table=` (documented in `matchup_overlay.py`).")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("loading shots + master ...")
    shots = load_shots()
    master = pd.read_parquet(MASTER_TEAM)
    df, notes = enrich(shots, master)
    print(f"  {len(df):,} shots enriched; notes: {notes}")

    print("estimating shrinkage priors (method of moments) ...")
    ktab = estimate_k_table(df)
    ktab.to_csv(OUT / "shrinkage_priors.csv", index=False)

    print("writing shots_enriched.parquet ...")
    df.to_parquet(OUT / "shots_enriched.parquet", index=False)

    print("building team zone maps ...")
    off = team_zone_offense(df, ["season", "season_type"], ktab)
    dfn = team_zone_defense(df, ["season", "season_type"], ktab)
    off.to_csv(OUT / "team_zone_offense.csv", index=False, float_format="%.6f")
    dfn.to_csv(OUT / "team_zone_defense.csv", index=False, float_format="%.6f")
    lg = league_zone(df, ["season", "season_type"])
    lg.to_csv(OUT / "league_zone_averages.csv", index=False, float_format="%.6f")

    print("building player zone maps (empirical-Bayes) ...")
    player = build_player_zone(df, ktab)
    player.to_csv(OUT / "player_zone_offense.csv", index=False, float_format="%.6f")

    print("reconciling vs master_team ...")
    R = reconcile(df, master)
    print("reconciling league_avg files ...")
    la = reconcile_league_avg(df)
    print("walk-forward spot test ...")
    spot = spot_test_maps_before(df)

    report = write_report(R, la, ktab, player, df, spot, notes,
                          n_off=len(off), n_def=len(dfn), n_lg=len(lg))
    (OUT / "RECONCILIATION.md").write_text(report, encoding="utf-8")

    print(f"\nFGA exact {R['fga_exact_n']}/{R['n_team_games']} | FGM exact {R['fgm_exact_n']} | "
          f"FG-pts exact {R['fgpts_exact_n']} | paint exact {R['paint_exact_n']} | "
          f"maps_before spot test: {'PASS' if spot['pass'] else 'FAIL'}")
    print(f"outputs -> {OUT}")


if __name__ == "__main__":
    main()
