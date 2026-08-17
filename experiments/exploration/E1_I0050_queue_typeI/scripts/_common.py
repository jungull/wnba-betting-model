"""Shared loader for E1_I0050.  Re-uses E1_I0044's exact reconstruction of E0_I0014's
screen matrices (verified there to 0.000e+00 on vsb and 3.9e-15 relative on t_classical).

PARTITION GUARD: 2021-2024 only.  2025/26 is a sealed confirmation holdout and is never
opened.  The guard is asserted here and re-asserted by every caller.

Nothing in this module writes outside experiments/exploration/E1_I0050_queue_typeI/.
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
S14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
S44 = os.path.join(EXPL, "E1_I0044_broken_nulls_and_composites")
S26 = os.path.join(EXPL, "E1_I0026_detection_floor")

# E1_I0044's rebuild script is read-only input; exec'd, never modified.
exec(open(os.path.join(S44, "scripts", "_rebuild_e14.py")).read())

# --- re-assert the partition guard in this screen's own name -------------------
assert f["season"].max() <= 2024, "PARTITION VIOLATION: season > 2024"
assert f["season"].min() >= 2021, "PARTITION VIOLATION: season < 2021"
assert pd.to_datetime(f["gdate"]).max() < pd.Timestamp("2025-01-01"), "PARTITION VIOLATION"
SEASONS_PRESENT = sorted(set(f["season"].tolist()))

Z80 = 0.8416212335729143          # Phi^{-1}(0.80)

ARM_MASKS = {
    "A4_CLEAN_DEC": (seas >= 2023) & DEC_MASK,
    "A3_CLEAN":     (seas >= 2023),
    "A2_DEC":       DEC_MASK.copy(),
    "A1_FULL":      np.ones(n, bool),
}


def arm_context(mask):
    """Everything a self-contained arm needs.  Own rows, own season dummies, own SST,
    own base, own blocks.  No quantity is ever compared across arms (D101)."""
    m = int(mask.sum())
    ss = seas[mask]
    sc = np.asarray(pd.Categorical(ss).codes, dtype=np.int64)
    nsn = int(sc.max() + 1)
    oh = np.zeros((m, nsn))
    oh[np.arange(m), sc] = 1.0
    cnt = oh.sum(0)

    def dm(M):
        M = np.asarray(M, float)
        return M - oh @ ((oh.T @ M) / cnt[:, None])

    Xa = X[mask, :]
    Xza = np.nan_to_num(np.column_stack([zwithin(Xa[:, j], ss) for j in range(C)]))
    Xzt = dm(Xza)
    Y, Yt, SST = {}, {}, {}
    for k, v in DEPS:
        y = v[mask]
        Y[k] = y
        Yt[k] = dm(y.reshape(-1, 1))[:, 0]
        SST[k] = float(Yt[k] @ Yt[k])
    return dict(m=m, ss=ss, nsn=nsn, dm=dm, Xza=Xza, Xzt=Xzt, Y=Y, Yt=Yt, SST=SST,
                df=m - nsn - 1, mask=mask)


def blocks_on(mask, keycol):
    """(season, key) blocks in subset-local row indices."""
    idx = np.where(mask)[0]
    sub = pd.DataFrame({"loc": np.arange(len(idx)), "s": seas[idx],
                        "k": f[keycol].to_numpy()[idx]})
    g = {}
    for (s, k), gg in sub.groupby(["s", "k"], sort=False):
        g.setdefault(s, []).append(gg["loc"].to_numpy())
    return g


def t_of(ytil, Mt, df):
    """t of ytil on each column of the ALREADY-demeaned matrix Mt.  SIGNED."""
    with np.errstate(invalid="ignore", divide="ignore"):
        sxx = (Mt * Mt).sum(0)
        sxy = Mt.T @ ytil
        beta = np.where(sxx > 0, sxy / sxx, np.nan)
        sse = float(ytil @ ytil) - beta * sxy
        se = np.sqrt(np.maximum(sse, 0.0) / df / np.where(sxx > 0, sxx, np.nan))
        return np.where(se > 0, beta / se, np.nan)


def t_many(Ytil, Mt, df):
    """SIGNED t for every (column of Mt) x (column of Ytil).  Returns (ncolM, ncolY).
    One BLAS call; this is what makes 54 cells x 1000 replicates affordable."""
    with np.errstate(invalid="ignore", divide="ignore"):
        sxx = (Mt * Mt).sum(0)[:, None]                 # (M,1)
        sxy = Mt.T @ Ytil                               # (M,B)
        beta = np.where(sxx > 0, sxy / sxx, np.nan)
        yy = (Ytil * Ytil).sum(0)[None, :]              # (1,B)
        sse = yy - beta * sxy
        se = np.sqrt(np.maximum(sse, 0.0) / df / np.where(sxx > 0, sxx, np.nan))
        return np.where(se > 0, beta / se, np.nan)
