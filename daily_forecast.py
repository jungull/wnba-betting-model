#!/usr/bin/env python3
"""
daily_forecast.py — v0 daily slate forecast job (DRY-RUN build).

ENGINEERING, not a registered experiment. This job assembles today's slate from
LOCAL captures only (no network), produces the promoted structural-channel team
forecast per game at a named cutoff, attaches an INFORMATIONAL per-player
availability/minutes layer, and logs hash-chained records via
``evalharness.forecast_log`` — to a SCRATCH chain only.

================================ REGIME-D WARNING ==============================
The FIRST REAL RECORD in the default forecast log (forecasts/forecast_log.jsonl)
officially starts the regime-D prospective clock (ROADMAP, "The four evaluation
regimes"; evalharness/forecast_log.py docstring). That decision belongs to the
orchestrator and John. This script therefore HARD-REFUSES to write anywhere but
experiments/forecast_dryrun/scratch_chain.jsonl (see _guard_scratch_path). Do
not point it at the real log; when regime D is started for real, that happens
by a deliberate, separate act — never by running this dry-run.
================================================================================

Model (v0, frozen from promoted work — nothing new is fitted here):
  * Team forecast: the PROMOTED structural channel chains from
    ``chanreval_2026_structural_repaired`` run 1 (regime A, PASS all 5 gates).
    Feature logic re-implements experiments/channel_reval/run_reval.py
    ``build_features`` for a FUTURE game: per-(team, season-2026) shifted EWMA
    trends — for a game later than every played game, the shift(1) value is the
    ewm(...).mean() of all games to date — plus strictly-earlier-dates league
    running means. Alphas and the train-years-only (2021-2023) linear
    calibrations are READ from experiments/channel_reval/run_summary.json,
    never refit.
  * Player layer (INFORMATIONAL columns only in v0 — it does NOT modify the
    team forecast): recency dressed roster (last 3 team games incl. DNP rows),
    per-player minutes EWMA alpha=0.30 (promoted minutes_ewma_vs_carryforward_v1),
    availability gate per MINUTES_MODEL_SPEC Phase 3: latest captured official
    designation ``Out`` at the cutoff => player excluded (rule-based, no
    training needed). Other designations annotate, never exclude.

Prediction contract (ROADMAP): one named cutoff per run (default: now),
labeled with the NEAREST contract decision time (T-24h / T-8h / T-90m / T-30m);
the actual hours-to-tip is recorded alongside so the label never overstates.
Every forecast row carries event_time / published_time / observed_time /
forecast_cutoff / source / source_version, the market line at the cutoff
(nearest PRIOR odds snapshot), the model version hash (git HEAD read from the
.git/HEAD FILE — no git command is ever run), and a data snapshot description.

No-imputation rule: every missing input degrades EXPLICITLY (a note in the
gaps ledger, a null field, or a skipped game) — never silently.

Inputs (all local):
  data/odds_capture/live_*.json           slate + market lines (The Odds API raw)
  data/ref_assignments/assignments_log.csv official game_ids + crews
  data/injury_capture/injury_log.csv      official designations (capture history)
  data/masters/master_team.parquet        channel inputs through yesterday
  data/masters/master_player.parquet      rosters/minutes through yesterday
  experiments/channel_reval/run_summary.json  frozen alphas + calibrations
  .git/HEAD (+ refs)                      code version (file read only)

Outputs (all inside experiments/forecast_dryrun/):
  scratch_chain.jsonl      hash-chained records via evalharness.log_forecast
  forecast_today.csv       human-readable slate rows w/ full provenance
  feature_snapshot.csv     the exact per-team feature rows that were hashed
  snapshot_manifest.json   input provenance + hashes + chain anchor + gaps
  REPORT.md                today's slate: forecasts vs market, player layer

Usage:
  python daily_forecast.py                     # slate = today (ET), cutoff = now
  python daily_forecast.py --slate-date 2026-07-30 --cutoff 2026-07-30T21:30:00Z
  python daily_forecast.py --no-log            # compute + report, skip chain writes
  python daily_forecast.py --game-id 1022600225   # per-game scope (D-c): only
                                               # this game; exclusions DECLARED
                                               # in scope_declaration.json

Per-game execution scope + obligation-keyed dedup (defect D-c, decision D-4,
adopted 2026-08-06 under D022): each slate game is an independent execution
unit — one failing game degrades explicitly and never aborts the rest — and a
record is refused when its obligation (game_id, decision_time_label,
model_version_hash) is already in the chain, regardless of the wall-clock
forecast_cutoff. Chain records are written as schema evalharness/forecast_log/2
(additive optional alt_model_predictions; /1 records stand).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from evalharness.forecast_log import (  # noqa: E402  (path guard below)
    DEFAULT_FORECAST_LOG,
    DuplicateForecastError,
    hash_dataframe,
    hash_model_config,
    log_forecast,
    read_forecasts,
    verify_chain,
)

ET = ZoneInfo("America/New_York")

DRYRUN_DIR = REPO / "experiments" / "forecast_dryrun"
SCRATCH_CHAIN = DRYRUN_DIR / "scratch_chain.jsonl"

RUN_SUMMARY = REPO / "experiments" / "channel_reval" / "run_summary.json"
ODDS_DIR = REPO / "data" / "odds_capture"
INJURY_LOG = REPO / "data" / "injury_capture" / "injury_log.csv"
REF_LOG = REPO / "data" / "ref_assignments" / "assignments_log.csv"
MASTER_TEAM = REPO / "data" / "masters" / "master_team.parquet"
MASTER_PLAYER = REPO / "data" / "masters" / "master_player.parquet"

SOURCE_NAME = "daily_forecast.py v0 dry-run"
SOURCE_NAME_LIVE = "daily_forecast.py v0 FROZEN (freeze-v0)"
SOURCE_EXPERIMENT = "chanreval_2026_structural_repaired/run1"
MINUTES_ALPHA = 0.30          # promoted: minutes_ewma_vs_carryforward_v1
SIGMA_V0 = 12.9022            # frozen margin sigma: dist_margin_cover_v1
# Regime-D go-live authorization. The first record in the DEFAULT forecast log
# is the official prospective start (ROADMAP regime D). John approved:
# "freeze v0 approved" 2026-07-31; protocol in project_docs/FREEZE_PROPOSAL_v0.md
# and the prospective_v0 registration. --live is refused unless this is True.
FREEZE_V0_APPROVED = True
MIN_PRIOR = 5                 # constitution rule 2 (same as run_reval.py)
RECENCY_GAMES = 3             # MINUTES_MODEL_SPEC §5 recency roster window
EXPANSION = {(2025, "GSV"), (2026, "TOR"), (2026, "PDX")}  # first-season teams
CHANNELS = ["ft", "3pt", "paint", "np2"]
ODDS_STALE_MIN = 75           # hourly capture cadence + 15 min slack

# The prediction contract's named decision times, in hours before tip.
CONTRACT_LABELS = [("T-24h", 24.0), ("T-8h", 8.0), ("T-90m", 1.5), ("T-30m", 0.5)]

# Odds API full names -> our abbreviations (build_odds_master_extension.py TEAMS,
# verified there against the gamelog TEAM_NAME/TEAM_ABBREVIATION pairs).
TEAMS = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV",
    "Indiana Fever": "IND", "Las Vegas Aces": "LVA",
    "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Phoenix Mercury": "PHX",
    "Portland Fire": "PDX", "Seattle Storm": "SEA",
    "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
}


# ---------------------------------------------------------------------------
# gaps ledger — every degradation is recorded, none is silent
# ---------------------------------------------------------------------------

class Gaps:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, severity: str, component: str, message: str) -> None:
        # BLOCK (O14/D022, fix F4, applied per ops_adoption_tests/O14/
        # B_HANDOFF.md): an unbindable Out/Doubtful designation marks the
        # AVAILABILITY estimate untrustworthy for the affected team — the
        # player layer fails closed. Documented ruling: while the player
        # layer is informational in v0, BLOCK does NOT abort the team
        # forecast; Gaps.fatal() stays FATAL-only.
        assert severity in ("FATAL", "BLOCK", "WARN", "INFO")
        self.items.append({"severity": severity, "component": component,
                           "message": message})
        # console may be cp1252; files stay utf-8
        print(f"[{severity}] {component}: {message}"
              .encode("ascii", "replace").decode("ascii"))

    def fatal(self) -> bool:
        return any(g["severity"] == "FATAL" for g in self.items)


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------

def _guard_scratch_path(path: Path) -> Path:
    """Refuse to run against anything but the dry-run scratch chain.

    The first record of the DEFAULT log starts regime D officially; that write
    is the orchestrator's and John's, never this dry-run's.
    """
    path = path.resolve()
    if path == DEFAULT_FORECAST_LOG.resolve():
        sys.exit("REFUSED: this dry-run must never write the official forecast "
                 f"log ({DEFAULT_FORECAST_LOG}). The first real record starts "
                 "regime D — that is the orchestrator's/John's deliberate act.")
    if DRYRUN_DIR.resolve() not in path.parents:
        sys.exit(f"REFUSED: forecast-log writes are confined to {DRYRUN_DIR}; "
                 f"got {path}.")
    return path


def read_git_head(repo: Path, gaps: Gaps) -> str:
    """Git HEAD commit hash by FILE READ (.git/HEAD -> ref file / packed-refs).
    Never runs a git command."""
    head_file = repo / ".git" / "HEAD"
    try:
        head = head_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        gaps.add("WARN", "git-head", f"cannot read {head_file}: {exc}; "
                 "source_version degrades to 'unknown'")
        return "unknown"
    if head.startswith("ref: "):
        ref = head[5:].strip()
        ref_file = repo / ".git" / ref
        if ref_file.exists():
            return ref_file.read_text(encoding="utf-8").strip()
        packed = repo / ".git" / "packed-refs"
        if packed.exists():
            for line in packed.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.endswith(" " + ref):
                    return line.split(" ", 1)[0]
        gaps.add("WARN", "git-head", f"ref {ref} not found in refs or "
                 "packed-refs; source_version degrades to 'unknown'")
        return "unknown"
    if re.fullmatch(r"[0-9a-f]{40}", head):
        return head                     # detached HEAD
    gaps.add("WARN", "git-head", f"unrecognized HEAD content {head!r}")
    return "unknown"


# ---------------------------------------------------------------------------
# frozen model parameters (promoted run — read, never refit)
# ---------------------------------------------------------------------------

def load_frozen_params() -> dict:
    if not RUN_SUMMARY.exists():
        sys.exit(f"REFUSED: {RUN_SUMMARY} missing — the frozen alphas and "
                 "train-years-only calibrations of the promoted structural "
                 "model live there. No defaults are invented (no-imputation).")
    s = json.loads(RUN_SUMMARY.read_text(encoding="utf-8"))
    try:
        alphas = {c: float(s["alphas"][c]) for c in CHANNELS}
        cal = s["calibration"]
        params = {
            "alphas": alphas,
            "cal_str_margin": [float(v) for v in cal["str_margin"]],
            "cal_str_home": [float(v) for v in cal["str_home"]],
            "cal_str_away": [float(v) for v in cal["str_away"]],
            "cal_n_train_games": int(cal["n_train_games"]),
            "experiment_id": s["experiment_id"],
            "run_number": s.get("run_number"),
            "eval_time": s.get("eval_time"),
        }
    except (KeyError, TypeError, ValueError) as exc:
        sys.exit(f"REFUSED: {RUN_SUMMARY} lacks expected keys ({exc}); will "
                 "not guess model parameters.")
    if params["experiment_id"] != "chanreval_2026_structural_repaired":
        sys.exit(f"REFUSED: run_summary.json belongs to "
                 f"{params['experiment_id']!r}, expected the promoted "
                 "chanreval_2026_structural_repaired.")
    return params


# ---------------------------------------------------------------------------
# masters -> current-season channel state (through yesterday)
# ---------------------------------------------------------------------------

def build_channel_rows(season: int, slate_date, gaps: Gaps) -> tuple[pd.DataFrame, dict]:
    """Per-team-game channel rows for `season`, games strictly before
    `slate_date`. Re-proves the build_channel_base_v2.py identities on the rows
    used (the masters certify them; we re-prove, never trust)."""
    team = pd.read_parquet(MASTER_TEAM)
    player = pd.read_parquet(MASTER_PLAYER)
    prov = {
        "master_team_path": str(MASTER_TEAM),
        "master_team_max_game_date": str(team.game_date.max()),
        "master_team_max_observed_time": str(team.observed_time.max()),
    }
    t = team[(team.season == season)
             & (pd.to_datetime(team.game_date).dt.date < slate_date)].copy()
    if not len(t):
        gaps.add("FATAL", "masters", f"no season-{season} team rows before "
                 f"{slate_date} in {MASTER_TEAM}")
        return pd.DataFrame(), prov

    stale_days = (slate_date - pd.to_datetime(t.game_date).dt.date.max()).days
    prov["season_rows_used"] = int(len(t))
    prov["latest_game_used"] = str(t.game_date.max())
    prov["days_since_latest_game"] = int(stale_days)
    if stale_days > 3:
        gaps.add("WARN", "masters", f"latest {season} game in masters is "
                 f"{t.game_date.max()} ({stale_days} days before the slate) — "
                 "check the daily gamelog/misc refresh before trusting trends")

    # team-summed player paint must equal master_team.points_paint on every row
    agg = (player[player.season == season]
           .groupby(["game_id", "team_id"], as_index=False)
           .agg(team_pts_paint=("points_paint", "sum")))
    t = t.merge(agg, on=["game_id", "team_id"], how="left", validate="one_to_one")
    paint_bad = int(((t.team_pts_paint - t.points_paint).abs() > 0).sum()
                    + t.team_pts_paint.isna().sum())

    d = t.rename(columns={
        "game_id": "GAME_ID", "team_id": "TEAM_ID", "opp_team_id": "OPP_TEAM_ID",
        "team_abbreviation": "TEAM_ABBREVIATION", "game_date": "GAME_DATE",
        "pf": "team_pf", "fta": "team_fta", "ftm": "team_ftm",
        "ft_pct": "team_ft_pct", "fg3a": "team_fg3a", "fg3m": "team_fg3m",
        "fgm": "team_fgm", "pts": "team_pts",
    })
    d["GAME_DATE"] = pd.to_datetime(d["GAME_DATE"])
    d["ch_ft"] = d.team_ftm.astype(float)
    d["ch_3pt"] = d.team_fg3m.astype(float) * 3
    d["pts_2s"] = (d.team_fgm - d.team_fg3m).astype(float) * 2
    d["ch_paint"] = d.team_pts_paint.astype(float)
    d["ch_np2"] = d.pts_2s - d.ch_paint
    # opp-side channel inputs from the master's own mirror columns
    d["opp_ch_paint"] = d.opp_points_paint.astype(float)
    d["opp_fg3a"] = d.opp_fg3a.astype(float)

    viol = int((d.ch_ft + d.ch_3pt + d.pts_2s - d.team_pts).abs().gt(0).sum())
    neg = int((d.ch_np2 < 0).sum())
    per_game = d.groupby("GAME_ID").agg(n=("TEAM_ID", "size"), h=("is_home", "sum"))
    bad_pairs = int((per_game.n != 2).sum()) + int((per_game.h != 1).sum())
    for n, what in [(viol, "box identity violations"),
                    (neg, "negative np2 rows"),
                    (paint_bad, "player-summed paint mismatches"),
                    (bad_pairs, "malformed game pairings")]:
        if n:
            gaps.add("FATAL", "masters", f"{what}: {n} on season-{season} rows "
                     "— channel inputs are not trustworthy; refusing to forecast")
    d = d.sort_values(["TEAM_ID", "GAME_DATE", "GAME_ID"]).reset_index(drop=True)
    d["prior_games"] = d.groupby("TEAM_ID").cumcount()
    return d, prov


def team_state(d: pd.DataFrame, alphas: dict, season: int, gaps: Gaps) -> dict:
    """Per-team feature state for a game AFTER every played game.

    For each trended input, the future game's shift(1)-EWMA value equals the
    plain ewm(alpha, adjust=True).mean() over the team's season games to date
    (run_reval.ewma_shifted evaluated at the next row). League running means
    over strictly earlier dates = season-to-date means (every played game is
    strictly before the slate date by construction).
    """
    a_ft, a_3pt, a_paint, a_np2 = (alphas[c] for c in CHANNELS)
    spec = [
        ("raw_ft", "ch_ft", a_ft), ("raw_3pt", "ch_3pt", a_3pt),
        ("raw_paint", "ch_paint", a_paint), ("raw_np2", "ch_np2", a_np2),
        ("fta_t", "team_fta", a_ft), ("ftpct_t", "team_ft_pct", a_ft),
        ("pf_t", "team_pf", a_ft),
        ("fg3a_t", "team_fg3a", a_3pt), ("fg3m_t", "team_fg3m", a_3pt),
        ("fg3a_allow_t", "opp_fg3a", a_3pt),
        ("paint_allow_t", "opp_ch_paint", a_paint),
        ("np2_allow_t", "opp_ch_np2", a_np2),
    ]
    # opp_ch_np2: opponent's non-paint 2s allowed by this team = opp pts_2s - opp paint
    d = d.copy()
    d["opp_pts_2s"] = (d.opp_fgm - d.opp_fg3m).astype(float) * 2
    d["opp_ch_np2"] = d.opp_pts_2s - d.opp_ch_paint

    lg = {
        "lg_pf": float(d.team_pf.mean()), "lg_fta": float(d.team_fta.mean()),
        "lg_ftpct": float(d.team_ft_pct.mean()), "lg_fg3a": float(d.team_fg3a.mean()),
        "lg_fg3m": float(d.team_fg3m.mean()), "lg_ft": float(d.ch_ft.mean()),
        "lg_3pt": float(d.ch_3pt.mean()), "lg_paint": float(d.ch_paint.mean()),
        "lg_np2": float(d.ch_np2.mean()),
        "n_league_rows": int(len(d)),
    }
    state: dict = {"__league__": lg}
    for team_id, g in d.groupby("TEAM_ID", sort=False):
        g = g.sort_values(["GAME_DATE", "GAME_ID"])
        ab = g.TEAM_ABBREVIATION.iloc[-1]
        st = {"team_id": int(team_id), "abbr": ab,
              "prior_games": int(len(g)),
              "last_game_date": str(g.GAME_DATE.max().date()),
              "is_expansion_first_season": (season, ab) in EXPANSION,
              "fallback": False}
        if len(g) < MIN_PRIOR:
            if st["is_expansion_first_season"]:
                st["fallback"] = True
                st.update({"raw_ft": lg["lg_ft"], "raw_3pt": lg["lg_3pt"],
                           "raw_paint": lg["lg_paint"], "raw_np2": lg["lg_np2"],
                           "fta_t": lg["lg_fta"], "ftpct_t": lg["lg_ftpct"],
                           "pf_t": lg["lg_pf"], "fg3a_t": lg["lg_fg3a"],
                           "fg3m_t": lg["lg_fg3m"], "fg3a_allow_t": lg["lg_fg3a"],
                           "paint_allow_t": lg["lg_paint"],
                           "np2_allow_t": lg["lg_np2"]})
                gaps.add("INFO", "eligibility", f"{ab}: expansion first-season "
                         f"team with {len(g)} < {MIN_PRIOR} prior games — "
                         "league-prior fallback in force (as in run_reval.py)")
            else:
                gaps.add("WARN", "eligibility", f"{ab}: only {len(g)} prior "
                         f"season games (< {MIN_PRIOR}) and not an expansion "
                         "first season — this team is NOT forecastable "
                         "(constitution rule 2); its games will be skipped")
                st["ineligible"] = True
        else:
            for out, col, a in spec:
                st[out] = float(g[col].ewm(alpha=a, adjust=True).mean().iloc[-1])
        state[ab] = st
    return state


def structural_forecast(home: dict, away: dict, lg: dict, params: dict) -> dict | None:
    """The promoted chains (run_reval.py build_features / calibrations),
    evaluated for one future game."""
    if home.get("ineligible") or away.get("ineligible"):
        return None
    ch = {}
    for side, own, opp in (("home", home, away), ("away", away, home)):
        fg3pct_t = own["fg3m_t"] / own["fg3a_t"]
        c = {
            "ft": own["fta_t"] * (opp["pf_t"] / lg["lg_pf"]) * own["ftpct_t"],
            "3pt": own["fg3a_t"] * (opp["fg3a_allow_t"] / lg["lg_fg3a"]) * fg3pct_t * 3.0,
            "paint": own["raw_paint"] * (opp["paint_allow_t"] / lg["lg_paint"]),
            "np2": own["raw_np2"] * (opp["np2_allow_t"] / lg["lg_np2"]),
        }
        c["sum"] = sum(c[k] for k in CHANNELS)
        ch[side] = c
    am, bm = params["cal_str_margin"]
    ah, bh = params["cal_str_home"]
    aa, ba = params["cal_str_away"]
    home_score = ah + bh * ch["home"]["sum"]
    away_score = aa + ba * ch["away"]["sum"]
    margin = am + bm * (ch["home"]["sum"] - ch["away"]["sum"])
    return {
        "home_score": home_score, "away_score": away_score,
        "margin": margin,                      # the registered margin calibration
        "total": home_score + away_score,      # joint total = home_cal + away_cal
        "margin_from_scores": home_score - away_score,
        "channels_home": ch["home"], "channels_away": ch["away"],
        "any_fallback": bool(home["fallback"] or away["fallback"]),
    }


# ---------------------------------------------------------------------------
# slate discovery — odds snapshot (primary) + ref assignments (game ids, crews)
# ---------------------------------------------------------------------------

def parse_live_filename(p: Path) -> datetime | None:
    m = re.fullmatch(r"live_(\d{8}T\d{6}Z)\.json", p.name)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def latest_snapshot_before(cutoff: datetime, gaps: Gaps) -> tuple[list, datetime | None, Path | None]:
    cands = sorted(
        ((ts, p) for p in ODDS_DIR.glob("live_*.json")
         if (ts := parse_live_filename(p)) is not None and ts <= cutoff),
        key=lambda x: x[0],
    )
    if not cands:
        gaps.add("WARN", "odds", f"no live odds snapshot at or before the "
                 f"cutoff {cutoff.isoformat()} in {ODDS_DIR} — no market "
                 "lines; slate falls back to ref assignments only")
        return [], None, None
    ts, path = cands[-1]
    age_min = (cutoff - ts).total_seconds() / 60.0
    if age_min > ODDS_STALE_MIN:
        gaps.add("WARN", "odds", f"nearest prior snapshot {path.name} is "
                 f"{age_min:.0f} min before the cutoff (capture is hourly; "
                 f"> {ODDS_STALE_MIN} min = stale) — lines may be off")
    try:
        events = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        gaps.add("WARN", "odds", f"cannot parse {path.name}: {exc}")
        return [], None, None
    return events, ts, path


def market_consensus(event: dict, gaps: Gaps) -> dict:
    """Median-across-books home spread, price at that spread, and total, from
    one Odds API event. Raw per-book detail is retained for the CSV."""
    home, away = event["home_team"], event["away_team"]
    spreads, spread_prices, totals, h2h_home = [], [], [], []
    last_updates = []
    for bk in event.get("bookmakers", []):
        for mkt in bk.get("markets", []):
            if mkt.get("last_update"):
                last_updates.append(mkt["last_update"])
            if mkt["key"] == "spreads":
                for o in mkt.get("outcomes", []):
                    if o.get("name") == home and o.get("point") is not None:
                        spreads.append(float(o["point"]))
                        if o.get("price") is not None:
                            spread_prices.append(float(o["price"]))
            elif mkt["key"] == "totals":
                for o in mkt.get("outcomes", []):
                    if o.get("name") == "Over" and o.get("point") is not None:
                        totals.append(float(o["point"]))
            elif mkt["key"] == "h2h":
                for o in mkt.get("outcomes", []):
                    if o.get("name") == home and o.get("price") is not None:
                        h2h_home.append(float(o["price"]))
    out = {
        "n_books_spread": len(spreads),
        "home_spread_median": float(np.median(spreads)) if spreads else None,
        "home_spread_price_median": (float(np.median(spread_prices))
                                     if spread_prices else None),
        "total_median": float(np.median(totals)) if totals else None,
        "n_books_total": len(totals),
        "h2h_home_price_median": float(np.median(h2h_home)) if h2h_home else None,
        "books_last_update_max": max(last_updates) if last_updates else None,
        "spread_min": float(min(spreads)) if spreads else None,
        "spread_max": float(max(spreads)) if spreads else None,
    }
    if not spreads:
        gaps.add("WARN", "odds", f"{away} @ {home}: no spread outcomes in the "
                 "snapshot (market suspended?) — market_line degrades to null")
    return out


def load_ref_crews(slate_date, cutoff: datetime, gaps: Gaps) -> dict:
    """(home_abbr, away_abbr) -> {game_id, crew, capture_utc} for the slate
    date, from the latest capture at/before the cutoff."""
    if not REF_LOG.exists():
        gaps.add("WARN", "refs", f"{REF_LOG} missing — no official game_ids or "
                 "crews; game ids degrade to provisional")
        return {}
    r = pd.read_csv(REF_LOG)
    r["cap_dt"] = pd.to_datetime(r.capture_utc, format="%Y%m%dT%H%M%SZ", utc=True)
    r = r[(r.game_date == str(slate_date)) & (r.cap_dt <= cutoff)]
    if not len(r):
        gaps.add("WARN", "refs", f"no ref assignments captured for {slate_date} "
                 f"at or before the cutoff — game ids degrade to provisional")
        return {}
    out = {}
    for (h, a), g in r.groupby(["home_team", "away_team"]):
        g = g[g.cap_dt == g.cap_dt.max()]
        hab, aab = TEAMS.get(h), TEAMS.get(a)
        if hab is None or aab is None:
            gaps.add("WARN", "refs", f"unmapped team name in ref log: {h!r} / "
                     f"{a!r} — row skipped")
            continue
        gid = g.game_id.dropna().unique()
        out[(hab, aab)] = {
            "game_id": str(int(float(gid[0]))) if len(gid) else None,
            "crew": [f"{row.official_name} ({row.crew_role})"
                     for row in g.itertuples()],
            "capture_utc": g.cap_dt.max().isoformat(),
        }
    return out


def discover_slate(slate_date, cutoff: datetime, gaps: Gaps) -> tuple[list[dict], dict]:
    """Union of the odds snapshot's slate-date events and the ref-assignment
    games, with explicit notes where either side is missing."""
    events, snap_ts, snap_path = latest_snapshot_before(cutoff, gaps)
    crews = load_ref_crews(slate_date, cutoff, gaps)
    odds_prov = {
        "snapshot_file": snap_path.name if snap_path else None,
        "snapshot_ts_utc": snap_ts.isoformat() if snap_ts else None,
    }
    slate, seen = [], set()
    for ev in events:
        try:
            tip = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            gaps.add("WARN", "odds", f"event {ev.get('id')} has a bad "
                     "commence_time — skipped")
            continue
        if tip.astimezone(ET).date() != slate_date:
            continue
        hab, aab = TEAMS.get(ev["home_team"]), TEAMS.get(ev["away_team"])
        if hab is None or aab is None:
            gaps.add("WARN", "odds", f"unmapped team name in odds event: "
                     f"{ev['home_team']!r} / {ev['away_team']!r} — skipped")
            continue
        ref = crews.get((hab, aab))
        if ref is None:
            gaps.add("WARN", "refs", f"{aab} @ {hab}: no ref-assignment row — "
                     "official game_id unavailable; provisional id in use "
                     "(a real run must resolve official ids before logging)")
        slate.append({
            "home": hab, "away": aab,
            "home_name": ev["home_team"], "away_name": ev["away_team"],
            "event_time": tip,
            "api_event_id": ev.get("id"),
            "game_id": (ref or {}).get("game_id")
                       or f"PROV-{slate_date}-{aab}@{hab}",
            "game_id_provisional": (ref or {}).get("game_id") is None,
            "crew": (ref or {}).get("crew"),
            "ref_capture_utc": (ref or {}).get("capture_utc"),
            "market": market_consensus(ev, gaps),
            "odds_event": True,
        })
        seen.add((hab, aab))
    for (hab, aab), ref in crews.items():
        if (hab, aab) in seen:
            continue
        gaps.add("WARN", "slate", f"{aab} @ {hab} appears in ref assignments "
                 "but NOT in the odds snapshot (market pulled/suspended?) — "
                 "included with null market and NULL tip time; not loggable "
                 "to the chain without an event_time")
        slate.append({
            "home": hab, "away": aab, "home_name": None, "away_name": None,
            "event_time": None, "api_event_id": None,
            "game_id": ref["game_id"] or f"PROV-{slate_date}-{aab}@{hab}",
            "game_id_provisional": ref["game_id"] is None,
            "crew": ref["crew"], "ref_capture_utc": ref["capture_utc"],
            "market": {"n_books_spread": 0, "home_spread_median": None,
                       "home_spread_price_median": None, "total_median": None,
                       "n_books_total": 0, "h2h_home_price_median": None,
                       "books_last_update_max": None,
                       "spread_min": None, "spread_max": None},
            "odds_event": False,
        })
    slate.sort(key=lambda g: (g["event_time"] is None,
                              g["event_time"] or cutoff, g["home"]))
    if not slate:
        gaps.add("FATAL", "slate", f"no games found for {slate_date} in either "
                 "the odds snapshot or the ref assignments — nothing to forecast")
    return slate, odds_prov


def nearest_label(hours_to_tip: float) -> str:
    return min(CONTRACT_LABELS, key=lambda lh: abs(hours_to_tip - lh[1]))[0]


# ---------------------------------------------------------------------------
# per-game execution scope + obligation-keyed dedup (defect D-c; decision D-4,
# adopted 2026-08-06 under D022 from the O12 design:
# experiments/player_program/ops_lane/O12_PER_GAME_EXECUTION_SCOPE/)
# ---------------------------------------------------------------------------
# The single idea (O12 REPORT.md §4): the thing a run owes is an OBLIGATION —
# (game_id, decision_time_label, model_version_hash) — not an instant.
# ``forecast_cutoff`` keeps its existing, correct meaning as the as-of data
# boundary (never in the future; enforced in main()). It is no longer the
# deduplication identity: a scheduled run's cutoff is a microsecond wall
# clock, so the chain's (game_id, forecast_cutoff, model_version_hash) key
# could never collide (D-c limb 2). The chain's own DuplicateForecastError
# stays in place underneath as a second line of defence.
#
# KNOWN LIMIT (O12 REPORT.md §3/§6, finding O12-1 / proposal P3, NOT adopted
# here): decision_time_label is still assigned by nearest_label(hours_to_tip)
# from the firing instant, with no proximity bound. Until P3 (label as the
# dispatched obligation, a registered-contract change) is ruled on, a badly
# timed firing can claim a label and cause the obligation guard to refuse a
# later, correctly timed serving. The guard errs on the side of refusing —
# never double-serving.

class ObligationAlreadyServedError(Exception):
    """This (game, decision label, model version) obligation is already in the chain.

    Distinct from ``DuplicateForecastError``: that one asks "did we already
    log this exact instant", which is always false for a wall-clock cutoff.
    This one asks "did we already discharge this obligation", which is the
    question the coverage audit actually grades.
    """


class OutOfScopeError(Exception):
    """A run scoped to one game tried to log a record for a different game."""


@dataclass
class ScopeDeclaration:
    """What a scoped run deliberately did not forecast, and why.

    The COMPLETENESS RULE frozen 2026-07-31 (see the chain-write loop) says
    every slate game gets a chain record, because logging only some games
    makes the chain a filtered sample of its own slate. Per-game scope is in
    tension with that rule. This object resolves the tension by making the
    filter DECLARED rather than silent: a scoped run states its scope and
    names every game it excluded, so a later grader can tell a scoped run
    apart from a run that dropped games. It is a declaration, NOT a chain
    record, and NOT a schema change.
    """
    scoped_to_game_ids: list
    excluded_game_ids: list
    slate_date: str
    reason: str
    fired_at_utc: str
    excluded_are_other_obligations: bool = True
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scope": "per_game",
            "scoped_to_game_ids": sorted(self.scoped_to_game_ids),
            "excluded_game_ids": sorted(self.excluded_game_ids),
            "n_slate_games": len(self.scoped_to_game_ids) + len(self.excluded_game_ids),
            "slate_date": self.slate_date,
            "reason": self.reason,
            "fired_at_utc": self.fired_at_utc,
            "excluded_are_other_obligations": self.excluded_are_other_obligations,
            "notes": list(self.notes),
        }

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True),
                        encoding="utf-8")
        return path


def served_obligation_keys(records) -> set:
    """Obligation keys already discharged, read from chain records on disk.

    Works on schema /1 AND /2 records: the obligation triple is derivable
    from fields both schemas carry — no schema change was needed for it.
    """
    out: set = set()
    for r in records:
        gid, lab, mh = (r.get("game_id"), r.get("decision_time_label"),
                        r.get("model_version_hash"))
        if gid is not None and lab is not None and mh is not None:
            out.add((str(gid), str(lab), str(mh)))
    return out


def scope_slate_to_games(slate: Sequence[dict], game_ids,
                         slate_date: str, fired_at_utc: datetime, reason: str):
    """Restrict a slate to the named games and declare what was excluded.

    ``game_ids=None`` means an unscoped (whole-slate) run: the slate is
    returned unchanged and no declaration is produced, so existing behaviour
    is exactly preserved when the new option is not used.
    """
    if game_ids is None:
        return list(slate), None
    want = {str(g) for g in game_ids}
    have = {str(g["game_id"]) for g in slate}
    missing = sorted(want - have)
    kept = [g for g in slate if str(g["game_id"]) in want]
    excluded = sorted(have - want)
    decl = ScopeDeclaration(
        scoped_to_game_ids=sorted(want & have),
        excluded_game_ids=excluded,
        slate_date=slate_date,
        reason=reason,
        fired_at_utc=fired_at_utc.astimezone(timezone.utc).isoformat(),
        notes=([f"requested game_ids absent from the discovered slate: {missing}"]
               if missing else []),
    )
    return kept, decl


def obligation_guard(log_path: Path, *, game_id: str, decision_time_label: str,
                     model_version_hash: str,
                     scoped_to_game_ids=None) -> None:
    """Refuse a repeat serving of an obligation BEFORE touching the chain.

    Raises OutOfScopeError if a scoped run tries to log a game outside its
    declared scope, and ObligationAlreadyServedError if the (game_id,
    decision_time_label, model_version_hash) obligation is already
    discharged in the chain — regardless of the wall-clock forecast_cutoff.
    This wrapper only ever ADDS a refusal; it can never permit something the
    chain itself would refuse.
    """
    if scoped_to_game_ids is not None and str(game_id) not in {
            str(g) for g in scoped_to_game_ids}:
        raise OutOfScopeError(
            f"run is scoped to {sorted(map(str, scoped_to_game_ids))} but "
            f"tried to log game_id={game_id!r}"
        )
    served = served_obligation_keys(read_forecasts(log_path))
    key = (str(game_id), str(decision_time_label), str(model_version_hash))
    if key in served:
        raise ObligationAlreadyServedError(
            f"obligation already discharged: game_id={game_id!r} "
            f"decision_time_label={decision_time_label!r} under "
            f"model_version_hash={model_version_hash!r}. A second serving of "
            "the same obligation is not a new prediction; it is the same "
            "decision re-timestamped."
        )


# ---------------------------------------------------------------------------
# player layer (informational in v0)
# ---------------------------------------------------------------------------

def _norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_injuries_at_cutoff(cutoff: datetime, gaps: Gaps) -> tuple[pd.DataFrame, dict]:
    prov = {"path": str(INJURY_LOG), "capture_used": None, "rows": 0}
    if not INJURY_LOG.exists():
        gaps.add("WARN", "injuries", f"{INJURY_LOG} missing — NO availability "
                 "data; player layer reports designations as unavailable-"
                 "unknown, NOT as 'everyone available'")
        return pd.DataFrame(), prov
    inj = pd.read_csv(INJURY_LOG)
    inj["cap_dt"] = pd.to_datetime(inj.capture_utc, format="%Y%m%dT%H%M%SZ",
                                   utc=True)
    inj = inj[inj.cap_dt <= cutoff]
    if not len(inj):
        gaps.add("WARN", "injuries", "no injury capture at or before the "
                 "cutoff — designations unknown (explicitly), not 'none'")
        return pd.DataFrame(), prov
    latest_cap = inj.cap_dt.max()
    age_h = (cutoff - latest_cap).total_seconds() / 3600.0
    if age_h > 2.0:
        gaps.add("WARN", "injuries", f"latest injury capture is {age_h:.1f} h "
                 "before the cutoff (game-day cadence is hourly) — stale")
    # latest designation per (team, player) as of the cutoff — whole-row dedupe
    # (never groupby().last(), which mixes last non-null values across rows)
    inj = (inj.sort_values("cap_dt")
              .drop_duplicates(subset=["team", "player"], keep="last"))
    prov.update({"capture_used": latest_cap.isoformat(), "rows": int(len(inj))})
    return inj, prov


def player_layer(slate: list[dict], season: int, slate_date, cutoff: datetime,
                 gaps: Gaps) -> tuple[dict, dict]:
    """Identity-resolved roster + minutes EWMA(0.30) + the Phase-3 rule gate
    (O14/D022): minutes history is keyed on player_id across the season (F1);
    rosters are single-tenant per identity as of the cutoff, each entry
    recording assignment_source last_game vs designation_transfer (F2);
    designations bind by identity via the cross-season index + alias table,
    never by (franchise-name, spelling) pair (F3); an unbindable Out/Doubtful
    raises BLOCK and materialises an explicit unresolved cold-start object —
    the availability estimate fails closed (F4). Informational only in v0:
    never modifies the team forecast."""
    from entity_resolution import player_layer_resolved
    inj, inj_prov = load_injuries_at_cutoff(cutoff, gaps)
    p_all = pd.read_parquet(MASTER_PLAYER)
    p = p_all[(p_all.season == season)
              & (pd.to_datetime(p_all.game_date).dt.date < slate_date)].copy()
    p["game_date"] = pd.to_datetime(p.game_date)
    abbr_to_name = {v: k for k, v in TEAMS.items()}
    teams = sorted({g["home"] for g in slate} | {g["away"] for g in slate})
    out = player_layer_resolved(teams, p, inj, abbr_to_name, gaps,
                                p_all=p_all, season=season)
    return out, inj_prov


# ---------------------------------------------------------------------------
# per-game forecast units (D-c: each game is an independent execution unit —
# one failing game must not abort or contaminate the remaining slate)
# ---------------------------------------------------------------------------

_NULL_MARKET = {"n_books_spread": 0, "home_spread_median": None,
                "home_spread_price_median": None, "total_median": None,
                "n_books_total": 0, "h2h_home_price_median": None,
                "books_last_update_max": None,
                "spread_min": None, "spread_max": None}


def forecast_one_game(g: dict, *, state: dict, lg: dict, params: dict,
                      players: dict, cutoff: datetime, season: int,
                      gaps: Gaps) -> tuple[dict, list[dict]]:
    """Forecast ONE slate game — the independent execution unit (D-c).

    May raise on an unexpected internal failure; forecast_slate() catches
    per game so the rest of the slate is untouched. Returns (row, its
    feature-snapshot rows)."""
    home, away = g["home"], g["away"]
    hs, as_ = state.get(home), state.get(away)
    tip = g["event_time"]
    hours_to_tip = ((tip - cutoff).total_seconds() / 3600.0
                    if tip is not None else None)
    label = nearest_label(hours_to_tip) if hours_to_tip is not None else "unknown-tip"
    skip = None
    if hs is None or as_ is None:
        skip = f"no season-{season} master rows for " + \
               ", ".join(ab for ab, st in ((home, hs), (away, as_)) if st is None)
        gaps.add("WARN", "forecast", f"{away} @ {home}: {skip}")
    elif hours_to_tip is not None and hours_to_tip <= 0:
        skip = "tip already passed at the cutoff — a post-tip 'forecast' " \
               "violates the prediction contract"
        gaps.add("WARN", "forecast", f"{away} @ {home}: {skip}")
    fc = (structural_forecast(hs, as_, lg, params)
          if skip is None else None)
    if fc is None and skip is None:
        skip = "team below eligibility floor (see gaps)"
    mk = g["market"]
    row = {
        "game_id": g["game_id"], "home": home, "away": away,
        "tip_utc": tip.isoformat() if tip else None,
        "tip_et": (tip.astimezone(ET).strftime("%Y-%m-%d %H:%M")
                   if tip else "unknown"),
        "hours_to_tip": hours_to_tip, "label": label,
        "forecast": fc, "market": mk, "crew": g["crew"],
        "players": players, "skip_reason": skip,
        "game_id_provisional": g["game_id_provisional"],
        "api_event_id": g["api_event_id"],
    }
    game_snap_rows = []
    for side, st in (("home", hs), ("away", as_)):
        if st is None or st.get("ineligible"):
            continue
        game_snap_rows.append({
            "game_id": g["game_id"], "side": side, "team": st["abbr"],
            "prior_games": st["prior_games"], "fallback": st["fallback"],
            **{k: st[k] for k in ("raw_ft", "raw_3pt", "raw_paint",
                                  "raw_np2", "fta_t", "ftpct_t", "pf_t",
                                  "fg3a_t", "fg3m_t", "fg3a_allow_t",
                                  "paint_allow_t", "np2_allow_t")
               if k in st},
            "lg_pf": lg["lg_pf"], "lg_fg3a": lg["lg_fg3a"],
            "lg_paint": lg["lg_paint"], "lg_np2": lg["lg_np2"],
            "market_home_spread_median": mk["home_spread_median"],
            "market_total_median": mk["total_median"],
            "n_books_spread": mk["n_books_spread"],
            "n_out_players": (players.get(st["abbr"], {}) or {}).get("n_out"),
            "event_time": tip.isoformat() if tip else None,
            "forecast_cutoff": cutoff.isoformat(),
        })
    return row, game_snap_rows


def failure_row(g: dict, cutoff: datetime, exc: BaseException,
                players: dict) -> dict:
    """COMPLETENESS RULE: a game whose per-game unit crashed still gets a row
    (and hence a NO_FORECAST chain record) with an explicit reason — never a
    silent drop from its own slate."""
    tip = g.get("event_time")
    try:
        hours = ((tip - cutoff).total_seconds() / 3600.0
                 if tip is not None else None)
    except Exception:
        hours = None
    return {
        "game_id": g.get("game_id"), "home": g.get("home"), "away": g.get("away"),
        "tip_utc": tip.isoformat() if tip else None,
        "tip_et": (tip.astimezone(ET).strftime("%Y-%m-%d %H:%M")
                   if tip else "unknown"),
        "hours_to_tip": hours,
        "label": nearest_label(hours) if hours is not None else "unknown-tip",
        "forecast": None,
        "market": g.get("market") or dict(_NULL_MARKET),
        "crew": g.get("crew"), "players": players,
        "skip_reason": (f"unhandled per-game failure: "
                        f"{type(exc).__name__}: {exc}"),
        "game_id_provisional": bool(g.get("game_id_provisional", True)),
        "api_event_id": g.get("api_event_id"),
    }


def forecast_slate(slate: list[dict], *, state: dict, lg: dict, params: dict,
                   players: dict, cutoff: datetime, season: int,
                   gaps: Gaps) -> tuple[list[dict], list[dict]]:
    """Per-game execution scope (D-c): every game is forecast in isolation.
    One failing game degrades EXPLICITLY (WARN + NO_FORECAST row) and the
    remaining slate continues uncontaminated."""
    rows, snap_rows = [], []
    for g in slate:
        try:
            row, srows = forecast_one_game(
                g, state=state, lg=lg, params=params, players=players,
                cutoff=cutoff, season=season, gaps=gaps)
        except Exception as exc:
            gaps.add("WARN", "forecast",
                     f"{g.get('away')} @ {g.get('home')}: unhandled per-game "
                     f"failure ({type(exc).__name__}: {exc}) — game isolated; "
                     "remaining slate continues (D-c per-game execution scope)")
            row, srows = failure_row(g, cutoff, exc, players), []
        rows.append(row)
        snap_rows.extend(srows)
    return rows, snap_rows


def log_row_to_chain(r: dict, *, players: dict, cutoff: datetime,
                     model_hash: str, snapshot_hash: str, snapshot_desc: str,
                     generated_at: str, observed_time, git_head: str,
                     odds_prov: dict, live: bool, log_path: Path,
                     scoped_game_ids, gaps: Gaps) -> str:
    """Write ONE game's chain record; never raises (D-c per-game isolation).

    The obligation guard runs before every log_forecast call: a second
    serving of (game_id, decision_time_label, model_version_hash) is refused
    regardless of the wall-clock forecast_cutoff — deduplication no longer
    keys on `now` (D-c limb 2). The chain's own DuplicateForecastError stays
    underneath as a second line of defence.

    Returns 'logged' | 'skipped_obligation' | 'skipped_duplicate' | 'failed'.
    """
    try:
        obligation_guard(log_path, game_id=str(r["game_id"]),
                         decision_time_label=r["label"],
                         model_version_hash=model_hash,
                         scoped_to_game_ids=scoped_game_ids)
        # COMPLETENESS RULE (frozen 2026-07-31): every slate game gets a
        # chain record, including ones we cannot forecast. Logging only
        # successful forecasts would make the chain a filtered sample of
        # its own slate; graded later, that is survivorship selection.
        # A no-forecast record carries status + reason and null predictions.
        if r["forecast"] is None or r["tip_utc"] is None:
            reason = (r["skip_reason"] if r["forecast"] is None
                      else "no event_time — provenance incomplete")
            gaps.add("INFO", "chain", f"{r['away']} @ {r['home']}: logged as "
                     f"NO_FORECAST ({reason})")
            log_forecast(
                game_id=str(r["game_id"]),
                forecast_cutoff=cutoff,
                decision_time_label=r["label"],
                model_version_hash=model_hash,
                data_snapshot_hash=snapshot_hash,
                core_only_prediction={
                    "model": "structural_channels_v2_daily_v0",
                    "status": "NO_FORECAST",
                    "no_forecast_reason": reason,
                    "home_team": r["home"], "away_team": r["away"],
                    "margin": None, "total": None,
                    "home_score": None, "away_score": None,
                    "p_home_cover_gauss_at_cutoff": None,
                    "market_total_median_at_cutoff":
                        r["market"]["total_median"],
                    "game_id_provisional": r["game_id_provisional"],
                    "provenance": {
                        "event_time": r["tip_utc"],
                        "published_time": generated_at,
                        "observed_time": observed_time,
                        "forecast_cutoff": cutoff.isoformat(),
                        "source": SOURCE_NAME_LIVE if live else SOURCE_NAME,
                        "source_version": f"git:{git_head}",
                        "data_snapshot": snapshot_desc,
                    },
                },
                w1_extraction=None,
                market_line=(r["market"]["home_spread_median"]
                             if r["market"]["home_spread_median"] is not None
                             else None),
                log_path=log_path,
            )
            return "logged"
        f, mk = r["forecast"], r["market"]
        pl_home = players.get(r["home"], {})
        pl_away = players.get(r["away"], {})
        # frozen distribution (dist_margin_cover_v1): Gaussian(margin, SIGMA_V0);
        # P(home covers) = P(margin_true > -spread) = Phi((margin + spread)/sigma)
        sp = mk["home_spread_median"]
        p_cover = (0.5 * (1.0 + math.erf(
            (f["margin"] + sp) / (SIGMA_V0 * math.sqrt(2.0))))
            if sp is not None else None)
        core = {
            "model": "structural_channels_v2_daily_v0",
            "margin_sigma": SIGMA_V0,
            "p_home_cover_gauss_at_cutoff": (round(p_cover, 4)
                                             if p_cover is not None else None),
            "home_team": r["home"], "away_team": r["away"],
            "home_score": round(f["home_score"], 3),
            "away_score": round(f["away_score"], 3),
            "margin": round(f["margin"], 3),
            "total": round(f["total"], 3),
            "margin_from_scores": round(f["margin_from_scores"], 3),
            "channels_home": {k: round(v, 3) for k, v in f["channels_home"].items()},
            "channels_away": {k: round(v, 3) for k, v in f["channels_away"].items()},
            "any_fallback": f["any_fallback"],
            "hours_to_tip_at_cutoff": round(r["hours_to_tip"], 3),
            "player_layer_informational": {
                "note": "v0: does NOT modify the team forecast",
                "home": {k: pl_home.get(k) for k in
                         ("n_roster", "n_out", "vacated_min_ewma",
                          "sum_min_ewma_available", "n_cold_start")},
                "away": {k: pl_away.get(k) for k in
                         ("n_roster", "n_out", "vacated_min_ewma",
                          "sum_min_ewma_available", "n_cold_start")},
                "out_home": [o["player"] for o in pl_home.get("out", [])],
                "out_away": [o["player"] for o in pl_away.get("out", [])],
            },
            "market_total_median_at_cutoff": mk["total_median"],
            "referee_crew": r["crew"],
            "game_id_provisional": r["game_id_provisional"],
            "provenance": {
                "event_time": r["tip_utc"],
                "published_time": generated_at,
                "observed_time": observed_time,
                "forecast_cutoff": cutoff.isoformat(),
                "source": SOURCE_NAME_LIVE if live else SOURCE_NAME,
                "source_version": f"git:{git_head}",
                "data_snapshot": snapshot_desc,
            },
        }
        has_line = mk["home_spread_median"] is not None
        log_forecast(
            game_id=str(r["game_id"]),
            forecast_cutoff=cutoff,
            decision_time_label=r["label"],
            model_version_hash=model_hash,
            data_snapshot_hash=snapshot_hash,
            core_only_prediction=core,
            w1_extraction=None,             # W1 did not run in v0
            core_plus_w1_prediction=None,
            market_line=mk["home_spread_median"],
            market_price=mk["home_spread_price_median"] if has_line else None,
            market_book=(f"consensus:median_of_{mk['n_books_spread']}_books"
                         if has_line else None),
            market_source=(f"the_odds_api live snapshot "
                           f"{odds_prov.get('snapshot_file')}@"
                           f"{odds_prov.get('snapshot_ts_utc')} "
                           "(nearest prior to cutoff); home spread, "
                           "median across books"
                           if has_line else None),
            predicted_close=None,
            intended_bet_decision="not_applicable",
            paper_stake=0.0,
            log_path=log_path,
        )
        return "logged"
    except ObligationAlreadyServedError:
        gaps.add("INFO", "chain", f"{r['away']} @ {r['home']}: obligation "
                 f"(game {r['game_id']}, {r['label']}, this model version) "
                 "already served — refused by the obligation guard (D-c: "
                 "dedup no longer keys on the wall-clock cutoff); a second "
                 "serving is the same decision re-timestamped, not a new "
                 "prediction")
        return "skipped_obligation"
    except DuplicateForecastError:
        gaps.add("INFO", "chain", f"{r['away']} @ {r['home']}: already "
                 "logged at this (game, cutoff, model) — duplicate "
                 "refused by the chain, skipped (re-logging a "
                 "prospective prediction is never a silent overwrite)")
        return "skipped_duplicate"
    except Exception as exc:
        gaps.add("WARN", "chain", f"{r['away']} @ {r['home']}: chain write "
                 f"failed ({type(exc).__name__}: {exc}) — game isolated; "
                 "remaining slate continues (D-c per-game execution scope)")
        return "failed"


# ---------------------------------------------------------------------------
# outputs
# ---------------------------------------------------------------------------

def fmt_spread(v):
    return "n/a" if v is None else f"{v:+.1f}"


def build_report(run: dict, rows: list[dict], gaps: Gaps, chain_note: str) -> str:
    L = []
    L.append("# Daily forecast — DRY RUN (scratch chain; NOT the regime-D log)")
    L.append("")
    L.append(f"*Generated {run['generated_at']} by `daily_forecast.py` (v0). "
             f"Slate date {run['slate_date']} (ET); forecast cutoff "
             f"{run['forecast_cutoff']}. Model hash `{run['model_version_hash'][:16]}…`; "
             f"data snapshot hash `{run['data_snapshot_hash'][:16]}…`; code "
             f"`git:{run['source_version'][:12]}`. Team model: promoted "
             f"structural channels ({SOURCE_EXPERIMENT}); player layer "
             "informational only — it does not modify the team forecast.*")
    L.append("")
    L.append("**This file is engineering output. The records behind it were "
             "written ONLY to `experiments/forecast_dryrun/scratch_chain.jsonl`. "
             "The official regime-D clock starts with the first record of "
             "`forecasts/forecast_log.jsonl`, which this job refuses to touch.**")
    L.append("")
    L.append("## Slate — model vs market")
    L.append("")
    L.append("| Game (away @ home) | Tip (ET) | Label | Model H | Model A | "
             "Model margin (H−A) | Market home spread | Model total | "
             "Market total | Edge vs spread | Edge vs total |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        mk = r["market"]
        sp = mk["home_spread_median"]
        tt = mk["total_median"]
        if r["forecast"] is None:
            L.append(f"| {r['away']} @ {r['home']} | {r['tip_et']} | "
                     f"{r['label']} | — | — | — | {fmt_spread(sp)} | — | "
                     f"{tt if tt is not None else 'n/a'} | — | — | (no forecast: "
                     f"{r['skip_reason']}) |")
            continue
        f = r["forecast"]
        edge_sp = (f["margin"] + sp) if sp is not None else None
        edge_tt = (f["total"] - tt) if tt is not None else None
        e_sp = "n/a" if edge_sp is None else f"{edge_sp:+.1f}"
        e_tt = "n/a" if edge_tt is None else f"{edge_tt:+.1f}"
        mk_sp = fmt_spread(sp) + (f" ({mk['n_books_spread']} bks)"
                                  if sp is not None else "")
        L.append(
            f"| {r['away']} @ {r['home']} | {r['tip_et']} | {r['label']} "
            f"| {f['home_score']:.1f} | {f['away_score']:.1f} "
            f"| {f['margin']:+.1f} | {mk_sp} | {f['total']:.1f} "
            f"| {tt if tt is not None else 'n/a'} | {e_sp} | {e_tt} |"
        )
    L.append("")
    L.append("*Market home spread is quoted book-style (negative = home "
             "favored); market-implied margin = −spread. Edge vs spread = "
             "model margin − market-implied margin. Both edges are "
             "informational — no betting layer ran (`not_applicable`, stake 0).*")
    L.append("")
    L.append("## Player layer (informational — does not modify the team forecast)")
    L.append("")
    for r in rows:
        for side in ("away", "home"):
            ab = r[side]
            pl = r["players"].get(ab)
            if pl is None or pl.get("unknown_roster"):
                L.append(f"- **{ab}**: roster unknown (see gaps)")
                continue
            outs = ", ".join(
                f"{o['player']} ({o['min_ewma']:.1f} min EWMA)" if o["min_ewma"]
                is not None else f"{o['player']} (no played games)"
                for o in pl["out"]) or "none"
            if not pl.get("availability_data", True):
                outs = "designations UNKNOWN (no injury capture at cutoff — " \
                       "not the same as 'no one out')"
            q = {k: v for k, v in pl["designations_counts"].items() if k != "Out"}
            long_absent = [f"{r['player']} ({r['status']}, last rostered "
                           f"{r['last_rostered']})" for r in pl.get("report_only", [])
                           if r["in_season_history"]]
            L.append(f"- **{ab}** — roster {pl['n_roster']} (last {RECENCY_GAMES} "
                     f"games through {pl['roster_last_game']}), OUT {pl['n_out']} "
                     f"(vacated {pl['vacated_min_ewma']:.1f} EWMA min): {outs}. "
                     f"Other designations: {q if q else 'none'}. "
                     f"Available min-EWMA sum {pl['sum_min_ewma_available']:.1f}"
                     + (f"; cold-start {pl['n_cold_start']}" if pl["n_cold_start"] else "")
                     + (f"; long-term absent (report-listed, outside recency "
                        f"roster): {'; '.join(long_absent)}" if long_absent else "")
                     + (f"; UNMATCHED report rows: {pl['unmatched_injury_rows']}"
                        if pl["unmatched_injury_rows"] else "") + ".")
        crew = r.get("crew")
        L.append(f"  - crew ({r['away']} @ {r['home']}): "
                 + ("; ".join(crew) if crew else "not captured") + "")
    L.append("")
    L.append("## Degradations & notes (no-imputation rule: explicit, never silent)")
    L.append("")
    if gaps.items:
        for g in gaps.items:
            L.append(f"- **{g['severity']}** [{g['component']}] {g['message']}")
    else:
        L.append("- none")
    L.append("")
    L.append("## Chain")
    L.append("")
    L.append(f"- {chain_note}")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--slate-date", default=None,
                    help="ET date of the slate (YYYY-MM-DD); default today ET")
    ap.add_argument("--cutoff", default=None,
                    help="forecast cutoff ISO timestamp; default now (UTC). "
                    "Only data observed at/before this instant is used.")
    ap.add_argument("--live", action="store_true",
                    help="write to the OFFICIAL forecast log (forecasts/"
                         "forecast_log.jsonl). Requires the freeze-v0 approval "
                         "marker; the first record starts regime D. Scheduled "
                         "tasks pass this; bare runs stay in the scratch chain.")
    ap.add_argument("--no-log", action="store_true",
                    help="compute + write CSV/report, skip scratch-chain writes")
    ap.add_argument("--game-id", action="append", dest="game_ids", default=None,
                    metavar="GAME_ID",
                    help="scope this run to the named game_id (repeatable). "
                         "Per-game execution scope (defect D-c, decision D-4): "
                         "the slate is restricted to these games and every "
                         "excluded game is DECLARED in scope_declaration.json "
                         "+ the manifest, so a scoped run is distinguishable "
                         "from a run that silently dropped games "
                         "(COMPLETENESS RULE honoured by declaration).")
    args = ap.parse_args()

    gaps = Gaps()
    now = datetime.now(timezone.utc)
    cutoff = (datetime.fromisoformat(args.cutoff.replace("Z", "+00:00"))
              if args.cutoff else now)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    cutoff = cutoff.astimezone(timezone.utc)
    if cutoff > now + timedelta(seconds=5):
        sys.exit("REFUSED: a forecast cutoff in the future would claim "
                 "information that does not exist yet.")
    slate_date = (datetime.strptime(args.slate_date, "%Y-%m-%d").date()
                  if args.slate_date else now.astimezone(ET).date())
    season = slate_date.year

    if args.live:
        if not FREEZE_V0_APPROVED:
            sys.exit("REFUSED: --live requires the freeze-v0 approval marker "
                     "(FREEZE_V0_APPROVED). See project_docs/FREEZE_PROPOSAL_v0.md.")
        log_path = DEFAULT_FORECAST_LOG
        log_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        log_path = _guard_scratch_path(SCRATCH_CHAIN)
    DRYRUN_DIR.mkdir(parents=True, exist_ok=True)

    git_head = read_git_head(REPO, gaps)
    params = load_frozen_params()

    print(f"slate date {slate_date} (ET) | season {season} | cutoff "
          f"{cutoff.isoformat()} | {'OFFICIAL chain' if args.live else 'scratch chain'} "
          f"{log_path}")

    # ---- inputs -----------------------------------------------------------
    d, masters_prov = build_channel_rows(season, slate_date, gaps)
    if gaps.fatal():
        return 1
    state = team_state(d, params["alphas"], season, gaps)
    lg = state["__league__"]
    slate, odds_prov = discover_slate(slate_date, cutoff, gaps)
    if gaps.fatal():
        return 1

    # ---- per-game execution scope (D-c adoption, decision D-4) ------------
    slate, scope_decl = scope_slate_to_games(
        slate, args.game_ids, str(slate_date), now,
        reason="--game-id per-game execution scope (defect D-c, decision D-4)")
    if scope_decl is not None:
        if not slate:
            gaps.add("FATAL", "scope", "no requested --game-id is present in "
                     f"the discovered slate (requested {args.game_ids}); "
                     "nothing to forecast")
            return 1
        decl_path = DRYRUN_DIR / "scope_declaration.json"
        scope_decl.write(decl_path)
        gaps.add("INFO", "scope", "run scoped to game_ids "
                 f"{sorted(scope_decl.scoped_to_game_ids)}; "
                 f"{len(scope_decl.excluded_game_ids)} slate game(s) excluded "
                 f"— scope DECLARED in {decl_path.name} and the manifest "
                 "(COMPLETENESS RULE honoured by declaration, not evaded)")

    players, inj_prov = player_layer(slate, season, slate_date, cutoff, gaps)

    # per-slate-team trend staleness (a long schedule gap is legitimate, but
    # the reader must know the trend state is that old)
    for ab in sorted({g["home"] for g in slate} | {g["away"] for g in slate}):
        st = state.get(ab)
        if st is None or "last_game_date" not in st:
            continue
        days = (slate_date
                - datetime.strptime(st["last_game_date"], "%Y-%m-%d").date()).days
        if days > 4:
            gaps.add("INFO", "trend-staleness", f"{ab} last played "
                     f"{st['last_game_date']} ({days} days before the slate) — "
                     "trend features are that old (schedule gap, not a data "
                     "failure: masters are current through yesterday)")

    # ---- frozen model config hash ----------------------------------------
    model_config = {
        "model": "structural_channels_v2_daily_v0",
        "purpose": "daily forecast job dry-run (engineering, not an experiment)",
        "source_experiment": SOURCE_EXPERIMENT,
        "alphas": params["alphas"],
        "calibration": {
            "str_margin": params["cal_str_margin"],
            "str_home": params["cal_str_home"],
            "str_away": params["cal_str_away"],
            "fit_window": "2021-2023 train years only (as recorded in "
                          "experiments/channel_reval/run_summary.json)",
            "n_train_games": params["cal_n_train_games"],
        },
        "min_prior_games": MIN_PRIOR,
        "expansion_fallback": sorted(f"{s}-{a}" for s, a in EXPANSION),
        "player_layer": {
            "mode": "informational-only (v0): does not modify the team forecast",
            "minutes_ewma_alpha": MINUTES_ALPHA,
            "recency_roster_games": RECENCY_GAMES,
            "availability_gate": "latest captured official designation Out at "
                                 "the cutoff => player excluded "
                                 "(MINUTES_MODEL_SPEC Phase 3 rule gate)",
        },
        "code_git_head": git_head,
    }
    model_hash = hash_model_config(model_config)

    # ---- per-game forecasts (each game an independent execution unit) -----
    rows, snap_rows = forecast_slate(
        slate, state=state, lg=lg, params=params, players=players,
        cutoff=cutoff, season=season, gaps=gaps)

    # ---- data snapshot hash + description --------------------------------
    snap_df = pd.DataFrame(snap_rows)
    snapshot_hash = (hash_dataframe(snap_df) if len(snap_df)
                     else hash_dataframe(pd.DataFrame({"empty": []})))
    snapshot_desc = (
        f"masters {season} through {masters_prov.get('latest_game_used')} "
        f"({masters_prov.get('season_rows_used')} team-rows, observed "
        f"{masters_prov.get('master_team_max_observed_time')}); odds "
        f"{odds_prov.get('snapshot_file')}@{odds_prov.get('snapshot_ts_utc')}; "
        f"injuries capture {inj_prov.get('capture_used')} "
        f"({inj_prov.get('rows')} designations); refs per assignments_log at "
        f"slate date; feature rows hashed: {len(snap_df)}"
    )

    generated_at = datetime.now(timezone.utc).isoformat()
    observed_times = [v for v in [
        masters_prov.get("master_team_max_observed_time"),
        odds_prov.get("snapshot_ts_utc"), inj_prov.get("capture_used"),
    ] if v]
    observed_time = max(observed_times) if observed_times else None

    # ---- chain writes ------------------------------------------------------
    # Per-game execution scope (D-c): every game's record is written in
    # isolation via log_row_to_chain(); one failing write never aborts the
    # remaining slate, and the obligation guard replaces wall-clock dedup.
    n_logged = n_skipped = n_failed = 0
    if args.no_log:
        chain_note = "chain writes skipped (--no-log)"
    else:
        for r in rows:
            status = log_row_to_chain(
                r, players=players, cutoff=cutoff, model_hash=model_hash,
                snapshot_hash=snapshot_hash, snapshot_desc=snapshot_desc,
                generated_at=generated_at, observed_time=observed_time,
                git_head=git_head, odds_prov=odds_prov, live=args.live,
                log_path=log_path, scoped_game_ids=args.game_ids, gaps=gaps)
            if status == "logged":
                n_logged += 1
            elif status in ("skipped_obligation", "skipped_duplicate"):
                n_skipped += 1
            else:
                n_failed += 1
        rep = verify_chain(log_path)
        which = "OFFICIAL" if args.live else "scratch"
        chain_note = (f"{which} chain verified ({log_path.name}): ok={rep.ok}, "
                      f"n_records={rep.n_records}, tip_sha256={rep.tip_sha256} — record "
                      "these two values out of band; tail truncation is only "
                      "detectable against an external anchor")
        if not rep.ok:
            gaps.add("FATAL", "chain", f"scratch chain FAILED verification at "
                     f"record {rep.first_bad_index}: {rep.reason}")
    print(chain_note)

    # ---- CSV --------------------------------------------------------------
    csv_rows = []
    for r in rows:
        f, mk = r["forecast"], r["market"]
        pl_h = players.get(r["home"], {}) or {}
        pl_a = players.get(r["away"], {}) or {}
        sp = mk["home_spread_median"]
        csv_rows.append({
            "game_id": r["game_id"],
            "game_id_provisional": r["game_id_provisional"],
            "away": r["away"], "home": r["home"],
            "tip_et": r["tip_et"], "event_time_utc": r["tip_utc"],
            "forecast_cutoff_utc": cutoff.isoformat(),
            "decision_time_label": r["label"],
            "hours_to_tip_at_cutoff": (round(r["hours_to_tip"], 3)
                                       if r["hours_to_tip"] is not None else None),
            "pred_home_score": None if f is None else round(f["home_score"], 2),
            "pred_away_score": None if f is None else round(f["away_score"], 2),
            "pred_margin": None if f is None else round(f["margin"], 2),
            "pred_total": None if f is None else round(f["total"], 2),
            "pred_margin_from_scores": None if f is None else round(f["margin_from_scores"], 2),
            "market_home_spread_median": sp,
            "market_implied_margin": None if sp is None else -sp,
            "market_spread_price_median": mk["home_spread_price_median"],
            "market_spread_n_books": mk["n_books_spread"],
            "market_spread_range": (None if sp is None else
                                    f"{mk['spread_min']}..{mk['spread_max']}"),
            "market_total_median": mk["total_median"],
            "market_h2h_home_price_median": mk["h2h_home_price_median"],
            "edge_margin_vs_market": (None if f is None or sp is None
                                      else round(f["margin"] + sp, 2)),
            "edge_total_vs_market": (None if f is None or mk["total_median"] is None
                                     else round(f["total"] - mk["total_median"], 2)),
            "home_n_out": pl_h.get("n_out"), "away_n_out": pl_a.get("n_out"),
            "home_out_players": "; ".join(o["player"] for o in pl_h.get("out", [])),
            "away_out_players": "; ".join(o["player"] for o in pl_a.get("out", [])),
            "home_vacated_min_ewma": pl_h.get("vacated_min_ewma"),
            "away_vacated_min_ewma": pl_a.get("vacated_min_ewma"),
            "referee_crew": "; ".join(r["crew"]) if r["crew"] else None,
            "skip_reason": r["skip_reason"],
            "event_time": r["tip_utc"],
            "published_time": generated_at,
            "observed_time": observed_time,
            "source": SOURCE_NAME,
            "source_version": f"git:{git_head}",
            "model_version_hash": model_hash,
            "data_snapshot_hash": snapshot_hash,
            "data_snapshot_description": snapshot_desc,
        })
    csv_path = DRYRUN_DIR / "forecast_today.csv"
    pd.DataFrame(csv_rows).to_csv(csv_path, index=False)
    if len(snap_df):
        snap_df.to_csv(DRYRUN_DIR / "feature_snapshot.csv", index=False)

    # ---- manifest + report ------------------------------------------------
    run_meta = {
        "generated_at": generated_at, "slate_date": str(slate_date),
        "forecast_cutoff": cutoff.isoformat(),
        "model_version_hash": model_hash, "data_snapshot_hash": snapshot_hash,
        "source_version": git_head,
    }
    manifest = {
        **run_meta,
        "source": SOURCE_NAME,
        "model_config": model_config,
        "inputs": {"masters": masters_prov, "odds": odds_prov,
                   "injuries": inj_prov,
                   "league_means": {k: lg[k] for k in
                                    ("lg_pf", "lg_fg3a", "lg_paint", "lg_np2",
                                     "n_league_rows")}},
        "chain": {"path": str(log_path), "n_logged_this_run": n_logged,
                  "n_skipped_already_served": n_skipped,
                  "n_failed_writes": n_failed, "note": chain_note},
        "scope": (scope_decl.to_dict() if scope_decl is not None
                  else {"scope": "whole_slate"}),
        "gaps": gaps.items,
        "snapshot_description": snapshot_desc,
    }
    (DRYRUN_DIR / "snapshot_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    report = build_report(run_meta, rows, gaps, chain_note)
    (DRYRUN_DIR / "REPORT.md").write_text(report, encoding="utf-8")

    print(f"\nwrote {csv_path}")
    print(f"wrote {DRYRUN_DIR / 'REPORT.md'}, feature_snapshot.csv, "
          f"snapshot_manifest.json")
    print(f"chain: {n_logged} logged, {n_skipped} already-served refused "
          f"(obligation-keyed dedup, D-c), {n_failed} failed writes")

    # console slate table
    print("\n== slate ==")
    for r in rows:
        f, mk = r["forecast"], r["market"]
        if f is None:
            print(f"{r['away']:>3} @ {r['home']:<3} {r['tip_et']} — no forecast: "
                  f"{r['skip_reason']}")
            continue
        sp = mk["home_spread_median"]
        print(f"{r['away']:>3} @ {r['home']:<3} tip {r['tip_et']} ET [{r['label']}] "
              f"H {f['home_score']:.1f} A {f['away_score']:.1f} "
              f"margin {f['margin']:+.1f} total {f['total']:.1f} | market "
              f"spread {fmt_spread(sp)} total {mk['total_median']}")
    return 1 if gaps.fatal() else 0


if __name__ == "__main__":
    sys.exit(main())
