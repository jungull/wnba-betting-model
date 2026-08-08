import json, io, os, sys

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
LED = os.path.join(ROOT, "experiments", "player_program", "orchestration", "DECISION_LEDGER.jsonl")
OUT = os.path.join(ROOT, "experiments", "exploration", "E1_I0036_level_artefact_sweep", "scripts", "_ledger_dump.txt")

recs = [json.loads(l) for l in io.open(LED, encoding="utf-8") if l.strip()]
print("n_records", len(recs))
with io.open(OUT, "w", encoding="utf-8") as f:
    for r in recs:
        f.write("=" * 110 + "\n" + r["decision_id"] + "  ts=" + str(r.get("ts", "")) + "\n")
        f.write("Q: " + str(r.get("question", "")) + "\n--- RULING ---\n" + str(r.get("ruling", "")) + "\n")
print("wrote", OUT, os.path.getsize(OUT), "bytes")

want = sys.argv[1:] if len(sys.argv) > 1 else []
for r in recs:
    if any(r["decision_id"].startswith(w) for w in want):
        print("=" * 110)
        print(r["decision_id"])
        print("Q:", r.get("question", ""))
        print("--- RULING ---")
        print(r.get("ruling", ""))
