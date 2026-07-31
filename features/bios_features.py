"""features/bios_features.py — RUN 2 of player_feature_screen_v1: the COLLECT-S
bios / city / tip-time tier (catalog #7, 9, 10, 27, 28, 29, 30, 31, 33, 80, 86).

This module is deliberately NOT imported by features/__init__.py — run 1's
battery (ALL_CANDIDATES) is committed and closed. The run-2 runner
(bios_screen.py, repo root) imports this module directly and reuses
feature_lab.py's machinery unchanged. Protocol identical to run 1; BH is
applied ACROSS THIS RUN'S BATTERY as its own family (labeled run 2).

Inputs (all small reference tables; loaded quarantine-filtered):
  * data/reference/player_bios.csv   — per (player_id, season): age, height,
    weight, draft slot. Filtered to season <= 2024 at read. The null-height
    player-seasons STAY NULL (never imputed): features involving height are
    NaN there and the harness's nan_share / coverage accounting reports it.
    (In practice both null-height rows — 1630445/2021, 1643434/2026 — belong
    to player-seasons with zero played regular-season rows, so the screen
    universe has 100% height coverage; the coverage table proves it.)
  * data/reference/team_cities.csv   — venue lat/lon/elevation/timezone by
    franchise abbreviation. Rows with first_season > 2024 (PHX/GSV/TOR/PDX)
    never match the screening window.
  * data/reference/tip_times.csv     — captured tip times 2022-2026. 2021 has
    NO tip times; quarantined-era rows (2025/2026) are dropped at read.
    Tip-based features cover 2022+ only: rows without a captured tip are NaN
    (mean-filled at FIT time by the harness's documented NaN policy, with
    nan_share reporting the share) — never silently bucketed.

Encoding decisions (pinned before results were seen):
  * INHERENTLY-INTERACTION candidates (#7, 28, 29, 31, 33, 80) get the honest
    POOLED encoding here: the centered product term as a single feature.
    The moderator-permutation version of each belongs to the separately
    registered interactions protocol (player_feature_interactions_v1) — the
    pooled row here makes no interaction claim and there is no double-claiming.
  * Centering constants are fixed A PRIORI (round numbers near the league
    center, chosen before any screening statistic was computed — the same
    doctrine as common.TEAM_ALPHA): AGE_REF=27.0 yrs, H_REF=72.5 in,
    W_REF=170.0 lbs, EXP_REF=5.0 yrs. A centered single product column is a
    blend of the interaction and the partner main effect; the clean
    interaction test lives in the other protocol.
  * Schedule facts (B2B flag, travel distance, tip hour, venue elevation)
    attach unshifted — known pre-tip. Trends inside features (#28/#29
    volatilities, #80 load) are strictly-prior via run 1's sroll/f79
    machinery. Traits (age, height, weight, draft, experience) are static
    per (player, season).
  * B2B is the PLAYER-level flag (days since own previous played game <= 1),
    the same rest basis as run 1's #6 rest profile: a player who sat
    yesterday's game is not on a back-to-back.
  * #9 is the raw haversine distance (main effect); #33 is the age-centered
    product — the catalog's "x age" note on #9 is realized by #33, not
    duplicated inside #9.
  * #27 sweeps its PEAK AGE over PEAK_GRID on the inner folds only through
    the harness's sweep engine (the committed #92 blend-weight precedent):
    feature = -(age - peak)^2, a single-column age curve that contains both
    the linear and quadratic age terms with the peak setting their mix,
    frozen per channel before 2024 is touched.
  * #30: pedigree = ln(UNDRAFTED_PICK / effective_pick), effective_pick =
    draft_number for drafted players and UNDRAFTED_PICK=40.0 (one past the
    deepest observed pick, 39) for explicit "Undrafted" rows; gated to
    low-experience rows (experience <= 2 yrs), 0 for vets. Experience =
    season - draft_year, computable for DRAFTED players only — undrafted
    rows have no debut year in bios, so their experience AND the gate are
    unknown and the feature is honestly NaN there (reported, never guessed).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

from .common import (Candidate, DATA, SCREEN_SEASONS, assert_quarantine, gps,
                     shrink, sroll)
from .fam_h import f79_rolling_7day_load

# --- a-priori constants (pinned; see module docstring) ----------------------
AGE_REF = 27.0            # yrs   (league mean ~27.8)
H_REF = 72.5              # in    (league mean ~72.6)
W_REF = 170.0             # lbs   (league mean ~172.7)
EXP_REF = 5.0             # yrs since draft
UNDRAFTED_PICK = 40.0     # one past the deepest observed pick (39)
LOW_EXP_MAX = 2.0         # "low-experience" gate for the draft-pedigree prior
AFTERNOON_CUTOFF = 17.0   # local tip hour < 17 = afternoon (run 1's cutoff)
PEAK_GRID = [float(a) for a in range(22, 35)]   # #27 peak-age sweep, inner folds only
TIP_BUCKET_K = 10.0       # shrinkage for the personal aft/eve profile (run 1's k)
VOL_WINDOW, VOL_MINP = 10, 4   # rolling-std params (exact #37 machinery)
EARTH_R_KM = 6371.0


# ---------------------------------------------------------------------------
# reference loaders (memoized on the shared Ctx; keys namespaced "r2_")
# ---------------------------------------------------------------------------

def bios_on_P(ctx) -> pd.DataFrame:
    """Per-P-row bios traits: age, height_inches, weight_lbs,
    experience_years (drafted only), pick_eff (draft slot; 40 = undrafted).
    Nulls PROPAGATE — no imputation here, ever."""
    def build():
        b = pd.read_csv(DATA / "reference" / "player_bios.csv")
        b = b[b["season"].isin(SCREEN_SEASONS)].copy()   # 2025/2026 rows never enter
        undrafted = b["draft_raw"].astype(str).str.startswith("Undrafted")
        b["experience_years"] = np.where(
            b["draft_year"].notna(), b["season"] - b["draft_year"], np.nan)
        b["pick_eff"] = np.where(
            b["draft_number"].notna(), b["draft_number"],
            np.where(undrafted, UNDRAFTED_PICK, np.nan))
        cols = ["player_id", "season", "age", "height_inches", "weight_lbs",
                "experience_years", "pick_eff"]
        P = ctx.P
        out = P[["player_id", "season"]].merge(
            b[cols], on=["player_id", "season"], how="left", validate="m:1")
        out.index = P.index
        return out
    return ctx._memo("r2_bios_on_P", build)


def venue_geo(ctx) -> pd.DataFrame:
    """Per-P-row venue lat/lon/elevation (home team's arena — schedule fact)."""
    def build():
        c = pd.read_csv(DATA / "reference" / "team_cities.csv")
        c = c[c["first_season"] <= 2024].copy()   # PHX/GSV/TOR/PDX rows are post-window
        geo = c.set_index("abbreviation")[["lat", "lon", "elevation_ft"]]
        P = ctx.P
        home_rows = P[P["is_home"].astype(float).eq(1)][["game_id", "team_abbreviation"]]
        game_home = (home_rows.drop_duplicates("game_id")
                     .set_index("game_id")["team_abbreviation"])
        venue = P["game_id"].map(game_home)
        out = pd.DataFrame({
            "lat": venue.map(geo["lat"]).astype(float),
            "lon": venue.map(geo["lon"]).astype(float),
            "elev_kft": venue.map(geo["elevation_ft"]).astype(float) / 1000.0,
        }, index=P.index)
        if out["lat"].isna().any():
            missing = venue[out["lat"].isna()].unique().tolist()
            raise RuntimeError(f"venue city unmapped for abbreviations {missing}")
        return out
    return ctx._memo("r2_venue_geo", build)


def tip_local(ctx) -> dict:
    """{'hour_on_P': Series (local fractional tip hour; NaN where uncaptured),
        'n_games': int, 'n_mismatch': int} — local hour recomputed from
    tip_utc + the team_cities timezone (zoneinfo, offline) and cross-checked
    against the table's tip_hour_local. 2021 games are all NaN (no captures);
    quarantined-era rows are dropped before anything enters memory."""
    def build():
        t = pd.read_csv(DATA / "reference" / "tip_times.csv")
        t = t[t["season"].isin(SCREEN_SEASONS)].copy()   # 2025/2026 rows never enter
        t["game_id"] = t["game_id"].astype(str)
        t = t[t["game_id"].isin(ctx.games)].copy()       # RS screen games only
        assert_quarantine(t["game_date"], f"tip_times[RS<=2024,n={len(t)}]", ctx.audit)
        c = pd.read_csv(DATA / "reference" / "team_cities.csv")
        tz_by_team = (c[c["first_season"] <= 2024]
                      .set_index("team_id")["timezone"].to_dict())
        utc = pd.to_datetime(t["tip_utc"], utc=True)
        hours, n_mismatch = [], 0
        for u, home_id, tab_hour in zip(utc, t["home_team_id"], t["tip_hour_local"]):
            tz = tz_by_team.get(int(home_id))
            if tz is None:
                hours.append(np.nan)
                continue
            loc = u.tz_convert(ZoneInfo(tz))
            h = loc.hour + loc.minute / 60.0
            if int(h) != int(tab_hour):
                n_mismatch += 1
            hours.append(h)
        t["tip_hour"] = hours
        m = t.set_index("game_id")["tip_hour"]
        return {"hour_on_P": ctx.P["game_id"].map(m).astype(float),
                "n_games": int(t["tip_hour"].notna().sum()),
                "n_mismatch": n_mismatch}
    return ctx._memo("r2_tip_local", build)


def travel_km(ctx) -> pd.Series:
    """Haversine km between this game's venue and the venue of the player's
    previous played game, within (player, season) — the same previous-game
    basis as run 1's #8 timezone shift. First played game of a season has no
    prior venue: 0.0 (no travel information; mirrors #8's fillna(0))."""
    def build():
        P = ctx.P
        g = venue_geo(ctx)
        lat = pd.Series(np.radians(g["lat"]), index=P.index)
        lon = pd.Series(np.radians(g["lon"]), index=P.index)
        plat = lat.groupby(gps(P)).shift(1)
        plon = lon.groupby(gps(P)).shift(1)
        a = (np.sin((lat - plat) / 2.0) ** 2
             + np.cos(lat) * np.cos(plat) * np.sin((lon - plon) / 2.0) ** 2)
        d = 2.0 * EARTH_R_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
        return pd.Series(d, index=P.index).fillna(0.0)
    return ctx._memo("r2_travel_km", build)


def b2b_flag(ctx) -> pd.Series:
    """Player-level back-to-back: own previous PLAYED game was yesterday.
    First played game of a season is not a B2B (NaN rest -> 0)."""
    return (ctx.P["days_rest_player"] <= 1.0).astype(float)


def load7(ctx) -> pd.Series:
    """Rolling 7-day strictly-prior minutes load — run 1's #79 machinery."""
    return ctx._memo("r2_load7", lambda: f79_rolling_7day_load(ctx, None))


# ---------------------------------------------------------------------------
# candidate builds
# ---------------------------------------------------------------------------

def f07_b2b_x_age(ctx, alpha):
    return b2b_flag(ctx) * (bios_on_P(ctx)["age"] - AGE_REF)


def f09_travel_distance(ctx, alpha):
    return travel_km(ctx)


def f10_tip_split_local(ctx, alpha):
    """Personal afternoon-vs-evening surprise profile (run 1's #10 encoding:
    shrunken strictly-prior mean of rate-minus-baseline within the tip bucket,
    k=10, personalized-only) — but tip class from CAPTURED LOCAL TIP TIMES
    instead of the PBP wall-clock proxy, and rows without a captured tip are
    NaN instead of silently classed as evening. Coverage: 2022+ only."""
    P = ctx.P
    tip = tip_local(ctx)["hour_on_P"]
    known = tip.notna()
    sub_pl = P.loc[known, "player_id"]
    sub_se = P.loc[known, "season"]
    sub_bk = pd.Series(np.where(tip[known] < AFTERNOON_CUTOFF, "aft", "eve"),
                       index=tip[known].index)
    grp = [sub_pl, sub_se, sub_bk]
    out = {}
    for ch, base in ctx.baselines.items():
        dv = (P[f"r_{ch}"] - base)[known]
        prior = dv.groupby(grp).transform(lambda x: x.expanding().mean().shift(1))
        n = pd.Series(0.0, index=dv.index).groupby(grp).cumcount().astype(float)
        val = shrink(prior, n, TIP_BUCKET_K).fillna(0.0)   # known rows: 0 until info
        out[ch] = val.reindex(P.index)                     # unknown tip -> NaN
    return out


def f27_age_curve(ctx, peak):
    """-(age - peak)^2; peak swept on inner folds only (PEAK_GRID, the #92
    sweep-engine precedent), frozen per channel."""
    return -((bios_on_P(ctx)["age"] - float(peak)) ** 2)


def f28_height_x_paintvol(ctx, alpha):
    vol = sroll(ctx.P, ctx.P["r_paint"], VOL_WINDOW, "std",
                min_periods=VOL_MINP).fillna(0.0)   # exact #37 machinery
    return (bios_on_P(ctx)["height_inches"] - H_REF) * vol


def f29_exp_x_minutesvol(ctx, alpha):
    vol = sroll(ctx.P, ctx.P["minutes"], VOL_WINDOW, "std",
                min_periods=VOL_MINP).fillna(0.0)
    return (bios_on_P(ctx)["experience_years"] - EXP_REF) * vol


def f30_draft_pedigree(ctx, alpha):
    b = bios_on_P(ctx)
    score = np.log(UNDRAFTED_PICK / b["pick_eff"])
    gate = (b["experience_years"] <= LOW_EXP_MAX).astype(float)
    return (score * gate).where(b["experience_years"].notna())


def f31_weight_x_b2b(ctx, alpha):
    return b2b_flag(ctx) * (bios_on_P(ctx)["weight_lbs"] - W_REF)


def f33_age_x_travel(ctx, alpha):
    return travel_km(ctx) * (bios_on_P(ctx)["age"] - AGE_REF)


def f80_load_x_age(ctx, alpha):
    return load7(ctx) * (bios_on_P(ctx)["age"] - AGE_REF)


def f86_venue_elevation(ctx, alpha):
    return venue_geo(ctx)["elev_kft"]


CANDIDATES = [
    Candidate(7, "b2b_x_age_pooled", "C", f07_b2b_x_age,
              note="player-level B2B flag x (age-27); pooled product — the "
                   "moderator-permutation version lives in the interactions protocol"),
    Candidate(9, "travel_km_since_last", "A", f09_travel_distance,
              note="haversine km venue-to-venue vs own previous played game; "
                   "first game of season = 0 (schedule fact)"),
    Candidate(10, "tip_split_local", "A", f10_tip_split_local,
              note="run-1 #10 encoding with captured local tip times (2022+ "
                   "only; uncaptured rows NaN, never bucketed)"),
    Candidate(27, "age_curve_peak", "C", f27_age_curve, alpha_swept=True,
              sweep_grid=PEAK_GRID,
              note="-(age-peak)^2; peak swept 22..34 on inner folds (the #92 "
                   "sweep-engine precedent), frozen per channel"),
    Candidate(28, "height_x_paint_vol", "C", f28_height_x_paintvol,
              channels=["paint"],
              note="(height-72.5) x rolling-10 std of paint rate (#37 "
                   "machinery); pooled product — interactions protocol owns "
                   "the moderator test"),
    Candidate(29, "experience_x_minutes_vol", "C", f29_exp_x_minutesvol,
              note="(exp-5) x rolling-10 std of minutes; exp = season - "
                   "draft_year (drafted only; undrafted NaN); pooled product"),
    Candidate(30, "draft_pedigree_lowexp", "C", f30_draft_pedigree,
              note="ln(40/pick) gated to experience<=2 (0 for vets, NaN for "
                   "undrafted — no debut year in bios); undrafted pick=40"),
    Candidate(31, "weight_x_b2b_pooled", "C", f31_weight_x_b2b,
              note="player-level B2B flag x (weight-170); pooled product; "
                   "15 in-window player-seasons lack weight (NaN)"),
    Candidate(33, "age_x_travel_pooled", "C", f33_age_x_travel,
              note="travel km x (age-27); pooled product — interactions "
                   "protocol owns the moderator test"),
    Candidate(80, "minutes_load_x_age_pooled", "H", f80_load_x_age,
              note="7-day strictly-prior minutes load (#79 machinery) x "
                   "(age-27); pooled product"),
    Candidate(86, "venue_elevation", "H", f86_venue_elevation,
              note="home arena elevation in kft (schedule fact; max 2.03 kft "
                   "Las Vegas — near-zero expected per catalog)"),
]
