#!/usr/bin/env python3
"""synthetic_fixture.py -- a structurally NON-REAL universe the runner is allowed to fit.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

The blinding predicate refuses to fit anything carrying a real signature: 2,982 / 2,990 rows,
1,491 / 1,495 clusters, or a D006 fold id. This fixture is deliberately built OUTSIDE every one
of those signatures -- 360 clusters, 720 rows, fold ids prefixed `SYN_` -- so that exercising the
fitters proves the machinery without ever approaching the sealed comparison.

Nothing here is calibrated to resemble WNBA scoring, and it must not be: a synthetic frame that
looked real would tempt someone to read a number off it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from universe import Universe  # noqa: E402

N_TEAMS = 8
GAMES_PER_SEASON = 90
SEASONS = (2001, 2002, 2003, 2004)          # NOT the real seasons
SYN_FOLDS = {"SYN_f1": {"train": [2001], "test": 2002},
             "SYN_f2": {"train": [2001, 2002], "test": 2003},
             "SYN_f3": {"train": [2001, 2002, 2003], "test": 2004}}


def _team_ids() -> list[int]:
    """Real franchise IDs, deliberately.

    SC06 reads venue timezones from the byte-pinned team_cities.csv and REFUSES a team it has no
    standard offset for -- a strictness worth keeping, because a franchise in an unmapped zone
    should fail closed rather than silently score zero travel. So the fixture borrows eight real
    team_ids instead of inventing 0..7. That does not make the frame real: blinding keys on row
    count, cluster count, fold ids and artifact hashes, and this fixture matches none of them.
    Team identity is schedule metadata; no outcome, date or count here comes from the universe."""
    import pandas as _pd
    import runner_constants as _K
    tc = _pd.read_csv(_K.artifact_path("data/reference/team_cities.csv"))
    return sorted({int(t) for t in tc["team_id"]})[:N_TEAMS]


def make_universe(seed: int = 7) -> Universe:
    rng = np.random.default_rng(seed)
    tids = _team_ids()
    rows = []
    gid = 0
    for si, season in enumerate(SEASONS):
        strength = rng.normal(0, 4, N_TEAMS)
        for k in range(GAMES_PER_SEASON):
            gid += 1
            h, a = rng.choice(N_TEAMS, size=2, replace=False)
            date = pd.Timestamp(f"{season}-04-01") + pd.Timedelta(days=int(k * 1.4))
            base = 78 + 3 * si
            hp = base + strength[h] - 0.4 * strength[a] + 2.5 + rng.normal(0, 9)
            ap = base + strength[a] - 0.4 * strength[h] + rng.normal(0, 9)
            hp, ap = float(round(hp)), float(round(ap))
            if hp == ap:                                   # no settled ties: E3 must be defined
                hp += 1.0
            th, ta = tids[int(h)], tids[int(a)]
            rows.append((f"S{gid:05d}", season, "Regular Season", str(date.date()),
                         th, ta, 1, hp, ap))
            rows.append((f"S{gid:05d}", season, "Regular Season", str(date.date()),
                         ta, th, 0, ap, hp))

    tr = pd.DataFrame(rows, columns=["game_id", "season", "season_type", "game_date", "team_id",
                                     "opp_team_id", "is_home", "pts", "opp_pts"])
    tr["margin"] = tr["pts"] - tr["opp_pts"]
    tr["env"] = tr["pts"] + tr["opp_pts"]
    tr = tr.sort_values(["game_date", "game_id", "team_id"], kind="mergesort").reset_index(
        drop=True)

    h = tr[tr["is_home"] == 1][["game_id", "season", "season_type", "game_date", "team_id",
                                "opp_team_id", "pts", "opp_pts"]].rename(
        columns={"team_id": "home_team_id", "opp_team_id": "away_team_id",
                 "pts": "home_pts", "opp_pts": "away_pts"})
    g = h.sort_values(["game_date", "game_id"], kind="mergesort").reset_index(drop=True)
    g["E1_GAME_TOTAL"] = g["home_pts"] + g["away_pts"]
    g["E2_FINAL_MARGIN_HOME"] = g["home_pts"] - g["away_pts"]
    g["E3_HOME_WIN_PROB"] = (g["E2_FINAL_MARGIN_HOME"] > 0).astype(float)
    # a stand-in null-granted composite: a noisy, deliberately imperfect view of the target
    g["C_margin"] = 0.55 * g["E2_FINAL_MARGIN_HOME"] + rng.normal(0, 6, len(g))
    g["C_total"] = 0.5 * g["E1_GAME_TOTAL"] + 80 + rng.normal(0, 6, len(g))
    g["C_p_home"] = 1.0 / (1.0 + np.exp(-g["C_margin"] / 9.0))
    g["composite_source"] = "synthetic"
    g["era_2024"] = (g["season"] >= 2003).astype(float)     # a synthetic era boundary
    # SC08's pinned pace ingredient has no rows for synthetic game_ids; the arm accepts a stand-in
    # ONLY on a frame carrying the synthetic digest (see sc08.pace_prior).
    g["_synthetic_pace_prior"] = 160.0 + rng.normal(0, 6, len(g))

    return Universe(games=g, team_rows=tr, game_id_digest="SYNTHETIC_NOT_A_REAL_DIGEST",
                    receipt={"schema": "s36_synthetic_universe/1", "is_real": False,
                             "n_clusters": len(g), "n_team_game_rows": len(tr)})


def folds(u: Universe) -> dict:
    s = u.games["season"].to_numpy()
    out = {}
    for fid, spec in SYN_FOLDS.items():
        out[fid] = {"fold_id": fid,
                    "train_idx": np.flatnonzero(np.isin(s, spec["train"])),
                    "test_idx": np.flatnonzero(s == spec["test"])}
    return out


def assert_not_real_shaped(u: Universe) -> None:
    """If the fixture ever drifted into a real signature the blinding tests would silently stop
    testing anything, so the fixture asserts its own non-realness."""
    import runner_constants as K
    assert len(u.team_rows) not in K.REAL_UNIVERSE_ROW_COUNTS
    assert len(u.games) not in K.REAL_UNIVERSE_CLUSTER_COUNTS
    assert not (set(SYN_FOLDS) & set(K.REAL_FOLD_IDS))
