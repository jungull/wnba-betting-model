import json, hashlib, sys
W = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
S2 = json.load(open(W+r"\experiments\player_program\stage3_score\S33R_PREREGISTRATION_REPAIR\SPEC_V2.json", encoding="utf-8"))
FR = json.load(open(W+r"\experiments\player_program\stage3_score\S35_FREEZE_TASK_CARDS\SPEC.json", encoding="utf-8"))

def h(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(',',':')).encode('utf-8')).hexdigest()

print("SPEC_V2 top keys:", list(S2.keys()))
ok=True
for c in FR["frozen_cards"]:
    eid=c["element_id"]
    obj=S2["k0_matched"][eid]
    got=h(obj)
    m = got==c["card_sha256"]
    ok &= m
    print(("OK  " if m else "MISMATCH "), eid, got[:12], c["card_sha256"][:12])
for i,b in enumerate(FR["frozen_arm_blocks"]):
    obj=S2["arms"][i]
    got=h(obj)
    m = got==b["arm_block_sha256"] and obj.get("arm_id")==b["arm_id"]
    ok &= m
    print(("OK  " if m else "MISMATCH "), b["arm_id"], got[:12], b["arm_block_sha256"][:12], "| arms[%d].arm_id=%s"%(i,obj.get("arm_id")))
print("task_cards_sha256 recompute:", h(FR["frozen_cards"]), "==", FR["task_cards_sha256"], h(FR["frozen_cards"])==FR["task_cards_sha256"])
print("arm_blocks_sha256 recompute:", h(FR["frozen_arm_blocks"]), "==", FR["arm_blocks_sha256"], h(FR["frozen_arm_blocks"])==FR["arm_blocks_sha256"])
print("ALL:", ok)
print()
print("k0_matched element ids (%d):"%len(S2["k0_matched"]))
for k in S2["k0_matched"]: print("   ", k)
print("card object keys for SC01::E3:", list(S2["k0_matched"]["SC01_OPP_ADJ_INTERACTING::E3_HOME_WIN_PROB"].keys()))
print("arm block keys for arms[0]:", list(S2["arms"][0].keys()))
