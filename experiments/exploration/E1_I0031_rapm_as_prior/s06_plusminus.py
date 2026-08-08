"""STEP 5 -- RAW PER-GAME PLUS-MINUS, TESTED SEPARATELY FROM RAPM.

WHY SEPARATELY.  Per-game `plus_minus` is a DIFFERENT OBJECT from RAPM.  It is row-granular, noisy,
and contaminated by which teammates and opponents were on the floor -- RAPM exists precisely to
strip that out.  But it is GAME-level where RAPM is SEASON-level, so it can in principle carry
within-season form that RAPM structurally cannot.  The two are never pooled into one block here.

NULL CONSTRUCTION.  The plus-minus features are prior-history series that VARY WITHIN a player-
season and are strongly autocorrelated.  A plain within-player SHUFFLE is anticonservative for
exactly this shape (D093 measured p=0.0015 where the honest null gave p=0.39) and the kit refuses
it.  The CYCLIC SHIFT is used instead: it preserves each player-season's marginal distribution and
its serial correlation exactly, and destroys only the alignment to the response.
CREDIT: E1_I0021_heterogeneity_diagnostic/hd_base.py (D093).

The season-level candidate P05 (`pm_prev_season`) is CONSTANT within a player-season, so it gets
the PLAYER-SEASON RELABELLING null instead, for the same reason RAPM does.  The two are reported
apart and never mixed.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rp_base as B  # noqa: E402

PRE = json.load(open(os.path.join(B.OUT, "_prereg.json")))
B.hdr("STEP 5 -- RAW PLUS-MINUS   (candidate sha256 %s)" % PRE["candidate_sha256"][:16])

f = pd.read_parquet(os.path.join(B.OUT, "analysis_frame.parquet"))
f = f.sort_values(["season", "player_id", "gdate"], kind="stable").reset_index(drop=True)
B.guard(f, "analysis frame")
season = f["season"].to_numpy()
YCOL = {"pts": "y_pts", "minutes": "y_minutes", "fga": "y_fga", "ppm": "y_ppm"}
RAPM = [c for _, c, _ in PRE["rapm_candidates"]]
PM_GAME = ["pm_ewma5_imp", "pm_ewma2_imp", "pm_run_mean_imp", "pm_per36_prior_imp"]
PM_SEASON = ["pm_prev_season_imp"]
PM_ALL = PM_GAME + PM_SEASON

B.sub("Confirming the two plus-minus families sit at DIFFERENT levels (this drives the null)")
for c in PM_ALL:
    g = f.groupby(["season", "player_id"], sort=False)[c].nunique(dropna=True)
    frac_const = float((g <= 1).mean())
    print("    %-22s constant within player-season for %.3f of player-seasons -> %s null"
          % (c, frac_const,
             "PLAYER-SEASON RELABEL" if frac_const > 0.95 else "CYCLIC SHIFT"))
B.assert_constant_within(f, "pm_prev_season_imp")
print("    VERIFIED: pm_prev_season is constant within player-season; the game-level series are "
      "not.")

for t, cs in PRE["base_cols"].items():
    for c in cs:
        if "b_" + c not in f.columns:
            f["b_" + c] = f[c].astype(float).fillna(f.groupby("season")[c].transform("mean"))
        if f[c].isna().any() and "bm_" + c not in f.columns:
            f["bm_" + c] = f[c].isna().astype(float)
BASE_DESIGN = {t: ["b_" + c for c in cs]
                  + [("bm_" + c) for c in cs if ("bm_" + c) in f.columns]
               for t, cs in PRE["base_cols"].items()}

M_WF = f["m_wf"].to_numpy(bool)
M_STRAT = M_WF & f["m_stratum"].to_numpy(bool)
ps_codes = f.groupby(["season", "player_id"], sort=False).ngroup().to_numpy()
codes, starts, ns = B.group_bounds(f)
RELAB = B.PlayerSeasonRelabeller(ps_codes)
SHIFT = B.CyclicShifter(starts, ns)

# VERIFY the vectorised shifter against the loop implementation it replaces, on the same seed.
_v = f["pm_ewma5_imp"].to_numpy(float)
for _s in range(5):
    _a = B.cyclic_shift_within_groups(_v, starts, ns, np.random.default_rng(_s))
    _b = SHIFT.draw(_v, np.random.default_rng(_s))
    assert np.array_equal(np.sort(_a), np.sort(_b)), "shifter changes the multiset"
    _ga = pd.Series(_a).groupby(codes).apply(lambda s: tuple(sorted(s)))
    _gb = pd.Series(_b).groupby(codes).apply(lambda s: tuple(sorted(s)))
    assert (_ga == _gb).all(), "shifter moves values ACROSS groups -- that is not a cyclic shift"
print("  vectorised cyclic shifter VERIFIED against the loop implementation "
      "(same multiset, values never leave their player-season), 5 seeds.")

# ============================================================ dR2 with the level-correct null
B.hdr("STEP 5a -- dR2 over BASE, and over BASE+RAPM, with level-correct nulls")


def dr2_with_null(y, Xb, add_cols, mask, null_kind, seed, n_draws=B.N_DRAWS):
    Xa = f[add_cols].to_numpy(float)
    d = B.dr2_common_denominator(y, Xb, np.column_stack([Xb, Xa]), sst_mask=mask)
    idx = np.flatnonzero(mask)
    yy = y[idx]
    Ab = np.column_stack([np.ones(len(idx)), Xb[idx]])
    bb, *_ = np.linalg.lstsq(Ab, yy, rcond=None)
    ry = yy - Ab @ bb
    sst = float(((yy - yy.mean()) ** 2).sum())
    P = np.linalg.pinv(Ab)
    rng = np.random.default_rng(seed)
    blockv = RELAB.block_values(Xa) if null_kind == "relabel" else None
    draws = np.empty(n_draws)
    for j in range(n_draws):
        Xp = (RELAB.draw(blockv, rng) if null_kind == "relabel" else SHIFT.draw(Xa, rng))[idx]
        R = Xp - Ab @ (P @ Xp)
        b = R.T @ ry
        coef = np.linalg.solve(R.T @ R + 1e-10 * np.eye(R.shape[1]), b)
        draws[j] = float(b @ coef) / sst
    p = (1.0 + int((draws >= d["dr2"]).sum())) / (n_draws + 1.0)
    return d, p, draws


rows = []
draw_rec = []
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    Xb0 = f[BASE_DESIGN[t]].to_numpy(float)
    Xb1 = np.column_stack([Xb0, f[RAPM].to_numpy(float)])
    for over_name, Xb in [("base_only", Xb0), ("base_plus_RAPM", Xb1)]:
        for add_name, add_cols, nk in [("pm_game_level", PM_GAME, "cyclic"),
                                       ("pm_prev_season", PM_SEASON, "relabel"),
                                       ("pm_all", PM_ALL, "cyclic")]:
            for sname, mask in [("wf_eval_2023_24", M_WF),
                                ("decision_stratum_wf", M_STRAT)]:
                d, p, dr = dr2_with_null(y, Xb, add_cols, mask, nk,
                                         B.SEED + abs(hash(t + over_name + add_name + sname))
                                         % 99991)
                y_wf = y[M_WF]
                sstf = float(((y_wf - y_wf.mean()) ** 2).sum())
                rows.append({"target": t, "over": over_name, "added": add_name,
                             "null": "player_season_relabel" if nk == "relabel"
                                     else "cyclic_shift_within_player_season",
                             "stratum": sname, "n": d["n"],
                             "r2_base": d["r2_base"], "dr2_own_sst": d["dr2"],
                             "dr2_on_full_wf_sst": (d["sse_base"] - d["sse_full"]) / sstf,
                             "sst_basis": "own stratum SST + full wf_eval SST (D099)",
                             "perm_p": p, "null_p95": float(np.quantile(dr, 0.95)),
                             "n_draws": B.N_DRAWS})
                if sname == "wf_eval_2023_24":
                    for j, v in enumerate(dr):
                        draw_rec.append({"test": "pm_dr2", "target": t, "over": over_name,
                                         "added": add_name, "draw": j, "value": float(v)})
                print("    %-8s over %-14s add %-15s %-20s dR2=%+.6f  p=%.4f  null95=%+.6f"
                      % (t, over_name, add_name, sname, d["dr2"], p, np.quantile(dr, 0.95)))
res = pd.DataFrame(rows)

# ============================================================ head-to-head
B.hdr("STEP 5b -- HEAD TO HEAD: which of the two, if either, survives over the other?")
h2h = []
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    Xb0 = f[BASE_DESIGN[t]].to_numpy(float)
    for sname, mask in [("wf_eval_2023_24", M_WF), ("decision_stratum_wf", M_STRAT)]:
        combos = {
            "RAPM_over_base": (Xb0, RAPM),
            "PM_over_base": (Xb0, PM_ALL),
            "RAPM_over_base_plus_PM": (np.column_stack([Xb0, f[PM_ALL].to_numpy(float)]), RAPM),
            "PM_over_base_plus_RAPM": (np.column_stack([Xb0, f[RAPM].to_numpy(float)]), PM_ALL),
        }
        for nm, (Xb, add) in combos.items():
            d = B.dr2_common_denominator(y, Xb, np.column_stack([Xb, f[add].to_numpy(float)]),
                                         sst_mask=mask)
            h2h.append({"target": t, "stratum": sname, "comparison": nm, "n": d["n"],
                        "dr2_own_sst": d["dr2"], "sst_basis": "own stratum SST"})
h2h = pd.DataFrame(h2h)
print(h2h[h2h["stratum"] == "wf_eval_2023_24"].pivot(index="comparison", columns="target",
                                                     values="dr2_own_sst").to_string(
    float_format=lambda v: "%+.6f" % v))

# ============================================================ as a reference fill
B.hdr("STEP 5c -- plus-minus as a REFERENCE FILL, head to head with RAPM on the same rows")
print("  This is the step-3 question asked of plus-minus: on rows with no prior-season mean in the")
print("  frame, does a PREVIOUS-SEASON PLUS-MINUS fill do what a RAPM fill does?\n")
dec = pd.read_csv(os.path.join(B.OUT, "decomposition_posthoc.csv"))
dec = dec[dec["analysis"] == "step3_V3_fill_decomposition_POSTHOC"]
print("  (for reference, from s05 -- skill vs D094's incumbent on wf_eval rows)")
print(dec[dec["stratum"] == "wf_eval_2023_24"].pivot(index="fill_source", columns="target",
                                                     values="skill_vs_D094").to_string(
    float_format=lambda v: "%+.4f%%" % (100 * v)))

# ============================================================ walk-forward forecast
B.hdr("STEP 5d -- WALK-FORWARD FORECAST: does adding plus-minus improve the refit forecast?")
ALPHA_GRID = [1e-3, 1e-2, 1e-1, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1e3, 3e3, 1e4]
gdate_num = f["gdate"].to_numpy("datetime64[D]").astype(np.int64)
_role_raw = np.where(f["rolebucket"].to_numpy(float) >= 0, f["rolebucket"].to_numpy(float), np.nan)
AVAIL_SRC = {}
for _t in B.TARGETS:
    AVAIL_SRC["b_prevseason_" + _t] = f["prevseason_raw_" + _t].to_numpy(float)
    AVAIL_SRC["b_role_" + _t] = _role_raw
AVAIL_SRC["pm_prev_season_imp"] = np.where(f["pm_prev_season"].notna(), 1.0, np.nan)


def _ridge(Z, y, a):
    ym = float(y.mean())
    return ym, np.linalg.solve(Z.T @ Z + a * np.eye(Z.shape[1]), Z.T @ (y - ym))


def wf(y, X, colnames):
    out = np.full(len(X), np.nan)
    for s in [2023, 2024]:
        tr = np.flatnonzero(season < s)
        te = np.flatnonzero(season == s)
        avail = np.array([not (cn in AVAIL_SRC
                               and np.mean(~np.isfinite(AVAIL_SRC[cn][tr])) > 0.99)
                          for cn in colnames])
        mu, sd = X[tr].mean(axis=0), X[tr].std(axis=0)
        keep = avail & (sd > 1e-8)
        Z = (X[:, keep] - mu[keep]) / sd[keep]
        Z = np.clip(Z, Z[tr].min(axis=0), Z[tr].max(axis=0))
        dtr = gdate_num[tr]
        cut = np.quantile(dtr, 0.70)
        fit_i, val_i = tr[dtr <= cut], tr[dtr > cut]
        best_a, best_m = None, np.inf
        for a in ALPHA_GRID:
            b0, bb = _ridge(Z[fit_i], y[fit_i], a)
            m = float(np.mean(np.abs(y[val_i] - (b0 + Z[val_i] @ bb))))
            if m < best_m:
                best_m, best_a = m, a
        b0, bb = _ridge(Z[tr], y[tr], best_a)
        out[te] = b0 + Z[te] @ bb
    return out


fcrows = []
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    bd = BASE_DESIGN[t]
    arms = {"base": (bd, f[bd].to_numpy(float)),
            "base+RAPM": (bd + RAPM, f[bd + RAPM].to_numpy(float)),
            "base+PM": (bd + PM_ALL, f[bd + PM_ALL].to_numpy(float)),
            "base+RAPM+PM": (bd + RAPM + PM_ALL, f[bd + RAPM + PM_ALL].to_numpy(float))}
    P = {nm: wf(y, X, cn) for nm, (cn, X) in arms.items()}
    for sname, mask in [("wf_eval_2023_24", M_WF), ("decision_stratum_wf", M_STRAT)]:
        for nm, p in P.items():
            sk_, ma, mb, n = B.skill(y[mask], p[mask], P["base"][mask])
            diff = np.abs(y[mask] - p[mask]) - np.abs(y[mask] - P["base"][mask])
            r, _ = B.block_signflip(diff, ps_codes[mask])
            fcrows.append({"target": t, "stratum": sname, "arm": nm, "n": n, "mae": ma,
                           "mae_base": mb, "skill_vs_base": sk_,
                           "p_blockflip": r["p_two_sided_blockflip"],
                           "mae_d094_est": B.mae(y[mask], f["est_" + t].to_numpy(float)[mask])})
fcd = pd.DataFrame(fcrows)
print(fcd[fcd["stratum"] == "wf_eval_2023_24"].pivot(index="arm", columns="target",
                                                     values="skill_vs_base").to_string(
    float_format=lambda v: "%+.4f%%" % (100 * v)))
print("\n  block sign-flip p:")
print(fcd[fcd["stratum"] == "wf_eval_2023_24"].pivot(index="arm", columns="target",
                                                     values="p_blockflip").to_string(
    float_format=lambda v: "%.4f" % v))

B.hdr("WRITE")
out = pd.concat([res.assign(block="dr2"), h2h.assign(block="head_to_head"),
                 fcd.assign(block="walkforward_forecast")], ignore_index=True, sort=False)
B.wcsv(out, "plusminus_separate.csv")
pd.DataFrame(draw_rec).to_csv(os.path.join(B.OUT, "permutation_draws_plusminus.csv"),
                              index=False)
print("  wrote permutation_draws_plusminus.csv (%d draws)" % len(draw_rec))
B.jdump({"dr2": res.to_dict("records"), "head_to_head": h2h.to_dict("records"),
         "forecast": fcd.to_dict("records")}, "_s06.json")
print("DONE s06")
