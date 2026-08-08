"""E1_I0041 s03 -- THE SIMULATION.  Pre-registered in PREREG.md (sha256 869a92f0...).

Synthetic clustered / unbalanced / autocorrelated panel.  Known effects planted on the ONE
declared contrast (PREREG 3.2).  Three analytic floors compared against an injection-verified
empirical floor, under both threshold regimes.

Every machinery check of PREREG 3.4 is executed and its result printed whether it passes or fails.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z80 = 0.8416212335729143
SEED = 20410807
SEED_POWER = SEED + 101
R_NULL = 800          # null-calibration draws (independent seed)
R_POW = 800           # power replicates (different seed)
DELTAS = np.concatenate([[0.0], np.geomspace(1e-6, 3e-1, 30)])
ALPHA = 0.05
O = {}


def hdr(s):
    print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


# ============================================================== generating process =============
def build_panel(rng, n_blocks, seasons, lam, w_between, rho, block_key="player"):
    """Unbalanced, clustered, AR(1) panel.  Returns (seas, blk, y_raw, x_raw)."""
    seas_l, blk_l, y_l, x_l = [], [], [], []
    per_season = max(1, n_blocks // seasons)
    bid = 0
    for s in range(seasons):
        for _ in range(per_season):
            g = int(np.clip(1 + rng.poisson(lam), 5, 44))       # unbalanced games per block
            # ---- response: block level + AR(1) within-block noise + team-game shock ----------
            a = rng.normal(0.0, 1.0)                            # block random effect
            e = np.empty(g)
            e[0] = rng.normal(0.0, 1.0)
            for i in range(1, g):
                e[i] = rho * e[i - 1] + np.sqrt(max(1 - rho ** 2, 1e-12)) * rng.normal()
            tg = rng.normal(0.0, 0.6, size=g)                   # team-game shock
            y = a + e + tg
            # ---- carrier: block-constant part + within-block part ---------------------------
            b = rng.normal(0.0, 1.0)
            u = rng.normal(0.0, 1.0, size=g)
            x = np.sqrt(w_between) * b + np.sqrt(max(1 - w_between, 0.0)) * u
            seas_l.append(np.full(g, s))
            blk_l.append(np.full(g, bid))
            y_l.append(y)
            x_l.append(x)
            bid += 1
    return (np.concatenate(seas_l), np.concatenate(blk_l),
            np.concatenate(y_l), np.concatenate(x_l))


def make_blocks(seas, blk):
    """rh_base.make_blocks equivalent: ordered row-index blocks, one per (season, key)."""
    groups = {}
    order = np.lexsort((blk, seas))
    s_o, b_o = seas[order], blk[order]
    start = 0
    for i in range(1, len(order) + 1):
        if i == len(order) or s_o[i] != s_o[start] or b_o[i] != b_o[start]:
            groups.setdefault(int(s_o[start]), []).append(order[start:i])
            start = i
    return groups


def block_index(groups, n, rng):
    """Literal re-implementation of rh_base.block_index:398-409 -- whole blocks reassigned within
    season, gathering donor rows cycling modulo donor length."""
    idx = np.arange(n)
    for s, blocks in groups.items():
        order = rng.permutation(len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[order[i]]
            idx[b] = don[np.arange(len(b)) % len(don)]
    return idx


def demean_within(v, seas_codes, n_seas):
    """rh_base.demean_within:348-354, vectorised."""
    sums = np.bincount(seas_codes, weights=v, minlength=n_seas)
    cnts = np.bincount(seas_codes, minlength=n_seas).astype(float)
    return v - (sums / np.maximum(cnts, 1))[seas_codes]


def t_from_parts(sxy, sxx, syy, n, k_extra=3):
    """rh_base.tstat:357-370 arithmetic, from precomputed dot products."""
    beta = sxy / sxx
    sse = syy - beta * sxy
    df = n - k_extra - 1
    se = np.sqrt(np.maximum(sse, 0.0) / df / sxx)
    return np.where(se > 0, beta / se, np.nan)


def mde_at(deltas, power, target=0.80):
    """s04_power.mde_at:146-161, verbatim behaviour."""
    d = np.asarray(deltas, float)
    p = np.asarray(power, float)
    ok = d > 0
    d, p = d[ok], p[ok]
    idx = np.where(p >= target)[0]
    if len(idx) == 0:
        return float("nan"), "ABOVE_GRID_MAX"
    i = idx[0]
    if i == 0:
        return float(d[0]), "AT_OR_BELOW_GRID_MIN"
    x0, x1, y0, y1 = np.log(d[i - 1]), np.log(d[i]), p[i - 1], p[i]
    if y1 == y0:
        return float(d[i]), "OK"
    return float(np.exp(x0 + (target - y0) * (x1 - x0) / (y1 - y0))), "OK"


# ============================================================== one condition ==================
def run_condition(cond, verify_closed_form=False):
    rng = np.random.default_rng(cond["seed"])
    seas, blk, y_raw, x_raw = build_panel(rng, cond["n_blocks"], cond["seasons"], cond["lam"],
                                          cond["w_between"], cond["rho"])
    n = len(y_raw)
    n_seas = int(seas.max()) + 1
    groups = make_blocks(seas, blk)
    nb = sum(len(v) for v in groups.values())

    yt = demean_within(y_raw, seas, n_seas)                 # season FE, FWL
    xt_real = demean_within(x_raw, seas, n_seas)
    syy0 = float(yt @ yt)                                   # SST0 -- the declared basis
    sxx_real = float(xt_real @ xt_real)
    yx_real = float(yt @ xt_real)

    # --- null calibration pass (seed A) -------------------------------------------------------
    rng_cal = np.random.default_rng(cond["seed"] + 1)
    tc = np.empty(R_NULL)
    for r in range(R_NULL):
        ip = block_index(groups, n, rng_cal)
        xp = demean_within(x_raw[ip], seas, n_seas)
        sxx = float(xp @ xp)
        if sxx <= 0:
            tc[r] = np.nan
            continue
        tc[r] = t_from_parts(float(xp @ yt), sxx, syy0, n)
    tc = tc[np.isfinite(tc)]
    sd_signed_true = float(tc.std(ddof=1))
    mean_signed = float(tc.mean())
    at = np.abs(tc)
    sd_abs = float(at.std(ddof=1))
    mean_abs = float(at.mean())
    sd_signed_rec = float(np.sqrt(sd_abs ** 2 + mean_abs ** 2))     # S3 recovery
    q_percell = float(np.quantile(at, 1 - ALPHA))
    # family-wise bar: max |t| over K independent cells, simulated from the same null cloud by
    # resampling K draws WITHOUT replacement per pseudo-family (independence is the assumption
    # this makes and it is stated: real cells are correlated, so this bar is an upper bound on
    # the true correlated bar).
    K = cond["K"]
    rr = np.random.default_rng(cond["seed"] + 2)
    mx = np.array([at[rr.integers(0, len(at), K)].max() for _ in range(2000)])
    q_fw = float(np.quantile(mx, 1 - ALPHA))

    # --- power replicates (seed B, deliberately different) -------------------------------------
    rng_p = np.random.default_rng(cond["seed"] + SEED_POWER)
    A1 = np.empty(R_POW)      # xp . yt
    A2 = np.empty(R_POW)      # xp . xt_real
    SX = np.empty(R_POW)      # xp . xp
    for r in range(R_POW):
        ip = block_index(groups, n, rng_p)
        xp = demean_within(x_raw[ip], seas, n_seas)
        A1[r] = float(xp @ yt)
        A2[r] = float(xp @ xt_real)
        SX[r] = float(xp @ xp)
    ok = np.isfinite(A1) & np.isfinite(SX) & (SX > 1e-12)
    A1, A2, SX = A1[ok], A2[ok], SX[ok]

    # closed form over the delta grid:  y(d) = yt + c*xt_real,  c = sqrt(d*SST0/sxx_real)
    c = np.sqrt(np.maximum(DELTAS, 0.0) * syy0 / sxx_real)          # (D,)
    sxy = A1[:, None] + c[None, :] * A2[:, None]                    # (R,D)
    syy = syy0 + 2.0 * c[None, :] * yx_real + (c ** 2)[None, :] * sxx_real
    T = t_from_parts(sxy, SX[:, None], syy, n)

    if verify_closed_form:                                          # S4
        worst = 0.0
        rngv = np.random.default_rng(99)
        for _ in range(25):
            ipv = block_index(groups, n, rngv)
            xpv = demean_within(x_raw[ipv], seas, n_seas)
            for dv in (1e-4, 1e-2, 1e-1):
                cv = float(np.sqrt(dv * syy0 / sxx_real))
                yv = yt + cv * xt_real
                lit = t_from_parts(float(xpv @ yv), float(xpv @ xpv), float(yv @ yv), n)
                cl = t_from_parts(float(xpv @ yt) + cv * float(xpv @ xt_real),
                                  float(xpv @ xpv),
                                  syy0 + 2 * cv * yx_real + cv ** 2 * sxx_real, n)
                worst = max(worst, abs(lit - cl))
        O.setdefault("S4_closed_form_worst", []).append(float(worst))

    # S5: does the permutation null's sd move with the planted effect?
    sd_by_delta = np.nanstd(T, axis=0, ddof=1)
    sd_drift = float(sd_by_delta[-1] / sd_by_delta[0]) if sd_by_delta[0] > 0 else np.nan

    out = {}
    for regime, q in (("per_cell", q_percell), ("family_wise", q_fw)):
        pw = np.nanmean(np.abs(T) >= q, axis=0)
        type1 = float(pw[0])
        m, st = mde_at(DELTAS, pw)
        t_crit = cond["t_crit_fw"] if regime == "family_wise" else 1.959964
        rec = dict(
            **{k: cond[k] for k in ("label", "n_blocks", "seasons", "lam", "w_between",
                                    "rho", "K", "t_crit_fw", "seed")},
            n=n, n_blocks_actual=nb, regime=regime, t_crit_used=t_crit,
            sd_signed_true=sd_signed_true, sd_signed_recovered=sd_signed_rec,
            sd_abs=sd_abs, mean_abs=mean_abs, mean_signed=mean_signed,
            fold_factor_sd=(sd_signed_true / sd_abs) if sd_abs > 0 else np.nan,
            recovery_rel_err=(abs(sd_signed_rec - sd_signed_true) / sd_signed_true
                              if sd_signed_true > 0 else np.nan),
            q_threshold=q, type1_at_delta0=type1, max_power=float(np.nanmax(pw)),
            power_monotone=bool(np.all(np.diff(pw[1:]) >= -0.05)),
            E_inj=m, E_inj_status=st, null_sd_drift_top_vs_zero=sd_drift,
            A_pub_folded=float(((t_crit + Z80) * sd_abs) ** 2 / n),
            A_pub_signed=float(((t_crit + Z80) * sd_signed_true) ** 2 / n),
            A_cor=float((q + Z80 * sd_signed_true) ** 2 / n),
        )
        for k in ("A_pub_folded", "A_pub_signed", "A_cor"):
            rec["ratio_" + k] = (rec[k] / m) if (np.isfinite(m) and m > 0) else np.nan
        out[regime] = rec
    return out


# ============================================================== the grid ======================
if __name__ == "__main__":
    t0 = time.time()
    hdr("A. S4 -- CLOSED FORM vs LITERAL RECOMPUTE (must agree to 1e-10)")
    conds = []
    lab = 0
    # real block counts first: E0_I0014 player 475 / team 36; E0_I0019 player-season 489 /
    # team-game 1486 / team-season 36.  Then a block-count ladder for the law.
    for nblk, K, tcf in ((36, 348, 6.686212), (475, 348, 6.686212),
                         (489, 318, 6.974475), (1486, 318, 6.974475),
                         (64, 348, 6.686212), (128, 318, 6.974475)):
        for w in (0.10, 0.50, 0.80, 1.00):
            for rho in (0.0, 0.5):
                for lam in (12, 30):
                    lab += 1
                    conds.append(dict(label="C%03d" % lab, n_blocks=nblk, seasons=4, lam=lam,
                                      w_between=w, rho=rho, K=K, t_crit_fw=tcf,
                                      seed=SEED + 7919 * lab))
    print("  conditions: %d" % len(conds))

    rows = []
    for i, cd in enumerate(conds):
        try:
            res = run_condition(cd, verify_closed_form=(i < 3))
            for regime, rec in res.items():
                rec["status"] = "OK"
                rows.append(rec)
        except Exception as e:
            rows.append(dict(**cd, regime="BOTH", status="ERROR: %s" % e))
        if (i + 1) % 12 == 0:
            print("    %3d/%d  %.0fs" % (i + 1, len(conds), time.time() - t0))
    S = pd.DataFrame(rows)
    S.to_csv(os.path.join(HERE, "SIMULATION.csv"), index=False)
    print("\n  wrote SIMULATION.csv  rows=%d  (%.0fs)" % (len(S), time.time() - t0))
    print("  S4 worst |closed-form - literal| = %.3e" % max(O["S4_closed_form_worst"]))
    assert max(O["S4_closed_form_worst"]) < 1e-10, "S4 FAILED: closed form does not reproduce"
    O["S4_pass"] = True

    ok = S[S["status"] == "OK"].copy()

    hdr("B. S1 -- TYPE-I RATE OF MY OWN MACHINERY (pre-committed: 0.05 +/- 0.02)")
    for regime, g in ok.groupby("regime"):
        t1 = g["type1_at_delta0"]
        print("  %-12s n=%3d  min=%.4f  p10=%.4f  median=%.4f  p90=%.4f  max=%.4f  "
              "outside [0.03,0.07]: %d"
              % (regime, len(g), t1.min(), t1.quantile(.1), t1.median(), t1.quantile(.9),
                 t1.max(), int(((t1 < 0.03) | (t1 > 0.07)).sum())))
    s1_ok = bool(abs(ok["type1_at_delta0"].median() - 0.05) <= 0.02)
    print("  S1: %s" % ("PASS" if s1_ok else "*** FAIL -- output preserved, nothing reported ***"))
    O["S1"] = dict(passed=s1_ok, median=float(ok["type1_at_delta0"].median()),
                   min=float(ok["type1_at_delta0"].min()),
                   max=float(ok["type1_at_delta0"].max()))

    hdr("C. S2 -- NON-DEGENERACY (power must move, and reach the top of the grid)")
    print("  conditions with max_power >= 0.99 : %d / %d"
          % (int((ok["max_power"] >= 0.99).sum()), len(ok)))
    print("  conditions with power monotone    : %d / %d"
          % (int(ok["power_monotone"].sum()), len(ok)))
    print("  conditions with a finite E_inj    : %d / %d"
          % (int(np.isfinite(ok["E_inj"]).sum()), len(ok)))
    print("  E_inj status counts: %s" % ok["E_inj_status"].value_counts().to_dict())
    O["S2"] = dict(max_power_ge_099=int((ok["max_power"] >= 0.99).sum()), n=int(len(ok)),
                   monotone=int(ok["power_monotone"].sum()),
                   finite_E_inj=int(np.isfinite(ok["E_inj"]).sum()))

    hdr("D. S3 -- THE FOLD RECOVERY sd(t) = sqrt(sd(|t|)^2 + mean(|t|)^2), CHECKED AGAINST TRUTH")
    re_ = ok["recovery_rel_err"].dropna()
    print("  relative error of the recovery: median=%.5f  p90=%.5f  max=%.5f  (n=%d)"
          % (re_.median(), re_.quantile(.9), re_.max(), len(re_)))
    ff = ok["fold_factor_sd"].dropna()
    print("  TRUE fold factor sd(t)/sd(|t|): min=%.4f p10=%.4f median=%.4f p90=%.4f max=%.4f"
          % (ff.min(), ff.quantile(.1), ff.median(), ff.quantile(.9), ff.max()))
    print("  half-normal reference = 1.658855")
    print("  |mean(signed t)| / sd(signed t): median=%.4f  max=%.4f"
          % ((ok["mean_signed"].abs() / ok["sd_signed_true"]).median(),
             (ok["mean_signed"].abs() / ok["sd_signed_true"]).max()))
    O["S3"] = dict(rel_err_median=float(re_.median()), rel_err_p90=float(re_.quantile(.9)),
                   rel_err_max=float(re_.max()), fold_median=float(ff.median()))

    hdr("E. S5 -- DOES THE PERMUTATION NULL'S sd MOVE WITH THE PLANTED EFFECT?")
    dr = ok["null_sd_drift_top_vs_zero"].dropna()
    print("  sd(statistic at delta=0.3) / sd(at delta=0): median=%.4f  p10=%.4f  p90=%.4f"
          % (dr.median(), dr.quantile(.1), dr.quantile(.9)))
    print("  (E1_I0037's two structural gates require a null whose sd GROWS with the effect.)")
    O["S5"] = dict(median=float(dr.median()), p10=float(dr.quantile(.1)),
                   p90=float(dr.quantile(.9)))

    hdr("F. THE RATIO DISTRIBUTION -- analytic floor / injection-verified floor")
    fin = ok[np.isfinite(ok["E_inj"])]
    for regime, g in fin.groupby("regime"):
        print("\n  --- %s (n=%d) ---" % (regime, len(g)))
        for col in ("ratio_A_pub_folded", "ratio_A_pub_signed", "ratio_A_cor"):
            v = g[col].replace([np.inf, -np.inf], np.nan).dropna()
            print("    %-22s min=%.3f p10=%.3f median=%.3f p90=%.3f max=%.3f"
                  % (col.replace("ratio_", ""), v.min(), v.quantile(.1), v.median(),
                     v.quantile(.9), v.max()))
    O["ratios"] = {}
    for regime, g in fin.groupby("regime"):
        O["ratios"][regime] = {}
        for col in ("ratio_A_pub_folded", "ratio_A_pub_signed", "ratio_A_cor"):
            v = g[col].replace([np.inf, -np.inf], np.nan).dropna()
            O["ratios"][regime][col] = dict(n=int(len(v)), min=float(v.min()),
                                            p10=float(v.quantile(.1)),
                                            median=float(v.median()),
                                            p90=float(v.quantile(.9)), max=float(v.max()))

    hdr("G. P4 -- DO THE RATIOS DEPEND ON n, rho, OR IMBALANCE?  (they should not)")
    for by in ("n_blocks", "rho", "lam", "w_between"):
        t = fin[fin["regime"] == "per_cell"].groupby(by).agg(
            n=("label", "size"),
            folded=("ratio_A_pub_folded", "median"),
            signed=("ratio_A_pub_signed", "median"),
            cor=("ratio_A_cor", "median"),
            fold=("fold_factor_sd", "median")).reset_index()
        print("\n  by %s (per_cell regime):" % by)
        print(t.to_string(index=False, float_format=lambda v: "%.4f" % v))

    json.dump(O, open(os.path.join(HERE, "_s03.json"), "w"), indent=2, default=str)
    print("\nwrote _s03.json   total %.0fs" % (time.time() - t0))
