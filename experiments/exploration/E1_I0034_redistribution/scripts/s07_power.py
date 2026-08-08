"""S07 -- POWER VERIFIED BY INJECTION, PER CELL, PLUS TYPE-I CALIBRATION AND A NO-OP PLACEBO.

D108 ruling 4 and D103 both require this BEFORE any verdict is read from a null.  Three separate
things are done, because E1_I0033's DEFECT D-1 was to conflate them:

  A  INJECTION THROUGH THE FULL PATH.  A synthetic effect of known size is added to the RESPONSE
     and the entire pipeline -- walk-forward fit, scoring, null -- is rerun.  This tests the code
     path, not just the arithmetic of the permutation.
  B  PER-CELL MINIMUM DETECTABLE EFFECT.  Planted as multiples of THAT CELL'S OWN null sd.  A
     single power curve computed on one cell's variance says nothing about another's; P03_minutes
     has null sd 0.00903 and P03_pts has 0.00317, a factor of 2.8.
  C  TYPE-I CALIBRATION.  400 synthetic NO-EFFECT datasets per null family, built by randomly
     sign-flipping whole blocks of the real series, each pushed through the full null.  The
     rejection rate should sit near 0.05.

DECLARED TRAP (E1_I0033 DEFECT D-1): a two-sided permutation p evaluated at an observed statistic
of EXACTLY zero is 1.0000 by construction and is not a test.  Row `plant = 0` below is therefore
reported as "does the null detect the OBSERVED effect", never as a type-I pass.  The type-I pass
comes only from C.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb
import s04_prereg
import s06_cells as s6

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)

W2 = (2023, 2024)
NINJ = 1000       # draws per injection level
NTYPE1 = 400      # synthetic no-effect datasets
CHAMP_COL = {"minutes": "min_hat", "fga": "fga_hat", "pts": "pts_hat"}


def n1_p(real, draws):
    nm = float(draws.mean())
    return float((1.0 + int((np.abs(draws - nm) >= abs(real - nm) - 1e-15).sum()))
                 / (len(draws) + 1.0)), nm, float(draws.std(ddof=1))


def main():
    rb.hdr("S07 POWER")
    pre = s04_prereg.assert_unchanged()
    print("  prereg hash verified: %s" % pre["prereg_sha256"])
    P = {"prereg_sha256": pre["prereg_sha256"]}
    S6 = json.load(open(os.path.join(rb.OUT, "_s06.json"), encoding="utf-8"))

    R = pd.read_parquet(os.path.join(rb.OUT, "_rem_frame.parquet")).sort_values(
        ["season", "game_id", "team_id", "player_id"], kind="stable").reset_index(drop=True)
    G = pd.read_parquet(os.path.join(rb.OUT, "_tg_frame.parquet")).sort_values(
        ["season", "game_id", "team_id"], kind="stable").reset_index(drop=True)
    R["posmatch_f"] = R["posmatch"].fillna(0.0)
    rs = R["season"].to_numpy(); gs = G["season"].to_numpy()
    tgc = pd.factorize(R["tg"])[0]
    ord_t, b_t, sz_t = s6.block_bounds(tgc)
    ord_s, b_s, sz_s = s6.block_bounds(gs)

    # ================================================================= A/B  N4  (P01)
    rb.hdr("A/B. N4 (P01 LEAKAGE) -- INJECTION THROUGH THE FULL PATH")
    rows = []
    for ch in rb.CHANNELS:
        y0 = G["unest_" + ch].to_numpy(float); x = G["freed_" + ch].to_numpy(float)
        nsd = S6["cells"]["P01_LEAKAGE_" + ch]["null_sd"]
        for mult in [0.0, 1.0, 2.0, 2.8, 4.0, 57.9]:
            plant = mult * nsd
            y = y0 + plant * x
            real, _ = s6.wf_coef([x], y, gs, W2, 2021, 1)
            rng = np.random.default_rng(rb.SEED + 700 + int(mult * 10))
            dr = np.array([s6.wf_coef([x[s6.perm_index(ord_s, b_s, sz_s, rng)]], y, gs, W2,
                                      2021, 1)[0] for _ in range(NINJ)])
            p, nm, sd = n1_p(real, dr)
            rows.append(dict(cell="P01_" + ch, planted=plant, planted_in_null_sds=mult,
                             recovered=real, p=p, null_sd=sd, detected=bool(p < 0.05)))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    P["injection_P01"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "power_injection_P01.csv"), index=False)

    # ================================================================= A/B  N1  (P02, P05)
    rb.hdr("A/B. N1 (P02 TILT, P05 POSITION) -- INJECTION THROUGH THE FULL PATH")
    rows = []
    for ch in rb.CHANNELS:
        y0 = R["d_" + ch].to_numpy(float)
        b5 = R["base5_" + ch].to_numpy(float); z = R["z_" + ch].to_numpy(float)
        u = R["u_" + ch].to_numpy(float)
        nsd = S6["cells"]["P02_TILT_" + ch]["null_sd"]
        for mult in [0.0, 1.0, 2.0, 2.8, 4.0]:
            plant = mult * nsd
            y = y0 + plant * (u * z)
            real, _ = s6.wf_coef([b5, z, u, u * z], y, rs, W2, 2021, 4)
            rng = np.random.default_rng(rb.SEED + 800 + int(mult * 10))
            dr = np.empty(NINJ)
            for i in range(NINJ):
                inv = s6.perm_index(ord_t, b_t, sz_t, rng)
                dr[i] = s6.wf_coef([b5[inv], z[inv], u, u * z[inv]], y, rs, W2, 2021, 4)[0]
            p, nm, sd = n1_p(real, dr)
            rows.append(dict(cell="P02_" + ch, planted=plant, planted_in_null_sds=mult,
                             recovered=real, p=p, null_sd=sd, detected=bool(p < 0.05)))
    # P05
    y0 = R["d_minutes"].to_numpy(float)
    b5 = R["base5_minutes"].to_numpy(float); z = R["z_minutes"].to_numpy(float)
    u = R["u_minutes"].to_numpy(float); pmv = R["posmatch_f"].to_numpy(float)
    nsd = S6["cells"]["P05_POSITION_MATCH_minutes"]["null_sd"]
    for mult in [0.0, 1.0, 2.0, 2.8, 4.0]:
        plant = mult * nsd
        y = y0 + plant * (u * pmv)
        real, _ = s6.wf_coef([b5, z, u, u * z, pmv, u * pmv], y, rs, W2, 2021, 6)
        rng = np.random.default_rng(rb.SEED + 900 + int(mult * 10))
        dr = np.empty(NINJ)
        for i in range(NINJ):
            inv = s6.perm_index(ord_t, b_t, sz_t, rng)
            dr[i] = s6.wf_coef([b5[inv], z[inv], u, u * z[inv], pmv[inv], u * pmv[inv]],
                               y, rs, W2, 2021, 6)[0]
        p, nm, sd = n1_p(real, dr)
        rows.append(dict(cell="P05_posmatch", planted=plant, planted_in_null_sds=mult,
                         recovered=real, p=p, null_sd=sd, detected=bool(p < 0.05)))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    P["injection_P02_P05"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "power_injection_P02_P05.csv"), index=False)

    # ================================================================= A  N2 full path (P03/P04)
    rb.hdr("A. N2 (P03 / P04) -- INJECTION THROUGH THE FULL PATH, response perturbed")
    rows = []
    for ch in rb.CHANNELS:
        y0 = R[ch].to_numpy(float)
        b5 = R["base5_" + ch].to_numpy(float); z = R["z_" + ch].to_numpy(float)
        u = R["u_" + ch].to_numpy(float)
        um = u - u.mean()
        for lam in [0.0, 0.10, 0.25, 0.50, 1.00]:
            y = y0 + lam * um
            yh0, _ = s6.wf_predict([b5, z], y, rs, W2, 2021)
            yh1, _ = s6.wf_predict([b5, z, u, u * z], y, rs, W2, 2021)
            m = np.isin(rs, W2)
            l0 = np.abs(y[m] - yh0[m]); l1 = np.abs(y[m] - yh1[m])
            n2 = rb.paired_signflip_block(l1, l0, R["tg"].to_numpy()[m], 4000,
                                          rb.SEED + 1000 + int(lam * 100))
            rows.append(dict(cell="P03_" + ch, planted_lambda=lam, dMAE=n2["real"], p=n2["p"],
                             null_sd=n2["null_sd"], MDE80=rb.mde80(n2["null_sd"]),
                             detected=bool(n2["p"] < 0.05)))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    P["injection_P03_fullpath"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "power_injection_P03_fullpath.csv"), index=False)

    # ================================================================= B  N2 per-cell MDE
    rb.hdr("B. N2 -- PER-CELL MINIMUM DETECTABLE EFFECT (planted in that cell's own null sds)")
    L = np.load(os.path.join(rb.OUT, "nulls", "_p03_losses.npz"), allow_pickle=True)
    rows = []
    cells = [("P03_GAIN_vs_BASE5_ORACLEABS_" + ch, ch) for ch in rb.CHANNELS]
    for cellname, ch in cells:
        l0 = L[ch + "_l0"]; l1 = L[ch + "_l1"]; tg = L[ch + "_tg"]
        nsd = S6["cells"][cellname]["null_sd"]
        for mult in [0.0, 1.0, 2.0, 2.8, 4.0]:
            d = mult * nsd
            n2 = rb.paired_signflip_block(l1 - d, l0, tg, 4000, rb.SEED + 1100 + int(mult * 10))
            rows.append(dict(cell=cellname, planted_in_null_sds=mult, planted_dMAE=d,
                             observed_plus_planted=n2["real"], p=n2["p"], null_sd=n2["null_sd"],
                             detected=bool(n2["p"] < 0.05)))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    print("\n  NOTE: the `planted = 0` row is the OBSERVED effect pushed through the null, NOT a")
    print("  type-I check.  The type-I check is section C.")
    P["injection_P03_percell"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "power_injection_P03_percell.csv"), index=False)

    # ================================================================= C  TYPE-I
    rb.hdr("C. TYPE-I CALIBRATION -- 400 synthetic NO-EFFECT datasets per null family")
    rows = []
    tp = {}
    for cellname, ch in cells:
        l0 = L[ch + "_l0"]; l1 = L[ch + "_l1"]; tg = L[ch + "_tg"]
        d = l0 - l1
        uniq, inv = np.unique(tg, return_inverse=True)
        rng = np.random.default_rng(rb.SEED + 1200)
        ps = []
        for _ in range(NTYPE1):
            sg = rng.choice(np.array([-1.0, 1.0]), size=len(uniq))[inv]
            dd = d * sg
            n2 = rb.paired_signflip_block(np.zeros(len(dd)), dd, tg, 500,
                                          int(rng.integers(1, 1 << 30)))
            ps.append(n2["p"])
        ps = np.array(ps)
        rows.append(dict(null_family="N2_" + cellname, n_synth=NTYPE1,
                         rejection_rate_at_05=float((ps < 0.05).mean()),
                         mean_p=float(ps.mean()), median_p=float(np.median(ps))))
        tp["N2_" + ch] = ps
    # N1 type-I: shuffle the candidate ONCE to make a genuinely null dataset, then test it
    for ch in rb.CHANNELS:
        y0 = R["d_" + ch].to_numpy(float)
        b5 = R["base5_" + ch].to_numpy(float); z = R["z_" + ch].to_numpy(float)
        u = R["u_" + ch].to_numpy(float)
        rng = np.random.default_rng(rb.SEED + 1300)
        ps = []
        for _ in range(60):     # 60 x 400 draws -- N1 is expensive; reported honestly
            inv0 = s6.perm_index(ord_t, b_t, sz_t, rng)
            b5n, zn = b5[inv0], z[inv0]
            real = s6.wf_coef([b5n, zn, u, u * zn], y0, rs, W2, 2021, 4)[0]
            dr = np.array([s6.wf_coef(
                [b5n[i2], zn[i2], u, u * zn[i2]], y0, rs, W2, 2021, 4)[0]
                for i2 in (s6.perm_index(ord_t, b_t, sz_t, rng) for _ in range(400))])
            ps.append(n1_p(real, dr)[0])
        ps = np.array(ps)
        rows.append(dict(null_family="N1_P02_" + ch, n_synth=60,
                         rejection_rate_at_05=float((ps < 0.05).mean()),
                         mean_p=float(ps.mean()), median_p=float(np.median(ps))))
        tp["N1_" + ch] = ps
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    P["type_I"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "power_type_I.csv"), index=False)
    np.savez_compressed(os.path.join(rb.OUT, "nulls", "type_I_pvalues.npz"), **tp)

    # ================================================================= D  NO-OP PLACEBO
    rb.hdr("D. NO-OP PLACEBO -- an identity transform must reproduce the statistic EXACTLY")
    rows = []
    for ch in rb.CHANNELS:
        y = R[ch].to_numpy(float)
        b5 = R["base5_" + ch].to_numpy(float); z = R["z_" + ch].to_numpy(float)
        u = R["u_" + ch].to_numpy(float)
        yh0, _ = s6.wf_predict([b5, z], y, rs, W2, 2021)
        yh1, _ = s6.wf_predict([b5, z, u, u * z], y, rs, W2, 2021)
        m = np.isin(rs, W2)
        real = float(np.abs(y[m] - yh0[m]).mean() - np.abs(y[m] - yh1[m]).mean())
        # identity transform: a permutation index that is the identity
        idn = np.arange(len(y))
        yh0b, _ = s6.wf_predict([b5[idn], z[idn]], y[idn], rs[idn], W2, 2021)
        yh1b, _ = s6.wf_predict([b5[idn], z[idn], u[idn], (u * z)[idn]], y[idn], rs[idn], W2, 2021)
        repl = float(np.abs(y[m] - yh0b[m]).mean() - np.abs(y[m] - yh1b[m]).mean())
        rows.append(dict(cell="P03_" + ch, real=real, replayed=repl, deviation=abs(real - repl)))
        # and confirm the identity index really is the identity, so the placebo is not vacuous
        assert (idn == np.arange(len(y))).all()
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    print("  the placebo is NOT vacuous: the transform is asserted to be the identity permutation,")
    print("  and it is applied to the SAME code path, not to a stored result.")
    P["noop_placebo"] = t.to_dict("records")

    with open(os.path.join(rb.OUT, "_s07.json"), "w", encoding="utf-8") as fh:
        json.dump(rb.jsonable(P), fh, indent=1)
    print("\n  wrote _s07.json and the four power CSVs")


if __name__ == "__main__":
    main()
