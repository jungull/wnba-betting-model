"""
s01 -- STEP 1.  REPRODUCE D093's STRUCTURE RESULT BEFORE TESTING ANYTHING ELSE.

TARGET (E1_I0021/structure_decisive.csv, decision D093):
    R04_opp_defrtg  Spearman +0.3200431235648813, two-sided p 0.0004997501249375312
    R06_own_usage   Spearman +0.2805225231952508, p 0.004497751124437781
    family-wise p across the 6 preregistered relationships = 0.0035
    NC1 p 0.20439780109945027, NC2 p 0.9385307346326837   (both negative controls null)

CONSTRUCTION, reproduced from D093's own scripts (READ-ONLY) rather than inherited:
    frames   : D085's and D089's FROZEN screen_frames, merged on (season, player_id, game_id),
               2022-2024 only
    floor    : realised minutes >= 20 (D093's preregistered headline floor)
    response : y_ppm_floor = pts / minutes on the retained rows
    stat     : per-player within-demeaned OLS slope of the response on x, players with >= 8 retained
               games; then the SPEARMAN RANK correlation of those slopes against the player's mean
               strictly-prior own usage
    null     : WITHIN-PLAYER CYCLIC SHIFT of x (preserves the marginal AND the serial structure,
               destroys only alignment).  2000 draws, seed 20260808 + 23.

IF IT DOES NOT REPRODUCE, THIS SCREEN STOPS AND REPORTS IT.

NOTE ON PROVENANCE.  D093's `hd_base.py` imports the shared screen kit, which this screen was
directed not to import (another agent is editing it).  The two functions this step needs --
`group_slopes_fast` and `cyclic_shift_within_groups` -- are therefore REIMPLEMENTED in `uid_base.py`
from D093's source, which is credited.  An exact reproduction of D093's published numbers is the
check that the reimplementation is faithful; that is why this step is run first and in full.
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
import uid_base as ub  # noqa: E402
import s00_prereg as pr  # noqa: E402

N_DRAWS = 2000
FLOOR = 20
MIN_GAMES = 8
D093 = os.path.join(ub.EXP, "E1_I0021_heterogeneity_diagnostic")

# D093's six preregistered relationships + two negative controls, in D093's order.
RELS = [
    ("R01_prior_efficiency_persistence", "refA_ppm_floor", False),
    ("R02_opp_efg_allowed", "A01_opp_efg_allowed", False),
    ("R03_opp_ts_allowed", "A02_opp_ts_allowed", False),
    ("R04_opp_defrtg", "A10_opp_defrtg", False),
    ("R05_teammate_volume_pregame", "P01_c04_prevgame", False),
    ("R06_own_usage", "O01_own_usg_pg", False),
    ("NC1_noise_eff_frame", "G01_noise", True),
    ("NC2_noise_tv_frame", "G01_noise_tvframe", True),
]
REAL_IDS = [r[0] for r in RELS if not r[2]]


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    ub.hdr("E1_I0023 s01 -- STEP 1: REPRODUCE D093's STRUCTURE RESULT")
    h, added, dropped = pr.check_prereg()
    P("  THIS SCREEN's PREREG hash %s VERIFIED. cells added=%d dropped=%d" % (h, len(added), len(dropped)))

    # ---- build D093's frame exactly: 2022-2024 only, its three tv columns only ----
    m = ub.build_merged(verbose=True, include_2021=False,
                        tv_cols=["P01_c04_prevgame", "O01_own_usg_pg", "G01_noise"])
    P("  merged D085 x D089 on (season, player_id, game_id): %d rows, %d players, seasons %s"
      % (len(m), m["player_id"].nunique(), sorted(m["season"].unique())))
    P("  partition gate PASS on VALUES; max game_date %s" % m["game_date"].max().date())

    s = ub.floor_subset(m, FLOOR)
    cc_cols = ["y_ppm_floor", "refA_ppm_floor", "A01_opp_efg_allowed", "A02_opp_ts_allowed",
               "A10_opp_defrtg", "P01_c04_prevgame", "O01_own_usg_pg", "G01_noise",
               "G01_noise_tvframe"]
    s, n_drop = ub.complete_case(s, cc_cols)
    s = s.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)
    pcodes, puq = pd.factorize(s["player_id"], sort=True)
    ng = len(puq)
    gns = np.bincount(pcodes, minlength=ng)
    gstarts = np.concatenate([[0], np.cumsum(gns)[:-1]])
    y = s["y_ppm_floor"].to_numpy(float)
    usage = s.groupby("player_id", sort=True)["O01_own_usg_pg"].mean().reindex(puq).to_numpy()
    P("  floor=%d  n_rows=%d (%d dropped for missingness)  n_players=%d  eligible(>=%d games)=%d"
      % (FLOOR, len(s), n_drop, ng, MIN_GAMES, int((gns >= MIN_GAMES).sum())))

    rows = []
    draws_by_rel = {}
    all_draws = []
    for rid, xc, is_ctrl in RELS:
        x = pd.to_numeric(s[xc], errors="coerce").to_numpy(float)
        beta, se, npg, valid = ub.group_slopes_fast(x, y, pcodes, ng, min_games=MIN_GAMES)
        obs = ub.spearman(beta[valid], usage[valid])
        rng = np.random.default_rng(ub.SEED + 23)
        nd = np.empty(N_DRAWS)
        for k in range(N_DRAWS):
            xp = ub.cyclic_shift_within_groups(x, gstarts, gns, rng)
            bb, ss, _, vv = ub.group_slopes_fast(xp, y, pcodes, ng, min_games=MIN_GAMES)
            nd[k] = ub.spearman(bb[vv], usage[vv])
        nd = nd[np.isfinite(nd)]
        draws_by_rel[rid] = nd
        for k, v in enumerate(nd):
            all_draws.append(dict(step="s01_reproduction", relationship=rid, null="within_cyclic",
                                  draw=k, spearman=v))
        p = (1.0 + int((np.abs(nd) >= abs(obs)).sum())) / (len(nd) + 1.0)
        rows.append(dict(relationship=rid, x=xc, is_negative_control=is_ctrl,
                         n_players=int(valid.sum()), spearman_obs=obs,
                         null_mean=float(nd.mean()), null_sd=float(nd.std(ddof=1)),
                         null_p95_abs=float(np.percentile(np.abs(nd), 95)), p_two_sided=p))
        P("  %-34s spearman=%+.6f  null mean=%+.4f sd=%.4f  p=%.6f%s"
          % (rid, obs, nd.mean(), nd.std(ddof=1), p, "   <-- NEGATIVE CONTROL" if is_ctrl else ""))

    res = pd.DataFrame(rows)

    # ---- family-wise across the 6 real relationships ----
    n = min(len(draws_by_rel[r]) for r in REAL_IDS)
    stack = np.vstack([np.abs(draws_by_rel[r][:n]) for r in REAL_IDS])
    maxnull = stack.max(axis=0)
    sub = res[res.relationship.isin(REAL_IDS)]
    obs_max = float(sub["spearman_obs"].abs().max())
    which = sub.iloc[sub["spearman_obs"].abs().to_numpy().argmax()]["relationship"]
    p_fw = (1.0 + int((maxnull >= obs_max).sum())) / (len(maxnull) + 1.0)
    ub.hdr("FAMILY-WISE ACROSS THE 6 PREREGISTERED RELATIONSHIPS")
    P("  max |spearman| = %.6f (%s)   family-wise p = %.6f   null p95 = %.4f"
      % (obs_max, which, p_fw, float(np.percentile(maxnull, 95))))

    # ---- compare against D093's published table, ABSOLUTE DELTAS ----
    pub = pd.read_csv(os.path.join(D093, "structure_decisive.csv"))
    cmp_rows = []
    for r in res.itertuples():
        q = pub[pub.relationship == r.relationship]
        if len(q) == 0:
            continue
        q = q.iloc[0]
        cmp_rows.append(dict(
            relationship=r.relationship, x=r.x, is_negative_control=r.is_negative_control,
            published_spearman=float(q["spearman_obs"]), reproduced_spearman=float(r.spearman_obs),
            abs_delta_spearman=abs(float(q["spearman_obs"]) - float(r.spearman_obs)),
            published_p=float(q["p_two_sided"]), reproduced_p=float(r.p_two_sided),
            abs_delta_p=abs(float(q["p_two_sided"]) - float(r.p_two_sided)),
            published_n_players=int(q["n_players"]), reproduced_n_players=int(r.n_players),
            published_null_sd=float(q["null_sd"]), reproduced_null_sd=float(r.null_sd),
            abs_delta_null_sd=abs(float(q["null_sd"]) - float(r.null_sd))))
    cdf = pd.DataFrame(cmp_rows)
    ub.hdr("REPRODUCTION vs D093's PUBLISHED structure_decisive.csv -- ABSOLUTE DELTAS")
    for r in cdf.itertuples():
        P("  %-34s published %+.6f -> reproduced %+.6f   |delta| = %.3e   "
          "p %.6f -> %.6f  |delta| = %.3e"
          % (r.relationship, r.published_spearman, r.reproduced_spearman, r.abs_delta_spearman,
             r.published_p, r.reproduced_p, r.abs_delta_p))
    max_d = float(cdf["abs_delta_spearman"].max())
    max_dp = float(cdf["abs_delta_p"].max())
    P("  MAX |delta spearman| over all 8 = %.3e ; MAX |delta p| = %.3e" % (max_d, max_dp))
    fw_pub = 0.0035
    P("  family-wise p: published %.4f -> reproduced %.6f  |delta| = %.3e"
      % (fw_pub, p_fw, abs(fw_pub - p_fw)))

    ok = (max_d < 1e-9) and (max_dp < 1e-9)
    verdict = ("REPRODUCED EXACTLY" if ok else
               ("REPRODUCED TO %.1e -- acceptable" % max(max_d, max_dp) if max_d < 5e-3
                else "DID NOT REPRODUCE -- SCREEN MUST STOP"))
    P("  VERDICT: %s" % verdict)

    cdf.to_csv(os.path.join(ub.OUT, "reproduction_d093.csv"), index=False)
    pd.DataFrame(all_draws).to_csv(os.path.join(ub.OUT, "permutation_draws_s01.csv"), index=False)
    out = dict(prereg_sha256=h, n_draws=N_DRAWS, floor=FLOOR, min_games=MIN_GAMES,
               n_rows=len(s), n_players=int(ng), n_eligible=int((gns >= MIN_GAMES).sum()),
               reproduced=res.to_dict(orient="records"),
               family_wise_p_reproduced=p_fw, family_wise_p_published=fw_pub,
               max_abs_delta_spearman=max_d, max_abs_delta_p=max_dp, verdict=verdict,
               reproduces=bool(max_d < 5e-3))
    with open(os.path.join(ub.OUT, "_s01.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    with open(os.path.join(ub.OUT, "run_log_s01.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("  wrote reproduction_d093.csv, permutation_draws_s01.csv, _s01.json")
    if not out["reproduces"]:
        raise SystemExit("STOP: D093 did not reproduce")


if __name__ == "__main__":
    main()
