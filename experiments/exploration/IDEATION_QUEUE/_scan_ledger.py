import json, os, sys

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
LED = os.path.join(ROOT, "experiments", "player_program", "orchestration", "DECISION_LEDGER.jsonl")
OUT = os.path.join(ROOT, "experiments", "exploration", "IDEATION_QUEUE", "_ledger_index.txt")

rows = []
with open(LED, "r", encoding="utf-8", errors="replace") as f:
    for i, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception as e:
            rows.append("PARSE_FAIL line %d: %s" % (i, e))
            continue
        did = d.get("decision_id", "?")
        ts = d.get("ts", "?")
        q = d.get("question", "")
        rul = d.get("ruling", "")
        ver = d.get("verdict", "")
        if isinstance(rul, dict):
            rul = " | ".join("%s :: %s" % (k, str(v)) for k, v in rul.items())
        if isinstance(ver, dict):
            ver = " | ".join("%s :: %s" % (k, str(v)) for k, v in ver.items())
        keys = ",".join(k for k in d.keys() if k not in
                        ("decision_id", "ts", "made_by", "authority", "nodes", "question", "ruling", "verdict"))
        rows.append("=" * 100)
        rows.append("[%03d] %s   (%s)" % (i, did, ts))
        rows.append("  OTHER_KEYS: %s" % keys)
        rows.append("  Q: %s" % str(q)[:1200])
        if ver:
            rows.append("  VERDICT: %s" % str(ver)[:2500])
        if rul:
            rows.append("  RULING: %s" % str(rul)[:2500])

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(rows))
print("wrote", OUT, len(rows), "lines")
