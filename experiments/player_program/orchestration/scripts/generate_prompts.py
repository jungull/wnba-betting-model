#!/usr/bin/env python
"""Generate one prompt file per node, derived from the node's own contract.

Prompts are GENERATED, not hand-written, so that what an agent is told and what its output
will be validated against cannot drift apart: both come from the same node definition. The
generated file is the auditable record of the brief -- it is committed alongside the output.

    generate_prompts.py [--only NODE_ID ...]
"""

from __future__ import annotations

import argparse
import sys

import graph_lib as G

PREAMBLE = """\
# {nid} — {title}

**Lane:** {lane}  |  **Type:** {ntype}  |  **Severity on failure:** {sev}  |  **Role:** {role}

> This file is GENERATED from the node's contract in `PROGRAM_GRAPH.json`. It is the auditable
> record of exactly what this node's agent was told. Do not edit it by hand.

---

## Standing rules — these override any instinct to be helpful

1. **Frozen bytes govern over prose.** Where a document and an artifact hash disagree, the hash
   wins. Never silently reconcile a contradiction — report it.
2. **You may write ONLY inside your declared write scope** (below). An agent may not broaden its
   own write scope. Writing outside it fails the node at integration.
3. **Do not modify any frozen artifact.** In particular: `feature_gate.py`, `comparison_gate.py`,
   `gate_invocation.py`, `receipt_integrity.py`, the arm registry, `PROGRAM_STATE.json`, the
   Stage 2A evidence packets and hypothesis files, anything under the canonical `*_v1`/`*_v2`
   artifact directories, and anything constituting Arm D (`D_ewma_shrunk`). Enforcement belongs at
   the **call site** — if a check is missing, write a task-specific wrapper, never edit a shared gate.
4. **Do not run git.** Write files. The coordinator makes the task-scoped commit after validating
   your output. This is how concurrent nodes avoid contending for the git index.
5. **You do not mark your own work accepted.** A separate verifier context validates it. Report
   what you found, including what you could not establish.
6. **Measure, do not assert.** Every number in your output must come from code you actually ran
   against the actual artifact. If you could not measure something, say so explicitly and say why.
   A plausible-sounding figure you did not compute is a defect, not a contribution.
7. **Preserve nulls and negative results.** "This mechanism does not exist in the data" is a
   finding. Do not manufacture a positive.
8. **No performance peeking.** You may run unit, synthetic, identity and schema tests. You may NOT
   inspect comparative historical performance of any challenger, and you may not read anything
   under `experiments/player_program/stage2b/SEALED_RESULTS/`.

## Epistemic status of your output

{epistemic}

Write this verbatim into your report. It bounds what your output may later be cited for.

---

## Scientific state you are working inside

* **Incumbent, frozen:** `D_ewma_shrunk`, K=200, α=0.1, operational team MAE ≈ 2.9675, intrinsic
  ≈ 2.896. No challenger has been promoted. Do not retune or alter it.
* **Primary target, settled:** `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`. Realized
  duration may normalize a *completed-game historical outcome* only. Current-game realized
  overtime, `game_minutes`, duration, overtime periods, and any exact or approximate same-game
  surrogate for those are **prohibited from the prediction path**.
* **Universe:** 2,982 team-game rows over 1,491 game clusters. Report both. Games must never be
  split across folds or cluster-bootstrap draws.
* **Controls:** `K0_FLAT` is diagnostic only. `K0_MATCHED` is authoritative and is **per-arm**.
* **Downstream:** the operational scorer pairs regulation-equivalent projected exposure with raw
  full-game turnovers. This mismatch is documented and the scorer is **frozen**. Possession
  candidates are selected on the primary possession target first; downstream turnover results are
  secondary and may never rescue a candidate that fails or worsens the primary target.
* **The V2 halt carries NINE findings, S1–S9.** S8 and S9 were raised by the estimator source that
  returned after the halt was declared. Read `stage2a/V2_STOP_CONDITION.json` for all nine.

---

## Your mandate

{mandate}

## Acceptance criteria — your output is validated against exactly these

{criteria}

## Stop conditions — HALT and report rather than resolving these yourself

{stops}

---

## Scope

**Read:** {reads}

**Write (nothing outside this):** {writes}

**Forbidden inputs:** {forbidden}

**Required outputs:**

{outputs}

## Validation that will be run against your output

{validators}

---

## Report format

Write `REPORT.md` as prose a scientist can audit, and the machine-readable file as structured
data. The report must contain:

* the epistemic-status line above, verbatim;
* what you measured, with the exact command or script that produced each number;
* what you could **not** establish, and why;
* every contradiction you found between documents, or between a document and the bytes;
* anything you believe trips a stop condition, stated plainly rather than worked around.

Do not narrate routine commands or transient debugging. Report the consequential facts.
"""


def render(n):
    def bullets(items, empty="_None declared._"):
        return "\n".join(f"* {i}" for i in items) if items else empty

    mandate = n.get("_mandate") or (
        f"**{n['title']}**\n\nDeliver exactly this, to the standard the acceptance criteria below "
        f"describe. The criteria are not a summary of the mandate — they *are* the mandate."
    )
    return PREAMBLE.format(
        nid=n["id"], title=n["title"], lane=n["lane"], ntype=n["type"],
        sev=n["severity_on_failure"], role=n["agent_role"],
        epistemic=n["epistemic_status"], mandate=mandate,
        criteria=bullets(n["acceptance_criteria"]),
        stops=bullets(n["stop_conditions"]),
        reads=", ".join(f"`{p}`" for p in n["allowed_read_paths"]) or "_unrestricted read_",
        writes=", ".join(f"`{p}`" for p in n["allowed_write_paths"]),
        forbidden=", ".join(f"`{p}`" for p in n["forbidden_inputs"]) or "_none_",
        outputs=bullets([f"`{o}`" for o in n["expected_outputs"]]),
        validators=bullets([f"`{v}`" for v in n["validation_commands"]],
                           "_No automated validator; a verifier context reviews the output._"),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    graph = G.load_graph()
    written = 0
    for n in graph["nodes"]:
        if args.only and n["id"] not in args.only:
            continue
        path = G.REPO / n["agent_prompt_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(n))
        written += 1
    print(f"wrote {written} prompt file(s) to {G.ORCH.relative_to(G.REPO)}/prompts/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
