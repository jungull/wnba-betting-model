import json, sys, os, re

LED = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\player_program\orchestration\DECISION_LEDGER.jsonl"
OUT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0033_aggregation_level\_ledger_extract.json"

want = set(["D076","D091","D099","D101","D103","D104","D106","D107","D108"])
rows = []
allids = []
with open(LED, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception as e:
            print("PARSE FAIL line", i, e)
            continue
        rows.append(o)

print("n rows", len(rows))
print("keys of first:", sorted(rows[0].keys()))

def getid(o):
    for k in ("decision_id","id","did","decision"):
        if k in o and isinstance(o[k], str):
            return o[k]
    return None

ids = [getid(o) for o in rows]
print("sample ids:", ids[:10])
print("last ids:", ids[-6:])

sel = {}
for o in rows:
    d = getid(o)
    if d and d.split("_")[0] in want:
        sel.setdefault(d, []).append(o)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"n_rows": len(rows), "selected": sel}, f, indent=1, default=str)
print("selected:", {k: len(v) for k, v in sel.items()})
print("wrote", OUT)
