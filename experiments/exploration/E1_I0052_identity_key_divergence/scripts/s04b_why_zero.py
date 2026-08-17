"""E1_I0052 s04b -- WHY the E0_I0006 panel shows zero divergence.

A zero is only worth as much as its explanation. Three candidate explanations:
  (a) the panel's player_id is a DIFFERENT dtype/id-space and my set arithmetic was vacuous
  (b) the panel genuinely excludes all 12 ambiguous identities (coverage)
  (c) the panel's raw source carries ONE spelling per player (bijection at source)
Only (c) is a real "safe" answer. This distinguishes them.
"""
import os, sys, json
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

SRC = os.path.join(B.EXP, "exploration", "E0_I0006_usage_redistribution")
played = pd.read_parquet(os.path.join(SRC, "clean_played_panel.parquet"))
p_all, _ = B.load_master_player("research")
p, _ = B.partition_guard(p_all, "season", "mp")

B.banner("s04b  why zero -- dtype, coverage, or a true bijection?")
print("  panel player_id dtype  : %s   sample: %s"
      % (played.player_id.dtype, played.player_id.head(3).tolist()))
print("  master player_id dtype : %s   sample: %s"
      % (p.player_id.dtype, p.player_id.head(3).tolist()))

pan = set(int(x) for x in played.player_id.dropna().unique())
mas = set(int(x) for x in p.player_id.dropna().unique())
print("\n  distinct ids  panel=%d  master(2021-24)=%d  intersection=%d"
      % (len(pan), len(mas), len(pan & mas)))
print("  panel ids NOT in master : %d" % len(pan - mas))
print("  -> (a) DIFFERENT ID SPACE?  %s"
      % ("YES - vacuous comparison" if len(pan & mas) < 0.5 * len(pan) else "NO"))

amb = [i for i in B.AMBIGUOUS_IDS_2021_2024]
print("\n  coverage of the 12 ambiguous identities IN THE PANEL:")
present = []
for pid in amb:
    sub = played[played.player_id == pid]
    msub = p[p.player_id == pid]
    nm_panel = sorted(sub.player_name.unique().tolist())
    nm_master = sorted(msub.player_name.unique().tolist())
    print("    %-9d panel_rows=%-4d panel_names=%-44s | master_rows=%-4d master_names=%s"
          % (pid, len(sub), " | ".join(nm_panel) if nm_panel else "-",
             len(msub), " | ".join(nm_master)))
    if len(sub):
        present.append(pid)
print("\n  ambiguous identities PRESENT in the panel: %d of 12  %s" % (len(present), present))
print("  of those, how many carry >1 spelling IN THE PANEL: %d"
      % sum(1 for pid in present if played[played.player_id == pid].player_name.nunique() > 1))
print("\n  -> (c) BIJECTION AT SOURCE? %s"
      % ("YES" if present and all(
          played[played.player_id == pid].player_name.nunique() == 1 for pid in present)
         else "n/a"))

# where does master's ambiguity come from? one spelling per source-row-type?
B.banner("where master_player's second spelling lives")
for pid in amb:
    msub = p[p.player_id == pid]
    for nm, g in msub.groupby("player_name"):
        print("    %-9d %-30s rows=%-4d seasons=%-16s played_rows(min>0)=%d"
              % (pid, nm, len(g), sorted(int(s) for s in g.season.unique()),
                 int((pd.to_numeric(g.get("minutes"), errors="coerce") > 0).sum())
                 if "minutes" in g else -1))
