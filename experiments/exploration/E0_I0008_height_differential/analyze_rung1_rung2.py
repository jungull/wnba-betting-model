"""
E0 I0008 -- analysis for RUNG 1 (whole-roster opponent height) and RUNG 2 (top-8 rotation
opponent height). No sklearn/scipy available in this env; correlations computed with numpy,
and "beyond own recent rate" tested via manual OLS (numpy.linalg.lstsq) comparing a
height-diff-only model to a height-diff + own-recent-rate model, plus a simple
median-split-on-own-recent-rate bucket check as a second, assumption-light way to see the
same thing (mirrors the bucket approach I0003 used).
"""
import pandas as pd
import numpy as np

OUT = "experiments/exploration/E0_I0008_height_differential"
df = pd.read_csv(f"{OUT}/player_game_height_vs_opponent.csv")
print("loaded:", df.shape)


def corr(a, b):
    m = a.notna() & b.notna()
    if m.sum() < 30:
        return np.nan, m.sum()
    return np.corrcoef(a[m], b[m])[0, 1], m.sum()


def ols_r2(y, X_cols, data):
    sub = data.dropna(subset=[y] + X_cols)
    Y = sub[y].values
    X = np.column_stack([np.ones(len(sub))] + [sub[c].values for c in X_cols])
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    pred = X @ beta
    ss_res = np.sum((Y - pred) ** 2)
    ss_tot = np.sum((Y - Y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return dict(zip(["intercept"] + X_cols, beta)), r2, len(sub)


print("\n=== RUNG 1: player height - opponent WHOLE-ROSTER weighted mean height ===")
for target, own in [("offensive_rebound_percentage", "own_recent_oreb_pct"),
                     ("defensive_rebound_percentage", "own_recent_dreb_pct")]:
    r, n = corr(df["rung1_height_diff"], df[target])
    print(f"  raw corr(rung1_height_diff, {target}) = {r:.4f}  (n={n})")

    beta_h, r2_h, n_h = ols_r2(target, ["rung1_height_diff"], df)
    beta_ho, r2_ho, n_ho = ols_r2(target, ["rung1_height_diff", own], df)
    beta_o, r2_o, n_o = ols_r2(target, [own], df)
    print(f"    OLS height-only:            R2={r2_h:.4f}  coef(height_diff)={beta_h['rung1_height_diff']:.5f}  n={n_h}")
    print(f"    OLS own-rate-only:          R2={r2_o:.4f}  coef({own})={beta_o[own]:.5f}  n={n_o}")
    print(f"    OLS height + own-rate:      R2={r2_ho:.4f}  coef(height_diff)={beta_ho['rung1_height_diff']:.5f}  coef(own)={beta_ho[own]:.5f}  n={n_ho}")
    print(f"    incremental R2 from adding height_diff to own-rate model: {r2_ho - r2_o:.5f}")

print("\n=== RUNG 2: player height - opponent TOP-8 ROTATION weighted mean height ===")
for target, own in [("offensive_rebound_percentage", "own_recent_oreb_pct"),
                     ("defensive_rebound_percentage", "own_recent_dreb_pct")]:
    r, n = corr(df["rung2_height_diff"], df[target])
    print(f"  raw corr(rung2_height_diff, {target}) = {r:.4f}  (n={n})")

    beta_h, r2_h, n_h = ols_r2(target, ["rung2_height_diff"], df)
    beta_ho, r2_ho, n_ho = ols_r2(target, ["rung2_height_diff", own], df)
    beta_o, r2_o, n_o = ols_r2(target, [own], df)
    print(f"    OLS height-only:            R2={r2_h:.4f}  coef(height_diff)={beta_h['rung2_height_diff']:.5f}  n={n_h}")
    print(f"    OLS own-rate-only:          R2={r2_o:.4f}  coef({own})={beta_o[own]:.5f}  n={n_o}")
    print(f"    OLS height + own-rate:      R2={r2_ho:.4f}  coef(height_diff)={beta_ho['rung2_height_diff']:.5f}  coef(own)={beta_ho[own]:.5f}  n={n_ho}")
    print(f"    incremental R2 from adding height_diff to own-rate model: {r2_ho - r2_o:.5f}")

print("\n=== bucket check: median-split on own_recent rate, then within-bucket corr(height_diff, target) ===")
for target, own, hcol in [
    ("offensive_rebound_percentage", "own_recent_oreb_pct", "rung1_height_diff"),
    ("defensive_rebound_percentage", "own_recent_dreb_pct", "rung1_height_diff"),
]:
    sub = df.dropna(subset=[target, own, hcol]).copy()
    med = sub[own].median()
    lo = sub[sub[own] <= med]
    hi = sub[sub[own] > med]
    r_lo, n_lo = corr(lo[hcol], lo[target])
    r_hi, n_hi = corr(hi[hcol], hi[target])
    print(f"  {target} (rung1): low-own-rate bucket corr={r_lo:.4f} (n={n_lo}); high-own-rate bucket corr={r_hi:.4f} (n={n_hi})")

print("\n=== position split (rung1), DREB% only ===")
for pos in df["position"].dropna().unique():
    sub = df[df["position"] == pos]
    r, n = corr(sub["rung1_height_diff"], sub["defensive_rebound_percentage"])
    print(f"  position={pos!r}: corr={r:.4f} n={n}")

print("\n=== season-by-season stability (rung1, DREB%) ===")
for season in sorted(df["season"].unique()):
    sub = df[df["season"] == season]
    r, n = corr(sub["rung1_height_diff"], sub["defensive_rebound_percentage"])
    print(f"  season={season}: corr={r:.4f} n={n}")

print("\nDONE analyze_rung1_rung2")
