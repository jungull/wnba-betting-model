"""S09 -- the one broken cell outside E0_I0014: E0_I0019 `pl_opps_prior|brier`.

Resolved WITHOUT a refit, from the screen's own draw archive, by the `E1_I0038` "the matched
null was already on disk" ruling.  E0_I0019 ran four schemes and stored all four; its DECISION
arm (`p_correct_level_WORST`) took `player_between`, a BETWEEN-player-season relabel, for a
candidate its own `grouping_levels.csv` records at var_share_between = 0.093425 -- i.e. 91% of
the candidate's variance is WITHIN player-season, the component a between-relabel cannot move.
"""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
D = os.path.join(EXPL, "E0_I0019_availability_forecast")

r = pd.read_csv(os.path.join(D, "screen_results.csv"))
cands = list(dict.fromkeys(r["candidate"].tolist()))
deps = list(dict.fromkeys(r["dependent"].tolist()))
print("candidates %d  dependents %d  cells %d" % (len(cands), len(deps), len(r)))
z = np.load(os.path.join(D, "permutation_nulls.npz"), allow_pickle=True)
assert z["null_player_between"].shape == (1000, len(cands), len(deps))

# ---- ANCHOR: reproduce every published sd and p from the stored draws (all 318 cells, 4 arms)
ARMS = [("player_between", "null_player_between", "sd_player_between", "p_player_between"),
        ("player_within",  "null_player_within",  "sd_player_within",  "p_player_within"),
        ("row",            "null_row",            "sd_row",            "p_row")]
mx_sd = 0.0; nbad_p = 0; nchk = 0
ri = r.set_index(["candidate", "dependent"])
for arm, key, sdc, pc in ARMS:
    A = z[key]
    for j, c in enumerate(cands):
        for k, dp in enumerate(deps):
            row = ri.loc[(c, dp)]
            dv = A[:, j, k]
            sd = float(dv.std(ddof=1))
            if np.isfinite(row[sdc]):
                mx_sd = max(mx_sd, abs(sd - row[sdc])); nchk += 1
                p = float((np.abs(dv) >= abs(row["t"])).mean())
                # E0_I0019 reports p as (count+1)/(R+1); check both conventions
                p2 = float((np.sum(np.abs(dv) >= abs(row["t"])) + 1) / (len(dv) + 1))
                if not (np.isclose(p, row[pc], atol=1e-12) or np.isclose(p2, row[pc], atol=1e-12)):
                    nbad_p += 1
print("ANCHOR C1  max|sd_recomputed - published| over %d arm-cells = %.3e" % (nchk, mx_sd))
print("ANCHOR C2  p mismatches (either convention) = %d of %d" % (nbad_p, nchk))
print("           E0_I0019 stores SIGNED draws: min over all arms = %.6f"
      % min(float(z[k].min()) for _, k, _, _ in ARMS))

j = cands.index("pl_opps_prior"); k = deps.index("brier")
obs = float(ri.loc[("pl_opps_prior", "brier"), "t"])
print("\n=== E0_I0019 pl_opps_prior|brier, observed t = %.6f, n = 17809 ===" % obs)
gl = pd.read_csv(os.path.join(D, "grouping_levels.csv")).set_index("candidate")
vsb = float(gl.loc["pl_opps_prior", "var_share_between_primary_block"])
print("candidate var_share_between (player-season), RECORDED by the screen: %.6f" % vsb)
out = []
for arm, key, sdc, pc in ARMS:
    dv = z[key][:, j, k]
    a = np.abs(dv)
    out.append(dict(arm=arm, null_mean_signed_t=float(dv.mean()),
                    null_sd_signed_t=float(dv.std(ddof=1)),
                    null_mean_abs_t=float(a.mean()), null_sd_abs_t=float(a.std(ddof=1)),
                    degeneracy_ratio=float(a.mean() / a.std(ddof=1)),
                    p_two_sided=float((a >= abs(obs)).mean()),
                    published_sd=float(ri.loc[("pl_opps_prior", "brier"), sdc]),
                    published_p=float(ri.loc[("pl_opps_prior", "brier"), pc]),
                    n_unique=int(len(np.unique(dv)))))
O = pd.DataFrame(out)
print(O.to_string(index=False))
O.to_csv(os.path.join(HERE, "_E0_I0019_ARMS.csv"), index=False)

# floors on each arm, E1_I0041's validated form, per-cell bar from the arm's own draws
Z80 = 0.8416212335729143
n = 17809
for _, row in O.iterrows():
    dv = z[dict(player_between="null_player_between", player_within="null_player_within",
                row="null_row")[row["arm"]]][:, j, k]
    bar = float(np.percentile(np.abs(dv), 97.5))
    mde = (bar + Z80 * row["null_sd_signed_t"]) ** 2 / n
    print("  %-16s bar_abs=%.4f  sd=%.4f  MDE80_percell=%.6f  vs 0.0023 -> %s"
          % (row["arm"], bar, row["null_sd_signed_t"], mde,
             "BLIND" if mde > 0.0023 else "ADEQUATE"))
print("\nDONE s09")
