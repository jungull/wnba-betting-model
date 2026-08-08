"""s06_retrospective.py -- STEP 2.  WHAT COULD EACH RECORDED NULL ACTUALLY HAVE DETECTED?

THE ANALYTIC MDE, AND WHY IT IS EXACT FOR THIS STATISTIC.

  Write the incremental statistic as dR2 = (e.xt)^2 / ((xt.xt) * SST).  Put
  u = (e.xt) / sqrt((xt.xt) * SST), so dR2 = u^2 exactly.  Planting an effect of size delta
  along xt adds c*xt to the response with c = sqrt(delta*SST/(xt.xt)), which shifts u by
  exactly sqrt(delta).  Therefore

        dR2(delta) = (u + sqrt(delta))^2 ,    u ~ N(0, sqrt(mu_null))

  because E[u^2] = E[dR2_null] = mu_null.  Rejecting when dR2 >= T gives

        power(delta) = Phi( (sqrt(delta) - sqrt(T)) / sqrt(mu_null) )
        MDE80        = ( sqrt(T) + 0.8416 * sqrt(mu_null) )^2 ,   T = mu_null + t_crit*sd_null

  Every quantity on the right is PUBLISHED BY THE SCREENS THEMSELVES (null mean, null sd, and
  the family-wise t threshold).  So the retrospective needs no re-run: it reads each screen's
  own null and asks what that null could have resolved.

  THIS FORMULA IS VALIDATED against the 5,616-row simulated power surface from s04 before it is
  used on anything.  The validation is printed and written to disk; if it fails the retrospective
  is not reported.

  For screens whose statistic is a PAIRED forecast difference (signed, centred on zero under a
  cluster sign-flip null) the model is dR2 ~ N(0, sd) shifted by delta, so
        MDE80 = t_crit*sd + 0.8416*sd .
  Those cells are marked `stat_family=paired` and never mixed with the others.

  NO SCREEN'S RESULT IS USED TO DECIDE WHETHER IT WAS POWERED.  Only its design -- n, grouping
  level, null width, family size -- enters.  (Preregistration s7 item 7.)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from df_base import EXPL, OUT, hdr
from s04_power import FAMILY_SIZES, familywise_thresholds

Z80 = 0.8416212335729143          # Phi^{-1}(0.80), implemented without scipy
BEST_LEAD = 0.0023                # D089, walk-forward points, the programme's best ever
CEIL_D079 = 0.001127              # D079 arithmetic ceiling, shot mix -> points
CEIL_D084 = 0.000129              # D084 arithmetic ceiling, conversion -> points
D097_FLOOR = (1.6e-4, 2.2e-4)     # the only resolution figure previously in the ledger

FORBIDDEN = ("E1_I0027_reference_ladder", "E0_I0028_degeneracy_sweep", "E0_I0029_freethrow_hurdle")


def mde80_increment(mu_null, sd_null, t_crit):
    T = mu_null + t_crit * sd_null
    if not np.isfinite(T) or T < 0 or not np.isfinite(mu_null) or mu_null < 0:
        return float("nan")
    return float((np.sqrt(T) + Z80 * np.sqrt(mu_null)) ** 2)


def mde80_paired(sd_null, t_crit):
    if not np.isfinite(sd_null):
        return float("nan")
    return float(t_crit * sd_null + Z80 * sd_null)


def mde80_tscale(sd_null_t, t_crit, n):
    """Two screens (E0_I0014, E0_I0019) published their nulls on the CLASSICAL-t scale, not on
    the dR2 scale.  For a single added regressor dR2 = t^2/(t^2+df) ~= t^2/n for small dR2, and
    planting an effect delta shifts t by sqrt(delta*n).  Both the threshold and the shift are
    measured from the SAME null mean, so the mean cancels and only the width enters:

        MDE80 = ((t_crit + z80) * sd_null_t)^2 / n

    This conversion is declared, and every cell it touches carries stat_family='t_statistic'."""
    if not np.isfinite(sd_null_t) or not np.isfinite(n) or n <= 0:
        return float("nan")
    return float(((t_crit + Z80) * sd_null_t) ** 2 / n)


N_E0_I0014 = 13879        # rows in E0_I0014_residual_heterogeneity/analysis_frame.parquet
N_E0_I0019 = 17809        # rows in E0_I0019_availability_forecast/analysis_frame.parquet


# =============================================================== validation ===================
def validate():
    mt = pd.read_csv(os.path.join(OUT, "s04_mde_table.csv"))
    mt = mt[np.isfinite(mt["mde80_familywise"])].copy()
    mt["mde80_analytic"] = [mde80_increment(r.null_mean, r.null_sd, r.t_crit_familywise)
                            for r in mt.itertuples()]
    mt["ratio"] = mt["mde80_analytic"] / mt["mde80_familywise"]
    mt2 = mt.copy()
    mt2["mde80_analytic_percell"] = [mde80_increment(r.null_mean, r.null_sd, r.t_crit_per_cell)
                                     for r in mt.itertuples()]
    mt2["ratio_percell"] = mt2["mde80_analytic_percell"] / mt2["mde80_per_cell"]
    mt2.to_csv(os.path.join(OUT, "s06_validation_analytic_vs_simulated.csv"), index=False)
    return mt2


# =============================================================== harvest ======================
def harvest(FW):
    rows = []

    def fwt(arm, K):
        """Family-wise q95 max-t at family size K.  K values not on the precomputed grid are
        log-linearly interpolated between the two neighbouring grid points; the grid itself is
        computed from the real 154-cell null matrix."""
        if (arm, K) in FW:
            return FW[(arm, K)]["q95_maxt"]
        ks = sorted(FAMILY_SIZES)
        lo = max([k for k in ks if k <= K], default=ks[0])
        hi = min([k for k in ks if k >= K], default=ks[-1])
        if lo == hi:
            return FW[(arm, lo)]["q95_maxt"]
        a, b = FW[(arm, lo)]["q95_maxt"], FW[(arm, hi)]["q95_maxt"]
        w = (np.log(K) - np.log(lo)) / (np.log(hi) - np.log(lo))
        return float(a + w * (b - a))

    # ---- E0_I0016 (D085) -- 132 cells, entity-swap + within-entity nulls, means published ----
    p = os.path.join(EXPL, "E0_I0016_efficiency_predictors", "screen_results.csv")
    t = pd.read_csv(p)
    K = len(t)
    for r in t.itertuples():
        for arm, mu, sd, lvl in (("N1_within", r.null_mean_N1, r.null_sd_N1,
                                  "within_%s" % r.entity_level),
                                 ("N2_entity_swap", r.null_mean_N2, r.null_sd_N2,
                                  "entity_swap_%s" % r.entity_level)):
            rows.append(dict(screen="E0_I0016_efficiency_predictors", decision="D085",
                             family_size_K=K, cell=r.cell_key, n=int(r.n),
                             n_clusters=int(r.n_entity_seasons), null_arm=arm, level=lvl,
                             stat_family="increment", null_mean=float(mu), null_sd=float(sd),
                             null_mean_source="published", reported_dr2=float(r.dr2),
                             reported_p_fw=float(r.p_familywise_maxt),
                             mde80_percell=mde80_increment(mu, sd, 1.645),
                             mde80_fw=mde80_increment(mu, sd, fwt(arm, 132))))

    # ---- E1_I0018 (D089) -- 154 cells, the best-lead screen ---------------------------------
    p = os.path.join(EXPL, "E1_I0018_teammate_volume_channel", "screen_results.csv")
    t = pd.read_csv(p)
    K = len(t)
    for r in t.itertuples():
        for arm, mu, sd, lvl in (("N1_within", r.null_mean_N1, r.null_sd_N1,
                                  "within_team_season"),
                                 ("N2_entity_swap", r.null_mean_N2, r.null_sd_N2,
                                  "entity_swap_team_season")):
            rows.append(dict(screen="E1_I0018_teammate_volume_channel", decision="D089",
                             family_size_K=K, cell=r.cell_key, n=int(r.n), n_clusters=48,
                             null_arm=arm, level=lvl, stat_family="increment",
                             null_mean=float(mu), null_sd=float(sd),
                             null_mean_source="published", reported_dr2=float(r.dr2),
                             reported_p_fw=float(r.p_familywise_maxt),
                             mde80_percell=mde80_increment(mu, sd, 1.645),
                             mde80_fw=mde80_increment(mu, sd, fwt(arm, 154))))

    # ---- E0_I0014 (residual heterogeneity) -- 348 cells, sd only ----------------------------
    p = os.path.join(EXPL, "E0_I0014_residual_heterogeneity", "screen_results.csv")
    t = pd.read_csv(p)
    K = len(t)
    for r in t.itertuples():
        sd = float(r.null_correct_sd)      # ON THE CLASSICAL-t SCALE, not dR2
        rows.append(dict(screen="E0_I0014_residual_heterogeneity", decision="D078/D082 era",
                         family_size_K=K, cell="%s|%s" % (r.candidate, r.dependent),
                         n=N_E0_I0014, n_clusters=np.nan, null_arm="N1_within",
                         level=str(r.correct_null_level), stat_family="t_statistic",
                         null_mean=np.nan, null_sd=sd, null_mean_source="t_scale_mean_cancels",
                         reported_dr2=float(r.delta_r2_plain_unweighted),
                         reported_p_fw=float(r.p_familywise_whole_screen),
                         mde80_percell=mde80_tscale(sd, 1.645, N_E0_I0014),
                         mde80_fw=mde80_tscale(sd, fwt("N1_within", 348), N_E0_I0014)))

    # ---- E0_I0024 (rebounds/assists characterisation, D097) -- 250 cells --------------------
    p = os.path.join(EXPL, "E0_I0024_reb_ast_characterisation", "upstream_signals.csv")
    t = pd.read_csv(p)
    K = len(t)
    for r in t.itertuples():
        for arm, sd, lvl in (("N2_entity_swap", r.null_sd_swap, "entity_swap"),
                             ("N1_within", r.null_sd_cyclic, "within_cyclic")):
            sd = float(sd)
            mu = sd / np.sqrt(2.0)
            rows.append(dict(screen="E0_I0024_reb_ast_characterisation", decision="D097",
                             family_size_K=K,
                             cell="%s|%s|%s|%s" % (r.stratum, r.target, r.base, r.candidate),
                             n=int(r.n), n_clusters=np.nan, null_arm=arm, level=lvl,
                             stat_family="increment", null_mean=mu, null_sd=sd,
                             null_mean_source="ESTIMATED_sd_over_sqrt2",
                             reported_dr2=float(r.dr2), reported_p_fw=float(r.fw_p),
                             mde80_percell=mde80_increment(mu, sd, 1.645),
                             mde80_fw=mde80_increment(mu, sd, fwt(arm, 250))))

    # ---- E0_I0019 (availability forecast, D090) -- 318 cells, means published ---------------
    p = os.path.join(EXPL, "E0_I0019_availability_forecast", "screen_results_repaired.csv")
    t = pd.read_csv(p)
    K = len(t)
    for r in t.itertuples():
        mu, sd = float(r.nullmean_between), float(r.nullsd_between)   # CLASSICAL-t scale
        rows.append(dict(screen="E0_I0019_availability_forecast", decision="D090",
                         family_size_K=K, cell="%s|%s" % (r.candidate, r.dependent),
                         n=int(r.n), n_clusters=np.nan, null_arm="N2_entity_swap",
                         level="between_block", stat_family="t_statistic",
                         null_mean=mu, null_sd=sd, null_mean_source="t_scale_mean_cancels",
                         reported_dr2=np.nan, reported_p_fw=float(r.p_familywise),
                         mde80_percell=mde80_tscale(sd, 1.645, int(r.n)),
                         mde80_fw=mde80_tscale(sd, fwt("N2_entity_swap", 318), int(r.n))))

    # ---- E0_I0017 (shot quality -> efficiency, D087) -- 117 cells, sd only ------------------
    p = os.path.join(EXPL, "E0_I0017_shot_quality_efficiency", "screen_results.csv")
    t = pd.read_csv(p)
    K = len(t)
    for r in t.itertuples():
        sd = float(r.sd_null_correct)
        mu = sd / np.sqrt(2.0)
        rows.append(dict(screen="E0_I0017_shot_quality_efficiency", decision="D087",
                         family_size_K=K,
                         cell="%s|%s|%s" % (r.candidate, r.outcome, r.entity), n=int(r.n),
                         n_clusters=np.nan, null_arm="N2_entity_swap",
                         level=str(r.entity), stat_family="increment", null_mean=mu, null_sd=sd,
                         null_mean_source="ESTIMATED_sd_over_sqrt2",
                         reported_dr2=float(r.dR2), reported_p_fw=float(r.p_familywise_maxz),
                         mde80_percell=mde80_increment(mu, sd, 1.645),
                         mde80_fw=mde80_increment(mu, sd, fwt("N2_entity_swap", 132))))

    # ---- E1_I0023 (usage x defence, D098/D099) -- PAIRED statistic -------------------------
    p = os.path.join(EXPL, "E1_I0023_usage_defence_interaction", "interaction_forecast.csv")
    t = pd.read_csv(p)
    K = len(t)
    for r in t.itertuples():
        sd = float(r.null_sd_cluster)
        rows.append(dict(screen="E1_I0023_usage_defence_interaction", decision="D098/D099",
                         family_size_K=K, cell=str(r.cell_id), n=int(r.n_scored),
                         n_clusters=int(r.n_clusters_present), null_arm="paired_cluster_signflip",
                         level="cluster", stat_family="paired", null_mean=0.0, null_sd=sd,
                         null_mean_source="paired_null_is_centred",
                         reported_dr2=float(r.dr2_a_minus_b), reported_p_fw=np.nan,
                         mde80_percell=mde80_paired(sd, 1.645),
                         mde80_fw=mde80_paired(sd, fwt("N2_entity_swap", 120))))

    return pd.DataFrame(rows)


if __name__ == "__main__":
    FW = familywise_thresholds()

    hdr("A. VALIDATE THE ANALYTIC MDE AGAINST THE 5,616-ROW SIMULATED POWER SURFACE")
    v = validate()
    for lab, col in (("family-wise", "ratio"), ("per-cell", "ratio_percell")):
        rr = v[col].replace([np.inf, -np.inf], np.nan).dropna()
        print("  %-12s analytic/simulated  median=%.3f  p10=%.3f  p90=%.3f  n=%d"
              % (lab, rr.median(), rr.quantile(0.1), rr.quantile(0.9), len(rr)))
    ok = abs(v["ratio"].median() - 1.0) < 0.15 and abs(v["ratio_percell"].median() - 1.0) < 0.15
    print("  VALIDATION: %s" % ("PASS -- analytic MDE reproduces the simulation" if ok
                                else "FAIL -- retrospective NOT reported"))
    assert ok, "analytic MDE does not reproduce the simulated power surface"

    hdr("B. RETROSPECTIVE OVER EVERY RECORDED CELL WITH A PUBLISHED NULL WIDTH")
    R = harvest(FW)
    R["could_detect_best_lead_0.0023_percell"] = R["mde80_percell"] <= BEST_LEAD
    R["could_detect_best_lead_0.0023_fw"] = R["mde80_fw"] <= BEST_LEAD
    R["could_detect_D079_ceiling_0.001127_fw"] = R["mde80_fw"] <= CEIL_D079
    R["could_detect_D084_ceiling_0.000129_fw"] = R["mde80_fw"] <= CEIL_D084
    R.to_csv(os.path.join(OUT, "retrospective_power.csv"), index=False)
    print("  %d cells across %d screens -> retrospective_power.csv"
          % (len(R), R["screen"].nunique()))

    g = R.groupby(["screen", "decision", "null_arm"]).agg(
        cells=("cell", "size"), K=("family_size_K", "max"),
        n_med=("n", "median"),
        mde80_fw_med=("mde80_fw", "median"), mde80_fw_min=("mde80_fw", "min"),
        mde80_percell_med=("mde80_percell", "median"),
        pct_could_see_best_lead_fw=("could_detect_best_lead_0.0023_fw", "mean"),
        pct_could_see_D079_fw=("could_detect_D079_ceiling_0.001127_fw", "mean"),
        pct_could_see_D084_fw=("could_detect_D084_ceiling_0.000129_fw", "mean"),
    ).reset_index()
    g.to_csv(os.path.join(OUT, "s06_retrospective_by_screen.csv"), index=False)
    pd.set_option("display.width", 250)
    print(g.to_string(index=False))
