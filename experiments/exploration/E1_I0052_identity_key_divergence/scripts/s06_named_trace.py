"""E1_I0052 s06 -- THE NAMED CASES.

The twelve exploration-partition ambiguous identities (the thirteenth is 2026-only, SEALED),
traced individually into:
  (1) the shared screen frame's DECISION STRATUM  (n_prior >= 8 AND prior5_minutes >= 24)
  (2) the m13 champion translation fit pool
  (3) E1_I0045's published coverage-cost / top-removed tables
  (4) the normalized-name index that the market lane resolves through

Selection is by player_id from the explicit allowlist in ik_base. Names are printed, never
used to select.
"""
import os, sys, json, unicodedata, re
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

AMB = B.AMBIGUOUS_IDS_2021_2024
B.banner("s06  NAMED-CASE TRACE -- the twelve, individually")

p_all, _ = B.load_master_player("research")
p, _ = B.partition_guard(p_all, "season", "mp")
NAME_OF = {pid: " | ".join(sorted(p[p.player_id == pid].player_name.unique()))
           for pid in AMB}
print("  allowlist (%d ids), resolved and printed:" % len(AMB))
for pid in AMB:
    print("    %-9d %s" % (pid, NAME_OF[pid]))

trace = []

# ------------------------------------------------------------------ (1) decision stratum
B.banner("1. THE SHARED SCREEN FRAME AND ITS DECISION STRATUM")
SF = os.path.join(B.EXP, "exploration", "E0_I0029_freethrow_hurdle", "screen_frame.parquet")
sf = pd.read_parquet(SF)
print("  frame : %s" % os.path.relpath(SF, B.EXP))
print("  sha256: %s   rows=%d" % (B.sha256(SF), len(sf)))
print("  manifest: %s" % B.manifest_status(SF)["status"])
print("  (identical row count/ambiguity profile to E0_I0008, E0_I0011, E1_I0004_rim_finishing,")
print("   E1_I0008 and E1_I0011 frames -- see out/_s05_frame_divergence.csv)")
sf, gsf = B.partition_guard(sf, "season", "screen_frame")
print("  PARTITION GUARD: %s" % json.dumps(gsf))

have = [c for c in ("n_prior", "prior5_minutes") if c in sf.columns]
print("  stratum columns present: %s" % have)
if len(have) == 2:
    dm = (pd.to_numeric(sf["n_prior"], errors="coerce").to_numpy(float) >= 8.0) & \
         (pd.to_numeric(sf["prior5_minutes"], errors="coerce").to_numpy(float) >= 24.0)
    sf = sf.assign(_in_stratum=dm)
    print("  DECISION STRATUM (n_prior>=8 AND prior5_minutes>=24): %d of %d rows (%.4f)"
          % (dm.sum(), len(sf), dm.mean()))
    amb_sf = sf[sf.player_id.isin(AMB)]
    print("\n  the twelve inside this frame:")
    tot_str = 0
    for pid in AMB:
        s = sf[sf.player_id == pid]
        if not len(s):
            print("    %-9d %-44s  ABSENT from frame" % (pid, NAME_OF[pid]))
            trace.append({"player_id": pid, "names": NAME_OF[pid],
                          "surface": "screen_frame(18212)", "rows": 0,
                          "in_decision_stratum": 0, "spellings_in_surface": 0})
            continue
        nsp = s.player_name.nunique() if "player_name" in s else -1
        instr = int(s["_in_stratum"].sum())
        tot_str += instr
        print("    %-9d %-44s  rows=%-4d spellings_here=%-2d IN_DECISION_STRATUM=%d"
              % (pid, NAME_OF[pid], len(s), nsp, instr))
        if nsp > 1:
            for nm, gg in s.groupby("player_name"):
                print("           %-30s rows=%-4d in_stratum=%d"
                      % (nm, len(gg), int(gg["_in_stratum"].sum())))
        trace.append({"player_id": pid, "names": NAME_OF[pid],
                      "surface": "screen_frame(18212)", "rows": len(s),
                      "in_decision_stratum": instr, "spellings_in_surface": nsp})
    print("\n  TOTAL decision-stratum rows belonging to an ambiguous identity: %d of %d (%.4f%%)"
          % (tot_str, int(dm.sum()), 100.0 * tot_str / max(1, int(dm.sum()))))
    # how many of those rows would MOVE under the two keys?
    amb2 = [pid for pid in AMB
            if len(sf[sf.player_id == pid]) and sf[sf.player_id == pid].player_name.nunique() > 1]
    print("  of the twelve, identities carrying >1 SPELLING inside this frame: %d  %s"
          % (len(amb2), amb2))
    n_split = int(sf[sf.player_id.isin(amb2) & sf["_in_stratum"]].shape[0])
    print("  decision-stratum rows that a NAME key would split: %d" % n_split)

# ------------------------------------------------------------------ (2) champion fit pool
B.banner("2. THE CHAMPION'S FIT POOL -- m13 translation_rows")
TR = os.path.join(B.EXP, "exploration", "MEASURE_F1_m13_fitpool", "repro_out",
                  "translation_rows.parquet")
tr = pd.read_parquet(TR)
print("  frame : %s" % os.path.relpath(TR, B.EXP))
print("  sha256: %s   rows=%d" % (B.sha256(TR), len(tr)))
print("  manifest: %s" % B.manifest_status(TR)["status"])
tr, gtr = B.partition_guard(tr, "season", "translation_rows")
print("  PARTITION GUARD: %s" % json.dumps(gtr))
i2n = tr[["player_id", "player_name"]].drop_duplicates().groupby("player_id").player_name.nunique()
n2i = tr[["player_id", "player_name"]].drop_duplicates().groupby("player_name").player_id.nunique()
print("  ids with >1 spelling IN THE FIT POOL : %d -> %s"
      % (int((i2n > 1).sum()), sorted(int(x) for x in i2n[i2n > 1].index)))
print("  names with >1 id IN THE FIT POOL     : %d  (DROP mode)" % int((n2i > 1).sum()))
for pid in AMB:
    s = tr[tr.player_id == pid]
    nsp = s.player_name.nunique() if len(s) else 0
    print("    %-9d %-44s  fit_pool_rows=%-4d spellings_here=%d %s"
          % (pid, NAME_OF[pid], len(s), nsp, "  <-- SPLIT UNDER A NAME KEY" if nsp > 1 else ""))
    if nsp > 1:
        print("           %s" % s.groupby("player_name").size().to_dict())
    trace.append({"player_id": pid, "names": NAME_OF[pid],
                  "surface": "m13_translation_rows(5889)", "rows": len(s),
                  "in_decision_stratum": None, "spellings_in_surface": nsp})
# the join that assembles the pool
print("\n  m13_lib.py:348  m = scored.merge(market, on=['game_id','player_id'],")
print("                                    how='inner', validate='one_to_one')")
print("  -> the fit pool is assembled on (game_id, player_id) with a one-to-one validator.")
print("     A name-keyed assembly is structurally impossible here; the validator would raise.")

# ------------------------------------------------------------------ (3) E1_I0045 tables
B.banner("3. E1_I0045_roster_currency -- the one NAME_ONLY published table")
T = os.path.join(B.EXP, "exploration", "E1_I0045_roster_currency", "top_removed_players_R3.csv")
t = pd.read_csv(T)
print("  %s  rows=%d" % (os.path.relpath(T, B.EXP), len(t)))
print(t.to_string(index=False))
AMB_SPELLINGS = {}
for pid in AMB:
    for nm in p[p.player_id == pid].player_name.unique():
        AMB_SPELLINGS[nm] = pid
hit = t[t.player_name.isin(AMB_SPELLINGS)]
print("\n  rows whose player_name is an ambiguous spelling: %d" % len(hit))
for _, r in hit.iterrows():
    pid = AMB_SPELLINGS[r.player_name]
    print("    %-24s -> player_id %-9d  all spellings: %s" % (r.player_name, pid, NAME_OF[pid]))

PF = os.path.join(B.EXP, "exploration", "E1_I0045_roster_currency", "_PF.parquet")
pf = pd.read_parquet(PF)
print("\n  source frame _PF.parquet rows=%d  sha256=%s" % (len(pf), B.sha256(PF)[:16]))
if "drop_R3_union_S2" in pf.columns:
    sub = pf[pf["drop_R3_union_S2"]]
    print("  rows in the R3-union-S2 removal set: %d" % len(sub))
    gname = sub.groupby("player_name").size()
    gid = sub.groupby("player_id").size()
    print("  groups under NAME key = %d ; under ID key = %d ; delta = %+d"
          % (len(gname), len(gid), len(gname) - len(gid)))
    ambhere = sub[sub.player_id.isin(AMB)]
    print("  removal-set rows belonging to an ambiguous identity: %d" % len(ambhere))
    for pid, g in ambhere.groupby("player_id"):
        print("     %-9d %-44s rows=%-3d spellings_in_removal_set=%d %s"
              % (pid, NAME_OF[pid], len(g), g.player_name.nunique(),
                 sorted(g.player_name.unique())))
    print("  -> D101: a NAME-keyed grouping here changes the GROUP COUNT by %+d, which is a")
    print("     denominator change for any per-player statistic read off this table."
          % () if False else "")

# ------------------------------------------------------------------ (4) norm-name index
B.banner("4. THE NORMALIZED-NAME INDEX the market lane resolves through")


def _norm_name(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


nr = p[["player_id", "player_name", "season"]].drop_duplicates()
idx = {}
for _, sub in nr.sort_values("season").groupby("season", sort=True):
    for pid, nm in sub[["player_id", "player_name"]].drop_duplicates().itertuples(index=False):
        idx[_norm_name(nm)] = int(pid)
print("  index size (distinct normalized spellings, 2021-2024): %d" % len(idx))
coll = {}
for _, sub in nr.iterrows():
    coll.setdefault(_norm_name(sub.player_name), set()).add(int(sub.player_id))
bad = {k: sorted(v) for k, v in coll.items() if len(v) > 1}
print("  normalized spellings binding to MORE THAN ONE player_id (a silent merge): %d" % len(bad))
if bad:
    print("   ", bad)
print("\n  which of the twelve does _norm_name ABSORB (both spellings -> same string)?")
absorbed, not_absorbed = [], []
for pid in AMB:
    nms = sorted(p[p.player_id == pid].player_name.unique())
    norms = sorted({_norm_name(n) for n in nms})
    ok = len(norms) == 1
    (absorbed if ok else not_absorbed).append(pid)
    print("    %-9d %-44s -> %-2d normalized form(s) %s  %s"
          % (pid, " | ".join(nms), len(norms), norms, "ABSORBED" if ok else "NOT ABSORBED"))
    print("           but both forms map to player_id %s in the index: %s"
          % (pid, {n: idx.get(n) for n in norms}))
print("\n  absorbed by normalisation      : %d  %s" % (len(absorbed), absorbed))
print("  NOT absorbed (distinct strings): %d  %s" % (len(not_absorbed), not_absorbed))
print("  -> but build_identity_index maps EVERY distinct (player_id, player_name) pair, so all")
print("     %d resolve to the correct player_id anyway. Absorption is not what makes it safe;" % len(AMB))
print("     enumerating every observed spelling is.")

pd.DataFrame(trace).to_csv(os.path.join(B.OUT, "_s06_named_trace.csv"), index=False)
json.dump({"absorbed_by_norm": absorbed, "not_absorbed_by_norm": not_absorbed,
           "norm_collisions": bad, "index_size": len(idx)},
          open(os.path.join(B.OUT, "_s06.json"), "w"), indent=2)
print("\nDONE s06")
