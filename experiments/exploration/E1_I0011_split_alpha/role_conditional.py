"""E1 I0011 -- is a ROLE-CONDITIONAL alpha worth carrying in the corrected baseline?

E0 found that role slices want different horizons. That was measured with alphas
re-selected inside each slice and scored inside that slice -- which says the slices
differ, but NOT that a role-conditional estimator beats a global one on the SAME
rows. This script asks the operational question:

  per fold, choose (alpha_eff, alpha_exp) SEPARATELY PER ROLE TIER on the train
  seasons, assemble one role-conditional estimator, and score it on the held-out
  season against a single GLOBAL (alpha_eff, alpha_exp) also chosen on train.

The role tiers partition the eval universe exactly (asserted below), so the
role-conditional test MAE is the n-weighted pool of the per-tier test cells and no
new prediction vector is needed -- the comparison is on identical rows.

PARTITION: 2021-2024 only.
"""
import numpy as np
import pandas as pd

PARTITION = [2021, 2022, 2023, 2024]
HERE = (r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees"
        r"\player-model-program\experiments\exploration\E1_I0011_split_alpha")
TARGETS = ["pts", "reb", "ast"]

FAMILIES = {
    "S1_starter": ["S1_starter1", "S1_starter0"],
    "S2_minutes": ["S2_min_lt15", "S2_min_15_25", "S2_min_ge25"],
    "S3_usage": ["S3_usage_low", "S3_usage_mid", "S3_usage_high"],
}

m = pd.read_parquet(HERE + r"\grid_metrics.parquet")
if not set(m["season"].unique()) <= set(PARTITION):
    raise SystemExit("PARTITION VIOLATION")
m = m[m["half"] == 0]
m["num"] = m["n"] * m["mae"]
print("[partition-check] seasons:", sorted(int(x) for x in m["season"].unique()))

# ------------------------------------------- do the tiers partition the eval universe?
chk = m[(m.target == "pts") & (m.form == "STD")]
for fam, tiers in FAMILIES.items():
    for s in PARTITION:
        tot = int(chk[(chk.season == s) & (chk["slice"] == "ALL")]["n"].iloc[0])
        part = int(chk[(chk.season == s) & (chk["slice"].isin(tiers))]["n"].sum())
        status = "OK" if tot == part else "MISMATCH"
        print(f"[tier-partition] {fam} season {s}: ALL={tot} sum(tiers)={part} {status}")
        if tot != part:
            raise SystemExit(f"{fam} does not partition the eval universe in {s}")


def sel(sub, seasons, slc):
    """Best PER36 (alpha_eff, alpha_exp) on the train pool of one slice."""
    k = sub[(sub["slice"] == slc) & (sub.season.isin(seasons)) & (sub.form == "PER36")]
    g = k.groupby(["alpha_eff", "alpha_exp"])[["n", "num"]].sum()
    g["mae"] = g["num"] / g["n"]
    return g["mae"].idxmin()


def score(sub, season, slc, cfg=None, form="PER36"):
    """(n, MAE) of one config on one test cell. cfg=None -> the STD naive default."""
    k = sub[(sub["slice"] == slc) & (sub.season == season)]
    if cfg is None:
        r = k[k.form == "STD"]
    else:
        r = k[(k.form == form) & np.isclose(k.alpha_eff, cfg[0]) &
              np.isclose(k.alpha_exp, cfg[1])]
    return int(r["n"].iloc[0]), float(r["mae"].iloc[0])


PROTOCOLS = ([("P1_LOSO", s, [x for x in PARTITION if x != s]) for s in PARTITION] +
             [("P2_WALKFWD", s, [x for x in PARTITION if x < s]) for s in [2022, 2023, 2024]])

rows = []
print("\n" + "=" * 108)
print("ROLE-CONDITIONAL vs GLOBAL alpha, scored on identical held-out rows")
print("=" * 108)
for tgt in TARGETS:
    sub = m[m.target == tgt]
    print(f"\n--- {tgt} ---")
    print(f"{'family':<12}{'protocol':<12}{'fold':<10}{'n':>7}{'global eff/exp':<18}"
          f"{'role MAE':>10}{'global MAE':>12}{'role-vs-global%':>17}{'per-tier eff/exp'}")
    for fam, tiers in FAMILIES.items():
        for proto, test_s, train_s in PROTOCOLS:
            gcfg = sel(sub, train_s, "ALL")
            gn, gmae = score(sub, test_s, "ALL", gcfg)
            num = den = 0.0
            desc = []
            for t in tiers:
                tcfg = sel(sub, train_s, t)
                tn, tmae = score(sub, test_s, t, tcfg)
                num += tn * tmae
                den += tn
                desc.append(f"{t.split('_', 1)[1]}:{tcfg[0]:.2f}/{tcfg[1]:.2f}")
            rmae = num / den
            gap = 100 * (gmae - rmae) / gmae
            print(f"{fam:<12}{proto:<12}{'test%d' % test_s:<10}{int(den):>7}"
                  f"{'%.2f / %.2f' % gcfg:<18}{rmae:>10.4f}{gmae:>12.4f}{gap:>17.3f}"
                  f"   {' '.join(desc)}")
            rows.append(dict(target=tgt, family=fam, protocol=proto, fold=f"test{test_s}",
                             n_test=int(den), global_alpha_eff=gcfg[0],
                             global_alpha_exp=gcfg[1], mae_role=rmae, mae_global=gmae,
                             gap_role_vs_global_pct=gap, per_tier=" ".join(desc)))

rc = pd.DataFrame(rows)
rc.to_csv(HERE + r"\role_conditional.csv", index=False)

print("\n" + "-" * 108)
print("SUMMARY -- role-conditional minus global, across folds (positive = role helps)")
print("-" * 108)
print(f"{'target':<7}{'family':<12}{'protocol':<12}{'k':>3}{'mean%':>9}{'sd%':>8}"
      f"{'min%':>9}{'max%':>9}{'k>0':>6}")
summ = []
for tgt in TARGETS:
    for fam in FAMILIES:
        for proto in ["P1_LOSO", "P2_WALKFWD"]:
            v = rc[(rc.target == tgt) & (rc.family == fam) &
                   (rc.protocol == proto)]["gap_role_vs_global_pct"].values
            print(f"{tgt:<7}{fam:<12}{proto:<12}{len(v):>3}{v.mean():>9.3f}"
                  f"{v.std(ddof=1):>8.3f}{v.min():>9.3f}{v.max():>9.3f}{int((v > 0).sum()):>6}")
            summ.append(dict(target=tgt, family=fam, protocol=proto, k_folds=len(v),
                             mean_gap_pct=float(v.mean()), sd_gap_pct=float(v.std(ddof=1)),
                             min_gap_pct=float(v.min()), max_gap_pct=float(v.max()),
                             n_folds_positive=int((v > 0).sum())))
pd.DataFrame(summ).to_csv(HERE + r"\role_conditional_summary.csv", index=False)
print("\nDONE. wrote role_conditional.csv role_conditional_summary.csv")
