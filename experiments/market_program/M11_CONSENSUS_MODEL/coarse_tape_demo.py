"""M11_CONSENSUS_MODEL -- coarse-tape (T2) demo.

Runs the SAME machinery in consensus.py against a small, fixed sample of
REAL bytes from data/drive_masters/master_odds.csv and data/masters/
master_team.csv in the live main worktree (read-only; this node never
writes there). Demonstrates the no-vig / consensus / residual machinery
against real-shaped data while staying inside the permitted use enumeration.

m00_use_class: M00-U2 (Vig structure and no-vig calibration against
realized outcomes, unknown-time).
Caveat text (verbatim, TAXONOMY.json final_state_archive_ruling.
permitted_uses[1].caveat_text, sha256
39b8dbde2fc3407e5563752775c18e61f161946b216cbd0194c8d0c110997e7b):
"Calibration is of a snapshot whose capture time is vendor-asserted and
unwitnessed (P2B: CUTOFF_UNPROVEN). Results characterize an unknown-time
pregame price level and must not be read as closing-line calibration,
opening-line calibration, or calibration at T-64 minutes. No CLV, timing,
or line-movement inference may be built on this result."

What this demo IS: a bounded descriptive check that the preregistered
no-vig method, applied to a real (T2) spread market, produces consensus
probabilities that track realized ATS (against-the-spread) outcomes in the
right direction, at unknown-time, spread market only. Realized outcome is
"did the priced team cover the spread" -- computed from real final margins
-- NOT "did the team win the game", which would conflate a spread market
with a moneyline market (a methodology error this script avoids).

What this demo is NOT: a benchmark, a timing/CLV/stale-line claim, a
predictive-model feature, or a HISTORICALLY_PROFITABLE claim. It never
touches game outcomes that are not from data/masters/master_team.csv game
results (per the C.1 subordination ruling: outcome labels come from game
results, never from the odds archive itself).

Scope discipline: this script samples a FIXED, small set of games (capped
below) rather than processing the full 20,004-row archive -- the mandate
calls for "a demo," and the live main worktree is read under a
headers/samples constraint. Every figure below is reproducible by rerunning
this script; nothing is hand-typed.
"""
from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import consensus as C

LIVE_ROOT = "C:/Users/jgallagher/wnba-betting-model"
ODDS_PATH = os.path.join(LIVE_ROOT, "data", "drive_masters", "master_odds.csv")
TEAM_PATH = os.path.join(LIVE_ROOT, "data", "masters", "master_team.csv")

MAX_GAMES = 60          # fixed cap: this is a demo, not a backtest

M00_U2_CAVEAT_TEXT = (
    "Calibration is of a snapshot whose capture time is vendor-asserted and "
    "unwitnessed (P2B: CUTOFF_UNPROVEN). Results characterize an "
    "unknown-time pregame price level and must not be read as "
    "closing-line calibration, opening-line calibration, or calibration at "
    "T\u221264 minutes. No CLV, timing, or line-movement inference may be "
    "built on this result."
)
M00_U2_CAVEAT_SHA256 = \
    "39b8dbde2fc3407e5563752775c18e61f161946b216cbd0194c8d0c110997e7b"

# Frozen WNBA franchise name <-> abbreviation map, built for this join only
# (small, stable, public information -- not derived from either master
# file's own labeling so it cannot silently absorb an archive convention).
TEAM_ABBR = {
    "Las Vegas Aces": "LVA", "Phoenix Mercury": "PHO",
    "Chicago Sky": "CHI", "Minnesota Lynx": "MIN",
    "Seattle Storm": "SEA", "Connecticut Sun": "CON",
    "New York Liberty": "NYL", "Indiana Fever": "IND",
    "Atlanta Dream": "ATL", "Washington Mystics": "WAS",
    "Dallas Wings": "DAL", "Los Angeles Sparks": "LAS",
    "Golden State Valkyries": "GSV",
}
# Some seasons use PHX instead of PHO in master_team.csv; accept both.
TEAM_ABBR_ALIASES = {"PHO": {"PHO", "PHX"}}


def _abbr_matches(name, abbr):
    canon = TEAM_ABBR.get(name)
    if canon is None:
        return False
    if abbr == canon:
        return True
    return abbr in TEAM_ABBR_ALIASES.get(canon, set())


def verify_caveat_hash():
    measured = C.sha256_hex(M00_U2_CAVEAT_TEXT)
    return measured, measured == M00_U2_CAVEAT_SHA256


def load_odds_rows(path, cap_games):
    """Read master_odds.csv, group by game_id, stop once cap_games distinct
    game_ids with a two-sided price on >=1 book have been collected. Ordered
    by first appearance in the file (file is not re-sorted)."""
    by_game = {}
    order = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gid = row["game_id"]
            if gid not in by_game:
                if len(order) >= cap_games:
                    # still collect rows for games already started
                    if gid not in by_game:
                        continue
                order.append(gid)
                by_game[gid] = []
            by_game[gid].append(row)
    # keep only the first cap_games distinct game_ids actually captured
    keep = order[:cap_games]
    return {gid: by_game[gid] for gid in keep}


def load_team_results(path, game_ids):
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["game_id"] in game_ids and row.get("is_home") == "1":
                out[row["game_id"]] = row
    return out


def build_book_pairs(rows):
    """rows: all master_odds rows for one game_id. Returns
    {bookmaker: {"home": row, "away": row}} keeping the FIRST snapshot seen
    per side per book (deterministic: file order)."""
    home_team = rows[0]["home_team"]
    away_team = rows[0]["away_team"]
    pairs = {}
    for r in rows:
        bm = r["bookmaker_key"]
        side = "home" if r["team"] == home_team else (
            "away" if r["team"] == away_team else None)
        if side is None:
            continue
        pairs.setdefault(bm, {})
        pairs[bm].setdefault(side, r)
    complete = {bm: v for bm, v in pairs.items()
                if "home" in v and "away" in v}
    return complete, home_team, away_team


def run_demo(odds_path=ODDS_PATH, team_path=TEAM_PATH, max_games=MAX_GAMES,
             write_json=True):
    caveat_measured, caveat_ok = verify_caveat_hash()
    if not os.path.isdir(os.path.join(LIVE_ROOT, "data", "drive_masters")):
        return {
            "schema": "market_program/M11/coarse_tape_demo/1",
            "status": "SKIPPED_LIVE_WORKTREE_ABSENT",
            "epistemic_status": C.EPISTEMIC_STATUS_LINE,
        }

    game_rows = load_odds_rows(odds_path, max_games)
    game_ids = set(game_rows)
    team_rows = load_team_results(team_path, game_ids)

    per_game = []
    for gid, rows in game_rows.items():
        pairs, home_team, away_team = build_book_pairs(rows)
        if len(pairs) < 1:
            continue
        tr = team_rows.get(gid)
        if tr is None or not _abbr_matches(home_team, tr["team_abbreviation"]):
            continue     # unresolved / unmatched -- excluded, not patched
        try:
            margin = int(tr["pts"]) - int(tr["opp_pts"])
        except (KeyError, ValueError):
            continue

        quotes = []
        spreads_home = []
        for bm, sides in pairs.items():
            home_row, away_row = sides["home"], sides["away"]
            try:
                home_price = int(home_row["odds_price"])
                away_price = int(away_row["odds_price"])
                home_spread = float(home_row["odds_spread"])
            except ValueError:
                continue
            spreads_home.append(home_spread)
            quotes.append({
                **C.make_quote(
                    bookmaker=bm, price=home_price, capture_ts=None,
                    tier="T2", vendor_ts=home_row["odds_snapshot_timestamp"],
                    vendor_ts_semantics="unknown_unverified",
                    market="spread", outcome="HOME", point=home_spread),
                "capture_ts": home_row["odds_snapshot_timestamp"],
                "opposite_price": away_price,
            })
        if not quotes:
            continue

        cons = C.consensus_fair_value(quotes, game_id=gid)
        avg_spread_home = sum(spreads_home) / len(spreads_home)
        cover_margin = margin + avg_spread_home
        if cover_margin > 0:
            realized_cover = 1
        elif cover_margin < 0:
            realized_cover = 0
        else:
            realized_cover = None    # PUSH -- excluded from calibration, not patched

        per_game.append({
            "game_id": gid, "home_team": home_team, "away_team": away_team,
            "n_books": len(quotes),
            "avg_spread_home": avg_spread_home,
            "consensus_fair_prob_home_covers": cons["consensus_fair_prob"],
            "uncertainty_std": cons["uncertainty_std"],
            "disagreement_score": cons["disagreement_score"],
            "realized_margin": margin,
            "realized_cover_home": realized_cover,
            "consensus_object": cons,
        })

    calibratable = [g for g in per_game if g["realized_cover_home"] is not None
                    and g["consensus_fair_prob_home_covers"] is not None]
    n_push_excluded = sum(1 for g in per_game
                           if g["realized_cover_home"] is None)

    calibration_buckets = {}
    for g in calibratable:
        p = g["consensus_fair_prob_home_covers"]
        bucket = "LOW(<0.45)" if p < 0.45 else (
            "MID(0.45-0.55)" if p <= 0.55 else "HIGH(>0.55)")
        b = calibration_buckets.setdefault(
            bucket, {"n": 0, "n_covered": 0, "mean_pred": 0.0})
        b["n"] += 1
        b["n_covered"] += g["realized_cover_home"]
        b["mean_pred"] += p
    for b in calibration_buckets.values():
        b["realized_cover_rate"] = b["n_covered"] / b["n"] if b["n"] else None
        b["mean_pred"] = b["mean_pred"] / b["n"] if b["n"] else None

    brier = None
    if calibratable:
        brier = sum((g["consensus_fair_prob_home_covers"]
                      - g["realized_cover_home"]) ** 2
                     for g in calibratable) / len(calibratable)

    result = {
        "schema": "market_program/M11/coarse_tape_demo/1",
        "epistemic_status": C.EPISTEMIC_STATUS_LINE,
        "not_a_fundamental_prediction": True,
        "evidence_ladder_labels_held": [],
        "m00_use_class": "M00-U2",
        "m00_caveat_text_verbatim": M00_U2_CAVEAT_TEXT,
        "m00_caveat_sha256_expected": M00_U2_CAVEAT_SHA256,
        "m00_caveat_sha256_measured": caveat_measured,
        "m00_caveat_hash_match": caveat_ok,
        "vig_method": C.PREREGISTERED_VIG_METHOD,
        "vig_method_preregistration_hash": C.PREREGISTRATION_HASH,
        "source_files": {
            "odds": "data/drive_masters/master_odds.csv (T2, D016/P2B "
                    "CUTOFF_UNPROVEN, never relitigated)",
            "outcomes": "data/masters/master_team.csv (real game results, "
                        "not the odds archive; per C.1 subordination "
                        "ruling item 1)",
        },
        "sampling": {
            "max_games_cap": max_games,
            "n_games_sampled_from_odds_file": len(game_rows),
            "n_games_with_resolvable_book_pairs_and_result": len(per_game),
            "n_games_push_excluded_from_calibration": n_push_excluded,
            "n_games_used_in_calibration": len(calibratable),
        },
        "calibration_buckets_of_consensus_prob_home_covers_spread": calibration_buckets,
        "brier_score": brier,
        "per_game": per_game,
        "prohibited_uses_not_touched": [
            "No timing, CLV, closing-line, or stale-window claim is made.",
            "No use of this archive as a feature or benchmark in any "
            "predictive model.",
            "odds_snapshot_timestamp is treated as vendor-asserted "
            "(channel VENDOR_ASSERTED), never as witnessed.",
        ],
    }
    result["result_hash"] = C.sha256_hex(C.canonical_json(
        {k: v for k, v in result.items() if k != "result_hash"}))

    if write_json:
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "demo_output.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True)
    return result


if __name__ == "__main__":
    r = run_demo()
    print(json.dumps({k: v for k, v in r.items() if k not in
                       ("per_game",)}, indent=2, sort_keys=True))
