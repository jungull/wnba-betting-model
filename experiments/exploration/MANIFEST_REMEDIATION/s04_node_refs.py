import json, os, re, collections

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
ORCH = os.path.join(ROOT, "experiments", "player_program", "orchestration")
OUT = os.path.join(ROOT, "experiments", "exploration", "MANIFEST_REMEDIATION")

pg = json.load(open(os.path.join(ORCH, "PROGRAM_GRAPH.json"), encoding="utf-8"))
n0 = pg["nodes"][0]
print("NODE KEYS:", list(n0.keys()))
print(json.dumps(n0, indent=1)[:3000])
