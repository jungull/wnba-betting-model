"""S07 -- IS TYPE-I PREDICTABLE FROM THE CANDIDATE'S DISTRIBUTIONAL SHAPE?

Also settles PREREG P3 and P4 explicitly, in the direction the data give, not the direction
predicted.

D101: every shape feature is a description of ONE column on ONE arm's rows after that arm's
own base.  Type-I rates are on that same arm.  Nothing is compared across arms; the two arms
are reported side by side as two separate measurements.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOL = 0.075


def spearman(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if len(a) < 4 or np.std(a) == 0 or np.std(b) == 0:
        return np.nan, len(a)
    ra = np.array(pd.Series(a).rank(), dtype=float, copy=True)
    rb = np.array(pd.Series(b).rank(), dtype=float, copy=True)
    ra = ra - ra.mean(); rb = rb - rb.mean()
    d = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return (float((ra * rb).sum() / d) if d > 0 else np.nan), len(a)


TI = pd.read_csv(os.path.join(HERE, "TYPEI_PER_CELL.csv"))
out_rows, corr_rows = [], []
for ARM in ("A4_CLEAN_DEC", "A1_FULL"):
    S = pd.read_csv(os.path.join(HERE, "_SHAPE_CAND_%s.csv" % ARM))
    Rr = pd.read_csv(os.path.join(HERE, "_SHAPE_RESP_%s.csv" % ARM))
    raw = pd.read_csv(os.path.join(HERE, "_TYPEI_RAW_%s.csv" % ARM))
    raw["not_estimable"] = raw.get("not_estimable", "").fillna("")
    # the DIRECT measurement of whether a generator planted an effect:
    # mean of the SIGNED observed t over the B synthetic "effect-free" datasets.
    pl = raw[raw["not_estimable"] == ""].pivot_table(
        index="cell", columns="generator", values="mean_signed_t_obs")
    pl.columns = ["planted_mean_signed_t_" + c for c in pl.columns]
    ti = TI[(TI["arm"] == ARM) & (TI["not_estimable"].fillna("") == "")].set_index("cell")
    M = ti.join(pl).reset_index().merge(S, on="candidate", how="left",
                                        suffixes=("", "_shape"))
    M = M.merge(Rr, on="dependent", how="left")
    M["arm"] = ARM
    out_rows.append(M)

    print("\n" + "=" * 78)
    print("ARM %s -- %d estimable cells" % (ARM, len(M)))
    print("=" * 78)
    print("\n-- did each generator plant an effect?  mean SIGNED observed t over %d "
          "'effect-free' datasets (should be ~0 if H0 really holds) --" % int(raw['B_reps'].iloc[0]))
    for g in ("EXCH", "CIRCSHIFT", "BLOCKBOOT"):
        c = "planted_mean_signed_t_" + g
        print("   %-10s  median |mean t| %.4f   max |mean t| %.4f   cells with |mean t| > 0.5 : %d"
              % (g, M[c].abs().median(), M[c].abs().max(), int((M[c].abs() > 0.5).sum())))

    targets = {
        "COMPOSED2 Type-I (EXCH)": "typeI_COMPOSED2_EXCH",
        "COMPOSED2 Type-I (CIRCSHIFT)": "typeI_COMPOSED2_CIRCSHIFT",
        "COMPOSED2 rejection (BLOCKBOOT)": "typeI_COMPOSED2_BLOCKBOOT",
        "E0_I0014 own null Type-I (EXCH)": "typeI_LEVEL_MATCHED_EXCH",
        "planted |mean t| (BLOCKBOOT)": "_abs_planted",
    }
    M["_abs_planted"] = M["planted_mean_signed_t_BLOCKBOOT"].abs()
    feats = ["var_share_between_block", "dev_excess_kurtosis", "dev_max_abs_z",
             "excess_kurtosis_whole", "max_within_block_spread_z", "n_distinct_over_n",
             "pos_corr_mean_abs", "pos_monotone_share", "dev_lag1_autocorr",
             "shared_position_profile_sd", "resp_shared_position_profile_sd"]
    tab = pd.DataFrame(index=feats)
    for lab, col in targets.items():
        vals = []
        for ft in feats:
            r, nn = spearman(M[ft], M[col])
            vals.append(r)
            corr_rows.append(dict(arm=ARM, target=lab, feature=ft, spearman=r, n_cells=nn))
        tab[lab] = vals
    print("\n-- SPEARMAN(shape feature, target), %d cells --" % len(M))
    print(tab.round(3).to_string())

    # ---- PREREG P3: the three position-monotone counters
    print("\n-- PREREG P3: the three position-monotone counters --")
    for cand in ("pl_games_prior", "pl_minutes_prior", "pts__n_prior_games"):
        sub = M[M["candidate"] == cand]
        if not len(sub):
            print("   %-20s not estimable on this arm" % cand); continue
        print("   %-20s pos_corr %.3f | EXCH %.4f-%.4f | CIRCSHIFT %.4f-%.4f | "
              "BLOCKBOOT %.4f-%.4f"
              % (cand, sub["pos_corr_mean"].iloc[0],
                 sub["typeI_COMPOSED2_EXCH"].min(), sub["typeI_COMPOSED2_EXCH"].max(),
                 sub["typeI_COMPOSED2_CIRCSHIFT"].min(), sub["typeI_COMPOSED2_CIRCSHIFT"].max(),
                 sub["typeI_COMPOSED2_BLOCKBOOT"].min(), sub["typeI_COMPOSED2_BLOCKBOOT"].max()))

    # ---- PREREG P4: kurtosis vs Type-I
    r4, n4 = spearman(M["dev_excess_kurtosis"], M["typeI_COMPOSED2_EXCH"])
    print("\n-- PREREG P4: Spearman(within-block excess kurtosis, COMPOSED2 Type-I under EXCH)"
          " = %.3f on %d cells   [P4 predicted > +0.5]" % (r4, n4))

    # ---- a candidate two-feature rule, evaluated on what it can actually predict
    print("\n-- what a shape rule CAN predict on this arm --")
    hi_pos = M["pos_corr_mean_abs"] > 0.9
    lo_btw = M["var_share_between_block"] < 0.30
    pred_conservative = hi_pos | lo_btw
    actual_conservative = M["typeI_COMPOSED2_worst_H0_generator"] <= 0.025
    tp = int((pred_conservative & actual_conservative).sum())
    fp = int((pred_conservative & ~actual_conservative).sum())
    fn = int((~pred_conservative & actual_conservative).sum())
    tn = int((~pred_conservative & ~actual_conservative).sum())
    print("   rule 'position-monotone OR between-block share < 0.30' -> CONSERVATIVE null")
    print("      TP %d  FP %d  FN %d  TN %d   misclassified %d of %d"
          % (tp, fp, fn, tn, fp + fn, len(M)))
    pred_conf = M["pos_corr_mean_abs"] > 0.9
    actual_conf = M["typeI_COMPOSED2_BLOCKBOOT"] > TOL
    tp2 = int((pred_conf & actual_conf).sum()); fp2 = int((pred_conf & ~actual_conf).sum())
    fn2 = int((~pred_conf & actual_conf).sum()); tn2 = int((~pred_conf & ~actual_conf).sum())
    print("   rule 'candidate is position-monotone (|pos corr| > 0.9)' -> a position-preserving")
    print("      Type-I generator will falsely condemn the null")
    print("      TP %d  FP %d  FN %d  TN %d   misclassified %d of %d"
          % (tp2, fp2, fn2, tn2, fp2 + fn2, len(M)))
    print("   cells BLOCKBOOT condemns that the rule misses:",
          sorted(M.loc[~pred_conf & actual_conf, "candidate"].unique()))

A = pd.concat(out_rows, ignore_index=True)
A.to_csv(os.path.join(HERE, "_SHAPE_TABLE.csv"), index=False)
pd.DataFrame(corr_rows).to_csv(os.path.join(HERE, "_SHAPE_SPEARMAN.csv"), index=False)
print("\nwrote _SHAPE_TABLE.csv and _SHAPE_SPEARMAN.csv")
print("DONE s07")
