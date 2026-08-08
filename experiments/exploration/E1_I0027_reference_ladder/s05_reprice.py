"""E1_I0027 s05 -- RE-PRICE THE LEDGER'S LIVE AND RECENTLY-KILLED LEADS ON THE CANONICAL RUNG.

Re-hashes the frozen spec first.  Every figure below is computed with ONE denominator per
(response, row set), passed explicitly, so the D099 defect -- a subset's SST standing in for the
stratum's -- is structurally impossible rather than merely discouraged.

WHAT IS RE-PRICED AND WHAT IS NOT is fixed in _prereg.json's `plan` block, written before any of
this ran.  Two of the five leads are SKIPPED, with reasons, rather than approximated.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")
KIT = os.path.join(EXP, "_screen_kit")
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
for p in (HERE, KIT):
    if p not in sys.path:
        sys.path.insert(0, p)
import refladder as RL          # noqa: E402
import screenkit as SK          # noqa: E402

OUT = HERE
SEED = 20260808
N_DRAWS = 4000
SCORED = [2022, 2023, 2024]

TV = os.path.join(EXP, r"E1_I0018_teammate_volume_channel\screen_frame.parquet")
EFF = os.path.join(EXP, r"E0_I0016_efficiency_predictors\screen_frame.parquet")
TIER = os.path.join(EXP, r"E1_I0020_coldstart_tiering\tier_frame.parquet")
PLPTS = os.path.join(EXP, r"E1_I0020_coldstart_tiering\placeholders_pts.csv")
CANON_FRAME = os.path.join(EXP, r"E0_I0024_reb_ast_characterisation\screen_frame.parquet")

B_COMPLETE = ["refB_ppm", "refB_spm", "refB_pps", "refB_mpg", "refB_own_usg_pg"]


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


hdr("0. re-hash the frozen preregistration")
pre = json.load(open(os.path.join(OUT, "_prereg.json"), encoding="utf-8"))
for t, c in pre["canon"].items():
    RL.CANON[t].update({k: c[k] for k in ("mode", "half_life", "shrink", "k", "floor", "source")})
assert RL.ladder_hash() == pre["sha256"], "LADDER SPEC CHANGED SINCE PREREGISTRATION"
print("  sha256 %s  MATCH" % pre["sha256"])

records = []          # -> reprice_table.csv
diag = {}


# --------------------------------------------------------------------------- helpers
def wf_forecast(y, basecols, xcol, season, rowmask, X_extra=None):
    """Walk-forward OLS: fit on seasons strictly < s, predict season s.  Returns (yhat_base,
    yhat_with, scored_mask).  `basecols`/`xcol` are already-materialised float arrays."""
    n = len(y)
    yb = np.full(n, np.nan)
    yw = np.full(n, np.nan)
    B = np.column_stack([np.ones(n)] + list(basecols))
    if X_extra is not None:
        B = np.column_stack([B] + list(X_extra))
    F = np.column_stack([B, xcol]) if xcol is not None else B
    good = np.isfinite(F).all(axis=1) & np.isfinite(y) & rowmask
    for s in SCORED:
        tr = good & (season < s)
        te = good & (season == s)
        if tr.sum() < F.shape[1] + 20 or te.sum() == 0:
            continue
        bb, *_ = np.linalg.lstsq(B[tr], y[tr], rcond=None)
        yb[te] = B[te] @ bb
        if xcol is not None:
            bf, *_ = np.linalg.lstsq(F[tr], y[tr], rcond=None)
            yw[te] = F[te] @ bf
    scored = np.isfinite(yb) & (np.isfinite(yw) if xcol is not None else True)
    return yb, yw, scored


def paired(y, a, b, groups, sst, name_a, name_b):
    """Paired dR2 on a FIXED, EXPLICITLY SUPPLIED denominator + the kit's clustered sign-flip."""
    m = np.isfinite(y) & np.isfinite(a) & np.isfinite(b)
    dr2 = RL.r2_of_forecast(y[m], a[m], sst=sst) - RL.r2_of_forecast(y[m], b[m], sst=sst)
    res = SK.paired_forecast_comparison(y[m], a[m], b[m], groups=groups[m], n_draws=N_DRAWS,
                                        seed=SEED, name_a=name_a, name_b=name_b,
                                        alternative="two_sided")
    d = dict(res)
    return dict(dr2_common_sst=float(dr2), n=int(m.sum()),
                dr2_kit_own_sst=float(d.get("dr2_a_minus_b", np.nan)),
                p_cluster=float(d.get("p", np.nan)),
                p_row_NAIVE=float(d.get("p_row_level_NAIVE", np.nan)),
                mae_base=float(np.mean(np.abs(y[m] - b[m]))),
                mae_with=float(np.mean(np.abs(y[m] - a[m]))))


# ============================================================ D089 and D099 (same frame, same rows)
hdr("1. D089 + D099 -- the E1_I0018 frame, DECISION stratum, seasons 2022-2024")
tv = pd.read_parquet(TV)
eff = pd.read_parquet(EFF)
print("  tv frame %s ; eff frame %s" % (tv.shape, eff.shape))
keys = ["season", "player_id", "game_id"]
have = [k for k in keys if k in tv.columns and k in eff.columns]
print("  join keys available: %s" % have)
defcol = "A10_opp_defrtg"
if defcol not in eff.columns:
    cands = [c for c in eff.columns if "defrtg" in c.lower()]
    print("  A10_opp_defrtg absent; candidates: %s" % cands)
    defcol = cands[0]
tv = tv.merge(eff[have + [defcol]].drop_duplicates(have), on=have, how="left")
print("  after join: %s ; %s non-null on %d rows" % (tv.shape, defcol, int(tv[defcol].notna().sum())))

rungs_pts, meta_pts = RL.ladder(tv, "pts", date_col="game_date", scored_seasons=SCORED)
rungs_ppm, meta_ppm = RL.ladder(tv, "ppm", date_col="game_date", scored_seasons=SCORED)
f = meta_pts["frame"]
assert (f.index == meta_ppm["frame"].index).all()
season = f["season"].to_numpy()
y_pts = RL.target_series(f, "pts")
y_ppm = RL.target_series(f, "ppm")
m_hat = pd.to_numeric(f["prior5_minutes"], errors="coerce").fillna(
    pd.to_numeric(f["refB_mpg"], errors="coerce")).to_numpy(float)
groups = (f["season"].astype(str) + "_" + f["player_id"].astype(str)).to_numpy()

DECISION = ((pd.to_numeric(f["n_prior"], errors="coerce") >= 8)
            & (pd.to_numeric(f["prior5_minutes"], errors="coerce") >= 24)).to_numpy()
print("  DECISION stratum rows (all seasons): %d" % int(DECISION.sum()))

Bc = [pd.to_numeric(f[c], errors="coerce").to_numpy(float) for c in B_COMPLETE]
P01 = pd.to_numeric(f["P01_c04_prevgame"], errors="coerce").to_numpy(float)
DEF = pd.to_numeric(f[defcol], errors="coerce").to_numpy(float)
NOISE = pd.to_numeric(f["G01_noise"], errors="coerce").to_numpy(float)
USG = pd.to_numeric(f["O01_own_usg_pg"], errors="coerce").to_numpy(float)

# ---- the COMMON scored row set: every arm of every comparison must live on it.
arms = {}
arms["QUOTED_D089_ppm_x_mhat"] = wf_forecast(y_ppm, Bc, P01, season, DECISION)
arms["QUOTED_D099_ppm"] = wf_forecast(y_ppm, Bc, DEF, season, DECISION, X_extra=[USG])
arms["QUOTED_D099_pts"] = wf_forecast(y_pts, Bc, DEF, season, DECISION, X_extra=[USG])
for rung in ["R1_PLAYER_EXPAND", "R2_EWMA_TUNED", RL.CANONICAL_RUNG]:
    rp = rungs_pts[rung].to_numpy(float)
    rm = rungs_ppm[rung].to_numpy(float)
    arms["D089_pts_%s" % rung] = wf_forecast(y_pts, [rp], P01, season, DECISION)
    arms["D099_pts_%s" % rung] = wf_forecast(y_pts, [rp], DEF, season, DECISION, X_extra=[USG])
    arms["D099_ppm_%s" % rung] = wf_forecast(y_ppm, [rm], DEF, season, DECISION, X_extra=[USG])
    arms["NEGCTRL_pts_%s" % rung] = wf_forecast(y_pts, [rp], NOISE, season, DECISION)

common = DECISION.copy()
for k, (yb, yw, sc) in arms.items():
    common &= sc
common &= np.isfinite(y_pts) & np.isfinite(y_ppm) & np.isfinite(m_hat)
n_common = int(common.sum())
SST_PTS = float(((y_pts[common] - y_pts[common].mean()) ** 2).sum())
SST_PPM = float(((y_ppm[common] - y_ppm[common].mean()) ** 2).sum())
print("\n  COMMON SCORED ROW SET (identical for every arm below): n = %d" % n_common)
print("    SST(points) = %.6f      SST(ppm) = %.6f" % (SST_PTS, SST_PPM))
print("    per season: %s" % pd.Series(season[common]).value_counts().sort_index().to_dict())
diag["common_row_set"] = {"n": n_common, "sst_points": SST_PTS, "sst_ppm": SST_PPM,
                          "per_season": {int(k): int(v) for k, v in
                                         pd.Series(season[common]).value_counts().items()}}

hdr("2. ANCHOR -- reproduce D089's own construction and reference before changing anything")
yb, yw, _ = arms["QUOTED_D089_ppm_x_mhat"]
a_pts = yw * m_hat
b_pts = yb * m_hat
anchor = paired(y_pts[common], a_pts[common], b_pts[common], groups[common], SST_PTS,
                "B_COMPLETE+P01", "B_COMPLETE")
print("  D089 own protocol (ppm model x m_hat), on THIS screen's common row set:")
print("    dR2 = %+.9f   (published on its own row set n=4517: +0.0023492235735383)"
      % anchor["dr2_common_sst"])
print("    n=%d  cluster p=%.5f  row-NAIVE p=%.5f" % (anchor["n"], anchor["p_cluster"],
                                                     anchor["p_row_NAIVE"]))
diag["D089_anchor"] = anchor

yb, yw, _ = arms["QUOTED_D099_ppm"]
anchor99 = paired(y_ppm[common], yw[common], yb[common], groups[common], SST_PPM,
                  "B_COMPLETE+usg+def", "B_COMPLETE+usg")
print("\n  D099 own construction (defence main effect over B_COMPLETE + usage, ppm):")
print("    dR2 = %+.9f   (published +0.005028055896626 on n=4514)" % anchor99["dr2_common_sst"])
print("    n=%d  cluster p=%.5f" % (anchor99["n"], anchor99["p_cluster"]))
diag["D099_anchor_ppm"] = anchor99

yb, yw, _ = arms["QUOTED_D099_pts"]
anchor99p = paired(y_pts[common], yw[common], yb[common], groups[common], SST_PTS,
                   "B_COMPLETE+usg+def", "B_COMPLETE+usg")
print("\n  D099 own construction, POINTS response:")
print("    dR2 = %+.9f   (published +0.003335424864284 on n=4514)" % anchor99p["dr2_common_sst"])
print("    n=%d  cluster p=%.5f" % (anchor99p["n"], anchor99p["p_cluster"]))
diag["D099_anchor_points"] = anchor99p
print("\n  READ THE TWO ANCHORS BEFORE THE RATIOS: they isolate the ROW-SET change from the "
      "REFERENCE change.\n  Anchor/published tells you how much the smaller row set moved the "
      "number; repriced/anchor tells you how much the REFERENCE moved it.")

hdr("2b. HOW GOOD IS EACH RUNG *ON THESE ROWS*?  (the ladder's order is not stratum-invariant)")
rq = []
for resp, yv, rr, sst in [("points", y_pts, rungs_pts, SST_PTS), ("ppm", y_ppm, rungs_ppm, SST_PPM)]:
    for r in RL.RUNGS:
        v = rr[r].to_numpy(float)
        m = common & np.isfinite(v)
        if m.sum() == 0:
            continue
        rq.append(dict(row_set="E1_I0018 DECISION common", response=resp, rung=r, n=int(m.sum()),
                       mae=float(np.mean(np.abs(yv[m] - v[m]))),
                       r2_common_sst=RL.r2_of_forecast(yv[m], v[m], sst=sst)))
        print("  %-8s %-20s MAE %10.6f   R2(common SST) %+9.6f"
              % (resp, r, rq[-1]["mae"], rq[-1]["r2_common_sst"]))

hdr("3. RE-PRICE on the ladder")
rows = []
for lead, resp, xname, arm_prefix, sst, y in [
        ("D089_teammate_volume", "points", "P01_c04_prevgame", "D089_pts_", SST_PTS, y_pts),
        ("D099_opponent_defence", "points", defcol, "D099_pts_", SST_PTS, y_pts),
        ("D099_opponent_defence", "ppm", defcol, "D099_ppm_", SST_PPM, y_ppm),
        ("NEGATIVE_CONTROL_noise", "points", "G01_noise", "NEGCTRL_pts_", SST_PTS, y_pts)]:
    for rung in ["R1_PLAYER_EXPAND", "R2_EWMA_TUNED", RL.CANONICAL_RUNG]:
        ybb, yww, _ = arms[arm_prefix + rung]
        r = paired(y[common], yww[common], ybb[common], groups[common], sst, "rung+x", "rung")
        r.update(lead=lead, response=resp, feature=xname, base_rung=rung, sst_common=sst)
        rows.append(r)
        print("  %-24s %-7s base=%-18s dR2 %+.9f  n=%d  p_cluster=%.5f  (MAE %.4f -> %.4f)"
              % (lead, resp, rung, r["dr2_common_sst"], r["n"], r["p_cluster"],
                 r["mae_base"], r["mae_with"]))
rung_df = pd.DataFrame(rows)
rung_df.to_csv(os.path.join(OUT, "reprice_by_rung.csv"), index=False)

hdr("4. correct-level null for the prior-history regressors (cyclic, not shuffle)")
# D093: a plain within-player SHUFFLE is ANTICONSERVATIVE for an autocorrelated prior-history
# regressor.  P01 and the defence column are exactly that shape, so the null is the cyclic shift.
cyc = []
sub = f.loc[common].copy()
sub["_y"] = y_pts[common]
sub["_ref"] = rungs_pts[RL.CANONICAL_RUNG].to_numpy(float)[common]
sub["_grp"] = groups[common]
for xname, arr in [("P01_c04_prevgame", P01), (defcol, DEF), ("G01_noise", NOISE)]:
    sub["_x"] = arr[common]

    def stat(d):
        X = np.column_stack([np.ones(len(d)), d["_ref"].to_numpy(float),
                             d["_x"].to_numpy(float)])
        yv = d["_y"].to_numpy(float)
        ok = np.isfinite(X).all(axis=1) & np.isfinite(yv)
        bb, *_ = np.linalg.lstsq(X[ok], yv[ok], rcond=None)
        e = yv[ok] - X[ok] @ bb
        X0 = X[ok][:, :2]
        b0, *_ = np.linalg.lstsq(X0, yv[ok], rcond=None)
        e0 = yv[ok] - X0 @ b0
        return float((float(e0 @ e0) - float(e @ e)) / SST_PTS)

    try:
        res = SK.permutation_null(stat, sub, group_col="_grp", n_draws=1000, seed=SEED,
                                  feature_col="_x", scheme=SK.SCHEME_WITHIN_CYCLIC,
                                  order_col="_date", alternative="greater")
        d = dict(res)
        rec = dict(feature=xname, scheme="within_cyclic",
                   real=float(d.get("real", np.nan)), p=float(d.get("p", np.nan)),
                   null_sd=float(d.get("null_sd", np.nan)))
    except Exception as e:                                   # noqa: BLE001
        rec = dict(feature=xname, scheme="within_cyclic", error=str(e)[:400])
    cyc.append(rec)
    print("  %-22s %s" % (xname, rec))
pd.DataFrame(cyc).to_csv(os.path.join(OUT, "cyclic_null.csv"), index=False)
diag["cyclic_null"] = cyc

# ============================================================================== D092
hdr("5. D092 -- the cold-start operating rule, re-priced on the ladder")
tier = pd.read_parquet(TIER)
ph = pd.read_csv(PLPTS)
print("  tier_frame %s ; placeholders_pts %s" % (tier.shape, ph.shape))
assert len(tier) == len(ph), "placeholder table is not row-aligned with tier_frame"
champ = pd.to_numeric(tier["pts__pred_point"], errors="coerce").to_numpy(float)
fallback = tier["pts__is_fallback"].to_numpy(bool)
blend = pd.to_numeric(ph["P5d_blend_k2"], errors="coerce").to_numpy(float)
refD076 = pd.to_numeric(ph["P1_ref_D076"], errors="coerce").to_numpy(float)
rule = np.where(fallback, blend, champ)
y_t = pd.to_numeric(tier["y_pts"], errors="coerce").to_numpy(float)
mae_rule = float(np.mean(np.abs(y_t - rule)))
mae_ref = float(np.mean(np.abs(y_t - refD076)))
print("  reproduction: pooled MAE(rule) = %.15f  (published 4.035010863560213)" % mae_rule)
print("                pooled skill vs D076 ref = %.15f  (published 0.03506239696863178)"
      % (1.0 - mae_rule / mae_ref))
diag["D092_reproduction"] = {"mae_rule": mae_rule, "published_mae_rule": 4.035010863560213,
                            "skill_vs_refD076": 1.0 - mae_rule / mae_ref,
                            "published_skill": 0.03506239696863178,
                            "n_rows": int(len(tier)), "n_fallback": int(fallback.sum())}

# rungs for the tier frame.  The tier frame starts in 2022, which has no previous season inside it,
# so R4 would be unscored there.  Rungs are therefore built on the 2021-2024 canonical frame and
# joined on (season, player_id, date), and the coverage is reported rather than assumed.
cf = pd.read_parquet(CANON_FRAME)
rg, mg = RL.ladder(cf, "pts", date_col="game_date", scored_seasons=[2022, 2023, 2024])
gf = mg["frame"]
lut = pd.DataFrame({"season": gf["season"].to_numpy(), "player_id": gf["player_id"].to_numpy(),
                    "_d": gf["_date"].to_numpy()})
for r in RL.RUNGS:
    lut[r] = rg[r].to_numpy(float)
tt = tier[["season", "player_id", "gdate"]].copy()
tt["_d"] = pd.to_datetime(tt["gdate"])
tt = tt.merge(lut, on=["season", "player_id", "_d"], how="left")
cov = {r: int(tt[r].notna().sum()) for r in RL.RUNGS}
print("  rung coverage on the %d tier rows: %s" % (len(tier), cov))
diag["D092_rung_coverage"] = cov

d92 = []
ok_all = np.isfinite(y_t) & np.isfinite(rule) & np.isfinite(refD076)
for r in RL.RUNGS:
    v = tt[r].to_numpy(float)
    m = ok_all & np.isfinite(v)
    if m.sum() == 0:
        continue
    mr = float(np.mean(np.abs(y_t[m] - rule[m])))
    mv = float(np.mean(np.abs(y_t[m] - v[m])))
    md = float(np.mean(np.abs(y_t[m] - refD076[m])))
    d92.append(dict(rung=r, n=int(m.sum()), mae_rule=mr, mae_rung=mv,
                    skill_vs_rung=1.0 - mr / mv, mae_refD076=md,
                    skill_vs_refD076_same_rows=1.0 - mr / md))
    rq.append(dict(row_set="E1_I0020 tier frame (pooled)", response="points", rung=r,
                   n=int(m.sum()), mae=mv,
                   r2_common_sst=RL.r2_of_forecast(y_t[m], v[m])))
    print("  %-20s n=%5d  MAE(rule)=%.5f  MAE(rung)=%.5f  skill=%+.5f   "
          "[same rows, vs D076 ref: %+.5f]"
          % (r, m.sum(), mr, mv, 1.0 - mr / mv, 1.0 - mr / md))
d92 = pd.DataFrame(d92)
d92.to_csv(os.path.join(OUT, "d092_reprice_by_rung.csv"), index=False)

# ============================================================================== the table
hdr("6. reprice_table.csv")
def rowfor(lead, resp, quoted, quoted_ref, quoted_n, repriced, repriced_n, sst, note,
           status="RE-PRICED", anchor_same_rows=None, repriced_R2=None, p_cluster=None,
           p_cyclic=None):
    ratio = (repriced / quoted) if (quoted not in (None, 0) and repriced is not None
                                    and np.isfinite(quoted) and quoted != 0) else np.nan
    ratio_a = ((repriced / anchor_same_rows)
               if (anchor_same_rows not in (None, 0) and repriced is not None) else np.nan)
    return dict(lead=lead, response=resp, status=status,
                quoted_figure=quoted, quoted_reference=quoted_ref, quoted_n=quoted_n,
                repriced_on=RL.CANONICAL_RUNG, repriced_figure=repriced, repriced_n=repriced_n,
                sst_common=sst, ratio_repriced_over_quoted=ratio,
                quoted_recomputed_on_reprice_rows=anchor_same_rows,
                ratio_vs_same_rows_anchor=ratio_a,
                also_on_R2_EWMA_TUNED=repriced_R2,
                p_cluster_signflip=p_cluster, p_cyclic_within=p_cyclic, note=note)


CYC = {c["feature"]: c.get("p") for c in cyc}


T = []
g = rung_df.set_index(["lead", "response", "base_rung"])
T.append(rowfor(
    "D089 teammate volume (prior-only)", "points", 0.0023492235735382717,
    "B_COMPLETE (refB_ppm/spm/pps/mpg/own_usg) fitted on ppm, times m_hat = trailing-5 prior "
    "minutes -- i.e. a rung-1-grade minutes reference", 4517,
    float(g.loc[("D089_teammate_volume", "points", RL.CANONICAL_RUNG), "dr2_common_sst"]),
    n_common, SST_PTS,
    "Response and rows unchanged; only the reference changed.",
    anchor_same_rows=anchor["dr2_common_sst"],
    repriced_R2=float(g.loc[("D089_teammate_volume", "points", "R2_EWMA_TUNED"), "dr2_common_sst"]),
    p_cluster=float(g.loc[("D089_teammate_volume", "points", RL.CANONICAL_RUNG), "p_cluster"]),
    p_cyclic=CYC.get("P01_c04_prevgame")))
T.append(rowfor(
    "D099 opponent defence", "ppm", 0.005028055896625616,
    "B_COMPLETE + own-usage main effect, DECISION stratum common denominator", 4514,
    float(g.loc[("D099_opponent_defence", "ppm", RL.CANONICAL_RUNG), "dr2_common_sst"]),
    n_common, SST_PPM, "",
    anchor_same_rows=anchor99["dr2_common_sst"],
    repriced_R2=float(g.loc[("D099_opponent_defence", "ppm", "R2_EWMA_TUNED"), "dr2_common_sst"]),
    p_cluster=float(g.loc[("D099_opponent_defence", "ppm", RL.CANONICAL_RUNG), "p_cluster"]),
    p_cyclic=CYC.get(defcol)))
T.append(rowfor(
    "D099 opponent defence", "points", 0.0033354248642841694,
    "B_COMPLETE + own-usage main effect, DECISION stratum common denominator", 4514,
    float(g.loc[("D099_opponent_defence", "points", RL.CANONICAL_RUNG), "dr2_common_sst"]),
    n_common, SST_PTS, "Same rows as D089 above -- literally the same row set, not merely the "
                       "same n.",
    anchor_same_rows=anchor99p["dr2_common_sst"],
    repriced_R2=float(g.loc[("D099_opponent_defence", "points", "R2_EWMA_TUNED"),
                            "dr2_common_sst"]),
    p_cluster=float(g.loc[("D099_opponent_defence", "points", RL.CANONICAL_RUNG), "p_cluster"]),
    p_cyclic=CYC.get(defcol)))
if len(d92):
    q = float(d92.loc[d92.rung == RL.CANONICAL_RUNG, "skill_vs_refD076_same_rows"].iloc[0])
    rp = float(d92.loc[d92.rung == RL.CANONICAL_RUNG, "skill_vs_rung"].iloc[0])
    nn = int(d92.loc[d92.rung == RL.CANONICAL_RUNG, "n"].iloc[0])
    T.append(rowfor(
        "D092 cold-start tiering", "points (MAE skill, not dR2)", 0.03506239696863178,
        "D076's expanding running mean over the champion's scored rows -- the same screen showed "
        "it is degenerate for 404 of 475 player-seasons", 13879, rp, nn, np.nan,
        "SAME ROWS as the published figure (n=13,879), so the ratio is exact. THE RUNG CHOICE "
        "DOMINATES THIS ONE: vs R2_EWMA_TUNED the gain is %+.5f and vs R3_RATE_X_MINUTES it is "
        "%+.5f -- i.e. the same rule scores +4.8%%, +0.2%% or -0.5%% depending only on the "
        "reference." % (float(d92.loc[d92.rung == "R2_EWMA_TUNED", "skill_vs_rung"].iloc[0]),
                        float(d92.loc[d92.rung == "R3_RATE_X_MINUTES", "skill_vs_rung"].iloc[0])),
        anchor_same_rows=q,
        repriced_R2=float(d92.loc[d92.rung == "R2_EWMA_TUNED", "skill_vs_rung"].iloc[0])))
T.append(rowfor(
    "D074/D079 shot-mix attempts channel", "restricted-area attempt counts", 0.016853345987369095,
    "a five-zone attempts forecast system (F_B), conditional on a forecast total-FGA", 51473,
    None, None, np.nan,
    "SKIPPED, NOT APPROXIMATED. The response is a ZONE-level attempt count; the ladder defines a "
    "rung for TOTAL attempts, not for attempts within a zone, and the base is a system of five "
    "forecasts. Re-pricing requires rebuilding the zone forecasts, i.e. re-running the pipeline. "
    "Substituting total FGA would be a different quantity wearing the same name.",
    status="SKIPPED_CANNOT_REPRICE_WITHOUT_RERUN"))
T.append(rowfor(
    "D072 I0009 additive pressure", "turnovers per 100 offensive possessions", 0.000413,
    "a fitted multi-term pressure model with a strictly-pregame player-tendency baseline "
    "(M_F), plain unweighted OLS", 18165, None, None, np.nan,
    "SKIPPED, NOT APPROXIMATED. The response is not one of the six ladder targets and the base is "
    "a fitted model rather than a reference forecast; there is no rung to re-price onto without "
    "defining a seventh target and re-running the screen. NOTE: this lead is the one case where "
    "the reference was ALREADY corrected -- D072 re-ran it after finding the baseline read the "
    "future, and 0.000413 is the post-correction number.",
    status="SKIPPED_CANNOT_REPRICE_WITHOUT_RERUN"))

TT = pd.DataFrame(T)
TT.to_csv(os.path.join(OUT, "reprice_table.csv"), index=False)
pd.DataFrame(rq).to_csv(os.path.join(OUT, "rung_quality_by_rowset.csv"), index=False)

hdr("7. ranking_change.csv -- the operative question")
# ONLY the leads that satisfy D1 (same response) and D2 (same rows) can be ranked against each
# other at all.  That is D089 and D099 on POINTS: identical row set, identical SST, identical
# protocol.  Everything else is listed with the reason it is not rankable, rather than ranked
# anyway -- which is the practice this screen exists to stop.
RANK = []
pts_pairs = [("D089 teammate volume (prior-only)", 0.0023492235735382717,
              float(g.loc[("D089_teammate_volume", "points", RL.CANONICAL_RUNG),
                          "dr2_common_sst"]),
              float(g.loc[("D089_teammate_volume", "points", RL.CANONICAL_RUNG), "p_cluster"]),
              CYC.get("P01_c04_prevgame"), anchor["dr2_common_sst"]),
             ("D099 opponent defence", 0.0033354248642841694,
              float(g.loc[("D099_opponent_defence", "points", RL.CANONICAL_RUNG),
                          "dr2_common_sst"]),
              float(g.loc[("D099_opponent_defence", "points", RL.CANONICAL_RUNG), "p_cluster"]),
              CYC.get(defcol), np.nan)]
q_order = sorted(pts_pairs, key=lambda r: -r[1])
r_order = sorted(pts_pairs, key=lambda r: -r[2])
for i, row in enumerate(pts_pairs):
    RANK.append(dict(comparable_family="POINTS dR2, identical %d-row set, identical SST" % n_common,
                     lead=row[0], quoted_figure=row[1],
                     rank_by_quoted=[x[0] for x in q_order].index(row[0]) + 1,
                     repriced_on_canonical_rung=row[2],
                     rank_by_repriced=[x[0] for x in r_order].index(row[0]) + 1,
                     p_cluster_signflip_repriced=row[3], p_cyclic_repriced=row[4],
                     rank_changed=([x[0] for x in q_order].index(row[0])
                                   != [x[0] for x in r_order].index(row[0]))))
for lead, resp, why in [
        ("D092 cold-start tiering", "points",
         "METRIC MISMATCH: an MAE SKILL RATIO, not a dR2. Cannot be ranked against a dR2 under D1 "
         "without recomputing it as a dR2 on the same rows; and its row set (the whole tier frame, "
         "cold-start heavy) is disjoint in character from the DECISION stratum."),
        ("D074/D079 shot-mix attempts", "restricted-area attempt counts",
         "RESPONSE MISMATCH (D1): zone attempt counts are not points. No denominator makes the two "
         "comparable."),
        ("D072 I0009 additive pressure", "turnovers per 100 offensive possessions",
         "RESPONSE MISMATCH (D1), already recorded by D072 ruling 4 itself.")]:
    RANK.append(dict(comparable_family="NOT RANKABLE", lead=lead, quoted_figure=np.nan,
                     rank_by_quoted=np.nan, repriced_on_canonical_rung=np.nan,
                     rank_by_repriced=np.nan, rank_changed=np.nan, reason=why))
RK = pd.DataFrame(RANK)
RK.to_csv(os.path.join(OUT, "ranking_change.csv"), index=False)
print(RK.to_string())
n_swap = int(RK["rank_changed"].fillna(False).astype(bool).sum())
print("\n  RANK SWAPS AMONG THE COMPARABLE FAMILY: %d" % n_swap)
print("  ORDER BY QUOTED    : %s" % [x[0] for x in q_order])
print("  ORDER BY RE-PRICED : %s" % [x[0] for x in r_order])
diag["ranking"] = {"n_swaps": n_swap, "order_quoted": [x[0] for x in q_order],
                   "order_repriced": [x[0] for x in r_order],
                   "n_rankable": len(pts_pairs), "n_not_rankable": len(RANK) - len(pts_pairs)}
pd.set_option("display.width", 250)
print(TT[["lead", "response", "status", "quoted_figure", "repriced_figure",
          "ratio_repriced_over_quoted", "quoted_n", "repriced_n"]].to_string())

with open(os.path.join(OUT, "_s05.json"), "w", encoding="utf-8") as fh:
    json.dump({"diag": diag, "reprice_by_rung": json.loads(rung_df.to_json(orient="records")),
               "d092": json.loads(d92.to_json(orient="records")) if len(d92) else [],
               "table": json.loads(TT.to_json(orient="records"))}, fh, indent=1, default=str)
print("\n  wrote reprice_table.csv, reprice_by_rung.csv, d092_reprice_by_rung.csv, "
      "cyclic_null.csv, _s05.json")
