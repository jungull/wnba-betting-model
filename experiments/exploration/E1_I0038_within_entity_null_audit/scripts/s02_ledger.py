"""S02 -- read the decision ledger; find every decision that turns on a null scheme,
and every ruling that constrains this audit (D097 D101 D103 D108 D111 D113 D087)."""
import os, json
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
LED = os.path.join(ROOT, "experiments", "player_program", "orchestration",
                   "DECISION_LEDGER.jsonl")

rows = []
with open(LED, encoding="utf-8") as f:
    for i, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception as e:
            print("PARSE FAIL line", i, e)
print("ledger entries:", len(rows))
keys = {}
for r in rows:
    for k in r:
        keys[k] = keys.get(k, 0) + 1
print("\nkeys:", json.dumps(keys, indent=1))

d = pd.DataFrame(rows)
idc = [c for c in d.columns if c.lower() in ("id", "decision_id", "did", "decision")]
print("\nid-ish cols:", idc)
print(d.head(2).to_string()[:3000])

out = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# full dump for grep
with open(os.path.join(out, "scripts", "_ledger_dump.txt"), "w", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(r, indent=1, ensure_ascii=False) + "\n" + "-" * 90 + "\n")
print("\nwrote _ledger_dump.txt")
