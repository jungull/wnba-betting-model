"""E1 I0011 -- addendum for COORDINATOR #04.

QUESTION: is the corrected own-recent-rate baseline close to, or materially
different from, a leave-one-out / expanding SEASON RATE of the kind idea I0009
measured its incremental R-squared against?

Answered in I0009's own currency (R-squared on the player-game target) as well as
in MAE, so the coordinator can read the size of any revision directly.

Baselines compared, all on the identical eval universe (2021-2024, minutes > 0,
n_prior >= 3):

  LOO_SEASON_TOTAL   leave-one-out full-season mean of the per-game total,
                     (season_sum - y_t) / (n - 1). I0009's `player_tendency_loo`
                     form. NOT pregame-observable -- it uses the player's later
                     games -- so it flatters itself relative to anything causal.
  LOO_PER36_x_MIN    the same leave-one-out idea applied per channel:
                     LOO(per-36 rate) * LOO(minutes) / 36.
  EXPANDING_TOTAL    season-to-date mean of the per-game total. The pregame-
                     observable expanding rate; I0009's E1 rebuilt this class and
                     reported it retained 96.2% of the effect.
  EXPANDING_BOTH     expanding per-36 rate * expanding minutes / 36 -- i.e. the
                     corrected baseline's functional form with BOTH channels slow.
                     This is the sharpest test of the coordinator's hypothesis,
                     because it differs from the corrected baseline ONLY in the
                     exposure alpha.
  CORRECTED          the E1 deliverable: alpha_eff = 0.03, alpha_exp = 0.30.
  INCUMBENT          props_edge.py, alpha 0.30 on both channels.

PARTITION: 2021-2024 only.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "baseline"))
from corrected_baseline import CorrectedOwnRateBaseline  # noqa: E402

PARTITION = [2021, 2022, 2023, 2024]
TARGETS = ["pts", "reb", "ast"]

df = pd.read_parquet(os.path.join(HERE, "frame.parquet"))
if not set(df["season"].unique()) <= set(PARTITION):
    raise SystemExit("PARTITION VIOLATION")
print("[partition-check] seasons:", sorted(int(x) for x in df["season"].unique()))
df = df.sort_values(["player_id", "season", "game_date", "game_id"]).reset_index(drop=True)
KEY = ["player_id", "season"]

BASE = CorrectedOwnRateBaseline(0.03, 0.30)
INC = CorrectedOwnRateBaseline(0.30, 0.30)
EXPBOTH = CorrectedOwnRateBaseline(0.00, 0.00)


def loo(col):
    """Leave-one-out full-season mean within (player_id, season)."""
    g = df.groupby(KEY, sort=False)[col]
    s, n = g.transform("sum"), g.transform("count")
    return (s - df[col]) / (n - 1)


rows = []
print("\n" + "=" * 104)
print("BASELINE COMPARISON, pooled 2021-2024 eval universe. R2 is in I0009's currency.")
print("=" * 104)
for tgt in TARGETS:
    y = df[tgt].astype(float)
    npri = BASE.n_prior(df, tgt)
    m = ((npri >= 3) & (df["minutes"] > 0)).values

    df["_p36"] = y / df["minutes"] * 36.0
    cand = {
        "LOO_SEASON_TOTAL": loo(tgt),
        "LOO_PER36_x_MIN": loo("_p36") * loo("minutes") / 36.0,
        "EXPANDING_TOTAL": df.groupby(KEY, sort=False)[tgt].shift(1)
                             .groupby([df["player_id"], df["season"]], sort=False)
                             .transform(lambda x: x.expanding(min_periods=1).mean()),
        "EXPANDING_BOTH": EXPBOTH.project(df, tgt),
        "CORRECTED": BASE.project(df, tgt),
        "INCUMBENT": INC.project(df, tgt),
    }
    df.drop(columns=["_p36"], inplace=True)

    yv = y.values[m]
    sst = float(((yv - yv.mean()) ** 2).sum())
    res = {}
    for nm, p in cand.items():
        pv = np.asarray(p, dtype=float)[m]
        ok = np.isfinite(pv)
        e = pv[ok] - yv[ok]
        res[nm] = dict(n=int(ok.sum()), mae=float(np.abs(e).mean()),
                       r2=1.0 - float((e ** 2).sum()) / float(((yv[ok] - yv[ok].mean()) ** 2).sum()))
    print(f"\n--- {tgt} --- (n = {res['CORRECTED']['n']}, SST about the eval-set mean)")
    print(f"{'baseline':<20}{'n':>7}{'MAE':>10}{'R2':>9}"
          f"{'CORRECTED - this (dR2)':>25}{'CORRECTED vs this (MAE%)':>27}")
    c = res["CORRECTED"]
    for nm in cand:
        r = res[nm]
        d_r2 = c["r2"] - r["r2"]
        d_mae = 100 * (r["mae"] - c["mae"]) / r["mae"]
        print(f"{nm:<20}{r['n']:>7}{r['mae']:>10.4f}{r['r2']:>9.4f}"
              f"{d_r2:>+25.4f}{d_mae:>+27.3f}")
        rows.append(dict(target=tgt, baseline=nm, n=r["n"], mae=r["mae"], r2=r["r2"],
                         corrected_minus_this_r2=d_r2, corrected_vs_this_mae_pct=d_mae))

out = pd.DataFrame(rows)
out.to_csv(os.path.join(HERE, "i0009_baseline_delta.csv"), index=False)

print("\n" + "=" * 104)
print("VERDICT FOR COORDINATOR #04")
print("=" * 104)
verdict = {}
for tgt in TARGETS:
    d = out[out.target == tgt].set_index("baseline")
    eb = d.loc["EXPANDING_BOTH"]
    lo = d.loc["LOO_SEASON_TOTAL"]
    et = d.loc["EXPANDING_TOTAL"]
    print(f"\n{tgt}:")
    print(f"  corrected R2 {d.loc['CORRECTED', 'r2']:.4f}  vs  expanding-both R2 "
          f"{eb.r2:.4f}  -> dR2 {eb.corrected_minus_this_r2:+.4f} "
          f"({100 * eb.corrected_minus_this_r2 / max(eb.r2, 1e-9):+.1f}% of the "
          f"expanding baseline's own R2)")
    print(f"  vs LOO season total   R2 {lo.r2:.4f} -> dR2 "
          f"{lo.corrected_minus_this_r2:+.4f}")
    print(f"  vs expanding total    R2 {et.r2:.4f} -> dR2 "
          f"{et.corrected_minus_this_r2:+.4f}")
    verdict[tgt] = dict(
        r2_corrected=float(d.loc["CORRECTED", "r2"]),
        r2_expanding_both=float(eb.r2), r2_loo_season_total=float(lo.r2),
        r2_expanding_total=float(et.r2),
        dr2_vs_expanding_both=float(eb.corrected_minus_this_r2),
        dr2_vs_loo_season_total=float(lo.corrected_minus_this_r2),
        dr2_vs_expanding_total=float(et.corrected_minus_this_r2),
        mae_pct_vs_expanding_both=float(eb.corrected_vs_this_mae_pct),
        mae_pct_vs_loo_season_total=float(lo.corrected_vs_this_mae_pct),
        mae_pct_vs_expanding_total=float(et.corrected_vs_this_mae_pct))
with open(os.path.join(HERE, "i0009_baseline_delta.json"), "w", encoding="utf-8") as fh:
    json.dump(verdict, fh, indent=2)
print("\nwrote i0009_baseline_delta.csv / .json")
