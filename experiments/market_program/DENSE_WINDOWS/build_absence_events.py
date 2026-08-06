#!/usr/bin/env python3
"""M00 lane / Track A (DENSE_WINDOWS) — high-value-absence event list, design+build only.

Builds the ranked list of "top-minutes player did not play after playing the
prior game" events, 2022-2026, from OWNED data only:

    - data/masters/master_player.parquet   (LIVE MAIN WORKTREE, READ-ONLY)

No network calls. No writes to the live main worktree — this script only reads
it and writes its outputs under this track's own directory
(experiments/market_program/DENSE_WINDOWS/ in this worktree).

Definition of an "absence event":
    For a given player P, order every row (played or DNP) chronologically by
    (game_date, game_id). For consecutive rows i-1 -> i:
      - row i-1 is a PLAYED game (minutes not null, dnp_reason null)
      - row i is an ABSENCE (dnp_reason not null, OR minutes is null/0)
      - the player's minutes-EWMA *as of row i-1* is >= MINUTES_EWMA_THRESHOLD
    -> emit one event keyed on row i (the game the player missed), carrying
       the team and minutes-share context from row i-1 (the prior, played game).

Minutes-EWMA: exponentially weighted mean of `minutes` over the player's own
played-game sequence (span=EWMA_SPAN games, i.e. alpha = 2/(span+1)), updated
only on played games (DNP games do not update it — the whole point is "how
many minutes was this player playing before the absence").

Ranking: descending by minutes-EWMA at the prior game (proxy for "how central
was this player to the team's rotation"), with team_minutes_share (prior-game
player minutes / prior-game team total minutes) reported alongside as a
secondary, more directly interpretable quantity. Ties broken by game_date.

Amendment-4 / M00 note: this list touches ONLY the master_player artifact
(fundamental gamelog data, not any odds archive). It carries no m00_use_class
because it makes no market-archive claim of any kind; it is pure event
discovery for a not-yet-executed prospective (T1, via live Odds API) capture.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

TRACK_ROOT = Path(__file__).resolve().parent
LIVE_MAIN_WORKTREE = Path("C:/Users/jgallagher/wnba-betting-model")  # READ-ONLY for this track
MASTER_PLAYER = LIVE_MAIN_WORKTREE / "data" / "masters" / "master_player.parquet"

MINUTES_EWMA_THRESHOLD_DEFAULT = 28.0  # minutes/game; "top-minutes / rotation-anchor" cut
EWMA_SPAN_DEFAULT = 10  # games
SEASON_MIN = 2022
SEASON_MAX = 2026


def compute_events(
    master_player_path: Path = MASTER_PLAYER,
    ewma_threshold: float = MINUTES_EWMA_THRESHOLD_DEFAULT,
    ewma_span: int = EWMA_SPAN_DEFAULT,
    season_min: int = SEASON_MIN,
    season_max: int = SEASON_MAX,
) -> pd.DataFrame:
    if not master_player_path.exists():
        raise FileNotFoundError(f"master_player parquet not found (read-only source): {master_player_path}")

    df = pd.read_parquet(master_player_path)
    df = df[(df["season"] >= season_min) & (df["season"] <= season_max)].copy()

    # played flag: has real minutes, no DNP reason
    df["played"] = df["dnp_reason"].isna() & df["minutes"].notna() & (df["minutes"] > 0)

    # team-game total minutes, for team_minutes_share (played rows only)
    team_game_minutes = (
        df.loc[df["played"], ["game_id", "team_id", "minutes"]]
        .groupby(["game_id", "team_id"], as_index=False)["minutes"]
        .sum()
        .rename(columns={"minutes": "team_game_minutes"})
    )
    df = df.merge(team_game_minutes, on=["game_id", "team_id"], how="left")

    df = df.sort_values(["player_id", "game_date", "game_id"]).reset_index(drop=True)

    # team_id -> abbreviation lookup (for opponent resolution on the absent game,
    # which the puller needs to match against the Odds API /events list)
    team_abbrev = (
        df[["team_id", "team_abbreviation"]]
        .drop_duplicates(subset="team_id", keep="last")  # most recent abbreviation wins (e.g. PHO->PHX)
        .set_index("team_id")["team_abbreviation"]
    )
    absent_game_opp = (
        df[["game_id", "team_id", "opp_team_id", "is_home"]]
        .drop_duplicates()
        .assign(opp_abbrev=lambda d: d["opp_team_id"].map(team_abbrev))
    )

    alpha = 2.0 / (ewma_span + 1.0)
    events = []

    for player_id, grp in df.groupby("player_id", sort=False):
        grp = grp.sort_values(["game_date", "game_id"])
        ewma = None
        prev_row = None
        for _, row in grp.iterrows():
            if prev_row is not None:
                prior_played = bool(prev_row["played"])
                curr_absent = not bool(row["played"])
                if prior_played and curr_absent and ewma is not None and ewma >= ewma_threshold:
                    opp_row = absent_game_opp[
                        (absent_game_opp["game_id"] == row["game_id"])
                        & (absent_game_opp["team_id"] == row["team_id"])
                    ]
                    opp_abbrev = opp_row["opp_abbrev"].iloc[0] if len(opp_row) else None
                    is_home = bool(opp_row["is_home"].iloc[0]) if len(opp_row) else None
                    events.append({
                        "player_id": player_id,
                        "player_name": row["player_name"],
                        "team_id": prev_row["team_id"],
                        "team_abbreviation": prev_row["team_abbreviation"],
                        "absent_game_opponent_abbreviation": opp_abbrev,
                        "absent_game_team_is_home": is_home,
                        "prior_game_id": prev_row["game_id"],
                        "prior_game_date": str(prev_row["game_date"]),
                        "absent_game_id": row["game_id"],
                        "absent_game_date": str(row["game_date"]),
                        "absent_season": int(row["season"]),
                        "absent_season_type": row["season_type"],
                        "dnp_reason": row["dnp_reason"],
                        "minutes_ewma_at_prior_game": round(float(ewma), 3),
                        "prior_game_minutes": round(float(prev_row["minutes"]), 3),
                        "prior_game_team_total_minutes": (
                            round(float(prev_row["team_game_minutes"]), 3)
                            if pd.notna(prev_row["team_game_minutes"]) else None
                        ),
                        "team_minutes_share_prior_game": (
                            round(float(prev_row["minutes"]) / float(prev_row["team_game_minutes"]), 4)
                            if pd.notna(prev_row["team_game_minutes"]) and prev_row["team_game_minutes"] > 0
                            else None
                        ),
                    })
            # update EWMA only on played games
            if row["played"]:
                m = float(row["minutes"])
                ewma = m if ewma is None else (alpha * m + (1 - alpha) * ewma)
            prev_row = row

    out = pd.DataFrame(events)
    if out.empty:
        return out
    out = out.sort_values(
        ["minutes_ewma_at_prior_game", "absent_game_date"], ascending=[False, True]
    ).reset_index(drop=True)
    out.insert(0, "rank", out.index + 1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threshold", type=float, default=MINUTES_EWMA_THRESHOLD_DEFAULT)
    ap.add_argument("--span", type=int, default=EWMA_SPAN_DEFAULT)
    ap.add_argument("--out-csv", type=Path, default=TRACK_ROOT / "absence_events_ranked.csv")
    ap.add_argument("--out-json", type=Path, default=TRACK_ROOT / "absence_events_ranked.json")
    args = ap.parse_args()

    events = compute_events(ewma_threshold=args.threshold, ewma_span=args.span)
    if events.empty:
        print("No events found at the given threshold.", file=sys.stderr)
        sys.exit(1)

    events.to_csv(args.out_csv, index=False)
    args.out_json.write_text(
        json.dumps(
            {
                "generated_by": "build_absence_events.py",
                "source": str(MASTER_PLAYER),
                "source_read_only": True,
                "minutes_ewma_threshold": args.threshold,
                "ewma_span_games": args.span,
                "season_range": [SEASON_MIN, SEASON_MAX],
                "n_events": len(events),
                "events": json.loads(events.to_json(orient="records")),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"{len(events)} absence events written to {args.out_csv} and {args.out_json}")
    print(events.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
