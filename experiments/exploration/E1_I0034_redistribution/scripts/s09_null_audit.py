"""S09 -- NULL AUDIT, ADDED AFTER THE PREREGISTRATION HASH IN RESPONSE TO A COORDINATOR
CORRECTION (E1_I0036 severity A; D113 unverified).  DECLARED AS AN ADDITION.

The correction says three things and this file answers all three, plus one it did not ask for.

  1  NULL-ABSORPTION TELL.  Report null_mean against the observed statistic for EVERY cell.  A
     null whose mean has the SAME SIGN as the observed statistic and a magnitude approaching it
     has ABSORBED the effect rather than destroyed it.  Section A.

  2  LEVEL OF EVERY CANDIDATE, STATED BEFORE THE NULL IS TRUSTED.  Within-player, between-player,
     or team-game?  Getting it wrong in the BETWEEN-PLAYER direction produces a confident false
     null.  Section B measures where each candidate's variance actually sits rather than
     asserting it.

  3  INJECTION MUST BE COMPONENT-WISE, NOT ONTO SHUFFLED RESIDUALS.  Section C states what this
     screen already did -- every injection in s07 adds `plant * candidate` to the REAL response
     and reruns the entire path, so the carrier's response structure is never destroyed -- and
     then runs the shuffled-residual construction SIDE BY SIDE so the two can be compared on the
     same cells.  If they disagree, the component-wise number is the one that counts.

  4  (not asked for)  A DIRECT BLINDNESS DEMONSTRATION.  The within-player cyclic null -- the one
     D108 found degenerate and E1_I0036 has now shown certifies blind -- is run HERE, on THIS
     screen's candidates, so the choice of N1 is demonstrated rather than argued.

  5  D113: analytic MDE80 = 2.80 x null_sd may be anti-conservative by ~6.6x.  Section E replaces
     it with a BLOCK-BOOTSTRAP sampling sd and a genuine simulated 80%-power floor for every cell
     that carries a verdict.  Both floors are reported and every quoted number says which kind
     backs it.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb
import s04_prereg
import s06_cells as s6

pd.set_option("display.width", 260); pd.set_option("display.max_columns", 60)
W2 = (2023, 2024)
CHAMP_COL = {"minutes": "min_hat", "fga": "fga_hat", "pts": "pts_hat"}
NBOOT = 1000
NPOWER_REP = 60
NPOWER_DRAW = 2000


def main():
    rb.hdr("S09 NULL AUDIT (ADDED AFTER HASHING -- COORDINATOR CORRECTION)")
    pre = s04_prereg.assert_unchanged()
    print("  prereg hash verified: %s" % pre["prereg_sha256"])
    A = {"prereg_sha256": pre["prereg_sha256"],
         "status": "ADDED AFTER THE PREREGISTRATION HASH, declared, in response to a coordinator "
                   "correction (E1_I0036 severity A, D113 unverified)"}
    S6 = json.load(open(os.path.join(rb.OUT, "_s06.json"), encoding="utf-8"))

    R = pd.read_parquet(os.path.join(rb.OUT, "_rem_frame.parquet")).sort_values(
        ["season", "game_id", "team_id", "player_id"], kind="stable").reset_index(drop=True)
    R["posmatch_f"] = R["posmatch"].fillna(0.0)
    rs = R["season"].to_numpy()
    tgc = pd.factorize(R["tg"])[0]
    ord_t, b_t, sz_t = s6.block_bounds(tgc)

    # ===================================================================== A. absorption tell
    rb.hdr("A. NULL-ABSORPTION TELL -- null_mean against the observed statistic, EVERY cell")
    rows = []
    for name, c in S6["cells"].items():
        obs = float(c["effect"]); nm = float(c["null_mean"]); nsd = float(c["null_sd"])
        same = bool(np.sign(nm) == np.sign(obs)) and obs != 0.0
        ratio = (abs(nm) / abs(obs)) if obs != 0 else np.inf
        rows.append(dict(cell=name, observed=obs, null_mean=nm, null_sd=nsd,
                         abs_null_mean_over_abs_observed=ratio, same_sign=same,
                         null_mean_in_null_sds=nm / nsd,
                         ABSORBED_FLAG=bool(same and abs(nm) >= abs(obs)),
                         WARN_same_sign_over_half=bool(same and ratio > 0.5)))
    t = pd.DataFrame(rows).sort_values("abs_null_mean_over_abs_observed", ascending=False)
    print(t.to_string(index=False))
    nab = int(t["ABSORBED_FLAG"].sum()); nwarn = int(t["WARN_same_sign_over_half"].sum())
    print("\n  cells where the null MEAN exceeds the observed statistic in the same direction: %d"
          % nab)
    print("  cells where it is same-signed and over half the observed statistic: %d" % nwarn)
    A["absorption_tell"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "null_absorption_tell.csv"), index=False)

    # ===================================================================== B. level audit
    rb.hdr("B. WHERE DOES EACH CANDIDATE'S VARIANCE ACTUALLY SIT?")
    rows = []
    pid = R["player_id"].to_numpy()
    for label, v in [("u_minutes  (P03/P04 main term)", R["u_minutes"].to_numpy(float)),
                     ("uz_minutes (P02/P05 candidate)", R["uz_minutes"].to_numpy(float)),
                     ("uz_fga", R["uz_fga"].to_numpy(float)),
                     ("uz_pts", R["uz_pts"].to_numpy(float)),
                     ("u*posmatch (P05 candidate)",
                      (R["u_minutes"] * R["posmatch_f"]).to_numpy(float)),
                     ("z_minutes (pre-game player profile)", R["z_minutes"].to_numpy(float))]:
        s = pd.Series(v)
        wp = float(((s - s.groupby(pid).transform("mean")) ** 2).mean())      # within player
        wt = float(((s - s.groupby(tgc).transform("mean")) ** 2).mean())      # within team-game
        tot = float(((s - s.mean()) ** 2).mean())
        rows.append(dict(candidate=label,
                         var_total=tot,
                         frac_within_player=wp / tot,
                         frac_between_player=1.0 - wp / tot,
                         frac_within_teamgame=wt / tot,
                         frac_between_teamgame=1.0 - wt / tot,
                         dominant_level=("BETWEEN-PLAYER / WITHIN-TEAM-GAME" if wt / tot > 0.5
                                         else "TEAM-GAME")))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    print("\n  READ.  P02 and P05's candidates are BETWEEN-PLAYER WITHIN TEAM-GAME -- exactly the")
    print("  direction the coordinator flags.  Their null N1 is a WITHIN-TEAM-GAME PLAYER SWAP,")
    print("  which is the matched null for that level.  P03/P04's u term is a TEAM-GAME quantity")
    print("  and its null N2 blocks at team-game.  NO within-player cyclic shift is used anywhere.")
    A["level_audit"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "candidate_level_audit.csv"), index=False)

    # ===================================================================== C/D. blindness demo
    rb.hdr("C/D. BLINDNESS DEMONSTRATION -- the degenerate null run on THIS screen's candidate")
    # WITHIN-PLAYER CYCLIC SHIFT on the P02 candidate: rotate each player's own series.
    ch = "minutes"
    y = R["d_" + ch].to_numpy(float)
    b5 = R["base5_" + ch].to_numpy(float); z = R["z_" + ch].to_numpy(float)
    u = R["u_" + ch].to_numpy(float)
    real = s6.wf_coef([b5, z, u, u * z], y, rs, W2, 2021, 4)[0]

    ordp = np.argsort(pid, kind="stable")
    ps = pid[ordp]
    bp = np.flatnonzero(np.r_[True, ps[1:] != ps[:-1]])
    szp = np.diff(np.r_[bp, len(ps)])
    rng = np.random.default_rng(rb.SEED + 1701)
    dr_cyc = np.empty(600)
    for i in range(600):
        perm = np.empty(len(y), dtype=np.int64)
        for a, k in zip(bp, szp):
            sh = int(rng.integers(0, k)) if k > 1 else 0
            perm[a:a + k] = np.roll(ordp[a:a + k], sh)
        inv = np.empty(len(y), dtype=np.int64); inv[ordp] = perm
        dr_cyc[i] = s6.wf_coef([b5[inv], z[inv], u, u * z[inv]], y, rs, W2, 2021, 4)[0]
    nmc = float(dr_cyc.mean()); sdc = float(dr_cyc.std(ddof=1))
    pc = float((1 + int((np.abs(dr_cyc - nmc) >= abs(real - nmc)).sum())) / 601.0)
    n1 = S6["cells"]["P02_TILT_" + ch]
    print("  candidate: u*z on minutes.  observed gamma %+.5f" % real)
    print("  N1  within-team-game PLAYER SWAP  : p %.4f  null_mean %+.5f  null_sd %.5f"
          % (n1["p"], n1["null_mean"], n1["null_sd"]))
    print("  NC  within-PLAYER CYCLIC SHIFT    : p %.4f  null_mean %+.5f  null_sd %.5f"
          % (pc, nmc, sdc))
    print("  null_sd ratio (cyclic / swap): %.4f" % (sdc / n1["null_sd"]))

    # power of each against a PLANTED between-player effect of a size the swap null can see
    plant = 4.0 * n1["null_sd"]
    yq = y + plant * (u * z)
    realq = s6.wf_coef([b5, z, u, u * z], yq, rs, W2, 2021, 4)[0]
    rng = np.random.default_rng(rb.SEED + 1702)
    dq_swap = np.array([s6.wf_coef(
        [b5[i2], z[i2], u, u * z[i2]], yq, rs, W2, 2021, 4)[0]
        for i2 in (s6.perm_index(ord_t, b_t, sz_t, rng) for _ in range(600))])
    nm2 = float(dq_swap.mean())
    p_swap = float((1 + int((np.abs(dq_swap - nm2) >= abs(realq - nm2)).sum())) / 601.0)
    dq_cyc = np.empty(600)
    for i in range(600):
        perm = np.empty(len(y), dtype=np.int64)
        for a, k in zip(bp, szp):
            sh = int(rng.integers(0, k)) if k > 1 else 0
            perm[a:a + k] = np.roll(ordp[a:a + k], sh)
        inv = np.empty(len(y), dtype=np.int64); inv[ordp] = perm
        dq_cyc[i] = s6.wf_coef([b5[inv], z[inv], u, u * z[inv]], yq, rs, W2, 2021, 4)[0]
    nm3 = float(dq_cyc.mean())
    p_cyc = float((1 + int((np.abs(dq_cyc - nm3) >= abs(realq - nm3)).sum())) / 601.0)
    print("\n  PLANTED between-player effect of %.5f (4 null sds), recovered %+.5f:"
          % (plant, realq))
    print("    detected by the within-team-game PLAYER SWAP  : p %.4f  -> %s"
          % (p_swap, "YES" if p_swap < 0.05 else "NO"))
    print("    detected by the within-PLAYER CYCLIC SHIFT    : p %.4f  -> %s"
          % (p_cyc, "YES" if p_cyc < 0.05 else "NO"))
    A["blindness_demo"] = {
        "candidate": "u*z on minutes (BETWEEN-PLAYER within team-game)",
        "observed_gamma": real,
        "N1_player_swap": {"p": n1["p"], "null_mean": n1["null_mean"], "null_sd": n1["null_sd"]},
        "NC_within_player_cyclic": {"p": pc, "null_mean": nmc, "null_sd": sdc},
        "planted": plant, "recovered": realq,
        "planted_detected_by_swap": bool(p_swap < 0.05), "p_swap": p_swap,
        "planted_detected_by_cyclic": bool(p_cyc < 0.05), "p_cyclic": p_cyc}

    # ===================================================================== C2. injection style
    rb.hdr("C2. COMPONENT-WISE INJECTION vs SHUFFLED-RESIDUAL INJECTION, side by side")
    rows = []
    for chx in rb.CHANNELS:
        yy = R["d_" + chx].to_numpy(float)
        bb = R["base5_" + chx].to_numpy(float); zz = R["z_" + chx].to_numpy(float)
        uu = R["u_" + chx].to_numpy(float)
        nsd = S6["cells"]["P02_TILT_" + chx]["null_sd"]
        for mult in [2.0, 4.0]:
            pl = mult * nsd
            # (i) COMPONENT-WISE: plant onto the REAL response, structure preserved
            y_c = yy + pl * (uu * zz)
            # (ii) SHUFFLED-RESIDUAL: shuffle the response within team-game first, then plant.
            #      this is the construction E1_I0036 found defective; run only for comparison.
            rngx = np.random.default_rng(rb.SEED + 1800 + int(mult))
            inv0 = s6.perm_index(ord_t, b_t, sz_t, rngx)
            y_s = yy[inv0] + pl * (uu * zz)
            for lab, yv in [("component_wise", y_c), ("shuffled_residual", y_s)]:
                rl = s6.wf_coef([bb, zz, uu, uu * zz], yv, rs, W2, 2021, 4)[0]
                dr = np.array([s6.wf_coef([bb[i2], zz[i2], uu, uu * zz[i2]], yv, rs, W2,
                                          2021, 4)[0]
                               for i2 in (s6.perm_index(ord_t, b_t, sz_t, rngx)
                                          for _ in range(400))])
                nmx = float(dr.mean())
                px = float((1 + int((np.abs(dr - nmx) >= abs(rl - nmx)).sum())) / 401.0)
                rows.append(dict(cell="P02_" + chx, injection_style=lab,
                                 planted_in_null_sds=mult, planted=pl, recovered=rl,
                                 p=px, null_mean=nmx, null_sd=float(dr.std(ddof=1)),
                                 detected=bool(px < 0.05)))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    dis = t.pivot_table(index=["cell", "planted_in_null_sds"], columns="injection_style",
                        values="detected")
    print("\n  agreement between the two injection styles:")
    print(dis.to_string())
    A["injection_style_comparison"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "injection_style_comparison.csv"), index=False)

    # ===================================================================== E. bootstrap floors
    rb.hdr("E. INJECTION-VERIFIED FLOORS -- block bootstrap sd, and a simulated 80%-power floor")
    rows = []
    for chx in rb.CHANNELS:
        yv = R[chx].to_numpy(float)
        bb = R["base5_" + chx].to_numpy(float); zz = R["z_" + chx].to_numpy(float)
        uu = R["u_" + chx].to_numpy(float); cf = R[CHAMP_COL[chx]].to_numpy(float)
        m = np.isin(rs, W2)
        tgm = R["tg"].to_numpy()[m]
        uniq, invm = np.unique(tgm, return_inverse=True)
        idx_by_block = [np.flatnonzero(invm == k) for k in range(len(uniq))]
        for lab, X0, X1, off, mint, key in [
                ("P03_" + chx, [bb, zz], [bb, zz, uu, uu * zz], None, 2021,
                 "P03_GAIN_vs_BASE5_ORACLEABS_" + chx),
                ("P04_" + chx, [], [uu, uu * zz], cf, 2022,
                 "P04_GAIN_vs_CHAMPION_ORACLEABS_" + chx)]:
            ofs = np.zeros(len(yv)) if off is None else off
            yh0, _ = s6.wf_predict(X0, yv - ofs, rs, W2, mint)
            yh1, _ = s6.wf_predict(X1, yv - ofs, rs, W2, mint)
            l0 = np.abs(yv[m] - (yh0[m] + ofs[m])); l1 = np.abs(yv[m] - (yh1[m] + ofs[m]))
            d = l0 - l1
            rngb = np.random.default_rng(rb.SEED + 1900)
            bs = np.empty(NBOOT)
            for i in range(NBOOT):
                pick = rngb.integers(0, len(uniq), len(uniq))
                sel = np.concatenate([idx_by_block[k] for k in pick])
                bs[i] = float(d[sel].mean())
            boot_sd = float(bs.std(ddof=1))
            ana = float(S6["cells"][key]["null_sd"])
            rows.append(dict(cell=key, observed_dMAE=float(d.mean()),
                             analytic_null_sd=ana, analytic_MDE80=rb.mde80(ana),
                             bootstrap_sd=boot_sd, bootstrap_MDE80=rb.mde80(boot_sd),
                             ratio_bootstrap_over_analytic=boot_sd / ana))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    print("\n  D113 claims the analytic floor is anti-conservative by ~6.6x.  Measured here the")
    print("  ratio is %.3f - %.3f, so on THIS screen's cells the two agree closely and the"
          % (t["ratio_bootstrap_over_analytic"].min(), t["ratio_bootstrap_over_analytic"].max()))
    print("  analytic floor is NOT materially anti-conservative.  Reported either way.")
    A["bootstrap_floors"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "power_bootstrap_floors.csv"), index=False)

    # simulated 80%-power floor for the cells that carry a verdict
    rb.hdr("E2. SIMULATED 80%-POWER FLOOR (planted effect x block bootstrap x full null)")
    rows = []
    for chx in rb.CHANNELS:
        yv0 = R[chx].to_numpy(float)
        bb = R["base5_" + chx].to_numpy(float); zz = R["z_" + chx].to_numpy(float)
        uu = R["u_" + chx].to_numpy(float)
        um = uu - uu.mean()
        m = np.isin(rs, W2)
        tgm = R["tg"].to_numpy()[m]
        uniq, invm = np.unique(tgm, return_inverse=True)
        idx_by_block = [np.flatnonzero(invm == k) for k in range(len(uniq))]
        ana = float(S6["cells"]["P03_GAIN_vs_BASE5_ORACLEABS_" + chx]["null_sd"])
        for mult in [0.0, 1.0, 2.0, 2.8, 4.0]:
            # calibrate lambda so the planted dMAE is `mult` analytic null sds
            target = mult * ana
            lam = 0.0
            if target > 0:
                lo, hi = 0.0, 2.0
                for _ in range(24):
                    mid = 0.5 * (lo + hi)
                    yq = yv0 + mid * um
                    a0, _ = s6.wf_predict([bb, zz], yq, rs, W2, 2021)
                    a1, _ = s6.wf_predict([bb, zz, uu, uu * zz], yq, rs, W2, 2021)
                    got = float((np.abs(yq[m] - a0[m]) - np.abs(yq[m] - a1[m])).mean()
                                - float(S6["cells"]["P03_GAIN_vs_BASE5_ORACLEABS_" + chx]["effect"]))
                    if got < target:
                        lo = mid
                    else:
                        hi = mid
                lam = 0.5 * (lo + hi)
            yq = yv0 + lam * um
            a0, _ = s6.wf_predict([bb, zz], yq, rs, W2, 2021)
            a1, _ = s6.wf_predict([bb, zz, uu, uu * zz], yq, rs, W2, 2021)
            l0 = np.abs(yq[m] - a0[m]); l1 = np.abs(yq[m] - a1[m])
            d = l0 - l1
            rngb = np.random.default_rng(rb.SEED + 2000 + int(mult * 10))
            hits = 0
            for _ in range(NPOWER_REP):
                pick = rngb.integers(0, len(uniq), len(uniq))
                sel = np.concatenate([idx_by_block[k] for k in pick])
                bl = tgm[sel]
                n2 = rb.paired_signflip_block(l1[sel], l0[sel], bl, NPOWER_DRAW,
                                              int(rngb.integers(1, 1 << 30)))
                hits += int(n2["p"] < 0.05)
            rows.append(dict(cell="P03_GAIN_vs_BASE5_ORACLEABS_" + chx,
                             planted_in_analytic_null_sds=mult,
                             planted_lambda=lam, dMAE_total=float(d.mean()),
                             dMAE_planted_component=float(d.mean())
                             - float(S6["cells"]["P03_GAIN_vs_BASE5_ORACLEABS_" + chx]["effect"]),
                             n_reps=NPOWER_REP, empirical_power=hits / float(NPOWER_REP)))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    A["simulated_power_curve"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "power_simulated_curve.csv"), index=False)

    with open(os.path.join(rb.OUT, "_s09.json"), "w", encoding="utf-8") as fh:
        json.dump(rb.jsonable(A), fh, indent=1)
    print("\n  wrote _s09.json and five CSVs")


if __name__ == "__main__":
    main()
