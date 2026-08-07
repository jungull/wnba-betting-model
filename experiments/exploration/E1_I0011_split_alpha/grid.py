"""E1 I0011 split-alpha -- compute the (efficiency alpha x exposure alpha) MAE grid.

Emits a TIDY metric table keyed by (target, form, alpha_eff, alpha_exp, cell) where
`cell` is an atomic evaluation unit (season, or season x half, or season x slice).
Every fold in folds.py is then an n-weighted pool of atomic cells, so no estimator
is ever recomputed and no fold can accidentally see a cell it did not ask for.

All estimators are strictly shifted within (player_id, season): the value used for
game t is built only from played games strictly before t. Eval gate n_prior >= 3
and minutes > 0 -- identical to props_edge.py's own gate.

FORMS
  PER36   EWMA_ar(pts/min*36) * EWMA_am(min) / 36        <- props_edge.py's form
                                                            (EWMA OF THE RATIO)
  RATE36  (EWMA_ar(pts)/EWMA_ar(min)) * EWMA_am(min)     <- ratio of EWMAs
  PER100  EWMA_ar(pts/poss*100) * EWMA_ap(poss) / 100
  RATE100 (EWMA_ar(pts)/EWMA_ar(poss)) * EWMA_ap(poss)
  TOT     EWMA_a(pts)                                     <- single channel, no split
  STD     expanding mean of pts                           <- the naive default

alpha == 0.0 is the sentinel for the expanding (season-to-date) mean, i.e. alpha->0.
PARTITION: 2021-2024 only.
"""
import numpy as np
import pandas as pd

SEED = 20260807
PARTITION = [2021, 2022, 2023, 2024]
HERE = (r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees"
        r"\player-model-program\experiments\exploration\E1_I0011_split_alpha")

ALPHAS = [0.00, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15,
          0.20, 0.25, 0.30, 0.40, 0.50, 0.70]
TARGETS = ["pts", "reb", "ast"]
MIN_PRIOR = 3

df = pd.read_parquet(HERE + r"\frame.parquet")
if not set(df["season"].unique()) <= set(PARTITION):
    raise SystemExit(f"PARTITION VIOLATION {sorted(df['season'].unique())}")
print("[partition-check] frame:", sorted(int(x) for x in df["season"].unique()), df.shape)

df = df.sort_values(["player_id", "season", "game_date", "game_id"]).reset_index(drop=True)
KEY = ["player_id", "season"]
gk = [df["player_id"], df["season"]]


def sh(col):
    return df.groupby(KEY, sort=False)[col].shift(1)


def smooth(s, alpha):
    """alpha == 0 -> expanding (season-to-date) mean; else EWMA, adjust=True
    (house convention, features/common.py, as used by props_edge.py)."""
    if alpha == 0.0:
        return s.groupby(gk, sort=False).transform(
            lambda x: x.expanding(min_periods=1).mean()).values.astype(float)
    return s.groupby(gk, sort=False).transform(
        lambda x: x.ewm(alpha=alpha, adjust=True, ignore_na=True).mean()).values.astype(float)


# ---------------------------------------------------------------- exposure channels
sh_min = sh("minutes")
sh_poss = sh("possessions")
E_MIN = {a: smooth(sh_min, a) for a in ALPHAS}
E_POSS = {a: smooth(sh_poss, a) for a in ALPHAS}
print("exposure channels built")

# ------------------------------------------------------------------- atomic cells
mask_eval = ((df["n_prior"] >= MIN_PRIOR) & (df["minutes"] > 0)).values

# usage terciles: cut PER TRAIN-FOLD in folds.py would be ideal, but the tercile
# edges are a nuisance constant with negligible selection power; they are cut here
# on the EARLIEST season only (2021) so no scored season defines its own slice edges.
u21 = df.loc[mask_eval & (df["season"] == 2021).values, "std_usage"].dropna()
Q1, Q2 = float(u21.quantile(1 / 3)), float(u21.quantile(2 / 3))
print(f"usage terciles cut on season 2021 ONLY: q33={Q1:.4f} q67={Q2:.4f}")

slices = {
    "ALL": np.ones(len(df), bool),
    "S1_starter1": (df["starter_flag"] == 1).values,
    "S1_starter0": (df["starter_flag"] == 0).values,
    "S2_min_lt15": (df["std_minutes"] < 15).values,
    "S2_min_15_25": ((df["std_minutes"] >= 15) & (df["std_minutes"] < 25)).values,
    "S2_min_ge25": (df["std_minutes"] >= 25).values,
    "S3_usage_low": (df["std_usage"] < Q1).values,
    "S3_usage_mid": ((df["std_usage"] >= Q1) & (df["std_usage"] < Q2)).values,
    "S3_usage_high": (df["std_usage"] >= Q2).values,
}

cells = {}
for s in PARTITION:
    ms = (df["season"] == s).values
    for sl, msl in slices.items():
        cells[(s, 0, sl)] = np.where(mask_eval & ms & msl)[0]
    for h in (1, 2):                      # within-season temporal halves (ALL slice only)
        cells[(s, h, "ALL")] = np.where(mask_eval & ms & (df["half"] == h).values)[0]
cells = {k: v for k, v in cells.items() if len(v) >= 100}
print(f"{len(cells)} atomic evaluation cells (>=100 rows each)")

cell_keys = list(cells.keys())
cell_idx = [cells[k] for k in cell_keys]


def eval_all(pred, y):
    """Return (n, mae) per atomic cell for one prediction vector."""
    ae = np.abs(pred - y)
    out = []
    for ix in cell_idx:
        v = ae[ix]
        ok = np.isfinite(v)
        out.append((int(ok.sum()), float(v[ok].mean()) if ok.any() else np.nan))
    return out


rows = []


def record(tgt, form, ar, ax, pred, y):
    for (s, h, sl), (n, mae) in zip(cell_keys, eval_all(pred, y)):
        rows.append((tgt, form, ar, ax, s, h, sl, n, mae))


for tgt in TARGETS:
    print(f"\n=== target={tgt} ===")
    y = df[tgt].astype(float).values
    sh_y = sh(tgt)
    E_Y = {a: smooth(sh_y, a) for a in ALPHAS}

    per36 = df[tgt].astype(float) / df["minutes"] * 36.0
    poss_safe = df["possessions"].where(df["possessions"] > 0)
    per100 = df[tgt].astype(float) / poss_safe * 100.0
    df["_p36"], df["_p100"] = per36, per100
    E_P36 = {a: smooth(sh("_p36"), a) for a in ALPHAS}
    E_P100 = {a: smooth(sh("_p100"), a) for a in ALPHAS}
    df.drop(columns=["_p36", "_p100"], inplace=True)

    # single-channel references (no split possible)
    record(tgt, "STD", np.nan, np.nan, E_Y[0.00], y)
    for a in ALPHAS:
        if a > 0:
            record(tgt, "TOT", a, a, E_Y[a], y)

    with np.errstate(divide="ignore", invalid="ignore"):
        for ar in ALPHAS:
            p36r, p100r, yr = E_P36[ar], E_P100[ar], E_Y[ar]
            d36 = np.where(E_MIN[ar] > 0, E_MIN[ar], np.nan)
            d100 = np.where(E_POSS[ar] > 0, E_POSS[ar], np.nan)
            for ax in ALPHAS:
                record(tgt, "PER36", ar, ax, p36r * E_MIN[ax] / 36.0, y)
                record(tgt, "RATE36", ar, ax, (yr / d36) * E_MIN[ax], y)
                record(tgt, "PER100", ar, ax, p100r * E_POSS[ax] / 100.0, y)
                record(tgt, "RATE100", ar, ax, (yr / d100) * E_POSS[ax], y)
    print(f"  done ({len(rows)} metric rows so far)")

met = pd.DataFrame(rows, columns=["target", "form", "alpha_eff", "alpha_exp",
                                  "season", "half", "slice", "n", "mae"])
met.to_parquet(HERE + r"\grid_metrics.parquet", index=False)
print("\nwrote grid_metrics.parquet", met.shape)
print("seasons present in metric table:", sorted(met['season'].unique()))
