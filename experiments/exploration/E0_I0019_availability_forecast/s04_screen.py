"""E0_I0019 -- s04: THE CONDITIONAL-EDGE SCREEN.  Where is `p_active` systematically wrong?

318 cells (53 pre-registered candidates x 6 dependents).  Correct-level permutation nulls with a
SHARED index per draw so the whole-screen max-|t| family-wise correction is valid; the naive
row-level null is run alongside ONLY to publish the inflation factor.
"""
import json
import os

import numpy as np
import pandas as pd

import av_base as B
import screenkit as sk

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 140)
OUT = B.OUT
N_DRAWS = 1000
SEED = 190019

F = pd.read_parquet(os.path.join(OUT, "analysis_frame.parquet"))
B.guard(F, "analysis frame reload")
CJ = json.load(open(os.path.join(OUT, "candidates.json")))
CANDS = CJ["candidates"]
FAMOF = {c: fam for fam, cs in CJ["families"].items() for c in cs}
print("  candidate hash = %s   (%d candidates, %d cells)"
      % (CJ["candidate_hash"], len(CANDS), CJ["n_cells"]))

y = F["y"].to_numpy(float)
p = F["v15__pred_point"].to_numpy(float)
R1 = F["R1"].to_numpy(float)
R2 = F["R2"].to_numpy(float)
R3 = F["R3"].to_numpy(float)
seas = F["season"].to_numpy()


def _ll(yv, pv):
    pv = np.clip(pv, B.EPS, 1 - B.EPS)
    return -(yv * np.log(pv) + (1 - yv) * np.log(1 - pv))


DEP = {
    "signed_err": y - p,
    "brier": (y - p) ** 2,
    "skill_vs_R1": (y - R1) ** 2 - (y - p) ** 2,
    "skill_vs_R2": (y - R2) ** 2 - (y - p) ** 2,
    "skill_vs_R3": (y - R3) ** 2 - (y - p) ** 2,
    "llskill_vs_R3": _ll(y, R3) - _ll(y, p),
}
DEPNAMES = list(DEP.keys())
YTIL = {k: B.demean_within(v, seas) for k, v in DEP.items()}   # season FE, applied identically
print("  dependents built.  season-demeaning is applied ONCE, to the dependent only, and is")
print("  identical for the model, every reference and every permutation draw (see TIME-WINDOW).")

# ---------------------------------------------------------------------- grouping levels
B.hdr("s04A -- GROUPING LEVEL PER CANDIDATE (screenkit.detect_grouping_level)")
KEYS = {
    "team_game": ["season", "team_id", "game_id"],
    "team_season": ["season", "team_id"],
    "player_season": ["season", "player_id"],
    "game": ["game_id"],
}
lvl_rows = []
for c in CANDS:
    r = sk.detect_grouping_level(F, c, candidate_keys=KEYS, verbose=False)
    lvl_rows.append(dict(candidate=c, family=FAMOF[c], status=r.get("status"),
                         recommended=r.get("recommended_permutation_level"),
                         row_null_anticonservative=r.get("row_null_is_anticonservative")))
LV = pd.DataFrame(lvl_rows)
print(LV.groupby(["family", "recommended"], dropna=False).size().to_string())
LV.to_csv(os.path.join(OUT, "grouping_levels.csv"), index=False)

# scheme assignment, DECLARED BY FAMILY before the run and cross-checked against the kit above
PLAYER_BLK = B.make_blocks(F, ["player_id"])          # blocks are (season, player_id)
TG_BLK = B.make_blocks(F, ["team_id", "game_id"])     # blocks are (season, team_id, game_id)
TS_BLK = B.make_blocks(F, ["team_id"])                # blocks are (season, team_id)
print("  blocks: player-season=%d  team-game=%d  team-season=%d"
      % (sum(len(v) for v in PLAYER_BLK.values()), sum(len(v) for v in TG_BLK.values()),
         sum(len(v) for v in TS_BLK.values())))

SCHEME = {}
for c in CANDS:
    fam = FAMOF[c]
    if fam in ("E_roster_churn", "F_schedule", "G_season_phase_contention"):
        SCHEME[c] = ("teamgame_between", "teamseason_between")
    else:
        SCHEME[c] = ("player_between", "player_within")
vsb = {}
for c in CANDS:
    v = pd.to_numeric(F[c], errors="coerce").to_numpy(float)
    blocks = TG_BLK if SCHEME[c][0].startswith("teamgame") else PLAYER_BLK
    vsb[c] = B.var_share_between(v, blocks)
LV["var_share_between_primary_block"] = LV["candidate"].map(vsb)
LV["scheme_primary"] = LV["candidate"].map(lambda c: SCHEME[c][0])
LV["scheme_secondary"] = LV["candidate"].map(lambda c: SCHEME[c][1])
# a feature that is CONSTANT within its block makes the WITHIN scheme the literal identity
LV["secondary_is_identity"] = LV["var_share_between_primary_block"] > 0.999
n_ident = int(LV["secondary_is_identity"].sum())
print("  candidates whose secondary (within) scheme would be the identity: %d (skipped there)"
      % n_ident)
LV.to_csv(os.path.join(OUT, "grouping_levels.csv"), index=False)

# ---------------------------------------------------------------------- observed statistics
B.hdr("s04B -- OBSERVED STATISTICS (318 cells)")
XV = {c: pd.to_numeric(F[c], errors="coerce").to_numpy(float) for c in CANDS}


def cell_t(x, ytil):
    xt = B.demean_within(x, seas)
    ok = np.isfinite(xt) & np.isfinite(ytil)
    n = int(ok.sum())
    if n < 50:
        return np.nan, np.nan, 0
    xt2 = np.where(ok, xt, 0.0)
    yt2 = np.where(ok, ytil, 0.0)
    sxx = float(xt2 @ xt2)
    if sxx <= 0:
        return np.nan, np.nan, n
    sxy = float(xt2 @ yt2)
    beta = sxy / sxx
    sse = float(yt2 @ yt2) - beta * sxy
    df = n - 4
    se = np.sqrt(max(sse, 0.0) / df / sxx)
    return (beta, beta / se if se > 0 else np.nan, n)


obs = []
for c in CANDS:
    for dname in DEPNAMES:
        b, t, n = cell_t(XV[c], YTIL[dname])
        obs.append(dict(candidate=c, family=FAMOF[c], dependent=dname, beta=b, t=t, n=n))
OBS = pd.DataFrame(obs)
print("  observed max |t| over all %d cells = %.5f  (%s / %s)"
      % (len(OBS), OBS["t"].abs().max(),
         OBS.loc[OBS["t"].abs().idxmax(), "candidate"],
         OBS.loc[OBS["t"].abs().idxmax(), "dependent"]))
print(OBS.reindex(OBS["t"].abs().sort_values(ascending=False).index).head(20)
      .to_string(index=False, float_format=lambda v: "%.4f" % v))

# ---------------------------------------------------------------------- permutation nulls
B.hdr("s04C -- PERMUTATION NULLS (%d draws, shared index per draw, three schemes)" % N_DRAWS)
schemes = ["player_between", "player_within", "teamgame_between", "teamseason_between", "row"]
null_t = {s: np.full((N_DRAWS, len(CANDS), len(DEPNAMES)), np.nan) for s in schemes}
maxt_primary = np.full(N_DRAWS, np.nan)
maxt_row = np.full(N_DRAWS, np.nan)
rng = np.random.default_rng(SEED)
n = len(F)
for d in range(N_DRAWS):
    idx = {
        "player_between": B.block_index(PLAYER_BLK, n, rng),
        "player_within": B.within_block_index(PLAYER_BLK, n, rng),
        "teamgame_between": B.block_index(TG_BLK, n, rng),
        "teamseason_between": B.block_index(TS_BLK, n, rng),
        "row": B.row_index(seas, rng),
    }
    mx_p, mx_r = 0.0, 0.0
    for ci, c in enumerate(CANDS):
        prim, sec = SCHEME[c]
        used = [prim, "row"] + ([sec] if not bool(LV.loc[LV["candidate"] == c,
                                                        "secondary_is_identity"].iloc[0]) else [])
        for s in set(used):
            xp = XV[c][idx[s]]
            xt = B.demean_within(xp, seas)
            for di, dname in enumerate(DEPNAMES):
                ytil = YTIL[dname]
                ok = np.isfinite(xt) & np.isfinite(ytil)
                nn = int(ok.sum())
                if nn < 50:
                    continue
                xt2 = np.where(ok, xt, 0.0)
                yt2 = np.where(ok, ytil, 0.0)
                sxx = float(xt2 @ xt2)
                if sxx <= 0:
                    continue
                sxy = float(xt2 @ yt2)
                beta = sxy / sxx
                sse = float(yt2 @ yt2) - beta * sxy
                se = np.sqrt(max(sse, 0.0) / (nn - 4) / sxx)
                tt = beta / se if se > 0 else np.nan
                null_t[s][d, ci, di] = tt
                if np.isfinite(tt):
                    if s == prim:
                        mx_p = max(mx_p, abs(tt))
                    if s == "row":
                        mx_r = max(mx_r, abs(tt))
    maxt_primary[d] = mx_p
    maxt_row[d] = mx_r
    if (d + 1) % 100 == 0:
        print("    draw %4d/%d   running max|t| primary=%.3f  row=%.3f"
              % (d + 1, N_DRAWS, np.nanmax(maxt_primary[:d + 1]), np.nanmax(maxt_row[:d + 1])))

np.savez_compressed(os.path.join(OUT, "permutation_nulls.npz"),
                    maxt_primary=maxt_primary, maxt_row=maxt_row,
                    **{("null_%s" % s): null_t[s] for s in schemes})
pd.DataFrame(dict(draw=np.arange(N_DRAWS), maxt_correct_level=maxt_primary,
                  maxt_row_NAIVE=maxt_row)).to_csv(
    os.path.join(OUT, "maxt_null_draws.csv"), index=False)
print("  correct-level max|t| null: mean=%.4f  median=%.4f  max=%.4f  q95=%.4f"
      % (maxt_primary.mean(), np.median(maxt_primary), maxt_primary.max(),
         np.quantile(maxt_primary, 0.95)))
print("  NAIVE row-level max|t| null: mean=%.4f  median=%.4f  max=%.4f  q95=%.4f"
      % (maxt_row.mean(), np.median(maxt_row), maxt_row.max(), np.quantile(maxt_row, 0.95)))
print("  -> if the naive null had been used, the family-wise bar would have been %.4f instead"
      " of %.4f" % (np.quantile(maxt_row, 0.95), np.quantile(maxt_primary, 0.95)))

# ---------------------------------------------------------------------- p-values
B.hdr("s04D -- P-VALUES: per-cell (both schemes) and FAMILY-WISE (whole-screen max-t)")
rows = []
for ci, c in enumerate(CANDS):
    prim, sec = SCHEME[c]
    ident = bool(LV.loc[LV["candidate"] == c, "secondary_is_identity"].iloc[0])
    for di, dname in enumerate(DEPNAMES):
        o = OBS[(OBS["candidate"] == c) & (OBS["dependent"] == dname)].iloc[0]
        t = o["t"]
        rec = dict(candidate=c, family=FAMOF[c], dependent=dname, beta=o["beta"], t=t, n=o["n"])
        for s in [prim] + ([sec] if not ident else []) + ["row"]:
            dr = null_t[s][:, ci, di]
            dr = dr[np.isfinite(dr)]
            if len(dr) == 0 or not np.isfinite(t):
                rec["p_" + s] = np.nan
                rec["sd_" + s] = np.nan
                continue
            rec["p_" + s] = float((1 + (np.abs(dr) >= abs(t)).sum()) / (1 + len(dr)))
            rec["sd_" + s] = float(np.std(dr))
        ps = [rec.get("p_" + s) for s in [prim] + ([sec] if not ident else [])]
        ps = [v for v in ps if v is not None and np.isfinite(v)]
        rec["p_correct_level_WORST"] = max(ps) if ps else np.nan
        rec["p_row_NAIVE"] = rec.get("p_row", np.nan)
        rec["inflation_sd_correct_over_row"] = (
            rec.get("sd_" + prim, np.nan) / rec.get("sd_row", np.nan)
            if rec.get("sd_row") else np.nan)
        rec["p_familywise"] = (float((1 + (maxt_primary >= abs(t)).sum()) / (1 + N_DRAWS))
                               if np.isfinite(t) else np.nan)
        rows.append(rec)
RES = pd.DataFrame(rows)
RES.to_csv(os.path.join(OUT, "screen_results.csv"), index=False)

infl = RES["inflation_sd_correct_over_row"].replace([np.inf, -np.inf], np.nan).dropna()
print("  per-cell sd inflation (correct / row): median=%.3fx  range %.3f-%.3f"
      % (infl.median(), infl.min(), infl.max()))
print("\n  ATTRITION")
n_all = len(RES)
n_p05 = int((RES["p_correct_level_WORST"] < 0.05).sum())
n_fw = int((RES["p_familywise"] < 0.05).sum())
n_fw_c = RES.loc[RES["p_familywise"] < 0.05, "candidate"].nunique()
n_p05_row = int((RES["p_row_NAIVE"] < 0.05).sum())
print("    cells screened                                 : %d" % n_all)
print("    clearing p<0.05 at the NAIVE ROW level         : %d" % n_p05_row)
print("    clearing p<0.05 at the CORRECT level (worst of : %d" % n_p05)
print("      the two schemes)")
print("    clearing FAMILY-WISE p<0.05 (whole-screen max-t): %d  across %d candidates"
      % (n_fw, n_fw_c))
skill_dep = ["skill_vs_R1", "skill_vs_R2", "skill_vs_R3", "llskill_vs_R3"]
n_fw_skill = int(((RES["p_familywise"] < 0.05) & (RES["dependent"].isin(skill_dep))).sum())
n_fw_skill_r3 = int(((RES["p_familywise"] < 0.05) &
                     (RES["dependent"].isin(["skill_vs_R3", "llskill_vs_R3"]))).sum())
print("    of those, on a DIFFERENTIAL-SKILL dependent     : %d" % n_fw_skill)
print("    of those, against the RICH reference R3         : %d" % n_fw_skill_r3)

print("\n  NEGATIVE CONTROLS (must not survive):")
print(RES[RES["family"] == "Z_negative_control"][
    ["candidate", "dependent", "t", "p_correct_level_WORST", "p_row_NAIVE", "p_familywise"]]
    .to_string(index=False, float_format=lambda v: "%.4f" % v))

print("\n  FAMILY-WISE SURVIVORS:")
sv = RES[RES["p_familywise"] < 0.05].sort_values("t", key=lambda s: s.abs(), ascending=False)
print(sv[["candidate", "family", "dependent", "t", "n", "p_correct_level_WORST",
          "p_row_NAIVE", "p_familywise"]].to_string(index=False,
                                                    float_format=lambda v: "%.4f" % v))

fam_tab = (RES.assign(fw=(RES["p_familywise"] < 0.05).astype(int))
           .groupby("family").agg(cells=("t", "size"), max_abs_t=("t", lambda s: s.abs().max()),
                                  n_familywise=("fw", "sum")))
print("\n  BY FAMILY:")
print(fam_tab.to_string())
fam_tab.to_csv(os.path.join(OUT, "family_summary.csv"))

# ---------------------------------------------------------------------- noop placebo
B.hdr("s04E -- NO-OP PLACEBO (screenkit.noop_placebo) + observed sds")


def stat_fn(frame):
    x = pd.to_numeric(frame["pl_consec_absences"], errors="coerce").to_numpy(float)
    _, t, _ = cell_t(x, YTIL["skill_vs_R3"])
    return t


ph = sk.noop_placebo(stat_fn, F, n_draws=200)
print("  noop_placebo: %s" % {k: v for k, v in ph.items() if k != "draws"})
json.dump({k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
           for k, v in ph.items() if k != "draws"},
          open(os.path.join(OUT, "noop_placebo.json"), "w"), indent=2)

sd_tab = []
for s in schemes:
    a = null_t[s].reshape(N_DRAWS, -1)
    a = a[:, np.isfinite(a).all(axis=0)] if a.size else a
    sd_tab.append(dict(scheme=s, n_cells_with_draws=a.shape[1] if a.size else 0,
                       median_cell_sd=float(np.median(np.std(a, axis=0))) if a.size else np.nan))
print("  observed null sds by scheme:")
print(pd.DataFrame(sd_tab).to_string(index=False))
pd.DataFrame(sd_tab).to_csv(os.path.join(OUT, "null_sds_by_scheme.csv"), index=False)

json.dump(dict(candidate_hash=CJ["candidate_hash"], n_cells=n_all, n_draws=N_DRAWS,
               observed_max_abs_t=float(OBS["t"].abs().max()),
               maxt_correct_mean=float(maxt_primary.mean()),
               maxt_correct_max=float(maxt_primary.max()),
               maxt_correct_q95=float(np.quantile(maxt_primary, 0.95)),
               maxt_row_mean=float(maxt_row.mean()), maxt_row_max=float(maxt_row.max()),
               maxt_row_q95=float(np.quantile(maxt_row, 0.95)),
               attrition=dict(cells=n_all, p05_row_naive=n_p05_row, p05_correct=n_p05,
                              familywise=n_fw, familywise_candidates=int(n_fw_c),
                              familywise_on_skill=n_fw_skill,
                              familywise_on_skill_vs_R3=n_fw_skill_r3),
               per_cell_inflation_median=float(infl.median()),
               noop_placebo={k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                             for k, v in ph.items() if k != "draws"}),
          open(os.path.join(OUT, "s04_screen.json"), "w"), indent=2, default=str)
print("\nwrote screen_results.csv, maxt_null_draws.csv, permutation_nulls.npz, s04_screen.json")
print("DONE")
