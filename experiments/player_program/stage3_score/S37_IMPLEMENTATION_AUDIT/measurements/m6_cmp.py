import json, sys, io, hashlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
S = r"C:\Users\JGALLA~1\AppData\Local\Temp\claude\C--Users-jgallagher\5939a782-46ad-4255-aa74-5e0bae6314bf\scratchpad"
W = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
a = json.load(open(S+r"\A1_DATE_WITNESS_RECEIPT.json", encoding="utf-8"))
b = json.load(open(W+r"\experiments\player_program\stage3_score\S33R_PREREGISTRATION_REPAIR\A1_DATE_WITNESS_RECEIPT.json", encoding="utf-8"))
def c(o): return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(',',':')).encode()).hexdigest()
print("S37 rerun canonical sha256:", c(a))
print("S33R frozen canonical sha256:", c(b))
print("BYTE-FOR-BYTE (canonical JSON) IDENTICAL:", c(a)==c(b))
if c(a)!=c(b):
    def diff(x,y,p=""):
        if type(x)!=type(y): print("TYPE",p); return
        if isinstance(x,dict):
            for k in set(x)|set(y):
                if k not in x: print("only in frozen:",p+"/"+k)
                elif k not in y: print("only in rerun:",p+"/"+k)
                else: diff(x[k],y[k],p+"/"+k)
        elif isinstance(x,list):
            if len(x)!=len(y): print("LEN",p,len(x),len(y))
            else:
                for i,(u,v) in enumerate(zip(x,y)): diff(u,v,p+"/%d"%i)
        elif x!=y: print("VAL",p,"rerun=",repr(x)[:200],"frozen=",repr(y)[:200])
    diff(a,b)
print()
rb = a["replacement_witness_B_release_ordinal"]
print("n_displaced_games (release-order displaced):", rb["n_displaced_games"])
wa = a["replacement_witness_A_shotchart_endpoint"]
print("shotchart witnessed clusters:", wa["universe_clusters_witnessed"]["n"],
      " UNWITNESSED:", wa["universe_clusters_UNWITNESSED"]["n"],
      " date deviations vs master_team:", wa["date_deviations_vs_master_team"])
print("universe:", json.dumps(a["universe"]))
