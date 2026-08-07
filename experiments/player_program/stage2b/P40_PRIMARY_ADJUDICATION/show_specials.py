import json
from pathlib import Path

OUT = Path(r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\player_program\stage2b\P40_PRIMARY_ADJUDICATION")
ex = json.loads((OUT / "EXTRACTION.json").read_text(encoding="utf-8"))

def brief(o, n=1200):
    s = json.dumps(o)
    return s[:n] + ("..." if len(s) > n else "")

for name, e in ex["elements"].items():
    sp = e.get("special") or {}
    for k, v in sp.items():
        print(f"== {name} / {k} ==")
        print(brief(v, 2200))
        print()
    r = e.get("receipt")
    if r:
        # fold basis fields for deactivated folds - need raw receipt; extraction kept extra_keys only
        gp = r.get("guard_pins_all_match")
        if gp is not True:
            print(f"!! {name}: guard_pins_all_match={gp}")
        # guard summary problems
        for gk, gs in (r.get("guard_summary") or {}).items():
            for fk, fv in gs.items():
                probs = fv.get("problems") or fv.get("blocking")
                if probs:
                    print(f"!! {name} guard {gk}/{fk}: {probs}")
print("=== manifest raised findings ===")
print(brief(ex["manifest_meta"].get("raised_findings"), 3000))
print("=== manifest registry_amendment ===")
print(brief(ex["manifest_meta"].get("registry_amendment"), 1500))
print("=== manifest inference_pins ===")
print(brief(ex["manifest_meta"].get("inference_pins"), 1500))
