"""
Tests for wikitext_tables.py and parse.py, run against small hand-built wikitext
fixtures (not live network calls). Run with: python -m pytest tests/ -v
or: python tests/test_parse.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wikitext_tables import find_tables, materialize_grid  # noqa: E402
from parse import parse_record  # noqa: E402


WAIVED_WIKITEXT = """
== Player movement ==
===Waived===
{| class="wikitable sortable" style="text-align:center"
|-
! style="width:180px" |Player
! style="width:80px" |Date Waived
! style="width:210px" |Former Team
! class="unsortable" |Ref
|-
| [[Kadi Sissoko]]
| March 15
| [[Phoenix Mercury]]
| <ref name="all moves"/>
|-
| [[Brea Beal]]
| rowspan=2 | May 3
| rowspan=2 | [[Las Vegas Aces]]
| rowspan=2 | <ref>cite</ref>
|-
| Morgan Jones
|}
"""

SIGNED_WIKITEXT = """
===Free agency===
{| class="wikitable"
|-
! Player
! Date signed
! New team
! Former team
! Ref
|-
| [[Some Player]]
| April 1
| [[Seattle Storm]]
| [[Chicago Sky]]
| <ref>cite</ref>
|-
|
| April 2
| [[Chicago Sky]]
| [[Seattle Storm]]
| <ref>cite</ref>
|}
"""

TRADE_WIKITEXT = """
===Trades===
{|class="wikitable" style="text-align:center; width: 95%"
!colspan=4|January
|-
|rowspan=2|January 31
|align=left valign=top|To [[Los Angeles Sparks]]<hr>
* [[Kia Nurse]]
* 2024 first-round pick (Pick 4)
|align=left valign=top|To [[Seattle Storm]]<hr>
* 2026 first-round pick
|align="center"|<ref>cite</ref>
|}
"""

UNRECOGNIZED_WIKITEXT = """
===Mystery Table===
{| class="wikitable"
|-
! Foo
! Bar
|-
| a
| b
|}
"""


def _record(wikitext, season=2024):
    return {
        "found": True,
        "season": season,
        "wikitext_raw": wikitext,
        "wiki_revision_id": 111,
        "wiki_revision_ts": "2024-01-01T00:00:00Z",
        "retrieval_ts": "2024-01-02T00:00:00Z",
        "payload_hash_sha256": "deadbeef",
    }


def test_waived_table_parses_with_rowspan_fill():
    parsed, rejects = parse_record(_record(WAIVED_WIKITEXT))
    players = {r["player"] for r in parsed}
    assert "Kadi Sissoko" in players
    assert "Brea Beal" in players
    assert "Morgan Jones" in players, f"rowspan-filled row missing; got {parsed}"
    morgan = next(r for r in parsed if r["player"] == "Morgan Jones")
    assert morgan["team_from"] == "Las Vegas Aces"
    assert morgan["date_wiki"] == "May 3"
    assert morgan["transaction_type"] == "waived"
    assert rejects == []


def test_signed_table_rejects_row_with_missing_player():
    parsed, rejects = parse_record(_record(SIGNED_WIKITEXT))
    assert len(parsed) == 1
    assert parsed[0]["player"] == "Some Player"
    assert parsed[0]["transaction_type"] == "signed"
    assert len(rejects) == 1
    assert "player" in rejects[0]["reason"]


def test_trade_table_produces_both_sides():
    parsed, rejects = parse_record(_record(TRADE_WIKITEXT))
    players = {(r["player"], r["team_to"], r["team_from"]) for r in parsed}
    assert ("Kia Nurse", "Los Angeles Sparks", "Seattle Storm") in players
    assert all(r["transaction_type"] == "traded" for r in parsed)
    # pick assets must never be emitted as players
    assert all("pick" not in r["player"].lower() for r in parsed)


def test_unrecognized_table_goes_to_rejects_not_dropped():
    parsed, rejects = parse_record(_record(UNRECOGNIZED_WIKITEXT))
    assert parsed == []
    assert len(rejects) == 1
    assert rejects[0]["table_type_guess"] == "unrecognized_simple_table"


def test_not_found_page_produces_single_reject_no_crash():
    rec = {"found": False, "season": 2099, "retrieval_ts": "x", "payload_hash_sha256": "y"}
    parsed, rejects = parse_record(rec)
    assert parsed == []
    assert len(rejects) == 1
    assert "not found" in rejects[0]["reason"]


def test_materialize_grid_basic_shape():
    tables = list(find_tables(WAIVED_WIKITEXT))
    assert len(tables) == 1
    grid = materialize_grid(tables[0].rows)
    assert len(grid) == 4  # header + 3 data rows (Sissoko, Beal, Jones)
    assert len(grid[0]) == 4  # 4 columns


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            failures += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    if failures:
        sys.exit(1)
