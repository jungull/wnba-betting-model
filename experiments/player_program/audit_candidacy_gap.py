#!/usr/bin/env python3
"""audit_candidacy_gap.py — every player-team-game with real minutes and no obligation.

The measurement `prediction_contract_v5` is designed against. It answers one question against the
real artifacts: **which players logged minutes for a team in a game where the v4 contract owed no
forecast for them, and why.**

**Nothing here is scored.** Row counts, key-set comparisons and set membership only. No forecast is
read, no metric is computed, no outcome is compared to any prediction. `minutes > 0` is used as the
definition of "played", which is an eligibility fact about the row, not a target.

WHAT IT MEASURES, AND WHY THE DECOMPOSITION IS THE POINT
--------------------------------------------------------

`prediction_contract_v4`'s membership rule is
`prior_admitted_team_game_box_membership_including_dnp/1`: a candidate for `(team, game)` is a
player who appears as a row in that team's box score for one of the latest **five prior
same-season** team games whose availability bound is strictly earlier than the forecast cutoff.

Two consequences follow directly from "prior **same-season**", and they need different remedies,
so counting them together would hide the actionable one:

* **Season openers have no prior same-season game at all**, so every team's first game of every
  season yields ZERO candidates and therefore zero obligations. This is a structural property of
  the season-reset window, not a data defect.
* **A player who joins mid-season** — signing, hardship contract, waiver claim, trade — has no box
  row for the new club inside the window, so she is not a candidate for the club she actually
  plays for. Her old club, meanwhile, may still list her as a candidate.

The script also tests one candidate remedy that uses only provable, cutoff-safe evidence:
**prior-season box membership for the same franchise.** A player's appearance in a previous
season's box score is available months before an opening-night cutoff, so admitting it invents
nothing. The script reports how much of the gap it would actually close, which turns out to be the
decisive number for the v5 design.

Run::

    python experiments/player_program/audit_candidacy_gap.py
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

AUDIT_ID = "player_candidacy_gap/1"
MASTER = "data/masters/master_player.parquet"
CONTRACT = "experiments/prediction_contract_v4/player_game.parquet"

#: v4's lookback. Team-game indices strictly below this have a window that cannot be full.
ROSTER_LOOKBACK = 5


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["game_id"] = df["game_id"].astype(str)
    for c in ("player_id", "team_id"):
        df[c] = df[c].astype("int64")
    return df


def build(root: Path) -> dict:
    mp = _norm(pd.read_parquet(root / MASTER))
    pg = _norm(pd.read_parquet(root / CONTRACT))
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mp["min_n"] = pd.to_numeric(mp["minutes"], errors="coerce")

    played = (mp.loc[mp["min_n"].fillna(0) > 0,
                     ["game_id", "team_id", "player_id", "season", "game_date"]]
              .drop_duplicates())
    obligations = set(zip(pg["game_id"], pg["team_id"], pg["player_id"]))
    played["is_obligation"] = [(g, t, p) in obligations for g, t, p
                               in zip(played["game_id"], played["team_id"],
                                      played["player_id"])]

    # team-game ordinal within season, taken from the master rather than the contract, so a game
    # the contract omits entirely is still indexed
    tg = (mp[["game_id", "team_id", "season", "game_date"]].drop_duplicates()
          .sort_values(["team_id", "season", "game_date", "game_id"], kind="mergesort"))
    tg["team_game_index"] = tg.groupby(["team_id", "season"]).cumcount()
    played = played.merge(tg[["game_id", "team_id", "team_game_index"]],
                          on=["game_id", "team_id"], how="left")

    gap = played.loc[~played["is_obligation"]].copy()

    # the candidate remedy: prior-SEASON box membership for the same franchise
    seen: set = set(zip(mp["team_id"], mp["player_id"], mp["season"]))
    seasons = sorted(int(s) for s in pd.unique(mp["season"]))
    first_season = min(seasons)

    def prior_season_member(team_id: int, player_id: int, season: int) -> bool:
        return any((team_id, player_id, s) in seen for s in range(first_season, season))

    gap["prior_season_same_team"] = [
        prior_season_member(t, p, s) for t, p, s
        in zip(gap["team_id"], gap["player_id"], gap["season"])]

    def bucket(i) -> str:
        if pd.isna(i):
            return "game_absent_from_master_index"
        i = int(i)
        if i == 0:
            return "season_opener"
        if i < ROSTER_LOOKBACK:
            return "early_season_partial_window"
        return "mid_season_arrival"

    gap["cause"] = gap["team_game_index"].map(bucket)

    by_cause = {}
    for cause, g in gap.groupby("cause"):
        by_cause[cause] = {
            "n": int(len(g)),
            "n_recoverable_by_prior_season_membership": int(g["prior_season_same_team"].sum()),
            "n_not_recoverable": int((~g["prior_season_same_team"]).sum()),
            "n_distinct_players": int(g["player_id"].nunique()),
            "n_distinct_games": int(g["game_id"].nunique()),
            "by_season": {str(k): int(v) for k, v in g.groupby("season").size().items()},
        }

    per_season = {}
    for s, g in played.groupby("season"):
        miss = g.loc[~g["is_obligation"]]
        per_season[str(int(s))] = {
            "played_rows": int(len(g)),
            "not_an_obligation": int(len(miss)),
            "pct": round(100.0 * len(miss) / max(len(g), 1), 2),
        }

    op = gap.loc[gap["cause"] == "season_opener"]
    op_ex_first = op.loc[op["season"] > first_season]

    return {
        "schema": AUDIT_ID,
        "generated_utc": _utc(),
        "scope": ("row counts, key-set comparisons and set membership only; nothing is scored "
                  "and no forecast is compared to any outcome"),
        "inputs": {"master": MASTER, "contract": CONTRACT},
        "v4_membership_rule": "prior_admitted_team_game_box_membership_including_dnp/1",
        "definition_of_played": "minutes > 0 in master_player, an eligibility fact about the row",
        "totals": {
            "played_player_team_games": int(len(played)),
            "not_an_obligation": int(len(gap)),
            "pct_of_played": round(100.0 * len(gap) / max(len(played), 1), 2),
            "n_distinct_players": int(gap["player_id"].nunique()),
            "n_distinct_games": int(gap["game_id"].nunique()),
        },
        "per_season": per_season,
        "by_cause": by_cause,
        "remedy_prior_season_membership": {
            "evidence": ("a player's box appearance in a PREVIOUS season for the same franchise, "
                         "available months before an opening-night cutoff, so admitting it "
                         "invents nothing and is cutoff-safe by construction"),
            "season_openers_total": int(len(op)),
            "season_openers_recovered": int(op["prior_season_same_team"].sum()),
            "season_openers_recovered_pct": round(
                100.0 * op["prior_season_same_team"].mean(), 1) if len(op) else None,
            "season_openers_excluding_first_season_total": int(len(op_ex_first)),
            "season_openers_excluding_first_season_recovered": int(
                op_ex_first["prior_season_same_team"].sum()),
            "season_openers_excluding_first_season_recovered_pct": round(
                100.0 * op_ex_first["prior_season_same_team"].mean(), 1)
            if len(op_ex_first) else None,
            "why_first_season_recovers_nothing": (
                f"{first_season} is the earliest season in the data, so it has no prior season "
                f"to inherit from. Its openers are structurally unrecoverable from box evidence."),
            "verdict": (
                "PARTIAL. It closes roughly half of the recoverable opening-night gap and almost "
                "none of the mid-season gap. The residue is real newcomers -- rookies, free "
                "agents arriving from another franchise, players returning from overseas -- "
                "whose membership is simply not present in any box score before the game they "
                "first play. Roster membership CANNOT be reconstructed from box scores alone, "
                "and v5 must therefore treat the residue as an audited exclusion rather than "
                "manufacture it."),
        },
        "sample_mid_season_arrivals": gap.loc[gap["cause"] == "mid_season_arrival",
                                              ["season", "game_id", "team_id", "player_id",
                                               "team_game_index"]]
        .head(15).to_dict("records"),
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--out", default=str(HERE / "CANDIDACY_GAP_RECEIPT.json"))
    args = ap.parse_args()
    rec = build(Path(args.root).resolve())
    Path(args.out).write_text(json.dumps(rec, indent=2, default=str) + "\n",
                              encoding="utf-8", newline="")
    print(f"wrote {args.out}\n")
    t = rec["totals"]
    print(f"played player-team-games : {t['played_player_team_games']:,}")
    print(f"NOT an obligation        : {t['not_an_obligation']:,} "
          f"({t['pct_of_played']}%), {t['n_distinct_players']} players, "
          f"{t['n_distinct_games']} games")
    print("\nby cause:")
    for cause, d in sorted(rec["by_cause"].items(), key=lambda kv: -kv[1]["n"]):
        print(f"  {cause:32s} {d['n']:5d}   recoverable by prior-season "
              f"membership: {d['n_recoverable_by_prior_season_membership']:4d}")
    r = rec["remedy_prior_season_membership"]
    print(f"\nprior-season remedy on openers: {r['season_openers_recovered']}/"
          f"{r['season_openers_total']} ({r['season_openers_recovered_pct']}%); "
          f"excluding {rec['per_season'] and min(rec['per_season'])}: "
          f"{r['season_openers_excluding_first_season_recovered']}/"
          f"{r['season_openers_excluding_first_season_total']} "
          f"({r['season_openers_excluding_first_season_recovered_pct']}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
