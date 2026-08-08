"""S05 -- MEASURE the between-entity variance share for every UNDETERMINABLE cell, and RECOVER
null means / sds from raw draw archives already on disk.

Two principles from E1_I0038, applied not rederived:
  * a variance share is a MEASUREMENT (E1_I0038 var_share_source=COMPUTED) -- it is not a refit and
    it is not a name lookup. Five findings in this programme died to substring matching.
  * before computing anything, look for the number already on disk.

Every frame here is a FROZEN 2021-2024 exploration artefact opened READ-ONLY. No 2025/26 file is
touched: each frame is asserted to carry no season > 2024 and no date >= 2025-01-01 before use.
"""
import os, json, glob
import numpy as np
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def assert_partition(df, label):
    for c in df.columns:
        lc = c.lower()
        if lc in ("season", "yr", "year"):
            v = pd.to_numeric(df[c], errors="coerce").dropna()
            if len(v) and v.max() > 2024:
                raise SystemExit("PARTITION VIOLATION in %s: %s max %s" % (label, c, v.max()))
        if "date" in lc:
            v = pd.to_datetime(df[c], errors="coerce").dropna()
            if len(v) and v.max() >= pd.Timestamp("2025-01-01"):
                raise SystemExit("PARTITION VIOLATION in %s: %s max %s" % (label, c, v.max()))
    return df

def var_share_between(v, codes):
    """Share of Var(v) carried by the entity means. Identical formula to
    E0_I0015/s03_mechanism_and_abstention.py:253 var_share_between and to
    E0_I0014/s04_screen.py's `vsb`, so the number is comparable to the programme's own."""
    v = np.asarray(v, float)
    ok = np.isfinite(v)
    v, c = v[ok], np.asarray(codes)[ok]
    if v.size < 3:
        return np.nan
    tot = float(np.var(v))
    if tot <= 0:
        return np.nan
    df = pd.DataFrame(dict(v=v, c=c))
    gm = df.groupby("c")["v"].transform("mean").to_numpy()
    return float(np.var(gm) / tot)

OUT = []
def rec(**k):
    OUT.append(k)

# ============================================================ E1_I0030 : is_home at player_id
pf = os.path.join(EXPL, "E1_I0030_home_advantage_accounting", "_player_frame.parquet")
f = assert_partition(pd.read_parquet(pf), "E1_I0030/_player_frame")
print("E1_I0030 player frame:", f.shape, "| cols with home:",
      [c for c in f.columns if "home" in c.lower()][:8])
if "is_home" in f.columns and "player_id" in f.columns:
    v = var_share_between(f["is_home"].to_numpy(float), f["player_id"].to_numpy())
    print("  MEASURED between-player variance share of is_home = %.6f" % v)
    rec(screen="E1_I0030_home_advantage_accounting", cell="heterogeneity.csv (all 4 targets)",
        candidate="is_home", null_entity="player_id", var_share_between=v,
        n_rows=int(len(f)), source="COMPUTED on E1_I0030/_player_frame.parquet (frozen, read-only)")

# ============================================================ E1_I0030 : travel arms at team_season
tf = os.path.join(EXPL, "E1_I0030_home_advantage_accounting", "_team_frame.parquet")
t = assert_partition(pd.read_parquet(tf), "E1_I0030/_team_frame")
print("\nE1_I0030 team frame:", t.shape)
travel_cols = [c for c in t.columns if any(k in c.lower() for k in
                                           ("east", "west", "zone", "travel", "tz"))]
print("  travel-ish cols:", travel_cols)
key = None
for cand in (["season", "team_id"], ["team_season"], ["season", "tm"]):
    if all(c in t.columns for c in cand):
        key = cand
        break
if key and travel_cols:
    codes = t[key].astype(str).agg("|".join, axis=1) if len(key) > 1 else t[key[0]].astype(str)
    for c in travel_cols:
        try:
            v = var_share_between(pd.to_numeric(t[c], errors="coerce").to_numpy(float), codes)
        except Exception:
            continue
        if np.isfinite(v):
            print("  MEASURED between-%s share of %-24s = %.6f" % ("+".join(key), c, v))
            rec(screen="E1_I0030_home_advantage_accounting", cell="travel_directional.csv",
                candidate=c, null_entity="+".join(key), var_share_between=v, n_rows=int(len(t)),
                source="COMPUTED on E1_I0030/_team_frame.parquet (frozen, read-only)")

# ============================================================ E1_I0031 : plus-minus at player_season
af = os.path.join(EXPL, "E1_I0031_rapm_as_prior", "analysis_frame.parquet")
a = assert_partition(pd.read_parquet(af), "E1_I0031/analysis_frame")
print("\nE1_I0031 analysis frame:", a.shape)
pmcols = [c for c in a.columns if c.lower().startswith("pm") or "plusminus" in c.lower()
          or "plus_minus" in c.lower()]
print("  plus-minus cols:", pmcols[:12])
kcands = [k for k in (["player_id", "season"], ["player_season"]) if all(c in a.columns for c in k)]
if pmcols and kcands:
    key = kcands[0]
    codes = a[key].astype(str).agg("|".join, axis=1) if len(key) > 1 else a[key[0]].astype(str)
    for c in pmcols:
        v = var_share_between(pd.to_numeric(a[c], errors="coerce").to_numpy(float), codes)
        if np.isfinite(v):
            print("  MEASURED between-player_season share of %-26s = %.6f" % (c, v))
            rec(screen="E1_I0031_rapm_as_prior", cell="plusminus_separate.csv", candidate=c,
                null_entity="player_season", var_share_between=v, n_rows=int(len(a)),
                source="COMPUTED on E1_I0031/analysis_frame.parquet (frozen, read-only)")

# ============================================================ E1_I0021 : the named highest-risk screen
# its regressors live in D085's and D089's frozen frames; measure the between-player share of each
for lbl, rel in [("D085", "E0_I0016_efficiency_predictors/screen_frame.parquet"),
                 ("D089", "E1_I0018_teammate_volume_channel/screen_frame.parquet")]:
    p = os.path.join(EXPL, rel.replace("/", os.sep))
    if not os.path.exists(p):
        continue
    fr = pd.read_parquet(p)
    if "season" in fr.columns:
        fr = fr[pd.to_numeric(fr["season"], errors="coerce") <= 2024]
    assert_partition(fr, rel)
    print("\nE1_I0021 source frame %s (%s): %s" % (lbl, rel, fr.shape))
    want = ["refA_ppm", "refA_ppm_floor", "A01_opp_efg_allowed", "A02_opp_ts_allowed",
            "A10_opp_defrtg", "P01_c04_prevgame", "O01_own_usg_pg", "G01_noise",
            "G01_noise_tvframe"]
    have = [c for c in want if c in fr.columns]
    if "player_id" not in fr.columns or not have:
        print("   (no player_id or none of the named regressors present here)")
        continue
    for c in have:
        v = var_share_between(pd.to_numeric(fr[c], errors="coerce").to_numpy(float),
                              fr["player_id"].to_numpy())
        print("   MEASURED between-player share of %-22s = %.6f" % (c, v))
        rec(screen="E1_I0021_heterogeneity_diagnostic", cell="pooling_diagnostic.csv",
            candidate=c, null_entity="player_id", var_share_between=v, n_rows=int(len(fr)),
            source="COMPUTED on %s (frozen, read-only)" % rel)

M = pd.DataFrame(OUT)
M.to_csv(os.path.join(HERE, "MEASURED_VARIANCE_SHARES.csv"), index=False)
print("\nwrote MEASURED_VARIANCE_SHARES.csv  rows=%d" % len(M))
