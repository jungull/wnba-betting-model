"""Tests for asof_invariant.py — the as-of-date invariant (audit deliverable C).

Runnable two ways:
    python -m pytest tests/ -q            (if pytest is installed)
    python tests/test_asof_invariant.py   (plain runner, no dependencies)

Coverage map:
  (a) manifest round-trip: write -> read -> required fields present + typed
  (b) read_manifest refuses absent / malformed / incomplete / wrong-schema files
  (c) content hash binds the manifest to the bytes: a rebuilt artifact whose
      manifest was not updated is DETECTED, not trusted
  (d) assert_asof passes when evidence strictly predates the forecast
  (e) assert_asof FAILS on equality (the boundary case that is the whole point)
      and on evidence that postdates the forecast
  (f) timezone handling: naive == UTC, offset strings normalize, bare dates
      become midnight UTC (the conservative reading)
  (g) assert_scored_seasons_clean reproduces the rapm_v0 failure: fit through
      2024, scoring 2024 -> raises; scoring 2025/2026 -> passes
  (h) the scanner finds unattested artifacts and does not raise on them
  (i) REGRESSION: a walk-forward artifact family (per-season tables) satisfies
      the invariant for every row it is allowed to score and violates it for
      every row it is not — the acceptance test for build_rapm_walkforward_v1
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asof_invariant as aoi  # noqa: E402

UTC = _dt.timezone.utc


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _artifact(tmp: Path, name: str = "table.csv", body: str = "player_id,net\n1,0.5\n") -> Path:
    p = tmp / name
    p.write_text(body, encoding="utf-8")
    return p


def _expect(exc_type, fn, *a, **kw):
    """Assert fn(*a, **kw) raises exc_type; return the exception."""
    try:
        fn(*a, **kw)
    except exc_type as e:
        return e
    except Exception as e:                                # pragma: no cover
        raise AssertionError(f"expected {exc_type.__name__}, got "
                             f"{type(e).__name__}: {e}") from e
    raise AssertionError(f"expected {exc_type.__name__}, nothing raised")


# --------------------------------------------------------------------------- #
# (a) round trip
# --------------------------------------------------------------------------- #

def test_manifest_round_trip():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        art = _artifact(tmp)
        mp = aoi.write_manifest(art, producer="build_rapm.py",
                                fit_through_date="2024-09-19",
                                fit_through_season=2024,
                                fit_seasons=[2021, 2022, 2023, 2024],
                                notes="static ridge fit")
        assert mp.exists() and mp.name == "table.csv" + aoi.MANIFEST_SUFFIX, mp
        m = aoi.read_manifest(art)
        for f in aoi.REQUIRED_FIELDS:
            assert f in m and m[f] not in (None, ""), (f, m)
        assert m["schema"] == aoi.SCHEMA
        assert m["producer"] == "build_rapm.py"
        assert m["fit_through_season"] == 2024
        assert m["fit_seasons"] == [2021, 2022, 2023, 2024]
        assert len(m["content_sha256"]) == 64, m["content_sha256"]
        # reading via the manifest path works too
        assert aoi.read_manifest(mp)["artifact"] == m["artifact"]
        # fit_seasons defaults to [fit_through_season] when not supplied
        art2 = _artifact(tmp, "t2.csv")
        aoi.write_manifest(art2, producer="p", fit_through_date="2023-10-18",
                           fit_through_season=2023)
        assert aoi.read_manifest(art2)["fit_seasons"] == [2023]


# --------------------------------------------------------------------------- #
# (b) refusals
# --------------------------------------------------------------------------- #

def test_read_manifest_refusals():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        art = _artifact(tmp)

        # absent
        e = _expect(aoi.ManifestError, aoi.read_manifest, art)
        assert "no manifest" in str(e).lower(), e

        mp = aoi.manifest_path(art)

        # not JSON
        mp.write_text("{not json", encoding="utf-8")
        _expect(aoi.ManifestError, aoi.read_manifest, art)

        # JSON but not an object
        mp.write_text("[1, 2, 3]", encoding="utf-8")
        _expect(aoi.ManifestError, aoi.read_manifest, art)

        # missing a required field
        good = {"schema": aoi.SCHEMA, "artifact": "table.csv", "producer": "p",
                "fit_through_date": "2024-09-19T00:00:00+00:00",
                "fit_through_season": 2024, "content_sha256": "x" * 64}
        for drop in aoi.REQUIRED_FIELDS:
            bad = {k: v for k, v in good.items() if k != drop}
            mp.write_text(json.dumps(bad), encoding="utf-8")
            e = _expect(aoi.ManifestError, aoi.read_manifest, art)
            assert drop in str(e), (drop, e)

        # empty-string field counts as missing
        mp.write_text(json.dumps({**good, "producer": ""}), encoding="utf-8")
        _expect(aoi.ManifestError, aoi.read_manifest, art)

        # wrong schema version
        mp.write_text(json.dumps({**good, "schema": "asof_invariant/99"}), encoding="utf-8")
        e = _expect(aoi.ManifestError, aoi.read_manifest, art)
        assert "schema" in str(e), e

        # unparseable date
        mp.write_text(json.dumps({**good, "fit_through_date": "last tuesday"}),
                      encoding="utf-8")
        _expect(aoi.ManifestError, aoi.read_manifest, art)

        # a valid one still loads after all that
        mp.write_text(json.dumps(good), encoding="utf-8")
        assert aoi.read_manifest(art)["producer"] == "p"


# --------------------------------------------------------------------------- #
# (c) the hash binds manifest to bytes
# --------------------------------------------------------------------------- #

def test_content_hash_detects_silent_refit():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        art = _artifact(tmp)
        aoi.write_manifest(art, producer="build_rapm.py",
                           fit_through_date="2024-09-19", fit_through_season=2024)
        m = aoi.read_manifest(art)
        assert aoi.verify_content(m, art) == m["content_sha256"]

        # somebody refits the table and forgets the manifest
        art.write_text("player_id,net\n1,0.9\n2,-0.2\n", encoding="utf-8")
        e = _expect(aoi.ManifestError, aoi.verify_content, m, art)
        assert "drift" in str(e).lower(), e

        # and assert_asof with verify_hash=True refuses to certify it
        _expect(aoi.ManifestError, aoi.assert_asof, m,
                "2026-07-31T00:00:00+00:00", artifact=art, verify_hash=True)

        # without the hash check the stale claim would sail through — which is
        # precisely why producers must rewrite the manifest on every refit
        aoi.assert_asof(m, "2026-07-31T00:00:00+00:00")


# --------------------------------------------------------------------------- #
# (d)+(e) the invariant itself, including the equality boundary
# --------------------------------------------------------------------------- #

def test_assert_asof_strict_ordering():
    m = {"schema": aoi.SCHEMA, "artifact": "a.csv", "producer": "p",
         "fit_through_date": "2024-09-19T00:00:00+00:00",
         "fit_through_season": 2024, "content_sha256": "x" * 64}

    # strictly after -> ok, and the manifest comes back for chaining
    out = aoi.assert_asof(m, "2025-05-16T23:00:00+00:00")
    assert out["producer"] == "p"

    # one microsecond after -> still ok
    aoi.assert_asof(m, "2024-09-19T00:00:00.000001+00:00")

    # EQUAL -> violation. This is the whole point: an artifact whose last
    # source observation IS the row being scored is the rapm_v0 failure.
    e = _expect(aoi.AsOfViolation, aoi.assert_asof, m, "2024-09-19T00:00:00+00:00")
    assert "NOT strictly before" in str(e), e

    # before -> violation
    _expect(aoi.AsOfViolation, aoi.assert_asof, m, "2024-06-01T00:00:00+00:00")

    # non-raising form agrees with the raising form
    ok, why = aoi.check_asof(m, "2025-05-16T23:00:00+00:00")
    assert ok and why == ""
    ok, why = aoi.check_asof(m, "2024-09-19T00:00:00+00:00")
    assert not ok and "AS-OF VIOLATION" in why, why


# --------------------------------------------------------------------------- #
# (f) timezones
# --------------------------------------------------------------------------- #

def test_timezone_normalisation():
    naive = aoi.to_utc("2024-09-19T12:00:00")
    aware = aoi.to_utc("2024-09-19T12:00:00+00:00")
    assert naive == aware, (naive, aware)

    # an offset timestamp normalises to the same instant
    assert aoi.to_utc("2024-09-19T08:00:00-04:00") == aoi.to_utc("2024-09-19T12:00:00Z")

    # a bare date becomes midnight UTC: a game played ON that date cannot be
    # proven to precede midnight of it, so midnight is the safe reading
    assert aoi.to_utc(_dt.date(2024, 9, 19)) == _dt.datetime(2024, 9, 19, tzinfo=UTC)

    # datetime objects, naive and aware, both work
    assert aoi.to_utc(_dt.datetime(2024, 9, 19, 12)) == aware
    assert aoi.to_utc(_dt.datetime(2024, 9, 19, 12, tzinfo=UTC)) == aware

    # a date-only fit_through vs a same-day tip-time forecast still passes,
    # because midnight strictly precedes the tip
    m = {"schema": aoi.SCHEMA, "artifact": "a.csv", "producer": "p",
         "fit_through_date": "2024-09-19", "fit_through_season": 2024,
         "content_sha256": "x" * 64}
    aoi.assert_asof(m, "2024-09-19T19:30:00+00:00")

    _expect(aoi.ManifestError, aoi.to_utc, "")
    _expect(aoi.ManifestError, aoi.to_utc, object())


# --------------------------------------------------------------------------- #
# (g) the season rule — the rapm_v0 regression
# --------------------------------------------------------------------------- #

def test_scored_seasons_reproduces_rapm_v0_failure():
    """The exact configuration that invalidated two registered experiments."""
    m = {"schema": aoi.SCHEMA, "artifact": "data/rapm/rapm_v0.csv",
         "producer": "build_rapm.py",
         "fit_through_date": "2024-09-19T00:00:00+00:00",
         "fit_through_season": 2024,
         "fit_seasons": [2021, 2022, 2023, 2024],
         "content_sha256": "x" * 64}

    # what oracle_bracket.py and joint_differential.py actually did
    e = _expect(aoi.AsOfViolation, aoi.assert_scored_seasons_clean, m,
                [2024, 2025, 2026])
    assert "2024" in str(e), e

    # the clean slice the erratum fell back to
    aoi.assert_scored_seasons_clean(m, [2025, 2026])

    # train seasons are inside the window too — the escalation this audit found
    _expect(aoi.AsOfViolation, aoi.assert_scored_seasons_clean, m,
            [2021, 2022, 2023])

    # a season listed in fit_seasons but below fit_through_season still fails
    m2 = dict(m, fit_through_season=2022, fit_seasons=[2021, 2022, 2024])
    _expect(aoi.AsOfViolation, aoi.assert_scored_seasons_clean, m2, [2024])
    aoi.assert_scored_seasons_clean(m2, [2023, 2025])
    # empty scored set is vacuously clean
    aoi.assert_scored_seasons_clean(m, [])


# --------------------------------------------------------------------------- #
# (h) scanner
# --------------------------------------------------------------------------- #

def test_scanner_reports_unattested_without_raising():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "data" / "rapm").mkdir(parents=True)
        good = _artifact(tmp / "data" / "rapm", "good.csv")
        bare = _artifact(tmp / "data" / "rapm", "bare.csv")
        aoi.write_manifest(good, producer="p", fit_through_date="2023-10-18",
                           fit_through_season=2023)

        rows = aoi.scan_artifacts(tmp, globs=("data/rapm/*.csv", "data/nope/*.csv"))
        by = {r["artifact"]: r for r in rows}
        assert by["data/rapm/good.csv"]["has_manifest"] is True
        assert by["data/rapm/good.csv"]["manifest_valid"] is True
        assert by["data/rapm/good.csv"]["hash_ok"] == "yes"
        assert by["data/rapm/bare.csv"]["has_manifest"] is False
        assert "NO MANIFEST" in by["data/rapm/bare.csv"]["problem"]
        # manifests themselves are never reported as artifacts
        assert not any(r["artifact"].endswith(aoi.MANIFEST_SUFFIX) for r in rows)
        # a glob that matches nothing is reported, not silently dropped
        assert any(r["matched_glob"] == "data/nope/*.csv" and not r["exists"]
                   for r in rows), rows

        # drift is surfaced by the scan, not raised
        good.write_text("changed\n", encoding="utf-8")
        rows2 = {r["artifact"]: r for r in aoi.scan_artifacts(tmp, globs=("data/rapm/*.csv",))}
        assert rows2["data/rapm/good.csv"]["hash_ok"] == "no"
        assert "HASH DRIFT" in rows2["data/rapm/good.csv"]["problem"]

        out = aoi.write_scan_csv(rows, tmp / "scan.csv")
        text = out.read_text(encoding="utf-8")
        assert "artifact,matched_glob" in text and "data/rapm/bare.csv" in text


# --------------------------------------------------------------------------- #
# (i) the acceptance test for the walk-forward rebuild
# --------------------------------------------------------------------------- #

def test_walkforward_family_satisfies_invariant():
    """build_rapm_walkforward_v1 acceptance shape.

    A per-season family of tables (values for season s fit only on seasons < s)
    must, for every season s: pass both the timestamp and the season rule for
    rows in s and later, and FAIL for any row at or before its fit window.
    A single static table cannot do this — which is the defect being fixed.
    """
    season_end = {2021: "2021-10-17", 2022: "2022-09-18",
                  2023: "2023-10-18", 2024: "2024-09-19", 2025: "2025-10-10"}
    season_start = {2022: "2022-05-06", 2023: "2023-05-19", 2024: "2024-05-14",
                    2025: "2025-05-16", 2026: "2026-05-15"}

    # the family: table_for[s] is fit on seasons < s
    family = {}
    for s in (2023, 2024, 2025, 2026):
        prior = [y for y in (2021, 2022, 2023, 2024, 2025) if y < s]
        family[s] = {"schema": aoi.SCHEMA, "artifact": f"rapm_wf_{s}.csv",
                     "producer": "build_rapm_walkforward.py",
                     "fit_through_date": season_end[max(prior)] + "T00:00:00+00:00",
                     "fit_through_season": max(prior),
                     "fit_seasons": prior,
                     "content_sha256": "x" * 64}

    for s, m in family.items():
        # the table for season s clears both rules on its own season's opener
        aoi.assert_asof(m, season_start[s] + "T19:30:00+00:00", label=f"wf_{s}")
        aoi.assert_scored_seasons_clean(m, [s], label=f"wf_{s}")
        # and on every later season too
        for later in [y for y in family if y > s]:
            aoi.assert_scored_seasons_clean(m, [later])
        # but it must refuse every season inside its own fit window
        for inside in m["fit_seasons"]:
            _expect(aoi.AsOfViolation, aoi.assert_scored_seasons_clean, m, [inside])

    # the static incumbent fails the same battery on 2024 — regression guard
    static = {"schema": aoi.SCHEMA, "artifact": "data/rapm/rapm_v0.csv",
              "producer": "build_rapm.py",
              "fit_through_date": season_end[2024] + "T00:00:00+00:00",
              "fit_through_season": 2024, "fit_seasons": [2021, 2022, 2023, 2024],
              "content_sha256": "x" * 64}
    _expect(aoi.AsOfViolation, aoi.assert_scored_seasons_clean, static, [2024])
    _expect(aoi.AsOfViolation, aoi.assert_asof, static,
            season_start[2024] + "T19:30:00+00:00")
    # yet it is legitimately clean for 2025 and 2026 rows
    aoi.assert_asof(static, season_start[2025] + "T19:30:00+00:00")
    aoi.assert_scored_seasons_clean(static, [2025, 2026])


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
