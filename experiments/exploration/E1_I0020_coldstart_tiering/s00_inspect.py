"""E1_I0020 s00 -- INSPECT ONLY.  Reads frozen inputs read-only; writes nothing but its own log/json.

Purpose: establish exactly what columns exist in the two anchor frames, what player_bios.csv
carries, whether bios genuinely vary by season (the user's proposal depends on draft/position being
pre-game-available), and the manifest status of every input.
"""
import json, os, sys
import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
OUT = os.path.join(ROOT, r"experiments\exploration\E1_I0020_coldstart_tiering")
D076 = os.path.join(ROOT, r"experiments\exploration\E0_I0014_residual_heterogeneity")
D081 = os.path.join(ROOT, r"experiments\exploration\E0_I0015_points_skill_decomposition")
if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 200)
res = {}

def hdr(s):
    print("\n" + "=" * 100); print(s); print("=" * 100)

# ---------------------------------------------------------------- 1. manifests
hdr("1. MANIFEST STATUS OF EVERY INPUT")
inputs = {
    "analysis_frame": os.path.join(D076, "analysis_frame.parquet"),
    "decomp_frame": os.path.join(D081, "decomp_frame.parquet"),
    "player_bios": os.path.join(ROOT, r"data\reference\player_bios.csv"),
}
res["manifests"] = {}
for k, p in inputs.items():
    print("\n--- %s\n    %s  exists=%s" % (k, p, os.path.exists(p)))
    try:
        m = sk.check_manifest(p, verbose=True)
    except Exception as e:
        m = {"status": "CHECK_RAISED", "error": repr(e)}
        print("   check_manifest raised: %r" % (e,))
    res["manifests"][k] = {kk: (str(vv) if not isinstance(vv, (int, float, bool, type(None), str, list, dict)) else vv)
                           for kk, vv in (m.items() if isinstance(m, dict) else [])}
    # what sibling files exist
    d = os.path.dirname(p); b = os.path.basename(p)
    sibs = [f for f in os.listdir(d) if f.startswith(b.split(".")[0]) and f != b]
    print("   siblings sharing stem: %s" % sibs)
    res["manifests"].setdefault(k, {})["siblings"] = sibs

# ---------------------------------------------------------------- 2. analysis_frame
hdr("2. D076 analysis_frame.parquet")
af = pd.read_parquet(inputs["analysis_frame"])
print("shape=%s" % (af.shape,))
print("seasons=%s  gdate range=%s..%s" % (sorted(af["season"].unique()), af["gdate"].min(), af["gdate"].max()))
print("\ncolumns (%d):" % af.shape[1])
for c in af.columns:
    print("   %-42s %-12s nn=%6d  ex=%s" % (c, str(af[c].dtype), af[c].notna().sum(), repr(af[c].dropna().iloc[0])[:44] if af[c].notna().any() else "-"))
res["analysis_frame_cols"] = list(af.columns)
res["analysis_frame_shape"] = list(af.shape)

# ---------------------------------------------------------------- 3. decomp_frame
hdr("3. D081 decomp_frame.parquet")
df = pd.read_parquet(inputs["decomp_frame"])
print("shape=%s" % (df.shape,))
print("\ncolumns (%d):" % df.shape[1])
for c in df.columns:
    print("   %-42s %-12s nn=%6d" % (c, str(df[c].dtype), df[c].notna().sum()))
res["decomp_frame_cols"] = list(df.columns)
res["decomp_frame_shape"] = list(df.shape)

# ---------------------------------------------------------------- 4. bios
hdr("4. data/reference/player_bios.csv")
bio = pd.read_csv(inputs["player_bios"])
print("shape=%s" % (bio.shape,))
print(bio.dtypes)
print("\nhead:")
print(bio.head(8))
print("\nseason counts:")
print(bio["season"].value_counts().sort_index())
res["bios_shape"] = list(bio.shape)
res["bios_cols"] = list(bio.columns)
res["bios_season_counts"] = {int(k): int(v) for k, v in bio["season"].value_counts().sort_index().items()}

hdr("4b. DOES player_bios VARY BY SEASON, OR IS IT A REPLICATED CURRENT-STATE PULL?")
# A replicated current-state pull would give every player the SAME age in every season.
multi = bio.groupby("player_id").filter(lambda g: g["season"].nunique() > 1)
print("players appearing in >1 season: %d  (rows %d)" % (multi["player_id"].nunique(), len(multi)))
for col in ["age", "height_inches", "weight_lbs", "position_raw", "draft_number", "draft_year", "college", "country"]:
    if col not in bio.columns:
        continue
    g = multi.groupby("player_id")[col].nunique(dropna=False)
    frac_vary = float((g > 1).mean()) if len(g) else float("nan")
    print("   %-16s distinct-values-per-player>1 in %.1f%% of multi-season players" % (col, 100 * frac_vary))
    res.setdefault("bios_within_player_variation", {})[col] = frac_vary

# age should increase by ~1 per season if per-season
sub = multi.sort_values(["player_id", "season"])
sub["dage"] = sub.groupby("player_id")["age"].diff()
sub["dseason"] = sub.groupby("player_id")["season"].diff()
ok = sub["dage"].notna() & sub["dseason"].notna()
print("\n  age delta per +1 season (consecutive pairs only):")
cons = sub[ok & (sub["dseason"] == 1)]
print(cons["dage"].value_counts(dropna=False).sort_index())
res["age_delta_value_counts"] = {str(k): int(v) for k, v in cons["dage"].value_counts().sort_index().items()}

print("\n  draft_year / draft_round / draft_number constancy within player (SHOULD be constant):")
for col in ["draft_year", "draft_round", "draft_number"]:
    g = multi.groupby("player_id")[col].nunique(dropna=False)
    print("     %-14s frac players with >1 distinct: %.4f" % (col, float((g > 1).mean())))

print("\n  position_raw values:")
print(bio["position_raw"].value_counts(dropna=False))
res["position_counts"] = {str(k): int(v) for k, v in bio["position_raw"].value_counts(dropna=False).items()}
print("\n  draft_round values:")
print(bio["draft_round"].value_counts(dropna=False).sort_index())
print("\n  draft_number describe:")
print(bio["draft_number"].describe())
print("\n  cpi_enriched / source:")
for c in ["source", "cpi_enriched"]:
    if c in bio.columns:
        print("   %s: %s" % (c, dict(bio[c].value_counts(dropna=False))))

# ---------------------------------------------------------------- 5. join coverage
hdr("5. BIOS JOIN COVERAGE ONTO THE ANALYSIS FRAME")
key = af[["season", "player_id"]].drop_duplicates()
print("distinct (season,player_id) in analysis_frame: %d" % len(key))
m = key.merge(bio, on=["season", "player_id"], how="left", indicator=True)
print(m["_merge"].value_counts())
res["bios_join_season_player"] = {str(k): int(v) for k, v in m["_merge"].value_counts().items()}
# player-level fallback
bp = bio.sort_values("season").groupby("player_id").first().reset_index()
m2 = key.merge(bp[["player_id", "draft_year", "draft_round", "draft_number", "position_raw"]], on="player_id", how="left", indicator=True)
print("\nplayer-level (any-season) fallback join:")
print(m2["_merge"].value_counts())
res["bios_join_player_only"] = {str(k): int(v) for k, v in m2["_merge"].value_counts().items()}
print("\nnon-null rate of key fields after season-level join:")
for c in ["draft_year", "draft_round", "draft_number", "position_raw"]:
    print("   %-14s %.4f" % (c, float(m[c].notna().mean())))

with open(os.path.join(OUT, "_s00.json"), "w") as fh:
    json.dump(res, fh, indent=2, default=str)
print("\nWROTE _s00.json")
