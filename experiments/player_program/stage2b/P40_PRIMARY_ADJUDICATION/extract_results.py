"""P40_PRIMARY_ADJUDICATION - step 1: open sealed receipts and extract the
adjudication-relevant numbers with per-file sha256 provenance (D036).

Authorized by D041: P40 is the FIRST AND ONLY context permitted to open
stage2b/SEALED_RESULTS/P38/.

Writes EXTRACTION.json into the P40 write scope. No frozen artifact is modified.
"""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\player_program")
SEALED = ROOT / "stage2b" / "SEALED_RESULTS" / "P38"
OUT = ROOT / "stage2b" / "P40_PRIMARY_ADJUDICATION"
OUT.mkdir(parents=True, exist_ok=True)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


extraction = {"schema": "p40_extraction/1", "elements": {}, "special_records": {}}

for d in sorted(SEALED.iterdir()):
    if not d.is_dir():
        continue
    entry = {"dir": d.name, "files": {}}
    for f in sorted(d.iterdir()):
        entry["files"][f.name] = {"bytes": f.stat().st_size, "sha256": sha256_file(f)}
    rp = d / "receipt.json"
    if rp.exists():
        r = json.loads(rp.read_text(encoding="utf-8"))
        folds = {}
        for fb in r.get("folds", []):
            fid = fb["fold_id"]
            tr = fb.get("train_refit") or {}
            pf = fb.get("point_fits") or {}
            arm_pf = pf.get("arm") or {}
            null_pf = pf.get("null") or {}
            folds[fid] = {
                "status": fb.get("status"),
                "test": fb.get("test"),
                "arm_point_beta": arm_pf.get("beta"),
                "arm_point_columns": arm_pf.get("column_names"),
                "arm_converged": arm_pf.get("converged"),
                "null_converged": null_pf.get("converged"),
                "arm_intervals": tr.get("arm_intervals"),
                "n_na_draws": tr.get("n_na_draws"),
                "na_reasons": tr.get("na_reasons"),
                "extra_keys": sorted(set(fb.keys()) - {"fold_id", "k0_flat", "point_fits", "status", "test", "train_refit"}),
            }
        # capture any non-standard receipt sections (stratum diagnostics etc.)
        std = {"arm_id", "blinding", "code", "declared_family", "element_id", "enumeration_element",
               "environment", "folds", "guard_pins", "guard_records", "inputs", "manifest_digest",
               "recorded_utc", "results", "schema", "seeds"}
        extra_top = {k: r[k] for k in sorted(set(r.keys()) - std)}
        gr = r.get("guard_records", {})
        guard_summary = {}
        for gk, gv in gr.items():
            if isinstance(gv, dict):
                # summarize pass/fail across folds
                s = {}
                for fk, fv in gv.items():
                    if isinstance(fv, dict):
                        s[fk] = {kk: fv.get(kk) for kk in ("passed", "valid", "conformant", "verdict", "blocked", "problems", "blocking") if kk in fv}
                guard_summary[gk] = s
        entry["receipt"] = {
            "arm_id": r.get("arm_id"),
            "element_id": r.get("element_id"),
            "enumeration_element": r.get("enumeration_element"),
            "declared_family": r.get("declared_family"),
            "recorded_utc": r.get("recorded_utc"),
            "results": r.get("results"),
            "folds": folds,
            "guard_pins_all_match": (r.get("guard_pins") or {}).get("all_match"),
            "guard_summary": guard_summary,
            "extra_top_level": extra_top,
            "seeds_present": "seeds" in r,
            "guard_record_keys": sorted(gr.keys()),
        }
    # small special records
    for special in ("EXCLUSION_RECORD.json", "BLOCK_VERDICT.json", "FINAL_FITS_SUPERSESSION.json",
                    "D040_SUPERSESSION.json", "A24_REGISTRY_FALLBACK_SCOPE_RECORD.json",
                    "BLOCK_DIAGNOSTICS.json"):
        sp = d / special
        if sp.exists():
            try:
                entry.setdefault("special", {})[special] = json.loads(sp.read_text(encoding="utf-8"))
            except Exception as e:  # noqa
                entry.setdefault("special", {})[special] = {"error": str(e)}
    extraction["elements"][d.name] = entry

man = SEALED.parent / "MANIFEST.json"
extraction["manifest_sha256"] = sha256_file(man)
mj = json.loads(man.read_text(encoding="utf-8"))
extraction["manifest_meta"] = {k: mj.get(k) for k in ("schema", "node", "recorded_utc", "epistemic_status",
                                                      "row_universe", "folds", "registry_amendment",
                                                      "executor_mandates", "raised_findings", "inference_pins")}

out_path = OUT / "EXTRACTION.json"
out_path.write_text(json.dumps(extraction, indent=1, sort_keys=True), encoding="utf-8")
print("wrote", out_path, out_path.stat().st_size, "bytes")
print("element dirs:", len(extraction["elements"]))
for k, v in extraction["elements"].items():
    has_receipt = "receipt" in v
    specials = sorted((v.get("special") or {}).keys())
    print(f"  {k}: receipt={has_receipt} specials={specials}")
