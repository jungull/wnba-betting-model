"""S02 -- THE DEGENERATE EXPLANATION.  How much of the signal is just "this player scores more"?

The published base is season fixed effects and NOTHING ELSE.  |residual| is mechanically
related to the level of the response.  This step puts trailing level in the base FROM THE
START and reports the increment over that base.

Bases (PREREG section 4).  B0/B1/B2/B3 are preregistered; B4 is POST-HOC and labelled as such
everywhere it appears.

  B0  season FE only                          <- the published base
  B1  B0 + matched trailing level             (pl_pts_mean5 / pl_min_mean5 / pl_fga_mean5)
  B2  B1 + matched forecast level             (<target>__pred_point)
  B3  B0 + all eight level columns, identical for every cell  (mapping-free control)
  B4  B3 + the three emitted forecast sd columns              (POST-HOC mechanism probe)

Every base gets its OWN composed-2 null over the same 348-cell family, its own bar, its own
p.  Nothing is compared across bases except the ratio dR2(Bk)/dR2(B0), which is stated as a
retained share on one arm, one response, one row set.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa

ARM = "A4_CLEAN_DEC"
mask = ARM_MASKS[ARM]
s00 = json.load(open(os.path.join(HERE, "scripts", "_s00.json")))
CELLS54 = s00["cells54"]
PUB16 = sorted(s00["published_16"])
CV = pd.read_csv(os.path.join(S50, "CORRECTED_VERDICTS.csv"))
VALID = {r["cell"]: str(r["null_validity"]) for _, r in CV[CV.arm == ARM].iterrows()}

BASES = ["B0", "B1", "B2", "B3", "B4"]
POSTHOC = {"B4"}
SD_COLS = ["pts__pred_sd", "minutes__pred_sd", "fga__pred_sd"]


def base_cols(bid, dep):
    if bid == "B4":
        return list(ALL_LEVEL_COLS) + SD_COLS
    return base_cols_for(bid, dep)


CELLNAMES = ["%s|%s" % (nm, k) for k in DEP_NAMES for nm in names]
IX = {c: i for i, c in enumerate(CELLNAMES)}
gp = blocks_on(mask, "player_id")
gt = blocks_on(mask, "team_id")
SEED = SEEDS[0]
t0 = time.time()

# --------------------------------------------------- descriptive: how level-like is each candidate
ctx0 = arm_context(mask)
lvl = {}
for tgt in ("pts", "minutes", "fga"):
    lvl[tgt] = ctx0["dm"](ctx0["Xza"][:, NAME_IX[MATCHED_LEVEL[tgt]]])
desc = []
for cell in CELLS54:
    cand, dep = cell.split("|")
    tgt = dep.split("_")[0]
    x = ctx0["dm"](ctx0["Xza"][:, NAME_IX[cand]])
    y = ctx0["Yt"][dep]
    L = lvl[tgt]
    def cor(a, b):
        sa, sb = a.std(), b.std()
        return float(np.corrcoef(a, b)[0, 1]) if sa > 0 and sb > 0 else np.nan
    desc.append(dict(arm=ARM, cell=cell, candidate=cand, dependent=dep,
                     corr_candidate_vs_matched_trailing_level=cor(x, L),
                     corr_response_vs_matched_trailing_level=cor(y, L),
                     corr_candidate_vs_response=cor(x, y)))
pd.DataFrame(desc).to_csv(os.path.join(HERE, "_LEVEL_CORRELATIONS.csv"), index=False)

rows, bars = [], []
for bid in BASES:
    # group dependents by their base column set so each group needs one projection per draw
    groups = {}
    for k in DEP_NAMES:
        groups.setdefault(tuple(base_cols(bid, k)), []).append(k)
    ctxs = {}
    for bc, deps in groups.items():
        ctxs[bc] = arm_context(mask, extra_base=list(bc))
    m = ctxs[list(groups)[0]]["m"]

    obs_t = np.full(C * len(DEP_NAMES), np.nan)
    obs_dr2 = np.full(C * len(DEP_NAMES), np.nan)
    for bc, deps in groups.items():
        ctx = ctxs[bc]
        for k in deps:
            _b, tt, dd = t_and_dr2(ctx["Yt"][k], ctx["Xzt"], ctx["df"], ctx["SST"][k])
            for j in range(C):
                obs_t[IX["%s|%s" % (names[j], k)]] = tt[j]
                obs_dr2[IX["%s|%s" % (names[j], k)]] = dd[j]

    rng = np.random.default_rng(SEED)
    NT = np.zeros((R_NULL_COMPOSED2, C * len(DEP_NAMES)))
    for d in range(R_NULL_COMPOSED2):
        ip = idx_composed2(gp, m, rng)
        it = idx_composed2(gt, m, rng)
        Xraw = np.where(is_player[None, :], ctxs[list(groups)[0]]["Xza"][ip],
                        ctxs[list(groups)[0]]["Xza"][it])
        for bc, deps in groups.items():
            ctx = ctxs[bc]
            Xp = ctx["resid"](Xraw)
            Ym = np.column_stack([ctx["Yt"][k] for k in deps])
            T = t_many(Ym, Xp, ctx["df"])           # (C, len(deps))
            for di, k in enumerate(deps):
                for j in range(C):
                    NT[d, IX["%s|%s" % (names[j], k)]] = T[j, di]
        if (d + 1) % 500 == 0:
            print("  %s draw %d/%d (%.0fs)" % (bid, d + 1, R_NULL_COMPOSED2,
                                               time.time() - t0), flush=True)
    A = np.abs(NT)
    maxt = np.nanmax(A, axis=1)
    argt = np.nanargmax(A, axis=1)
    bar95 = float(np.nanpercentile(maxt, 95))
    vc = pd.Series([CELLNAMES[i] for i in argt]).value_counts()
    bars.append(dict(arm=ARM, base=bid, posthoc=bid in POSTHOC, seed=SEED,
                     R=R_NULL_COMPOSED2, bar_familywise_q95=bar95,
                     bar_mean=float(maxt.mean()), top_supplier_cell=str(vc.index[0]),
                     top_supplier_share=float(vc.iloc[0] / len(maxt)),
                     n_distinct_suppliers=int(len(vc)),
                     base_columns_example=";".join(base_cols(bid, "pts_absres"))))
    print("%s  bar q95 %.4f  top supplier %s %.3f  distinct %d  (%.0fs)"
          % (bid, bar95, vc.index[0], vc.iloc[0] / len(maxt), len(vc), time.time() - t0),
          flush=True)
    np.savez_compressed(os.path.join(RAW, "composed2_%s_%s_seed%d.npz" % (ARM, bid, SEED)),
                        arm=np.array([ARM]), base=np.array([bid]), seed=np.array([SEED]),
                        n=np.array([m]), R=np.array([R_NULL_COMPOSED2]),
                        cells=np.array(CELLNAMES), t_signed=NT, maxt_familywise=maxt,
                        argmax_cell=argt, observed_t_signed=obs_t, observed_dr2=obs_dr2)

    for cell in CELLS54:
        j = IX[cell]
        dv = NT[:, j]; fin = np.isfinite(dv)
        obs = float(obs_t[j])
        rec = dict(arm=ARM, base=bid, posthoc=bid in POSTHOC, cell=cell,
                   candidate=cell.split("|")[0], dependent=cell.split("|")[1],
                   base_columns=";".join(base_cols(bid, cell.split("|")[1])),
                   n=m, observed_signed_t=obs, observed_dr2=float(obs_dr2[j]),
                   null_mean_signed_t=float(dv[fin].mean()) if fin.any() else np.nan,
                   bar_familywise_q95=bar95,
                   null_validity_from_E1_I0050=VALID.get(cell, "MISSING"))
        rec["blind_flag_T3"] = bool(np.isfinite(rec["null_mean_signed_t"])
                                    and abs(rec["null_mean_signed_t"]) > TOL_BLIND)
        if np.isfinite(obs):
            a = np.abs(dv[fin])
            rec["p_percell_plus1"] = float((np.sum(a >= abs(obs)) + 1) / (len(a) + 1))
            rec["p_familywise_plus1"] = float((np.sum(maxt >= abs(obs)) + 1) / (len(maxt) + 1))
        else:
            rec["p_percell_plus1"] = np.nan; rec["p_familywise_plus1"] = np.nan
        ok = str(rec["null_validity_from_E1_I0050"]).startswith("ACCEPTABLE")
        rec["familywise_significant"] = bool(ok and np.isfinite(rec["p_familywise_plus1"])
                                             and rec["p_familywise_plus1"] < 0.05
                                             and not rec["blind_flag_T3"])
        rows.append(rec)

V = pd.DataFrame(rows)
b0 = V[V.base == "B0"].set_index("cell")["observed_dr2"]
V["dr2_B0"] = V["cell"].map(b0)
V["retained_share_vs_B0"] = V["observed_dr2"] / V["dr2_B0"]
V.to_csv(os.path.join(HERE, "VOLUME_PROXY.csv"), index=False)
pd.DataFrame(bars).to_csv(os.path.join(HERE, "_BAR_ANATOMY_BY_BASE.csv"), index=False)
print("\nwrote VOLUME_PROXY.csv %s" % (V.shape,))

print("\n=== the published 16 under each base (A4_CLEAN_DEC) ===")
piv = V[V.cell.isin(PUB16)].pivot_table(index="cell", columns="base",
                                        values=["observed_dr2", "retained_share_vs_B0",
                                                "p_familywise_plus1"])
pd.set_option("display.width", 250)
print(piv.round(5).to_string())
print("\n=== family-wise survival count among the 16, by base ===")
for bid in BASES:
    s = V[(V.base == bid) & (V.cell.isin(PUB16))]
    print("  %s%s : %2d of 16 still family-wise significant   median retained share %.3f"
          % (bid, " (POST-HOC)" if bid in POSTHOC else "",
             int(s["familywise_significant"].sum()),
             float(s["retained_share_vs_B0"].median())))

json.dump(dict(bases=BASES, posthoc=sorted(POSTHOC), seed=SEED,
               survivors={bid: sorted(V[(V.base == bid) & V.familywise_significant]["cell"])
                          for bid in BASES},
               survivors_within_16={bid: sorted(V[(V.base == bid) & V.familywise_significant
                                                  & V.cell.isin(PUB16)]["cell"])
                                    for bid in BASES},
               bars=bars),
          open(os.path.join(HERE, "scripts", "_s02.json"), "w"), indent=2)
print("\nDONE s02 (%.0fs)" % (time.time() - t0))
