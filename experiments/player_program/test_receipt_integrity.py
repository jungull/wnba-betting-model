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

The chain-layer suite below replays what the repair established: the TARGET receipt had NOT
drifted. Its manifest matched the rebuilt parquets exactly. The stale PASS lived in
`TURNOVER_VALIDATION.json`, written 11m55s before the rebuild and certifying `a360e5d8...` and
`65447449...`. `Case1CurrentManifestStalePass` replays that with those literal hashes, and
`test_a_manifest_only_check_would_have_cleared_this_tree` proves the manifest layer alone sees
nothing wrong with it. One class per numbered failure shape in `RI.CASES`.

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
        # the chain layer reaches OUTSIDE the family directory to recompute what receipts claim
        # about their upstream inputs. Those files are read-only too, and the proof must cover
        # them: a witness that rewrote a master or a prediction parquet would be catastrophic.
        for w in (spec.get("witnesses") or {}).values():
            p = (RI.HERE if w.get("anchor") == "base" else RI.ROOT) / w["path"]
            for f in (sorted(p.glob("*")) if p.is_dir() else [p]):
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
            # WIDENED by the chain layer: the validation receipt records PASS, and it now
            # certifies bytes that are not on disk, so the stale-verdict detector fires too.
            self.assertEqual(_kinds(r), {"artifact_hash_mismatch", "stale_validation_verdict"})
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
            # WIDENED by the chain layer: the stale PASS and the receipt-vs-receipt hash
            # disagreement are now named in their own right, not inferred from the manifest.
            self.assertEqual(_kinds(r), {"artifact_hash_mismatch", "count_divergence",
                                         "stale_validation_verdict", "receipt_hash_disagreement"})
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
            # the manifest layer, frozen
            "artifact_missing", "receipt_missing", "receipt_unreadable", "receipt_hash_absent",
            "artifact_hash_mismatch", "input_hash_mismatch", "count_divergence",
            "count_unrecomputable", "producer_sha_absent", "producer_version_divergence",
            "contract_version_divergence", "receipt_predates_artifact",
            "validation_verdict_not_pass",
            # the chain layer
            "stale_validation_verdict", "validation_precedes_artifact", "validator_sha_absent",
            "validator_version_divergence", "validated_input_divergence",
            "input_witness_divergence", "receipt_hash_disagreement", "validation_link_absent",
            "fresh_execution_not_proven"})

    def test_blocking_v1_is_still_wholly_blocking(self):
        """The extension may only ADD. Nothing the manifest layer blocked may have been relaxed."""
        self.assertEqual(len(RI.BLOCKING_V1), 13)
        self.assertTrue(RI.BLOCKING_V1 <= RI.BLOCKING)
        self.assertEqual(RI.BLOCKING, set(RI.BLOCKING_V1 | RI.BLOCKING_CHAIN))
        self.assertFalse(RI.BLOCKING & RI.NON_BLOCKING)

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


# =========================================================================== #
# the chain layer
#
# `contract -> producer -> artifact -> target receipt -> validation execution -> validation
# receipt`. Everything above this line checks the artifact against its own manifest, which is
# precisely the check that would have CLEARED the broken tree: TURNOVER_TARGET_RECEIPT.json had
# NOT drifted. The file carrying the stale PASS was TURNOVER_VALIDATION.json.
# =========================================================================== #
EVENTS = "event_contract_v1"
EVAL = "EVENT_VALIDATION.json"
PROJ = "projected_exposure_v1"
PREC = "PROJECTED_EXPOSURE_RECEIPT.json"

#: the two hashes the stale PASS actually certified, verbatim from the defect
PRIOR_PLAYER_SHA = "a360e5d8d000256224739d76c1d9f0902fe36aadb1c667af6a90f1d612f7f9d0"
PRIOR_TEAM_SHA = "6544744941be425aba219216f224252866c68f7eccb73fbac87eff649d39fabf"


def _cases(res: dict) -> set[int]:
    return {c for f in res["blocking"] for c in (f.get("cases") or [])}


def _of_kind(res: dict, kind: str) -> list[dict]:
    return [f for f in res["blocking"] if f["kind"] == kind]


class Case1CurrentManifestStalePass(unittest.TestCase):
    """CASE 1 -- the defect that actually occurred, replayed with the observed hashes."""

    def test_target_receipt_perfect_but_validation_certifies_prior_hashes_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            d = base / TURNOVER

            # the target receipt is left EXACTLY as it is: it matches the artifact in every
            # field. Only the validation receipt certifies the pre-rebuild bytes.
            trec = _load(d / TREC)
            self.assertEqual(trec["artifact_sha256"]["player"],
                             RI.sha256_file(d / PLAYER_PARQUET))

            R = _load(d / TVAL)
            R["artifact_sha256"] = {"player": PRIOR_PLAYER_SHA, "team": PRIOR_TEAM_SHA}
            _save(d / TVAL, R)

            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertIn("stale_validation_verdict", _kinds(r))
            self.assertIn(1, _cases(r))
            self.assertTrue(r["target_receipt_current"],
                            "the target receipt must still be current; that is the whole point")

            stale = _of_kind(r, "stale_validation_verdict")
            self.assertEqual({f["receipt"] for f in stale}, {TVAL})
            self.assertEqual({f["subject"] for f in stale}, {"player", "team"})
            for f in stale:
                self.assertEqual(f["evidence"], "certified_hashes_are_not_the_artifact")
                self.assertEqual(f["verdict"], "PASS")
                self.assertTrue(f["target_receipt_current"])
            certified = {f["subject"]: f["certifies"] for f in stale}
            self.assertEqual(certified, {"player": PRIOR_PLAYER_SHA, "team": PRIOR_TEAM_SHA})

            # and the two receipts no longer agree about which bytes exist at all
            self.assertIn("receipt_hash_disagreement", _kinds(r))

    def test_a_manifest_only_check_would_have_cleared_this_tree(self):
        """The regression that justifies the whole chain layer: with only the manifest layer's
        kinds enabled, the stale PASS is invisible."""
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            R = _load(base / TURNOVER / TVAL)
            R["artifact_sha256"] = {"player": PRIOR_PLAYER_SHA, "team": PRIOR_TEAM_SHA}
            R["validated_utc"] = "2026-08-04T11:54:25.000000Z"     # 11m55s BEFORE the rebuild
            _save(base / TURNOVER / TVAL, R)
            r = _audit(base)
            chain_only = {f["kind"] for f in r["blocking"]} - set(RI.BLOCKING_V1)
            self.assertIn("stale_validation_verdict", chain_only)
            self.assertIn("validation_precedes_artifact", chain_only)
            # the target receipt, checked alone, is spotless
            self.assertEqual([f for f in r["blocking"] if f.get("receipt") == TREC], [])


class Case2OldValidatorRun(unittest.TestCase):
    """CASE 2 -- a current artifact paired with an old validation run."""

    def test_validation_timestamp_before_artifact_creation_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            d = base / TURNOVER
            built = _load(d / TREC)["finished_utc"]
            R = _load(d / TVAL)
            R["validated_utc"] = "2026-08-04T11:54:25.000000Z"
            _save(d / TVAL, R)                      # hashes and counts left CURRENT

            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertIn("validation_precedes_artifact", _kinds(r))
            self.assertIn(2, _cases(r))
            f = _of_kind(r, "validation_precedes_artifact")[0]
            self.assertEqual(f["receipt"], TVAL)
            self.assertEqual(f["validated_utc"], "2026-08-04T11:54:25.000000Z")
            self.assertEqual(f["artifact_generated_utc"], built)
            self.assertGreater(f["seconds_early"], 700)
            # the PASS is stale on timeline evidence even though every hash still matches
            stale = _of_kind(r, "stale_validation_verdict")
            self.assertEqual([f["evidence"] for f in stale], ["verdict_predates_the_artifact"])

    def test_recorded_timestamps_are_used_not_file_mtime(self):
        """mtime does not survive a checkout. Recorded instants do, so they must decide."""
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            d = base / TURNOVER
            R = _load(d / TVAL)
            R["validated_utc"] = "2026-08-04T11:54:25.000000Z"
            _save(d / TVAL, R)
            # make every mtime identical, as a fresh checkout would
            for f in sorted(d.glob("*")):
                os.utime(f, (1_800_000_000, 1_800_000_000))
            r = _audit(base)
            self.assertNotIn("receipt_predates_artifact", _kinds(r))   # mtime sees nothing
            self.assertIn("validation_precedes_artifact", _kinds(r))   # the record does

    def test_mtime_findings_are_labelled_corroboration_only(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            d = base / TURNOVER
            amt = (d / PLAYER_PARQUET).stat().st_mtime
            for name in (TREC, TVAL):
                os.utime(d / name, (amt - 3600, amt - 3600))
            r = _audit(base)
            for f in _of_kind(r, "receipt_predates_artifact"):
                self.assertEqual(f["evidence_class"], "mtime_corroboration")


class Case3SourceDrift(unittest.TestCase):
    """CASE 3 -- producer or validator changed AFTER the receipt was written."""

    def test_validator_hash_divergence_blocks_and_is_not_the_producer_kind(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td), EVENTS)
            p = base / "validate_canonical_events.py"
            p.write_text(p.read_text(encoding="utf-8") + "\n# a later edit to the VALIDATOR\n",
                         encoding="utf-8")
            r = _audit(base, EVENTS)
            self.assertFalse(r["passed"])
            self.assertEqual(_kinds(r), {"validator_version_divergence"})
            self.assertNotIn("producer_version_divergence", _kinds(r))
            f = r["blocking"][0]
            self.assertEqual(f["receipt"], EVAL)
            self.assertEqual(f["subject"], "validator")
            self.assertEqual(f["link"], "validation_execution")
            self.assertIn(3, f["cases"])

    def test_producer_and_validator_are_separately_named(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td), EVENTS)
            for name in ("build_canonical_events.py", "validate_canonical_events.py"):
                p = base / name
                p.write_text(p.read_text(encoding="utf-8") + "\n# later\n", encoding="utf-8")
            r = _audit(base, EVENTS)
            self.assertEqual(_kinds(r),
                             {"producer_version_divergence", "validator_version_divergence"})
            by = {f["kind"]: f for f in r["blocking"]}
            self.assertEqual(by["producer_version_divergence"]["subject"], "producer")
            self.assertEqual(by["validator_version_divergence"]["subject"], "validator")

    def test_missing_validator_pin_blocks_unless_declared_as_a_gap(self):
        """The turnover validator is unpinned and DECLARED so. The event one is pinned; remove
        it and the gate must block, because that absence is not declared anywhere."""
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td), EVENTS)
            R = _load(base / EVENTS / EVAL)
            del R["validator_sha256"]
            _save(base / EVENTS / EVAL, R)
            r = _audit(base, EVENTS)
            self.assertIn("validator_sha_absent", _kinds(r))

    def test_the_turnover_validator_gap_is_declared_not_silent(self):
        r = _audit(RI.HERE)
        gap = [g for g in r["gaps"] if g["gap"] == "validator_not_pinned"]
        self.assertEqual(len(gap), 1)
        self.assertEqual(gap[0]["receipt"], TVAL)
        self.assertTrue(gap[0]["still_open"])
        self.assertIn("validate_turnover_targets.py", gap[0]["why"])
        self.assertTrue(r["passed"])          # declared, visible, and not silently blocking


class Case4FreshExecutionNotProven(unittest.TestCase):
    """CASE 4 -- a receipt copied forward. NOT decidable from what these receipts record."""

    def test_duplicate_recorded_instant_is_reported_as_not_proven_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            d = base / TURNOVER
            R = _load(d / TVAL)
            R["validated_utc"] = _load(d / TREC)["finished_utc"]      # the same microsecond
            _save(d / TVAL, R)
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertIn("fresh_execution_not_proven", _kinds(r))
            self.assertIn(4, _cases(r))
            f = _of_kind(r, "fresh_execution_not_proven")[0]
            self.assertEqual(sorted(f["recorded_by"]),
                             sorted([f"{TREC}:created", f"{TVAL}:validated"]))

    def test_duplicate_run_token_is_reported_as_not_proven_fresh(self):
        """The evidence that WOULD close case 4: a per-execution token. Given one, a copied
        receipt is detectable on its own, with no timeline finding needed."""
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            spec = dict(RI.FAMILIES[TURNOVER])
            spec["run_token"] = ("run_id",)
            for name in (TREC, TVAL):
                R = _load(base / TURNOVER / name)
                R["run_id"] = "1c0ffee0-0000-4000-8000-000000000001"
                _save(base / TURNOVER / name, R)
            r = RI.audit_family(TURNOVER, spec=spec, base=base, root=RI.ROOT,
                                raise_on_block=False)
            self.assertEqual(_kinds(r), {"fresh_execution_not_proven"})
            self.assertEqual(_of_kind(r, "fresh_execution_not_proven")[0]["subject"], "run_token")

    def test_the_finding_never_claims_validation_did_not_happen(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            d = base / TURNOVER
            R = _load(d / TVAL)
            R["validated_utc"] = _load(d / TREC)["finished_utc"]
            _save(d / TVAL, R)
            reason = _of_kind(_audit(base), "fresh_execution_not_proven")[0]["reason"]
            self.assertIn("may have been copied forward", reason)
            self.assertIn("NOT a claim that validation did not run", reason)

    def test_an_unduplicated_clean_tree_reports_the_gap_and_no_finding(self):
        r = _audit(RI.HERE)
        self.assertNotIn("fresh_execution_not_proven", _kinds(r))
        gap = [g for g in r["gaps"] if g["gap"] == "fresh_execution_unprovable"]
        self.assertEqual(len(gap), 1)
        self.assertTrue(gap[0]["still_open"])
        self.assertIn("run_id", gap[0]["why"] + json.dumps(RI.UNIVERSAL_GAPS[0]["probe"]))

    def test_a_declared_gap_that_is_no_longer_real_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            R = _load(base / TURNOVER / TVAL)
            R["run_id"] = "1c0ffee0-0000-4000-8000-000000000002"
            _save(base / TURNOVER / TVAL, R)
            r = _audit(base)
            self.assertIn("gap_declaration_stale", {f["kind"] for f in r["findings"]})
            self.assertTrue(r["passed"], "a closed gap is news, not a failure")


class Case5RegeneratedArtifactStaleMetadata(unittest.TestCase):
    """CASE 5 -- the artifact was regenerated and the validation metadata was left untouched."""

    def test_rebuilt_artifact_with_untouched_validation_metadata_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            d = base / TURNOVER
            p = d / PLAYER_PARQUET
            df = pd.read_parquet(p)
            df.to_parquet(p, index=False, compression="gzip")   # same rows, new bytes

            # the BUILD receipt is regenerated, exactly as a real rebuild would regenerate it
            trec = _load(d / TREC)
            trec["artifact_sha256"]["player"] = RI.sha256_file(p)
            trec["generated_utc"] = "2026-08-04T15:00:00.000000Z"
            trec["finished_utc"] = "2026-08-04T15:00:01.000000Z"
            _save(d / TREC, trec)
            # TURNOVER_VALIDATION.json is left exactly as it was. That is the defect.

            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertIn(5, _cases(r))
            self.assertIn("stale_validation_verdict", _kinds(r))
            self.assertIn("validation_precedes_artifact", _kinds(r))
            stale = _of_kind(r, "stale_validation_verdict")
            self.assertEqual({f["receipt"] for f in stale}, {TVAL})
            ev = {f["evidence"] for f in stale}
            self.assertEqual(ev, {"certified_hashes_are_not_the_artifact",
                                  "verdict_predates_the_artifact"})
            self.assertEqual([f for f in r["blocking"] if f.get("receipt") == TREC], [])


class ValidatedInputManifest(unittest.TestCase):
    """What the validation run actually consumed, not what the build claims it consumed."""

    @staticmethod
    def _spec_with_validated_inputs():
        spec = dict(RI.FAMILIES[TURNOVER])
        spec["receipts"] = [dict(r) for r in spec["receipts"]]
        spec["receipts"][1]["validated_inputs"] = {
            ("validated_inputs", "master_team"): "data/masters/master_team.parquet"}
        return spec

    def test_a_faithful_validated_input_manifest_passes(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            R = _load(base / TURNOVER / TVAL)
            R["validated_inputs"] = {
                "master_team": RI.sha256_file(RI.ROOT / "data/masters/master_team.parquet")}
            _save(base / TURNOVER / TVAL, R)
            r = RI.audit_family(TURNOVER, spec=self._spec_with_validated_inputs(), base=base,
                                root=RI.ROOT, raise_on_block=False)
            self.assertTrue(r["passed"], r["blocking"])

    def test_validated_input_hash_differing_from_disk_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            R = _load(base / TURNOVER / TVAL)
            R["validated_inputs"] = {"master_team": "e" * 64}
            _save(base / TURNOVER / TVAL, R)
            r = RI.audit_family(TURNOVER, spec=self._spec_with_validated_inputs(), base=base,
                                root=RI.ROOT, raise_on_block=False)
            self.assertFalse(r["passed"])
            self.assertIn("validated_input_divergence", _kinds(r))
            f = _of_kind(r, "validated_input_divergence")[0]
            self.assertEqual(f["in_receipt"], "e" * 64)
            self.assertEqual(f["link"], "validation_execution")

    def test_validation_consuming_a_different_input_than_the_build_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            true_sha = RI.sha256_file(RI.ROOT / "data/masters/master_team.parquet")
            R = _load(base / TURNOVER / TVAL)
            R["validated_inputs"] = {"master_team": true_sha}
            _save(base / TURNOVER / TVAL, R)
            T = _load(base / TURNOVER / TREC)
            T["inputs"]["master_team"] = "d" * 64            # the build used other bytes
            _save(base / TURNOVER / TREC, T)
            r = RI.audit_family(TURNOVER, spec=self._spec_with_validated_inputs(), base=base,
                                root=RI.ROOT, raise_on_block=False)
            self.assertFalse(r["passed"])
            self.assertIn("input_hash_mismatch", _kinds(r))            # the build's pin is wrong
            self.assertIn("validated_input_divergence", _kinds(r))     # and they disagree
            f = [x for x in _of_kind(r, "validated_input_divergence")
                 if x.get("build_receipt")][0]
            self.assertEqual(f["in_build_receipt"], "d" * 64)
            self.assertEqual(f["in_receipt"], true_sha)


class CrossFamilyWitnesses(unittest.TestCase):
    """OPEN EDGE 1, closed: counts that cannot be recomputed inside their own family."""

    def test_the_cross_family_turnover_event_count_is_bound(self):
        r = _audit(RI.HERE)
        self.assertIn("events", r["input_witnesses_checked"])
        self.assertTrue(r["passed"])

    def test_turnover_events_recorded_by_the_build_receipt_is_checked_against_the_events_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            R = _load(base / TURNOVER / TREC)
            R["counts"]["turnover_events"] = 42083          # the stale pre-dedup number
            _save(base / TURNOVER / TREC, R)
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertEqual(_kinds(r), {"input_witness_divergence"})
            f = r["blocking"][0]
            self.assertEqual(f["receipt"], TREC)
            self.assertEqual(f["subject"], "events.turnover_rows")
            self.assertEqual((f["in_receipt"], f["recomputed"]), (42083, 42082))

    def test_the_event_census_the_validation_run_recorded_is_checked_against_the_events_artifact(self):
        """This is the strongest available evidence of WHICH events bytes the validation read."""
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            R = _load(base / TURNOVER / TVAL)
            chk = next(c for c in R["checks"] if c["check"] == "no_double_counting")
            chk["detail"]["families_present_in_events"]["turnover"] = 42083
            _save(base / TURNOVER / TVAL, R)
            r = _audit(base)
            self.assertFalse(r["passed"])
            self.assertEqual(_kinds(r), {"input_witness_divergence"})
            f = r["blocking"][0]
            self.assertEqual(f["receipt"], TVAL)
            self.assertEqual(f["subject"], "events.family_census")

    def test_master_player_witness_binds_what_the_validation_read(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            R = _load(base / TURNOVER / TVAL)
            chk = next(c for c in R["checks"]
                       if c["check"] == "universe_excludes_non_appearances")
            chk["detail"]["box_rows"] = 33713
            _save(base / TURNOVER / TVAL, R)
            r = _audit(base)
            self.assertIn("input_witness_divergence", _kinds(r))
            f = _of_kind(r, "input_witness_divergence")[0]
            self.assertEqual(f["subject"], "master_player.box_rows")
            self.assertEqual((f["in_receipt"], f["recomputed"]), (33713, 33712))

    def test_an_unreachable_input_is_reported_not_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            r = RI.audit_family(TURNOVER, base=base, root=Path(td) / "nowhere",
                                raise_on_block=False)
            kinds = {f["kind"] for f in r["findings"]}
            self.assertIn("input_witness_unavailable", kinds)


class NestedPredictionPin(unittest.TestCase):
    """OPEN EDGE 2, closed: the v15 pin is a nested dict of hash LISTS, not a scalar."""

    def test_the_nested_v15_pin_is_bound_on_the_real_tree(self):
        r = _audit(RI.HERE, PROJ)
        self.assertTrue(r["passed"], r["blocking"])
        self.assertIn("v15", r["input_witnesses_checked"])

    def test_a_tampered_v15_model_hash_list_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td), PROJ)
            R = _load(base / PROJ / PREC)
            R["inputs"]["v15_predictions"]["hashes"]["p_active"]["model_hash"][0] = "0" * 64
            _save(base / PROJ / PREC, R)
            r = _audit(base, PROJ)
            self.assertFalse(r["passed"])
            self.assertIn("input_witness_divergence", _kinds(r))
            f = _of_kind(r, "input_witness_divergence")[0]
            self.assertEqual(f["subject"], "v15.*")

    def test_a_dropped_prediction_head_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td), PROJ)
            R = _load(base / PROJ / PREC)
            del R["inputs"]["v15_predictions"]["hashes"]["e_minutes_given_active"]
            _save(base / PROJ / PREC, R)
            r = _audit(base, PROJ)
            self.assertIn("input_witness_divergence", _kinds(r))


class ChainStructure(unittest.TestCase):
    def test_the_full_clean_chain_passes_on_the_real_tree(self):
        s = RI.sweep()
        self.assertTrue(s["passed"])
        self.assertEqual(s["blocking"], [])
        self.assertEqual(list(s["chain"]), list(RI.CHAIN))
        for fam in ("projected_exposure_v1", "event_contract_v1", "turnover_targets_v1"):
            p = s["per_family"][fam]
            self.assertTrue(p["passed"], fam)
            self.assertTrue(p["target_receipt_current"], fam)
            self.assertGreater(p["counts_cross_checked"], 0, fam)
            self.assertGreater(p["input_witnesses_checked"], 0, fam)
            for link in RI.CHAIN:
                self.assertEqual(s["results"][fam]["chain"][link]["blocking"], 0, (fam, link))

    def test_every_family_records_both_endpoints_of_the_timeline(self):
        s = RI.sweep()
        for fam in s["families"]:
            r = s["results"][fam]
            self.assertIsNotNone(r["artifact_generated_utc"], fam)
            for rname, v in r["validated_utc"].items():
                self.assertTrue(v and v != "None", (fam, rname))

    def test_a_family_with_a_validator_and_no_validation_receipt_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            spec = dict(RI.FAMILIES[TURNOVER])
            spec["receipts"] = [r for r in spec["receipts"] if r.get("role") != "validation"]
            r = RI.audit_family(TURNOVER, spec=spec, base=base, root=RI.ROOT,
                                raise_on_block=False)
            self.assertIn("validation_link_absent", _kinds(r))

    def test_every_finding_is_tagged_with_the_link_it_broke(self):
        with tempfile.TemporaryDirectory() as td:
            base = _stage(Path(td))
            R = _load(base / TURNOVER / TVAL)
            R["artifact_sha256"] = {"player": PRIOR_PLAYER_SHA, "team": PRIOR_TEAM_SHA}
            _save(base / TURNOVER / TVAL, R)
            r = _audit(base)
            for f in r["findings"]:
                self.assertIn(f["link"], RI.CHAIN, f)
            links = {f["kind"]: f["link"] for f in r["blocking"]}
            self.assertEqual(links["artifact_hash_mismatch"], "artifact")
            self.assertEqual(links["stale_validation_verdict"], "validation_receipt")
            self.assertEqual(links["receipt_hash_disagreement"], "validation_execution")

    def test_the_five_cases_are_declared(self):
        self.assertEqual(set(RI.CASES), {1, 2, 3, 4, 5})
        self.assertIn("stale", RI.CASES[1])
        self.assertIn("copied_forward", RI.CASES[4])

    def test_cross_family_duplicate_validation_instants_are_caught_by_the_sweep(self):
        s = RI.sweep(raise_on_block=False)
        self.assertNotIn("fresh_execution_not_proven", s["blocking_kinds"])
        stamps = [v for fam in s["families"]
                  for v in (s["results"][fam]["validated_utc"] or {}).values()]
        self.assertEqual(len(stamps), len(set(stamps)), "real runs must not share an instant")


class CommitLineage(unittest.TestCase):
    """Corroboration only. The receipts record no producing commit -- a declared gap."""

    def test_git_lineage_runs_and_produces_structure(self):
        L = RI.git_lineage(TURNOVER)
        self.assertIn("git_available", L)
        if not L["git_available"]:
            self.skipTest("not a git work tree")
        self.assertIn("artifact:player", L["paths"])
        self.assertIn(f"receipt:{TVAL}", L["paths"])
        for v in L["verdicts"]:
            self.assertIn(v["verdict"], {"descendant_or_same", "not_a_descendant", "no_evidence"})

    def test_lineage_is_never_blocking(self):
        s = RI.sweep(raise_on_block=False, lineage=True)
        self.assertTrue(s["passed"])
        self.assertIn("git_lineage", s)

    def test_the_missing_producing_commit_is_a_declared_gap(self):
        r = _audit(RI.HERE)
        gap = [g for g in r["gaps"] if g["gap"] == "producing_commit_unrecorded"]
        self.assertEqual(len(gap), 1)
        self.assertTrue(gap[0]["still_open"])


class RealTree(unittest.TestCase):
    def test_real_tree_untouched(self):
        for path, sha in _REAL_STATE.items():
            self.assertEqual(RI.sha256_file(Path(path)), sha, f"the suite modified {path}")

    def test_the_untouched_set_covers_artifacts_receipts_and_witness_inputs(self):
        covered = set(_REAL_STATE)
        for name in ("player_turnover_targets_v1.parquet", "canonical_player_events_v1.parquet",
                     "TURNOVER_VALIDATION.json"):
            self.assertTrue(any(p.endswith(name) for p in covered), name)
        for rel in ("data/masters/master_player.parquet", "data/masters/master_team.parquet",
                    "experiments/prediction_contract_v5/player_game_enriched.parquet"):
            self.assertIn(str(RI.ROOT / rel), covered)
        self.assertTrue(any("cbs_v15_player_oof_v5" in p for p in covered))


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
