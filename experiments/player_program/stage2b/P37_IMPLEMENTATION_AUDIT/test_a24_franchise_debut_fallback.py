"""
Standalone fixture test for the A24 franchise-debut fallback adjudicated in
A24_AMENDMENT_PAYLOAD.json (P37_IMPLEMENTATION_AUDIT, finding A3-B3, D039 option (a)).

Purpose: prove, on a small synthetic schedule containing a franchise-debut game, that the
adjudicated fallback rule

    rest(t, g) := cap   when t has no prior CONTRACT-SCHEDULE game before g

makes A24's frozen model

    rest(t, g) = min(days since max prior contract game date of t, 10)
    x(t, g)    = (rest(t, g) + rest(opp(g, t), g)) / 2

fully decidable (no NaN / no A24ConstructionFailure) on every row, including the debut game's own
two rows, while:
  (a) leaving every non-debut row's rest(.,.) value byte-identical to the un-amended formula
      (the fallback is a pure domain extension, never a redefinition on defined inputs);
  (b) being computable from schedule membership facts alone, before any fit -- i.e.
      preregistration-decidable;
  (c) producing the identical x(.,.) value for the two rows of a debut game (deterministic and
      symmetric), which is what the arm AND its K0-matched null both consume (the null omits the
      coefficient on x, not the row or the value -- see A24's k0_matched_frozen.null: "same
      machinery; treatment adds ONLY x").

Standard library only. Run with: python test_a24_franchise_debut_fallback.py
"""

from __future__ import annotations

import datetime as dt
import unittest
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

CAP = 10  # A24's frozen cap, from stage2b/P35_FREEZE_TASK_CARDS/SPEC.json arm A24's model text


@dataclass(frozen=True)
class ContractGame:
    game_id: str
    game_date: dt.date
    team: str
    opp: str


def build_prior_game_dates(
    games: List[ContractGame],
    known_history_start: Optional[Dict[str, dt.date]] = None,
) -> Dict[Tuple[str, str], Optional[dt.date]]:
    """(team, game_id) -> that team's max prior CONTRACT-SCHEDULE game date, if any exists.

    `known_history_start` seeds an incumbent team with a real off-fixture prior date -- this
    models the real archive, where an incumbent's contract-schedule history extends into earlier
    seasons that are not themselves rows in a reduced fixture (exactly what the original card's
    "cross-season prior game covers openers" text refers to for incumbents). A team with NO entry
    in `known_history_start` and no earlier game in `games` is a true franchise debut: its very
    first appearance in `games` has no prior date, by construction -- the case the fallback fires
    on.
    """
    known_history_start = known_history_start or {}
    by_team: Dict[str, List[ContractGame]] = {}
    for g in games:
        by_team.setdefault(g.team, []).append(g)
    for team in by_team:
        by_team[team].sort(key=lambda g: (g.game_date, g.game_id))

    prior: Dict[Tuple[str, str], Optional[dt.date]] = {}
    for team, team_games in by_team.items():
        seen: List[dt.date] = [known_history_start[team]] if team in known_history_start else []
        for g in team_games:
            prior[(team, g.game_id)] = max(seen) if seen else None
            seen.append(g.game_date)
    return prior


def rest_UNAMENDED(team: str, game_id: str, game_date: dt.date,
                    prior_dates: Dict[Tuple[str, str], Optional[dt.date]]) -> Optional[float]:
    """A24's frozen formula with NO fallback -- returns None (undefined) on a franchise debut,
    reproducing the measured A24ConstructionFailure trigger from finding A3-B3."""
    prior = prior_dates[(team, game_id)]
    if prior is None:
        return None  # structurally undefined: no prior contract game to measure "days since" from
    return min((game_date - prior).days, CAP)


def rest_AMENDED(team: str, game_id: str, game_date: dt.date,
                  prior_dates: Dict[Tuple[str, str], Optional[dt.date]]) -> float:
    """A24's frozen formula WITH the adjudicated franchise-debut fallback: rest := cap when the
    team has no prior contract-schedule game. Identical to rest_UNAMENDED on every row where a
    prior game exists (requirement (a))."""
    prior = prior_dates[(team, game_id)]
    if prior is None:
        return float(CAP)  # adjudicated fallback: debuting team treated as fully rested
    return float(min((game_date - prior).days, CAP))


def x_value(rest_fn, team: str, opp: str, game_id: str, game_date: dt.date,
            prior_dates) -> Optional[float]:
    """A24's frozen symmetric-mean formula, unchanged, parameterised by which rest() to use."""
    r_t = rest_fn(team, game_id, game_date, prior_dates)
    r_o = rest_fn(opp, game_id, game_date, prior_dates)
    if r_t is None or r_o is None:
        return None
    return (r_t + r_o) / 2.0


class A24FranchiseDebutFallbackFixture(unittest.TestCase):
    """Synthetic schedule: two incumbent teams (A, B) with contract-schedule history predating
    this fixture's rows, plus one debuting franchise ('EXP1') with NO prior contract game
    anywhere. Mirrors the real archive's shape (auditor-named debuts: 1611661331/2025,
    1611661327/2026, 1611661332/2026) without using real data -- team ids and dates below are
    entirely synthetic."""

    def setUp(self) -> None:
        base = dt.date(2026, 5, 1)
        self.games: List[ContractGame] = [
            # Incumbent A's most recent game before the debut game (establishes A's real rest).
            ContractGame("g0", base - dt.timedelta(days=6), "A", "B"),
            ContractGame("g0", base - dt.timedelta(days=6), "B", "A"),
            # Incumbent B's second game (rest is well-defined: 3 days since g0).
            ContractGame("g1", base - dt.timedelta(days=3), "B", "A"),
            ContractGame("g1", base - dt.timedelta(days=3), "A", "B"),
            # The debut game: franchise EXP1's first-ever contract game, vs incumbent A.
            ContractGame("g_debut", base, "EXP1", "A"),
            ContractGame("g_debut", base, "A", "EXP1"),
        ]
        # A and B are INCUMBENTS: their contract-schedule history extends into an earlier season
        # not itself modelled as a row here (exactly as in the real archive, where the "cross-
        # season prior game covers openers" text is correct for incumbents). EXP1 gets no entry:
        # it is a true franchise debut with no prior contract game anywhere, ever.
        self.known_history_start = {
            "A": base - dt.timedelta(days=200),
            "B": base - dt.timedelta(days=200),
        }
        self.prior_dates = build_prior_game_dates(self.games, self.known_history_start)

    def test_unamended_formula_is_undefined_on_the_debut_rows(self) -> None:
        """Reproduces the measured defect (A3-B3): with no fallback, rest() and therefore x() are
        undefined (None here; A24ConstructionFailure in the real module) on BOTH rows of the
        debut game -- the debuting team's own row and its opponent's row -- exactly as the
        auditor measured ('the symmetric mean is NaN on both sides of each debut game')."""
        debut_date = dt.date(2026, 5, 1)
        x_exp1_row = x_value(rest_UNAMENDED, "EXP1", "A", "g_debut", debut_date, self.prior_dates)
        x_a_row = x_value(rest_UNAMENDED, "A", "EXP1", "g_debut", debut_date, self.prior_dates)
        self.assertIsNone(x_exp1_row)
        self.assertIsNone(x_a_row)

    def test_amended_formula_is_fully_decidable_on_every_row(self) -> None:
        """The adjudicated fallback resolves x() on every row of the fixture, including both
        rows of the debut game -- no NaN, no exception, no undefined value anywhere."""
        for g in self.games:
            x = x_value(rest_AMENDED, g.team, g.opp, g.game_id, g.game_date, self.prior_dates)
            self.assertIsNotNone(x, f"x undefined for team={g.team} game={g.game_id}")
            self.assertTrue(0.0 <= x <= float(CAP))

    def test_debuting_team_is_scored_as_fully_rested(self) -> None:
        """rest(EXP1, g_debut) := cap (10), per the adjudicated rule, not an inferred/estimated
        value -- deterministic and preregistration-decidable from schedule membership alone."""
        debut_date = dt.date(2026, 5, 1)
        self.assertEqual(
            rest_AMENDED("EXP1", "g_debut", debut_date, self.prior_dates), float(CAP)
        )

    def test_both_rows_of_the_debut_game_get_the_identical_x(self) -> None:
        """Symmetric mean: EXP1's own row and A's row (opp=EXP1) for the same game must carry the
        identical x, per A24's frozen formula being row-order-invariant. This is also what makes
        the fallback identical for arm and null -- both consume the same x value at this row."""
        debut_date = dt.date(2026, 5, 1)
        x_exp1_row = x_value(rest_AMENDED, "EXP1", "A", "g_debut", debut_date, self.prior_dates)
        x_a_row = x_value(rest_AMENDED, "A", "EXP1", "g_debut", debut_date, self.prior_dates)
        self.assertEqual(x_exp1_row, x_a_row)
        # EXP1 is fallback-rested at cap=10 (debut). A's last prior game before g_debut is g1
        # (3 days earlier), so A's real rest = min(3, 10) = 3. x = (10 + 3) / 2 = 6.5.
        self.assertAlmostEqual(x_exp1_row, (10.0 + 3.0) / 2.0)

    def test_non_debut_rows_are_byte_identical_between_unamended_and_amended(self) -> None:
        """Requirement (a): the fallback must never change a value that was already defined. Every
        row NOT touching the debut game must produce the exact same rest() under both formulas."""
        for g in self.games:
            if g.game_id == "g_debut":
                continue
            unamended = rest_UNAMENDED(g.team, g.game_id, g.game_date, self.prior_dates)
            amended = rest_AMENDED(g.team, g.game_id, g.game_date, self.prior_dates)
            self.assertIsNotNone(unamended, f"fixture bug: {g.team}/{g.game_id} should be defined")
            self.assertEqual(unamended, amended)

    def test_fallback_trigger_is_decidable_from_schedule_facts_alone(self) -> None:
        """Preregistration-decidability check: the trigger condition (does team t have a prior
        contract-schedule game before g) is computable purely from the schedule table -- no
        fitted parameter, no fold assignment, no result of any kind is consulted."""
        # rebuilt from schedule facts (games + known incumbent history-start dates) only
        prior_dates = build_prior_game_dates(self.games, self.known_history_start)
        self.assertIsNone(prior_dates[("EXP1", "g_debut")])  # debut: no prior game -> fallback fires
        self.assertIsNotNone(prior_dates[("A", "g_debut")])  # incumbent: fallback does not fire
        self.assertIsNotNone(prior_dates[("B", "g1")])

    def test_row_count_matches_the_auditors_measured_scope(self) -> None:
        """The fallback fires for exactly one (team, game) pair in this fixture (EXP1's debut),
        touching exactly the 2 rows of that game (both sides) -- the same '>=6 rows... including
        fold-4/5 TEST rows' shape the auditor measured on the real archive (3 real debuts x 2
        rows/game = 6; this fixture models one such debut game in isolation)."""
        fired = [
            (g.team, g.game_id)
            for g in self.games
            if self.prior_dates[(g.team, g.game_id)] is None
        ]
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0], ("EXP1", "g_debut"))
        rows_touched = [g for g in self.games if g.game_id == "g_debut"]
        self.assertEqual(len(rows_touched), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
