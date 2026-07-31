"""features/moderators.py — the 11 preregistered moderator traits for
player_feature_interactions_v1 (registered 2026-07-31T13:16:25Z), plus the
own-trait subset reused by player_vs_archetype_v1.

NEW module for the interaction screens: it READS and REUSES the committed
harness (features.common, fam_h, fam_f) and modifies nothing.

Moderator set (preregistered, CLOSED — the registration's features_desc):
    age, height_inches, experience_years        (data/reference/player_bios.csv)
    career_minutes                              (odometer, cross-season strictly prior)
    usage_ewma, min7d_load, rim_share,
    fg3a_rate, transition_share, starter_share  (walk-forward player trends)
    bench_depth                                 (own-team rotation trait, shifted)

Pinned decisions (documented in the run REPORT.md):
  * Trend-moderator EWMAs are FIXED at alpha=0.10 (constitution rule 3
    constant). The registered alpha-sweep clause applies to candidate
    FEATURES; the moderator set is a closed trait battery, so its smoothing
    is pinned a-priori, not tuned.
  * Bios traits are static per (player, season); age is computed from
    birthdate at July 1 of the season (fallback: the bios age column).
  * experience_years = season - draft_year for drafted players; undrafted
    players (147 bios rows) use the a-priori proxy age - 22 (typical rookie
    age), clipped at 0. This is feature encoding, not raw-data imputation.
  * career_minutes counts 2021+ minutes only (data starts 2021) — a
    truncated odometer; documented limitation, same as catalog #32 would
    have had.
  * The bios file contains 2025/2026 season rows; they are filtered out at
    load (season <= 2024) in keeping with the absolute quarantine.
  * transition_share reuses the harness's #65 early-clock ATTEMPT share
    implementation (the committed reading of catalog #65), at alpha 0.10.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import REPO, sew, sratio_ew, sexp_mean, gps
from . import fam_h, fam_f

MOD_ALPHA = 0.10

MODERATORS = [
    "age", "height_inches", "experience_years", "career_minutes",
    "usage_ewma", "min7d_load", "rim_share", "fg3a_rate",
    "transition_share", "starter_share", "bench_depth",
]

# own-trait subset for player_vs_archetype_v1 level-2 tests
OWN_TRAITS = ["height_inches", "rim_share", "fg3a_rate", "transition_share"]


def load_bios(audit: list | None = None) -> pd.DataFrame:
    """Season-filtered bios (<=2024). Appends a manual audit row (the file has
    no game dates; the quarantine check is on the season key)."""
    b = pd.read_csv(REPO / "data" / "reference" / "player_bios.csv")
    n_raw = len(b)
    b = b[b["season"] <= 2024].copy()
    if audit is not None:
        audit.append({
            "matrix": "player_bios[season<=2024]", "n": int(len(b)),
            "min_date": f"season {int(b['season'].min())}",
            "max_date": f"season {int(b['season'].max())}",
            "cutoff": "season 2024 (quarantine-era rows dropped at load: "
                      f"{n_raw - len(b)})",
            "pass": bool(b["season"].max() <= 2024),
        })
    b["birthdate"] = pd.to_datetime(b["birthdate"], errors="coerce")
    return b


def heights_by_player(bios: pd.DataFrame) -> pd.Series:
    """Static height per player_id (median across bios seasons)."""
    return bios.groupby("player_id")["height_inches"].median()


def build_moderators(ctx, bios: pd.DataFrame) -> pd.DataFrame:
    """The 11-column moderator frame aligned to ctx.P.index. NaNs are left in
    place — the harness Design mean-fills with FIT-row means at fit time."""
    P = ctx.P
    out = pd.DataFrame(index=P.index)

    # --- bios traits (static per player-season) ----------------------------
    key = P[["player_id", "season"]].copy()
    bsub = bios[["player_id", "season", "age", "birthdate", "draft_year"]].copy()
    merged = key.merge(bsub, on=["player_id", "season"], how="left")
    merged.index = P.index

    season_mid = pd.to_datetime(P["season"].astype(int).astype(str) + "-07-01")
    age_bd = (season_mid - merged["birthdate"]).dt.days / 365.25
    out["age"] = age_bd.where(age_bd.notna(), merged["age"])

    out["height_inches"] = P["player_id"].map(heights_by_player(bios))

    dy = merged["draft_year"]
    drafted = dy.notna() & (dy > 1990) & (dy <= P["season"].astype(float))
    exp_draft = (P["season"].astype(float) - dy).where(drafted)
    exp_proxy = (out["age"] - 22.0).clip(lower=0.0)
    out["experience_years"] = exp_draft.where(drafted, exp_proxy)

    # --- career odometer (cross-season strictly prior; P is chronological
    #     within player because it is sorted (player, season, date)) --------
    out["career_minutes"] = (P.groupby("player_id")["minutes"]
                             .transform(lambda s: s.cumsum().shift(1))
                             .fillna(0.0))

    # --- walk-forward player trends (alpha pinned at 0.10) -----------------
    out["usage_ewma"] = sew(P, P["usage36"], MOD_ALPHA)
    out["min7d_load"] = fam_h.f79_rolling_7day_load(ctx, None)

    sp = ctx.shot_pg_on_P(["ra_a", "fga"]).fillna(0.0)
    out["rim_share"] = sratio_ew(P, sp["ra_a"], sp["fga"], MOD_ALPHA)

    out["fg3a_rate"] = sratio_ew(P, P["fg3a"], P["minutes"], MOD_ALPHA) * 36.0
    out["transition_share"] = fam_f.f65_early_clock_share(ctx, MOD_ALPHA)
    out["starter_share"] = sexp_mean(P, P["starter_flag"])

    # --- own-team rotation trait (shifted EWMA 0.10, from the team frame) --
    out["bench_depth"] = ctx.team_cols_on_P(["bench_share_sew"])["t_bench_share_sew"]

    return out[MODERATORS]
