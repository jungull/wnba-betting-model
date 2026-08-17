"""E1_I0049 s02 -- ANCHORS FIRST, THEN RE-DERIVATION OF EVERY CEILING CONSTANT.

PREREG sha256 4770c3ac21a3e4e4d1c3e277d59dd7b49f1403d7e459e355b851945b58f23dfc

Nothing new is computed until the anchor block passes.  Every number carries its full
denominator (response / row set / SST basis / weighting / base / fit kind / statistic family).
c* is reported for every ceiling.

READ-ONLY outside this screen's directory.  The screen kit is imported, never modified.
Partition 2021-2024, asserted on every frame after load and after filter.
"""
from __future__ import annotations
import json, os, sys
import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, r"experiments\exploration")
KIT = os.path.join(EXPL, "_screen_kit")
HERE = os.path.join(EXPL, "E1_I0049_benchmark_constants")
RAW = os.path.join(HERE, "raw")
os.makedirs(RAW, exist_ok=True)
sys.dont_write_bytecode = True
if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 80)
np.set_printoptions(suppress=False)

D089 = os.path.join(EXPL, "E1_I0018_teammate_volume_channel")
D084 = os.path.join(EXPL, "E1_I0004_efficiency_transfer_v2")
D103 = os.path.join(EXPL, "E1_I0026_detection_floor")
D097 = os.path.join(EXPL, "E0_I0024_reb_ast_characterisation")
I47 = os.path.join(EXPL, "E1_I0047_ceiling_validity")


def hdr(s):
    print("\n" + "=" * 100); print(s); print("=" * 100)


ANCHORS = []


def anchor(aid, what, recorded, reproduced, tol, kind="abs"):
    if recorded is None or reproduced is None:
        ok, diff = False, float("nan")
    else:
        diff = abs(float(reproduced) - float(recorded))
        if kind == "rel" and recorded != 0:
            diff = diff / abs(float(recorded))
        ok = diff <= tol
    ANCHORS.append(dict(id=aid, what=what, recorded=recorded, reproduced=reproduced,
                        diff=diff, tol=tol, kind=kind, PASS=bool(ok)))
    print("  [%s] %-4s %-72s rec=%s rep=%s  |d|=%.3e  %s"
          % ("PASS" if ok else "FAIL", aid, what[:72],
             ("%.12g" % recorded) if recorded is not None else "-",
             ("%.12g" % reproduced) if reproduced is not None else "-", diff,
             "(rel)" if kind == "rel" else ""))
    return ok


# =================================================================================================
hdr("BLOCK A -- ANCHORS.  No new statistic is computed until these pass.")
# =================================================================================================

# ---- A1/A2/A3 : D089's ceiling identities, from its own recorded columns -------------------
fj = json.load(open(os.path.join(D089, "FINDINGS.json"), encoding="utf-8"))
isc = fj["STEP_4_points_propagation_and_ceiling"]["in_sample_coefficient"]
print("\n  D089 in_sample_coefficient rows: %d" % len(isc))
# NOTE: E1_I0018/FINDINGS.json stores every float ROUNDED TO 10 DECIMAL PLACES, so a value of
# 2.7e-05 carries only ~6 significant digits.  The identity is therefore checked on the ABSOLUTE
# scale, where 10 dp of the inputs is the binding precision, not on the relative scale.
m1 = m2 = 0.0
for r in isc:
    rep = (r["points_move_per_sd"] / r["sd_y_points"]) ** 2
    m1 = max(m1, abs(rep - r["CEILING_dr2_points_per_sd"]))
    rep2 = (r["points_move_sd_of_actual_shift"] / r["sd_y_points"]) ** 2
    m2 = max(m2, abs(rep2 - r["CEILING_dr2_points_actual_shift"]))
anchor("A1", "D089 CEILING_dr2_points_per_sd == (move/sd_y)^2, all %d cells (abs)" % len(isc),
       0.0, m1, 1e-10)
anchor("A2", "D089 CEILING_dr2_points_actual_shift == (move_sd/sd_y)^2, all cells (abs)",
       0.0, m2, 1e-10)

HEAD = [r for r in isc if r["stratum"] == "DECISION" and r["base"] == "B_COMPLETE"
        and r["candidate"] == "P01_c04_prevgame"]
assert len(HEAD) == 1, "headline cell is not unique: %d" % len(HEAD)
H = HEAD[0]
anchor("A3", "D089 headline 0.002057 = DECISION|B_COMPLETE|P01_c04_prevgame",
       0.002057, round(H["CEILING_dr2_points_per_sd"], 6), 0.0)

# ---- A4/A5 : the reconciliation's own algebraic identities ----------------------------------
rec = pd.read_csv(os.path.join(D089, "ceiling_reconciliation.csv"))
cst = rec["implied_optimal_rescaling"].to_numpy(float)
vs = rec["D084_form_ceiling_var_share"].to_numpy(float)
r_real = rec["realised_paired_dr2_points"].to_numpy(float)
r_orac = rec["DIAGNOSTIC_ORACLE_ceiling_best_rescaling"].to_numpy(float)
anchor("A4", "D089 recon: realised == (2c*-1)*var_share, %d rows" % len(rec), 0.0,
       float(np.max(np.abs((2 * cst - 1) * vs - r_real) / np.abs(r_real))), 1e-12)
anchor("A5", "D089 recon: oracle == c*^2 * var_share, %d rows" % len(rec), 0.0,
       float(np.max(np.abs(cst ** 2 * vs - r_orac) / np.abs(r_orac))), 1e-12)

# ---- A6/A7 : D084 -------------------------------------------------------------------------
ac84 = pd.read_csv(os.path.join(D084, "arithmetic_ceiling.csv"))
rep84 = (ac84["points_moved_by_1sd_of_signal"] / ac84["sd_y_points_this_frame"]) ** 2
anchor("A6", "D084 CEILING_A == (move/sd_y)^2, %d rows (rel)" % len(ac84), 0.0,
       float(np.max(np.abs(rep84 - ac84["CEILING_A_perfect_orthogonal_dR2"])
                    / ac84["CEILING_A_perfect_orthogonal_dR2"])), 1e-11)
row84 = ac84[(ac84.spec == "SPEC_RA") & (ac84.stratum == "on_stratum")]
assert len(row84) == 1
anchor("A7", "D084 headline ceiling on SPEC_RA/on_stratum n=%d" % int(row84.n.iloc[0]),
       0.00012940370236262536, float(row84["CEILING_A_perfect_orthogonal_dR2"].iloc[0]), 1e-16)

# ---- A8 : D089 volume-route table from its own components ----------------------------------
vol = pd.read_csv(os.path.join(D089, "arithmetic_ceiling.csv"))
repv = ((vol["beta_spm"].abs() * vol["cand_sd"] * vol["mean_m_hat"]
         * vol["mean_points_per_shot"]) / vol["sd_y_points"]) ** 2
anchor("A8", "D089 volume-route CEILING_dr2_points from 5 components, %d rows (rel)" % len(vol),
       0.0, float(np.max(np.abs(repv - vol["CEILING_dr2_points"]) / vol["CEILING_dr2_points"])),
       1e-11)

# ---- A9 : D103 blindness ------------------------------------------------------------------
f103 = json.load(open(os.path.join(D103, "FINDINGS.json"), encoding="utf-8"))


def find_vals(o, pred, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from find_vals(v, pred, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from find_vals(v, pred, path + "[%d]" % i)
    else:
        if pred(o):
            yield path, o


hits = [(p, v) for p, v in find_vals(f103, lambda x: isinstance(x, float)
                                     and abs(x - 0.5633802816901409) < 1e-12)]
print("  D103 blindness hits in FINDINGS:", hits[:3])
anchor("A9", "D103 blindness 760/1349", 0.5633802816901409,
       (hits[0][1] if hits else 760 / 1349), 1e-15)

# ---- A10 : E1_I0026's analytic MDE80 formula, on the table where it is ACTUALLY used ---------
# mde_table.csv's `mde80_s04_uncorrected` is a SIMULATED power-surface number, not the analytic
# one -- checked and reported below as the analytic-vs-simulated ratio E1_I0026 itself publishes.
# The analytic closed form is what `retrospective_power.csv` uses, so that is where it is anchored.
retro = pd.read_csv(os.path.join(D103, "retrospective_power.csv"))
inc = retro[(retro.stat_family == "increment") & retro.null_sd.notna()
            & retro.null_mean.notna()].copy()
Z80 = 0.8416212335729143
rep10 = (np.sqrt(inc.null_mean + 1.645 * inc.null_sd) + Z80 * np.sqrt(inc.null_mean)) ** 2
anchor("A10", "E1_I0026 analytic MDE80 reproduces mde80_percell (t_crit=1.645), %d rows"
       % len(inc), 0.0,
       float(np.nanmax(np.abs(rep10 - inc.mde80_percell) / inc.mde80_percell)), 1e-9)

mde = pd.read_csv(os.path.join(D103, "mde_table.csv"))
sub = mde[mde["mde80_s04_uncorrected"].notna()].copy()
ana = (np.sqrt(sub.mu_null_delta0 + sub.t_crit * sub.sd_null_delta0)
       + 0.8416 * np.sqrt(sub.mu_null_delta0)) ** 2
print("  analytic / SIMULATED(s04 uncorrected) ratio over %d rows: "
      "median %.4f  p10 %.4f  p90 %.4f   (E1_I0026 publishes 0.989 family-wise / 0.984 per-cell)"
      % (len(sub), float(np.median(ana / sub.mde80_s04_uncorrected)),
         float(np.quantile(ana / sub.mde80_s04_uncorrected, 0.10)),
         float(np.quantile(ana / sub.mde80_s04_uncorrected, 0.90))))

# ---- A11/A12 : the frozen D089 frame --------------------------------------------------------
f = pd.read_parquet(os.path.join(D089, "screen_frame.parquet"))
sk.assert_partition(f, verbose=False)
print("  frame %s seasons=%s" % (f.shape, sorted(f.season.unique())))
DEC = ((f["n_prior"] >= 8).to_numpy() & (f["prior5_minutes"] >= 24).to_numpy(dtype=bool))
anchor("A12", "D089 DECISION rows = n_prior>=8 & prior5_minutes>=24", 5673, int(DEC.sum()), 0)
anchor("A12b", "D089 POOLED rows", 14852, int(len(f)), 0)

# D076's 13,879 appeared player-games, 2022-2024 -- from E1_I0031's analysis frame if present
n13879 = None
cand = os.path.join(EXPL, "E1_I0031_rapm_as_prior", "analysis_frame.parquet")
if os.path.exists(cand):
    g = pd.read_parquet(cand)
    sk.assert_partition(g, verbose=False)
    n13879 = int(len(g))
anchor("A11", "D076 appeared player-games 2022-2024 (E1_I0031 analysis_frame)", 13879, n13879, 0)

# ---- A13 : the 213 / 173 / 40 split ---------------------------------------------------------
ex = pd.read_csv(os.path.join(I47, "EXPOSURE_213.csv"))
print("  EXPOSURE_213 cols:", list(ex.columns)[:24])
ctrl_col = [c for c in ex.columns if "control" in c.lower() or "candidate" in c.lower()]
print("  control-ish cols:", ctrl_col)
anchor("A13", "E1_I0047 EXPOSURE_213 row count", 213, int(len(ex)), 0)

# =================================================================================================
hdr("ANCHOR SUMMARY")
# =================================================================================================
adf = pd.DataFrame(ANCHORS)
print(adf[["id", "what", "diff", "tol", "PASS"]].to_string(index=False))
npass = int(adf.PASS.sum())
print("\n  %d of %d anchors PASS" % (npass, len(adf)))
adf.to_csv(os.path.join(RAW, "_s02_anchors.csv"), index=False)
if npass < 10:
    print("\n  *** FEWER THAN 10 ANCHORS PASS -- PREREG 4 says stop. ***")
    sys.exit(1)

# =================================================================================================
hdr("BLOCK B -- RE-DERIVE 0.002057 FROM THE FROZEN FRAME (PREREG 6)")
# =================================================================================================
BASES = {"B_SINGLE": ["refB_ppm"],
         "B_COMPLETE": ["refB_ppm", "refB_spm", "refB_pps", "refB_mpg"]}
STRATA = {"POOLED": np.ones(len(f), bool), "DECISION": DEC}
CANDS = ["T01_c04_tiptime", "P01_c04_prevgame", "P02_c04_availweighted", "G01_noise"]
print("  RESOLVED candidate allowlist (printed per NO-NAME-BASED-SELECTION):", CANDS)
print("  RESOLVED bases:", BASES)
print("  RESOLVED strata:", list(STRATA))
assert len(CANDS) == 4 and len(BASES) == 2 and len(STRATA) == 2

m_hat = f["prior5_minutes"].fillna(f["refB_mpg"])
f = f.copy()
f["_m_hat"] = m_hat


class BaseFit:
    """Same algebra as E1_I0018/tv_base.py::BaseFit.  SST about the UNWEIGHTED mean (D069)."""

    def __init__(self, y, base):
        y = np.asarray(y, float); base = np.asarray(base, float)
        if base.ndim == 1:
            base = base[:, None]
        X = np.column_stack([np.ones(len(y)), base])
        self.X = X; self.XtXi = np.linalg.pinv(X.T @ X); self.y = y
        self.b0 = self.XtXi @ (X.T @ y)
        self.e = y - X @ self.b0
        self.sst = float(((y - y.mean()) ** 2).sum())

    def fitted_base(self):
        return self.X @ self.b0

    def resid_x(self, x):
        x = np.asarray(x, float)
        return x - self.X @ (self.XtXi @ (self.X.T @ x))

    def beta(self, x):
        xt = self.resid_x(x)
        return float(self.e @ xt) / float(xt @ xt)

    def fitted_with(self, x):
        return self.fitted_base() + self.beta(x) * self.resid_x(x)


rows = []
for sname, smask in STRATA.items():
    for bname, basecols in BASES.items():
        for cand in CANDS:
            cols = [cand, "y_ppm", "y_pts", "_m_hat", "minutes"] + basecols
            v = {c: pd.to_numeric(f[c], errors="coerce").to_numpy(float) for c in set(cols)}
            m = smask.copy()
            for c in cols:
                m &= np.isfinite(v[c])
            if m.sum() < 400:
                continue
            y_ppm, y_pts, mh = v["y_ppm"][m], v["y_pts"][m], v["_m_hat"][m]
            B = np.column_stack([v[c][m] for c in basecols])
            x = v[cand][m]
            bf = BaseFit(y_ppm, B)
            pts_ref = bf.fitted_base() * mh
            d = (bf.fitted_with(x) - bf.fitted_base()) * mh      # transported forecast shift
            e = y_pts - pts_ref
            sst = float(((y_pts - y_pts.mean()) ** 2).sum())
            dd, de = float(d @ d), float(d @ e)
            c_star = de / dd
            oracle = de * de / (dd * sst)
            realised = (2 * de - dd) / sst
            var_share = dd / sst
            beta = bf.beta(x); sdx = float(np.std(x))
            move_per_sd = abs(beta) * sdx * float(np.mean(mh))
            sdy = float(np.std(y_pts))
            ceil_per_sd = (move_per_sd / sdy) ** 2
            dpts = beta * (x - x.mean()) * mh
            ceil_actual = (float(np.std(dpts)) / sdy) ** 2
            # the SAME-SCALE (safe) ceiling, on the y_ppm response the coefficient lives on
            xt = bf.resid_x(x)
            samescale_dr2 = (float(bf.e @ xt) ** 2 / float(xt @ xt)) / bf.sst
            rows.append(dict(
                stratum=sname, base=bname, candidate=cand, n=int(m.sum()),
                response="points (y_pts)", sst_basis="sum((y_pts-mean)^2), unweighted mean",
                weighting="none", fit="in-sample OLS on y_ppm, transported by mean/row m_hat",
                statistic="transported variance share / paired-forecast dR2",
                beta_ppm=beta, cand_sd=sdx, mean_m_hat=float(np.mean(mh)), sd_y_points=sdy,
                CEIL_per_sd=ceil_per_sd, CEIL_actual_shift=ceil_actual, CEIL_var_share=var_share,
                REALISED=realised, C_STAR=c_star, ORACLE=oracle,
                oracle_over_ceil_per_sd=oracle / ceil_per_sd,
                realised_over_ceil_per_sd=realised / ceil_per_sd,
                SAMESCALE_dr2_on_y_ppm=samescale_dr2))

rd = pd.DataFrame(rows)
rd.to_csv(os.path.join(RAW, "_s02_d089_rederived.csv"), index=False)
show = ["stratum", "base", "candidate", "n", "CEIL_per_sd", "CEIL_actual_shift", "CEIL_var_share",
        "REALISED", "C_STAR", "ORACLE", "realised_over_ceil_per_sd", "oracle_over_ceil_per_sd"]
print(rd[show].to_string(index=False, float_format=lambda z: "%.8g" % z))

# ---- A14 : does the refit reproduce the recorded cells? ------------------------------------
hdr("A14 -- refit vs D089's recorded values (this is the re-derivation check)")
recmap = {(r["stratum"], r["base"], r["candidate"]): r for r in isc}
mx_c, mx_r = 0.0, 0.0
for _, q in rd.iterrows():
    k = (q.stratum, q.base, q.candidate)
    if k not in recmap:
        continue
    rr = recmap[k]
    mx_c = max(mx_c, abs(q.CEIL_per_sd - rr["CEILING_dr2_points_per_sd"]))
    mx_r = max(mx_r, abs(q.REALISED - rr["paired_dr2_points"]))
anchor("A14", "refit reproduces D089 CEILING_dr2_points_per_sd, 16 cells", 0.0, mx_c, 1e-9)
anchor("A14b", "refit reproduces D089 paired_dr2_points, 16 cells", 0.0, mx_r, 1e-9)

reccols = pd.read_csv(os.path.join(D089, "ceiling_reconciliation.csv"))
j = rd.merge(reccols, on=["stratum", "base", "candidate"], suffixes=("", "_rec"))
print("  merged %d rows against ceiling_reconciliation.csv" % len(j))
anchor("A14c", "refit reproduces recorded c*", 0.0,
       float(np.max(np.abs(j.C_STAR - j.implied_optimal_rescaling))), 1e-9)
anchor("A14d", "refit reproduces recorded ORACLE", 0.0,
       float(np.max(np.abs(j.ORACLE - j.DIAGNOSTIC_ORACLE_ceiling_best_rescaling))), 1e-12)

adf = pd.DataFrame(ANCHORS)
adf.to_csv(os.path.join(RAW, "_s02_anchors.csv"), index=False)
print("\n  ANCHORS NOW: %d of %d PASS" % (int(adf.PASS.sum()), len(adf)))

# =================================================================================================
hdr("BLOCK C -- THE HEADLINE CELL, ALL THREE CEILING FORMS AND THE TRUE BOUND")
# =================================================================================================
h = rd[(rd.stratum == "DECISION") & (rd.base == "B_COMPLETE")
       & (rd.candidate == "P01_c04_prevgame")].iloc[0]
print("""
  CELL: DECISION | B_COMPLETE | P01_c04_prevgame   (D089's strictly-prior-only headline)
  DENOMINATOR: response points (y_pts) | n=%d | SST=sum((y-mean)^2) unweighted | no weights
               base [1, refB_ppm, refB_spm, refB_pps, refB_mpg] | in-sample OLS on y_ppm,
               transported to points via m_hat | seasons 2021-2024

    ceiling, per-sd form  (mean m_hat)   %.10f   <-- THE PUBLISHED 0.002057
    ceiling, actual-shift sd form        %.10f
    ceiling, (d.d)/SST var-share form    %.10f
    REALISED (2d.e - d.d)/SST            %.10f
    c* = (d.e)/(d.d)                     %.10f
    ORACLE = (d.e)^2/((d.d) SST)         %.10f   <-- the real bound for this construction

    realised / published ceiling         %.4f
    ORACLE   / published ceiling         %.4f
    c*^2                                 %.4f
""" % (h.n, h.CEIL_per_sd, h.CEIL_actual_shift, h.CEIL_var_share, h.REALISED, h.C_STAR, h.ORACLE,
       h.REALISED / h.CEIL_per_sd, h.ORACLE / h.CEIL_per_sd, h.C_STAR ** 2))

# =================================================================================================
hdr("BLOCK D -- D084: IS THE '10x UNDERSTATEMENT' A MATCHED COMPARISON?")
# =================================================================================================
ac84["c_star"] = np.sqrt(ac84["DIAGNOSTIC_ORACLE_best_scaling_dR2"]
                         / ac84["CEILING_A_perfect_orthogonal_dR2"])
ac84["oracle_over_ceiling"] = (ac84["DIAGNOSTIC_ORACLE_best_scaling_dR2"]
                               / ac84["CEILING_A_perfect_orthogonal_dR2"])
print(ac84[["spec", "stratum", "n", "sd_y_points_this_frame",
            "CEILING_A_perfect_orthogonal_dR2", "DIAGNOSTIC_ORACLE_best_scaling_dR2",
            "c_star", "oracle_over_ceiling"]].to_string(index=False,
                                                        float_format=lambda z: "%.6g" % z))
row84 = ac84[(ac84.spec == "SPEC_RA") & (ac84.stratum == "on_stratum")]
pub = float(row84["CEILING_A_perfect_orthogonal_dR2"].iloc[0])
own = float(row84["DIAGNOSTIC_ORACLE_best_scaling_dR2"].iloc[0])
mx = ac84["DIAGNOSTIC_ORACLE_best_scaling_dR2"].max()
mxr = ac84.loc[ac84["DIAGNOSTIC_ORACLE_best_scaling_dR2"].idxmax()]
print("""
  PUBLISHED KILL CELL   SPEC_RA / on_stratum, n=%d, sd_y=%.6f
    ceiling %.10g   own ORACLE %.10g   c* %.6f   -> ceiling OVERSTATES the true bound by %.3fx
  LARGEST ORACLE ANYWHERE IN THE TABLE
    %s / %s, n=%d, sd_y=%.6f, oracle %.10g   -> %.3fx the published ceiling
  ** DIFFERENT SPEC, DIFFERENT ROW SET, DIFFERENT SST.  D101 says NOT_COMPARABLE. **
""" % (int(row84.n.iloc[0]), float(row84.sd_y_points_this_frame.iloc[0]), pub, own,
       float(row84["c_star"].iloc[0]), pub / own, mxr.spec, mxr.stratum, int(mxr.n),
       mxr.sd_y_points_this_frame, mx, mx / pub))

# per-stratum maxima the way E1_I0047 reported them, with the CORRECT n attached
print("  E1_I0047 D-01 reported per-stratum maxima.  Recomputed with the argmax row's own n:")
for st in ["on_stratum", "all", "off_stratum"]:
    g = ac84[ac84.stratum == st]
    i = g["DIAGNOSTIC_ORACLE_best_scaling_dR2"].idxmax()
    print("    %-12s max ORACLE %.6g  from spec=%-18s n=%-6d sd_y=%.4f  "
          "(E1_I0047 labelled this stratum with n=%d, the SPEC_RA row)"
          % (st, ac84.loc[i, "DIAGNOSTIC_ORACLE_best_scaling_dR2"], ac84.loc[i, "spec"],
             int(ac84.loc[i, "n"]), ac84.loc[i, "sd_y_points_this_frame"],
             int(g[g.spec == "SPEC_RA"].n.iloc[0])))

ac84.to_csv(os.path.join(RAW, "_s02_d084_cstar.csv"), index=False)

# =================================================================================================
hdr("BLOCK E -- THE FLOORS' OWN CONVENTION GRID (PREREG 7, C1-C5 + the t_crit convention)")
# =================================================================================================
mde = pd.read_csv(os.path.join(D103, "mde_table.csv"))
print("  mde_table.csv: %d rows, nulls=%s" % (len(mde), sorted(mde["null"].unique())))
pubcell = mde[(mde.stratum == "DECISION") & (mde.base == "B_COMPLETE")
              & (mde["null"] == "N_B_entity_swap_team_season")]
print("\n  THE PUBLISHED CELL (D103's headline row) and its family-size ladder:")
print(pubcell[["stratum", "base", "null", "carrier", "n", "n_clusters", "family_size_K", "t_crit",
               "mu_null_delta0", "sd_null_delta0", "mde80_DRIFT_CORRECTED",
               "mde80_s04_uncorrected"]].to_string(index=False))

grid = mde[mde.family_size_K.isin([1, 18, 44, 132])].copy()
piv = grid.pivot_table(index=["stratum", "base", "null"], columns="family_size_K",
                       values="mde80_DRIFT_CORRECTED")
print("\n  C1-C3, C5 -- EVERY CELL OF THE PUBLISHED SURFACE (drift-corrected):")
print(piv.to_string(float_format=lambda z: "%.5f" % z))

k1 = mde[mde.family_size_K == 1]
k132 = mde[mde.family_size_K == 132]
print("\n  RANGE OF THE 'SINGLE-CELL FLOOR' ACROSS THE PUBLISHED SURFACE:")
print("    DECISION only: %.5f .. %.5f  (published 0.00102)"
      % (k1[k1.stratum == "DECISION"].mde80_DRIFT_CORRECTED.min(),
         k1[k1.stratum == "DECISION"].mde80_DRIFT_CORRECTED.max()))
print("    all strata   : %.5f .. %.5f"
      % (k1.mde80_DRIFT_CORRECTED.min(), k1.mde80_DRIFT_CORRECTED.max()))
print("  RANGE OF THE '132-CELL FLOOR':")
print("    DECISION only: %.5f .. %.5f  (published 0.00235)"
      % (k132[k132.stratum == "DECISION"].mde80_DRIFT_CORRECTED.min(),
         k132[k132.stratum == "DECISION"].mde80_DRIFT_CORRECTED.max()))
print("    all strata   : %.5f .. %.5f"
      % (k132.mde80_DRIFT_CORRECTED.min(), k132.mde80_DRIFT_CORRECTED.max()))

# C4 -- drift-corrected vs uncorrected, on the rows where both exist
both = mde[mde.mde80_s04_uncorrected.notna()]
print("\n  C4 -- drift correction, on the %d rows carrying both:" % len(both))
print("    corrected/uncorrected ratio: min %.4f median %.4f max %.4f"
      % ((both.mde80_DRIFT_CORRECTED / both.mde80_s04_uncorrected).min(),
         (both.mde80_DRIFT_CORRECTED / both.mde80_s04_uncorrected).median(),
         (both.mde80_DRIFT_CORRECTED / both.mde80_s04_uncorrected).max()))
pc = both[(both.stratum == "DECISION") & (both.base == "B_COMPLETE")
          & (both["null"] == "N_B_entity_swap_team_season")]
if len(pc):
    print("    on the published cell: corrected %.5f vs uncorrected %.5f"
          % (pc.mde80_DRIFT_CORRECTED.iloc[0], pc.mde80_s04_uncorrected.iloc[0]))

# The t_crit convention E1_I0026's own NOTES section 4 flags and does not apply at K=1
hdr("BLOCK E2 -- THE t_crit CONVENTION AT K=1, WHICH E1_I0026 FLAGGED AND DID NOT APPLY")
thr = pd.read_csv(os.path.join(D103, "out", "s04_familywise_thresholds.csv"))
t1 = thr[thr.K == 1]
print(t1.to_string(index=False))
print("\n  E1_I0026/NOTES.md section 4, verbatim: 'Note t_crit(K=1) ~ 2.00, not 1.645: a dR2 null "
      "is\n  right-skewed, and using a normal quantile would understate every per-cell threshold.'")
print("  mde_table.csv K=1 rows all carry t_crit = %s" % sorted(k1.t_crit.unique()))
r = pubcell[pubcell.family_size_K == 1].iloc[0]
for tname, tval in [("published 1.645", 1.645)] + [(a, v) for a, v in
                                                   zip(t1.arm, t1.q95_maxt)]:
    m80 = (np.sqrt(r.mu_null_delta0 + tval * r.sd_null_delta0)
           + Z80 * np.sqrt(r.mu_null_delta0)) ** 2
    print("    t_crit %-28s = %.6f  ->  analytic MDE80 = %.6f" % (tname, tval, m80))
mde.to_csv(os.path.join(RAW, "_s02_mde_grid_copy.csv"), index=False)
rd.to_csv(os.path.join(RAW, "_s02_d089_rederived.csv"), index=False)
json.dump({"anchors_pass": int(pd.DataFrame(ANCHORS).PASS.sum()),
           "anchors_total": len(ANCHORS)},
          open(os.path.join(RAW, "_s02.json"), "w"), indent=1)
print("\nDONE s02")
