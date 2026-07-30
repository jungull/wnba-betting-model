#!/usr/bin/env python3
"""
W5 closing-line groundwork — cadence audit + honest baselines.

Part A: audit the OLD master (data/drive_masters/master_odds.csv, 2022-2025).
        Measured finding (do not assume the ROADMAP's "~5-min cadence"): it
        holds ONE snapshot per (game, book), requested at commence-1h. The
        5-min grid exists only in the upstream API archive it was pulled
        from. Open/close pairs therefore CANNOT be built from it.

Part B: open/close + baselines on the NEW capture era
        (data/odds_capture/master_odds_extension.csv, 2025-07-05 -> present,
        2 snapshots/day at 15Z/22Z, games listed several days ahead).
        Per (game, book): open = earliest pre-tip snapshot's HOME spread,
        close = last snapshot strictly before tip.
        Baselines: (a) close = open; (b) close = line at T hours before tip
        (last snapshot at/before tip-T), T in {24,12,6,3,1}. Pairs missing an
        endpoint are excluded from that comparison, never imputed. Where the
        T-line snapshot IS the close snapshot the pair is "degenerate"
        (prediction trivially equals target); we report the degenerate share
        and MAE on non-degenerate pairs alongside.

Part C: first model row — closed-form ridge (numpy; sklearn not installed)
        predicting close from (current line, hours-to-tip, movement-so-far).
        Train = 2025 season rows, test = 2026 (walk-forward across seasons;
        every feature is computable at the snapshot moment). The original
        plan (train 2022-23, test 2024-25) is impossible: those seasons have
        no multi-snapshot data anywhere on disk.

All outputs are CSVs in this directory + stdout. Metric everywhere: MAE in
spread points (home-team spread). This is a CLOSE-prediction leaderboard,
separate from the project's score-differential leaderboard.
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OLD = ROOT / "data" / "drive_masters" / "master_odds.csv"
EXT = ROOT / "data" / "odds_capture" / "master_odds_extension.csv"
T_HOURS = [24, 12, 6, 3, 1]
BUCKETS = [(72, np.inf), (48, 72), (24, 48), (12, 24), (6, 12), (3, 6),
           (1, 3), (0, 1)]


def pctiles(s):
    return {f"p{p}": round(float(np.percentile(s, p)), 2)
            for p in (50, 75, 90, 95)} | {"max": round(float(s.max()), 2)}


# ---------------------------------------------------------------- Part A
def audit_old_master():
    df = pd.read_csv(OLD)
    home = df[df.team == df.home_team].copy()
    home["snap"] = pd.to_datetime(home.odds_snapshot_timestamp)
    home["tip"] = pd.to_datetime(home.odds_commence_time)
    home["min_before_tip"] = (home.tip - home.snap).dt.total_seconds() / 60

    pair_sizes = home.groupby(["api_event_id", "bookmaker_key"]).size()
    rows = []
    for season, g in home.groupby("season"):
        rows.append({
            "season": season,
            "n_rows_home_side": len(g),
            "n_events": g.api_event_id.nunique(),
            "n_games_with_game_id": g.dropna(subset=["game_id"]).game_id.nunique(),
            "n_game_book_pairs": g.groupby(["api_event_id", "bookmaker_key"]).ngroups,
            "n_books": g.bookmaker_key.nunique(),
            "snapshots_per_pair_max": int(g.groupby(
                ["api_event_id", "bookmaker_key"]).size().max()),
            "min_before_tip_p10": round(g.min_before_tip.quantile(.10), 1),
            "min_before_tip_p50": round(g.min_before_tip.quantile(.50), 1),
            "min_before_tip_p90": round(g.min_before_tip.quantile(.90), 1),
        })
    audit = pd.DataFrame(rows)
    audit.to_csv(HERE / "old_master_cadence_audit.csv", index=False)

    cov = (home.groupby(["season", "bookmaker_key"]).api_event_id.nunique()
           .rename("n_games").reset_index()
           .pivot(index="bookmaker_key", columns="season", values="n_games")
           .fillna(0).astype(int))
    cov.to_csv(HERE / "old_master_coverage_by_book.csv")

    print("=== Part A: old master (2022-2025) cadence audit ===")
    print(f"home-side rows: {len(home)} | events: {home.api_event_id.nunique()}"
          f" | game-book pairs: {len(pair_sizes)}")
    print(f"pairs with exactly 1 snapshot: {(pair_sizes == 1).sum()} "
          f"({(pair_sizes == 1).mean():.2%}); max snapshots in any pair: "
          f"{pair_sizes.max()}")
    print(f"snapshot timing (min before tip): "
          f"p10={home.min_before_tip.quantile(.1):.0f} "
          f"p50={home.min_before_tip.quantile(.5):.0f} "
          f"p90={home.min_before_tip.quantile(.9):.0f}")
    print(audit.to_string(index=False))
    print("-> single T~1h snapshot per (game,book): open/close pairs and "
          "T-hour baselines are NOT computable on the old master.\n")


# ---------------------------------------------------------------- Part B
def build_openclose():
    df = pd.read_csv(EXT, dtype={"game_id": "string"})
    df = df[df.game_id.notna() & (df.game_id != "")]
    home = df[df.team == df.home_team].copy()
    home["snap"] = pd.to_datetime(home.odds_snapshot_timestamp)
    home["commence"] = pd.to_datetime(home.odds_commence_time)

    # Authoritative tip = commence quoted at the LATEST snapshot of the game
    # (reschedules/time-drift resolve to the final listing).
    last = home.sort_values("snap").groupby("game_id").tail(1)
    tip = dict(zip(last.game_id, last.commence))
    home["tip"] = home.game_id.map(tip)
    pre = home[home.snap < home.tip].copy()          # walk-forward: pre-tip only
    pre["hrs_to_tip"] = (pre.tip - pre.snap).dt.total_seconds() / 3600

    recs = []
    for (gid, book), g in pre.sort_values("snap").groupby(
            ["game_id", "bookmaker_key"]):
        recs.append({
            "game_id": gid, "bookmaker_key": book,
            "season": g.season.iloc[-1],
            "home_team": g.home_team.iloc[-1],
            "away_team": g.away_team.iloc[-1],
            "tip_utc": g.tip.iloc[-1].isoformat(),
            "n_snapshots": len(g),
            "open_spread": g.odds_spread.iloc[0],
            "close_spread": g.odds_spread.iloc[-1],
            "open_ts": g.snap.iloc[0].isoformat(),
            "close_ts": g.snap.iloc[-1].isoformat(),
            "open_hrs_to_tip": round(g.hrs_to_tip.iloc[0], 2),
            "close_hrs_to_tip": round(g.hrs_to_tip.iloc[-1], 2),
            "abs_close_minus_open": abs(g.odds_spread.iloc[-1]
                                        - g.odds_spread.iloc[0]),
        })
    oc = pd.DataFrame(recs)
    oc.to_csv(HERE / "extension_game_book_openclose.csv", index=False)
    return pre, oc


def part_b(pre, oc):
    print("=== Part B: new-era (2025-07-05 -> 2026-07-29) open/close study ===")
    print(f"pre-tip home-side snapshot rows: {len(pre)} | game-book pairs: "
          f"{len(oc)} | games: {oc.game_id.nunique()} | books: "
          f"{oc.bookmaker_key.nunique()}")
    print("snapshots per pair: " + str({k: int(v) for k, v in
          oc.n_snapshots.describe()[["min", "25%", "50%", "75%", "max"]]
          .items()}))
    print("close hours-to-tip: " + str(pctiles(oc.close_hrs_to_tip)))
    print("open hours-to-tip:  " + str(pctiles(oc.open_hrs_to_tip)))

    # |close - open| distribution
    rows = []
    for label, g in [("ALL", oc)] + list(oc.groupby("season")):
        d = g.abs_close_minus_open
        rows.append({"season": label, "n_pairs": len(g)} | pctiles(d) |
                    {"mean": round(d.mean(), 3),
                     "share_zero": round((d == 0).mean(), 3),
                     "share_ge_1pt": round((d >= 1).mean(), 3),
                     "share_ge_2pt": round((d >= 2).mean(), 3)})
    dist = pd.DataFrame(rows)
    dist.to_csv(HERE / "movement_distribution.csv", index=False)
    print("\n|close - open| (spread points):")
    print(dist.to_string(index=False))

    # Baselines. Build line@T per pair via merge_asof-style lookup.
    pre_s = pre.sort_values("snap")
    base_rows, per_book = [], []
    oc_idx = oc.set_index(["game_id", "bookmaker_key"])
    groups = {k: g for k, g in pre_s.groupby(["game_id", "bookmaker_key"])}
    for label in ["ALL"] + sorted(oc.season.unique().tolist()):
        sub = oc if label == "ALL" else oc[oc.season == label]
        err_open = (sub.close_spread - sub.open_spread).abs()
        base_rows.append({"season": label, "baseline": "close=open",
                          "mae": round(err_open.mean(), 3), "n_pairs": len(sub),
                          "degenerate_share": round(
                              (sub.n_snapshots == 1).mean(), 3),
                          "mae_nondegenerate": round(err_open[
                              sub.n_snapshots > 1].mean(), 3),
                          "n_nondegenerate": int((sub.n_snapshots > 1).sum()),
                          "mae_open_same_sample": round(err_open.mean(), 3)})
        for T in T_HOURS:
            errs, degen, err_open_same = [], [], []
            for _, r in sub.iterrows():
                g = groups[(r.game_id, r.bookmaker_key)]
                cut = g[g.hrs_to_tip >= T]
                if cut.empty:
                    continue
                line_t = cut.odds_spread.iloc[-1]
                is_close = cut.snap.iloc[-1].isoformat() == r.close_ts
                errs.append(abs(r.close_spread - line_t))
                degen.append(is_close)
                err_open_same.append(abs(r.close_spread - r.open_spread))
            errs, degen = np.array(errs), np.array(degen)
            nd = errs[~degen]
            base_rows.append({
                "season": label, "baseline": f"close=line@T-{T}h",
                "mae": round(errs.mean(), 3) if len(errs) else np.nan,
                "n_pairs": len(errs),
                "degenerate_share": round(degen.mean(), 3) if len(errs) else np.nan,
                "mae_nondegenerate": round(nd.mean(), 3) if len(nd) else np.nan,
                "n_nondegenerate": len(nd),
                "mae_open_same_sample": round(np.mean(err_open_same), 3)
                if err_open_same else np.nan})
    base = pd.DataFrame(base_rows)
    base.to_csv(HERE / "baseline_mae_by_season.csv", index=False)
    print("\nBaseline MAE (predicting the close, spread points):")
    print(base.to_string(index=False))

    # per book (pooled seasons): close=open and T-24h
    for book, g in oc.groupby("bookmaker_key"):
        per_book.append({"bookmaker_key": book, "n_pairs": len(g),
                         "n_games": g.game_id.nunique(),
                         "mae_close_eq_open": round(
                             (g.close_spread - g.open_spread).abs().mean(), 3),
                         "mean_n_snapshots": round(g.n_snapshots.mean(), 1),
                         "median_close_hrs_to_tip": round(
                             g.close_hrs_to_tip.median(), 2)})
    bk = pd.DataFrame(per_book).sort_values("mae_close_eq_open")
    bk.to_csv(HERE / "baseline_by_book.csv", index=False)
    print("\nPer book (pooled 2025-26), close=open:")
    print(bk.to_string(index=False))

    # movement per consecutive snapshot step, bucketed by hours-to-tip of the
    # LATER snapshot in the step
    steps = []
    for (gid, book), g in pre_s.groupby(["game_id", "bookmaker_key"]):
        sp, hr = g.odds_spread.values, g.hrs_to_tip.values
        for i in range(1, len(sp)):
            steps.append((hr[i], abs(sp[i] - sp[i - 1]), hr[i - 1] - hr[i]))
    st = pd.DataFrame(steps, columns=["hrs_to_tip", "abs_move", "step_hours"])
    rows = []
    for lo, hi in BUCKETS:
        b = st[(st.hrs_to_tip >= lo) & (st.hrs_to_tip < hi)]
        if b.empty:
            continue
        rows.append({"hrs_to_tip_bucket": f"[{lo},{hi})", "n_steps": len(b),
                     "mean_abs_move_per_step": round(b.abs_move.mean(), 3),
                     "share_steps_nonzero": round((b.abs_move > 0).mean(), 3),
                     "mean_step_hours": round(b.step_hours.mean(), 1),
                     "abs_move_per_elapsed_hour": round(
                         b.abs_move.sum() / b.step_hours.sum(), 4)})
    mv = pd.DataFrame(rows)
    mv.to_csv(HERE / "movement_by_hours_bucket.csv", index=False)
    print("\nLine movement per consecutive snapshot step:")
    print(mv.to_string(index=False))
    return base


# ---------------------------------------------------------------- Part C
def part_c(pre, oc):
    print("\n=== Part C: first model — ridge close-prediction "
          "(train 2025, test 2026) ===")
    oc_key = oc.set_index(["game_id", "bookmaker_key"])
    samples = []
    for (gid, book), g in pre.sort_values("snap").groupby(
            ["game_id", "bookmaker_key"]):
        r = oc_key.loc[(gid, book)]
        opens = g.odds_spread.iloc[0]
        for i in range(len(g)):
            row = g.iloc[i]
            if row.snap.isoformat() == r.close_ts:
                continue                       # predict only strictly earlier
            samples.append({"season": row.season, "game_id": gid,
                            "book": book,
                            "current": row.odds_spread,
                            "hrs_to_tip": row.hrs_to_tip,
                            "move_so_far": row.odds_spread - opens,
                            "close": r.close_spread})
    s = pd.DataFrame(samples)
    tr, te = s[s.season == 2025], s[s.season == 2026]
    feats = ["current", "hrs_to_tip", "move_so_far"]
    Xtr, ytr = tr[feats].values, tr["close"].values
    Xte, yte = te[feats].values, te["close"].values
    mu, sd = Xtr.mean(0), Xtr.std(0)
    Ztr, Zte = (Xtr - mu) / sd, (Xte - mu) / sd
    lam = 1.0
    A = Ztr.T @ Ztr + lam * np.eye(len(feats))
    b = Ztr.T @ (ytr - ytr.mean())
    w = np.linalg.solve(A, b)
    pred = Zte @ w + ytr.mean()
    mae_ridge = np.abs(pred - yte).mean()
    mae_cur = np.abs(te.current - te.close).mean()
    mae_open = np.abs((te.current - te.move_so_far) - te.close).mean()

    res = pd.DataFrame([
        {"model": "ridge(current,hrs_to_tip,move_so_far) lam=1",
         "test_mae": round(mae_ridge, 3), "n_train": len(tr), "n_test": len(te)},
        {"model": "baseline close=current line",
         "test_mae": round(mae_cur, 3), "n_train": 0, "n_test": len(te)},
        {"model": "baseline close=open",
         "test_mae": round(mae_open, 3), "n_train": 0, "n_test": len(te)},
    ]).sort_values("test_mae")
    res.to_csv(HERE / "ridge_model_result.csv", index=False)
    coef = pd.DataFrame({"feature": feats, "coef_standardized": np.round(w, 4),
                         "train_mean": np.round(mu, 3),
                         "train_std": np.round(sd, 3)})
    coef.to_csv(HERE / "ridge_coefficients.csv", index=False)
    print(res.to_string(index=False))
    print(coef.to_string(index=False))
    print(f"(train rows are 2025-season snapshots strictly before each "
          f"pair's close; test rows 2026; features known at snapshot time)")


if __name__ == "__main__":
    audit_old_master()
    pre, oc = build_openclose()
    b = part_b(pre, oc)
    part_c(pre, oc)
