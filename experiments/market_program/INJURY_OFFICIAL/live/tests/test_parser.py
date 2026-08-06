#!/usr/bin/env python3
"""
Fixture tests for parser.py -- run regardless of live network accessibility
(D033 mandate item 4). Fixtures are real production WNBA official
injury-report PDF bytes, sourced read-only from the live main worktree's
own production archive (data/injury_capture/raw/), copied once into
tests/fixtures/ for reproducible offline testing -- see
tests/fixtures/PROVENANCE.md for exact source paths and SHA-256 hashes.
These are NOT captures made by this track; they are fixtures.

Run: python -m unittest discover -s tests -v
     (from experiments/market_program/INJURY_OFFICIAL/live/)
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parser import parse_official_pdf, OFFICIAL_STATUSES  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name):
    return (FIXTURES / name).read_bytes()


class TestParserAgainstRealBytes(unittest.TestCase):
    def test_20260806_190009_full_shape(self):
        rows, meta, rejects = parse_official_pdf(
            _load("reference_prod_wnba_official_20260806T190009Z.pdf"))
        self.assertEqual(len(rows), 13)
        self.assertEqual(len(rejects), 0)
        self.assertEqual(len(meta["not_yet_submitted"]), 6)
        self.assertEqual(meta["report_publication_ts_raw"],
                          "08/06/26 03:00 PM")
        self.assertEqual(meta["report_publication_ts_et"],
                          "2026-08-06T15:00:00")

        by_player = {r["player_raw"]: r for r in rows}
        self.assertIn("Cheyenne Parker-Tyus", by_player)
        row = by_player["Cheyenne Parker-Tyus"]
        self.assertEqual(row["status"], "Out")
        self.assertEqual(row["reason"], "Concussion Protocol")
        self.assertEqual(row["team_raw"], "Las Vegas Aces")
        self.assertEqual(row["game_date"], "2026-08-06")

        clark = by_player["Caitlin Clark"]
        self.assertEqual(clark["status"], "Probable")
        self.assertIn("Back", clark["reason"])

        # hyphenated-name-with-line-wrap handling
        self.assertNotIn("Parker- Tyus", by_player)

        for r in rows:
            self.assertIn(r["status"], OFFICIAL_STATUSES)

    def test_20260731_205354_and_215354_are_structurally_stable(self):
        """Two captures ~1h apart of what turns out to be an unchanged
        report: same row count/content, DIFFERENT payload bytes (footer
        pagination/whitespace can differ even when content doesn't) --
        this is exactly the case hash-dedup at the orchestrator layer must
        collapse to one snapshot, and the parser layer must agree they
        parse to the same rows."""
        rows1, meta1, rej1 = parse_official_pdf(
            _load("reference_prod_wnba_official_20260731T205354Z.pdf"))
        rows2, meta2, rej2 = parse_official_pdf(
            _load("reference_prod_wnba_official_20260731T215354Z.pdf"))
        self.assertEqual(len(rows1), len(rows2))
        self.assertEqual(rej1, rej2)
        key1 = sorted((r["team_raw"], r["player_raw"], r["status"])
                      for r in rows1)
        key2 = sorted((r["team_raw"], r["player_raw"], r["status"])
                      for r in rows2)
        self.assertEqual(key1, key2)

    def test_not_yet_submitted_never_becomes_a_player_row(self):
        rows, meta, rejects = parse_official_pdf(
            _load("reference_prod_wnba_official_20260806T190009Z.pdf"))
        for r in rows:
            self.assertNotIn("NOT YET SUBMITTED", r["player_raw"].upper())
            self.assertNotIn("NOT YET SUBMITTED", r["status"].upper())
        self.assertGreater(len(meta["not_yet_submitted"]), 0)
        for nys in meta["not_yet_submitted"]:
            self.assertTrue(nys["team_raw"])

    def test_dense_report_known_reason_wrap_limitation_is_rejected_not_silent(self):
        """Documented known limitation (see parser.py module docstring):
        this specific fixture has a reason-cell y-baseline offset that
        produces one legitimate reject rather than a silently-wrong row.
        This test pins that CURRENT, honestly-imperfect behavior so a
        future change is a deliberate decision, not a silent regression
        either direction."""
        rows, meta, rejects = parse_official_pdf(
            _load("reference_prod_wnba_official_20260805T230003Z.pdf"))
        self.assertGreaterEqual(len(rejects), 1)
        reject_reasons = {r["reason"] for r in rejects}
        self.assertTrue(
            any(r == "unplaceable_row_fragment" for r in reject_reasons))
        # Every row that DID get placed still has a valid status -- the
        # limitation affects free-text reason word order, not designation
        # correctness.
        for r in rows:
            self.assertIn(r["status"], OFFICIAL_STATUSES)
            self.assertTrue(r["player_raw"])

    def test_no_status_outside_taxonomy_silently_accepted(self):
        for fixture in FIXTURES.glob("reference_prod_*.pdf"):
            rows, meta, rejects = parse_official_pdf(fixture.read_bytes())
            for r in rows:
                self.assertIn(r["status"], OFFICIAL_STATUSES,
                              f"{fixture.name}: {r}")


if __name__ == "__main__":
    unittest.main()
