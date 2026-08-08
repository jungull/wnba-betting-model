"""s04_power.py -- STAGE 2.  THE POWER CURVES.

METHOD, and why it is exact rather than approximate.

  For each (stratum, base, null) cell the carrier is permuted BY THE PROGRAMME'S OWN NULL.  A
  permuted carrier x_r has the carrier's REAL marginal distribution and REAL grouping structure
  (that is what the kit's schemes preserve by construction) and, under the null that generated
  it, no association with the response beyond chance.  The planted effect is then ADDED TO THE
  RESPONSE along x_r:

        y(delta) = y_real + c * xt_r ,    c = sqrt(delta * SST0 / (xt_r . xt_r))

  where xt_r is x_r residualised on the base.  Nothing is simulated from scratch; the response
  is the real one and the carrier is a real column with its structure intact.

  BECAUSE the base design matrix X does not change and xt_r is already orthogonal to X:

        e(delta)   = e + c * xt_r                                   (exactly)
        SST(delta) = SST + 2c*(e.xt_r) + c^2*(xt_r.xt_r)            (exactly)
        dR2(delta) = ((e.xt_r + c*(xt_r.xt_r))^2 / (xt_r.xt_r)) / SST(delta)

  so the whole delta grid is closed-form from two dot products per replicate.  No refit is
  approximated away -- this IS the refit, written out.  Asserted against a literal BaseFit
  refit on a random subsample before the sweep runs.

  AT delta = 0 the statistic is literally a draw from that null, so the type-I rate is 0.05 by
  construction and the delta=0 row of every curve is a machinery check, not a result.

  The null calibration draws (mu, sigma, t_crit) come from a SEPARATE kit pass with a DIFFERENT
  seed, so the replicates are never standardised by their own draws.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from df_base import (BASES, CARRIER_OPP, CARRIER_PLAYER, D089_NPZ, N_DRAWS, OUT, OUTCOME, SEED,
                     BaseFit, hdr, load_frame, sk, stratum_mask)

R_REPS = 2000
SEED_POWER = SEED + 101      # deliberately NOT the calibration seed
DELTAS = np.concatenate([[0.0], np.geomspace(1e-5, 1e-2, 25)])
FAMILY_SIZES = [1, 18, 39, 44, 132, 154, 250, 318, 348]

NULLS = [
    ("N_A_within_player_cyclic", CARRIER_PLAYER, "perm_cyclic", ["player_id", "season"], None),
    ("N_B_entity_swap_team_season", CARRIER_PLAYER, "entity_swap", ["team_id", "season"], None),
    ("N_C_entity_swap_opp_team_season", CARRIER_OPP, "entity_swap", ["opp_team_id", "season"], None),
    ("N_D_within_date_opp_swap", CARRIER_OPP, "perm_between", ["opp_team_id", "game_id"],
     "game_date"),
    ("N_R_row_level_CONTRAST_ONLY", CARRIER_PLAYER, "perm_row", sk.ROW_LEVEL, None),
    ("N_R_row_level_CONTRAST_ONLY_OPP", CARRIER_OPP, "perm_row", sk.ROW_LEVEL, None),
]
DESIGNS = [(s, b) for s in ("POOLED", "DECISION") for b in ("B_SINGLE", "B_COMPLETE")]


# ============================================================ family-wise thresholds ==========
def familywise_thresholds(seed=SEED):
    """q95 of max-t over K cells, taken from THE REAL 154-cell x 600-draw null matrix that
    E1_I0018 (D089) left on disk, so the between-cell correlation is this programme's own."""
    z = np.load(D089_NPZ, allow_pickle=True)
    out = {}
    rng = np.random.default_rng(seed)
    for arm, key in (("N1_within", "draws_N1_within"), ("N2_entity_swap", "draws_N2_entity_swap")):
        D = z[key].astype(float)                        # (154, 600)
        mu = D.mean(axis=1, keepdims=True)
        sd = D.std(axis=1, ddof=1, keepdims=True)
        sd = np.where(sd > 1e-300, sd, np.nan)
        T = (D - mu) / sd                               # standardised per cell
        nc = T.shape[0]
        for K in FAMILY_SIZES:
            qs = []
            for _ in range(400):
                repl = K > nc
                idx = rng.choice(nc, size=K, replace=repl)
                qs.append(np.nanquantile(np.nanmax(T[idx], axis=0), 0.95))
            out[(arm, K)] = dict(q95_maxt=float(np.median(qs)),
                                 q95_maxt_lo=float(np.quantile(qs, 0.1)),
                                 q95_maxt_hi=float(np.quantile(qs, 0.9)),
                                 extrapolated_beyond_real_family=bool(K > nc),
                                 real_family_size=int(nc))
    return out


# ============================================================ per-cell machinery ==============
def cell_arrays(f, sname, bname, carrier):
    basecols = BASES[bname]
    cols = [OUTCOME] + basecols + [carrier]
    m = stratum_mask(f, sname).copy()
    for c in cols:
        m &= np.isfinite(pd.to_numeric(f[c], errors="coerce").to_numpy(float))
    sub = f.loc[m].reset_index(drop=True)
    sk.assert_partition(sub, verbose=False)
    y = sub[OUTCOME].to_numpy(float)
    B = sub[basecols].to_numpy(float)
    bf = BaseFit(y, B)
    return sub, y, B, bf


def kit_pass(bf, sub, carrier, kind, level, block, n_draws, seed, capture):
    """One kit permutation pass.  `capture` collects (a, b) = (e.xt, xt.xt) for every draw."""
    d = sub[["season", "player_id", "team_id", "opp_team_id", "game_id", "game_date"]].copy()
    d["feat"] = sub[carrier].to_numpy(float)

    def stat_fn(dfr, _bf=bf, _cap=capture):
        x = pd.to_numeric(dfr["feat"], errors="coerce").to_numpy(float)
        xt = _bf.resid_x(x)
        b = float(xt @ xt)
        a = float(_bf.e @ xt)
        _cap.append((a, b))
        if b <= 1e-12:
            return 0.0
        return (a * a / b) / _bf.sst

    if kind == "perm_cyclic":
        r = sk.permutation_null(stat_fn, d, level, n_draws, seed, feature_col="feat",
                                scheme=sk.SCHEME_WITHIN_CYCLIC, order_col="game_date",
                                alternative="greater")
    elif kind == "entity_swap":
        r = sk.entity_swap_null(stat_fn, d, level, n_draws, seed, feature_col="feat",
                                date_col="game_date", season_col="season",
                                tiebreak_col="game_id", alternative="greater")
    elif kind == "perm_between":
        r = sk.permutation_null(stat_fn, d, level, n_draws, seed, feature_col="feat",
                                scheme=sk.SCHEME_BETWEEN, block_col=block, alternative="greater")
    elif kind == "perm_row":
        r = sk.permutation_null(stat_fn, d, sk.ROW_LEVEL, n_draws, seed, feature_col="feat",
                                alternative="greater")
    else:
        raise KeyError(kind)
    return r


def dr2_grid(a, b, sst, deltas):
    """Closed-form dR2 over the whole delta grid.  See the module docstring for the derivation."""
    c = np.sqrt(np.maximum(deltas, 0.0) * sst / b)
    num = (a + c * b) ** 2 / b
    den = sst + 2.0 * c * a + c * c * b
    return num / den


def mde_at(deltas, power, target=0.80):
    """Log-linear interpolation of the delta at which power first crosses `target`."""
    d = np.asarray(deltas, float)
    p = np.asarray(power, float)
    ok = d > 0
    d, p = d[ok], p[ok]
    idx = np.where(p >= target)[0]
    if len(idx) == 0:
        return float("nan"), "ABOVE_GRID_MAX_1e-2"
    i = idx[0]
    if i == 0:
        return float(d[0]), "AT_OR_BELOW_GRID_MIN_1e-5"
    x0, x1, y0, y1 = np.log(d[i - 1]), np.log(d[i]), p[i - 1], p[i]
    if y1 == y0:
        return float(d[i]), "OK"
    return float(np.exp(x0 + (target - y0) * (x1 - x0) / (y1 - y0))), "OK"


# ============================================================ main ============================
if __name__ == "__main__":
    t_start = time.time()
    hdr("A. FRAME + FAMILY-WISE THRESHOLDS FROM THE REAL D089 NULL MATRIX")
    f = load_frame(verbose=False)
    print("  frame %s" % (f.shape,))
    FW = familywise_thresholds()
    fwrows = [dict(arm=k[0], K=k[1], **v) for k, v in FW.items()]
    pd.DataFrame(fwrows).to_csv(os.path.join(OUT, "s04_familywise_thresholds.csv"), index=False)
    print(pd.DataFrame(fwrows).to_string(index=False))

    hdr("B. CLOSED-FORM dR2 vs A LITERAL REFIT (must agree to ~1e-12)")
    sub, y, B, bf = cell_arrays(f, "POOLED", "B_SINGLE", CARRIER_PLAYER)
    rng = np.random.default_rng(7)
    worst = 0.0
    for _ in range(25):
        xr = rng.permutation(sub[CARRIER_PLAYER].to_numpy(float))
        xt = bf.resid_x(xr)
        a, b2 = float(bf.e @ xt), float(xt @ xt)
        for dlt in (1e-5, 1e-3, 1e-2):
            c = float(np.sqrt(dlt * bf.sst / b2))
            closed = dr2_grid(a, b2, bf.sst, np.array([dlt]))[0]
            literal = BaseFit(y + c * xt, B).dr2(xr)
            worst = max(worst, abs(closed - literal))
    print("  worst |closed-form - literal refit| over 75 checks = %.3e" % worst)
    assert worst < 1e-10, "closed form does not reproduce the refit"

    hdr("C. POWER SWEEP -- %d replicates x %d deltas x %d design-null cells"
        % (R_REPS, len(DELTAS), len(DESIGNS) * len(NULLS)))
    rows, tirows = [], []
    cal_meta = pd.read_csv(os.path.join(OUT, "s03_null_meta.csv"))
    for sname, bname in DESIGNS:
        for nname, carrier, kind, level, block in NULLS:
            t0 = time.time()
            sub, y, B, bf = cell_arrays(f, sname, bname, carrier)
            # --- null calibration: an INDEPENDENT kit pass, seed = SEED (matches s03) ---------
            cap_cal = []
            rcal = kit_pass(bf, sub, carrier, kind, level, block, N_DRAWS, SEED, cap_cal)
            cal = np.asarray(rcal["draws"], float)
            mu, sd = float(np.nanmean(cal)), float(np.nanstd(cal, ddof=1))
            tcal = (cal - mu) / sd
            t_crit_percell = float(np.nanquantile(tcal, 0.95))
            # --- power replicates: a DIFFERENT seed ------------------------------------------
            cap = []
            kit_pass(bf, sub, carrier, kind, level, block, R_REPS, SEED_POWER, cap)
            A = np.array([c[0] for c in cap], float)
            Bd = np.array([c[1] for c in cap], float)
            good = np.isfinite(A) & np.isfinite(Bd) & (Bd > 1e-12)
            A, Bd = A[good], Bd[good]
            DR = np.vstack([dr2_grid(A[i], Bd[i], bf.sst, DELTAS) for i in range(len(A))])
            T = (DR - mu) / sd
            # sigma drift check (pre-committed): sd of the delta=1e-2 statistic vs delta=0
            drift = float(abs(np.nanstd(DR[:, -1], ddof=1) - np.nanstd(DR[:, 0], ddof=1))
                          / np.nanstd(DR[:, 0], ddof=1))
            pw_cell = (T >= t_crit_percell).mean(axis=0)
            arm = "N2_entity_swap" if "entity_swap" in nname or "opp_swap" in nname \
                else "N1_within"
            for K in FAMILY_SIZES:
                tc = FW[(arm, K)]["q95_maxt"]
                pw = (T >= tc).mean(axis=0)
                m, st = mde_at(DELTAS, pw)
                for di, dlt in enumerate(DELTAS):
                    rows.append(dict(stratum=sname, base=bname, null=nname, carrier=carrier,
                                     n=int(len(sub)), n_clusters=int(rcal.get("n_groups", -1)),
                                     family_size_K=K, planted_dr2=float(dlt),
                                     power=float(pw[di]),
                                     power_per_cell_alpha05=float(pw_cell[di]),
                                     median_realised_dr2=float(np.nanmedian(DR[:, di])),
                                     t_crit_familywise=float(tc),
                                     t_crit_per_cell=t_crit_percell,
                                     null_mean=mu, null_sd=sd, R=int(len(A))))
                tirows.append(dict(stratum=sname, base=bname, null=nname, carrier=carrier,
                                   n=int(len(sub)), n_clusters=int(rcal.get("n_groups", -1)),
                                   family_size_K=K, mde80_familywise=m, mde80_status=st,
                                   mde80_per_cell=mde_at(DELTAS, pw_cell)[0],
                                   type1_at_delta0_familywise=float(pw[0]),
                                   type1_at_delta0_per_cell=float(pw_cell[0]),
                                   null_mean=mu, null_sd=sd,
                                   sigma_drift_delta1e2_vs_0=drift,
                                   t_crit_familywise=float(tc),
                                   t_crit_per_cell=t_crit_percell))
            print("  %-9s %-11s %-32s n=%-6d grp=%-5s mu=%.2e sd=%.2e  typeI(cell)=%.3f "
                  "drift=%.3f  MDE80(K=1)=%s  %5.1fs"
                  % (sname, bname, nname, len(sub), rcal.get("n_groups", -1), mu, sd,
                     pw_cell[0], drift,
                     ("%.2e" % mde_at(DELTAS, pw_cell)[0]), time.time() - t0))
            pd.DataFrame(rows).to_csv(os.path.join(OUT, "s04_power_curves_partial.csv"),
                                      index=False)

    pc = pd.DataFrame(rows)
    pc.to_csv(os.path.join(OUT, "power_curves.csv"), index=False)
    mm = pd.DataFrame(tirows)
    mm.to_csv(os.path.join(OUT, "s04_mde_table.csv"), index=False)
    print("\n  wrote power_curves.csv (%d rows) and s04_mde_table.csv (%d rows)  total %.1fs"
          % (len(pc), len(mm), time.time() - t_start))

    hdr("D. MDE80 AT 80%% POWER -- family-wise K=1 (per-cell) and the ledger's real K values")
    piv = mm[mm["family_size_K"].isin([1, 44, 132, 318, 348])].pivot_table(
        index=["stratum", "base", "null", "n", "n_clusters"],
        columns="family_size_K", values="mde80_familywise")
    print(piv.to_string())
