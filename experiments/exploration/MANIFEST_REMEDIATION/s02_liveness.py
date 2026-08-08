import json, os, collections, io

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
ORCH = os.path.join(ROOT, "experiments", "player_program", "orchestration")
OUT = os.path.join(ROOT, "experiments", "exploration", "MANIFEST_REMEDIATION")

gs = json.load(open(os.path.join(ORCH, "GRAPH_STATE.json"), encoding="utf-8"))
print("GRAPH_STATE top keys:", list(gs.keys()))
print(json.dumps(gs, indent=1)[:4000])

print("\n=== ARTIFACT_LEDGER sample ===")
for i, line in enumerate(open(os.path.join(ORCH, "ARTIFACT_LEDGER.jsonl"), encoding="utf-8")):
    if i < 3:
        print(line[:800])
print("ledger lines:", i + 1)

pg = json.load(open(os.path.join(ORCH, "PROGRAM_GRAPH.json"), encoding="utf-8"))
print("\nPROGRAM_GRAPH top keys:", list(pg.keys()) if isinstance(pg, dict) else type(pg))
if isinstance(pg, dict):
    for k, v in pg.items():
        print("  ", k, type(v).__name__, (len(v) if hasattr(v, "__len__") else ""))
