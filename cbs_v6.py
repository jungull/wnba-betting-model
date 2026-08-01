#!/usr/bin/env python3
"""cbs_v6.py — the COMPLETE end-to-end runner for `contract_baseline_suite_v6`.

v5 corrected the primitives but stopped at `resolve_feature_asof`: there was no
v5 fold runner, no emission path, no fitted-state constructor and no validation
composition, so **none of v5's corrections ever reached a generated contract
row**. The only executable runners were still v4's, with v4's defects and v4's
arm identity. v6 supplies the missing pipeline.

**Synthetic only, and structurally so.** No path argument exists anywhere in this
module; every frame arrives from the caller. Running it produces no artifact, no
accuracy figure and no coverage score.

WHAT v6 ADDS OVER v5
--------------------
* `run_player_fold` / `run_team_fold` built from the **corrected v5 primitives**;
* all five target emissions for **every required obligation**;
* a versioned **history-audit sidecar** persisting `n_prior_candidate_games`,
  `n_prior_appearances` and team `prior_games` per row — v5 promised the separate
  accounting but never persisted it anywhere;
* target-specific cold / fallback logic **bound into the emitted rows**, not just
  available as a helper;
* an explicit **fitted-state constructor** per fold and target, so `model_hash`
  covers the actual fitted objects rather than a hand-built dictionary;
* strict real-boundary identity binding the registered config hash and an exact
  snapshot hash;
* one **composite validation receipt** (historical AND strict), produced before
  any scoring function is reachable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from cbs_builders import QUANTILE_Z
from cbs_generator import (ALPHA_GRID, DECLARED, SplitContext, Standardizer,
                           TEAM_POINTS_FLOOR, active_shifted_ewma,
                           active_shifted_ratio_ewma, emit_quantiles, logistic_fit,
                           logistic_predict, order_obligations, player_split,
                           prefix_mean, select_alpha_bound, team_split)
from cbs_v5 import (MissingRequiredInput, P_ACTIVE_FEATURES, REQUIRED_CHANNELS,
                    REQUIRED_SIDES, SIDE_COL, apply_side_maps, cold_start_flag,
                    dispersion, fit_side_maps, fitted_state_hash,
                    player_history_accounting, require_identity, residuals,
                    select_lambda_chronological, stage_a_features_strict,
                    team_prior_games, team_structural)
from contract_validator_v2_strict import validate_arm_output

ARM_ID = "contract_baseline_suite_v6"
HISTORY_SIDECAR_SCHEMA = "cbs_history_audit/1"

PLAYER_TARGETS = ("p_active", "e_minutes_given_active", "attempts_usage",
                  "player_scoring_distribution")
CONDITIONAL_TARGETS = ("e_minutes_given_active", "attempts_usage",
                       "player_scoring_distribution")


# --------------------------------------------------------------------------
# fitted state — one explicit object per fold and target
# --------------------------------------------------------------------------

@dataclass
class FittedState:
    """Everything that can change a prediction, in one hashable object.

    v5 hashed a generic dict that only a hand-built test ever populated. Here the
    runner constructs it from the actual fitted objects, so the emitted
    `model_hash` moves iff something that affects predictions moved.
    """
    target: str
    fold_id: str
    feature_order: list = field(default_factory=list)
    scaler_mean: list = field(default_factory=list)
    scaler_std: list = field(default_factory=list)
    dropped_features: list = field(default_factory=list)
    lam: float | None = None
    beta: list = field(default_factory=list)
    alphas: dict = field(default_factory=dict)
    calibration_maps: dict = field(default_factory=dict)
    base_rate: float | None = None
    fallback_mean: float | None = None
    dispersion_sd: float | None = None
    dispersion_method: str | None = None
    dispersion_offsets: list = field(default_factory=list)
    support: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    def hash(self) -> str:
        return fitted_state_hash(self.to_dict())


def _emit(uni: pd.DataFrame, target: str, point: pd.Series, sd: pd.Series | None,
          offsets: np.ndarray | None, *, fold_id: str, config_hash: str,
          snapshot_hash: str, model_hash: str, is_fallback: pd.Series,
          is_cold: pd.Series, n_prior: pd.Series, exclusion: pd.Series,
          low, high, want_q: bool) -> pd.DataFrame:
    out = pd.DataFrame({
        "row_uid": uni["row_uid"].to_numpy(),
        "target_key": target, "arm_id": ARM_ID, "fold_id": fold_id,
        "forecast_cutoff": uni["forecast_cutoff"].to_numpy(),
        "pred_point": np.asarray(point, dtype=float),
        "pred_sd": (np.asarray(sd, dtype=float) if sd is not None
                    else np.full(len(uni), np.nan)),
        "is_fallback": np.asarray(is_fallback, dtype=bool),
        "is_cold_start": np.asarray(is_cold, dtype=bool),
        "n_prior_games": np.asarray(n_prior, dtype=int),
        "feature_asof": uni["feature_asof"].to_numpy(),
        "model_hash": model_hash, "config_hash": config_hash,
        "data_snapshot_hash": snapshot_hash,
        "exclusion_reason": exclusion.to_numpy(),
    })
    for c in ("pred_q05", "pred_q25", "pred_q50", "pred_q75", "pred_q95"):
        out[c] = np.nan

    if low is not None:
        out["pred_point"] = out["pred_point"].clip(lower=low)
    if high is not None:
        out["pred_point"] = out["pred_point"].clip(upper=high)

    if want_q and offsets is not None and np.all(np.isfinite(offsets)):
        q = emit_quantiles(out["pred_point"].to_numpy(dtype=float), offsets,
                           low=low, high=high)
        for i, c in enumerate(("pred_q05", "pred_q25", "pred_q50",
                               "pred_q75", "pred_q95")):
            out[c] = q[:, i]

    excl = out.exclusion_reason.notna()
    if excl.any():                       # excluded rows carry NO values, full lineage
        out.loc[excl, ["pred_point", "pred_sd", "pred_q05", "pred_q25",
                       "pred_q50", "pred_q75", "pred_q95"]] = np.nan
    return out


def history_sidecar(rows: pd.DataFrame, hist: pd.DataFrame | None = None, *,
                    team_prior: pd.Series | None = None,
                    fold_id: str) -> pd.DataFrame:
    """The versioned history audit — persisted, not merely promised.

    v5 computed `n_prior_candidate_games` and `n_prior_appearances` and then
    dropped them on the floor. They are the evidence that 0-of-k was treated as
    evidence rather than absence, so they must survive into an artifact.
    """
    out = pd.DataFrame({
        "schema": HISTORY_SIDECAR_SCHEMA,
        "fold_id": fold_id,
        "row_uid": rows["row_uid"].to_numpy(),
    })
    if hist is not None:
        out["n_prior_candidate_games"] = hist["n_prior_candidate_games"].to_numpy()
        out["n_prior_appearances"] = hist["n_prior_appearances"].to_numpy()
        out["has_prior_obligation"] = hist["has_prior_obligation"].to_numpy()
        out["has_prior_appearance"] = hist["has_prior_appearance"].to_numpy()
        out["team_prior_games"] = np.nan
    else:
        out["n_prior_candidate_games"] = np.nan
        out["n_prior_appearances"] = np.nan
        out["has_prior_obligation"] = pd.NA
        out["has_prior_appearance"] = pd.NA
        out["team_prior_games"] = (np.asarray(team_prior, dtype=float)
                                   if team_prior is not None else np.nan)
    return out


# --------------------------------------------------------------------------
# player fold
# --------------------------------------------------------------------------

def run_player_fold(train: pd.DataFrame, test: pd.DataFrame, fold_id: str, *,
                    config_hash: str, snapshot_hash: str, universe=None,
                    synthetic: bool = True,
                    allow_declared_defaults: bool = True) -> dict:
    """All four player targets, every obligation row, with receipts."""
    require_identity(config_hash, snapshot_hash, synthetic=synthetic)

    train = order_obligations(train) if len(train) else train
    test = order_obligations(test)

    diag: dict = {"fold_id": fold_id, "selected": {}, "dispersion": {},
                  "fallback_mean": {}, "fitted_state": {}}
    ctx = (player_split(train) if len(train) else
           SplitContext(np.array([], dtype=np.int64), np.array([], dtype=np.int64),
                        degenerate=True, reason="empty training window", label="player"))
    diag["degenerate"], diag["reason"] = ctx.degenerate, ctx.reason

    hist_te = player_history_accounting(test)
    sidecar = history_sidecar(test, hist_te, fold_id=fold_id)
    preds: dict[str, pd.DataFrame] = {}
    no_excl = pd.Series(pd.NA, index=test.index)

    if ctx.degenerate or len(train) == 0:
        for tgt in PLAYER_TARGETS:
            d = DECLARED[tgt]
            sd = d.get("sd")
            st = FittedState(target=tgt, fold_id=fold_id,
                             fallback_mean=d["point"], dispersion_sd=sd,
                             dispersion_method="declared",
                             support={"low": d.get("low"), "high": d.get("high")})
            preds[tgt] = _emit(
                test, tgt, pd.Series(d["point"], index=test.index),
                pd.Series(sd, index=test.index) if sd else None,
                (np.asarray(QUANTILE_Z) * sd) if sd else None,
                fold_id=fold_id, config_hash=config_hash, snapshot_hash=snapshot_hash,
                model_hash=st.hash(),
                is_fallback=pd.Series(True, index=test.index),
                is_cold=pd.Series(True, index=test.index),
                n_prior=hist_te["n_prior_appearances"], exclusion=no_excl,
                low=d.get("low"), high=d.get("high"), want_q=(tgt != "p_active"))
            diag["fitted_state"][tgt] = st.to_dict()
        diag["fallback"] = "declared_constants"
        return _finish(preds, sidecar, diag, test, universe, fold_id,
                       config_hash, snapshot_hash)

    hist_tr = player_history_accounting(train)
    tuning_mask = pd.Series(False, index=train.index)
    tuning_mask.loc[ctx.tuning_idx] = True
    active_any = train["appeared"].astype(bool)
    all_tune, active_tune = tuning_mask, tuning_mask & active_any

    # ---- p_active: ALL candidate obligations -----------------------------
    base_rate = prefix_mean(train["appeared"].astype(float), ctx, all_tune)
    Xtr = stage_a_features_strict(train, hist_tr, base_rate,
                                  allow_declared_defaults=allow_declared_defaults)
    Xte = stage_a_features_strict(test, hist_te, base_rate,
                                  allow_declared_defaults=allow_declared_defaults)
    lam, lam_default, inner = select_lambda_chronological(
        Xtr, train["appeared"].astype(float), ctx, train)
    tr_idx = ctx.require_tuning(np.asarray(train.index[all_tune]))
    std = Standardizer(Xtr.loc[tr_idx])
    beta = logistic_fit(std.transform(Xtr.loc[tr_idx]),
                        train["appeared"].reindex(tr_idx).to_numpy(float), lam)
    p_hat = pd.Series(logistic_predict(std.transform(Xte), beta), index=test.index)

    st_pa = FittedState(target="p_active", fold_id=fold_id,
                        feature_order=list(P_ACTIVE_FEATURES),
                        scaler_mean=std.mean.tolist(), scaler_std=std.std.tolist(),
                        dropped_features=list(std.dropped), lam=lam,
                        beta=np.round(beta, 12).tolist(), base_rate=base_rate,
                        support={"low": 0.0, "high": 1.0})
    diag["selected"].update({"lambda": lam, "lambda_default": lam_default,
                             "lambda_inner_fit_dates": len(inner.fit_dates),
                             "lambda_inner_val_dates": len(inner.val_dates)})
    diag["base_rate"] = base_rate
    diag["fitted_state"]["p_active"] = st_pa.to_dict()
    preds["p_active"] = _emit(
        test, "p_active", p_hat, None, None, fold_id=fold_id,
        config_hash=config_hash, snapshot_hash=snapshot_hash, model_hash=st_pa.hash(),
        is_fallback=pd.Series(False, index=test.index),
        is_cold=cold_start_flag(hist_te, "p_active"),
        n_prior=hist_te["n_prior_appearances"], exclusion=no_excl,
        low=0.0, high=1.0, want_q=False)

    # ---- conditional targets, ordered tuning with the minutes leg fixed ---
    def minutes_pred(a, frame=None):
        f = train if frame is None else frame
        return active_shifted_ewma(f, f["minutes"], a)

    m_alpha, _, m_b = select_alpha_bound(minutes_pred, train["minutes"], ctx, active_tune)

    def attempts_pred(a, frame=None):
        f = train if frame is None else frame
        mins = active_shifted_ewma(f, f["minutes"], m_alpha)
        return active_shifted_ratio_ewma(f, f["fga"], f["minutes"], a) * (mins / 36.0)

    def points_pred(a, frame=None):
        f = train if frame is None else frame
        mins = active_shifted_ewma(f, f["minutes"], m_alpha)
        rate = active_shifted_ewma(
            f, f["points"] / f["minutes"].replace(0, np.nan) * 36.0, a)
        return rate * (mins / 36.0)

    a_alpha, _, a_b = select_alpha_bound(attempts_pred, train["fga"], ctx, active_tune)
    p_alpha, _, p_b = select_alpha_bound(points_pred, train["points"], ctx, active_tune)
    diag["selected"].update({"minutes_alpha": m_alpha, "attempts_alpha": a_alpha,
                             "points_alpha": p_alpha,
                             "minutes_alpha_held_fixed_at": m_alpha,
                             "boundaries": {"minutes": m_b, "attempts": a_b,
                                            "points": p_b}})

    for tgt, fn, ycol in (
            ("e_minutes_given_active",
             lambda f: active_shifted_ewma(f, f["minutes"], m_alpha), "minutes"),
            ("attempts_usage", lambda f: attempts_pred(a_alpha, f), "fga"),
            ("player_scoring_distribution", lambda f: points_pred(p_alpha, f), "points")):
        d = DECLARED[tgt]
        fb_mean = prefix_mean(train[ycol].astype(float), ctx, active_tune)
        if not np.isfinite(fb_mean):
            fb_mean = d["point"]
        diag["fallback_mean"][tgt] = fb_mean

        cal = np.intersect1d(ctx.calibration_idx, np.asarray(train.index[active_any]))
        sd_v, off, method = dispersion(
            residuals(train[ycol].reindex(cal), fn(train).reindex(cal)),
            min_resid=200)
        if method == "insufficient":
            sd_v = d["sd"]
            off = np.asarray(QUANTILE_Z) * sd_v
        diag["dispersion"][tgt] = {"method": method, "sd": float(sd_v),
                                   "n_resid": int(len(cal))}

        raw = fn(test)
        fb = ~np.isfinite(raw)
        cold = cold_start_flag(hist_te, tgt)
        st = FittedState(target=tgt, fold_id=fold_id,
                         alphas={"minutes": m_alpha, "attempts": a_alpha,
                                 "points": p_alpha},
                         fallback_mean=fb_mean, dispersion_sd=float(sd_v),
                         dispersion_method=method,
                         dispersion_offsets=np.round(off, 12).tolist(),
                         support={"low": d.get("low"), "high": d.get("high")})
        diag["fitted_state"][tgt] = st.to_dict()
        preds[tgt] = _emit(
            test, tgt, raw.where(~fb, fb_mean), pd.Series(sd_v, index=test.index), off,
            fold_id=fold_id, config_hash=config_hash, snapshot_hash=snapshot_hash,
            model_hash=st.hash(),
            is_fallback=(fb | cold), is_cold=cold,
            n_prior=hist_te["n_prior_appearances"], exclusion=no_excl,
            low=d.get("low"), high=d.get("high"), want_q=True)

    return _finish(preds, sidecar, diag, test, universe, fold_id,
                   config_hash, snapshot_hash)


# --------------------------------------------------------------------------
# team fold
# --------------------------------------------------------------------------

def require_team_inputs_strict(frame: pd.DataFrame) -> None:
    """Structural preconditions, all fail-closed.

    v5 checked only that the channel columns existed. Null or non-finite channel
    values, a null side, duplicate team-game rows, or a game that is not exactly
    one home and one away row are all equally capable of producing a confident
    wrong number.
    """
    for k in ("team_id", "game_date", "game_id", "season", "team_points"):
        if k not in frame.columns:
            raise MissingRequiredInput(f"team frame missing {k!r}")
    missing = [c for c in REQUIRED_CHANNELS if f"ch_{c}" not in frame.columns]
    if missing:
        raise MissingRequiredInput(f"required team channels absent: {missing}")
    for c in REQUIRED_CHANNELS:
        col = pd.to_numeric(frame[f"ch_{c}"], errors="coerce")
        if col.isna().any() or not np.isfinite(col).all():
            raise MissingRequiredInput(f"channel ch_{c} has null/non-finite values")
    if SIDE_COL not in frame.columns:
        raise MissingRequiredInput(f"required side indicator {SIDE_COL!r} absent")
    if frame[SIDE_COL].isna().any():
        raise MissingRequiredInput(f"{SIDE_COL} has null values")
    bad = set(pd.unique(frame[SIDE_COL])) - set(REQUIRED_SIDES)
    if bad:
        raise MissingRequiredInput(f"unexpected {SIDE_COL} values: {sorted(bad)}")
    if frame.duplicated(subset=["team_id", "game_id"]).any():
        raise MissingRequiredInput("duplicate (team_id, game_id) team rows")
    per_game = frame.groupby("game_id")[SIDE_COL].agg(list)
    for gid, sides in per_game.items():
        if sorted(sides) != sorted(REQUIRED_SIDES):
            raise MissingRequiredInput(
                f"game {gid!r} is not exactly one home and one away row: {sides}")


def run_team_fold(train: pd.DataFrame, test: pd.DataFrame, fold_id: str, *,
                  config_hash: str, snapshot_hash: str, universe=None,
                  synthetic: bool = True) -> dict:
    require_identity(config_hash, snapshot_hash, synthetic=synthetic)
    require_team_inputs_strict(train)
    require_team_inputs_strict(test)

    d = DECLARED["team_game_distribution"]
    tgt = "team_game_distribution"
    diag: dict = {"fold_id": fold_id}
    ts = team_split(train)
    diag["degenerate"], diag["reason"] = ts.degenerate, ts.reason
    diag["segment_dates"] = {"T1": len(ts.t1_dates), "T2": len(ts.t2_dates),
                             "T3": len(ts.t3_dates)}
    prior_te = team_prior_games(test)
    sidecar = history_sidecar(test, None, team_prior=prior_te, fold_id=fold_id)
    diag["zero_candidate_team_games"] = int(
        test.get("n_candidates", pd.Series(1, index=test.index)).eq(0).sum())
    no_excl = pd.Series(pd.NA, index=test.index)

    if ts.degenerate:
        st = FittedState(target=tgt, fold_id=fold_id, fallback_mean=d["point"],
                         dispersion_sd=d["sd"], dispersion_method="declared",
                         support={"low": d["low"]})
        pred = _emit(test, tgt, pd.Series(d["point"], index=test.index),
                     pd.Series(d["sd"], index=test.index),
                     np.asarray(QUANTILE_Z) * d["sd"], fold_id=fold_id,
                     config_hash=config_hash, snapshot_hash=snapshot_hash,
                     model_hash=st.hash(),
                     is_fallback=pd.Series(True, index=test.index),
                     is_cold=pd.Series(True, index=test.index),
                     n_prior=prior_te, exclusion=no_excl,
                     low=d["low"], high=None, want_q=True)
        diag["fitted_state"] = {tgt: st.to_dict()}
        diag["fallback"] = "declared_constants"
        return _finish({tgt: pred}, sidecar, diag, test, universe, fold_id,
                       config_hash, snapshot_hash)

    ctx1 = ts.context_for_alpha()
    t1_mask = pd.Series(False, index=train.index)
    t1_mask.loc[ts.t1] = True
    alphas: dict[str, float] = {}
    for ch in REQUIRED_CHANNELS:
        def chan_pred(a, frame=None, ch=ch):
            f = train if frame is None else frame
            from cbs_v5 import team_channel_trend
            return team_channel_trend(f, ch, a)
        alphas[ch], _, _ = select_alpha_bound(chan_pred, train[f"ch_{ch}"],
                                              ctx1, t1_mask, grid=ALPHA_GRID)
    diag["channel_alphas"] = alphas

    ctx2 = ts.context_for_calibration_map()
    struct_tr = team_structural(train, alphas)
    maps = fit_side_maps(train, struct_tr, ctx2.tuning_idx)
    diag["calibration_maps"] = maps

    fitted = apply_side_maps(train, struct_tr, maps)
    sd_v, off, method = dispersion(
        residuals(train["team_points"].reindex(ts.t3), fitted.reindex(ts.t3)),
        min_resid=30)
    if method == "insufficient":
        sd_v = d["sd"]
        off = np.asarray(QUANTILE_Z) * sd_v
    diag["dispersion"] = {"method": method, "sd": float(sd_v), "n_resid": int(len(ts.t3))}

    raw = apply_side_maps(test, team_structural(test, alphas), maps)
    fb = ~np.isfinite(raw)
    st = FittedState(target=tgt, fold_id=fold_id, alphas=dict(alphas),
                     calibration_maps={k: list(v) for k, v in maps.items()},
                     fallback_mean=d["point"], dispersion_sd=float(sd_v),
                     dispersion_method=method,
                     dispersion_offsets=np.round(off, 12).tolist(),
                     support={"low": d["low"]})
    diag["fitted_state"] = {tgt: st.to_dict()}
    pred = _emit(test, tgt, raw.where(~fb, d["point"]),
                 pd.Series(sd_v, index=test.index), off, fold_id=fold_id,
                 config_hash=config_hash, snapshot_hash=snapshot_hash,
                 model_hash=st.hash(), is_fallback=fb,
                 is_cold=(prior_te == 0), n_prior=prior_te, exclusion=no_excl,
                 low=d["low"], high=None, want_q=True)
    return _finish({tgt: pred}, sidecar, diag, test, universe, fold_id,
                   config_hash, snapshot_hash)


# --------------------------------------------------------------------------
# receipts — produced BEFORE any scoring function is reachable
# --------------------------------------------------------------------------

def _finish(preds, sidecar, diag, test, universe, fold_id,
            config_hash, snapshot_hash) -> dict:
    receipts, coverage = {}, {}
    if universe is not None:
        for tgt, p in preds.items():
            receipts[tgt] = validate_arm_output(
                p, universe, tgt, expected_arm_id=ARM_ID, expected_fold_id=fold_id,
                expected_config_hash=config_hash, expected_snapshot_hash=snapshot_hash)
            coverage[tgt] = {
                "n_rows_emitted": int(len(p)),
                "n_excluded": int(p.exclusion_reason.notna().sum()),
                "n_fallback": int(p.is_fallback.sum()),
                "n_cold_start": int(p.is_cold_start.sum()),
            }
    all_ok = bool(receipts) and all(r["ok"] for r in receipts.values())
    return {
        "arm_id": ARM_ID, "fold_id": fold_id,
        "predictions": preds, "history_sidecar": sidecar, "diagnostics": diag,
        "validation_receipts": receipts, "coverage": coverage,
        "validated": all_ok,
        "scoring_permitted": all_ok,
        "scoring_note": "scoring is unreachable until validated is True; this runner "
                        "computes no accuracy or coverage score in any case",
    }
