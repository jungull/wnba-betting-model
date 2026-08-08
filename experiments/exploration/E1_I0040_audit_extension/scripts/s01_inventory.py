"""S01 -- Inventory the 30 unaudited screens.

For each of the 30 screens outside E1_I0036's census:
  * every .csv that looks like a CELL TABLE (has a p-value column and is not a raw draw dump)
  * which null-scheme columns it carries (within-entity / between-entity / row)
  * whether a null mean / null sd is recorded
  * whether the screen's source code contains the BANNED `max(p_a, p_b)` combination signature
  * whether raw permutation draws exist, and whether they were stored STANDARDISED
Read-only outside this screen's own directory.
"""
import os, re, json, io
import pandas as pd
import numpy as np

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CENSUS_SCREENS = {
    "E0_I0014_residual_heterogeneity", "E0_I0016_efficiency_predictors",
    "E0_I0017_shot_quality_efficiency", "E0_I0019_availability_forecast",
    "E0_I0024_reb_ast_characterisation", "E0_I0029_freethrow_hurdle",
    "E1_I0018_teammate_volume_channel", "E1_I0023_usage_defence_interaction",
}
# this screen itself, and the two audit screens whose outputs we are extending, are not targets
SELF = {"E1_I0040_audit_extension", "E1_I0038_within_entity_null_audit",
        "AUDIT_baseline_provenance", "AUDIT_SCREEN_INTEGRITY", "IDEATION_QUEUE",
        "MANIFEST_REMEDIATION"}

# the 30, taken from E1_I0038/CENSUS_COVERAGE.csv screen column minus the 8 census screens
cov = pd.read_csv(os.path.join(EXPL, "E1_I0038_within_entity_null_audit", "CENSUS_COVERAGE.csv"))
ALL38 = sorted(cov["screen"].unique())
TARGETS = [s for s in ALL38 if s not in CENSUS_SCREENS]
assert len(TARGETS) == 30, (len(TARGETS), TARGETS)

WITHIN_PAT = re.compile(r"cyclic|within[_ ]?(player|entity|block|group|shuffle)|shift_within|within_shuffle|SCHEME_WITHIN", re.I)
BETWEEN_PAT = re.compile(r"eswap|entity_swap|pswap|between[_ ]?(entity|block|player)|block_reassign|sign[_ ]?flip|team_?game|SCHEME_BETWEEN|swap", re.I)
ROW_PAT = re.compile(r"row[_ ]?(level|null|shuffle)|free_shuffle|SCHEME_ROW", re.I)
P_PAT = re.compile(r"(^|_)p($|_)|p_value|pval|^p[A-Z_]|_p$|family_wise_p|p_two_sided|p_vs_", re.I)
NULLMEAN_PAT = re.compile(r"null_mean|_mean_null|nullmean", re.I)
NULLSD_PAT = re.compile(r"null_sd|null_p95|_sd_null|nullsd", re.I)
OBS_PAT = re.compile(r"^(obs|observed)|_obs$|dr2|delta_r2|dR2|ratio|spread|corr|beta|_t$|stat", re.I)

# the BANNED signature: p = max(p_a, p_b)
MAX_SIG = re.compile(r"max\s*\(\s*[^)]*\bp[_a-z0-9]*\b[^)]*,[^)]*\bp[_a-z0-9]*\b[^)]*\)", re.I)
MAXT_SIG = re.compile(r"p_?(correct|decision|familywise|family_wise|final)[a-z_]*\s*=\s*.*\bmax\b", re.I)
NPMAX_SIG = re.compile(r"np\.max(imum)?\s*\(\s*\[?\s*p_", re.I)

rows_tables, rows_code, rows_npz, rows_screen = [], [], [], []

for sc in TARGETS:
    d = os.path.join(EXPL, sc)
    if not os.path.isdir(d):
        rows_screen.append(dict(screen=sc, exists=False))
        continue
    n_csv = n_cell = 0
    has_within = has_between = has_row = False
    max_hits_total = 0
    # ---------- csv tables ----------
    for root, _dirs, files in os.walk(d):
        for fn in files:
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, EXPL).replace("\\", "/")
            if fn.lower().endswith(".csv"):
                n_csv += 1
                try:
                    head = pd.read_csv(fp, nrows=5)
                except Exception as e:
                    rows_tables.append(dict(screen=sc, file=rel, rows=-1, error=str(e)[:80]))
                    continue
                cols = list(head.columns)
                colstr = "|".join(cols)
                is_draw_dump = ("draw" in colstr.lower() and len(head.columns) <= 8 and
                                any(c.lower() in ("draw", "draw_id", "rep", "i") for c in cols))
                try:
                    nrows = sum(1 for _ in open(fp, "r", encoding="utf-8", errors="replace")) - 1
                except Exception:
                    nrows = -1
                pcols = [c for c in cols if P_PAT.search(c)]
                wcols = [c for c in cols if WITHIN_PAT.search(c)]
                bcols = [c for c in cols if BETWEEN_PAT.search(c)]
                rcols = [c for c in cols if ROW_PAT.search(c)]
                mcols = [c for c in cols if NULLMEAN_PAT.search(c)]
                scols = [c for c in cols if NULLSD_PAT.search(c)]
                if pcols and not is_draw_dump:
                    n_cell += 1
                has_within |= bool(wcols); has_between |= bool(bcols); has_row |= bool(rcols)
                rows_tables.append(dict(
                    screen=sc, file=rel, rows=nrows, ncols=len(cols),
                    is_draw_dump=is_draw_dump,
                    p_cols="|".join(pcols), within_cols="|".join(wcols),
                    between_cols="|".join(bcols), row_cols="|".join(rcols),
                    null_mean_cols="|".join(mcols), null_sd_cols="|".join(scols),
                    all_cols=colstr[:900], error=""))
            elif fn.lower().endswith(".npz"):
                try:
                    z = np.load(fp, allow_pickle=True)
                    keys = list(z.files)
                    std = any(("standard" in k.lower() or "zscore" in k.lower() or "_z" == k[-2:].lower())
                              for k in keys)
                    # empirical standardisation test: mean ~0 and sd ~1 on every numeric key
                    emp = []
                    for k in keys[:40]:
                        a = z[k]
                        if getattr(a, "dtype", None) is not None and np.issubdtype(a.dtype, np.number) and a.size >= 20:
                            emp.append((k, float(np.nanmean(a)), float(np.nanstd(a))))
                    emp_std = bool(emp) and all(abs(m) < 1e-8 and abs(s - 1) < 1e-6 for _k, m, s in emp)
                    rows_npz.append(dict(screen=sc, file=rel, n_keys=len(keys),
                                         keys="|".join(keys[:25]),
                                         name_says_standardised=std,
                                         empirically_standardised=emp_std,
                                         sample_stats=json.dumps(emp[:6])))
                except Exception as e:
                    rows_npz.append(dict(screen=sc, file=rel, n_keys=-1, keys="",
                                         name_says_standardised=False,
                                         empirically_standardised=False,
                                         sample_stats="ERR:" + str(e)[:60]))
            elif fn.lower().endswith(".py"):
                try:
                    src = open(fp, "r", encoding="utf-8", errors="replace").read()
                except Exception:
                    continue
                hits = []
                for ln, line in enumerate(src.splitlines(), 1):
                    if line.lstrip().startswith("#"):
                        continue
                    if MAX_SIG.search(line) or MAXT_SIG.search(line) or NPMAX_SIG.search(line):
                        hits.append((ln, line.strip()[:200]))
                if hits:
                    max_hits_total += len(hits)
                    for ln, line in hits[:12]:
                        rows_code.append(dict(screen=sc, file=rel, line=ln, code=line))
    rows_screen.append(dict(screen=sc, exists=True, n_csv=n_csv, n_cell_tables=n_cell,
                            has_within_col=has_within, has_between_col=has_between,
                            has_row_col=has_row, max_signature_hits=max_hits_total))

pd.DataFrame(rows_screen).to_csv(os.path.join(HERE, "INVENTORY_SCREENS.csv"), index=False)
pd.DataFrame(rows_tables).to_csv(os.path.join(HERE, "INVENTORY_TABLES.csv"), index=False)
pd.DataFrame(rows_code).to_csv(os.path.join(HERE, "MAX_SIGNATURE_HITS.csv"), index=False)
pd.DataFrame(rows_npz).to_csv(os.path.join(HERE, "INVENTORY_NPZ.csv"), index=False)

print("targets:", len(TARGETS))
print(pd.DataFrame(rows_screen).to_string())
print("\n--- max() signature hits ---")
mh = pd.DataFrame(rows_code)
print(mh.to_string() if len(mh) else "(none)")
print("\n--- npz archives ---")
nz = pd.DataFrame(rows_npz)
print(nz[["screen", "file", "n_keys", "name_says_standardised", "empirically_standardised"]].to_string()
      if len(nz) else "(none)")
print("\n--- tables carrying a within-entity null column ---")
tt = pd.DataFrame(rows_tables)
sel = tt[(tt.get("within_cols", "").astype(str) != "") & (~tt["is_draw_dump"].fillna(False))]
print(sel[["screen", "file", "rows", "within_cols", "p_cols"]].to_string() if len(sel) else "(none)")
