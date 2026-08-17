"""
s04 -- (a) the SCALE-MATCHED ceiling, correcting this screen's own s02;
       (b) per-season stability;
       (c) placebos, including the vacuous-control check;
       (d) the CORRECT demonstration that a within-entity null is blind to this candidate.

(a) EXISTS BECAUSE THIS SCREEN MADE THE D101 MISTAKE ON ITSELF.  s02 computed the ceiling on a
    rate-times-minutes points forecast and this screen's cells fit points directly.  Those are two
    different models and a bar derived on one is not a bar on the other -- which is the exact D101
    failure ("a critical value must be derived on the scale it is applied to").  It is recorded in
    DEFECTS.md as D-02 and corrected here rather than quietly reissued.

    It also exposes a convention problem the programme has not recorded: `(d.d)/SST`, the statistic
    D084 and D089 both call "the ceiling", IS NOT AN UPPER BOUND ON dR2.  dR2 = (2 d.e - d.d)/SST,
    which exceeds (d.d)/SST whenever d.e > d.d.  The true arithmetic bound on what this shift can
    achieve under any rescaling is the ORACLE (d.e)^2/((d.d) SST).  Both are reported.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import od_base as ob  # noqa: E402
import od_fast as of  # noqa: E402

LOG = []
FLOOR_SINGLE, FLOOR_132, LARGEST_LIVE = 0.00102, 0.00235, 0.002057


def P(x=""):
    print(x)
    LOG.append(str(x))


def shift_stats(cell):
    ya, beta = cell._pred(cell.d_full)
    d = ya - cell.yb
    e = cell.y - cell.yb
    sst = cell.sst
    sdd, sde = float(d @ d), float(d @ e)
    return dict(beta=beta, injected_var_share=sdd / sst,
                oracle_upper_bound=(sde * sde) / (sdd * sst) if sdd > 0 else np.nan,
                realised_signed_dr2=(2 * sde - sdd) / sst,
                implied_optimal_rescaling=(sde / sdd) if sdd > 0 else np.nan,
                sd_shift=float(np.std(d, ddof=1)), sd_y=float(np.std(cell.y, ddof=1)))


def main():
    ob.hdr("E1_I0043 s04 -- SCALE-MATCHED CEILING, STABILITY, CONTROLS, BLIND-NULL DEMO")
    P("  PREREG.md sha256 %s" % ob.prereg_sha())
    m = ob.build_merged(verbose=False)
    m["_m_hat"] = m["prior5_minutes"].fillna(m["refB_mpg"])
    ssn = m["season"].to_numpy()
    dec = ob.decision_mask(m)
    need = list(dict.fromkeys(ob.BASE_B2_FAMILY + ob.CANDIDATE + ob.NEG_CONTROL
                              + ["y_ppm", "y_pts", "_m_hat"]))
    fin = ob.finite_mask(m, need)
    mask = dec & fin
    v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float) for c in need}

    # ---------------------------------------------------------------- (a) matched ceiling
    ob.hdr("(a) THE SCALE-MATCHED CEILING -- same model, same rows, same SST as the cell it gates")
    P("  NOTE: (d.d)/SST is NOT an upper bound on dR2. The ORACLE is. Both are printed.")
    crows = []
    for yname in ["y_ppm", "y_pts"]:
        for wlbl, ev in [("CLEAN_2023_24", ob.CLEAN_EVAL_SEASONS),
                         ("DISCLOSED_2022", ob.DISCLOSED_CONTRAST_EVAL_SEASONS)]:
            for bkey in ["B0_COMPLETE", "B1_HONEST", "B2_FAMILY"]:
                packs, trm, tem = of.build_packs(v, ob.BASES[bkey], yname, mask, ev, ssn)
                if not packs:
                    continue
                for cand, is_nc in [("A10_opp_defrtg", False), ("G01_noise", True)]:
                    for arm in [of.UNFROZEN, of.FROZEN]:
                        cell = of.FastCell(packs, arm, v[cand], trm, tem)
                        s = shift_stats(cell)
                        # the interpretable lever, on this cell's own model
                        dtr = np.concatenate([v[cand][t] - v[cand][t].mean() for t in trm])
                        r = dict(response=yname, window=wlbl, base=bkey, arm=arm, candidate=cand,
                                 is_negative_control=is_nc, n=cell.n,
                                 sd_defence_centred=float(np.std(dtr, ddof=1)), **s)
                        r["response_moved_by_1sd_of_shift"] = s["sd_shift"]
                        r["pct_of_response_sd"] = 100.0 * s["sd_shift"] / s["sd_y"]
                        r["oracle_vs_floor_single"] = s["oracle_upper_bound"] / FLOOR_SINGLE
                        r["oracle_vs_floor_132"] = s["oracle_upper_bound"] / FLOOR_132
                        r["realised_over_oracle"] = s["realised_signed_dr2"] / s["oracle_upper_bound"]
                        crows.append(r)
                        if not is_nc and arm == of.UNFROZEN:
                            P("    %-6s %-14s %-12s n=%5d  injected var share %.8f | ORACLE bound "
                              "%.8f (%.2fx single-cell floor) | realised %+.8f (%.3f of oracle)"
                              % (yname, wlbl, bkey, cell.n, s["injected_var_share"],
                                 s["oracle_upper_bound"], r["oracle_vs_floor_single"],
                                 s["realised_signed_dr2"], r["realised_over_oracle"]))
    cf = pd.DataFrame(crows)
    cf.to_csv(os.path.join(ob.OUT, "CEILING_MATCHED.csv"), index=False)
    hl = cf[(cf.candidate == "A10_opp_defrtg") & (cf.base == "B1_HONEST")
            & (cf.window == "CLEAN_2023_24") & (cf.response == "y_ppm")
            & (cf.arm == of.UNFROZEN)].iloc[0]
    nc = cf[(cf.candidate == "G01_noise") & (cf.base == "B1_HONEST")
            & (cf.window == "CLEAN_2023_24") & (cf.response == "y_ppm")
            & (cf.arm == of.UNFROZEN)].iloc[0]
    P("\n  PRIMARY CELL, on its own scale: ORACLE arithmetic ceiling %.8f = %.2fx the single-cell "
      "floor %.5f and %.2fx the 132-cell floor %.5f."
      % (hl["oracle_upper_bound"], hl["oracle_vs_floor_single"], FLOOR_SINGLE,
         hl["oracle_vs_floor_132"], FLOOR_132))
    P("  MATCHED PURE-NOISE ORACLE on the identical path: %.8f -> the real ceiling is %.1fx its "
      "own noise floor." % (nc["oracle_upper_bound"],
                            hl["oracle_upper_bound"] / nc["oracle_upper_bound"]))

    # ---------------------------------------------------------------- (b) per-season stability
    ob.hdr("(b) PER-SEASON STABILITY -- one eval season at a time, trained strictly on earlier ones")
    srows = []
    for yname in ["y_ppm", "y_pts"]:
        for s_eval in [2022, 2023, 2024]:
            packs, trm, tem = of.build_packs(v, ob.BASE_B1_HONEST, yname, mask, [s_eval], ssn)
            if not packs:
                continue
            for arm in [of.UNFROZEN, of.FROZEN]:
                c = of.FastCell(packs, arm, v["A10_opp_defrtg"], trm, tem)
                r = c.full()
                cn = of.FastCell(packs, arm, v["G01_noise"], trm, tem).full()
                srows.append(dict(response=yname, eval_season=s_eval, arm=arm, n=r["n"],
                                  n_train=int((mask & (ssn < s_eval)).sum()),
                                  signed_dr2=r["dr2"], beta=r["beta"],
                                  noise_control_dr2=cn["dr2"],
                                  clean_window=bool(s_eval in ob.CLEAN_EVAL_SEASONS),
                                  n_blocks=int(m.loc[tem[0], "opp_team_season"].nunique())))
                P("    %-6s eval %d  %-9s n=%5d (train %5d, %2d blocks)  signed dR2 %+.8f  "
                  "beta %+.3e  noise %+.8f%s"
                  % (yname, s_eval, arm, r["n"], srows[-1]["n_train"], srows[-1]["n_blocks"],
                     r["dr2"], r["beta"], cn["dr2"],
                     "" if s_eval in ob.CLEAN_EVAL_SEASONS
                     else "   <-- NOT THE CLEAN WINDOW (trained on the degenerate 2021 fold)"))
    sf = pd.DataFrame(srows)
    sf.to_csv(os.path.join(ob.OUT, "SEASON_STABILITY.csv"), index=False)

    # ---------------------------------------------------------------- (c) placebos & vacuity
    ob.hdr("(c) PLACEBOS AND THE VACUOUS-CONTROL CHECK")
    packs, trm, tem = of.build_packs(v, ob.BASE_B1_HONEST, "y_ppm", mask,
                                     ob.CLEAN_EVAL_SEASONS, ssn)
    real = of.FastCell(packs, of.UNFROZEN, v["A10_opp_defrtg"], trm, tem).full()["dr2"]
    x = v["A10_opp_defrtg"].copy()
    dts = m["game_date"].to_numpy()
    # P1 league-mean-on-date: replace every value by the mean over that date. If the effect is a
    #    calendar/level artefact this reproduces it; if it is cross-sectional opponent info it dies.
    lm = pd.Series(x).groupby(pd.Series(dts)).transform("mean").to_numpy(float)
    # P2 within-date demeaned: strip the date level, keep only who-you-faced. The complement of P1.
    wd = x - lm
    # P3 opponent-season MEAN only (the 77.1% between component)
    bet = pd.Series(x).groupby(m["opp_team_season"].to_numpy()).transform("mean").to_numpy(float)
    # P4 within-opponent-season deviation only (the 22.9% within component)
    wit = x - bet
    # P5 a no-op: the identical column. MUST return exactly the observed statistic.
    prows = []
    for lbl, col, expect in [("OBSERVED", x, "reference"),
                             ("P5_noop_identical_column", x.copy(), "MUST equal OBSERVED exactly"),
                             ("P1_league_mean_on_date", lm, "date/level artefact probe"),
                             ("P2_within_date_demeaned", wd, "cross-sectional opponent info"),
                             ("P3_opp_season_mean_only", bet, "the between component (77.1%)"),
                             ("P4_within_opp_season_only", wit, "the within component (22.9%)")]:
        d = of.FastCell(packs, of.UNFROZEN, col, trm, tem).full()["dr2"]
        prows.append(dict(probe=lbl, signed_dr2=d, share_of_observed=d / real, note=expect))
        P("    %-28s signed dR2 %+.8f   = %+7.3f of the observed   (%s)"
          % (lbl, d, d / real, expect))
    noop = [r for r in prows if r["probe"] == "P5_noop_identical_column"][0]
    P("    NO-OP CHECK: |P5 - OBSERVED| = %.3e" % abs(noop["signed_dr2"] - real))
    assert abs(noop["signed_dr2"] - real) < 1e-15, "no-op placebo is not a no-op"

    # vacuous-control check: does the gain live on the rows actually treated?
    P("\n    VACUOUS-CONTROL CHECK -- the gain must live on the rows the candidate actually moves.")
    cellU = of.FastCell(packs, of.UNFROZEN, v["A10_opp_defrtg"], trm, tem)
    ya, _ = cellU._pred(cellU.d_full)
    y, yb = cellU.y, cellU.yb
    dv = np.concatenate([v["A10_opp_defrtg"][t] for t in tem])
    dvc = dv - np.mean(dv)
    q = np.quantile(np.abs(dvc), [1 / 3, 2 / 3])
    band = np.digitize(np.abs(dvc), q)
    sst = cellU.sst
    vrows = []
    for bi, blbl in enumerate(["|dev| LOW  (nearest an average defence)", "|dev| MID ",
                               "|dev| HIGH (most extreme defences)"]):
        s = band == bi
        contrib = (float(((y[s] - yb[s]) ** 2).sum()) - float(((y[s] - ya[s]) ** 2).sum())) / sst
        vrows.append(dict(band=blbl.strip(), n=int(s.sum()), sse_reduction_share_of_SST=contrib,
                          share_of_total_gain=contrib / real))
        P("      %-42s n=%5d  contributes %+.8f  = %+6.1f%% of the total gain"
          % (blbl, s.sum(), contrib, 100.0 * contrib / real))
    pd.DataFrame(prows).to_csv(os.path.join(ob.OUT, "PLACEBOS.csv"), index=False)
    pd.DataFrame(vrows).to_csv(os.path.join(ob.OUT, "VACUITY_BANDS.csv"), index=False)

    # ---------------------------------------------------------------- (d) blind-null demo
    ob.hdr("(d) THE BLIND NULL, DEMONSTRATED ON THIS SCREEN'S OWN CELL")
    blind = ob.WithinEntityShuffle(m, ("opp_team_id", "season"))
    swap = ob.EntitySwap(m, ["opp_team_id", "season"])
    cyc = ob.WithinPlayerCyclic(m)
    cellv = type("C", (), {})()
    cellv.v = {"A10_opp_defrtg": v["A10_opp_defrtg"]}
    cellv.dname = "A10_opp_defrtg"
    cellv.dr2 = lambda dv=None, c=cellU: c.dr2(dv)
    brows = []
    for sname, sw, kind in [("N_ESWAP_between_opp_team_season", swap, "VERDICT"),
                            ("N_BLIND_within_opp_team_season", blind, "CONTRAST ONLY"),
                            ("N_WITHIN_PLAYER_cyclic", cyc, "CONTRAST ONLY")]:
        res = ob.run_null(cellv, sw, n_draws=1000, seed=ob.SEED, label=sname)
        ob.save_null("BLINDDEMO__" + sname, res, extra=dict(kind=kind,
                                                            stratum="DECISION",
                                                            window="CLEAN_2023_24"))
        # how much of the candidate's variance does this scheme actually destroy?
        rng = np.random.default_rng(ob.SEED)
        pert = np.mean([float(np.mean(sw.draw(v["A10_opp_defrtg"], rng)[mask]
                                      != v["A10_opp_defrtg"][mask])) for _ in range(20)])
        keep = np.mean([float(np.corrcoef(sw.draw(v["A10_opp_defrtg"], rng)[mask],
                                          v["A10_opp_defrtg"][mask])[0, 1]) for _ in range(20)])
        brows.append(dict(scheme=sname, kind=kind, n_blocks=res["n_groups"], n_draws=1000,
                          signed_observed=res["real"], null_mean=res["null_mean"],
                          null_sd=res["null_sd"], z=res["z"], p=res["p"],
                          frac_values_changed=pert, corr_drawn_vs_real=keep))
        P("    %-34s %-13s blocks=%5d  null_sd %.8f  z %+7.3f  p %.6f   "
          "changes %.1f%% of values, corr(drawn, real) %+.4f"
          % (sname, kind, res["n_groups"], res["null_sd"], res["z"], res["p"],
             100 * pert, keep))
    pd.DataFrame(brows).to_csv(os.path.join(ob.OUT, "BLIND_NULL_DEMO.csv"), index=False)

    with open(os.path.join(HERE, "_s04.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha=ob.prereg_sha(),
                       ceiling=json.loads(cf.to_json(orient="records")),
                       stability=json.loads(sf.to_json(orient="records")),
                       placebos=prows, vacuity=vrows, blind=brows), fh, indent=2, default=float)
    with open(os.path.join(HERE, "run_log_s04.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))


if __name__ == "__main__":
    main()
