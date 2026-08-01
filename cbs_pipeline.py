#!/usr/bin/env python3
"""cbs_pipeline.py — the registered end-to-end fold runners for v4.

`cbs_generator.py` holds the guarded primitives; this module is the pipeline
that composes them into contract-schema output for a whole outer fold.

**No file I/O.** Frames arrive as arguments. Running this produces no artifact,
no accuracy figure and no coverage score, and it cannot reach the real contract
because it is never given a path.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cbs_builders import (MIN_RESID_PLAYER, MIN_RESID_TEAM, QUANTILE_Z,
                          prior_candidate_history, shifted_ewma, shifted_ratio_ewma)
from cbs_generator import (ARM_ID, DECLARED, SplitContext, Standardizer, TeamSplit,
                           _hash, active_shifted_ewma, active_shifted_ratio_ewma,
                           dispersion, emit_rows, logistic_fit, logistic_predict,
                           order_obligations, player_split, prefix_mean,
                           select_alpha_bound, select_lambda, stage_a_features,
                           team_split)


def _declared_rows(test, tgt, fold_id, config_hash, snapshot_hash, n_prior):
    d = DECLARED[tgt]
    sd = d.get("sd")
    off = (np.asarray(QUANTILE_Z) * sd) if sd else None
    return emit_rows(
        test, tgt, pd.Series(d["point"], index=test.index),
        pd.Series(sd if sd else np.nan, index=test.index), off,
        arm_id=ARM_ID, fold_id=fold_id, config_hash=config_hash,
        model_hash=_hash(["declared", tgt]), snapshot_hash=snapshot_hash,
        is_fallback=pd.Series(True, index=test.index),
        is_cold_start=pd.Series(True, index=test.index),
        n_prior=n_prior, exclusion=pd.Series(pd.NA, index=test.index),
        low=d.get("low"), high=d.get("high"), want_quantiles=tgt != "p_active")


def run_player_fold(train: pd.DataFrame, test: pd.DataFrame, fold_id: str, *,
                    config_hash: str, snapshot_hash: str = "synthetic") -> dict:
    """Emit all four player targets for one outer fold.

    When `train` is empty (`season:2021`) every row takes the declared constants
    and is flagged, so the obligation count stays honest rather than shrinking.
    """
    train = order_obligations(train) if len(train) else train
    test = order_obligations(test)

    diag: dict = {"fold_id": fold_id, "selected": {}}
    ctx = player_split(train) if len(train) else SplitContext(
        np.array([], dtype=np.int64), np.array([], dtype=np.int64),
        degenerate=True, reason="empty training window", label="player")
    diag["degenerate"], diag["reason"] = ctx.degenerate, ctx.reason

    hist_te = prior_candidate_history(test)
    n_prior = hist_te["n_prior_appearances"].astype(int)
    cold = ~hist_te["has_prior_obligation"]
    preds: dict[str, pd.DataFrame] = {}

    if ctx.degenerate or len(train) == 0:
        for tgt in ("p_active", "e_minutes_given_active", "attempts_usage",
                    "player_scoring_distribution"):
            preds[tgt] = _declared_rows(test, tgt, fold_id, config_hash,
                                        snapshot_hash, n_prior)
        diag["fallback"] = "declared_constants"
        return {"predictions": preds, "diagnostics": diag}

    hist_tr = prior_candidate_history(train)

    # Every tuning mask is built as a SUBSET OF ctx.tuning_idx. Passing a mask
    # that spans the whole training frame is what the SplitContext guard exists
    # to reject -- and it did, on the first run of this pipeline.
    tuning_mask = pd.Series(False, index=train.index)
    tuning_mask.loc[ctx.tuning_idx] = True
    active_any = train["appeared"].astype(bool)      # ALL rows; calibration use only
    all_tr = tuning_mask                             # p_active: every obligation...
    active_tr = tuning_mask & active_any             # ...conditional: active only

    # ---- p_active -- ALL candidate obligations ---------------------------
    base_rate = prefix_mean(train["appeared"].astype(float), ctx, all_tr)
    Xtr = stage_a_features(train, hist_tr, base_rate)
    Xte = stage_a_features(test, hist_te, base_rate)
    lam, lam_default = select_lambda(Xtr, train["appeared"].astype(float), ctx, all_tr)
    tr_idx = ctx.require_tuning(np.asarray(train.index[all_tr]))
    std = Standardizer(Xtr.loc[tr_idx])
    beta = logistic_fit(std.transform(Xtr.loc[tr_idx]),
                        train["appeared"].reindex(tr_idx).to_numpy(float), lam)
    p_hat = pd.Series(logistic_predict(std.transform(Xte), beta), index=test.index)
    diag["selected"].update({"lambda": lam, "lambda_default": lam_default})
    diag["base_rate"] = base_rate
    diag["dropped_features"] = list(std.dropped)
    preds["p_active"] = emit_rows(
        test, "p_active", p_hat, pd.Series(np.nan, index=test.index), None,
        arm_id=ARM_ID, fold_id=fold_id, config_hash=config_hash,
        model_hash=_hash(np.round(beta, 9).tolist()), snapshot_hash=snapshot_hash,
        is_fallback=pd.Series(False, index=test.index), is_cold_start=cold,
        n_prior=n_prior, exclusion=pd.Series(pd.NA, index=test.index),
        low=0.0, high=1.0, want_quantiles=False)

    # ---- ordered tuning on ACTIVE, outcome-scoreable rows only ------------
    # Conditional-target history is the ACTIVE subsequence only -- see
    # cbs_generator.active_shifted_ewma. Using all obligations would let a DNP
    # row's outcome move the selected alphas.
    def minutes_pred(a, frame=None):
        f = train if frame is None else frame
        return active_shifted_ewma(f, f["minutes"], a)

    m_alpha, _, m_bound = select_alpha_bound(minutes_pred, train["minutes"],
                                             ctx, active_tr)

    def attempts_pred(a, frame=None):
        f = train if frame is None else frame
        mins = active_shifted_ewma(f, f["minutes"], m_alpha)   # minutes leg HELD FIXED
        return active_shifted_ratio_ewma(f, f["fga"], f["minutes"], a) * (mins / 36.0)

    def points_pred(a, frame=None):
        f = train if frame is None else frame
        mins = active_shifted_ewma(f, f["minutes"], m_alpha)   # same fixed leg
        rate = active_shifted_ewma(
            f, f["points"] / f["minutes"].replace(0, np.nan) * 36.0, a)
        return rate * (mins / 36.0)

    a_alpha, _, a_bound = select_alpha_bound(attempts_pred, train["fga"], ctx, active_tr)
    p_alpha, _, p_bound = select_alpha_bound(points_pred, train["points"], ctx, active_tr)
    diag["selected"].update({
        "minutes_alpha": m_alpha, "minutes_alpha_boundary": m_bound,
        "attempts_alpha": a_alpha, "attempts_alpha_boundary": a_bound,
        "points_alpha": p_alpha, "points_alpha_boundary": p_bound,
        "minutes_alpha_held_fixed_at": m_alpha})

    for tgt, fn, ycol in (
            ("e_minutes_given_active",
             lambda f: active_shifted_ewma(f, f["minutes"], m_alpha), "minutes"),
            ("attempts_usage", lambda f: attempts_pred(a_alpha, f), "fga"),
            ("player_scoring_distribution", lambda f: points_pred(p_alpha, f), "points")):
        d = DECLARED[tgt]
        fb_mean = prefix_mean(train[ycol].astype(float), ctx, active_tr)
        if not np.isfinite(fb_mean):
            fb_mean = d["point"]
        diag.setdefault("fallback_mean", {})[tgt] = fb_mean

        # Residuals come from the CALIBRATION segment (active rows there), which
        # is disjoint from every mask used above for selection.
        cal = np.intersect1d(ctx.calibration_idx, np.asarray(train.index[active_any]))
        resid = (fn(train).reindex(cal) - train[ycol].reindex(cal)).to_numpy(dtype=float)
        sd_v, off, method = dispersion(resid, min_resid=MIN_RESID_PLAYER)
        if method == "insufficient":
            sd_v = d["sd"]
            off = np.asarray(QUANTILE_Z) * sd_v
        diag.setdefault("dispersion", {})[tgt] = {
            "method": method, "sd": float(sd_v), "n_resid": int(len(cal))}

        raw = fn(test)
        fb = ~np.isfinite(raw)
        preds[tgt] = emit_rows(
            test, tgt, raw.where(~fb, fb_mean), pd.Series(sd_v, index=test.index), off,
            arm_id=ARM_ID, fold_id=fold_id, config_hash=config_hash,
            model_hash=_hash([tgt, m_alpha, a_alpha, p_alpha]),
            snapshot_hash=snapshot_hash,
            is_fallback=pd.Series(fb.to_numpy(), index=test.index),
            is_cold_start=cold, n_prior=n_prior,
            exclusion=pd.Series(pd.NA, index=test.index),
            low=d.get("low"), high=d.get("high"), want_quantiles=True)

    return {"predictions": preds, "diagnostics": diag}


def run_team_fold(train: pd.DataFrame, test: pd.DataFrame, fold_id: str, *,
                  config_hash: str, snapshot_hash: str = "synthetic") -> dict:
    """Emit `team_game_distribution`: T1 alphas, T2 calibration map, T3 dispersion."""
    d = DECLARED["team_game_distribution"]
    diag: dict = {"fold_id": fold_id}
    ts = team_split(train) if len(train) else TeamSplit(
        np.array([], dtype=np.int64), np.array([], dtype=np.int64),
        np.array([], dtype=np.int64), [], [], [], True, "empty window")
    diag["degenerate"], diag["reason"] = ts.degenerate, ts.reason
    diag["segment_dates"] = {"T1": len(ts.t1_dates), "T2": len(ts.t2_dates),
                             "T3": len(ts.t3_dates)}
    diag["zero_candidate_team_games"] = int(
        test.get("n_candidates", pd.Series(1, index=test.index)).eq(0).sum())

    if ts.degenerate:
        off = np.asarray(QUANTILE_Z) * d["sd"]
        pred = emit_rows(test, "team_game_distribution",
                         pd.Series(d["point"], index=test.index),
                         pd.Series(d["sd"], index=test.index), off,
                         arm_id=ARM_ID, fold_id=fold_id, config_hash=config_hash,
                         model_hash=_hash(["declared", "team"]),
                         snapshot_hash=snapshot_hash,
                         is_fallback=pd.Series(True, index=test.index),
                         is_cold_start=pd.Series(True, index=test.index),
                         n_prior=pd.Series(0, index=test.index),
                         exclusion=pd.Series(pd.NA, index=test.index),
                         low=d["low"], high=None, want_quantiles=True)
        diag["fallback"] = "declared_constants"
        return {"predictions": {"team_game_distribution": pred}, "diagnostics": diag}

    ctx1 = ts.context_for_alpha()
    # As on the player side: the channel-tuning mask must be a SUBSET of T1.
    t1_mask = pd.Series(False, index=train.index)
    t1_mask.loc[ts.t1] = True
    chans = [c for c in ("ft", "fg3", "paint", "np2") if f"ch_{c}" in train.columns]
    alphas: dict[str, float] = {}
    for ch in chans:
        col = f"ch_{ch}"

        def chan_pred(a, frame=None, col=col):
            f = train if frame is None else frame
            return f.groupby("team_id", sort=False)[col].transform(
                lambda s: s.ewm(alpha=a, adjust=True).mean().shift(1))

        alphas[ch], _, _ = select_alpha_bound(chan_pred, train[col], ctx1, t1_mask)
    diag["channel_alphas"] = alphas

    def structural(frame):
        if not chans:
            return pd.Series(np.nan, index=frame.index)
        tot = None
        for ch in chans:
            s = frame.groupby("team_id", sort=False)[f"ch_{ch}"].transform(
                lambda x, a=alphas[ch]: x.ewm(alpha=a, adjust=True).mean().shift(1))
            tot = s if tot is None else tot + s
        return tot

    ctx2 = ts.context_for_calibration_map()
    x2 = structural(train).reindex(ctx2.tuning_idx)
    y2 = train["team_points"].reindex(ctx2.tuning_idx)
    ok = np.isfinite(x2) & np.isfinite(y2)
    if int(ok.sum()) >= 3:
        slope, intercept = np.polyfit(x2[ok].to_numpy(float), y2[ok].to_numpy(float), 1)
        cal = (float(intercept), float(slope))
    else:
        cal = (float(d["point"]), 0.0)
    diag["calibration_map_intercept_slope"] = cal
    diag["calibration_map_n"] = int(ok.sum())

    fitted = cal[0] + cal[1] * structural(train)
    resid = (fitted.reindex(ts.t3) - train["team_points"].reindex(ts.t3)).to_numpy(float)
    sd_v, off, method = dispersion(resid, min_resid=MIN_RESID_TEAM)
    if method == "insufficient":
        sd_v = d["sd"]
        off = np.asarray(QUANTILE_Z) * sd_v
    diag["dispersion"] = {"method": method, "sd": float(sd_v), "n_resid": int(len(ts.t3))}

    raw = cal[0] + cal[1] * structural(test)
    fb = ~np.isfinite(raw)
    pred = emit_rows(test, "team_game_distribution", raw.where(~fb, d["point"]),
                     pd.Series(sd_v, index=test.index), off,
                     arm_id=ARM_ID, fold_id=fold_id, config_hash=config_hash,
                     model_hash=_hash([cal, sorted(alphas.items())]),
                     snapshot_hash=snapshot_hash,
                     is_fallback=pd.Series(fb.to_numpy(), index=test.index),
                     is_cold_start=pd.Series(False, index=test.index),
                     n_prior=pd.Series(0, index=test.index),
                     exclusion=pd.Series(pd.NA, index=test.index),
                     low=d["low"], high=None, want_quantiles=True)
    return {"predictions": {"team_game_distribution": pred}, "diagnostics": diag}
