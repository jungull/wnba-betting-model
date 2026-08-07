"""
E1 I0009 -- shared pregame (strictly-before-date, expanding, shrunk) rate lookups.

Used by BOTH build_data.py (real) and analyze.py (placebo), so the real effect and the
noise floor are computed through EXACTLY the same construction.

HARD RULE (GRAPH_POLICY 13.2): exploration partition = seasons 2021-2024 ONLY.
This module never loads data itself; callers hand it an already-filtered frame and the
constructor asserts the partition.
"""
import numpy as np
import pandas as pd

EXPLORATION_SEASONS = [2021, 2022, 2023, 2024]

# Shrinkage pseudo-counts (in possessions) toward the early-season anchor.
SHRINK_K_TEAM = 200.0    # ~2.5 team-games of defensive possessions  (same as E0)
SHRINK_K_VENUE = 200.0   # venue-split rate shrunk toward the team's own overall pregame rate
SHRINK_K_PLAYER = 100.0  # player offensive possessions


def _ns(x):
    """datetime-like -> int64 nanoseconds, so searchsorted is unambiguous."""
    return pd.to_datetime(pd.Series(x)).astype("int64").to_numpy()


class _PrefixIndex:
    """Sorted-by-date prefix sums of (num, den) for each (unit, season) group."""

    def __init__(self, frame, unit_col, num_col, den_col):
        self.idx = {}
        for key, g in frame.groupby([unit_col, "season"], sort=False):
            g = g.sort_values("game_date")
            self.idx[key] = (
                _ns(g["game_date"]),
                np.concatenate([[0.0], np.cumsum(g[den_col].to_numpy(float))]),
                np.concatenate([[0.0], np.cumsum(g[num_col].to_numpy(float))]),
            )

    def prefix(self, unit, season, date_ns):
        e = self.idx.get((unit, season))
        if e is None:
            return 0.0, 0.0, 0
        dates, cd, cn = e
        k = int(np.searchsorted(dates, date_ns, side="left"))  # STRICTLY before date
        return cd[k], cn[k], k


class PregameTeamPressure:
    """
    Expanding, strictly-before-date team DEFENSIVE rate per 100 defensive possessions,
    shrunk toward an anchor (prior-season team rate when season-1 is itself inside the
    exploration partition, else that season's league mean -- a scalar, non-discriminating).

    Also provides a VENUE-SPLIT version: the same expanding rate computed only over the
    team's prior games on the given side of the venue (defending at home vs on the road),
    shrunk toward that team's own overall pregame rate at the same date.

    Nothing here can see a game on or after `date` for the queried team.
    """

    def __init__(self, team_game, num_col="def_tov", den_col="def_poss", K=SHRINK_K_TEAM):
        assert set(team_game["season"].unique()).issubset(set(EXPLORATION_SEASONS)), \
            "PARTITION VIOLATION in PregameTeamPressure"
        self.K = K
        self.num_col, self.den_col = num_col, den_col

        lg = team_game.groupby("season").agg(d=(den_col, "sum"), n=(num_col, "sum"))
        self.league_mean = (100.0 * lg["n"] / lg["d"]).to_dict()

        ts = team_game.groupby(["team_id", "season"]).agg(d=(den_col, "sum"), n=(num_col, "sum"))
        self.season_rate = (100.0 * ts["n"] / ts["d"]).to_dict()

        self.anchor = {}
        for (team, season) in self.season_rate:
            prior = self.season_rate.get((team, season - 1))
            if prior is not None and (season - 1) in EXPLORATION_SEASONS:
                self.anchor[(team, season)] = prior
            else:
                self.anchor[(team, season)] = self.league_mean[season]

        self.all_idx = _PrefixIndex(team_game, "team_id", num_col, den_col)
        self.venue_idx = {
            h: _PrefixIndex(team_game[team_game["def_is_home"] == h], "team_id", num_col, den_col)
            for h in (0, 1)
        }
        self.teams_by_season = {
            s: sorted(t for (t, ss) in self.season_rate if ss == s) for s in EXPLORATION_SEASONS
        }

    def lookup(self, team_id, season, date_ns):
        cd, cn, k = self.all_idx.prefix(team_id, season, date_ns)
        anchor = self.anchor.get((team_id, season), self.league_mean.get(season, np.nan))
        return 100.0 * (cn + self.K * anchor / 100.0) / (cd + self.K), k

    def lookup_venue(self, team_id, season, date_ns, def_is_home):
        """Venue-specific pregame rate, shrunk toward the team's own overall pregame rate."""
        base, _ = self.lookup(team_id, season, date_ns)
        cd, cn, k = self.venue_idx[int(def_is_home)].prefix(team_id, season, date_ns)
        return 100.0 * (cn + SHRINK_K_VENUE * base / 100.0) / (cd + SHRINK_K_VENUE), k

    def matrix_all_teams(self, seasons, date_ns_arr):
        """
        For the placebo: [n_rows x n_teams_in_season] pregame values, i.e. every team's
        ALREADY-COMPUTED pregame pressure evaluated at each row's own date.
        Returns dict season -> (team_list, matrix aligned to the rows of that season).
        """
        out = {}
        seasons = np.asarray(seasons)
        date_ns_arr = np.asarray(date_ns_arr)
        for s in EXPLORATION_SEASONS:
            m = seasons == s
            if not m.any():
                continue
            teams = self.teams_by_season[s]
            d = date_ns_arr[m]
            mat = np.empty((m.sum(), len(teams)))
            for j, t in enumerate(teams):
                for i, dd in enumerate(d):
                    mat[i, j] = self.lookup(t, s, dd)[0]
            out[s] = (teams, mat, np.flatnonzero(m))
        return out


class PregamePlayerTendency:
    """
    Fully pregame-observable player turnover rate per 100 offensive possessions:
    expanding over the player's games strictly before this game's date, shrunk toward
    the player's prior-season rate (when season-1 is in the partition) else the season
    league mean player rate.
    """

    def __init__(self, player_game, K=SHRINK_K_PLAYER):
        assert set(player_game["season"].unique()).issubset(set(EXPLORATION_SEASONS)), \
            "PARTITION VIOLATION in PregamePlayerTendency"
        self.K = K
        lg = player_game.groupby("season").agg(d=("realised_off_possessions", "sum"),
                                               n=("turnovers", "sum"))
        self.league_mean = (100.0 * lg["n"] / lg["d"]).to_dict()

        ps = player_game.groupby(["player_id", "season"]).agg(
            d=("realised_off_possessions", "sum"), n=("turnovers", "sum"))
        ps = ps[ps["d"] > 0]
        self.season_rate = (100.0 * ps["n"] / ps["d"]).to_dict()

        self.anchor = {}
        for (pid, season) in self.season_rate:
            prior = self.season_rate.get((pid, season - 1))
            if prior is not None and (season - 1) in EXPLORATION_SEASONS:
                self.anchor[(pid, season)] = prior
            else:
                self.anchor[(pid, season)] = self.league_mean[season]

        self.idx = _PrefixIndex(player_game, "player_id", "turnovers", "realised_off_possessions")

    def lookup(self, player_id, season, date_ns):
        cd, cn, k = self.idx.prefix(player_id, season, date_ns)
        anchor = self.anchor.get((player_id, season), self.league_mean.get(season, np.nan))
        return 100.0 * (cn + self.K * anchor / 100.0) / (cd + self.K), k
