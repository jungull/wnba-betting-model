"""E1_I0020 STEP 7 -- THE RECOMMENDED OPERATING RULE, PRICED ON THE WHOLE POOLED FRAME.

  The rule:  IF the champion flags the row as a fallback (equivalently: the player has fewer than 3
  prior appearances this season, plus 62 returning-from-absence rows), REPLACE the champion's
  forecast with
        BLEND = lam(n)*own_complete_running_mean + (1-lam(n))*(league + depth_dev + draft_dev)
        lam(n) = n/(n+2),  n = prior same-season appearances
  Otherwise keep the champion untouched.  Nothing is refitted; the champion is never retrained.

  This is the same shape as D081's crude splice, so the two are priced side by side on the same
  rows with the same inference, and the increment over the crude splice is what the extra machinery
  actually buys.
"""
import json
import os

import numpy as np
import pandas as pd

import ct_base as B
import screenkit as sk

OUT = {}
w = pd.read_parquet(os.path.join(B.OUT, "placeholder_frame.parquet"))
PH = {t: pd.read_csv(os.path.join(B.OUT, "placeholders_%s.csv" % t)) for t in B.TARGETS}
B.assert_partition_adjudicated(w, where="s05")
tier = w["pts__is_fallback"].to_numpy(bool)
groups_all = B.block_codes(w)

B.hdr("STEP 7.1 -- POOLED IMPACT OF THE RECOMMENDED RULE ON ALL 13,879 ROWS")
rows = []
for t in B.TARGETS:
    y = w["t_" + t].to_numpy(float)
    champ = w["champ_" + t].to_numpy(float)
    p1full = w["p1full_" + t].to_numpy(float)
    p1ref = w["p1_" + t].to_numpy(float)
    blend = PH[t]["P5d_blend_k2"].to_numpy(float)
    variants = {
        "champion_untouched": champ,
        "D081_crude_splice_refD076": np.where(w["pl_games_prior"] < 3, p1ref, champ),
        "crude_splice_COMPLETE_running_mean": np.where(tier, p1full, champ),
        "RECOMMENDED_blend_splice": np.where(tier, blend, champ),
    }
    for nm, v in variants.items():
        r, _ = B.paired(y, v, champ, groups_all, name_a=nm, name_b="champion")
        rc, _ = B.paired(y, v, variants["crude_splice_COMPLETE_running_mean"], groups_all)
        rows.append(dict(target=t, variant=nm,
                         pooled_mae=B.mae(y, v),
                         pooled_r2_of_forecast=B.r2f(y, v),
                         pooled_skill_vs_refD076=1.0 - B.mae(y, v) / B.mae(y, p1ref),
                         dr2_vs_champion=r["dr2_a_minus_b"], p_vs_champion=r["p"],
                         p_row_NAIVE_vs_champion=r["p_row_level_NAIVE"],
                         inflation=r["inflation"],
                         dr2_vs_crude_complete=rc["dr2_a_minus_b"],
                         p_vs_crude_complete=rc["p"]))
P = pd.DataFrame(rows)
P.to_csv(os.path.join(B.OUT, "pooled_operating_rule.csv"), index=False)
for t in B.TARGETS:
    print("\n  --- target=%s   (pooled over all 13,879 rows, 475 player-season clusters)" % t)
    print(P[P["target"] == t][["variant", "pooled_mae", "pooled_r2_of_forecast",
                               "pooled_skill_vs_refD076", "dr2_vs_champion", "p_vs_champion",
                               "dr2_vs_crude_complete", "p_vs_crude_complete"]].to_string(
        index=False, float_format=lambda v: "%+.5f" % v))
OUT["pooled_operating_rule"] = P.to_dict("records")
print("""
  The `pooled_skill_vs_refD076` column is the number that is directly comparable to D081's
  headline: the champion untouched sits at -0.00222 and D081's crude splice at +0.01360, both
  reproduced exactly in s01.
""")

B.hdr("STEP 7.2 -- PER-SEASON STABILITY (a rule that works in one fold is not a rule)")
srows = []
for S in B.SCREEN_SEASONS:
    m = (w["season"] == S).to_numpy()
    sub = w[m]
    g = B.block_codes(sub)
    for t in ["pts", "minutes"]:
        y = sub["t_" + t].to_numpy(float)
        champ = sub["champ_" + t].to_numpy(float)
        blend = PH[t][m]["P5d_blend_k2"].to_numpy(float)
        p1full = sub["p1full_" + t].to_numpy(float)
        rec = np.where(tier[m], blend, champ)
        crude = np.where(tier[m], p1full, champ)
        r, _ = B.paired(y, rec, champ, g)
        rc, _ = B.paired(y, rec, crude, g)
        srows.append(dict(season=S, target=t, n=int(m.sum()), n_tier=int(tier[m].sum()),
                          mae_champion=B.mae(y, champ), mae_recommended=B.mae(y, rec),
                          dr2_vs_champion=r["dr2_a_minus_b"], p_vs_champion=r["p"],
                          dr2_vs_crude=rc["dr2_a_minus_b"], p_vs_crude=rc["p"]))
SS = pd.DataFrame(srows)
SS.to_csv(os.path.join(B.OUT, "per_season_stability.csv"), index=False)
print(SS.to_string(index=False, float_format=lambda v: "%+.5f" % v))
OUT["per_season"] = SS.to_dict("records")

B.hdr("STEP 7.3 -- WHAT THE CHAMPION EMITS ON THE TIER, AND WHAT THE RULE EMITS INSTEAD")
for t in ["pts", "minutes"]:
    c = w.loc[tier, "champ_" + t]
    b = PH[t][tier]["P5d_blend_k2"]
    y = w.loc[tier, "t_" + t]
    print("  %-8s champion: mean=%7.3f sd=%6.3f  min=%7.3f max=%7.3f"
          % (t, c.mean(), c.std(), c.min(), c.max()))
    print("  %-8s RULE    : mean=%7.3f sd=%6.3f  min=%7.3f max=%7.3f"
          % ("", b.mean(), b.std(), b.min(), b.max()))
    print("  %-8s truth   : mean=%7.3f sd=%6.3f\n" % ("", y.mean(), y.std()))
    OUT.setdefault("tier_forecast_spread", {})[t] = {
        "champion_sd": float(c.std()), "rule_sd": float(b.std()), "truth_sd": float(y.std())}

B.hdr("STEP 7.4 -- FINAL NEGATIVE CONTROL: THE RULE APPLIED TO A RANDOMISED TIER")
print("""
  If the rule's pooled gain came from the blend simply being a better forecast everywhere, then
  applying it on a RANDOM 7.6% of rows would gain too.  It must not.
""")
rng = np.random.default_rng(B.SEED)
nc = []
for t in ["pts", "minutes"]:
    y = w["t_" + t].to_numpy(float)
    champ = w["champ_" + t].to_numpy(float)
    blend = PH[t]["P5d_blend_k2"].to_numpy(float)
    real = np.where(tier, blend, champ)
    r_real, _ = B.paired(y, real, champ, groups_all)
    fake_dr2 = []
    for i in range(200):
        fake = np.zeros(len(w), bool)
        fake[rng.choice(len(w), size=int(tier.sum()), replace=False)] = True
        fake_dr2.append(B.r2f(y, np.where(fake, blend, champ)) - B.r2f(y, champ))
    fake_dr2 = np.array(fake_dr2)
    print("  %-8s real tier dR2=%+.5f | random-tier dR2 mean=%+.5f sd=%.5f max=%+.5f"
          % (t, r_real["dr2_a_minus_b"], fake_dr2.mean(), fake_dr2.std(ddof=1), fake_dr2.max()))
    nc.append(dict(target=t, real_dr2=r_real["dr2_a_minus_b"],
                   random_tier_mean=float(fake_dr2.mean()),
                   random_tier_sd=float(fake_dr2.std(ddof=1)),
                   random_tier_max=float(fake_dr2.max())))
pd.DataFrame(nc).to_csv(os.path.join(B.OUT, "negative_control_random_tier.csv"), index=False)
OUT["negative_control_random_tier"] = nc

B.jdump(OUT, "_s05.json")
print("\nSTEP 7 COMPLETE.")
