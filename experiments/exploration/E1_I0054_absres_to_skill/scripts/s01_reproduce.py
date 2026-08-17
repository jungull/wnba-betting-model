"""S01 -- REPRODUCE THE SIXTEEN, independently.

Composed-2 null rebuilt from the specification (E1_I0044/s07_remeasure_v2.py:46-58), not
imported.  R = 2000, one shared gather index per draw across all 58 candidates, PLAYER-scheme
candidates on player-season blocks and TEAM-scheme on team-season blocks.  Family-wise bar =
q95 of max|t| over the 348-cell family.  p = (k+1)/(R+1).  Three independent seeds.

Also recorded, because nobody had looked before E1_I0050 and it is now mandatory:
  * which cell supplies the family-wise bar, per draw (R-C / T4)
  * the null's mean SIGNED t on the real response, per cell (T3 blindness)

SIGNED, UNSTANDARDISED draws with full stratum keys are stored in raw/.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa

s00 = json.load(open(os.path.join(HERE, "scripts", "_s00.json")))
CELLS54 = s00["cells54"]
PUB16 = set(s00["published_16"])

CV = pd.read_csv(os.path.join(S50, "CORRECTED_VERDICTS.csv"))
VALID = {(r["arm"], r["cell"]): str(r["null_validity"]) for _, r in CV.iterrows()}

CELLNAMES = ["%s|%s" % (nm, k) for k in DEP_NAMES for nm in names]
t0 = time.time()
allrows, summary = [], []

for arm in ("A4_CLEAN_DEC", "A1_FULL"):
    mask = ARM_MASKS[arm]
    ctx = arm_context(mask)
    m, df, dm = ctx["m"], ctx["df"], ctx["dm"]
    gp = blocks_on(mask, "player_id")
    gt = blocks_on(mask, "team_id")
    nbp = sum(len(v) for v in gp.values()); nbt = sum(len(v) for v in gt.values())
    Ymat = np.column_stack([ctx["Yt"][k] for k in DEP_NAMES])
    obs_t, obs_dr2 = {}, {}
    for k in DEP_NAMES:
        _b, tt, dd = t_and_dr2(ctx["Yt"][k], ctx["Xzt"], df, ctx["SST"][k])
        obs_t[k] = tt; obs_dr2[k] = dd
    obs_flat = np.concatenate([obs_t[k] for k in DEP_NAMES])
    print("\n=== %s  n=%d  df=%d  player-blocks=%d  team-blocks=%d ==="
          % (arm, m, df, nbp, nbt), flush=True)

    seeds = SEEDS if arm == "A4_CLEAN_DEC" else SEEDS[:1]
    for seed in seeds:
        rng = np.random.default_rng(seed)
        NT = np.zeros((R_NULL_COMPOSED2, C * len(DEP_NAMES)))
        for d in range(R_NULL_COMPOSED2):
            ip = idx_composed2(gp, m, rng)
            it = idx_composed2(gt, m, rng)
            Xp = dm(np.where(is_player[None, :], ctx["Xza"][ip], ctx["Xza"][it]))
            NT[d] = t_many(Ymat, Xp, df).T.reshape(-1)   # (dep, cand) -> flat in CELLNAMES order
            if (d + 1) % 500 == 0:
                print("   seed %d draw %d/%d (%.0fs)" % (seed, d + 1, R_NULL_COMPOSED2,
                                                         time.time() - t0), flush=True)
        A = np.abs(NT)
        maxt = np.nanmax(A, axis=1)
        argt = np.nanargmax(A, axis=1)
        bar95 = float(np.nanpercentile(maxt, 95))
        vc = pd.Series([CELLNAMES[i] for i in argt]).value_counts()
        print("   seed %d  bar q95 = %.4f | top supplier %s in %d/%d draws | %d distinct suppliers"
              % (seed, bar95, vc.index[0], int(vc.iloc[0]), len(maxt), len(vc)), flush=True)

        np.savez_compressed(os.path.join(RAW, "composed2_%s_seed%d.npz" % (arm, seed)),
                            arm=np.array([arm]), seed=np.array([seed]),
                            n=np.array([m]), R=np.array([R_NULL_COMPOSED2]),
                            n_blocks_player=np.array([nbp]), n_blocks_team=np.array([nbt]),
                            cells=np.array(CELLNAMES), t_signed=NT,
                            maxt_familywise=maxt, argmax_cell=argt,
                            observed_t_signed=obs_flat,
                            observed_dr2=np.concatenate([obs_dr2[k] for k in DEP_NAMES]))

        summary.append(dict(arm=arm, seed=seed, n=m, R=R_NULL_COMPOSED2,
                            bar_familywise_q95=bar95,
                            bar_mean=float(maxt.mean()),
                            top_supplier_cell=str(vc.index[0]),
                            top_supplier_share=float(vc.iloc[0] / len(maxt)),
                            n_distinct_suppliers=int(len(vc))))

        ix = {c: i for i, c in enumerate(CELLNAMES)}
        for cell in CELLS54:
            j = ix[cell]
            dv = NT[:, j]
            fin = np.isfinite(dv)
            obs = float(obs_flat[j])
            rec = dict(arm=arm, seed=seed, cell=cell, candidate=cell.split("|")[0],
                       dependent=cell.split("|")[1], n=m, n_blocks=nbp,
                       R=R_NULL_COMPOSED2, observed_signed_t=obs,
                       observed_dr2=float(np.concatenate([obs_dr2[k] for k in DEP_NAMES])[j]),
                       null_mean_signed_t=float(dv[fin].mean()) if fin.any() else np.nan,
                       null_sd_signed_t=float(dv[fin].std(ddof=1)) if fin.any() else np.nan,
                       bar_familywise_q95=bar95,
                       null_validity_from_E1_I0050=VALID.get((arm, cell), "MISSING"))
            rec["blind_flag_T3"] = bool(np.isfinite(rec["null_mean_signed_t"])
                                        and abs(rec["null_mean_signed_t"]) > TOL_BLIND)
            if np.isfinite(obs):
                a = np.abs(dv[fin])
                rec["p_percell_plus1"] = float((np.sum(a >= abs(obs)) + 1) / (len(a) + 1))
                rec["p_familywise_plus1"] = float((np.sum(maxt >= abs(obs)) + 1) / (len(maxt) + 1))
                rec["not_estimable"] = ""
            else:
                rec["p_percell_plus1"] = np.nan
                rec["p_familywise_plus1"] = np.nan
                rec["not_estimable"] = "OBSERVED_T_NOT_FINITE"
            ok = str(rec["null_validity_from_E1_I0050"]).startswith("ACCEPTABLE")
            if not np.isfinite(rec["p_familywise_plus1"]):
                v = "UNVERIFIABLE_NO_FINITE_STATISTIC"
            elif not ok:
                v = "UNVERIFIABLE_NULL_FAILS_TYPE_I"
            elif rec["blind_flag_T3"]:
                v = "VOID_NULL_IS_BLIND"
            elif rec["p_familywise_plus1"] < 0.05:
                v = "FAMILYWISE_SIGNIFICANT"
            elif rec["p_percell_plus1"] < 0.05:
                v = "PERCELL_SIGNIFICANT_ONLY"
            else:
                v = "NOT_SIGNIFICANT"
            rec["my_verdict"] = v
            allrows.append(rec)

RP = pd.DataFrame(allrows)
RP.to_csv(os.path.join(HERE, "REPRODUCTION.csv"), index=False)
pd.DataFrame(summary).to_csv(os.path.join(HERE, "_BAR_ANATOMY.csv"), index=False)
print("\nwrote REPRODUCTION.csv %s and _BAR_ANATOMY.csv" % (RP.shape,))

print("\n=== the sets, by seed (A4_CLEAN_DEC) ===")
sets = {}
for seed in SEEDS:
    s = set(RP[(RP.arm == "A4_CLEAN_DEC") & (RP.seed == seed)
               & (RP.my_verdict == "FAMILYWISE_SIGNIFICANT")]["cell"])
    sets[seed] = s
    print("  seed %d : %d cells   |symdiff vs published 16| = %d"
          % (seed, len(s), len(s ^ PUB16)))
    if s ^ PUB16:
        print("      only mine     : %s" % sorted(s - PUB16))
        print("      only published: %s" % sorted(PUB16 - s))
u = set.union(*sets.values()); i = set.intersection(*sets.values())
print("  across-seed union %d  intersection %d  max pairwise symdiff %d"
      % (len(u), len(i),
         max(len(sets[a] ^ sets[b]) for a in SEEDS for b in SEEDS)))
a1 = set(RP[(RP.arm == "A1_FULL") & (RP.my_verdict == "FAMILYWISE_SIGNIFICANT")]["cell"])
print("  A1_FULL (seed %d) : %d cells" % (SEEDS[0], len(a1)))

json.dump(dict(sets={str(k): sorted(v) for k, v in sets.items()},
               union=sorted(u), intersection=sorted(i),
               a1_full=sorted(a1),
               published_16=sorted(PUB16),
               bar_anatomy=summary),
          open(os.path.join(HERE, "scripts", "_s01.json"), "w"), indent=2)
print("\nDONE s01 (%.0fs)" % (time.time() - t0))
