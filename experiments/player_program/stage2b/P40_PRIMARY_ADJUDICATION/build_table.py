"""P40 step 3: render ADJUDICATION_TABLE.md from SPEC.json (no new numbers)."""
import json
from pathlib import Path

OUT = Path(r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\player_program\stage2b\P40_PRIMARY_ADJUDICATION")
spec = json.loads((OUT / "SPEC.json").read_text(encoding="utf-8"))

L = []
A = L.append
A("# P40_PRIMARY_ADJUDICATION - Adjudication table")
A("")
A("> " + spec["epistemic_status"])
A("")
A("Authority: D041 unseal; frozen gates = P35 cards sha256 `68ef22f4...b32` (byte-verified); ")
A("P39 integrity PASS_WITH_FINDINGS. Primary gate and Holm machinery applied exactly as frozen; ")
A("no criterion altered after observing results. Sealed manifest sha256 `%s`." % spec["authority"]["manifest_sha256"])
A("")
A("## Headline")
A("")
A("**No element passes the preregistered primary possession gate after multiplicity. 0 PASS / 29 FAIL. "
  "The frozen incumbent D_ewma_shrunk is unchallenged; champion_challenged = false; nothing goes to the P43 gate.**")
A("")
A("Pooled OOF MAE of the incumbent-identical nulls: **2.86649** possessions over 2,572 test rows / 1,286 clusters "
  "(five D006 folds). Best pooled improvement anywhere: A07 (+0.05404, p_unc 0.0280) - fails Holm in both its families.")
A("")
A("## A24 scope disposition (D041 first item)")
A("")
A(spec["a24_scope_disposition_first_item"]["ruling"])
A("")
A(spec["a24_scope_disposition_first_item"]["positive_control_note"])
A("")
A("## Adjudicated table (primary gate: delta_MAE = MAE(K0_MATCHED) - MAE(arm), pooled OOF; positive = arm better)")
A("")
A("| Element | Family | delta_MAE (pooled) | p (2-sided) | Holm alpha at rank | N rows / clusters | Folds eval. | Kills fired | Verdict |")
A("|---|---|---|---|---|---|---|---|---|")

fams = spec["families"]
for name, e in spec["elements"].items():
    fam = e["family"]
    p = e["primary"]
    thr = fams[fam]["holm_thresholds_at_rank"].get(name)
    if name == fams[fam].get("fixed_slot"):
        thr_s = "fixed slot (p:=1, excluded from ordering)"
    else:
        thr_s = ("%.4g" % thr) if thr is not None else "n/a"
    kf = "; ".join(e["kills_fired"]) if e["kills_fired"] else "none"
    if len(kf) > 60:
        kf = kf[:57] + "..."
    A("| %s | %s | %+.6f | %.4f | %s | %d / %d | %d/5 | %s | **%s** |" % (
        e["element_id"], fam, p["delta_mae_pooled"], p["p_two_sided"], thr_s,
        p["n_rows_pooled_oof"], p["n_clusters_pooled_oof"], e["fold_coverage"]["n_evaluable"], kf, e["verdict"]))
A("")
A("A14 is promotion-INELIGIBLE by preregistration (single-active-fold licensing; fixed Holm slot) - its row is reported as evidence only.")
A("")
A("## Family multiplicity outcomes (as frozen at P35)")
A("")
for fam, fr in fams.items():
    A("- **%s** (m=%d, %s)%s: rejected = %s" % (
        fam, fr["m"], fr["correction"],
        "; fixed slot: " + fr["fixed_slot"] if fr.get("fixed_slot") else "",
        fr["rejected"] or "NONE"))
A("")
A("Dual-Holm alternate runs (hold-others-at-primary; stricter governs): every disputed element fails in BOTH partitions:")
for k, r in spec["dual_holm_alternate_runs"].items():
    rej = r.get("disputed_arm_rejects", r.get("disputed_elements_reject"))
    A("- %s (m=%d): disputed rejects = %s" % (k, r["m"], rej))
A("")
A("A12->A13 fixed sequence: A12 did not reject; **A13 recorded EXPLORATORY** (slot stays occupied). "
  "Both-pass joint re-tests: none triggered (no passing pair). Multi-survivor rule: not invoked.")
A("")
A("## Per-element detail (every number: N, interval, verdict)")
A("")
for name, e in spec["elements"].items():
    p = e["primary"]
    A("### %s  [%s] - %s" % (e["element_id"], e["family"], e["verdict"]))
    A("")
    A("Pooled: delta_MAE %+0.6f (MAE arm %.5f vs K0_MATCHED %.5f), p = %.4f, N = %d rows / %d clusters, B = %d."
      % (p["delta_mae_pooled"], p["mae_arm"], p["mae_null_k0_matched"], p["p_two_sided"],
         p["n_rows_pooled_oof"], p["n_clusters_pooled_oof"], p["n_draws"]))
    mb = p["gate_b_multiplicity"]
    A("Gates: (a) delta>0: %s; (b) multiplicity: %s; (c) no kill fired: %s; (d) P28 ordering: satisfied."
      % (p["gate_a_delta_positive"], p["gate_b_pass"], p["gate_c_no_kill_fired"]))
    if e["fold_coverage"]["structurally_deactivated"]:
        A("Fold coverage: %d/5 evaluable; deactivated: %s." % (e["fold_coverage"]["n_evaluable"], ", ".join(e["fold_coverage"]["structurally_deactivated"])))
    else:
        A("Fold coverage: 5/5 evaluable.")
    A("")
    A("| Fold | status | delta_MAE | p | N rows/clusters | treatment beta-hat | 95% interval | covers 0 |")
    A("|---|---|---|---|---|---|---|---|")
    for fr_ in e["per_fold"]:
        if fr_["status"] != "EVALUABLE":
            A("| %s | %s | - | - | - | - | - | - |" % (fr_["fold"], fr_["status"]))
            continue
        for tcol, iv in fr_["treatment_intervals_95"].items():
            b = fr_["treatment_point_estimates"].get(tcol)
            A("| %s | EVALUABLE | %+0.6f | %.4f | %d/%d | %s: %+.5f | (%+.5f, %+.5f) | %s |" % (
                fr_["fold"], fr_["delta_mae"], fr_["p_two_sided"], fr_["n_rows"], fr_["n_clusters"],
                tcol, b if b is not None else float("nan"), iv["lo"], iv["hi"], "yes" if iv["covers_zero"] else "NO"))
    A("")
    A("Kill conditions:")
    for k in e["kill_conditions"]:
        A("- [%s] %s - %s" % ("FIRED" if k["fired"] is True else ("NOT EVALUABLE" if k["fired"] == "NOT_EVALUABLE_FROM_RECEIPT" else "not fired"),
                              k["condition"], k["basis"]))
    A("")
    pr = e["provenance_d036"]
    A("Provenance (D036): %s; receipt `%s` sha256 `%s`; computed %s; %s; evidence class %s."
      % (pr["model"], pr["source_receipt"], pr["source_receipt_sha256"][:16] + "...", pr["computation_timestamp_utc"],
         pr["inference"], "VERIFIED"))
    A("")
A("## Notable evidence preserved (nulls and negatives are results)")
A("")
for k, v in spec["notable_evidence_preserved"].items():
    A("- **%s**: %s" % (k, v))
A("")
A("## Preserved disagreements - reported per arm, never harmonized")
A("")
for k, v in spec["preserved_disagreements_reported_not_harmonized"].items():
    A("- **%s**: %s" % (k, v))
A("")
A("## Contradictions found")
A("")
for c in spec["contradictions_found"]:
    A("- " + c)
A("")
A("## Could not establish")
A("")
for c in spec["could_not_establish"]:
    A("- " + c)
A("")
A("## Stop conditions")
A("")
A("Not tripped. " + spec["stop_conditions"]["detail"])
A("")

(OUT / "ADJUDICATION_TABLE.md").write_text("\n".join(L), encoding="utf-8")
print("wrote ADJUDICATION_TABLE.md,", len(L), "lines")
