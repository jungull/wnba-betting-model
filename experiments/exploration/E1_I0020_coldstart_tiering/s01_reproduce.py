"""E1_I0020 STEP 1 -- REPRODUCE THE TWO ANCHORS BEFORE BUILDING ANYTHING ON THEM.

  ANCHOR A (D076 / E0_I0014): quintiles of pl_games_prior with the champion's MAE skill against the
      point-in-time prior-appearance-mean reference.  Published bottom quintile: minutes -15.1%,
      points -6.6%.
  ANCHOR B (D081 / E0_I0015): the cold-start splice.  Pooled points skill -0.22% -> +1.36% at
      threshold 3 prior appearances, p = 0.0010 by (season, player_id) block sign-flip.

  Both are recomputed HERE from the frozen frames and compared to the frozen published CSVs with
  ABSOLUTE deltas.  If either fails, this script raises and the screen stops.

  A negative control (noop placebo) and a partition value-test run first.
"""
import os

import numpy as np
import pandas as pd

import ct_base as B
import screenkit as sk

OUT = {}
B.hdr("STEP 1.0 -- PARTITION VALUE TEST AND MANIFEST STATUS OF EVERY INPUT")
for label, path in [("analysis_frame.parquet", B.FRAME), ("decomp_frame.parquet", B.DECOMP),
                    ("master_player.parquet", B.MASTER), ("player_bios.csv", B.BIOS)]:
    m = sk.check_manifest(path, verbose=False)
    print("  %-26s -> status=%-42s asof=%s fit_through=%s"
          % (label, m.get("status"), m.get("asof_granularity"), m.get("fit_through_season")))
    OUT.setdefault("manifests", {})[label] = {k: v for k, v in m.items()
                                              if k in ("status", "asof_granularity",
                                                       "fit_through_season", "verdict",
                                                       "manifest_path")}
print("""
  HONEST STATUS.  Three of the four inputs have NO sibling manifest and check_manifest therefore
  returns UNVERIFIABLE, which this program's rule says is NEVER a pass.  Two of them
  (analysis_frame, decomp_frame) are the FROZEN OUTPUTS of D076 and D081, whose own inputs were
  manifest-checked in those screens; they are re-verified here on COLUMN VALUES (assert_partition +
  explicit max-date assertion) rather than on a manifest.  player_bios.csv is verified structurally
  in s02 on column values.  master_player.parquet DOES have a manifest and it is row-granular.
""")

f = B.load_frame()
d = pd.read_parquet(B.DECOMP)
sk.assert_partition(d, verbose=False)
assert d["gdate"].max() < pd.Timestamp("2025-01-01")
print("  decomp_frame    shape=%s  seasons=%s" % (d.shape, sorted(d["season"].unique())))

# --------------------------------------------------------------------- ANCHOR A
B.hdr("STEP 1.1 -- ANCHOR A: D076 depth-quintile skill table")
q = pd.qcut(f["pl_games_prior"], 5, labels=False, duplicates="drop")
tab = f.assign(depth_quintile=q).groupby("depth_quintile").agg(
    n=("absres_minutes", "size"),
    median_prior_games=("pl_games_prior", "median"),
    mean_team_game_idx=("tm_game_idx", "mean"),
    mean_newfaces=("tm_newfaces_prior", "mean"),
    fallback_rate=("pts__is_fallback", "mean"),
    mae_minutes=("absres_minutes", "mean"),
    ref_mae_minutes=("refabs_minutes", "mean"),
    mae_pts=("absres_pts", "mean"),
    ref_mae_pts=("refabs_pts", "mean"),
)
tab["skill_minutes"] = 1 - tab["mae_minutes"] / tab["ref_mae_minutes"]
tab["skill_pts"] = 1 - tab["mae_pts"] / tab["ref_mae_pts"]
tab = tab.reset_index()
print(tab.to_string(index=False))

pub = pd.read_csv(os.path.join(B.D076, "depth_quintile_table.csv"))
cmpcols = ["n", "median_prior_games", "fallback_rate", "mae_minutes", "ref_mae_minutes",
           "mae_pts", "ref_mae_pts", "skill_minutes", "skill_pts"]
deltas = {}
print("\n  ABSOLUTE DELTAS vs the frozen published depth_quintile_table.csv:")
for c in cmpcols:
    dd = (tab[c].to_numpy(float) - pub[c].to_numpy(float))
    deltas[c] = float(np.max(np.abs(dd)))
    print("     %-18s max |delta| = %.3e" % (c, deltas[c]))
OUT["anchorA_max_abs_deltas"] = deltas
OUT["anchorA_table"] = tab.to_dict("records")
worst = max(deltas.values())
print("\n  WORST ABSOLUTE DELTA ACROSS THE WHOLE TABLE: %.3e" % worst)
assert worst < 1e-9, "ANCHOR A FAILED TO REPRODUCE -- STOP"
print("  ANCHOR A REPRODUCES EXACTLY (bottom quintile: minutes skill %+.4f, points skill %+.4f)"
      % (tab.loc[0, "skill_minutes"], tab.loc[0, "skill_pts"]))
B.wcsv(tab, "repro_depth_quintile_table.csv")

# --------------------------------------------------------------------- ANCHOR B
B.hdr("STEP 1.2 -- ANCHOR B: D081 cold-start splice")
y = d["y_pts"].to_numpy(float)
ref_pts = d["ref_pts"].to_numpy(float)
champ = d["pts__pred_point"].to_numpy(float)
gp = d["pl_games_prior"].to_numpy(float)
blocks = B.block_codes(d)

# reproduce D081's own block sign-flip machinery, independently reimplemented here
def block_signflip(diff, codes, n_draws=1000, seed=20260807):
    dv = np.asarray(diff, float)
    ok = np.isfinite(dv)
    dv = np.where(ok, dv, 0.0)
    uq, inv = np.unique(np.asarray(codes), return_inverse=True)
    nb = len(uq)
    bsum = np.bincount(inv, weights=dv, minlength=nb)
    n_ok = int(ok.sum())
    real = float(bsum.sum() / n_ok)
    rng = np.random.default_rng(seed)
    draws = np.empty(n_draws, float)
    for i in range(n_draws):
        s = rng.choice(np.array([-1.0, 1.0]), size=nb)
        draws[i] = float((bsum * s).sum() / n_ok)
    p = (1.0 + int((np.abs(draws) >= abs(real)).sum())) / (n_draws + 1.0)
    return real, float(p), float(draws.std(ddof=1))

rows = []
for thr in [0, 3, 5, 8, 10, 15, 20]:
    m = gp < thr
    yh = np.where(m, ref_pts, champ)
    s_pool, mm, mr = B.skill_mae(y, yh, ref_pts)
    s_kept = B.skill_mae(y[~m], champ[~m], ref_pts[~m])[0] if (~m).sum() > 50 else np.nan
    diff = np.abs(y - yh) - np.abs(y - champ)
    real, p, sd = block_signflip(diff, blocks, n_draws=1000)
    rows.append(dict(splice_threshold_prior_games=thr, n_spliced=int(m.sum()),
                     pct_spliced=100.0 * m.mean(), pooled_points_mae=mm,
                     pooled_skill_vs_ref=s_pool, skill_on_UNspliced_rows=s_kept,
                     p_vs_champion_blockflip=p))
rep = pd.DataFrame(rows)
print(rep.to_string(index=False))
pubB = pd.read_csv(os.path.join(B.D081, "coldstart_splice.csv"))
dB = {}
print("\n  ABSOLUTE DELTAS vs the frozen published coldstart_splice.csv:")
for c in ["n_spliced", "pct_spliced", "pooled_points_mae", "pooled_skill_vs_ref",
          "skill_on_UNspliced_rows", "p_vs_champion_blockflip"]:
    dd = rep[c].to_numpy(float) - pubB[c].to_numpy(float)
    dB[c] = float(np.nanmax(np.abs(dd)))
    print("     %-28s max |delta| = %.3e" % (c, dB[c]))
OUT["anchorB_max_abs_deltas"] = dB
OUT["anchorB_table"] = rep.to_dict("records")
assert dB["pooled_skill_vs_ref"] < 1e-9, "ANCHOR B FAILED TO REPRODUCE (skill) -- STOP"
assert dB["p_vs_champion_blockflip"] < 1e-12, "ANCHOR B FAILED TO REPRODUCE (p) -- STOP"
print("\n  ANCHOR B REPRODUCES EXACTLY: pooled points skill %+.6f -> %+.6f at threshold 3, p=%.4f"
      % (rep.loc[0, "pooled_skill_vs_ref"], rep.loc[1, "pooled_skill_vs_ref"],
         rep.loc[1, "p_vs_champion_blockflip"]))
B.wcsv(rep, "repro_coldstart_splice.csv")

# --------------------------------------------------------------------- the -18.6% fallback claim
B.hdr("STEP 1.3 -- THE 'FALLBACK ROWS SCORING -18.6%' CLAIM")
fb = d["pts__is_fallback"].to_numpy()
s_fb = B.skill_mae(y[fb], champ[fb], ref_pts[fb])
s_nfb = B.skill_mae(y[~fb], champ[~fb], ref_pts[~fb])
print("  fallback rows      n=%5d  champ MAE=%.4f  ref MAE=%.4f  skill=%+.4f"
      % (fb.sum(), s_fb[1], s_fb[2], s_fb[0]))
print("  non-fallback rows  n=%5d  champ MAE=%.4f  ref MAE=%.4f  skill=%+.4f"
      % ((~fb).sum(), s_nfb[1], s_nfb[2], s_nfb[0]))
OUT["fallback_rows"] = {"n": int(fb.sum()), "skill_pts": s_fb[0], "champ_mae": s_fb[1],
                        "ref_mae": s_fb[2]}
OUT["nonfallback_rows"] = {"n": int((~fb).sum()), "skill_pts": s_nfb[0]}
print("  (briefing said ~1,061 fallback rows scoring -18.6%%; measured n=%d, skill=%+.4f)"
      % (fb.sum(), s_fb[0]))

# --------------------------------------------------------------------- kit cross-check + placebo
B.hdr("STEP 1.4 -- KIT CROSS-CHECK AND NEGATIVE CONTROLS")
print("  screenkit.r2_of_forecast (scores as-is) vs screenkit.r2_plain (REFITS) on champion points:")
r_asis = B.r2f(y, champ)
r_refit = float(sk.r2_plain(y, champ.reshape(-1, 1)))
print("     r2_of_forecast = %.6f   r2_plain(REFIT) = %.6f   gap = %.6f"
      % (r_asis, r_refit, r_refit - r_asis))
OUT["champion_points_r2_of_forecast"] = r_asis
OUT["champion_points_r2_plain_REFIT"] = r_refit

print("\n  NEGATIVE CONTROL 1 -- paired_forecast_comparison of the champion WITH ITSELF:")
self_cmp, _ = B.paired(y, champ, champ, groups=blocks, name_a="champ", name_b="champ")
print("     dR2 = %.3e   p = %.6f   n=%d  n_groups=%d"
      % (self_cmp["dr2_a_minus_b"], self_cmp["p"], self_cmp["n"], self_cmp["n_groups"]))
assert self_cmp["p"] == 1.0 and abs(self_cmp["dr2_a_minus_b"]) < 1e-15
OUT["negctrl_self_comparison"] = {"dr2": self_cmp["dr2_a_minus_b"], "p": self_cmp["p"]}

print("\n  NEGATIVE CONTROL 2 -- noop_placebo on a statistic that ignores the permuted column:")
dd = d[["y_pts", "pts__pred_point", "pl_games_prior"]].copy()

def stat_ignores_feature(frame):
    return float(np.mean(np.abs(frame["y_pts"].to_numpy(float)
                                - frame["pts__pred_point"].to_numpy(float))))

np_res = sk.noop_placebo(stat_ignores_feature, dd, n_draws=200, verbose=True)
print("     observed sd across 200 draws = %.3e   n_distinct_draw_values = %s"
      % (np_res.get("sd"), np_res.get("n_distinct_draw_values")))
OUT["noop_placebo"] = {k: v for k, v in np_res.items() if k != "draws"}
if "draws" in np_res:
    pd.DataFrame({"draw": np_res["draws"]}).to_csv(
        os.path.join(B.OUT, "noop_placebo_draws.csv"), index=False)

print("\n  NEGATIVE CONTROL 3 -- a PURE-NOISE placeholder must not beat the champion:")
rng = np.random.default_rng(B.SEED)
noise = float(np.mean(y)) + rng.normal(0, float(np.std(y)), size=len(y))
nz, _ = B.paired(y, noise, champ, groups=blocks, name_a="pure_noise", name_b="champion")
print("     dR2(noise - champ) = %+.5f   p = %.4f  (must be strongly NEGATIVE)"
      % (nz["dr2_a_minus_b"], nz["p"]))
assert nz["dr2_a_minus_b"] < -0.2
OUT["negctrl_pure_noise"] = {"dr2": nz["dr2_a_minus_b"], "p": nz["p"]}

B.jdump(OUT, "_s01.json")
print("\nSTEP 1 COMPLETE -- BOTH ANCHORS REPRODUCE.")
