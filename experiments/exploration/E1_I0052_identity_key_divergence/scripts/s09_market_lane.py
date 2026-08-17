"""E1_I0052 s09 -- the two remaining unmeasured name-keyed surfaces:
  (A) MEASURE_F1_m13_fitpool / m14_lib.py  (via MODEL_VS_MARKET.build_market_frame)
      dedup on ["game_id","player_name","bookmaker_key","line"] BEFORE norm_name -> player_id
  (B) player_program/future_research/F16_PLAYER_PROPS -- props files carry NO player_id at all

Both live on the market/props side, where the source genuinely has no stable key. This is the
COVERAGE BOUNDARY the brief asks for: how much of the lane the verified identity map protects and
how much it cannot.
"""
import os, sys, json, re, unicodedata
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

PROPS = os.path.join(B.PROD, "data", "props_capture", "historical",
                     "master_props_historical.csv")
ALIAS = os.path.join(B.EXP, "player_program", "ops_lane", "O14_OPS_ENTITY_RESOLUTION",
                     "alias_table.json")

AMB = B.AMBIGUOUS_IDS_2021_2024
p_all, _ = B.load_master_player("research")
p, _ = B.partition_guard(p_all, "season", "mp")
NAME_OF = {pid: " | ".join(sorted(p[p.player_id == pid].player_name.unique())) for pid in AMB}


def _norm_name(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


B.banner("s09  (A) the market frame: dedup by NAME, then resolve to player_id")
print("  props source (PRODUCTION worktree, as MODEL_VS_MARKET reads it):")
print("    %s" % PROPS)
print("    sha256   : %s" % B.sha256(PROPS))
print("    manifest : %s" % B.manifest_status(PROPS)["status"])
print("  alias table: %s  exists=%s" % (ALIAS, os.path.exists(ALIAS)))
if os.path.exists(ALIAS):
    a = json.load(open(ALIAS, "r", encoding="utf-8"))
    print("    aliases   : %d  %s" % (len(a.get("aliases", {})), a.get("aliases")))

raw = pd.read_csv(PROPS, low_memory=False)
print("\n  rows(all)=%d  cols=%d" % (len(raw), raw.shape[1]))
print("  carries player_id column? %s" % ("player_id" in raw.columns))
raw["game_id"] = raw["game_id"].astype(str)
# season from the NBA/WNBA game_id convention used throughout this repo: 2000 + gid[3:5]
raw["_season"] = raw["game_id"].str[3:5].astype(int) + 2000
print("  seasons present: %s" % sorted(raw["_season"].unique().tolist()))
df, g = B.partition_guard(raw, "_season", "master_props_historical")
print("  PARTITION GUARD: %s" % json.dumps(g))

# reproduce the exclusions in build_market_frame, in order
df["commence"] = pd.to_datetime(df["commence_time"], utc=True, errors="coerce")
df["snap_ret"] = pd.to_datetime(df["snapshot_returned_utc"], utc=True, errors="coerce")
n0 = len(df)
df = df[~(df["snap_ret"] >= df["commence"])].copy()
n1 = len(df)
df = df[~(df["over_price"].isna() | df["under_price"].isna())].copy()
n2 = len(df)
print("  in-play excluded=%d ; one-sided excluded=%d ; two-sided rows=%d"
      % (n0 - n1, n1 - n2, n2))

# --- the name-keyed dedup, and its id-keyed counterpart ------------------------------
nr = p[["player_id", "player_name", "season"]].drop_duplicates()
idx = {}
for _, sub in nr.sort_values("season").groupby("season", sort=True):
    for pid, nm in sub[["player_id", "player_name"]].drop_duplicates().itertuples(index=False):
        idx[_norm_name(nm)] = int(pid)

df["norm_name"] = df["player_name"].map(_norm_name)
df["player_id"] = df["norm_name"].map(idx)
n_unres = int(df["player_id"].isna().sum())
print("\n  normalized-exact resolution: unresolved rows=%d of %d (%.4f%%)"
      % (n_unres, len(df), 100.0 * n_unres / max(1, len(df))))
if n_unres:
    print("  unresolved names: %s"
          % df[df.player_id.isna()].player_name.value_counts().head(12).to_dict())

KN = ["game_id", "player_name", "bookmaker_key", "line"]
KI = ["game_id", "player_id", "bookmaker_key", "line"]
d_name = df[~df.duplicated(KN)].copy()
res = df[df.player_id.notna()].copy()
d_id = res[~res.duplicated(KI)].copy()
print("\n  dedup by NAME key %s  -> %d rows" % (KN, len(d_name)))
print("  dedup by ID   key %s  -> %d rows (resolved rows only, %d)"
      % (KI, len(d_id), len(res)))
# the honest comparison: apply BOTH deduplications to the SAME resolved row set
rn = d_name[d_name.player_id.notna()]
print("\n  on the identical resolved row set:")
print("    name-key survivors = %d" % len(rn))
print("    id-key   survivors = %d" % len(d_id))
print("    DELTA              = %+d" % (len(rn) - len(d_id)))
extra = len(rn) - len(d_id)
print("    direction          = %s"
      % ("DUPLICATION (name key keeps rows the id key collapses)" if extra > 0
         else ("DROP" if extra < 0 else "NONE")))
if extra:
    k = rn.groupby(["game_id", "player_id", "bookmaker_key", "line"]).size()
    off = k[k > 1]
    print("    offending (game, player_id, book, line) cells: %d" % len(off))
    for (gid, pid, bk, ln), c in off.head(20).items():
        nms = sorted(rn[(rn.game_id == gid) & (rn.player_id == pid) &
                        (rn.bookmaker_key == bk) & (rn.line == ln)].player_name.unique())
        print("       %s pid=%s %s line=%s  n=%d  spellings=%s" % (gid, pid, bk, ln, c, nms))

# the twelve, inside the priced universe
print("\n  the twelve inside the priced (2024) universe:")
for pid in AMB:
    s = res[res.player_id == pid]
    if len(s):
        print("    %-9d %-44s priced_rows=%-5d spellings_priced=%s"
              % (pid, NAME_OF[pid], len(s),
                 sorted(str(x) for x in s.player_name.dropna().unique())))
present = [pid for pid in AMB if len(res[res.player_id == pid])]
print("    identities present: %d of 12 ; carrying >1 spelling in the props feed: %d"
      % (len(present),
         sum(1 for pid in present if res[res.player_id == pid].player_name.nunique() > 1)))

# ------------------------------------------------------------------ (B) F16 coverage
B.banner("s09  (B) F16_PLAYER_PROPS -- the surface with NO stable key at source")
print("  measure_props_evidence.py joins props to box scores on normalized name + game_id.")
print("  Its own note, quoted from the file: 'no player_id exists on either props file.'")
print("  So this is not a choice of key -- it is the only key the source admits.")
print("\n  COVERAGE consequence, measured above on the same feed:")
print("    priced rows 2021-2024 (2024 only)               : %d" % len(df))
print("    resolved to a player_id by normalized-exact     : %d (%.4f%%)"
      % (len(res), 100.0 * len(res) / max(1, len(df))))
print("    unresolved (excluded and listed, never guessed) : %d" % n_unres)
print("    normalized spellings binding to >1 player_id    : 0  (s06)")
print("    -> once resolved, every downstream operation is keyed on player_id.")

json.dump({"props_sha256": B.sha256(PROPS), "props_path": PROPS,
           "rows_2021_2024": int(len(df)), "resolved": int(len(res)),
           "unresolved": int(n_unres),
           "dedup_name_survivors": int(len(rn)), "dedup_id_survivors": int(len(d_id)),
           "delta": int(extra),
           "ambiguous_identities_priced": present},
          open(os.path.join(B.OUT, "_s09.json"), "w"), indent=2)
print("\nDONE s09")
