"""S00 -- reproduce anchors BEFORE any new statistic is computed.

Anchors (all pre-stated, from prior screens' published verdicts):
  A1  D103 out/retrospective_power.csv keyed (screen, decision, family_size_K, cell),
      worst null arm's mde80_fw  ->  1349 unique cells, 760 blind, share 0.5633802816901409
  A2  E1_I0041 TSTAT_CELL_FLOORS.csv -> 666 t_statistic cells
  A3  ... of which degeneracy_ratio > 5  -> 67
  A4  ... of which sd_used_by_D103 == 0 exactly -> 6
  A5  ... 73 total, of which 35 are recorded ADEQUATELY POWERED (not blind) by D103
  A6  E1_I0040: 38 screens exist; census covers 8; 213 arithmetic-ceiling kills
  A7  E1_I0040 EXPOSED programme-wide = 115, undeterminable = 3

No 2025/26 data is opened anywhere in this screen.
"""
import json, os, sys, hashlib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
OUT = {}

def say(k, v):
    OUT[k] = v
    print(f"{k} = {v!r}")

# ---------- A1 : D103 anchor ----------
d103 = os.path.join(EXPL, "E1_I0026_detection_floor", "out", "retrospective_power.csv")
rp = pd.read_csv(d103)
print("retrospective_power.csv shape:", rp.shape)
print("cols:", list(rp.columns))

key = ["screen", "decision", "family_size_K", "cell"]
# worst null arm == largest mde80_fw
g = rp.sort_values("mde80_fw").groupby(key, dropna=False).tail(1)
say("A1_n_cells", int(len(g)))
blind = g["mde80_fw"] > 0.0023
say("A1_n_blind", int(blind.sum()))
say("A1_share", float(blind.mean()))
assert len(g) == 1349, len(g)
assert int(blind.sum()) == 760
assert repr(float(blind.mean())) == repr(0.5633802816901409), float(blind.mean())
print("A1 OK -- 1349 / 760 / 0.5633802816901409 reproduced exactly")

# ---------- A2..A5 : E1_I0041 ----------
tf = pd.read_csv(os.path.join(EXPL, "E1_I0041_tstat_family_audit", "TSTAT_CELL_FLOORS.csv"))
say("A2_n_tstat_cells", int(len(tf)))
assert len(tf) == 666

deg = tf["degeneracy_ratio"] > 5
sd0 = tf["sd_used_by_D103"] == 0.0
say("A3_n_degenerate_gt5", int(deg.sum()))
say("A4_n_sd_exactly_zero", int(sd0.sum()))
broken = deg | sd0
say("A5_n_broken_total", int(broken.sum()))
assert int(deg.sum()) == 67, int(deg.sum())
assert int(sd0.sum()) == 6, int(sd0.sum())
assert int(broken.sum()) == 73, int(broken.sum())
print("A3/A4/A5 OK -- 67 + 6 = 73 reproduced exactly")
print("  overlap deg&sd0 =", int((deg & sd0).sum()))
print("  by screen:", tf.loc[broken, "screen"].value_counts().to_dict())

# how many of the 73 are recorded ADEQUATELY POWERED by D103 (mde_published <= 0.0023)?
adeq = tf.loc[broken, "mde_published"] <= 0.0023
say("A5b_n_broken_recorded_adequate", int(adeq.sum()))
print("  (target from E1_I0041 VERDICT sec.3 = 35)")

# also cross-check against D103's own keyed table
tfb = tf.loc[broken, ["screen", "cell"]].copy()
gg = g.set_index(["screen", "cell"])
found = 0; adeq_d103 = 0
for _, r in tfb.iterrows():
    k = (r["screen"], r["cell"])
    if k in gg.index:
        found += 1
        row = gg.loc[k]
        v = row["mde80_fw"] if np.ndim(row["mde80_fw"]) == 0 else row["mde80_fw"].iloc[0]
        if v <= 0.0023:
            adeq_d103 += 1
say("A5c_broken_found_in_d103_keyed", found)
say("A5c_broken_adequate_in_d103_keyed", adeq_d103)

# ---------- A6/A7 : E1_I0040 ----------
at = pd.read_csv(os.path.join(EXPL, "E1_I0040_audit_extension", "AUDIT_TABLE_EXT.csv"), low_memory=False)
print("AUDIT_TABLE_EXT shape:", at.shape)
print("AUDIT_TABLE_EXT cols:", list(at.columns))
say("A6_screens_on_disk", int(len([d for d in os.listdir(EXPL)
                                   if os.path.isdir(os.path.join(EXPL, d))])))

with open(os.path.join(HERE, "scripts", "_s00.json"), "w") as f:
    json.dump(OUT, f, indent=2, default=str)
print("\nDONE s00")
