#!/usr/bin/env python
"""test_cbs_identity_v3.py — synthetic suite for `cbs_frame_identity/3` and
`cbs_provenance/3`.

**Synthetic only.** Every section that needs an artifact tree builds its own
miniature contract and masters inside a `TemporaryDirectory`. Nothing is fitted,
no prediction is produced, no accuracy, coverage or profitability figure is
computed, and no feature is related to any outcome. The only real files read are
the five CBS input MANIFESTS, and only to confirm each one's `fit_through_date`
follows the convention it declares.

  A  the three collisions `/2` still had — each shown to COLLIDE under `/2` and
     to be rejected (or, in strict mode, distinguished) under `/3`
  B  every `/2` guarantee that already worked, still holding under `/3`
  C  exactly five artifacts: a subset rejected, a superset rejected, the five
     accepted — and `/2` shown accepting the one-artifact manifest
  D  the test-only escape, and the several independent reasons a real run cannot
     reach it
  E  every required artifact's bound follows its declared convention
  F  zero fits before rejection: `cbs_v8.logistic_fit` call-counted through a
     `cbs_v9.run_player_fold` that must refuse a mismatched frame
"""

from __future__ import annotations

import inspect
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asof_invariant as aoi  # noqa: E402
import cbs_frame_identity as fid2  # noqa: E402  (the frozen /2, for regressions)
import cbs_identity_v3 as v3  # noqa: E402
import cbs_provenance as prov2  # noqa: E402  (the frozen /2, for regressions)
import cbs_provenance_v3 as p3  # noqa: E402
import cbs_v8 as v8  # noqa: E402
import cbs_v9 as v9  # noqa: E402

PASSED = 0
FAILED: list[str] = []
CFG = v9.SYNTHETIC_CONFIG_HASH


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


def raises(name, exc, fn, *a, **kw) -> None:
    try:
        fn(*a, **kw)
        check(name, False, "no exception raised")
    except exc:
        check(name, True)
    except Exception as other:
        check(name, False, f"raised {type(other).__name__}: {other}")


def _try(fn, *a, **kw):
    """Run `fn` and return the exception it raised, or None. For type assertions."""
    try:
        fn(*a, **kw)
        return None
    except Exception as exc:
        return exc


def F(v, uid="r1"):
    """A one-row, one-value frame with a string column label."""
    return pd.DataFrame({"row_uid": [uid], "v": [v]})


def intcol(value):
    """A frame whose second column is labelled with the INTEGER 1."""
    f = pd.DataFrame({"row_uid": ["r1"]})
    f[1] = [value]
    return f


# --------------------------------------------------------------------------
# A -- the three collisions /2 still had
# --------------------------------------------------------------------------

check("A the identity schema is versioned to /3",
      v3.FRAME_IDENTITY_SCHEMA == "cbs_frame_identity/3"
      and v3.SUPERSEDES == fid2.FRAME_IDENTITY_SCHEMA)

# --- (a) integer-labelled columns -----------------------------------------
# /2 does `cols = sorted(map(str, frame.columns))` and then reindexes on the
# STRINGIFIED name, which does not exist; pandas supplies an all-NaN column, so
# the real column's values never enter the digest at all.
A10, A20 = intcol(10), intcol(20)
check("A(a) /2 COLLIDED: two frames differing only inside an int-labelled column",
      fid2.frame_digest(A10) == fid2.frame_digest(A20),
      "if this fails the /2 defect is not what the regression describes")
check("A(a) /2 dropped the int-labelled column entirely",
      fid2.frame_digest(A10) == fid2.frame_digest(
          pd.DataFrame({"row_uid": ["r1"]}).assign(**{"1": [np.nan]})),
      "the reindex filled NaN, so any value in that column hashed the same")
raises("A(a) /3 REJECTS an int-labelled column before hashing",
       v3.NonStringColumnLabel, v3.frame_digest, A10)
raises("A(a) the rejection is a FrameIdentityError subclass",
       v3.FrameIdentityError, v3.frame_digest, A20)
try:
    v3.frame_digest(A10)
    check("A(a) the /3 error explains the dropped-column mechanism", False, "no raise")
except v3.NonStringColumnLabel as exc:
    check("A(a) the /3 error explains the dropped-column mechanism",
          "all-NaN" in str(exc) and "never entered the digest" in str(exc), str(exc))
    check("A(a) the /3 error names the offending label and its type",
          "'int'" in str(exc) or "int" in str(exc), str(exc)[:120])

_f = pd.DataFrame({"row_uid": ["r1"]})
_f[2.5] = [1]
check("A(a) a float column label is refused too",
      isinstance(_try(v3.frame_digest, _f), v3.NonStringColumnLabel))
_dupe = pd.DataFrame([[1, 2, "r1"]], columns=["x", "x", "row_uid"])
check("A(a) a duplicated column label is refused (its sort order is ambiguous)",
      isinstance(_try(v3.frame_digest, _dupe), v3.DuplicateColumnLabel))
check("A(a) a normal all-string frame is unaffected",
      len(v3.frame_digest(F(1))) == 64)

# --- (b) mapping keys 1 vs "1" --------------------------------------------
MK_INT, MK_STR = F({1: "a"}), F({"1": "a"})
check("A(b) /2 COLLIDED: dict keys 1 and '1' inside a cell",
      fid2.frame_digest(MK_INT) == fid2.frame_digest(MK_STR),
      "/2 rendered mapping keys with str(k) — the same defect it fixed for values")
raises("A(b) /3 REJECTS a dict cell before hashing", v3.NonScalarCell,
       v3.frame_digest, MK_INT)
check("A(b) /3 strict mode DISTINGUISHES the two mapping keys instead",
      v3.frame_digest(MK_INT, mode=v3.STRICT_CONTAINERS)
      != v3.frame_digest(MK_STR, mode=v3.STRICT_CONTAINERS))
check("A(b) strict mode still agrees with itself on an identical mapping",
      v3.frame_digest(MK_INT, mode=v3.STRICT_CONTAINERS)
      == v3.frame_digest(F({1: "a"}), mode=v3.STRICT_CONTAINERS))
check("A(b) strict mode does not depend on mapping insertion order",
      v3.frame_digest(F({"a": 1, "b": 2}), mode=v3.STRICT_CONTAINERS)
      == v3.frame_digest(F({"b": 2, "a": 1}), mode=v3.STRICT_CONTAINERS))

# --- (c) list vs tuple ------------------------------------------------------
LST, TUP = F([1, 2]), F((1, 2))
check("A(c) /2 COLLIDED: a list and a tuple shared the 'seq' tag",
      fid2.frame_digest(LST) == fid2.frame_digest(TUP))
check("A(c) /2 collided for an ndarray too",
      fid2.frame_digest(F(np.array([1, 2]))) == fid2.frame_digest(LST))
raises("A(c) /3 REJECTS a list cell before hashing", v3.NonScalarCell,
       v3.frame_digest, LST)
raises("A(c) /3 REJECTS a tuple cell before hashing", v3.NonScalarCell,
       v3.frame_digest, TUP)
raises("A(c) /3 REJECTS an ndarray cell before hashing", v3.NonScalarCell,
       v3.frame_digest, F(np.array([1, 2])))
raises("A(c) /3 REJECTS a set cell before hashing", v3.NonScalarCell,
       v3.frame_digest, F({1, 2}))
check("A(c) /3 strict mode DISTINGUISHES list, tuple, ndarray and set",
      len({v3.frame_digest(x, mode=v3.STRICT_CONTAINERS)
           for x in (F([1, 2]), F((1, 2)), F(np.array([1, 2])), F({1, 2}))}) == 4)
check("A(c) strict mode does not depend on set iteration order",
      v3.frame_digest(F({1, 2, 3}), mode=v3.STRICT_CONTAINERS)
      == v3.frame_digest(F({3, 2, 1}), mode=v3.STRICT_CONTAINERS))

# --- rejection happens BEFORE hashing, not during ---------------------------
check("A the pre-hash contract is a standalone check that raises on its own",
      isinstance(_try(v3.require_digestible, LST), v3.NonScalarCell)
      and isinstance(_try(v3.require_string_columns, A10), v3.NonStringColumnLabel))
_receipt = v3.require_digestible(F(1))
check("A a passing frame gets a precheck receipt naming what was verified",
      _receipt["ok"] and _receipt["string_columns_verified"]
      and _receipt["scalar_cells_verified"] and _receipt["mode"] == v3.SCALAR_ONLY)
check("A the default mode is the reject-before-hashing contract",
      v3.SCALAR_ONLY == v3.REAL_PATH_MODE
      and inspect.signature(v3.frame_digest).parameters["mode"].default
      == v3.SCALAR_ONLY
      and inspect.signature(v3.frames_digest).parameters["mode"].default
      == v3.SCALAR_ONLY)
check("A a strict digest and a scalar-only digest are different strings",
      v3.frame_digest(F(1)) != v3.frame_digest(F(1), mode=v3.STRICT_CONTAINERS),
      "the mode is inside the hashed payload, so the two cannot be confused")
raises("A an unknown mode is refused", v3.FrameIdentityError,
       v3.frame_digest, F(1), mode="lenient")
check("A a /3 digest differs from the /2 digest of the same frame",
      v3.frame_digest(F(1)) != fid2.frame_digest(F(1)))


# --------------------------------------------------------------------------
# B -- every /2 guarantee that worked, still working
# --------------------------------------------------------------------------

PROBES = [None, "", 1, "1", 1.0, "1.0", True, False, 0, "true", b"1"]
_digs = [v3.frame_digest(F(v)) for v in PROBES]
check("B no pair among the whole scalar probe set collides",
      len(set(_digs)) == len(PROBES),
      f"{len(PROBES) - len(set(_digs))} collisions")
check("B null and empty string stay distinct",
      v3.frame_digest(F(None)) != v3.frame_digest(F("")))
check("B integer 1 and string '1' stay distinct",
      v3.frame_digest(F(1)) != v3.frame_digest(F("1")))
check("B integer 1 and float 1.0 stay distinct",
      v3.frame_digest(F(1)) != v3.frame_digest(F(1.0)))
check("B True and integer 1 stay distinct (bool is a subclass of int)",
      v3.frame_digest(F(True)) != v3.frame_digest(F(1)))
check("B False and integer 0 stay distinct",
      v3.frame_digest(F(False)) != v3.frame_digest(F(0)))
check("B None, NaN and NaT remain ONE null (deliberate)",
      v3.frame_digest(F(None)) == v3.frame_digest(F(np.nan))
      == v3.frame_digest(F(pd.NaT)))

BIG = pd.DataFrame({"row_uid": [f"r{i}" for i in range(40)], "a": range(40),
                    "b": [str(i) for i in range(40)],
                    "c": [None if i % 3 else "" for i in range(40)]})
check("B the digest is row-order (shuffle) invariant",
      v3.frame_digest(BIG) == v3.frame_digest(BIG.sample(frac=1, random_state=7)))
check("B the digest is column-order invariant",
      v3.frame_digest(BIG) == v3.frame_digest(BIG[list(reversed(BIG.columns))]))
_mut = BIG.copy()
_mut.loc[0, "a"] = 999
check("B a changed value moves the digest", v3.frame_digest(_mut) != v3.frame_digest(BIG))
_swap = BIG.copy()
_swap["c"] = _swap["c"].map(lambda x: "" if x is None else None)
check("B swapping nulls for empty strings moves the digest",
      v3.frame_digest(_swap) != v3.frame_digest(BIG))
_cast = BIG.copy()
_cast["a"] = _cast["a"].astype(str)
check("B retyping a column moves the digest",
      v3.frame_digest(_cast) != v3.frame_digest(BIG))
raises("B a frame with no row_uid is still refused", v3.FrameIdentityError,
       v3.frame_digest, BIG.drop(columns=["row_uid"]))
raises("B a duplicate row_uid is still refused", v3.FrameIdentityError,
       v3.frame_digest, pd.concat([BIG, BIG.iloc[[0]]], ignore_index=True))
raises("B a null row_uid is still refused", v3.FrameIdentityError,
       v3.frame_digest, BIG.assign(row_uid=BIG.row_uid.mask(BIG.index == 0)))
raises("B a non-DataFrame is still refused", v3.FrameIdentityError,
       v3.frame_digest, {"row_uid": ["r1"]})
check("B frames_digest skips None and covers the rest",
      set(v3.frames_digest({"train": BIG, "test": None, "universe": F(1)}))
      == {"train", "universe"})


# --------------------------------------------------------------------------
# a miniature, fully synthetic five-artifact tree
# --------------------------------------------------------------------------

TEAMS = [10, 20]
PLAYERS = {10: [101, 102], 20: [201, 202]}


def synth(root: Path, seasons=(2098, 2099), n_dates=10):
    """Two teams, two players each, one game per team per date. All five inputs."""
    (root / "data" / "masters").mkdir(parents=True)
    # reconciled at fan-in: the required artifact set is the v3 contract, so
    # the synthetic tree must mirror the v3 layout the code now reads
    (root / "experiments" / "prediction_contract_v3").mkdir(parents=True)
    # This suite deliberately exercises the SUPERSEDED /2 module as well, to show
    # what it used to accept, so the tree carries both layouts. The v2 copies are
    # COPIES; the v3 originals stay exactly where the v10 code reads them.
    (root / "experiments" / "prediction_contract_v2").mkdir(parents=True)
    prow, trow = [], []
    for season in seasons:
        dates = pd.date_range(f"{season}-05-01", periods=n_dates, freq="D")
        for gi, d in enumerate(dates):
            gid = f"G{season}{gi:03d}"
            cut = (d - pd.Timedelta(hours=6)).tz_localize("UTC")
            for ti, tid in enumerate(TEAMS):
                ftm, fgm, fg3m, paint = 10, 30 + gi, 5, 30
                trow.append({"game_id": gid, "team_id": tid, "season": season,
                             "game_date": d.strftime("%Y-%m-%d"),
                             "is_home": 1 if ti == 0 else 0,
                             "pts": ftm + 3 * fg3m + 2 * (fgm - fg3m),
                             "ftm": ftm, "fgm": fgm, "fg3m": fg3m,
                             "points_paint": paint})
                for pid in PLAYERS[tid]:
                    out = (pid == 101 and gi in (3, 4))
                    prow.append({
                        "game_id": gid, "player_id": pid, "team_id": tid,
                        "season": season, "game_date": d.strftime("%Y-%m-%d"),
                        "minutes": None if out else 20.0 + (gi % 5),
                        "starter_flag": 0 if out else 1,
                        "dnp_reason": "DND - Injury/Illness" if out else None,
                        "is_home": 1 if ti == 0 else 0,
                        "pts": None if out else 10, "fga": None if out else 8,
                        "_cut": cut, "_date": d})
    mp, mt = pd.DataFrame(prow), pd.DataFrame(trow)

    pg = mp.copy()
    pg["row_uid"] = [f"pg_{i:05d}" for i in range(len(pg))]
    pg["forecast_cutoff"] = pg["_cut"]
    pg["game_date"] = pd.to_datetime(pg["_date"])
    pg["appeared"] = pg["minutes"].notna()
    pg["fold_id"] = "season:" + pg["season"].astype(str)
    pg = pg[["row_uid", "game_id", "player_id", "team_id", "season", "game_date",
             "forecast_cutoff", "fold_id", "appeared", "minutes", "pts", "fga"]]

    tg = mt.copy()
    tg["row_uid"] = [f"tg_{i:05d}" for i in range(len(tg))]
    tg["game_date"] = pd.to_datetime(tg["game_date"])
    tg["forecast_cutoff"] = (tg["game_date"] - pd.Timedelta(hours=6)).dt.tz_localize("UTC")
    tg["fold_id"] = "season:" + tg["season"].astype(str)
    tg = tg[["row_uid", "game_id", "team_id", "season", "game_date",
             "forecast_cutoff", "fold_id"]]

    mp = mp.drop(columns=["_cut", "_date"])
    mp.to_parquet(root / p3.MASTER_PLAYER, index=False)
    mt.to_parquet(root / p3.MASTER_TEAM, index=False)
    pg.to_parquet(root / p3.PLAYER_GAME, index=False)
    tg.to_parquet(root / p3.TEAM_GAME, index=False)
    import shutil
    import cbs_provenance as _p2legacy
    for _s, _d in ((p3.PLAYER_GAME, _p2legacy.PLAYER_GAME),
                   (p3.TEAM_GAME, _p2legacy.TEAM_GAME)):
        shutil.copy2(root / _s, root / _d)
    (root / p3.CONTRACT_JSON).write_text('{"contract_version":"synthetic/1"}',
                                         encoding="utf-8")
    return pg, tg


def attest_all(root: Path, seasons=(2098, 2099)):
    """Attest all five on the SAME convention the real tree now uses."""
    for rel in p3.DATE_BEARING_ARTIFACTS:
        p3.attest_artifact(rel, root=root, producer="synthetic", granularity="row",
                           dry_run=False)
    inherited = max(aoi.to_utc(aoi.read_manifest(root / rel)["fit_through_date"])
                    for rel in p3.DATE_BEARING_ARTIFACTS)
    import shutil as _sh
    import cbs_provenance as _p2legacy
    _sh.copy2(root / p3.CONTRACT_JSON, root / _p2legacy.CONTRACT_JSON)
    for _rel in (_p2legacy.PLAYER_GAME, _p2legacy.TEAM_GAME):
        p3.attest_artifact(_rel, root=root, producer="synthetic",
                           granularity="row", dry_run=False)
    aoi.write_manifest(root / _p2legacy.CONTRACT_JSON, producer="synthetic",
                       fit_through_date=aoi.bound_from_dates(["2099-05-20"]),
                       fit_through_season=2099, fit_seasons=[2098, 2099],
                       asof_granularity="artifact", notes="synthetic v2 mirror")
    aoi.write_manifest(root / p3.CONTRACT_JSON, producer="synthetic",
                       fit_through_date=inherited, fit_through_season=max(seasons),
                       fit_seasons=list(seasons), asof_granularity="artifact",
                       notes="synthetic policy document; bound INHERITED from the tables",
                       extra={"bound_source": "INHERITED via "
                                              "asof_invariant.bound_from_dates"})


# --------------------------------------------------------------------------
# C -- exactly five artifacts, D -- the test-only escape, E -- bound convention
# --------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    R = Path(td)
    PG, TG = synth(R)
    attest_all(R)
    FRAMES = {"train": PG[PG.season == 2098].reset_index(drop=True),
              "test": PG[PG.season == 2099].reset_index(drop=True),
              "universe": TG}

    # --- C: what /2 allowed --------------------------------------------------
    LEAN = prov2.build_snapshot_manifest(FRAMES, root=R,
                                         artifacts=(prov2.PLAYER_GAME,))
    check("C /2 BUILT a valid one-artifact manifest",
          len(LEAN["artifacts"]) == 1 and prov2.PLAYER_GAME in LEAN["artifacts"],
          "if this fails the /2 hole is not what the regression describes")
    check("C and cbs_v9.snapshot_identity ACCEPTED it",
          len(v9.snapshot_identity(LEAN)) == 64,
          "four of five consumed artifacts were never named, and every downstream "
          "receipt still reported success")

    # --- C: exact key equality, both directions ------------------------------
    MAN5 = p3.build_snapshot_manifest(FRAMES, root=R)
    check("C /3 builds a manifest over exactly the five required artifacts",
          set(MAN5["artifacts"]) == set(p3.CBS_REQUIRED_ARTIFACTS)
          and len(MAN5["artifacts"]) == 5)
    check("C the manifest declares the /3 frame identity schema",
          MAN5["frame_identity_schema"] == v3.FRAME_IDENTITY_SCHEMA
          and MAN5["frame_identity_mode"] == v3.REAL_PATH_MODE)
    check("C the manifest declares the exact-set rule in words",
          "subsets and supersets are both rejected" in MAN5["artifact_set_rule"])
    check("C the manifest carries the carried policy limitations",
          set(MAN5["accepted_policy_limitations"])
          == set(prov2.ACCEPTED_POLICY_LIMITATIONS))
    check("C a five-artifact manifest passes the real-path gate",
          p3.require_real_snapshot_manifest(MAN5)["ok"])

    SUBSET = {**MAN5, "artifacts": {k: v for k, v in MAN5["artifacts"].items()
                                    if k != p3.TEAM_GAME}}
    raises("C a SUBSET manifest is rejected", p3.ArtifactSetError,
           p3.require_real_snapshot_manifest, SUBSET)
    try:
        p3.require_real_snapshot_manifest(SUBSET)
    except p3.ArtifactSetError as exc:
        check("C the subset rejection NAMES what is missing",
              "MISSING" in str(exc) and p3.TEAM_GAME in str(exc), str(exc)[:160])

    SUPER = {**MAN5, "artifacts": {**MAN5["artifacts"],
                                   "data/masters/master_odds.parquet": {"sha256": "b" * 64}}}
    raises("C a SUPERSET manifest is rejected too", p3.ArtifactSetError,
           p3.require_real_snapshot_manifest, SUPER)
    try:
        p3.require_real_snapshot_manifest(SUPER)
    except p3.ArtifactSetError as exc:
        check("C the superset rejection NAMES what is extra",
              "EXTRA" in str(exc) and "master_odds" in str(exc), str(exc)[:160])
    check("C the exact-set error is a ProvenancePreconditionError subclass",
          issubclass(p3.ArtifactSetError, p3.ProvenancePreconditionError),
          "a new failure mode that slips past existing handlers is a new way to "
          "run unnoticed")
    raises("C require_exact_artifact_set rejects the empty set",
           p3.ArtifactSetError, p3.require_exact_artifact_set, ())
    check("C require_exact_artifact_set accepts exactly the five",
          p3.require_exact_artifact_set(p3.CBS_REQUIRED_ARTIFACTS)
          == tuple(p3.CBS_REQUIRED_ARTIFACTS))
    # Reconciled at fan-in. This read "the exact five are the same five /2
    # documented", which was true when the branch wrote it and is now FALSE by
    # design: the row universe moved to prediction_contract_v3, so three of the
    # five are v3 paths. Asserting equality with /2's set would have locked the
    # enforcement onto the SUPERSEDED contract -- the check would have passed
    # while binding the wrong universe. The replacement states what must now hold.
    check("C the required set is exactly five and every one must be attested",
          len(p3.CBS_REQUIRED_ARTIFACTS) == 5
          and set(p3.MUST_BE_ATTESTED) == set(p3.CBS_REQUIRED_ARTIFACTS)
          and p3.N_REQUIRED_ARTIFACTS == 5)
    check("C the three contract artifacts moved to prediction_contract_v3",
          all(a.startswith("experiments/prediction_contract_v3/")
              for a in p3.CBS_REQUIRED_ARTIFACTS if "prediction_contract" in a)
          and sum("prediction_contract" in a
                  for a in p3.CBS_REQUIRED_ARTIFACTS) == 3)
    check("C the two masters are unchanged from /2",
          {a for a in p3.CBS_REQUIRED_ARTIFACTS if a.startswith("data/masters/")}
          == {a for a in prov2.CBS_REQUIRED_ARTIFACTS
              if a.startswith("data/masters/")})
    check("C the superseded /2 set is retained for audit, not erased",
          set(p3.CBS_REQUIRED_ARTIFACTS_V2_SUPERSEDED)
          == set(prov2.CBS_REQUIRED_ARTIFACTS))
    check("C a /3 manifest is REFUSED by cbs_v9, which is bound to /2 identity",
          isinstance(_try(v9.snapshot_identity, MAN5), v9.AdapterBoundaryError),
          "a runner must not accept an identity computed under an encoding it has "
          "not been checked against")

    # --- D: the test-only escape --------------------------------------------
    raises("D _test_artifacts WITHOUT synthetic=True is rejected outright",
           p3.TestEscapeMisuse, p3.build_snapshot_manifest, FRAMES, root=R,
           _test_artifacts=(p3.PLAYER_GAME,))
    try:
        p3.build_snapshot_manifest(FRAMES, root=R, _test_artifacts=(p3.PLAYER_GAME,))
    except p3.TestEscapeMisuse as exc:
        check("D it is REJECTED, not silently ignored and not silently honoured",
              "refused outright" in str(exc), str(exc)[:160])
    raises("D synthetic=True ALONE grants nothing: the exact five still apply",
           p3.ArtifactSetError, p3.require_real_snapshot_manifest,
           {**p3.build_snapshot_manifest(FRAMES, root=R, synthetic=True),
            "artifacts": {p3.PLAYER_GAME: {"sha256": "a" * 64}}})
    _syn_only = p3.build_snapshot_manifest(FRAMES, root=R, synthetic=True)
    check("D synthetic=True alone still produces all five artifacts",
          set(_syn_only["artifacts"]) == set(p3.CBS_REQUIRED_ARTIFACTS))

    ESC = p3.build_snapshot_manifest(FRAMES, root=R, synthetic=True,
                                     _test_artifacts=(p3.PLAYER_GAME,))
    check("D with BOTH tokens the escape works for a synthetic fixture",
          set(ESC["artifacts"]) == {p3.PLAYER_GAME})
    check("D the escape LABELS its own output",
          ESC["synthetic"] is True and ESC["real_path_permitted"] is False
          and ESC["artifact_set_scope"] == "TEST_ONLY_SYNTHETIC_OVERRIDE")
    raises("D and a labelled manifest is refused by the real-path gate",
           p3.ArtifactSetError, p3.require_real_snapshot_manifest, ESC)
    check("D the refusal does not depend on remembering how it was built",
          isinstance(_try(p3.require_real_snapshot_manifest,
                          {k: v for k, v in ESC.items() if k != "artifact_set_scope"}),
                     p3.ArtifactSetError),
          "the synthetic / real_path_permitted stamps carry the refusal")

    _sig = inspect.signature(p3.build_snapshot_manifest)
    check("D both escape parameters are KEYWORD-ONLY",
          _sig.parameters["_test_artifacts"].kind is inspect.Parameter.KEYWORD_ONLY
          and _sig.parameters["synthetic"].kind is inspect.Parameter.KEYWORD_ONLY,
          "no positional call can reach them")
    check("D their defaults are the safe values",
          _sig.parameters["_test_artifacts"].default is None
          and _sig.parameters["synthetic"].default is False)
    check("D neither parameter can arrive from **kwargs",
          not any(p.kind is inspect.Parameter.VAR_KEYWORD
                  for p in _sig.parameters.values()),
          "build_snapshot_manifest accepts no **kwargs to forward a stray key into")

    _rsig = inspect.signature(p3.build_real_snapshot_manifest)
    check("D the REAL entry point has no artifact parameter at all",
          set(_rsig.parameters) == {"frames", "root"},
          f"got {list(_rsig.parameters)}")
    check("D the real entry point accepts no **kwargs either",
          not any(p.kind in (inspect.Parameter.VAR_KEYWORD,
                             inspect.Parameter.VAR_POSITIONAL)
                  for p in _rsig.parameters.values()))
    raises("D so a real caller cannot even NAME the escape", TypeError,
           p3.build_real_snapshot_manifest, FRAMES, root=R,
           _test_artifacts=(p3.PLAYER_GAME,))
    raises("D nor can a real caller pass synthetic=True through it", TypeError,
           p3.build_real_snapshot_manifest, FRAMES, root=R, synthetic=True)
    REALMAN = p3.build_real_snapshot_manifest(FRAMES, root=R)
    check("D the real entry point yields exactly five and passes the gate",
          set(REALMAN["artifacts"]) == set(p3.CBS_REQUIRED_ARTIFACTS)
          and p3.require_real_snapshot_manifest(REALMAN)["ok"]
          and REALMAN["real_path_permitted"] is True)
    check("D the escape name is never read from a CLI flag or an env var",
          "_test_artifacts" not in Path(ROOT / "cbs_provenance_v3.py")
          .read_text(encoding="utf-8").split("def main(")[-1])

    # --- the /2 behaviour that must survive ---------------------------------
    A3 = p3.audit(R)
    check("C /3 keeps ALL-required column semantics, not any-present",
          all(v["complete"] for v in A3["required_columns"].values() if v["exists"]),
          str({k: v["missing"] for k, v in A3["required_columns"].items()
               if not v["complete"]}))
    check("C /3 keeps hard blockers separate from carried policy limitations",
          A3["n_hard_blockers"] == 0 and A3["n_accepted_policy_limitations"] == 2,
          str(A3["hard_blockers"]))
    check("C /3 keeps `provenance_preconditions_met`, never `real_run_permitted`",
          "real_run_permitted" not in A3
          and A3["provenance_preconditions_met"] is True
          and A3["supervisory_authorization_required"] is True)
    check("C /3 keeps attestation over all five artifacts",
          set(A3["attestation"]) == set(p3.CBS_REQUIRED_ARTIFACTS)
          and all(e["must_be_attested"] and e["manifest_valid"]
                  for e in A3["attestation"].values()))
    check("C the audit declares the /3 identity and provenance",
          A3["provenance"] == "cbs_provenance/3"
          and A3["frame_identity_schema"] == v3.FRAME_IDENTITY_SCHEMA
          and A3["supersedes"] == "cbs_provenance/2")

    # a partial schema is still a hard blocker
    _part = pd.read_parquet(R / p3.MASTER_TEAM).drop(columns=["points_paint"])
    _part.to_parquet(R / p3.MASTER_TEAM, index=False)
    _st = p3.schema_status(R)
    check("C a PARTIAL schema is still not complete",
          _st[p3.MASTER_TEAM]["complete"] is False
          and _st[p3.MASTER_TEAM]["missing"] == ["points_paint"])
    check("C and it is still a hard blocker",
          any(b["kind"] == "required_columns_missing"
              for b in p3.audit(R)["hard_blockers"]))
    raises("C manifest construction refuses after the artifact drifts",
           p3.ProvenancePreconditionError, p3.build_real_snapshot_manifest,
           FRAMES, root=R)

# --- E: bound convention, on a synthetic tree and on the real inputs --------
with tempfile.TemporaryDirectory() as td:
    R2 = Path(td)
    synth(R2)
    attest_all(R2)
    _b = p3.bound_convention_status(R2)
    check("E every synthetic artifact follows the bound convention",
          all(e["verdict"] == "follows_convention" for e in _b.values()),
          str({k: (e["verdict"], e["problem"]) for k, e in _b.items()
               if e["verdict"] != "follows_convention"}))
    # re-stamp ONE artifact with the anti-conservative midnight reading
    _m = aoi.read_manifest(R2 / p3.PLAYER_GAME)
    _dates = pd.to_datetime(pd.read_parquet(R2 / p3.PLAYER_GAME,
                                            columns=["game_date"])["game_date"])
    aoi.write_manifest(R2 / p3.PLAYER_GAME, producer=_m["producer"],
                       fit_through_date=_dates.max(),
                       fit_through_season=int(_m["fit_through_season"]),
                       fit_seasons=list(_m["fit_seasons"]),
                       asof_granularity=_m["asof_granularity"],
                       notes="midnight reading of max(game_date)")
    _b2 = p3.bound_convention_status(R2)
    check("E the midnight reading of max(game_date) is caught as anti-conservative",
          _b2[p3.PLAYER_GAME]["verdict"] == "anti_conservative",
          str(_b2[p3.PLAYER_GAME]))
    check("E and it becomes a HARD blocker",
          any(b["kind"] == "bound_convention_violation"
              for b in p3.audit(R2)["hard_blockers"]))
    check("E the blocker explains why midnight is the unsafe direction",
          "BEFORE the games" in _b2[p3.PLAYER_GAME]["problem"])
    # a LATER bound is over-cautious, reported but not a blocker
    aoi.write_manifest(R2 / p3.PLAYER_GAME, producer=_m["producer"],
                       fit_through_date=_dates.max() + pd.Timedelta(days=30),
                       fit_through_season=int(_m["fit_through_season"]),
                       fit_seasons=list(_m["fit_seasons"]),
                       asof_granularity=_m["asof_granularity"], notes="over-cautious")
    _b3 = p3.bound_convention_status(R2)
    check("E a LATER bound is conservative, reported and NOT a blocker",
          _b3[p3.PLAYER_GAME]["verdict"] == "conservative_but_not_exact"
          and not any(b["kind"] == "bound_convention_violation"
                      for b in p3.audit(R2)["hard_blockers"]))

_real = p3.bound_convention_status(ROOT)
if all(e["exists"] for e in _real.values()):
    check("E all five REAL CBS inputs follow their declared bound convention",
          all(e["verdict"] == "follows_convention" for e in _real.values()),
          str({k: (e["verdict"], e["declared"], e["recomputed"])
               for k, e in _real.items() if e["verdict"] != "follows_convention"}))
    check("E all four date-bearing inputs are on bound_from_dates",
          all(_real[r]["declared"] == _real[r]["recomputed"]
              for r in p3.DATE_BEARING_ARTIFACTS))
    check("E player_game.parquet is no longer on the midnight reading",
          _real[p3.PLAYER_GAME]["declared"] == "2026-08-01T12:00:00+00:00"
          and not _real[p3.PLAYER_GAME]["declared"].endswith("T00:00:00+00:00"),
          str(_real[p3.PLAYER_GAME]))
    check("E every date-bearing real input DECLARES bound_from_dates as its source",
          all("bound_from_dates" in str(_real[r]["declared_bound_source"])
              for r in p3.DATE_BEARING_ARTIFACTS),
          str({r: _real[r]["declared_bound_source"]
               for r in p3.DATE_BEARING_ARTIFACTS}))
    check("E contract.json declares an INHERITED bound, and matches the tables",
          "INHERITED" in str(_real[p3.CONTRACT_JSON]["declared_bound_source"]).upper()
          and _real[p3.CONTRACT_JSON]["verdict"] == "follows_convention",
          str(_real[p3.CONTRACT_JSON]))
    check("E the real tree has no bound-convention hard blocker",
          not p3.bound_convention_blockers(_real))
else:
    check("E the real CBS inputs are present to check", False,
          str({k: e["exists"] for k, e in _real.items()}))


# --------------------------------------------------------------------------
# F -- zero fits before rejection (the H6 pattern from tests/test_cbs_v9.py)
# --------------------------------------------------------------------------

def pframe(season, n_players=8, n_dates=40, seed=3):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(f"{season}-05-01", periods=n_dates, freq="D")
    rows = []
    for gi, d in enumerate(dates):
        for pid in range(n_players):
            ap = int(rng.random() < 0.6)
            mn = float(rng.uniform(9, 33)) if ap else 0.0
            cut = (d - pd.Timedelta(hours=6)).tz_localize("UTC")
            row = {"row_uid": f"pg_{season}_{gi:04d}_{pid}", "player_id": f"P{pid}",
                   "season": season, "game_id": f"G{season}{gi:04d}", "game_date": d,
                   "forecast_cutoff": cut.isoformat(),
                   "feature_asof": (cut - pd.Timedelta(hours=6)).isoformat(),
                   "appeared": ap, "minutes": mn,
                   "fga": float(rng.poisson(max(mn, .1) * .35)) if ap else 0.0,
                   "points": float(rng.poisson(max(mn, .1) * .45)) if ap else 0.0}
            for k, lag in zip(v9.REQUIRED_PLAYER_FEATURE_SOURCES, (9, 8, 30)):
                row[k] = (cut - pd.Timedelta(hours=lag)).isoformat()
            rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)


FOLD = "season:2100"
TRAIN, TEST = pframe(2099), pframe(2100, seed=9, n_dates=14)
PUNI = pd.DataFrame({"row_uid": TEST.row_uid, "fold_id": FOLD,
                     "forecast_cutoff": TEST.forecast_cutoff,
                     "appeared": TEST.appeared.astype(bool)})
for _t in v9.PLAYER_TARGETS:
    PUNI[f"prediction_required__{_t}"] = True
    PUNI[f"outcome_scoreable__{_t}"] = (PUNI["appeared"] if _t != "p_active" else True)

# cbs_v9 is bound to the /2 identity, so its manifest is built with /2 digests.
# That is the runner under test here; F is about WHEN the refusal happens.
MAN = {"schema": v9.SNAPSHOT_MANIFEST_SCHEMA,
       "frame_identity_schema": fid2.FRAME_IDENTITY_SCHEMA,
       "captured_at": "2100-09-01T00:00:00+00:00",
       "artifacts": {"player_game.parquet": "a" * 64},
       "frames": fid2.frames_digest({"train": TRAIN, "test": TEST, "universe": PUNI})}
SNAP = v9.snapshot_identity(MAN)

MUT = TEST.copy()
MUT.loc[MUT.index[0], "minutes"] = 999.0
check("F the frames really do differ from what the manifest declares",
      fid2.frame_digest(MUT) != MAN["frames"]["test"]
      and v3.frame_digest(MUT) != v3.frame_digest(TEST))
raises("F a mismatched frame is rejected", v9.FrameBindingError, v9.run_player_fold,
       TRAIN, MUT, FOLD, config_hash=CFG, snapshot_hash=SNAP, snapshot_manifest=MAN,
       universe=PUNI)

_fits = {"n": 0}
_real_fit = v8.logistic_fit
try:
    v8.logistic_fit = lambda *a, **k: (_fits.__setitem__("n", _fits["n"] + 1)
                                       or _real_fit(*a, **k))
    try:
        v9.run_player_fold(TRAIN, MUT, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                           snapshot_manifest=MAN, universe=PUNI)
        check("F the mismatched frame was rejected", False, "no rejection")
    except v9.FrameBindingError:
        check("F the mismatched frame was rejected", True)
    check("F ZERO fits ran before the rejection", _fits["n"] == 0,
          f"{_fits['n']} fits ran first")
finally:
    v8.logistic_fit = _real_fit
check("F the counter would have moved had a fit run",
      callable(_real_fit) and _fits["n"] == 0)

check("F the frozen /2 modules are untouched and still importable",
      fid2.FRAME_IDENTITY_SCHEMA == "cbs_frame_identity/2"
      and prov2.PROVENANCE_ID == "cbs_provenance/2"
      and v9.ARM_ID == "contract_baseline_suite_v9")

print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAIL  {f}")
sys.exit(1 if FAILED else 0)
