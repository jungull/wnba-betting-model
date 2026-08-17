"""E1_I0052 s05 -- ARTIFACT CENSUS: the check the code scan cannot make.

A code scan can only see keys it can resolve. The complementary, assumption-free test is on the
PERSISTED FRAMES themselves: if a research frame carries a player identity at all, does it carry
`player_id`? A frame that carries a name but NO id forces every downstream consumer to key on the
name -- that is name-keying I could never see in a call graph, because it is imposed by the
schema.

For every persisted frame in experiments/exploration and experiments/player_program:
  - does it carry a player-identity column at all?
  - if so: ID_ONLY / ID_AND_NAME / NAME_ONLY (the exposed class)
  - for NAME_ONLY and ID_AND_NAME frames: how many rows would diverge under the two keys?
"""
import os, sys, json
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

SCOPES = [os.path.join(B.EXP, "exploration"), os.path.join(B.EXP, "player_program")]
SELF = os.path.join(B.EXP, "exploration", "E1_I0052_identity_key_divergence")

ID_COLS = ("player_id", "person_id", "athlete_id", "nba_player_id", "playerid")
NAME_COLS = ("player_name", "player", "playername", "name", "full_name",
             "display_name", "norm_name", "player_norm", "athlete_name")

rows = []
skipped = []
n_files = 0

for scope in SCOPES:
    for dirpath, dirnames, filenames in os.walk(scope):
        if "__pycache__" in dirpath or dirpath.startswith(SELF):
            continue
        for fn in filenames:
            if not fn.lower().endswith((".parquet", ".csv")):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                sz = os.path.getsize(fp)
                if sz > 220_000_000:
                    skipped.append((fp, "too large %d" % sz)); continue
                if fn.lower().endswith(".parquet"):
                    import pyarrow.parquet as pq
                    sch = pq.read_schema(fp)
                    cols = list(sch.names)
                else:
                    cols = list(pd.read_csv(fp, nrows=0).columns)
            except Exception as e:
                skipped.append((fp, repr(e)[:90])); continue
            n_files += 1
            low = {c.lower(): c for c in cols}
            has_id = [low[c] for c in ID_COLS if c in low]
            has_nm = [low[c] for c in NAME_COLS if c in low]
            if not has_id and not has_nm:
                klass = "NO_PLAYER_IDENTITY"
            elif has_id and has_nm:
                klass = "ID_AND_NAME"
            elif has_id:
                klass = "ID_ONLY"
            else:
                klass = "NAME_ONLY"
            rows.append({"path": os.path.relpath(fp, B.EXP).replace("\\", "/"),
                         "bytes": sz, "n_cols": len(cols), "class": klass,
                         "id_cols": "|".join(has_id), "name_cols": "|".join(has_nm)})

df = pd.DataFrame(rows)
B.banner("s05  ARTIFACT CENSUS -- persisted frames in the research lane")
print("  frames read: %d   unreadable/skipped: %d" % (n_files, len(skipped)))
print(df["class"].value_counts().to_string())

# ---- the exposed class: NAME_ONLY frames -------------------------------------------------
B.banner("NAME_ONLY frames -- a downstream consumer has no choice but to key on the name")
no = df[df["class"] == "NAME_ONLY"].sort_values("bytes", ascending=False)
print("  count: %d" % len(no))
for _, r in no.iterrows():
    print("    %-9d  %-22s  %s" % (r.bytes, r.name_cols, r.path))

# ---- measure divergence in every ID_AND_NAME and NAME_ONLY frame -------------------------
B.banner("row-level divergence inside every frame that carries a player identity")
p_all, _ = B.load_master_player("research")
p, _ = B.partition_guard(p_all, "season", "mp")
# name -> id map from the manifest-verified master, exploration partition only
n2i = (p[["player_name", "player_id"]].dropna().drop_duplicates()
       .groupby("player_name").player_id.apply(lambda s: sorted(set(int(x) for x in s))))
AMB_NAMES = set()
for pid in B.AMBIGUOUS_IDS_2021_2024:
    for nm in p[p.player_id == pid].player_name.unique():
        AMB_NAMES.add(nm)
print("  ambiguous spellings in the exploration partition (resolved, printed): %d" % len(AMB_NAMES))
print("   ", sorted(AMB_NAMES))

det = []
for _, r in df[df["class"].isin(["ID_AND_NAME", "NAME_ONLY"])].iterrows():
    fp = os.path.join(B.EXP, r.path.replace("/", os.sep))
    try:
        usecols = [c for c in (r.id_cols.split("|") + r.name_cols.split("|")) if c]
        if fp.lower().endswith(".parquet"):
            d = pd.read_parquet(fp, columns=usecols)
        else:
            d = pd.read_csv(fp, usecols=lambda c: c in usecols, low_memory=False)
    except Exception as e:
        det.append({"path": r.path, "class": r["class"], "status": "UNREADABLE",
                    "err": repr(e)[:80]})
        continue
    ncol = r.name_cols.split("|")[0] if r.name_cols else None
    icol = r.id_cols.split("|")[0] if r.id_cols else None
    rec = {"path": r.path, "class": r["class"], "rows": len(d),
           "id_col": icol, "name_col": ncol, "status": "OK"}
    if ncol is not None:
        nm_series = d[ncol].astype(str)
        rec["rows_with_ambiguous_spelling"] = int(nm_series.isin(AMB_NAMES).sum())
        rec["distinct_ambiguous_spellings"] = int(
            nm_series[nm_series.isin(AMB_NAMES)].nunique())
    if icol is not None and ncol is not None:
        g = d[[icol, ncol]].dropna().drop_duplicates()
        try:
            gi = g.groupby(icol)[ncol].nunique()
            gn = g.groupby(ncol)[icol].nunique()
            rec["ids_with_multiple_names"] = int((gi > 1).sum())
            rec["names_with_multiple_ids"] = int((gn > 1).sum())
            # row-level divergence: rows whose name key splits/merges an identity
            bad_i = set(gi[gi > 1].index)
            bad_n = set(gn[gn > 1].index)
            rec["rows_diverging_duplication"] = int(d[icol].isin(bad_i).sum())
            rec["rows_diverging_drop"] = int(d[ncol].isin(bad_n).sum())
        except Exception as e:
            rec["status"] = "GROUP_FAIL:" + repr(e)[:50]
    if icol is not None:
        rec["rows_with_ambiguous_id"] = int(
            pd.to_numeric(d[icol], errors="coerce").isin(B.AMBIGUOUS_IDS_2021_2024).sum())
    det.append(rec)

dd = pd.DataFrame(det)
df.to_csv(os.path.join(B.OUT, "_s05_frame_classes.csv"), index=False)
dd.to_csv(os.path.join(B.OUT, "_s05_frame_divergence.csv"), index=False)

print("\n  frames carrying a player identity: %d" % len(dd))
if "ids_with_multiple_names" in dd:
    hot = dd[(dd.get("ids_with_multiple_names", 0).fillna(0) > 0) |
             (dd.get("names_with_multiple_ids", 0).fillna(0) > 0)]
    print("  frames in which an identity is actually AMBIGUOUS: %d" % len(hot))
    if len(hot):
        print(hot[["path", "rows", "ids_with_multiple_names", "names_with_multiple_ids",
                   "rows_diverging_duplication", "rows_diverging_drop"]].to_string(index=False))
nm_only = dd[dd["class"] == "NAME_ONLY"]
if len(nm_only):
    print("\n  NAME_ONLY frames and their exposure to an ambiguous spelling:")
    print(nm_only[["path", "rows", "name_col", "rows_with_ambiguous_spelling",
                   "distinct_ambiguous_spellings"]].to_string(index=False))

if skipped:
    print("\n  skipped/unreadable (reported, not hidden): %d" % len(skipped))
    for fp, e in skipped[:25]:
        print("    %-80s %s" % (os.path.relpath(fp, B.EXP)[:80], e))

json.dump({"n_frames": n_files, "n_skipped": len(skipped),
           "class_counts": df["class"].value_counts().to_dict(),
           "ambiguous_spellings": sorted(AMB_NAMES)},
          open(os.path.join(B.OUT, "_s05.json"), "w"), indent=2)
