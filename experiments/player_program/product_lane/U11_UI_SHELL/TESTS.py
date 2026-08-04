#!/usr/bin/env python3
"""TESTS.py — validation for U11_UI_SHELL.

Asserts the three acceptance criteria of the node, behaviourally rather than by reading
the source and believing it:

  A. the UI runs entirely against fixtures or frozen outputs
  B. no possession challenger is hard-coded
  C. an absent or stale input renders as a warning, never as a number

The load-bearing tests are the sweeps: every numeric leaf of the nominal payload is
removed, nulled, made non-finite and made non-numeric in turn, and every blocker class is
applied in turn, and in each case the page is required to lose the number and gain a
warning. That is a property, not a spot check.

Run::

    python experiments/player_program/product_lane/U11_UI_SHELL/TESTS.py
"""
from __future__ import annotations

import ast
import builtins
import copy
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ui_shell  # noqa: E402

FIXTURES = HERE / "fixtures"
RENDERED = HERE / "rendered"
FAILED: list[str] = []


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILED.append(label)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def n_numbers(html: str) -> int:
    return html.count(ui_shell.NUMBER_MARKER)


def n_warnings(html: str) -> int:
    return html.count("<span class='badge'>WARNING</span>")


def game_section(html: str, game_id: str) -> str:
    """The slice of the page from one game's heading to the next heading."""
    start = html.find(f"<code>{game_id}</code>")
    if start < 0:
        return ""
    nxt = html.find("<h2>", start)
    return html[start:nxt if nxt > 0 else len(html)]


# ------------------------------------------------------ B. model-agnosticism
# Anything that would name a model, an arm or a challenger. Present in the program's
# scientific artifacts; must be absent from this product node's code AND fixtures.
FORBIDDEN_TOKENS = [
    "ewma", "shrunk", "D_ewma", "arm_registry", "K0_FLAT", "K0_MATCHED",
    "challenger", "incumbent", "champion", "arm_d", "possession_features",
    "projected_exposure", "turnover_p1", "turnover_p2", "stage2a", "stage2b",
    "SEALED_RESULTS", "alpha=0.1", "K=200", "2.9675", "2.896",
]

NODE_FILES = sorted(
    [p for p in HERE.rglob("*") if p.is_file() and p.suffix in {".py", ".json", ".html", ".md"}]
)


def test_no_model_or_challenger_is_hard_coded() -> None:
    src = (HERE / "ui_shell.py").read_text(encoding="utf-8")
    hits = [t for t in FORBIDDEN_TOKENS if t.lower() in src.lower()]
    check(not hits, f"ui_shell.py names no model/arm/challenger token (hits: {hits})")

    fx_hits: dict[str, list[str]] = {}
    for p in sorted(FIXTURES.glob("*.json")):
        text = p.read_text(encoding="utf-8").lower()
        h = [t for t in FORBIDDEN_TOKENS if t.lower() in text]
        if h:
            fx_hits[p.name] = h
    check(not fx_hits, f"no fixture names a model/arm/challenger token (hits: {fx_hits})")

    rend_hits: dict[str, list[str]] = {}
    for p in sorted(RENDERED.glob("*.html")):
        text = p.read_text(encoding="utf-8").lower()
        h = [t for t in FORBIDDEN_TOKENS if t.lower() in text]
        if h:
            rend_hits[p.name] = h
    check(not rend_hits, f"no rendered page names a model/arm/challenger token (hits: {rend_hits})")


def test_model_identity_is_payload_data() -> None:
    """Two payloads differing ONLY in model identity must render that difference."""
    a = load("F1_nominal.json")
    b = copy.deepcopy(a)
    b["model"]["version"] = "SOME-OTHER-FIXTURE-MODEL@9.9.9"
    b["model"]["artifact_sha256"] = {"other_table": "f" * 64}
    ha, hb = ui_shell.render_payload(a), ui_shell.render_payload(b)
    check(a["model"]["version"] in ha and "SOME-OTHER-FIXTURE-MODEL@9.9.9" in hb,
          "each payload's model version is rendered verbatim")
    check("SOME-OTHER-FIXTURE-MODEL@9.9.9" not in ha and a["model"]["version"] not in hb,
          "neither model version leaks into the other page")
    check(("f" * 64) in hb and ("f" * 64) not in ha,
          "artifact digests are rendered from the payload")
    check(n_numbers(ha) == n_numbers(hb),
          "swapping the producing model changes no projection cell (shell is model-agnostic)")


def test_no_scientific_or_network_imports() -> None:
    tree = ast.parse((HERE / "ui_shell.py").read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    allowed = {"__future__", "datetime", "html", "json", "math", "sys", "pathlib", "typing"}
    check(mods <= allowed, f"ui_shell.py imports only inert stdlib (imports: {sorted(mods)})")
    banned = {"urllib", "requests", "http", "socket", "pandas", "numpy", "pyarrow", "subprocess"}
    check(not (mods & banned), f"ui_shell.py imports nothing model-bearing or networked")


# --------------------------------------- A. fixtures / frozen outputs only
def test_render_touches_no_filesystem_and_is_deterministic() -> None:
    payload = load("F1_nominal.json")

    real_open, real_io_open = builtins.open, io.open
    real_read_text, real_path_open = Path.read_text, Path.open

    def boom(*a, **k):
        raise AssertionError("render_payload attempted filesystem access")

    builtins.open, io.open, Path.read_text, Path.open = boom, boom, boom, boom
    try:
        h1 = ui_shell.render_payload(payload)
        h2 = ui_shell.render_payload(payload)
        ok = True
    except AssertionError as e:
        ok, h1, h2 = False, "", str(e)
    finally:
        builtins.open, io.open = real_open, real_io_open
        Path.read_text, Path.open = real_read_text, real_path_open
    check(ok, "render_payload performs no filesystem access")
    check(bool(h1) and h1 == h2, "render_payload is deterministic for a fixed payload")


def test_every_fixture_declares_itself_a_fixture() -> None:
    names = sorted(p.name for p in FIXTURES.glob("*.json"))
    check(len(names) >= 6, f"fixture set present ({len(names)} fixtures)")
    bad = []
    for p in sorted(FIXTURES.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if (d.get("audit") or {}).get("source") != "FIXTURE":
            bad.append(p.name)
    check(not bad, f"every fixture declares audit.source == FIXTURE (bad: {bad})")

    refs = []
    for p in sorted(FIXTURES.glob("*.json")):
        t = p.read_text(encoding="utf-8")
        if ".parquet" in t or "experiments/" in t or "SEALED" in t:
            refs.append(p.name)
    check(not refs, f"no fixture references a repository artifact path (hits: {refs})")


def test_node_reads_nothing_forbidden() -> None:
    """No executable file or fixture may name the forbidden input. Prose is exempt:
    REPORT.md names the path in order to state that it was not read, and this test file
    names it in order to check for it."""
    exempt = {"TESTS.py", "REPORT.md", "VIEW_CONTRACT.md"}
    hits = [p.name for p in NODE_FILES
            if p.name not in exempt
            and "SEALED_RESULTS" in p.read_text(encoding="utf-8", errors="ignore")]
    check(not hits, f"no executable file or fixture references the forbidden input (hits: {hits})")


def test_rendered_pages_match_the_fixtures() -> None:
    stale = []
    for p in sorted(FIXTURES.glob("*.json")):
        want = ui_shell.render_payload(json.loads(p.read_text(encoding="utf-8")))
        got_path = RENDERED / (p.stem + ".html")
        if not got_path.exists() or got_path.read_text(encoding="utf-8") != want:
            stale.append(p.stem)
    check(not stale, f"committed rendered/*.html reproduce byte-identically (stale: {stale})")


# ------------------------------- C. absence and staleness render as warnings
def test_manifest_is_current() -> None:
    import make_manifest

    committed = json.loads((HERE / "MANIFEST.json").read_text(encoding="utf-8"))
    rebuilt = make_manifest.build()
    check(committed == rebuilt, "MANIFEST.json matches a fresh rebuild (digests and counts)")
    check(committed["epistemic_status"].startswith("PRODUCT SCAFFOLD built against fixtures"),
          "MANIFEST.json carries the node's epistemic status")


def test_nominal_actually_renders_numbers() -> None:
    """Without this, every suppression test below would pass vacuously."""
    h = ui_shell.render_payload(load("F1_nominal.json"))
    check(n_numbers(h) > 0, f"nominal fixture renders numbers ({n_numbers(h)} of them)")
    check(n_warnings(h) == 0, f"nominal fixture renders no warnings ({n_warnings(h)})")


def test_stale_input_suppresses_every_number() -> None:
    h = ui_shell.render_payload(load("F2_stale_input.json"))
    sec = game_section(h, "FIXTURE-G-0001")
    check(n_numbers(sec) == 0, f"stale input: no number anywhere in the game view ({n_numbers(sec)})")
    check("INPUT_STALE" in sec, "stale input: the reason code is shown")
    check("41.2" not in h and "40.5" not in h, "stale input: the payload's numbers do not leak")


def test_failed_job_suppresses_every_number() -> None:
    h = ui_shell.render_payload(load("F4_failed_job.json"))
    sec = game_section(h, "FIXTURE-G-0004")
    check(n_numbers(sec) == 0, f"failed job: no number in the game view ({n_numbers(sec)})")
    check("INPUT_FAILED" in sec, "failed job: the reason code is shown")


def test_missing_lineup_suppresses_only_the_dependent_game() -> None:
    h = ui_shell.render_payload(load("F3_missing_lineup.json"))
    blocked = game_section(h, "FIXTURE-G-0002")
    clean = game_section(h, "FIXTURE-G-0003")
    check(n_numbers(blocked) == 0, "missing lineup: dependent game shows no numbers")
    check("INPUT_MISSING" in blocked, "missing lineup: the reason code is shown")
    check(n_numbers(clean) > 0, "missing lineup: the game that does not require it is unaffected")
    check("18.400" not in clean and "18.500" not in clean and "INPUT_MISSING" in clean,
          "missing lineup: a ROW that declares the dependency is suppressed inside an otherwise fine game")


def test_unbound_output_suppresses_every_number() -> None:
    h = ui_shell.render_payload(load("F6_unbound_model.json"))
    check(n_numbers(h) == 0, f"unbound output: no number on the page ({n_numbers(h)})")
    check("OUTPUT_UNBOUND" in h, "unbound output: the reason code is shown")
    check("INPUT_UNDECLARED" in h, "an input required but absent from the ledger is a warning")
    check("MISSING" in h, "an input with no freshness claim fails closed to MISSING")


def test_value_level_absence_renders_warnings() -> None:
    h = ui_shell.render_payload(load("F5_absent_values.json"))
    check("VALUE_ABSENT" in h, "explicit null / absent key renders VALUE_ABSENT")
    check("VALUE_NOT_NUMERIC" in h, "a non-numeric value renders VALUE_NOT_NUMERIC")
    check("ROW_BLOCKED" in h, "an explicit row blocker renders ROW_BLOCKED")
    check("n/a" not in h.replace("VALUE_NOT_NUMERIC", ""), "the junk value itself is not printed as data")
    # 5 rows: only E-09's projection, interval and (absent) market are partially renderable.
    check(n_warnings(h) >= 8, f"every absent cell produced its own warning ({n_warnings(h)})")


def test_non_finite_values_never_render() -> None:
    for bad in (float("nan"), float("inf"), float("-inf")):
        p = load("F1_nominal.json")
        p["games"][0]["rows"][0]["projection"]["value"] = bad
        h = ui_shell.render_payload(p)
        low = h.lower()
        check("VALUE_NOT_FINITE" in h and "nan" not in low and "inf" not in low.replace("finite", ""),
              f"non-finite value {bad!r} renders as a warning and is not echoed anywhere")


# -------------------------------------------------------------- the sweeps
NUMERIC_PATHS = [
    ("games", 0, "rows", 0, "projection", "value"),
    ("games", 0, "rows", 0, "uncertainty", "lo"),
    ("games", 0, "rows", 0, "uncertainty", "hi"),
    ("games", 0, "rows", 0, "market", "line"),
    ("games", 0, "rows", 0, "components", 0, "contribution"),
    ("games", 0, "rows", 1, "projection", "value"),
    ("games", 0, "rows", 1, "uncertainty", "lo"),
    ("games", 0, "rows", 1, "market", "line"),
]


def _set(obj, path, value, delete=False):
    cur = obj
    for k in path[:-1]:
        cur = cur[k]
    if delete:
        if isinstance(cur, dict):
            cur.pop(path[-1], None)
        else:
            del cur[path[-1]]
    else:
        cur[path[-1]] = value


def test_sweep_every_numeric_leaf() -> None:
    base = load("F1_nominal.json")
    base_html = ui_shell.render_payload(base)
    base_n, base_w = n_numbers(base_html), n_warnings(base_html)
    problems = []
    for path in NUMERIC_PATHS:
        for label, mutate in (
            ("null", lambda p: _set(p, path, None)),
            ("deleted", lambda p: _set(p, path, None, delete=True)),
            ("nan", lambda p: _set(p, path, float("nan"))),
            ("string", lambda p: _set(p, path, "12.3")),
            ("bool", lambda p: _set(p, path, True)),
        ):
            p = copy.deepcopy(base)
            mutate(p)
            h = ui_shell.render_payload(p)
            if not (n_numbers(h) < base_n and n_warnings(h) > base_w):
                problems.append(f"{'.'.join(map(str, path))}/{label}")
    check(not problems,
          f"every numeric leaf, under 5 corruptions each ({len(NUMERIC_PATHS) * 5} cases), "
          f"loses its number and gains a warning (failures: {problems})")


BLOCKER_CASES = {
    "stale_input": lambda p: p["inputs"].__setitem__(2, dict(p["inputs"][2], captured_at="2026-08-01T00:00:00Z")),
    "missing_input": lambda p: p["inputs"].__setitem__(2, {"input_id": "rolling_features", "label": "x", "status": "missing"}),
    "failed_input": lambda p: p["inputs"].__setitem__(2, {"input_id": "rolling_features", "label": "x", "status": "failed"}),
    "no_inputs_at_all": lambda p: p.__setitem__("inputs", []),
    "input_ledger_absent": lambda p: p.pop("inputs", None),
    "no_model_version": lambda p: p["model"].__setitem__("version", None),
    "no_digests": lambda p: p["model"].__setitem__("artifact_sha256", {}),
    "model_block_absent": lambda p: p.pop("model", None),
    "as_of_absent": lambda p: p.pop("as_of", None),
    "as_of_unparseable": lambda p: p.__setitem__("as_of", "not-a-timestamp"),
    "freshness_claim_absent": lambda p: [i.pop("max_age_seconds", None) for i in p["inputs"]],
    "row_blocked": lambda p: p["games"][0]["rows"][0].__setitem__("row_blockers", ["blocked"]),
}


def test_sweep_every_blocker_class() -> None:
    problems = []
    for label, mutate in BLOCKER_CASES.items():
        p = load("F1_nominal.json")
        mutate(p)
        h = ui_shell.render_payload(p)
        sec = game_section(h, "FIXTURE-G-0001")
        if label == "row_blocked":
            ok = n_numbers(sec) > 0 and "ROW_BLOCKED" in sec  # scoped to one row only
        else:
            ok = n_numbers(sec) == 0 and n_warnings(sec) > 0
        if not ok:
            problems.append(label)
    check(not problems,
          f"every blocker class ({len(BLOCKER_CASES)} cases) suppresses the numbers it should "
          f"(failures: {problems})")


U10_RESPONSES = HERE.parent / "U10_PREDICTION_API_SCHEMA" / "fixtures" / "responses"


def test_optional_u10_adapter_is_advisory_only() -> None:
    """Never fails on U10's account. U10 was RUNNING when this node ran; if its shape
    changes or its files vanish, this test reports SKIP rather than failing U11."""
    import u10_adapter

    if not U10_RESPONSES.is_dir():
        print("  SKIP  no U10 response fixtures present (U10 was RUNNING; not a dependency)")
        return
    files = sorted(U10_RESPONSES.glob("*.json"))
    usable = []
    for f in files:
        try:
            resp = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not u10_adapter.looks_like_u10(resp):
            continue
        try:
            view = u10_adapter.adapt(resp)
            html = ui_shell.render_payload(view)
        except Exception as e:  # noqa: BLE001
            print(f"  SKIP  {f.name}: adapter/shell could not process it ({e!r})")
            continue
        usable.append((f.name, n_numbers(html), n_warnings(html)))
    if not usable:
        print("  SKIP  no U10 response fixture matched the adapter's expected shape")
        return
    for name, nums, warns in usable:
        print(f"  INFO  {name}: adapted -> {nums} number(s), {warns} warning(s)")
    degraded = [u for u in usable if "missing" in u[0] or "failed" in u[0] or "no_value" in u[0]]
    ok = all(w > 0 for _, _, w in degraded)
    check(ok or not degraded,
          "advisory: adapted U10 degraded responses render at least one warning each")


def test_malformed_payloads_do_not_crash_or_invent() -> None:
    cases = [None, [], "", 0, {}, {"schema": "wrong"}, {"schema": ui_shell.VIEW_SCHEMA, "games": [{}]}]
    problems = []
    for c in cases:
        try:
            h = ui_shell.render_payload(c)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{c!r} raised {e!r}")
            continue
        if ui_shell.EPISTEMIC_BANNER not in h:
            problems.append(f"{c!r} rendered without the banner")
        if n_numbers(h) != 0:
            problems.append(f"{c!r} invented {n_numbers(h)} number(s)")
    check(not problems, f"malformed payloads render warnings, never numbers (failures: {problems})")


def test_banner_is_not_payload_suppressible() -> None:
    p = load("F1_nominal.json")
    p["banner"] = ""
    p["title"] = "<script>alert(1)</script>"
    h = ui_shell.render_payload(p)
    check(ui_shell.EPISTEMIC_BANNER in h, "the epistemic banner is rendered unconditionally")
    check("<script>" not in h, "payload strings are escaped, not executed")


SAFE_PHRASES = [
    "must not imply a model has been promoted",
    "no model has been promoted",
    "nothing here asserts that any model has been promoted",
]
CLAIM_PHRASES = ["has been promoted", "is promoted", "promoted model", "production model", "live model"]


def test_page_never_claims_promotion() -> None:
    for p in sorted(FIXTURES.glob("*.json")):
        low = ui_shell.render_payload(json.loads(p.read_text(encoding="utf-8"))).lower()
        for safe in SAFE_PHRASES:
            low = low.replace(safe, " ")
        claims = [ph for ph in CLAIM_PHRASES if ph in low]
        check(not claims, f"{p.stem}: page makes no promotion claim (hits: {claims})")


def main() -> int:
    print("=" * 78)
    print("U11_UI_SHELL — validation")
    print("=" * 78)
    tests = [
        test_no_model_or_challenger_is_hard_coded,
        test_model_identity_is_payload_data,
        test_no_scientific_or_network_imports,
        test_render_touches_no_filesystem_and_is_deterministic,
        test_every_fixture_declares_itself_a_fixture,
        test_node_reads_nothing_forbidden,
        test_rendered_pages_match_the_fixtures,
        test_manifest_is_current,
        test_nominal_actually_renders_numbers,
        test_stale_input_suppresses_every_number,
        test_failed_job_suppresses_every_number,
        test_missing_lineup_suppresses_only_the_dependent_game,
        test_unbound_output_suppresses_every_number,
        test_value_level_absence_renders_warnings,
        test_non_finite_values_never_render,
        test_sweep_every_numeric_leaf,
        test_sweep_every_blocker_class,
        test_optional_u10_adapter_is_advisory_only,
        test_malformed_payloads_do_not_crash_or_invent,
        test_banner_is_not_payload_suppressible,
        test_page_never_claims_promotion,
    ]
    for fn in tests:
        print(f"\n--- {fn.__name__} ---")
        fn()
    print("\n" + "=" * 78)
    print("PASS — all checks green" if not FAILED else f"FAIL ({len(FAILED)}): {FAILED}")
    print("=" * 78)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
