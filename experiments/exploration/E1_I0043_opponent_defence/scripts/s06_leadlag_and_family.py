"""
s06 -- (a) a LEAD-LAG / oracle-column probe, and (b) the family-wise correction over this screen's
       own 12 preregistered cells.

(a) WHY.  The whole channel turns out to be the opponent's SEASON-LEVEL defensive level (s04 P3
    reproduces 117% of it from the opponent-season mean alone).  A season-level quantity is exactly
    the shape a leak would take if the "strictly prior" expanding mean were contaminated by the
    rest of the season.  The probe: replace the strictly-prior column with a FULL-SEASON mean, which
    reads the future by construction.  If the prior column already performs like the oracle column,
    the prior column is not prior.  If the oracle column is materially BETTER, the prior column is
    a genuinely noisy forward-looking estimate and the separation is the evidence.
    THE ORACLE COLUMN IS A DIAGNOSTIC.  It is never a headline and never a lead.

(b) The 12 preregistered real cells get a max-statistic family-wise p under the verdict null, with
    the SAME draws shared across cells so the maximum is coupled rather than a stack of independent
    maxima.  D103: the unfair comparison is against a single preregistered test, so the family bar
    is computed and quoted.
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
FLOOR_SINGLE, FLOOR_132 = 0.00102, 0.00235


def P(x=""):
    print(x)
    LOG.append(str(x))


def main():
    ob.hdr("E1_I0043 s06 -- LEAD-LAG ORACLE PROBE AND THE FAMILY-WISE BAR")
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
    x = v["A10_opp_defrtg"]

    # ---------------------------------------------------------------- (a) oracle probe
    ob.hdr("(a) LEAD-LAG ORACLE PROBE -- DIAGNOSTIC ONLY, never a headline")
    ots = m["opp_team_season"].to_numpy()
    full_season_mean = pd.Series(x).groupby(ots).transform("mean").to_numpy(float)
    # a strictly-prior season-level estimate: expanding mean of the opponent's own prior values,
    # which is what A10 already is; and the opponent's PREVIOUS-season mean, strictly prior.
    prev = {}
    for key in np.unique(ots):
        tid, sy = key.split("|")
        prev[key] = np.nan
    ms = pd.DataFrame(dict(k=ots, s=ssn, t=m["opp_team_id"].astype(str).to_numpy(), x=x))
    tmean = ms.groupby(["t", "s"], sort=False)["x"].mean()
    prevcol = np.array([tmean.get((t, s - 1), np.nan)
                        for t, s in zip(ms["t"].to_numpy(), ssn)], float)
    prev_ok = np.isfinite(prevcol)
    P("  prior-season opponent mean available on %d of %d rows (%.1f%%)"
      % (prev_ok.sum(), len(m), 100.0 * prev_ok.mean()))

    rows = []
    for yname in ["y_ppm", "y_pts"]:
        packs, trm, tem = of.build_packs(v, ob.BASE_B1_HONEST, yname, mask,
                                         ob.CLEAN_EVAL_SEASONS, ssn)
        base_cell = of.FastCell(packs, of.UNFROZEN, x, trm, tem)
        for lbl, col, kind in [
                ("A10 strictly-prior expanding (THE CANDIDATE)", x, "REAL"),
                ("opponent FULL-SEASON mean (READS THE FUTURE)", full_season_mean, "ORACLE"),
                ("opponent PREVIOUS-SEASON mean (strictly prior)",
                 np.where(prev_ok, prevcol, np.nanmean(x)), "REAL")]:
            d = of.FastCell(packs, of.UNFROZEN, col, trm, tem).full()["dr2"]
            rows.append(dict(response=yname, column=lbl, kind=kind, signed_dr2=d))
            P("    %-6s %-46s %-6s signed dR2 %+.8f" % (yname, lbl, kind, d))
        real = [r for r in rows if r["response"] == yname and r["kind"] == "REAL"][0]["signed_dr2"]
        orc = [r for r in rows if r["response"] == yname and r["kind"] == "ORACLE"][0]["signed_dr2"]
        P("    -> oracle / prior ratio = %.3f.  %s"
          % (orc / real,
             "The future-reading column is MATERIALLY BETTER, so the prior column is genuinely "
             "prior and noisy." if orc / real > 1.15 else
             "The prior column performs like the oracle -- THAT IS THE LEAK SIGNATURE and must be "
             "investigated before anything here is believed."))
    pd.DataFrame(rows).to_csv(os.path.join(ob.OUT, "LEADLAG_ORACLE.csv"), index=False)

    # ---------------------------------------------------------------- (b) family-wise
    ob.hdr("(b) FAMILY-WISE BAR OVER THIS SCREEN'S 12 PREREGISTERED REAL CELLS")
    swap = ob.EntitySwap(m, ["opp_team_id", "season"])
    cells, keys = [], []
    for yname in ["y_ppm", "y_pts"]:
        for wlbl, ev in [("CLEAN_2023_24", ob.CLEAN_EVAL_SEASONS),
                         ("DISCLOSED_2022", ob.DISCLOSED_CONTRAST_EVAL_SEASONS)]:
            if wlbl != "CLEAN_2023_24":
                continue
            for bkey in ["B0_COMPLETE", "B1_HONEST", "B2_FAMILY"]:
                packs, trm, tem = of.build_packs(v, ob.BASES[bkey], yname, mask, ev, ssn)
                for arm in [of.UNFROZEN, of.FROZEN]:
                    cells.append(of.FastCell(packs, arm, x, trm, tem))
                    keys.append((yname, wlbl, bkey, arm))
    P("  family size K = %d (2 responses x 3 bases x 2 arms, one stratum, one window)" % len(cells))
    assert len(cells) == 12, "family size is not 12"
    obs = np.array([c.full()["dr2"] for c in cells])
    rng = np.random.default_rng(ob.SEED)
    ND = 2000
    maxd = np.empty(ND)
    allsd = np.empty((ND, len(cells)))
    for i in range(ND):
        xd = swap.draw(x, rng)                       # SHARED draw across every cell -> coupled max
        vals = np.array([c.dr2(xd) for c in cells])
        allsd[i] = vals
        maxd[i] = vals.max()
    fw, per = [], []
    for j, k in enumerate(keys):
        p_cell = (1.0 + int((allsd[:, j] >= obs[j]).sum())) / (ND + 1.0)
        p_fw = (1.0 + int((maxd >= obs[j]).sum())) / (ND + 1.0)
        fw.append(dict(response=k[0], window=k[1], base=k[2], arm=k[3], signed_dr2=obs[j],
                       p_per_cell=p_cell, p_familywise_maxt=p_fw,
                       null_mean=float(allsd[:, j].mean()), null_sd=float(allsd[:, j].std(ddof=1)),
                       vs_floor_single=obs[j] / FLOOR_SINGLE, vs_floor_132=obs[j] / FLOOR_132))
        P("    %-6s %-12s %-9s dR2 %+.8f   p_cell %.6f   p_FAMILYWISE %.6f   (%.2fx single-cell "
          "floor)" % (k[0], k[2], k[3], obs[j], p_cell, p_fw, obs[j] / FLOOR_SINGLE))
    ff = pd.DataFrame(fw)
    ff.to_csv(os.path.join(ob.OUT, "FAMILYWISE.csv"), index=False)
    np.savez(os.path.join(ob.NULLS, "familywise_maxt_draws.npz"),
             max_draws_raw_unstandardised=maxd, per_cell_draws_raw_unstandardised=allsd,
             observed_signed=obs, keys=np.array([str(k) for k in keys]))
    P("  n clearing family-wise at 0.05: %d of 12" % int((ff.p_familywise_maxt < 0.05).sum()))

    with open(os.path.join(HERE, "_s06.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha=ob.prereg_sha(), leadlag=rows,
                       familywise=json.loads(ff.to_json(orient="records"))), fh, indent=2,
                  default=float)
    with open(os.path.join(HERE, "run_log_s06.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))


if __name__ == "__main__":
    main()
