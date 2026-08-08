"""E1_I0027 s00 -- READ-ONLY: pull the decision-ledger entries this screen must re-price.

Writes nothing outside E1_I0027_reference_ladder/.  Opens DECISION_LEDGER.jsonl in read mode only.
"""
import json
import os
import re

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
LEDGER = os.path.join(ROOT, r"experiments\player_program\orchestration\DECISION_LEDGER.jsonl")
OUT = os.path.join(ROOT, r"experiments\exploration\E1_I0027_reference_ladder")

WANT = ["D069", "D072", "D074", "D076", "D079", "D081", "D089", "D090", "D091",
        "D092", "D093", "D094", "D095", "D096", "D097", "D098", "D099", "D100", "D101"]

rows = []
with open(LEDGER, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        rows.append(o)

print("total ledger rows: %d" % len(rows))
if rows:
    print("keys of first row: %s" % sorted(rows[0].keys()))

# find the id field
idfields = [k for k in rows[0].keys() if "id" in k.lower()]
print("id-like fields: %s" % idfields)

def rowid(o):
    for k in ("decision_id", "id", "did", "key", "node_id"):
        if k in o and isinstance(o[k], str):
            return o[k]
    return None

ids = [rowid(o) for o in rows]
print("ALL decision ids (%d):" % len(ids))
for i in ids:
    print("   " + str(i))

sel = [o for o in rows if rowid(o) and rowid(o).split("_")[0] in WANT]
print("selected %d rows" % len(sel))
with open(os.path.join(OUT, "_ledger_extract.json"), "w", encoding="utf-8") as fh:
    json.dump(sel, fh, indent=1, default=str)
for o in sel:
    print("\n" + "=" * 100)
    print(json.dumps(o, indent=1, default=str)[:6000])
