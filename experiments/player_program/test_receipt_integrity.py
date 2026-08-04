#!/usr/bin/env python3
"""test_receipt_integrity.py — the receipt-integrity gate must actually block.

Every tampering test operates on a TEMPORARY COPY. The real artifacts and receipts under
`experiments/player_program/*_v1/` are never written to; `test_real_tree_untouched` proves it by
re-hashing every real artifact and receipt at the end of the run.

The regression case is the real one: on 2026-08-04, `canonical_player_events/1` was rebuilt under
`source_aware_exact_duplicate/1` and `player_turnover_targets/1` was rebuilt on top of it, but
`TURNOVER_VALIDATION.json` was not regenerated. The stale receipt claimed 42,083 turnover events,
39,279 player-attributed and 2,989/2,990 external agreement with one named off-by-one, against a
corrected artifact holding 42,082 / 39,278 / 2,990-of-2,990 exact -- and it still said PASS.

Run::  python -m unittest experiments.player_program.test_receipt_integrity -v
   or:: python experiments/player_program/test_receipt_integrity.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import receipt_integrity as RI                                               # noqa: E402

TURNOVER = "turnover_targets_v1"
TREC = "TURNOVER_TARGET_RECEIPT.json"
TVAL = "TURNOVER_VALIDATION.json"
PLAYER_PARQUET = "player_turnover_targets_v1.parquet"

#: hashes of everything the suite must not touch, captured before any test runs
_REAL_STATE: dict[str, str] = {}


def setUpModule() -> None:
    for fam, spec in RI.FAMILIES.items():
        d = RI.HERE / spec["dir"]
        for f in sorted(d.glob("*")):
            if f.is_file():
                _REAL_STATE[str(f)] = RI.sha256_file(f)


def _stage(tmp: Path, family: str = TURNOVER) -> Path:
    """Copy a family directory plus its producer/validator sources into a temp base."""
    spec = RI.FAMILIES[family]
    shutil.copytree(RI.HERE / spec["dir"], tmp / spec["dir"])
    for role in ("producer", "validator"):
        rel = spec.get(role)
        if rel and (RI.HERE / rel).exists():
            shutil.copy2(RI.HERE / rel, tmp / rel)
    return tmp


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _save(p: Path, obj: dict) -> None:
    p.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def _kinds(res: dict) -> set[str]:
    return {f["kind"] for f in res["blocking"]}


def _audit(base: Path, family: str = TURNOVER, **kw):
    return RI.audit_family(family, base=base, root=RI.ROOT, raise_on_block=False, **kw)


class CleanState(unittest.TestCase):
    def test_real_sweep_passes_and_does_not_raise(self):
        s = RI.sweep()                                   # raise_on_block defaults to True
        self.assertTrue(s["passed"])
        self.assertEqual(s["blocking"], [])
        for fam in ("projected_exposure_v1", "event_contract_v1", "turnover_targets_v1"):
            self.assertIn(fam, s["per_family"])
            self.assertTrue(s["per_family"][fam]["passed"], fam)
            self.assertGreater(s["per_family"][fam]["counts_cross_checked"], 0, fam)

    def test_sweep_covers_the_three_required_families(self):
        self.assertEqual(set(RI.FAMILIES),
                         {"projected_exposure_v1", "event_contract_v1", "turnover_targets_v1"})

    def test_staged_copy_passes(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            r = _audit(base)
            self.assertTrue(r["passed"], r["blocking"])
            self.assertEqual(r["findings"], [])

    def test_turnover_reconciliation_numbers_are_the_registered_ones(self):
        """The corrected artifact must hold the four reconciliation numbers, not the stale ones."""
        r = _audit(RI.HERE)
        c = r["recomputed_counts"]
        self.assertEqual(c["team_player_attributed"], 39278)
        self.assertEqual(c["team_exact"], 2990)
        self.assertEqual(c["team_game_rows"], 2990)
        self.assertEqual(c["team_off_by_one"], 0)
        self.assertEqual(c["team_larger"], 0)
        ev = _audit(RI.HERE, "event_contract_v1")["recomputed_counts"]
        self.assertEqual(ev["canonical_rows"], 589123)
        self.assertEqual(ev["turnover_rows"], 42082)


class TamperedHash(unittest.TestCase):
    def test_rewritten_artifact_blocks_on_hash_alone(self):
        """Same rows, different bytes, original mtime: only the hash check can see this."""
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            p = base / TURNOVER / PLAYER_PARQUET
            st = p.stat()
            df = pd.read_parquet(p)
            df.to_parquet(p, index=False, compression="gzip")
            os.utime(p, (st.st_atime, st.st_mtime))      # isolate the hash finding from mtime
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertEqual(_kinds(r), {"artifact_hash_mismatch"})
            subj = {f["subject"] for f in r["blocking"]}
            self.assertEqual(subj, {"player"})
            self.assertEqual({f["receipt"] for f in r["blocking"]}, {TREC, TVAL})

    def test_receipt_recorded_hash_edited_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TREC
            R = _load(rp)
            R["artifact_sha256"]["team"] = "0" * 64
            _save(rp, R)
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertIn("artifact_hash_mismatch", _kinds(r))
            f = next(x for x in r["blocking"] if x["kind"] == "artifact_hash_mismatch")
            self.assertEqual(f["subject"], "team")
            self.assertEqual(f["in_receipt"], "0" * 64)

    def test_missing_hash_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TREC
            R = _load(rp)
            del R["artifact_sha256"]["player"]
            _save(rp, R)
            r = _audit(base)
            self.assertIn("receipt_hash_absent", _kinds(r))

    def test_upstream_input_hash_drift_blocks(self):
        """The exact edge the real defect travelled: the events artifact moved underneath."""
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TREC
            R = _load(rp)
            R["inputs"]["events"] = "f" * 64          # pre-dedup bytes, no longer on disk
            _save(rp, R)
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertIn("input_hash_mismatch", _kinds(r))
            f = next(x for x in r["blocking"] if x["kind"] == "input_hash_mismatch")
            self.assertTrue(f["subject"].endswith("canonical_player_events_v1.parquet"))


class CountDivergence(unittest.TestCase):
    def test_producer_receipt_count_divergence_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TREC
            R = _load(rp)
            R["counts"]["player_game_rows"] = int(R["counts"]["player_game_rows"]) + 1
            _save(rp, R)
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertEqual(_kinds(r), {"count_divergence"})
            f = r["blocking"][0]
            self.assertEqual(f["subject"], "player_game_rows")
            self.assertEqual(f["delta"], 1)
            self.assertEqual(f["recomputed"], 28328)

    def test_validation_receipt_count_divergence_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TVAL
            R = _load(rp)
            chk = next(c for c in R["checks"] if c["check"] == "external_team_reconciliation")
            chk["detail"]["exact"] = 2989
            chk["detail"]["off_by_one"] = 1
            _save(rp, R)
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertEqual(_kinds(r), {"count_divergence"})
            got = {f["subject"]: (f["in_receipt"], f["recomputed"]) for f in r["blocking"]}
            self.assertEqual(got["team_exact"], (2989, 2990))
            self.assertEqual(got["team_off_by_one"], (1, 0))

    def test_the_real_stale_receipt_would_have_blocked(self):
        """Regression from the actual defect: the pre-regeneration TURNOVER_VALIDATION.json."""
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TVAL
            R = _load(rp)
            # exactly what the stale receipt asserted, verbatim
            R["artifact_sha256"] = {
                "player": "a360e5d8d000256224739d76c1d9f0902fe36aadb1c667af6a90f1d612f7f9d0",
                "team": "6544744941be425aba219216f224252866c68f7eccb73fbac87eff649d39fabf"}
            by = {c["check"]: c for c in R["checks"]}
            by["mechanism_sums_to_player_total"]["detail"].update(
                {"total_turnovers": 39279, "total_from_mechanisms": 39279})
            by["components_sum_to_team_total"]["detail"].update(
                {"player_attributed": 39279, "team_total": 42082})
            by["external_team_reconciliation"]["detail"].update({"exact": 2989, "off_by_one": 1})
            _save(rp, R)
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertEqual(_kinds(r), {"artifact_hash_mismatch", "count_divergence"})
            got = {f["subject"]: f for f in r["blocking"] if f["kind"] == "count_divergence"}
            self.assertEqual(got["player_turnovers_total"]["delta"], 1)
            self.assertEqual(got["team_player_attributed"]["delta"], 1)
            self.assertEqual(got["team_turnovers_total"]["delta"], 1)
            self.assertEqual(got["team_exact"]["delta"], -1)
            self.assertEqual(got["team_off_by_one"]["delta"], 1)

    def test_unrecomputable_counts_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            (base / TURNOVER / PLAYER_PARQUET).write_bytes(b"not a parquet file")
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertIn("count_unrecomputable", _kinds(r))


class VersionDivergence(unittest.TestCase):
    def test_producer_source_drift_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            p = base / "build_turnover_targets.py"
            p.write_text(p.read_text(encoding="utf-8") + "\n# a later edit\n", encoding="utf-8")
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertEqual(_kinds(r), {"producer_version_divergence"})
            self.assertEqual({f["receipt"] for f in r["blocking"]}, {TREC, TVAL})

    def test_unpinned_producer_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TREC
            R = _load(rp)
            del R["producer_sha256"]
            _save(rp, R)
            r = _audit(base)
            self.assertIn("producer_sha_absent", _kinds(r))

    def test_contract_identity_drift_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TVAL
            R = _load(rp)
            R["schema"] = "turnover_target_validation/2"
            _save(rp, R)
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertEqual(_kinds(r), {"contract_version_divergence"})
            f = r["blocking"][0]
            self.assertEqual(f["in_receipt"], "turnover_target_validation/2")
            self.assertEqual(f["registered"], "turnover_target_validation/1")

    def test_artifact_carried_version_differing_from_receipt_blocks(self):
        """The artifact states its own contract version; the receipt states another."""
        with tempfile.TemporaryDirectory() as td:
            base, spec = _synth_family(Path(td))
            r = RI.audit_family("synth_v1", spec=spec, base=base, root=base,
                                raise_on_block=False)
            self.assertTrue(r["passed"], r["blocking"])

            rp = base / "synth_v1" / "SYNTH_RECEIPT.json"
            R = _load(rp)
            R["contract_version"] = "synth_contract/2"
            _save(rp, R)
            r = RI.audit_family("synth_v1", spec=spec, base=base, root=base,
                                raise_on_block=False)
            self.assertFalse(r["passed"])
            self.assertEqual(_kinds(r), {"contract_version_divergence"})
            f = r["blocking"][0]
            self.assertEqual(f["in_artifact"], "synth_contract/1")
            self.assertEqual(f["in_receipt"], "synth_contract/2")


class Staleness(unittest.TestCase):
    def test_artifact_newer_than_receipt_blocks(self):
        """A rebuilt artifact whose receipt was never regenerated, with hashes still consistent."""
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            d = base / TURNOVER
            amt = (d / PLAYER_PARQUET).stat().st_mtime
            for name in (TREC, TVAL):
                os.utime(d / name, (amt - 3600, amt - 3600))
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertEqual(_kinds(r), {"receipt_predates_artifact"})
            for f in r["blocking"]:
                self.assertGreater(f["seconds_stale"], 3000)
            self.assertEqual({f["receipt"] for f in r["blocking"]}, {TREC, TVAL})

    def test_receipt_written_after_the_artifact_is_fine(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            d = base / TURNOVER
            amt = (d / PLAYER_PARQUET).stat().st_mtime
            os.utime(d / TVAL, (amt + 600, amt + 600))
            r = _audit(base)
            self.assertTrue(r["passed"], r["blocking"])


class MissingAndMalformed(unittest.TestCase):
    def test_missing_receipt_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            (base / TURNOVER / TVAL).unlink()
            r = _audit(base)
            self.assertEqual(_kinds(r), {"receipt_missing"})

    def test_unreadable_receipt_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            (base / TURNOVER / TVAL).write_text("{ this is not json", encoding="utf-8")
            r = _audit(base)
            self.assertEqual(_kinds(r), {"receipt_unreadable"})

    def test_missing_artifact_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            (base / TURNOVER / PLAYER_PARQUET).unlink()
            r = _audit(base)
            self.assertIn("artifact_missing", _kinds(r))

    def test_recorded_fail_verdict_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TVAL
            R = _load(rp)
            R["verdict"] = "FAIL"
            _save(rp, R)
            r = _audit(base)
            self.assertEqual(_kinds(r), {"validation_verdict_not_pass"})


class Adjudication(unittest.TestCase):
    def test_adjudicated_finding_stays_visible_but_does_not_block(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TREC
            R = _load(rp)
            R["counts"]["player_game_rows"] = int(R["counts"]["player_game_rows"]) + 1
            _save(rp, R)
            key = f"{TURNOVER}|{TREC}|count_divergence|player_game_rows"
            r = _audit(base, adjudicated={key: "adjudicated in the test only"})
            self.assertTrue(r["passed"])
            self.assertEqual(len(r["findings"]), 1)
            self.assertEqual(r["findings"][0]["adjudicated"], "adjudicated in the test only")

    def test_unrelated_adjudication_does_not_unblock(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TREC
            R = _load(rp)
            R["counts"]["team_game_rows"] = 1
            _save(rp, R)
            r = _audit(base, adjudicated={f"{TURNOVER}|{TREC}|count_divergence|player_game_rows":
                                          "wrong subject"})
            self.assertFalse(r["passed"])


class Contract(unittest.TestCase):
    def test_blocking_set_is_the_documented_one(self):
        self.assertEqual(RI.BLOCKING, {
            "artifact_missing", "receipt_missing", "receipt_unreadable", "receipt_hash_absent",
            "artifact_hash_mismatch", "input_hash_mismatch", "count_divergence",
            "count_unrecomputable", "producer_sha_absent", "producer_version_divergence",
            "contract_version_divergence", "receipt_predates_artifact",
            "validation_verdict_not_pass"})

    def test_audit_raises_by_default_on_a_blocking_finding(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            rp = base / TURNOVER / TREC
            R = _load(rp)
            R["counts"]["team_game_rows"] = 1
            _save(rp, R)
            with self.assertRaises(RI.ReceiptIntegrityFailure):
                RI.audit_family(TURNOVER, base=base, root=RI.ROOT)

    def test_resolve_selects_a_check_by_name_not_position(self):
        doc = {"checks": [{"check": "b", "detail": {"n": 2}}, {"check": "a", "detail": {"n": 1}}]}
        self.assertEqual(RI.resolve(doc, ("checks", "check:a", "detail", "n")), 1)
        self.assertIs(RI.resolve(doc, ("checks", "check:zz", "detail", "n")), RI._MISSING)

    def test_cli_exit_code_is_zero_on_a_clean_tree(self):
        self.assertEqual(RI.main([]), 0)


class RealTree(unittest.TestCase):
    def test_real_tree_untouched(self):
        for path, sha in _REAL_STATE.items():
            self.assertEqual(RI.sha256_file(Path(path)), sha, f"the suite modified {path}")


# --------------------------------------------------------------------------- #
def _synth_family(tmp: Path):
    """A tiny purpose-built family: an artifact that carries its own contract version."""
    d = tmp / "synth_v1"
    d.mkdir(parents=True)
    (tmp / "build_synth.py").write_text("# synthetic producer\n", encoding="utf-8")
    df = pd.DataFrame({"x": [1, 2, 3], "contract_version": ["synth_contract/1"] * 3})
    df.to_parquet(d / "synth_v1.parquet", index=False)
    receipt = {
        "schema": "synth_receipt/1",
        "artifact_id": "synth/1",
        "contract_version": "synth_contract/1",
        "rows": 3,
        "producer_sha256": RI.sha256_file(tmp / "build_synth.py"),
        "artifact_sha256": {"main": RI.sha256_file(d / "synth_v1.parquet")},
    }
    _save(d / "SYNTH_RECEIPT.json", receipt)
    spec = {
        "artifact_id": "synth/1", "dir": "synth_v1", "producer": "build_synth.py",
        "validator": None, "artifacts": {"main": "synth_v1.parquet"},
        "recount": lambda p: {"rows": int(len(pd.read_parquet(p / "synth_v1.parquet")))},
        "expected_versions": {"main": {"contract_version": "synth_contract/1"}},
        "version_bindings": [{"artifact": "main", "column": "contract_version",
                              "receipt": "SYNTH_RECEIPT.json", "path": ("contract_version",)}],
        "receipts": [{
            "file": "SYNTH_RECEIPT.json", "role": "producer",
            "identity": {"schema": ("schema",)},
            "expect_identity": {"schema": "synth_receipt/1"},
            "hashes": {"main": ("artifact_sha256", "main")},
            "producer_sha": ("producer_sha256",),
            "counts": [{"path": ("rows",), "count": "rows"}],
        }],
    }
    return tmp, spec


if __name__ == "__main__":
    unittest.main(verbosity=2)
