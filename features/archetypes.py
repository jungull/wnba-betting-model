"""features/archetypes.py — opponent-archetype axes and composites for
player_vs_archetype_v1 (registered 2026-07-31T13:33:33Z).

NEW module: READS and REUSES the committed harness context (Ctx.team(),
Ctx.poss(), Ctx.shots()); modifies nothing. Works on COPIES of the cached
frames — the shared Ctx caches are never mutated.

The five preregistered axes (all walk-forward shifted traits of a team,
attached to player rows via tonight's opponent — a schedule fact):

  1. rot_height   minutes-weighted height of the team's rotation, averaged
                  over its last 10 games strictly before tonight
                  (data/reference/player_bios.csv heights; rolling(10,
                  min_periods=3).mean().shift(1) within (team, season))
  2. opp_3pa      the team's own 3PA-per-game, shifted EWMA alpha 0.10
  3. rim_protect  blocks per paint-attempt FACED: shifted-EWMA(blk) /
                  shifted-EWMA(paint attempts faced), alpha 0.10 (paint
                  attempts faced = RA+ITP shots taken against the team,
                  from the x-y shot charts)
  4. pressure     steals per defensive possession: shifted-EWMA(stl) /
                  shifted-EWMA(defensive possessions), alpha 0.10
  5. pace         possessions-per-game shifted EWMA (the harness's
                  pace_sew column, alpha 0.10)

Composites (preregistered):
  TALL_SHOOTERS  = rot_height > league median AND opp_3pa > league median
  SMALL_PRESSURE = rot_height < league median AND pressure > league median
with league medians computed WALK-FORWARD: the median of all team-game as-of
axis values at dates strictly before tonight, within season. Rows where any
input is NaN carry a NaN flag (mean-filled at fit time by the Design, never
peeked forward).

Pinned decisions: axis EWMAs fixed at alpha 0.10 (constitution rule 3
constant, same stance as the moderator set); rotation-height window = last
10 games, min_periods=3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import assert_quarantine

AX_ALPHA = 0.10
AXES = ["rot_height", "opp_3pa", "rim_protect", "pressure", "pace"]
COMPOSITES = ["TALL_SHOOTERS", "SMALL_PRESSURE"]


def _sew_tg(TG: pd.DataFrame, s: pd.Series, alpha: float = AX_ALPHA) -> pd.Series:
    return s.groupby([TG["team_id"], TG["season"]]).transform(
        lambda x: x.ewm(alpha=alpha, adjust=True).mean().shift(1))


def _sratio_tg(TG: pd.DataFrame, num: pd.Series, den: pd.Series,
               alpha: float = AX_ALPHA) -> pd.Series:
    n = num.groupby([TG["team_id"], TG["season"]]).transform(
        lambda x: x.ewm(alpha=alpha, adjust=True).mean())
    d = den.groupby([TG["team_id"], TG["season"]]).transform(
        lambda x: x.ewm(alpha=alpha, adjust=True).mean())
    return (n / d.replace(0.0, np.nan)).groupby(
        [TG["team_id"], TG["season"]]).shift(1)


def _walkforward_median(TG: pd.DataFrame, col: str) -> pd.Series:
    """League median of `col` over rows STRICTLY BEFORE each row's date,
    within season (same-date rows share the same value)."""
    out = pd.Series(np.nan, index=TG.index)
    for season, sub in TG.groupby("season"):
        days = np.sort(sub["game_date"].unique())
        med_by_day = {}
        for d in days:
            prior = sub.loc[sub["game_date"] < d, col].dropna()
            med_by_day[d] = float(np.median(prior)) if len(prior) else np.nan
        out.loc[sub.index] = sub["game_date"].map(med_by_day)
    return out


def build_archetype_table(ctx, heights: pd.Series,
                          audit: list | None = None) -> pd.DataFrame:
    """One row per (team, game) with the five as-of axes, the walk-forward
    medians, and the two composite flags. Row order: (team, season, date)."""
    T = ctx.team()
    TG = T[["game_id", "team_id", "season", "game_date",
            "fg3a", "blk", "stl", "pace_sew"]].copy()
    TG = TG.reset_index(drop=True)
    assert_quarantine(TG["game_date"], "archetype_team_game_table", audit)

    P = ctx.P
    # per-game minutes-weighted rotation height of the players who played
    h = P["player_id"].map(heights)
    wh = (P["minutes"] * h)
    grp = P.groupby(["game_id", "team_id"])
    num = wh.groupby([P["game_id"], P["team_id"]]).sum()
    den = P["minutes"].where(h.notna()).groupby([P["game_id"], P["team_id"]]).sum()
    h_game = (num / den).rename("h_game").reset_index()
    TG = TG.merge(h_game, on=["game_id", "team_id"], how="left", validate="1:1")
    TG["rot_height"] = TG["h_game"].groupby(
        [TG["team_id"], TG["season"]]).transform(
        lambda x: x.rolling(10, min_periods=3).mean().shift(1))

    # own 3PA volume
    TG["opp_3pa"] = _sew_tg(TG, TG["fg3a"])

    # paint attempts faced (RA+ITP shots against this defense)
    s = ctx.shots()
    smap = s.merge(
        P[["game_id", "player_id", "opp_team_id"]].drop_duplicates(),
        on=["game_id", "player_id"], how="left")
    smap = smap.dropna(subset=["opp_team_id"])
    paint = smap[smap["zone"].isin(["RA", "ITP"])]
    paf = (paint.groupby(["game_id", "opp_team_id"]).size()
           .rename("paint_faced").reset_index()
           .rename(columns={"opp_team_id": "team_id"}))
    paf["team_id"] = paf["team_id"].astype(np.int64)
    TG = TG.merge(paf, on=["game_id", "team_id"], how="left", validate="1:1")
    TG["rim_protect"] = _sratio_tg(TG, TG["blk"], TG["paint_faced"].fillna(0.0))

    # defensive possessions -> steals per defensive possession
    poss = ctx.poss()
    dp = (poss.groupby(["game_id", "defense_team_id"]).size()
          .rename("def_poss").reset_index()
          .rename(columns={"defense_team_id": "team_id"}))
    dp["team_id"] = dp["team_id"].astype(np.int64)
    TG = TG.merge(dp, on=["game_id", "team_id"], how="left", validate="1:1")
    TG["pressure"] = _sratio_tg(TG, TG["stl"], TG["def_poss"].fillna(0.0))

    # pace: reuse the committed as-of column
    TG["pace"] = TG["pace_sew"]

    # walk-forward league medians + composites
    TG["med_rot_height"] = _walkforward_median(TG, "rot_height")
    TG["med_opp_3pa"] = _walkforward_median(TG, "opp_3pa")
    TG["med_pressure"] = _walkforward_median(TG, "pressure")

    def _flag(cond_a, cond_b, inputs):
        ok = np.ones(len(TG), dtype=bool)
        for c in inputs:
            ok &= TG[c].notna().to_numpy()
        val = (cond_a & cond_b).astype(float)
        return pd.Series(np.where(ok, val, np.nan), index=TG.index)

    TG["TALL_SHOOTERS"] = _flag(
        TG["rot_height"] > TG["med_rot_height"],
        TG["opp_3pa"] > TG["med_opp_3pa"],
        ["rot_height", "med_rot_height", "opp_3pa", "med_opp_3pa"])
    TG["SMALL_PRESSURE"] = _flag(
        TG["rot_height"] < TG["med_rot_height"],
        TG["pressure"] > TG["med_pressure"],
        ["rot_height", "med_rot_height", "pressure", "med_pressure"])

    return TG


def opponent_pointer(ctx, TG: pd.DataFrame) -> np.ndarray:
    """Position array: for each ctx.P row, the TG row of tonight's OPPONENT
    (-1 if missing). Attaching by opponent is a schedule fact."""
    tg = TG.reset_index()[["index", "game_id", "team_id"]].rename(
        columns={"index": "tg_row"})
    key = ctx.P[["game_id", "opp_team_id"]].merge(
        tg, left_on=["game_id", "opp_team_id"],
        right_on=["game_id", "team_id"], how="left", validate="m:1")
    return key["tg_row"].fillna(-1).astype(np.int64).to_numpy()


def axis_on_rows(ctx, TG: pd.DataFrame, ptr: np.ndarray, col: str) -> pd.Series:
    """Opponent axis/composite value per P row (NaN where no opponent row)."""
    vals = TG[col].to_numpy(float)
    out = np.where(ptr >= 0, vals[np.clip(ptr, 0, None)], np.nan)
    return pd.Series(out, index=ctx.P.index)
