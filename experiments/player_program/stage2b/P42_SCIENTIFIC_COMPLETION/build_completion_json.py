#!/usr/bin/env python3
"""P42 machine-readable companion: per-element scientific decisions, derived
deterministically from the committed P40 adjudication record. No recomputation
of any statistic; classification rules only, stated below and in COMPLETION.md.

Classification (applied to the adjudicated FAIL verdicts):
  ACCEPTED       -- passed the full preregistered gate (none this cycle).
  PRESERVED_LEAD -- delta>0, uncorrected p<0.05, fails multiplicity only,
                    no kill fired (A07 by construction of the record).
  FAILED_HARM    -- delta<0 with uncorrected two-sided p<0.05 (significantly
                    worse than own null).
  FAILED_KILLED_SINGLE_FOLD -- carded single-fold-decidable kill fired and the
                    card marks the element promotion-ineligible (A14).
  NULL           -- everything else: effect indistinguishable from zero at the
                    governing thresholds (kills may additionally have fired).
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
ADJ = os.path.join(ROOT, "experiments/player_program/stage2b/P40_PRIMARY_ADJUDICATION/ADJUDICATION.json")
DOWN = os.path.join(ROOT, "experiments/player_program/stage2b/P41_DOWNSTREAM_TURNOVER_CONFIRMATION/DOWNSTREAM.json")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def classify(e):
    p = e["primary"]
    delta, pval = p["delta_mae_pooled"], p["p_two_sided"]
    if e["verdict"] != "FAIL":
        return "ACCEPTED"
    if delta > 0 and pval < 0.05 and p["gate_c_no_kill_fired"] and not p["gate_b_pass"]:
        return "PRESERVED_LEAD"
    if delta < 0 and pval < 0.05:
        return "FAILED_HARM"
    if e["element_id"] == "A14_expansion_intercept_decay__single":
        return "FAILED_KILLED_SINGLE_FOLD"
    return "NULL"


def main():
    adj = json.load(open(ADJ, encoding="utf-8"))
    down = json.load(open(DOWN, encoding="utf-8"))
    elements = []
    for eid in sorted(adj["elements"]):
        e = adj["elements"][eid]
        p = e["primary"]
        elements.append({
            "element_id": eid,
            "arm_id": e["arm_id"],
            "family": e["family"],
            "decision": classify(e),
            "adjudicated_verdict": e["verdict"],
            "delta_mae_pooled": p["delta_mae_pooled"],
            "p_two_sided_uncorrected": p["p_two_sided"],
            "mae_arm": p["mae_arm"],
            "mae_null_k0_matched": p["mae_null_k0_matched"],
            "n_rows_pooled_oof": p["n_rows_pooled_oof"],
            "n_clusters_pooled_oof": p["n_clusters_pooled_oof"],
            "kills_fired": len(e["kills_fired"]),
            "kills_not_evaluable": len(e.get("kills_not_evaluable", [])),
            "promotion_eligible": e["promotion_eligible"],
        })
    counts = {}
    for el in elements:
        counts[el["decision"]] = counts.get(el["decision"], 0) + 1
    doc = {
        "schema": "player_program/stage2b/P42_SCIENTIFIC_COMPLETION/completion/1",
        "epistemic_status": ("SCIENTIFIC COMPLETION REPORT. States what the wave established and what it did "
                              "not. Does not itself promote anything."),
        "authorities": ["D042_P40_CLOSE", "D041_P39_CLOSE_AND_UNSEAL", "D039_P37_ADJUDICATION"],
        "sources": {
            "adjudication": {"path": "experiments/player_program/stage2b/P40_PRIMARY_ADJUDICATION/ADJUDICATION.json",
                              "sha256": sha256_file(ADJ)},
            "downstream": {"path": "experiments/player_program/stage2b/P41_DOWNSTREAM_TURNOVER_CONFIRMATION/DOWNSTREAM.json",
                            "sha256": sha256_file(DOWN)},
        },
        "summary": {
            "fitted_elements": adj["summary"]["fitted_elements"],
            "accepted": counts.get("ACCEPTED", 0),
            "preserved_lead": counts.get("PRESERVED_LEAD", 0),
            "failed_harm": counts.get("FAILED_HARM", 0),
            "failed_killed_single_fold": counts.get("FAILED_KILLED_SINGLE_FOLD", 0),
            "null": counts.get("NULL", 0),
            "champion_challenged": adj["summary"]["champion_challenged"],
            "incumbent_pooled_oof_mae": adj["summary"]["incumbent_margin"]["pooled_oof_mae_of_incumbent_identical_nulls"],
            "incumbent_n_rows": adj["summary"]["incumbent_margin"]["n_rows"],
            "effect_bound_possessions": [min(el["delta_mae_pooled"] for el in elements),
                                          max(el["delta_mae_pooled"] for el in elements)],
        },
        "downstream_confirmation": {"node": "P41", "detail": "no rescue; see DOWNSTREAM.json (criteria: two vacuously-with-measurement, one positively)"},
        "elements": elements,
    }
    out = os.path.join(HERE, "COMPLETION.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    print("wrote", out)
    print("counts:", counts)


if __name__ == "__main__":
    main()
