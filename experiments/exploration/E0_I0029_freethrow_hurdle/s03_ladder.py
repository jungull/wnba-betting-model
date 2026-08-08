"""E0_I0029 s03 -- STEP 1: THE ORACLE LADDER, PER HURDLE STAGE.

THE CENTRAL QUESTION.  How predictable is each stage of the free-throw hurdle from strictly
prior-games-only information, against a MATCHED prior-history reference, and how much is
irreducible even to an oracle knowing the player and their realised exposure?

LADDER RUNGS -- D081/D097 shape, so the answer is comparable with the rest of the ledger.
    HONEST (strictly prior-games-only, pre-game attainable)
      REF  expanding prior mean of the target        <- THE MATCHED REFERENCE
      H1   EWMA of the prior target (halflife 5)
      H2   trailing-5 prior mean
      H3   (FLOORED prior per-exposure rate) x (prior mean exposure)
      H4   OLS on the full B_COMPLETE base, WALK-FORWARD by season   <- best reachable here
    ORACLE (LABELLED; conditions on outcomes; NEVER pre-game attainable)
      O1   the player's SEASON-MEAN target
      O2   ACTUAL exposure x SEASON-MEAN per-exposure rate           <- THE HEADLINE
      O3   within-player-season OLS of the target on ACTUAL exposure
      O4   ACTUAL exposure x FLOORED PRIOR rate
      O5   prior mean exposure x SEASON-MEAN rate

EXPOSURE is MINUTES for stages A, B and the composites, and REALISED FTA for stage C, because
conversion is a per-ATTEMPT rate and minutes are not its exposure.  Declared in the prereg.

THE HEADLINE NUMBER is 1 - R2(O2): the share of the stage's variance that is irreducible even to
an estimator handed the player's season-long rate AND their realised exposure.

D099 DENOMINATOR RULE.  Stages B and C are computed on the fta>0 SUBSET and every row of the
output carries `denominator` = FULL_STRATUM or CONDITIONAL_SUBSET.  These R2s are NOT compared
across stages here.  The cross-stage comparison happens ONLY in s04, on SST(ftm) over the full
stratum.  y_pts is carried through the identical machinery as a CALIBRATION ANCHOR -- if it does
not reproduce D081/D097's ~51.7% irreducible on this frame, the whole ladder is off-scale.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ft_base import (BASE_COLS, HEADLINE_SEASONS, OUT, TARGETS, TARGET_ORDER, assert_partition,
                     basecols_for, hdr, jsonable, mae, r2_plain, rmse)

rep = {}
F = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F)
F = F.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
print("  frame %s  headline seasons %s" % (F.shape, list(HEADLINE_SEASONS)))


def wf_ols(d, target, basecols):
    """Season s is scored by an OLS fitted on seasons < s ONLY.  2021 has no earlier season and is
    unscorable; the headline is 2022-2024 in any case.  This is the ONLY fitting in the ladder and
    it never touches the champion."""
    yhat = np.full(len(d), np.nan)
    X = d[basecols].to_numpy(float)
    y = d[target].to_numpy(float)
    seasons = d["season"].to_numpy()
    for s in sorted(set(seasons.tolist())):
        tr, te = seasons < s, seasons == s
        if tr.sum() < 200:
            continue
        Xtr = np.column_stack([np.ones(int(tr.sum())), X[tr]])
        ok = np.isfinite(Xtr).all(axis=1) & np.isfinite(y[tr])
        if ok.sum() < 200:
            continue
        beta, *_ = np.linalg.lstsq(Xtr[ok], y[tr][ok], rcond=None)
        yhat[te] = np.column_stack([np.ones(int(te.sum())), X[te]]) @ beta
    return yhat


# =====================================================================================
hdr("1. THE LADDER, PER STAGE")
# =====================================================================================
rows = []
SUBSETS = [
    ("ALL (2022-2024)", F["season"].isin(HEADLINE_SEASONS).to_numpy(), False),
    ("DECISION (>=8 prior, >=24 trail-5 min)",
     (F["season"].isin(HEADLINE_SEASONS) & (F["DECISION"] == 1)).to_numpy(), False),
    ("ALL incl 2021 (power sensitivity)", np.ones(len(F), bool), False),
]

for label, mask, _ in SUBSETS:
    for t in TARGET_ORDER:
        meta = TARGETS[t]
        m = mask.copy()
        if meta["rowset"] == "CONDITIONAL":
            m = m & (F["COND"] == 1).to_numpy()
        d = F.loc[m].copy()
        if len(d) < 100:
            continue
        y = d[t].to_numpy(float)
        expo_act = d[meta["exposure"]].to_numpy(float)          # ORACLE exposure (realised)
        expo_pri = d["ref_mean_exposure__" + t].to_numpy(float)  # honest prior exposure
        denom = "CONDITIONAL_SUBSET(fta>0)" if meta["rowset"] == "CONDITIONAL" else "FULL_STRATUM"

        preds = {
            ("REF  expanding prior mean (MATCHED)", "honest"): d["ref_mean__" + t].to_numpy(float),
            ("H1   EWMA prior (hl=5)", "honest"): d["ref_ewma__" + t].to_numpy(float),
            ("H2   trailing-5 prior mean", "honest"): d["ref_trail5__" + t].to_numpy(float),
            ("H3   prior rate(floored) x prior exposure", "honest"):
                d["ref_rate_x_min__" + t].to_numpy(float),
            ("H4   walk-forward OLS on B_COMPLETE", "honest"):
                wf_ols(d, t, basecols_for("B_COMPLETE", t)),
            ("O1   SEASON-MEAN target", "ORACLE"): d["ORACLE_seasonmean__" + t].to_numpy(float),
            ("O2   ACTUAL exposure x SEASON-MEAN rate", "ORACLE"):
                expo_act * d["ORACLE_seasonrate__" + t].to_numpy(float),
            ("O4   ACTUAL exposure x prior rate(floored)", "ORACLE"):
                expo_act * d["ref_rate_floored__" + t].to_numpy(float),
            ("O5   prior exposure x SEASON-MEAN rate", "ORACLE"):
                expo_pri * d["ORACLE_seasonrate__" + t].to_numpy(float),
        }
        # O3: within-player-season OLS of the target on ACTUAL exposure (in-sample, ORACLE)
        o3 = np.full(len(d), np.nan)
        pos = {ix: k for k, ix in enumerate(d.index)}
        for _, g in d.groupby(["season", "player_id"], sort=False):
            ii = [pos[x] for x in g.index]
            xx = g[meta["exposure"]].to_numpy(float)
            yy = g[t].to_numpy(float)
            if len(g) < 3 or np.std(xx) == 0:
                o3[ii] = yy.mean()
                continue
            A = np.column_stack([np.ones(len(g)), xx])
            b, *_ = np.linalg.lstsq(A, yy, rcond=None)
            o3[ii] = A @ b
        preds[("O3   within-player-season OLS on ACTUAL exposure", "ORACLE")] = o3

        for (nm, kind), p in preds.items():
            ok = np.isfinite(y) & np.isfinite(p)
            rows.append(dict(subset=label, target=t, stage=meta["stage"], denominator=denom,
                             exposure=meta["exposure"], n=int(ok.sum()), rung=nm, kind=kind,
                             mae=mae(y[ok], p[ok]), rmse=rmse(y[ok], p[ok]),
                             r2=r2_plain(y[ok], p[ok]), sd_y=float(np.std(y[ok], ddof=1)),
                             coverage=float(ok.mean())))

L = pd.DataFrame(rows)
L.to_csv(os.path.join(OUT, "oracle_ladder_ft.csv"), index=False)
L[L["kind"] == "honest"].to_csv(os.path.join(OUT, "baseline_accuracy.csv"), index=False)

for label in L["subset"].unique():
    print("\n" + "-" * 104)
    print("  SUBSET: %s" % label)
    print("-" * 104)
    for t in TARGET_ORDER:
        sub = L[(L["subset"] == label) & (L["target"] == t)]
        if not len(sub):
            continue
        print("\n   %-13s stage %-6s  n=%-6d sd_y=%.4f  exposure=%-7s  denominator=%s"
              % (t, sub["stage"].iloc[0], sub["n"].max(), sub["sd_y"].iloc[0],
                 sub["exposure"].iloc[0], sub["denominator"].iloc[0]))
        print("     %-52s %-7s %8s %8s %9s" % ("rung", "kind", "MAE", "RMSE", "R2"))
        for _, r in sub.iterrows():
            print("     %-52s %-7s %8.4f %8.4f %9.5f"
                  % (r["rung"], r["kind"], r["mae"], r["rmse"], r["r2"]))

# =====================================================================================
hdr("2. HEADLINE -- IRREDUCIBLE SHARE AND REACHABLE HEADROOM, PER STAGE")
# =====================================================================================
summ = []
for label in L["subset"].unique():
    for t in TARGET_ORDER:
        sub = L[(L["subset"] == label) & (L["target"] == t)].set_index("rung")
        if not len(sub):
            continue
        hon = sub[sub["kind"] == "honest"]["r2"]
        g = lambda pfx: float(sub.loc[[i for i in sub.index if i.startswith(pfx)][0], "r2"])
        summ.append(dict(
            subset=label, target=t, stage=sub["stage"].iloc[0],
            denominator=sub["denominator"].iloc[0], n=int(sub["n"].max()),
            sd_y=float(sub["sd_y"].iloc[0]),
            r2_REF_matched=g("REF"), best_honest_rung=hon.idxmax(), r2_best_honest=float(hon.max()),
            r2_O1_seasonmean=g("O1"), r2_O2_oracle=g("O2"), r2_O3_oracle=g("O3"),
            r2_O5_semioracle=g("O5"),
            IRREDUCIBLE_share_even_to_O2=1.0 - g("O2"),
            IRREDUCIBLE_share_even_to_O3=1.0 - g("O3"),
            headroom_O2_minus_best_honest=g("O2") - float(hon.max()),
            headroom_O1_minus_REF=g("O1") - g("REF")))
S = pd.DataFrame(summ)
S.to_csv(os.path.join(OUT, "ladder_summary.csv"), index=False)

for label in S["subset"].unique():
    print("\n  SUBSET: %s" % label)
    print("   %-13s %-6s %6s %8s %9s %9s %9s %12s %11s"
          % ("target", "stage", "n", "sd_y", "R2 REF", "R2 best", "R2 O2", "IRREDUCIBLE", "headroom"))
    print("   %-13s %-6s %6s %8s %9s %9s %9s %12s %11s"
          % ("", "", "", "", "matched", "honest", "ORACLE", "even to O2", "O2-besthon"))
    for _, r in S[S["subset"] == label].iterrows():
        print("   %-13s %-6s %6d %8.4f %9.5f %9.5f %9.5f %11.2f%% %11.5f"
              % (r["target"], r["stage"], r["n"], r["sd_y"], r["r2_REF_matched"],
                 r["r2_best_honest"], r["r2_O2_oracle"],
                 100 * r["IRREDUCIBLE_share_even_to_O2"], r["headroom_O2_minus_best_honest"]))

# =====================================================================================
hdr("3. CALIBRATION ANCHOR -- does y_pts reproduce D081/D097 on THIS frame?")
# =====================================================================================
anchor = S[(S["subset"] == "DECISION (>=8 prior, >=24 trail-5 min)") & (S["target"] == "y_pts")]
irr = float(anchor["IRREDUCIBLE_share_even_to_O2"].iloc[0])
print("  y_pts IRREDUCIBLE even to O2 on the DECISION stratum = %.4f%%" % (100 * irr))
print("  D081 published 51.3%% ; D097 reproduced 51.68%% on n=5111.")
print("  This screen's decision-stratum n = %d" % int(anchor["n"].iloc[0]))
dev = abs(100 * irr - 51.68)
print("  deviation from D097 = %.2f points  -> %s"
      % (dev, "ON SCALE" if dev < 2.0 else "OFF SCALE -- LADDER NOT COMPARABLE"))
rep["anchor"] = dict(y_pts_irreducible_O2=irr, D081_published=0.513, D097_reproduced=0.5168,
                     deviation_points=dev, on_scale=bool(dev < 2.0),
                     n=int(anchor["n"].iloc[0]))

rep["ladder_summary"] = summ
json.dump(jsonable(rep), open(os.path.join(OUT, "_s03.json"), "w"), indent=2)
print("\n  WROTE oracle_ladder_ft.csv, ladder_summary.csv, baseline_accuracy.csv, _s03.json")
