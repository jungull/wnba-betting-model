#!/usr/bin/env python3
"""cbs_provenance_v4.py — `cbs_provenance/4`: the key is a precondition, not a comment.

WHAT `/3` GOT RIGHT AND IS KEPT HERE
------------------------------------
`cbs_provenance_v3.py` (`/3`, frozen under `contract_baseline_suite_v10`) is reused rather than
restated wherever its behaviour was correct — a duplicated audit is an audit that will
eventually disagree with itself:

* **exact-five artifact-set equality**, in both directions, with the enforced list identical to
  the documented one;
* **hard blockers separated from carried policy limitations**, and
  `provenance_preconditions_met` rather than `real_run_permitted`;
* **the bound-convention check**: a declared `fit_through_date` EARLIER than
  `asof_invariant.bound_from_dates` is a hard blocker; LATER is conservative and merely
  reported;
* **the two-token synthetic escape**, keyword-only, underscore-prefixed, inert alone,
  self-labelling, and refused downstream by `require_real_snapshot_manifest`.

WHAT `/3` STILL GOT WRONG
-------------------------
**It audited everything about the contract except whether the contract could be joined.**
`/3` checked that `player_game.parquet` exists, is attested, hashes correctly, carries a
`row_uid` COLUMN and declares a lawful bound. Every one of those passed for
`prediction_contract_v3`, whose `row_uid` is `pg_uid(player_id, game_id)` — a value 28 rows
share across 14 ids. So `contract_baseline_suite_v10` reported a green gate over a path whose
first real call raises::

    cbs_real_frames_v2.build_player_frame(2024, require_attested=True)
    MergeError: Merge keys are not unique in left dataset; not a one-to-one merge

A column named `row_uid` is not a key. `/4` makes the key itself a **precondition**, checked
against the bytes on disk:

1. **`row_uid` must be UNIQUE** over the emitted frame — the single check whose absence let a
   green gate ship over an unexecutable path.
2. **`row_uid` must RECOMPUTE** from `(player_id, game_id, team_id)` under
   `cbs_obligation_key`. A unique column of arbitrary strings would satisfy (1); it would not
   name the obligation, and a scoring join built on it could not be reproduced from the data.
3. **`player_game_uid` must recompute byte-identically to `prediction_contract_v2.pg_uid`**, so
   the legacy linkage is genuinely the legacy value and not a re-derivation that drifted.
4. **The frame must DECLARE its key rule** (`obligation_key_id`) — an unlabelled key cannot be
   checked against the rule it was supposed to follow.

`/4` adds two further preconditions that `/3` had no notion of, both of which exist because a
receipt that cannot be falsified is not a receipt:

* **The roster provenance must be BOUND, and the binding must hold in the bytes.**
  `src_asof_roster` must equal `admitted_window_bound` and `n_roster_games_consumed` must equal
  `lookback_games_used` on every row, and the window's identity (`roster_evidence_digest`) must
  be present. `/3` accepted a `src_asof_roster` recomputed from a feature-history window that
  merely shared the same maximum timestamp; that coincidence holds on 100% of rows while the
  record sets differ on most of them, so it can never fail and therefore never checked
  anything.
* **The membership rule must be declared as what it is.** The contract must register
  `prior_admitted_team_game_box_membership_including_dnp/1` and carry the measured
  appeared-only counterfactual. `/3`'s contract.json said candidates "APPEARED in a prior
  game" while the producer pooled DNP rows; an audit that reads the document and not the rule
  id cannot notice.

**This module fits nothing, predicts nothing and scores nothing.** Every value it produces is a
path, a column name, a byte count, a hash, a count, a timestamp bound or a boolean.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import asof_invariant as aoi
import cbs_obligation_key as obk
import cbs_provenance as _p2
import cbs_provenance_v3 as _p3
from cbs_identity_v3 import (FRAME_IDENTITY_SCHEMA, REAL_PATH_MODE,
                             frames_digest)
import cbs_v10 as _v10
from prediction_contract_v2 import pg_uid as _v2_pg_uid

PROVENANCE_ID = "cbs_provenance/4"
AUDIT_SCHEMA = "cbs_real_input_audit/4"
SUPERSEDES = _p3.PROVENANCE_ID

#: A NEW manifest schema id, not a redefinition of `/4`.
#:
#: Reconciled by the coordinator at fan-in.  The branch that wrote this module reused
#: `cbs_v10.SNAPSHOT_MANIFEST_SCHEMA` (`cbs_snapshot_manifest/4`) while ALSO adding three
#: required fields to the manifest body -- `obligation_key_id`, `membership_rule_id` and
#: `roster_binding_id`.  A genuine v10-era `/4` manifest carries none of them, so it would
#: have been refused by a checker that still called itself `/4`: two different contracts
#: wearing one name, which is precisely the defect this codebase keeps correcting.
#:
#: `/5` therefore names the stricter contract, and `/1`-`/4` are REFUSED rather than
#: superseded, following the same discipline `cbs_v10` applied to `/1`-`/3`.  v10's manifests
#: remain valid `/4` documents; they are simply not `/5` documents.
SNAPSHOT_MANIFEST_SCHEMA = "cbs_snapshot_manifest/5"

#: Refused outright, not merely superseded: none of these name the obligation key, so a
#: frame digest recorded under them cannot be shown to describe a uniquely-keyed row set.
REJECTED_MANIFEST_SCHEMAS = tuple(_v10.REJECTED_MANIFEST_SCHEMAS) + (
    _v10.SNAPSHOT_MANIFEST_SCHEMA,)

REPO_ROOT = _p2.REPO_ROOT

# --- the v4 contract trio, plus the two masters ----------------------------
CONTRACT_DIR = "experiments/prediction_contract_v4"
PLAYER_GAME = f"{CONTRACT_DIR}/player_game.parquet"
TEAM_GAME = f"{CONTRACT_DIR}/team_game.parquet"
CONTRACT_JSON = f"{CONTRACT_DIR}/contract.json"
MASTER_PLAYER = _p2.MASTER_PLAYER
MASTER_TEAM = _p2.MASTER_TEAM

CBS_REQUIRED_ARTIFACTS = (PLAYER_GAME, TEAM_GAME, CONTRACT_JSON,
                          MASTER_PLAYER, MASTER_TEAM)
#: the superseded sets, retained so each supersession is auditable rather than implied by
#: absence
CBS_REQUIRED_ARTIFACTS_V3_SUPERSEDED = _p3.CBS_REQUIRED_ARTIFACTS
CBS_REQUIRED_ARTIFACTS_V2_SUPERSEDED = _p2.CBS_REQUIRED_ARTIFACTS

MUST_BE_ATTESTED = CBS_REQUIRED_ARTIFACTS
N_REQUIRED_ARTIFACTS = len(CBS_REQUIRED_ARTIFACTS)

# --- the /2 and /3 behaviour that was correct, imported rather than copied --
ACCEPTED_POLICY_LIMITATIONS = _p2.ACCEPTED_POLICY_LIMITATIONS
RUNNER_DERIVED_FEATURES = _p2.RUNNER_DERIVED_FEATURES
ADAPTER_DERIVED_FEATURES = _p2.ADAPTER_DERIVED_FEATURES
ProvenancePreconditionError = _p2.ProvenancePreconditionError
ArtifactSetError = _p3.ArtifactSetError
BoundConventionError = _p3.BoundConventionError
TestEscapeMisuse = _p3.TestEscapeMisuse
artifact_sha256 = _p2.artifact_sha256
attestation_status = _p2.attestation_status
attest_artifact = _p2.attest_artifact

BOUND_CONVENTION = _p3.BOUND_CONVENTION
DATE_BEARING_ARTIFACTS = (PLAYER_GAME, TEAM_GAME, MASTER_PLAYER, MASTER_TEAM)
INHERITED_BOUND_ARTIFACTS = (CONTRACT_JSON,)

# --- the contract's registered ids, which the audit checks the bytes against
OBLIGATION_KEY_ID = obk.OBLIGATION_KEY_ID
MEMBERSHIP_RULE_ID = "prior_admitted_team_game_box_membership_including_dnp/1"
ROSTER_BINDING_ID = "contract_admitted_window/1"
N_CUTOFF_IDENTITY_FIELDS = 8

#: `/3`'s column contract, re-keyed onto v4 and EXTENDED with the columns the new
#: preconditions read. A precondition that depends on a column nobody requires is a
#: precondition that will one day be skipped for lack of input.
REQUIRED_COLUMNS = {
    PLAYER_GAME: ("row_uid", "player_game_uid", "obligation_uid", "obligation_key_id",
                  "membership_rule_id", "game_id", "player_id", "team_id", "season",
                  "game_date", "forecast_cutoff", "fold_id", "appeared", "minutes",
                  "pts", "fga", "src_asof_roster", "n_roster_games_consumed",
                  "src_policy_roster", "roster_binding_id", "roster_evidence_digest",
                  "admitted_window_bound", "lookback_games_used"),
    TEAM_GAME: ("row_uid", "game_id", "team_id", "season", "game_date",
                "forecast_cutoff", "fold_id", "n_candidates", "n_roster_games_consumed",
                "admitted_window_digest"),
    MASTER_PLAYER: _p2.REQUIRED_COLUMNS[_p2.MASTER_PLAYER],
    MASTER_TEAM: _p2.REQUIRED_COLUMNS[_p2.MASTER_TEAM],
}


class ObligationKeyError(ProvenancePreconditionError):
    """The emitted frame's key is absent, non-unique, unlabelled or not reproducible.

    A subclass of `ProvenancePreconditionError` so every existing caller that already catches
    provenance failures catches this one too — a new failure mode that slips past old handlers
    is a new way to run unnoticed.
    """


class RosterBindingError(ProvenancePreconditionError):
    """`src_asof_roster` / `n_roster_games_consumed` are not bound to the candidacy record."""


# --------------------------------------------------------------------------
# exact five, enforced by key equality  (the /3 rule, re-keyed to v4)
# --------------------------------------------------------------------------

def require_exact_artifact_set(artifacts, *, where: str = "snapshot manifest") -> tuple:
    """The artifact set must EQUAL `CBS_REQUIRED_ARTIFACTS`. Both directions."""
    try:
        got = set(artifacts)
    except TypeError as exc:
        raise ArtifactSetError(
            f"{where}: artifacts must be an iterable of paths; got "
            f"{type(artifacts).__name__}") from exc
    want = set(CBS_REQUIRED_ARTIFACTS)
    missing, extra = sorted(want - got), sorted(got - want)
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"MISSING {len(missing)} required artifact(s): {missing}")
        if extra:
            parts.append(f"EXTRA {len(extra)} artifact(s) that are not CBS inputs: {extra}")
        raise ArtifactSetError(
            f"{where} must cover EXACTLY the {N_REQUIRED_ARTIFACTS} CBS required artifacts, no "
            f"subset and no superset. " + "; ".join(parts) + ". A subset means a run's identity "
            f"omits inputs it actually consumed; a superset means the identity silently widens "
            f"to cover a file no reviewer agreed was an input. Required set: "
            f"{sorted(CBS_REQUIRED_ARTIFACTS)}")
    return tuple(CBS_REQUIRED_ARTIFACTS)


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

def schema_status(root: Path | str = REPO_ROOT) -> dict:
    """Do the v4 artifacts supply EVERY required column? ALL, not any."""
    root = Path(root)
    out = {}
    for rel, required in REQUIRED_COLUMNS.items():
        path = root / rel
        if not path.exists():
            out[rel] = {"exists": False, "complete": False,
                        "missing": list(required), "present": []}
            continue
        try:
            cols = set(pd.read_parquet(path).columns)
        except Exception as exc:
            out[rel] = {"exists": True, "complete": False, "unreadable": True,
                        "problem": f"{type(exc).__name__}: {exc}",
                        "missing": list(required), "present": []}
            continue
        missing = [c for c in required if c not in cols]
        out[rel] = {"exists": True, "complete": not missing,
                    "n_required": len(required),
                    "n_present": len(required) - len(missing),
                    "missing": missing,
                    "present": [c for c in required if c in cols]}
    return out


# --------------------------------------------------------------------------
# the key, as a precondition  (the /3 gap)
# --------------------------------------------------------------------------

def obligation_key_status(root: Path | str = REPO_ROOT) -> dict:
    """Is the emitted frame's key a KEY? Unique, reproducible, and labelled.

    Four independent questions, because passing any three of them is still a broken join:

    * `unique` — the check whose absence let `/3` ship. `prediction_contract_v3` satisfies
      "has a row_uid column" and fails this one on 28 rows.
    * `recomputes` — `row_uid` must equal `cbs_obligation_key.row_uid(player_id, game_id,
      team_id)` on every row. A unique column of arbitrary strings passes uniqueness while
      naming nothing; a key that cannot be recomputed from the data cannot be reproduced by a
      reviewer, and a scoring join on it is unverifiable.
    * `legacy_recomputes` — `player_game_uid` must equal `prediction_contract_v2.pg_uid`
      byte-for-byte, so the retained linkage really is the v2 value.
    * `declared` — the frame must carry `obligation_key_id`, so the rule the key claims to
      follow is checkable rather than assumed.
    """
    root = Path(root)
    p = root / PLAYER_GAME
    rec: dict = {"artifact": PLAYER_GAME, "exists": p.exists(),
                 "expected_key_id": OBLIGATION_KEY_ID,
                 "canonical_key_fields": list(obk.CANONICAL_KEY_FIELDS),
                 "unique": None, "recomputes": None, "legacy_recomputes": None,
                 "declared": None, "rows": None, "problems": []}
    if not p.exists():
        rec["problems"].append("artifact absent")
        rec["ok"] = False
        return rec
    try:
        df = pd.read_parquet(p, columns=["row_uid", "player_game_uid", "obligation_key_id",
                                         "player_id", "game_id", "team_id"])
    except Exception as exc:
        rec["problems"].append(f"cannot read the key columns: {type(exc).__name__}: {exc}")
        rec["ok"] = False
        return rec

    rec["rows"] = int(len(df))
    n_dup = int(df.row_uid.duplicated(keep=False).sum())
    rec["unique"] = n_dup == 0
    rec["n_rows_sharing_a_row_uid"] = n_dup
    rec["n_distinct_row_uids"] = int(df.row_uid.nunique())
    if n_dup:
        rec["problems"].append(
            f"row_uid is NOT unique: {n_dup} rows share a key. This is the defect that made "
            f"cbs_real_frames_v2.build_player_frame raise MergeError while the v10 gate "
            f"reported green.")

    want = [obk.row_uid(pl, g, t)
            for pl, g, t in zip(df.player_id, df.game_id.astype(str), df.team_id)]
    n_bad = int((df.row_uid.to_numpy() != pd.Series(want).to_numpy()).sum())
    rec["recomputes"] = n_bad == 0
    rec["n_rows_where_row_uid_does_not_recompute"] = n_bad
    if n_bad:
        rec["problems"].append(
            f"{n_bad} rows whose row_uid does not equal "
            f"cbs_obligation_key.row_uid(player_id, game_id, team_id)")

    want_legacy = [_v2_pg_uid(pl, g) for pl, g in zip(df.player_id, df.game_id.astype(str))]
    n_legacy = int((df.player_game_uid.to_numpy() != pd.Series(want_legacy).to_numpy()).sum())
    rec["legacy_recomputes"] = n_legacy == 0
    rec["n_rows_where_player_game_uid_is_not_v2_pg_uid"] = n_legacy
    rec["n_rows_sharing_a_player_game_uid"] = int(
        df.player_game_uid.duplicated(keep=False).sum())
    rec["legacy_key_is_not_unique_and_that_is_expected"] = True
    if n_legacy:
        rec["problems"].append(
            f"{n_legacy} rows whose player_game_uid is not prediction_contract_v2.pg_uid")

    declared = set(df.obligation_key_id.dropna().unique())
    rec["declared_key_ids"] = sorted(str(x) for x in declared)
    rec["declared"] = declared == {OBLIGATION_KEY_ID}
    if not rec["declared"]:
        rec["problems"].append(
            f"the frame declares obligation_key_id {rec['declared_key_ids']}, not "
            f"[{OBLIGATION_KEY_ID!r}]")

    rec["ok"] = not rec["problems"]
    return rec


def obligation_key_blockers(status: dict) -> list[dict]:
    """Every key failure is a HARD blocker. A frame that cannot be joined cannot be used."""
    return [{"kind": "obligation_key_violation", "artifact": status["artifact"],
             "repairable": True, "detail": prob}
            for prob in status.get("problems", [])]


# --------------------------------------------------------------------------
# the roster binding, as a precondition
# --------------------------------------------------------------------------

def roster_binding_status(root: Path | str = REPO_ROOT) -> dict:
    """Do `src_asof_roster` / `n_roster_games_consumed` hold the candidacy record's values?

    Checked in the BYTES, not in the prose. `/3` had no such check because there was nothing to
    check against: its downstream roster bound was recomputed from a feature-history window and
    agreed with the contract by arithmetic coincidence on every row.
    """
    root = Path(root)
    p = root / PLAYER_GAME
    rec: dict = {"artifact": PLAYER_GAME, "exists": p.exists(),
                 "expected_binding_id": ROSTER_BINDING_ID, "problems": []}
    if not p.exists():
        rec["problems"].append("artifact absent")
        rec["ok"] = False
        return rec
    cols = ["src_asof_roster", "n_roster_games_consumed", "admitted_window_bound",
            "lookback_games_used", "roster_binding_id", "roster_evidence_digest",
            "roster_evidence_first_game", "roster_evidence_last_game"]
    try:
        df = pd.read_parquet(p, columns=cols)
    except Exception as exc:
        rec["problems"].append(f"cannot read the roster columns: {type(exc).__name__}: {exc}")
        rec["ok"] = False
        return rec

    rec["rows"] = int(len(df))
    a = pd.to_datetime(df.src_asof_roster, utc=True)
    b = pd.to_datetime(df.admitted_window_bound, utc=True)
    n_bound = int(((a != b) | a.isna() | b.isna()).sum())
    rec["bound_equals_admitted_window_bound"] = n_bound == 0
    rec["n_rows_where_the_bound_is_not_the_candidacy_bound"] = n_bound
    if n_bound:
        rec["problems"].append(
            f"{n_bound} rows whose src_asof_roster is not the contract's "
            f"admitted_window_bound; the roster bound is not bound to the candidacy record")

    n_count = int((df.n_roster_games_consumed.astype("int64")
                   != df.lookback_games_used.astype("int64")).sum())
    rec["count_equals_lookback_games_used"] = n_count == 0
    rec["n_rows_where_the_count_is_not_the_window_size"] = n_count
    if n_count:
        rec["problems"].append(
            f"{n_count} rows whose n_roster_games_consumed is not lookback_games_used")

    n_empty = int((df.n_roster_games_consumed.astype("int64") <= 0).sum())
    rec["n_rows_reporting_no_roster_evidence"] = n_empty
    if n_empty:
        rec["problems"].append(
            f"{n_empty} candidate rows report zero roster games consumed; a candidate cannot "
            f"exist without a non-empty admitted window")

    n_nodigest = int(df.roster_evidence_digest.isna().sum())
    rec["window_identity_present"] = n_nodigest == 0
    rec["n_rows_without_a_window_digest"] = n_nodigest
    if n_nodigest:
        rec["problems"].append(
            f"{n_nodigest} rows carry no roster_evidence_digest; without the window's identity "
            f"a consumer that read different records is undetectable")

    declared = set(df.roster_binding_id.dropna().unique())
    rec["declared_binding_ids"] = sorted(str(x) for x in declared)
    rec["declared"] = declared == {ROSTER_BINDING_ID}
    if not rec["declared"]:
        rec["problems"].append(
            f"the frame declares roster_binding_id {rec['declared_binding_ids']}, not "
            f"[{ROSTER_BINDING_ID!r}]")

    rec["ok"] = not rec["problems"]
    return rec


def roster_binding_blockers(status: dict) -> list[dict]:
    return [{"kind": "roster_binding_violation", "artifact": status["artifact"],
             "repairable": True, "detail": prob}
            for prob in status.get("problems", [])]


# --------------------------------------------------------------------------
# the contract's own declarations
# --------------------------------------------------------------------------

def contract_declaration_status(root: Path | str = REPO_ROOT) -> dict:
    """Does contract.json register the rules the frame claims to follow?

    Three declarations, each of which `/3` either lacked or got wrong:

    * the MEMBERSHIP rule id must be the box-membership one, and the appeared-only
      counterfactual must be present with its measured count — `/3`'s document said candidates
      "APPEARED in a prior game" while the producer pooled DNP rows;
    * the OBLIGATION KEY id must be registered in the document, not only in the parquet;
    * the CUTOFF IDENTITY receipt must record all eight fields compared and `ok` — `/3`
      compared two.
    """
    root = Path(root)
    p = root / CONTRACT_JSON
    rec: dict = {"artifact": CONTRACT_JSON, "exists": p.exists(), "problems": []}
    if not p.exists():
        rec["problems"].append("artifact absent")
        rec["ok"] = False
        return rec
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        rec["problems"].append(f"unreadable contract.json: {type(exc).__name__}: {exc}")
        rec["ok"] = False
        return rec

    rec["contract_version"] = doc.get("contract_version")
    rec["membership_rule_id"] = doc.get("membership_rule_id")
    if doc.get("membership_rule_id") != MEMBERSHIP_RULE_ID:
        rec["problems"].append(
            f"contract declares membership_rule_id {doc.get('membership_rule_id')!r}, not "
            f"{MEMBERSHIP_RULE_ID!r}")

    cf = doc.get("appeared_only_counterfactual") or {}
    rec["appeared_only_rows"] = cf.get("appeared_only_rows")
    rec["registered_rows"] = cf.get("registered_rows")
    rec["appeared_only_delta"] = cf.get("obligations_that_exist_only_because_dnp_rows_count")
    if not cf:
        rec["problems"].append(
            "contract carries no appeared_only_counterfactual; the membership rule is stated "
            "without the measurement that shows how far it is from the rule v3's prose "
            "described")
    elif not isinstance(cf.get("appeared_only_rows"), int):
        rec["problems"].append("appeared_only_counterfactual carries no measured row count")

    key = doc.get("obligation_key") or {}
    rec["declared_key_id"] = key.get("obligation_key_id")
    if key.get("obligation_key_id") != OBLIGATION_KEY_ID:
        rec["problems"].append(
            f"contract declares obligation key {key.get('obligation_key_id')!r}, not "
            f"{OBLIGATION_KEY_ID!r}")

    ci = ((doc.get("accounting") or {}).get("cutoff_identity_vs_v2")) or {}
    rec["cutoff_identity_fields"] = ci.get("n_fields_compared")
    rec["cutoff_identity_ok"] = ci.get("ok")
    rec["cutoff_identity_games"] = ci.get("games_compared")
    if ci.get("n_fields_compared") != N_CUTOFF_IDENTITY_FIELDS:
        rec["problems"].append(
            f"cutoff identity compared {ci.get('n_fields_compared')} fields, not "
            f"{N_CUTOFF_IDENTITY_FIELDS}; v3 compared forecast_cutoff and cutoff_policy only, "
            f"so a run reproducing the same cutoff from different tip evidence would pass")
    if ci.get("ok") is not True:
        rec["problems"].append("cutoff identity against the registered v2 game.parquet is not "
                               "recorded as ok")

    rb = doc.get("roster_provenance_binding") or {}
    rec["roster_binding_id"] = rb.get("binding_id")
    if rb.get("binding_id") != ROSTER_BINDING_ID:
        rec["problems"].append(
            f"contract declares roster binding {rb.get('binding_id')!r}, not "
            f"{ROSTER_BINDING_ID!r}")

    rec["ok"] = not rec["problems"]
    return rec


def contract_declaration_blockers(status: dict) -> list[dict]:
    return [{"kind": "contract_declaration_violation", "artifact": status["artifact"],
             "repairable": True, "detail": prob}
            for prob in status.get("problems", [])]


# --------------------------------------------------------------------------
# bound convention  (the /3 check, re-keyed to v4)
# --------------------------------------------------------------------------

def bound_convention_status(root: Path | str = REPO_ROOT) -> dict:
    """`/3`'s bound-convention verdicts, computed over the v4 artifact set.

    Delegating to `_p3.bound_convention_status` would have audited the SUPERSEDED v3 paths,
    which is the class of mistake `/3` itself documented when it re-keyed `/2`'s audit.
    """
    root = Path(root)
    out: dict[str, dict] = {}
    recomputed: dict[str, object] = {}

    for rel in DATE_BEARING_ARTIFACTS:
        p = root / rel
        rec = {"exists": p.exists(), "kind": "date_bearing",
               "convention": BOUND_CONVENTION, "declared": None, "recomputed": None,
               "declared_bound_source": None, "verdict": None, "problem": None}
        if not p.exists():
            rec["verdict"], rec["problem"] = "unknown", "artifact absent"
            out[rel] = rec
            continue
        try:
            m = aoi.read_manifest(p)
        except Exception as exc:
            rec["verdict"] = "unknown"
            rec["problem"] = f"unreadable manifest: {type(exc).__name__}: {exc}"
            out[rel] = rec
            continue
        rec["declared_bound_source"] = m.get("bound_source")
        declared = aoi.to_utc(m["fit_through_date"])
        rec["declared"] = declared.isoformat()
        bound, why = _p3._recompute_bound(p)
        if bound is None:
            rec["verdict"], rec["problem"] = "unknown", why
            out[rel] = rec
            continue
        recomputed[rel] = bound
        rec["recomputed"] = bound.isoformat()
        if declared == bound:
            rec["verdict"] = "follows_convention"
        elif declared > bound:
            rec["verdict"] = "conservative_but_not_exact"
            rec["problem"] = ("declared bound is LATER than bound_from_dates; over-cautious, "
                              "so not a blocker")
        else:
            rec["verdict"] = "anti_conservative"
            rec["problem"] = (
                f"declared {declared.isoformat()} is EARLIER than the convention's "
                f"{bound.isoformat()}. A bare game_date read as midnight sits BEFORE the games "
                f"played on that date.")
        out[rel] = rec

    inherited_from = max(recomputed.values()) if recomputed else None
    for rel in INHERITED_BOUND_ARTIFACTS:
        p = root / rel
        rec = {"exists": p.exists(), "kind": "inherited",
               "convention": f"max over {list(DATE_BEARING_ARTIFACTS)} via {BOUND_CONVENTION}",
               "declared": None, "recomputed": None, "declared_bound_source": None,
               "verdict": None, "problem": None}
        if not p.exists():
            rec["verdict"], rec["problem"] = "unknown", "artifact absent"
            out[rel] = rec
            continue
        try:
            m = aoi.read_manifest(p)
        except Exception as exc:
            rec["verdict"] = "unknown"
            rec["problem"] = f"unreadable manifest: {type(exc).__name__}: {exc}"
            out[rel] = rec
            continue
        rec["declared_bound_source"] = m.get("bound_source")
        declared = aoi.to_utc(m["fit_through_date"])
        rec["declared"] = declared.isoformat()
        if inherited_from is None:
            rec["verdict"] = "unknown"
            rec["problem"] = "no date-bearing bound could be recomputed to inherit from"
        elif declared == inherited_from:
            rec["verdict"] = "follows_convention"
            rec["recomputed"] = inherited_from.isoformat()
        elif declared > inherited_from:
            rec["verdict"] = "conservative_but_not_exact"
            rec["recomputed"] = inherited_from.isoformat()
            rec["problem"] = "inherited bound is later than the tables it describes"
        else:
            rec["verdict"] = "anti_conservative"
            rec["recomputed"] = inherited_from.isoformat()
            rec["problem"] = (
                f"declared {declared.isoformat()} is EARLIER than the maximum bound of the "
                f"tables it describes ({inherited_from.isoformat()})")
        out[rel] = rec
    return out


bound_convention_blockers = _p3.bound_convention_blockers


def feature_availability(root: Path | str = REPO_ROOT) -> dict:
    """Which Stage-A features the V4 contract itself supplies. ALL-required semantics.

    `/3` called `_p2.feature_availability`, which reads the V2 contract paths — so the audit of
    the v3 universe reported the v2 frame's feature coverage.
    """
    root = Path(root)
    out: dict = {}
    p = root / PLAYER_GAME
    if p.exists():
        try:
            cols = set(pd.read_parquet(p).columns)
        except Exception:
            cols = set()
        present = [f for f in ADAPTER_DERIVED_FEATURES if f in cols]
        missing = [f for f in ADAPTER_DERIVED_FEATURES if f not in cols]
        out["stage_a_from_contract"] = {
            "n_required": len(ADAPTER_DERIVED_FEATURES), "n_present": len(present),
            "present": present, "missing": missing, "complete": not missing,
            "note": ("p_plays_prior and player_gp_season are derived by the RUNNER from its "
                     "own admitted history and are excluded from this set. The contract is a "
                     "ROW UNIVERSE, not a feature store: it is expected to supply none of "
                     "these, and this entry is reported, never a blocker.")}
    return out


# --------------------------------------------------------------------------
# the audit
# --------------------------------------------------------------------------

def audit(root: Path | str = REPO_ROOT) -> dict:
    """`/3`'s audit, re-keyed to v4, plus the key, roster-binding and declaration checks.

    Schema, provenance and identity only. Fits nothing, predicts nothing, scores nothing,
    relates no feature to any outcome.
    """
    root = Path(root)
    att = attestation_status(root, CBS_REQUIRED_ARTIFACTS)
    for entry in att.values():
        entry["must_be_attested"] = True
    sch = schema_status(root)
    bounds = bound_convention_status(root)
    keys = obligation_key_status(root)
    roster = roster_binding_status(root)
    decl = contract_declaration_status(root)

    hard: list[dict] = []
    for rel, e in sorted(att.items()):
        if not e["exists"]:
            hard.append({"kind": "artifact_absent", "artifact": rel,
                         "repairable": True, "detail": "file not found"})
        elif not e["manifest_valid"]:
            hard.append({"kind": "artifact_unattested", "artifact": rel,
                         "repairable": True, "detail": e["problem"]})
        elif e["hash_ok"] is False:
            hard.append({"kind": "artifact_hash_drift", "artifact": rel, "repairable": True,
                         "detail": "manifest does not match the bytes on disk"})
    for rel, e in sorted(sch.items()):
        if e["exists"] and not e["complete"]:
            hard.append({"kind": "required_columns_missing", "artifact": rel,
                         "repairable": True, "detail": f"missing {e['missing']}"})
    hard += bound_convention_blockers(bounds)
    hard += obligation_key_blockers(keys)
    hard += roster_binding_blockers(roster)
    hard += contract_declaration_blockers(decl)

    try:
        require_exact_artifact_set(CBS_REQUIRED_ARTIFACTS)
        set_ok, set_problem = True, None
    except ArtifactSetError as exc:                                # pragma: no cover
        set_ok, set_problem = False, str(exc)

    return {
        "schema": AUDIT_SCHEMA,
        "provenance": PROVENANCE_ID,
        "supersedes": SUPERSEDES,
        "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "required_artifact_set": list(CBS_REQUIRED_ARTIFACTS),
        "n_required_artifacts": N_REQUIRED_ARTIFACTS,
        "artifact_set_rule": ("EXACT key equality with CBS_REQUIRED_ARTIFACTS: subsets and "
                              "supersets are both rejected"),
        "artifact_set_self_check": {"ok": set_ok, "problem": set_problem},
        "superseded_artifact_sets": {
            "cbs_provenance/3": list(CBS_REQUIRED_ARTIFACTS_V3_SUPERSEDED),
            "cbs_provenance/2": list(CBS_REQUIRED_ARTIFACTS_V2_SUPERSEDED)},
        "attestation": att,
        "required_columns": sch,
        "contract_feature_availability": feature_availability(root),
        "bound_convention": BOUND_CONVENTION,
        "bound_convention_status": bounds,
        "obligation_key": OBLIGATION_KEY_ID,
        "obligation_key_status": keys,
        "roster_binding_status": roster,
        "contract_declaration_status": decl,
        "accepted_policy_limitations": ACCEPTED_POLICY_LIMITATIONS,
        "n_accepted_policy_limitations": len(ACCEPTED_POLICY_LIMITATIONS),
        "hard_blockers": hard,
        "n_hard_blockers": len(hard),
        # still NOT `real_run_permitted`; /2's reasoning stands
        "provenance_preconditions_met": not hard,
        "supervisory_authorization_required": True,
        "verdict": ("all hard blockers cleared; the accepted policy limitations above are "
                    "carried and labelled per row. This is a statement about provenance "
                    "readiness ONLY — it is not authorization to fit, predict, score or "
                    "evaluate anything."
                    if not hard else
                    f"{len(hard)} hard blocker(s) must be fixed before a real run"),
    }


# --------------------------------------------------------------------------
# manifest construction  (the /3 design, unchanged in structure)
# --------------------------------------------------------------------------

def _manifest_body(status: dict, artifacts: tuple, frames: dict) -> dict:
    return {
        "schema": SNAPSHOT_MANIFEST_SCHEMA,
        "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
        "frame_identity_mode": REAL_PATH_MODE,
        "provenance": PROVENANCE_ID,
        "obligation_key_id": OBLIGATION_KEY_ID,
        "membership_rule_id": MEMBERSHIP_RULE_ID,
        "roster_binding_id": ROSTER_BINDING_ID,
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifact_set_rule": ("EXACT key equality with CBS_REQUIRED_ARTIFACTS: subsets and "
                              "supersets are both rejected"),
        "n_required_artifacts": N_REQUIRED_ARTIFACTS,
        "artifacts": {rel: {"sha256": status[rel]["sha256"], "bytes": status[rel]["bytes"]}
                      for rel in sorted(artifacts)},
        "frames": frames_digest(frames, mode=REAL_PATH_MODE),
        "accepted_policy_limitations": ACCEPTED_POLICY_LIMITATIONS,
    }


def build_snapshot_manifest(frames: dict, *, root: Path | str = REPO_ROOT,
                            require_attested: bool = True, synthetic: bool = False,
                            _test_artifacts=None) -> dict:
    """A snapshot manifest over EXACTLY the five required artifacts.

    The two-token synthetic escape is `/3`'s, unchanged: keyword-only, underscore-prefixed,
    rejected outright without `synthetic=True`, granting nothing when `synthetic=True` is
    passed alone, and labelling its own output so a downstream refusal does not depend on
    anyone remembering how the manifest was made.
    """
    root = Path(root)
    if _test_artifacts is not None and not synthetic:
        raise TestEscapeMisuse(
            "_test_artifacts is a SYNTHETIC-ONLY override and was passed without "
            "synthetic=True. It is refused outright rather than being ignored or falling back "
            "to the required five: silently ignoring it would let a caller believe they had "
            "overridden the artifact set, and silently honouring it would let one stray "
            "keyword disable the check that guarantees a real run names every input it "
            "consumed. Two independent explicit tokens are required, by design.")

    if _test_artifacts is None:
        artifacts = require_exact_artifact_set(CBS_REQUIRED_ARTIFACTS,
                                               where="snapshot manifest")
        test_only = False
    else:
        artifacts = tuple(_test_artifacts)
        if not artifacts:
            raise TestEscapeMisuse("_test_artifacts must name at least one artifact")
        test_only = True

    status = attestation_status(root, artifacts)
    problems = []
    for rel, e in sorted(status.items()):
        if not e["exists"]:
            problems.append(f"{rel}: absent")
        elif require_attested and rel in CBS_REQUIRED_ARTIFACTS:
            if not e["manifest_valid"]:
                problems.append(f"{rel}: unattested ({e['problem']})")
            elif e["hash_ok"] is False:
                problems.append(f"{rel}: manifest does not match the file's bytes")
    if problems:
        raise ProvenancePreconditionError(
            "cannot build a snapshot manifest; required inputs are not provenance-ready: "
            + "; ".join(problems))

    # /4: the key is part of provenance readiness, not a downstream surprise.
    if not test_only and require_attested:
        keys = obligation_key_status(root)
        if not keys["ok"]:
            raise ObligationKeyError(
                "cannot build a snapshot manifest; the contract's obligation key is not a key: "
                + "; ".join(keys["problems"]))
        roster = roster_binding_status(root)
        if not roster["ok"]:
            raise RosterBindingError(
                "cannot build a snapshot manifest; roster provenance is not bound to the "
                "candidacy record: " + "; ".join(roster["problems"]))

    man = _manifest_body(status, artifacts, frames)
    if test_only:
        man["synthetic"] = True
        man["real_path_permitted"] = False
        man["artifact_set_scope"] = "TEST_ONLY_SYNTHETIC_OVERRIDE"
        man["why_not_real"] = (
            "built through the synthetic-only _test_artifacts escape; its artifact set is NOT "
            "the five CBS required inputs and it is refused by "
            "require_real_snapshot_manifest")
    else:
        man["synthetic"] = bool(synthetic)
        man["real_path_permitted"] = not synthetic
    return man


def build_real_snapshot_manifest(frames: dict, *, root: Path | str = REPO_ROOT) -> dict:
    """The REAL entry point. No artifact parameter exists, so none can be misused."""
    return build_snapshot_manifest(frames, root=root, require_attested=True)


def require_real_snapshot_manifest(manifest: dict) -> dict:
    """Refuse any manifest a real run must not consume. Raises, or returns a receipt."""
    if not isinstance(manifest, dict):
        raise ArtifactSetError("snapshot manifest must be a mapping")
    if manifest.get("real_path_permitted") is False or manifest.get("synthetic"):
        raise ArtifactSetError(
            f"this manifest is stamped synthetic / real_path_permitted=False "
            f"({manifest.get('why_not_real') or 'built for a synthetic fixture'}) and must not "
            f"be consumed by a real run")
    # The schema gate is enforced HERE, not merely declared in REJECTED_MANIFEST_SCHEMAS.
    # Added by the coordinator at fan-in: the real-integration gate measured that this
    # function never read `schema`, so a document stamped `cbs_snapshot_manifest/4` but
    # otherwise /5-shaped was ACCEPTED. A refusal list that nothing consults is a comment.
    # Genuine v10-era documents were already refused below for lacking `obligation_key_id`;
    # this closes the case where the field is present but the schema label disagrees.
    schema = manifest.get("schema")
    if schema in REJECTED_MANIFEST_SCHEMAS:
        raise ArtifactSetError(
            f"manifest schema {schema!r} is REFUSED by {PROVENANCE_ID}: it does not name an "
            f"obligation key, so its frame digests cannot be shown to describe a uniquely "
            f"keyed row set. Rebuild with {SNAPSHOT_MANIFEST_SCHEMA!r}.")
    if schema != SNAPSHOT_MANIFEST_SCHEMA:
        raise ArtifactSetError(
            f"snapshot manifest schema must be {SNAPSHOT_MANIFEST_SCHEMA!r}; got {schema!r}")
    if manifest.get("frame_identity_schema") != FRAME_IDENTITY_SCHEMA:
        raise ArtifactSetError(
            f"manifest must declare frame_identity_schema {FRAME_IDENTITY_SCHEMA!r}; got "
            f"{manifest.get('frame_identity_schema')!r}")
    if manifest.get("obligation_key_id") != OBLIGATION_KEY_ID:
        raise ArtifactSetError(
            f"manifest must declare obligation_key_id {OBLIGATION_KEY_ID!r}; got "
            f"{manifest.get('obligation_key_id')!r}. A snapshot identity that does not name "
            f"the key its rows are addressed by cannot be checked against the frame it covers.")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ArtifactSetError("snapshot manifest lists no artifacts")
    require_exact_artifact_set(artifacts.keys(), where="snapshot manifest")
    frames = manifest.get("frames")
    if not isinstance(frames, dict) or not frames:
        raise ArtifactSetError(
            "snapshot manifest declares no frames; the identity must cover the frames actually "
            "consumed, not only the files they came from")
    return {"receipt": "real_snapshot_manifest/2", "ok": True, "provenance": PROVENANCE_ID,
            "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
            "obligation_key_id": OBLIGATION_KEY_ID,
            "n_artifacts": len(artifacts), "n_frames": len(frames)}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    rep = audit(args.root)
    text = json.dumps(rep, indent=2, default=str) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    print(f"\nhard blockers: {rep['n_hard_blockers']}  |  carried policy limitations: "
          f"{rep['n_accepted_policy_limitations']}")
    for rel, e in sorted(rep["bound_convention_status"].items()):
        print(f"  bound  {e['verdict']:28s}  {rel}")
    k = rep["obligation_key_status"]
    print(f"  key    unique={k.get('unique')} recomputes={k.get('recomputes')} "
          f"legacy={k.get('legacy_recomputes')} declared={k.get('declared')}")
    r = rep["roster_binding_status"]
    print(f"  roster bound_ok={r.get('bound_equals_admitted_window_bound')} "
          f"count_ok={r.get('count_equals_lookback_games_used')} "
          f"identity={r.get('window_identity_present')}")
    print(rep["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
