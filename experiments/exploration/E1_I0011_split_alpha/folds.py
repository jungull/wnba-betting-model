"""E1 I0011 split-alpha -- the out-of-sample protocol.

E0 used ONE split (select 2021-22, score 2023-24). E1 asks whether the split-alpha
advantage PERSISTS out-of-sample, so it uses three protocols, all strictly inside
the 2021-2024 exploration partition:

  P1 LOSO     leave-one-season-out. test = season s, train = the other three.
              4 folds. Non-temporal (train can post-date test); maximises fold count.
  P2 WALKFWD  strictly temporal. test = season s, train = all seasons < s.
              3 folds (2022, 2023, 2024). This is the honest deployment analogue.
  P3 HALF     within-season temporal. test = second half of season s,
              train = first half of s plus every earlier season. 4 folds.
              Secondary: train and test share players heavily, so it tests
              "does the alpha choice transfer forward in time", not much more.

ARMS (everything with "tuned" in the name is re-selected on the TRAIN pool of that
fold and on nothing else):

  INCUMBENT     PER36 alpha_eff=0.30 alpha_exp=0.30   (props_edge.py, NOT tuned)
  NAIVE         season-to-date mean of the total      (NOT tuned)
  TOT_tuned     best single-channel EWMA of the total
  SINGLE_tuned  best PER36 cell CONSTRAINED to alpha_eff == alpha_exp
  SPLIT_tuned   best PER36 cell over the full 14x14 grid       <- THE LEAD
  SPLITFORM     best cell over all four two-channel forms
  FROZEN_SPLIT  PER36 alpha_eff=0.03 alpha_exp=0.30, fixed a priori (no tuning)

THE DECISIVE CONTRAST IS SPLIT_tuned vs SINGLE_tuned. Both are tuned on the same
train pool, in the same family, with the same number of estimators evaluated in
spirit -- the ONLY difference is whether the two channels are allowed different
alphas. SPLIT_tuned vs INCUMBENT confounds "splitting the channels" with "tuning
at all"; the E0 headline was that confounded number.

PARTITION: 2021-2024 only.
"""
import json
import numpy as np
import pandas as pd

PARTITION = [2021, 2022, 2023, 2024]
HERE = (r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees"
        r"\player-model-program\experiments\exploration\E1_I0011_split_alpha")
TARGETS = ["pts", "reb", "ast"]
FROZEN = (0.03, 0.30)

m = pd.read_parquet(HERE + r"\grid_metrics.parquet")
if not set(m["season"].unique()) <= set(PARTITION):
    raise SystemExit("PARTITION VIOLATION")
print("[partition-check] grid_metrics seasons:", sorted(int(x) for x in m["season"].unique()))
m["num"] = m["n"] * m["mae"]


def pool(sub, cells):
    """n-weighted pooled MAE per estimator key over a set of atomic cells."""
    k = sub[sub["_cell"].isin(cells)]
    g = k.groupby(["form", "alpha_eff", "alpha_exp"], dropna=False)[["n", "num"]].sum()
    g["mae"] = g["num"] / g["n"]
    return g


m["_cell"] = list(zip(m["season"], m["half"], m["slice"]))


def season_cells(seasons, slc="ALL"):
    return [(s, 0, slc) for s in seasons]


def half_cells(pairs, slc="ALL"):
    return [(s, h, slc) for s, h in pairs]


# ------------------------------------------------------------------ fold definitions
FOLDS = []
for s in PARTITION:                                        # P1 LOSO
    FOLDS.append(dict(protocol="P1_LOSO", fold=f"test{s}",
                      train=season_cells([x for x in PARTITION if x != s]),
                      test=season_cells([s])))
for s in [2022, 2023, 2024]:                               # P2 walk-forward by season
    FOLDS.append(dict(protocol="P2_WALKFWD", fold=f"test{s}",
                      train=season_cells([x for x in PARTITION if x < s]),
                      test=season_cells([s])))
for s in PARTITION:                                        # P3 within-season halves
    FOLDS.append(dict(protocol="P3_HALF", fold=f"test{s}H2",
                      train=season_cells([x for x in PARTITION if x < s]) + half_cells([(s, 1)]),
                      test=half_cells([(s, 2)])))


def arms(tr, tgt_sub):
    """Select every tuned arm on the TRAIN pool only. Returns {arm: (form, ae, ax)}."""
    g = pool(tgt_sub, tr).reset_index()
    per36 = g[g.form == "PER36"]
    two = g[g.form.isin(["PER36", "RATE36", "PER100", "RATE100"])]
    tot = g[g.form == "TOT"]
    diag = per36[np.isclose(per36.alpha_eff, per36.alpha_exp)]
    pick = lambda d: tuple(d.loc[d["mae"].idxmin(), ["form", "alpha_eff", "alpha_exp"]])
    return {
        "INCUMBENT": ("PER36", 0.30, 0.30),
        "NAIVE": ("STD", np.nan, np.nan),
        "FROZEN_SPLIT": ("PER36", FROZEN[0], FROZEN[1]),
        "TOT_tuned": pick(tot),
        "SINGLE_tuned": pick(diag),
        "SPLIT_tuned": pick(per36),
        "SPLITFORM": pick(two),
    }


def mae_of(g, key):
    form, ae, ax = key
    if form == "STD":
        r = g[g.form == "STD"]
    else:
        r = g[(g.form == form) & np.isclose(g.alpha_eff, ae) & np.isclose(g.alpha_exp, ax)]
    return float(r["mae"].iloc[0]), int(r["n"].iloc[0])


CONTRASTS = [("SPLIT_tuned", "SINGLE_tuned"), ("SPLIT_tuned", "INCUMBENT"),
             ("SPLIT_tuned", "NAIVE"), ("SPLIT_tuned", "TOT_tuned"),
             ("SPLITFORM", "SINGLE_tuned"), ("SPLITFORM", "INCUMBENT"),
             ("SPLITFORM", "NAIVE"), ("FROZEN_SPLIT", "INCUMBENT"),
             ("FROZEN_SPLIT", "NAIVE"), ("FROZEN_SPLIT", "SINGLE_tuned"),
             ("SINGLE_tuned", "INCUMBENT"), ("SINGLE_tuned", "NAIVE")]

fold_rows, contrast_rows = [], []
main = m[(m["slice"] == "ALL")]
for tgt in TARGETS:
    sub = main[main.target == tgt]
    for F in FOLDS:
        A = arms(F["train"], sub)
        gt = pool(sub, F["test"]).reset_index()
        maes = {a: mae_of(gt, k)[0] for a, k in A.items()}
        ntest = mae_of(gt, A["NAIVE"])[1]
        for a, k in A.items():
            fold_rows.append(dict(target=tgt, protocol=F["protocol"], fold=F["fold"],
                                  arm=a, form=k[0], alpha_eff=k[1], alpha_exp=k[2],
                                  n_test=ntest, test_mae=maes[a]))
        for hi, lo in CONTRASTS:
            contrast_rows.append(dict(
                target=tgt, protocol=F["protocol"], fold=F["fold"],
                contrast=f"{hi}_vs_{lo}", n_test=ntest,
                mae_hi=maes[hi], mae_lo=maes[lo],
                gap_pct=100 * (maes[lo] - maes[hi]) / maes[lo]))

fold_df = pd.DataFrame(fold_rows)
con_df = pd.DataFrame(contrast_rows)
fold_df.to_csv(HERE + r"\fold_arms.csv", index=False)
con_df.to_csv(HERE + r"\fold_contrasts.csv", index=False)

# --------------------------------------------------------------------- printouts
print("\n" + "=" * 110)
print("SELECTED ALPHAS PER FOLD -- does the SHAPE of the finding (alpha_eff << alpha_exp) persist?")
print("=" * 110)
for tgt in TARGETS:
    print(f"\n--- {tgt} ---")
    print(f"{'protocol':<12}{'fold':<12}{'SPLIT_tuned':<26}{'SINGLE_tuned':<16}"
          f"{'SPLITFORM':<28}{'ratio exp/eff':>14}")
    for _, r in fold_df[(fold_df.target == tgt) & (fold_df.arm == "SPLIT_tuned")].iterrows():
        sg = fold_df[(fold_df.target == tgt) & (fold_df.protocol == r.protocol) &
                     (fold_df.fold == r.fold)].set_index("arm")
        sp, si, sf = sg.loc["SPLIT_tuned"], sg.loc["SINGLE_tuned"], sg.loc["SPLITFORM"]
        ratio = (sp.alpha_exp / sp.alpha_eff) if sp.alpha_eff > 0 else np.inf
        print(f"{r.protocol:<12}{r.fold:<12}"
              f"{'eff=%.2f exp=%.2f' % (sp.alpha_eff, sp.alpha_exp):<26}"
              f"{'a=%.2f' % si.alpha_eff:<16}"
              f"{'%s eff=%.2f exp=%.2f' % (sf.form, sf.alpha_eff, sf.alpha_exp):<28}"
              f"{ratio:>14.1f}")

print("\n" + "=" * 110)
print("OUT-OF-SAMPLE GAPS PER FOLD (% MAE reduction of the first arm over the second)")
print("=" * 110)
for tgt in TARGETS:
    print(f"\n--- {tgt} ---")
    piv = con_df[con_df.target == tgt].pivot_table(
        index=["protocol", "fold"], columns="contrast", values="gap_pct")
    cols = ["SPLIT_tuned_vs_SINGLE_tuned", "SPLIT_tuned_vs_INCUMBENT",
            "SPLIT_tuned_vs_NAIVE", "SINGLE_tuned_vs_INCUMBENT",
            "FROZEN_SPLIT_vs_INCUMBENT", "FROZEN_SPLIT_vs_NAIVE"]
    print(piv[cols].round(3).to_string())

print("\n" + "=" * 110)
print("EFFECT SIZE ACROSS FOLDS -- mean, sd, min, max, and how many folds are positive")
print("(sd across folds is the headline uncertainty; a pooled single number is NOT reported)")
print("=" * 110)
summ_rows = []
for tgt in TARGETS:
    print(f"\n--- {tgt} ---")
    print(f"{'contrast':<34}{'protocol':<12}{'k':>3}{'mean%':>9}{'sd%':>8}"
          f"{'min%':>9}{'max%':>9}{'k>0':>6}")
    for c in ["SPLIT_tuned_vs_SINGLE_tuned", "SPLIT_tuned_vs_INCUMBENT",
              "SPLIT_tuned_vs_NAIVE", "SPLITFORM_vs_SINGLE_tuned",
              "SPLITFORM_vs_NAIVE", "SINGLE_tuned_vs_INCUMBENT",
              "SINGLE_tuned_vs_NAIVE", "FROZEN_SPLIT_vs_INCUMBENT",
              "FROZEN_SPLIT_vs_NAIVE", "FROZEN_SPLIT_vs_SINGLE_tuned"]:
        for p in ["P1_LOSO", "P2_WALKFWD", "P3_HALF"]:
            v = con_df[(con_df.target == tgt) & (con_df.contrast == c) &
                       (con_df.protocol == p)]["gap_pct"].values
            if not len(v):
                continue
            print(f"{c:<34}{p:<12}{len(v):>3}{v.mean():>9.3f}{v.std(ddof=1):>8.3f}"
                  f"{v.min():>9.3f}{v.max():>9.3f}{int((v > 0).sum()):>6}")
            summ_rows.append(dict(target=tgt, contrast=c, protocol=p, k_folds=len(v),
                                  mean_gap_pct=float(v.mean()),
                                  sd_gap_pct=float(v.std(ddof=1)),
                                  min_gap_pct=float(v.min()), max_gap_pct=float(v.max()),
                                  n_folds_positive=int((v > 0).sum())))
pd.DataFrame(summ_rows).to_csv(HERE + r"\fold_summary.csv", index=False)

# ------------------------------------------------------- per-role-slice, LOSO folds
print("\n" + "=" * 110)
print("PER-ROLE-SLICE, LOSO folds: alphas re-selected WITHIN the slice on the train")
print("seasons only, then scored in-slice on the held-out season.")
print("=" * 110)
SLICES = ["S1_starter1", "S1_starter0", "S2_min_lt15", "S2_min_15_25", "S2_min_ge25",
          "S3_usage_low", "S3_usage_mid", "S3_usage_high"]
slice_rows = []
for tgt in TARGETS:
    print(f"\n--- {tgt} ---")
    print(f"{'slice':<16}{'fold':<10}{'SPLIT eff/exp':<18}{'SINGLE a':>9}"
          f"{'n':>7}{'vs SINGLE%':>12}{'vs INC%':>10}{'vs NAIVE%':>11}")
    for sl in SLICES:
        sub = m[(m.target == tgt) & (m["slice"] == sl)]
        if sub.empty:
            continue
        for s in PARTITION:
            tr = season_cells([x for x in PARTITION if x != s], sl)
            te = season_cells([s], sl)
            if not set(te) <= set(sub["_cell"]) or len(set(tr) & set(sub["_cell"])) < 2:
                continue
            A = arms(tr, sub)
            gt = pool(sub, te).reset_index()
            mm = {a: mae_of(gt, k)[0] for a, k in A.items()}
            nn = mae_of(gt, A["NAIVE"])[1]
            sp = A["SPLIT_tuned"]
            g1 = 100 * (mm["SINGLE_tuned"] - mm["SPLIT_tuned"]) / mm["SINGLE_tuned"]
            g2 = 100 * (mm["INCUMBENT"] - mm["SPLIT_tuned"]) / mm["INCUMBENT"]
            g3 = 100 * (mm["NAIVE"] - mm["SPLIT_tuned"]) / mm["NAIVE"]
            print(f"{sl:<16}{'test%d' % s:<10}"
                  f"{'%.2f / %.2f' % (sp[1], sp[2]):<18}"
                  f"{A['SINGLE_tuned'][1]:>9.2f}{nn:>7}{g1:>12.3f}{g2:>10.3f}{g3:>11.3f}")
            slice_rows.append(dict(target=tgt, slice=sl, fold=f"test{s}", n_test=nn,
                                   split_alpha_eff=sp[1], split_alpha_exp=sp[2],
                                   single_alpha=A["SINGLE_tuned"][1],
                                   mae_split=mm["SPLIT_tuned"],
                                   mae_single=mm["SINGLE_tuned"],
                                   mae_incumbent=mm["INCUMBENT"], mae_naive=mm["NAIVE"],
                                   gap_vs_single_pct=g1, gap_vs_incumbent_pct=g2,
                                   gap_vs_naive_pct=g3))
sl_df = pd.DataFrame(slice_rows)
sl_df.to_csv(HERE + r"\slice_folds.csv", index=False)

print("\n" + "-" * 110)
print("SLICE SUMMARY across the 4 LOSO folds (mean +- sd, folds positive)")
print("-" * 110)
print(f"{'target':<7}{'slice':<16}{'vs SINGLE mean%':>17}{'sd':>8}{'k>0':>5}"
      f"{'vs INC mean%':>14}{'sd':>8}{'k>0':>5}{'vs NAIVE mean%':>16}{'sd':>8}{'k>0':>5}"
      f"{'eff alphas':>22}{'exp alphas':>22}")
slsum = []
for tgt in TARGETS:
    for sl in SLICES:
        d = sl_df[(sl_df.target == tgt) & (sl_df["slice"] == sl)]
        if len(d) < 2:
            continue
        row = dict(target=tgt, slice=sl, k_folds=len(d))
        for nm, col in [("single", "gap_vs_single_pct"), ("inc", "gap_vs_incumbent_pct"),
                        ("naive", "gap_vs_naive_pct")]:
            row[f"mean_vs_{nm}"] = float(d[col].mean())
            row[f"sd_vs_{nm}"] = float(d[col].std(ddof=1))
            row[f"kpos_vs_{nm}"] = int((d[col] > 0).sum())
        row["alpha_eff_folds"] = ",".join("%.2f" % x for x in d.split_alpha_eff)
        row["alpha_exp_folds"] = ",".join("%.2f" % x for x in d.split_alpha_exp)
        slsum.append(row)
        print(f"{tgt:<7}{sl:<16}{row['mean_vs_single']:>17.3f}{row['sd_vs_single']:>8.3f}"
              f"{row['kpos_vs_single']:>5}{row['mean_vs_inc']:>14.3f}{row['sd_vs_inc']:>8.3f}"
              f"{row['kpos_vs_inc']:>5}{row['mean_vs_naive']:>16.3f}{row['sd_vs_naive']:>8.3f}"
              f"{row['kpos_vs_naive']:>5}{row['alpha_eff_folds']:>22}{row['alpha_exp_folds']:>22}")
pd.DataFrame(slsum).to_csv(HERE + r"\slice_summary.csv", index=False)

# ------------------------------------------------------------- alpha surface shape
print("\n" + "=" * 110)
print("ALPHA SURFACE, pooled over all four partition seasons (DESCRIPTIVE, in-sample --")
print("this is the shape of the objective, not an out-of-sample claim)")
print("=" * 110)
surf_rows = []
for tgt in TARGETS:
    g = pool(main[main.target == tgt], season_cells(PARTITION)).reset_index()
    p = g[g.form == "PER36"]
    best = p.loc[p["mae"].idxmin()]
    print(f"\n--- {tgt} --- PER36 grid minimum at eff={best.alpha_eff:.2f} "
          f"exp={best.alpha_exp:.2f} MAE={best.mae:.4f}")
    piv = p.pivot_table(index="alpha_eff", columns="alpha_exp", values="mae")
    print(piv.round(4).to_string())
    for _, r in p.iterrows():
        surf_rows.append(dict(target=tgt, alpha_eff=r.alpha_eff, alpha_exp=r.alpha_exp,
                              mae_pooled_2021_2024=r.mae))
pd.DataFrame(surf_rows).to_csv(HERE + r"\alpha_surface.csv", index=False)
print("\nDONE. wrote fold_arms.csv fold_contrasts.csv fold_summary.csv "
      "slice_folds.csv slice_summary.csv alpha_surface.csv")
