"""
c01 -- REPRODUCTION GATE.  Reproduce D098's +0.023863 and +0.018703 BEFORE anything else is computed.

If this fails the screen STOPS and reports.  Everything downstream compares a new number to D098's,
and a comparison to a number that could not be regenerated is worthless.

The reproduction is run TWO ways: through D098's own `s05.score` (the function that produced the
published figure) and through this screen's `score_rung('L4', ...)` (the function every later rung
goes through).  They must agree with each other AND with the published value.  That is what licenses
using the new ladder code to make claims about D098's number.
"""
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np      # noqa: E402
import pandas as pd     # noqa: E402
import cbase as cb      # noqa: E402
import c00_prereg as c0  # noqa: E402

TOL = 1e-9


def main():
    P = cb.Tee()
    cb.hdr("E1_I0025 c01 -- REPRODUCTION GATE")
    h, added, dropped = c0.check()
    P("  PREREG hash %s VERIFIED.  specs added=%d dropped=%d" % (h, len(added), len(dropped)))
    P("  D098 modules imported READ-ONLY from %s" % cb.D098DIR)

    m, v, need, ncl, unit = cb.build(P)
    mask = cb.decision_mask(m, v, need)
    tier, q = cb.tier_labels(m, v, mask)
    P("  DECISION stratum: %d rows.  tercile cut points from the 2021 training fold only: "
      "%.6f / %.6f" % (int(mask.sum()), q[0], q[1]))
    for t in (0, 1, 2):
        P("    %-8s %d rows in frame" % (cb.TN[t], int((mask & (tier == t)).sum())))

    rows = []
    for rid in ("ppm", "points"):
        resp = cb.s02.RESP[rid]
        # ---- route 1: D098's own function, unchanged ----
        d098 = cb.s05.score(m, v, cb.BASE, mask & (tier == 2), v[cb.DEFENCE], cb.UCOL, False, resp)
        dr2_d098, y98 = d098[0], d098[1]
        # ---- route 2: this screen's ladder code at rung L4 ----
        fl = cb.folds(m, mask, mask & (tier == 2))
        dr2_new, y, A, B, C, sst, bet = cb.score_rung(m, v, "L4", fl, v[cb.DEFENCE], tier, resp,
                                                      ret_pred=True)
        pub = cb.D098_ANCHORS["tier_refit_defence_maineffect_%s_DECISION_T3" % rid]
        rows.append(dict(response=rid, published=pub, reproduced_via_D098_score=dr2_d098,
                         reproduced_via_E1_I0025_ladder=dr2_new,
                         abs_delta_published_vs_D098route=abs(dr2_d098 - pub),
                         abs_delta_published_vs_newroute=abs(dr2_new - pub),
                         abs_delta_route_vs_route=abs(dr2_new - dr2_d098),
                         n_scored=int(len(y)), n_scored_D098route=int(len(y98)),
                         sst=sst, sd_response=float(np.std(y, ddof=1)),
                         mean_defence_beta=float(np.mean([b[0] for b in bet])),
                         PASS=bool(abs(dr2_new - pub) < TOL and abs(dr2_d098 - pub) < TOL
                                   and int(len(y)) == cb.D098_ANCHORS["n_scored_T3_DECISION"])))
        r = rows[-1]
        P("  %-7s published %+.15f" % (rid, pub))
        P("          D098 route %+.15f   |delta| = %.3e" % (dr2_d098, r["abs_delta_published_vs_D098route"]))
        P("          new  route %+.15f   |delta| = %.3e" % (dr2_new, r["abs_delta_published_vs_newroute"]))
        P("          route-vs-route |delta| = %.3e   n_scored=%d (published %d)   -> %s"
          % (r["abs_delta_route_vs_route"], r["n_scored"],
             cb.D098_ANCHORS["n_scored_T3_DECISION"], "PASS" if r["PASS"] else "*** FAIL ***"))

    # ------------------------------------------------------------------ the other two anchors
    P("")
    P("  The two POOLED anchors this screen's ladder must also line up with (D098 s05, ALL_TIERS):")
    anch = []
    for rid in ("ppm", "points"):
        resp = cb.s02.RESP[rid]
        me = cb.s05.score(m, v, cb.BASE, mask, v[cb.DEFENCE], cb.UCOL, False, resp)[0]
        it = cb.s05.score(m, v, cb.BASE, mask, v[cb.DEFENCE], cb.UCOL, True, resp)[0]
        pm = cb.D098_ANCHORS["pooled_defence_maineffect_%s_DECISION_ALL" % rid]
        pi = cb.D098_ANCHORS["pooled_linear_interaction_%s_DECISION_ALL" % rid]
        anch.append(dict(response=rid, anchor="pooled_defence_maineffect_ALL_TIERS",
                         published=pm, reproduced=me, abs_delta=abs(me - pm)))
        anch.append(dict(response=rid, anchor="pooled_linear_interaction_ALL_TIERS",
                         published=pi, reproduced=it, abs_delta=abs(it - pi)))
        P("    %-7s pooled defence main   published %+.12f  reproduced %+.12f  |d|=%.3e"
          % (rid, pm, me, abs(me - pm)))
        P("    %-7s pooled linear interac published %+.12f  reproduced %+.12f  |d|=%.3e"
          % (rid, pi, it, abs(it - pi)))

    rdf = pd.DataFrame(rows)
    adf = pd.DataFrame(anch)
    rdf.to_csv(os.path.join(cb.OUT, "reproduction.csv"), index=False)
    adf.to_csv(os.path.join(cb.OUT, "reproduction_anchors.csv"), index=False)

    allpass = bool(rdf["PASS"].all()) and bool((adf["abs_delta"] < TOL).all())
    cb.hdr("REPRODUCTION GATE: %s" % ("PASS -- proceed" if allpass else "FAIL -- STOP"))
    P("  max |delta| over the two headline anchors = %.3e" % rdf["abs_delta_published_vs_newroute"].max())
    P("  max |delta| over the four pooled anchors  = %.3e" % adf["abs_delta"].max())
    if not allpass:
        P("  *** THE SCREEN STOPS HERE.  Downstream comparisons would be meaningless. ***")

    with open(os.path.join(cb.OUT, "_c01.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha256=h, gate_pass=allpass, tol=TOL,
                       headline=json.loads(rdf.to_json(orient="records")),
                       pooled_anchors=json.loads(adf.to_json(orient="records")),
                       tier_cut_low=float(q[0]), tier_cut_high=float(q[1]),
                       n_decision_rows=int(mask.sum()),
                       n_clusters=int(ncl)), fh, indent=2, default=float)
    P.write(os.path.join(cb.OUT, "run_log_c01.txt"))
    if not allpass:
        sys.exit(2)


if __name__ == "__main__":
    main()
