"""Tests for the regime-D prospective forecast log (ROADMAP "four regimes", D).

Runnable two ways:
    python -m pytest tests/test_forecast_log.py -q   (if pytest is installed)
    python tests/test_forecast_log.py                (plain runner, no deps)

Coverage map:
  (a) chain verifies clean on N appends; genesis sentinel; canonical lines;
      record_idx contiguity; tip hash recomputable
  (b) tampering — editing / deleting / reordering / inserting a middle
      record is detected and localized to the right index; tail-truncation
      limitation is explicit; appends to a broken chain are refused
  (c) duplicate (game_id, forecast_cutoff, model_version_hash) refusal,
      including ISO-normalized cutoff equivalence ("Z" == "+00:00")
  (d) field validation: bet-decision enum, stake coherence, market-source
      provenance, core-prediction requirements, NaN refusal (no-imputation)
  (e) nullable fields round-trip (present-as-null and fully populated)
  (f) hash determinism: model-config dicts and DataFrames (same -> same,
      changed -> changed, column-order invariance, row-order flag, dtype
      width stability, NaN/multiplicity handling)
  (g) prospective_start: None before first record; first logged_at_utc
      after; refuses a broken ledger
  (h) fsync path exercised on every append
"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evalharness import forecast_log as fl  # noqa: E402
from evalharness.forecast_log import (  # noqa: E402
    GENESIS_PREV_SHA256,
    ChainVerificationError,
    DuplicateForecastError,
    ForecastValidationError,
    canonical_json,
    hash_dataframe,
    hash_model_config,
    log_forecast,
    prospective_start,
    read_forecasts,
    record_sha256,
    verify_chain,
)


def _raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return True
    except Exception as e:  # pragma: no cover
        raise AssertionError(
            f"expected {exc_type.__name__}, got {type(e).__name__}: {e}"
        ) from e
    raise AssertionError(f"expected {exc_type.__name__}, nothing raised")


def _base_kwargs(i=0, **over):
    """Deterministic kwargs for the i-th synthetic forecast record."""
    kw = dict(
        game_id=f"G2026{i:04d}",
        forecast_cutoff=f"2026-08-{(i % 27) + 1:02d}T19:00:00+00:00",
        decision_time_label="T-24h",
        model_version_hash="a" * 64,
        data_snapshot_hash="b" * 64,
        core_only_prediction={
            "margin": 4.5 + i,
            "total": 162.0,
            "home_points": 83.25 + i,
            "away_points": 78.75,
            "margin_dist": [1.0, 4.5 + i, 8.0],
        },
        logged_at_utc=f"2026-08-01T10:{i:02d}:00+00:00",
    )
    kw.update(over)
    return kw


def _fill(path, n=6):
    return [log_forecast(log_path=path, **_base_kwargs(i)) for i in range(n)]


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _write_lines(path: Path, lines) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


# ===========================================================================
# (a) clean chain on N appends
# ===========================================================================

def test_a_chain_clean_on_n_appends():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        recs = _fill(path, n=8)
        rep = verify_chain(path)
        assert rep.ok and rep.first_bad_index is None and rep.reason is None
        assert rep.n_records == 8 and rep.n_verified == 8
        assert [r["record_idx"] for r in recs] == list(range(8)), \
            "record_idx must be contiguous from 0"
        # every line on disk is exactly canonical JSON
        for ln in _lines(path):
            assert ln == canonical_json(json.loads(ln)), \
                "on-disk bytes must equal canonical serialization"
        # tip hash is recomputable from the last line — the external anchor
        assert rep.tip_sha256 == record_sha256(json.loads(_lines(path)[-1]))
        # each record's prev pointer equals the hash of its predecessor
        parsed = read_forecasts(path)
        for i in range(1, 8):
            assert parsed[i]["prev_record_sha256"] == record_sha256(parsed[i - 1])


def test_a_genesis_sentinel_fixed():
    # pinned forever: changing the sentinel would orphan existing ledgers
    assert GENESIS_PREV_SHA256 == "0" * 64
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        _fill(path, n=2)
        first = read_forecasts(path)[0]
        assert first["prev_record_sha256"] == GENESIS_PREV_SHA256
        assert first["record_idx"] == 0


def test_a_empty_and_missing_file_verify_ok():
    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "nope.jsonl"
        rep = verify_chain(missing)
        assert rep.ok and rep.n_records == 0 and rep.tip_sha256 is None
        empty = Path(tmp) / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        rep2 = verify_chain(empty)
        assert rep2.ok and rep2.n_records == 0


# ===========================================================================
# (b) tampering detected and localized to the right index
# ===========================================================================

def test_b_edit_middle_record_detected():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        _fill(path, n=6)
        original = _lines(path)

        # content edit, re-serialized canonically: record 2's successor is
        # the first invariant that fails -> localized to index 3
        rec = json.loads(original[2])
        rec["core_only_prediction"]["margin"] = 99.0
        tampered = list(original)
        tampered[2] = canonical_json(rec)
        _write_lines(path, tampered)
        rep = verify_chain(path)
        assert not rep.ok and rep.first_bad_index == 3
        assert rep.n_verified == 3 and rep.tip_sha256 is None
        assert "prev_record_sha256" in rep.reason

        # formatting-only edit (same content, whitespace variance): caught
        # AT the edited record by the canonical-bytes check
        _write_lines(path, original)
        assert verify_chain(path).ok, "restore sanity"
        tampered2 = list(original)
        tampered2[2] = json.dumps(json.loads(original[2]), sort_keys=True)  # ", " separators
        _write_lines(path, tampered2)
        rep2 = verify_chain(path)
        assert not rep2.ok and rep2.first_bad_index == 2
        assert "canonical" in rep2.reason


def test_b_delete_middle_record_detected():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        _fill(path, n=6)
        lines = _lines(path)
        del lines[2]
        _write_lines(path, lines)
        rep = verify_chain(path)
        assert not rep.ok and rep.first_bad_index == 2
        assert "record_idx" in rep.reason
        assert rep.n_records == 5 and rep.n_verified == 2


def test_b_reorder_detected():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        _fill(path, n=6)
        lines = _lines(path)
        lines[1], lines[2] = lines[2], lines[1]
        _write_lines(path, lines)
        rep = verify_chain(path)
        assert not rep.ok and rep.first_bad_index == 1
        assert "record_idx" in rep.reason


def test_b_chain_valid_forged_duplicate_detected():
    # even a forged record with correct idx + prev hash cannot smuggle in a
    # duplicate key: verify_chain enforces uniqueness independently
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        _fill(path, n=2)
        recs = read_forecasts(path)
        forged = dict(recs[0])                      # same key as record 0
        forged["record_idx"] = 2
        forged["prev_record_sha256"] = record_sha256(recs[1])
        lines = _lines(path) + [canonical_json(forged)]
        _write_lines(path, lines)
        rep = verify_chain(path)
        assert not rep.ok and rep.first_bad_index == 2
        assert "duplicate" in rep.reason


def test_b_tail_truncation_is_the_documented_limitation():
    # deleting the LAST record leaves an internally consistent chain — this
    # is the documented limitation; the defense is the external anchor
    # (n_records + tip_sha256, committed to git).
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        _fill(path, n=6)
        anchor = verify_chain(path)
        _write_lines(path, _lines(path)[:-1])
        rep = verify_chain(path)
        assert rep.ok, "self-contained chain cannot see tail truncation"
        assert rep.n_records == anchor.n_records - 1, \
            "…but the anchored record count exposes it"
        assert rep.tip_sha256 != anchor.tip_sha256, \
            "…and the anchored tip hash exposes it"


def test_b_append_refused_on_broken_chain():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        _fill(path, n=4)
        lines = _lines(path)
        del lines[1]
        _write_lines(path, lines)
        try:
            log_forecast(log_path=path, **_base_kwargs(99))
            raise AssertionError("expected ChainVerificationError")
        except ChainVerificationError as e:
            assert e.report is not None and e.report.first_bad_index == 1, \
                "the refusal carries the localizing report"


# ===========================================================================
# (c) duplicate (game_id, forecast_cutoff, model_version_hash) refusal
# ===========================================================================

def test_c_duplicate_key_refused():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        _fill(path, n=3)
        _raises(DuplicateForecastError, log_forecast,
                log_path=path, **_base_kwargs(1))
        # same game+cutoff under a NEW frozen model version is legitimate
        log_forecast(log_path=path, **_base_kwargs(1, model_version_hash="c" * 64))
        # same game+model at a different cutoff (another decision time) is fine
        log_forecast(log_path=path, **_base_kwargs(
            1, forecast_cutoff="2026-08-02T11:00:00+00:00",
            decision_time_label="T-8h"))
        assert verify_chain(path).ok


def test_c_duplicate_detected_across_iso_spellings():
    # "Z" and "+00:00" spell the same instant; normalization must see through
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        log_forecast(log_path=path, **_base_kwargs(
            0, forecast_cutoff="2026-08-05T19:00:00+00:00"))
        _raises(DuplicateForecastError, log_forecast, log_path=path,
                **_base_kwargs(0, forecast_cutoff="2026-08-05T19:00:00Z"))
        _raises(DuplicateForecastError, log_forecast, log_path=path,
                **_base_kwargs(0, forecast_cutoff=datetime(
                    2026, 8, 5, 19, 0, 0, tzinfo=timezone.utc)))


# ===========================================================================
# (d) field validation
# ===========================================================================

def test_d_bet_decision_enum_and_stake_coherence():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        _raises(ForecastValidationError, log_forecast, log_path=path,
                **_base_kwargs(0, intended_bet_decision="bet_over"))
        _raises(ForecastValidationError, log_forecast, log_path=path,
                **_base_kwargs(0, intended_bet_decision="no_bet",
                               paper_stake=1.0))
        _raises(ForecastValidationError, log_forecast, log_path=path,
                **_base_kwargs(0, intended_bet_decision="bet_home",
                               paper_stake=0.0))
        rec = log_forecast(log_path=path, **_base_kwargs(
            0, intended_bet_decision="bet_home", paper_stake=25.0,
            market_line=-6.5, market_price=-110, market_book="book_a",
            market_source="odds_capture_hourly"))
        assert rec["intended_bet_decision"] == "bet_home"
        assert rec["paper_stake"] == 25.0
        rec2 = log_forecast(log_path=path, **_base_kwargs(1))  # defaults
        assert rec2["intended_bet_decision"] == "not_applicable"
        assert rec2["paper_stake"] == 0.0


def test_d_market_source_provenance_required():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        _raises(ForecastValidationError, log_forecast, log_path=path,
                **_base_kwargs(0, market_line=-6.5))
        _raises(ForecastValidationError, log_forecast, log_path=path,
                **_base_kwargs(0, market_book="book_a"))
        rec = log_forecast(log_path=path, **_base_kwargs(
            0, market_line=-6.5, market_price=-108.0, market_book="book_a",
            market_source="odds_capture_hourly"))
        assert rec["market_source"] == "odds_capture_hourly"


def test_d_core_prediction_required_and_nan_refused():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        _raises(ForecastValidationError, log_forecast, log_path=path,
                **_base_kwargs(0, core_only_prediction=None))
        _raises(ForecastValidationError, log_forecast, log_path=path,
                **_base_kwargs(0, core_only_prediction={}))
        # NaN is never logged: explicit missing state (null) or no prediction
        _raises(ForecastValidationError, log_forecast, log_path=path,
                **_base_kwargs(0, core_only_prediction={"margin": float("nan")}))
        # core+W1 without a recorded extraction is unauditable -> refused
        _raises(ForecastValidationError, log_forecast, log_path=path,
                **_base_kwargs(0, core_plus_w1_prediction={"margin": 3.0}))
        # {} extraction = "W1 ran, found nothing" — allowed and distinct
        rec = log_forecast(log_path=path, **_base_kwargs(
            0, w1_extraction={}, core_plus_w1_prediction={"margin": 3.0}))
        assert rec["w1_extraction"] == {}
        assert rec["core_plus_w1_prediction"] == {"margin": 3.0}


def test_d_logged_at_wall_clock_default():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        kw = _base_kwargs(0)
        kw.pop("logged_at_utc")                     # omit -> wall clock
        rec = log_forecast(log_path=path, **kw)
        t = datetime.fromisoformat(rec["logged_at_utc"])
        assert t.tzinfo is not None and t.utcoffset().total_seconds() == 0
        assert abs((datetime.now(timezone.utc) - t).total_seconds()) < 300


# ===========================================================================
# (e) nullable fields round-trip
# ===========================================================================

def test_e_nullable_fields_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        log_forecast(log_path=path, **_base_kwargs(0))   # minimal record
        minimal = read_forecasts(path)[0]
        for f in ("w1_extraction", "core_plus_w1_prediction", "market_line",
                  "market_price", "market_book", "market_source",
                  "predicted_close"):
            assert f in minimal and minimal[f] is None, \
                f"{f} must be present-as-null on a minimal record"

        w1 = {"designation": "questionable", "body_part": "ankle",
              "source_tier": "coach", "published_time": "2026-08-01T18:05:00Z",
              "quoted_evidence": "listed questionable at shootaround"}
        full = log_forecast(log_path=path, **_base_kwargs(
            1,
            w1_extraction=w1,
            core_plus_w1_prediction={"margin": np.float64(3.25),
                                     "total": 158.5,
                                     "margin_dist": [0.5, 3.25, 6.0]},
            market_line=-4.5, market_price=-112.0, market_book="book_b",
            market_source="odds_capture_hourly",
            predicted_close=-5.0,
            intended_bet_decision="bet_away", paper_stake=12.5,
        ))
        back = read_forecasts(path)[1]
        assert back == full, "the returned record equals the on-disk record"
        assert back["w1_extraction"] == w1
        assert back["core_plus_w1_prediction"]["margin"] == 3.25, \
            "numpy scalars normalize to plain floats"
        assert back["core_plus_w1_prediction"]["margin_dist"] == [0.5, 3.25, 6.0]
        assert back["market_line"] == -4.5 and back["market_price"] == -112.0
        assert back["market_book"] == "book_b"
        assert back["predicted_close"] == -5.0
        assert verify_chain(path).ok


# ===========================================================================
# (f) hash determinism — model config and dataframe
# ===========================================================================

def test_f_hash_model_config_deterministic():
    d1 = {"features": ["trend", "rapm"], "ridge": 0.5,
          "nested": {"a": 1, "b": [1, 2, 3]}}
    d2 = {"nested": {"b": [1, 2, 3], "a": 1}, "ridge": 0.5,
          "features": ["trend", "rapm"]}          # same content, other order
    h1, h2 = hash_model_config(d1), hash_model_config(d2)
    assert h1 == h2, "key order never matters"
    assert len(h1) == 64 and int(h1, 16) >= 0, "sha256 hex"
    # changed value -> changed hash
    d3 = {**d1, "ridge": 0.5000001}
    assert hash_model_config(d3) != h1
    # numpy scalars == python equivalents; tuples == lists
    assert hash_model_config({"lr": np.float64(0.05)}) == \
        hash_model_config({"lr": 0.05})
    assert hash_model_config({"f": (1, 2)}) == hash_model_config({"f": [1, 2]})
    # deterministic-or-refuse: arbitrary objects and NaN are rejected
    _raises(ForecastValidationError, hash_model_config, {"x": object()})
    _raises(ForecastValidationError, hash_model_config, {"x": float("nan")})
    _raises(ForecastValidationError, hash_model_config, ["not", "a", "dict"])


def _snap_df():
    return pd.DataFrame({
        "game_id": ["G1", "G2", "G3"],
        "margin": [4.5, -2.0, np.nan],
        "season": np.array([2024, 2024, 2025], dtype=np.int64),
    })


def test_f_hash_dataframe_deterministic():
    df = _snap_df()
    h = hash_dataframe(df)
    assert len(h) == 64 and int(h, 16) >= 0
    assert hash_dataframe(_snap_df()) == h, "same content -> same hash"
    # column order invariance
    assert hash_dataframe(df[["season", "margin", "game_id"]]) == h
    # row order invariance under the DEFAULT (row_order_independent=True)
    shuffled = df.iloc[[2, 0, 1]]
    assert hash_dataframe(shuffled) == h
    # …and sensitivity when the flag is off
    assert hash_dataframe(shuffled, row_order_independent=False) != \
        hash_dataframe(df, row_order_independent=False)
    assert hash_dataframe(_snap_df(), row_order_independent=False) == \
        hash_dataframe(df, row_order_independent=False)
    # changed value -> changed hash (including NaN vs value)
    df2 = _snap_df()
    df2.loc[0, "margin"] = 4.6
    assert hash_dataframe(df2) != h
    df3 = _snap_df()
    df3.loc[2, "margin"] = 0.0
    assert hash_dataframe(df3) != h
    # index is ignored
    assert hash_dataframe(df.set_axis([10, 20, 30], axis=0)) == h


def test_f_hash_dataframe_dtype_and_multiplicity():
    # storage width is not data: int32 == int64 for equal values
    a = pd.DataFrame({"x": np.array([1, 2], dtype=np.int32)})
    b = pd.DataFrame({"x": np.array([1, 2], dtype=np.int64)})
    assert hash_dataframe(a) == hash_dataframe(b)
    # …but int 1 vs float 1.0 IS a data difference
    c = pd.DataFrame({"x": [1.0, 2.0]})
    assert hash_dataframe(a) != hash_dataframe(c)
    # duplicate-row multiplicity preserved under order independence
    r = pd.DataFrame({"x": ["A", "A", "B"]})
    s = pd.DataFrame({"x": ["A", "B", "B"]})
    assert hash_dataframe(r) != hash_dataframe(s)
    # empty frames differ by column set
    e1 = pd.DataFrame({"a": []})
    e2 = pd.DataFrame({"b": []})
    assert hash_dataframe(e1) != hash_dataframe(e2)
    # duplicate column names refused (ambiguous snapshot)
    dup = pd.DataFrame([[1, 2]], columns=["x", "x"])
    _raises(ForecastValidationError, hash_dataframe, dup)


# ===========================================================================
# (g) prospective_start — the official regime-D start date
# ===========================================================================

def test_g_prospective_start():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        assert prospective_start(path) is None, \
            "no log -> the prospective clock has not started"
        recs = _fill(path, n=3)
        start = prospective_start(path)
        assert start == recs[0]["logged_at_utc"]
        assert datetime.fromisoformat(start) == datetime(
            2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc), \
            "caller-supplied logged_at_utc is the recorded start"
        # later appends never move the start date
        log_forecast(log_path=path, **_base_kwargs(7))
        assert prospective_start(path) == start
        # a broken ledger has no trustworthy start date
        lines = _lines(path)
        del lines[1]
        _write_lines(path, lines)
        _raises(ChainVerificationError, prospective_start, path)


# ===========================================================================
# (h) fsync exercised on every append
# ===========================================================================

def test_h_fsync_called_on_append():
    calls = []
    real_fsync = fl.os.fsync

    def counting_fsync(fd):
        calls.append(fd)
        return real_fsync(fd)

    fl.os.fsync = counting_fsync
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forecast_log.jsonl"
            log_forecast(log_path=path, **_base_kwargs(0))
            assert len(calls) == 1, "exactly one fsync per append"
            log_forecast(log_path=path, **_base_kwargs(1))
            assert len(calls) == 2
            assert verify_chain(path).ok
    finally:
        fl.os.fsync = real_fsync


def test_h_record_durable_before_return():
    # the file must be complete and re-readable immediately after return
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast_log.jsonl"
        rec = log_forecast(log_path=path, **_base_kwargs(0))
        on_disk = read_forecasts(path)
        assert len(on_disk) == 1 and on_disk[0] == rec
        assert verify_chain(path).ok


# ===========================================================================
# plain runner
# ===========================================================================

def _run_all():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception:
            failures.append(name)
            print(f"FAIL  {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - len(failures)}/{len(tests)} tests passed")
    if failures:
        print("FAILED:", *failures, sep="\n  - ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_run_all())
