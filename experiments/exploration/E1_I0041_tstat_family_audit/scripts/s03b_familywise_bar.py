"""E1_I0041 s03b -- THE FAMILY-WISE BAR, CALIBRATED ON A LARGE NULL CLOUD.

s03's per-cell arm validated the FORMULA:  MDE80 = (bar + z80*sd_signed)^2 / n  reproduces the
injection-verified floor to 0.99 (median).  Whether the floor is right therefore reduces to
whether `bar` is right.  `bar` is a pure distributional question about the null |t| cloud and
needs no power sweep -- but at K = 348 it is the 0.99985 quantile, which 1,000 draws cannot
estimate.  s03's family-wise arm is therefore RETIRED as not-estimable (its family-level Type-I
came out 0.284, a discreteness artefact of resampling K = 348 values from a 1,000-value cloud;
see DEFECTS.md D-3) and replaced here by a 60,000-draw cloud with a HELD-OUT calibration half.

The question asked here, and nothing else:
    is  t_crit * sd  --  D103's bar -- the value that gives 5 % FAMILY-WISE error at K cells?
for t_crit = 6.686212 (E0_I0014, K=348) and 6.974475 (E0_I0019, K=318), and for sd = sd(|t|)
(the published form) and sd = sd(t) (the corrected form).
"""
import json
import os
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 20410807
ALPHA = 0.05
R_BAR = 30000          # cloud used to SET the bar
R_TEST = 30000         # independent cloud used to MEASURE the family-wise error
O = {}


def hdr(s):
    print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


import importlib.util as _il
_spec = _il.spec_from_file_location(
    "s03", os.path.join(os.path.dirname(os.path.abspath(__file__)), "s03_simulation.py"))
_m = _il.module_from_spec(_spec)
import sys as _sys
_sys.modules["s03"] = _m
_o = _m.__dict__.get("__name__")
_spec.loader.exec_module(_m)          # module guards heavy work behind __main__
build_panel, make_blocks, block_index = _m.build_panel, _m.make_blocks, _m.block_index
demean_within, t_from_parts = _m.demean_within, _m.t_from_parts


# ---------------------------------------------------------------- vectorised block_index ------
class FastBlocks:
    """Vectorised equivalent of rh_base.block_index:398-409.  Asserted identical to the literal
    loop implementation on the same rng stream before it is used."""

    def __init__(self, groups, n):
        self.n = n
        self.seasons = list(groups.keys())
        self.rows = {}
        for s, blocks in groups.items():
            flat = np.concatenate(blocks)
            lens = np.array([len(b) for b in blocks])
            starts = np.concatenate([[0], np.cumsum(lens)[:-1]])
            tgt = np.repeat(np.arange(len(blocks)), lens)
            pos = np.concatenate([np.arange(L) for L in lens])
            self.rows[s] = dict(flat=flat, lens=lens, starts=starts, tgt=tgt, pos=pos)

    def draw(self, rng):
        idx = np.arange(self.n)
        for s in self.seasons:
            d = self.rows[s]
            order = rng.permutation(len(d["lens"]))
            ds = d["starts"][order][d["tgt"]]
            dl = d["lens"][order][d["tgt"]]
            idx[d["flat"]] = d["flat"][ds + (d["pos"] % dl)]
        return idx


def null_cloud(x_raw, yt, seas, n_seas, fb, n, R, seed):
    rng = np.random.default_rng(seed)
    out = np.empty(R)
    syy0 = float(yt @ yt)
    for r in range(R):
        ip = fb.draw(rng)
        xp = demean_within(x_raw[ip], seas, n_seas)
        sxx = float(xp @ xp)
        out[r] = t_from_parts(float(xp @ yt), sxx, syy0, n) if sxx > 0 else np.nan
    return out[np.isfinite(out)]


if __name__ == "__main__":
    t0 = time.time()
    CONDS = []
    for nblk, K, tcf, tag in ((475, 348, 6.686212, "E0_I0014_player475"),
                              (36, 348, 6.686212, "E0_I0014_team36"),
                              (489, 318, 6.974475, "E0_I0019_playerseason489"),
                              (1486, 318, 6.974475, "E0_I0019_teamgame1486")):
        for w in (0.10, 0.80):
            for rho in (0.0, 0.5):
                CONDS.append(dict(tag=tag, n_blocks=nblk, K=K, t_crit_fw=tcf, w_between=w,
                                  rho=rho, lam=20, seasons=4))

    hdr("A. VECTORISED block_index MUST BE IDENTICAL TO THE LITERAL LOOP")
    rng = np.random.default_rng(SEED)
    seas, blk, y_raw, x_raw = build_panel(rng, 64, 4, 12, 0.5, 0.0)
    groups = make_blocks(seas, blk)
    fb = FastBlocks(groups, len(y_raw))
    ok = True
    for t in range(20):
        a = block_index(groups, len(y_raw), np.random.default_rng(1000 + t))
        b = fb.draw(np.random.default_rng(1000 + t))
        ok &= bool(np.array_equal(a, b))
    print("  20 draws, literal loop vs vectorised: %s" % ("IDENTICAL" if ok else "*** DIFFER ***"))
    assert ok, "vectorised block_index does not reproduce the literal implementation"
    O["vectorisation_identical"] = True

    hdr("B. THE BAR, ON A %d-DRAW CLOUD WITH A HELD-OUT %d-DRAW TEST CLOUD" % (R_BAR, R_TEST))
    rows = []
    for ci, cd in enumerate(CONDS):
        rng = np.random.default_rng(SEED + 131 * ci)
        seas, blk, y_raw, x_raw = build_panel(rng, cd["n_blocks"], cd["seasons"], cd["lam"],
                                              cd["w_between"], cd["rho"])
        n = len(y_raw)
        n_seas = int(seas.max()) + 1
        groups = make_blocks(seas, blk)
        fb = FastBlocks(groups, n)
        yt = demean_within(y_raw, seas, n_seas)
        tc = null_cloud(x_raw, yt, seas, n_seas, fb, n, R_BAR, SEED + 7 + ci)
        te = null_cloud(x_raw, yt, seas, n_seas, fb, n, R_TEST, SEED + 90001 + ci)
        at, ae = np.abs(tc), np.abs(te)
        sd_signed = float(tc.std(ddof=1))
        sd_abs = float(at.std(ddof=1))
        K = cd["K"]
        p_cell = 1.0 - (1.0 - ALPHA) ** (1.0 / K)          # Sidak per-cell alpha
        bar_exact = float(np.quantile(at, 1.0 - p_cell))
        bar_pub_folded = cd["t_crit_fw"] * sd_abs
        bar_pub_signed = cd["t_crit_fw"] * sd_signed

        def fam_err(bar):
            """P(any of K independent cells exceeds bar), from the HELD-OUT cloud, analytically
            from the per-cell exceedance rate -- no resampling, so no discreteness artefact."""
            pc = float((ae >= bar).mean())
            return 1.0 - (1.0 - pc) ** K, pc

        e_exact, pc_exact = fam_err(bar_exact)
        e_fold, pc_fold = fam_err(bar_pub_folded)
        e_sign, pc_sign = fam_err(bar_pub_signed)
        rows.append(dict(**cd, n=n, R_bar=len(tc), R_test=len(ae),
                         sd_signed=sd_signed, sd_abs=sd_abs,
                         fold_factor=sd_signed / sd_abs,
                         sidak_percell_alpha=p_cell,
                         bar_exact=bar_exact, bar_exact_in_sd_signed=bar_exact / sd_signed,
                         bar_pub_folded=bar_pub_folded, bar_pub_signed=bar_pub_signed,
                         famerr_exact=e_exact, famerr_pub_folded=e_fold,
                         famerr_pub_signed=e_sign,
                         percell_exceed_exact=pc_exact, percell_exceed_folded=pc_fold,
                         percell_exceed_signed=pc_sign,
                         mde_ratio_pub_folded=(bar_pub_folded + 0.8416212335729143 * sd_signed) ** 2
                         / (bar_exact + 0.8416212335729143 * sd_signed) ** 2,
                         mde_ratio_pub_signed=(bar_pub_signed + 0.8416212335729143 * sd_signed) ** 2
                         / (bar_exact + 0.8416212335729143 * sd_signed) ** 2))
        print("  %-26s nb=%-5d w=%.2f rho=%.1f  sd(t)=%.3f  bar_exact=%.3f (=%.2f sd)  "
              "bar_pub_folded=%.3f  famerr: exact=%.4f folded=%.4f signed=%.4f  %.0fs"
              % (cd["tag"], cd["n_blocks"], cd["w_between"], cd["rho"], sd_signed, bar_exact,
                 bar_exact / sd_signed, bar_pub_folded, e_exact, e_fold, e_sign,
                 time.time() - t0))

    B = pd.DataFrame(rows)
    B.to_csv(os.path.join(HERE, "FAMILYWISE_BAR.csv"), index=False)

    hdr("C. SUMMARY -- is t_crit the right multiplier?")
    print("  target family-wise error = %.3f" % ALPHA)
    for tag, g in B.groupby("tag"):
        print("\n  %s (K=%d, t_crit=%.6f)" % (tag, g["K"].iloc[0], g["t_crit_fw"].iloc[0]))
        print("    exact bar, in units of sd(t)          : median %.3f  (t_crit is %.3f)"
              % (g["bar_exact_in_sd_signed"].median(), g["t_crit_fw"].iloc[0]))
        print("    family-wise error at the exact bar    : median %.4f" % g["famerr_exact"].median())
        print("    family-wise error at t_crit*sd(|t|)   : median %.4f  <- PUBLISHED, E0_I0014"
              % g["famerr_pub_folded"].median())
        print("    family-wise error at t_crit*sd(t)     : median %.4f  <- PUBLISHED, E0_I0019"
              % g["famerr_pub_signed"].median())
        print("    MDE ratio published/correct, folded   : median %.4f"
              % g["mde_ratio_pub_folded"].median())
        print("    MDE ratio published/correct, signed   : median %.4f"
              % g["mde_ratio_pub_signed"].median())
    O["by_tag"] = {k: dict(bar_in_sd=float(g["bar_exact_in_sd_signed"].median()),
                           t_crit=float(g["t_crit_fw"].iloc[0]),
                           famerr_exact=float(g["famerr_exact"].median()),
                           famerr_folded=float(g["famerr_pub_folded"].median()),
                           famerr_signed=float(g["famerr_pub_signed"].median()),
                           mde_ratio_folded=float(g["mde_ratio_pub_folded"].median()),
                           mde_ratio_signed=float(g["mde_ratio_pub_signed"].median()))
                   for k, g in B.groupby("tag")}
    json.dump(O, open(os.path.join(HERE, "_s03b.json"), "w"), indent=2, default=str)
    print("\nwrote FAMILYWISE_BAR.csv, _s03b.json   total %.0fs" % (time.time() - t0))
