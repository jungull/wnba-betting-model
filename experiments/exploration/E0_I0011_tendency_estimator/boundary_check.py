"""E0 I0011 -- boundary probe.

The selected RATE/EFFICIENCY alpha came out at 0.05, the FLOOR of the main grid.
A "tuned" horizon sitting on the edge of its own grid is not a tuned horizon, so
this probe extends the efficiency-alpha grid downward (and adds the expanding
mean of the rate, alpha -> 0) with the exposure alpha held at the values the main
run selected. Selection is still on 2021-2022 ONLY; 2023/2024 are scored, never
consulted for selection.

PARTITION: 2021-2024 only (input frame is already filtered; re-asserted).
"""
import numpy as np
import pandas as pd

PARTITION = [2021, 2022, 2023, 2024]
SELECT = [2021, 2022]
HERE = (r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees"
        r"\player-model-program\experiments\exploration\E0_I0011_tendency_estimator")

RATE_ALPHAS = [0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30]
EXPOSURE = {"pts": 0.25, "reb": 0.30, "ast": 0.30}

df = pd.read_parquet(HERE + r"\frame.parquet")
assert set(df["season"].unique()) <= set(PARTITION), df["season"].unique()
print("[partition-check] frame:", sorted(df["season"].unique()), df.shape)
df = df.sort_values(["player_id", "season", "game_date", "game_id"]).reset_index(drop=True)
KEY = ["player_id", "season"]
gk = [df["player_id"], df["season"]]
mask = (df["n_prior"] >= 3) & (df["minutes"] > 0)

rows = []
for tgt, am in EXPOSURE.items():
    y = df[tgt].astype(float)
    df["_r"] = y / df["minutes"] * 36.0
    sh_r = df.groupby(KEY, sort=False)["_r"].shift(1)
    sh_m = df.groupby(KEY, sort=False)["minutes"].shift(1)
    ewm_m = sh_m.groupby(gk, sort=False).transform(
        lambda x: x.ewm(alpha=am, adjust=True, ignore_na=True).mean())
    cand = {}
    for a in RATE_ALPHAS:
        e = sh_r.groupby(gk, sort=False).transform(
            lambda x: x.ewm(alpha=a, adjust=True, ignore_na=True).mean())
        cand[f"a{a:.2f}"] = e * ewm_m / 36.0
    e = sh_r.groupby(gk, sort=False).transform(lambda x: x.expanding(min_periods=1).mean())
    cand["a->0 (expanding mean of rate)"] = e * ewm_m / 36.0

    print(f"\n--- {tgt} --- exposure alpha held at {am} (value selected in main run)")
    print(f"{'efficiency alpha':<32}{'SELECT 21-22 MAE':>18}{'2023 MAE':>10}{'2024 MAE':>10}")
    for nm, pred in cand.items():
        out = {}
        for lab, ss in [("sel", SELECT), ("2023", [2023]), ("2024", [2024])]:
            m = mask & df["season"].isin(ss) & pred.notna() & y.notna()
            out[lab] = float(np.abs(pred[m] - y[m]).mean())
        print(f"{nm:<32}{out['sel']:>18.4f}{out['2023']:>10.4f}{out['2024']:>10.4f}")
        rows.append(dict(target=tgt, exposure_alpha=am, efficiency_alpha=nm,
                         mae_select=out["sel"], mae_2023=out["2023"], mae_2024=out["2024"]))
    df.drop(columns=["_r"], inplace=True)

pd.DataFrame(rows).to_csv(HERE + r"\boundary_check.csv", index=False)
print("\nwrote boundary_check.csv")
