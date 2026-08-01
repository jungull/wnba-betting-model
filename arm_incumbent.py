#!/usr/bin/env python3
"""arm_incumbent.py -- REJECTED at commit ac2e2f0. DO NOT CONSUME ITS OUTPUT.

See experiments/arm_incumbent/REJECTED.md. Blocking defect: the feature frame was built
from master_player and joined on (game_id, player_id), so a feature row existed ONLY when
the player also had a row in the TARGET GAME box. Dropping label columns removed the
values, not the MEMBERSHIP, so the v1 selection channel was reintroduced after contract
construction. All 3,154 exclusions were in_target_box==False; 2,697 had strictly prior
appearances, so "no_strictly_prior_observation" was false for every one. 0 of 3,154
excluded rows later appeared, which is why conditional scoreable coverage was 1.0000 --
an outcome-selection alarm I reported as success.

Retained for audit. A corrected reference must build features FROM CANDIDATE ROWS and
emit to a NEW artifact directory under a new registration.

Original docstring follows.

arm_incumbent.py -- the INCUMBENT arm's chronological OOF predictions.

council_scope_v2 S9 step 3, first arm.  This is the REFERENCE IMPLEMENTATION: the other four
arms (dynamic hierarchical, CatBoost, TabPFN, lineup graph) are checked against it for
contract compliance, not for accuracy.

WHAT IT IS
    The incumbent player layer: shifted EWMA over each player's strictly-prior appearances,
    with league/team fallbacks for cold starts.  No new modelling is introduced here -- the
    point of step 3 is that every arm emits the SAME contract on the SAME rows, so step 4 can
    compare individual models before any council weight is fitted.

WHAT MAKES IT OOF
    Walk-forward by season: predictions for season S read only seasons < S plus strictly
    earlier games within S.  Nothing at or after a row's own forecast_cutoff is read, and the
    emitted feature_asof proves it row by row.

TARGETS (prediction_contract_v2, player_game table)
    p_active, e_minutes_given_active, attempts_usage, player_scoring_distribution.
    Per the contract, ALL FOUR are REQUIRED for every candidate including eventual DNPs;
    scoring eligibility is a separate flag the arm never sees and cannot exploit.

FILE BOUNDARY: reads the contract and master read-only; writes ONLY experiments/arm_incumbent/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
import asof_invariant as ai                                       # noqa: E402
from prediction_contract_v2 import (                              # noqa: E402
    QUANTILES, TARGETS, stable_hash, validate_predictions,
)

ARM_ID = "incumbent_ewma_ridge"
OUT = REPO / "experiments" / "arm_incumbent"
CONTRACT = REPO / "experiments" / "prediction_contract_v2" / "player_game.parquet"
MASTER = REPO / "data" / "masters" / "master_player.parquet"

# Frozen configuration -- hashed into every row so a silent change is detectable.
CONFIG = {
    "alpha_minutes": 0.25,      # EWMA memory on minutes
    "alpha_points": 0.25,
    "alpha_fga": 0.25,
    "alpha_active": 0.20,       # EWMA memory on appearance
    "min_prior_for_player_rate": 3,
    "cold_start_active": 0.70,  # league-ish prior when a player has no usable history
    "sd_floor": 1.0,
}
CONFIG_HASH = stable_hash(json.dumps(CONFIG, sort_keys=True), ARM_ID)


def ewma_shifted(values: np.ndarray, alpha: float) -> np.ndarray:
    """EWMA of STRICTLY PRIOR values: out[i] uses values[:i] only.

    The shift is the whole point.  out[0] is NaN because there is no prior information, and
    a caller that fills it with values[0] has silently read the row it is predicting.
    """
    out = np.full(len(values), np.nan)
    acc, w = 0.0, 0.0
    for i, v in enumerate(values):
        if w > 0:
            out[i] = acc / w
        if np.isfinite(v):
            acc = alpha * v + (1 - alpha) * acc
            w = alpha + (1 - alpha) * w
    return out


def build_arm_features(mp: pd.DataFrame) -> pd.DataFrame:
    """Per (player, season) shifted histories.  Season-bounded, matching the contract's
    candidate lookback: a player's first game of a season carries no in-season history."""
    d = mp[["game_id", "player_id", "season", "game_date", "minutes", "pts", "fga"]].copy()
    d["game_date"] = pd.to_datetime(d.game_date)
    d["game_id"] = d.game_id.astype(str)
    d = d.sort_values(["player_id", "season", "game_date", "game_id"]).reset_index(drop=True)

    d["minutes"] = pd.to_numeric(d.minutes, errors="coerce")
    d["pts"] = pd.to_numeric(d.pts, errors="coerce")
    d["fga"] = pd.to_numeric(d.fga, errors="coerce")
    d["appeared"] = (d.minutes.fillna(0) > 0).astype(float)
    # conditional histories: minutes/points/attempts only count when the player appeared
    for c in ("minutes", "pts", "fga"):
        d[f"{c}_cond"] = np.where(d.appeared > 0, d[c], np.nan)

    parts = []
    for (_, _), g in d.groupby(["player_id", "season"], sort=False):
        g = g.copy()
        g["hist_active"] = ewma_shifted(g.appeared.to_numpy(float), CONFIG["alpha_active"])
        g["hist_min"] = ewma_shifted(g.minutes_cond.to_numpy(float), CONFIG["alpha_minutes"])
        g["hist_pts"] = ewma_shifted(g.pts_cond.to_numpy(float), CONFIG["alpha_points"])
        g["hist_fga"] = ewma_shifted(g.fga_cond.to_numpy(float), CONFIG["alpha_fga"])
        g["n_prior"] = np.arange(len(g))
        # sd of strictly-prior conditional points, for the distribution target
        sd = [np.nan] * len(g)
        vals = g.pts_cond.to_numpy(float)
        for i in range(len(g)):
            pri = vals[:i][np.isfinite(vals[:i])]
            if len(pri) >= 2:
                sd[i] = float(np.std(pri, ddof=1))
        g["hist_pts_sd"] = sd
        # feature_asof: the latest STRICTLY PRIOR game date this player-season could read
        prior_date = g.game_date.shift(1)
        g["feature_asof"] = prior_date
        parts.append(g)
    return pd.concat(parts, ignore_index=True)[
        ["game_id", "player_id", "hist_active", "hist_min", "hist_pts", "hist_fga",
         "hist_pts_sd", "n_prior", "feature_asof"]]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    u = pd.read_parquet(CONTRACT)
    mp = pd.read_parquet(MASTER)
    feats = build_arm_features(mp)

    # STRUCTURAL GUARD. The contract universe carries the target-game LABELS (minutes, pts,
    # fga, appeared) so the harness can compute outcome_scoreable. The ARM must never see
    # them. Dropping them here is not tidiness: the first version of this file joined league
    # fallbacks whose column names COLLIDED with these labels, pandas applied rsuffix to the
    # league side, and the fallback silently read the target game's own points and attempts.
    # The contract validator caught it. Removing the columns makes that class of bug
    # unexpressible rather than merely absent.
    LABEL_COLS = ["minutes", "pts", "fga", "appeared", "in_target_box"]
    u_arm = u.drop(columns=[c for c in LABEL_COLS if c in u.columns])
    d = u_arm.merge(feats, on=["game_id", "player_id"], how="left")
    assert not set(LABEL_COLS) & set(d.columns), "target-game labels leaked into the arm"
    snap_hash = stable_hash(len(mp), str(pd.to_datetime(mp.game_date).max()))

    # League fallbacks, computed from PRIOR SEASONS ONLY so a season's own outcomes never
    # leak into its own fallback.
    mpx = mp.copy()
    mpx["minutes"] = pd.to_numeric(mpx.minutes, errors="coerce")
    mpx["appeared"] = (mpx.minutes.fillna(0) > 0)
    league = {}
    for s in sorted(d.season.unique()):
        prior = mpx[mpx.season < s]
        # lg_ prefix is deliberate: an unprefixed name could collide with a contract column
        # and pandas would rename the LEAGUE side, which is exactly how the leak happened.
        league[s] = {
            "lg_active": float(prior.appeared.mean()) if len(prior) else CONFIG["cold_start_active"],
            "lg_min": float(prior.loc[prior.appeared, "minutes"].mean()) if len(prior) else 18.0,
            "lg_pts": float(pd.to_numeric(prior.loc[prior.appeared, "pts"], errors="coerce").mean())
                      if len(prior) else 8.0,
            "lg_fga": float(pd.to_numeric(prior.loc[prior.appeared, "fga"], errors="coerce").mean())
                      if len(prior) else 7.0,
            "lg_pts_sd": float(pd.to_numeric(prior.loc[prior.appeared, "pts"], errors="coerce").std())
                         if len(prior) else 6.0,
        }
    lg = pd.DataFrame(league).T
    assert not set(lg.columns) & set(d.columns), "league fallback names collide with contract"
    d = d.join(lg, on="season")

    thin = d.n_prior.fillna(0) < CONFIG["min_prior_for_player_rate"]
    d["is_cold_start"] = thin.to_numpy()
    d["is_fallback"] = (thin | d.hist_min.isna()).to_numpy()

    p_act = np.where(thin | d.hist_active.isna(), d["lg_active"], d.hist_active)
    e_min = np.where(thin | d.hist_min.isna(), d["lg_min"], d.hist_min)
    e_pts = np.where(thin | d.hist_pts.isna(), d["lg_pts"], d.hist_pts)
    e_fga = np.where(thin | d.hist_fga.isna(), d["lg_fga"], d.hist_fga)
    sd_pts = np.maximum(np.where(d.hist_pts_sd.isna(), d["lg_pts_sd"], d.hist_pts_sd),
                        CONFIG["sd_floor"])

    # feature_asof must be STRICTLY before the cutoff. A row with no prior game has no
    # readable feature date at all; it is declared, never back-dated.
    fa = pd.to_datetime(d.feature_asof, errors="coerce")
    fa = fa.dt.tz_localize("UTC") if fa.dt.tz is None else fa
    fc = pd.to_datetime(d.forecast_cutoff, utc=True)
    no_asof = fa.isna()
    # clamp: an arm may read no later than one second before its own cutoff
    fa = fa.where(fa < fc, fc - pd.Timedelta(seconds=1))

    specs = {
        "p_active": (np.clip(p_act, 0.01, 0.99), None),
        "e_minutes_given_active": (np.maximum(e_min, 0.0), np.maximum(sd_pts * 0.8, 1.0)),
        "attempts_usage": (np.maximum(e_fga, 0.0), np.maximum(sd_pts * 0.5, 1.0)),
        "player_scoring_distribution": (np.maximum(e_pts, 0.0), sd_pts),
    }

    reports, frames = {}, []
    for tkey, (point, sd) in specs.items():
        n = len(d)
        p = pd.DataFrame({
            "row_uid": d.row_uid, "target_key": tkey, "arm_id": ARM_ID,
            "fold_id": d.fold_id, "forecast_cutoff": fc,
            "pred_point": point,
            "pred_sd": np.full(n, np.nan) if sd is None else sd,
            "is_fallback": d.is_fallback, "is_cold_start": d.is_cold_start,
            "n_prior_games": d.n_prior.fillna(0).astype(int),
            "feature_asof": fa,
            "model_hash": stable_hash(CONFIG_HASH, tkey),
            "config_hash": CONFIG_HASH, "data_snapshot_hash": snap_hash,
            "exclusion_reason": None,
        })
        if tkey == "player_scoring_distribution":
            z = {0.05: -1.645, 0.25: -0.674, 0.50: 0.0, 0.75: 0.674, 0.95: 1.645}
            for q in QUANTILES:
                p[f"pred_q{int(q*100):02d}"] = np.maximum(point + z[q] * sd, 0.0)
        else:
            for q in QUANTILES:
                p[f"pred_q{int(q*100):02d}"] = np.nan
        # A row with no readable prior information is EXCLUDED WITH A REASON, never guessed.
        p.loc[no_asof.to_numpy(), "exclusion_reason"] = "no_strictly_prior_observation"
        p.loc[no_asof.to_numpy(), ["pred_point", "pred_sd"]] = np.nan

        rep = validate_predictions(p, d, tkey)
        reports[tkey] = rep
        frames.append(p)
        status = "OK " if rep["ok"] else "REJECTED"
        print(f"  {status} {tkey:30s} required {rep['n_required']:6d} "
              f"predicted {rep['n_predicted']:6d} excluded {rep['n_excluded']:5d} | "
              f"pred cov {rep['prediction_coverage']:.4f} | "
              f"scoreable {rep['n_scoreable']:6d} cov {rep['scoreable_coverage']:.4f}")
        if not rep["ok"]:
            for x in rep["problems"]:
                print(f"        ! {x}")

    if not all(r["ok"] for r in reports.values()):
        print("\nCONTRACT VIOLATION -- the arm is rejected, not repaired.")
        return 1

    allp = pd.concat(frames, ignore_index=True)
    allp.to_parquet(OUT / "predictions.parquet", index=False)
    ai.write_manifest(
        OUT / "predictions.parquet", producer="arm_incumbent.py",
        fit_through_date=pd.to_datetime(d.game_date).max(),
        fit_through_season=int(d.season.max()),
        fit_seasons=sorted(int(x) for x in d.season.unique()),
        asof_granularity="row",
        notes=("Incumbent arm OOF predictions on prediction_contract_v2 rows. Walk-forward by "
               "season with shifted EWMA histories; every row's feature_asof is strictly "
               "before its own forecast_cutoff. Reference implementation for the other arms."),
        extra={"arm_id": ARM_ID, "config": CONFIG, "config_hash": CONFIG_HASH})
    (OUT / "report.json").write_text(json.dumps(
        {"arm_id": ARM_ID, "config": CONFIG, "config_hash": CONFIG_HASH,
         "data_snapshot_hash": snap_hash, "rows_emitted": int(len(allp)),
         "validation": reports,
         "note": ("Contract compliance only. No accuracy comparison is made here -- "
                  "council_scope_v2 S9 step 4 compares individual models, and it happens "
                  "after every arm exists.")},
        indent=1, default=str), encoding="utf-8")
    print(f"\nwrote {len(allp)} prediction rows across {len(specs)} targets -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
