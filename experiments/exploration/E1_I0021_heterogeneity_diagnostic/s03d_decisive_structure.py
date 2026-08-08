"""
s03d -- THE ONE CLEAN TEST THAT SETTLES THE STRUCTURE QUESTION.

s03c established, using this screen's own negative controls, that the PRECISION-WEIGHTED
correlation is the anticonservative statistic here: a pure noise column (NC1) cleared it at
p=0.0076, while the same column stayed null under the unweighted (p=0.074) and rank (p=0.194)
versions.  The weights are the one player-attached quantity the covariate permutation does not
permute, so they leak.  THAT IS A DEFECT IN THIS SCREEN'S OWN FIRST PASS AND IT IS RECORDED AS ONE.

This script therefore runs a single test with every choice made the conservative way:
  * statistic  : SPEARMAN RANK correlation between the per-player coefficient and the player's own
                 strictly-prior usage.  No precision weights anywhere.
  * null       : refit the per-player coefficients on CYCLIC-SHIFTED x -- the null that preserves
                 each regressor's serial structure and that step 2 showed is the honest one -- and
                 recompute the same rank correlation.  This null tests the coefficients and the
                 covariate together, so nothing player-attached leaks.
  * controls   : both preregistered noise columns go through the identical path.
  * family-wise: max |rank correlation| across the 6 preregistered relationships, against the
                 max drawn from the same null, so the 6-way multiplicity is paid for.
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
import hd_base as hb  # noqa: E402
import s00_prereg as pr  # noqa: E402
import s02_pooling as s02  # noqa: E402

N_DRAWS = 2000


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10:
        return np.nan
    ra = pd.Series(a[ok]).rank().to_numpy()
    rb = pd.Series(b[ok]).rank().to_numpy()
    sa, sb = ra.std(), rb.std()
    if sa == 0 or sb == 0:
        return np.nan
    return float(np.mean((ra - ra.mean()) * (rb - rb.mean())) / (sa * sb))


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    hb.hdr("E1_I0021 s03d -- DECISIVE STRUCTURE TEST (rank statistic, cyclic-shift null)")
    h, _, _ = s02.check_prereg()
    P("  PREREG hash %s VERIFIED" % h)
    m = s02.build_merged(verbose=True)
    floor = pr.HEADLINE_FLOOR
    s = s02.floor_subset(m, floor)
    s, _ = s02.complete_case(s)
    s = s.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)
    pcodes, puq = pd.factorize(s["player_id"], sort=True)
    ng = len(puq)
    gns = np.bincount(pcodes, minlength=ng)
    gstarts = np.concatenate([[0], np.cumsum(gns)[:-1]])
    y = s["y_ppm_floor"].to_numpy(float)
    usage = s.groupby("player_id", sort=True)["O01_own_usg_pg"].mean().reindex(puq).to_numpy()
    P("  floor=%d  n_rows=%d  n_players_eligible(>=%d games)=%d  covariate = mean strictly-prior "
      "own usage per game" % (floor, len(s), pr.MIN_GAMES_PER_PLAYER,
                              int((gns >= pr.MIN_GAMES_PER_PLAYER).sum())))

    rows = []
    draws_by_rel = {}
    for rel in s02.ALL_RELS:
        rid = rel["id"]
        xc = s02.xcol_for(rel)
        x = pd.to_numeric(s[xc], errors="coerce").to_numpy(float)
        beta, se, npg, valid = hb.group_slopes_fast(x, y, pcodes, ng,
                                                    min_games=pr.MIN_GAMES_PER_PLAYER)
        obs = spearman(beta[valid], usage[valid])
        rng = np.random.default_rng(pr.SEED + 23)
        nd = np.empty(N_DRAWS)
        for k in range(N_DRAWS):
            xp = hb.cyclic_shift_within_groups(x, gstarts, gns, rng)
            bb, ss, _, vv = hb.group_slopes_fast(xp, y, pcodes, ng,
                                                 min_games=pr.MIN_GAMES_PER_PLAYER)
            nd[k] = spearman(bb[vv], usage[vv])
        nd = nd[np.isfinite(nd)]
        draws_by_rel[rid] = nd
        p = (1.0 + int((np.abs(nd) >= abs(obs)).sum())) / (len(nd) + 1.0)
        rows.append(dict(relationship=rid, x=xc, is_negative_control=rel in pr.NEGATIVE_CONTROLS,
                         n_players=int(valid.sum()), spearman_obs=obs,
                         null_mean=float(nd.mean()), null_sd=float(nd.std(ddof=1)),
                         null_p95_abs=float(np.percentile(np.abs(nd), 95)),
                         p_two_sided=p))
        P("  %-32s spearman(beta, prior usage) = %+.3f   null mean=%+.3f sd=%.3f  "
          "null p95|r|=%.3f   p=%.4f%s"
          % (rid, obs, nd.mean(), nd.std(ddof=1), np.percentile(np.abs(nd), 95), p,
             "   <-- NEGATIVE CONTROL" if rel in pr.NEGATIVE_CONTROLS else ""))

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(hb.OUT, "structure_decisive.csv"), index=False)

    real_ids = [r["id"] for r in pr.RELATIONSHIPS]
    n = min(len(draws_by_rel[r]) for r in real_ids)
    stack = np.vstack([np.abs(draws_by_rel[r][:n]) for r in real_ids])
    maxnull = stack.max(axis=0)
    obs_max = float(res[res.relationship.isin(real_ids)]["spearman_obs"].abs().max())
    which = res[res.relationship.isin(real_ids)].iloc[
        res[res.relationship.isin(real_ids)]["spearman_obs"].abs().to_numpy().argmax()]["relationship"]
    p_fw = (1.0 + int((maxnull >= obs_max).sum())) / (len(maxnull) + 1.0)
    hb.hdr("FAMILY-WISE ACROSS THE 6 PREREGISTERED RELATIONSHIPS")
    P("  max |spearman| observed = %.3f (%s)" % (obs_max, which))
    P("  family-wise null p95 of max|spearman| = %.3f" % float(np.percentile(maxnull, 95)))
    P("  FAMILY-WISE p = %.4f  ->  %s"
      % (p_fw, "CLEARS 0.05" if p_fw < 0.05 else "does not clear 0.05"))
    ctrl = res[res.is_negative_control]
    P("  negative controls: %s"
      % ", ".join("%s r=%+.3f p=%.4f" % (r.relationship, r.spearman_obs, r.p_two_sided)
                  for r in ctrl.itertuples()))
    verdict = ("POSITIVE: the per-player coefficients carry structure along the prior-usage axis "
               "that survives the serial-structure-preserving null, the rank statistic and the "
               "6-way family-wise correction, with both negative controls null."
               if (p_fw < 0.05 and (ctrl["p_two_sided"] > 0.05).all())
               else "NOT ESTABLISHED at the family-wise level.")
    P("  VERDICT: %s" % verdict)

    out = dict(prereg_sha256=h, n_draws=N_DRAWS, floor=floor,
               max_abs_spearman=obs_max, argmax=which, family_wise_p=p_fw,
               family_wise_null_p95=float(np.percentile(maxnull, 95)),
               controls_clean=bool((ctrl["p_two_sided"] > 0.05).all()),
               verdict=verdict,
               per_relationship={r.relationship: dict(spearman=r.spearman_obs, p=r.p_two_sided)
                                 for r in res.itertuples()})
    with open(os.path.join(hb.OUT, "_s03d.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    with open(os.path.join(hb.OUT, "run_log_s03d.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("  wrote structure_decisive.csv, _s03d.json")


if __name__ == "__main__":
    main()
