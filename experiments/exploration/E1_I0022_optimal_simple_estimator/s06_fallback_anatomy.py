"""E1_I0022 STEP 6 -- ANATOMY OF THE CHAMPION'S DEFICIT.

s05 found the champion's entire pooled deficit is concentrated on the rows where it emits a
FALLBACK.  This step characterises those rows, and prices the one obvious repair: keep the champion
wherever it is actually modelling, and hand the fallback rows to the tuned simple estimator.

DISCLOSURE.  The fallback split was chosen AFTER seeing the tier results -- it is POST HOC and is
labelled as such throughout.  It is not a tuned hyperparameter (nothing is re-selected), and the
switch variable `<target>__is_fallback` is emitted by the champion's own inference before the game,
so the hybrid is implementable; but the DECISION to look at this split came from the data and the
hybrid's headline must be read as descriptive, not as a validated result.
"""
import json
import os

import numpy as np
import pandas as pd

import ose_base as B

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 80)

f = B.load_frame(verbose=True)
codes, starts, ns = B.group_bounds(f)
z = np.load(os.path.join(B.OUT, "best_simple_forecasts.npz"))
EST = {t: z[t] for t in B.TARGETS}
WF, tier, stratum = z["wf"], z["tier"], z["stratum"]
TIER_NAMES = ["0", "1-2", "3-7", "8-14", "15-24", "25+"]
YCOL = {"pts": "y_pts", "minutes": "y_minutes", "fga": "y_fga", "ppm": "r_ppm"}
CHAMPC = {"pts": "pts__pred_point", "minutes": "minutes__pred_point",
          "fga": "fga__pred_point", "ppm": "mdl_ppm"}
OUT = {}

B.hdr("STEP 6a -- WHO ARE THE FALLBACK ROWS?")
fb = f["pts__is_fallback"].to_numpy(bool)
lv = f["pts__fallback_level"].to_numpy(int)
gp = f["pl_games_prior"].to_numpy(float)
ct = pd.crosstab(pd.Series(np.array(TIER_NAMES)[tier][WF], name="prior_appearance_tier"),
                 pd.Series(np.where(fb[WF], "FALLBACK", "modelled"), name="champion_state"))
ct = ct.reindex(TIER_NAMES)
print(ct.to_string())
print("\n  fallback LEVEL distribution on WF rows: %s"
      % dict(zip(*[x.tolist() for x in np.unique(lv[WF], return_counts=True)])))
print("  WF rows: %d   fallback: %d (%.2f%%)" % (WF.sum(), fb[WF].sum(), 100 * fb[WF].mean()))
print("\n  On fallback rows the champion emits how many DISTINCT point forecasts?")
for t in B.TARGETS[:3]:
    v = f[CHAMPC[t]].to_numpy(float)
    m = WF & fb
    print("    %-8s n=%d  distinct values=%d  sd=%.4f   |  on modelled rows: distinct=%d sd=%.4f"
          % (t, m.sum(), len(np.unique(np.round(v[m], 6))), v[m].std(),
             len(np.unique(np.round(v[WF & ~fb], 6))), v[WF & ~fb].std()))
ct.to_csv(os.path.join(B.OUT, "fallback_by_tier.csv"))
OUT["fallback_rows_wf"] = int(fb[WF].sum())
OUT["fallback_share_wf"] = float(fb[WF].mean())
OUT["fallback_levels_wf"] = {str(k): int(v) for k, v in
                             zip(*[x.tolist() for x in np.unique(lv[WF], return_counts=True)])}

B.hdr("STEP 6b -- THE DEFICIT SPLIT: fallback rows vs modelled rows")
rows = []
print("  %-8s %-26s %6s %11s %11s %13s %10s" %
      ("target", "slice", "n", "champ MAE", "best simple", "CHAMP SKILL", "p"))
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    ch = f[CHAMPC[t]].to_numpy(float)
    ec, ee = np.abs(y - ch), np.abs(y - EST[t])
    for nm, m in [("pooled_wf", WF), ("champion_FALLBACK_rows", WF & fb),
                  ("champion_MODELLED_rows", WF & ~fb),
                  ("modelled AND decision stratum", WF & ~fb & stratum),
                  ("modelled AND >=3 priors", WF & ~fb & (gp >= 3))]:
        a, b = float(ec[m].mean()), float(ee[m].mean())
        r = B.block_signflip_test((ec - ee)[m], codes[m], n_draws=4000, seed=B.SEED)
        rows.append(dict(target=t, slice=nm, n=int(m.sum()), champ_mae=a, best_simple_mae=b,
                         champ_skill_vs_best_simple=float(1 - a / b),
                         mean_abs_err_diff=r["mean_diff"], p_two_sided_blockflip=r["p_two_sided_blockflip"]))
        print("  %-8s %-26s %6d %11.5f %11.5f %+12.4f%% %10.4f"
              % (t, nm, m.sum(), a, b, 100 * (1 - a / b), r["p_two_sided_blockflip"]))
    print()
pd.DataFrame(rows).to_csv(os.path.join(B.OUT, "fallback_split.csv"), index=False)

B.hdr("STEP 6c -- POST HOC (declared): hybrid = champion where it models, estimator where it falls back")
print("  The switch is the champion's OWN pre-game `<target>__is_fallback` flag, so this is")
print("  implementable.  But the split was chosen after seeing the tier table -- DESCRIPTIVE ONLY.\n")
hy = []
print("  %-8s %11s %11s %11s %13s %13s" %
      ("target", "champ MAE", "best simple", "hybrid MAE", "hybrid vs champ", "hybrid vs est"))
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    ch = f[CHAMPC[t]].to_numpy(float)
    fbt = f["%s__is_fallback" % t].to_numpy(bool) if t != "ppm" else (
        f["pts__is_fallback"].to_numpy(bool) | f["minutes__is_fallback"].to_numpy(bool))
    hyb = np.where(fbt, EST[t], ch)
    a = float(np.abs(y - ch)[WF].mean())
    b = float(np.abs(y - EST[t])[WF].mean())
    h = float(np.abs(y - hyb)[WF].mean())
    hy.append(dict(target=t, n=int(WF.sum()), champ_mae=a, best_simple_mae=b, hybrid_mae=h,
                   n_switched=int((fbt & WF).sum()),
                   hybrid_skill_vs_champ=float(1 - h / a), hybrid_skill_vs_best_simple=float(1 - h / b),
                   champ_skill_vs_best_simple=float(1 - a / b)))
    print("  %-8s %11.5f %11.5f %11.5f %+12.4f%% %+12.4f%%"
          % (t, a, b, h, 100 * (1 - h / a), 100 * (1 - h / b)))
pd.DataFrame(hy).to_csv(os.path.join(B.OUT, "hybrid_postocc.csv"), index=False)

json.dump(OUT, open(os.path.join(B.OUT, "_s06.json"), "w"), indent=2, default=str)
print("\nDONE s06")
