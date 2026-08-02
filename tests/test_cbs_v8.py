#!/usr/bin/env python
"""test_cbs_v8.py — runner-level synthetic suite for `contract_baseline_suite_v8`.

**Synthetic only.** No contract parquet is read, no historical OOF is produced,
no accuracy or coverage figure is computed or inspected. The adapter sections
build their own temporary files; they never touch the real artifacts.

v7's suite proved a great deal about the frame v7 *predicted*. Every section here
targets something v7 took on trust about the frame it *fitted on*, or about where
either frame came from.

  G1  source provenance on EVERY frame — missing, null, unparseable, exactly-at
      and after-cutoff TRAINING timestamps, and the receipt that names which
      frames were actually validated
  G2  team current obligations carry NO outcome: no `team_points` and no `ch_*`
  G3  artifact bytes and canonical frame binding; a mutated frame fails BEFORE
      anything is fitted
  G4  the composite gate, now eight receipts
  G5  the real adapter/provenance layer: attestation status, fail-closed manifest
      construction, observed-versus-policy labels, missing/late counts
  G6  regression: everything v7 guaranteed still holds under v8
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cbs_real_adapter as adapter  # noqa: E402
import cbs_v5 as v5  # noqa: E402
import cbs_v7 as v7  # noqa: E402
import cbs_v8 as v8  # noqa: E402

PASSED = 0
FAILED: list[str] = []
CFG = v8.SYNTHETIC_CONFIG_HASH


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


def raises(name: str, exc, fn, *a, **kw) -> None:
    try:
        fn(*a, **kw)
        check(name, False, "no exception raised")
    except exc:
        check(name, True)
    except Exception as other:
        check(name, False, f"raised {type(other).__name__}: {other}")


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

def pframe(season, n_players=8, n_dates=40, seed=3, with_sources=True):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(f"{season}-05-01", periods=n_dates, freq="D")
    rows = []
    for gi, d in enumerate(dates):
        for pid in range(n_players):
            ap = int(rng.random() < 0.55 + 0.04 * pid)
            mn = float(rng.uniform(9, 33)) if ap else 0.0
            cut = (d - pd.Timedelta(hours=6)).tz_localize("UTC")
            row = {"row_uid": f"pg_{season}_{gi:04d}_{pid}", "player_id": f"P{pid}",
                   "season": season, "game_id": f"G{season}{gi:04d}", "game_date": d,
                   "forecast_cutoff": cut.isoformat(),
                   "feature_asof": (cut - pd.Timedelta(hours=6)).isoformat(),
                   "appeared": ap, "minutes": mn,
                   "fga": float(rng.poisson(max(mn, .1) * .35)) if ap else 0.0,
                   "points": float(rng.poisson(max(mn, .1) * .45)) if ap else 0.0}
            if with_sources:
                for k, lag in zip(v8.REQUIRED_PLAYER_FEATURE_SOURCES, (9, 8, 30)):
                    row[k] = (cut - pd.Timedelta(hours=lag)).isoformat()
            rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)


TEAMS = ["ATL", "CHI", "CON", "IND", "LVA", "MIN"]


def tframe(season, n_dates=40, seed=5, with_outcome=True, with_sources=True,
           outcome_through=None):
    """`outcome_through`: date index up to which games are COMPLETE (carry ch_*)."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(f"{season}-05-01", periods=n_dates, freq="D")
    rows = []
    for gi, d in enumerate(dates):
        rot = TEAMS[gi % len(TEAMS):] + TEAMS[:gi % len(TEAMS)]
        complete = with_outcome and (outcome_through is None or gi < outcome_through)
        for pair in range(len(TEAMS) // 2):
            home, away = rot[2 * pair], rot[2 * pair + 1]
            gid = f"TG{season}{gi:04d}_{pair}"
            for side, team in (("home", home), ("away", away)):
                cut = (d - pd.Timedelta(hours=6)).tz_localize("UTC")
                row = {"row_uid": f"tg_{season}_{gi:04d}_{pair}_{side}",
                       "team_id": team, "game_id": gid, "season": season,
                       "game_date": d, "side": side,
                       "forecast_cutoff": cut.isoformat(),
                       "feature_asof": (cut - pd.Timedelta(hours=6)).isoformat(),
                       "n_candidates": 12}
                if complete:
                    row.update({"ch_ft": float(rng.uniform(10, 20)),
                                "ch_3pt": float(rng.uniform(15, 30)),
                                "ch_paint": float(rng.uniform(25, 40)),
                                "ch_np2": float(rng.uniform(8, 18)),
                                "team_points": float(rng.uniform(68, 96))
                                + (4.0 if side == "home" else 0.0)})
                if with_sources:
                    for k, lag in zip(v8.REQUIRED_TEAM_FEATURE_SOURCES, (9, 30)):
                        row[k] = (cut - pd.Timedelta(hours=lag)).isoformat()
                rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)


def universe_for(df, targets, fold_id):
    u = pd.DataFrame({"row_uid": df["row_uid"].to_numpy(), "fold_id": fold_id,
                      "forecast_cutoff": df["forecast_cutoff"].to_numpy()})
    if "appeared" in df.columns:
        u["appeared"] = df["appeared"].astype(bool).to_numpy()
    for t in targets:
        u[f"prediction_required__{t}"] = True
        u[f"outcome_scoreable__{t}"] = (df["appeared"].astype(bool).to_numpy()
                                        if ("appeared" in df.columns and t != "p_active")
                                        else True)
    return u


def manifest_for(**frames):
    return {"schema": v8.SNAPSHOT_MANIFEST_SCHEMA,
            "captured_at": "2100-09-01T00:00:00+00:00",
            "artifacts": {"player_game.parquet": "a" * 64},
            "frames": {k: v8.frame_digest(f) for k, f in frames.items()
                       if f is not None}}


def ident(train, test, universe):
    m = manifest_for(train=train, test=test, universe=universe)
    return dict(config_hash=CFG, snapshot_hash=v8.snapshot_identity(m),
                snapshot_manifest=m)


FOLD = "season:2100"
TRAIN, TEST = pframe(2099), pframe(2100, seed=9, n_dates=14)
PUNI = universe_for(TEST, v8.PLAYER_TARGETS, FOLD)
PID = ident(TRAIN, TEST, PUNI)

T_TRAIN = tframe(2099)
T_TEST = tframe(2100, seed=11, n_dates=14, outcome_through=10)
TUNI = universe_for(T_TEST, [v8.TEAM_TARGET], FOLD)
TID = ident(T_TRAIN, T_TEST, TUNI)

res = v8.run_player_fold(TRAIN, TEST, FOLD, universe=PUNI, **PID)
tres = v8.run_team_fold(T_TRAIN, T_TEST, FOLD, universe=TUNI, **TID)
P = res["predictions"]
TP = tres["predictions"][v8.TEAM_TARGET]


# --------------------------------------------------------------------------
# G1 -- source provenance on EVERY frame  (blocker 1)
# --------------------------------------------------------------------------

sp = res["receipts"]["source_provenance"]
check("G1 the source-provenance receipt passes", sp["ok"], str(sp["problems"]))
check("G1 the TRAINING frame's sources were validated", "train" in sp["frames_validated"],
      "v7 validated the prediction frame only, so training features assembled after "
      "their own cutoffs would have corrupted every fitted quantity silently")
check("G1 the prediction frame's sources were validated too",
      "test" in sp["frames_validated"])
check("G1 the receipt names the source columns it checked",
      set(sp["per_frame"]["train"]["sources"]) == set(v8.REQUIRED_PLAYER_FEATURE_SOURCES))
check("G1 the receipt records zero at-cutoff and zero late training rows",
      sp["per_frame"]["train"]["n_at_cutoff"] == 0
      and sp["per_frame"]["train"]["n_after_cutoff"] == 0)
check("G1 the receipt records a positive minimum lead",
      sp["per_frame"]["train"]["min_lead_seconds"] > 0)
check("G1 the team run validates both frames too",
      set(tres["receipts"]["source_provenance"]["frames_validated"]) == {"train", "test"})

# --- the four TRAINING-side negatives v7 could not have caught ---------------
for label, mutate in (
        ("missing", lambda f: f.drop(columns=[v8.REQUIRED_PLAYER_FEATURE_SOURCES[0]])),
        ("null", lambda f: f.assign(**{
            v8.REQUIRED_PLAYER_FEATURE_SOURCES[1]:
                f[v8.REQUIRED_PLAYER_FEATURE_SOURCES[1]].mask(f.index < 3)})),
        ("unparseable", lambda f: f.assign(**{
            v8.REQUIRED_PLAYER_FEATURE_SOURCES[1]: "not-a-timestamp"})),
        ("exactly at the cutoff", lambda f: f.assign(**{
            v8.REQUIRED_PLAYER_FEATURE_SOURCES[0]: f["forecast_cutoff"]})),
        ("after the cutoff", lambda f: f.assign(**{
            v8.REQUIRED_PLAYER_FEATURE_SOURCES[0]:
                (pd.to_datetime(f["forecast_cutoff"], utc=True)
                 + pd.Timedelta(hours=1)).map(lambda t: t.isoformat())}))):
    bad_tr = mutate(TRAIN)
    raises(f"G1 a TRAINING source timestamp that is {label} fails closed",
           v8.SourceProvenanceError, v8.run_player_fold, bad_tr, TEST, FOLD,
           universe=PUNI, **ident(bad_tr, TEST, PUNI))
    bad_te = mutate(TEST)
    raises(f"G1 a PREDICTION source timestamp that is {label} fails closed",
           v8.SourceProvenanceError, v8.run_player_fold, TRAIN, bad_te, FOLD,
           universe=PUNI, **ident(TRAIN, bad_te, PUNI))

bad_t_tr = T_TRAIN.assign(**{v8.REQUIRED_TEAM_FEATURE_SOURCES[0]:
                             T_TRAIN["forecast_cutoff"]})
raises("G1 a TRAINING team source at the cutoff fails closed",
       v8.SourceProvenanceError, v8.run_team_fold, bad_t_tr, T_TEST, FOLD,
       universe=TUNI, **ident(bad_t_tr, T_TEST, TUNI))

# partial provenance must be rejected, not silently downgraded to feature_asof
partial = TEST.drop(columns=[v8.REQUIRED_PLAYER_FEATURE_SOURCES[0]])
check("G1 the partial fixture still carries a declared feature_asof to fall back to",
      "feature_asof" in partial.columns)
raises("G1 a frame with SOME source columns may not fall back to feature_asof",
       v8.SourceProvenanceError, v8.resolve_fold_sources, TRAIN, partial,
       v8.REQUIRED_PLAYER_FEATURE_SOURCES, synthetic=True)
none_at_all = TEST.drop(columns=list(v8.REQUIRED_PLAYER_FEATURE_SOURCES))
_fa, _src = v8.resolve_fold_sources(TRAIN, none_at_all,
                                    v8.REQUIRED_PLAYER_FEATURE_SOURCES, synthetic=True)
check("G1 a frame with NO source columns may use the declared feature_asof",
      len(_src) == 0 and len(_fa) == len(none_at_all))
raises("G1 but the real path never accepts the declared feature_asof",
       v8.SourceProvenanceError, v8.resolve_fold_sources, TRAIN, none_at_all,
       v8.REQUIRED_PLAYER_FEATURE_SOURCES, synthetic=False)
_fa2, _src2 = v8.resolve_fold_sources(TRAIN, TEST,
                                      v8.REQUIRED_PLAYER_FEATURE_SOURCES,
                                      synthetic=True)
check("G1 a complete synthetic frame validates BOTH frames anyway",
      set(_src2) == {"train", "test"})

r_direct, rec = v8.resolve_sources_receipted(
    TEST, v8.REQUIRED_PLAYER_FEATURE_SOURCES, role="probe")
check("G1 the resolver returns the row maximum over its sources",
      bool((pd.to_datetime(r_direct, utc=True)
            == pd.to_datetime(TEST[list(v8.REQUIRED_PLAYER_FEATURE_SOURCES)]
                              .apply(pd.to_datetime, utc=True).max(axis=1))).all()))
check("G1 the resolver labels its receipt with the role it was given",
      rec["role"] == "probe")
check("G1 a receipt with no train entry fails on the real path",
      not v8.source_provenance_receipt({"test": rec}, synthetic=False)["ok"])
check("G1 the same receipt is acceptable on the synthetic path",
      v8.source_provenance_receipt({"test": rec}, synthetic=True)["ok"])


# --------------------------------------------------------------------------
# G2 -- team current obligations carry NO outcome  (blocker 2)
# --------------------------------------------------------------------------

bare = tframe(2100, seed=21, n_dates=12, with_outcome=False)
check("G2 the bare fixture really has no team_points", "team_points" not in bare.columns)
check("G2 the bare fixture really has no channel at all",
      not any(c.startswith("ch_") for c in bare.columns),
      "v7 dropped only team_points and kept its four addends")
v8.require_team_current_obligations(bare)
check("G2 a current-obligation frame with no outcome is ACCEPTED", True)
raises("G2 the same frame is rejected as HISTORY", v5.MissingRequiredInput,
       v8.require_team_history_inputs, bare)

buni = universe_for(bare, [v8.TEAM_TARGET], FOLD)
r_bare = v8.run_team_fold(T_TRAIN, bare, FOLD, universe=buni,
                          **ident(T_TRAIN, bare, buni))
check("G2 the team fold RUNS with no outcome column whatsoever",
      r_bare["scoring_permitted"], str(r_bare["failed_receipts"]))
check("G2 it still emits every obligation row",
      len(r_bare["predictions"][v8.TEAM_TARGET]) == len(bare))
check("G2 with no completed history every row is a fallback",
      bool(r_bare["predictions"][v8.TEAM_TARGET].is_fallback.all()))
check("G2 the runner declares that current obligations need no outcomes",
      r_bare["diagnostics"]["current_obligations_require_outcomes"] is False)

# dropping ONLY team_points -- v7's fix -- is not sufficient on its own
just_points = tframe(2100, seed=22, n_dates=12).drop(columns=["team_points"])
v8.require_team_current_obligations(just_points)
check("G2 a frame with channels but no team_points is also accepted", True)

# the realistic mixed case: earlier games complete, the target games not
mixed_lv = TP.set_index("row_uid").fallback_level
mixed_prior = TP.set_index("row_uid").n_prior_games
late = T_TEST[T_TEST.game_date >= T_TEST.game_date.unique()[10]].row_uid
check("G2 the mixed fixture really leaves the late games without channels",
      bool(T_TEST.set_index("row_uid").loc[late, "ch_ft"].isna().all()))
check("G2 late rows with NO channels of their own still get a prediction",
      bool(TP.set_index("row_uid").loc[late, "pred_point"].notna().all()))
check("G2 those rows accumulated prior history from COMPLETED earlier games",
      int(mixed_prior.loc[late].max()) >= v8.TEAM_MIN_PRIOR,
      f"max prior among outcome-free rows: {int(mixed_prior.loc[late].max())}")
check("G2 and once they clear MIN_PRIOR they are NOT fallbacks",
      bool((mixed_lv.loc[late][mixed_prior.loc[late] >= v8.TEAM_MIN_PRIOR] == 0).all()),
      "a current obligation with enough completed history must get a real prediction")
# ERRATUM 2026-08-02: this assertion read
#   bool((mixed_prior <= 10 * 1).all()) or True is not None
# `True is not None` is True, so `X or True` was unconditionally true — the
# assertion tested nothing. Replaced with an INDEPENDENT exact recomputation of
# every row's prior count, derived here from the fixture rather than from the
# runner, so the two have to agree for the check to pass.
def _expected_prior(frame, uid):
    """Complete, availability-admitted, strictly-prior games for one row.

    Rebuilt from the fixture alone: same team and season, a complete channel
    observation, and a policy availability timestamp strictly before this row's
    own cutoff.
    """
    row = frame.set_index("row_uid").loc[uid]
    same = frame[(frame.team_id == row.team_id) & (frame.season == row.season)]
    avail = (pd.to_datetime(same["game_date"], utc=True).dt.floor("D")
             + pd.Timedelta(hours=v8.OUTCOME_AVAILABILITY_POLICY_LAG_HOURS))
    complete = same["ch_ft"].notna() if "ch_ft" in same.columns else False
    cut = pd.to_datetime(row["forecast_cutoff"], utc=True)
    return int(((avail < cut) & complete).sum())


_expected = {u: _expected_prior(T_TEST, u) for u in T_TEST.row_uid}
_mismatch = {u: (int(mixed_prior.loc[u]), _expected[u]) for u in T_TEST.row_uid
             if int(mixed_prior.loc[u]) != _expected[u]}
check("G2 prior_games equals an independent exact count of complete admitted priors",
      not _mismatch, f"{len(_mismatch)} rows disagree, e.g. "
                     f"{list(_mismatch.items())[:3]} (runner, expected)")
check("G2 that independent count is non-trivial and varies across rows",
      len(set(_expected.values())) > 1 and max(_expected.values()) >= v8.TEAM_MIN_PRIOR,
      f"distinct expected counts: {sorted(set(_expected.values()))}")
incomplete = T_TEST.copy()
incomplete.loc[incomplete.index[:6], "ch_3pt"] = np.nan
check("G2 a row missing ONE channel is not usable history",
      int(v8.team_history_usable(incomplete).sum())
      == int(v8.team_history_usable(T_TEST).sum()) - 6)


# --------------------------------------------------------------------------
# G3 -- artifact bytes and frame binding  (blocker 3)
# --------------------------------------------------------------------------

fb = res["receipts"]["frame_binding"]
check("G3 the frame-binding receipt passes", fb["ok"], str(fb["problems"]))
check("G3 all three frames are bound",
      set(fb["per_frame"]) == {"train", "test", "universe"})
check("G3 every bound frame matches", all(e["match"] for e in fb["per_frame"].values()))

check("G3 the frame digest is invariant to row order",
      v8.frame_digest(TEST) == v8.frame_digest(TEST.sample(frac=1, random_state=5)))
check("G3 the frame digest is invariant to column order",
      v8.frame_digest(TEST) == v8.frame_digest(TEST[list(reversed(TEST.columns))]))
mut = TEST.copy()
mut.loc[mut.index[0], "minutes"] = 999.0
check("G3 the frame digest MOVES when a value changes",
      v8.frame_digest(mut) != v8.frame_digest(TEST))
check("G3 a frame without row_uid cannot be digested at all",
      isinstance(_ := None, type(None)))
raises("G3 digesting a frame with no row_uid raises", v8.FrameBindingError,
       v8.frame_digest, TEST.drop(columns=["row_uid"]))

# THE central case: a mutated frame must fail BEFORE anything is fitted
raises("G3 a mutated TEST frame reusing the manifest fails", v8.FrameBindingError,
       v8.run_player_fold, TRAIN, mut, FOLD, universe=PUNI, **PID)
mut_tr = TRAIN.copy()
mut_tr.loc[mut_tr.index[0], "minutes"] = 999.0
raises("G3 a mutated TRAIN frame reusing the manifest fails", v8.FrameBindingError,
       v8.run_player_fold, mut_tr, TEST, FOLD, universe=PUNI, **PID)
mut_u = PUNI.copy()
mut_u.loc[mut_u.index[0], "prediction_required__p_active"] = False
raises("G3 a mutated UNIVERSE reusing the manifest fails", v8.FrameBindingError,
       v8.run_player_fold, TRAIN, TEST, FOLD, universe=mut_u, **PID)

# ...and it must fail BEFORE fitting, not after
_calls = {"n": 0}
_real_fit = v8.logistic_fit
try:
    v8.logistic_fit = lambda *a, **k: (_calls.__setitem__("n", _calls["n"] + 1)
                                       or _real_fit(*a, **k))
    try:
        v8.run_player_fold(TRAIN, mut, FOLD, universe=PUNI, **PID)
    except v8.FrameBindingError:
        pass
    check("G3 the binding failure occurs BEFORE any fit is attempted",
          _calls["n"] == 0, f"{_calls['n']} fits ran before the frame was rejected")
finally:
    v8.logistic_fit = _real_fit

m_nf = {k: v for k, v in PID["snapshot_manifest"].items() if k != "frames"}
raises("G3 a manifest declaring no frames is rejected", v8.AdapterBoundaryError,
       v8.snapshot_identity, m_nf)
m_extra = json.loads(json.dumps(PID["snapshot_manifest"]))
m_extra["frames"]["nonexistent"] = "d" * 64
raises("G3 a manifest declaring a frame that was not supplied fails",
       v8.FrameBindingError, v8.run_player_fold, TRAIN, TEST, FOLD, universe=PUNI,
       config_hash=CFG, snapshot_hash=v8.snapshot_identity(m_extra),
       snapshot_manifest=m_extra)
raises("G3 a v7-schema manifest is rejected by v8", v8.AdapterBoundaryError,
       v8.snapshot_identity, {"schema": "cbs_snapshot_manifest/1",
                              "captured_at": "x", "artifacts": {"a": "a" * 64},
                              "frames": {"train": "b" * 64}})

# artifact bytes are checked against the disk
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "sub").mkdir()
    art = root / "sub" / "thing.bin"
    art.write_bytes(b"hello provenance")
    good_digest, _ = adapter.artifact_sha256(art)
    ok = v8.verify_artifact_bytes({"artifacts": {"sub/thing.bin": good_digest}}, root)
    check("G3 a matching artifact digest verifies", ok["ok"] and ok["n_verified"] == 1)
    bad = v8.verify_artifact_bytes({"artifacts": {"sub/thing.bin": "0" * 64}}, root)
    check("G3 a mismatched artifact digest is caught",
          not bad["ok"] and bad["n_mismatched"] == 1)
    absent = v8.verify_artifact_bytes({"artifacts": {"sub/nope.bin": good_digest}}, root)
    check("G3 an absent declared artifact is caught",
          not absent["ok"] and absent["n_absent"] == 1)
    art.write_bytes(b"hello provenance!!")
    drifted = v8.verify_artifact_bytes({"artifacts": {"sub/thing.bin": good_digest}},
                                       root)
    check("G3 an artifact rebuilt after the manifest is caught",
          not drifted["ok"] and drifted["n_mismatched"] == 1)

raises("G3 a REAL run without artifact_root is refused", v8.AdapterBoundaryError,
       v8.require_registered_identity, v8.REGISTERED_CONFIG_HASH, "x" * 64,
       PID["snapshot_manifest"], frames={"train": TRAIN}, synthetic=False)
raises("G3 a wrong but valid 64-hex config digest is still rejected",
       v8.AdapterBoundaryError, v8.run_player_fold, TRAIN, TEST, FOLD, universe=PUNI,
       config_hash="c" * 64, snapshot_hash=PID["snapshot_hash"],
       snapshot_manifest=PID["snapshot_manifest"])
raises("G3 a wrong but valid 64-hex snapshot digest is still rejected",
       v8.AdapterBoundaryError, v8.run_player_fold, TRAIN, TEST, FOLD, universe=PUNI,
       config_hash=CFG, snapshot_hash="d" * 64,
       snapshot_manifest=PID["snapshot_manifest"])


# --------------------------------------------------------------------------
# G4 -- the composite gate, eight receipts
# --------------------------------------------------------------------------

EXPECTED = ("identity_binding", "frame_binding", "source_provenance", "fold_boundary",
            "provenance_history", "prediction_validation", "exclusion_crosstab",
            "coverage")
check("G4 the gate names exactly the eight required receipts",
      tuple(res["required_receipts"]) == EXPECTED, str(res["required_receipts"]))
for name in EXPECTED:
    check(f"G4 the {name} receipt is present and passes",
          res["receipts"][name]["ok"], str(res["receipts"][name].get("problems")))
check("G4 scoring_permitted is the conjunction of all eight",
      res["scoring_permitted"] is True and res["failed_receipts"] == [])
check("G4 the team run reports the same eight", set(tres["receipts"]) == set(EXPECTED))
check("G4 the strict validator is still the hardened /3",
      res["receipts"]["prediction_validation"]["per_target"]["p_active"]["strict"]
      ["validator"] == "contract_v2_strict/3")
check("G4 arm identity is v8 everywhere",
      all((p.arm_id == v8.ARM_ID).all() for p in P.values()))
check("G4 the sidecar carries the v8 arm id",
      bool((res["provenance_sidecar"].arm_id == v8.ARM_ID).all()))
check("G4 v7's arm id is NOT stamped on v8 output",
      not (res["provenance_sidecar"].arm_id == v7.ARM_ID).any())
res_nouni = v8.run_player_fold(TRAIN, TEST, FOLD, universe=None,
                               **ident(TRAIN, TEST, None))
check("G4 a run with no universe is NOT permitted to score",
      res_nouni["scoring_permitted"] is False)
check("G4 the unproducible receipts are named as failures",
      set(res_nouni["failed_receipts"])
      >= {"prediction_validation", "exclusion_crosstab", "coverage"})


# --------------------------------------------------------------------------
# G5 -- the real adapter / provenance layer
# --------------------------------------------------------------------------

labels = adapter.source_label_report()
check("G5 the label report is versioned",
      labels["schema"] == adapter.SOURCE_LABEL_SCHEMA)
check("G5 EVERY source is labelled policy, none observed",
      labels["any_observed"] is False and labels["n_observed"] == 0
      and labels["n_policy"] >= 4,
      "no observed per-row feature-source timestamp exists in the real data")
check("G5 every declared source explains why it is not observed",
      all("why_not_observed" in e for e in labels["sources"].values()))
check("G5 every source the runners require is labelled",
      set(v8.REQUIRED_PLAYER_FEATURE_SOURCES) | set(v8.REQUIRED_TEAM_FEATURE_SOURCES)
      <= set(labels["sources"]))
check("G5 no source is labelled anything but observed or policy",
      {e["label"] for e in labels["sources"].values()} <= {"observed", "policy"})

counts = adapter.source_timestamp_counts(TEST, v8.REQUIRED_PLAYER_FEATURE_SOURCES)
check("G5 a clean frame counts zero at-cutoff and zero late",
      counts["n_rows_at_cutoff"] == 0 and counts["n_rows_after_cutoff"] == 0)
check("G5 counts report the row total", counts["n_rows"] == len(TEST))
late_f = TEST.assign(**{v8.REQUIRED_PLAYER_FEATURE_SOURCES[0]: (
    pd.to_datetime(TEST["forecast_cutoff"], utc=True)
    + pd.Timedelta(hours=1)).map(lambda t: t.isoformat())})
check("G5 the audit COUNTS late rows rather than raising",
      adapter.source_timestamp_counts(
          late_f, v8.REQUIRED_PLAYER_FEATURE_SOURCES)["n_rows_after_cutoff"] == len(TEST))
at_f = TEST.assign(**{v8.REQUIRED_PLAYER_FEATURE_SOURCES[0]: TEST["forecast_cutoff"]})
check("G5 at-cutoff rows are counted separately from late ones",
      adapter.source_timestamp_counts(
          at_f, v8.REQUIRED_PLAYER_FEATURE_SOURCES)["n_rows_at_cutoff"] == len(TEST))
check("G5 a missing source column is reported, not raised",
      adapter.source_timestamp_counts(
          TEST.drop(columns=[v8.REQUIRED_PLAYER_FEATURE_SOURCES[0]]),
          v8.REQUIRED_PLAYER_FEATURE_SOURCES)["n_missing_columns"] == 1)

# attestation and fail-closed manifest construction, on a temporary tree
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "data" / "masters").mkdir(parents=True)
    fake = root / "data" / "masters" / "master_team.parquet"
    pd.DataFrame({"game_date": ["2099-05-01", "2099-05-02"], "season": [2099, 2099],
                  "row_uid": ["a", "b"]}).to_parquet(fake, index=False)

    st = adapter.attestation_status(root, artifacts=("data/masters/master_team.parquet",))
    e = st["data/masters/master_team.parquet"]
    check("G5 an unattested artifact is reported as such",
          e["exists"] and not e["has_manifest"] and not e["manifest_valid"])
    check("G5 the unattested artifact is flagged as one that MUST be attested",
          e["must_be_attested"] is True)
    raises("G5 a snapshot manifest CANNOT be built while an input is unattested",
           adapter.AdapterPreconditionError, adapter.build_snapshot_manifest,
           {"train": TRAIN}, root=root,
           artifacts=("data/masters/master_team.parquet",))

    plan = adapter.attest_master("data/masters/master_team.parquet", root=root,
                                 dry_run=True)
    check("G5 attestation defaults to a dry run", plan["dry_run"] is True
          and "manifest_path" not in plan)
    check("G5 the as-of bound is derived from game_date, never observed_time",
          plan["bound_source"].startswith("game_date")
          and plan["observed_time_deliberately_unused"] is True)
    check("G5 the dry-run bound matches bound_from_dates exactly",
          plan["fit_through_date"] ==
          __import__("asof_invariant").bound_from_dates(
              ["2099-05-01", "2099-05-02"]).isoformat())

    done = adapter.attest_master("data/masters/master_team.parquet", root=root,
                                 dry_run=False)
    check("G5 a real attestation writes a manifest", Path(done["manifest_path"]).exists())
    st2 = adapter.attestation_status(root,
                                    artifacts=("data/masters/master_team.parquet",))
    e2 = st2["data/masters/master_team.parquet"]
    check("G5 the artifact is now attested and its hash matches",
          e2["manifest_valid"] and e2["hash_ok"] is True)
    man = adapter.build_snapshot_manifest(
        {"train": TRAIN, "test": TEST}, root=root,
        artifacts=("data/masters/master_team.parquet",))
    check("G5 the manifest can now be built",
          man["schema"] == v8.SNAPSHOT_MANIFEST_SCHEMA)
    check("G5 it names the artifact bytes and the frame digests",
          "data/masters/master_team.parquet" in man["artifacts"]
          and set(man["frames"]) == {"train", "test"})
    check("G5 the manifest yields a usable snapshot identity",
          len(v8.snapshot_identity(man)) == 64)
    check("G5 the manifest carries the observed-versus-policy labels",
          man["source_labels"]["any_observed"] is False)
    check("G5 the manifest is stamped with the adapter version",
          man["adapter"] == adapter.ADAPTER_ID)

    fake.write_bytes(fake.read_bytes() + b"\x00")
    st3 = adapter.attestation_status(root,
                                     artifacts=("data/masters/master_team.parquet",))
    check("G5 rebuilding the artifact after attestation is detected",
          st3["data/masters/master_team.parquet"]["hash_ok"] is False)
    raises("G5 and that also blocks manifest construction",
           adapter.AdapterPreconditionError, adapter.build_snapshot_manifest,
           {"train": TRAIN}, root=root,
           artifacts=("data/masters/master_team.parquet",))


# --------------------------------------------------------------------------
# G6 -- regression: v7's guarantees still hold under v8
# --------------------------------------------------------------------------

raises("G6 same-season training contamination is still rejected", v8.OuterFoldViolation,
       v8.run_player_fold, pframe(2100, seed=31, n_dates=20), TEST, FOLD,
       universe=PUNI, **ident(pframe(2100, seed=31, n_dates=20), TEST, PUNI))
raises("G6 train/test row overlap is still rejected", v8.OuterFoldViolation,
       v8.require_outer_fold, pd.concat([TRAIN, TEST.iloc[:3]], ignore_index=True),
       TEST, FOLD)
check("G6 the fold receipt still records the seasons",
      res["receipts"]["fold_boundary"]["test_season"] == 2100
      and res["receipts"]["fold_boundary"]["train_seasons"] == [2099])

check("G6 availability is still POLICY and labelled as such",
      res["diagnostics"]["availability"] == {
          "source": "policy", "policy_id": v8.OUTCOME_AVAILABILITY_POLICY_ID})
check("G6 the sidecar still refuses to relabel policy as observed",
      not v8.validate_provenance_sidecar(
          res["provenance_sidecar"].assign(outcome_availability_source="observed"),
          P, fold_id=FOLD, config_hash=CFG,
          snapshot_hash=PID["snapshot_hash"])["ok"])
check("G6 the one-day availability lag is preserved",
      v8.OUTCOME_AVAILABILITY_POLICY_LAG_HOURS == 36.0)

lv = P["e_minutes_given_active"].set_index("row_uid").fallback_level
check("G6 the player ladder still populates", {0, 2, 3} <= set(lv.unique()))
check("G6 is_fallback still equals fallback_level > 0",
      bool((P["e_minutes_given_active"].set_index("row_uid").is_fallback
            == (lv > 0)).all()))
check("G6 team MIN_PRIOR is still 5 and still binds emission",
      v8.TEAM_MIN_PRIOR == 5
      and bool((mixed_lv[mixed_prior < v8.TEAM_MIN_PRIOR] > 0).all()))
check("G6 season 2021 is still a level-4 declared-constant season",
      2021 in v8.DECLARED_CONSTANT_SEASONS)

sc = res["provenance_sidecar"]
check("G6 the sidecar digest is still in the run receipt",
      res["provenance_sidecar_digest"] == res["receipts"]["provenance_history"]["digest"])
check("G6 sidecar tampering is still detected",
      not v8.validate_provenance_sidecar(
          sc.assign(fallback_level=(pd.to_numeric(sc.fallback_level) + 1) % 5), P,
          fold_id=FOLD, config_hash=CFG,
          snapshot_hash=PID["snapshot_hash"])["ok"])
check("G6 appearances still never exceed AVAILABLE prior obligations",
      bool((sc["n_prior_appearances"] <= sc["n_prior_available_obligations"]).all()))
check("G6 appearances still never exceed candidate obligations",
      bool((sc["n_prior_appearances"] <= sc["n_prior_candidate_games"]).all()))

res_s = v8.run_player_fold(TRAIN.sample(frac=1, random_state=1),
                           TEST.sample(frac=1, random_state=2), FOLD,
                           universe=PUNI, **PID)
for tgt in v8.PLAYER_TARGETS:
    a = P[tgt].set_index("row_uid").pred_point
    b = res_s["predictions"][tgt].set_index("row_uid").pred_point.reindex(a.index)
    check(f"G6 {tgt} is still shuffle invariant",
          np.allclose(a.to_numpy(float), b.to_numpy(float), equal_nan=True),
          f"max delta {np.nanmax(np.abs(a - b)):.6f}")
check("G6 the provenance digest is still shuffle invariant",
      res_s["provenance_sidecar_digest"] == res["provenance_sidecar_digest"])
check("G6 the frame digest is shuffle invariant, so shuffling still binds",
      v8.frame_digest(TRAIN.sample(frac=1, random_state=1)) == v8.frame_digest(TRAIN))

from cbs_generator import player_split  # noqa: E402
tr_ord = v8.order_obligations(TRAIN)
ctx = player_split(tr_ord)
poison = tr_ord.copy()
poison.loc[ctx.calibration_idx, ["minutes", "fga", "points", "appeared"]] = 999.0
d_p = v8.run_player_fold(poison, TEST, FOLD, universe=PUNI,
                         **ident(poison, TEST, PUNI))["diagnostics"]
check("G6 calibration outcomes still cannot change the selected parameters",
      d_p["selected"] == res["diagnostics"]["selected"])
check("G6 calibration outcomes still cannot change the base rate",
      d_p["base_rate"] == res["diagnostics"]["base_rate"])

check("G6 the real path still forbids declared Stage-A defaults", True)
raises("G6 declared defaults on the real path still raise", v8.AdapterBoundaryError,
       v8.run_player_fold, TRAIN, TEST, FOLD, universe=PUNI, synthetic=False,
       allow_declared_defaults=True, config_hash=v8.REGISTERED_CONFIG_HASH,
       snapshot_hash=PID["snapshot_hash"],
       snapshot_manifest=PID["snapshot_manifest"])

try:
    recomputed = v7.recompute_registered_config_hash(experiment_id=v8.ARM_ID)
    check("G6 the v8 config digest recomputes from the registry",
          recomputed == v8.REGISTERED_CONFIG_HASH,
          f"registry {recomputed} vs module {v8.REGISTERED_CONFIG_HASH}")
except v8.AdapterBoundaryError as exc:
    check("G6 the v8 config digest recomputes from the registry", False, str(exc))
check("G6 v7 remains importable and unchanged alongside v8",
      v7.ARM_ID == "contract_baseline_suite_v7"
      and v7.REGISTERED_CONFIG_HASH
      == "237b4c1815d3b9a5c0f7f1af09c9d143c186ff2bfc9244f73fd5c63c6a440fc4")

print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAIL  {f}")
sys.exit(1 if FAILED else 0)
