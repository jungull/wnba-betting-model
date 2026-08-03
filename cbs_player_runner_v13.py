"""`cbs_player_runner/13` — the registered player runner, forked at ONE seam.

WHY THIS FILE EXISTS, AND WHY IT IS A COPY
-------------------------------------------

`cbs_v12` proved the real player fold cannot enter the modelling core: the inherited
`cbs_generator.order_obligations` refuses `prediction_contract_v4`'s 28 dual-team obligations
because its tie key is team-blind. The correction is `cbs_obligation_order/2`, which appends
`team_id` and a terminal `row_uid` tie-breaker.

`cbs_v8.run_player_fold` calls the inherited orderer **with its default column names** and exposes
no seam to pass the new key through. `cbs_generator` and `cbs_v8` are registered and immutable,
and rebinding another module's global would change that module's behaviour for every other caller
in the process — which `cbs_v8._provenance_rows` already rejects by name as not reentrant. The
supervisor's ruling (reply `20260802T232025204Z`) was therefore explicit:

    Make the smallest explicit player-runner fork needed to call it. Preserve the registered
    estimator, masks, tuning, calibration, and walk-forward logic byte-for-byte except for the
    ordering seam and v13 identity/receipt wrapper.

THE ENTIRE PERMITTED DIFF, AND HOW IT IS ENFORCED
--------------------------------------------------

This file was **generated from `inspect.getsource(cbs_v8.run_player_fold)`**, so the copy is exact
by construction rather than by care. Exactly two lines differ, both of them the ordering call:

    -    train = order_obligations(train) if len(train) else train
    -    test = order_obligations(test)
    +    train = (_order.order_obligations_v2(train, where="train frame") if len(train) else train)
    +    test = _order.order_obligations_v2(test, where="test frame")

`tests/test_cbs_v13.py` section 7 re-derives that diff at test time against the live
`cbs_v8.run_player_fold` source and **fails on any third differing line**. If the inherited runner
is ever amended, this fork stops being a fork and the gate says so.

Every other name the body uses — the estimator, the standardizer, the lambda and alpha selection,
the masks, the calibration, the dispersion, the walk-forward plan, the emission and the receipt
helpers — is IMPORTED from `cbs_v8`, so they are the same objects and cannot drift. Nothing is
reimplemented here.

WHAT IS *NOT* CHANGED, AND IS ASSERTED NOT TO BE
-------------------------------------------------

`build_walk_forward_plan(..., group_cols=["player_id", "season"])` is untouched. `team_id` is an
ordering discriminator and enters no grouping, no admission rule, no feature and no estimator, so
a traded player's history follows the player rather than resetting at the trade.

Two obligations at the same cutoff cannot enter each other's history, and that is structural
rather than incidental: admission is `availability < cutoff`, and
`cbs_v7.require_own_outcome_unavailable` already forbids a row's own outcome from being available
at its own cutoff. A dual-team sibling shares that game and that cutoff, so its availability is
never strictly less than its sibling's cutoff. Section 4 of the v13 suite asserts it on the real
collision rather than deducing it here.

This module fits real models when handed a real training window. It scores nothing.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import cbs_obligation_order as _order
from cbs_builders import QUANTILE_Z
from cbs_generator import (DECLARED, SplitContext, Standardizer, logistic_fit,
                           logistic_predict, player_split, prefix_mean,
                           select_alpha_bound)
from cbs_v5 import (MIN_RESID_PLAYER, P_ACTIVE_FEATURES, PLAYER_SORT_KEYS,
                    dispersion, residuals)
from cbs_v7 import (FittedState, REGISTRY_PATH, build_walk_forward_plan,
                    combine_history_frames, conditional_center,
                    player_fallback_level, require_outer_fold, walk_forward_ewma)
from cbs_v8 import (AdapterBoundaryError, PLAYER_TARGETS,
                    REQUIRED_PLAYER_FEATURE_SOURCES, _emit, _finish,
                    _provenance_rows, player_history_walk_forward,
                    require_registered_identity, resolve_fold_sources,
                    source_provenance_receipt, stage_a_features_v8)

RUNNER_ID = "cbs_player_runner/13"
FORKED_FROM = "cbs_v8.run_player_fold"

#: The complete permitted diff against the inherited runner, as line numbers within
#: `inspect.getsource(cbs_v8.run_player_fold)`. The v13 suite re-derives the actual diff and
#: fails if it is not exactly this.
PERMITTED_DIFF_LINES = (25, 26)


def run_player_fold(train: pd.DataFrame, test: pd.DataFrame, fold_id: str, *,
                    config_hash: str, snapshot_hash: str,
                    snapshot_manifest: dict | None = None, universe=None,
                    synthetic: bool = True,
                    allow_declared_defaults: bool | None = None,
                    artifact_root: Path | str | None = None,
                    registry_path: Path | str = REGISTRY_PATH) -> dict:
    """All four player targets, with provenance receipted on EVERY frame read."""
    # Identity and frame binding run FIRST, before any split, selection or fit,
    # so a mutated frame cannot reach a coefficient.
    identity = require_registered_identity(
        config_hash, snapshot_hash, snapshot_manifest,
        frames={"train": train, "test": test, "universe": universe},
        synthetic=synthetic, artifact_root=artifact_root, registry_path=registry_path)
    config_hash = identity["config_hash"]
    snapshot_hash = identity["snapshot_hash"]

    if allow_declared_defaults is None:
        allow_declared_defaults = bool(synthetic)
    if not synthetic and allow_declared_defaults:
        raise AdapterBoundaryError(
            "declared Stage-A defaults are forbidden on the real path; every "
            "registered input must actually be supplied")

    fold = require_outer_fold(train, test, fold_id)
    train = (_order.order_obligations_v2(train, where="train frame") if len(train) else train)
    test = _order.order_obligations_v2(test, where="test frame")

    # ---- source provenance on BOTH frames  (blocker 1) --------------------
    feature_asof, src = resolve_fold_sources(
        train, test, REQUIRED_PLAYER_FEATURE_SOURCES, synthetic=synthetic)
    prov_src = source_provenance_receipt(src, synthetic=synthetic)

    combined = combine_history_frames(train, test)
    if "appeared" not in combined.columns:
        combined["appeared"] = np.nan

    plan_all = build_walk_forward_plan(combined, group_cols=["player_id", "season"],
                                       sort_cols=list(PLAYER_SORT_KEYS))
    hist_all = player_history_walk_forward(combined, plan_all)
    hist_by_uid = hist_all.set_axis(combined["row_uid"].to_numpy(), axis=0)
    hist_te = hist_by_uid.reindex(test["row_uid"].to_numpy()).set_axis(test.index, axis=0)
    hist_tr = (hist_by_uid.reindex(train["row_uid"].to_numpy())
               .set_axis(train.index, axis=0) if len(train) else None)

    avail_src, policy_id = plan_all.availability_source, plan_all.policy_id
    diag: dict = {"fold_id": fold_id, "selected": {}, "dispersion": {},
                  "fallback_mean": {}, "fitted_state": {}, "fold_boundary": fold,
                  "availability": {"source": avail_src, "policy_id": policy_id},
                  "source_provenance": prov_src,
                  "walk_forward": {
                      "n_rows": int(len(combined)),
                      "mean_admitted_prior": float(np.mean(plan_all.n_admitted)),
                      "max_admitted_prior": int(np.max(plan_all.n_admitted))}}

    ctx = (player_split(train) if len(train) else
           SplitContext(np.array([], dtype=np.int64), np.array([], dtype=np.int64),
                        degenerate=True, reason="empty training window", label="player"))
    diag["degenerate"], diag["reason"] = ctx.degenerate, ctx.reason

    preds: dict[str, pd.DataFrame] = {}
    prov: list[pd.DataFrame] = []
    no_excl = pd.Series(pd.NA, index=test.index)
    hist_flat = hist_te.reset_index(drop=True)

    def record(tgt, pred, alpha, lam, npool):
        preds[tgt] = pred
        prov.append(_provenance_rows(
            pred, target=tgt, fold_id=fold_id, config_hash=config_hash,
            snapshot_hash=snapshot_hash, selected_alpha=alpha, selected_lambda=lam,
            residual_pool_n=npool, hist=hist_flat, team_prior=None,
            availability_source=avail_src, policy_id=policy_id))

    if ctx.degenerate or len(train) == 0:
        for tgt in PLAYER_TARGETS:
            d = DECLARED[tgt]
            sd = d.get("sd")
            comp = f"{tgt}/declared_constant"
            st = FittedState(target=tgt, fold_id=fold_id, component_id=comp,
                             fallback_mean=d["point"], dispersion_sd=sd,
                             dispersion_method="declared",
                             availability_source=avail_src,
                             availability_policy_id=policy_id,
                             support={"low": d.get("low"), "high": d.get("high")})
            n_prior = hist_te["n_prior_appearances"]
            lvl = player_fallback_level(test, n_prior,
                                        pd.Series(True, index=test.index),
                                        degenerate=True)
            record(tgt, _emit(
                test, tgt, pd.Series(d["point"], index=test.index),
                pd.Series(sd, index=test.index) if sd else None,
                (np.asarray(QUANTILE_Z) * sd) if sd else None,
                fold_id=fold_id, config_hash=config_hash, snapshot_hash=snapshot_hash,
                model_hash=st.hash(), feature_asof=feature_asof, fallback_level=lvl,
                component_id=pd.Series(comp, index=test.index),
                is_cold=pd.Series(True, index=test.index), n_prior=n_prior,
                exclusion=no_excl, low=d.get("low"), high=d.get("high"),
                want_q=(tgt != "p_active")), None, None, None)
            diag["fitted_state"][tgt] = st.to_dict()
        diag["fallback"] = "declared_constants"
        return _finish(preds, pd.concat(prov, ignore_index=True), diag, universe,
                       fold_id, config_hash, snapshot_hash, fold, identity, prov_src)

    tuning_mask = pd.Series(False, index=train.index)
    tuning_mask.loc[ctx.tuning_idx] = True
    active_any = train["appeared"].astype(bool)
    all_tune, active_tune = tuning_mask, tuning_mask & active_any

    base_rate = prefix_mean(train["appeared"].astype(float), ctx, all_tune)
    Xtr = stage_a_features_v8(train, hist_tr, base_rate,
                              allow_declared_defaults=allow_declared_defaults)
    Xte = stage_a_features_v8(test, hist_te, base_rate,
                              allow_declared_defaults=allow_declared_defaults)
    from cbs_v5 import select_lambda_chronological
    lam, lam_default, inner = select_lambda_chronological(
        Xtr, train["appeared"].astype(float), ctx, train)
    tr_idx = ctx.require_tuning(np.asarray(train.index[all_tune]))
    std = Standardizer(Xtr.loc[tr_idx])
    beta = logistic_fit(std.transform(Xtr.loc[tr_idx]),
                        train["appeared"].reindex(tr_idx).to_numpy(float), lam)
    p_hat = pd.Series(logistic_predict(std.transform(Xte), beta), index=test.index)

    comp_pa = "p_active/ridge_logistic_stage_a"
    st_pa = FittedState(target="p_active", fold_id=fold_id, component_id=comp_pa,
                        feature_order=list(P_ACTIVE_FEATURES),
                        scaler_mean=std.mean.tolist(), scaler_std=std.std.tolist(),
                        dropped_features=list(std.dropped), lam=lam,
                        beta=np.round(beta, 12).tolist(), base_rate=base_rate,
                        availability_source=avail_src, availability_policy_id=policy_id,
                        support={"low": 0.0, "high": 1.0})
    diag["selected"].update({"lambda": lam, "lambda_default": lam_default,
                             "lambda_inner_fit_dates": len(inner.fit_dates),
                             "lambda_inner_val_dates": len(inner.val_dates)})
    diag["base_rate"] = base_rate
    diag["fitted_state"]["p_active"] = st_pa.to_dict()

    n_oblig = hist_te["n_prior_candidate_games"]
    lvl_pa = player_fallback_level(test, n_oblig, np.isfinite(p_hat))
    comp_col_pa = pd.Series(comp_pa, index=test.index).mask(
        lvl_pa > 0, "p_active/declared_constant")
    record("p_active", _emit(
        test, "p_active", p_hat.where(lvl_pa == 0, DECLARED["p_active"]["point"]),
        None, None, fold_id=fold_id, config_hash=config_hash,
        snapshot_hash=snapshot_hash, model_hash=st_pa.hash(),
        feature_asof=feature_asof, fallback_level=lvl_pa, component_id=comp_col_pa,
        is_cold=~hist_te["has_prior_obligation"],
        n_prior=hist_te["n_prior_appearances"], exclusion=no_excl,
        low=0.0, high=1.0, want_q=False), None, lam, None)

    plan_tr = build_walk_forward_plan(train, group_cols=["player_id", "season"],
                                      sort_cols=list(PLAYER_SORT_KEYS))
    act_tr = train["appeared"].astype(bool)

    def minutes_pred(a):
        return walk_forward_ewma(plan_tr, train["minutes"], a, mask=act_tr)

    m_alpha, _, m_b = select_alpha_bound(minutes_pred, train["minutes"], ctx, active_tune)

    def attempts_pred(a):
        return conditional_center(plan_tr, train, act_tr, "attempts_usage",
                                  minutes_alpha=m_alpha, rate_alpha=a)

    def points_pred(a):
        return conditional_center(plan_tr, train, act_tr,
                                  "player_scoring_distribution",
                                  minutes_alpha=m_alpha, rate_alpha=a)

    a_alpha, _, a_b = select_alpha_bound(attempts_pred, train["fga"], ctx, active_tune)
    p_alpha, _, p_b = select_alpha_bound(points_pred, train["points"], ctx, active_tune)
    diag["selected"].update({"minutes_alpha": m_alpha, "attempts_alpha": a_alpha,
                             "points_alpha": p_alpha,
                             "minutes_alpha_held_fixed_at": m_alpha,
                             "boundaries": {"minutes": m_b, "attempts": a_b,
                                            "points": p_b}})

    act_all = combined["appeared"].astype(float).fillna(0.0).astype(bool)

    def _center(alpha_rate, tgt):
        s = conditional_center(plan_all, combined, act_all, tgt,
                               minutes_alpha=m_alpha, rate_alpha=alpha_rate)
        return (pd.Series(s.to_numpy(), index=combined["row_uid"].to_numpy())
                .reindex(test["row_uid"].to_numpy()).set_axis(test.index))

    for tgt, alpha, ycol, tr_fn in (
            ("e_minutes_given_active", m_alpha, "minutes",
             lambda: walk_forward_ewma(plan_tr, train["minutes"], m_alpha, mask=act_tr)),
            ("attempts_usage", a_alpha, "fga", lambda: attempts_pred(a_alpha)),
            ("player_scoring_distribution", p_alpha, "points",
             lambda: points_pred(p_alpha))):
        d = DECLARED[tgt]
        fb_mean = prefix_mean(train[ycol].astype(float), ctx, active_tune)
        if not np.isfinite(fb_mean):
            fb_mean = d["point"]
        diag["fallback_mean"][tgt] = fb_mean

        cal = np.intersect1d(ctx.calibration_idx, np.asarray(train.index[act_tr]))
        sd_v, off, method = dispersion(
            residuals(train[ycol].reindex(cal), tr_fn().reindex(cal)),
            min_resid=MIN_RESID_PLAYER)
        if method == "insufficient":
            sd_v = d["sd"]
            off = np.asarray(QUANTILE_Z) * sd_v
        diag["dispersion"][tgt] = {"method": method, "sd": float(sd_v),
                                   "n_resid": int(len(cal))}

        raw = _center(alpha, tgt)
        n_prior = hist_te["n_prior_appearances"]
        lvl = player_fallback_level(test, n_prior, np.isfinite(raw))
        comp = f"{tgt}/walk_forward_active_ewma"
        comp_col = pd.Series(comp, index=test.index).mask(lvl > 0, f"{tgt}/prefix_mean")

        st = FittedState(target=tgt, fold_id=fold_id, component_id=comp,
                         alphas={"minutes": m_alpha, "attempts": a_alpha,
                                 "points": p_alpha},
                         fallback_mean=fb_mean, dispersion_sd=float(sd_v),
                         dispersion_method=method,
                         dispersion_offsets=np.round(off, 12).tolist(),
                         residual_pool_n=int(len(cal)),
                         availability_source=avail_src, availability_policy_id=policy_id,
                         support={"low": d.get("low"), "high": d.get("high")})
        diag["fitted_state"][tgt] = st.to_dict()
        record(tgt, _emit(
            test, tgt, raw.where(lvl == 0, fb_mean),
            pd.Series(sd_v, index=test.index), off, fold_id=fold_id,
            config_hash=config_hash, snapshot_hash=snapshot_hash,
            model_hash=st.hash(), feature_asof=feature_asof, fallback_level=lvl,
            component_id=comp_col, is_cold=~hist_te["has_prior_appearance"],
            n_prior=n_prior, exclusion=no_excl, low=d.get("low"), high=d.get("high"),
            want_q=True), alpha, None, int(len(cal)))

    return _finish(preds, pd.concat(prov, ignore_index=True), diag, universe,
                   fold_id, config_hash, snapshot_hash, fold, identity, prov_src)
