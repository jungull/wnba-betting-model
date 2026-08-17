"""
s03 -- THE EFFECT, FROZEN AND UNFROZEN, WITH THE MATCHED NULLS.

Nothing here runs until s01's anchors and s02's ceiling gate have passed.
Every statistic is SIGNED and stored signed.  Every null's raw unstandardised draws are written to
nulls/*.npz with the observed statistic, the block count and the stratum key alongside.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import od_base as ob  # noqa: E402
import od_fast as of  # noqa: E402

LOG = []
FLOOR_SINGLE = 0.00102
FLOOR_132 = 0.00235
LARGEST_LIVE = 0.002057


def P(x=""):
    print(x)
    LOG.append(str(x))


def main():
    t0 = time.time()
    ob.hdr("E1_I0043 s03 -- THE EFFECT, FROZEN AND UNFROZEN")
    P("  PREREG.md sha256 %s" % ob.prereg_sha())
    m = ob.build_merged(verbose=True)
    m["_m_hat"] = m["prior5_minutes"].fillna(m["refB_mpg"])
    ssn = m["season"].to_numpy()
    dec = ob.decision_mask(m)
    need = list(dict.fromkeys(ob.BASE_B2_FAMILY + ob.CANDIDATE + ob.NEG_CONTROL
                              + ["y_ppm", "y_pts", "_m_hat"]))
    fin = ob.finite_mask(m, need)
    mask = dec & fin
    v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float) for c in need}

    # ---------------- D087 coverage assertions on every base column -----------
    P("\n  D087 REFERENCE-COVERAGE ASSERTIONS (counts, not assumptions):")
    cov = []
    for bkey, cols in ob.BASES.items():
        cov += ob.coverage_report(m, cols, mask, bkey, P)
    pd.DataFrame(cov).to_csv(os.path.join(ob.OUT, "REFERENCE_COVERAGE.csv"), index=False)

    # ---------------- machinery validation ------------------------------------
    fast, slow, d = of.assert_fast_equals_lstsq(v, ob.BASE_B1_HONEST, "y_ppm", "A10_opp_defrtg",
                                                mask, ob.CLEAN_EVAL_SEASONS, ssn)
    P("\n  MACHINERY VALIDATION: fast FWL path %.14f vs literal lstsq refit %.14f  |diff| %.3e"
      % (fast, slow, d))

    # ---------------- the cells -----------------------------------------------
    ob.hdr("THE PREREGISTERED CELLS")
    swap = ob.EntitySwap(m, ["opp_team_id", "season"])
    dateswap = ob.WithinDateOppSwap(m)
    cyc = ob.WithinPlayerCyclic(m)
    P("  N_ESWAP  opponent-team-season relabel   : %d entity-seasons, per-season blocks %s"
      % (swap.n_groups, sorted(swap.n_blocks_per_season.items())))
    P("  N_DATE   within-date opponent swap      : %d dates with >1 opponent-team-game, %d units"
      % (dateswap.n_blocks, dateswap.n_groups))
    P("  N_WITHIN within-player cyclic (CONTRAST ONLY, never a verdict): %d player-seasons"
      % cyc.n_groups)

    rows, nullrows = [], []
    for yname in ["y_ppm", "y_pts"]:
        for wlbl, ev in [("CLEAN_2023_24", ob.CLEAN_EVAL_SEASONS),
                         ("DISCLOSED_2022", ob.DISCLOSED_CONTRAST_EVAL_SEASONS)]:
            for bkey in ["B0_COMPLETE", "B1_HONEST", "B2_FAMILY"]:
                packs, trm, tem = of.build_packs(v, ob.BASES[bkey], yname, mask, ev, ssn)
                if not packs:
                    continue
                for arm in [of.UNFROZEN, of.FROZEN, of.INTERCEPT_ONLY]:
                    for cand, is_nc in [("A10_opp_defrtg", False), ("G01_noise", True)]:
                        if arm == of.INTERCEPT_ONLY and is_nc:
                            continue
                        cell = of.FastCell(packs, arm, v[cand], trm, tem)
                        r = cell.full()
                        nbk = int(m.loc[tem[0] | (tem[1] if len(tem) > 1 else tem[0]),
                                        "opp_team_season"].nunique())
                        rows.append(dict(response=yname, window=wlbl, base=bkey, arm=arm,
                                         candidate=cand, is_negative_control=is_nc,
                                         n=r["n"], n_folds=r["n_folds"], n_blocks=nbk,
                                         signed_dr2=r["dr2"], beta=r["beta"],
                                         rmse_base=r["rmse_base"], rmse_aug=r["rmse_aug"],
                                         sst=r["sst"],
                                         vs_floor_single=r["dr2"] / FLOOR_SINGLE,
                                         vs_floor_132=r["dr2"] / FLOOR_132,
                                         vs_largest_live=r["dr2"] / LARGEST_LIVE))
                        P("    %-6s %-14s %-12s %-15s %-15s n=%5d  signed dR2 = %+.8f  "
                          "(%.2fx single-cell floor)%s"
                          % (yname, wlbl, bkey, arm, cand, r["n"], r["dr2"],
                             r["dr2"] / FLOOR_SINGLE, "  <-- NEG CONTROL" if is_nc else ""))
    cells = pd.DataFrame(rows)
    cells.to_csv(os.path.join(ob.OUT, "CELLS.csv"), index=False)

    # ---------------- nulls on the primary / co-primary and the family ---------
    ob.hdr("THE NULLS -- MATCHED TO THE LEVEL THE CANDIDATE VARIES AT")
    P("  A10_opp_defrtg is a TEAM-SEASON quantity: between-opponent-team-season variance share "
      "%.6f (reproduced anchor A3). Both verdict nulls are BETWEEN-entity."
      % 0.771355969528)
    todo = []
    for yname in ["y_ppm", "y_pts"]:
        for bkey in ["B0_COMPLETE", "B1_HONEST", "B2_FAMILY"]:
            for arm in [of.UNFROZEN, of.FROZEN]:
                todo.append((yname, "CLEAN_2023_24", ob.CLEAN_EVAL_SEASONS, bkey, arm,
                             "A10_opp_defrtg"))
    todo.append(("y_ppm", "CLEAN_2023_24", ob.CLEAN_EVAL_SEASONS, "B1_HONEST", of.UNFROZEN,
                 "G01_noise"))
    todo.append(("y_ppm", "DISCLOSED_2022", ob.DISCLOSED_CONTRAST_EVAL_SEASONS, "B1_HONEST",
                 of.UNFROZEN, "A10_opp_defrtg"))

    for yname, wlbl, ev, bkey, arm, cand in todo:
        packs, trm, tem = of.build_packs(v, ob.BASES[bkey], yname, mask, ev, ssn)
        cell = of.FastCell(packs, arm, v[cand], trm, tem)
        cellv = type("C", (), {})()
        cellv.v = {cand: v[cand]}
        cellv.dname = cand
        cellv.dr2 = lambda dv=None, c=cell: c.dr2(dv)
        schemes = [("N_ESWAP", swap), ("N_DATE", dateswap)]
        if bkey == "B1_HONEST" and cand == "A10_opp_defrtg" and wlbl == "CLEAN_2023_24":
            schemes.append(("N_WITHIN_CONTRAST_ONLY", cyc))
        for sname, sw in schemes:
            res = ob.run_null(cellv, sw, n_draws=ob.N_DRAWS, seed=ob.SEED,
                              label="%s|%s|%s|%s|%s|%s" % (yname, wlbl, bkey, arm, cand, sname))
            fn = ob.save_null("%s__%s__%s__%s__%s__%s" % (yname, wlbl, bkey, arm, cand, sname),
                              res, extra=dict(stratum="DECISION_n_prior8_prior5min24",
                                              response=yname, base=bkey, arm=arm,
                                              window=wlbl, scheme=sname))
            nullrows.append(dict(response=yname, window=wlbl, base=bkey, arm=arm, candidate=cand,
                                 scheme=sname, is_verdict_null=(sname != "N_WITHIN_CONTRAST_ONLY"),
                                 n_blocks=res["n_groups"], n_draws=res["n_draws"],
                                 signed_observed=res["real"], null_mean=res["null_mean"],
                                 null_sd=res["null_sd"], z=res["z"], p=res["p"],
                                 p_min_attainable=1.0 / (res["n_draws"] + 1), npz=os.path.basename(fn)))
            P("    %-6s %-12s %-15s %-15s %-22s blocks=%5d  obs %+.8f  null_mean %+.8f  "
              "null_sd %.8f  z %+7.3f  p %.6f%s"
              % (yname, bkey, arm, cand, sname, res["n_groups"], res["real"], res["null_mean"],
                 res["null_sd"], res["z"], res["p"],
                 "   [CONTRAST ONLY]" if sname == "N_WITHIN_CONTRAST_ONLY" else ""))
    nf = pd.DataFrame(nullrows)
    nf.to_csv(os.path.join(ob.OUT, "NULLS.csv"), index=False)

    P("\n  elapsed %.1f s" % (time.time() - t0))
    with open(os.path.join(HERE, "_s03.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha=ob.prereg_sha(),
                       cells=json.loads(cells.to_json(orient="records")),
                       nulls=json.loads(nf.to_json(orient="records"))), fh, indent=2, default=float)
    with open(os.path.join(HERE, "run_log_s03.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))


if __name__ == "__main__":
    main()
