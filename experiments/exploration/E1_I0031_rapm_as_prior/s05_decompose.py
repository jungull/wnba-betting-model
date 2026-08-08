"""DECOMPOSITION OF THE TWO SURVIVORS.  POST-HOC -- DISCLOSED AS SUCH.

The preregistered list fixed the CANDIDATE FEATURES and the VARIANT FAMILIES.  The controls in
this step were NOT on that list: they were built after seeing that V3 (step 3) and C3 (step 4)
beat their incumbents, precisely because the brief requires any survivor to be decomposed against
its own components.  They can only REDUCE the claim, never create one, and every number here is
labelled post-hoc.

THE TWO CONFOUNDS BEING TESTED
  V3 differs from D094's incumbent V0 in exactly ONE way: on rows where the player has no
  prior-season mean IN THE FRAME, V0 falls back to the LEAGUE value and V3 falls back to a
  RAPM-derived value.  So the V3 gain could be either (i) RAPM's opponent-and-teammate ADJUSTMENT,
  or (ii) merely HAVING ANY player-specific prior-season number there at all -- and RAPM reaches
  back to 2021, which the frame does not, so it has strictly better COVERAGE than the frame's own
  prior-season mean.  Coverage is not quality.

  C3 beat D092 -- but C3 refits a coefficient on D092's OWN structural prior as well as adding a
  RAPM term.  The gain could be pure RECALIBRATION of D092's prior with no RAPM content.

THE DECISIVE CONTROL, and it is also the user's actual question.  Replace the RAPM fill with the
player's RAW previous-season per-game production computed from master_player -- which has the SAME
backward coverage as RAPM (both reach 2021) and is the SAME season-level object, but carries NO
opponent or teammate adjustment.  If the raw box score does as well, then the adjustment adds
nothing and RAPM is doing coverage work, not quality work.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rp_base as B  # noqa: E402

PRE = json.load(open(os.path.join(B.OUT, "_prereg.json")))
B.hdr("DECOMPOSITION (POST-HOC)   candidate sha256 %s" % PRE["candidate_sha256"][:16])

f = pd.read_parquet(os.path.join(B.OUT, "analysis_frame.parquet"))
f = f.sort_values(["season", "player_id", "gdate"], kind="stable").reset_index(drop=True)
season = f["season"].to_numpy()
mins = f["y_minutes"].to_numpy(float)
codes, starts, ns = B.group_bounds(f)
bucket_role = B.role_bucket(f)
YCOL = {"pts": "y_pts", "minutes": "y_minutes", "fga": "y_fga", "ppm": "y_ppm"}
SEL = PRE["d094_selected_cells"]
K_GRID = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0]
RAPM_MAP_COLS = ["z_net_100_imp", "z_orapm_100_imp", "z_drapm_100_imp", "log_total_poss_imp"]

# =============================================== the same-coverage NON-ADJUSTED comparator
B.sub("Building the RAW previous-season box score from master_player (SAME coverage as RAPM)")
mp = pd.read_parquet(B.MASTER, columns=["game_id", "player_id", "season", "game_date",
                                        "minutes", "pts", "fga"])
mp = mp[mp["season"].isin(B.PARTITION)].copy()                       # FILTER-POINT
mp["gdate"] = pd.to_datetime(mp["game_date"])
assert mp["gdate"].max() < pd.Timestamp("2025-01-01")
B.guard(mp, "master_player for prior-season box score")
for c in ["minutes", "pts", "fga"]:
    mp[c] = pd.to_numeric(mp[c], errors="coerce")
mp = mp[mp["minutes"].fillna(0) > 0].copy()
agg = mp.groupby(["season", "player_id"]).agg(
    m_minutes=("minutes", "mean"), m_pts=("pts", "mean"), m_fga=("fga", "mean"),
    s_pts=("pts", "sum"), s_min=("minutes", "sum"), g=("pts", "size")).reset_index()
agg["m_ppm"] = agg["s_pts"] / agg["s_min"].replace(0, np.nan)
agg["season"] = agg["season"] + 1          # attach to the FOLLOWING season -> strictly prior
PREV = agg[["season", "player_id", "m_pts", "m_minutes", "m_fga", "m_ppm", "g"]].rename(
    columns={"g": "prev_games_master"})
PREV = PREV[PREV["season"].isin(B.SCREEN_SEASONS)]
B.guard(PREV, "prior-season box score after shift")
f = f.merge(PREV, on=["season", "player_id"], how="left", validate="m:1")
print("  coverage of the RAW prior-season box score on the scored frame, by season:")
print(f.groupby("season")["m_pts"].apply(lambda s: float(s.notna().mean())).to_string())
print("  coverage of RAPM on the same rows, by season:")
print(f.groupby("season")["has_rapm"].mean().to_string())
both = f["m_pts"].notna() & f["has_rapm"]
print("  rows with BOTH: %.4f   RAPM only: %.4f   raw-box only: %.4f"
      % (both.mean(), (f["has_rapm"] & f["m_pts"].isna()).mean(),
         (~f["has_rapm"] & f["m_pts"].notna()).mean()))

# =============================================== V3 fill-source decomposition
B.hdr("A -- STEP 3 SURVIVOR: what is the V3 fill actually buying?")
PS_ATTR = (f.groupby(["season", "player_id"], sort=False)[RAPM_MAP_COLS].first().reset_index())
ps_codes = f.groupby(["season", "player_id"], sort=False).ngroup().to_numpy()
RELAB = B.PlayerSeasonRelabeller(ps_codes)
rng = np.random.default_rng(B.SEED)
SHUF = RELAB.draw(RELAB.block_values(f[RAPM_MAP_COLS].to_numpy(float)), rng)
for i, c in enumerate(RAPM_MAP_COLS):
    f["shuf_" + c] = SHUF[:, i]
MASTERCOL = {"pts": "m_pts", "minutes": "m_minutes", "fga": "m_fga", "ppm": "m_ppm"}

rows = []
draws_all = []
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    cellA, cellB = SEL[t]["A"], SEL[t]["B"]
    preds = {}
    for fold, cell in [(2023, cellA), (2024, cellB)]:
        mode = cell["mode"]
        legs = ([("minutes", "equal"), ("ppm", "ratio_of_prior_sums")]
                if (t == "pts" and mode == "composite") else [(t, mode)])
        pool = season < fold
        scored = season == fold
        leg = {}
        for (lt, lm) in legs:
            num, den = B.numden(f, lt, lm)
            tgts, _ = B.build_shrink_targets(f, num, den, bucket_role,
                                             float(num.sum() / den.sum()))
            d_ = pd.DataFrame({"season": season, "pid": f["player_id"].to_numpy(),
                               "n": num, "d": den})
            gsum = d_.groupby(["season", "pid"], sort=False)[["n", "d"]].sum()
            lvl = (gsum["n"] / gsum["d"].replace(0.0, np.nan)).rename("lvl").reset_index()
            lvl = lvl.merge(PS_ATTR.rename(columns={"player_id": "pid"}),
                            on=["season", "pid"], how="left")
            plv = lvl[lvl["season"] < fold].dropna(subset=["lvl"] + RAPM_MAP_COLS)

            def _map(cols, src_lvl=plv):
                A = np.column_stack([np.ones(len(src_lvl))]
                                    + [src_lvl[c].to_numpy(float) for c in cols])
                bt, *_ = np.linalg.lstsq(A, src_lvl["lvl"].to_numpy(float), rcond=None)
                Ar = np.column_stack([np.ones(len(f))]
                                     + [f[c].to_numpy(float) for c in cols])
                return Ar @ bt

            g_rapm = _map(RAPM_MAP_COLS)
            # shuffled-RAPM map: fit on the SAME pool but with relabelled attributes
            plv_s = lvl[lvl["season"] < fold].copy()
            for c in RAPM_MAP_COLS:
                pass
            g_shuf = np.column_stack([np.ones(len(f))]
                                     + [f["shuf_" + c].to_numpy(float)
                                        for c in RAPM_MAP_COLS])
            A0 = np.column_stack([np.ones(len(plv))]
                                 + [plv[c].to_numpy(float) for c in RAPM_MAP_COLS])
            b0, *_ = np.linalg.lstsq(A0, plv["lvl"].to_numpy(float), rcond=None)
            g_shuf = g_shuf @ b0

            league = tgts["league"]
            prior_raw = tgts["_prior_season_raw"]
            mcol = f[MASTERCOL[lt if len(legs) > 1 else t]].to_numpy(float)
            # raw prior-season box score, put on the leg's own scale by a pool-fitted 1-D map
            ok = plv.merge(
                f[["season", "player_id", MASTERCOL[lt if len(legs) > 1 else t]]]
                .drop_duplicates(["season", "player_id"])
                .rename(columns={"player_id": "pid"}), on=["season", "pid"], how="left")
            ok = ok.dropna(subset=[MASTERCOL[lt if len(legs) > 1 else t]])
            Am = np.column_stack([np.ones(len(ok)),
                                  ok[MASTERCOL[lt if len(legs) > 1 else t]].to_numpy(float)])
            bm, *_ = np.linalg.lstsq(Am, ok["lvl"].to_numpy(float), rcond=None)
            g_master = bm[0] + bm[1] * mcol
            g_both = None
            okb = ok.dropna(subset=RAPM_MAP_COLS)
            Ab = np.column_stack([np.ones(len(okb)),
                                  okb[MASTERCOL[lt if len(legs) > 1 else t]].to_numpy(float)]
                                 + [okb[c].to_numpy(float) for c in RAPM_MAP_COLS])
            bb, *_ = np.linalg.lstsq(Ab, okb["lvl"].to_numpy(float), rcond=None)
            g_both = (np.column_stack([np.ones(len(f)), np.nan_to_num(mcol, nan=np.nanmean(mcol))]
                                      + [f[c].to_numpy(float) for c in RAPM_MAP_COLS]) @ bb)

            FILLS = {
                "F0_league_D094": league,
                "F1_rapm": np.where(np.isfinite(g_rapm), g_rapm, league),
                "F2_raw_prev_box_master": np.where(np.isfinite(g_master), g_master, league),
                "F3_rapm_plus_raw_box": np.where(np.isfinite(g_both), g_both, league),
                "F4_negcontrol_shuffled_rapm": np.where(np.isfinite(g_shuf), g_shuf, league),
            }
            leg[(lt, lm)] = {
                "S": B.prior_sums(num, den, mins, starts, ns, float(cell["floor"]),
                                  (cell["memory_kind"], float(cell["memory_param"]))),
                "T": {k: np.where(np.isfinite(prior_raw), prior_raw, v)
                      for k, v in FILLS.items()}}
        for fname in ["F0_league_D094", "F1_rapm", "F2_raw_prev_box_master",
                      "F3_rapm_plus_raw_box", "F4_negcontrol_shuffled_rapm"]:
            best_k, best_m = None, np.inf
            for k in K_GRID:
                sh = ("none", 0.0) if k == 0.0 else ("custom", k)
                parts = [B.apply_shrink(*leg[L]["S"], {"custom": leg[L]["T"][fname],
                                                       "league": leg[L]["T"][fname],
                                                       "none": leg[L]["T"][fname]}, sh)
                         for L in leg]
                e = parts[0] if len(parts) == 1 else parts[0] * parts[1]
                m = B.mae(y[pool], e[pool])
                if m < best_m:
                    best_m, best_k = m, k
            sh = ("none", 0.0) if best_k == 0.0 else ("custom", best_k)
            parts = [B.apply_shrink(*leg[L]["S"], {"custom": leg[L]["T"][fname],
                                                   "league": leg[L]["T"][fname],
                                                   "none": leg[L]["T"][fname]}, sh)
                     for L in leg]
            e = parts[0] if len(parts) == 1 else parts[0] * parts[1]
            preds.setdefault(fname, np.full(len(f), np.nan))[scored] = e[scored]
    inc = f["ref_%s_V0_D094_exact" % t].to_numpy(float)
    M_WF = f["m_wf"].to_numpy(bool)
    M_POOR = M_WF & f["m_datapoor"].to_numpy(bool)
    for sname, mask in [("wf_eval_2023_24", M_WF), ("data_poor_wf", M_POOR)]:
        for fname, p in preds.items():
            sk_, ma, mb, n = B.skill(y[mask], p[mask], inc[mask])
            diff = np.abs(y[mask] - p[mask]) - np.abs(y[mask] - inc[mask])
            r, dr = B.block_signflip(diff, ps_codes[mask])
            rows.append({"analysis": "step3_V3_fill_decomposition_POSTHOC", "target": t,
                         "stratum": sname, "fill_source": fname, "n": n,
                         "mae": ma, "mae_D094_incumbent": mb, "skill_vs_D094": sk_,
                         "p_blockflip": r["p_two_sided_blockflip"]})
            if sname == "wf_eval_2023_24":
                for j, v in enumerate(dr):
                    draws_all.append({"test": "v3_fill_decomposition", "target": t,
                                      "fill_source": fname, "draw": j, "value": float(v)})
A = pd.DataFrame(rows)
for sname in ["wf_eval_2023_24", "data_poor_wf"]:
    print("\n  --- %s: skill vs D094's incumbent, by WHAT FILLS the missing prior season ---"
          % sname)
    print(A[A["stratum"] == sname].pivot(index="fill_source", columns="target",
                                         values="skill_vs_D094").to_string(
        float_format=lambda v: "%+.4f%%" % (100 * v)))
    print("  block sign-flip p:")
    print(A[A["stratum"] == sname].pivot(index="fill_source", columns="target",
                                         values="p_blockflip").to_string(
        float_format=lambda v: "%.4f" % v))

# =============================================== C3 decomposition
B.hdr("B -- STEP 4 SURVIVOR: is C3 recalibration, or RAPM?")
d = pd.read_parquet(os.path.join(B.OUT, "coldstart_frame.parquet"))
d = d.sort_values(["season", "player_id", "gdate"], kind="stable").reset_index(drop=True)
dseason = d["season"].to_numpy()
POOR = d["tier_poor"].to_numpy(bool) & np.isin(dseason, [2023, 2024])
lam_d = d["mp_prior_games"].to_numpy(float)
lam_d = lam_d / (lam_d + 2.0)
dps = d.groupby(["season", "player_id"], sort=False).ngroup().to_numpy()
DREL = B.PlayerSeasonRelabeller(dps)
rng2 = np.random.default_rng(B.SEED + 1)
TCOL = {"pts": "t_pts", "minutes": "t_minutes", "ppm": "t_ppm"}
rowsB = []
for t in ["pts", "minutes", "ppm"]:
    y = d[TCOL[t]].to_numpy(float)
    struct = d["struct_" + t].to_numpy(float)
    g = d["g_" + t].to_numpy(float)
    g_shuf = DREL.draw(DREL.block_values(np.nan_to_num(g)[:, None]), rng2)[:, 0]
    variants = {}
    for nm, extra in [("C3_full_rapm", g - struct),
                      ("C3_recalibration_only_NO_RAPM", None),
                      ("C3_negcontrol_shuffled_rapm", g_shuf - struct)]:
        out = np.full(len(d), np.nan)
        for S in [2023, 2024]:
            tr = (dseason < S) & d["tier_poor"].to_numpy(bool)
            te = dseason == S
            cols_tr = [np.ones(int(tr.sum())), struct[tr]]
            cols_te = [np.ones(int(te.sum())), struct[te]]
            if extra is not None:
                cols_tr.append(np.nan_to_num(extra[tr]))
                cols_te.append(np.nan_to_num(extra[te]))
            Atr = np.column_stack(cols_tr)
            yy = y[tr]
            ok = np.isfinite(yy) & np.isfinite(Atr).all(axis=1)
            bt, *_ = np.linalg.lstsq(Atr[ok], yy[ok], rcond=None)
            out[te] = np.column_stack(cols_te) @ bt
        variants[nm] = lam_d * d["own_" + t].to_numpy(float) + (1 - lam_d) * out
    inc = d["C0_" + t].to_numpy(float)
    for pname, mask in [("all_data_poor", POOR),
                        ("veteran_returning", POOR & (d["pop"] == "veteran_returning").to_numpy()),
                        ("true_rookie", POOR & (d["pop"] == "true_rookie").to_numpy())]:
        for nm, p in variants.items():
            sk_, ma, mb, n = B.skill(y[mask], p[mask], inc[mask])
            diff = np.abs(y[mask] - p[mask]) - np.abs(y[mask] - inc[mask])
            r, _ = B.block_signflip(diff, dps[mask])
            rowsB.append({"analysis": "step4_C3_decomposition_POSTHOC", "target": t,
                          "population": pname, "variant": nm, "n": n, "mae": ma,
                          "mae_D092_incumbent": mb, "skill_vs_D092": sk_,
                          "p_blockflip": r["p_two_sided_blockflip"]})
Bd = pd.DataFrame(rowsB)
for pname in ["all_data_poor", "veteran_returning", "true_rookie"]:
    print("\n  --- %s: skill vs D092's placeholder ---" % pname)
    print(Bd[Bd["population"] == pname].pivot(index="variant", columns="target",
                                              values="skill_vs_D092").to_string(
        float_format=lambda v: "%+.4f%%" % (100 * v)))
    print("  block sign-flip p:")
    print(Bd[Bd["population"] == pname].pivot(index="variant", columns="target",
                                              values="p_blockflip").to_string(
        float_format=lambda v: "%.4f" % v))

B.hdr("WRITE")
out = pd.concat([A, Bd], ignore_index=True, sort=False)
out.to_csv(os.path.join(B.OUT, "decomposition_posthoc.csv"), index=False)
print("  wrote decomposition_posthoc.csv (%d rows)" % len(out))
pd.DataFrame(draws_all).to_csv(os.path.join(B.OUT, "permutation_draws_decomposition.csv"),
                               index=False)
print("  wrote permutation_draws_decomposition.csv (%d draws)" % len(draws_all))
B.jdump({"v3_fill_decomposition": A.to_dict("records"),
         "c3_decomposition": Bd.to_dict("records")}, "_s05.json")
print("DONE s05")
