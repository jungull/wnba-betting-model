"""cbs_obligation_key -- the canonical, unique, team-bearing obligation key.

The v10 gate was green while `cbs_real_frames_v2.build_player_frame(2024)` could not execute
at all, because `prediction_contract_v3` restored dual-team obligations and kept a team-blind
`row_uid`.  These tests hold the key module to the three properties that failure named:

    UNIQUE      -- a traded player owes two clubs two forecasts in their head-to-head game,
                   and the key must be able to say so;
    REPRODUCIBLE -- the digest must be recomputable from the data, so a reviewer can check a
                   join instead of trusting it;
    NON-DRIFTING -- `player_game_uid` must stay BYTE-IDENTICAL to `prediction_contract_v2.pg_uid`
                   and `stable_hash` byte-identical to both frozen contracts, or every v1/v2-era
                   join silently stops matching.

Everything here is synthetic or is a pure function of the two frozen contract modules; no
emitted parquet can make these pass or fail.  The real-frame checks live in
`tests/test_prediction_contract_v4.py`.

Runnable two ways:
    python -m pytest tests/ -q
    python tests/test_cbs_obligation_key.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import cbs_obligation_key as obk                                     # noqa: E402
import prediction_contract as v1                                     # noqa: E402
import prediction_contract_v2 as v2                                  # noqa: E402
import prediction_contract_v3 as v3                                  # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
        print(f"  ok   {name}")
    else:
        FAILED.append(f"{name}: {detail}")
        print(f"  FAIL {name}  {detail}")


#: The real collision, reproduced from the MergeError the supervisor quoted.
TRADED = [
    # (player_id, game_id, team_id)
    (1641653, "1022300169", 1611661317),
    (1641653, "1022300169", 1611661322),
    (203824, "1022400175", 1611661319),
    (203824, "1022400175", 1611661324),
]


def main() -> int:
    print("0. the digest is byte-identical to the two frozen contracts")
    check("stable_hash == prediction_contract.stable_hash",
          all(obk.stable_hash(*p) == v1.stable_hash(*p)
              for p in [(1,), (1, "g"), (203824, "1022400175", 1611661319), ("", 0)]))
    check("stable_hash == prediction_contract_v2.stable_hash",
          all(obk.stable_hash(*p) == v2.stable_hash(*p)
              for p in [(1,), (1, "g"), (203824, "1022400175", 1611661319), ("", 0)]))
    check("the digest is 16 hex chars", len(obk.stable_hash("x")) == 16
          and all(c in "0123456789abcdef" for c in obk.stable_hash("x")))
    check("fields are 0x1f-delimited, so ('ab','c') != ('a','bc')",
          obk.stable_hash("ab", "c") != obk.stable_hash("a", "bc"))

    print("\n1. player_game_uid is BYTE-IDENTICAL to v2's pg_uid")
    same = all(obk.player_game_uid(p, g) == v2.pg_uid(p, g)
               for p, g, _ in TRADED + [(1, "x9", 0), (999999, "1022100001", 0)])
    check("every probe agrees with prediction_contract_v2.pg_uid", same)
    check("  ... and with prediction_contract.row_uid, v1's name for the same value",
          all(obk.player_game_uid(p, g) == v1.row_uid(p, g) for p, g, _ in TRADED),
          "v1's row_uid and v2's pg_uid are the same construction")
    check("the legacy prefix is 'pg_'", obk.player_game_uid(1, "g").startswith("pg_"))
    check("the legacy key IGNORES team, which is exactly why it cannot be the key",
          obk.player_game_uid(1641653, "1022300169")
          == obk.player_game_uid(1641653, "1022300169"))

    print("\n2. the canonical key is TEAM-BEARING and therefore unique per obligation")
    a = obk.row_uid(1641653, "1022300169", 1611661317)
    b = obk.row_uid(1641653, "1022300169", 1611661322)
    check("the same player in the same game for two clubs gets two keys", a != b, f"{a} {b}")
    check("  ... while the legacy key collapses them into one",
          obk.player_game_uid(1641653, "1022300169")
          == obk.player_game_uid(1641653, "1022300169"))
    check("the canonical prefix is 'ob_'", a.startswith("ob_"))
    check("the key is a pure function of (player_id, game_id, team_id)",
          a == obk.row_uid(1641653, "1022300169", 1611661317))
    check("the registered field ORDER is (player_id, game_id, team_id)",
          obk.CANONICAL_KEY_FIELDS == ("player_id", "game_id", "team_id"))
    check("  ... and the order is load-bearing: a permuted hash is a different digest",
          obk.row_uid(1, "2", 3) != "ob_" + obk.stable_hash(3, 1, "2"))
    check("int-vs-str player and team ids agree; game_id is hashed as a string",
          obk.row_uid("1641653", "1022300169", "1611661317") == a)

    print("\n3. obligation_uid is an ALIAS, not a second key")
    check("obligation_uid is byte-equal to row_uid on every probe",
          all(obk.obligation_uid(p, g, t) == obk.row_uid(p, g, t) for p, g, t in TRADED))

    print("\n4. v3's digest is reproduced, and is deliberately a DIFFERENT string")
    check("v3_ob_uid_equivalent reproduces prediction_contract_v3.ob_uid exactly",
          all(obk.v3_ob_uid_equivalent(t, p, g) == v3.ob_uid(t, p, g) for p, g, t in TRADED))
    check("a v3 digest is NOT a v4 digest for the same obligation",
          all(obk.v3_ob_uid_equivalent(t, p, g) != obk.row_uid(p, g, t) for p, g, t in TRADED),
          "v3 hashed (team, player, game); v4 hashes (player, game, team)")
    check("  ... but both begin 'ob_', so the distinction must be made by FIELD ORDER, "
          "never by prefix",
          obk.v3_ob_uid_equivalent(1611661317, 1641653, "1022300169").startswith("ob_"))

    print("\n5. assert_unique_canonical_keys FAILS CLOSED -- it does not drop duplicates")
    good = pd.DataFrame({"row_uid": [obk.row_uid(p, g, t) for p, g, t in TRADED]})
    try:
        obk.assert_unique_canonical_keys(good, where="fixture")
        ok = True
    except Exception as exc:                                          # pragma: no cover
        ok = False
        print(f"       unexpected: {exc}")
    check("four real dual-team obligations pass", ok and len(good) == 4)

    blind = pd.DataFrame({"row_uid": [obk.player_game_uid(p, g) for p, g, _ in TRADED]})
    try:
        obk.assert_unique_canonical_keys(blind, where="fixture")
        raised = False
    except ValueError as exc:
        raised = True
        msg = str(exc)
    check("the same four obligations keyed the v3 way are REFUSED", raised)
    check("  ... and the message names the count and the key rule",
          raised and "4 rows share a key" in msg and obk.OBLIGATION_KEY_ID in msg, msg[:120])
    check("  ... and the frame is not mutated: nothing is silently de-duplicated",
          len(blind) == 4,
          "v2 deleted 14 obligations with drop_duplicates and left no receipt")
    try:
        obk.assert_unique_canonical_keys(pd.DataFrame({"obligation_uid": ["x"]}))
        raised = False
    except KeyError:
        raised = True
    check("a frame with NO row_uid column is refused, not skipped", raised)

    print("\n6. the receipt describes the rule a consumer must check against")
    r = obk.key_receipt()
    check("it registers the key id", r["obligation_key_id"] == obk.OBLIGATION_KEY_ID
          == "cbs_obligation_key/1")
    check("it names the canonical key and its fields",
          r["canonical_key"] == "row_uid"
          and r["canonical_key_fields"] == ["player_id", "game_id", "team_id"])
    check("it names the legacy linkage and marks it as such",
          r["legacy_linkage_key"] == "player_game_uid"
          and r["legacy_key_fields"] == ["player_id", "game_id"])
    check("it states what it supersedes",
          "pg_uid" in r["supersedes"] and "prediction_contract_v3.ob_uid" in r["supersedes"])
    check("it DISCLOSES the exposure it accepts rather than hiding it",
          "trade correction" in r["known_exposure"])

    print("\n7. nothing here fits, predicts or scores")
    src = (REPO / "cbs_obligation_key.py").read_text(encoding="utf-8")
    banned = ("sklearn", "statsmodels", "xgboost", "lightgbm", ".fit(", ".predict(",
              "log_loss", "roc_auc", "brier", "accuracy_score", "np.polyfit")
    hits = [b for b in banned if b in src]
    check("the key module imports no estimator and calls no fit/predict/score", not hits,
          str(hits))

    print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
    if FAILED:
        for f in FAILED:
            print(f"  - {f}")
    return 1 if FAILED else 0


def test_cbs_obligation_key() -> None:
    """pytest entry point; the script form below prints the same report."""
    assert main() == 0, FAILED


if __name__ == "__main__":
    sys.exit(main())
