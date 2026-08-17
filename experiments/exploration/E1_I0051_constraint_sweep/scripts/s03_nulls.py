"""E1_I0051 -- s03.  Matched nulls, family-wise correction, the null-centre check, and the
blind-null demonstration re-run on THIS screen's own cells.

Every verdict requires BOTH N_TGSWAP and N_PSWAP.  A5_opp_defrtg uses N_TGBLOCK and is ALSO run
under N_TGSWAP deliberately, as a control that cannot fail (the swap is the literal identity for a
team-game-constant column).
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_base as B  # noqa: E402

pd.set_option("display.width", 240)

d = pd.read_parquet(os.path.join(B.SCR, "_frame.parquet"))
B.assert_partition(d, "FRAME_reload", True)
dm = B.decision_mask(d)
season = d["season"].to_numpy()
B_live = d["B_live"].to_numpy(float)
B_rules = d["B_rules"].to_numpy(float)
T_real = d["T_min"].to_numpy(float)

CHOSEN = {("M_level_min", 2023): (3, 1.0), ("M_level_min", 2024): (3, 1.0),
          ("M_level_min", 2022): (2, 2.0),
          ("S_share_min", 2023): (3, 1.0), ("S_share_min", 2024): (3, 1.0),
          ("S_share_min", 2022): (2, 1.0)}

N_TGSWAP = B.WithinTeamGameSwap(d)
N_PSWAP = B.PlayerSeriesSwap(d)
N_TGBLOCK = B.WithinDateTeamGameSwap(d)
N_BLIND = B.WithinPlayerCyclic(d)
print("  N_TGSWAP  blocks %d groups %d" % (N_TGSWAP.n_blocks, N_TGSWAP.n_groups))
print("  N_PSWAP   blocks %d groups %d" % (N_PSWAP.n_blocks, N_PSWAP.n_groups))
print("  N_TGBLOCK blocks %d groups %d" % (N_TGBLOCK.n_blocks, N_TGBLOCK.n_groups))
print("  N_BLIND   blocks %d groups %d  (CONTRAST ONLY -- never a verdict)"
      % (N_BLIND.n_blocks, N_BLIND.n_groups))


def make_cell(resp, cand, arm, proj, ev_set, mask):
    base = np.zeros(len(d))
    for ev in ev_set:
        h, k = CHOSEN[(resp, ev)]
        f = B.allocator_raw(d, resp, h, k)
        base = np.where((season == ev) | (season < ev), f, base)
    is_lvl = (resp == "M_level_min")
    return B.Cell(d, d[resp].to_numpy(float), base, cand, d[cand].to_numpy(float),
                  mask, mask, ev_set, arm, proj, B_rules,
                  B_live if is_lvl else np.ones(len(d)),
                  T_real if is_lvl else np.ones(len(d)))


B.hdr("TIMING PROBE")
t0 = time.time()
c = make_cell("M_level_min", "A4_vac_x_own", "UNFROZEN", "PROJ_BUDGET", B.CLEAN_EVAL_SEASONS, dm)
rng = np.random.default_rng(1)
for _ in range(20):
    c.dr2(N_TGSWAP.draw(c.cand, rng))
per = (time.time() - t0) / 20.0
print("  %.4f s per draw  ->  2000 draws = %.1f s per cell" % (per, per * 2000))

# =============================================================================================
DRAWS_MAIN = 2000
DRAWS_PSWAP = 600
RESP = "M_level_min"
PROJS = ["RAW", "PROJ_BUDGET"]
ARMS = ["FROZEN", "UNFROZEN"]

B.hdr("PRIMARY NULLS -- %s | DECISION | CLEAN_2023_24 | SST on scored rows | no weighting" % RESP)
rows = []
fam_draws = {}          # (arm, proj) -> dict cand -> draws, from ONE SHARED STREAM (D120)

for proj in PROJS:
    for arm in ARMS:
        # ---- shared draw stream for the five between-player candidates ----------------------
        cells = {c: make_cell(RESP, c, arm, proj, B.CLEAN_EVAL_SEASONS, dm)
                 for c in B.BETWEEN_PLAYER_CANDIDATES}
        obs = {c: float(cells[c].dr2()) for c in B.BETWEEN_PLAYER_CANDIDATES}
        rng = np.random.default_rng(B.SEED)
        dr = {c: np.empty(DRAWS_MAIN) for c in B.BETWEEN_PLAYER_CANDIDATES}
        t0 = time.time()
        for i in range(DRAWS_MAIN):
            keys = rng.random(N_TGSWAP.n)
            perm = np.lexsort((keys, N_TGSWAP.codes))
            for c in B.BETWEEN_PLAYER_CANDIDATES:
                x = cells[c].cand
                out = np.empty_like(x)
                out[N_TGSWAP.order] = x[perm]
                dr[c][i] = cells[c].dr2(out)
        print("  [%s/%s] N_TGSWAP %d draws in %.1f s" % (proj, arm, DRAWS_MAIN, time.time() - t0))
        fam_draws[(arm, proj)] = dict(obs=obs, draws=dr)
        for c in B.BETWEEN_PLAYER_CANDIDATES:
            dd = dr[c]
            mean, sd = float(dd.mean()), float(dd.std(ddof=1))
            res = dict(label="%s|%s|%s|%s|N_TGSWAP" % (RESP, c, arm, proj), real=obs[c],
                       draws=dd, n_draws=DRAWS_MAIN, null_mean=mean, null_sd=sd,
                       z=(obs[c] - mean) / sd if sd > 0 else np.nan,
                       p=float((1.0 + int((dd >= obs[c]).sum())) / (len(dd) + 1.0)),
                       n_groups=N_TGSWAP.n_groups, n_blocks=N_TGSWAP.n_blocks)
            B.save_null("%s__DECISION__%s__%s__%s__N_TGSWAP" % (RESP, arm, proj, c), res)
            rows.append(dict(response=RESP, row_set="DECISION x CLEAN_2023_24", candidate=c,
                             arm=arm, projection=proj, null="N_TGSWAP", n_draws=DRAWS_MAIN,
                             observed=obs[c], null_mean=mean, null_sd=sd, z=res["z"], p=res["p"],
                             n_blocks=N_TGSWAP.n_blocks,
                             mde80_analytic=2.80 * sd,
                             null_centre_flag=("NULL MEAN FURTHER FROM 0 THAN OBSERVED"
                                               if abs(mean) > abs(obs[c]) else "")))
        # ---- N_PSWAP -----------------------------------------------------------------------
        for c in B.BETWEEN_PLAYER_CANDIDATES:
            r = B.run_null(cells[c], N_PSWAP, n_draws=DRAWS_PSWAP, seed=B.SEED,
                           label="%s|%s|%s|%s|N_PSWAP" % (RESP, c, arm, proj))
            B.save_null("%s__DECISION__%s__%s__%s__N_PSWAP" % (RESP, arm, proj, c), r)
            rows.append(dict(response=RESP, row_set="DECISION x CLEAN_2023_24", candidate=c,
                             arm=arm, projection=proj, null="N_PSWAP", n_draws=DRAWS_PSWAP,
                             observed=r["real"], null_mean=r["null_mean"], null_sd=r["null_sd"],
                             z=r["z"], p=r["p"], n_blocks=r["n_blocks"],
                             mde80_analytic=2.80 * r["null_sd"],
                             null_centre_flag=("NULL MEAN FURTHER FROM 0 THAN OBSERVED"
                                               if abs(r["null_mean"]) > abs(r["real"]) else "")))
        # ---- A5: N_TGBLOCK (correct) AND N_TGSWAP (the identity -- control that cannot fail)
        c5 = make_cell(RESP, "A5_opp_defrtg", arm, proj, B.CLEAN_EVAL_SEASONS, dm)
        for nm, sw, nd in (("N_TGBLOCK", N_TGBLOCK, DRAWS_MAIN),
                           ("N_TGSWAP_VACUOUS_CONTROL", N_TGSWAP, 400)):
            r = B.run_null(c5, sw, n_draws=nd, seed=B.SEED,
                           label="%s|A5_opp_defrtg|%s|%s|%s" % (RESP, arm, proj, nm))
            B.save_null("%s__DECISION__%s__%s__A5_opp_defrtg__%s" % (RESP, arm, proj, nm), r)
            rows.append(dict(response=RESP, row_set="DECISION x CLEAN_2023_24",
                             candidate="A5_opp_defrtg", arm=arm, projection=proj, null=nm,
                             n_draws=nd, observed=r["real"], null_mean=r["null_mean"],
                             null_sd=r["null_sd"], z=r["z"], p=r["p"], n_blocks=r["n_blocks"],
                             mde80_analytic=2.80 * r["null_sd"], null_centre_flag=""))
            print("    A5 %-26s %s/%s  obs %+.6f  null sd %.3e  z %+.2f  p %.4f"
                  % (nm, arm, proj, r["real"], r["null_sd"], r["z"], r["p"]))

nl = pd.DataFrame(rows)
nl.to_csv(os.path.join(B.OUT, "NULLS.csv"), index=False)

B.hdr("NULLS -- N_TGSWAP, the primary null")
show = nl[nl["null"] == "N_TGSWAP"].pivot_table(
    index=["candidate", "arm"], columns="projection",
    values=["observed", "z", "p"])
print(show.to_string(float_format=lambda x: "%+.6f" % x))

# =============================================================================================
B.hdr("FAMILY-WISE -- max-z over the five between-player candidates, ONE SHARED DRAW STREAM")
fw = []
for (arm, proj), pack in fam_draws.items():
    obs, dr = pack["obs"], pack["draws"]
    zs = {}
    for c in B.BETWEEN_PLAYER_CANDIDATES:
        m, s = dr[c].mean(), dr[c].std(ddof=1)
        zs[c] = (obs[c] - m) / s if s > 0 else np.nan
    Z = np.column_stack([(dr[c] - dr[c].mean()) / dr[c].std(ddof=1)
                         for c in B.BETWEEN_PLAYER_CANDIDATES])
    maxz_null = Z.max(axis=1)
    for c in B.BETWEEN_PLAYER_CANDIDATES:
        p_fw = float((1.0 + int((maxz_null >= zs[c]).sum())) / (len(maxz_null) + 1.0))
        fw.append(dict(response=RESP, row_set="DECISION x CLEAN_2023_24", candidate=c, arm=arm,
                       projection=proj, z=zs[c], p_familywise=p_fw,
                       n_family=len(B.BETWEEN_PLAYER_CANDIDATES), n_draws=DRAWS_MAIN))
    np.savez(os.path.join(B.NULLS, "FAMILYWISE__%s__%s__%s.npz" % (RESP, arm, proj)),
             draws_raw_unstandardised=np.column_stack(
                 [dr[c] for c in B.BETWEEN_PLAYER_CANDIDATES]),
             maxz_null=maxz_null,
             observed_signed=np.array([obs[c] for c in B.BETWEEN_PLAYER_CANDIDATES]),
             candidates=np.array(B.BETWEEN_PLAYER_CANDIDATES))
fw = pd.DataFrame(fw)
fw.to_csv(os.path.join(B.OUT, "FAMILYWISE.csv"), index=False)
print(fw.pivot_table(index=["candidate", "arm"], columns="projection",
                     values="p_familywise").to_string(float_format=lambda x: "%.4f" % x))

# =============================================================================================
B.hdr("BLIND-NULL DEMONSTRATION -- re-run on THIS screen's own cells, not cited")
bd = []
for c in ("A1_pts_share_prior", "A4_vac_x_own"):
    for arm in ("FROZEN", "UNFROZEN"):
        cell = make_cell(RESP, c, arm, "PROJ_BUDGET", B.CLEAN_EVAL_SEASONS, dm)
        for nm, sw in (("N_TGSWAP_CORRECT", N_TGSWAP), ("N_WITHIN_PLAYER_BLIND", N_BLIND)):
            r = B.run_null(cell, sw, n_draws=400, seed=B.SEED,
                           label="BLINDDEMO|%s|%s|%s" % (c, arm, nm))
            B.save_null("BLINDDEMO__%s__%s__%s__%s" % (RESP, c, arm, nm), r)
            bd.append(dict(response=RESP, candidate=c, arm=arm, projection="PROJ_BUDGET",
                           null=nm, observed=r["real"], null_mean=r["null_mean"],
                           null_sd=r["null_sd"], z=r["z"], p=r["p"], n_draws=400,
                           verdict_valid=("YES" if nm == "N_TGSWAP_CORRECT" else
                                          "NO -- CONTRAST ONLY")))
            print("  %-20s %-8s %-24s obs %+.6f  null mean %+.6f  z %+7.2f  p %.4f  %s"
                  % (c, arm, nm, r["real"], r["null_mean"], r["z"], r["p"],
                     "" if nm == "N_TGSWAP_CORRECT" else "<-- INVALID, contrast only"))
pd.DataFrame(bd).to_csv(os.path.join(B.OUT, "BLIND_NULL_DEMO.csv"), index=False)

B.dump("s03", dict(prereg_sha=B.prereg_sha(), n_null_rows=len(nl)))
print("\nwrote NULLS.csv FAMILYWISE.csv BLIND_NULL_DEMO.csv and nulls/*.npz")
B.hdr("DONE s03")
