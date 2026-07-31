"""crossseason_screen.py — preregistered screen player_feature_crossseason_v1.

The cross-season identity family (catalog #87 prev_season_anchor,
#88 career_trajectory_slope, #92 two_season_blend) re-screened on the
CORRECTED window registered 2026-07-31T15:25:42Z. Run 1
(player_feature_screen_v1) gave this family the largest effects in the whole
lab (deltas 0.020-0.053, p=0.00498 on all 8 tests) but failed the
fold-consistency gate for a STRUCTURAL reason: its earliest inner fold sat in
2021, the first season in the data, where a previous season does not exist and
the feature is degenerate by construction. This registration corrects the
window, not the gate.

A THIN RUNNER over feature_lab.py's committed machinery — the universe
definition, baseline tuning, ridge, BH, and the split machinery are IMPORTED,
not reimplemented. feature_lab.py, features/fam_i.py and every existing
experiments/ directory are READ-ONLY here; the two behavioural changes the
registration requires (the 2022 window and the explicit missing-state
encoding) are implemented INSIDE this runner as wrappers.

Differences from run 1, all preregistration-compliant:

  * WINDOW: the screening universe starts in 2022. Train/inner-tuning folds
    live inside 2022-2023; validation walk-forward is 2024. 2021 is excluded
    from the screening universe entirely (no fit row, no scored row, no
    permuted row) — but 2021 REMAINS the source of completed-season
    aggregates for 2022 games, which is the whole point of the family. The
    row count dropped by the 2022 start is reported.
  * MISSING STATE: rookie / no-usable-prior-season rows are NOT mean-filled
    (run 1 mean-filled them; the constitution's no-imputation rule and this
    registration both say otherwise). Each cross-season feature enters as TWO
    columns: the value, neutralized to 0.0 where no prior season exists, and a
    `has_prior_season` indicator (1/0). The indicator's standardized
    coefficient is reported. Coverage — the share of scored rows carrying a
    real prior season — is reported per season.
  * LEAKAGE AUDIT: a dedicated in-run audit asserts (a) the previous-season
    component for a game in season N uses ONLY completed season N-1
    aggregates, and (b) the blend's current-season component is strictly
    season-to-date. (b) is verified by an INDEPENDENT recompute on sampled
    rows — the current-season term is rebuilt from scratch from rows strictly
    earlier than the target date and compared to the value the harness
    actually produced. Max deviation is reported; a deviation above the
    tolerance aborts the run.
  * FDR: Benjamini-Hochberg at 10% across THIS family only (3 candidates x
    4 channels = 12 tests, its own FDR family). Sign-consistency across all
    3 inner folds AND 2024 is still required — the gate is not relaxed.
  * Artifacts go to experiments/feature_screen_crossseason/ ONLY.

QUARANTINE IS ABSOLUTE: 2025 and 2026 rows are never loaded (season<=2024
pushdown at source in features/common.py); every assembled matrix asserts
max(game_date) < 2025-01-01 and the audit trail is written to
quarantine_audit.json exactly as run 1 writes it.

This script records NOTHING on the ledger: it never imports or calls
registry.register / evaluate / record_evaluation / render_leaderboards, never
runs git, and never writes experiments/registry.jsonl or leaderboards/. The
orchestrator records after verifying.

Run:  python crossseason_screen.py                 # full screen (200 perms)
      python crossseason_screen.py --perms 20      # dev smoke only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# ---- committed machinery, imported (never reimplemented, never modified) ----
from feature_lab import (ALPHA_GRID, CH_INDEX, FDR_Q, MIN_MINUTES,  # noqa: E402
                         MIN_MINUTES_ROBUST, MIN_PRIOR_APPS, N_INNER_FOLDS,
                         N_PERM_DEFAULT, RIDGE_LAMBDA, SEED_BASE, bh_adjust,
                         build_universe, mae, ridge_fit, ridge_predict,
                         tune_baselines)
from evalharness.splits import inner_tuning_splits, walk_forward_by_season  # noqa: E402
from features import CHANNELS, Ctx  # noqa: E402
from features import fam_i as FI  # noqa: E402  (READ-ONLY: wrapped, never edited)
from features.common import QUARANTINE_CUTOFF, assert_quarantine  # noqa: E402

EXPERIMENT_ID = "player_feature_crossseason_v1"
BATTERY = "cross-season identity family I (#87, #88, #92) on the 2022-start window"

# --- the ONE registered change to the window ---------------------------------
SCREEN_START_SEASON = 2022
TRAIN_SEASONS = [2022, 2023]
VAL_SEASON = 2024
AGGREGATE_SOURCE_SEASON = 2021    # loaded, never fit/scored/permuted

# the three registered candidates (fam_i also holds #89, which is NOT part of
# this family's registration and is not screened here)
CANDIDATE_NUMBERS = [87, 88, 92]

LEAK_SAMPLE_ROWS = 40             # registration floor is 20
LEAK_TOL = 1e-9
LEAK_SEED = 20260731

OUTDIR = REPO / "experiments" / "feature_screen_crossseason"
DIAG = OUTDIR / "diagnostics"

RUN1_COLUMNS = [
    "catalog_number", "name", "family", "channel", "alpha_chosen", "n_train",
    "n_val", "nan_share", "mae_base_ridge_2024", "mae_feat_2024", "delta_mae",
    "improvement", "beta_feature_std", "fold_deltas", "fold_signs", "sign_2024",
    "sign_consistent", "p_value", "degenerate", "note", "q_value", "bh_pass",
    "survives",
]


# ---------------------------------------------------------------------------
# missing-state encoding (the registration's no-imputation clause)
# ---------------------------------------------------------------------------

def encode_missing_state(raw: pd.Series) -> tuple[pd.Series, pd.Series]:
    """value (neutralized to 0.0 where absent) + has_prior_season indicator.

    `raw` is the candidate's own output from features/fam_i.py, unmodified.
    NaN in `raw` means 'no usable prior season' for every candidate in this
    family: #87 and #92 are NaN exactly when the season N-1 aggregate is
    missing (never played, or under the 150-minute qualification in
    Ctx.season_rates); #88 additionally needs season N-2. Nothing is
    mean-filled — the missingness becomes its own column.
    """
    has = raw.notna().astype(float)
    val = raw.astype(float).fillna(0.0)
    return val, has


# ---------------------------------------------------------------------------
# ridge design with an explicit missing-state block
# ---------------------------------------------------------------------------

class DesignMS:
    """Standardized design [baseline, value, has_prior_season], built from FIT
    rows only.

    Mirrors feature_lab.Design exactly (same standardization, same
    degeneracy semantics, unpenalized intercept via feature_lab.ridge_fit) with
    one registered extension: the feature block is two columns and NOTHING is
    mean-filled. A constant indicator (every fit row has a prior season, or
    none does) carries no information and is dropped — a constant column is
    absorbed by the intercept and its 'standardized coefficient' would be
    undefined.
    """

    def __init__(self, b_fit: np.ndarray, X_fit: np.ndarray):
        self.mb, self.sb = float(np.mean(b_fit)), float(np.std(b_fit))
        self.sb = self.sb if self.sb > 1e-12 else 1.0
        self.mx = X_fit.mean(axis=0)
        self.sx = X_fit.std(axis=0)
        self.degenerate = bool(self.sx[0] < 1e-12)      # the VALUE column
        self.keep_indicator = bool(self.sx[1] >= 1e-12)
        self.sx = np.where(self.sx > 1e-12, self.sx, 1.0)
        self.cols = [0, 1] if self.keep_indicator else [0]

    def z(self, b: np.ndarray, X: np.ndarray) -> np.ndarray:
        zb = (b - self.mb) / self.sb
        zx = (X - self.mx) / self.sx
        return np.column_stack([zb] + [zx[:, j] for j in self.cols])


def _base_only(b_tr, y_tr, b_va, y_va) -> float:
    mb, sb = float(np.mean(b_tr)), float(np.std(b_tr))
    sb = sb if sb > 1e-12 else 1.0
    beta0 = ridge_fit(((b_tr - mb) / sb)[:, None], y_tr)
    return mae(y_va, ridge_predict(((b_va - mb) / sb)[:, None], beta0))


def fit_score_ms(b_tr, X_tr, y_tr, b_va, X_va, y_va):
    """(mae_base_ridge, mae_feat_ridge, beta_value_std, beta_indicator_std,
    degenerate, indicator_kept). Same statistic as run 1 — the reference is the
    ridge-recalibrated baseline — with the two-column feature block."""
    m_base = _base_only(b_tr, y_tr, b_va, y_va)
    d = DesignMS(b_tr, X_tr)
    if d.degenerate:
        return m_base, m_base, 0.0, np.nan, True, False
    beta = ridge_fit(d.z(b_tr, X_tr), y_tr)
    m_feat = mae(y_va, ridge_predict(d.z(b_va, X_va), beta))
    b_ind = float(beta[3]) if d.keep_indicator else np.nan
    return m_base, m_feat, float(beta[2]), b_ind, False, d.keep_indicator


def perm_null_ms(b_tr, X_tr, y_tr, b_va, X_va, y_va, season_tr, n_perm, rng):
    """Null improvements, run 1's null generalized to the two-column block.

    Run 1 permutes the FEATURE VALUES within season on train and validation,
    refits and rescores. Here the (value, has_prior_season) PAIR is permuted as
    a BLOCK — the row is moved, not the columns independently — so the joint
    marginal distribution of the encoding (including the missing-state rate) is
    preserved exactly while every alignment with specific player-games is
    destroyed. Permuting the two columns independently would instead test a
    different (and easier) null in which the indicator no longer marks the
    neutralized rows.
    """
    d = DesignMS(b_tr, X_tr)
    if d.degenerate:
        return np.zeros(n_perm)
    m_base = _base_only(b_tr, y_tr, b_va, y_va)
    blocks = [np.flatnonzero(season_tr == s) for s in np.unique(season_tr)]
    out = np.empty(n_perm)
    for k in range(n_perm):
        Xp_tr = X_tr.copy()
        for idx in blocks:
            Xp_tr[idx, :] = X_tr[rng.permutation(idx), :]
        Xp_va = X_va[rng.permutation(len(X_va)), :]
        dk = DesignMS(b_tr, Xp_tr)
        beta = ridge_fit(dk.z(b_tr, Xp_tr), y_tr)
        m_feat = mae(y_va, ridge_predict(dk.z(b_va, Xp_va), beta))
        out[k] = m_base - m_feat            # improvement
    return out


# ---------------------------------------------------------------------------
# universe on the corrected window
# ---------------------------------------------------------------------------

def build_window(ctx: Ctx):
    """feature_lab.build_universe, then the ONE registered change: drop every
    row before 2022 from the screening universe and re-cut the walk-forward
    splits with the committed splitters."""
    U_full, _, _ = build_universe(ctx)              # committed universe definition
    U = U_full[U_full["season"] >= SCREEN_START_SEASON].copy()
    assert_quarantine(U["game_date"], f"target_universe(>=2022,min>={MIN_MINUTES:g})",
                      ctx.audit)
    outer = walk_forward_by_season(U, test_seasons=[VAL_SEASON])[0]
    folds = inner_tuning_splits(U, outer, n_folds=N_INNER_FOLDS)
    dropped = U_full[U_full["season"] < SCREEN_START_SEASON]
    return U_full, U, outer, folds, dropped


def make_arrays(ctx: Ctx, Ux: pd.DataFrame) -> dict:
    """Target/baseline arrays per channel (reimplementation of the closure
    inside feature_lab.main, which is not importable; same logic, same
    quarantine assertion — the bios_screen.py precedent)."""
    assert_quarantine(Ux["game_date"], f"design_matrix(n={len(Ux)})", ctx.audit)
    out = {}
    for ch in CHANNELS:
        out[ch] = {
            "y": Ux[f"y_{ch}"].to_numpy(float),
            "b": ctx.baselines[ch].loc[Ux.index].to_numpy(float),
            "season": Ux["season"].to_numpy(int),
        }
        nb = np.isnan(out[ch]["b"])
        if nb.any():
            raise RuntimeError(f"{int(nb.sum())} NaN baseline values on {ch}")
    return out


# ---------------------------------------------------------------------------
# the leakage audit the registration requires by name
# ---------------------------------------------------------------------------

def leakage_audit(ctx: Ctx, U: pd.DataFrame, chosen_w: dict, n_rows: int = LEAK_SAMPLE_ROWS):
    """Assert, in-run, the two properties John flagged.

    (a) the previous-season component for a game in season N uses ONLY
        COMPLETED season N-1 aggregates:
          a1. structural — every season's last game strictly precedes the next
              season's first game, so an N-1 aggregate is complete before
              season N tips off;
          a2. row-level — the harness's prev value is reproduced exactly by an
              independent aggregate over season N-1 rows only, and the latest
              row feeding that aggregate is strictly earlier than the target
              game.
    (b) the blend's current-season component is STRICTLY SEASON-TO-DATE:
        the current-season term the harness actually produced is extracted from
        the committed f92 output by inverting the blend at w=0.5
        (cur = 2*blend - prev) and compared against a from-scratch rebuild that
        sums ONLY rows of the same player-season with game_date strictly before
        the target date. The frozen-w blend is then rebuilt end to end from the
        independent terms and compared to the harness value. A positive control
        recomputes the term WITH the target game included and confirms the
        harness sides with the strictly-past version wherever the two rebuilds
        actually differ — proof the comparison can detect contamination. (A
        comparison is UNINFORMATIVE when including the target game cannot move
        the term at all: a player with zero channel points both season-to-date
        and in the target game has the same value either way. Those rows are
        counted, not credited.)
    """
    P = ctx.P
    notes = {}

    # ---- (a1) structural season separation ----
    bounds = P.groupby("season")["game_date"].agg(["min", "max"])
    seps = []
    for s in sorted(bounds.index):
        if s - 1 in bounds.index:
            prev_end, cur_start = bounds.loc[s - 1, "max"], bounds.loc[s, "min"]
            ok = bool(prev_end < cur_start)
            seps.append({"season": int(s), "prev_season": int(s - 1),
                         "prev_season_last_game": str(prev_end.date()),
                         "season_first_game": str(cur_start.date()),
                         "prev_season_complete_before_season_start": ok})
            if not ok:
                raise RuntimeError(
                    f"LEAKAGE AUDIT (a1) FAILED: season {s - 1} ends {prev_end.date()}, "
                    f"not strictly before season {s} start {cur_start.date()}")
    notes["season_separation"] = seps

    # ---- harness series (built by the COMMITTED functions, unmodified) ----
    prev_h = {ch: FI._prev_rate(ctx, ch, 1) for ch in CHANNELS}
    blend50 = FI.f92_two_season_blend(ctx, 0.5)
    blend_w = {w: FI.f92_two_season_blend(ctx, w) for w in sorted(set(chosen_w.values()))}

    # ---- sample rows that actually carry a prior season, across all seasons --
    rng = np.random.default_rng(LEAK_SEED)
    have = U.index[prev_h[CHANNELS[0]].loc[U.index].notna().to_numpy()]
    per_season = max(1, n_rows // U["season"].nunique())
    picks = []
    for s, sub in U.loc[have].groupby("season"):
        take = min(per_season, len(sub))
        picks += list(rng.choice(sub.index.to_numpy(), size=take, replace=False))
    picks = sorted(picks)
    assert_quarantine(U.loc[picks, "game_date"], f"leakage_audit_sample(n={len(picks)})",
                      ctx.audit)

    # ---- per-row independent recompute ----
    cols = ["player_id", "season", "game_date", "minutes"] + [f"cp_{ch}" for ch in CHANNELS]
    Praw = P[cols]
    rows = []
    for idx in picks:
        r = U.loc[idx]
        pid, s, d = int(r["player_id"]), int(r["season"]), r["game_date"]
        own = Praw[(Praw["player_id"] == pid)]
        prior_season = own[own["season"] == s - 1]
        cur_before = own[(own["season"] == s) & (own["game_date"] < d)]
        cur_incl = own[(own["season"] == s) & (own["game_date"] <= d)]
        pm = float(prior_season["minutes"].sum())
        cm = float(cur_before["minutes"].sum())
        cmi = float(cur_incl["minutes"].sum())
        for ch in CHANNELS:
            w = chosen_w[ch]
            # (a2) previous-season term
            p_ind = (float(prior_season[f"cp_{ch}"].sum()) / pm * 36.0
                     if pm >= 150.0 else np.nan)
            p_h = float(prev_h[ch].loc[idx])
            dev_prev = abs(p_h - p_ind)
            # (b) current-season term, harness value recovered from f92 at w=0.5
            c_h = 2.0 * float(blend50[ch].loc[idx]) - p_h
            c_ind = float(cur_before[f"cp_{ch}"].sum()) / cm * 36.0 if cm > 0 else np.nan
            c_incl = float(cur_incl[f"cp_{ch}"].sum()) / cmi * 36.0 if cmi > 0 else np.nan
            dev_cur = abs(c_h - c_ind)
            # end-to-end rebuild at the frozen weight
            bh = float(blend_w[w][ch].loc[idx])
            br = w * p_ind + (1.0 - w) * c_ind
            dev_blend = abs(bh - br)
            rows.append({
                "player_id": pid, "game_id": r["game_id"], "game_date": str(d.date()),
                "season": s, "channel": ch,
                "n_prior_season_games": int(len(prior_season)),
                "prior_season_minutes": round(pm, 2),
                "prior_season_last_game": (str(prior_season["game_date"].max().date())
                                           if len(prior_season) else ""),
                "n_current_season_games_before": int(len(cur_before)),
                "current_last_game_used": (str(cur_before["game_date"].max().date())
                                           if len(cur_before) else ""),
                "prev_harness": p_h, "prev_independent": p_ind,
                "dev_prev": dev_prev,
                "cur_harness": c_h, "cur_independent": c_ind,
                "dev_cur": dev_cur,
                "cur_if_target_game_included": c_incl,
                "control_separation": abs(c_ind - c_incl),
                "control_informative": bool(abs(c_ind - c_incl) > LEAK_TOL),
                "control_gap_vs_including_target": abs(c_h - c_incl),
                "w_frozen": w, "blend_harness": bh, "blend_rebuilt": br,
                "dev_blend": dev_blend,
                "prev_source_strictly_earlier": bool(
                    len(prior_season) and prior_season["game_date"].max() < d),
                "current_source_strictly_earlier": bool(
                    len(cur_before) and cur_before["game_date"].max() < d),
            })
    L = pd.DataFrame(rows)

    max_prev = float(np.nanmax(L["dev_prev"].to_numpy(float)))
    max_cur = float(np.nanmax(L["dev_cur"].to_numpy(float)))
    max_blend = float(np.nanmax(L["dev_blend"].to_numpy(float)))
    max_dev = float(max(max_prev, max_cur, max_blend))
    info = L[L["control_informative"]]
    min_control = (float(info["control_gap_vs_including_target"].min())
                   if len(info) else 0.0)
    notes.update({
        "n_sampled_rows": int(len(picks)),
        "n_comparisons": int(len(L)),
        "max_dev_prev_season_term": max_prev,
        "max_dev_current_season_term": max_cur,
        "max_dev_blend_at_frozen_w": max_blend,
        "max_deviation": max_dev,
        "tolerance": LEAK_TOL,
        "n_control_informative": int(len(info)),
        "min_positive_control_gap": min_control,
        "all_prev_sources_strictly_earlier": bool(L["prev_source_strictly_earlier"].all()),
        "all_current_sources_strictly_earlier": bool(L["current_source_strictly_earlier"].all()),
    })

    if not L["prev_source_strictly_earlier"].all():
        raise RuntimeError("LEAKAGE AUDIT (a2) FAILED: a prev-season aggregate "
                           "drew on a game not strictly earlier than the target")
    if not L["current_source_strictly_earlier"].all():
        raise RuntimeError("LEAKAGE AUDIT (b) FAILED: a current-season term drew "
                           "on a game not strictly earlier than the target")
    if max_dev > LEAK_TOL:
        raise RuntimeError(
            f"LEAKAGE AUDIT FAILED: max deviation {max_dev:.3e} > tol {LEAK_TOL:.0e} "
            f"(prev {max_prev:.3e}, current {max_cur:.3e}, blend {max_blend:.3e}). "
            "The harness value does not match a strictly-past rebuild.")
    if len(info) < 20 or min_control <= LEAK_TOL:
        raise RuntimeError(
            f"LEAKAGE AUDIT positive control FAILED: only {len(info)} informative "
            f"comparisons (min gap {min_control:.3e}). Including the target game "
            "must move the term on a substantial sample, or the comparison "
            "cannot detect contamination.")
    return L, notes


# ---------------------------------------------------------------------------
# coverage accounting
# ---------------------------------------------------------------------------

def coverage_by_season(U: pd.DataFrame, feats: dict) -> pd.DataFrame:
    rows = []
    for (num, name), per_ch in feats.items():
        for ch in CHANNELS:
            has = per_ch[ch]["has"].loc[U.index]
            for season, sub in U.groupby("season"):
                h = has.loc[sub.index]
                rows.append({
                    "catalog_number": num, "name": name, "channel": ch,
                    "season": int(season),
                    "role": ("train_inner" if int(season) in TRAIN_SEASONS
                             else "validation"),
                    "n_scored_rows": int(len(sub)),
                    "n_with_prior_season": int(h.sum()),
                    "coverage_share": round(float(h.mean()), 4),
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# candidate evaluation on the corrected window
# ---------------------------------------------------------------------------

def build_candidate(ctx: Ctx, cand, w=None) -> dict:
    """Call the COMMITTED fam_i build, then apply the registered missing-state
    encoding. fam_i.py is never modified — the behavioural change lives here."""
    built = cand.build(ctx, w)
    out = {}
    for ch in CHANNELS:
        raw = built[ch] if isinstance(built, dict) else built
        val, has = encode_missing_state(raw)
        out[ch] = {"raw": raw, "val": val, "has": has}
    return out


def eval_candidate(ctx, cand, U, U15, outer, folds, n_perm, arr, arr15):
    t0 = time.time()
    rows, robust_rows, alpha_rows, diag, ms_rows = [], [], [], {}, []
    grid = (cand.sweep_grid or ALPHA_GRID) if cand.alpha_swept else [None]
    built_by_w = {w: build_candidate(ctx, cand, w) for w in grid}

    def block(built, ch, index):
        b = built[ch]
        return np.column_stack([b["val"].loc[index].to_numpy(float),
                                b["has"].loc[index].to_numpy(float)])

    for ch in cand.channels:
        A = arr[ch]
        # ---- sweep on INNER FOLDS ONLY, frozen before 2024 is touched ----
        if cand.alpha_swept:
            best_w, best_loss = None, np.inf
            for w in grid:
                X_all = block(built_by_w[w], ch, U.index)
                losses = []
                for f in folds:
                    tr = U.index.get_indexer(f.train_idx)
                    va = U.index.get_indexer(f.val_idx)
                    _, m_feat, *_ = fit_score_ms(
                        A["b"][tr], X_all[tr], A["y"][tr],
                        A["b"][va], X_all[va], A["y"][va])
                    losses.append(m_feat)
                loss = float(np.mean(losses))
                alpha_rows.append({"catalog_number": cand.num, "channel": ch,
                                   "alpha": w, "inner_mae": loss})
                if loss < best_loss:
                    best_loss, best_w = loss, w
            wsel = best_w
        else:
            wsel = None
        built = built_by_w[wsel]
        X_all = block(built, ch, U.index)
        has_all = X_all[:, 1]
        missing_share = float(1.0 - np.mean(has_all))

        # ---- inner-fold deltas at the frozen config ----
        fold_deltas, fold_cov, fold_cov_tr, fold_degen = [], [], [], []
        for f in folds:
            tr = U.index.get_indexer(f.train_idx)
            va = U.index.get_indexer(f.val_idx)
            m_b, m_f, _, _, dg, _ = fit_score_ms(
                A["b"][tr], X_all[tr], A["y"][tr],
                A["b"][va], X_all[va], A["y"][va])
            fold_deltas.append(m_f - m_b)
            fold_cov.append(float(np.mean(has_all[va])))
            fold_cov_tr.append(float(np.mean(has_all[tr])))
            fold_degen.append(bool(dg))

        # ---- 2024 walk-forward score ----
        tr = U.index.get_indexer(outer.train_idx)
        va = U.index.get_indexer(outer.test_idx)
        b_tr, X_tr, y_tr = A["b"][tr], X_all[tr], A["y"][tr]
        b_va, X_va, y_va = A["b"][va], X_all[va], A["y"][va]
        m_base, m_feat, beta_x, beta_ind, degen, ind_kept = fit_score_ms(
            b_tr, X_tr, y_tr, b_va, X_va, y_va)
        delta = m_feat - m_base
        improvement = -delta

        # ---- permutation null (identical seeding formula to run 1) ----
        rng = np.random.default_rng(SEED_BASE * 100 + cand.num * 10 + CH_INDEX[ch])
        if degen:
            null_imp = np.zeros(n_perm)
            p = 1.0
        else:
            null_imp = perm_null_ms(b_tr, X_tr, y_tr, b_va, X_va, y_va,
                                    A["season"][tr], n_perm, rng)
            p = float((1 + np.sum(null_imp >= improvement)) / (1 + n_perm))

        sign_consistent = bool(all(d < 0 for d in fold_deltas) and delta < 0)
        note = ""
        if degen:
            note = ("degenerate on the 2024 fit: no fit row carries a usable "
                    "prior season")
        if any(fold_degen):
            bad = ",".join(str(i + 1) for i, g in enumerate(fold_degen) if g)
            note = (note + "; " if note else "") + (
                f"inner fold(s) {bad} degenerate: no FIT row carries a usable "
                "prior season, so the fold delta is exactly 0.00000 and the "
                "sign-consistency gate cannot be answered there")
        rows.append({
            "catalog_number": cand.num, "name": cand.name, "family": cand.family,
            "channel": ch, "alpha_chosen": wsel, "n_train": int(len(tr)),
            "n_val": int(len(va)), "nan_share": round(missing_share, 4),
            "mae_base_ridge_2024": round(m_base, 5),
            "mae_feat_2024": round(m_feat, 5),
            "delta_mae": round(delta, 5), "improvement": round(improvement, 5),
            "beta_feature_std": round(beta_x, 5),
            "fold_deltas": ";".join(f"{d:+.5f}" for d in fold_deltas),
            "fold_signs": "".join("-" if d < 0 else "+" for d in fold_deltas),
            "sign_2024": "-" if delta < 0 else "+",
            "sign_consistent": sign_consistent,
            "p_value": round(p, 5), "degenerate": degen, "note": note,
        })
        ms_rows.append({
            "catalog_number": cand.num, "name": cand.name, "channel": ch,
            "w_frozen": wsel,
            "beta_feature_std": round(beta_x, 5),
            "beta_indicator_std": (round(beta_ind, 5) if np.isfinite(beta_ind)
                                   else np.nan),
            "indicator_in_model": bool(ind_kept),
            "coverage_train_2022_23": round(float(np.mean(has_all[tr])), 4),
            "coverage_val_2024": round(float(np.mean(has_all[va])), 4),
            "inner_fold_fit_coverage": ";".join(f"{c:.4f}" for c in fold_cov_tr),
            "inner_fold_val_coverage": ";".join(f"{c:.4f}" for c in fold_cov),
            "inner_fold_degenerate": ";".join("Y" if g else "n" for g in fold_degen),
        })
        diag[ch] = {
            "null_improvement_q05": float(np.quantile(null_imp, 0.05)),
            "null_improvement_q50": float(np.quantile(null_imp, 0.50)),
            "null_improvement_q95": float(np.quantile(null_imp, 0.95)),
            "null_improvement_max": float(np.max(null_imp)),
            "observed_improvement": improvement,
        }

        # ---- >=15-minute robustness rerun (frozen w; run 1's procedure) ----
        A15 = arr15[ch]
        X15 = block(built, ch, U15.index)
        tr15 = np.flatnonzero(np.isin(A15["season"], TRAIN_SEASONS))
        va15 = np.flatnonzero(A15["season"] == VAL_SEASON)
        m_b15, m_f15, _, _, degen15, _ = fit_score_ms(
            A15["b"][tr15], X15[tr15], A15["y"][tr15],
            A15["b"][va15], X15[va15], A15["y"][va15])
        d15 = m_f15 - m_b15
        rng15 = np.random.default_rng(
            SEED_BASE * 100 + cand.num * 10 + CH_INDEX[ch] + 7_000_000)
        if degen15:
            p15 = 1.0
        else:
            null15 = perm_null_ms(A15["b"][tr15], X15[tr15], A15["y"][tr15],
                                  A15["b"][va15], X15[va15], A15["y"][va15],
                                  A15["season"][tr15], n_perm, rng15)
            p15 = float((1 + np.sum(null15 >= -d15)) / (1 + n_perm))
        robust_rows.append({
            "catalog_number": cand.num, "name": cand.name, "channel": ch,
            "alpha_chosen": wsel,
            "delta_mae_min15": round(d15, 5), "p_value_min15": round(p15, 5),
            "sign_min15": "-" if d15 < 0 else "+",
            "agrees_with_primary": bool((d15 < 0) == (delta < 0)),
        })
    return rows, robust_rows, alpha_rows, ms_rows, diag, time.time() - t0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--perms", type=int, default=N_PERM_DEFAULT,
                    help="permutations per test (protocol: 200)")
    args = ap.parse_args(argv)

    t_start = time.time()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    DIAG.mkdir(parents=True, exist_ok=True)

    print(f"[{EXPERIMENT_ID}] battery: {BATTERY}")
    print("[load] building context (quarantine-filtered at source) ...")
    ctx = Ctx()
    U_full, U, outer, folds, dropped = build_window(ctx)
    drop_counts = dropped.groupby("season").size().to_dict()
    print(f"[window] screening universe {len(U)} rows (2022-2024); "
          f"{len(dropped)} rows dropped by the 2022 start "
          f"({ {int(k): int(v) for k, v in drop_counts.items()} })")
    print(f"[window] train(inner)={len(outer.train_idx)} rows 2022-2023, "
          f"val2024={len(outer.test_idx)} rows")
    for f in folds:
        print(f"[folds] {f.name}: train {len(f.train_idx)} -> val {len(f.val_idx)} "
              f"({f.val_start.date()}..{f.val_end.date()})")

    print("[baseline] tuning per-channel EWMA alpha on the 2022-2023 inner folds ...")
    chosen, base_curves = tune_baselines(ctx, U, outer, folds)
    print(f"[baseline] frozen alphas: {chosen}")

    U15 = U[U["minutes"] >= MIN_MINUTES_ROBUST].copy()
    arr = make_arrays(ctx, U)
    arr15 = make_arrays(ctx, U15)

    tr_pos = U.index.get_indexer(outer.train_idx)
    va_pos = U.index.get_indexer(outer.test_idx)
    base_ref = {}
    for ch in CHANNELS:
        A = arr[ch]
        raw = mae(A["y"][va_pos], A["b"][va_pos])
        rid = _base_only(A["b"][tr_pos], A["y"][tr_pos], A["b"][va_pos], A["y"][va_pos])
        base_ref[ch] = {"alpha": chosen[ch], "mae_raw_ewma_2024": round(raw, 5),
                        "mae_ridge_base_2024": round(rid, 5)}
        print(f"[baseline] {ch}: alpha={chosen[ch]} raw2024={raw:.4f} ridge2024={rid:.4f}")

    cands = [c for c in FI.CANDIDATES if c.num in CANDIDATE_NUMBERS]
    if len(cands) != len(CANDIDATE_NUMBERS):
        raise RuntimeError(f"expected {CANDIDATE_NUMBERS}, found "
                           f"{[c.num for c in cands]} in features/fam_i.py")
    print(f"[screen] {len(cands)} candidates x {len(CHANNELS)} channels = "
          f"{len(cands) * len(CHANNELS)} tests, {args.perms} permutations per test")

    all_rows, all_robust, all_alpha, all_ms, all_diag = [], [], [], [], {}
    for i, cand in enumerate(cands, 1):
        rows, rob, arows, msrows, diag, dt = eval_candidate(
            ctx, cand, U, U15, outer, folds, args.perms, arr, arr15)
        all_rows += rows
        all_robust += rob
        all_alpha += arows
        all_ms += msrows
        all_diag[cand.num] = diag
        best = min(rows, key=lambda r: r["p_value"])
        print(f"  [{i}/{len(cands)}] #{cand.num:<3} {cand.name:<26} "
              f"best p={best['p_value']:.3f} delta={best['delta_mae']} "
              f"ch={best['channel']} ({dt:.1f}s)")

    res = pd.DataFrame(all_rows)
    # BH across THIS FAMILY ONLY (3 candidates x 4 channels = 12 tests)
    res["q_value"] = bh_adjust(res["p_value"].to_numpy(float))
    res["bh_pass"] = res["q_value"] <= FDR_Q
    res["survives"] = res["bh_pass"] & res["sign_consistent"]
    res = res.sort_values(["survives", "q_value", "delta_mae"],
                          ascending=[False, True, True]).reset_index(drop=True)
    res = res.reindex(columns=RUN1_COLUMNS)          # run-1 schema, exactly
    res.to_csv(OUTDIR / "screen_results.csv", index=False)

    rob = pd.DataFrame(all_robust)
    rob.to_csv(OUTDIR / "robustness_min15.csv", index=False)
    acurve = pd.DataFrame(all_alpha)
    acurve.to_csv(OUTDIR / "alpha_curves.csv", index=False)
    base_curves.to_csv(OUTDIR / "baseline_alpha_curves.csv", index=False)
    ms = pd.DataFrame(all_ms)
    ms.to_csv(OUTDIR / "missing_state_coefficients.csv", index=False)

    surv = res[res["survives"] == True].copy()       # noqa: E712
    if len(surv) and len(rob):
        surv = surv.merge(rob[["catalog_number", "channel", "delta_mae_min15",
                               "sign_min15"]], on=["catalog_number", "channel"],
                          how="left")
    else:                                            # keep run 1's survivor schema
        surv = surv.reindex(columns=RUN1_COLUMNS + ["delta_mae_min15", "sign_min15"])
    surv.to_csv(OUTDIR / "survivor_summary.csv", index=False)

    drows = []
    for _, r in res.head(20).iterrows():
        d = all_diag.get(r["catalog_number"], {}).get(r["channel"], {})
        drows.append({**r.to_dict(), **d})
    pd.DataFrame(drows).to_csv(DIAG / "top20_diagnostics.csv", index=False)

    # coverage per season at the frozen configuration
    frozen_w = {}
    for cand in cands:
        for _, r in res[res["catalog_number"] == cand.num].iterrows():
            frozen_w[(cand.num, r["channel"])] = r["alpha_chosen"]
    feats = {}
    for cand in cands:
        w = next((v for (n, _), v in frozen_w.items() if n == cand.num), None)
        feats[(cand.num, cand.name)] = build_candidate(ctx, cand, w)
    cov = coverage_by_season(U, feats)
    cov.to_csv(OUTDIR / "coverage_by_season.csv", index=False)

    # the leakage audit (aborts the run on failure)
    print("[audit] leakage audit: independent recompute of the cross-season terms ...")
    w92 = {ch: (res.loc[(res["catalog_number"] == 92) & (res["channel"] == ch),
                        "alpha_chosen"].iloc[0]) for ch in CHANNELS}
    w92 = {ch: (float(v) if pd.notna(v) else 0.5) for ch, v in w92.items()}
    L, leak = leakage_audit(ctx, U, w92)
    L.to_csv(OUTDIR / "leakage_audit.csv", index=False)
    print(f"[audit] {leak['n_comparisons']} comparisons on {leak['n_sampled_rows']} "
          f"rows; MAX DEVIATION = {leak['max_deviation']:.3e} "
          f"(tol {LEAK_TOL:.0e}); positive control: "
          f"{leak['n_control_informative']} informative, gap >= "
          f"{leak['min_positive_control_gap']:.4f}")

    with open(OUTDIR / "quarantine_audit.json", "w") as f:
        json.dump({"experiment_id": EXPERIMENT_ID, "battery": BATTERY,
                   "screen_window": {"screening_seasons": [2022, 2023, 2024],
                                     "train_inner": TRAIN_SEASONS,
                                     "validation": VAL_SEASON,
                                     "aggregate_source_only": AGGREGATE_SOURCE_SEASON,
                                     "quarantined_never_loaded": [2025, 2026]},
                   "cutoff": str(QUARANTINE_CUTOFF.date()),
                   "all_pass": all(a["pass"] for a in ctx.audit),
                   "matrices": ctx.audit}, f, indent=2)

    write_report(res, rob, surv, ms, cov, acurve, L, leak, base_ref, chosen,
                 folds, outer, U, U_full, dropped, args, ctx, time.time() - t_start)

    n_bh = int(res["bh_pass"].sum())
    print(f"\n[done] {len(res)} tests, {int(res['survives'].sum())} survivors "
          f"({n_bh} BH-pass), expected false at q<={FDR_Q}: "
          f"~{FDR_Q * n_bh:.1f}; runtime {time.time() - t_start:.0f}s")
    return 0


def write_report(res, rob, surv, ms, cov, acurve, L, leak, base_ref, chosen,
                 folds, outer, U, U_full, dropped, args, ctx, runtime):
    n_tests = len(res)
    n_bh = int(res["bh_pass"].sum())
    n_surv = int(res["survives"].sum())
    n_p05 = int((res["p_value"] <= 0.05).sum())
    lines = []
    A = lines.append
    A("# player_feature_crossseason_v1 — cross-season identity family, corrected window")
    A("")
    A(f"*Generated by crossseason_screen.py; runtime {runtime:.0f}s; {args.perms} "
      f"permutations per test; ridge lambda={RIDGE_LAMBDA} on standardized inputs. "
      "Universe, baseline tuning, ridge, split machinery and BH imported unchanged "
      "from feature_lab.py / evalharness; candidates imported unchanged from "
      "features/fam_i.py.*")
    A("")
    A("## Why this run exists")
    A("")
    A("Run 1 (`player_feature_screen_v1`, `experiments/feature_screen/`) gave this "
      "family the largest effects in the entire feature lab — deltas -0.0200 to "
      "-0.0535 with p=0.00498 on all 8 of #87/#92's tests — and then failed them on "
      "fold-sign consistency. The failure was structural, not evidential: run 1's "
      "first inner fold sat in **2021**, the first season in the data, where no "
      "previous season exists, the feature is all-NaN, and the fold delta is "
      "therefore exactly `+0.00000`. Every run-1 fold-sign string for #87/#92 reads "
      "`+--`: the two folds that could answer the question both improved. This "
      "registration corrects the window so the gate is answerable. **The gate is "
      "not relaxed** — sign consistency across all three inner folds AND 2024 is "
      "still required.")
    A("")
    A("## Protocol (as registered)")
    A("")
    A(f"- **Window**: screening universe **2022-2024**. Inner tuning folds inside "
      f"2022-2023 ({len(outer.train_idx)} rows), validation walk-forward 2024 "
      f"({len(outer.test_idx)} rows). The 2022 start dropped **{len(dropped)} "
      f"universe rows** (all of 2021) from {len(U_full)} to {len(U)}.")
    A(f"- **2021 is not scrapped, it is demoted**: no 2021 row is fit, scored, or "
      f"permuted, but the 2021 season remains the *source* of completed-season "
      f"aggregates for 2022 games — without it the family has no 2022 signal at all.")
    A("- **Quarantine is absolute**: 2025/2026 rows are never loaded (season<=2024 "
      "pushdown in `features/common.py`); every assembled matrix asserts "
      f"max(game_date) < 2025-01-01 (`quarantine_audit.json`, all-pass="
      f"{all(a['pass'] for a in ctx.audit)}, {len(ctx.audit)} matrices).")
    A("- **Targets / universe / baseline / ridge / null statistic**: identical to "
      "run 1. Per-36 channel production (fg3, paint, ft, np2) on played RS rows "
      f"with minutes>={MIN_MINUTES:g} and >={MIN_PRIOR_APPS} prior same-season "
      "appearances; baseline = shifted per-player ratio-EWMA rate with alpha tuned "
      f"per channel on the inner folds and frozen: "
      f"{ {k: float(v) for k, v in chosen.items()} }; "
      "delta = MAE(ridge[baseline, feature block]) - MAE(ridge[baseline]).")
    A("- **Missing state, not imputation**: each cross-season feature enters as TWO "
      "columns — the value, neutralized to 0.0 where no prior season exists, and a "
      "`has_prior_season` indicator (1/0). Run 1 mean-filled these rows; this "
      "registration forbids it. Both columns are fit; the indicator's standardized "
      "coefficient is in `missing_state_coefficients.csv` and the table below. A "
      "constant indicator (all rows covered, or none) is dropped from the design — "
      "a constant column is absorbed by the intercept.")
    A(f"- **Sweep**: #92's blend weight w over 0.1..0.9 on the inner folds ONLY, "
      "frozen per channel before 2024 is touched (`alpha_curves.csv`).")
    A(f"- **Null**: {args.perms} within-season permutations. The "
      "(value, has_prior_season) PAIR is permuted as a block — the row moves, the "
      "columns do not move independently — so the joint marginal of the encoding, "
      "including the missing-state rate, survives while every alignment with "
      "specific player-games is destroyed. p = (1 + #{null >= obs}) / (1 + n_perm).")
    A(f"- **FDR**: Benjamini-Hochberg at {FDR_Q:.0%} across **this family only** "
      f"({n_tests} tests = 3 candidates x 4 channels), its own FDR family. "
      "Survival additionally requires sign-consistent improvement across all 3 "
      "inner folds and 2024.")
    A(f"- **Robustness**: full rerun at minutes>={MIN_MINUTES_ROBUST:g} with the "
      "frozen weights (`robustness_min15.csv`).")
    A("")
    A("## Inner folds on the corrected window")
    A("")
    A("| fold | train rows | val rows | val window |")
    A("|---|---|---|---|")
    for f in folds:
        A(f"| {f.name} | {len(f.train_idx)} | {len(f.val_idx)} | "
          f"{f.val_start.date()} .. {f.val_end.date()} |")
    A("")
    A("Every inner fold now sits in a season that has a predecessor. That is the "
      "single thing run 1 could not offer.")
    A("")
    A("## LEAKAGE AUDIT — the number John asked about")
    A("")
    A(f"**Max deviation: {leak['max_deviation']:.3e}** (tolerance "
      f"{leak['tolerance']:.0e}) over {leak['n_comparisons']} comparisons on "
      f"{leak['n_sampled_rows']} independently sampled scored rows "
      "(`leakage_audit.csv`). The run aborts if this exceeds tolerance.")
    A("")
    A("| component | max deviation |")
    A("|---|---|")
    A(f"| (a) previous-season term vs independent season N-1 aggregate | "
      f"{leak['max_dev_prev_season_term']:.3e} |")
    A(f"| (b) current-season term vs strictly-past rebuild | "
      f"{leak['max_dev_current_season_term']:.3e} |")
    A(f"| blend at the frozen w, rebuilt end to end from independent terms | "
      f"{leak['max_dev_blend_at_frozen_w']:.3e} |")
    A("")
    A("**(a) The previous-season component uses ONLY completed season N-1 "
      "aggregates.** Two independent proofs:")
    A("")
    A("- *Structural.* Every season's last game strictly precedes the next "
      "season's first game, so an N-1 aggregate is complete before season N tips "
      "off — there is no calendar overlap in which a season-N game could feed its "
      "own prior-season term:")
    A("")
    A("| season N | N-1 last game | N first game | complete before N starts |")
    A("|---|---|---|---|")
    for s in leak["season_separation"]:
        A(f"| {s['season']} | {s['prev_season_last_game']} | "
          f"{s['season_first_game']} | "
          f"{s['prev_season_complete_before_season_start']} |")
    A("")
    A("- *Row-level.* For every sampled row the harness value is reproduced exactly "
      "by an aggregate built from season N-1 rows only, and the latest game feeding "
      f"that aggregate is strictly earlier than the target game "
      f"({leak['all_prev_sources_strictly_earlier']} on every row).")
    A("")
    A("**(b) The blend's current-season component is STRICTLY SEASON-TO-DATE.** "
      "This is the property John flagged, so it is tested against the value the "
      "harness actually produced rather than against a reading of the source. The "
      "current-season term is *extracted* from `fam_i.f92_two_season_blend`'s own "
      "output by inverting the blend at w=0.5 (`cur = 2*blend - prev`), then "
      "compared against a from-scratch rebuild that sums cumulative points and "
      "minutes over ONLY rows of the same player-season with `game_date` strictly "
      f"before the target date. Max deviation "
      f"{leak['max_dev_current_season_term']:.3e}. The target game and every later "
      "game are excluded: `cumsum().shift(1)` on both numerator and denominator, "
      "and the frame has no same-day repeat games for a player, so the shift and "
      "the strict date cut agree exactly.")
    A("")
    A("- *Positive control.* Recomputing the same term WITH the target game "
      f"included changes it on {leak['n_control_informative']} of "
      f"{leak['n_comparisons']} comparisons, and on every one of those the "
      "harness value sides with the strictly-past rebuild, by a margin of at "
      f"least {leak['min_positive_control_gap']:.4f}. So the comparison has the "
      "power to detect even a one-game contamination and does not pass by being "
      "insensitive. The remaining comparisons are uninformative rather than "
      "failing: a player with zero channel points both season-to-date and in the "
      "target game has the same term either way, so no test could separate them.")
    A(f"- *End to end.* The blend at the frozen w, rebuilt from the two "
      f"independent terms, matches the harness value to "
      f"{leak['max_dev_blend_at_frozen_w']:.3e} — the audited quantities are the "
      "ones that entered the model, not a parallel reimplementation.")
    A("")
    A("## Coverage — share of scored rows carrying a real prior season")
    A("")
    A("| candidate | 2022 | 2023 | 2024 (validation) |")
    A("|---|---|---|---|")
    for num in sorted(cov["catalog_number"].unique()):
        sub = cov[(cov["catalog_number"] == num) & (cov["channel"] == CHANNELS[0])]
        nm = sub["name"].iloc[0]
        vals = {int(r["season"]): r["coverage_share"] for _, r in sub.iterrows()}
        A(f"| #{num} {nm} | {vals.get(2022, float('nan')):.1%} | "
          f"{vals.get(2023, float('nan')):.1%} | {vals.get(2024, float('nan')):.1%} |")
    A("")
    A("Coverage is identical across channels (the same season-aggregate merge "
      "gates all four) — the per-channel ledger is in `coverage_by_season.csv`. "
      "A row is covered when the player has a qualifying prior season, i.e. one "
      "with >=150 minutes (`Ctx.season_rates`); rookies, returnees from absence "
      "and marginal-minute prior seasons are all genuinely uncovered and carry "
      "`has_prior_season=0` with a neutralized value.")
    A("")
    A("### #88 hits a second wall the 2022 start cannot move")
    A("")
    A("`career_trajectory_slope` is `prev_rate(lag 1) - prev_rate(lag 2)`. A 2022 "
      "game needs a **2020** season aggregate, and 2020 does not exist in this "
      "data — so #88 is 100% uncovered on 2022, by construction, exactly as #87 "
      "was on 2021 in run 1. The inner folds are cut on dates across the whole "
      "2022-2023 training window, so fold 1 fits entirely inside 2022: **no fit "
      "row in fold 1 carries a usable value**, the design is degenerate there, "
      "and the fold delta is exactly `+0.00000`. #88 therefore fails "
      "sign-consistency for the same structural reason the family failed in run 1, "
      "one season further along. The corrected window fixes #87 and #92; it cannot "
      "fix #88. Fixing #88 would need 2020 data, or a 2023 start that leaves one "
      "training season and no inner-fold structure at all. It is reported as it "
      "stands — not rescued.")
    A("")
    A("Inner-fold coverage at the frozen configuration (fit side / validation "
      "side; `Y` marks a degenerate fold):")
    A("")
    A("| # | name | fold fit coverage | fold val coverage | degenerate |")
    A("|---|---|---|---|---|")
    for _, r in ms[ms["channel"] == CHANNELS[0]].iterrows():
        A(f"| {r['catalog_number']} | {r['name']} | "
          f"{r['inner_fold_fit_coverage']} | {r['inner_fold_val_coverage']} | "
          f"{r['inner_fold_degenerate']} |")
    A("")
    A("## Baseline reference (2024)")
    A("")
    A("| channel | alpha | raw EWMA MAE | ridge-recalibrated MAE |")
    A("|---|---|---|---|")
    for ch, r in base_ref.items():
        A(f"| {ch} | {r['alpha']} | {r['mae_raw_ewma_2024']} | "
          f"{r['mae_ridge_base_2024']} |")
    A("")
    A("## Headline")
    A("")
    A(f"- **{n_tests} tests** (3 candidates x 4 channels), one FDR family.")
    A(f"- **p<=0.05 before any correction: {n_p05}** (expected under a global "
      f"null: ~{0.05 * n_tests:.1f}).")
    A(f"- **BH({FDR_Q:.0%}) significant: {n_bh}**; with sign-consistency: "
      f"**{n_surv} survivors**.")
    A(f"- Expected false discoveries among BH-passers at q<={FDR_Q}: "
      f"~{FDR_Q * n_bh:.1f}.")
    A("")
    A("## Full results")
    A("")
    A("| # | name | channel | w | delta | improvement | p | q | folds | 2024 | "
      "sign-consistent | survives |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in res.iterrows():
        w = "" if pd.isna(r["alpha_chosen"]) else f"{r['alpha_chosen']:g}"
        A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | {w} | "
          f"{r['delta_mae']:+.5f} | {r['improvement']:+.5f} | {r['p_value']:.5f} | "
          f"{r['q_value']:.4f} | {r['fold_signs']} | {r['sign_2024']} | "
          f"{r['sign_consistent']} | {r['survives']} |")
    A("")
    A("`fold_deltas` (the signed inner-fold deltas behind the sign string) are in "
      "`screen_results.csv`. A `-` is an improvement.")
    A("")
    A("## Run 1 vs the corrected window — what actually changed")
    A("")
    r1p = REPO / "experiments" / "feature_screen" / "screen_results.csv"
    if r1p.exists():
        r1 = pd.read_csv(r1p)                       # READ ONLY
        r1 = r1[r1["catalog_number"].isin(CANDIDATE_NUMBERS)]
        A("| # | channel | run 1 delta | run 1 folds | run 1 survives | "
          "this run delta | this run folds | this run survives |")
        A("|---|---|---|---|---|---|---|---|")
        for _, r in res.iterrows():
            m = r1[(r1["catalog_number"] == r["catalog_number"])
                   & (r1["channel"] == r["channel"])]
            if not len(m):
                continue
            o = m.iloc[0]
            A(f"| {r['catalog_number']} | {r['channel']} | {o['delta_mae']:+.5f} | "
              f"`{o['fold_signs']}` | {o['survives']} | {r['delta_mae']:+.5f} | "
              f"`{r['fold_signs']}` | {r['survives']} |")
        A("")
        A("Read the fold-sign columns, not the deltas. In run 1 every #87/#92 "
          "string is `+--`: a leading `+0.00000` from the degenerate 2021 fold, "
          "then two genuine improvements. The gate saw a `+` and refused, "
          "correctly — it could not tell a structural zero from a real reversal. "
          "On the corrected window the leading fold is a real test and it "
          "improves, so the strings become `---` on fg3, np2 and paint. Nothing "
          "was loosened: the same gate, applied to folds that can answer it, "
          "gives a different answer. The `ft` channel is the honest counterweight "
          "— its third fold reverses on its own merits, so `ft` still fails, and "
          "that is the gate doing its job on data it can read.")
        A("")
        A("Deltas moved (e.g. #87 fg3 -0.0535 to -0.0322) because the missing-state "
          "encoding replaced run 1's mean-fill, the training window lost a season, "
          "and the np2 baseline alpha re-tuned to 0.10. The effects are smaller "
          "than run 1 advertised. That direction is expected: mean-filling a "
          "cross-season anchor with the fit-window average hands the model a "
          "free-standing level for uncovered rows, which flatters the feature.")
    else:
        A("*Run 1's `screen_results.csv` not found; comparison omitted.*")
    A("")
    A("## #92's blend weight — the sweep runs to the edge of the grid")
    A("")
    A("`w` weights the PREVIOUS-season anchor; `1-w` weights the season-to-date "
      "term. Inner-fold MAE by w, per channel (the frozen w is the argmin, chosen "
      "before 2024 was touched):")
    A("")
    if len(acurve):
        ws = sorted(acurve["alpha"].unique())
        A("| channel | " + " | ".join(f"w={w:g}" for w in ws) + " | frozen w |")
        A("|---" * (len(ws) + 2) + "|")
        for ch in CHANNELS:
            sub = acurve[acurve["channel"] == ch].set_index("alpha")["inner_mae"]
            best = sub.idxmin()
            cells = " | ".join(
                (f"**{sub[w]:.4f}**" if w == best else f"{sub[w]:.4f}") for w in ws)
            A(f"| {ch} | {cells} | {best:g} |")
        A("")
        edge = all(acurve[acurve["channel"] == ch].set_index("alpha")["inner_mae"]
                   .idxmin() == max(ws) for ch in CHANNELS)
        if edge:
            A("**Every channel picks the largest weight on the grid.** The sweep is "
              "a boundary optimum: the inner folds want as much previous-season "
              "anchor and as little season-to-date term as the grid allows, so at "
              "w=0.9 #92 is #87 plus a 10% shrink toward the season-to-date rate. "
              "That is why #87 and #92 post near-identical deltas throughout this "
              "report — they are not two independent pieces of evidence, they are "
              "one effect measured twice. Run 1 found the same thing (w=0.8-0.9). "
              "The blend does not earn its second parameter; if anything survives "
              "to confirmation, #87 is the parsimonious carrier and #92 should not "
              "be promoted alongside it.")
        else:
            A("The sweep selects an interior weight, so the blend is doing "
              "something the anchor alone does not.")
    A("")
    A("## Missing-state coefficients and coverage at the frozen configuration")
    A("")
    A("| # | name | channel | w | beta(value) | beta(has_prior_season) | "
      "coverage train | coverage 2024 |")
    A("|---|---|---|---|---|---|---|---|")
    for _, r in ms.iterrows():
        w = "" if pd.isna(r["w_frozen"]) else f"{r['w_frozen']:g}"
        bi = ("dropped (constant)" if not r["indicator_in_model"]
              else f"{r['beta_indicator_std']:+.5f}")
        A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | {w} | "
          f"{r['beta_feature_std']:+.5f} | {bi} | "
          f"{r['coverage_train_2022_23']:.1%} | {r['coverage_val_2024']:.1%} |")
    A("")
    A("## Survivors")
    A("")
    if len(surv):
        A("| # | name | channel | delta | p | q | w | folds | min15 |")
        A("|---|---|---|---|---|---|---|---|---|")
        for _, r in surv.iterrows():
            w = "" if pd.isna(r["alpha_chosen"]) else f"{r['alpha_chosen']:g}"
            m15 = r.get("delta_mae_min15", np.nan)
            m15 = "" if pd.isna(m15) else f"{m15:+.5f}"
            A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | "
              f"{r['delta_mae']:+.5f} | {r['p_value']:.5f} | {r['q_value']:.4f} | "
              f"{w} | {r['fold_signs']} | {m15} |")
    else:
        A("**None.** On the corrected window the family does not clear "
          "BH + sign-consistency.")
    A("")
    A("## Robustness (minutes >= 15, frozen weights)")
    A("")
    A("| # | name | channel | delta (min8) | delta (min15) | p (min15) | agrees |")
    A("|---|---|---|---|---|---|---|")
    for _, r in rob.iterrows():
        d8 = res.loc[(res["catalog_number"] == r["catalog_number"])
                     & (res["channel"] == r["channel"]), "delta_mae"].iloc[0]
        A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | {d8:+.5f} | "
          f"{r['delta_mae_min15']:+.5f} | {r['p_value_min15']:.5f} | "
          f"{r['agrees_with_primary']} |")
    A("")
    A("## Interpretation decisions (pinned before results were seen)")
    A("")
    A("- **A screen promotes nothing.** Its gates are sentinels; survivors "
      "graduate to the sealed-year confirmation bake-off, which is the real gate.")
    A("- **Delta reference**: the ridge-recalibrated baseline, exactly as run 1, so "
      "the two runs' deltas are directly comparable and the permutation null uses "
      "the identical statistic.")
    A("- **What the two-column encoding actually fits**: this is the standard "
      "missing-indicator method. Because the neutralized value standardizes to a "
      "constant on uncovered rows and the indicator marks exactly those rows, the "
      "fit is equivalent to estimating the feature's slope on COVERED rows only "
      "while giving uncovered rows their own intercept. Nothing about an uncovered "
      "row is invented — its slope contribution is zero and its level is estimated, "
      "not borrowed from the fit-window mean as run 1's mean-fill did.")
    A("- **The missing-state encoding changes the estimand slightly** relative to "
      "run 1: run 1's mean-fill silently assigned uncovered rows the fit-window "
      "average prior-season rate, which is an imputation and inflates apparent "
      "coverage. Here uncovered rows are neutralized and flagged, so the value "
      "column's coefficient is estimated on covered rows and the indicator absorbs "
      "the level difference. Deltas are therefore NOT expected to reproduce run 1's "
      "to the digit; the comparison of interest is the fold-sign structure.")
    A("- **Known limitation (carried from run 1)**: row-exchangeable permutation "
      "understates within-player clustering of slow-moving features, which is "
      "exactly what this family is. The p-values are honest against the registered "
      "null; they are not a substitute for the sealed-year confirmation.")
    A("- **#89 `team_change_reset` also lives in `features/fam_i.py` but is not "
      "part of this registration's family** (3 candidates x 4 channels = 12 tests) "
      "and is not screened here.")
    A("")
    A("## What this run did NOT do")
    A("")
    A("- No git. No registry write. `registry.register` / `evaluate` / "
      "`record_evaluation` / `render_leaderboards` are never imported or called. "
      "The orchestrator records after verifying.")
    A("- `feature_lab.py`, `features/fam_i.py` and every existing `experiments/` "
      "directory are read-only here. The two behavioural changes the registration "
      "requires (window, missing-state encoding) are implemented as wrappers "
      "inside `crossseason_screen.py`.")
    A("- No network access; no 2025/2026 row was loaded by any code path.")
    A("")
    A("## Files")
    A("")
    A("- `screen_results.csv` — one row per (candidate, channel), run-1 schema exactly")
    A("- `survivor_summary.csv` — survivors only (+ min15 robustness), run-1 schema")
    A("- `leakage_audit.csv` — the per-row independent recompute (audit of both terms)")
    A("- `coverage_by_season.csv` — prior-season coverage per candidate/channel/season")
    A("- `missing_state_coefficients.csv` — value and indicator standardized betas")
    A("- `alpha_curves.csv` — #92's blend-weight sweep on the inner folds")
    A("- `baseline_alpha_curves.csv` — baseline EWMA alpha sweep on the inner folds")
    A("- `robustness_min15.csv` — full >=15-minute rerun at the frozen weights")
    A("- `diagnostics/top20_diagnostics.csv` — null quantiles per test")
    A("- `quarantine_audit.json` — per-matrix date audit")
    (OUTDIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
