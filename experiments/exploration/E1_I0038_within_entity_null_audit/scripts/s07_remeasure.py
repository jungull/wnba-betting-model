"""S07 -- what the exposed cells look like under a MATCHED null.

Two parts:
  A. THE FREE ANSWER.  For most exposed cells the correctly-matched BETWEEN-entity null was
     ALREADY RUN AND ALREADY RECORDED -- the screens computed both arms and then took
     max(p_within, p_between).  So the corrected verdict is a QUERY, exactly as D115 hoped.
  B. THE PAID ANSWER.  The 4 cells selected by the frozen triage rule are re-measured from the
     frame with an injection-verified matched null under the AMENDED D-04 protocol.

D101: identical response, row set, SST basis, base.  D087: coverage asserted.
No reference is rebuilt (no retrospective baseline).  MDE80 is INJECTION-VERIFIED only (D113).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab38 import (BEST_LIVE, BaseFit, DELTAS_D04, EXP, FLOOR_1CELL, FLOOR_132, NREP_D04, OUT,
                   R_DRAWS, SEED, amended_injection, assert_partition, hdr, mde80, null_draws,
                   perm_p, r2_twofit, resolve, var_share_between)

A = pd.read_csv(os.path.join(OUT, "AUDIT_TABLE.csv"))
E = A[A["EXPOSURE"] == "EXPOSED"].copy()

# ================================================================= A. the free answer
hdr("A. WAS THE EXPOSED CELL ACTUALLY KILLED *BY* THE WITHIN-ENTITY NULL?")
E["killed_by_the_within_null"] = E["p_decision"] >= 0.05
print(f"  exposed cells                                             : {len(E)}")
print(f"  ... where the within-entity null's own p >= 0.05 (it vetoed): "
      f"{int(E['killed_by_the_within_null'].sum())}")
print(f"  ... where the within-entity null gave p < 0.05 anyway       : "
      f"{int((~E['killed_by_the_within_null']).sum())}")
print("      (those were killed by family-wise multiplicity, not by the null's blindness)")
print("\n  by screen:")
print(pd.crosstab(E["screen"], E["killed_by_the_within_null"]).to_string())

hdr("A2. THE MATCHED NULL WAS ALREADY RUN AND ALREADY RECORDED -- READ IT OFF DISK")
rec = []
d16 = pd.read_csv(os.path.join(EXP, "E0_I0016_efficiency_predictors", "screen_results.csv"))
d18 = pd.read_csv(os.path.join(EXP, "E1_I0018_teammate_volume_channel", "screen_results.csv"))
d24 = pd.read_csv(os.path.join(EXP, "E0_I0024_reb_ast_characterisation",
                               "upstream_signals.csv"))
SRC = {"E0_I0016_efficiency_predictors": (d16, "p_N2_entity_swap", "p_familywise_N2",
                                          "null_mean_N2", "null_sd_N2"),
       "E1_I0018_teammate_volume_channel": (d18, "p_N2_entity_swap", "p_familywise_N2",
                                            "null_mean_N2", "null_sd_N2"),
       "E0_I0024_reb_ast_characterisation": (d24, "p_entity_swap", None, None,
                                             "null_sd_swap")}
A["_i"] = A.groupby("screen").cumcount()
E["_i"] = A.loc[E.index, "_i"]
for i, r in E.iterrows():
    src, pcol, fwcol, nmcol, sdcol = SRC[r["screen"]]
    row = src.iloc[int(r["_i"])]
    rec.append(dict(
        screen=r["screen"], candidate=r["candidate"], target=r["target"],
        stratum=r["stratum"], base=r["base"], n=r["n"], dr2=r["dr2_reported"],
        var_share_between=r["var_share_between"],
        p_WITHIN_null_used_for_the_kill=r["p_decision"],
        p_MATCHED_between_null_ALREADY_ON_DISK=float(row[pcol]),
        p_familywise_matched=float(row[fwcol]) if fwcol else np.nan,
        null_mean_within=r["null_mean"],
        null_mean_matched=float(row[nmcol]) if nmcol else np.nan,
        null_sd_matched=float(row[sdcol]) if sdcol else np.nan,
        killed_by_the_within_null=bool(r["killed_by_the_within_null"]),
        recorded_kill_reason=r["kill_reason"]))
MM = pd.DataFrame(rec)
MM["matched_null_clears_percell"] = MM["p_MATCHED_between_null_ALREADY_ON_DISK"] < 0.05
MM["matched_null_clears_familywise"] = MM["p_familywise_matched"] < 0.05
MM["VERDICT_FLIPS"] = MM["killed_by_the_within_null"] & MM["matched_null_clears_percell"]
print(f"  exposed cells whose MATCHED (between-entity) null p is already recorded: "
      f"{int(MM['p_MATCHED_between_null_ALREADY_ON_DISK'].notna().sum())} of {len(MM)}")
print(f"  ... matched null clears PER-CELL p<0.05     : "
      f"{int(MM['matched_null_clears_percell'].sum())}")
print(f"  ... matched null clears FAMILY-WISE p<0.05  : "
      f"{int(MM['matched_null_clears_familywise'].sum())} "
      f"(of {int(MM['p_familywise_matched'].notna().sum())} with a recorded family-wise p)")
print(f"  >>> CELLS WHERE THE WITHIN-ENTITY NULL VETOED A CELL THE MATCHED NULL CLEARS "
      f"PER-CELL: {int(MM['VERDICT_FLIPS'].sum())}")
print("\n  the flipping cells:")
fl = MM[MM["VERDICT_FLIPS"]].sort_values("dr2", ascending=False)
print(fl[["screen", "candidate", "target", "stratum", "base", "n", "dr2",
          "var_share_between", "p_WITHIN_null_used_for_the_kill",
          "p_MATCHED_between_null_ALREADY_ON_DISK", "p_familywise_matched"]].to_string(
              index=False) if len(fl) else "  (none)")
MM.to_csv(os.path.join(OUT, "MATCHED_NULL_RECHECK.csv"), index=False)
print("\n  wrote MATCHED_NULL_RECHECK.csv")

# ================================================================= B. the paid answer
hdr("B. FULL RE-MEASUREMENT OF THE PREREGISTERED TOP CELLS (frozen triage, PREREG 5.2/5.3)")
SEL = pd.read_csv(os.path.join(OUT, "REMEASUREMENT_CELLS.csv"))
print(SEL[["screen", "candidate", "target", "stratum", "base", "n", "dr2_reported"]].to_string(
    index=False))

BASE_COLS = {"B_SINGLE": ["ref_mean"],
             "B_COMPLETE": ["ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min",
                            "ref_mean_minutes", "ref_trail5_minutes", "ref_pct",
                            "ref_mean_pace", "n_prior", "is_home"]}
PERTARGET = ("ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min", "ref_pct")


def basecols_24(target, base):
    cols = [c + "__" + target if c in PERTARGET else c
            for c in BASE_COLS["B_SINGLE" if base == "B_SINGLE" else "B_COMPLETE"]]
    if base == "B_COMPLETE_PLUS_R10":
        cols.append("R10_opp_allowed_oreb_pg")
    return cols


F24 = pd.read_parquet(os.path.join(EXP, "E0_I0024_reb_ast_characterisation",
                                   "screen_frame.parquet"))
F24["game_date"] = pd.to_datetime(F24["game_date"])
assert_partition(F24, "E0_I0024")
F24 = F24[F24["season"].isin((2022, 2023, 2024))].reset_index(drop=True)
F16 = pd.read_parquet(os.path.join(EXP, "E0_I0016_efficiency_predictors",
                                   "screen_frame.parquet"))
F16["game_date"] = pd.to_datetime(F16["game_date"])
assert_partition(F16, "E0_I0016")
ENT16 = {"B03_pl_fouls_drawn_per36": ("player_season", ["player_id", "season"]),
         "E02_pl_paintpts_share": ("player_season", ["player_id", "season"])}

out, inj = [], []
for _, s in SEL.iterrows():
    hdr(f"RE-MEASURE  {s['screen']}  {s['candidate']} -> {s['target']}  "
        f"[{s['stratum']}|{s['base']}]")
    if s["screen"] == "E0_I0024_reb_ast_characterisation":
        bcols = basecols_24(s["target"], s["base"])
        nd = [s["target"]] + bcols + [s["candidate"]]
        sub = F24 if s["stratum"] == "POOLED" else F24[F24["DECISION"] == 1]
        sub = sub.dropna(subset=[c for c in nd if c in F24.columns]).reset_index(drop=True)
        bcols = resolve(sub, list(bcols), len(bcols), f"{s['base']}({s['target']})")
        entcols = ["player_id", "season"]
        entname = "player_season"
    else:
        cand = s["candidate"]
        entname, entcols = ENT16[cand]
        ycol, bcol = "y_" + s["target"], "refB_" + s["target"]
        m = (np.isfinite(pd.to_numeric(F16[cand], errors="coerce").to_numpy(float))
             & np.isfinite(F16[ycol].to_numpy(float))
             & np.isfinite(F16[bcol].to_numpy(float)))
        sub = F16.loc[m].reset_index(drop=True)
        bcols = resolve(sub, [bcol], 1, f"refB({s['target']})")
        s = s.copy(); s["target"] = ycol

    print(f"  rows = {len(sub)}   (recorded n = {s['n']})")
    if int(s["n"]) != len(sub):
        print("  *** ROW SET MISMATCH -- ANCHOR_FAILED, NOT RE-MEASURED (PREREG 5.3.1) ***")
        out.append(dict(screen=s["screen"], candidate=s["candidate"], target=s["target"],
                        stratum=s["stratum"], base=s["base"], status="ANCHOR_FAILED_ROWS",
                        n_recorded=s["n"], n_reproduced=len(sub)))
        continue
    for c in bcols:
        assert int(sub[c].notna().sum()) == len(sub), f"A_REF_COVERAGE FAILED {c}"
    print(f"  A_REF_COVERAGE ok: {len(bcols)} base cols cover all {len(sub)} rows (D087)")

    y = sub[s["target"]].to_numpy(float)
    Xb = sub[bcols].to_numpy(float)
    x = pd.to_numeric(sub[s["candidate"]], errors="coerce").to_numpy(float)
    bf = BaseFit(y, Xb)
    obs = bf.dr2(x)
    lit = r2_twofit(y, np.column_stack([Xb, x])) - r2_twofit(y, Xb)
    print(f"  dR2 reproduced = {obs:.10f}   recorded = {s['dr2_reported']:.10f}   "
          f"|diff| = {abs(obs - s['dr2_reported']):.3e}   (literal check {abs(obs-lit):.2e})")
    if abs(obs - s["dr2_reported"]) >= 5e-7:
        print("  *** ANCHOR FAILED -- NOT RE-MEASURED (PREREG 5.3.1) ***")
        out.append(dict(screen=s["screen"], candidate=s["candidate"], target=s["target"],
                        stratum=s["stratum"], base=s["base"], status="ANCHOR_FAILED_DR2",
                        dr2_recorded=s["dr2_reported"], dr2_reproduced=obs))
        continue

    g = (sub[entcols[0]].astype(str) + "_" + sub[entcols[1]].astype(str)).to_numpy()
    seas = sub["season"].to_numpy()
    gd = sub["game_date"].to_numpy()
    vsb = var_share_between(x, g)
    print(f"  var share BETWEEN {entname} = {vsb:.4f}  (recorded/computed {s['var_share_between']:.4f})")

    rr = np.random.default_rng(SEED + abs(hash(str(s["candidate"]) + str(s["target"]))) % 99991)
    Xp = null_draws("N_SWAP", x, rr, groups=g, order_key=gd, blocks=seas, R=R_DRAWS)
    EX = bf.resid_X(Xp)
    den = np.einsum("ij,ij->j", EX, EX)
    draws = ((bf.e @ EX) ** 2 / den) / bf.sst
    p = perm_p(obs, draws)
    print(f"  MATCHED NULL N_ESWAP: p = {p:.6f}   null_mean = {draws.mean():.4e}   "
          f"null_sd = {draws.std(ddof=1):.4e}   flag={draws.mean() > obs}")

    v, pw = amended_injection(bf, x, EX, g, np.random.default_rng(SEED + 101),
                              DELTAS_D04, NREP_D04)
    print(pw.pivot_table(index="delta", columns="planted_along", values="power").to_string())
    print(f"  AMENDED VERDICT ON THE MATCHED NULL = {v['AMENDED_VERDICT']}   "
          f"(dominant={v['dominant_component']}, power={v['power_dominant_at_best_live']:.2f}, "
          f"typeI={v['type_I_at_zero']:.2f})")
    mde = v["mde80_injection_verified_dominant"]
    print(f"  MDE80 (INJECTION-VERIFIED, dominant component) = {mde:.4e}   "
          f"observed/{'MDE80'} = {obs / mde if np.isfinite(mde) and mde > 0 else np.nan:.2f}x")
    print(f"  vs floors: single-cell {FLOOR_1CELL} -> {obs / FLOOR_1CELL:.2f}x   "
          f"132-cell {FLOOR_132} -> {obs / FLOOR_132:.2f}x")

    tag = f"{s['screen'][:9]}_{s['candidate']}_{s['target']}_{s['base']}"
    np.savez_compressed(os.path.join(OUT, "nulls", f"remeasure_{tag}.npz"),
                        N_ESWAP=draws, observed_dr2=np.array([obs]))
    out.append(dict(
        screen=s["screen"], candidate=s["candidate"], target=s["target"],
        stratum=s["stratum"], base=s["base"], status="REMEASURED",
        n=len(sub), dr2_recorded=s["dr2_reported"], dr2_reproduced=obs,
        var_share_between=vsb, entity=entname,
        p_recorded_within_null=s["p_decision"],
        p_matched_N_ESWAP=p, null_mean_matched=float(draws.mean()),
        null_sd_matched=float(draws.std(ddof=1)),
        flag_matched=bool(draws.mean() > obs),
        amended_verdict_on_matched_null=v["AMENDED_VERDICT"],
        dominant_component=v["dominant_component"], w_between=v["w_between"],
        power_dominant=v["power_dominant_at_best_live"], type_I=v["type_I_at_zero"],
        mde80_injection_verified=mde, mde80_kind="INJECTION_VERIFIED",
        obs_over_mde80=obs / mde if np.isfinite(mde) and mde > 0 else np.nan,
        obs_over_floor_1cell=obs / FLOOR_1CELL, obs_over_floor_132=obs / FLOOR_132,
        R_draws=R_DRAWS, min_attainable_p=1.0 / (R_DRAWS + 1)))
    inj += [dict(cell=tag, **r) for r in pw.to_dict("records")]

O = pd.DataFrame(out)
hdr("RE-MEASUREMENT SUMMARY")
print(O.to_string(index=False))
O.to_csv(os.path.join(OUT, "REMEASUREMENT_RESULTS.csv"), index=False)
pd.DataFrame(inj).to_csv(os.path.join(OUT, "REMEASUREMENT_INJECTION_POWER.csv"), index=False)
json.dump(dict(
    exposed=len(E),
    vetoed_by_within_null=int(E["killed_by_the_within_null"].sum()),
    matched_null_recorded=int(MM["p_MATCHED_between_null_ALREADY_ON_DISK"].notna().sum()),
    matched_clears_percell=int(MM["matched_null_clears_percell"].sum()),
    matched_clears_familywise=int(MM["matched_null_clears_familywise"].sum()),
    verdict_flips=int(MM["VERDICT_FLIPS"].sum()),
    remeasured=int((O["status"] == "REMEASURED").sum()) if len(O) else 0,
), open(os.path.join(OUT, "scripts", "_s07.json"), "w"), indent=1)
print("\nwrote REMEASUREMENT_RESULTS.csv, REMEASUREMENT_INJECTION_POWER.csv")
