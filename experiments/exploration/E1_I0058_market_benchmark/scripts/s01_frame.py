"""s01_frame.py -- build the analysis frame under PREREG.sha256, and PROVE zero holdout leak.

Order of operations is the point:  PARTITION FILTER FIRST, then everything else.
Every row that enters any computation is counted, and its season is asserted.
"""
from __future__ import annotations
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mb_base as mb  # noqa: E402
import screenkit as sk  # noqa: E402

L = mb.Tee(os.path.join(mb.EXP_DIR, "run_log_s01.txt"))
PRE = open(os.path.join(mb.EXP_DIR, "PREREG.sha256")).read().split()[0]
L(f"E1_I0058 s01 -- frame construction under PREREG {PRE}")
L("=" * 92)

SEASON = mb.PROPS_EXPLORATION_SEASON
LEAK = {}   # every leak counter recorded here goes into PARTITION_PROOF.md

# ============================================================================================
L("")
L("--- A. PARTITION FILTER, APPLIED BEFORE ANY OTHER OPERATION ----------------------------")
raw = pd.read_csv(mb.PROPS_CSV, low_memory=False)
raw["commence_ts"] = pd.to_datetime(raw.commence_time, utc=True)
raw["yr"] = raw.commence_ts.dt.year
LEAK["props_rows_total"] = int(len(raw))
LEAK["props_rows_by_commence_year"] = {int(k): int(v) for k, v in
                                       raw.yr.value_counts().sort_index().items()}
del raw

h = mb.load_props_raw()
m = mb.load_master(SEASON)                       # <-- season filter inside the loader
LEAK["master_seasons_after_filter"] = sorted(int(x) for x in m.season.unique())
assert LEAK["master_seasons_after_filter"] == [SEASON]

g_ok = set(m.gid)
hp = h[h.gid.isin(g_ok)].copy()
hp_years = sorted(int(x) for x in hp.commence_ts.dt.year.unique())
LEAK["props_rows_admitted"] = int(len(hp))
LEAK["props_rows_excluded_as_holdout_or_later"] = int(len(h) - len(hp))
LEAK["admitted_props_commence_years"] = hp_years
assert hp_years == [SEASON], f"HOLDOUT LEAK: {hp_years}"
for s in mb.HOLDOUT_SEASONS:
    assert s not in hp_years
L(f"  props rows total {len(h)} -> admitted {len(hp)} "
  f"(excluded {len(h) - len(hp)} = every 2025 and 2026 row, plus 2024 rows without a "
  f"season-2024 master game)")
L(f"  admitted commence years: {hp_years}  (assert == [{SEASON}] PASSED)")
L(f"  master rows admitted: {len(m)}; seasons {LEAK['master_seasons_after_filter']}")

# ============================================================================================
L("")
L("--- B. sigma(.) CALIBRATION, seasons 2021-2023 ONLY (PREREG 3.3) -----------------------")
cal = pd.read_parquet(mb.MASTER, columns=["season", "player_id", "minutes", "pts"])
cal_years = (2021, 2022, 2023)
cal = cal[cal.season.isin(cal_years) & (cal.minutes.fillna(0) > 0)]
LEAK["sigma_calibration_seasons"] = sorted(int(x) for x in cal.season.unique())
assert set(LEAK["sigma_calibration_seasons"]) <= set(mb.EXPLORATION_SEASONS)
assert SEASON not in LEAK["sigma_calibration_seasons"], "2024 outcomes must not calibrate sigma"
ps = cal.groupby(["season", "player_id"]).pts.agg(["mean", "std", "count"])
ps = ps[ps["count"] >= 10].dropna()
X = np.column_stack([np.ones(len(ps)), np.sqrt(ps["mean"].values)])
a_b, *_ = np.linalg.lstsq(X, ps["std"].values, rcond=None)
SIG_A, SIG_B = float(a_b[0]), float(a_b[1])
L(f"  player-seasons used: {len(ps)} (seasons {LEAK['sigma_calibration_seasons']}, >=10 played games)")
L(f"  FROZEN:  sigma(x) = {SIG_A:.6f} + {SIG_B:.6f} * sqrt(x),  clipped to [1.0, 15.0]")
L(f"  sanity:  sigma(5)={np.clip(SIG_A + SIG_B * np.sqrt(5), 1, 15):.3f}  "
  f"sigma(10)={np.clip(SIG_A + SIG_B * np.sqrt(10), 1, 15):.3f}  "
  f"sigma(20)={np.clip(SIG_A + SIG_B * np.sqrt(20), 1, 15):.3f}")
L("  NOTE: 2021-2023 outcomes are exploration-partition. No 2024 outcome and no props row")
L("        of any year entered this fit.")


def sigma(x):
    return np.clip(SIG_A + SIG_B * np.sqrt(np.maximum(np.asarray(x, float), 0.0)), 1.0, 15.0)


# ============================================================================================
L("")
L("--- C. BOOK-LEVEL PRICES -> de-vig -> per-book mu (PREREG 3.1-3.4) ---------------------")
last = (hp.sort_values(["snap_ts", "bookmaker_key"])
          .groupby(["gid", "pn", "bookmaker_key"]).tail(1)).copy()
L(f"  latest pre-tip snapshot per (game, player, book): {len(last)} rows")
L(f"  lead time (h) of the used snapshot: median {last.lead_h.median():.3f} "
  f"p10 {last.lead_h.quantile(.1):.3f} p90 {last.lead_h.quantile(.9):.3f} min {last.lead_h.min():.3f}")
before = len(last)
last = last[last.line.notna() & last.over_price.notna() & last.under_price.notna()]
L(f"  dropped {before - len(last)} book rows with an incomplete two-sided price")

po_raw = mb.american_to_prob(last.over_price.values)
pu_raw = mb.american_to_prob(last.under_price.values)
last["overround"] = po_raw + pu_raw - 1.0
L(f"  overround: mean {last.overround.mean():.4f} median {last.overround.median():.4f} "
  f"p05 {last.overround.quantile(.05):.4f} p95 {last.overround.quantile(.95):.4f}")
neg = (last.overround < 0).sum()
L(f"  book rows with a NEGATIVE overround (arbitrage-looking, kept): {neg}")

po_p, _ = mb.devig_proportional(po_raw, pu_raw)
po_a, _ = mb.devig_additive(po_raw, pu_raw)
last["p_over_fair_prop"] = po_p
last["p_over_fair_add"] = np.clip(po_a, 1e-6, 1 - 1e-6)
last["sig"] = sigma(last.line.values)
last["mu_prop"] = last.line.values + last.sig.values * mb.norm_ppf(np.clip(po_p, 1e-6, 1 - 1e-6))
last["mu_add"] = last.line.values + last.sig.values * mb.norm_ppf(last.p_over_fair_add.values)
L(f"  p_over_fair (proportional): mean {last.p_over_fair_prop.mean():.4f} "
  f"p05 {last.p_over_fair_prop.quantile(.05):.4f} p95 {last.p_over_fair_prop.quantile(.95):.4f}")
L(f"  per-book mu - line: mean {(last.mu_prop - last.line).mean():+.4f} "
  f"sd {(last.mu_prop - last.line).std():.4f} "
  f"p05 {(last.mu_prop - last.line).quantile(.05):+.4f} "
  f"p95 {(last.mu_prop - last.line).quantile(.95):+.4f}")

cons = last.groupby(["gid", "pn"]).agg(
    M1=("line", "median"), line_sd=("line", "std"), n_books=("line", "size"),
    M2=("mu_prop", "mean"), M3=("mu_add", "mean"),
    p_over_fair=("p_over_fair_prop", "mean"),
    overround=("overround", "mean"), lead_h=("lead_h", "median")).reset_index()
cons["line_sd"] = cons.line_sd.fillna(0.0)
L(f"  consensus obligations (game x player): {len(cons)}")

# ============================================================================================
L("")
L("--- D. JOIN TO OUTCOMES AND TO THE MODEL ANCHOR ----------------------------------------")
J = m.merge(cons, on=["gid", "pn"], how="inner")
L(f"  joined to master: {len(J)}")
J = J[J.minutes.fillna(0) > 0].copy()
L(f"  played rows (PREREG 1.2): {len(J)}")

d1, p1 = mb.load_anchor(mb.ANCHOR_PRIMARY)
d2, p2 = mb.load_anchor(mb.ANCHOR_SECONDARY)
for tag, pth in (("F1", p1), ("F2", p2)):
    rec = mb.verify_manifest(pth)
    L(f"  {tag} manifest re-verified at analysis time: match={rec['match']} "
      f"sha256={rec['sha256_recomputed'][:16]}...")
J = J.merge(d1[["row_uid", "pred_point", "pred_sd", "fallback_level", "is_fallback",
                "component_id", "n_prior_games", "forecast_cutoff", "feature_asof"]]
            .rename(columns={"pred_point": "F1"}), on="row_uid", how="inner")
L(f"  after PRIMARY anchor join: {len(J)}")
J = J.merge(d2[["row_uid", "pred_point"]].rename(columns={"pred_point": "F2"}),
            on="row_uid", how="left")
L(f"  F2 (robustness anchor) present on {J.F2.notna().sum()} of {len(J)} rows")

mn = pd.read_parquet(os.path.join(mb.ANCHOR_PRIMARY,
                                  "predictions__e_minutes_given_active__2024.parquet"),
                     columns=["row_uid", "pred_point"]).rename(columns={"pred_point": "min_hat"})
J = J.merge(mn, on="row_uid", how="left")
L(f"  pregame minutes forecast (for subgroup S1) present on {J.min_hat.notna().sum()} rows")

J["pts"] = J.pts.astype(float)
L(f"  anchor fallback on the admitted rows: level {J.fallback_level.value_counts().to_dict()}; "
  f"share {J.is_fallback.mean():.4f}  (vs 0.2801 on the whole 2024 anchor -- the priced "
  f"population is far better covered, as expected)")

# ============================================================================================
L("")
L("--- E. FINAL LEAK PROOF ON THE FRAME THAT ENTERS EVERY COMPUTATION ---------------------")
LEAK["analysis_rows"] = int(len(J))
LEAK["analysis_seasons"] = sorted(int(x) for x in J.season.unique())
LEAK["analysis_game_date_min"] = str(J.game_date.min())[:10]
LEAK["analysis_game_date_max"] = str(J.game_date.max())[:10]
LEAK["analysis_commence_years"] = sorted(
    int(x) for x in pd.to_datetime(hp[hp.gid.isin(set(J.gid))].commence_ts).dt.year.unique())
LEAK["n_players"] = int(J.player_id.nunique())
LEAK["n_games"] = int(J.gid.nunique())
LEAK["rows_from_holdout_seasons"] = int(J.season.isin(mb.HOLDOUT_SEASONS).sum())
LEAK["rows_dated_after_partition"] = int(
    (pd.to_datetime(J.game_date) > pd.Timestamp(f"{SEASON}-12-31")).sum())
assert LEAK["rows_from_holdout_seasons"] == 0
assert LEAK["rows_dated_after_partition"] == 0

sk.assert_partition(J[["season"]], allowed=mb.EXPLORATION_SEASONS, season_cols=["season"])
L("  screenkit.assert_partition(allowed=EXPLORATION_SEASONS, season_cols=['season']) PASSED")
L(f"  rows from a HOLDOUT season: {LEAK['rows_from_holdout_seasons']}")
L(f"  rows dated after {SEASON}-12-31: {LEAK['rows_dated_after_partition']}")
L(f"  final frame: n={len(J)} players={LEAK['n_players']} games={LEAK['n_games']} "
  f"dates {LEAK['analysis_game_date_min']}..{LEAK['analysis_game_date_max']}")

keep = ["row_uid", "season", "gid", "game_date", "player_id", "player_name", "team_id",
        "is_home", "starter_flag", "minutes", "pts", "M1", "M2", "M3", "F1", "F2",
        "pred_sd", "min_hat", "line_sd", "n_books", "p_over_fair", "overround", "lead_h",
        "fallback_level", "is_fallback", "n_prior_games", "forecast_cutoff", "feature_asof"]
A = J[keep].sort_values(["game_date", "player_id"]).reset_index(drop=True)
ap = os.path.join(mb.OUT, "analysis_frame.csv")
A.to_csv(ap, index=False)
LEAK["analysis_frame_sha256"] = hashlib.sha256(open(ap, "rb").read()).hexdigest()
LEAK["sigma_a"], LEAK["sigma_b"] = SIG_A, SIG_B
LEAK["prereg_sha256"] = PRE
json.dump(LEAK, open(os.path.join(mb.OUT, "leak_proof.json"), "w"), indent=1)
L(f"  wrote out/analysis_frame.csv  sha256={LEAK['analysis_frame_sha256'][:16]}...")
L("")
L("  NO STATISTIC RELATING pts TO ANY FORECAST WAS COMPUTED IN THIS STAGE.")
L.close()
