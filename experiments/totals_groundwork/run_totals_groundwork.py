#!/usr/bin/env python3
"""
Totals-market groundwork — reconnaissance, NOT a registered experiment.

READ-ONLY on all data. Writes only to experiments/totals_groundwork/.

Answers, with row-level evidence CSVs:
  1. Inventory: where totals (over/under) lines exist on disk, by season.
  2. Bookie consensus total vs actual game total — bookie totals MAE by season.
  3. Our model (channel_reval predictions_v2: str_total_cal) vs the bookie
     consensus total, paired on the same games.
  4. Error-structure diagnosis: bias / dispersion / calibration slope /
     home-away error covariance (why totals error != margin error).

Conventions mirror the registered margin benchmark (oracle_bracket.py
build_bookie_margins): per (game, book) take the LATEST snapshot with
snap <= commence, then average across books. Totals line = the Over
outcome's point (verified identical to Under on every pair).

All comparisons here are exploratory / diagnostic. Nothing is registered,
nothing touches the ledger or leaderboards.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CAP = ROOT / "data" / "odds_capture"
HIST = CAP / "historical"
OLD_MASTER = ROOT / "data" / "drive_masters" / "master_odds.csv"
EXT_OTHER = CAP / "master_odds_extension_other_markets.csv"
EXT_MAIN = CAP / "master_odds_extension.csv"
MASTER_TEAM = ROOT / "data" / "masters" / "master_team.parquet"
PREDICTIONS = ROOT / "experiments" / "channel_reval" / "predictions_v2.csv"

RNG_SEED = 42
N_BOOT = 4000


# ---------------------------------------------------------------- helpers
def fmt(df, floatfmt="{:.4f}"):
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: floatfmt.format(v) if pd.notna(v) else "")
    return d.to_string(index=False)


def date_clustered_bootstrap(deltas, dates, n_boot=N_BOOT, seed=RNG_SEED):
    """Bootstrap mean(delta) resampling GAME DATES with replacement.

    Mirrors the harness's date-clustered CI logic in spirit. Exploratory:
    this is recon, not a gated evaluation.
    """
    df = pd.DataFrame({"delta": deltas, "date": dates})
    groups = {d: g.delta.values for d, g in df.groupby("date")}
    keys = list(groups)
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        vals = np.concatenate([groups[keys[j]] for j in pick])
        means[i] = vals.mean()
    return float(np.percentile(means, 5)), float(np.percentile(means, 95))


# ---------------------------------------------------------------- Part 1
def part1_inventory():
    print("=" * 72)
    print("PART 1 — INVENTORY: what totals data exists on disk")
    print("=" * 72)

    # --- 1a. raw snapshot JSONs: which markets does each capture hold?
    rows = []
    for f in sorted(HIST.glob("hist_*.json")):
        m = re.match(r"hist_(\d{4}-\d{2}-\d{2})_(\d{2})Z\.json", f.name)
        d = json.loads(f.read_text())
        games = d.get("data", [])
        rows.append(_market_counts(f.name, "historical_backfill",
                                   m.group(1), games))
    for f in sorted(CAP.glob("live_*.json")):
        m = re.match(r"live_(\d{8})T\d{6}Z\.json", f.name)
        ds = m.group(1)
        date = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"
        rows.append(_market_counts(f.name, "live_capture", date,
                                   json.loads(f.read_text())))
    raw = pd.DataFrame(rows)
    raw.to_csv(HERE / "raw_snapshot_market_inventory.csv", index=False)

    n_files = len(raw)
    with_events = raw[raw.n_events > 0]
    full_totals = (with_events.n_events_with_totals ==
                   with_events.n_events).sum()
    print(f"\nRaw snapshot files scanned: {n_files} "
          f"({(raw.source == 'historical_backfill').sum()} historical backfill "
          f"2/day + {(raw.source == 'live_capture').sum()} live hourly)")
    print(f"Files with >=1 event: {len(with_events)}; of those, files where "
          f"EVERY event quotes totals in >=1 book: {full_totals}")
    print(f"Events across all files: {raw.n_events.sum()} sightings | "
          f"with totals {raw.n_events_with_totals.sum()} | "
          f"with spreads {raw.n_events_with_spreads.sum()}")
    print("-> row-level file inventory: raw_snapshot_market_inventory.csv")

    # --- 1b. old master (2022 -> 2025-07-04): spreads only, structurally
    old = pd.read_csv(OLD_MASTER)
    has_market_col = "market_key" in old.columns
    print(f"\nOLD master {OLD_MASTER.relative_to(ROOT)}:")
    print(f"  columns: {list(old.columns)}")
    print(f"  has market dimension: {has_market_col} — the file is "
          f"spread-shaped (team / odds_spread / odds_price); NO totals rows "
          f"exist in it or anywhere else on disk for 2022 -> 2025-07-04.")
    old_sum = (old.groupby("season")
               .agg(n_rows=("api_event_id", "size"),
                    n_games=("game_id", "nunique"),
                    n_books=("bookmaker_key", "nunique"))
               .reset_index())
    old_sum.insert(0, "table", "drive_masters/master_odds.csv (spreads only)")
    print(fmt(old_sum))

    # --- 1c. extension other-markets: the totals that DO exist
    om = pd.read_csv(EXT_OTHER, dtype={"game_id": "string"}, low_memory=False)
    tot = om[om.market_key == "totals"].copy()
    piv = tot.pivot_table(index=["api_event_id", "bookmaker_key",
                                 "odds_snapshot_timestamp"],
                          columns="outcome_name", values="outcome_point",
                          aggfunc="first")
    n_mismatch = int((piv["Over"] != piv["Under"]).sum())
    ext_sum = (tot.assign(mapped=tot.game_id.notna() & (tot.game_id != ""))
               .groupby("season")
               .agg(n_rows=("api_event_id", "size"),
                    n_events=("api_event_id", "nunique"),
                    n_games_mapped=("game_id",
                                    lambda s: s[s.notna() & (s != "")]
                                    .nunique()),
                    n_books=("bookmaker_key", "nunique"))
               .reset_index())
    ext_sum.insert(0, "table",
                   "odds_capture/master_odds_extension_other_markets.csv "
                   "(totals rows)")
    print(f"\nNEW-ERA totals (2025-07-05 -> present), "
          f"{EXT_OTHER.relative_to(ROOT)}:")
    print(fmt(ext_sum))
    print(f"  Over/Under point symmetry: {len(piv)} (event,book,snapshot) "
          f"pairs, {n_mismatch} mismatched points, "
          f"{int(tot.outcome_point.isna().sum())} null points")

    inv = pd.concat([old_sum, ext_sum], ignore_index=True)
    inv.to_csv(HERE / "inventory_by_season.csv", index=False)
    print("-> inventory_by_season.csv")
    return tot


def _market_counts(fname, source, date, games):
    n_tot = n_spr = n_h2h = 0
    for g in games:
        mk = {m["key"] for b in g.get("bookmakers", [])
              for m in b.get("markets", [])}
        n_tot += "totals" in mk
        n_spr += "spreads" in mk
        n_h2h += "h2h" in mk
    return {"file": fname, "source": source, "snapshot_date": date,
            "n_events": len(games), "n_events_with_totals": n_tot,
            "n_events_with_spreads": n_spr, "n_events_with_h2h": n_h2h}


# ---------------------------------------------------------------- Part 2
def part2_bookie_totals(tot):
    print("\n" + "=" * 72)
    print("PART 2 — BOOKIE CONSENSUS TOTAL vs ACTUAL GAME TOTAL")
    print("=" * 72)
    print("Convention (mirrors oracle_bracket.build_bookie_margins): per "
          "(game, book) the LATEST snapshot with snap <= commence; consensus "
          "= mean across books; line = Over outcome point.")

    t = tot[tot.game_id.notna() & (tot.game_id != "")].copy()
    t = t[t.outcome_name == "Over"]
    t["game_id"] = t.game_id.astype(str)
    t["snap"] = pd.to_datetime(t.odds_snapshot_timestamp, utc=True,
                               format="mixed")
    t["tip"] = pd.to_datetime(t.odds_commence_time, utc=True, format="mixed")
    pre = t[t.snap <= t.tip]
    n_inplay = len(t) - len(pre)
    last = (pre.sort_values("snap")
            .groupby(["game_id", "bookmaker_key"]).tail(1))
    per_game = (last.groupby("game_id")
                .agg(consensus_total=("outcome_point", "mean"),
                     median_total=("outcome_point", "median"),
                     book_spread_minmax=("outcome_point",
                                         lambda s: float(s.max() - s.min())),
                     n_books=("outcome_point", "size"))
                .reset_index())

    # actual totals from master_team (authoritative final scores)
    mt = pd.read_parquet(MASTER_TEAM,
                         columns=["game_id", "season", "game_date", "pts"])
    mt["game_id"] = mt.game_id.astype(str)
    actual = (mt.groupby("game_id")
              .agg(actual_total=("pts", "sum"), n_team_rows=("pts", "size"),
                   season=("season", "first"), game_date=("game_date", "first"))
              .reset_index())
    bad = actual[actual.n_team_rows != 2]
    assert bad.empty, f"games without exactly 2 team rows: {bad}"

    bk = per_game.merge(actual, on="game_id", how="inner")
    unmatched = set(per_game.game_id) - set(bk.game_id)
    bk["err"] = bk.consensus_total - bk.actual_total
    bk["abs_err"] = bk.err.abs()
    bk = bk.sort_values(["season", "game_date"])
    bk.to_csv(HERE / "bookie_totals_per_game.csv", index=False)

    rows = []
    for label, g in [("ALL", bk)] + list(bk.groupby("season")):
        rows.append({
            "season": label, "n_games": len(g),
            "bookie_totals_mae": g.abs_err.mean(),
            "bookie_totals_rmse": float(np.sqrt((g.err ** 2).mean())),
            "bookie_bias_line_minus_actual": g.err.mean(),
            "mean_consensus_total": g.consensus_total.mean(),
            "mean_actual_total": g.actual_total.mean(),
            "sd_actual_total": g.actual_total.std(ddof=1),
            "mean_n_books": g.n_books.mean(),
        })
    by_season = pd.DataFrame(rows)
    by_season.to_csv(HERE / "bookie_totals_mae_by_season.csv", index=False)

    print(f"\nPre-tip totals rows kept: {len(pre)} (dropped {n_inplay} "
          f"in-play rows, snapshot > commence)")
    print(f"Games with a pre-tip consensus total: {len(bk)} "
          f"({len(unmatched)} mapped game_ids without a master_team match: "
          f"{sorted(unmatched) if unmatched else 'none'})")
    print(fmt(by_season))
    print("\nWhere totals lines DO NOT exist: all of 2022, 2023, 2024 and "
          "2025 before Jul 5 — no totals market anywhere on disk for those "
          "games (old master is spreads-only).")
    print("-> bookie_totals_per_game.csv, bookie_totals_mae_by_season.csv")
    return bk


# ---------------------------------------------------------------- Part 3
def part3_model_vs_bookie(bk):
    print("\n" + "=" * 72)
    print("PART 3 — OUR MODEL (str_total_cal) vs BOOKIE CONSENSUS, PAIRED")
    print("=" * 72)

    p = pd.read_csv(PREDICTIONS)
    p["game_id"] = p.GAME_ID.astype(str)
    p["date"] = pd.to_datetime(p.GAME_DATE_h)

    # sanity: reproduce the registered totals MAE (report: str 14.2236 raw 14.763)
    print("\nOur totals MAE on the full 673-game channel_reval test set "
          "(sanity vs REPORT.md gate-4 figures 14.2236 / 14.763):")
    rows = []
    for label, g in [("ALL", p)] + list(p.groupby("season_h")):
        rows.append({
            "season": label, "n_games": len(g),
            "model_str_total_mae": (g.str_total_cal - g.total_true)
            .abs().mean(),
            "model_raw_total_mae": (g.raw_total_cal - g.total_true)
            .abs().mean(),
            "model_str_margin_mae": (g.str_margin_cal - g.margin_true)
            .abs().mean(),
        })
    full = pd.DataFrame(rows)
    full.to_csv(HERE / "model_totals_mae_by_season_full673.csv", index=False)
    print(fmt(full))

    # paired subset: test games that ALSO have a bookie consensus total
    m = p.merge(bk[["game_id", "consensus_total", "n_books", "actual_total"]],
                on="game_id", how="inner")
    chk = (m.total_true != m.actual_total).sum()
    assert chk == 0, f"{chk} games where predictions total_true != master_team"
    m["e_model"] = (m.str_total_cal - m.total_true).abs()
    m["e_bookie"] = (m.consensus_total - m.total_true).abs()
    m["delta_bookie_minus_model"] = m.e_bookie - m.e_model
    m = m.sort_values(["season_h", "date"])
    keep = ["game_id", "GAME_DATE_h", "season_h", "TEAM_ABBREVIATION_h",
            "TEAM_ABBREVIATION_a", "total_true", "str_total_cal",
            "raw_total_cal", "consensus_total", "n_books", "e_model",
            "e_bookie", "delta_bookie_minus_model", "margin_true",
            "str_margin_cal"]
    m[keep].to_csv(HERE / "model_vs_bookie_totals_paired.csv", index=False)

    # margin benchmark on the SAME games, for the totals-vs-margin gap contrast
    bm = build_bookie_margins_like_oracle()
    mm = m.merge(bm, on="game_id", how="inner")

    rows = []
    for label, g in [("ALL", m)] + list(m.groupby("season_h")):
        lo, hi = date_clustered_bootstrap(
            g.delta_bookie_minus_model.values, g.GAME_DATE_h.values)
        gm = mm[mm.game_id.isin(g.game_id)]
        rows.append({
            "season": label, "n_paired_games": len(g),
            "model_totals_mae": g.e_model.mean(),
            "bookie_totals_mae": g.e_bookie.mean(),
            "totals_gap_model_minus_bookie":
                g.e_model.mean() - g.e_bookie.mean(),
            "delta_ci90_lo": lo, "delta_ci90_hi": hi,
            "share_games_model_closer": (g.e_model < g.e_bookie).mean(),
            "n_margin_paired": len(gm),
            "model_margin_mae_same_games":
                (gm.str_margin_cal - gm.margin_true).abs().mean(),
            "bookie_margin_mae_same_games":
                (gm.bookie_margin - gm.margin_true).abs().mean(),
        })
    paired = pd.DataFrame(rows)
    paired["margin_gap_model_minus_bookie"] = (
        paired.model_margin_mae_same_games
        - paired.bookie_margin_mae_same_games)
    paired.to_csv(HERE / "paired_summary_by_season.csv", index=False)

    print(f"\nPaired same-games comparison (test games with a pre-tip "
          f"consensus total): n = {len(m)} of 673")
    print("(2024: zero — no totals lines exist for 2024; 2025: only games "
          "on/after 2025-07-05; 2026: season through Jul 29)")
    print("delta = |bookie err| - |model err|, positive = model better; "
          "CI = date-clustered bootstrap, EXPLORATORY (recon, ungated)")
    print(fmt(paired))
    print("-> model_vs_bookie_totals_paired.csv, paired_summary_by_season.csv")
    return p, m, mm


def build_bookie_margins_like_oracle():
    """Reproduce oracle_bracket.build_bookie_margins (verified against
    experiments/oracle_bracket/bookie_gap.csv)."""
    frames = []
    for path in (OLD_MASTER, EXT_MAIN):
        o = pd.read_csv(path, low_memory=False)
        o = o[o["game_id"].notna()].copy()
        o = o[o["game_id"].astype(str).str.strip() != ""]
        o["game_id"] = o["game_id"].astype(np.int64).astype(str)
        o["snap"] = pd.to_datetime(o.odds_snapshot_timestamp, utc=True,
                                   format="mixed")
        o["tip"] = pd.to_datetime(o.odds_commence_time, utc=True,
                                  format="mixed")
        o = o[(o.team == o.home_team) & (o.snap <= o.tip)
              & o.odds_spread.notna()]
        frames.append(o[["game_id", "bookmaker_key", "snap", "odds_spread"]])
    allo = pd.concat(frames, ignore_index=True)
    allo = allo.sort_values("snap").groupby(
        ["game_id", "bookmaker_key"]).tail(1)
    return (allo.groupby("game_id")
            .agg(bookie_margin=("odds_spread", lambda s: float(-s.mean())),
                 n_books_margin=("odds_spread", "size"))
            .reset_index())


# ---------------------------------------------------------------- Part 4
def part4_diagnosis(p, m):
    print("\n" + "=" * 72)
    print("PART 4 — ERROR-STRUCTURE DIAGNOSIS (all EXPLORATORY)")
    print("=" * 72)

    # 4a. bias / dispersion / calibration slope, totals vs margin, by season
    rows = []
    specs = [("total", "str_total_cal", "total_true"),
             ("margin", "str_margin_cal", "margin_true")]
    for target, pred_c, true_c in specs:
        for label, g in [("ALL", p)] + list(p.groupby("season_h")):
            e = g[pred_c] - g[true_c]
            slope, intercept = np.polyfit(g[pred_c], g[true_c], 1)
            rows.append({
                "target": target, "season": label, "n": len(g),
                "mae": e.abs().mean(),
                "rmse": float(np.sqrt((e ** 2).mean())),
                "bias_pred_minus_true": e.mean(),
                "sd_error": e.std(ddof=1),
                "sd_pred": g[pred_c].std(ddof=1),
                "sd_true": g[true_c].std(ddof=1),
                "corr_pred_true": g[pred_c].corr(g[true_c]),
                "ols_slope_true_on_pred": slope,
                "ols_intercept": intercept,
            })
    diag = pd.DataFrame(rows)
    diag.to_csv(HERE / "totals_error_decomposition.csv", index=False)
    print("\n4a. Bias / dispersion / calibration (full 673 test games):")
    print("    (ols_slope_true_on_pred == 1 means the prediction spread is "
          "used efficiently; < 1 = predictions over-dispersed, > 1 = "
          "under-dispersed / too compressed)")
    print(fmt(diag))

    # 4b. THE structural story: home/away error covariance.
    # var(total_err)  = var(eh) + var(ea) + 2cov
    # var(margin_err) = var(eh) + var(ea) - 2cov
    print("\n4b. Home-side vs away-side error covariance (str chains, "
          "calibrated):")
    rows = []
    for label, g in [("ALL", p)] + list(p.groupby("season_h")):
        eh = g.str_home_cal - g.team_pts_h
        ea = g.str_away_cal - g.team_pts_a
        cov = float(np.cov(eh, ea, ddof=1)[0, 1])
        rows.append({
            "season": label, "n": len(g),
            "var_home_err": eh.var(ddof=1), "var_away_err": ea.var(ddof=1),
            "cov_home_away_err": cov,
            "corr_home_away_err": float(np.corrcoef(eh, ea)[0, 1]),
            "var_total_err": (eh + ea).var(ddof=1),
            "var_margin_err": (eh - ea).var(ddof=1),
        })
    cov_tbl = pd.DataFrame(rows)
    cov_tbl.to_csv(HERE / "home_away_error_covariance.csv", index=False)
    print(fmt(cov_tbl))
    print("    Positive covariance -> shared game-environment error (pace, "
          "officiating, shooting variance) ADDS in the total and CANCELS in "
          "the margin. This is why the same chains give margin MAE ~10 but "
          "total MAE ~14.")

    # 4c. season/month drift in the totals bias
    p2 = p.copy()
    p2["month"] = p2.date.dt.to_period("M").astype(str)
    drift = (p2.groupby(["season_h", "month"])
             .apply(lambda g: pd.Series({
                 "n": len(g),
                 "mean_total_true": g.total_true.mean(),
                 "mean_pred_total": g.str_total_cal.mean(),
                 "bias_pred_minus_true":
                     (g.str_total_cal - g.total_true).mean(),
                 "mae": (g.str_total_cal - g.total_true).abs().mean()}),
                 include_groups=False)
             .reset_index())
    drift.to_csv(HERE / "totals_bias_by_month.csv", index=False)
    print("\n4c. Totals bias drift by month (model under-predicts when "
          "bias < 0):")
    print(fmt(drift))

    # 4d. bookie vs model bias on the paired subset
    print("\n4d. Paired subset — who carries the bias?")
    rows = []
    for label, g in [("ALL", m)] + list(m.groupby("season_h")):
        rows.append({
            "season": label, "n": len(g),
            "model_bias": (g.str_total_cal - g.total_true).mean(),
            "bookie_bias": (g.consensus_total - g.total_true).mean(),
            "model_sd_pred": g.str_total_cal.std(ddof=1),
            "bookie_sd_line": g.consensus_total.std(ddof=1),
            "sd_true": g.total_true.std(ddof=1),
            "corr_model_bookie": g.str_total_cal.corr(g.consensus_total),
        })
    pb = pd.DataFrame(rows)
    pb.to_csv(HERE / "paired_bias_comparison.csv", index=False)
    print(fmt(pb))
    return diag, cov_tbl


if __name__ == "__main__":
    tot = part1_inventory()
    bk = part2_bookie_totals(tot)
    p, m, mm = part3_model_vs_bookie(bk)
    part4_diagnosis(p, m)
    print("\nDone. Evidence CSVs written to experiments/totals_groundwork/.")
