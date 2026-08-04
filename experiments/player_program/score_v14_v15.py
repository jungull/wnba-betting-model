#!/usr/bin/env python3
"""score_v14_v15.py — AUTHORISED diagnostic scoring of two FROZEN artifacts.

Scores `contract_baseline_suite_v14` on `prediction_contract_v4` and
`cbs_v15_player_oof_v5` revision 8 on `prediction_contract_v5`. Both artifacts are read-only.

**This module changes nothing.** It fits nothing, tunes nothing, selects no threshold, repairs no
sensitivity arm and generates no revision. It reads frozen forecasts and frozen outcomes and
computes metrics.

Scoring is DIAGNOSTIC: what can the frozen baseline predict, and where does the v5 universe help
or hurt. It is not authorisation to optimise, promote, claim betting value, claim adjusted
score-differential impact, or start P3.
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
V14 = REPO / "experiments" / "cbs_v14_player_oof" / "attempt_001"
V15 = REPO / "experiments" / "cbs_v15_player_oof_v5" / "attempt_001"
CONTRACT5 = REPO / "experiments" / "prediction_contract_v5" / "player_game_enriched.parquet"
MASTER = REPO / "data" / "masters" / "master_player.parquet"

TARGETS = ("p_active", "e_minutes_given_active", "attempts_usage",
           "player_scoring_distribution")
OUTCOME_OF = {"p_active": "appeared", "e_minutes_given_active": "minutes",
              "attempts_usage": "fga", "player_scoring_distribution": "pts"}
SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
RNG = np.random.default_rng(20260803)
N_BOOT = 2000


# ---------------------------------------------------------------- loading

def load_preds(root: Path, target: str) -> pd.DataFrame:
    fr = []
    for s in SEASONS:
        p = root / f"predictions__{target}__{s}.parquet"
        if p.exists():
            fr.append(pd.read_parquet(p)[["row_uid", "pred_point", "fold_id", "is_cold_start",
                                          "is_fallback", "component_id"]])
    return pd.concat(fr, ignore_index=True)


def load_context() -> pd.DataFrame:
    c = pd.read_parquet(CONTRACT5)
    keep = ["row_uid", "player_id", "team_id", "game_id", "game_date", "season",
            "evaluation_tier", "universe_tier", "appeared", "minutes", "pts", "fga",
            "is_cold_start", "n_prior_appearances", "era"] + \
        [f"outcome_scoreable__{t}" for t in TARGETS]
    c = c[[k for k in keep if k in c.columns]].copy()
    mp = pd.read_parquet(MASTER)[["game_id", "team_id", "player_id", "starter_flag"]]
    mp["game_id"] = mp["game_id"].astype(str)
    for col in ("team_id", "player_id"):
        mp[col] = mp[col].astype("int64")
    mp = mp.drop_duplicates(["game_id", "team_id", "player_id"])
    c["game_id"] = c["game_id"].astype(str)
    c = c.merge(mp, on=["game_id", "team_id", "player_id"], how="left")
    c["starter"] = pd.to_numeric(c["starter_flag"], errors="coerce")
    c["game_date"] = pd.to_datetime(c["game_date"])
    return c


# ---------------------------------------------------------------- metrics

def _auroc(y: np.ndarray, p: np.ndarray) -> float | None:
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), float)
    ranks[order] = np.arange(1, len(p) + 1)
    # average ranks for ties
    df = pd.DataFrame({"p": p, "r": ranks})
    ranks = df.groupby("p")["r"].transform("mean").to_numpy()
    n1, n0 = len(pos), len(neg)
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _cal_slope_intercept(y: np.ndarray, p: np.ndarray) -> tuple:
    """Logistic recalibration of the outcome on logit(p). Newton, no sklearn."""
    eps = 1e-9
    x = np.log(np.clip(p, eps, 1 - eps) / (1 - np.clip(p, eps, 1 - eps)))
    b = np.array([0.0, 1.0])
    X = np.column_stack([np.ones_like(x), x])
    for _ in range(60):
        eta = X @ b
        mu = 1.0 / (1.0 + np.exp(-eta))
        W = np.clip(mu * (1 - mu), 1e-12, None)
        g = X.T @ (y - mu)
        H = X.T @ (X * W[:, None])
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            return None, None
        b = b + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return float(b[1]), float(b[0])


def prob_metrics(y: np.ndarray, p: np.ndarray) -> dict:
    if len(y) == 0:
        return {"n": 0}
    eps = 1e-15
    pc = np.clip(p, eps, 1 - eps)
    slope, icpt = _cal_slope_intercept(y.astype(float), p)
    return {
        "n": int(len(y)),
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc))),
        "auroc": _auroc(y, p),
        "calibration_slope": slope, "calibration_intercept": icpt,
        "pred_active_rate": float(np.mean(p)), "actual_active_rate": float(np.mean(y)),
        "rate_gap": float(np.mean(p) - np.mean(y)),
    }


def reg_metrics(y: np.ndarray, p: np.ndarray) -> dict:
    if len(y) == 0:
        return {"n": 0}
    e = p - y
    return {"n": int(len(y)), "mae": float(np.mean(np.abs(e))),
            "rmse": float(np.sqrt(np.mean(e ** 2))),
            "mean_signed_error": float(np.mean(e)),
            "mean_actual": float(np.mean(y)), "mean_pred": float(np.mean(p))}


def reliability(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list:
    if len(y) == 0:
        return []
    q = np.quantile(p, np.linspace(0, 1, bins + 1))
    q[0], q[-1] = -np.inf, np.inf
    idx = np.digitize(p, q[1:-1])
    out = []
    for b in range(bins):
        m = idx == b
        if m.sum() == 0:
            continue
        out.append({"bin": b, "n": int(m.sum()), "mean_pred": round(float(p[m].mean()), 5),
                    "actual_rate": round(float(y[m].mean()), 5)})
    return out


def bucket_calibration(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list:
    if len(y) == 0:
        return []
    q = np.quantile(p, np.linspace(0, 1, bins + 1))
    q[0], q[-1] = -np.inf, np.inf
    idx = np.digitize(p, q[1:-1])
    out = []
    for b in range(bins):
        m = idx == b
        if m.sum() == 0:
            continue
        out.append({"bin": b, "n": int(m.sum()),
                    "mean_pred": round(float(p[m].mean()), 4),
                    "mean_actual": round(float(y[m].mean()), 4),
                    "mean_signed_error": round(float((p[m] - y[m]).mean()), 4)})
    return out


# ---------------------------------------------------------------- bootstrap

def cluster_boot_diff(loss_a: np.ndarray, loss_b: np.ndarray, clusters: np.ndarray,
                      n_boot: int = N_BOOT, level: float = 0.90) -> dict:
    """Paired difference (a - b) with a CLUSTER bootstrap. Positive = a worse."""
    d = loss_a - loss_b
    uniq, inv = np.unique(clusters, return_inverse=True)
    k = len(uniq)
    sums = np.bincount(inv, weights=d, minlength=k)
    cnts = np.bincount(inv, minlength=k).astype(float)
    stats = np.empty(n_boot)
    for i in range(n_boot):
        pick = RNG.integers(0, k, k)
        stats[i] = sums[pick].sum() / max(cnts[pick].sum(), 1e-12)
    lo, hi = np.quantile(stats, [(1 - level) / 2, 1 - (1 - level) / 2])
    return {"point": float(d.mean()), "ci_low": float(lo), "ci_high": float(hi),
            "ci_level": level, "n_rows": int(len(d)), "n_clusters": int(k),
            "n_boot": n_boot, "excludes_zero": bool(lo > 0 or hi < 0)}


# ---------------------------------------------------------------- assembly

def build(root: Path, ctx: pd.DataFrame) -> dict:
    out = {}
    for t in TARGETS:
        p = load_preds(root, t)
        d = p.merge(ctx, on="row_uid", how="left", suffixes=("", "_ctx"))
        d["is_cold_start"] = d["is_cold_start_ctx"].fillna(d["is_cold_start"]) \
            if "is_cold_start_ctx" in d.columns else d["is_cold_start"]
        d["y"] = d[OUTCOME_OF[t]].astype(float)
        sc = f"outcome_scoreable__{t}"
        d["scoreable"] = d[sc].astype(bool) if sc in d.columns else True
        if t != "p_active":
            d["scoreable"] &= d["appeared"].astype(bool)
        out[t] = d
    return out


def score_slice(t: str, d: pd.DataFrame) -> dict:
    d = d[d["scoreable"]]
    if not len(d):
        return {"n": 0}
    y, p = d["y"].to_numpy(float), d["pred_point"].to_numpy(float)
    if t == "p_active":
        m = prob_metrics(y, p)
        m["reliability_deciles"] = reliability(y, p)
    else:
        m = reg_metrics(y, p)
        m["calibration_by_predicted_bucket"] = bucket_calibration(y, p)
    return m


def breakdowns(t: str, d: pd.DataFrame) -> dict:
    s = d[d["scoreable"]]
    res = {"by_tier": {}, "by_season": {}, "by_cold_start": {}}
    for k, g in s.groupby("evaluation_tier"):
        res["by_tier"][k] = score_slice(t, g)
    for k, g in s.groupby("season"):
        res["by_season"][str(int(k))] = score_slice(t, g)
    for k, g in s.groupby(s["is_cold_start"].astype(bool)):
        res["by_cold_start"]["cold" if k else "warm"] = score_slice(t, g)
    if t != "p_active" and s["starter"].notna().any():
        res["by_role"] = {}
        for k, g in s.groupby(s["starter"].fillna(-1).astype(int)):
            if k < 0:
                continue
            res["by_role"]["starter" if k == 1 else "bench"] = score_slice(t, g)
    if t != "p_active":
        pooled = score_slice(t, s)
        per_player = s.groupby("player_id").apply(
            lambda g: np.mean(np.abs(g["pred_point"] - g["y"])))
        res["macro_average_by_player_mae"] = float(per_player.mean())
        res["n_players"] = int(len(per_player))
        w = s["minutes"].to_numpy(float)
        if t != "e_minutes_given_active" and w.sum() > 0:
            res["minutes_weighted_mae"] = float(
                np.sum(w * np.abs(s["pred_point"] - s["y"])) / w.sum())
        res["pooled_player_game_mae"] = pooled["mae"]
    return res


def main() -> int:
    ctx = load_context()
    d14, d15 = build(V14, ctx), build(V15, ctx)

    rep = {
        "schema": "v14_v15_scoring/1",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifacts": {
            "v14": "experiments/cbs_v14_player_oof/attempt_001 (contract_baseline_suite_v14 / "
                   "prediction_contract_v4)",
            "v15": "experiments/cbs_v15_player_oof_v5/attempt_001 "
                   "(cbs_v15_player_oof_v5 rev 8 / prediction_contract_v5)",
            "both_frozen_and_unmodified": True,
        },
        "purpose": "DIAGNOSTIC. Not authorisation to optimise, promote, claim betting value, "
                   "claim adjusted score-differential impact, or start P3.",
        "targets_are_game_totals_not_possession_normalised": True,
        "by_target": {},
    }

    for t in TARGETS:
        rep["by_target"][t] = {
            "v14_on_v4_universe": {**score_slice(t, d14[t]), **breakdowns(t, d14[t])},
            "v15_all_tiers_pooled": score_slice(t, d15[t]),
            "v15_breakdowns": breakdowns(t, d15[t]),
        }

    # ---- common rows and expanded universe -------------------------------
    common_rep, expanded_rep = {}, {}
    for t in TARGETS:
        a, b = d14[t], d15[t]
        k14, k15 = set(a["row_uid"]), set(b["row_uid"])
        common = k14 & k15
        m = a[a["row_uid"].isin(common)][["row_uid", "pred_point", "y", "scoreable",
                                          "season", "game_date", "player_id",
                                          "is_cold_start"]].merge(
            b[b["row_uid"].isin(common)][["row_uid", "pred_point", "scoreable"]],
            on="row_uid", suffixes=("_14", "_15"))
        m = m[m["scoreable_14"] & m["scoreable_15"]]
        y = m["y"].to_numpy(float)
        p14, p15 = m["pred_point_14"].to_numpy(float), m["pred_point_15"].to_numpy(float)
        if t == "p_active":
            l14, l15 = (p14 - y) ** 2, (p15 - y) ** 2
            met = "brier"
        else:
            l14, l15 = np.abs(p14 - y), np.abs(p15 - y)
            met = "mae"
        entry = {
            "metric": met, "n_scoreable_common": int(len(m)),
            "v14": float(l14.mean()) if len(m) else None,
            "v15": float(l15.mean()) if len(m) else None,
            "paired_diff_v15_minus_v14": float((l15 - l14).mean()) if len(m) else None,
        }
        if len(m):
            entry["bootstrap_date_cluster"] = cluster_boot_diff(
                l15, l14, m["game_date"].dt.strftime("%Y-%m-%d").to_numpy())
            entry["bootstrap_player_cluster_sensitivity"] = cluster_boot_diff(
                l15, l14, m["player_id"].to_numpy())
            by_season = {}
            for s, g in m.groupby("season"):
                yy = g["y"].to_numpy(float)
                a2 = (g["pred_point_14"].to_numpy(float) - yy)
                b2 = (g["pred_point_15"].to_numpy(float) - yy)
                la = a2 ** 2 if t == "p_active" else np.abs(a2)
                lb = b2 ** 2 if t == "p_active" else np.abs(b2)
                by_season[str(int(s))] = {"n": int(len(g)), "v14": float(la.mean()),
                                          "v15": float(lb.mean()),
                                          "diff": float((lb - la).mean())}
            entry["by_season"] = by_season
            cs = {}
            for k, g in m.groupby(m["is_cold_start"].astype(bool)):
                yy = g["y"].to_numpy(float)
                a2 = g["pred_point_14"].to_numpy(float) - yy
                b2 = g["pred_point_15"].to_numpy(float) - yy
                la = a2 ** 2 if t == "p_active" else np.abs(a2)
                lb = b2 ** 2 if t == "p_active" else np.abs(b2)
                cs["cold" if k else "warm"] = {"n": int(len(g)), "v14": float(la.mean()),
                                               "v15": float(lb.mean()),
                                               "diff": float((lb - la).mean())}
            entry["by_cold_start"] = cs
        common_rep[t] = entry

        ex = b[~b["row_uid"].isin(k14) & b["scoreable"]]
        expanded_rep[t] = score_slice(t, ex)
        expanded_rep[t]["by_tier"] = {k: score_slice(t, g)
                                      for k, g in ex.groupby("evaluation_tier")}
    rep["common_rows"] = common_rep
    rep["expanded_universe_only"] = expanded_rep

    # ---- end-to-end expected minutes + exposure decomposition -------------
    rep["end_to_end_and_decomposition"] = end_to_end(d14, d15)

    # ---- Tier B history attribution on SCORED rows -----------------------
    rep["tier_b_history_attribution_on_scored_rows"] = tier_b_effect(d14, d15)

    (HERE / "V14_V15_SCORING.json").write_text(
        json.dumps(rep, indent=2, default=str) + "\n", encoding="utf-8", newline="")
    print("wrote V14_V15_SCORING.json")
    return 0


def end_to_end(d14: dict, d15: dict) -> dict:
    out = {}
    for name, d in (("v14", d14), ("v15", d15)):
        pa = d["p_active"][["row_uid", "pred_point", "y", "evaluation_tier",
                            "season", "minutes", "appeared"]].rename(
            columns={"pred_point": "p", "y": "act"})
        em = d["e_minutes_given_active"][["row_uid", "pred_point"]].rename(
            columns={"pred_point": "m"})
        j = pa.merge(em, on="row_uid")
        j["exp_min_honest"] = j["p"] * j["m"]
        j["exp_min_oracle_active"] = j["act"] * j["m"]
        y = j["minutes"].fillna(0.0).to_numpy(float)
        out[name] = {
            "n": int(len(j)),
            "information_honest": reg_metrics(y, j["exp_min_honest"].to_numpy(float)),
            "oracle_active_diagnostic": reg_metrics(
                y, j["exp_min_oracle_active"].to_numpy(float)),
            "oracle_label": ("HINDSIGHT-ASSISTED. Uses actual active/inactive status with the "
                             "frozen conditional-minutes prediction. Attribution only; NOT "
                             "live-achievable and NOT a betting backtest."),
        }
    # oracle-exposure for the production targets
    for name, d in (("v14", d14), ("v15", d15)):
        ex = {}
        for t in ("attempts_usage", "player_scoring_distribution"):
            s = d[t][d[t]["scoreable"]].copy()
            em = d["e_minutes_given_active"][["row_uid", "pred_point"]].rename(
                columns={"pred_point": "m_pred"})
            s = s.merge(em, on="row_uid")
            s = s[s["m_pred"] > 0]
            rate = s["pred_point"] / s["m_pred"]                    # frozen per-minute rate
            oracle = rate * s["minutes"].astype(float)
            ex[t] = {
                "frozen_full_prediction": reg_metrics(s["y"].to_numpy(float),
                                                      s["pred_point"].to_numpy(float)),
                "oracle_minutes_exposure": reg_metrics(s["y"].to_numpy(float),
                                                       oracle.to_numpy(float)),
                "n": int(len(s)),
                "oracle_label": ("HINDSIGHT-ASSISTED: the frozen pregame per-minute rate applied "
                                 "to ACTUAL minutes. Isolates the rate estimate from exposure "
                                 "error. NOT live-achievable."),
            }
        out[name]["oracle_exposure"] = ex
    return out


def tier_b_effect(d14: dict, d15: dict) -> dict:
    """Do v14/v15 common-row differences concentrate in Tier A rows whose history moved?"""
    import cbs_real_frames_v5 as rf5
    affected = set()
    for s in (2022, 2023, 2024, 2025, 2026):
        pri = rf5.build_player_frame_v5(s, REPO, require_attested=True, tier_b_history=True)
        sen = rf5.build_player_frame_v5(s, REPO, require_attested=True, tier_b_history=False)
        a = pri["test"].sort_values("row_uid").reset_index(drop=True)
        b = sen["test"].sort_values("row_uid").reset_index(drop=True)
        b = b[b["row_uid"].isin(set(a["row_uid"]))].sort_values("row_uid").reset_index(drop=True)
        a2 = a[a["row_uid"].isin(set(b["row_uid"]))].sort_values("row_uid").reset_index(drop=True)
        cols = [c for c in ("min_ewma", "start_share_l5", "played_share_l10_team_games",
                            "days_since_last_appearance", "started_last", "games_missed_streak")
                if c in a2.columns and c in b.columns]
        mask = np.zeros(len(a2), dtype=bool)
        for c in cols:
            mask |= a2[c].to_numpy() != b[c].to_numpy()
        affected |= set(a2.loc[mask, "row_uid"])

    out = {"n_scored_tier_a_rows_with_history_affected": None, "per_target": {}}
    for t in TARGETS:
        a, b = d14[t], d15[t]
        common = set(a["row_uid"]) & set(b["row_uid"])
        m = a[a["row_uid"].isin(common)][["row_uid", "pred_point", "y", "scoreable"]].merge(
            b[b["row_uid"].isin(common)][["row_uid", "pred_point", "scoreable"]],
            on="row_uid", suffixes=("_14", "_15"))
        m = m[m["scoreable_14"] & m["scoreable_15"]]
        m["aff"] = m["row_uid"].isin(affected)
        y = m["y"].to_numpy(float)
        e14 = m["pred_point_14"].to_numpy(float) - y
        e15 = m["pred_point_15"].to_numpy(float) - y
        l14 = e14 ** 2 if t == "p_active" else np.abs(e14)
        l15 = e15 ** 2 if t == "p_active" else np.abs(e15)
        chg = ~np.isclose(m["pred_point_14"], m["pred_point_15"], atol=1e-12)
        res = {}
        for lab, mask in (("history_affected", m["aff"].to_numpy()),
                          ("unaffected", ~m["aff"].to_numpy())):
            if mask.sum():
                res[lab] = {"n": int(mask.sum()),
                            "v14": float(l14[mask].mean()), "v15": float(l15[mask].mean()),
                            "diff": float((l15 - l14)[mask].mean()),
                            "pct_predictions_changed": round(
                                100.0 * float(chg[mask].mean()), 2)}
        out["per_target"][t] = res
        out["n_scored_tier_a_rows_with_history_affected"] = int(m["aff"].sum())
    out["metric"] = "brier for p_active, MAE otherwise"
    out["note"] = ("attribution, not model selection. Tier B contributed NO target loss but DID "
                   "influence later Tier A history features.")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
