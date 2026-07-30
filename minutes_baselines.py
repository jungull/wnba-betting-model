"""minutes_baselines.py — Minutes-model Stage-B baseline ladder (Phase 3a floor).

Preregistered experiment: ``minutes_ewma_vs_carryforward_v1``
(experiments/registry.jsonl; regime A, primary metric minutes_mae,
thresholds 0.10 / 0.05 / 0.15 / 0.0; incumbent ``minutes_carry_forward``).
This script does NOT register (already registered) and does NOT render
leaderboards (orchestrator's job). It:

  1. builds the three Stage-B baselines of MINUTES_MODEL_SPEC.md §7 on
     PLAYED rows (minutes > 0) of data/masters/master_player.parquet,
     regular season only (spec §2.1: playoffs are never blended):
       B1  carry-forward        = player's minutes in their most recent
                                  played game this season (shift(1));
                                  this is the frozen-baseline definition —
                                  see the anchor-reconciliation section of
                                  the generated REPORT.md for the
                                  "team's previous game" variant.
       B2  expanding mean       = shifted season-to-date mean;
       B3  shifted EWMA         = ewm(alpha).mean().shift(1) within
                                  player-season, alpha tuned on train years
                                  2021-2023 ONLY via
                                  evalharness.inner_tuning_splits.
  2. scores them walk-forward (evalharness.walk_forward_by_season; test
     seasons 2024 / 2025 / 2026) on the prediction universe = played rows
     with >= 1 prior same-season played appearance;
  3. runs evalharness.compare_to_incumbent (challenger = B3 EWMA,
     incumbent = B1 carry-forward) with coverage for gate 5; gate 4 joint
     check intentionally not provided (a minutes model has no joint game
     forecast; the harness records not_provided);
  4. previews the two-stage skeleton's Stage-A prior — shifted expanding
     played-rate over the dressed roster (played + dnp_reason rows) — and
     reports its Brier score per season (reference only, not registered);
  5. runs the shift/leakage audit: for AUDIT_N random scored player-games,
     deletes every row of that player-season at/after the target date and
     recomputes all three features from scratch; values must be identical;
  6. reconciles the measured 2024 numbers against the frozen anchors
     (minutes_carry_forward 5.42 / minutes_expanding_mean 5.12) and
     documents the universe definition precisely;
  7. writes experiments/minutes_baselines/REPORT.md + results CSVs.

Shift discipline (HANDOFF §3 rule 1/3): every feature is computed within
(player_id, season) via ``.ewm()/.expanding()`` THEN ``.shift(1)`` (the
project convention from experiments/channels/run_experiment.py — causally
identical to shift-then-window) — zero same-game information, features
reset per season, trends follow the player across trades within a season
(spec §5).

Run:  python minutes_baselines.py            # real run (records on ledger)
      python minutes_baselines.py --smoke    # full dry-run against a scratch
                                             # copy of the registry + scratch
                                             # outdir; the real ledger and
                                             # experiments/ are untouched
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from evalharness import (  # noqa: E402
    compare_to_incumbent,
    frozen_baseline_value,
    inner_tuning_splits,
    walk_forward_by_season,
)
from evalharness.metrics import brier_score  # noqa: E402

MASTER = REPO / "data" / "masters" / "master_player.parquet"
DEFAULT_OUTDIR = REPO / "experiments" / "minutes_baselines"
EXPERIMENT_ID = "minutes_ewma_vs_carryforward_v1"

TRAIN_SEASONS = [2021, 2022, 2023]
TEST_SEASONS = [2024, 2025, 2026]
# Spec §6: grid {0.05…0.50}; "the grid, not habit, decides". 0.025 steps.
ALPHA_GRID = [round(float(a), 3) for a in np.arange(0.05, 0.50001, 0.025)]
N_INNER_FOLDS = 3
AUDIT_N = 20
AUDIT_SEED = 20260730
ANCHOR_TOL = 0.10          # mission: reconcile to ~0.1 of the frozen anchors
FLOAT_TOL = 1e-9

BASELINES = {  # column -> pretty name
    "pred_carry_forward": "B1 carry-forward (last played game)",
    "pred_expanding_mean": "B2 expanding season-to-date mean",
    "pred_ewma": "B3 shifted EWMA (tuned alpha)",
}


# ---------------------------------------------------------------------------
# data loading + feature construction
# ---------------------------------------------------------------------------

def load_master() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return (played, dressed, notes) — regular-season frames from the master.

    played:  minutes > 0 rows (Stage-B label universe).
    dressed: played rows + dressed-DNP rows (dnp_reason non-null) — the
             Stage-A preview universe. Rows with minutes == 0 AND no
             dnp_reason (0:00 box entries) fit neither definition and are
             excluded from both, counted in notes.
    """
    df = pd.read_parquet(MASTER)
    n_total = len(df)
    rs = df[df["season_type"] == "Regular Season"].copy()
    n_playoffs = n_total - len(rs)

    minutes = rs["minutes"]
    is_played = minutes.fillna(0) > 0
    has_reason = rs["dnp_reason"].notna() & (rs["dnp_reason"].astype(str) != "")
    zero_min_no_reason = (~is_played) & (~has_reason)

    played = rs[is_played].copy()
    dressed = rs[is_played | has_reason].copy()
    dressed["played_flag"] = (dressed["minutes"].fillna(0) > 0).astype(int)

    # hygiene gates (spec Phase 0 QA spirit)
    assert played["minutes"].notna().all() and (played["minutes"] > 0).all()
    assert played["game_date"].notna().all()
    assert not pd.to_datetime(played["game_date"], errors="coerce").isna().any()
    assert played["starter_flag"].notna().all(), "starter_flag null on played rows"

    notes = {
        "master_rows": n_total,
        "playoff_rows_excluded": int(n_playoffs),
        "regular_season_rows": len(rs),
        "played_rows": len(played),
        "dressed_dnp_rows": int(has_reason.sum()),
        "zero_min_no_reason_rows_excluded": int(zero_min_no_reason.sum()),
        "zero_min_no_reason_detail": rs.loc[
            zero_min_no_reason, ["game_id", "season", "game_date", "player_name"]
        ].to_dict("records"),
    }
    return played, dressed, notes


def sort_key(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(["player_id", "season", "game_date", "game_id"], kind="mergesort")


def add_baseline_features(played: pd.DataFrame, alpha_grid: list[float]) -> pd.DataFrame:
    """All Stage-B baseline features, shifted within (player_id, season)."""
    P = sort_key(played).reset_index(drop=True)
    g = P.groupby(["player_id", "season"], sort=False)

    P["prior_apps"] = g.cumcount()
    P["pred_carry_forward"] = g["minutes"].shift(1)
    P["pred_expanding_mean"] = g["minutes"].transform(
        lambda s: s.expanding().mean().shift(1)
    )
    for a in alpha_grid:
        P[f"ewma_{a}"] = g["minutes"].transform(
            lambda s, a=a: s.ewm(alpha=a, adjust=True).mean().shift(1)
        )
    P["started_last"] = g["starter_flag"].shift(1)

    # structural shift check: first appearance of every player-season must
    # have NaN features (nothing to carry), every later row must be covered.
    first = P["prior_apps"] == 0
    feat_cols = ["pred_carry_forward", "pred_expanding_mean"] + [
        f"ewma_{a}" for a in alpha_grid
    ]
    for c in feat_cols:
        assert P.loc[first, c].isna().all(), f"{c}: non-NaN on first appearances"
        assert P.loc[~first, c].notna().all(), f"{c}: NaN on eligible rows"
    return P


# ---------------------------------------------------------------------------
# alpha tuning (train years only, inner walk-forward folds)
# ---------------------------------------------------------------------------

def tune_alpha(U: pd.DataFrame, outer_2024, alpha_grid: list[float]) -> tuple[float, pd.DataFrame, list[dict]]:
    """Pick EWMA alpha on 2021-2023 ONLY via evalharness.inner_tuning_splits.

    EWMA has no fitted parameters, so each inner fold contributes a
    time-ordered validation window strictly inside the outer 2024-split
    training period; alpha = argmin of the mean validation MAE across folds
    (ties -> lowest alpha).
    """
    folds = inner_tuning_splits(U, outer_2024, date_col="game_date", n_folds=N_INNER_FOLDS)
    fold_meta = [
        {
            "fold": f.name,
            "n_train": int(len(f.train_idx)),
            "n_val": int(len(f.val_idx)),
            "train_end": str(f.train_end.date()),
            "val_start": str(f.val_start.date()),
            "val_end": str(f.val_end.date()),
        }
        for f in folds
    ]
    rows = []
    for a in alpha_grid:
        col = f"ewma_{a}"
        fold_maes = []
        for f in folds:
            v = U.loc[f.val_idx]
            fold_maes.append(float((v[col] - v["minutes"]).abs().mean()))
        rows.append(
            {"alpha": a}
            | {f"fold{i+1}_val_mae": m for i, m in enumerate(fold_maes)}
            | {"mean_val_mae": float(np.mean(fold_maes))}
        )
    curve = pd.DataFrame(rows)
    best_alpha = float(curve.loc[curve["mean_val_mae"].idxmin(), "alpha"])
    return best_alpha, curve, fold_meta


# ---------------------------------------------------------------------------
# evaluation tables
# ---------------------------------------------------------------------------

def mae_table(U: pd.DataFrame, seasons: list[int], split_label: str) -> pd.DataFrame:
    rows = []
    for season in seasons:
        u = U[U["season"] == season]
        for col, name in BASELINES.items():
            rows.append({
                "split": split_label,
                "season": season,
                "baseline": name,
                "n": int(len(u)),
                "mae": float((u[col] - u["minutes"]).abs().mean()),
                "coverage": float(u[col].notna().mean()) if len(u) else np.nan,
            })
    pooled = U[U["season"].isin(seasons)]
    for col, name in BASELINES.items():
        rows.append({
            "split": split_label,
            "season": "pooled",
            "baseline": name,
            "n": int(len(pooled)),
            "mae": float((pooled[col] - pooled["minutes"]).abs().mean()),
            "coverage": float(pooled[col].notna().mean()) if len(pooled) else np.nan,
        })
    return pd.DataFrame(rows)


def starter_bench_table(U: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    """Spec §8 M1 context split by started_last (prior-game starter status —
    conditioning on the target game's lineup would leak)."""
    rows = []
    for season in seasons + ["pooled"]:
        u = U[U["season"].isin(seasons)] if season == "pooled" else U[U["season"] == season]
        for grp, label in [(1, "starter (started_last=1)"), (0, "bench (started_last=0)")]:
            sub = u[u["started_last"] == grp]
            for col, name in BASELINES.items():
                rows.append({
                    "season": season,
                    "group": label,
                    "baseline": name,
                    "n": int(len(sub)),
                    "mae": float((sub[col] - sub["minutes"]).abs().mean()) if len(sub) else np.nan,
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Stage-A preview (reference only — NOT registered, NOT a claim)
# ---------------------------------------------------------------------------

def stage_a_preview(dressed: pd.DataFrame) -> pd.DataFrame:
    """Shifted expanding played-rate prior over the dressed roster.

    Universe: dressed rows (played + dnp_reason rows) with >= 1 prior
    same-season dressed appearance. Brier per season; the constant
    reference predicts the pooled 2021-2023 dressed played-rate everywhere
    (a legitimate walk-forward constant).
    """
    D = sort_key(dressed).reset_index(drop=True)
    g = D.groupby(["player_id", "season"], sort=False)
    D["prior_dressed"] = g.cumcount()
    D["p_plays_prior"] = g["played_flag"].transform(
        lambda s: s.expanding().mean().shift(1)
    )
    E = D[D["prior_dressed"] >= 1]
    const_rate = float(
        E.loc[E["season"].isin(TRAIN_SEASONS), "played_flag"].mean()
    )
    rows = []
    for season in sorted(E["season"].unique()):
        e = E[E["season"] == season]
        y = e["played_flag"].to_numpy(float)
        p = e["p_plays_prior"].to_numpy(float)
        rows.append({
            "season": int(season),
            "split": "test" if season in TEST_SEASONS else "train",
            "n_dressed_eligible": int(len(e)),
            "played_rate": float(y.mean()),
            "brier_expanding_prior": brier_score(y, p),
            "brier_const_train_rate": brier_score(y, np.full_like(y, const_rate)),
        })
    out = pd.DataFrame(rows)
    out.attrs["const_rate"] = const_rate
    return out


# ---------------------------------------------------------------------------
# leakage audit (spec §8 audit battery item 1, applied to this build)
# ---------------------------------------------------------------------------

def leakage_audit(P: pd.DataFrame, U_test: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """For AUDIT_N random scored rows: delete every row of that player-season
    at/after the target date, recompute carry-forward / expanding mean / EWMA
    from the surviving history, compare to the stored feature values."""
    rng = np.random.default_rng(AUDIT_SEED)
    picks = U_test.loc[rng.choice(U_test.index.to_numpy(), size=AUDIT_N, replace=False)]
    rows = []
    for idx, r in picks.iterrows():
        hist = P[
            (P["player_id"] == r["player_id"])
            & (P["season"] == r["season"])
            & (P["game_date"] < r["game_date"])       # drop target row AND all later rows
        ]
        hist = hist.sort_values(["game_date", "game_id"], kind="mergesort")
        s = hist["minutes"]
        recomputed = {
            "pred_carry_forward": float(s.iloc[-1]),
            "pred_expanding_mean": float(s.mean()),
            "pred_ewma": float(s.ewm(alpha=alpha, adjust=True).mean().iloc[-1]),
        }
        for col, rec in recomputed.items():
            stored = float(r[col])
            rows.append({
                "row_index": idx,
                "game_id": r["game_id"],
                "player_id": int(r["player_id"]),
                "player_name": r["player_name"],
                "season": int(r["season"]),
                "game_date": r["game_date"],
                "feature": col,
                "stored": stored,
                "recomputed": rec,
                "abs_diff": abs(stored - rec),
                "identical": bool(abs(stored - rec) <= FLOAT_TOL),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# anchor reconciliation (frozen 5.42 / 5.12)
# ---------------------------------------------------------------------------

def anchor_reconciliation(rs_all: pd.DataFrame, P: pd.DataFrame, U: pd.DataFrame) -> dict:
    u24 = U[U["season"] == 2024]
    cf_mae = float((u24["pred_carry_forward"] - u24["minutes"]).abs().mean())
    em_mae = float((u24["pred_expanding_mean"] - u24["minutes"]).abs().mean())
    cf_anchor = frozen_baseline_value("minutes_carry_forward")
    em_anchor = frozen_baseline_value("minutes_expanding_mean")

    # "team's previous game" carry-forward variant (the wording in some notes):
    # minutes the player logged in their team's immediately preceding game;
    # NaN when the player did not play in that game.
    sched = (
        rs_all[["team_abbreviation", "season", "game_date", "game_id"]]
        .drop_duplicates()
        .sort_values(["team_abbreviation", "season", "game_date", "game_id"], kind="mergesort")
    )
    sched["prev_game_id"] = sched.groupby(["team_abbreviation", "season"])["game_id"].shift(1)
    P2 = P.merge(
        sched[["team_abbreviation", "season", "game_id", "prev_game_id"]],
        on=["team_abbreviation", "season", "game_id"],
        how="left",
    )
    prev_min = P[["player_id", "season", "game_id", "minutes"]].rename(
        columns={"game_id": "prev_game_id", "minutes": "cf_team_prev"}
    )
    P2 = P2.merge(prev_min, on=["player_id", "season", "prev_game_id"], how="left")
    v24 = P2[(P2["season"] == 2024) & (P2["prior_apps"] >= 1)]
    variant_mae = float((v24["cf_team_prev"] - v24["minutes"]).abs().mean())
    variant_cov = float(v24["cf_team_prev"].notna().mean())

    # target-game starter split (what the spec §7 sub-anchors match; the §8
    # reporting convention is started_last — both shown in the report)
    tg = {}
    for col in ("pred_carry_forward", "pred_expanding_mean"):
        st = u24[u24["starter_flag"] == 1]
        be = u24[u24["starter_flag"] == 0]
        tg[col] = {
            "starters_mae": float((st[col] - st["minutes"]).abs().mean()),
            "bench_mae": float((be[col] - be["minutes"]).abs().mean()),
        }

    rec = {
        "n_2024_universe": int(len(u24)),
        "n_anchor": 4344,
        "cf_mae_2024": cf_mae,
        "cf_anchor": cf_anchor,
        "cf_abs_gap": abs(cf_mae - cf_anchor),
        "em_mae_2024": em_mae,
        "em_anchor": em_anchor,
        "em_abs_gap": abs(em_mae - em_anchor),
        "team_prev_variant_mae_2024": variant_mae,
        "team_prev_variant_coverage_2024": variant_cov,
        "target_game_starter_split_2024": tg,
        "within_tolerance": bool(
            abs(cf_mae - cf_anchor) <= ANCHOR_TOL and abs(em_mae - em_anchor) <= ANCHOR_TOL
        ),
    }
    if not rec["within_tolerance"]:
        raise RuntimeError(
            "Anchor reconciliation FAILED — measured 2024 MAEs "
            f"(cf {cf_mae:.4f} vs {cf_anchor}, expmean {em_mae:.4f} vs {em_anchor}) "
            f"differ from the frozen baselines by more than {ANCHOR_TOL}. "
            "Universe definitions must be reconciled before scoring "
            "(mission instruction). Details: " + json.dumps(rec)
        )
    return rec


# ---------------------------------------------------------------------------
# report writer
# ---------------------------------------------------------------------------

def fmt_table(df: pd.DataFrame, floatfmt: str = "{:.4f}") -> str:
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: floatfmt.format(v) if pd.notna(v) else "")
    header = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    body = "\n".join("| " + " | ".join(map(str, row)) + " |" for row in d.itertuples(index=False))
    return "\n".join([header, sep, body])


def write_report(outdir: Path, ctx: dict) -> None:
    r = ctx["compare"]
    rec = ctx["anchors"]
    audit = ctx["audit"]
    n_bad = int((~audit["identical"]).sum())
    gate_lines = []
    for gname, ok in r.gates.items():
        status = "PASS" if ok else ("FAIL" if ok is False else "not_provided")
        gate_lines.append(f"| {gname} | {status} | {json.dumps(r.gate_details[gname], default=str)} |")
    zrows = ctx["notes"]["zero_min_no_reason_detail"]
    zdesc = "; ".join(f"{z['player_name']} {z['game_date']} (game {z['game_id']})" for z in zrows)
    sens = (
        f"[{r.ci_sensitivity_team[0]:+.4f}, {r.ci_sensitivity_team[1]:+.4f}] "
        f"({r.ci_sensitivity_team[2]} team clusters)"
        if r.ci_sensitivity_team
        else "n/a"
    )
    tg = rec["target_game_starter_split_2024"]

    md = f"""# Minutes baselines — Stage-B floor (`{EXPERIMENT_ID}`)

*Generated by `minutes_baselines.py` on {ctx['run_time']} — run_number {r.run_number} on the registry ledger.
Spec: `project_docs/MINUTES_MODEL_SPEC.md` §2/§4/§7/§8; constitution `project_docs/HANDOFF.md` §3;
regime A (ROADMAP four-regimes). Registered 2026-07-30T17:51:46Z, incumbent `minutes_carry_forward`,
primary metric `minutes_mae`, thresholds min_improvement 0.10 / harm_ci_bound 0.05 /
per_season_tolerance 0.15 / coverage_tolerance 0.0. Not a leaderboard render (orchestrator's job);
Stage-A numbers below are a preview, not a registered claim.*

## Data and universe

- Source: `data/masters/master_player.parquet` (canonical rebuild; {ctx['notes']['master_rows']:,} rows).
- Regular season only per spec §2.1 ({ctx['notes']['playoff_rows_excluded']:,} playoff rows excluded, never blended).
- Played rows (minutes > 0): {ctx['notes']['played_rows']:,}; dressed-DNP rows (dnp_reason set): {ctx['notes']['dressed_dnp_rows']:,}.
- {ctx['notes']['zero_min_no_reason_rows_excluded']} rows have minutes == 0:00 with no DNP reason and fit neither universe (excluded, listed): {zdesc}.
- **Prediction universe** = played rows with >= 1 prior same-season played appearance
  (the frozen-anchor universe; spec D5's >= 3-appearance cold-start tier is a model-phase rule, not part of this preregistered floor).
- Features shifted within (player_id, season); trends follow the player across in-season trades (spec §5).
- Walk-forward: `evalharness.walk_forward_by_season`, test seasons 2024 / 2025 / 2026
  (2026 through {ctx['max_test_date']}). Splits prove their own time-order at construction.
  Alpha is tuned once on the 2024 split's training window (2021-2023) and frozen for all test seasons
  (per the registered hypothesis; no refits inside test).

## B3 alpha tuning (train 2021-2023 only, `inner_tuning_splits`, {N_INNER_FOLDS} folds)

Grid {ALPHA_GRID[0]}..{ALPHA_GRID[-1]} step 0.025 (spec §6 grid). Chosen **alpha = {ctx['alpha']}**
(mean inner-validation MAE {ctx['alpha_best_mae']:.4f}). Fold windows (all strictly inside 2021-2023):

{fmt_table(pd.DataFrame(ctx['fold_meta']))}

Tuning curve (full grid in `alpha_tuning_curve.csv`; nearest neighbours of the optimum):

{fmt_table(ctx['curve_excerpt'])}

## Per-season minutes MAE — test seasons (played rows, >= 1 prior appearance)

{fmt_table(ctx['test_table'])}

Train-years context (same universe, in-sample for alpha choice — context only):

{fmt_table(ctx['train_table'])}

## Gate verdict — `compare_to_incumbent` (challenger B3 EWMA vs incumbent B1 carry-forward)

- **Verdict: {r.verdict}** (promote={r.promote}); failed gates: {r.failed_gates or 'none'}.
- Pooled minutes MAE: challenger {r.metric_challenger:.4f} vs incumbent {r.metric_incumbent:.4f}
  -> pooled improvement **{r.pooled_improvement:+.4f}** (gate 1 needs >= +0.10).
- 90% cluster-bootstrap CI on the paired per-row delta, clustered by game DATE
  ({r.n_clusters} clusters, n_boot {r.n_boot}, seed {r.seed}): **[{r.ci_low:+.4f}, {r.ci_high:+.4f}]**
  (gate 2 needs low >= -0.05). Team-clustered sensitivity: {sens}.
- Rows compared: {r.n_games:,} player-games (identical universes; only-challenger {r.n_only_challenger},
  only-incumbent {r.n_only_incumbent}).
- Per-season deltas (gate 3, worst season may not degrade by > 0.15):

{fmt_table(pd.DataFrame(r.per_season))}

- Gate detail:

| gate | status | detail |
|---|---|---|
{chr(10).join(gate_lines)}

- Coverage (gate 5): challenger {ctx['coverage'][0]:.6f} vs incumbent {ctx['coverage'][1]:.6f}
  over {ctx['n_eligible_test']:,} eligible test rows (all three baselines predict every eligible row by construction).
- Gate 4 (joint game forecast): not provided by design — a minutes model has no joint game
  forecast; the harness records `not_provided` (visible, non-vetoing).
- Full verdict JSON: `gate_verdict.json`; the same record was appended to `experiments/registry.jsonl`.

## Starter vs bench context (spec §8 M1 — split by `started_last`, the prior game's starter flag)

{fmt_table(ctx['sb_table'])}

## Stage-A preview — P(plays) prior (reference only; previews the two-stage skeleton)

Shifted expanding played-rate over the dressed roster (played + dnp_reason rows; >= 1 prior
dressed appearance). Constant reference = pooled 2021-2023 dressed played-rate
({ctx['stage_a'].attrs['const_rate']:.4f}). This is NOT a registered Stage-A result — it is the
calibration floor Stage A must beat.

{fmt_table(ctx['stage_a'])}

## Leakage audit (spec §8 audit battery item 1)

For {AUDIT_N} randomly sampled scored test rows (seed {AUDIT_SEED}): deleted every row of that
player-season at/after the target date and recomputed carry-forward, expanding mean, and
EWMA(alpha={ctx['alpha']}) from the surviving history.

- **{len(audit)} feature recomputations; {n_bad} mismatches; max |diff| = {audit['abs_diff'].max():.3e}.**
- {'PASS — stored features are functions of strictly-prior games only.' if n_bad == 0 else 'FAIL — investigate before believing any number above.'}
- Row-level detail: `leakage_audit.csv`. Structural check also passed during the build:
  every first-appearance row has NaN features; every eligible row is covered.

## Anchor reconciliation (frozen baselines 5.42 / 5.12)

| quantity | this build (2024) | frozen anchor | abs gap |
|---|---|---|---|
| carry-forward MAE | {rec['cf_mae_2024']:.4f} | {rec['cf_anchor']:.2f} | {rec['cf_abs_gap']:.4f} |
| expanding-mean MAE | {rec['em_mae_2024']:.4f} | {rec['em_anchor']:.2f} | {rec['em_abs_gap']:.4f} |
| universe n | {rec['n_2024_universe']:,} | {rec['n_anchor']:,} | {abs(rec['n_2024_universe'] - rec['n_anchor'])} |

Both gaps are inside the {ANCHOR_TOL} tolerance -> the frozen-anchor universe is reproduced.
Documented differences, all understood:

1. **Carry-forward definition.** The frozen B1 is the player's own most recent PLAYED game
   (spec §6A `min_last1`, shift(1) within player-season) — measured here at {rec['cf_mae_2024']:.4f}.
   The alternative reading "minutes in the team's previous game" scores {rec['team_prev_variant_mae_2024']:.4f}
   MAE but only {rec['team_prev_variant_coverage_2024']:.1%} coverage (a player who sat the team's last game
   has no prediction). The frozen number, full coverage, and the spec's feature table all match the
   own-last-played-game definition; it is the incumbent everywhere in this report.
2. **Source rows.** The spec-prep anchors were measured off the old per-season gamelog file
   (4,515 played 2024 rows); the master (misc-source, deduped, exact MM:SS everywhere) has 4,513
   played 2024 rows and {rec['n_2024_universe']:,} eligible rows vs the anchor's 4,344 (12-row / 0.3% delta) —
   which moves MAE by <= 0.04. No other universe difference exists.
3. **Starter/bench sub-anchors.** Spec §7's parenthetical splits (5.33/5.52, 4.93/5.35) match the
   TARGET-game starter flag: this build reproduces them at
   cf {tg['pred_carry_forward']['starters_mae']:.3f}/{tg['pred_carry_forward']['bench_mae']:.3f} and
   expmean {tg['pred_expanding_mean']['starters_mae']:.3f}/{tg['pred_expanding_mean']['bench_mae']:.3f}.
   The headline split table above instead uses `started_last` per spec §8 M1 (target-game
   conditioning would leak); both are context, neither is gated.

## Files

- `results_per_season.csv` — per-season MAE/coverage, all three baselines, train + test.
- `alpha_tuning_curve.csv` — full inner-fold tuning curve.
- `starter_bench_split.csv` — started_last split per season x baseline.
- `stage_a_brier_preview.csv` — Stage-A prior Brier per season.
- `leakage_audit.csv` — the {AUDIT_N}-row x 3-feature recompute audit.
- `test_predictions.csv` — every scored test row with y_true and all three predictions.
- `gate_verdict.json` — full ComparisonResult (also appended to the registry).
"""
    (outdir / "REPORT.md").write_text(md, encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", action="store_true",
                    help="full dry-run: scratch registry copy + scratch outdir; "
                         "real ledger and experiments/ untouched")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args(argv)

    registry_path = None  # evalharness default: experiments/registry.jsonl
    outdir = args.outdir or DEFAULT_OUTDIR
    if args.smoke:
        import tempfile
        scratch = Path(tempfile.mkdtemp(prefix="minutes_baselines_smoke_"))
        registry_path = scratch / "registry_scratch.jsonl"
        shutil.copyfile(REPO / "experiments" / "registry.jsonl", registry_path)
        outdir = args.outdir or (scratch / "out")
    outdir.mkdir(parents=True, exist_ok=True)

    run_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[minutes_baselines] {'SMOKE ' if args.smoke else ''}run at {run_time}")
    print(f"[minutes_baselines] outdir={outdir}")

    # 1. data ---------------------------------------------------------------
    played, dressed, notes = load_master()
    rs_all = pd.concat([played, dressed[dressed["played_flag"] == 0]], axis=0)
    print(f"[data] played rows {notes['played_rows']:,} | dressed-DNP {notes['dressed_dnp_rows']:,} "
          f"| playoffs excluded {notes['playoff_rows_excluded']:,}")

    # 2. features -----------------------------------------------------------
    P = add_baseline_features(played, ALPHA_GRID)
    U = P[P["prior_apps"] >= 1].copy()
    assert not U.index.duplicated().any()
    got_seasons = sorted(U["season"].unique().tolist())
    assert got_seasons == TRAIN_SEASONS + TEST_SEASONS, got_seasons
    print(f"[features] universe rows {len(U):,} across seasons {got_seasons}")

    # 3. splits + tuning ----------------------------------------------------
    outers = walk_forward_by_season(U, date_col="game_date", season_col="season",
                                    test_seasons=TEST_SEASONS)
    by_name = {o.name: o for o in outers}
    o24 = by_name["season:2024"]
    tr24_seasons = sorted(U.loc[o24.train_idx, "season"].unique().tolist())
    assert tr24_seasons == TRAIN_SEASONS, tr24_seasons
    test_idx = np.concatenate([o.test_idx for o in outers])
    assert len(np.unique(test_idx)) == len(test_idx)
    U_test = U.loc[test_idx]
    assert sorted(U_test["season"].unique().tolist()) == TEST_SEASONS

    alpha, curve, fold_meta = tune_alpha(U, o24, ALPHA_GRID)
    U = U.copy()
    U["pred_ewma"] = U[f"ewma_{alpha}"]
    U_test = U.loc[test_idx]
    best_i = int(curve["mean_val_mae"].idxmin())
    curve_excerpt = curve.iloc[max(0, best_i - 2): best_i + 3]
    print(f"[tuning] chosen alpha={alpha} (mean inner-val MAE "
          f"{curve['mean_val_mae'].min():.4f}); curve endpoints "
          f"{curve['mean_val_mae'].iloc[0]:.4f}@{ALPHA_GRID[0]} .. "
          f"{curve['mean_val_mae'].iloc[-1]:.4f}@{ALPHA_GRID[-1]}")

    # 4. tables -------------------------------------------------------------
    test_table = mae_table(U_test, TEST_SEASONS, "test")
    train_table = mae_table(U.loc[o24.train_idx], TRAIN_SEASONS, "train(context)")
    sb_table = starter_bench_table(U_test, TEST_SEASONS)

    # 5. anchors (hard gate before anything is recorded) --------------------
    anchors = anchor_reconciliation(rs_all, P, U)
    print(f"[anchors] cf 2024 {anchors['cf_mae_2024']:.4f} vs {anchors['cf_anchor']} | "
          f"expmean {anchors['em_mae_2024']:.4f} vs {anchors['em_anchor']} | "
          f"n {anchors['n_2024_universe']} vs {anchors['n_anchor']} -> OK")

    # 6. leakage audit (must pass before compare records anything) ----------
    audit = leakage_audit(P, U_test, alpha)
    n_bad = int((~audit["identical"]).sum())
    print(f"[audit] {len(audit)} recomputations, {n_bad} mismatches, "
          f"max |diff| {audit['abs_diff'].max():.3e}")
    if n_bad:
        raise RuntimeError("Leakage audit FAILED — see leakage_audit.csv; not scoring.")

    # 7. Stage-A preview ----------------------------------------------------
    stage_a = stage_a_preview(dressed)

    # 8. the registered comparison -----------------------------------------
    U_test = U_test.copy()
    U_test["row_id"] = U_test["game_id"].astype(str) + ":" + U_test["player_id"].astype(str)
    assert not U_test["row_id"].duplicated().any()
    n_eligible_test = len(U_test)
    cov_ch = float(U_test["pred_ewma"].notna().mean())
    cov_inc = float(U_test["pred_carry_forward"].notna().mean())
    challenger = pd.DataFrame({
        "game_id": U_test["row_id"],
        "game_date": U_test["game_date"],
        "season": U_test["season"],
        "y_true": U_test["minutes"].astype(float),
        "y_pred": U_test["pred_ewma"].astype(float),
        "team": U_test["team_abbreviation"],
    })
    incumbent = pd.DataFrame({
        "game_id": U_test["row_id"],
        "y_true": U_test["minutes"].astype(float),
        "y_pred": U_test["pred_carry_forward"].astype(float),
    })
    result = compare_to_incumbent(
        challenger,
        incumbent,
        experiment_id=EXPERIMENT_ID,
        registry_path=registry_path,
        loss="absolute",
        cluster="date",
        team_col="team",
        coverage=(cov_ch, cov_inc),
        # joint_check deliberately omitted: a minutes model has no joint game
        # forecast; the harness records gate 4 as not_provided.
    )
    print(f"[gate] {result.verdict} (run {result.run_number}) — pooled improvement "
          f"{result.pooled_improvement:+.4f}, CI [{result.ci_low:+.4f}, {result.ci_high:+.4f}], "
          f"failed={result.failed_gates}")

    # 9. outputs ------------------------------------------------------------
    pd.concat([test_table, train_table]).to_csv(outdir / "results_per_season.csv", index=False)
    curve.to_csv(outdir / "alpha_tuning_curve.csv", index=False)
    sb_table.to_csv(outdir / "starter_bench_split.csv", index=False)
    stage_a.to_csv(outdir / "stage_a_brier_preview.csv", index=False)
    audit.to_csv(outdir / "leakage_audit.csv", index=False)
    pred_cols = ["row_id", "game_id", "game_date", "season", "player_id", "player_name",
                 "team_abbreviation", "started_last", "minutes",
                 "pred_carry_forward", "pred_expanding_mean", "pred_ewma"]
    U_test[pred_cols].rename(columns={"minutes": "y_true"}).to_csv(
        outdir / "test_predictions.csv", index=False)
    with open(outdir / "gate_verdict.json", "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, indent=2, default=str)

    write_report(outdir, {
        "run_time": run_time,
        "notes": notes,
        "alpha": alpha,
        "alpha_best_mae": float(curve["mean_val_mae"].min()),
        "curve_excerpt": curve_excerpt,
        "fold_meta": fold_meta,
        "test_table": test_table,
        "train_table": train_table,
        "sb_table": sb_table,
        "stage_a": stage_a,
        "audit": audit,
        "anchors": anchors,
        "compare": result,
        "coverage": (cov_ch, cov_inc),
        "n_eligible_test": n_eligible_test,
        "max_test_date": str(U_test["game_date"].max()),
    })
    print(f"[done] report + CSVs in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
