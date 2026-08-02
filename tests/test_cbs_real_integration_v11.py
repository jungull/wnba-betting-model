#!/usr/bin/env python
"""test_cbs_real_integration_v11.py — the REAL end-to-end no-fit gate, all six seasons.

WHY THIS FILE EXISTS SEPARATELY FROM THE UNIT SUITES
----------------------------------------------------
`tests/test_cbs_real_frames_v3.py`, `tests/test_contract_validator_v4_strict.py`,
`tests/test_prediction_contract_v4.py`, `tests/test_cbs_obligation_key.py` and
`tests/test_cbs_accounting_v11.py` each test a COMPONENT. Every one of them can be green
while the whole path is not runnable end to end — which is precisely the failure
`contract_baseline_suite_v10` shipped: a green gate over a player path whose first real
call raised `MergeError`. A component that passes in isolation proves nothing about the
composition, and the composition is what a run consumes.

So this file executes the WHOLE real path, in one process, from the bytes on disk to a
bound snapshot manifest, and asserts the numbers it produces:

  G0  the checkout itself: the five required artifacts exist, are attested, and their
      recorded digests equal the bytes on disk; `cbs_provenance/4` reports no hard blocker
  G1  the exhaustive season loop: BOTH the player fold and the team fold, for every season
      2021-2026, built with `require_attested=True`. Twelve real frames, twelve asserted
      row counts. A count that differs is reported with its actual value and FAILS; it is
      never relaxed
  G2  the canonical obligation key is unique on every emitted frame, re-derives from
      `(player_id, game_id, team_id)`, and names the rule it followed
  G3  EXACT universe coverage: the union of the six seasons' test frames equals the v4
      contract's 35,627 obligations as a SET of `row_uid` — no row missing, none
      duplicated across folds, none invented
  G4  identity binding: every fold is digested by `cbs_identity_v3` and the digests are
      carried into a snapshot manifest built through `cbs_provenance_v4`. The manifest
      must declare `cbs_snapshot_manifest/5`, the superseded `/1`-`/4` must be refused,
      and the artifact digests the manifest records must equal the bytes on disk
  G5  OBLIGATION COMPLETENESS through the real validator: every required universe row of
      every season gets a forecast SLOT, and `contract_validator_v4_strict` accounts for
      all 35,627 of them with a fan-out of exactly one obligation per key. Three negative
      controls prove the accounting can still fail
  G6  the duplicate-obligation fixture — the REAL collision, player 203824 in game
      1022400175 owing forecasts to both 1611661320 and 1611661321 — flowed through the
      ACTUAL validator, not a mock: one forecast does NOT cover two obligations, and two
      legitimate forecasts are NOT rejected as duplicates
  Z7  ZERO fits, predictions, scores or evaluations, proved three ways: an AST scan of
      every repository module the real path loaded, a RUNTIME sentinel installed before
      the path ran, and an inspection of what is in `sys.modules` afterwards

WHAT IS AND IS NOT DONE HERE
----------------------------
Nothing is fitted, predicted, scored or evaluated. No estimator is imported or
constructed. No forecast is compared to any outcome. The `pred_point` values in G5 and G6
are the CONSTANT 0.5, chosen only to satisfy the prediction frame's schema so that the
validator's OBLIGATION ACCOUNTING can run; no model produces them and no outcome is read
against them. "Coverage" throughout means OBLIGATION COMPLETENESS — did every owed
forecast get a slot — and never predictive accuracy, statistical coverage or profit.

Reading the real artifacts is the point of the file and is authorized. Handing them to an
estimator is not, and Z7 exists to prove it did not happen.

Run as a script (this repository has no pytest installed):

    python tests/test_cbs_real_integration_v11.py
"""

from __future__ import annotations

import ast
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SELF = Path(__file__).resolve()

T_START = time.time()

# ==========================================================================
# the RUNTIME no-fit sentinel, installed BEFORE the real path is imported
# ==========================================================================
# The AST scan in Z7 proves no fitting call is WRITTEN on the path. It cannot prove none
# was EXECUTED — a call reached through getattr, or living in a module the scan did not
# enumerate, would be invisible to it. These sentinels answer the executed question
# directly: they are installed before a single real frame is built, and Z7 asserts that
# none of them ever fired. `numpy.polyfit` is named explicitly because `cbs_v5.py` — a
# registered module this path IMPORTS, for its channel list — really does contain one, and
# a disclosure that the call exists is worth more than a scan tuned until it disappears.
FIT_CALLS: list[str] = []


def _forbidden(label: str):
    def _fn(*_a, **_kw):                              # pragma: no cover - must never run
        FIT_CALLS.append(label)
        raise AssertionError(f"{label} was called on the real no-fit path")
    return _fn


np.polyfit = _forbidden("numpy.polyfit")
np.linalg.lstsq = _forbidden("numpy.linalg.lstsq")

import cbs_identity_v3 as fid                          # noqa: E402
import cbs_obligation_key as obk                       # noqa: E402
import cbs_provenance as prov2                         # noqa: E402
import cbs_provenance_v4 as prov                       # noqa: E402
import cbs_real_frames_v3 as rf3                       # noqa: E402
import cbs_v10 as v10                                  # noqa: E402
import contract_validator_v4_strict as cv4             # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")
        print(f"  FAIL  {name}  {detail}")


def raises(name, exc, fn, *a, **kw) -> None:
    try:
        fn(*a, **kw)
        check(name, False, "no exception raised")
    except exc:
        check(name, True)
    except Exception as other:
        check(name, False, f"raised {type(other).__name__}: {other}")


SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)

#: Measured against the registered v4 contract. These are the season's OBLIGATION counts,
#: not sample sizes for anything: they are the number of rows the contract says are owed a
#: forecast. If one of them moves, the contract moved, and this gate must say so loudly
#: rather than be relaxed to fit.
EXPECTED_PLAYER_TEST = {2021: 4850, 2022: 5563, 2023: 6150,
                        2024: 6096, 2025: 7439, 2026: 5529}
EXPECTED_TEAM_TEST = {2021: 418, 2022: 478, 2023: 520, 2024: 524, 2025: 620, 2026: 430}
EXPECTED_OBLIGATIONS = 35627
#: the 14 obligations the retained legacy `player_game_uid` would collapse (28 rows, 14 ids)
EXPECTED_LEGACY_COLLAPSE = 14

#: the real collision, lifted from the registered artifacts rather than invented
COLL_PID, COLL_GID = 203824, "1022400175"
COLL_TEAMS = {1611661320, 1611661321}

TARGET = "p_active"
H_CONFIG, H_SNAPSHOT, H_MODEL = "c" * 64, "d" * 64, "ab" * 32
SLOT_ARM = "obligation_slot_accounting_probe"


# ==========================================================================
# G0 -- the checkout: the bytes this gate is about to read
# ==========================================================================
print("G0  the checkout: five artifacts, attested, hashes equal to the bytes on disk")

check("G0 cbs_provenance/4 requires exactly five artifacts",
      prov.N_REQUIRED_ARTIFACTS == 5 and len(set(prov.CBS_REQUIRED_ARTIFACTS)) == 5,
      str(prov.CBS_REQUIRED_ARTIFACTS))
for _rel in prov.CBS_REQUIRED_ARTIFACTS:
    check(f"G0 {_rel} exists", (ROOT / _rel).exists())

ATT = prov2.attestation_status(ROOT, prov.CBS_REQUIRED_ARTIFACTS)
for _rel, _e in sorted(ATT.items()):
    check(f"G0 {_rel} is attested", bool(_e["manifest_valid"]), str(_e.get("problem")))
    check(f"G0 {_rel} the attested digest equals the bytes on disk", _e["hash_ok"] is True)
    _sha, _n = prov2.artifact_sha256(ROOT / _rel)
    check(f"G0 {_rel} re-hashing the file reproduces the attested digest",
          _sha == _e["sha256"] and _n == _e["bytes"],
          f"{_sha[:12]} vs {str(_e['sha256'])[:12]}")

# a subset and a superset are both refused: the identity of a run must name every input it
# consumed, and no file a reviewer did not agree was an input
raises("G0 a SUBSET of the required artifact set is refused",
       prov.ArtifactSetError, prov.require_exact_artifact_set,
       prov.CBS_REQUIRED_ARTIFACTS[:4])
raises("G0 a SUPERSET of the required artifact set is refused",
       prov.ArtifactSetError, prov.require_exact_artifact_set,
       tuple(prov.CBS_REQUIRED_ARTIFACTS) + ("data/masters/master_game.parquet",))

AUDIT = prov.audit(ROOT)
check("G0 cbs_provenance/4 reports no hard blocker on the real artifact set",
      AUDIT["n_hard_blockers"] == 0, str(AUDIT["hard_blockers"][:3]))
check("G0 provenance preconditions are met",
      AUDIT["provenance_preconditions_met"] is True)
check("G0 the audit still refuses to call itself an authorization to run",
      AUDIT["supervisory_authorization_required"] is True)

KEYS = AUDIT["obligation_key_status"]
check("G0 the contract's row_uid is UNIQUE", KEYS["unique"] is True,
      str(KEYS.get("n_rows_sharing_a_row_uid")))
check("G0 the contract's row_uid RE-DERIVES from (player_id, game_id, team_id)",
      KEYS["recomputes"] is True)
check("G0 the retained legacy player_game_uid is byte-identical to v2's pg_uid",
      KEYS["legacy_recomputes"] is True)
check("G0 the contract DECLARES the key rule it followed",
      KEYS["declared"] is True and KEYS["expected_key_id"] == obk.OBLIGATION_KEY_ID)
check(f"G0 the contract holds exactly {EXPECTED_OBLIGATIONS} obligations",
      KEYS["rows"] == EXPECTED_OBLIGATIONS, str(KEYS["rows"]))
check("G0 ... and exactly that many distinct canonical keys",
      KEYS["n_distinct_row_uids"] == EXPECTED_OBLIGATIONS,
      str(KEYS["n_distinct_row_uids"]))
check(f"G0 the legacy key would collapse {EXPECTED_LEGACY_COLLAPSE} of them",
      KEYS["rows"] - int(pd.read_parquet(ROOT / prov.PLAYER_GAME,
                                         columns=["player_game_uid"])
                         ["player_game_uid"].nunique()) == EXPECTED_LEGACY_COLLAPSE)
check("G0 the roster provenance is bound to the candidacy record in the bytes",
      AUDIT["roster_binding_status"]["ok"] is True,
      str(AUDIT["roster_binding_status"]["problems"][:2]))
check("G0 the contract declares the membership rule and the cutoff identity",
      AUDIT["contract_declaration_status"]["ok"] is True,
      str(AUDIT["contract_declaration_status"]["problems"][:2]))


# ==========================================================================
# G1 -- the exhaustive season loop: twelve real folds, attested
# ==========================================================================
print("G1  the exhaustive season loop 2021-2026, player AND team, require_attested=True")

PLAYER: dict[int, dict] = {}
TEAM: dict[int, dict] = {}
_t_build = time.time()
for _s in SEASONS:
    _t0 = time.time()
    try:
        PLAYER[_s] = rf3.build_player_frame(_s, ROOT, require_attested=True)
        _ok, _why = True, ""
    except Exception as exc:                                # pragma: no cover - the defect
        _ok, _why = False, f"{type(exc).__name__}: {exc}"
    check(f"G1 build_player_frame({_s}) builds against the v4 contract, attested",
          _ok, _why)
    try:
        TEAM[_s] = rf3.build_team_frame(_s, ROOT, require_attested=True)
        _ok2, _why2 = True, ""
    except Exception as exc:                                # pragma: no cover
        _ok2, _why2 = False, f"{type(exc).__name__}: {exc}"
    check(f"G1 build_team_frame({_s}) builds against the v4 contract, attested",
          _ok2, _why2)
    if _ok and _ok2:
        print(f"    {_s}: player train={len(PLAYER[_s]['train']):>6} "
              f"test={len(PLAYER[_s]['test']):>5} | team train={len(TEAM[_s]['train']):>5} "
              f"test={len(TEAM[_s]['test']):>4}  ({time.time() - _t0:.1f}s)")
BUILD_SECONDS = time.time() - _t_build
print(f"    twelve real folds built in {BUILD_SECONDS:.0f}s")

check("G1 all twelve real folds built", len(PLAYER) == 6 and len(TEAM) == 6,
      f"{sorted(PLAYER)} / {sorted(TEAM)}")

if len(PLAYER) != 6 or len(TEAM) != 6:                      # pragma: no cover
    print("\nthe season loop did not complete; the remaining sections cannot be run")
    print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
    for f in FAILED:
        print(f"  FAILED  {f}")
    sys.exit(1)

for _s in SEASONS:
    _got = len(PLAYER[_s]["test"])
    check(f"G1 the {_s} player fold owes exactly {EXPECTED_PLAYER_TEST[_s]} obligations",
          _got == EXPECTED_PLAYER_TEST[_s],
          f"OBSERVED {_got}, expected {EXPECTED_PLAYER_TEST[_s]} -- the contract moved")
    _gott = len(TEAM[_s]["test"])
    check(f"G1 the {_s} team fold owes exactly {EXPECTED_TEAM_TEST[_s]} obligations",
          _gott == EXPECTED_TEAM_TEST[_s],
          f"OBSERVED {_gott}, expected {EXPECTED_TEAM_TEST[_s]} -- the contract moved")
    check(f"G1 the {_s} player universe is exactly its test frame",
          len(PLAYER[_s]["universe"]) == _got)
    check(f"G1 the {_s} team universe is exactly its test frame",
          len(TEAM[_s]["universe"]) == _gott)

check("G1 the six player folds sum to the contract's whole obligation set",
      sum(len(PLAYER[s]["test"]) for s in SEASONS) == EXPECTED_OBLIGATIONS,
      str(sum(len(PLAYER[s]["test"]) for s in SEASONS)))
check("G1 2021 has no training rows and every later fold has strictly more",
      len(PLAYER[2021]["train"]) == 0
      and all(len(PLAYER[SEASONS[i]]["train"]) < len(PLAYER[SEASONS[i + 1]]["train"])
              for i in range(len(SEASONS) - 1)))
check("G1 every player fold reports zero obligations that appeared with no master box row",
      all(PLAYER[s]["receipts"]["join"]["unmatched_that_appeared"] == 0 for s in SEASONS))
check("G1 every player fold used the TEAM-AWARE obligation join",
      all(PLAYER[s]["receipts"]["team_awareness"]["obligation_join_key"]
          == list(rf3.PLAYER_JOIN_KEY) for s in SEASONS))
check("G1 every player fold used the TEAM-AWARE appearance index",
      all(PLAYER[s]["receipts"]["team_awareness"]["appearance_index_key"]
          == list(rf3.APPEARANCE_INDEX_KEY) for s in SEASONS))
check("G1 every team fold's four channels reconstruct team_points exactly",
      all(float(((TEAM[s]["test"].ch_ft + TEAM[s]["test"].ch_3pt
                  + TEAM[s]["test"].ch_paint + TEAM[s]["test"].ch_np2)
                 - TEAM[s]["test"].team_points).abs().max()) < 1e-9 for s in SEASONS))


# ==========================================================================
# G2 -- the canonical key, on every frame this path emitted
# ==========================================================================
print("G2  canonical obligation keys on all twelve folds")

for _s in SEASONS:
    for _nm in ("train", "test", "universe"):
        _fr = PLAYER[_s][_nm]
        check(f"G2 player {_s} {_nm}: row_uid is unique",
              len(_fr) == _fr["row_uid"].nunique(),
              f"{len(_fr)} rows, {_fr['row_uid'].nunique()} keys")
    for _nm in ("test", "universe"):
        _fr = TEAM[_s][_nm]
        check(f"G2 team {_s} {_nm}: row_uid is unique",
              len(_fr) == _fr["row_uid"].nunique())
    _u = PLAYER[_s]["universe"]
    _want = [obk.row_uid(p, g, t) for p, g, t in
             zip(_u["player_id"], _u["game_id"].astype(str), _u["team_id"])]
    check(f"G2 player {_s} universe: row_uid re-derives from the three registered fields",
          list(_u["row_uid"].astype(str)) == _want)
    check(f"G2 player {_s} universe declares {obk.OBLIGATION_KEY_ID}",
          set(map(str, _u["obligation_key_id"])) == {obk.OBLIGATION_KEY_ID})
    check(f"G2 player {_s} universe: obligation_uid is an exact alias of row_uid",
          list(_u["obligation_uid"].astype(str)) == list(_u["row_uid"].astype(str)))

_collapse = {s: len(PLAYER[s]["universe"])
                - PLAYER[s]["universe"]["player_game_uid"].nunique() for s in SEASONS}
print(f"    obligations the LEGACY team-blind key would collapse: {_collapse}")
check("G2 the legacy key would collapse obligations in every one of the six seasons",
      all(v > 0 for v in _collapse.values()), str(_collapse))
check(f"G2 the legacy key would collapse {EXPECTED_LEGACY_COLLAPSE} obligations in total",
      sum(_collapse.values()) == EXPECTED_LEGACY_COLLAPSE, str(sum(_collapse.values())))
check("G2 the canonical key collapses none of them",
      all(len(PLAYER[s]["universe"]) == PLAYER[s]["universe"]["row_uid"].nunique()
          for s in SEASONS))

# uniqueness is a refusal, not a silent de-duplication, on a REAL frame
_bad = PLAYER[2024]["universe"].copy()
_bad.loc[_bad.index[1], "row_uid"] = _bad.loc[_bad.index[0], "row_uid"]
raises("G2 a non-unique row_uid on a real frame is a hard refusal",
       ValueError, obk.assert_unique_canonical_keys, _bad, "probe")


# ==========================================================================
# G3 -- EXACT universe coverage, as a set, against the registered contract
# ==========================================================================
print("G3  exact universe coverage: set equality against the v4 contract")

CONTRACT = pd.read_parquet(ROOT / prov.PLAYER_GAME,
                           columns=["row_uid", "season", "player_id", "team_id", "game_id"])
CONTRACT_KEYS = set(CONTRACT["row_uid"].astype(str))
check(f"G3 the contract carries {EXPECTED_OBLIGATIONS} distinct obligations",
      len(CONTRACT_KEYS) == EXPECTED_OBLIGATIONS == len(CONTRACT), str(len(CONTRACT_KEYS)))

PER_SEASON_KEYS = {s: set(PLAYER[s]["test"]["row_uid"].astype(str)) for s in SEASONS}
UNIVERSE_KEYS = {s: set(PLAYER[s]["universe"]["row_uid"].astype(str)) for s in SEASONS}
BUILT = set().union(*PER_SEASON_KEYS.values())

_n_rows = sum(len(PLAYER[s]["test"]) for s in SEASONS)
check("G3 no obligation appears in two folds -- the union counts every row once",
      len(BUILT) == _n_rows, f"{len(BUILT)} distinct over {_n_rows} rows")
check("G3 the union of the six test frames EQUALS the contract's obligation set",
      BUILT == CONTRACT_KEYS,
      f"missing {len(CONTRACT_KEYS - BUILT)}, invented {len(BUILT - CONTRACT_KEYS)}")
check("G3   ... no required obligation is MISSING", not (CONTRACT_KEYS - BUILT),
      str(sorted(CONTRACT_KEYS - BUILT)[:5]))
check("G3   ... and no obligation is INVENTED", not (BUILT - CONTRACT_KEYS),
      str(sorted(BUILT - CONTRACT_KEYS)[:5]))
check("G3 the union of the six universes is the same set as the six test frames",
      set().union(*UNIVERSE_KEYS.values()) == BUILT)

_contract_by_season = {int(s): set(g["row_uid"].astype(str))
                       for s, g in CONTRACT.groupby("season")}
for _s in SEASONS:
    check(f"G3 the {_s} fold is exactly the contract's {_s} obligations, as a set",
          PER_SEASON_KEYS[_s] == _contract_by_season[_s],
          f"missing {len(_contract_by_season[_s] - PER_SEASON_KEYS[_s])}, "
          f"invented {len(PER_SEASON_KEYS[_s] - _contract_by_season[_s])}")
    check(f"G3 the {_s} universe is exactly the {_s} test frame, as a set",
          UNIVERSE_KEYS[_s] == PER_SEASON_KEYS[_s])

for _i in range(len(SEASONS) - 1):
    _a, _b = SEASONS[_i], SEASONS[_i + 1]
    check(f"G3 the {_a} and {_b} folds are disjoint",
          not (PER_SEASON_KEYS[_a] & PER_SEASON_KEYS[_b]))

# the TRAIN side is the union of the EARLIER folds, exactly -- so the walk-forward
# partition covers the contract once and only once
for _s in SEASONS[1:]:
    _earlier = set().union(*[PER_SEASON_KEYS[e] for e in SEASONS if e < _s])
    check(f"G3 the {_s} train frame is exactly the union of the earlier folds",
          set(PLAYER[_s]["train"]["row_uid"].astype(str)) == _earlier,
          f"{len(PLAYER[_s]['train'])} rows vs {len(_earlier)} earlier obligations")

TEAM_KEYS = {s: set(TEAM[s]["universe"]["row_uid"].astype(str)) for s in SEASONS}
_team_all = set().union(*TEAM_KEYS.values())
check("G3 the six team universes are pairwise disjoint and sum to their own union",
      len(_team_all) == sum(len(TEAM[s]["universe"]) for s in SEASONS),
      str(len(_team_all)))
_tg_contract = pd.read_parquet(ROOT / prov.TEAM_GAME, columns=["row_uid", "season"])
check("G3 the team universes cover the team contract exactly",
      _team_all == set(_tg_contract["row_uid"].astype(str)),
      f"missing {len(set(_tg_contract['row_uid'].astype(str)) - _team_all)}, "
      f"invented {len(_team_all - set(_tg_contract['row_uid'].astype(str)))}")


# ==========================================================================
# G4 -- identity binding and the snapshot manifest
# ==========================================================================
print("G4  identity binding: twelve folds digested into one cbs_snapshot_manifest/5")

# WHAT IS BOUND, AND WHY THIS SET. The universe names the obligations; the test frame is
# what was actually built for them. Both are bound for both sides of all six folds, so the
# manifest covers the frames a run would consume. The TRAIN frames are deliberately not
# digested: G3 has just proved each one is exactly the union of the earlier folds' test
# frames, so a train digest would restate an identity already bound rather than add one,
# at several seconds per fold.
FRAMES = {}
for _s in SEASONS:
    FRAMES[f"player_universe:{_s}"] = PLAYER[_s]["universe"]
    FRAMES[f"player_test:{_s}"] = PLAYER[_s]["test"]
    FRAMES[f"team_universe:{_s}"] = TEAM[_s]["universe"]
    FRAMES[f"team_test:{_s}"] = TEAM[_s]["test"]

_t0 = time.time()
MANIFEST = prov.build_real_snapshot_manifest(FRAMES, root=ROOT)
print(f"    24 frames digested and bound in {time.time() - _t0:.0f}s")

check("G4 the manifest declares cbs_snapshot_manifest/5",
      MANIFEST["schema"] == "cbs_snapshot_manifest/5" == prov.SNAPSHOT_MANIFEST_SCHEMA,
      str(MANIFEST["schema"]))
check("G4 /1 through /4 are all registered as REFUSED",
      {f"cbs_snapshot_manifest/{i}" for i in (1, 2, 3, 4)}
      <= set(prov.REJECTED_MANIFEST_SCHEMAS),
      str(prov.REJECTED_MANIFEST_SCHEMAS))
check("G4 the v10-era /4 is among them, so one name cannot cover two contracts",
      v10.SNAPSHOT_MANIFEST_SCHEMA == "cbs_snapshot_manifest/4"
      and v10.SNAPSHOT_MANIFEST_SCHEMA in prov.REJECTED_MANIFEST_SCHEMAS)
check("G4 the emitted schema is not itself in the rejected set",
      prov.SNAPSHOT_MANIFEST_SCHEMA not in prov.REJECTED_MANIFEST_SCHEMAS)

# Each refused schema, exercised through the REAL consumer on a manifest of that era. A
# genuine `/1`-`/4` document names no obligation key -- the three fields `/5` added did not
# exist -- so `require_real_snapshot_manifest` refuses it. DISCLOSURE, printed below: that
# refusal comes from the MISSING FIELD, not from the schema string, because
# `require_real_snapshot_manifest` does not read `schema`. The check is written on the
# stable side so a future schema gate cannot invalidate it.
for _i in (1, 2, 3, 4):
    _stale = dict(MANIFEST)
    _stale["schema"] = f"cbs_snapshot_manifest/{_i}"
    _stale.pop("obligation_key_id", None)
    raises(f"G4 a genuine cbs_snapshot_manifest/{_i} document is refused by the real "
           f"consumer", prov.ArtifactSetError, prov.require_real_snapshot_manifest, _stale)
_schema_only = dict(MANIFEST)
_schema_only["schema"] = "cbs_snapshot_manifest/4"
try:
    prov.require_real_snapshot_manifest(_schema_only)
    _schema_read = False
except prov.ArtifactSetError:
    _schema_read = True
print(f"    DISCLOSURE: require_real_snapshot_manifest reads the schema field: "
      f"{_schema_read}; the refusals above bite on the absent obligation_key_id")

RECEIPT = prov.require_real_snapshot_manifest(MANIFEST)
check("G4 the real consumer accepts the manifest this path built", RECEIPT["ok"] is True)
check("G4 the manifest is not synthetic and permits the real path",
      MANIFEST["synthetic"] is False and MANIFEST["real_path_permitted"] is True)
check("G4 the manifest declares the frame-identity schema and the scalar-only mode",
      MANIFEST["frame_identity_schema"] == fid.FRAME_IDENTITY_SCHEMA
      and MANIFEST["frame_identity_mode"] == fid.REAL_PATH_MODE == fid.SCALAR_ONLY)
check("G4 the manifest names the obligation key, the membership rule and the binding",
      MANIFEST["obligation_key_id"] == obk.OBLIGATION_KEY_ID
      and MANIFEST["membership_rule_id"] == prov.MEMBERSHIP_RULE_ID
      and MANIFEST["roster_binding_id"] == prov.ROSTER_BINDING_ID)

check("G4 the manifest covers exactly the five required artifacts",
      set(MANIFEST["artifacts"]) == set(prov.CBS_REQUIRED_ARTIFACTS),
      str(sorted(MANIFEST["artifacts"])))
for _rel, _rec in sorted(MANIFEST["artifacts"].items()):
    _sha, _n = prov2.artifact_sha256(ROOT / _rel)
    check(f"G4 the manifest's digest for {_rel} equals the bytes on disk",
          _rec["sha256"] == _sha and _rec["bytes"] == _n,
          f"{str(_rec['sha256'])[:12]} vs {_sha[:12]}")

check("G4 the manifest binds all twenty-four frames",
      set(MANIFEST["frames"]) == set(FRAMES) and len(MANIFEST["frames"]) == 24,
      str(len(MANIFEST["frames"])))
check("G4 every bound digest is a 64-hex sha256",
      all(isinstance(d, str) and len(d) == 64 and set(d) <= set("0123456789abcdef")
          for d in MANIFEST["frames"].values()))
check("G4 no two of the twenty-four folds share a digest",
      len(set(MANIFEST["frames"].values())) == 24)

# the bound digest is a REAL cbs_identity_v3 digest, recomputed here rather than trusted
_recomputed = fid.frame_digest(PLAYER[2024]["universe"], mode=fid.REAL_PATH_MODE)
check("G4 the manifest's player_universe:2024 digest recomputes exactly",
      MANIFEST["frames"]["player_universe:2024"] == _recomputed,
      f"{MANIFEST['frames']['player_universe:2024'][:12]} vs {_recomputed[:12]}")
check("G4 the digest is deterministic on the same frame",
      fid.frame_digest(TEAM[2021]["universe"]) == fid.frame_digest(TEAM[2021]["universe"]))
_shuffled = TEAM[2021]["universe"].sample(frac=1.0, random_state=0)
check("G4 the digest is independent of row order, as designed",
      fid.frame_digest(_shuffled) == fid.frame_digest(TEAM[2021]["universe"]))
_mutated = TEAM[2021]["universe"].copy()
_mutated.loc[_mutated.index[0], "fold_id"] = "season:9999"
check("G4 ... and moves when a single cell changes",
      fid.frame_digest(_mutated) != fid.frame_digest(TEAM[2021]["universe"]))
_precheck = fid.require_digestible(PLAYER[2026]["universe"], mode=fid.REAL_PATH_MODE)
check("G4 the real frames satisfy the scalar-only identity contract outright",
      _precheck["ok"] is True and _precheck["string_columns_verified"] is True
      and _precheck["scalar_cells_verified"] is True)


# ==========================================================================
# G5 -- obligation completeness through the REAL validator, every season
# ==========================================================================
print("G5  obligation completeness through contract_validator_v4_strict, all six seasons")
# The values below are CONSTANTS that satisfy the prediction frame's schema. They are
# forecast SLOTS, not forecasts: nothing produced them, and no outcome is read against
# them. What is being measured is whether every OWED obligation has a slot -- completeness
# -- which is the only sense in which the word "coverage" is used anywhere in this file.


def slots(universe: pd.DataFrame, asof, *, arm: str = SLOT_ARM) -> pd.DataFrame:
    """A schema-valid, constant-valued forecast slot for every row of `universe`."""
    p = pd.DataFrame({"row_uid": universe["row_uid"].astype(str).to_numpy()})
    p["target_key"] = TARGET
    p["arm_id"] = arm
    p["fold_id"] = universe["fold_id"].astype(str).to_numpy()
    p["forecast_cutoff"] = universe["forecast_cutoff"].to_numpy()
    p["pred_point"] = 0.5                      # a CONSTANT slot value, not a forecast
    p["pred_sd"] = None
    for q in cv4.QUANTILE_COLS:
        p[q] = None
    p["is_fallback"] = False
    p["is_cold_start"] = False
    p["n_prior_games"] = 0
    p["feature_asof"] = asof
    p["config_hash"] = H_CONFIG
    p["data_snapshot_hash"] = H_SNAPSHOT
    p["model_hash"] = H_MODEL
    p["exclusion_reason"] = None
    p["fallback_level"] = 0
    p["component_id"] = "obligation_slot"
    return p


def asof_for(season: int, universe: pd.DataFrame):
    """The fold's OWN feature_asof, taken from the frame the adapter actually built."""
    src = PLAYER[season]["test"].set_index("row_uid")["feature_asof"]
    return src.reindex(universe["row_uid"]).to_numpy()


def bind(fold_id: str) -> dict:
    return dict(expected_arm_id=SLOT_ARM, expected_fold_id=fold_id,
                expected_config_hash=H_CONFIG, expected_snapshot_hash=H_SNAPSHOT)


TOTAL_ACCOUNTED = 0
for _s in SEASONS:
    _u = PLAYER[_s]["universe"]
    _fold = str(_u["fold_id"].iloc[0])
    _r = cv4.validate_strict_v4(slots(_u, asof_for(_s, _u)), _u, TARGET, **bind(_fold))
    check(f"G5 {_s}: the validator accounts for the fold outright", _r["ok"] is True,
          str(_r.get("problems"))[:300])
    check(f"G5 {_s}: it performed the accounting rather than refusing",
          _r.get("accounting_performed") is True)
    check(f"G5 {_s}: {EXPECTED_PLAYER_TEST[_s]} obligations required, all with a slot",
          _r.get("n_required") == _r.get("n_predicted") == EXPECTED_PLAYER_TEST[_s],
          f"{_r.get('n_required')} required, {_r.get('n_predicted')} slots")
    check(f"G5 {_s}: required ROWS equal required KEYS -- no obligation hides in a key",
          _r.get("n_required") == _r.get("n_required_keys"))
    check(f"G5 {_s}: obligation completeness is 1.0 and nothing is uncovered",
          _r.get("prediction_coverage") == 1.0 and _r.get("n_uncovered") == 0)
    check(f"G5 {_s}: exactly one obligation per forecast key",
          _r.get("max_obligations_per_forecast") == 1
          and _r.get("n_duplicate_prediction_rows") == 0
          and _r.get("n_join_fanout_rows") == 0)
    check(f"G5 {_s}: the validator states that this is not an accuracy",
          "not an accuracy" in _r["coverage_semantics"])
    TOTAL_ACCOUNTED += int(_r["n_required"])

check(f"G5 all {EXPECTED_OBLIGATIONS} obligations were accounted for across the six folds",
      TOTAL_ACCOUNTED == EXPECTED_OBLIGATIONS, str(TOTAL_ACCOUNTED))

# three negative controls on the smallest fold: the accounting can still FAIL
_u21 = PLAYER[2021]["universe"]
_fold21 = str(_u21["fold_id"].iloc[0])
_full = slots(_u21, asof_for(2021, _u21))
_missing = cv4.validate_strict_v4(_full.iloc[1:].reset_index(drop=True), _u21, TARGET,
                                  **bind(_fold21))
check("G5 a single missing slot is caught as an uncovered obligation",
      _missing["ok"] is False and _missing["n_uncovered"] == 1,
      str(_missing.get("problems"))[:200])
_dup = cv4.validate_strict_v4(
    pd.concat([_full, _full.iloc[[0]]], ignore_index=True), _u21, TARGET, **bind(_fold21))
check("G5 a doubled slot is caught as a genuine double-answer",
      _dup["ok"] is False and _dup["n_duplicate_prediction_rows"] == 2,
      str(_dup.get("problems"))[:200])
_alien = _full.copy()
_alien.loc[_alien.index[0], "row_uid"] = "ob_notanobligation"
_unknown = cv4.validate_strict_v4(_alien, _u21, TARGET, **bind(_fold21))
check("G5 a slot for a row_uid the universe does not contain is caught",
      _unknown["ok"] is False
      and any("absent from the universe" in p for p in _unknown["problems"]),
      str(_unknown.get("problems"))[:200])
_unbound = cv4.validate_strict_v4(_full, _u21, TARGET, expected_arm_id=SLOT_ARM,
                                  expected_fold_id=_fold21,
                                  expected_config_hash=H_CONFIG)
check("G5 an unbound identity is refused before any accounting happens",
      _unbound["ok"] is False
      and any("identity binding is mandatory" in p for p in _unbound["problems"]))


# ==========================================================================
# G6 -- the duplicate-obligation fixture, through the ACTUAL validator
# ==========================================================================
print("G6  the real duplicate obligation, through contract_validator_v4_strict")

U24 = PLAYER[2024]["universe"]
PAIR = U24[(U24["player_id"] == COLL_PID)
           & (U24["game_id"].astype(str) == COLL_GID)].reset_index(drop=True)
check("G6 the real collision is present in the built 2024 universe: two obligations",
      len(PAIR) == 2, f"{len(PAIR)} rows for player {COLL_PID} in game {COLL_GID}")
check("G6 they belong to the two clubs the correction names",
      set(int(t) for t in PAIR["team_id"]) == COLL_TEAMS,
      str(sorted(int(t) for t in PAIR["team_id"])))
check("G6 their canonical keys are DISTINCT",
      PAIR["row_uid"].nunique() == 2)
check("G6 their legacy player_game_uid is the SAME -- the key that collapsed them",
      PAIR["player_game_uid"].nunique() == 1)
check("G6 both keys re-derive from (player_id, game_id, team_id)",
      list(PAIR["row_uid"].astype(str))
      == [obk.row_uid(p, g, t) for p, g, t in
          zip(PAIR["player_id"], PAIR["game_id"].astype(str), PAIR["team_id"])])
check("G6 exactly one of the two obligations records an appearance",
      int(PAIR["appeared"].astype(bool).sum()) == 1,
      str(list(PAIR["appeared"])))
check("G6 both are REQUIRED forecasts, so neither may be dropped",
      bool(PAIR[f"prediction_required__{TARGET}"].astype(bool).all()))

_fold24 = str(PAIR["fold_id"].iloc[0])
_asof_pair = asof_for(2024, PAIR)
K_APPEARED = str(PAIR.loc[PAIR["appeared"].astype(bool), "row_uid"].iloc[0])
K_OTHER = str(PAIR.loc[~PAIR["appeared"].astype(bool), "row_uid"].iloc[0])

# --- one forecast must NOT cover two obligations -------------------------
ONE = cv4.validate_strict_v4(slots(PAIR.iloc[[0]], _asof_pair[:1]), PAIR, TARGET,
                             **bind(_fold24))
check("G6 ONE forecast against TWO real obligations is REFUSED",
      ONE["ok"] is False, str(ONE.get("problems")))
check("G6   ... and it is named as one uncovered obligation, not as a rounding error",
      ONE["n_uncovered"] == 1 and ONE["n_required"] == 2 and ONE["n_predicted"] == 1,
      f"{ONE.get('n_uncovered')} / {ONE.get('n_required')} / {ONE.get('n_predicted')}")
check("G6   ... completeness is reported as one half, never as one",
      ONE["prediction_coverage"] == 0.5, str(ONE.get("prediction_coverage")))
check("G6   ... and the accounting DID run: the key was sound, the answer was incomplete",
      ONE["accounting_performed"] is True)

# --- two legitimate forecasts must NOT be rejected as duplicates ---------
TWO = cv4.validate_strict_v4(slots(PAIR, _asof_pair), PAIR, TARGET, **bind(_fold24))
check("G6 TWO forecasts, one per club, are ACCEPTED", TWO["ok"] is True,
      str(TWO.get("problems")))
check("G6   ... and are NOT counted as duplicates",
      TWO["n_duplicate_prediction_rows"] == 0 and TWO["n_predicted"] == 2)
check("G6   ... each forecast answers exactly one obligation",
      TWO["max_obligations_per_forecast"] == 1)
check("G6   ... obligation completeness is 1.0 over two required obligations",
      TWO["prediction_coverage"] == 1.0 and TWO["n_required_keys"] == 2)
COMPOSED = cv4.validate_arm_output_v4(slots(PAIR, _asof_pair), PAIR, TARGET,
                                      **bind(_fold24))
check("G6 the COMPOSED gate (historical AND /4) also accepts the two forecasts",
      COMPOSED["ok"] is True, str(COMPOSED["problems"])[:300])

# --- the same two obligations under the SUPERSEDED team-blind key --------
BLIND = PAIR.copy()
BLIND["row_uid"] = BLIND["player_game_uid"]
_ks = cv4.key_status(BLIND, where="team-blind universe")
check("G6 under the team-blind key the two obligations share one id",
      _ks["unique"] is False and _ks["n_obligations_hidden_by_key_collision"] == 1,
      str(_ks.get("n_rows_sharing_a_key")))
BLIND_ONE = cv4.validate_strict_v4(slots(BLIND.iloc[[0]], _asof_pair[:1]), BLIND, TARGET,
                                   **bind(_fold24))
check("G6 the validator REFUSES to account over the team-blind key at all",
      BLIND_ONE["ok"] is False and BLIND_ONE["accounting_performed"] is False)
check("G6   ... rather than reporting the one-covers-two answer as complete",
      "prediction_coverage" not in BLIND_ONE
      and any("invisible to any set-based count" in p for p in BLIND_ONE["problems"]),
      str(BLIND_ONE["problems"])[:200])
check("G6   ... and it says how many obligations the collision hides",
      BLIND_ONE["key_status"]["n_obligations_hidden_by_key_collision"] == 1)
check("G6 the two correct forecasts collide under that key too, which is why it is gone",
      cv4.key_status(slots(BLIND, _asof_pair), require_declared_key=False,
                     where="team-blind predictions")["unique"] is False)


# ==========================================================================
# Z7 -- ZERO fits, predictions, scores or evaluations
# ==========================================================================
print("Z7  zero fits, predictions, scores or evaluations")

ESTIMATOR_MODULES = ("sklearn", "statsmodels", "xgboost", "lightgbm", "torch", "keras",
                     "tensorflow", "catboost", "scipy.optimize", "patsy", "pymc")
ESTIMATOR_CALLS = {"fit", "predict", "predict_proba", "fit_predict", "fit_transform",
                   "score", "partial_fit", "polyfit", "curve_fit", "minimize", "lstsq"}
METRIC_NAMES = {"log_loss", "roc_auc_score", "brier_score_loss", "accuracy_score",
                "r2_score", "mean_squared_error", "mean_absolute_error", "polyfit"}

#: The ONE fitting call reachable from a module this path imports, disclosed rather than
#: excluded from the scan. `cbs_real_frames/3` imports `cbs_v5` for `REQUIRED_CHANNELS`;
#: `cbs_v5` also contains a `np.polyfit` inside its own channel-map builder, which this
#: path never calls. The runtime sentinel below is what proves it never ran.
DISCLOSED_STATIC_FITS = {"cbs_v5.py": ["polyfit"]}


def scan(path: Path) -> dict:
    """AST, not text: prose saying 'nothing is fitted' must not fail a substring test."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    calls: list[str] = []
    names: list[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            imports.append(n.module or "")
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in ESTIMATOR_CALLS:
                calls.append(f.attr)
            if isinstance(f, ast.Name) and f.id in ESTIMATOR_CALLS | METRIC_NAMES:
                calls.append(f.id)
        elif isinstance(n, ast.Name) and n.id in METRIC_NAMES:
            names.append(n.id)
    return {"imports": [m for m in imports
                        if any(m == e or m.startswith(e + ".") for e in ESTIMATOR_MODULES)],
            "calls": sorted(set(calls)), "names": sorted(set(names))}


# every REPOSITORY module the real path actually loaded, enumerated from sys.modules
# rather than from a hand-written list that a future import could quietly outgrow
LOADED = sorted({
    Path(m.__file__).resolve().name
    for m in list(sys.modules.values())
    if getattr(m, "__file__", None)
    and Path(m.__file__).resolve().parent == ROOT
    and Path(m.__file__).resolve().suffix == ".py"})
print(f"    scanning {len(LOADED)} repository modules the real path loaded")
check("Z7 the real path loaded the modules under test",
      {"cbs_real_frames_v3.py", "cbs_provenance_v4.py", "contract_validator_v4_strict.py",
       "cbs_identity_v3.py", "cbs_obligation_key.py"} <= set(LOADED), str(LOADED))

_bad_imports = {}
_trips = {}
for _name in LOADED:
    _rep = scan(ROOT / _name)
    if _rep["imports"]:
        _bad_imports[_name] = _rep["imports"]
    if _rep["calls"] or _rep["names"]:
        _trips[_name] = sorted(set(_rep["calls"] + _rep["names"]))
check("Z7 not one loaded module imports an estimator library", not _bad_imports,
      str(_bad_imports))
check("Z7 the only fitting call written anywhere on the path is the disclosed one",
      _trips == DISCLOSED_STATIC_FITS, str(_trips))

_self = scan(SELF)
check("Z7 this test file imports no estimator library", not _self["imports"],
      str(_self["imports"]))
check("Z7 this test file calls no fit, predict or score method", not _self["calls"],
      str(_self["calls"]))
check("Z7 this test file references no accuracy or error metric", not _self["names"],
      str(_self["names"]))

# the RUNTIME answer: the sentinels were installed before the first frame was built
check("Z7 the numpy fitting sentinels were installed before the real path ran",
      np.polyfit.__name__ == "_fn" and np.linalg.lstsq.__name__ == "_fn")
check("Z7 no fitting call fired during the entire real path", not FIT_CALLS,
      str(FIT_CALLS))
_live = sorted({m for m in sys.modules
                if any(m == e or m.startswith(e.split(".")[0] + ".")
                       for e in ESTIMATOR_MODULES)})
check("Z7 no estimator library is in sys.modules after the whole path executed",
      not _live, str(_live))

# nothing the path EMITTED looks like a prediction, a score or a residual
_emitted = set()
for _s in SEASONS:
    _emitted |= set(PLAYER[_s]["test"].columns) | set(PLAYER[_s]["universe"].columns)
    _emitted |= set(TEAM[_s]["test"].columns) | set(TEAM[_s]["universe"].columns)
_predlike = sorted(c for c in _emitted
                   if any(w in c.lower() for w in ("pred", "score", "yhat", "resid",
                                                   "accur", "error", "profit", "edge"))
                   and not c.startswith(("prediction_required__", "outcome_scoreable__")))
check("Z7 no emitted frame carries a prediction, score, residual or accuracy column",
      not _predlike, str(_predlike))


def _keys(o, acc=None):
    acc = [] if acc is None else acc
    if isinstance(o, dict):
        for k, v in o.items():
            acc.append(str(k).lower())
            _keys(v, acc)
    elif isinstance(o, list):
        for v in o:
            _keys(v, acc)
    return acc


# KEYS, not the JSON blob: a receipt whose prose disclaims accuracy must not fail a
# substring test for the word it is disclaiming. What matters is that no FIELD holds one.
_bad_fields = sorted({k for _s in SEASONS
                      for k in _keys(PLAYER[_s]["receipts"]) + _keys(TEAM[_s]["receipts"])
                      + _keys(MANIFEST)
                      if any(m in k for m in ("accuracy", "log_loss", "auc", "brier",
                                              "rmse", "r_squared", "bankroll", "pnl",
                                              "coefficient", "profit"))})
check("Z7 no field of any receipt or of the manifest holds an accuracy or P&L figure",
      not _bad_fields, str(_bad_fields))
check("Z7 every fold receipt states its own scope in words",
      all("nothing fitted" in PLAYER[s]["receipts"]["scope"]
          and "nothing fitted" in TEAM[s]["receipts"]["scope"] for s in SEASONS))
check("Z7 no module on the path exposes a fit, predict, score or backtest entry point",
      not [f"{m}.{n}" for m in (rf3, prov, cv4, fid, obk)
           for n in ("fit", "predict", "score", "evaluate", "backtest")
           if hasattr(m, n)])
check("Z7 the validator's completeness figure is labelled an obligation count",
      "not an accuracy" in TWO["coverage_semantics"]
      and "never a comparison against an outcome" in TWO["coverage_semantics"])


print(f"\n    total runtime {time.time() - T_START:.0f}s "
      f"(twelve real folds: {BUILD_SECONDS:.0f}s)")
print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAILED  {f}")
sys.exit(1 if FAILED else 0)
