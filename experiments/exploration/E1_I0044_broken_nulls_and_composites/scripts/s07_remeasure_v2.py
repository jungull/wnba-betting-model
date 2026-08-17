"""S04 -- re-measure E0_I0014's 348 cells under the COMPOSED null, on four self-contained arms.

Composed null (PREREG 1):  idx = block_index(...) then positions reshuffled inside the
receiving block.  One shared gather index per draw across all 58 candidates so the max-|t|
family-wise statistic stays valid.

SIGNED, UNSTANDARDISED draws are saved for every arm and every dependent.  np.abs is used
nowhere at a storage site.  Every stratum arm of every null is saved.

Arms (D101: nothing is ever compared across arms):
  A4_CLEAN_DEC  2023-2024, decision stratum   <- reported first (standing requirement)
  A3_CLEAN      2023-2024, all rows
  A2_DEC        2022-2024, decision stratum
  A1_FULL       2022-2024, all rows            <- the arm the published verdict was formed on
"""
import json, os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
S14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
exec(open(os.path.join(HERE, "scripts", "_rebuild_e14.py")).read())

R = 2000
SEED = 20260808
Z80 = 0.8416212335729143      # Phi^{-1}(0.80)

ARMS = [
    ("A4_CLEAN_DEC", (seas >= 2023) & DEC_MASK),
    ("A3_CLEAN",     (seas >= 2023)),
    ("A2_DEC",       DEC_MASK.copy()),
    ("A1_FULL",      np.ones(n, bool)),
]

def build_blocks(mask, keycol):
    """(season,key) blocks on the SUBSET, in subset-local row indices."""
    idx = np.where(mask)[0]
    sub = pd.DataFrame({"loc": np.arange(len(idx)),
                        "s": seas[idx], "k": f[keycol].to_numpy()[idx]})
    groups = {}
    for (s, k), g in sub.groupby(["s", "k"], sort=False):
        groups.setdefault(s, []).append(g["loc"].to_numpy())
    return groups

def composed_index(groups, m, rng):
    """COMPOSED-2.  E0_I0014's block_index truncates a long donor to its FIRST len(b) rows,
    which for a monotone-in-time candidate leaves block length correlated with the permuted
    value (measured in s04: composed-1 left pts__n_prior_games|minutes_absres centred at
    -3.36 with sd 1.14).  Here the receiving block is filled by a uniform resample of the
    WHOLE donor block, so no donor position is favoured and no ordering survives."""
    idx = np.arange(m)
    for s, blocks in groups.items():
        order = rng.permutation(len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[order[i]]
            idx[b] = don[rng.integers(0, len(don), len(b))]
    return idx

def composed_index_v1(groups, m, rng):
    idx = np.arange(m)
    for s, blocks in groups.items():
        order = rng.permutation(len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[order[i]]
            take = don[np.arange(len(b)) % len(don)]
            idx[b] = rng.permutation(take)
        # note: rng.permutation(take) randomises the ORDER of the donor values inside the
        # receiving block, killing the chronological alignment block_index preserves.
    return idx

allrows = []
t0 = time.time()
for arm, mask in ARMS:
    m = int(mask.sum())
    ss = seas[mask]
    sc = np.asarray(pd.Categorical(ss).codes, dtype=np.int64)
    nsn = int(sc.max() + 1)
    oh = np.zeros((m, nsn)); oh[np.arange(m), sc] = 1.0
    cn = oh.sum(0)
    def dm(M):  # demean within season on this arm
        return M - oh @ ((oh.T @ M) / cn[:, None])
    def tv(ytil, Mtil):
        with np.errstate(invalid="ignore", divide="ignore"):
            sxx = (Mtil * Mtil).sum(0); sxy = Mtil.T @ ytil
            beta = np.where(sxx > 0, sxy / sxx, np.nan)
            sse = float(ytil @ ytil) - beta * sxy
            df = m - nsn - 1
            se = np.sqrt(np.maximum(sse, 0.0) / df / np.where(sxx > 0, sxx, np.nan))
            return np.where(se > 0, beta / se, np.nan), sse

    # arm-local z-score within season then demean -- same construction as the screen
    Xa = X[mask, :]
    Xza = np.nan_to_num(np.column_stack([zwithin(Xa[:, j], ss) for j in range(C)]))
    Xzt = dm(Xza)
    Ya, Yt, SST = {}, {}, {}
    for k, v in DEPS:
        y = v[mask]
        Ya[k] = y
        Yt[k] = dm(y.reshape(-1, 1))[:, 0]
        SST[k] = float(Yt[k] @ Yt[k])
    obs_t = {}; obs_dr2 = {}
    for k, _ in DEPS:
        tt, sse = tv(Yt[k], Xzt)
        obs_t[k] = tt
        obs_dr2[k] = (SST[k] - sse) / SST[k]

    gpa = build_blocks(mask, "player_id"); gta = build_blocks(mask, "team_id")
    nbp = sum(len(v) for v in gpa.values()); nbt = sum(len(v) for v in gta.values())
    print("\n=== %s  n=%d  seasons=%s  player-blocks=%d  team-blocks=%d ==="
          % (arm, m, sorted(set(ss.tolist())), nbp, nbt), flush=True)

    rng = np.random.default_rng(SEED)
    NT = {k: np.zeros((R, C)) for k, _ in DEPS}     # SIGNED t draws
    for d in range(R):
        ip = composed_index(gpa, m, rng)
        it = composed_index(gta, m, rng)
        Xp = dm(np.where(is_player[None, :], Xza[ip], Xza[it]))
        for k, _ in DEPS:
            NT[k][d] = tv(Yt[k], Xp)[0]
        if (d + 1) % 500 == 0:
            print("   draw %d/%d  (%.0fs)" % (d + 1, R, time.time() - t0), flush=True)

    # family-wise max-|t| bar over the whole 348-cell family, per draw, shared index
    maxt = np.nanmax(np.abs(np.concatenate([NT[k] for k, _ in DEPS], axis=1)), axis=1)
    bar_fw = float(np.nanpercentile(maxt, 95))

    np.savez_compressed(os.path.join(HERE, "nulls", "composed2_null_%s.npz" % arm),
                        arm=np.array([arm]), n=np.array([m]), R=np.array([R]),
                        seed=np.array([SEED]),
                        names=np.array(names), dependents=np.array([k for k, _ in DEPS]),
                        n_blocks_player=np.array([nbp]), n_blocks_team=np.array([nbt]),
                        maxt_familywise=maxt,
                        **{("t_signed__" + k): NT[k] for k, _ in DEPS},
                        **{("observed_t__" + k): obs_t[k] for k, _ in DEPS},
                        **{("observed_dr2__" + k): obs_dr2[k] for k, _ in DEPS})

    for j, nm in enumerate(names):
        nb = nbp if is_player[j] else nbt
        for k, _ in DEPS:
            dv = NT[k][:, j]
            fin = np.isfinite(dv)
            dvf = dv[fin]
            if len(dvf) == 0:
                allrows.append(dict(arm=arm, screen="E0_I0014_residual_heterogeneity",
                                    cell="%s|%s" % (nm, k), candidate=nm, dependent=k,
                                    n=m, n_blocks=nb, n_draws_finite=0))
                continue
            a = np.abs(dvf)
            obs = obs_t[k][j]
            sd_signed = float(dvf.std(ddof=1))
            bar_pc = float(np.percentile(a, 97.5))
            mde_pc = (bar_pc + Z80 * sd_signed) ** 2 / m
            mde_fw = (bar_fw + Z80 * sd_signed) ** 2 / m
            allrows.append(dict(
                arm=arm, screen="E0_I0014_residual_heterogeneity",
                cell="%s|%s" % (nm, k), candidate=nm, dependent=k,
                n=m, n_blocks=nb, n_draws_finite=int(fin.sum()),
                observed_t=float(obs) if np.isfinite(obs) else np.nan,
                observed_dr2=float(obs_dr2[k][j]) if np.isfinite(obs_dr2[k][j]) else np.nan,
                null_mean_signed_t=float(dvf.mean()), null_sd_signed_t=sd_signed,
                null_mean_abs_t=float(a.mean()), null_sd_abs_t=float(a.std(ddof=1)),
                degeneracy_ratio=float(a.mean() / a.std(ddof=1)) if a.std(ddof=1) > 0 else np.inf,
                n_unique_draws=int(len(np.unique(dvf))),
                p_two_sided=float(np.mean(a >= abs(obs))) if np.isfinite(obs) else np.nan,
                bar_percell_abs_t=bar_pc, bar_familywise_abs_t=bar_fw,
                mde80_percell=float(mde_pc), mde80_familywise=float(mde_fw),
                floor_basis="ANALYTIC",
                null_mean_gt_observed=bool(np.isfinite(obs) and a.mean() > abs(obs)),
                z_obs_vs_null=(float((abs(obs) - a.mean()) / a.std(ddof=1))
                               if (np.isfinite(obs) and a.std(ddof=1) > 0) else np.nan),
            ))

RM = pd.DataFrame(allrows)
RM.to_csv(os.path.join(HERE, "_REMEASURE2_ALL_ARMS.csv"), index=False)
print("\nwrote _REMEASURE2_ALL_ARMS.csv", RM.shape, " elapsed %.0fs" % (time.time() - t0))

# ---- functioning test (PREREG P1) on the broken cells
BD = pd.read_csv(os.path.join(HERE, "_E0_I0014_CELL_DIAG.csv"))
brk = set(BD.loc[BD["is_broken"], "cell"])
sub = RM[RM["cell"].isin(brk)].copy()
sub["functions"] = (sub["null_mean_signed_t"].abs() < 0.20) & \
                   sub["degeneracy_ratio"].between(1.10, 1.60)
print("\n=== PREREG P1: composed-null functioning test on the 72 broken cells ===")
print(sub.groupby("arm")["functions"].agg(["size", "sum", "mean"]).to_string())
print("\n--- non-functioning cells on A1_FULL ---")
bad = sub[(sub["arm"] == "A1_FULL") & (~sub["functions"])]
print(bad[["cell", "null_mean_signed_t", "null_sd_signed_t", "null_mean_abs_t",
           "null_sd_abs_t", "degeneracy_ratio", "n_unique_draws"]].to_string(index=False))
print("\n=== whole family functioning on A1_FULL (all 348) ===")
w = RM[RM["arm"] == "A1_FULL"].copy()
w["functions"] = (w["null_mean_signed_t"].abs() < 0.20) & \
                 w["degeneracy_ratio"].between(1.10, 1.60)
print(w["functions"].value_counts().to_string())
print("median degeneracy ratio (348 cells, A1_FULL): %.4f" % w["degeneracy_ratio"].median())
print("median |mean signed t|      (348 cells, A1_FULL): %.4f"
      % w["null_mean_signed_t"].abs().median())
print("DONE s07")

