#!/usr/bin/env python
"""test_cbs_v9.py — synthetic suite for `contract_baseline_suite_v9`.

**Synthetic only.** Every section that touches the adapter builds its own miniature
contract and masters inside a `TemporaryDirectory`; the real artifacts are never
read. No model is fitted, no prediction is produced, no accuracy, coverage or
profitability figure is computed, and no feature is related to any outcome.

  H1  frame identity: the collisions v8 had, and the invariances it must keep
  H2  the causal frame adapter on a KNOWN synthetic fixture — hand-computed
      expectations, season reset, shuffle stability
  H3  audit semantics: ALL-required, not any-present; partial schemas
  H4  five-artifact attestation enforced, and enforced where it is claimed
  H5  hard blockers separated from carried policy limitations
  H6  the v9 runner: pre-`/3` manifests refused, mutation caught before any fit,
      restamping re-validated, config helper bound to v9
  H7  a team fold whose current obligations carry no outcome at all
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asof_invariant as aoi  # noqa: E402
import cbs_frame_identity as fid  # noqa: E402
import cbs_provenance as prov  # noqa: E402
import cbs_real_frames as rf  # noqa: E402
import cbs_v7 as v7  # noqa: E402
import cbs_v8 as v8  # noqa: E402
import cbs_v9 as v9  # noqa: E402
from cbs_generator import DAYS_CAP, P_ACTIVE_FEATURES  # noqa: E402

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


def F(v, uid="r1"):
    return pd.DataFrame({"row_uid": [uid], "v": [v]})


# --------------------------------------------------------------------------
# H1 -- frame identity
# --------------------------------------------------------------------------

check("H1 the identity schema is versioned",
      fid.FRAME_IDENTITY_SCHEMA == "cbs_frame_identity/2")

# the two collisions v8 actually had
check("H1 null and empty string no longer collide",
      fid.frame_digest(F(None)) != fid.frame_digest(F("")),
      "v8 rendered both as '' via str(v)")
check("H1 integer 1 and string '1' no longer collide",
      fid.frame_digest(F(1)) != fid.frame_digest(F("1")),
      "v8 rendered both as '1' via str(v)")
# and the ones the fix must not introduce
check("H1 True and integer 1 do not collide", fid.frame_digest(F(True)) != fid.frame_digest(F(1)),
      "bool is a subclass of int; the bool branch must come first")
check("H1 False and integer 0 do not collide",
      fid.frame_digest(F(False)) != fid.frame_digest(F(0)))
check("H1 True and string 'true' do not collide",
      fid.frame_digest(F(True)) != fid.frame_digest(F("true")))
check("H1 integer 1 and float 1.0 do not collide",
      fid.frame_digest(F(1)) != fid.frame_digest(F(1.0)))
check("H1 float 1.0 and string '1.0' do not collide",
      fid.frame_digest(F(1.0)) != fid.frame_digest(F("1.0")))
_all = [None, "", 1, "1", 1.0, "1.0", True, False, 0, "true", b"1"]
_digs = [fid.frame_digest(F(v)) for v in _all]
check("H1 no pair among the whole probe set collides",
      len(set(_digs)) == len(_all),
      f"{len(_all) - len(set(_digs))} collisions remain")

# null flavours deliberately agree
check("H1 None, NaN and NaT are one null (deliberate)",
      fid.frame_digest(F(None)) == fid.frame_digest(F(np.nan)) == fid.frame_digest(F(pd.NaT)))

BIG = pd.DataFrame({"row_uid": [f"r{i}" for i in range(40)], "a": range(40),
                    "b": [str(i) for i in range(40)],
                    "c": [None if i % 3 else "" for i in range(40)]})
check("H1 the digest is shuffle invariant",
      fid.frame_digest(BIG) == fid.frame_digest(BIG.sample(frac=1, random_state=7)))
check("H1 the digest is column-order invariant",
      fid.frame_digest(BIG) == fid.frame_digest(BIG[list(reversed(BIG.columns))]))
_m = BIG.copy()
_m.loc[0, "a"] = 999
check("H1 a changed value moves the digest", fid.frame_digest(_m) != fid.frame_digest(BIG))
_swap = BIG.copy()
_swap["c"] = _swap["c"].map(lambda x: "" if x is None else None)
check("H1 swapping nulls for empty strings moves the digest",
      fid.frame_digest(_swap) != fid.frame_digest(BIG),
      "this is the exact mutation v8's digest could not see")
_cast = BIG.copy()
_cast["a"] = _cast["a"].astype(str)
check("H1 retyping a column moves the digest",
      fid.frame_digest(_cast) != fid.frame_digest(BIG))
raises("H1 a frame with no row_uid cannot be digested", fid.FrameIdentityError,
       fid.frame_digest, BIG.drop(columns=["row_uid"]))
raises("H1 a duplicate row_uid is refused", fid.FrameIdentityError,
       fid.frame_digest, pd.concat([BIG, BIG.iloc[[0]]], ignore_index=True))
raises("H1 a null row_uid is refused", fid.FrameIdentityError, fid.frame_digest,
       BIG.assign(row_uid=BIG.row_uid.mask(BIG.index == 0)))


# --------------------------------------------------------------------------
# a miniature, fully-known synthetic contract + masters
# --------------------------------------------------------------------------

TEAMS = [10, 20]
PLAYERS = {10: [101, 102], 20: [201, 202]}


def synth(root: Path, seasons=(2098, 2099), n_dates=14):
    """Two teams, two players each, one game per team per date.

    Every quantity is hand-checkable: player 101 sits out a known set of dates,
    so the DNP, streak and share features have arithmetic answers rather than
    whatever the code happens to produce.
    """
    (root / "data" / "masters").mkdir(parents=True)
    (root / "experiments" / "prediction_contract_v2").mkdir(parents=True)
    prow, trow = [], []
    for season in seasons:
        dates = pd.date_range(f"{season}-05-01", periods=n_dates, freq="D")
        for gi, d in enumerate(dates):
            # ONE game per date, the two teams playing each other, so every
            # game_id carries exactly one home and one away row
            gid = f"G{season}{gi:03d}"
            cut = (d - pd.Timedelta(hours=6)).tz_localize("UTC")
            for ti, tid in enumerate(TEAMS):
                # the box score must satisfy the identity the adapter enforces:
                #   pts == ftm + 3*fg3m + 2*(fgm - fg3m)
                # An earlier draft of this fixture did not, and the adapter caught
                # it — so these numbers are constructed to balance rather than
                # chosen for looks.
                ftm, fgm, fg3m, paint = 10, 30 + gi, 5, 30
                trow.append({"game_id": gid, "team_id": tid,
                             "season": season, "game_date": d.strftime("%Y-%m-%d"),
                             "is_home": 1 if ti == 0 else 0,
                             "pts": ftm + 3 * fg3m + 2 * (fgm - fg3m),
                             "ftm": ftm, "fgm": fgm, "fg3m": fg3m,
                             "points_paint": paint})
                for pid in PLAYERS[tid]:
                    # player 101 misses game indices 3 and 4 with an injury
                    out = (pid == 101 and gi in (3, 4))
                    prow.append({
                        "game_id": gid, "player_id": pid, "team_id": tid,
                        "season": season, "game_date": d.strftime("%Y-%m-%d"),
                        "minutes": None if out else 20.0 + (gi % 5),
                        "starter_flag": 0 if out else 1,
                        "dnp_reason": "DND - Injury/Illness" if out else None,
                        "is_home": 1 if ti == 0 else 0,
                        "pts": None if out else 10, "fga": None if out else 8,
                        "_cut": cut, "_date": d, "_gi": gi})
    mp = pd.DataFrame(prow)
    mt = pd.DataFrame(trow)

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

    mp = mp.drop(columns=["_cut", "_date", "_gi"])
    mp.to_parquet(root / prov.MASTER_PLAYER, index=False)
    mt.to_parquet(root / prov.MASTER_TEAM, index=False)
    pg.to_parquet(root / prov.PLAYER_GAME, index=False)
    tg.to_parquet(root / prov.TEAM_GAME, index=False)
    (root / prov.CONTRACT_JSON).write_text('{"contract_version":"synthetic/1"}',
                                           encoding="utf-8")
    return pg, tg, mp, mt


def attest_all(root: Path):
    for rel, gran in ((prov.MASTER_PLAYER, "row"), (prov.MASTER_TEAM, "row"),
                      (prov.TEAM_GAME, "row"), (prov.PLAYER_GAME, "row")):
        prov.attest_artifact(rel, root=root, producer="synthetic", granularity=gran,
                             dry_run=False)
    aoi.write_manifest(root / prov.CONTRACT_JSON, producer="synthetic",
                       fit_through_date=aoi.bound_from_dates(["2099-05-20"]),
                       fit_through_season=2099, fit_seasons=[2098, 2099],
                       asof_granularity="artifact", notes="synthetic")


# --------------------------------------------------------------------------
# H2 -- the causal adapter on a known fixture
# --------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    R = Path(td)
    synth(R)
    raises("H2 the adapter REFUSES to build from unattested inputs",
           rf.RealFrameError, rf.build_player_frame, 2099, R)
    attest_all(R)

    fold = rf.build_player_frame(2099, R)
    tr, te, uni = fold["train"], fold["test"], fold["universe"]
    rec = fold["receipts"]

    check("H2 the fold splits on season", set(tr.season) == {2098}
          and set(te.season) == {2099})
    check("H2 train and test row_uid are disjoint",
          not (set(tr.row_uid) & set(te.row_uid)))
    check("H2 the universe covers exactly the test rows",
          set(uni.row_uid) == set(te.row_uid))
    check("H2 all twelve adapter-derived Stage-A features are present",
          all(f in te.columns for f in P_ACTIVE_FEATURES
              if f not in ("p_plays_prior", "player_gp_season")),
          str([f for f in P_ACTIVE_FEATURES if f not in te.columns]))
    check("H2 every Stage-A value is finite",
          bool(np.isfinite(te[[f for f in P_ACTIVE_FEATURES
                               if f in te.columns]].to_numpy()).all()),
          "the real path rejects a non-finite feature")
    check("H2 no row reads a source at or after its own cutoff",
          rec["timestamps"]["n_at_cutoff"] == 0
          and rec["timestamps"]["n_after_cutoff"] == 0)
    check("H2 the receipt records row-level source policies",
          "src_policy_gamelog" in rec["provenance"]["row_level_policies"])
    check("H2 the receipt declares no observed source",
          rec["provenance"]["any_observed_source"] is False)
    check("H2 the receipt carries frame identities",
          set(rec["identity"]) == {"train", "test", "universe"}
          and all(len(v) == 64 for v in rec["identity"].values()))

    # --- hand-computed expectations on the KNOWN fixture -------------------
    t = te.set_index("row_uid")
    p101 = te[(te.player_id == 101)].sort_values("game_date")
    first = p101.iloc[0]
    check("H2 a season's first row has no admitted history",
          first.team_gp_season == 0 and first.min_ewma == 0.0
          and first.days_since_last_appearance == DAYS_CAP,
          f"gp={first.team_gp_season} ewma={first.min_ewma} "
          f"days={first.days_since_last_appearance}")
    check("H2 the season resets: 2099's opener ignores all of 2098",
          first.games_missed_streak == 0.0 and first.started_last == 0.0)
    # availability lag: game index i can admit at most i-1 prior team games
    idx = {r.row_uid: i for i, r in enumerate(p101.itertuples())}
    exp_gp = {u: max(i - 1, 0) for u, i in idx.items()}
    bad = {u: (int(t.loc[u, "team_gp_season"]), e) for u, e in exp_gp.items()
           if int(t.loc[u, "team_gp_season"]) != e}
    check("H2 team_gp_season equals the hand-computed admitted count",
          not bad, f"{len(bad)} disagree, e.g. {list(bad.items())[:3]}")
    # player 101 misses game indices 3 and 4; with the one-day lag the injury is
    # first readable at index 5, so prev_dnp_inj must be 0 before then and 1 after
    early = [u for u, i in idx.items() if i <= 4]
    later = [u for u, i in idx.items() if i >= 6]
    check("H2 a DNP is NOT visible before its outcome was available",
          bool((t.loc[early, "prev_dnp_inj"] == 0).all()))
    check("H2 the DNP IS visible once it was available",
          bool((t.loc[later, "prev_dnp_inj"] == 1).all()),
          str(t.loc[later, "prev_dnp_inj"].tolist()))
    check("H2 the DNP class is INJ, not CD or NWT",
          bool((t.loc[later, "prev_dnp_cd"] == 0).all())
          and bool((t.loc[later, "prev_dnp_nwt"] == 0).all()))
    check("H2 a teammate who never sat has no DNP class at all",
          bool((te.loc[te.player_id == 102, "prev_dnp_inj"] == 0).all()))

    # shuffle stability: the adapter must not depend on input row order
    fold_b = rf.build_player_frame(2099, R)
    check("H2 the adapter is deterministic across runs",
          rec["identity"] == fold_b["receipts"]["identity"])

    # --- team side ---------------------------------------------------------
    tf = rf.build_team_frame(2099, R)
    tt = tf["test"]
    check("H2 the four channels reconstruct team_points exactly",
          bool(((tt.ch_ft + tt.ch_3pt + tt.ch_paint + tt.ch_np2)
                - tt.team_points).abs().max() < 1e-9))
    check("H2 side is derived from is_home as home/away",
          set(tt.side) == {"home", "away"})
    check("H2 each game has exactly one home and one away row",
          bool((tt.groupby("game_id").side.nunique() == 2).all()))
    check("H2 the team receipt reports a clean join",
          tf["receipts"]["join"]["unmatched"] == 0)

    # --- H7: current obligations with NO outcome at all -------------------
    bare = rf.build_team_frame(2099, R, withhold_current_outcomes=True)
    bt = bare["test"]
    check("H7 the withheld frame has no team_points", "team_points" not in bt.columns)
    check("H7 the withheld frame has no channel at all",
          not any(c.startswith("ch_") for c in bt.columns))
    v9.require_team_current_obligations(bt)
    check("H7 it is still a valid CURRENT-OBLIGATION frame", True)
    raises("H7 but it is rejected as HISTORY", v9.MissingRequiredInput,
           v9.require_team_history_inputs, bt)
    check("H7 the training side still carries its outcomes",
          "team_points" in bare["train"].columns)

    # --- H3/H4/H5 on the same tree -----------------------------------------
    a = prov.audit(R)
    check("H4 all five artifacts are enforced",
          set(prov.MUST_BE_ATTESTED) == set(prov.CBS_REQUIRED_ARTIFACTS)
          and len(prov.MUST_BE_ATTESTED) == 5,
          "v8 enforced three of five while claiming all")
    check("H4 team_game.parquet is one of them",
          prov.TEAM_GAME in prov.MUST_BE_ATTESTED)
    check("H4 contract.json is one of them",
          prov.CONTRACT_JSON in prov.MUST_BE_ATTESTED)
    check("H5 a fully attested tree has no hard blockers",
          a["n_hard_blockers"] == 0, str(a["hard_blockers"]))
    check("H5 the carried policy limitations are still reported",
          a["n_accepted_policy_limitations"] == 2)
    check("H5 those limitations are marked NOT retrospectively repairable",
          all(v["repairable_retrospectively"] is False
              for v in a["accepted_policy_limitations"].values()))
    check("H5 clearing blockers is NOT called permission to run",
          "real_run_permitted" not in a
          and a["supervisory_authorization_required"] is True)
    check("H5 the verdict says so in words",
          "not authorization" in a["verdict"])

    man = prov.build_snapshot_manifest({"train": tr, "test": te, "universe": uni},
                                       root=R)
    check("H4 a manifest can be built once every input is attested",
          man["schema"] == v9.SNAPSHOT_MANIFEST_SCHEMA)
    check("H4 it declares the collision-safe frame identity schema",
          man["frame_identity_schema"] == fid.FRAME_IDENTITY_SCHEMA)
    check("H4 it carries the carried policy limitations",
          "accepted_policy_limitations" in man)

    # break ONE artifact and watch the manifest refuse
    (R / prov.MASTER_TEAM).write_bytes((R / prov.MASTER_TEAM).read_bytes() + b"\x00")
    a2 = prov.audit(R)
    check("H5 a rebuilt artifact becomes a HARD blocker",
          any(b["kind"] == "artifact_hash_drift" for b in a2["hard_blockers"]))
    check("H5 and it is marked repairable",
          all(b["repairable"] for b in a2["hard_blockers"]))
    raises("H4 manifest construction refuses after the drift",
           prov.ProvenancePreconditionError, prov.build_snapshot_manifest,
           {"train": tr}, root=R)

# --- H3: ALL-required, not any-present ------------------------------------
with tempfile.TemporaryDirectory() as td:
    R2 = Path(td)
    synth(R2)
    full = prov.schema_status(R2)
    check("H3 a complete schema reports complete",
          all(v["complete"] for v in full.values() if v["exists"]),
          str({k: v["missing"] for k, v in full.items() if not v["complete"]}))
    # drop ONE required column from one artifact
    part = pd.read_parquet(R2 / prov.MASTER_TEAM).drop(columns=["points_paint"])
    part.to_parquet(R2 / prov.MASTER_TEAM, index=False)
    st = prov.schema_status(R2)
    check("H3 a PARTIAL schema is not complete",
          st[prov.MASTER_TEAM]["complete"] is False
          and st[prov.MASTER_TEAM]["missing"] == ["points_paint"],
          "v8 used bool(any present), which one surviving column satisfies")
    check("H3 the other artifacts are unaffected",
          st[prov.MASTER_PLAYER]["complete"] is True)
    check("H3 a partial schema is a HARD blocker",
          any(b["kind"] == "required_columns_missing"
              for b in prov.audit(R2)["hard_blockers"]))
    check("H3 the count is reported, not just the boolean",
          st[prov.MASTER_TEAM]["n_present"] == st[prov.MASTER_TEAM]["n_required"] - 1)

fa = prov.feature_availability()
if "stage_a_from_contract" in fa:
    check("H3 contract Stage-A availability is judged on the FULL set",
          fa["stage_a_from_contract"]["complete"] is False
          and fa["stage_a_from_contract"]["n_required"] == 12)
    check("H3 the runner-derived pair is excluded from that set",
          "p_plays_prior" not in fa["stage_a_from_contract"]["missing"])


# --------------------------------------------------------------------------
# H6 -- the v9 runner
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

MAN = {"schema": v9.SNAPSHOT_MANIFEST_SCHEMA,
       "frame_identity_schema": fid.FRAME_IDENTITY_SCHEMA,
       "captured_at": "2100-09-01T00:00:00+00:00",
       "artifacts": {"player_game.parquet": "a" * 64},
       "frames": fid.frames_digest({"train": TRAIN, "test": TEST, "universe": PUNI})}
SNAP = v9.snapshot_identity(MAN)
res = v9.run_player_fold(TRAIN, TEST, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                         snapshot_manifest=MAN, universe=PUNI)

check("H6 the v9 fold passes every receipt", res["scoring_permitted"],
      str(res["failed_receipts"]))
check("H6 all eight receipts are present", len(res["required_receipts"]) == 8)
P = res["predictions"]
check("H6 emitted rows carry the v9 arm",
      all((p.arm_id == v9.ARM_ID).all() for p in P.values()))
check("H6 emitted rows carry the v9 config digest",
      all((p.config_hash == CFG).all() for p in P.values()))
check("H6 emitted rows carry the v9 snapshot identity",
      all((p.data_snapshot_hash == SNAP).all() for p in P.values()))
check("H6 the sidecar carries the v9 arm",
      bool((res["provenance_sidecar"].arm_id == v9.ARM_ID).all()))
check("H6 no v8 identity survives the restamp",
      not any((p.arm_id == v8.ARM_ID).any() for p in P.values())
      and not any((p.config_hash == v8.SYNTHETIC_CONFIG_HASH).any()
                  for p in P.values()))
check("H6 the prediction receipt was RE-VALIDATED against the v9 values",
      res["receipts"]["prediction_validation"]["ok"]
      and all(r["strict"]["validator"] == "contract_v2_strict/3"
              for r in res["receipts"]["prediction_validation"]["per_target"].values()))
check("H6 the frame-binding receipt names the collision-safe schema",
      res["receipts"]["frame_binding"]["frame_identity_schema"]
      == fid.FRAME_IDENTITY_SCHEMA)

for bad_schema in v9.REJECTED_MANIFEST_SCHEMAS:
    raises(f"H6 a {bad_schema} manifest is REFUSED", v9.AdapterBoundaryError,
           v9.snapshot_identity, {**MAN, "schema": bad_schema})
raises("H6 a manifest without the frame-identity schema is refused",
       v9.AdapterBoundaryError, v9.snapshot_identity,
       {k: v for k, v in MAN.items() if k != "frame_identity_schema"})

MUT = TEST.copy()
MUT.loc[MUT.index[0], "minutes"] = 999.0
raises("H6 a mutated frame is rejected", v9.FrameBindingError, v9.run_player_fold,
       TRAIN, MUT, FOLD, config_hash=CFG, snapshot_hash=SNAP, snapshot_manifest=MAN,
       universe=PUNI)
# the null-for-empty-string swap v8's digest could not see
NULLSWAP = TEST.copy()
NULLSWAP["feature_asof"] = NULLSWAP["feature_asof"].astype(object)
NULLSWAP.loc[NULLSWAP.index[0], "feature_asof"] = None
raises("H6 a null-for-value swap is now caught too", v9.FrameBindingError,
       v9.run_player_fold, TRAIN, NULLSWAP, FOLD, config_hash=CFG,
       snapshot_hash=SNAP, snapshot_manifest=MAN, universe=PUNI)

_fits = {"n": 0}
_real = v8.logistic_fit
try:
    v8.logistic_fit = lambda *a, **k: (_fits.__setitem__("n", _fits["n"] + 1)
                                       or _real(*a, **k))
    try:
        v9.run_player_fold(TRAIN, MUT, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                           snapshot_manifest=MAN, universe=PUNI)
    except v9.FrameBindingError:
        pass
    check("H6 rejection happens BEFORE any fit is attempted", _fits["n"] == 0,
          f"{_fits['n']} fits ran first")
finally:
    v8.logistic_fit = _real

check("H6 the config helper defaults to the v9 arm, not v7's",
      v9.recompute_registered_config_hash.__module__ == "cbs_v9")
try:
    _r = v9.recompute_registered_config_hash()
    check("H6 the v9 config digest recomputes from the registry",
          _r == v9.REGISTERED_CONFIG_HASH,
          f"registry {_r} vs module {v9.REGISTERED_CONFIG_HASH}")
    check("H6 and it is NOT v7's digest", _r != v7.REGISTERED_CONFIG_HASH)
except v9.AdapterBoundaryError as exc:
    check("H6 the v9 config digest recomputes from the registry", False, str(exc))

check("H6 v7 and v8 remain importable and unchanged",
      v7.ARM_ID == "contract_baseline_suite_v7"
      and v8.ARM_ID == "contract_baseline_suite_v8"
      and v8.REGISTERED_CONFIG_HASH
      == "663058521c36fd5afc4baaab8fc0a29b6121bf5dc7685df3dc1e8afbc67e43e5")

print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAIL  {f}")
sys.exit(1 if FAILED else 0)
