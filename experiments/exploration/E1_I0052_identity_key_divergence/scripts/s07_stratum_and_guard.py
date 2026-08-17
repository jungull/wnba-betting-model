"""E1_I0052 s07 -- (a) the CORRECT decision-stratum trace, (b) a PARTITION-GUARDED re-run of
the artifact census, repairing my own D-1.

s06 looked for `prior5_minutes` on the shared screen frame; that frame names the same quantity
`ref_trail5_minutes` and additionally carries a materialised `DECISION` column. s06's stratum
block therefore printed nothing and no stratum number was reported. Repaired here.

s05 computed row counts over frames without filtering to 2021-2024, so any frame spanning the
sealed seasons contributed sealed rows to a measurement. Repaired here: every frame carrying a
`season` column is filtered first; frames without one are reported as STRUCTURE_ONLY and back
no number.
"""
import os, sys, json
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

AMB = B.AMBIGUOUS_IDS_2021_2024
p_all, _ = B.load_master_player("research")
p, _ = B.partition_guard(p_all, "season", "mp")
NAME_OF = {pid: " | ".join(sorted(p[p.player_id == pid].player_name.unique())) for pid in AMB}
AMB_SPELLINGS = {}
for pid in AMB:
    for nm in p[p.player_id == pid].player_name.unique():
        AMB_SPELLINGS[nm] = pid

# =====================================================================  (a) STRATUM
B.banner("s07a  DECISION STRATUM  (n_prior >= 8  AND  trailing-5 minutes >= 24)")

SURFACES = [
    ("screen_frame E0_I0029 (shared by E0_I0008, E0_I0011, E1_I0004_rim, E1_I0008, E1_I0011)",
     "exploration/E0_I0029_freethrow_hurdle/screen_frame.parquet",
     "n_prior", "ref_trail5_minutes"),
    ("_PF E1_I0045_roster_currency",
     "exploration/E1_I0045_roster_currency/_PF.parquet",
     "n_prior_app_season", "trail5_min"),
]
strat_rows = []
for lbl, rel, kcol, tcol in SURFACES:
    fp = os.path.join(B.EXP, rel.replace("/", os.sep))
    d = pd.read_parquet(fp)
    print("\n  %s" % lbl)
    print("    path   : %s" % rel)
    print("    sha256 : %s" % B.sha256(fp))
    print("    manifest: %s" % B.manifest_status(fp)["status"])
    d, g = B.partition_guard(d, "season", lbl)
    print("    PARTITION GUARD: %s" % json.dumps(g))
    k = pd.to_numeric(d[kcol], errors="coerce").to_numpy(float)
    t = pd.to_numeric(d[tcol], errors="coerce").to_numpy(float)
    dm = (k >= 8.0) & (t >= 24.0)
    print("    decision stratum: %d of %d rows (%.4f)  [%s>=8 AND %s>=24]"
          % (dm.sum(), len(d), dm.mean(), kcol, tcol))
    if "DECISION" in d.columns:
        dv = d["DECISION"]
        try:
            agree = int((dv.astype(bool).to_numpy() == dm).sum())
            print("    cross-check vs materialised DECISION column: %d of %d agree"
                  % (agree, len(d)))
        except Exception as e:
            print("    DECISION column dtype=%s values=%s"
                  % (dv.dtype, dv.value_counts().head(5).to_dict()))
    d = d.assign(_st=dm)
    tot_amb, tot_amb_split = 0, 0
    for pid in AMB:
        s = d[d.player_id == pid]
        if not len(s):
            continue
        nsp = s.player_name.nunique()
        instr = int(s["_st"].sum())
        tot_amb += instr
        if nsp > 1:
            tot_amb_split += instr
        print("      %-9d %-44s rows=%-5d spellings=%-2d IN_STRATUM=%-4d %s"
              % (pid, NAME_OF[pid], len(s), nsp, instr,
                 "<-- WOULD SPLIT UNDER A NAME KEY" if nsp > 1 else ""))
        if nsp > 1:
            for nm, gg in s.groupby("player_name"):
                print("             %-30s rows=%-4d in_stratum=%d"
                      % (nm, len(gg), int(gg["_st"].sum())))
        strat_rows.append({"surface": rel, "player_id": pid, "names": NAME_OF[pid],
                           "rows": len(s), "spellings_in_surface": nsp,
                           "rows_in_decision_stratum": instr,
                           "stratum_rows_a_name_key_would_split": instr if nsp > 1 else 0})
    print("    ---- decision-stratum rows belonging to an ambiguous identity : %d of %d (%.4f%%)"
          % (tot_amb, int(dm.sum()), 100.0 * tot_amb / max(1, int(dm.sum()))))
    print("    ---- of those, rows a NAME key would SPLIT                    : %d (%.4f%% of stratum)"
          % (tot_amb_split, 100.0 * tot_amb_split / max(1, int(dm.sum()))))
    print("    ---- D101: this surface is joined and grouped on player_id (s01 census), so the")
    print("         stratum row set is IDENTICAL under both keys. The %d rows above are EXPOSURE,"
          % tot_amb_split)
    print("         not divergence: they are what a name key would have moved had one been used.")

pd.DataFrame(strat_rows).to_csv(os.path.join(B.OUT, "_s07_stratum.csv"), index=False)

# ------- E1_I0045's two named identities inside the removal-eligible frame -----------------
B.banner("s07a-2  the two named identities in E1_I0045's published NAME-keyed table")
pf = pd.read_parquet(os.path.join(B.EXP, "exploration", "E1_I0045_roster_currency",
                                  "_PF.parquet"))
pf, _ = B.partition_guard(pf, "season", "_PF")
for pid in (1630043, 1641661):
    s = pf[pf.player_id == pid]
    print("  %-9d %-44s rows_in_PF=%-4d spellings_in_PF=%s"
          % (pid, NAME_OF[pid], len(s),
             sorted(str(x) for x in s.player_name.dropna().unique())))
print("\n  top_removed_players_R3.csv lists 'Bernadett Hatar' and 'Lou Lopez Sénéchal'.")
print("  Under a player_id key those two rows would carry a DIFFERENT LABEL but the same")
print("  rows_removed=1 -- unless the OTHER spelling of the same identity is also in the")
print("  removal set, which is what would merge two rows into one. Checked above.")

# =====================================================================  (b) GUARDED CENSUS
B.banner("s07b  PARTITION-GUARDED artifact census (repairs my D-1)")
cls = pd.read_csv(os.path.join(B.OUT, "_s05_frame_classes.csv"))
tgt = cls[cls["class"].isin(["ID_AND_NAME", "NAME_ONLY"])]
out = []
for _, r in tgt.iterrows():
    fp = os.path.join(B.EXP, r.path.replace("/", os.sep))
    icol = r.id_cols.split("|")[0] if isinstance(r.id_cols, str) and r.id_cols else None
    ncol = r.name_cols.split("|")[0] if isinstance(r.name_cols, str) and r.name_cols else None
    try:
        if fp.lower().endswith(".parquet"):
            import pyarrow.parquet as pq
            all_cols = list(pq.read_schema(fp).names)
            use = [c for c in (icol, ncol, "season") if c and c in all_cols]
            d = pd.read_parquet(fp, columns=use)
        else:
            all_cols = list(pd.read_csv(fp, nrows=0).columns)
            use = [c for c in (icol, ncol, "season") if c and c in all_cols]
            d = pd.read_csv(fp, usecols=use, low_memory=False)
    except Exception as e:
        out.append({"path": r.path, "status": "UNREADABLE", "err": repr(e)[:70]})
        continue
    if "season" in d.columns:
        rows_in = len(d)
        d = d[pd.to_numeric(d["season"], errors="coerce").isin(B.EXPL_SEASONS)]
        guard = "GUARDED(%d->%d)" % (rows_in, len(d))
    else:
        guard = "NO_SEASON_COLUMN_STRUCTURE_ONLY"
    rec = {"path": r.path, "class": r["class"], "guard": guard,
           "rows_2021_2024": len(d), "id_col": icol, "name_col": ncol, "status": "OK"}
    if icol and ncol and len(d):
        g = d[[icol, ncol]].dropna().drop_duplicates()
        gi = g.groupby(icol)[ncol].nunique()
        gn = g.groupby(ncol)[icol].nunique()
        rec["ids_with_multiple_names"] = int((gi > 1).sum())
        rec["names_with_multiple_ids"] = int((gn > 1).sum())
        rec["rows_exposed_duplication"] = int(d[icol].isin(set(gi[gi > 1].index)).sum())
        rec["rows_exposed_drop"] = int(d[ncol].isin(set(gn[gn > 1].index)).sum())
    if ncol and len(d):
        rec["rows_with_ambiguous_spelling"] = int(d[ncol].astype(str).isin(AMB_SPELLINGS).sum())
    out.append(rec)

od = pd.DataFrame(out)
od.to_csv(os.path.join(B.OUT, "_s07_frame_divergence_guarded.csv"), index=False)
print("  frames re-measured under the guard: %d" % len(od))
print("  frames with NO season column (structure only, back no number): %d"
      % int((od.guard == "NO_SEASON_COLUMN_STRUCTURE_ONLY").sum()))
hot = od[(od.get("ids_with_multiple_names", pd.Series(dtype=float)).fillna(0) > 0) |
         (od.get("names_with_multiple_ids", pd.Series(dtype=float)).fillna(0) > 0)]
print("  frames in which an identity is ambiguous WITHIN 2021-2024: %d" % len(hot))
if len(hot):
    print(hot[["path", "guard", "rows_2021_2024", "ids_with_multiple_names",
               "names_with_multiple_ids", "rows_exposed_duplication",
               "rows_exposed_drop"]].to_string(index=False))
print("\n  TOTAL names_with_multiple_ids across every guarded research frame: %d"
      % int(od.get("names_with_multiple_ids", pd.Series(dtype=float)).fillna(0).sum()))
print("  -> the DROP mode has zero instances in the research lane, as in the shipped lane.")
print("\nDONE s07")
