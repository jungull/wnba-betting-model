#!/usr/bin/env python3
"""ws4_run.py -- DISCOVERY workstream ws4_ewma_timescale_family.

Tests a small, basketball-motivated EWMA effective-half-life family against the FROZEN
incumbent alpha=0.10. Development evidence only. Promotes nothing. Registers nothing.

The candidate set, folds, strata, gate threshold and selection rule are frozen in
PREREGISTRATION.json, committed before this script produced any number.

The chronological state machine mirrors run_turnover_p1_universe_fix.py exactly:
one left-to-right pass over game dates; every prediction is read from state that
contains strictly earlier games only; state is advanced from realised rows after
the whole date is predicted.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]                      # experiments/player_program
ROOT = PP.parents[1]                      # repo root
sys.path.insert(0, str(PP))
sys.path.insert(0, str(ROOT))
from evalharness.compare import cluster_bootstrap_ci                          # noqa: E402
from register_turnover_p1 import EB_PRIOR_K, EWMA_ALPHA                       # noqa: E402
from register_turnover_p2 import INVOLVE_ALPHA                                # noqa: E402

OUT = HERE
TGT = PP / "turnover_targets_v1"

# ---- FROZEN family (PREREGISTRATION.json) --------------------------------------- #
A_SLOW, A_INC, A_FAST = 0.05, 0.10, 0.20
assert A_INC == EWMA_ALPHA, "the incumbent alpha must be the registered one"
GATE_ROLE_SHIFT = 0.05          # share of team minutes
GATE_PERSIST_APPEARANCES = 10
TEAM_CHANGE_WINDOW = 5

VARIANTS = ["V0_incumbent_a010", "V1_slow_season_memory", "V3_fast_role_responsive",
            "V4_dual_equal", "V5_dual_precision", "V6_gate_instant", "V7_gate_persist10"]
INCUMBENT = "V0_incumbent_a010"
CHALLENGERS = [v for v in VARIANTS if v != INCUMBENT]

SEED = 20260730
N_BOOT = 2000
FOLD_SEASONS = [2022, 2023, 2024, 2025, 2026]     # 2021 = burn-in, never used for selection
MIN_STRATUM_ROWS = 200                            # below this a stratum is reported, not judged


def half_life(a):
    return float(np.log(0.5) / np.log(1 - a))


def span(a):
    return float(2.0 / a - 1.0)


def _sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _pois_dev(y, mu):
    mu = np.clip(np.asarray(mu, float), 1e-9, None)
    y = np.asarray(y, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(y > 0, y * np.log(np.where(y > 0, y, 1.0) / mu), 0.0)
    return float(2 * np.mean(t - (y - mu)))


# =================================================================================== #
# stage 0 -- leakage receipt for the canonical P2 role feature
# =================================================================================== #
def leakage_receipt(F, O):
    m = F.merge(O[["game_id", "team_id", "player_id", "did_appear"]],
                on=["game_id", "team_id", "player_id"], how="inner")
    ct = pd.crosstab(m["role_change"].notna(), m["did_appear"])
    return {
        "artifact": "experiments/player_program/turnover_p2_v1/turnover_role_context_features_v1.parquet",
        "columns_affected": ["trailing_minutes_share", "trailing_rotation_rank", "role_change",
                             "offensive_involvement_proxy"],
        "defect": ("trailing_minutes_share is built by iterating the REALISED box score "
                   "(data/masters/master_player.parquet filtered to minutes.notna()) and "
                   "left-merged onto the Tier A candidate universe. A candidate who did not "
                   "appear has no box-score row for that game and receives NULL."),
        "consequence": ("role_change.notna() is an EXACT indicator of did_appear. Any operational "
                        "use of role_change (as a gate, a feature, or a stratum) leaks the "
                        "appearance outcome perfectly."),
        "crosstab_role_change_notna_by_did_appear": {
            str(k): {str(kk): int(vv) for kk, vv in v.items()} for k, v in ct.to_dict().items()},
        "off_diagonal": int(ct.to_numpy()[0, 1] + ct.to_numpy()[1, 0]),
        "verified": bool(ct.to_numpy()[0, 1] == 0 and ct.to_numpy()[1, 0] == 0),
        "ws4_response": ("WS4 does NOT use this column. It rebuilds the signal with the identical "
                         "EWMA state machine and constant but reads the state for every candidate "
                         "on the date instead of only for players in that date's box score."),
        "canonical_artifact_modified": False,
        "scope_note": ("this also affects P2 arms F (prior_role) and I (all groups) on the "
                       "operational track. Diagnosing or repairing P2 is OUT OF SCOPE for WS4; "
                       "it is reported here so the defect is on the record."),
    }


# =================================================================================== #
# main
# =================================================================================== #
def main() -> int:
    # ------------------------------- inputs ------------------------------------- #
    P = pd.read_parquet(TGT / "player_turnover_targets_v1.parquet")
    TM = pd.read_parquet(TGT / "team_turnover_reconciliation_v1.parquet")
    C = pd.read_parquet(ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet",
                        columns=["game_id", "game_date", "season"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)
    P = P.merge(C[["game_id", "game_date"]], on="game_id", how="left")
    TM = TM.merge(C[["game_id", "game_date"]], on="game_id", how="left")

    PX = pd.read_parquet(PP / "projected_exposure_v1/projected_player_possessions_v1.parquet",
                         columns=["game_id", "team_id", "player_id", "regime", "season",
                                  "season_type", "projected_minutes", "projected_off_possessions",
                                  "team_game_status"])
    PX = PX[PX["regime"] == "tier_a_only"].drop(columns="regime")
    PX = PX.merge(C[["game_id", "game_date"]], on="game_id", how="left")
    g = PX.groupby(["game_id", "team_id"])["projected_minutes"]
    PX["proj_minutes_share"] = PX["projected_minutes"] / g.transform("sum")

    box = pd.read_parquet(ROOT / "data/masters/master_player.parquet",
                          columns=["game_id", "team_id", "player_id", "minutes"])
    box["game_id"] = box["game_id"].astype(str)
    box = box[box["minutes"].notna()].merge(C[["game_id", "game_date"]], on="game_id", how="left")

    F_p2 = pd.read_parquet(PP / "turnover_p2_v1/turnover_role_context_features_v1.parquet",
                           columns=["game_id", "team_id", "player_id", "role_change"])
    O_p1 = pd.read_parquet(PP / "turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet",
                           columns=["game_id", "team_id", "player_id", "did_appear",
                                    "pred_D_ewma_shrunk", "D_ewma_shrunk"])
    LEAK = leakage_receipt(F_p2, O_p1)

    P = P.sort_values(["game_date", "game_id", "team_id", "player_id"]).reset_index(drop=True)
    fit = P[P["realised_off_possessions"] > 0].copy()
    real = P.set_index(["game_id", "team_id", "player_id"])["turnovers"]
    appeared = set(real.index)
    st_map = dict(zip(P["game_id"], P["season_type"]))
    px_st = dict(zip(PX["game_id"], PX["season_type"]))
    st_map = {**px_st, **st_map}

    fit_by = {d: gg for d, gg in fit.groupby("game_date")}
    px_by = {d: gg for d, gg in PX.groupby("game_date")}
    box_by = {d: gg for d, gg in box.groupby("game_date")}
    dates = sorted(set(fit["game_date"]) | set(PX["game_date"]) | set(box["game_date"]))

    # ------------------------------- state -------------------------------------- #
    lg_x = lg_n = 0.0
    car_n: dict = {}                                   # career realised off possessions
    ew_x = {A_SLOW: {}, A_INC: {}, A_FAST: {}}
    ew_n = {A_SLOW: {}, A_INC: {}, A_FAST: {}}
    ewm_min: dict = {}                                 # role signal: player minutes EWMA
    ewm_tm_min: dict = {}                              # role signal: team minutes EWMA
    last_team: dict = {}                               # most recent PRIOR realised team
    last_team_season: dict = {}
    since_change: dict = {}                            # appearances since most recent team change
    change_was_in_season: dict = {}
    fast_left: dict = {}                               # V7 persistence counter

    intr_rows, oper_rows = [], []

    def _rates(pid, r_lg, trig):
        out = {}
        rs = {}
        for a in (A_SLOW, A_INC, A_FAST):
            x, n = ew_x[a].get(pid, 0.0), ew_n[a].get(pid, 0.0)
            rs[a] = (x + EB_PRIOR_K * r_lg) / (n + EB_PRIOR_K)
        out["V0_incumbent_a010"] = rs[A_INC]
        out["V1_slow_season_memory"] = rs[A_SLOW]
        out["V3_fast_role_responsive"] = rs[A_FAST]
        out["V4_dual_equal"] = 0.5 * rs[A_SLOW] + 0.5 * rs[A_FAST]
        nf = ew_n[A_FAST].get(pid, 0.0)
        ns = ew_n[A_SLOW].get(pid, 0.0)
        rf = nf / (nf + EB_PRIOR_K)
        rsl = ns / (ns + EB_PRIOR_K)
        w = 0.5 if (rf + rsl) <= 0 else rf / (rf + rsl)
        out["V5_dual_precision"] = w * rs[A_FAST] + (1.0 - w) * rs[A_SLOW]
        out["V6_gate_instant"] = rs[A_FAST] if trig else rs[A_SLOW]
        persist = trig or fast_left.get(pid, 0) > 0
        out["V7_gate_persist10"] = rs[A_FAST] if persist else rs[A_SLOW]
        return out, w, persist

    for d in dates:
        r_lg = (lg_x / lg_n) if lg_n > 0 else np.nan
        px_day = px_by.get(d)
        fit_day = fit_by.get(d)

        # role-shift signal read from state strictly prior to this date, for EVERY candidate
        shift_by_key = {}
        if px_day is not None:
            for r in px_day.itertuples(index=False):
                tm = ewm_tm_min.get(r.team_id, 0.0)
                pm = ewm_min.get(r.player_id, 0.0)
                tms = (pm / tm) if tm > 0 else np.nan
                shift_by_key[(r.game_id, r.team_id, r.player_id)] = (
                    (r.proj_minutes_share - tms) if tm > 0 else np.nan)

        if not np.isnan(r_lg):
            # ---- intrinsic universe (realised appearances, realised exposure) ------ #
            if fit_day is not None:
                for r in fit_day.itertuples(index=False):
                    pid, tid = r.player_id, r.team_id
                    sh = shift_by_key.get((r.game_id, tid, pid), np.nan)
                    lt = last_team.get(pid)
                    tc = (lt is not None) and (lt != tid)
                    trig = (not np.isnan(sh) and abs(sh) >= GATE_ROLE_SHIFT) or tc
                    rt, w5, persist = _rates(pid, r_lg, trig)
                    sc = 0 if tc else since_change.get(pid)
                    intr_rows.append({
                        "game_id": r.game_id, "team_id": tid, "player_id": pid, "game_date": d,
                        "season": r.season, "season_type": r.season_type,
                        "turnovers": float(r.turnovers),
                        "exposure": float(r.realised_off_possessions),
                        "prior_off_poss": car_n.get(pid, 0.0),
                        "role_shift_ws4": sh, "team_change": tc,
                        "since_change": (np.nan if sc is None else float(sc)),
                        "change_in_season": (True if (tc and last_team_season.get(pid) == r.season)
                                             else change_was_in_season.get(pid, False) if not tc
                                             else False),
                        "gate_trigger": bool(trig), "gate_persist": bool(persist),
                        "v5_w_fast": w5, **rt})
            # ---- operational universe (all Tier A candidates, projected exposure) --- #
            if px_day is not None:
                for r in px_day.itertuples(index=False):
                    pid, tid = r.player_id, r.team_id
                    k = (r.game_id, tid, pid)
                    sh = shift_by_key.get(k, np.nan)
                    lt = last_team.get(pid)
                    tc = (lt is not None) and (lt != tid)
                    trig = (not np.isnan(sh) and abs(sh) >= GATE_ROLE_SHIFT) or tc
                    rt, w5, persist = _rates(pid, r_lg, trig)
                    sc = 0 if tc else since_change.get(pid)
                    oper_rows.append({
                        "game_id": r.game_id, "team_id": tid, "player_id": pid, "game_date": d,
                        "season": r.season, "season_type": r.season_type,
                        "turnovers": float(real.get(k, 0.0)), "did_appear": k in appeared,
                        "exposure": float(r.projected_off_possessions),
                        "prior_off_poss": car_n.get(pid, 0.0),
                        "role_shift_ws4": sh, "team_change": tc,
                        "since_change": (np.nan if sc is None else float(sc)),
                        "change_in_season": (True if (tc and last_team_season.get(pid) == r.season)
                                             else change_was_in_season.get(pid, False) if not tc
                                             else False),
                        "gate_trigger": bool(trig), "gate_persist": bool(persist),
                        "v5_w_fast": w5, **rt})

        # ---- advance state from REALISED rows only, after the whole date ---------- #
        if fit_day is not None:
            for r in fit_day.itertuples(index=False):
                pid, tid = r.player_id, r.team_id
                x, n = float(r.turnovers), float(r.realised_off_possessions)
                lg_x += x
                lg_n += n
                car_n[pid] = car_n.get(pid, 0.0) + n
                for a in (A_SLOW, A_INC, A_FAST):
                    ew_x[a][pid] = (1 - a) * ew_x[a].get(pid, 0.0) + x
                    ew_n[a][pid] = (1 - a) * ew_n[a].get(pid, 0.0) + n
                # team-change bookkeeping on realised appearances
                lt = last_team.get(pid)
                sh = shift_by_key.get((r.game_id, tid, pid), np.nan)
                tc = (lt is not None) and (lt != tid)
                if tc:
                    since_change[pid] = 0
                    change_was_in_season[pid] = (last_team_season.get(pid) == r.season)
                elif pid in since_change:
                    since_change[pid] += 1
                last_team[pid] = tid
                last_team_season[pid] = r.season
                # V7 persistence counter, advanced only on realised appearances
                trig = (not np.isnan(sh) and abs(sh) >= GATE_ROLE_SHIFT) or tc
                if trig:
                    fast_left[pid] = GATE_PERSIST_APPEARANCES
                elif fast_left.get(pid, 0) > 0:
                    fast_left[pid] -= 1
        # role-signal state advanced from the box score for this date
        bd = box_by.get(d)
        if bd is not None:
            for r in bd.itertuples(index=False):
                ewm_min[r.player_id] = ((1 - INVOLVE_ALPHA) * ewm_min.get(r.player_id, 0.0)
                                        + float(r.minutes or 0))
            for t, sub in bd.groupby("team_id"):
                ewm_tm_min[t] = ((1 - INVOLVE_ALPHA) * ewm_tm_min.get(t, 0.0)
                                 + float(sub["minutes"].sum()))

    I = pd.DataFrame(intr_rows)
    O = pd.DataFrame(oper_rows)
    for df in (I, O):
        for v in VARIANTS:
            df[v] = df[v].clip(0.0, 1.0)
            df[f"pred_{v}"] = df[v] * df["exposure"].astype(float)

    # ---- fidelity check: our alpha=0.10 chain must reproduce the frozen incumbent -- #
    fro = pd.read_parquet(PP / "turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet",
                          columns=["game_id", "team_id", "player_id", "pred_D_ewma_shrunk"])
    chk = I[["game_id", "team_id", "player_id", "pred_V0_incumbent_a010"]].merge(
        fro, on=["game_id", "team_id", "player_id"], how="inner")
    fid_intr = {
        "rows_matched": int(len(chk)),
        "frozen_rows": int(len(fro)), "ws4_rows": int(len(I)),
        "max_abs_diff": float(np.max(np.abs(chk["pred_V0_incumbent_a010"]
                                            - chk["pred_D_ewma_shrunk"]))) if len(chk) else None,
        "bit_identical_1e_12": bool(len(chk) == len(fro) == len(I) and np.allclose(
            chk["pred_V0_incumbent_a010"], chk["pred_D_ewma_shrunk"], rtol=0, atol=1e-12)),
    }
    chk2 = O[["game_id", "team_id", "player_id", "pred_V0_incumbent_a010"]].merge(
        O_p1[["game_id", "team_id", "player_id", "pred_D_ewma_shrunk"]],
        on=["game_id", "team_id", "player_id"], how="inner")
    fid_oper = {
        "rows_matched": int(len(chk2)),
        "frozen_rows": int(len(O_p1)), "ws4_rows": int(len(O)),
        "max_abs_diff": float(np.max(np.abs(chk2["pred_V0_incumbent_a010"]
                                            - chk2["pred_D_ewma_shrunk"]))) if len(chk2) else None,
        "bit_identical_1e_12": bool(len(chk2) == len(O_p1) == len(O) and np.allclose(
            chk2["pred_V0_incumbent_a010"], chk2["pred_D_ewma_shrunk"], rtol=0, atol=1e-12)),
    }

    # =============================== strata ====================================== #
    def add_strata(df):
        sh = df["role_shift_ws4"]
        a = sh.abs()
        recent_tc = df["since_change"].notna() & (df["since_change"] <= TEAM_CHANGE_WINDOW)
        s = {
            "all": pd.Series(True, index=df.index),
            "stable_role": (a < 0.02) & ~recent_tc & (df["prior_off_poss"] >= 500),
            "unstable_role": (a >= 0.05),
            "moderate_shift": (a >= 0.03) & (a < 0.05),
            "shift_up": (sh >= 0.05),
            "shift_down": (sh <= -0.05),
            "post_team_change_5": recent_tc,
            "post_trade_in_season": recent_tc & df["change_in_season"].fillna(False),
            "offseason_team_change": recent_tc & ~df["change_in_season"].fillna(False),
            "cold_start": (df["prior_off_poss"] == 0),
            "rookie_low_history": (df["prior_off_poss"] < 200),
            "established": (df["prior_off_poss"] >= 1000),
            "regular_season": (df["season_type"] == "Regular Season"),
            "playoffs": (df["season_type"] == "Playoffs"),
            "gate_fired": df["gate_trigger"],
            "gate_not_fired": ~df["gate_trigger"],
        }
        for yr in sorted(df["season"].unique()):
            s[f"season_{int(yr)}"] = (df["season"] == yr)
        return {k: v.fillna(False).to_numpy(bool) for k, v in s.items()}

    def paired(df, mask, v, level):
        """delta = |incumbent err| - |challenger err|; positive = challenger better."""
        d = df[mask]
        if level == "player":
            if len(d) < 2:
                return None
            e_i = np.abs(d["turnovers"] - d[f"pred_{INCUMBENT}"]).to_numpy(float)
            e_c = np.abs(d["turnovers"] - d[f"pred_{v}"]).to_numpy(float)
            dv = e_i - e_c
            cl = d["game_id"].to_numpy()
        else:
            gg = d.groupby(["game_id", "team_id"]).agg(
                y=("turnovers", "sum"), i=(f"pred_{INCUMBENT}", "sum"),
                c=(f"pred_{v}", "sum")).reset_index()
            if len(gg) < 2:
                return None
            dv = (np.abs(gg["i"] - gg["y"]) - np.abs(gg["c"] - gg["y"])).to_numpy(float)
            cl = gg["game_id"].to_numpy()
        if len(np.unique(cl)) < 2:
            return None
        ci = cluster_bootstrap_ci(dv, cl, n_boot=N_BOOT, seed=SEED)
        return {"n": int(len(dv)), "mean_improvement": float(dv.mean()),
                "ci90": [ci["low"], ci["high"]], "clusters": ci["n_clusters"],
                "improved": int((dv > 0).sum()), "worsened": int((dv < 0).sum()),
                "tied": int((dv == 0).sum())}

    def level_metrics(df, mask):
        d = df[mask]
        if len(d) == 0:
            return {}
        y = d["turnovers"].to_numpy(float)
        out = {}
        for v in VARIANTS:
            mu = d[f"pred_{v}"].to_numpy(float)
            out[v] = {"n": int(len(d)), "mae": float(np.mean(np.abs(y - mu))),
                      "poisson_deviance": _pois_dev(y, mu),
                      "rmse": float(np.sqrt(np.mean((y - mu) ** 2))),
                      "bias": float(np.mean(mu - y)),
                      "mean_rate": float(d[v].mean())}
        return out

    def fold_deltas(df, mask, v, level):
        out = {}
        for s in FOLD_SEASONS:
            m = mask & (df["season"] == s).to_numpy(bool)
            if m.sum() < 2:
                out[str(s)] = None
                continue
            d = df[m]
            if level == "player":
                dv = (np.abs(d["turnovers"] - d[f"pred_{INCUMBENT}"])
                      - np.abs(d["turnovers"] - d[f"pred_{v}"])).to_numpy(float)
            else:
                gg = d.groupby(["game_id", "team_id"]).agg(
                    y=("turnovers", "sum"), i=(f"pred_{INCUMBENT}", "sum"),
                    c=(f"pred_{v}", "sum")).reset_index()
                if len(gg) < 2:
                    out[str(s)] = None
                    continue
                dv = (np.abs(gg["i"] - gg["y"]) - np.abs(gg["c"] - gg["y"])).to_numpy(float)
            out[str(s)] = {"n": int(len(dv)), "delta": float(dv.mean())}
        return out

    def selection(pooled, folds):
        """The frozen four-condition rule. Returns verdict + which conditions held."""
        if pooled is None:
            return {"declared_superior": False, "reason": "insufficient rows"}
        c1 = pooled["mean_improvement"] > 0
        c2 = pooled["ci90"][0] > 0
        got = [f for f in folds.values() if f is not None]
        pos = sum(1 for f in got if f["delta"] > 0)
        c3 = pos >= 4 and len(got) >= 5
        worst = min((f["delta"] for f in got), default=0.0)
        c4 = worst >= -0.5 * abs(pooled["mean_improvement"])
        return {"C1_pooled_positive": bool(c1), "C2_ci_low_above_zero": bool(c2),
                "C3_positive_in_4_of_5_folds": bool(c3),
                "C4_no_fold_degrades_beyond_half": bool(c4),
                "folds_positive": int(pos), "folds_evaluated": int(len(got)),
                "worst_fold_delta": float(worst),
                "declared_superior": bool(c1 and c2 and c3 and c4)}

    # =============================== evaluate ==================================== #
    results = {}
    for tname, df in (("intrinsic", I), ("operational", O)):
        S = add_strata(df)
        blk = {"rows": int(len(df)), "team_games": int(df.groupby(["game_id", "team_id"]).ngroups),
               "strata_sizes": {k: int(v.sum()) for k, v in S.items()}, "by_stratum": {}}
        for sname, mask in S.items():
            n = int(mask.sum())
            entry = {"n_rows": n,
                     "judged": bool(n >= MIN_STRATUM_ROWS),
                     "player_level": level_metrics(df, mask),
                     "paired_player": {}, "paired_team": {},
                     "folds_player": {}, "selection_player": {}, "selection_team": {}}
            if n == 0:
                blk["by_stratum"][sname] = entry
                continue
            for v in CHALLENGERS:
                pp = paired(df, mask, v, "player")
                pt = paired(df, mask, v, "team")
                fp = fold_deltas(df, mask, v, "player")
                ft = fold_deltas(df, mask, v, "team")
                entry["paired_player"][v] = pp
                entry["paired_team"][v] = pt
                entry["folds_player"][v] = fp
                entry["selection_player"][v] = selection(pp, fp)
                entry["selection_team"][v] = selection(pt, ft)
            blk["by_stratum"][sname] = entry
        results[tname] = blk

    # =============================== stability =================================== #
    stab = {}
    for tname, df in (("intrinsic", I), ("operational", O)):
        d = df.sort_values(["player_id", "game_date"])
        churn = {}
        for v in VARIANTS:
            ch = d.groupby("player_id")[v].diff().abs()
            churn[v] = {"mean_abs_rate_change_between_consecutive_rows": float(ch.mean()),
                        "p95": float(ch.quantile(0.95)),
                        "rate_std_across_rows": float(d[v].std())}
        # per-season pooled team MAE for every variant + rank stability
        per_season = {}
        for s, sub in df.groupby("season"):
            gg = sub.groupby(["game_id", "team_id"]).agg(
                y=("turnovers", "sum"),
                **{v: (f"pred_{v}", "sum") for v in VARIANTS}).reset_index()
            per_season[int(s)] = {v: float(np.mean(np.abs(gg[v] - gg["y"]))) for v in VARIANTS}
        ranks = {int(s): {v: i + 1 for i, (v, _) in enumerate(sorted(m.items(), key=lambda kv: kv[1]))}
                 for s, m in per_season.items()}
        rank_spread = {v: {"best": min(r[v] for r in ranks.values()),
                           "worst": max(r[v] for r in ranks.values()),
                           "mean": float(np.mean([r[v] for r in ranks.values()]))}
                       for v in VARIANTS}
        pl_season = {}
        for s, sub in df.groupby("season"):
            pl_season[int(s)] = {v: float(np.mean(np.abs(sub["turnovers"] - sub[f"pred_{v}"])))
                                 for v in VARIANTS}
        stab[tname] = {"rate_churn": churn, "team_mae_by_season": per_season,
                       "player_mae_by_season": pl_season,
                       "team_mae_rank_by_season": ranks, "rank_spread": rank_spread,
                       "team_mae_season_spread": {
                           v: float(max(m[v] for m in per_season.values())
                                    - min(m[v] for m in per_season.values()))
                           for v in VARIANTS}}

    # =============================== gate diagnostics ============================ #
    gate = {}
    for tname, df in (("intrinsic", I), ("operational", O)):
        gate[tname] = {
            "rows": int(len(df)),
            "role_shift_ws4_non_null": int(df["role_shift_ws4"].notna().sum()),
            "role_shift_ws4_null": int(df["role_shift_ws4"].isna().sum()),
            "trigger_fired": int(df["gate_trigger"].sum()),
            "trigger_fired_pct": float(df["gate_trigger"].mean()),
            "trigger_from_role_shift_only": int(((df["role_shift_ws4"].abs() >= GATE_ROLE_SHIFT)
                                                 & ~df["team_change"]).sum()),
            "trigger_from_team_change_only": int((df["team_change"]
                                                  & ~(df["role_shift_ws4"].abs()
                                                      >= GATE_ROLE_SHIFT)).sum()),
            "persist_active": int(df["gate_persist"].sum()),
            "persist_active_pct": float(df["gate_persist"].mean()),
            "team_changes": int(df["team_change"].sum()),
            "distinct_players_with_team_change": int(df.loc[df["team_change"], "player_id"].nunique()),
            "v5_w_fast": {"mean": float(df["v5_w_fast"].mean()),
                          "min": float(df["v5_w_fast"].min()),
                          "max": float(df["v5_w_fast"].max())},
        }
        if tname == "operational":
            # leakage self-check on the REBUILT signal: it must NOT predict appearance
            ct = pd.crosstab(df["role_shift_ws4"].notna(), df["did_appear"])
            gate[tname]["rebuilt_signal_leakage_self_check"] = {
                "crosstab": {str(k): {str(kk): int(vv) for kk, vv in v.items()}
                             for k, v in ct.to_dict().items()},
                "non_null_among_non_appearers": int(
                    df.loc[~df["did_appear"], "role_shift_ws4"].notna().sum()),
                "is_an_exact_appearance_indicator": bool(
                    ct.shape == (2, 2) and ct.to_numpy()[0, 1] == 0 and ct.to_numpy()[1, 0] == 0),
            }

    # =============================== verdict ===================================== #
    def any_superior(track, strata_list):
        hits = []
        for sname in strata_list:
            e = results[track]["by_stratum"].get(sname)
            if not e or not e["judged"]:
                continue
            for v in CHALLENGERS:
                sp = e["selection_player"].get(v, {})
                if sp.get("declared_superior"):
                    hits.append({"stratum": sname, "variant": v, "level": "player",
                                 "improvement": e["paired_player"][v]["mean_improvement"],
                                 "ci90": e["paired_player"][v]["ci90"]})
                st = e["selection_team"].get(v, {})
                if st.get("declared_superior"):
                    hits.append({"stratum": sname, "variant": v, "level": "team",
                                 "improvement": e["paired_team"][v]["mean_improvement"],
                                 "ci90": e["paired_team"][v]["ci90"]})
        return hits

    all_strata = list(results["operational"]["by_stratum"].keys())
    unstable_strata = ["unstable_role", "shift_up", "shift_down", "post_team_change_5",
                       "post_trade_in_season", "offseason_team_change", "moderate_shift",
                       "gate_fired"]
    verdict = {
        "operational_superior_anywhere": any_superior("operational", all_strata),
        "intrinsic_superior_anywhere": any_superior("intrinsic", all_strata),
        "operational_superior_in_unstable": any_superior("operational", unstable_strata),
        "intrinsic_superior_in_unstable": any_superior("intrinsic", unstable_strata),
    }

    out = {
        "schema": "ws4_ewma_timescale_family_results/1",
        "workstream": "ws4_ewma_timescale_family",
        "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": ("DISCOVERY / development evidence only. Promotes nothing. Registers nothing. "
                   "alpha=0.10 remains the FROZEN registered incumbent regardless of these numbers."),
        "preregistration": {
            "file": "PREREGISTRATION.json",
            "sha256": _sha(HERE / "PREREGISTRATION.json"),
            "committed_before_execution": True,
        },
        "family": {v: ({"alpha": A_INC, "half_life": half_life(A_INC), "span": span(A_INC)}
                       if v == "V0_incumbent_a010" else
                       {"alpha": A_SLOW, "half_life": half_life(A_SLOW), "span": span(A_SLOW)}
                       if v == "V1_slow_season_memory" else
                       {"alpha": A_FAST, "half_life": half_life(A_FAST), "span": span(A_FAST)}
                       if v == "V3_fast_role_responsive" else
                       {"composite_of": [A_SLOW, A_FAST]}) for v in VARIANTS},
        "sign_convention": "INCUMBENT(alpha=0.10) absolute error MINUS CHALLENGER absolute error; POSITIVE = CHALLENGER BETTER",
        "incumbent_fidelity": {"intrinsic": fid_intr, "operational": fid_oper,
                               "meaning": ("the WS4 alpha=0.10 chain must reproduce the frozen "
                                           "D_ewma_shrunk predictions exactly, or the comparison "
                                           "is against a different incumbent")},
        "p2_role_feature_leakage": LEAK,
        "gate_diagnostics": gate,
        "stability": stab,
        "results": results,
        "verdict": verdict,
    }
    (OUT / "WS4_RESULTS.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    I.to_parquet(OUT / "ws4_predictions_intrinsic.parquet", index=False)
    O.to_parquet(OUT / "ws4_predictions_operational.parquet", index=False)

    # ------------------------------- console ------------------------------------- #
    print(f"incumbent fidelity intrinsic={fid_intr['bit_identical_1e_12']} "
          f"operational={fid_oper['bit_identical_1e_12']}")
    for t in ("intrinsic", "operational"):
        e = results[t]["by_stratum"]["all"]
        print(f"\n=== {t} ALL  n={e['n_rows']:,} ===")
        print(f"{'variant':26s} {'plMAE':>8s} {'dev':>9s} {'d_player':>10s} {'ci90':>22s} {'d_team':>9s}")
        for v in VARIANTS:
            m = e["player_level"][v]
            if v == INCUMBENT:
                print(f"{v:26s} {m['mae']:8.5f} {m['poisson_deviance']:9.5f} "
                      f"{'--- incumbent ---':>10s}")
                continue
            pp = e["paired_player"][v]
            pt = e["paired_team"][v]
            print(f"{v:26s} {m['mae']:8.5f} {m['poisson_deviance']:9.5f} "
                  f"{pp['mean_improvement']:+10.5f} "
                  f"[{pp['ci90'][0]:+.5f},{pp['ci90'][1]:+.5f}] {pt['mean_improvement']:+9.5f}")
    print("\nsuperior (operational):", json.dumps(verdict["operational_superior_anywhere"])[:800])
    print("superior (intrinsic):", json.dumps(verdict["intrinsic_superior_anywhere"])[:800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
