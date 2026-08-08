import json
import os

OUT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0027_reference_ladder"
sel = json.load(open(os.path.join(OUT, "_ledger_extract.json"), encoding="utf-8"))
d = os.path.join(OUT, "_ledger_txt")
os.makedirs(d, exist_ok=True)
for o in sel:
    did = o["decision_id"].split("_")[0]
    with open(os.path.join(d, did + ".txt"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(o, indent=1, default=str))
    print(did, os.path.getsize(os.path.join(d, did + ".txt")))
