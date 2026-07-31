"""Assemble the complete feature inventory: catalog x implemented x tested x result."""
import json
import re
from pathlib import Path
import pandas as pd

REPO = Path(r"C:\Users\jgallagher\wnba-betting-model")

# --- what was implemented (from the features package CANDIDATES lists) ---
impl = []
for f in sorted((REPO / "features").glob("*.py")):
    txt = f.read_text(encoding="utf-8")
    for m in re.finditer(r'Candidate\(\s*(\d+)\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"', txt):
        impl.append({"num": int(m.group(1)), "impl_name": m.group(2),
                     "family": m.group(3), "module": f.name})
impl = pd.DataFrame(impl).drop_duplicates("num")
print(f"implemented candidates: {len(impl)}")

# --- results across all screening runs ---
frames = []
for path, run in [("experiments/feature_screen/screen_results.csv", "run1 pooled"),
                  ("experiments/feature_screen_run2/screen_results.csv", "run2 bios")]:
    p = REPO / path
    if p.exists():
        d = pd.read_csv(p)
        d["run"] = run
        frames.append(d)
res = pd.concat(frames, ignore_index=True)
print(f"pooled-screen test rows: {len(res)}")

# best result per candidate
agg = (res.sort_values("improvement", ascending=False)
       .groupby("catalog_number")
       .agg(name=("name", "first"), best_channel=("channel", "first"),
            best_improvement=("improvement", "first"),
            best_p=("p_value", "min"),
            any_survives=("survives", "max"),
            n_tests=("channel", "size"),
            run=("run", "first"))
       .reset_index())
agg["status"] = agg.apply(
    lambda r: "CONFIRMED" if r.any_survives else
    ("FLAGGED" if r.catalog_number in (87, 92) else "not confirmed"), axis=1)
print(agg.status.value_counts().to_dict())

full = impl.merge(agg, left_on="num", right_on="catalog_number", how="outer")
full["tested"] = full.catalog_number.notna()
full["implemented"] = full.num.notna()
out = REPO / "experiments" / "lab_manual_inventory.csv"
full.to_csv(out, index=False)
print(f"wrote {out}: {len(full)} rows | implemented {full.implemented.sum()} | "
      f"tested {full.tested.sum()}")

# --- registered experiments ---
regs = []
for line in open(REPO / "experiments" / "registry.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r.get("kind") == "experiment":
        regs.append({"id": r["experiment_id"], "regime": r["regime"],
                     "metric": r["primary_metric"], "at": r["registered_at"][:16]})
print(f"\nregistered experiments: {len(regs)}")
for r in regs:
    print(f"  {r['at']}  {r['id']:42s} regime {r['regime']}  {r['metric']}")

# --- confirmed list for the manual ---
conf = res[res.survives == True][["catalog_number", "name", "channel", "improvement",
                                  "alpha_chosen", "p_value", "q_value"]]
print(f"\nconfirmed feature-channel rows: {len(conf)}")
print(conf.sort_values("improvement", ascending=False).to_string())
