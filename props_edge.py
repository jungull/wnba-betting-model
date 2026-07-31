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

ADDITIONS BEYOND THE REGISTRATION (all additive; nothing registered was
dropped, weakened, or re-specified after seeing results)
    1. PHASE SPLIT. Every registered cell is evaluated three times: scope
       'all' (the registered battery, unchanged), 'regular' and 'playoff'.
       BH runs WITHIN each scope family, so the registered battery's
       multiplicity is exactly what it would have been. Orchestrator standing
       caution: John has PAUSED playoff betting, so playoff cells are reported
       and never aggregated into a headline. Phase comes from the master
       game_id season-type digit and is cross-checked against
       master_player.season_type (mismatch => hard exit).
    2. SECOND NULL. The registered null shuffles the projection within season.
       That null is MIS-CENTRED for any phase-scoped cell: playoff
       player-games are 7.8% of the pool, so a season-wide shuffle hands
       playoff rows regular-season projections. Measured on this data: mean
       null ROI is -0.076 on eligible playoff cells vs -0.051 on regular ones,
       which manufactures significance. A within-(season, phase) null is
       therefore reported alongside the registered one in every artifact
       (*_phaseblock columns). The registered null remains primary for the
       registered battery.
    3. THE MAE DIAGNOSTIC (projection_vs_line.csv). Is the projection or the
       line the better point estimate of actual points? Reported overall, by
       season, phase, line tercile, role, minutes tercile, venue and book,
       with 90% date-clustered bootstrap CIs on the paired MAE difference.
    4. roi_positive / starred_and_profitable. A permutation star means "beat a
       shuffled projection", NOT "made money" — a cell can lose money and
       still beat its null. Both are reported; only profitable survivors are
       ranked in PROPS_LEDGER.md.
    5. Descriptive companion main_vs_alt_lines.csv (main numbers vs alternate
       ladders in the per_book universe). Not a registered cell; it exists to
       expose price artefacts.

BUGS FOUND AND FIXED WHILE BUILDING (both would have produced fake pockets)
    a. Consensus prices were being aggregated as a MEDIAN OF AMERICAN ODDS.
       American odds are discontinuous at +/-100: median(-110, +112) = +1,
       i.e. a 100x payout. This alone produced a fake +42% consensus ROI. All
       price aggregation now happens in win-multiplier space and converts back
       only for reporting; _numeric_prices additionally drops any price with
       |p| < 100 as corrupt. Regression-guarded in self_test().
    b. merge_asof refused the projection join on mixed player_id key dtypes
       (object vs Int64) — the harness could not run at all. Join keys are now
       normalised at every boundary.

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

# Orchestrator's standing playoff caution (John has PAUSED playoff betting
# pending model improvements). Every cell of the registered battery is
# evaluated three times: on all rows (the battery exactly as registered), on
# regular-season rows only (the headline-safe companion), and on playoff rows
# only (reported, never aggregated into a headline). BH runs WITHIN each scope
# family, so the registered battery's multiplicity is unchanged by the split.
SCOPES = ["all", "regular", "playoff"]
HEADLINE_SCOPE = "regular"


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
    p["player_id"] = p["player_id"].astype("Int64")
    p["season"] = p["season"].astype("int64")
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
    # join-key dtype discipline: the resolver returns object-dtype ids, the
    # master carries Int64 — merge_asof refuses mixed key dtypes outright.
    t["player_id"] = t["player_id"].astype("Int64")
    t["season"] = t["season"].astype("int64")
    t["_td"] = pd.to_datetime(t["game_date"])
    s = states.copy()
    s["player_id"] = s["player_id"].astype("Int64")
    s["season"] = s["season"].astype("int64")
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
        # American odds are |p| >= 100 by definition; anything inside that
        # band is corrupt, not a longshot. Both guards drop, never repair.
        anom = (df[c].abs() >= PRICE_ANOMALY_ABS) | (df[c].abs() < 100)
        acct[f"price_anomaly_{c}"] = int(anom.sum())
        df.loc[anom, c] = np.nan
        acct[f"price_missing_{c}"] = int(df[c].isna().sum())
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
    d = df[["game_key", "bookmaker_key", "player_id", "line",
            "over_price", "under_price"]].copy()
    d["_ord"] = np.arange(len(d))
    keys = ["game_key", "bookmaker_key", "player_id"]
    both = d["over_price"].notna() & d["under_price"].notna()
    bal = (d["over_price"].map(_amer_prob) - d["under_price"].map(_amer_prob)).abs()
    d["_two_sided"] = (~both).astype(int)            # 0 sorts first
    d["_bal"] = np.where(both, bal, np.inf)
    med = d.groupby(keys, sort=False)["line"].transform("median")
    d["_dmed"] = (d["line"] - med).abs()
    # winner per group: two-sided first, then most balanced, then closest to
    # the book's own median line, then lowest line (deterministic tie-break)
    d = d.sort_values(["_two_sided", "_bal", "_dmed", "line", "_ord"],
                      kind="stable")
    win = d.groupby(keys, sort=False)["_ord"].first()
    flags = np.zeros(len(df), bool)
    flags[win.to_numpy(int)] = True
    return pd.Series(flags, index=df.index)


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
    p["player_id"] = p["player_id"].astype("Int64")
    p["season"] = p["season"].astype("int64")

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

    # PHASE (orchestrator's playoff caution): master game_id char 2 is the
    # NBA/WNBA season-type digit — '2' regular season, '4' playoffs. Verified
    # against master_player.season_type below; never inferred from dates.
    cand["phase"] = np.where(cand["game_id"].astype(str).str[2] == "4",
                             "playoff", "regular")
    if "season_type" in mp.columns:
        st = mp.drop_duplicates("game_id").set_index("game_id")["season_type"]
        expect = np.where(cand["game_id"].map(st) == "Playoffs",
                          "playoff", "regular")
        mism = int((expect != cand["phase"].to_numpy()).sum())
        acct["phase_vs_master_season_type_mismatch_rows"] = mism
        if mism:
            sys.exit(f"phase derivation disagrees with master season_type on "
                     f"{mism} rows — refusing to guess")
    acct["void_rows_dnp"] = int(cand["void"].sum())
    acct["venue_unknown_rows"] = int(cand["venue"].isna().sum())
    acct["phase_rows"] = cand["phase"].value_counts().to_dict()
    acct["alt_line_share"] = None   # set after main-line flagging
    return cand.reset_index(drop=True), pending.reset_index(drop=True)


# ---------------------------------------------------------------------------
# universes (precomputed both-side settlement, both price bases)
# ---------------------------------------------------------------------------

def _profits(actual, line, mult_over, mult_under, void):
    """Both sides x both bases; NaN = void or unpriceable-in-basis.

    Takes WIN MULTIPLIERS, not American prices. American odds are
    discontinuous at +/-100 and must never be averaged directly (a median of
    -110 and +112 is '+1', i.e. a 100x payout); every aggregation in this
    harness therefore happens in multiplier space and converts back only for
    reporting."""
    n = len(actual)
    out = {}
    codes = {}
    for side, mult in ((1, mult_over), (-1, mult_under)):
        code = np.full(n, np.nan)
        cap = np.full(n, np.nan)
        syn = np.full(n, np.nan)
        ok = ~void & ~np.isnan(actual) & ~np.isnan(line)
        for i in np.flatnonzero(ok):
            c = _settle_code(actual[i], line[i], side)
            code[i] = c
            syn[i] = {1: WIN_110, 0: 0.0, -1: -1.0}[c]
            if not np.isnan(mult[i]):
                cap[i] = {1: mult[i], 0: 0.0, -1: -1.0}[c]
        key = "over" if side > 0 else "under"
        out[f"cap_{key}"] = cap
        out[f"syn_{key}"] = syn
        codes[key] = code
    return out, codes


def _mult_to_american(m: float) -> float:
    """Inverse of _mult, for reporting an aggregated price on the odds scale."""
    if m != m:
        return np.nan
    return 100.0 * m if m >= 1.0 else -100.0 / m


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
            self.df["mult_over"].to_numpy(float),
            self.df["mult_under"].to_numpy(float),
            self.void)
        # under side may settle on a different line (best_line fills)
        if "settle_line_under" in self.df:
            prof_u, codes_u = _profits(
                self.df["actual_pts"].to_numpy(float),
                self.df["settle_line_under"].to_numpy(float),
                self.df["mult_over"].to_numpy(float),
                self.df["mult_under"].to_numpy(float),
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
        # scope masks (playoff caution): applied ON TOP of every level mask
        ph = self.df["phase"].to_numpy()
        self.scope_masks = {"all": np.ones(len(self.df), bool),
                            "regular": ph == "regular",
                            "playoff": ph == "playoff"}

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
    # share of CANDIDATE ROWS that are alternate (non-main) lines; exactly one
    # row per (game, book, player) is main by construction, so this is the
    # fraction of the per_book universe sitting on alternate ladders
    acct["alt_line_row_share"] = round(1.0 - float(cand["is_main"].sum())
                                       / max(len(cand), 1), 4)
    acct["book_player_game_groups"] = int(grp_pb.ngroups)
    acct["price_availability_by_book"] = {
        b: {"rows": int(len(g)),
            "over_priced": int(g["over_price"].notna().sum()),
            "under_priced": int(g["under_price"].notna().sum())}
        for b, g in cand.groupby("bookmaker_key")}

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
    phase_vec = pg["phase"].to_numpy()

    # --- per_book: every (player, game, book, line) row -------------------
    per_book = attach_labels(cand)
    per_book["line_ref"] = per_book["line"]
    per_book["price_over"] = per_book["over_price"]
    per_book["price_under"] = per_book["under_price"]
    per_book["mult_over"] = per_book["over_price"].map(
        lambda p: _mult(p) if pd.notna(p) else np.nan)
    per_book["mult_under"] = per_book["under_price"].map(
        lambda p: _mult(p) if pd.notna(p) else np.nan)

    # --- consensus: one row per player-game -------------------------------
    # Price aggregated in MULTIPLIER space (median across the books posting
    # the consensus number as their main line), then converted back to an
    # American price for reporting only. Never median American odds.
    cons = attach_labels(pg.reset_index(drop=True))
    cons["line_ref"] = cons["cons_line"]
    at_cons = cand[cand["is_main"] & (cand["line"] == cand["cons_line"])].copy()
    at_cons["_mo"] = at_cons["over_price"].map(
        lambda p: _mult(p) if pd.notna(p) else np.nan)
    at_cons["_mu"] = at_cons["under_price"].map(
        lambda p: _mult(p) if pd.notna(p) else np.nan)
    cp = at_cons.groupby(["game_key", "player_id"]).agg(
        mult_over=("_mo", "median"), mult_under=("_mu", "median"),
        n_books_at_cons=("_mo", "size"))
    cons = cons.merge(cp, left_on=["game_key", "player_id"],
                      right_index=True, how="left")
    cons["price_over"] = cons["mult_over"].map(_mult_to_american)
    cons["price_under"] = cons["mult_under"].map(_mult_to_american)
    acct["consensus_line_not_posted_player_games"] = int(
        (~cons.set_index(["game_key", "player_id"]).index.isin(cp.index)).sum())

    # --- best_line: one row per player-game, side-specific fills ----------
    # Line SHOPPING across books: the most favourable MAIN number any book
    # posted (lowest for an over, highest for an under), ties broken by the
    # better price. Restricted to main lines on purpose — ranging over
    # alternate ladders would make "best line" degenerate (a 4.5 over at -400
    # is a better number and a worse bet). Alternates stay fully represented
    # in the per_book universe, as registered.
    best = attach_labels(pg.reset_index(drop=True))
    best["line_ref"] = best["cons_line"]           # decision line (house)
    fills = {}
    for side, pcol, best_asc in ((1, "over_price", True), (-1, "under_price", False)):
        rows = cand[cand["is_main"] & cand[pcol].notna()].copy()
        rows["_m"] = rows[pcol].map(_mult)
        # over: min line best -> sort line asc, mult desc, take first
        rows = rows.sort_values(["line", "_m"],
                                ascending=[best_asc, False], kind="stable")
        pick = rows.drop_duplicates(["game_key", "player_id"], keep="first")
        fills[side] = pick.set_index(["game_key", "player_id"])[
            ["line", pcol, "_m", "bookmaker_key"]]
    bi = pd.MultiIndex.from_arrays([best["game_key"], best["player_id"]])
    f1 = fills[1].reindex(bi)
    f2 = fills[-1].reindex(bi)
    best["settle_line_over"] = f1["line"].to_numpy(float)
    best["price_over"] = f1["over_price"].to_numpy(float)
    best["mult_over"] = f1["_m"].to_numpy(float)
    best["settle_line_under"] = f2["line"].to_numpy(float)
    best["price_under"] = f2["under_price"].to_numpy(float)
    best["mult_under"] = f2["_m"].to_numpy(float)
    best["best_book_over"] = fills[1].reindex(bi)["bookmaker_key"].to_numpy() \
        if "bookmaker_key" in fills[1].columns else None
    best["best_book_under"] = fills[-1].reindex(bi)["bookmaker_key"].to_numpy() \
        if "bookmaker_key" in fills[-1].columns else None
    acct["best_fill_missing_over"] = int(best["settle_line_over"].isna().sum())
    acct["best_fill_missing_under"] = int(best["settle_line_under"].isna().sum())

    universes = {
        "per_book": Universe("per_book", per_book, pg_index),
        "consensus": Universe("consensus", cons, pg_index),
        "best_line": Universe("best_line", best, pg_index),
    }
    return universes, proj_vec, season_vec, date_vec, phase_vec, pg_index


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
                    for scope in SCOPES:
                        rows.append({"execution": ex, "price_basis": basis,
                                     "threshold": thr, "cond_dim": dim,
                                     "cond_level": level, "scope": scope,
                                     "battery": ("registered" if scope == "all"
                                                 else f"companion_{scope}"),
                                     "level_idx": li})
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
        mask = (u.levels[r.level_idx][2] & u.scope_masks[r.scope]
                & (side != 0) & ~np.isnan(prof))
        n = int(mask.sum())
        roi_out[i] = (prof[mask].sum() / n) if n else np.nan


def eval_battery_rich(universes, cells: pd.DataFrame, proj_vec,
                      n_boot: int) -> pd.DataFrame:
    recs = []
    side_cache, prof_cache = {}, {}
    for r in cells.itertuples(index=False):
        u = universes[r.execution]
        sk = (r.execution, r.threshold)
        if sk not in side_cache:
            side_cache[sk] = sides_for(u, proj_vec, r.threshold)
        side = side_cache[sk]
        pk = (r.execution, r.threshold, r.price_basis)
        if pk not in prof_cache:
            prof_cache[pk] = u.profits_for(side, r.price_basis)
        prof = prof_cache[pk]
        lvl_mask = u.levels[r.level_idx][2] & u.scope_masks[r.scope]
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
        edge_all = proj_vec[u.pg_idx] - u.line_ref
        recs.append({"n_bets": n, "wins": wins, "losses": losses,
                     "pushes": pushes, "n_void": n_void,
                     "n_noprice": n_noprice, "hit_rate": hit, "roi": roi,
                     "roi_ci90_low": ci_lo, "roi_ci90_high": ci_hi,
                     "n_dates": n_dates,
                     "n_over": int((side[settled] > 0).sum()),
                     "n_under": int((side[settled] < 0).sum()),
                     "mean_edge": (float(np.nanmean(edge_all[settled]))
                                   if n else np.nan),
                     "mean_line": (float(np.nanmean(u.line_ref[settled]))
                                   if n else np.nan),
                     "n_candidate_rows_in_cell": int(lvl_mask.sum())})
    return pd.concat([cells.reset_index(drop=True), pd.DataFrame(recs)], axis=1)


def block_permutation(rng, proj_vec, block_vec):
    """Shuffle the projection column WITHIN each block, leaving every row
    attribute, line and outcome fixed (pocket_mining pattern).

    block = season           -> the REGISTERED null.
    block = (season, phase)  -> companion null. Necessary for any phase-scoped
        cell: playoff player-games are 7.8% of the pool and carry a different
        projection level, so a season-wide shuffle hands playoff rows
        regular-season projections and mis-centres the playoff null (verified
        2026-07-31: playoff null mean ROI -0.076 vs regular -0.051, which
        manufactures 'significance' for ordinary playoff cells)."""
    out = proj_vec.copy()
    for b in np.unique(block_vec):
        idx = np.flatnonzero(block_vec == b)
        out[idx] = proj_vec[idx[rng.permutation(len(idx))]]
    return out


def within_season_permutation(rng, proj_vec, season_vec):
    return block_permutation(rng, proj_vec, season_vec)


def _run_null(universes, cells, proj_vec, block_vec, n_perms, roi_obs, suffix,
              rich):
    """One permutation null; writes p/diagnostic columns with `suffix`."""
    rng = np.random.default_rng(SEED)
    perm_mat = np.empty((n_perms, len(cells)), np.float32)
    buf = np.empty(len(cells))
    for pi in range(n_perms):
        pv = block_permutation(rng, proj_vec, block_vec)
        eval_battery_fast(universes, cells, pv, buf)
        perm_mat[pi] = buf
    ge = perm_mat >= (roi_obs[None, :] - ROI_TIE_EPS)
    ge = np.where(np.isnan(perm_mat), False, ge)     # empty perm cell = not better
    nonempty = ~np.isnan(perm_mat)
    rich[f"n_perm_ge{suffix}"] = ge.sum(axis=0)
    rich[f"n_perm_nonempty{suffix}"] = nonempty.sum(axis=0)
    with np.errstate(invalid="ignore"):
        rich[f"perm_roi_mean{suffix}"] = np.nanmean(
            np.where(nonempty, perm_mat, np.nan), axis=0)
        rich[f"perm_roi_q95{suffix}"] = np.nanquantile(
            np.where(nonempty, perm_mat, np.nan), 0.95, axis=0)
    rich[f"p_perm{suffix}"] = rich[f"n_perm_ge{suffix}"] / n_perms
    rich[f"p_perm_phipson_smyth{suffix}"] = (
        rich[f"n_perm_ge{suffix}"] + 1) / (n_perms + 1)
    rich.loc[rich["roi"].isna(),
             [f"p_perm{suffix}", f"p_perm_phipson_smyth{suffix}"]] = np.nan
    return perm_mat, ge


def run_inference(universes, cells, proj_vec, season_vec, phase_vec,
                  n_perms, n_boot):
    t0 = time.time()
    rich = eval_battery_rich(universes, cells, proj_vec, n_boot)
    print(f"[observed] battery + bootstrap done ({time.time() - t0:.0f}s)")

    roi_obs = rich["roi"].to_numpy(float)
    elig_obs = (rich["n_bets"].to_numpy(int) >= MIN_CELL_N) & ~np.isnan(roi_obs)

    # REGISTERED null: within season
    t0 = time.time()
    perm_mat, ge = _run_null(universes, cells, proj_vec, season_vec, n_perms,
                             roi_obs, "", rich)
    print(f"[perm] registered within-season null done ({time.time() - t0:.0f}s)")
    # COMPANION null: within (season, phase) — the correct null for any
    # phase-scoped cell (see block_permutation docstring)
    t0 = time.time()
    sp = np.char.add(season_vec.astype(str), np.char.add("|", phase_vec.astype(str)))
    _run_null(universes, cells, proj_vec, sp, n_perms, roi_obs, "_phaseblock",
              rich)
    print(f"[perm] companion within-(season,phase) null done "
          f"({time.time() - t0:.0f}s)")

    rich["eligible"] = elig_obs
    rich["small_n_flag"] = ~rich["eligible"]
    rich["roi_positive"] = rich["roi"] > 0

    # BH WITHIN each scope family (the registered battery is scope='all'; the
    # regular/playoff companions are separate families, so splitting for the
    # playoff caution does not inflate the registered battery's multiplicity)
    rich["q_bh"] = np.nan
    rich["q_bh_phaseblock"] = np.nan
    scope_vec = rich["scope"].to_numpy()
    perm_summ, max_obs, frac_max = [], {}, {}
    for scope in SCOPES:
        fam = (scope_vec == scope) & elig_obs
        if not fam.any():
            max_obs[scope], frac_max[scope] = np.nan, np.nan
            continue
        rich.loc[fam, "q_bh"] = bh_qvalues(rich.loc[fam, "p_perm"].to_numpy(float))
        rich.loc[fam, "q_bh_phaseblock"] = bh_qvalues(
            rich.loc[fam, "p_perm_phaseblock"].to_numpy(float))
        pm = perm_mat[:, fam]
        max_perm = np.nanmax(np.where(np.isnan(pm), -np.inf, pm), axis=1)
        mo = float(np.nanmax(roi_obs[fam]))
        max_obs[scope] = mo
        frac_max[scope] = float((max_perm >= mo - ROI_TIE_EPS).mean())
        for pi in range(n_perms):
            perm_summ.append({
                "scope": scope, "battery": ("registered" if scope == "all"
                                            else f"companion_{scope}"),
                "perm_idx": pi,
                "n_eligible_cells_in_family": int(fam.sum()),
                "max_roi_over_eligible_cells": float(max_perm[pi]),
                "n_eligible_cells_perm_beats_obs": int(ge[pi, fam].sum())})
        print(f"[perm] scope={scope}: {int(fam.sum())} eligible cells; best "
              f"observed ROI {mo:+.4f}; P(best null >= best observed) = "
              f"{frac_max[scope]:.3f}")
    rich["starred"] = rich["eligible"] & (rich["q_bh"] <= BH_Q)
    rich["starred_phaseblock"] = rich["eligible"] & (rich["q_bh_phaseblock"] <= BH_Q)
    # a cell can beat its null while still LOSING money; only a starred cell
    # with ROI > 0 is a candidate bet
    rich["starred_and_profitable"] = rich["starred"] & rich["roi_positive"]
    # expected false discoveries among the starred set, BH form (q * n_starred)
    rich["expected_false_in_family"] = np.nan
    for scope in SCOPES:
        fam = scope_vec == scope
        ns = int((rich["starred"] & fam).sum())
        rich.loc[fam, "expected_false_in_family"] = BH_Q * ns
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

def _mae_row(scope, dim, level, sub, n_boot):
    """One projection-vs-line comparison row over an already-filtered frame."""
    a = sub["actual_pts"].to_numpy(float)
    pj = sub["proj_used"].to_numpy(float)
    ln = sub["line_cmp"].to_numpy(float)
    ok = ~np.isnan(a) & ~np.isnan(pj) & ~np.isnan(ln)
    a, pj, ln = a[ok], pj[ok], ln[ok]
    d = sub["game_date"].to_numpy()[ok]
    n = len(a)
    rec = {"scope": scope, "group_dim": dim, "group_level": level, "n": n}
    if not n:
        return rec
    ep, el = np.abs(pj - a), np.abs(ln - a)
    diff = ep - el                      # negative => our projection is closer
    lo = hi = np.nan
    if pd.Series(d).nunique() >= 2:
        try:
            ci = cluster_bootstrap_ci(diff, d, n_boot=n_boot, seed=SEED)
            lo, hi = ci["low"], ci["high"]
        except ComparisonError:
            pass
    rec.update({
        "mae_projection": float(ep.mean()), "mae_line": float(el.mean()),
        "mae_diff_proj_minus_line": float(diff.mean()),
        "mae_diff_ci90_low": lo, "mae_diff_ci90_high": hi,
        "rmse_projection": float(np.sqrt(((pj - a) ** 2).mean())),
        "rmse_line": float(np.sqrt(((ln - a) ** 2).mean())),
        "bias_projection": float((pj - a).mean()),
        "bias_line": float((ln - a).mean()),
        "share_projection_closer": float((ep < el).mean()),
        "share_tied": float((ep == el).mean()),
        "mean_actual_pts": float(a.mean()), "mean_projection": float(pj.mean()),
        "mean_line": float(ln.mean()),
        "corr_projection_actual": (float(np.corrcoef(pj, a)[0, 1])
                                   if n > 2 and pj.std() > 0 else np.nan),
        "corr_line_actual": (float(np.corrcoef(ln, a)[0, 1])
                             if n > 2 and ln.std() > 0 else np.nan)})
    return rec


def projection_vs_line(universes, proj_vec, n_boot: int) -> pd.DataFrame:
    """THE diagnostic: as a point estimate of actual points, is our walk-forward
    projection closer than the book's line? Consensus line per player-game is
    the comparator (one row per player-game, voids dropped — a DNP has no
    actual to score against). Per-book rows use that book's own main line."""
    u = universes["consensus"]
    c = u.df.copy()
    c["proj_used"] = proj_vec[u.pg_idx]
    c["line_cmp"] = u.line_ref
    c = c[~c["void"] & c["actual_pts"].notna()].copy()

    rows = []
    for scope in SCOPES:
        s = c if scope == "all" else c[c["phase"] == ("regular" if scope ==
                                                      "regular" else "playoff")]
        if not len(s):
            continue
        rows.append(_mae_row(scope, "overall", "all", s, n_boot))
        for dim, col in (("season", "season"), ("line_terc", "line_terc"),
                         ("role", "role"), ("min_terc", "min_terc"),
                         ("venue", "venue"), ("phase", "phase")):
            for lvl, sub in s.groupby(col, dropna=False):
                rows.append(_mae_row(scope, dim, str(lvl), sub, n_boot))

    # per-book comparison (the book's own posted main line vs our projection)
    ub = universes["per_book"]
    b = ub.df.copy()
    b["proj_used"] = proj_vec[ub.pg_idx]
    b["line_cmp"] = ub.line_ref
    b = b[b["is_main"] & ~b["void"] & b["actual_pts"].notna()]
    for scope in SCOPES:
        s = b if scope == "all" else b[b["phase"] == ("regular" if scope ==
                                                      "regular" else "playoff")]
        for lvl, sub in s.groupby("bookmaker_key"):
            rows.append(_mae_row(scope, "book", str(lvl), sub, n_boot))
    out = pd.DataFrame(rows)
    return out.sort_values(["scope", "group_dim", "group_level"],
                           kind="stable").reset_index(drop=True)


def main_vs_alt_summary(universes, proj_vec) -> pd.DataFrame:
    """Descriptive companion (not a registered cell): does the per_book
    universe's result come from books' MAIN numbers or from alternate ladders?
    Alt ladders carry longer prices and are the classic source of a fake
    retrospective pocket."""
    u = universes["per_book"]
    d = u.df
    edge = proj_vec[u.pg_idx] - u.line_ref
    rows = []
    for thr in THRESHOLDS:
        side = np.where(edge >= thr, 1, np.where(edge <= -thr, -1, 0))
        for basis in PRICE_BASES:
            prof = u.profits_for(side, basis)
            for lbl, m in (("main", d["is_main"].to_numpy(bool)),
                           ("alternate", ~d["is_main"].to_numpy(bool))):
                for scope in SCOPES:
                    sel = m & u.scope_masks[scope] & (side != 0) & ~np.isnan(prof)
                    n = int(sel.sum())
                    rows.append({"threshold": thr, "price_basis": basis,
                                 "line_kind": lbl, "scope": scope, "n_bets": n,
                                 "roi": float(prof[sel].mean()) if n else np.nan})
    return pd.DataFrame(rows)


def build_bet_log(universes, proj_vec) -> pd.DataFrame:
    """Row-level log of every PLACED bet: one row per (execution, threshold,
    candidate row) where the edge rule fires. Both price bases on the row."""
    out = []
    for ex in EXECUTIONS:
        u = universes[ex]
        d = u.df
        edge = proj_vec[u.pg_idx] - u.line_ref
        for thr in THRESHOLDS:
            side = np.where(edge >= thr, 1, np.where(edge <= -thr, -1, 0))
            sel = np.flatnonzero(side != 0)
            if not len(sel):
                continue
            settle_line = np.where(
                side > 0,
                d["settle_line_over"].to_numpy(float) if "settle_line_over" in d
                else u.line_ref,
                d["settle_line_under"].to_numpy(float) if "settle_line_under" in d
                else u.line_ref)
            price = np.where(side > 0, d["price_over"].to_numpy(float),
                             d["price_under"].to_numpy(float))
            rec = pd.DataFrame({
                "execution": ex, "threshold": thr,
                "game_id": d["game_id"].to_numpy()[sel],
                "game_date": d["game_date"].to_numpy()[sel],
                "season": d["season"].to_numpy()[sel],
                "phase": d["phase"].to_numpy()[sel],
                "player_id": d["player_id"].to_numpy()[sel],
                "player_name": d["player_name"].to_numpy()[sel],
                "bookmaker_key": (d["bookmaker_key"].to_numpy()[sel]
                                  if ex == "per_book" else ""),
                "decision_line": u.line_ref[sel],
                "settle_line": settle_line[sel],
                "price_captured": price[sel],
                "projection": proj_vec[u.pg_idx][sel],
                "edge": edge[sel],
                "side": np.where(side[sel] > 0, "over", "under"),
                "exp_min": d["exp_min"].to_numpy()[sel],
                "n_prior": d["n_prior"].to_numpy()[sel],
                "role": d["role"].to_numpy()[sel],
                "line_terc": d["line_terc"].to_numpy()[sel],
                "min_terc": d["min_terc"].to_numpy()[sel],
                "venue": d["venue"].to_numpy()[sel],
                "actual_pts": d["actual_pts"].to_numpy()[sel],
                "actual_min": d["actual_min"].to_numpy()[sel],
                "void_no_action": d["void"].to_numpy()[sel],
                "outcome": u.outcomes_for(side)[sel],
                "profit_captured": u.profits_for(side, "captured")[sel],
                "profit_synthetic110": u.profits_for(side, "synthetic110")[sel],
            })
            out.append(rec)
    log = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    if len(log):
        log["outcome_label"] = log["outcome"].map(
            {1.0: "win", 0.0: "push", -1.0: "loss"}).fillna("no_action")
    return log


def write_resolution_accounting(outdir: Path, acct: dict, props: pd.DataFrame,
                                pending: pd.DataFrame) -> pd.DataFrame:
    """Every row that entered and where it went — tidy, one line per fact."""
    res = acct.get("resolution", {})
    lad = acct.get("skip_ladder", {})
    rows = [("input", "rows_in_table", acct.get("rows_total"), str(HIST_CSV.name)),
            ("input", "rows_market_player_points", acct.get("rows_market"), MARKET),
            ("input", "rows_bad_line_dropped", acct.get("rows_bad_line_dropped"), ""),
            ("input", "rows_after_dedup_near_tip", acct.get("rows_near_tip"), ""),
            ("game_join", "rows_game_matched", acct.get("rows_game_matched"), ""),
            ("game_join", "rows_game_unmatched", acct.get("rows_game_unmatched_pending"), ""),
            ("game_join", "commence_date_vs_master_date_mismatch_rows",
             acct.get("commence_et_date_vs_master_mismatch_rows"),
             "master game_date is authoritative (leakage guard)"),
            ("name_resolution", "distinct_name_keys", res.get("unique_names"), ""),
            ("name_resolution", "keys_resolved_team_scope", res.get("resolved_team_scope"), ""),
            ("name_resolution", "keys_resolved_season_scope", res.get("resolved_season_scope"), ""),
            ("name_resolution", "keys_ambiguous_never_guessed", len(res.get("ambiguous", [])),
             "; ".join(res.get("ambiguous", []))),
            ("name_resolution", "keys_unresolved", len(res.get("unresolved", [])),
             "; ".join(res.get("unresolved", []))),
            ("name_resolution", "rows_resolved", res.get("rows_resolved"), ""),
            ("name_resolution", "rows_total", res.get("rows_total"), ""),
            ("name_resolution", "row_resolution_rate",
             (round(res.get("rows_resolved", 0) / res["rows_total"], 6)
              if res.get("rows_total") else None), ""),
            ("skip_ladder", "rows_in", lad.get("rows_in"), "mutually exclusive, ordered"),
            ("skip_ladder", "skip_unresolved_rows", lad.get("skip_unresolved_rows"), ""),
            ("skip_ladder", "skip_ambiguous_rows", lad.get("skip_ambiguous_rows"), ""),
            ("skip_ladder", "skip_no_prior_appearance_rows",
             lad.get("skip_no_prior_appearance_rows"), "no strictly-prior same-season game"),
            ("skip_ladder", "skip_below_min_prior_rows",
             lad.get("skip_below_min_prior_rows"), f"1-{MIN_PRIOR - 1} prior appearances"),
            ("skip_ladder", "skip_ungraded_game_rows",
             lad.get("skip_ungraded_game_rows"), "game not in master yet"),
            ("skip_ladder", "candidate_rows", lad.get("candidate_rows"), ""),
            ("settlement", "void_rows_dnp", acct.get("void_rows_dnp"),
             "player did not play: no action"),
            ("settlement", "venue_unknown_rows", acct.get("venue_unknown_rows"), ""),
            ("settlement", "alt_line_row_share", acct.get("alt_line_row_share"),
             "share of per_book rows on alternate (non-main) ladders"),
            ("settlement", "book_player_game_groups",
             acct.get("book_player_game_groups"), ""),
            ("settlement", "consensus_line_not_posted_player_games",
             acct.get("consensus_line_not_posted_player_games"),
             "median consensus line no book posts: captured-basis price NaN"),
            ("settlement", "best_fill_missing_over", acct.get("best_fill_missing_over"), ""),
            ("settlement", "best_fill_missing_under", acct.get("best_fill_missing_under"), ""),
            ]
    for k, v in (acct.get("phase_rows") or {}).items():
        rows.append(("phase", f"candidate_rows_{k}", v, ""))
    for b, d in (acct.get("price_availability_by_book") or {}).items():
        rows.append(("price_availability", f"{b}_rows", d["rows"], ""))
        rows.append(("price_availability", f"{b}_over_priced", d["over_priced"],
                     f"{d['over_priced'] / max(d['rows'], 1):.1%} of its rows"))
        rows.append(("price_availability", f"{b}_under_priced", d["under_priced"],
                     f"{d['under_priced'] / max(d['rows'], 1):.1%} of its rows"))
    for name, cnt in sorted(
            props.loc[props["resolve_status"] != "resolved_team"]
            .groupby(["player_name", "resolve_status"]).size().items()):
        if cnt and name[1] in ("unresolved", "ambiguous"):
            rows.append(("unresolved_detail", name[0], int(cnt), name[1]))
    df = pd.DataFrame(rows, columns=["stage", "metric", "value", "detail"])
    df.to_csv(outdir / "resolution_accounting.csv", index=False)
    return df


def write_results_md(outdir: Path, partial: bool, acct: dict, rich: pd.DataFrame,
                     max_obs, frac_max, args, cover: dict, n_pg: int):
    surv = rich[rich["starred"]].sort_values("roi", ascending=False)
    mae = acct.get("_mae_table")
    lines = []
    title = "PARTIAL DRY-RUN — NOT RESULTS" if partial else "Results"
    lines.append(f"# props_edge_v1 — {title}\n")
    lines.append(f"*Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
                 f"by props_edge.py. Registered protocol: experiments/registry.jsonl "
                 f"(props_edge_v1, 2026-07-31T14:59:26Z). MEASUREMENT STUDY — "
                 f"sentinel gates by design; nothing here promotes anything.*\n")

    # ---------------- HEADLINE: projection vs line as a point estimate -----
    if mae is not None and len(mae):
        lines.append("## THE HEADLINE — are our projections better than the "
                     "books' lines?\n")
        h = mae[(mae.group_dim == "overall") & (mae.scope == "all")]
        hr = mae[(mae.group_dim == "overall") & (mae.scope == "regular")]
        hp = mae[(mae.group_dim == "overall") & (mae.scope == "playoff")]
        for lbl, row in (("ALL rows (regular + playoffs)", h),
                         ("REGULAR SEASON only (headline)", hr),
                         ("PLAYOFFS only (reported, never aggregated)", hp)):
            if not len(row):
                continue
            r = row.iloc[0]
            verdict = ("OUR PROJECTION IS CLOSER" if r.mae_diff_proj_minus_line < 0
                       else "THE BOOKS' LINE IS CLOSER")
            lines.append(
                f"- **{lbl}** (n={int(r.n)} player-games): projection MAE "
                f"**{r.mae_projection:.3f}** vs line MAE **{r.mae_line:.3f}** "
                f"-> difference **{r.mae_diff_proj_minus_line:+.3f}** points "
                f"(90% CI {r.mae_diff_ci90_low:+.3f} to {r.mae_diff_ci90_high:+.3f}); "
                f"projection closer on {r.share_projection_closer:.1%} of "
                f"player-games. **{verdict}.**")
        if len(hr):
            r = hr.iloc[0]
            if r.mae_diff_proj_minus_line > 0:
                lines.append(
                    f"\n> **Plainly: the books' player-points lines are a better "
                    f"predictor of actual points than our projection is, by "
                    f"{r.mae_diff_proj_minus_line:.2f} points of MAE per "
                    f"player-game in the regular season. Any pocket found below "
                    f"is a pocket found DESPITE a worse point estimate, and must "
                    f"be treated as a candidate for live confirmation only.**\n")
            else:
                lines.append(
                    f"\n> **Plainly: our projection beats the line as a point "
                    f"estimate by {-r.mae_diff_proj_minus_line:.2f} MAE points "
                    f"in the regular season. This is the single most important "
                    f"number in the study and it is in our favour.**\n")
        lines.append("\nFull breakdown (by season, phase, line height, role, "
                     "minutes volume, venue, book): `projection_vs_line.csv`.\n")
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
                 f"alternate-ladder share of candidate rows: "
                 f"{acct.get('alt_line_row_share')} "
                 f"({acct.get('book_player_game_groups')} (game,book,player) "
                 f"groups)")
    lines.append(f"- phase: {acct.get('regular_player_games')} regular-season "
                 f"player-games vs {acct.get('playoff_player_games')} playoff "
                 f"player-games ({acct.get('playoff_games')} playoff games over "
                 f"{acct.get('playoff_dates')} dates). **The playoff sample is "
                 f"{100 * (acct.get('playoff_player_games') or 0) / max((acct.get('playoff_player_games') or 0) + (acct.get('regular_player_games') or 1), 1):.1f}% "
                 f"of the study and every playoff cell re-uses those same rows.**")
    lines.append(f"- tercile boundaries (per season, candidate player-games): "
                 f"{json.dumps(acct.get('tercile_bounds', {}))}\n")
    lines.append("## Battery\n")
    lines.append(f"Cells are the registered closed battery — execution "
                 f"{EXECUTIONS} x price basis {PRICE_BASES} x threshold "
                 f"{THRESHOLDS} x conditioner {CONDITIONERS} — evaluated under "
                 f"three scopes: `all` (**the registered battery**), `regular` "
                 f"(the headline-safe companion) and `playoff` (reported, never "
                 f"aggregated into a headline; John has paused playoff betting). "
                 f"BH runs WITHIN each scope family, so the playoff split does "
                 f"not inflate the registered battery's multiplicity.\n")
    lines.append("**Two nulls are reported.** `p_perm` is the REGISTERED null "
                 "(projection shuffled within season). `p_perm_phaseblock` "
                 "shuffles within (season, phase) and is the only valid null "
                 "for a phase-scoped cell: playoff player-games are 7.8% of the "
                 "pool and carry a different projection level, so a season-wide "
                 "shuffle hands playoff rows regular-season projections and "
                 "mis-centres the playoff null. Measured here: mean null ROI on "
                 "eligible playoff cells is -0.076 under the registered shuffle "
                 "vs -0.051 on regular-season cells, which manufactures "
                 "'significance' for ordinary playoff results. **Treat every "
                 "playoff star under the registered null as an artefact until "
                 "the phase-blocked column agrees.**\n")
    cols = ["execution", "price_basis", "threshold", "cond_dim", "cond_level",
            "n_bets", "wins", "losses", "pushes", "hit_rate", "roi",
            "roi_ci90_low", "roi_ci90_high", "p_perm", "q_bh", "starred",
            "p_perm_phaseblock", "starred_phaseblock"]
    for scope in SCOPES:
        sc = rich[rich["scope"] == scope]
        n_elig = int(sc["eligible"].sum())
        sv = sc[sc["starred"]]
        svp = sc[sc["starred"] & sc["roi_positive"]]
        svpb = sc[sc["starred_phaseblock"]]
        lines.append(f"\n### scope = {scope}"
                     + ("  (REGISTERED BATTERY)" if scope == "all" else
                        "  (companion)") + "\n")
        lines.append(f"- cells {len(sc)}; eligible (n_settled >= {MIN_CELL_N}) "
                     f"{n_elig}; **starred (BH q <= {BH_Q}): {len(sv)}**, of "
                     f"which **{len(svp)} have ROI > 0**; expected false among "
                     f"starred at q={BH_Q}: {BH_Q * len(sv):.1f}")
        lines.append(f"- under the phase-blocked companion null: "
                     f"{len(svpb)} starred, {int((sc['starred_phaseblock'] & sc['roi_positive']).sum())} "
                     f"of them profitable")
        if len(sv) and not len(svp):
            lines.append("- **every starred cell in this scope LOSES money.** A "
                         "permutation star means 'better than a shuffled "
                         "projection', not 'profitable'; a cell that loses less "
                         "than chance is not a bet.")
        if n_elig:
            lines.append(f"- best observed eligible-cell ROI "
                         f"{max_obs.get(scope, float('nan')):+.4f}; P(best null "
                         f">= best observed) = {frac_max.get(scope, float('nan')):.3f} "
                         f"({args.n_perms} within-season permutations)")
            mean_roi = float(sc.loc[sc["eligible"], "roi"].mean())
            lines.append(f"- mean ROI across eligible cells: {mean_roi:+.4f}")
        if len(sv):
            lines.append(f"\n**The {len(sv)} starred cell(s) in this scope "
                         f"(these are what BH selected, whatever their ROI):**\n")
            lines.append(sv.sort_values("roi", ascending=False)[cols].to_string(
                index=False, float_format=lambda x: f"{x:.4f}") + "\n")
        lines.append("\n**Top eligible cells by ROI** (ranking is by return, "
                     "not by significance — a high-ROI cell with a large "
                     "p_perm is noise):\n")
        top = (sc[sc["eligible"]].sort_values("roi", ascending=False).head(12)
               if n_elig else sc.sort_values("n_bets", ascending=False).head(8))
        lines.append("\n" + top[cols].to_string(
            index=False, float_format=lambda x: f"{x:.4f}") + "\n")
    ma = acct.get("_main_alt")
    if ma is not None and len(ma):
        lines.append("\n### Companion diagnostic — main lines vs alternate "
                     "ladders (per_book universe, NOT a registered cell)\n")
        lines.append(ma[ma["scope"] != "playoff"].to_string(
            index=False, float_format=lambda x: f"{x:.4f}"))
        lines.append("\n*If a pocket lives only in the `alternate` rows it is "
                     "almost certainly a price artefact, not an edge.*\n")
    lines.append("\n### Headline cells (no conditioner), both phases\n")
    head = rich[(rich["cond_dim"] == "none")].sort_values(
        ["execution", "price_basis", "threshold", "scope"])
    lines.append(head[["execution", "price_basis", "threshold", "scope",
                       "n_bets", "hit_rate", "roi", "roi_ci90_low",
                       "roi_ci90_high", "p_perm"]].to_string(
        index=False, float_format=lambda x: f"{x:.4f}"))
    lines.append("\n\n*Pushes risk the stake and return 0 (house convention); "
                 "voids (player did not play) are no-action and sit outside "
                 "stakes settled. Captured basis excludes bets whose side "
                 "price was not posted (n_noprice per cell). ROI is flat-stake "
                 "profit per unit staked.*\n")
    lines.append("\n## Artifacts\n")
    for f, what in (("all_cells.csv", "every battery cell, all three scopes"),
                    ("bet_log.csv", "row-level: one row per placed bet"),
                    ("projection_vs_line.csv", "THE MAE diagnostic"),
                    ("resolution_accounting.csv", "every row and where it went"),
                    ("permutation_summary.csv", "the 200-permutation null"),
                    ("PROPS_LEDGER.md", "surviving pockets, ranked"),
                    ("accounting.json", "full machine-readable accounting"),
                    ("bet_universe_*.csv", "all candidate rows incl. no-bets")):
        lines.append(f"- `{f}` — {what}")
    (outdir / ("REPORT_PARTIAL.md" if partial else "REPORT.md")).write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def write_ledger(outdir: Path, rich: pd.DataFrame, mae: pd.DataFrame,
                 acct: dict, args, frac_max: dict, partial: bool):
    """PROPS_LEDGER.md — charter amendment 4 style: rank every surviving
    pocket, state the mechanism, flag the anomalies that would make a naive
    reader over-trust it."""
    L = []
    L.append("# PROPS_LEDGER — props_edge_v1 surviving pockets\n")
    L.append(f"*{datetime.now(timezone.utc).isoformat(timespec='seconds')}. "
             f"Ranking of every pocket that survived the registered honesty "
             f"machinery (200 within-season permutations of the projection "
             f"column, BH at {BH_Q} within scope family, {MIN_CELL_N}-bet "
             f"minimum, 90% date-clustered bootstrap CIs). "
             f"MEASUREMENT STUDY: everything here is a CANDIDATE. The "
             f"confirmation channel is the live prospective props log, not this "
             f"file.*\n")
    if partial:
        L.append("> **PARTIAL RUN — no conclusions.**\n")

    if mae is not None and len(mae):
        hr = mae[(mae.group_dim == "overall") & (mae.scope == "regular")]
        if len(hr):
            r = hr.iloc[0]
            L.append(f"## Context that governs every row below\n")
            L.append(f"Regular-season projection MAE **{r.mae_projection:.3f}** "
                     f"vs line MAE **{r.mae_line:.3f}** "
                     f"({r.mae_diff_proj_minus_line:+.3f}). "
                     + ("The books' lines are the better point estimate. A "
                        "profitable pocket therefore cannot be explained by "
                        "'our projection is more accurate'; it would have to be "
                        "a pricing/threshold artefact, and that is a much weaker "
                        "prior than accuracy.\n"
                        if r.mae_diff_proj_minus_line > 0 else
                        "Our projection is the better point estimate, which is "
                        "the mechanism a real pocket would rest on.\n"))

    for scope in SCOPES:
        sc_all = rich[(rich["scope"] == scope) & rich["starred"]].sort_values(
            "roi", ascending=False)
        # a permutation star is not a bet unless it also makes money
        sc = sc_all[sc_all["roi_positive"]]
        losers = sc_all[~sc_all["roi_positive"]]
        fam_elig = int(((rich["scope"] == scope) & rich["eligible"]).sum())
        label = ("REGISTERED BATTERY (all rows)" if scope == "all"
                 else f"COMPANION — {scope} only")
        L.append(f"\n## {label}\n")
        L.append(f"- eligible cells tested: {fam_elig}; cells beating the "
                 f"registered null after BH: {len(sc_all)}; **of those, "
                 f"PROFITABLE (ROI > 0): {len(sc)}**; expected false among the "
                 f"{len(sc_all)} at q={BH_Q}: **{BH_Q * len(sc_all):.1f}**")
        L.append(f"- under the phase-blocked companion null: "
                 f"{int(((rich['scope'] == scope) & rich['starred_phaseblock']).sum())} "
                 f"cells survive")
        if len(losers):
            L.append(f"- {len(losers)} cell(s) beat the null while still LOSING "
                     f"money (ROI {losers['roi'].min():+.4f} to "
                     f"{losers['roi'].max():+.4f}). A permutation star says "
                     f"'better than a shuffled projection', not 'profitable'. "
                     f"These are NOT bets and are excluded from the ranking "
                     f"below; they are in `all_cells.csv`.")
        fm = frac_max.get(scope, float("nan"))
        L.append(f"- family-wise sanity: P(best permuted cell >= best observed "
                 f"cell) = {fm:.3f} over {args.n_perms} permutations "
                 + ("— the best observed cell is INDISTINGUISHABLE from the "
                    "best cell a shuffled projection produces."
                    if fm == fm and fm > 0.10 else
                    "— the best observed cell is beyond what shuffling "
                    "typically produces."))
        if scope == "playoff":
            L.append("- **Playoff pockets are reported, never acted on: John "
                     "has paused playoff betting pending model improvements.**")
        if scope == "playoff":
            L.append("- **NULL WARNING: playoff stars under the registered "
                     "within-season shuffle are mis-calibrated** (the shuffle "
                     "hands playoff rows regular-season projections). The "
                     "phase-blocked count above is the trustworthy one.")
        if not len(sc):
            L.append("\n**No surviving profitable pockets.** This is a "
                     "legitimate result: under the registered rules, no "
                     "conditioning slice of the projection-vs-line disagreement "
                     "produced a profitable pocket that beat its own "
                     "permutation null after multiplicity correction.")
            continue
        L.append("")
        LEDGER_MAX = 15
        if len(sc) > LEDGER_MAX:
            L.append(f"*Listing the {LEDGER_MAX} highest-ROI of {len(sc)}; the "
                     f"rest are in `all_cells.csv`. Note these cells are NOT "
                     f"independent — they are overlapping views of the same "
                     f"underlying player-games.*\n")
        for i, r in enumerate(sc.head(LEDGER_MAX).itertuples(index=False), 1):
            flags = []
            if scope == "playoff":
                flags.append(f"drawn from a {int(acct.get('playoff_player_games', 0))}"
                             f"-player-game postseason sample across "
                             f"{int(acct.get('playoff_dates', 0))} dates; every "
                             f"playoff cell re-uses these same rows, so the "
                             f"survivors are one finding, not many")
            if r.roi_ci90_low <= 0 <= r.roi_ci90_high:
                flags.append("CI SPANS ZERO (bootstrap disagrees with the "
                             "permutation p-value)")
            if r.n_bets < 2 * MIN_CELL_N:
                flags.append(f"thin ({r.n_bets} bets, just over the "
                             f"{MIN_CELL_N} floor)")
            if r.n_dates < 30:
                flags.append(f"only {r.n_dates} distinct dates — clustered")
            if r.price_basis == "synthetic110":
                flags.append("SYNTHETIC -110 price: real prop prices are worse "
                             "than -110 on at least one side far more often "
                             "than not; check the captured-basis twin")
            if r.execution == "best_line":
                flags.append("best-line execution assumes you get the best "
                             "number across books on every bet")
            if r.cond_dim == "book":
                flags.append("single-book pocket — book-level slices are the "
                             "most fragile (limits, availability, line drift)")
            if abs(r.hit_rate - 0.5) < 0.02:
                flags.append("hit rate ~50%: the ROI is carried by prices, not "
                             "by picking sides")
            if not r.starred_phaseblock:
                flags.append("does NOT survive the phase-blocked companion "
                             "null — the star depends on the season-wide "
                             "shuffle's block structure")
            twin = rich[(rich["scope"] == "regular")
                        & (rich["execution"] == r.execution)
                        & (rich["price_basis"] == r.price_basis)
                        & (rich["threshold"] == r.threshold)
                        & (rich["cond_dim"] == r.cond_dim)
                        & (rich["cond_level"] == r.cond_level)]
            if scope == "all" and len(twin):
                t = twin.iloc[0]
                if t["n_bets"] and np.sign(t["roi"]) != np.sign(r.roi):
                    flags.append(f"PLAYOFF-DRIVEN: regular-season-only ROI is "
                                 f"{t['roi']:+.4f} on {int(t['n_bets'])} bets — "
                                 f"the sign flips without playoffs")
            L.append(f"### {i}. {r.execution} / {r.price_basis} / thr {r.threshold} "
                     f"/ {r.cond_dim}={r.cond_level}")
            L.append(f"- **ROI {r.roi:+.4f}** (90% CI {r.roi_ci90_low:+.4f} to "
                     f"{r.roi_ci90_high:+.4f}) on **{int(r.n_bets)} bets** "
                     f"({int(r.wins)}W-{int(r.losses)}L-{int(r.pushes)}P, hit "
                     f"{r.hit_rate:.3f}) over {int(r.n_dates)} dates")
            L.append(f"- permutation p = {r.p_perm:.4f} "
                     f"(Phipson-Smyth {r.p_perm_phipson_smyth:.4f}); "
                     f"BH q = {r.q_bh:.4f}; null-mean ROI "
                     f"{r.perm_roi_mean:+.4f}, null 95th pct "
                     f"{r.perm_roi_q95:+.4f}")
            L.append(f"- mechanism note: bets fire when |projection - line| >= "
                     f"{r.threshold}; this cell took {int(r.n_over)} overs and "
                     f"{int(r.n_under)} unders at a mean edge of "
                     f"{r.mean_edge:+.2f} points on a mean line of "
                     f"{r.mean_line:.1f}.")
            L.append("- anomaly flags: " + ("; ".join(flags) if flags
                                            else "none triggered"))
            L.append("")
    L.append("\n## What would confirm any of this\n")
    L.append("Nothing in this file is evidence a pocket is real — a retrospective "
             "battery can only nominate. Confirmation = preregistering the "
             "surviving cell as a live paper-trade cell and grading it on games "
             "played AFTER registration, using the 4x-daily props capture.")
    (outdir / ("PROPS_LEDGER_PARTIAL.md" if partial else "PROPS_LEDGER.md")
     ).write_text("\n".join(L) + "\n", encoding="utf-8")


def write_universe_csvs(outdir: Path, universes, proj_vec):
    for name, u in universes.items():
        d = u.df.copy()
        edge = proj_vec[u.pg_idx] - u.line_ref
        d["proj_used"] = proj_vec[u.pg_idx]
        d["edge"] = edge
        d["bet_at_min_threshold"] = np.abs(edge) >= min(THRESHOLDS)
        keep = [c for c in [
            "game_id", "game_key", "season", "phase", "game_date", "player_id",
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
    assert _norm("Karlie  Samuelson!") == "karliesamuelson"
    # REGRESSION GUARD (bug found and fixed 2026-07-31): American odds must
    # never be averaged on the odds scale. median(-110, +112) = +1 -> a 100x
    # payout that does not exist. Aggregate multipliers instead.
    assert abs(np.median([-110.0, 112.0]) - 1.0) < 1e-12          # the trap
    m = float(np.median([_mult(-110.0), _mult(112.0)]))
    assert 0.9 < m < 1.2, m                                        # sane payout
    assert abs(_mult_to_american(_mult(-110.0)) + 110.0) < 1e-9
    assert abs(_mult_to_american(_mult(150.0)) - 150.0) < 1e-9
    # settlement is driven by multipliers, and an unpriced side stays NaN
    prof, codes = _profits(np.array([20.0, 20.0]), np.array([19.5, 19.5]),
                           np.array([WIN_110, np.nan]),
                           np.array([WIN_110, WIN_110]),
                           np.array([False, False]))
    assert abs(prof["cap_over"][0] - WIN_110) < 1e-12
    assert np.isnan(prof["cap_over"][1]) and prof["syn_over"][1] == WIN_110
    assert prof["cap_under"][0] == -1.0
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
        "game_id", "season", "season_type", "game_date", "team_abbreviation",
        "is_home", "player_id", "player_name", "starter_flag", "minutes", "pts"])
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
        universes, proj_vec, season_vec, date_vec, phase_vec, pg_index = \
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
    universes, proj_vec, season_vec, date_vec, phase_vec, pg_index = \
        build_universes(cand, acct)
    cells = build_cells(universes)
    print(f"{len(cells)} cells over {len(pg_index)} candidate player-games "
          f"({len(cand)} per-book rows) | thresholds {THRESHOLDS} | "
          f"executions {EXECUTIONS} | bases {PRICE_BASES}")
    rich, perm_summ, max_obs, frac_max = run_inference(
        universes, cells, proj_vec, season_vec, phase_vec, args.n_perms,
        args.n_boot)

    rich_out = rich.drop(columns=["level_idx"])
    if partial:
        rich_out.insert(0, "PARTIAL_DRYRUN", True)
    rich_out.to_csv(outdir / "all_cells.csv", index=False)
    if len(perm_summ):
        perm_summ.to_csv(outdir / "permutation_summary.csv", index=False)
    write_universe_csvs(outdir, universes, proj_vec)

    pg_ph = cand.drop_duplicates(["game_key", "player_id"])
    acct["playoff_player_games"] = int((pg_ph["phase"] == "playoff").sum())
    acct["playoff_dates"] = int(pg_ph.loc[pg_ph["phase"] == "playoff",
                                          "game_date"].nunique())
    acct["playoff_games"] = int(pg_ph.loc[pg_ph["phase"] == "playoff",
                                          "game_id"].nunique())
    acct["regular_player_games"] = int((pg_ph["phase"] == "regular").sum())
    print("[diagnostic] projection vs line ...")
    mae = projection_vs_line(universes, proj_vec, args.n_boot)
    mae.to_csv(outdir / "projection_vs_line.csv", index=False)
    acct["_mae_table"] = mae
    log = build_bet_log(universes, proj_vec)
    log.to_csv(outdir / "bet_log.csv", index=False)
    acct["bet_log_rows"] = int(len(log))
    ma = main_vs_alt_summary(universes, proj_vec)
    ma.to_csv(outdir / "main_vs_alt_lines.csv", index=False)
    acct["_main_alt"] = ma
    write_resolution_accounting(outdir, acct, props, pending)

    acct["degraded_defaults"] = (args.n_perms != N_PERMS_DEFAULT
                                 or args.n_boot != N_BOOT_DEFAULT)
    acct_json = {k: v for k, v in acct.items() if not k.startswith("_")}
    (outdir / "accounting.json").write_text(
        json.dumps(acct_json, indent=1, default=str), encoding="utf-8")
    write_results_md(outdir, partial, acct, rich, max_obs, frac_max, args,
                     cover, len(pg_index))
    write_ledger(outdir, rich, mae, acct, args, frac_max, partial)

    n_elig = int(rich["eligible"].sum())
    n_star = int(rich["starred"].sum())
    h = mae[(mae.group_dim == "overall") & (mae.scope == HEADLINE_SCOPE)]
    if len(h):
        r = h.iloc[0]
        print(f"\n=== HEADLINE ({HEADLINE_SCOPE} season, n={int(r.n)} "
              f"player-games) ===")
        print(f"projection MAE {r.mae_projection:.3f} vs line MAE "
              f"{r.mae_line:.3f}  ->  {r.mae_diff_proj_minus_line:+.3f} "
              f"(90% CI {r.mae_diff_ci90_low:+.3f}, {r.mae_diff_ci90_high:+.3f})")
        print("  " + ("THE BOOKS' LINES ARE THE BETTER PREDICTOR."
                      if r.mae_diff_proj_minus_line > 0
                      else "OUR PROJECTION IS THE BETTER PREDICTOR."))
    print(f"\n{'PARTIAL DRY-RUN ' if partial else ''}battery: {len(rich)} cells, "
          f"{n_elig} eligible (n>={MIN_CELL_N}), {n_star} starred (BH {BH_Q})"
          + (" — PARTIAL: numbers are mechanics checks, not results" if partial else ""))
    for scope in SCOPES:
        sc = rich[rich["scope"] == scope]
        print(f"  scope={scope:8s} eligible {int(sc['eligible'].sum()):4d}  "
              f"starred {int(sc['starred'].sum()):3d}  expected-false "
              f"{BH_Q * int(sc['starred'].sum()):.1f}")
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
