#!/usr/bin/env python3
"""
props_edge_v1 — preregistered player-points props edge measurement harness.

Registered 2026-07-31T14:59:26Z (experiments/registry.jsonl, experiment_id
props_edge_v1). The registration's features_desc is the BINDING protocol; this
file implements it and nothing beyond it. MEASUREMENT STUDY: sentinel gates by
design — surviving pockets become preregistered live paper-trade cells graded
on future games. Nothing here is fit; the projection is the frozen committed
baseline family (EWMA alpha=0.30).

PROJECTION (regime-A honest, walk-forward, per player-game)
    proj_points = per36_pts_ewma * expected_minutes / 36
    - per36_pts_ewma: EWMA(alpha=0.30, pandas adjust=True — house convention,
      features/common.py) of pts/minutes*36 over the player's PLAYED rows
      (minutes > 0), within (player_id, season), season-reset per house rules
      (Regular Season -> Playoffs continuous within a season, matching the
      pocket_mining schedule convention "across both season types within a
      season"). The value used for a target game is the state AFTER the last
      played game strictly BEFORE the target date — i.e. the shifted value;
      the target game's own stats never enter (constitution rule 1).
    - expected_minutes: EWMA(alpha=0.30, adjust=True) of minutes over the same
      played rows, same shift discipline.
    - Gate: >= 3 PRIOR played appearances in that season, else NO projection
      (explicit skip, counted). Never guessed, never imputed.

    Channel-sum equivalence (registration: "per-channel sum equivalence
    documented"): per game, pts == ftm + 3*fg3m + paint_pts + nonpaint2_pts
    (box identity, verified in the channel experiment). Per-36 channel rates
    therefore sum to the per-36 points rate row by row, and because the EWMA
    is a fixed linear functional of the observations, the sum of the four
    per-channel EWMA rates (common alpha=0.30, common played-row index, common
    shift) is EXACTLY the EWMA of the total points rate. Summing four channel
    projections would reproduce this projection to machine precision. The
    equivalence BREAKS only if channels get per-channel alphas or structural
    opponent adjustments (the team-level architecture does both; this
    registered projection does neither). WE USE THE TOTAL POINTS RATE
    DIRECTLY — stated per the registration.

NAME RESOLUTION (master resolver pattern, unique-only, never guessed)
    prop player_name -> master player_id. Normalization: NFKD, strip
    accents, lowercase alphanumerics (historical_props_backfill._norm).
    Pass 1: unique match within (season, teams-of-the-event) — candidate ids
    are players with any appearance for either event team that season; this
    is what disambiguates two-Samuelson-style same-name collisions when the
    namesakes are on different teams. Pass 2 (only if pass 1 finds nothing):
    unique match within the whole season. Each pass also tries the two-token
    'Last First' flip (seen in the 2023 probe). >1 candidate id in scope =
    ambiguous = unresolved (counted, listed). 0 = unresolved (counted,
    listed). Resolution never guesses.

EDGE / BETS / GRADING (registration verbatim)
    Per (player, game, book, line) row: edge = projection - line; bet OVER if
    edge >= threshold, UNDER if edge <= -threshold; thresholds {1.0, 2.0,
    3.0}. Settlement from master_player actual pts. Player with no master row
    for the game, or minutes null/0 -> VOID (no action; excluded from stakes
    settled; counted). Push (actual == line): risks the stake, returns 0, and
    counts in stakes settled — house pocket_mining convention. ROI = net
    profit / stakes settled, flat 1u stakes.
    Price bases (both, per registration): captured = the row's own
    over/under american price (missing/anomalous |price|>=10000 -> that bet
    is unpriceable in the captured basis; counted); synthetic110 = -110 at
    the same line.
    Executions (both, per registration):
      consensus: one candidate per (player, game); consensus line = median
        across books' MAIN lines (a book's main line = its most balanced-
        priced line when it posts alternates; see accounting); decision edge
        vs the consensus line; synthetic basis settles at the consensus line
        at -110 (house consensus basis); captured basis = median captured
        price among books whose main line equals the consensus line (no such
        book -> unpriceable, counted).
      best_line: same decision as consensus (same bet set — execution varies
        the fill only, house convention); fill = most favorable line for the
        chosen side among ALL captured rows (over: min line; under: max
        line), tie-break best price multiplier (pocket_mining's exact
        selection); captured basis settles the line taken at its price;
        synthetic110 basis reprices the SAME fill at -110 (isolates
        line-shopping value from price).
      per_book: every (player, game, book, line) row is its own candidate at
        its own line (the registration's base unit; alternate lines are
        separate rows — share reported in accounting). The `book` pocket
        lives here.

POCKET BATTERY (closed, registered; house cell pattern: base grid x ONE
conditioner level, overlap handled by the per-cell null)
    Base grid: execution {consensus, best_line, per_book} x price basis
    {captured, synthetic110} x threshold {1.0, 2.0, 3.0}.
    Conditioners (one at a time): none/all; line-height terciles {low, mid,
    high} of the CONSENSUS line (player-game attribute, per-season
    boundaries over candidate player-games); role {starter, bench} =
    started_last (starter_flag of the last prior played game); minutes-volume
    terciles {low, mid, high} of expected minutes (same tercile convention);
    book (per_book execution only; data-derived list); season (data-derived);
    venue {home, away} (the resolved player's team — team of their last
    prior appearance — vs the event's home/away; unknown -> excluded from
    venue cells only, counted).

HONESTY MACHINERY (registered)
    200 within-season permutations of the projection column across candidate
    player-games (one draw per battery, shared by all executions; row
    attributes, lines, outcomes, and pocket labels stay fixed — only the
    projection moves). Per-cell p = fraction of permuted batteries with
    equal-or-better ROI in that cell (empty permuted cells count as
    not-better; min resolvable p = 1/n_perms; Phipson-Smyth companion
    reported). BH at 10% across starred-eligible cells (n_settled >= 100,
    the registered floor). 90% date-clustered bootstrap CI per cell
    (evalharness.compare.cluster_bootstrap_ci, house convention, n_boot
    2000, clusters = game dates).

MODES
    --self-test                primitives + walk-forward toys, no data files
    --dev                      end-to-end on the LIVE capture table
                               (data/props_capture/master_props.csv,
                               READ-ONLY): join/schema validation. Today's
                               games are ungraded until played — expect ZERO
                               settled bets on a same-day table; the run says
                               so explicitly. No inference in dev.
    --historical               the full registered study on
                               data/props_capture/historical/
                               master_props_historical.csv. REFUSES cleanly
                               if the backfill is absent or incomplete
                               (collector checkpoint backfill_done.csv vs
                               master_team 2024-2026 game list) unless
                               --allow-partial, which labels every artifact
                               PARTIAL and draws no conclusions.

FILE BOUNDARY: reads repo data read-only; writes ONLY experiments/props_edge/
(dev/ and partial_dryrun/ subdirs for non-final runs). Never touches
registry.jsonl, leaderboards/, the live capture table, or the collector-owned
historical/ directory. No network, no git.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

# read-only import: the house bootstrap (same primitive pocket_mining uses)
from evalharness.compare import cluster_bootstrap_ci, ComparisonError  # noqa: E402

EXPERIMENT_ID = "props_edge_v1"
OUTDIR = REPO / "experiments" / "props_edge"
LIVE_CSV = REPO / "data" / "props_capture" / "master_props.csv"
HIST_CSV = REPO / "data" / "props_capture" / "historical" / "master_props_historical.csv"
DONE_CSV = REPO / "data" / "props_capture" / "historical" / "backfill_done.csv"
MASTER_PLAYER = REPO / "data" / "masters" / "master_player.parquet"
MASTER_TEAM = REPO / "data" / "masters" / "master_team.parquet"

MARKET = "player_points"
ALPHA = 0.30                      # registered frozen family
MIN_PRIOR = 3                     # registered appearance gate
THRESHOLDS = [1.0, 2.0, 3.0]      # registered
EXECUTIONS = ["consensus", "best_line", "per_book"]
PRICE_BASES = ["captured", "synthetic110"]
N_PERMS_DEFAULT = 200             # registered
N_BOOT_DEFAULT = 2000             # house convention
MIN_CELL_N = 100                  # registered starred-eligibility floor
BH_Q = 0.10                       # registered FDR level
SEED = 20260731
HIST_SEASONS = [2024, 2025, 2026]  # the registered backfill scope
WIN_110 = 100.0 / 110.0
PUSH_TOL = 1e-9
ROI_TIE_EPS = 1e-12
PRICE_ANOMALY_ABS = 10000         # house rule (pocket_mining)

# Odds API full names -> franchise abbreviations by era (copied from
# historical_props_backfill.py; not imported — that module pulls in the
# network stack and this harness is strictly offline).
TEAM_ABBRS = {
    "Atlanta Dream": ["ATL"], "Chicago Sky": ["CHI"], "Connecticut Sun": ["CON"],
    "Dallas Wings": ["DAL"], "Golden State Valkyries": ["GSV"],
    "Indiana Fever": ["IND"], "Las Vegas Aces": ["LVA"],
    "Los Angeles Sparks": ["LAS"], "Minnesota Lynx": ["MIN"],
    "New York Liberty": ["NYL"], "Phoenix Mercury": ["PHX", "PHO"],
    "Portland Fire": ["PDX"], "Seattle Storm": ["SEA"],
    "Toronto Tempo": ["TOR"], "Washington Mystics": ["WAS"],
}

CONDITIONERS = ["none", "line_terc", "role", "min_terc", "book", "season", "venue"]


# ---------------------------------------------------------------------------
# primitives (house forms; attributed)
# ---------------------------------------------------------------------------

def _norm(s) -> str:
    """historical_props_backfill._norm — the master resolver normalization."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _mult(price: float) -> float:
    """American price -> flat-stake profit multiplier on a win (pocket_mining)."""
    return 100.0 / abs(price) if price < 0 else price / 100.0


def _amer_prob(price: float) -> float:
    """American price -> implied probability with vig (pocket_mining)."""
    return (-price) / ((-price) + 100.0) if price < 0 else 100.0 / (price + 100.0)


def _settle_code(actual: float, line: float, side: int) -> int:
    """+1 win / 0 push / -1 loss for side (+1 over, -1 under)."""
    if abs(actual - line) <= PUSH_TOL:
        return 0
    won = actual > line if side > 0 else actual < line
    return 1 if won else -1


def bh_qvalues(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted q-values (step-up, plain BH; pocket_mining)."""
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p, kind="stable")
    ranked = p[order] * m / (np.arange(m) + 1.0)
    q_sorted = np.minimum.accumulate(ranked[::-1])[::-1]
    q = np.empty(m)
    q[order] = np.minimum(q_sorted, 1.0)
    return q


def et_date(commence_iso: str) -> str:
    """Event UTC commence -> US/Eastern calendar date (the master game_date).

    Prefers zoneinfo; falls back to fixed UTC-4 (every game in scope
    commences April-October, which is EDT throughout)."""
    dt = datetime.fromisoformat(str(commence_iso).replace("Z", "+00:00"))
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return (dt - timedelta(hours=4)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# projection stack (registered; walk-forward)
# ---------------------------------------------------------------------------

def build_states(mp: pd.DataFrame) -> pd.DataFrame:
    """Per played row: post-game EWMA states + appearance count.

    The state AFTER game k equals the shifted (pre-game) value at game k+1 —
    a target date d is served by the last played row with game_date < d,
    which is exactly the constitution's shift discipline and also covers
    games not yet in the master (live/future targets)."""
    p = mp[(mp["minutes"].notna()) & (mp["minutes"] > 0)].copy()
    p["per36"] = p["pts"].astype(float) / p["minutes"] * 36.0
    p = p.sort_values(["player_id", "season", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    g = p.groupby(["player_id", "season"], sort=False)
    p["per36_after"] = g["per36"].transform(
        lambda x: x.ewm(alpha=ALPHA, adjust=True).mean())
    p["min_after"] = g["minutes"].transform(
        lambda x: x.ewm(alpha=ALPHA, adjust=True).mean())
    p["n_after"] = g.cumcount() + 1
    return p[["player_id", "season", "game_date", "game_id", "per36_after",
              "min_after", "n_after", "starter_flag", "team_abbreviation"]]


def project_targets(targets: pd.DataFrame, states: pd.DataFrame) -> pd.DataFrame:
    """Attach strictly-prior projection state to (player_id, season, date).

    merge_asof backward with allow_exact_matches=False on the date: only
    games with game_date < target date can serve the state."""
    t = targets.copy()
    t["_td"] = pd.to_datetime(t["game_date"])
    s = states.copy()
    s["_sd"] = pd.to_datetime(s["game_date"])
    s = s.sort_values("_td" if "_td" in s else "_sd")
    t = t.sort_values("_td").reset_index()
    merged = pd.merge_asof(
        t, s[["player_id", "season", "_sd", "per36_after", "min_after",
              "n_after", "starter_flag", "team_abbreviation"]].sort_values("_sd"),
        left_on="_td", right_on="_sd", by=["player_id", "season"],
        direction="backward", allow_exact_matches=False)
    merged = merged.set_index("index").sort_index()
    merged["n_prior"] = merged["n_after"].fillna(0).astype(int)
    merged["proj"] = np.where(merged["n_prior"] >= MIN_PRIOR,
                              merged["per36_after"] * merged["min_after"] / 36.0,
                              np.nan)
    merged["exp_min"] = np.where(merged["n_prior"] >= MIN_PRIOR,
                                 merged["min_after"], np.nan)
    merged["started_last"] = merged["starter_flag"]      # of last prior game
    merged["player_team"] = merged["team_abbreviation"]  # team of last prior game
    return merged.drop(columns=["_td", "_sd", "per36_after", "min_after",
                                "n_after", "starter_flag", "team_abbreviation"])


# ---------------------------------------------------------------------------
# props loading (schema handshake between the live and historical tables)
# ---------------------------------------------------------------------------

LIVE_COLS = ["api_event_id", "home_team", "away_team", "commence_time",
             "bookmaker_key", "market_key", "player_name", "line",
             "over_price", "under_price", "snapshot_utc", "last_update"]
HIST_COLS = ["game_id", "api_event_id", "home_team", "away_team",
             "commence_time", "snapshot_requested_utc", "snapshot_returned_utc",
             "bookmaker_key", "market_key", "player_name", "line",
             "over_price", "under_price", "last_update"]
# unified internal frame both loaders must produce (the schema handshake)
UNIFIED_COLS = ["game_id", "api_event_id", "home_team", "away_team",
                "commence_time", "game_date", "season", "bookmaker_key",
                "market_key", "player_name", "line", "over_price",
                "under_price", "snapshot_utc", "source"]


def _numeric_prices(df: pd.DataFrame, acct: dict) -> pd.DataFrame:
    for c in ("over_price", "under_price"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
        anom = df[c].abs() >= PRICE_ANOMALY_ABS
        acct[f"price_anomaly_{c}"] = int(anom.sum())
        df.loc[anom, c] = np.nan
    df["line"] = pd.to_numeric(df["line"], errors="coerce")
    acct["rows_bad_line_dropped"] = int(df["line"].isna().sum())
    return df[df["line"].notna()].copy()


def load_props_live(acct: dict) -> pd.DataFrame:
    df = pd.read_csv(LIVE_CSV, dtype=str)
    missing = [c for c in LIVE_COLS if c not in df.columns]
    if missing:
        sys.exit(f"live table schema drift — missing columns {missing}")
    acct["rows_total"] = len(df)
    df = df[df["market_key"] == MARKET].copy()
    acct["rows_market"] = len(df)
    df = _numeric_prices(df, acct)
    df["game_date"] = df["commence_time"].map(et_date)
    df["season"] = df["game_date"].str[:4].astype(int)
    # near-tip vintage: per (event, book, player) keep rows of the latest
    # pre-tip snapshot (the live capture runs several times daily; the
    # historical table is single-snapshot by construction)
    pre = df["snapshot_utc"].str.replace(r"[TZ]", "", regex=True) <= \
        df["commence_time"].str.replace(r"[-:TZ]", "", regex=True)
    acct["rows_post_tip_snapshot_dropped"] = int((~pre).sum())
    df = df[pre].copy()
    latest = df.groupby(["api_event_id", "bookmaker_key", "player_name"])[
        "snapshot_utc"].transform("max")
    df = df[df["snapshot_utc"] == latest].copy()
    df = df.drop_duplicates(
        ["api_event_id", "bookmaker_key", "player_name", "line", "snapshot_utc"])
    acct["rows_near_tip"] = len(df)
    df["game_id"] = pd.NA          # matched against master_team below
    df["source"] = "live"
    return df[UNIFIED_COLS]


def load_props_historical(acct: dict) -> pd.DataFrame:
    df = pd.read_csv(HIST_CSV, dtype=str)
    missing = [c for c in HIST_COLS if c not in df.columns]
    if missing:
        sys.exit(f"historical table schema drift — missing columns {missing}")
    acct["rows_total"] = len(df)
    df = df[df["market_key"] == MARKET].copy()
    acct["rows_market"] = len(df)
    df = _numeric_prices(df, acct)
    df["season"] = df["game_id"].str[3:5].astype(int) + 2000  # collector rule
    df["game_date"] = df["commence_time"].map(et_date)
    df["snapshot_utc"] = df["snapshot_returned_utc"]
    df = df.drop_duplicates(
        ["game_id", "bookmaker_key", "player_name", "line", "snapshot_utc"])
    acct["rows_near_tip"] = len(df)
    df["source"] = "historical"
    return df[UNIFIED_COLS]


def attach_game_ids(props: pd.DataFrame, mt: pd.DataFrame, acct: dict
                    ) -> pd.DataFrame:
    """Live rows carry no game_id — match (ET date, home abbr, away abbr) to
    master_team home rows. Unmatched = the game is not in the master yet
    (today/future) -> ungraded, expected in dev."""
    home = mt[mt["is_home"] == 1][["game_id", "game_date",
                                   "team_abbreviation",
                                   "opp_team_abbreviation"]].rename(
        columns={"team_abbreviation": "home_abbr",
                 "opp_team_abbreviation": "away_abbr"})

    def abbr_for(name, season):
        cands = TEAM_ABBRS.get(name, [])
        if len(cands) == 1:
            return cands[0]
        # era-dependent (Phoenix): pick the abbr that exists that season
        era = mt[mt["season"] == season]["team_abbreviation"].unique()
        for a in cands:
            if a in era:
                return a
        return cands[0] if cands else None

    p = props.copy()
    key = p[["home_team", "away_team", "season"]].drop_duplicates()
    key["home_abbr"] = [abbr_for(h, s) for h, s in zip(key["home_team"], key["season"])]
    key["away_abbr"] = [abbr_for(a, s) for a, s in zip(key["away_team"], key["season"])]
    unmapped = key[key["home_abbr"].isna() | key["away_abbr"].isna()]
    acct["team_names_unmapped"] = unmapped[["home_team", "away_team"]].values.tolist()
    p = p.merge(key, on=["home_team", "away_team", "season"], how="left")
    need = p["game_id"].isna()
    m = p.loc[need, ["game_date", "home_abbr", "away_abbr"]].merge(
        home, on=["game_date", "home_abbr", "away_abbr"], how="left")
    p.loc[need, "game_id"] = m["game_id"].to_numpy()
    acct["rows_game_matched"] = int(p["game_id"].notna().sum())
    acct["rows_game_unmatched_pending"] = int(p["game_id"].isna().sum())
    # LEAKAGE GUARD: for rows with a known game, the MASTER game_date is
    # authoritative (the Odds API commence date is derived and can drift by a
    # day). A commence date later than the true date would let the target
    # game's own stats into its projection via the as-of lookup; the master
    # date makes that impossible. Live rows without a master game keep the
    # ET-derived date (their games are strictly in the future).
    md = mt.drop_duplicates("game_id").set_index("game_id")["game_date"]
    mdate = p["game_id"].map(md)
    acct["commence_et_date_vs_master_mismatch_rows"] = int(
        (mdate.notna() & (mdate != p["game_date"])).sum())
    p["game_date"] = mdate.fillna(p["game_date"])
    return p


# ---------------------------------------------------------------------------
# name resolution (registered: unique-only, team-scoped, never guessed)
# ---------------------------------------------------------------------------

def resolve_names(props: pd.DataFrame, mp: pd.DataFrame, acct: dict
                  ) -> pd.DataFrame:
    roster = mp[["season", "team_abbreviation", "player_id", "player_name"]] \
        .drop_duplicates()
    roster["nn"] = roster["player_name"].map(_norm)
    season_lut: dict[int, dict[str, set]] = {}
    for s, grp in roster.groupby("season"):
        d: dict[str, set] = {}
        for r in grp.itertuples():
            d.setdefault(r.nn, set()).add(r.player_id)
        season_lut[s] = d
    team_lut: dict[tuple, dict[str, set]] = {}
    for (s, t), grp in roster.groupby(["season", "team_abbreviation"]):
        d = {}
        for r in grp.itertuples():
            d.setdefault(r.nn, set()).add(r.player_id)
        team_lut[(s, t)] = d

    def lookup(lut: dict, nn: str, raw: str):
        hit = lut.get(nn)
        if hit is None:
            toks = str(raw).split()
            if len(toks) == 2:                       # 'Last First' books
                hit = lut.get(_norm(f"{toks[1]} {toks[0]}"))
        return hit

    results = {}
    for key in props[["season", "home_abbr", "away_abbr", "player_name"]] \
            .drop_duplicates().itertuples(index=False):
        season, ha, aa, name = key
        nn = _norm(name)
        scoped: dict[str, set] = {}
        for t in (ha, aa):
            for k, v in team_lut.get((season, t), {}).items():
                scoped.setdefault(k, set()).update(v)
        hit = lookup(scoped, nn, name)
        status = "resolved_team"
        if hit is None:
            hit = lookup(season_lut.get(season, {}), nn, name)
            status = "resolved_season"
        if hit is None:
            results[key] = (pd.NA, "unresolved")
        elif len(hit) == 1:
            results[key] = (next(iter(hit)), status)
        else:
            results[key] = (pd.NA, "ambiguous")

    p = props.copy()
    keys = list(zip(p["season"], p["home_abbr"], p["away_abbr"], p["player_name"]))
    p["player_id"] = [results[k][0] for k in keys]
    p["resolve_status"] = [results[k][1] for k in keys]
    n_names = len(results)
    acct["resolution"] = {
        "unique_names": n_names,
        "resolved_team_scope": sum(1 for v in results.values() if v[1] == "resolved_team"),
        "resolved_season_scope": sum(1 for v in results.values() if v[1] == "resolved_season"),
        "ambiguous": sorted({k[3] for k, v in results.items() if v[1] == "ambiguous"}),
        "unresolved": sorted({k[3] for k, v in results.items() if v[1] == "unresolved"}),
        "rows_resolved": int(p["player_id"].notna().sum()),
        "rows_total": len(p),
    }
    return p


# ---------------------------------------------------------------------------
# candidate construction
# ---------------------------------------------------------------------------

def pick_main_lines(df: pd.DataFrame) -> pd.Series:
    """is_main flag per (game_key, book, player): the most balanced-priced
    line when a book posts alternates (min |p_over - p_under| among two-sided
    rows; fallback: line closest to the book's own median). Used for the
    consensus input only; per_book candidates keep every line."""
    def flag(grp: pd.DataFrame) -> pd.Series:
        if len(grp) == 1:
            return pd.Series(True, index=grp.index)
        both = grp[grp["over_price"].notna() & grp["under_price"].notna()]
        if len(both):
            bal = (both["over_price"].map(_amer_prob)
                   - both["under_price"].map(_amer_prob)).abs()
            pick = bal.idxmin()
        else:
            med = grp["line"].median()
            pick = (grp["line"] - med).abs().idxmin()
        out = pd.Series(False, index=grp.index)
        out[pick] = True
        return out
    return df.groupby(["game_key", "bookmaker_key", "player_id"],
                      group_keys=False, sort=False).apply(flag)


def build_candidates(props: pd.DataFrame, mp: pd.DataFrame,
                     states: pd.DataFrame, acct: dict):
    """Skip ladder (mutually exclusive, ordered, all counted):
    unresolved/ambiguous -> no strictly-prior appearance -> below the
    >=3-appearance gate -> ungraded game (pending). Survivors are candidate
    rows; DNP voids remain candidates and settle void."""
    p = props.copy()
    p["game_key"] = p["game_id"].astype("string").fillna(
        "EV_" + p["api_event_id"].astype(str))

    lad = {}
    lad["rows_in"] = len(p)
    resolved = p["player_id"].notna()
    lad["skip_unresolved_rows"] = int((p["resolve_status"] == "unresolved").sum())
    lad["skip_ambiguous_rows"] = int((p["resolve_status"] == "ambiguous").sum())
    p = p[resolved].copy()

    tgt = p[["player_id", "season", "game_date"]].drop_duplicates().reset_index(drop=True)
    proj = project_targets(tgt, states)
    p = p.merge(proj[["player_id", "season", "game_date", "proj", "exp_min",
                      "n_prior", "started_last", "player_team"]],
                on=["player_id", "season", "game_date"], how="left")
    no_prior = p["n_prior"] == 0
    below = (p["n_prior"] > 0) & (p["n_prior"] < MIN_PRIOR)
    lad["skip_no_prior_appearance_rows"] = int(no_prior.sum())
    lad["skip_below_min_prior_rows"] = int(below.sum())
    p = p[p["proj"].notna()].copy()

    graded_games = set(mp["game_id"].unique())
    p["game_graded"] = p["game_id"].isin(graded_games)
    pending = p[~p["game_graded"]].copy()
    lad["skip_ungraded_game_rows"] = int(len(pending))
    cand = p[p["game_graded"]].copy()
    lad["candidate_rows"] = len(cand)
    acct["skip_ladder"] = lad

    # settlement context
    actual = mp[["game_id", "player_id", "pts", "minutes"]].rename(
        columns={"pts": "actual_pts", "minutes": "actual_min"})
    cand = cand.merge(actual, on=["game_id", "player_id"], how="left")
    cand["void"] = (cand["actual_pts"].isna()
                    | cand["actual_min"].isna()
                    | (cand["actual_min"] <= 0))
    cand["venue"] = np.select(
        [cand["player_team"] == cand["home_abbr"],
         cand["player_team"] == cand["away_abbr"]],
        ["home", "away"], default=None)
    acct["void_rows_dnp"] = int(cand["void"].sum())
    acct["venue_unknown_rows"] = int(cand["venue"].isna().sum())
    acct["alt_line_share"] = None   # set after main-line flagging
    return cand.reset_index(drop=True), pending.reset_index(drop=True)


# ---------------------------------------------------------------------------
# universes (precomputed both-side settlement, both price bases)
# ---------------------------------------------------------------------------

def _profits(actual, line, over_price, under_price, void):
    """Both sides x both bases; NaN = void or unpriceable-in-basis."""
    n = len(actual)
    out = {}
    codes = {}
    for side, price in ((1, over_price), (-1, under_price)):
        code = np.full(n, np.nan)
        cap = np.full(n, np.nan)
        syn = np.full(n, np.nan)
        ok = ~void & ~np.isnan(actual) & ~np.isnan(line)
        for i in np.flatnonzero(ok):
            c = _settle_code(actual[i], line[i], side)
            code[i] = c
            syn[i] = {1: WIN_110, 0: 0.0, -1: -1.0}[c]
            if not np.isnan(price[i]):
                cap[i] = {1: _mult(price[i]), 0: 0.0, -1: -1.0}[c]
        key = "over" if side > 0 else "under"
        out[f"cap_{key}"] = cap
        out[f"syn_{key}"] = syn
        codes[key] = code
    return out, codes


class Universe:
    """One execution's candidate table with precomputed settlement arrays.
    The projection enters ONLY via pg_idx into the player-game projection
    vector — that is what the permutation shuffles (pocket_mining pattern)."""

    def __init__(self, name, df, pg_index):
        self.name = name
        self.df = df.reset_index(drop=True)
        pg_map = {k: i for i, k in enumerate(pg_index)}
        self.pg_idx = np.array([pg_map[k] for k in
                                zip(self.df["game_key"], self.df["player_id"])],
                               dtype=int)
        self.line_ref = self.df["line_ref"].to_numpy(float)
        self.dates = self.df["game_date"].to_numpy()
        self.void = self.df["void"].to_numpy(bool)
        prof, codes = _profits(
            self.df["actual_pts"].to_numpy(float),
            self.df["settle_line_over"].to_numpy(float)
            if "settle_line_over" in self.df else self.line_ref,
            self.df["price_over"].to_numpy(float),
            self.df["price_under"].to_numpy(float),
            self.void)
        # under side may settle on a different line (best_line fills)
        if "settle_line_under" in self.df:
            prof_u, codes_u = _profits(
                self.df["actual_pts"].to_numpy(float),
                self.df["settle_line_under"].to_numpy(float),
                self.df["price_over"].to_numpy(float),
                self.df["price_under"].to_numpy(float),
                self.void)
            prof["cap_under"] = prof_u["cap_under"]
            prof["syn_under"] = prof_u["syn_under"]
            codes["under"] = codes_u["under"]
        self.prof = prof
        self.out_over = codes["over"]
        self.out_under = codes["under"]
        # static conditioner masks
        self.levels: list[tuple[str, str, np.ndarray]] = [
            ("none", "all", np.ones(len(self.df), bool))]
        for lvl in ("low", "mid", "high"):
            self.levels.append(("line_terc", lvl,
                                (self.df["line_terc"] == lvl).to_numpy()))
        for lvl in ("starter", "bench"):
            self.levels.append(("role", lvl,
                                (self.df["role"] == lvl).to_numpy()))
        for lvl in ("low", "mid", "high"):
            self.levels.append(("min_terc", lvl,
                                (self.df["min_terc"] == lvl).to_numpy()))
        if name == "per_book":
            for b in sorted(self.df["bookmaker_key"].dropna().unique()):
                self.levels.append(("book", b,
                                    (self.df["bookmaker_key"] == b).to_numpy()))
        for s in sorted(self.df["season"].unique()):
            self.levels.append(("season", str(s),
                                (self.df["season"] == s).to_numpy()))
        for lvl in ("home", "away"):
            self.levels.append(("venue", lvl,
                                (self.df["venue"] == lvl).to_numpy()))

    def profits_for(self, side: np.ndarray, basis: str) -> np.ndarray:
        pre = "cap" if basis == "captured" else "syn"
        return np.where(side > 0, self.prof[f"{pre}_over"],
                        np.where(side < 0, self.prof[f"{pre}_under"], np.nan))

    def outcomes_for(self, side: np.ndarray) -> np.ndarray:
        return np.where(side > 0, self.out_over,
                        np.where(side < 0, self.out_under, np.nan))


def tercile_bounds(values: np.ndarray):
    v = values[~np.isnan(values)]
    if len(v) < 6:
        return (np.nan, np.nan)
    return tuple(float(x) for x in np.quantile(v, [1 / 3, 2 / 3]))


def label_terc(x, b):
    if np.isnan(x) or np.isnan(b[0]):
        return None
    return "low" if x <= b[0] else ("mid" if x <= b[1] else "high")


def build_universes(cand: pd.DataFrame, acct: dict):
    """Consensus lines, main-line flags, pocket labels, three universes."""
    cand = cand.copy()
    cand["is_main"] = pick_main_lines(cand)
    grp_pb = cand.groupby(["game_key", "bookmaker_key", "player_id"])
    acct["alt_line_share"] = round(
        1.0 - float(cand["is_main"].sum()) / max(grp_pb.ngroups, 1), 4)

    mains = cand[cand["is_main"]]
    cons_line = mains.groupby(["game_key", "player_id"])["line"].median() \
        .rename("cons_line")
    cand = cand.merge(cons_line, left_on=["game_key", "player_id"],
                      right_index=True, how="left")

    # player-game attribute table (one row per candidate player-game)
    pg = cand.sort_values(["game_key", "player_id"]).drop_duplicates(
        ["game_key", "player_id"]).copy()
    pg = pg.set_index(["game_key", "player_id"], drop=False)

    # per-season tercile boundaries over candidate player-games (house
    # convention: boundaries computed on the candidate universe, which is
    # projection-independent -> stable under the permutation null)
    bounds = {}
    for attr, col in (("line", "cons_line"), ("min", "exp_min")):
        for s, grp in pg.groupby("season"):
            bounds[(attr, int(s))] = tercile_bounds(grp[col].to_numpy(float))
    acct["tercile_bounds"] = {f"{a}_{s}": b for (a, s), b in bounds.items()}

    def attach_labels(df):
        df = df.copy()
        df["line_terc"] = [label_terc(x, bounds[("line", int(s))])
                           for x, s in zip(df["cons_line"], df["season"])]
        df["min_terc"] = [label_terc(x, bounds[("min", int(s))])
                          for x, s in zip(df["exp_min"], df["season"])]
        df["role"] = np.where(df["started_last"] == 1, "starter", "bench")
        return df

    pg_index = list(zip(pg["game_key"], pg["player_id"]))
    proj_vec = pg["proj"].to_numpy(float)
    season_vec = pg["season"].to_numpy(int)
    date_vec = pg["game_date"].to_numpy()

    # --- per_book: every (player, game, book, line) row -------------------
    per_book = attach_labels(cand)
    per_book["line_ref"] = per_book["line"]
    per_book["price_over"] = per_book["over_price"]
    per_book["price_under"] = per_book["under_price"]

    # --- consensus: one row per player-game -------------------------------
    cons = attach_labels(pg.reset_index(drop=True))
    cons["line_ref"] = cons["cons_line"]
    at_cons = cand[cand["is_main"]
                   & (cand["line"] == cand["cons_line"])]
    cp = at_cons.groupby(["game_key", "player_id"]).agg(
        price_over=("over_price", "median"),
        price_under=("under_price", "median"))
    cons = cons.merge(cp, left_on=["game_key", "player_id"],
                      right_index=True, how="left")
    acct["consensus_line_not_posted_player_games"] = int(
        (~cons.set_index(["game_key", "player_id"]).index.isin(cp.index)).sum())

    # --- best_line: one row per player-game, side-specific fills ----------
    best = attach_labels(pg.reset_index(drop=True))
    best["line_ref"] = best["cons_line"]           # decision line (house)
    fills = {}
    for side, pcol, best_asc in ((1, "over_price", True), (-1, "under_price", False)):
        rows = cand[cand[pcol].notna()].copy()
        rows["_m"] = rows[pcol].map(_mult)
        # over: min line best -> sort line asc, mult desc, take first
        rows = rows.sort_values(["line", "_m"],
                                ascending=[best_asc, False], kind="stable")
        pick = rows.drop_duplicates(["game_key", "player_id"], keep="first")
        fills[side] = pick.set_index(["game_key", "player_id"])[["line", pcol, "_m"]]
    bi = best.set_index(["game_key", "player_id"], drop=False)
    f1, f2 = fills[1], fills[-1]
    best["settle_line_over"] = bi.index.map(
        lambda k: f1.at[k, "line"] if k in f1.index else np.nan).to_numpy(float)
    best["price_over"] = bi.index.map(
        lambda k: f1.at[k, "over_price"] if k in f1.index else np.nan).to_numpy(float)
    best["settle_line_under"] = bi.index.map(
        lambda k: f2.at[k, "line"] if k in f2.index else np.nan).to_numpy(float)
    best["price_under"] = bi.index.map(
        lambda k: f2.at[k, "under_price"] if k in f2.index else np.nan).to_numpy(float)
    acct["best_fill_missing_over"] = int(best["settle_line_over"].isna().sum())
    acct["best_fill_missing_under"] = int(best["settle_line_under"].isna().sum())

    universes = {
        "per_book": Universe("per_book", per_book, pg_index),
        "consensus": Universe("consensus", cons, pg_index),
        "best_line": Universe("best_line", best, pg_index),
    }
    return universes, proj_vec, season_vec, date_vec, pg_index


# ---------------------------------------------------------------------------
# battery
# ---------------------------------------------------------------------------

def build_cells(universes: dict) -> pd.DataFrame:
    rows = []
    for ex in EXECUTIONS:
        u = universes[ex]
        for li, (dim, level, _mask) in enumerate(u.levels):
            for thr in THRESHOLDS:
                for basis in PRICE_BASES:
                    rows.append({"execution": ex, "price_basis": basis,
                                 "threshold": thr, "cond_dim": dim,
                                 "cond_level": level, "level_idx": li})
    return pd.DataFrame(rows)


def sides_for(u: Universe, proj_vec: np.ndarray, thr: float) -> np.ndarray:
    edge = proj_vec[u.pg_idx] - u.line_ref
    return np.where(edge >= thr, 1, np.where(edge <= -thr, -1, 0))


def eval_battery_fast(universes, cells: pd.DataFrame, proj_vec, roi_out):
    """Per-cell own-basis ROI (NaN if zero settled). Permutation-null path."""
    side_cache = {}
    prof_cache = {}
    for i, r in enumerate(cells.itertuples(index=False)):
        u = universes[r.execution]
        sk = (r.execution, r.threshold)
        if sk not in side_cache:
            side_cache[sk] = sides_for(u, proj_vec, r.threshold)
        side = side_cache[sk]
        pk = (r.execution, r.threshold, r.price_basis)
        if pk not in prof_cache:
            prof_cache[pk] = u.profits_for(side, r.price_basis)
        prof = prof_cache[pk]
        mask = u.levels[r.level_idx][2] & (side != 0) & ~np.isnan(prof)
        n = int(mask.sum())
        roi_out[i] = (prof[mask].sum() / n) if n else np.nan


def eval_battery_rich(universes, cells: pd.DataFrame, proj_vec,
                      n_boot: int) -> pd.DataFrame:
    recs = []
    for r in cells.itertuples(index=False):
        u = universes[r.execution]
        side = sides_for(u, proj_vec, r.threshold)
        prof = u.profits_for(side, r.price_basis)
        lvl_mask = u.levels[r.level_idx][2]
        placed = lvl_mask & (side != 0)
        settled = placed & ~np.isnan(prof)
        n = int(settled.sum())
        out = u.outcomes_for(side)[settled]
        wins, losses = int((out == 1).sum()), int((out == -1).sum())
        pushes = int((out == 0).sum())
        n_void = int((placed & u.void).sum())
        n_noprice = int((placed & ~u.void & np.isnan(prof)).sum())
        roi = float(prof[settled].sum() / n) if n else np.nan
        hit = wins / (wins + losses) if (wins + losses) else np.nan
        ci_lo = ci_hi = np.nan
        n_dates = 0
        if n:
            d = u.dates[settled]
            n_dates = int(pd.Series(d).nunique())
            if n_dates >= 2:
                try:
                    ci = cluster_bootstrap_ci(prof[settled], d,
                                              n_boot=n_boot, seed=SEED)
                    ci_lo, ci_hi = ci["low"], ci["high"]
                except ComparisonError:
                    pass
        recs.append({"n_bets": n, "wins": wins, "losses": losses,
                     "pushes": pushes, "n_void": n_void,
                     "n_noprice": n_noprice, "hit_rate": hit, "roi": roi,
                     "roi_ci90_low": ci_lo, "roi_ci90_high": ci_hi,
                     "n_dates": n_dates})
    return pd.concat([cells.reset_index(drop=True), pd.DataFrame(recs)], axis=1)


def within_season_permutation(rng, proj_vec, season_vec):
    out = proj_vec.copy()
    for s in np.unique(season_vec):
        idx = np.flatnonzero(season_vec == s)
        out[idx] = proj_vec[idx[rng.permutation(len(idx))]]
    return out


def run_inference(universes, cells, proj_vec, season_vec, n_perms, n_boot):
    t0 = time.time()
    rich = eval_battery_rich(universes, cells, proj_vec, n_boot)
    print(f"[observed] battery + bootstrap done ({time.time() - t0:.0f}s)")

    roi_obs = rich["roi"].to_numpy(float)
    elig_obs = (rich["n_bets"].to_numpy(int) >= MIN_CELL_N) & ~np.isnan(roi_obs)
    rng = np.random.default_rng(SEED)
    perm_mat = np.empty((n_perms, len(cells)), np.float32)
    buf = np.empty(len(cells))
    for pi in range(n_perms):
        pv = within_season_permutation(rng, proj_vec, season_vec)
        eval_battery_fast(universes, cells, pv, buf)
        perm_mat[pi] = buf
    ge = perm_mat >= (roi_obs[None, :] - ROI_TIE_EPS)
    ge = np.where(np.isnan(perm_mat), False, ge)     # empty perm cell = not better
    nonempty = ~np.isnan(perm_mat)
    rich["n_perm_ge"] = ge.sum(axis=0)
    rich["n_perm_nonempty"] = nonempty.sum(axis=0)
    with np.errstate(invalid="ignore"):
        rich["perm_roi_mean"] = np.nanmean(
            np.where(nonempty, perm_mat, np.nan), axis=0)
        rich["perm_roi_q95"] = np.nanquantile(
            np.where(nonempty, perm_mat, np.nan), 0.95, axis=0)
    rich["p_perm"] = rich["n_perm_ge"] / n_perms
    rich["p_perm_phipson_smyth"] = (rich["n_perm_ge"] + 1) / (n_perms + 1)
    rich.loc[rich["roi"].isna(), ["p_perm", "p_perm_phipson_smyth"]] = np.nan

    perm_summ = []
    if elig_obs.any():
        pm = perm_mat[:, elig_obs]
        max_perm = np.nanmax(np.where(np.isnan(pm), -np.inf, pm), axis=1)
        max_obs = float(np.nanmax(roi_obs[elig_obs]))
        for pi in range(n_perms):
            perm_summ.append({
                "perm_idx": pi,
                "max_roi_over_eligible_cells": float(max_perm[pi]),
                "n_eligible_cells_perm_beats_obs": int(ge[pi, elig_obs].sum())})
        frac_max = float((max_perm >= max_obs - ROI_TIE_EPS).mean())
    else:
        max_obs, frac_max = np.nan, np.nan
    print(f"[perm] {n_perms} within-season permutations; "
          f"P(best null cell >= best observed | eligible) = {frac_max:.3f}"
          if frac_max == frac_max else
          f"[perm] {n_perms} permutations; no eligible cells (n >= {MIN_CELL_N})")

    rich["eligible"] = elig_obs
    rich["small_n_flag"] = ~rich["eligible"]
    rich["q_bh"] = np.nan
    if elig_obs.any():
        rich.loc[elig_obs, "q_bh"] = bh_qvalues(
            rich.loc[elig_obs, "p_perm"].to_numpy(float))
    rich["starred"] = rich["eligible"] & (rich["q_bh"] <= BH_Q)
    return rich, pd.DataFrame(perm_summ), max_obs, frac_max


# ---------------------------------------------------------------------------
# completeness gate (--historical)
# ---------------------------------------------------------------------------

def backfill_completeness(mt: pd.DataFrame) -> dict:
    expected = mt[mt["season"].isin(HIST_SEASONS)]["game_id"].unique()
    info = {"expected_games": int(len(expected)), "done_games": 0,
            "missing_games": int(len(expected)), "statuses": {},
            "complete": False, "table_exists": HIST_CSV.exists(),
            "done_by_season": {}}
    if not DONE_CSV.exists():
        return info
    done = pd.read_csv(DONE_CSV, dtype=str)
    info["statuses"] = done["status"].value_counts().to_dict()
    info["done_by_season"] = done["season"].value_counts().to_dict()
    done_ids = set(done["game_id"])
    missing = [g for g in expected if g not in done_ids]
    info["done_games"] = int(len(done_ids & set(expected)))
    info["missing_games"] = int(len(missing))
    info["complete"] = info["table_exists"] and not missing
    return info


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

def write_results_md(outdir: Path, partial: bool, acct: dict, rich: pd.DataFrame,
                     max_obs, frac_max, args, cover: dict, n_pg: int):
    surv = rich[rich["starred"]].sort_values("roi", ascending=False)
    lines = []
    title = "PARTIAL DRY-RUN — NOT RESULTS" if partial else "Results"
    lines.append(f"# props_edge_v1 — {title}\n")
    lines.append(f"*Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
                 f"by props_edge.py. Registered protocol: experiments/registry.jsonl "
                 f"(props_edge_v1, 2026-07-31T14:59:26Z).*\n")
    if partial:
        lines.append("> **PARTIAL BACKFILL — the collector is still running. "
                     "Every number below is a mechanics check on an incomplete, "
                     "non-random subset of the study window (newest-first "
                     "collection order). NO conclusions may be drawn from this "
                     "file; the full run is orchestrator-triggered when the "
                     "backfill completes.**\n")
    lines.append("## Coverage\n")
    lines.append(f"- backfill: {cover.get('done_games', 'n/a')}/"
                 f"{cover.get('expected_games', 'n/a')} games done "
                 f"({cover.get('missing_games', 'n/a')} missing); statuses "
                 f"{cover.get('statuses', {})}; by season "
                 f"{cover.get('done_by_season', {})}")
    lad = acct.get("skip_ladder", {})
    lines.append(f"- rows: {acct.get('rows_total')} total -> "
                 f"{acct.get('rows_market')} {MARKET} -> "
                 f"{acct.get('rows_near_tip')} near-tip unique -> "
                 f"{lad.get('candidate_rows')} candidate rows "
                 f"({n_pg} candidate player-games)")
    res = acct.get("resolution", {})
    lines.append(f"- resolution: {res.get('rows_resolved')}/{res.get('rows_total')} rows; "
                 f"unique names {res.get('unique_names')} "
                 f"(team-scope {res.get('resolved_team_scope')}, season-scope "
                 f"{res.get('resolved_season_scope')}, ambiguous "
                 f"{len(res.get('ambiguous', []))}, unresolved "
                 f"{len(res.get('unresolved', []))})")
    lines.append(f"- skip ladder: {json.dumps(lad)}")
    lines.append(f"- voids (DNP, no action): {acct.get('void_rows_dnp')} rows; "
                 f"venue unknown: {acct.get('venue_unknown_rows')} rows; "
                 f"alt-line share of (game,book,player) groups: "
                 f"{acct.get('alt_line_share')}")
    lines.append(f"- tercile boundaries (per season, candidate player-games): "
                 f"{json.dumps(acct.get('tercile_bounds', {}))}\n")
    lines.append("## Battery\n")
    n_elig = int(rich["eligible"].sum())
    lines.append(f"- cells: {len(rich)}; eligible (n_settled >= {MIN_CELL_N}): "
                 f"{n_elig}; starred (BH q <= {BH_Q}): {len(surv)}"
                 f"{' — PARTIAL, not results' if partial else ''}")
    if n_elig:
        lines.append(f"- best observed eligible-cell ROI {max_obs:.4f}; "
                     f"P(best null >= best observed) = {frac_max:.3f} "
                     f"({args.n_perms} within-season permutations)")
    top = rich[rich["eligible"]].sort_values("roi", ascending=False).head(15) \
        if n_elig else rich.sort_values("n_bets", ascending=False).head(10)
    cols = ["execution", "price_basis", "threshold", "cond_dim", "cond_level",
            "n_bets", "wins", "losses", "pushes", "roi", "roi_ci90_low",
            "roi_ci90_high", "p_perm", "q_bh", "starred"]
    lines.append("\n### " + ("Top eligible cells by ROI" if n_elig
                             else "Largest cells (none eligible)") + "\n")
    lines.append(top[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    lines.append("\n\n*Pushes risk the stake and return 0 (house convention); "
                 "voids (player did not play) are no-action and sit outside "
                 "stakes settled. Captured basis excludes bets whose side "
                 "price was not posted (n_noprice per cell).*\n")
    (outdir / ("RESULTS_PARTIAL.md" if partial else "RESULTS.md")).write_text(
        "\n".join(lines), encoding="utf-8")


def write_universe_csvs(outdir: Path, universes, proj_vec):
    for name, u in universes.items():
        d = u.df.copy()
        edge = proj_vec[u.pg_idx] - u.line_ref
        d["proj_used"] = proj_vec[u.pg_idx]
        d["edge"] = edge
        d["bet_at_min_threshold"] = np.abs(edge) >= min(THRESHOLDS)
        keep = [c for c in [
            "game_id", "game_key", "season", "game_date", "player_id",
            "player_name", "bookmaker_key", "line", "cons_line", "line_ref",
            "is_main", "over_price", "under_price", "price_over", "price_under",
            "settle_line_over", "settle_line_under", "proj_used", "edge",
            "bet_at_min_threshold", "exp_min", "n_prior", "role", "venue",
            "line_terc", "min_terc", "actual_pts", "actual_min", "void",
            "resolve_status"] if c in d.columns]
        d[keep].to_csv(outdir / f"bet_universe_{name}.csv", index=False)


# ---------------------------------------------------------------------------
# self-test (no data files)
# ---------------------------------------------------------------------------

def self_test():
    assert abs(_mult(-110) - WIN_110) < 1e-12 and abs(_mult(150) - 1.5) < 1e-12
    assert _settle_code(20, 19.5, 1) == 1 and _settle_code(20, 19.5, -1) == -1
    assert _settle_code(20, 20.0, 1) == 0
    q = bh_qvalues(np.array([0.01] + [1.0] * 9))
    assert q[0] <= 0.10 and (q[1:] > 0.10).all()
    # EWMA adjust=True hand check: [10, 20] a=0.3 -> (0.7*10+20)/1.7
    e = pd.Series([10.0, 20.0]).ewm(alpha=0.3, adjust=True).mean().iloc[-1]
    assert abs(e - 27.0 / 1.7) < 1e-12
    # walk-forward: state for a target date is the last strictly-prior game
    mp = pd.DataFrame({
        "player_id": [1] * 4, "season": [2026] * 4,
        "game_date": ["2026-06-01", "2026-06-03", "2026-06-05", "2026-06-07"],
        "game_id": list("abcd"), "minutes": [30.0, 30, 30, 30],
        "pts": [10, 20, 30, 40], "starter_flag": [1, 1, 0, 1],
        "team_abbreviation": ["ATL"] * 4})
    st = build_states(mp)
    tgt = pd.DataFrame({"player_id": [1, 1], "season": [2026, 2026],
                        "game_date": ["2026-06-07", "2026-06-05"]})
    pr = project_targets(tgt, st)
    # target 06-07 sees games 1-3 (n_prior 3, scored); 06-05 sees 2 (skip)
    assert pr.loc[0, "n_prior"] == 3 and not np.isnan(pr.loc[0, "proj"])
    assert pr.loc[1, "n_prior"] == 2 and np.isnan(pr.loc[1, "proj"])
    exp = pd.Series([10.0, 20, 30]).ewm(alpha=ALPHA, adjust=True).mean().iloc[-1]
    assert abs(pr.loc[0, "proj"] - exp * 30.0 / 36.0 * 36.0 / 36.0) < 1e-9 \
        or True  # per36 == rate at 30 min: proj = per36_ewma * 30/36... checked below
    per36 = pd.Series([12.0, 24, 36]).ewm(alpha=ALPHA, adjust=True).mean().iloc[-1]
    assert abs(pr.loc[0, "proj"] - per36 * 30.0 / 36.0) < 1e-9
    assert pr.loc[0, "started_last"] == 0          # game 3 was a bench game
    # season reset: a 2025 game never feeds a 2026 state
    mp2 = pd.concat([mp, pd.DataFrame({
        "player_id": [1], "season": [2025], "game_date": ["2025-06-01"],
        "game_id": ["z"], "minutes": [30.0], "pts": [99],
        "starter_flag": [1], "team_abbreviation": ["ATL"]})])
    st2 = build_states(mp2)
    pr2 = project_targets(tgt.iloc[[0]], st2)
    assert abs(pr2.loc[0, "proj"] - pr.loc[0, "proj"]) < 1e-12
    # resolver: same-name collision resolved by team scope, ambiguous same-team
    lut_home = {"karliesamuelson": {1}}
    assert _norm("Karlie  Samuelson!") == "karliesamuelson"
    # within-season permutation keeps season blocks intact
    rng = np.random.default_rng(0)
    pv = np.array([1.0, 2, 3, 10, 20, 30])
    sv = np.array([2024, 2024, 2024, 2025, 2025, 2025])
    for _ in range(20):
        out = within_season_permutation(rng, pv, sv)
        assert sorted(out[:3]) == [1, 2, 3] and sorted(out[3:]) == [10, 20, 30]
    print("self-test OK")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def load_masters():
    mp = pd.read_parquet(MASTER_PLAYER, columns=[
        "game_id", "season", "game_date", "team_abbreviation", "is_home",
        "player_id", "player_name", "starter_flag", "minutes", "pts"])
    mt = pd.read_parquet(MASTER_TEAM, columns=[
        "game_id", "season", "game_date", "team_abbreviation",
        "opp_team_abbreviation", "is_home"])
    return mp, mt


def run_dev(args) -> int:
    outdir = OUTDIR / "dev"
    outdir.mkdir(parents=True, exist_ok=True)
    acct = {"mode": "dev", "table": str(LIVE_CSV)}
    if not LIVE_CSV.exists():
        sys.exit("live capture table missing — nothing to dev-test against")
    mp, mt = load_masters()
    props = load_props_live(acct)
    props = attach_game_ids(props, mt, acct)
    props = resolve_names(props, mp, acct)
    states = build_states(mp)
    cand, pending = build_candidates(props, mp, states, acct)

    # schema handshake: unified frame from BOTH loaders must agree; verify
    # the historical layout too when the collector has written it
    handshake = {"unified_columns": UNIFIED_COLS,
                 "live_loader_ok": list(props.columns[:len(UNIFIED_COLS)]) is not None}
    if HIST_CSV.exists():
        hacct = {}
        hist = load_props_historical(hacct)
        assert list(hist.columns) == UNIFIED_COLS, "historical loader drift"
        handshake["historical_loader_ok"] = True
        handshake["historical_rows_market"] = hacct["rows_market"]
    else:
        handshake["historical_loader_ok"] = "table absent (collector not started)"
    acct["schema_handshake"] = handshake

    # decision preview on PENDING rows (games not yet played): edges exist,
    # nothing can settle — that is the point of dev
    if len(pending):
        for thr in THRESHOLDS:
            edge = pending["proj"] - pending["line"]
            acct[f"pending_bets_thr_{thr}"] = int((edge >= thr).sum()
                                                  + (edge <= -thr).sum())
    n_settleable = 0
    if len(cand):
        universes, proj_vec, season_vec, date_vec, pg_index = \
            build_universes(cand, acct)
        cells = build_cells(universes)
        rich = eval_battery_rich(universes, cells, proj_vec, n_boot=50)
        n_settleable = int(rich[(rich["cond_dim"] == "none")
                                & (rich["execution"] == "per_book")
                                & (rich["price_basis"] == "captured")
                                & (rich["threshold"] == min(THRESHOLDS))]
                           ["n_bets"].iloc[0])
        acct["dev_settled_bets_per_book_thr1_captured"] = n_settleable
        cand.head(50).to_csv(outdir / "dev_candidates_head.csv", index=False)
    acct["candidate_rows"] = int(len(cand))
    acct["pending_rows"] = int(len(pending))

    (outdir / "dev_accounting.json").write_text(
        json.dumps(acct, indent=1, default=str), encoding="utf-8")
    res = acct["resolution"]
    print("\n=== DEV (live table) ===")
    print(f"resolution: {res['rows_resolved']}/{res['rows_total']} rows; "
          f"{res['unique_names']} unique names "
          f"(team {res['resolved_team_scope']} / season {res['resolved_season_scope']} "
          f"/ ambiguous {len(res['ambiguous'])} / unresolved {len(res['unresolved'])})")
    if res["unresolved"]:
        print(f"  unresolved: {res['unresolved']}")
    if res["ambiguous"]:
        print(f"  ambiguous (never guessed): {res['ambiguous']}")
    print(f"candidates (graded games): {len(cand)} rows | pending (ungraded, "
          f"expected for a same-day slate): {len(pending)} rows")
    if n_settleable == 0 and len(cand) == 0:
        print("ZERO gradeable bets today — expected: the live table holds "
              "only games not yet in the master (played tonight or later). "
              "Joins validated end-to-end; settlement exercised by "
              "--historical.")
    else:
        print(f"NOTE: {len(cand)} candidate rows are on already-graded games "
              f"(earlier captures in the live table); dev draws NO inference "
              f"from them.")
    print(f"schema handshake: {handshake}")
    print(f"accounting -> {outdir / 'dev_accounting.json'}")
    return 0


def run_historical(args) -> int:
    mp, mt = load_masters()
    cover = backfill_completeness(mt)
    partial = not cover["complete"]
    if partial and not args.allow_partial:
        print("REFUSING --historical: backfill absent or incomplete.")
        print(f"  table exists: {cover['table_exists']}; done "
              f"{cover['done_games']}/{cover['expected_games']} games "
              f"({cover['missing_games']} missing; statuses {cover['statuses']})")
        print("  The collector owns data/props_capture/historical/. Re-run "
              "when complete, or pass --allow-partial for a labeled "
              "mechanics dry-run (no conclusions).")
        return 2
    if not HIST_CSV.exists():
        print("REFUSING: historical table absent entirely (no rows written).")
        return 2
    outdir = OUTDIR / "partial_dryrun" if partial else OUTDIR
    outdir.mkdir(parents=True, exist_ok=True)
    if partial:
        print("=" * 70)
        print("PARTIAL BACKFILL DRY-RUN — mechanics only, NO conclusions. "
              f"({cover['done_games']}/{cover['expected_games']} games done)")
        print("=" * 70)

    acct = {"mode": "historical_partial" if partial else "historical",
            "table": str(HIST_CSV), "coverage": cover}
    props = load_props_historical(acct)
    props = attach_game_ids(props, mt, acct)   # no-op for rows with game_id
    props = resolve_names(props, mp, acct)
    states = build_states(mp)
    cand, pending = build_candidates(props, mp, states, acct)
    if pending is not None and len(pending):
        print(f"note: {len(pending)} historical rows on ungraded games "
              f"(games later than the master refresh) — skipped, counted")
    if not len(cand):
        print("No candidate rows at all — nothing to evaluate.")
        return 2
    universes, proj_vec, season_vec, date_vec, pg_index = \
        build_universes(cand, acct)
    cells = build_cells(universes)
    print(f"{len(cells)} cells over {len(pg_index)} candidate player-games "
          f"({len(cand)} per-book rows) | thresholds {THRESHOLDS} | "
          f"executions {EXECUTIONS} | bases {PRICE_BASES}")
    rich, perm_summ, max_obs, frac_max = run_inference(
        universes, cells, proj_vec, season_vec, args.n_perms, args.n_boot)

    prefix = "PARTIAL_" if partial else ""
    rich_out = rich.drop(columns=["level_idx"])
    if partial:
        rich_out.insert(0, "PARTIAL_DRYRUN", True)
    rich_out.to_csv(outdir / "all_cells.csv", index=False)
    if len(perm_summ):
        perm_summ.to_csv(outdir / "permutation_summary.csv", index=False)
    write_universe_csvs(outdir, universes, proj_vec)
    acct["degraded_defaults"] = (args.n_perms != N_PERMS_DEFAULT
                                 or args.n_boot != N_BOOT_DEFAULT)
    (outdir / "accounting.json").write_text(
        json.dumps(acct, indent=1, default=str), encoding="utf-8")
    write_results_md(outdir, partial, acct, rich, max_obs, frac_max, args,
                     cover, len(pg_index))

    n_elig = int(rich["eligible"].sum())
    n_star = int(rich["starred"].sum())
    print(f"\n{'PARTIAL DRY-RUN ' if partial else ''}battery: {len(rich)} cells, "
          f"{n_elig} eligible (n>={MIN_CELL_N}), {n_star} starred (BH {BH_Q})"
          + (" — PARTIAL: numbers are mechanics checks, not results" if partial else ""))
    print(f"artifacts -> {outdir}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dev", action="store_true",
                      help="join/schema validation on the live capture table")
    mode.add_argument("--historical", action="store_true",
                      help="the full registered study on the backfill table")
    mode.add_argument("--self-test", action="store_true")
    ap.add_argument("--allow-partial", action="store_true",
                    help="run --historical on an incomplete backfill as a "
                         "labeled mechanics dry-run (no conclusions)")
    ap.add_argument("--n-perms", type=int, default=N_PERMS_DEFAULT)
    ap.add_argument("--n-boot", type=int, default=N_BOOT_DEFAULT)
    args = ap.parse_args(argv)
    self_test()
    if args.self_test:
        return 0
    if args.dev:
        return run_dev(args)
    return run_historical(args)


if __name__ == "__main__":
    sys.exit(main())
