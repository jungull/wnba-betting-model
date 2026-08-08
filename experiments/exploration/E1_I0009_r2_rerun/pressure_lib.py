"""
E0 I0009 -- shared helper: a date-indexed "pregame" opponent forced-turnover-rate lookup.

Used by BOTH build_data.py (real opponent) and analyze.py (placebo / permuted opponent),
so the real effect and the noise floor are computed through EXACTLY the same construction.

HARD RULE (GRAPH_POLICY 13.2): exploration partition = seasons 2021-2024 ONLY.
This module never loads data itself; callers must hand it an already-filtered frame.
"""
import numpy as np
import pandas as pd

EXPLORATION_SEASONS = [2021, 2022, 2023, 2024]

# Shrinkage pseudo-count, in defensive possessions, toward the early-season anchor.
# 200 def possessions ~ 2.5 games, so by ~10 games observed the anchor carries ~20% weight.
SHRINK_K = 200.0


class PregamePressure:
    """
    Expanding, strictly-before-date team defensive forced-turnover rate per 100 def possessions,
    shrunk toward an anchor (prior-season team rate where available, else that season's league mean).

    lookup(team_id, season, date) -> (shrunk_rate, n_games_observed_before_date)

    Nothing in this class can see a game on or after `date` for the queried team.
    """

    def __init__(self, team_game: pd.DataFrame):
        """
        team_game: one row per (game_id, team_id-as-DEFENSE) with columns
                   team_id, season, game_date, def_poss, def_tov, def_pts_allowed
        """
        assert set(team_game["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"

        # league mean forced-TO rate per season (a single scalar per season; it does not
        # discriminate between opponents, so it cannot carry cross-sectional information)
        lg = team_game.groupby("season").agg(p=("def_poss", "sum"), t=("def_tov", "sum"),
                                             pts=("def_pts_allowed", "sum"))
        self.league_mean = (100.0 * lg["t"] / lg["p"]).to_dict()
        self.league_pts_mean = (100.0 * lg["pts"] / lg["p"]).to_dict()

        # full-season team rates -> prior-season anchor
        ts = team_game.groupby(["team_id", "season"]).agg(p=("def_poss", "sum"), t=("def_tov", "sum"))
        self.season_rate = (100.0 * ts["t"] / ts["p"]).to_dict()

        self.anchor = {}
        for (team, season) in self.season_rate:
            prior = self.season_rate.get((team, season - 1))
            # season-1 must itself be inside the exploration partition to be readable
            if prior is not None and (season - 1) in EXPLORATION_SEASONS:
                self.anchor[(team, season)] = prior
            else:
                self.anchor[(team, season)] = self.league_mean[season]

        # per (team, season): sorted game dates + prefix sums (cum[k] = sum of first k games)
        self.idx = {}
        for (team, season), g in team_game.groupby(["team_id", "season"]):
            g = g.sort_values("game_date")
            dates = g["game_date"].to_numpy()
            self.idx[(team, season)] = (
                dates,
                np.concatenate([[0.0], np.cumsum(g["def_poss"].to_numpy(float))]),
                np.concatenate([[0.0], np.cumsum(g["def_tov"].to_numpy(float))]),
                np.concatenate([[0.0], np.cumsum(g["def_pts_allowed"].to_numpy(float))]),
            )

        self.teams_by_season = {
            s: sorted({t for (t, ss) in self.idx if ss == s}) for s in EXPLORATION_SEASONS
        }

    def _prefix(self, team, season, date):
        entry = self.idx.get((team, season))
        if entry is None:
            return None
        dates, cp, ct, cpts = entry
        k = int(np.searchsorted(dates, date, side="left"))  # games STRICTLY before date
        return cp[k], ct[k], cpts[k], k

    def lookup(self, team_id, season, date):
        pre = self._prefix(team_id, season, date)
        if pre is None:
            return np.nan, 0
        cp, ct, _, k = pre
        anchor = self.anchor.get((team_id, season), self.league_mean[season])
        rate = 100.0 * (ct + SHRINK_K * anchor / 100.0) / (cp + SHRINK_K)
        return rate, k

    def lookup_defrtg(self, team_id, season, date):
        """Pregame opponent-quality control: points allowed per 100 defensive possessions."""
        pre = self._prefix(team_id, season, date)
        if pre is None:
            return np.nan, 0
        cp, _, cpts, k = pre
        # shrunk toward that season's league mean points-allowed rate (scalar, non-discriminating)
        anchor = self.league_pts_mean[season]
        return 100.0 * (cpts + SHRINK_K * anchor / 100.0) / (cp + SHRINK_K), k

    def lookup_many(self, teams, seasons, dates):
        rates = np.empty(len(teams))
        ngames = np.empty(len(teams), dtype=int)
        for i, (t, s, d) in enumerate(zip(teams, seasons, dates)):
            rates[i], ngames[i] = self.lookup(t, s, d)
        return rates, ngames
