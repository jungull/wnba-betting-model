#!/usr/bin/env python3
"""run_p3_downstream.py — execute the registered P3 downstream comparison.

Registered before execution as `p3_projected_exposure_downstream_v1`. Nothing is refit: the P3
coefficients, the exposure model, the pace model and the team incumbent are all consumed frozen.

Historical development evidence only. This cannot promote anything.

Run::

    python experiments/player_program/run_p3_downstream.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from evalharness.compare import cluster_bootstrap_ci     # noqa: E402
from evalharness.metrics import mae, rmse                # noqa: E402

OUT = HERE / "p3_downstream_v1"
EXPOSURE = HERE / "projected_exposure_v1/projected_player_possessions_v1.parquet"
ROTATIONS = HERE / "projected_exposure_v1/projected_team_rotations_v1.parquet"
PACE_ART = HERE / "projected_exposure_v1/team_possession_prior_v1.parquet"
P3 = HERE / "fits_v1/p3_coefficients_v1.parquet"
INCUMBENT = ROOT / "experiments/channel_reval/predictions_v2.csv"
MASTER_TEAM = ROOT / "data/masters/master_team.parquet"

AUTHORISED_COMMIT = "9806cb5"
PRIMARY_REGIME = "tier_a_only"
SENSITIVITY = ["tier_a_plus_tx_b", "tier_a_plus_tx_b_plus_s2"]

# frozen centering ladder — identical structure to team_possession_prior/1
WINDOW_K = 10
MIN_HISTORY_M = 3
FIRST_COEF_SEASON = 2022        # cutoffs 2021-2025 serve target seasons 2022-2026

ARMS = ["A_incumbent", "B_offensive", "C_net", "D_separate", "E_defensive_diagnostic"]


class ExperimentFailure(RuntimeError):
    """Any violation of the registered design. Nothing is written."""


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# preflight: the exposure numbers must be the authorised ones
# --------------------------------------------------------------------------- #
def assert_exposure_matches_authorised_commit() -> dict:
    rel = "experiments/player_program/projected_exposure_v1/projected_player_possessions_v1.parquet"
    cur = pd.read_parquet(EXPOSURE)
    with tempfile.TemporaryDirectory() as td:
        old_path = Path(td) / "old.parquet"
        r = subprocess.run(["git", "show", f"{AUTHORISED_COMMIT}:{rel}"],
                           cwd=ROOT, capture_output=True)
        if r.returncode != 0:
            raise ExperimentFailure(f"cannot read {AUTHORISED_COMMIT} exposure: {r.stderr[:200]}")
        old_path.write_bytes(r.stdout)
        old = pd.read_parquet(old_path)

    key = ["game_id", "team_id", "regime", "row_uid"]
    num = ["projected_minutes", "projected_minutes_micro", "projected_off_possessions",
           "projected_def_possessions", "projected_team_off_possessions",
           "projected_opp_off_possessions", "p_active", "e_minutes_given_active",
           "raw_expected_minutes"]
    a = old.set_index(key).sort_index()
    b = cur.set_index(key).sort_index()
    if not a.index.equals(b.index):
        raise ExperimentFailure("exposure row set differs from the authorised commit")
    for c in num:
        x, y = a[c].to_numpy(), b[c].to_numpy()
        if not np.allclose(x, y, rtol=0, atol=0, equal_nan=True):
            raise ExperimentFailure(f"exposure column {c} differs from {AUTHORISED_COMMIT}")
    added = sorted(set(b.columns) - set(a.columns))
    return {"authorised_commit": AUTHORISED_COMMIT,
            "rows": int(len(cur)),
            "numeric_columns_identical": num,
            "columns_added_since": added,
            "verdict": "every projected minute and possession is byte-identical to the "
                       "authorised commit; only labelling columns were added"}


# --------------------------------------------------------------------------- #
# personnel effects
# --------------------------------------------------------------------------- #
def personnel_effects(players: pd.DataFrame, p3: pd.DataFrame) -> pd.DataFrame:
    """E_off, E_def, E_net per (game_id, team_id, regime), in POINTS."""
    df = players[["game_id", "team_id", "regime", "player_id", "season", "game_date",
                  "projected_off_possessions", "projected_def_possessions",
                  "team_game_status"]].copy()
    df["cutoff"] = df["season"] - 1
    coef = p3.rename(columns={"training_cutoff_season": "cutoff"})
    df = df.merge(coef[["cutoff", "player_id", "orapm_100", "drapm_100", "net_rapm_100"]],
                  on=["cutoff", "player_id"], how="left", validate="m:1")
    df["has_coef"] = df["orapm_100"].notna()
    for c in ("orapm_100", "drapm_100", "net_rapm_100"):
        df[c] = df[c].fillna(0.0)          # neutral, league-average value in RAPM units

    df["c_off"] = df["orapm_100"] * df["projected_off_possessions"] / 100.0
    df["c_def"] = df["drapm_100"] * df["projected_def_possessions"] / 100.0
    df["c_net"] = df["net_rapm_100"] * df["projected_off_possessions"] / 100.0
    df["poss_with_coef"] = np.where(df["has_coef"], df["projected_off_possessions"], 0.0)

    g = df.groupby(["game_id", "team_id", "regime"], as_index=False).agg(
        season=("season", "first"), game_date=("game_date", "first"),
        status=("team_game_status", "first"),
        E_off=("c_off", "sum"), E_def=("c_def", "sum"), E_net=("c_net", "sum"),
        n_players=("player_id", "size"), n_with_coef=("has_coef", "sum"),
        poss=("projected_off_possessions", "sum"), poss_with_coef=("poss_with_coef", "sum"))
    g["coef_support"] = g["poss_with_coef"] / g["poss"].replace(0, np.nan)
    # a team-game whose pace is unresolved has no possessions, hence no personnel effect
    unresolved = g["status"] != "normal"
    g.loc[unresolved, ["E_off", "E_def", "E_net", "coef_support"]] = np.nan
    # seasons before the first admissible cutoff have no coefficient at all
    g.loc[g["season"] < FIRST_COEF_SEASON, ["E_off", "E_def", "E_net"]] = np.nan
    return g


def trailing_baselines(E: pd.DataFrame) -> pd.DataFrame:
    """B_off, B_def, B_net: the team's prior-games-only expected personnel effect."""
    out = []
    for regime, sub in E.groupby("regime", sort=True):
        sub = sub.sort_values(["game_date", "game_id"]).reset_index(drop=True)
        usable = sub[sub["E_net"].notna()]
        league = {}
        for col in ("E_off", "E_def", "E_net"):
            by_date = usable.groupby("game_date")[col].agg(["sum", "count"]).sort_index()
            league[col] = (by_date["sum"].cumsum().shift(1) / by_date["count"].cumsum().shift(1))
        hist: dict[int, list] = {}
        for t, s in usable.groupby("team_id", sort=True):
            hist[t] = list(zip(s["game_date"], s["season"],
                               s["E_off"], s["E_def"], s["E_net"]))
        for r in sub.itertuples(index=False):
            h = hist.get(r.team_id, [])
            same = [(o, d, n) for (dt, se, o, d, n) in h
                    if dt < r.game_date and se == r.season]
            prev = [(o, d, n) for (dt, se, o, d, n) in h
                    if dt < r.game_date and se == r.season - 1]
            if len(same) >= MIN_HISTORY_M:
                lvl, vals = 1, same[-WINDOW_K:]
            elif len(prev) >= MIN_HISTORY_M:
                lvl, vals = 2, prev[-WINDOW_K:]
            else:
                vals = None
                lv = {c: league[c].get(r.game_date, np.nan) for c in ("E_off", "E_def", "E_net")}
                if all(pd.notna(v) for v in lv.values()):
                    lvl = 3
                    b_off, b_def, b_net = lv["E_off"], lv["E_def"], lv["E_net"]
                    n_hist = -1
                else:
                    lvl = 4
                    b_off = b_def = b_net = np.nan
                    n_hist = 0
            if vals is not None:
                arr = np.array(vals, dtype=float)
                b_off, b_def, b_net = arr[:, 0].mean(), arr[:, 1].mean(), arr[:, 2].mean()
                n_hist = len(vals)
            out.append((r.game_id, r.team_id, regime, lvl, n_hist, b_off, b_def, b_net))
    B = pd.DataFrame(out, columns=["game_id", "team_id", "regime", "baseline_level",
                                   "n_baseline_history", "B_off", "B_def", "B_net"])
    return E.merge(B, on=["game_id", "team_id", "regime"], how="left", validate="1:1")


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #
def build_rows(EB: pd.DataFrame, regime: str) -> tuple[pd.DataFrame, dict]:
    inc = pd.read_csv(INCUMBENT)
    mt = pd.read_parquet(MASTER_TEAM, columns=["game_id", "team_id", "team_abbreviation"])
    mt["game_id"] = mt["game_id"].astype(str)
    inc["game_id"] = inc["GAME_ID"].astype(str)

    for side, abb in (("h", "TEAM_ABBREVIATION_h"), ("a", "TEAM_ABBREVIATION_a")):
        m = mt.rename(columns={"team_abbreviation": abb, "team_id": f"team_id_{side}"})
        inc = inc.merge(m, on=["game_id", abb], how="left", validate="1:1")
    if inc[["team_id_h", "team_id_a"]].isna().any().any():
        raise ExperimentFailure("could not map every incumbent club abbreviation to a team_id")

    e = EB[EB["regime"] == regime]
    for side in ("h", "a"):
        cols = {c: f"{c}_{side}" for c in ["E_off", "E_def", "E_net", "B_off", "B_def", "B_net",
                                           "baseline_level", "coef_support", "status",
                                           "n_players", "poss"]}
        sub = e[["game_id", "team_id"] + list(cols)].rename(
            columns={**cols, "team_id": f"team_id_{side}"})
        inc = inc.merge(sub, on=["game_id", f"team_id_{side}"], how="left", validate="1:1")

    n0 = len(inc)
    reasons = {}
    ok = pd.Series(True, index=inc.index)
    for label, cond in (
        ("rotation_not_normal_home", inc["status_h"] != "normal"),
        ("rotation_not_normal_away", inc["status_a"] != "normal"),
        ("personnel_effect_unresolved", inc[["E_net_h", "E_net_a"]].isna().any(axis=1)),
        ("baseline_unresolved", inc[["B_net_h", "B_net_a"]].isna().any(axis=1)),
        ("incumbent_prediction_missing", inc[["str_home_cal", "str_away_cal"]].isna().any(axis=1)),
    ):
        newly = cond & ok
        reasons[label] = int(newly.sum())
        ok &= ~cond
    rows = inc[ok].copy()

    for x in ("off", "def", "net"):
        for side in ("h", "a"):
            rows[f"d_{x}_{side}"] = rows[f"E_{x}_{side}"] - rows[f"B_{x}_{side}"]

    excl = {"incumbent_games": n0, "eligible_games": int(len(rows)),
            "excluded": int(n0 - len(rows)), "by_reason": reasons}
    return rows, excl


def arm_predictions(rows: pd.DataFrame) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    h0 = rows["str_home_cal"].to_numpy()
    a0 = rows["str_away_cal"].to_numpy()
    do_h, do_a = rows["d_off_h"].to_numpy(), rows["d_off_a"].to_numpy()
    dd_h, dd_a = rows["d_def_h"].to_numpy(), rows["d_def_a"].to_numpy()
    dn_h, dn_a = rows["d_net_h"].to_numpy(), rows["d_net_a"].to_numpy()
    return {
        "A_incumbent": (h0, a0),
        "B_offensive": (h0 + do_h, a0 + do_a),
        "C_net": (h0 + dn_h, a0 + dn_a),
        "D_separate": (h0 + do_h - dd_a, a0 + do_a - dd_h),
        "E_defensive_diagnostic": (h0 - dd_a, a0 - dd_h),
    }


def evaluate(rows: pd.DataFrame, preds: dict) -> dict:
    ph = rows["team_pts_h"].to_numpy(dtype=float)
    pa = rows["team_pts_a"].to_numpy(dtype=float)
    margin_true = ph - pa
    total_true = ph + pa
    game_ids = rows["game_id"].to_numpy()
    out = {}
    for arm, (h, a) in preds.items():
        scores_true = np.concatenate([ph, pa])
        scores_pred = np.concatenate([h, a])
        score_cluster = np.concatenate([game_ids, game_ids])
        m_pred = h - a
        t_pred = h + a
        slope = float(np.polyfit(m_pred, margin_true, 1)[0])
        out[arm] = {
            "n_games": int(len(rows)),
            "n_team_score_rows": int(len(scores_true)),
            "team_score_mae": mae(scores_true, scores_pred),
            "team_score_rmse": rmse(scores_true, scores_pred),
            "team_score_bias": float(np.mean(scores_pred - scores_true)),
            "home_score_mae": mae(ph, h), "away_score_mae": mae(pa, a),
            "home_score_bias": float(np.mean(h - ph)), "away_score_bias": float(np.mean(a - pa)),
            "margin_mae": mae(margin_true, m_pred), "margin_rmse": rmse(margin_true, m_pred),
            "margin_bias": float(np.mean(m_pred - margin_true)),
            "margin_calibration_slope": slope,
            "total_mae": mae(total_true, t_pred),
            "_score_abs_err": np.abs(scores_true - scores_pred),
            "_score_cluster": score_cluster,
            "_margin_abs_err": np.abs(margin_true - m_pred),
        }
    return out


def paired(res: dict, arm: str, base: str = "A_incumbent") -> dict:
    d_score = res[base]["_score_abs_err"] - res[arm]["_score_abs_err"]
    d_margin = res[base]["_margin_abs_err"] - res[arm]["_margin_abs_err"]
    gid = res[arm]["_score_cluster"]
    mg = np.arange(len(d_margin))
    ci_s = cluster_bootstrap_ci(d_score, gid)
    ci_m = cluster_bootstrap_ci(d_margin, mg)
    return {
        "team_score_mae_improvement": float(np.mean(d_score)),
        "team_score_ci90": [ci_s["low"], ci_s["high"]], "score_clusters": ci_s["n_clusters"],
        "margin_mae_improvement": float(np.mean(d_margin)),
        "margin_ci90": [ci_m["low"], ci_m["high"]], "margin_clusters": ci_m["n_clusters"],
        "note": "positive improvement means the arm beats the incumbent",
    }


def _strip(res: dict) -> dict:
    return {a: {k: v for k, v in d.items() if not k.startswith("_")} for a, d in res.items()}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    provenance = assert_exposure_matches_authorised_commit()

    players = pd.read_parquet(EXPOSURE)
    p3 = pd.read_parquet(P3)
    E = personnel_effects(players, p3)
    EB = trailing_baselines(E)

    rows, excl = build_rows(EB, PRIMARY_REGIME)
    if len(rows) == 0:
        raise ExperimentFailure("the primary universe is empty")
    preds = arm_predictions(rows)

    # predeclared consequence 2: arms C and D must produce identical margins
    mc = preds["C_net"][0] - preds["C_net"][1]
    md = preds["D_separate"][0] - preds["D_separate"][1]
    if not np.allclose(mc, md, rtol=0, atol=1e-9):
        raise ExperimentFailure(
            "registered prediction violated: arms C and D do not produce identical margins")
    # predeclared consequence 1: equal exposure implies E_net == E_off + E_def
    chk = (EB["E_net"] - (EB["E_off"] + EB["E_def"])).abs()
    if float(chk.max(skipna=True)) > 1e-9:
        raise ExperimentFailure("registered prediction violated: E_net != E_off + E_def")

    res = evaluate(rows, preds)
    pairs = {a: paired(res, a) for a in ARMS if a != "A_incumbent"}

    # by season
    by_season = {}
    for s, sub in rows.groupby("season_h"):
        p2 = arm_predictions(sub)
        r2 = evaluate(sub, p2)
        by_season[int(s)] = {
            "n_games": int(len(sub)),
            "margin_mae": {a: r2[a]["margin_mae"] for a in ARMS},
            "team_score_mae": {a: r2[a]["team_score_mae"] for a in ARMS},
        }

    # buckets: coefficient support and adjustment magnitude
    buckets = {}
    rows = rows.copy()
    rows["_support"] = (rows["coef_support_h"] + rows["coef_support_a"]) / 2.0
    rows["_adjmag"] = (rows["d_net_h"] - rows["d_net_a"]).abs()
    for name, col in (("coefficient_support", "_support"), ("adjustment_magnitude", "_adjmag")):
        try:
            lab = pd.qcut(rows[col], 3, labels=["low", "mid", "high"], duplicates="drop")
        except ValueError:
            continue
        blk = {}
        for b, sub in rows.groupby(lab, observed=True):
            if len(sub) < 5:
                continue
            r2 = evaluate(sub, arm_predictions(sub))
            blk[str(b)] = {"n_games": int(len(sub)),
                           "range": [float(sub[col].min()), float(sub[col].max())],
                           "margin_mae": {a: r2[a]["margin_mae"] for a in ARMS},
                           "team_score_mae": {a: r2[a]["team_score_mae"] for a in ARMS}}
        buckets[name] = blk

    # concentration of any margin gain, per arm
    concentration = {}
    for a in ARMS:
        if a == "A_incumbent":
            continue
        d = res["A_incumbent"]["_margin_abs_err"] - res[a]["_margin_abs_err"]
        order = np.argsort(-np.abs(d))
        k = max(1, int(round(0.05 * len(d))))
        top = d[order[:k]]
        concentration[a] = {
            "total_margin_improvement_points": float(np.sum(d)),
            "share_of_absolute_movement_in_top_5pct_games": float(
                np.sum(np.abs(top)) / np.sum(np.abs(d))) if np.sum(np.abs(d)) > 0 else None,
            "games_improved": int((d > 0).sum()), "games_worsened": int((d < 0).sum()),
            "by_season_margin_improvement": {
                int(s): float(np.mean(d[(rows["season_h"] == s).to_numpy()]))
                for s in sorted(rows["season_h"].unique())},
        }

    # sensitivity regimes, separately labelled, never enlarging the primary universe
    sens = {}
    primary_games = set(rows["game_id"])
    for regime in SENSITIVITY:
        r2, e2 = build_rows(EB, regime)
        r2 = r2[r2["game_id"].isin(primary_games)]
        if len(r2) < 10:
            sens[regime] = {"skipped": "fewer than ten eligible games"}
            continue
        rr = evaluate(r2, arm_predictions(r2))
        sens[regime] = {
            "label": "SENSITIVITY ONLY -- not production-eligible, not the primary universe",
            "n_games": int(len(r2)),
            "restricted_to_primary_games": True,
            "exclusions": e2,
            "margin_mae": {a: rr[a]["margin_mae"] for a in ARMS},
            "team_score_mae": {a: rr[a]["team_score_mae"] for a in ARMS},
        }

    out = {
        "schema": "p3_downstream_results/1",
        "experiment_id": "p3_projected_exposure_downstream_v1",
        "arm_id": "p3_projected_exposure_downstream/1",
        "executed_utc": _utc(),
        "evidence_class": "historical development evidence only; promotes nothing",
        "exposure_provenance": provenance,
        "input_sha256": {
            "incumbent": _sha(INCUMBENT), "p3_coefficients": _sha(P3),
            "exposure": _sha(EXPOSURE), "rotations": _sha(ROTATIONS), "pace": _sha(PACE_ART),
        },
        "executor_sha256": _sha(Path(__file__)),
        "primary_regime": PRIMARY_REGIME,
        "universe": excl,
        "centering": {"window_K": WINDOW_K, "min_history_m": MIN_HISTORY_M,
                      "baseline_levels": rows["baseline_level_h"].value_counts().sort_index().to_dict()},
        "coefficient_support": {
            "possession_weighted_share_with_a_coefficient": {
                "mean": float(rows["_support"].mean()), "min": float(rows["_support"].min()),
                "p05": float(rows["_support"].quantile(0.05)),
                "p50": float(rows["_support"].quantile(0.50)),
                "max": float(rows["_support"].max())},
            "players_without_a_coefficient_treated_as": "0.0 (neutral, league-average in RAPM units)",
        },
        "adjustment_magnitude_points": {
            "margin_adjustment_abs": {
                "mean": float(rows["_adjmag"].mean()), "p50": float(rows["_adjmag"].median()),
                "p95": float(rows["_adjmag"].quantile(0.95)), "max": float(rows["_adjmag"].max())},
        },
        "predeclared_consequences_verified": {
            "E_net_equals_E_off_plus_E_def": True,
            "arms_C_and_D_have_identical_margins": True,
            "meaning": ("C and D can differ only in the home/away SCORE split; a margin difference "
                        "between them would be an executor defect, not a finding"),
        },
        "results": _strip(res),
        "paired_vs_incumbent": pairs,
        "by_season": by_season,
        "buckets": buckets,
        "concentration": concentration,
        "sensitivity": sens,
    }
    (OUT / "P3_DOWNSTREAM_RESULTS.json").write_text(json.dumps(out, indent=2, default=str),
                                                    encoding="utf-8")
    keep = [c for c in rows.columns if not c.startswith("_")]
    rows[keep].to_parquet(OUT / "p3_downstream_rows.parquet", index=False)

    print(f"eligible games: {len(rows)} of {excl['incumbent_games']}")
    print(f"{'arm':26s} {'margin MAE':>11s} {'team MAE':>10s} {'home MAE':>9s} {'away MAE':>9s}")
    for a in ARMS:
        r = res[a]
        print(f"{a:26s} {r['margin_mae']:11.4f} {r['team_score_mae']:10.4f} "
              f"{r['home_score_mae']:9.4f} {r['away_score_mae']:9.4f}")
    print(f"\nresults: {OUT / 'P3_DOWNSTREAM_RESULTS.json'}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ExperimentFailure as exc:
        print(f"EXPERIMENT FAILED CLOSED: {exc}", file=sys.stderr)
        sys.exit(2)
