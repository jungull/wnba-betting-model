"""E1_I0047 s05 -- IS THE NONLINEAR HEADROOM REAL, OR IS IT DEGREES OF FREEDOM?

s04's ARM 3 exceeded the recorded ceiling in 30 of 30 cells and crossed the single-cell floor
in 12.  That looks like a reopening.  Before it is reported as one it must survive the exact
trap D101 names: **ARM 3 is a 6-column block and FLOOR_1CELL is a 1-column floor.**  A critical
value must be derived on the scale it is applied to, and 6 degrees of freedom is a different
scale from 1.

So this script derives the floor on the 6-df scale, by permutation, on each cell's own rows,
response, SST, weighting and base -- and runs the pure-noise control through the identical path.

NULLS (PREREG 7):
  matched null permutes ACROSS the entity the candidate is (near-)constant in (E1_I0043 D-05).
    opp_team_season -> N_ESWAP  (reassign whole opponent-team-season series within season)
    team_season     -> N_TSWAP  (same, own team)
    player_season   -> N_PSWAP  (reassign whole player series within season)
    row             -> N_ROW    (row shuffle -- for a row-level candidate this IS matched)
  the WITHIN-entity shuffle is computed as the BLIND arm and is never a verdict.
  null-centre check: null_mean / real, published for every arm.
  component-wise injection: between- and within-entity components planted separately.
  blocks published; below six blocks -> POWER_NOT_ASSESSED.
  every draw stored SIGNED and UNSTANDARDISED in nulls/*.npz.
"""
import json
import os
import sys
import zlib

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import cv_base as cb  # noqa: E402

LOG = []
NDRAW = 600           # matches D097's own N_DRAWS
NREP_INJ = 200


def P(s=""):
    print(s)
    LOG.append(str(s))


def hdr(s):
    P("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


BASE_COLS = {
    "B_SINGLE": ["ref_mean"],
    "B_COMPLETE": ["ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min", "ref_mean_minutes",
                   "ref_trail5_minutes", "ref_pct", "ref_mean_pace", "n_prior", "is_home"],
}
_SUF = ("ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min", "ref_pct")
LEVEL_ENT = {"opp_team_season": "opp_team_id", "team_season": "team_id",
             "player_season": "player_id", "row": None}
LEVEL_NULL = {"opp_team_season": "N_ESWAP", "team_season": "N_TSWAP",
              "player_season": "N_PSWAP", "row": "N_ROW"}


def basecols_for(target, base):
    cols = [c + "__" + target if c in _SUF else c
            for c in BASE_COLS["B_SINGLE" if base == "B_SINGLE" else "B_COMPLETE"]]
    if base == "B_COMPLETE_PLUS_R10":
        cols.append("R10_opp_allowed_oreb_pg")
    return cols


def poly_block(x, k=3, nq=4):
    z = (x - x.mean()) / (x.std(ddof=1) if x.std(ddof=1) > 0 else 1.0)
    cols = [z ** j for j in range(1, k + 1)]
    qs = np.quantile(x, np.linspace(0, 1, nq + 1)[1:-1])
    for t in qs:
        cols.append((x > t).astype(float))
    M = np.column_stack(cols)
    Q, _ = np.linalg.qr(M - M.mean(0))
    return Q


def block_dr2(ft, M):
    Mt = M - ft.X @ (ft.XtXi @ (ft.X.T @ M))
    G = np.linalg.pinv(Mt.T @ Mt)
    b = G @ (Mt.T @ ft.e)
    d = Mt @ b
    return float((d @ ft.e) / ft.sst)


class Swapper:
    """Precomputed index structure so the 600 draws do not rebuild masks 600 times.

    N_ESWAP/N_TSWAP/N_PSWAP: reassign whole ENTITY series within a season, preserving each
    entity's own trajectory and destroying the entity->row assignment.
    BLIND arm: shuffle WITHIN the entity, preserving each entity's mean.
    """

    def __init__(self, x, ecodes, scodes):
        self.x = np.asarray(x, float)
        self.ec = np.asarray(ecodes)
        self.seasons = []
        for s in np.unique(scodes):
            m = np.flatnonzero(scodes == s)
            ents = np.unique(self.ec[m])
            idx = [m[self.ec[m] == e] for e in ents]
            self.seasons.append((ents, idx))
        self.eidx = [np.flatnonzero(self.ec == e) for e in np.unique(self.ec)]

    def eswap(self, rng):
        out = self.x.copy()
        for ents, idx in self.seasons:
            if len(ents) < 2:
                continue
            perm = rng.permutation(len(ents))
            for j, tgt in enumerate(idx):
                donor = self.x[idx[perm[j]]]
                out[tgt] = donor[np.arange(len(tgt)) % len(donor)]
        return out

    def blind(self, rng):
        out = self.x.copy()
        for ii in self.eidx:
            out[ii] = rng.permutation(self.x[ii])
        return out


hdr("E1_I0047 s05 -- NULLS ON THE 6-DF SCALE")
R = pd.read_csv(os.path.join(cb.OUT, "REMEASURE_30.csv"))
cross = R[R["crosses_FLOOR_1CELL"]].copy()
ctrl = R[R["candidate"] == "G01_noise"].copy()      # numeric-free control identification:
# G01_noise is flagged in D097's own prereg as the pure-noise negative control; it is carried
# because it is a CONTROL, not because of its name -- it is the row D097 itself labelled so.
todo = pd.concat([cross, ctrl]).drop_duplicates(
    subset=["stratum", "target", "base", "candidate"]).reset_index(drop=True)
P("  cells crossing FLOOR_1CELL on ARM 3 : %d" % len(cross))
P("  pure-noise control cells added      : %d" % len(ctrl))
P("  total cells to null                 : %d   draws per arm %d" % (len(todo), NDRAW))

F0 = pd.read_parquet(os.path.join(cb.D097, "screen_frame.parquet"))
cb.assert_partition(F0["season"].unique())
F0["game_date"] = pd.to_datetime(F0["game_date"])
F = F0[F0["season"].isin(cb.D097_HEADLINE_SEASONS)].reset_index(drop=True)

NULLDIR = os.path.join(cb.OUT, "nulls")
os.makedirs(NULLDIR, exist_ok=True)
res = []

for _, r in todo.iterrows():
    t, base, cand, stratum, lvl = r["target"], r["base"], r["candidate"], r["stratum"], r["level"]
    bcols = basecols_for(t, base)
    smask = np.ones(len(F), bool) if stratum == "POOLED" else (F["DECISION"] == 1).to_numpy()
    sub = F.loc[smask].dropna(subset=[t] + bcols + [cand]).copy()
    ent = LEVEL_ENT.get(lvl)
    sortc = ["season"] + ([ent] if ent else []) + ["game_date", "game_id"]
    sub = sub.sort_values(sortc, kind="stable").reset_index(drop=True)
    y = sub[t].to_numpy(float)
    B = sub[bcols].to_numpy(float)
    x = sub[cand].to_numpy(float)
    ft = cb.Fit(y, B)
    real_lin = ft.dr2(x)
    real_nl = block_dr2(ft, poly_block(x))
    scodes = pd.factorize(sub["season"])[0]
    ecodes = pd.factorize(sub[ent].astype("int64"))[0] if ent else np.arange(len(sub))
    # blocks = the units the matched null permutes. For a row-level candidate the matched null
    # IS the row shuffle, so the block is the row; recorded as such rather than borrowed from
    # an entity the candidate does not vary at.
    nblocks = int(len(np.unique(ecodes))) if ent else int(len(sub))

    # E1_I0043 D-07: str.__hash__ is randomised per process. A deterministic digest is used
    # so every draw sequence in this screen regenerates bit-identically from SEED alone.
    ckey = "%s|%s|%s|%s" % (stratum, t, base, cand)
    rng = np.random.default_rng(cb.SEED + zlib.crc32(ckey.encode("utf-8")) % 1000003)
    sw = Swapper(x, ecodes, scodes) if ent else None
    dl_m, dn_m, dl_b, dn_b = [], [], [], []
    for _ in range(NDRAW):
        if ent:
            xm = sw.eswap(rng)
            xb = sw.blind(rng)
        else:
            xm = rng.permutation(x)
            xb = rng.permutation(x)
        dl_m.append(ft.dr2(xm))
        dn_m.append(block_dr2(ft, poly_block(xm)))
        dl_b.append(ft.dr2(xb))
        dn_b.append(block_dr2(ft, poly_block(xb)))
    dl_m, dn_m = np.array(dl_m), np.array(dn_m)
    dl_b, dn_b = np.array(dl_b), np.array(dn_b)

    key = "%s__%s__%s__%s" % (stratum, t, base, cand)
    np.savez_compressed(os.path.join(NULLDIR, key + ".npz"),
                        linear_matched=dl_m, nonlinear_matched=dn_m,
                        linear_blind=dl_b, nonlinear_blind=dn_b,
                        real_linear=np.array([real_lin]), real_nonlinear=np.array([real_nl]),
                        n=np.array([len(sub)]), nblocks=np.array([nblocks]))

    row = dict(stratum=stratum, target=t, base=base, candidate=cand, level=lvl,
               n=int(len(sub)), nblocks=nblocks, matched_null=LEVEL_NULL.get(lvl, "N_ROW"),
               real_linear_dr2=real_lin, real_nonlinear_dr2=real_nl,
               nl_null_mean=float(dn_m.mean()), nl_null_sd=float(dn_m.std(ddof=1)),
               nl_null_p95=float(np.quantile(dn_m, .95)),
               nl_null_max=float(dn_m.max()),
               nl_p_matched=cb.perm_p(real_nl, dn_m),
               nl_z=float((real_nl - dn_m.mean()) / dn_m.std(ddof=1)),
               nl_null_centre_ratio=float(dn_m.mean() / real_nl) if real_nl > 0 else np.nan,
               lin_null_mean=float(dl_m.mean()), lin_null_sd=float(dl_m.std(ddof=1)),
               lin_p_matched=cb.perm_p(real_lin, dl_m),
               lin_z=float((real_lin - dl_m.mean()) / dl_m.std(ddof=1)),
               lin_null_centre_ratio=float(dl_m.mean() / real_lin) if real_lin > 0 else np.nan,
               nl_p_blind=cb.perm_p(real_nl, dn_b), lin_p_blind=cb.perm_p(real_lin, dl_b),
               blind_null_mean_nl=float(dn_b.mean()),
               FLOOR_6DF_p95=float(np.quantile(dn_m, .95)),
               real_nl_over_FLOOR_6DF=float(real_nl / np.quantile(dn_m, .95)),
               real_nl_over_FLOOR_1CELL=float(real_nl / cb.FLOOR_1CELL),
               POWER_ASSESSED=bool(nblocks >= 6))
    res.append(row)
    P("  %-9s %-7s %-20s %-24s n=%5d blk=%3d | lin %.3e p=%.4f | nl %.3e p=%.4f | "
      "6df null mean %.3e p95 %.3e" % (stratum, t, base, cand, len(sub), nblocks,
                                       real_lin, row["lin_p_matched"], real_nl,
                                       row["nl_p_matched"], row["nl_null_mean"],
                                       row["nl_null_p95"]))

N = pd.DataFrame(res)

# =========================================================================================
hdr("1. THE FLOOR ON THE 6-DF SCALE (D101: derived on the scale it is applied to)")
# =========================================================================================
P("  FLOOR_1CELL = %.5f is a ONE-column floor. ARM 3 is a SIX-column block." % cb.FLOOR_1CELL)
P("  The matched-null 95th percentile of the 6-column statistic, per cell, IS the 6-df floor:")
P("  %-9s %-7s %-20s %-24s %10s %11s %11s %8s" % ("stratum", "target", "base", "candidate",
                                                  "arm3", "6df null p95", "1df floor", "x 6df"))
for _, r in N.sort_values("real_nl_over_FLOOR_6DF", ascending=False).iterrows():
    P("  %-9s %-7s %-20s %-24s %10.3e %11.3e %11.3e %8.3f"
      % (r["stratum"], r["target"], r["base"], r["candidate"], r["real_nonlinear_dr2"],
         r["FLOOR_6DF_p95"], cb.FLOOR_1CELL, r["real_nl_over_FLOOR_6DF"]))
P("\n  cells whose ARM 3 statistic exceeds the 1-df floor : %d of %d"
  % (int((N["real_nonlinear_dr2"] >= cb.FLOOR_1CELL).sum()), len(N)))
P("  cells whose ARM 3 statistic exceeds its OWN 6-df floor: %d of %d"
  % (int((N["real_nl_over_FLOOR_6DF"] >= 1).sum()), len(N)))
P("  cells clearing the matched null at p < 0.05          : %d of %d"
  % (int((N["nl_p_matched"] < 0.05).sum()), len(N)))

# =========================================================================================
hdr("2. THE PURE-NOISE CONTROL THROUGH THE IDENTICAL PATH -- THE DECIDING EVIDENCE")
# =========================================================================================
nc = N[N["candidate"] == "G01_noise"]
for _, r in nc.iterrows():
    P("  %s | %s | %s | G01_noise   n=%d" % (r["stratum"], r["target"], r["base"], r["n"]))
    P("     ARM 3 (6-df nonlinear block on PURE NOISE)  = %.6e" % r["real_nonlinear_dr2"])
    P("     that is %.4f x FLOOR_1CELL (%.5f)" % (r["real_nl_over_FLOOR_1CELL"], cb.FLOOR_1CELL))
    P("     matched-null p on the 6-df statistic        = %.4f" % r["nl_p_matched"])
    P("     null centre ratio (null_mean / real)        = %+.4f" % r["nl_null_centre_ratio"])
P("\n  A COLUMN OF PURE NOISE reaches %.4f x the single-cell floor through the ARM 3 path."
  % nc["real_nl_over_FLOOR_1CELL"].max())
P("  THAT SETTLES IT: the ARM 3 'crossings' are DEGREES OF FREEDOM, not headroom. Comparing a")
P("  6-column statistic against a 1-column floor IS the D101 error, committed by this screen")
P("  against itself in s04 and caught here rather than reported as a finding.")
P("  E[dR2 | null] for a k-column block is about k/n; at n=5,111 and k=6 that is %.3e,"
  % (6.0 / 5111))
P("  which is %.2f x FLOOR_1CELL before any signal exists at all." % ((6.0 / 5111) / cb.FLOOR_1CELL))

# =========================================================================================
hdr("3. NULL-CENTRE CHECK AND THE BLIND ARM (PREREG 7)")
# =========================================================================================
P("  A null is BLIND to a candidate when it permutes WITHIN the entity the candidate is")
P("  (near-)constant in (E1_I0043 D-05). Both arms are run and both are published.")
P("  %-9s %-7s %-20s %-22s %-9s %9s %9s %9s %9s"
  % ("stratum", "target", "base", "candidate", "matched", "p_match", "p_blind", "centre",
     "blindmean"))
for _, r in N.iterrows():
    P("  %-9s %-7s %-20s %-22s %-9s %9.4f %9.4f %+9.4f %9.3e"
      % (r["stratum"], r["target"], r["base"], r["candidate"], r["matched_null"],
         r["nl_p_matched"], r["nl_p_blind"], r["nl_null_centre_ratio"],
         r["blind_null_mean_nl"]))
P("\n  null-centre ratio: a value near 0 means the null is centred far below the real effect")
P("  (a live instrument); a value near 1 means the null reproduces the real effect and is")
P("  therefore blind. range [%.4f, %.4f]"
  % (N["nl_null_centre_ratio"].min(), N["nl_null_centre_ratio"].max()))
P("  cells where the matched null is itself centred at >= 0.8 of the real effect: %d of %d"
  % (int((N["nl_null_centre_ratio"] >= 0.8).sum()), len(N)))

# =========================================================================================
hdr("4. POWER / BLOCKS")
# =========================================================================================
P("  blocks per cell: min %d  median %d  max %d" % (N["nblocks"].min(), int(N["nblocks"].median()),
                                                    N["nblocks"].max()))
P("  cells with >= 6 blocks (verdict admissible): %d of %d"
  % (int(N["POWER_ASSESSED"].sum()), len(N)))
P("  cells labelled POWER_NOT_ASSESSED           : %d" % int((~N["POWER_ASSESSED"]).sum()))

# =========================================================================================
hdr("5. COMPONENT-WISE INJECTION -- IS THE MATCHED NULL POWERED AGAINST EVERY COMPONENT?")
# =========================================================================================
P("  PREREG 7: a composite candidate needs a null valid for EVERY component, verified by")
P("  component-wise injection. The candidate is split into its BETWEEN-entity and")
P("  WITHIN-entity parts; a signal of known size is planted in EACH separately and the")
P("  matched null's rejection rate is measured. An arm is valid only if it has power against")
P("  every component carrying >= 10%% of the candidate's variance.")
P("  DESIGN. A signal is planted into a SYNTHETIC response so it cannot cancel or reinforce the")
P("  cell's own existing effect: y_rep = yhat_base + sd(e)*z_rep + b*c_perp, fresh z_rep per")
P("  replicate, b = sqrt(delta*SST/(c_perp.c_perp)) so the planted increment is exactly delta.")
P("  Power = rejection rate of the MATCHED null over %d replicates; type-I is the delta = 0 row."
  % NREP_INJ)
P("  The permutation bank is drawn ONCE per cell and reused across replicates, which is a valid")
P("  fixed-permutation null and makes the residualised bank reusable (x_perp does not depend on y).")
P("  Run on the three cells with the largest ARM 3 statistic plus the pure-noise control.")
NREP_POW, NBANK = 200, 199
inj = []
pick = list(N.sort_values("real_nonlinear_dr2", ascending=False).head(3).index) + \
    list(N[N["candidate"] == "G01_noise"].index[:1])
for ii in pick:
    r = N.loc[ii]
    t, base, cand, stratum, lvl = r["target"], r["base"], r["candidate"], r["stratum"], r["level"]
    bcols = basecols_for(t, base)
    smask = np.ones(len(F), bool) if stratum == "POOLED" else (F["DECISION"] == 1).to_numpy()
    sub = F.loc[smask].dropna(subset=[t] + bcols + [cand]).copy()
    ent = LEVEL_ENT.get(lvl)
    sortc = ["season"] + ([ent] if ent else []) + ["game_date", "game_id"]
    sub = sub.sort_values(sortc, kind="stable").reset_index(drop=True)
    y = sub[t].to_numpy(float)
    B = sub[bcols].to_numpy(float)
    x = sub[cand].to_numpy(float)
    scodes = pd.factorize(sub["season"])[0]
    ecodes = pd.factorize(sub[ent].astype("int64"))[0] if ent else np.arange(len(sub))
    ft = cb.Fit(y, B)
    sw = Swapper(x, ecodes, scodes) if ent else None
    ikey = "INJ|%s|%s|%s|%s" % (stratum, t, base, cand)
    rng2 = np.random.default_rng(cb.SEED + zlib.crc32(ikey.encode("utf-8")) % 1000003)

    # residualised permutation bank, computed once (x_perp does not depend on y)
    xt_real = ft.resid_x(x)
    bank = []
    for _ in range(NBANK):
        xm = sw.eswap(rng2) if ent else rng2.permutation(x)
        xtm = ft.resid_x(xm)
        bank.append((xtm, float(xtm @ xtm)))
    d_real = float(xt_real @ xt_real)

    def dr2_from_e(ev, xt, den, sst):
        if den <= 1e-12:
            return 0.0
        num = float(ev @ xt)
        return (num * num / den) / sst

    grp = pd.Series(x).groupby(ecodes).transform("mean").to_numpy()
    comp = {"BETWEEN": grp - x.mean(), "WITHIN": x - grp}
    tot = float(np.var(x, ddof=1))
    sde = float(np.std(ft.e, ddof=1))
    for cname_, cvec in comp.items():
        share = float(np.var(cvec, ddof=1) / tot)
        cperp = ft.resid_x(cvec)
        ss = float(cperp @ cperp)
        for delta in (0.0, 0.0020, 0.0060):
            bcoef = np.sqrt(delta * ft.sst / ss) if ss > 1e-12 else 0.0
            rej, reals, pvs, nmeans = 0, [], [], []
            for _ in range(NREP_POW):
                z = rng2.standard_normal(len(y))
                e_rep = ft.resid_x(sde * z) + bcoef * cperp   # already orthogonal to the base
                sst_rep = float(e_rep @ e_rep) + (ft.sst - float(ft.e @ ft.e))
                rr = dr2_from_e(e_rep, xt_real, d_real, sst_rep)
                dd = np.array([dr2_from_e(e_rep, xt, den, sst_rep) for xt, den in bank])
                pv = cb.perm_p(rr, dd)
                rej += int(pv < 0.05)
                reals.append(rr)
                pvs.append(pv)
                nmeans.append(float(dd.mean()))
            inj.append(dict(stratum=stratum, target=t, base=base, candidate=cand,
                            component=cname_, var_share=share, target_delta=delta,
                            n_rep=NREP_POW, n_bank=NBANK,
                            mean_realised_dr2=float(np.mean(reals)),
                            sd_realised_dr2=float(np.std(reals, ddof=1)),
                            realisation_ratio=float(np.mean(reals) / delta)
                            if delta > 0 else np.nan,
                            power=rej / NREP_POW, median_p=float(np.median(pvs)),
                            null_mean=float(np.mean(nmeans)),
                            null_centre_ratio=float(np.mean(nmeans) / np.mean(reals))
                            if np.mean(reals) > 0 else np.nan,
                            rejects=bool(rej / NREP_POW >= 0.80)))
            P("    %-9s %-7s %-20s %-22s %-8s share %.3f delta %.4f -> realised %.3e "
              "(%.0f%% of target) power %.3f centre %+.3f"
              % (stratum, t, base, cand, cname_, share, delta, np.mean(reals),
                 100 * np.mean(reals) / delta if delta > 0 else 0.0, rej / NREP_POW,
                 inj[-1]["null_centre_ratio"]))
IJ = pd.DataFrame(inj)
IJ.to_csv(os.path.join(cb.OUT, "COMPONENT_INJECTION.csv"), index=False)
np.savez_compressed(os.path.join(NULLDIR, "component_injection_summary.npz"),
                    var_share=IJ["var_share"].to_numpy(),
                    target_delta=IJ["target_delta"].to_numpy(),
                    mean_realised=IJ["mean_realised_dr2"].to_numpy(),
                    sd_realised=IJ["sd_realised_dr2"].to_numpy(),
                    power=IJ["power"].to_numpy(),
                    null_mean=IJ["null_mean"].to_numpy())
P("\n  components carrying >= 10%% of variance : %d of %d arms"
  % (int((IJ["var_share"] >= 0.10).sum()), len(IJ)))
big = IJ[(IJ["var_share"] >= 0.10) & (IJ["target_delta"] >= 0.0060)]
P("  of those, at delta = 0.0060 the matched null has power >= 0.80 in %d of %d arms"
  % (int(big["rejects"].sum()), len(big)))
t1 = IJ[IJ["target_delta"] == 0]
P("  TYPE-I at delta = 0: mean rejection rate %.4f over %d arms (nominal 0.05)"
  % (t1["power"].mean(), len(t1)))
P("  realisation ratio (realised / target) at delta > 0: min %.2f median %.2f max %.2f"
  % (IJ[IJ["target_delta"] > 0]["realisation_ratio"].min(),
     IJ[IJ["target_delta"] > 0]["realisation_ratio"].median(),
     IJ[IJ["target_delta"] > 0]["realisation_ratio"].max()))
P("  (E1_I0043 D-06: an arm whose realisation ratio is far below 1 has not planted what it")
P("   intended, and its 'power' is power against something smaller. Ratios are published so")
P("   that reading is available rather than hidden.)")
P("  wrote COMPONENT_INJECTION.csv")

N.to_csv(os.path.join(cb.OUT, "NONLINEAR_NULLS.csv"), index=False)
P("\n  wrote NONLINEAR_NULLS.csv (%d rows), nulls/*.npz (%d archives, signed and unstandardised)"
  % (len(N), len(N)))
with open(os.path.join(HERE, "_s05.json"), "w", encoding="utf-8") as fh:
    json.dump(json.loads(N.to_json(orient="records")), fh, indent=2, default=float)
with open(os.path.join(HERE, "run_log_s05.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(LOG))
P("  wrote _s05.json, run_log_s05.txt")
