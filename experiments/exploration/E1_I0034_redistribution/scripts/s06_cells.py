"""S06 -- THE 14 PREREGISTERED CELLS, THEIR NULLS, AND THEIR INJECTION-VERIFIED POWER.

Order inside every cell: statistic -> null -> null_mean / null_sd -> MDE80 -> verdict.
No verdict is taken from a null whose power has not first been verified by injection.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb
import s04_prereg

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)

W2 = (2023, 2024)          # PRIMARY scoring window
W1 = (2022, 2023, 2024)    # declared secondary
NDRAW_N2 = 20000
NDRAW_N1 = 2000
NDRAW_N4 = 20000
CHAMP_COL = {"minutes": "min_hat", "fga": "fga_hat", "pts": "pts_hat"}


# --------------------------------------------------------------------------- linear algebra
def design(cols, n=None):
    n = len(cols[0]) if cols else int(n)
    return np.column_stack([np.ones(n)] + list(cols))


def ols(X, y):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return b


def wf_predict(Xcols, y, season, score_seasons, min_train_season):
    """WALK-FORWARD.  Season S is predicted by a fit on seasons [min_train_season, S).
    Returns (yhat over the scored rows mask, per-season coefficient record)."""
    X = design(Xcols, len(y))
    yhat = np.full(len(y), np.nan)
    per = {}
    for s in score_seasons:
        tr = (season < s) & (season >= min_train_season)
        te = (season == s)
        b = ols(X[tr], y[tr])
        yhat[te] = X[te] @ b
        per[int(s)] = {"n_train": int(tr.sum()), "n_score": int(te.sum()),
                       "beta": [float(v) for v in b]}
    return yhat, per


def wf_coef(Xcols, y, season, score_seasons, min_train_season, which):
    """WALK-FORWARD COEFFICIENT, row-count weighted across the scored seasons.
    `which` is the index into [const] + Xcols."""
    X = design(Xcols, len(y))
    num = 0.0; den = 0.0; per = {}
    for s in score_seasons:
        tr = (season < s) & (season >= min_train_season)
        te = (season == s)
        b = ols(X[tr], y[tr])
        w = float(te.sum())
        num += w * b[which]; den += w
        per[int(s)] = {"coef": float(b[which]), "n_train": int(tr.sum()), "n_score": int(w)}
    return float(num / den), per


# --------------------------------------------------------------------------- permutation index
def block_bounds(block_codes):
    order = np.argsort(block_codes, kind="stable")
    cs = np.asarray(block_codes)[order]
    b = np.flatnonzero(np.r_[True, cs[1:] != cs[:-1]])
    sizes = np.diff(np.r_[b, len(cs)])
    return order, b, sizes


def perm_index(order, bounds, sizes, rng):
    """Index array `inv` such that v[inv] is v permuted WITHIN each block."""
    n = len(order)
    perm = np.empty(n, dtype=np.int64)
    for a, k in zip(bounds, sizes):
        perm[a:a + k] = order[a + rng.permutation(k)]
    inv = np.empty(n, dtype=np.int64)
    inv[order] = perm
    return inv


# --------------------------------------------------------------------------- the cells
def main():
    rb.hdr("S06 CELLS")
    pre = s04_prereg.assert_unchanged()
    print("  prereg hash verified: %s" % pre["prereg_sha256"])
    OUTJ = {"prereg_sha256": pre["prereg_sha256"], "cells": {}, "power": {}, "seed": rb.SEED}
    NPZ = {}

    R = pd.read_parquet(os.path.join(rb.OUT, "_rem_frame.parquet"))
    G = pd.read_parquet(os.path.join(rb.OUT, "_tg_frame.parquet"))
    R = R.sort_values(["season", "game_id", "team_id", "player_id"],
                      kind="stable").reset_index(drop=True)
    G = G.sort_values(["season", "game_id", "team_id"], kind="stable").reset_index(drop=True)
    R["posmatch_f"] = R["posmatch"].fillna(0.0)
    assert float(np.abs(R.loc[R["posmatch"].isna(), "u_minutes"]).max()) == 0.0, \
        "posmatch undefined on a row with non-zero freed volume"
    print("  REM rows %d (all seasons); team-games %d" % (len(R), len(G)))

    # ======================================================================= P01 LEAKAGE
    rb.hdr("P01 -- LEAKAGE: does the freed volume leave the established roster?")
    gs = G["season"].to_numpy()
    order_s, b_s, sz_s = block_bounds(gs)         # blocks = seasons, for N4
    for ch in rb.CHANNELS:
        y = G["unest_" + ch].to_numpy(float)
        x = G["freed_" + ch].to_numpy(float)

        def stat(xv, y=y, gs=gs):
            c, _ = wf_coef([xv], y, gs, W2, 2021, 1)
            return c
        real, per = wf_coef([x], y, gs, W2, 2021, 1)
        rng = np.random.default_rng(rb.SEED + 101)
        draws = np.empty(NDRAW_N4)
        for i in range(NDRAW_N4):
            draws[i] = stat(x[perm_index(order_s, b_s, sz_s, rng)])
        nm, nsd = float(draws.mean()), float(draws.std(ddof=1))
        p = float((1.0 + int((np.abs(draws - nm) >= abs(real - nm) - 1e-15).sum()))
                  / (NDRAW_N4 + 1.0))
        m = rb.mde80(nsd)
        print("  P01_%-8s theta %+.5f  p %.4f  null_mean %+.5f  null_sd %.5f  MDE80 %.5f"
              % (ch, real, p, nm, nsd, m))
        print("           per-season: %s" % {k: round(v["coef"], 4) for k, v in per.items()})
        OUTJ["cells"]["P01_LEAKAGE_" + ch] = dict(
            cell="P01_LEAKAGE_" + ch, level="team-game", n=int((G["season"].isin(W2)).sum()),
            row_set="RST-W2", response="volume of players with no established baseline",
            candidate="FREED_" + ch, effect=real, p=p, null_scheme="N4_freed_permute_within_season",
            null_mean=nm, null_sd=nsd, MDE80=m, per_season=per,
            interpretation="theta ~ 1 = full leakage to call-ups; theta ~ 0 = none")
        NPZ["P01_" + ch] = draws

    # ======================================================================= P02 TILT
    rb.hdr("P02 -- ALLOCATION TILT: who absorbs the freed volume?")
    rs = R["season"].to_numpy()
    tgc = pd.factorize(R["tg"])[0]
    order_t, b_t, sz_t = block_bounds(tgc)
    p02_store = {}
    for ch in rb.CHANNELS:
        y = R["d_" + ch].to_numpy(float)
        base5 = R["base5_" + ch].to_numpy(float)
        z = R["z_" + ch].to_numpy(float)
        u = R["u_" + ch].to_numpy(float)

        def stat(b5, zz, y=y, u=u, rs=rs):
            c, _ = wf_coef([b5, zz, u, u * zz], y, rs, W2, 2021, 4)
            return c
        real, per = wf_coef([base5, z, u, u * z], y, rs, W2, 2021, 4)
        rng = np.random.default_rng(rb.SEED + 201)
        draws = np.empty(NDRAW_N1)
        for i in range(NDRAW_N1):
            inv = perm_index(order_t, b_t, sz_t, rng)
            draws[i] = stat(base5[inv], z[inv])
        nm, nsd = float(draws.mean()), float(draws.std(ddof=1))
        p = float((1.0 + int((np.abs(draws - nm) >= abs(real - nm) - 1e-15).sum()))
                  / (NDRAW_N1 + 1.0))
        m = rb.mde80(nsd)
        print("  P02_%-8s gamma %+.5f  p %.4f  null_mean %+.5f  null_sd %.5f  MDE80 %.5f"
              % (ch, real, p, nm, nsd, m))
        print("           per-season: %s" % {k: round(v["coef"], 4) for k, v in per.items()})
        p02_store[ch] = dict(real=real, nsd=nsd, base5=base5, z=z, u=u, y=y)
        OUTJ["cells"]["P02_TILT_" + ch] = dict(
            cell="P02_TILT_" + ch, level="remaining-player-game in team-game",
            n=int((R["season"].isin(W2)).sum()), row_set="RSP-W2", response="delta_" + ch,
            base="1 + base5 + z + u  (mean-reversion main effect IN THE BASE)",
            candidate="u * z", effect=real, p=p,
            null_scheme="N1_within_teamgame_shuffle_of_(base5,z)",
            null_mean=nm, null_sd=nsd, MDE80=m, per_season=per,
            interpretation=("gamma < 0 = the freed volume tilts to the SMALLER-baseline players; "
                            "gamma > 0 = to the larger; gamma ~ 0 = diffuse/uniform"))
        NPZ["P02_" + ch] = draws

    # ======================================================================= P03 / P04
    def forecast_cell(name, ch, y, X0cols, X1cols, min_train, offset=None, frame=R,
                      seed_off=0, extra=None):
        season = frame["season"].to_numpy()
        tg = frame["tg"].to_numpy()
        off = np.zeros(len(y)) if offset is None else offset
        yh0, per0 = wf_predict(X0cols, y - off, season, W2, min_train)
        yh1, per1 = wf_predict(X1cols, y - off, season, W2, min_train)
        m = np.isin(season, W2)
        f0 = yh0[m] + off[m]; f1 = yh1[m] + off[m]; yy = y[m]
        l0 = np.abs(yy - f0); l1 = np.abs(yy - f1)
        n2 = rb.paired_signflip_block(l1, l0, tg[m], NDRAW_N2, rb.SEED + 301 + seed_off)
        mde = rb.mde80(n2["null_sd"])
        rec = dict(cell=name, level="remaining-player-game in team-game", n=int(m.sum()),
                   n_blocks=n2["n_blocks"], row_set="RSP-W2", response=ch,
                   MAE_M0=float(l0.mean()), MAE_M1=float(l1.mean()),
                   effect=n2["real"], p=n2["p"], null_scheme=n2["scheme"],
                   null_mean=n2["null_mean"], null_sd=n2["null_sd"], MDE80=mde,
                   per_season_M0=per0, per_season_M1=per1,
                   conditioning="ORACLE ON ABSENCE -- realised absence indicator; a CEILING")
        if extra:
            rec.update(extra)
        print("  %-42s MAE %8.5f -> %8.5f   dMAE %+.5f  p %.4f  null_sd %.5f  MDE80 %.5f"
              % (name, l0.mean(), l1.mean(), n2["real"], n2["p"], n2["null_sd"], mde))
        return rec, n2["draws"], (l0, l1, tg[m], yy, m)

    rb.hdr("P03 -- FORECAST GAIN over the trailing-5 base (ORACLE ON ABSENCE)")
    p03_keep = {}
    for i, ch in enumerate(rb.CHANNELS):
        y = R[ch].to_numpy(float)
        b5 = R["base5_" + ch].to_numpy(float); z = R["z_" + ch].to_numpy(float)
        u = R["u_" + ch].to_numpy(float)
        rec, dr, keep = forecast_cell("P03_GAIN_vs_BASE5_ORACLEABS_" + ch, ch, y,
                                      [b5, z], [b5, z, u, u * z], 2021, seed_off=i)
        rec["base_M0"] = "1 + base5 + z (absence-blind, walk-forward)"
        rec["base_M1"] = "M0 + u + u*z"
        OUTJ["cells"][rec["cell"]] = rec
        NPZ["P03_" + ch] = dr
        p03_keep[ch] = keep

    rb.hdr("P04 -- FORECAST GAIN over the CHAMPION (ORACLE ON ABSENCE) -- the commercial cell")
    for i, ch in enumerate(rb.CHANNELS):
        y = R[ch].to_numpy(float)
        cf = R[CHAMP_COL[ch]].to_numpy(float)
        z = R["z_" + ch].to_numpy(float); u = R["u_" + ch].to_numpy(float)
        m = np.isin(R["season"].to_numpy(), W2)
        raw = float(np.abs(y[m] - cf[m]).mean())
        rec, dr, _ = forecast_cell("P04_GAIN_vs_CHAMPION_ORACLEABS_" + ch, ch, y,
                                   [], [u, u * z], 2022, offset=cf, seed_off=10 + i,
                                   extra={"MAE_champion_raw_no_intercept": raw})
        rec["base_M0"] = "champion %s + walk-forward intercept" % CHAMP_COL[ch]
        rec["base_M1"] = "M0 + u + u*z"
        rec["note"] = ("2021 is excluded from P04 training: the champion's 2021 fold receipt "
                       "declares degenerate:true. min_train_season=2022.")
        print("      (champion raw, no intercept: MAE %.5f)" % raw)
        OUTJ["cells"][rec["cell"]] = rec
        NPZ["P04_" + ch] = dr

    # ======================================================================= P05
    rb.hdr("P05 -- WHO BENEFITS: POSITION MATCH (minutes)")
    ch = "minutes"
    y = R["d_" + ch].to_numpy(float)
    b5 = R["base5_" + ch].to_numpy(float); z = R["z_" + ch].to_numpy(float)
    u = R["u_" + ch].to_numpy(float); pmv = R["posmatch_f"].to_numpy(float)

    def stat05(b5v, zv, pv, y=y, u=u, rs=rs):
        c, _ = wf_coef([b5v, zv, u, u * zv, pv, u * pv], y, rs, W2, 2021, 6)
        return c
    real05, per05 = wf_coef([b5, z, u, u * z, pmv, u * pmv], y, rs, W2, 2021, 6)
    rng = np.random.default_rng(rb.SEED + 401)
    draws05 = np.empty(NDRAW_N1)
    for i in range(NDRAW_N1):
        inv = perm_index(order_t, b_t, sz_t, rng)
        draws05[i] = stat05(b5[inv], z[inv], pmv[inv])
    nm, nsd = float(draws05.mean()), float(draws05.std(ddof=1))
    p05 = float((1.0 + int((np.abs(draws05 - nm) >= abs(real05 - nm) - 1e-15).sum()))
                / (NDRAW_N1 + 1.0))
    print("  P05_posmatch delta %+.5f  p %.4f  null_mean %+.5f  null_sd %.5f  MDE80 %.5f"
          % (real05, p05, nm, nsd, rb.mde80(nsd)))
    print("     posmatch rate on FREED>0 rows: %.4f"
          % float(R.loc[(R["u_minutes"] > 0) & R["season"].isin(W2), "posmatch"].mean()))
    OUTJ["cells"]["P05_POSITION_MATCH_minutes"] = dict(
        cell="P05_POSITION_MATCH_minutes", level="remaining-player-game in team-game",
        n=int((R["season"].isin(W2)).sum()), row_set="RSP-W2", response="delta_minutes",
        base="1 + base5 + z + u + u*z + posmatch  (P02's tilt IS in the base)",
        candidate="u * posmatch", effect=real05, p=p05,
        null_scheme="N1_within_teamgame_shuffle_of_(base5,z,posmatch)",
        null_mean=nm, null_sd=nsd, MDE80=rb.mde80(nsd), per_season=per05,
        posmatch_rate_on_absence_rows=float(
            R.loc[(R["u_minutes"] > 0) & R["season"].isin(W2), "posmatch"].mean()))
    NPZ["P05"] = draws05

    # ======================================================================= P06 NEG CONTROL
    rb.hdr("P06 -- NEGATIVE CONTROL: PSEUDO-ABSENCE (minutes)")
    # empirical n_absent distribution over ALL team-games, per PREREG
    emp = G["n_absent"].to_numpy()
    zero = G.loc[G["freed_minutes"] == 0.0, ["game_id", "team_id"]]
    print("  team-games with FREED == 0 (the control pool): %d of %d" % (len(zero), len(G)))
    C = R.merge(zero, on=["game_id", "team_id"], how="inner").copy()
    print("  control REM rows: %d over %d team-games" % (len(C), C["tg"].nunique()))
    rng = np.random.default_rng(rb.SEED + 501)
    C = C.sort_values(["season", "game_id", "team_id", "player_id"],
                      kind="stable").reset_index(drop=True)
    keep = np.ones(len(C), bool)
    pseudo_freed = np.zeros(len(C))
    for _, idx in C.groupby("tg").indices.items():
        m = int(rng.choice(emp))
        m = min(m, max(len(idx) - 3, 0))
        if m > 0:
            pick = rng.choice(idx, size=m, replace=False)
            keep[pick] = False
            pseudo_freed[idx] = C.loc[pick, "base5_minutes"].sum()
    C["_pf"] = pseudo_freed
    C2 = C[keep].copy()
    C2["n_rem_p"] = C2.groupby("tg")["minutes"].transform("size")
    C2["u_p"] = C2["_pf"] / C2["n_rem_p"]
    C2["uz_p"] = C2["u_p"] * C2["z_minutes"]
    print("  after removal: %d rows; mean pseudo-FREED %.4f (real mean FREED %.4f)"
          % (len(C2), C2.groupby("tg")["_pf"].first().mean(),
             G.loc[G["freed_minutes"] > 0, "freed_minutes"].mean()))
    y = C2["minutes"].to_numpy(float)
    b5 = C2["base5_minutes"].to_numpy(float); z = C2["z_minutes"].to_numpy(float)
    up = C2["u_p"].to_numpy(float)
    rec, dr, _ = forecast_cell("P06_NEGCONTROL_PSEUDOABSENCE_minutes", "minutes", y,
                               [b5, z], [b5, z, up, up * z], 2021, frame=C2, seed_off=20)
    rec["row_set"] = "control: REM rows in team-games with FREED == 0, seasons 2023-2024"
    rec["construction"] = ("m pseudo-absentees drawn per team-game from the empirical n_absent "
                           "distribution, removed from REM, pseudo-FREED taken from their base5. "
                           "DISJOINT from the treatment row set by construction -- not a mask.")
    rec["mean_pseudo_freed"] = float(C2.groupby("tg")["_pf"].first().mean())
    OUTJ["cells"]["P06_NEGCONTROL_PSEUDOABSENCE_minutes"] = rec
    NPZ["P06"] = dr

    np.savez_compressed(os.path.join(rb.OUT, "nulls", "permutation_draws_P01_P06.npz"), **NPZ)
    with open(os.path.join(rb.OUT, "_s06.json"), "w", encoding="utf-8") as fh:
        json.dump(rb.jsonable(OUTJ), fh, indent=1)
    # keep the loss series for the power step
    np.savez_compressed(os.path.join(rb.OUT, "nulls", "_p03_losses.npz"),
                        **{("%s_%s" % (ch, k)): v for ch in rb.CHANNELS
                           for k, v in zip(["l0", "l1", "tg", "y", "mask"],
                                           [p03_keep[ch][0], p03_keep[ch][1],
                                            p03_keep[ch][2].astype(str), p03_keep[ch][3],
                                            p03_keep[ch][4]])})
    print("\n  wrote _s06.json and nulls/permutation_draws_P01_P06.npz")


if __name__ == "__main__":
    main()
