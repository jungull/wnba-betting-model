"""E1_I0034 step 0: pull the decisions that BIND this screen out of the programme ledger.

Read-only.  Writes _ledger_extract.json inside this screen's own directory only.
"""
import json, os

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
LED = os.path.join(ROOT, "experiments", "player_program", "orchestration", "DECISION_LEDGER.jsonl")
OUT = os.path.join(ROOT, "experiments", "exploration", "E1_I0034_redistribution",
                   "_ledger_extract.json")

WANT = {"D076", "D087", "D090", "D091", "D092", "D101", "D103", "D104",
        "D107", "D108", "D111"}

rows = []
with open(LED, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception as e:
            print("PARSE FAIL", i, e)

print("n ledger rows", len(rows))
print("keys of first:", sorted(rows[0].keys()))


def getid(o):
    for k in ("decision_id", "id", "did", "decision"):
        v = o.get(k)
        if isinstance(v, str):
            return v
    return None


ids = [getid(o) for o in rows]
print("last 8 ids:", ids[-8:])

sel = {}
for o in rows:
    d = getid(o)
    if d and d.split("_")[0] in WANT:
        sel.setdefault(d, []).append(o)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"n_rows": len(rows), "selected": sel}, f, indent=1, default=str)
print("selected:", {k: len(v) for k, v in sel.items()})
print("wrote", OUT)
