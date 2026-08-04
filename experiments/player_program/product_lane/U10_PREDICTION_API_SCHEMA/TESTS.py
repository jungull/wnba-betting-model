"""
U10_PREDICTION_API_SCHEMA -- tests.

Repo convention (pytest is not installed): standalone runnable script, main()
returns 1 on failure.  Run:

    python experiments/player_program/product_lane/U10_PREDICTION_API_SCHEMA/TESTS.py

These tests read `arm_registry.jsonl` (read-only) to derive the list of model
identifiers that must NOT appear in the schema source.  They read nothing under
`stage2b/SEALED_RESULTS`, and they fit, score and compare nothing.
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROGRAM = HERE.parent.parent          # experiments/player_program
sys.path.insert(0, str(HERE))

import build_fixtures as BF                      # noqa: E402
import prediction_response_schema as S           # noqa: E402

FAILURES: list[str] = []
SKIPS: list[str] = []
CHECKS = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(f"{name}: {detail}")


def skip(name: str, why: str) -> None:
    print(f"  SKIP  {name}  ({why})")
    SKIPS.append(f"{name}: {why}")


def rejects(name: str, doc: dict, expect_fragment: str = "") -> None:
    try:
        S.validate_response(doc)
    except S.SchemaViolation as exc:
        check(name, expect_fragment in str(exc),
              f"raised {exc!r}, expected fragment {expect_fragment!r}")
        return
    check(name, False, "validator ACCEPTED a document it must reject")


def golden() -> dict[str, dict]:
    out = {}
    for p in sorted((HERE / "fixtures" / "responses").glob("*.json")):
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


# ---------------------------------------------------------------- 1. envelope


def t_envelope_and_versioning() -> None:
    print("\n[1] envelope and versioning")
    check("schema name", S.SCHEMA_NAME == "player_prediction_response/1", S.SCHEMA_NAME)
    check("semver parses", S.parse_version(S.SCHEMA_VERSION) == (1, 0, 0))
    check("same version compatible", S.is_compatible("1.0.0"))
    check("future minor rejected", not S.is_compatible("1.1.0"))
    check("other major rejected", not S.is_compatible("2.0.0"))
    for name, doc in golden().items():
        check(f"{name}: envelope versioned",
              doc["schema"] == S.SCHEMA_NAME and doc["schema_version"] == S.SCHEMA_VERSION)
        check(f"{name}: audit repeats version",
              doc["audit"]["schema_version"] == doc["schema_version"])


# --------------------------------------------------------- 2. model agnostic


def registry_identifiers() -> set[str]:
    ids: set[str] = set()
    reg = PROGRAM / "arm_registry.jsonl"
    if not reg.exists():
        return ids
    for line in reg.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("arm_id", "arm", "id", "experiment_id", "name", "family"):
            v = rec.get(key)
            if isinstance(v, str) and len(v) > 3:
                ids.add(v)
    return ids


# Identifiers named in the governing scientific state, which this schema must
# also not know about.
EXTRA_MODEL_LITERALS = {
    "D_ewma_shrunk", "ewma_shrunk", "K0_FLAT", "K0_MATCHED",
    "bottomup_3pt_channel_v1", "cbs_player_runner_v14", "cbs_v15",
}


def t_model_agnosticism() -> None:
    print("\n[2] model agnosticism")
    src = (HERE / "prediction_response_schema.py").read_text(encoding="utf-8")
    ids = registry_identifiers()
    check("registry read", len(ids) > 0, f"{len(ids)} identifiers")
    hits = sorted(i for i in ids | EXTRA_MODEL_LITERALS if i in src)
    check("no model identifier appears in the schema source", not hits, str(hits))

    bsrc = (HERE / "build_fixtures.py").read_text(encoding="utf-8")
    bhits = sorted(i for i in ids | EXTRA_MODEL_LITERALS if i in bsrc)
    check("no model identifier appears in the fixture generator", not bhits, str(bhits))

    g = golden()
    a, b = g["nominal"], g["nominal_other_model"]
    check("two different model descriptors over identical fixtures",
          a["model"]["model_version"] != b["model"]["model_version"]
          and a["model"]["artifact_sha256"] != b["model"]["artifact_sha256"])
    strip_a = {k: v for k, v in a.items() if k not in ("model", "response_id", "audit")}
    strip_b = {k: v for k, v in b.items() if k not in ("model", "response_id", "audit")}
    check("swapping the model changes only the model block",
          strip_a == strip_b,
          "documents differ outside model/response_id/audit")
    check("promotion status is a closed vocabulary",
          all(d["model"]["promotion_status"] in S.PROMOTION_STATUS_VALUES
              for d in g.values()))
    check("no fixture asserts a promotion",
          all(d["model"]["promotion_status"] == "no_challenger_promoted"
              for d in g.values()))
    check("every fixture response is flagged fixture_mode",
          all(d["audit"]["fixture_mode"] is True for d in g.values()))


# ------------------------------------------------------ 3. required contents


REQUIRED_BLOCKS = {
    "game ids": lambda d: bool(d["game"]["game_id"]) and bool(d["game"]["game_cluster_id"]),
    "model version": lambda d: bool(d["model"]["model_version"]),
    "artifact hashes": lambda d: bool(d["model"]["artifact_sha256"]),
    "input freshness": lambda d: all("freshness" in i for i in d["inputs"]),
    "projections": lambda d: len(d["projections"]) > 0,
    "uncertainty": lambda d: all(
        set(p["uncertainty"]) == set(S.UNCERTAINTY_FIELDS) for p in d["projections"]
    ),
    "warnings": lambda d: isinstance(d["warnings"], list),
    "component explanations": lambda d: all(
        len(p["components"]) > 0 for p in d["projections"]
    ),
    "market comparison": lambda d: all("market" in p for p in d["projections"]),
    "audit metadata": lambda d: bool(d["audit"]["inputs_digest"]),
}


def t_required_contents() -> None:
    print("\n[3] required response contents")
    for name, doc in golden().items():
        for block, fn in REQUIRED_BLOCKS.items():
            check(f"{name}: carries {block}", fn(doc))


# ------------------------------------------- 4. absence renders as a warning


DEGRADED_SCENARIOS = {
    "stale_input": "team_history",
    "missing_lineup": "lineup_report",
    "failed_job": "lineup_report",
    "no_market": "market_capture",
}


def t_absence_is_a_warning() -> None:
    print("\n[4] absence renders as an explicit warning, never as a number")
    g = golden()
    for scenario, bad_input in DEGRADED_SCENARIOS.items():
        doc = g[scenario]
        rec = next(i for i in doc["inputs"] if i["input_id"] == bad_input)
        check(f"{scenario}: {bad_input} is marked degraded", rec["degraded"] is True)
        check(f"{scenario}: degraded input raises a blocking warning",
              any(w["severity"] == "blocking" and w["scope"] == f"input:{bad_input}"
                  for w in doc["warnings"]))
        dependants = [p for p in doc["projections"] if bad_input in p["depends_on"]]
        for p in dependants:
            pid = p["projection_id"]
            check(f"{scenario}: {pid} withheld", p["status"] == "withheld")
            check(f"{scenario}: {pid} carries no point", p["point"] is None)
            check(f"{scenario}: {pid} carries no uncertainty",
                  all(v is None for v in p["uncertainty"].values()))
            check(f"{scenario}: {pid} carries no component numbers",
                  all(c["contribution"] is None for c in p["components"]))
            check(f"{scenario}: {pid} carries no market edge",
                  p["market"]["edge_vs_line"] is None)
            check(f"{scenario}: {pid} has a blocking warning",
                  any(w["severity"] == "blocking" and w["scope"] == f"projection:{pid}"
                      for w in doc["warnings"]))

    # An unavailable market is stated, never imputed.
    doc = g["no_market"]
    check("no_market: every market block is explicitly unavailable with a reason",
          all(p["market"]["available"] is False
              and p["market"]["line"] is None
              and p["market"]["edge_vs_line"] is None
              and bool(p["market"]["unavailable_reason"])
              for p in doc["projections"]))
    check("no_market: a missing market does not withhold the projection",
          all(p["status"] == "served" for p in doc["projections"]),
          "market capture is not declared a projection dependency")

    # A model that produced nothing gets no substitute.
    doc = g["no_value_produced"]
    p = next(p for p in doc["projections"] if p["projection_id"] == "player_0002_exposure")
    check("no_value_produced: absent value is withheld, not defaulted",
          p["status"] == "withheld" and p["point"] is None
          and "no_value_produced" in p["withheld_reasons"])

    # No withheld projection anywhere carries any number at all.
    leaked = []
    for name, doc in g.items():
        for p in doc["projections"]:
            if p["status"] != "withheld":
                continue
            nums = [p["point"], *p["uncertainty"].values(),
                    *[c["contribution"] for c in p["components"]],
                    p["market"]["edge_vs_line"]]
            if any(v is not None for v in nums):
                leaked.append(f"{name}/{p['projection_id']}")
    check("no withheld projection carries any number", not leaked, str(leaked))


# ---------------------------------------------------- 5. validator tamper set


def t_validator_rejects_tampering() -> None:
    print("\n[5] the validator rejects hand-assembled violations")
    g = golden()

    d = copy.deepcopy(g["missing_lineup"])
    p = next(p for p in d["projections"] if p["status"] == "withheld")
    p["point"] = 50.0
    rejects("withheld projection with a point value", d, "I5")

    d = copy.deepcopy(g["missing_lineup"])
    p = next(p for p in d["projections"] if p["status"] == "withheld")
    p["status"] = "served"
    p["point"] = 50.0
    p["uncertainty"] = {"sd": 1.0, "p10": 48.0, "p50": 50.0, "p90": 52.0}
    p["withheld_reasons"] = []
    rejects("served over a degraded input", d, "I4")

    d = copy.deepcopy(g["missing_lineup"])
    d["warnings"] = [w for w in d["warnings"] if w["scope"] != "input:lineup_report"]
    d["audit"]["n_blocking_warnings"] = sum(
        1 for w in d["warnings"] if w["severity"] == "blocking")
    rejects("degraded input with its warning removed", d, "I4")

    d = copy.deepcopy(g["missing_lineup"])
    for w in d["warnings"]:
        if w["scope"].startswith("projection:"):
            w["severity"] = "advisory"
    d["audit"]["n_blocking_warnings"] = sum(
        1 for w in d["warnings"] if w["severity"] == "blocking")
    rejects("withheld projection downgraded to advisory", d, "I5")

    d = copy.deepcopy(g["nominal"])
    d["audit"]["inputs_digest"] = "0" * 64
    rejects("tampered inputs digest", d, "I8")

    d = copy.deepcopy(g["nominal"])
    d["inputs"][0]["sha256"] = "f" * 64
    rejects("tampered input hash breaks the digest", d, "I8")

    d = copy.deepcopy(g["nominal"])
    d["audit"]["epistemic_status"] = "production ready"
    rejects("altered epistemic status", d, "I8")

    d = copy.deepcopy(g["nominal"])
    d["inputs"][0]["freshness"] = "stale"
    rejects("freshness flipped without the degraded flag", d, "I3")

    d = copy.deepcopy(g["nominal"])
    d["inputs"][0]["freshness"] = "probably_ok"
    rejects("freshness outside the vocabulary", d, "I3")

    d = copy.deepcopy(g["nominal"])
    p = d["projections"][1]
    p["market"]["edge_vs_line"] = 2.0
    rejects("edge computed against an unavailable market", d, "I9")

    d = copy.deepcopy(g["nominal"])
    d["projections"][0]["point"] = float("nan")
    rejects("non-finite point", d, "I6")

    d = copy.deepcopy(g["nominal"])
    d["projections"][0]["uncertainty"]["p90"] = None
    rejects("served projection with incomplete uncertainty", d, "I6")

    d = copy.deepcopy(g["nominal"])
    d["model"]["artifact_sha256"] = {}
    rejects("model with no artifact hashes", d, "I2")

    d = copy.deepcopy(g["nominal"])
    d["model"]["artifact_sha256"]["exposure_artifact"] = "not-a-hash"
    rejects("malformed artifact hash", d, "I2")

    d = copy.deepcopy(g["nominal"])
    d["model"]["promotion_status"] = "promoted"
    rejects("promotion status outside the vocabulary", d, "I2")

    d = copy.deepcopy(g["nominal"])
    d["schema_version"] = "2.0.0"
    rejects("incompatible major version", d, "I1")

    d = copy.deepcopy(g["nominal"])
    d["projections"][0]["depends_on"] = ["a_source_not_in_the_ledger"]
    rejects("dependency absent from the input ledger", d, "I4")

    d = copy.deepcopy(g["nominal"])
    d["projections"][0]["components"][0]["name"] = "team_minutes_lag1"
    rejects("prohibited prediction-path term in a component", d, "I7")

    d = copy.deepcopy(g["nominal"])
    d["audit"]["n_projections_served"] = 99
    rejects("audit counts disagreeing with the body", d, "I8")

    d = copy.deepcopy(g["nominal"])
    del d["warnings"]
    rejects("missing top-level block", d, "missing required key")

    d = copy.deepcopy(g["nominal"])
    d["surprise"] = 1
    rejects("unknown top-level key", d, "unknown key")


# --------------------------------------------- 6. prediction-path prohibition


def t_prohibited_terms() -> None:
    print("\n[6] prediction-path prohibition, enforced at this call site")
    pos = ["game_minutes", "home.game_minutes", "team_minutes_lag1",
           "is_overtime", "n_overtime_periods_prior", "realized_duration_sec",
           "regulation_seconds_remaining"]
    for n in pos:
        check(f"flags {n!r}", bool(S.prohibited_terms_in(n)))
    neg = ["team_trailing_window", "rotation_share_prior", "league_prior",
           "opponent_adjustment", "availability_probability",
           "team_exposure_offset", "possessions_per_game_prior"]
    for n in neg:
        check(f"allows {n!r}", not S.prohibited_terms_in(n))

    try:
        BF.build_response(
            response_id="X", generated_at_utc="2026-08-05T20:50:00Z",
            request=BF.REQUEST, game=BF.GAME, model=BF.MODEL_ALPHA,
            inputs=BF.base_inputs(),
            projections=[
                S.ProjectionSpec(
                    projection_id="bad", subject_type="team",
                    subject_id="T", team_id="T",
                    target="REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                    unit="possessions", point=80.0,
                    uncertainty={"sd": 1.0, "p10": 79.0, "p50": 80.0, "p90": 81.0},
                    components=[S.Component("game_minutes", "adjustment", 1.0, "min")],
                    depends_on=["team_history"],
                )
            ],
            code_version="t", fixture_mode=True)
    except S.SchemaViolation as exc:
        check("builder refuses to serialise a prohibited component",
              "game_minutes" in str(exc))
    else:
        check("builder refuses to serialise a prohibited component", False,
              "builder ACCEPTED it")

    # The shared feature gate carries no name-based prohibition list; this is a
    # measured statement about the repository, not an assumption.
    fg = (PROGRAM / "feature_gate.py")
    if fg.exists():
        text = fg.read_text(encoding="utf-8")
        check("feature_gate.py carries no name-based prohibition list "
              "(so call-site enforcement here is necessary, not redundant)",
              "game_minutes" not in text and "PROHIBIT" not in text)
    else:
        skip("feature_gate.py inspection", "file absent")


# ------------------------------------------------ 7. determinism and fixtures


def t_fixtures_are_deterministic_and_valid() -> None:
    print("\n[7] fixtures rebuild deterministically and validate")
    g = golden()
    check("all expected scenarios present",
          set(g) == set(BF.scenarios()), str(sorted(set(g) ^ set(BF.scenarios()))))
    for name, kwargs in BF.scenarios().items():
        rebuilt = BF.build_response(**kwargs)
        on_disk = g[name]
        check(f"{name}: rebuild is byte-identical", rebuilt == on_disk)
        try:
            S.validate_response(on_disk)
            check(f"{name}: golden response validates", True)
        except S.SchemaViolation as exc:
            check(f"{name}: golden response validates", False, str(exc))
    for p in sorted((HERE / "fixtures" / "responses").glob("*.json")):
        try:
            S.load_and_validate(str(p))
            check(f"load_and_validate {p.name}", True)
        except S.SchemaViolation as exc:
            check(f"load_and_validate {p.name}", False, str(exc))


# ---------------------------------------------------- 8. freshness derivation


def t_freshness_derivation() -> None:
    print("\n[8] freshness is derived, not declared")
    base = dict(input_id="x", source="s", sha256="a" * 64,
                as_of_utc="2026-08-05T19:00:00Z",
                observed_at_utc="2026-08-05T19:00:00Z",
                age_seconds=10.0, max_age_seconds=100.0, job_status="ok")
    check("within bound is fresh", S.InputRecord(**base).freshness() == "fresh")
    r = S.InputRecord(**{**base, "age_seconds": 1000.0})
    check("beyond bound is stale", r.freshness() == "stale")
    check("stale is degraded", r.is_degraded())
    r = S.InputRecord(**{**base, "sha256": None, "as_of_utc": None})
    check("no bytes and no as-of is missing", r.freshness() == "missing")
    r = S.InputRecord(**{**base, "age_seconds": None,
                         "declared_freshness": "fresh"})
    check("an explicit declaration is honoured only when age is unmeasurable",
          r.freshness() == "fresh")
    r = S.InputRecord(**{**base, "age_seconds": None, "max_age_seconds": None})
    check("unmeasurable age with no declaration is missing, not fresh",
          r.freshness() == "missing")
    r = S.InputRecord(**{**base, "job_status": "failed"})
    check("a fresh file from a failed job is still degraded", r.is_degraded())
    r = S.InputRecord(**{**base, "job_status": "not_run"})
    check("a job that never ran is degraded", r.is_degraded())


# --------------------------------------------------------- 9. lane hygiene


def t_lane_hygiene() -> None:
    print("\n[9] lane hygiene")
    own = sorted(p for p in HERE.rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts)
    offenders = []
    for p in own:
        # Executable and data files must not reach for the forbidden path at
        # all.  Prose may NAME it -- REPORT.md has to be able to say the path
        # was not read -- so only code and fixtures are scanned.
        if p.suffix not in (".py", ".json"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if "SEALED_RESULTS" in text and p.name != "TESTS.py":
            offenders.append(str(p.relative_to(HERE)))
    check("no code or fixture file references the forbidden sealed-results path",
          not offenders, str(offenders))
    check("outputs live only under this node directory",
          all(HERE in p.parents or p.parent == HERE for p in own))
    check("REPORT.md exists", (HERE / "REPORT.md").exists())
    check("SCHEMA.md exists", (HERE / "SCHEMA.md").exists())
    check("JSON Schema exists", (HERE / "prediction_response.schema.json").exists())
    check("invariant list is complete", len(S.INVARIANTS) == 10, str(S.INVARIANTS))


def main() -> int:
    print("U10_PREDICTION_API_SCHEMA -- TESTS")
    print("=" * 72)
    t_envelope_and_versioning()
    t_model_agnosticism()
    t_required_contents()
    t_absence_is_a_warning()
    t_validator_rejects_tampering()
    t_prohibited_terms()
    t_fixtures_are_deterministic_and_valid()
    t_freshness_derivation()
    t_lane_hygiene()
    print("\n" + "=" * 72)
    print(f"{CHECKS} checks run")
    if SKIPS:
        print(f"{len(SKIPS)} skipped:")
        for s in SKIPS:
            print(f"  - {s}")
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
