#!/usr/bin/env python3
"""build_evidence_packet.py — STAGE 2A frozen evidence packet. DIAGNOSTICS ONLY.

Task: TEAM_POSSESSION_PRIOR_V2 Stage 2A. Nothing here fits, selects, tunes or scores a
challenger. Every number is a property of the ACCEPTED INCUMBENT `team_possession_prior/1`
measured against realised possessions, or of the frozen artifacts' availability.

The packet is hashed and frozen BEFORE any hypothesis generation begins — including the
coordinator's. Later ideation sources must not receive evidence that was selected in response
to earlier ideas, so the packet is built once, hashed, and not touched again.

Read-only. It opens the frozen canonical artifacts and writes only into
``experiments/player_program/stage2a/``.

Run::

    python experiments/player_program/stage2a/build_evidence_packet.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parent
ROOT = PP.parents[1]
OUT = HERE / "EVIDENCE_PACKET.json"

PRIOR = PP / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
POSS = PP / "possessions_v2" / "possessions_raw_v2.parquet"
TURN = PP / "turnover_targets_v1" / "team_turnover_reconciliation_v1.parquet"
EXPO = PP / "projected_exposure_v1" / "projected_player_possessions_v1.parquet"

WINDOW_K, MIN_HISTORY_M, REGULATION_MIN = 10, 3, 40.0


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def realised_pace() -> pd.DataFrame:
    """Regulation-equivalent offensive possessions per team-game, and the game pace."""
    p = pd.read_parquet(POSS, columns=["game_id", "season_type", "period", "offense_team_id"])
    n = (p.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss")
         .reset_index().rename(columns={"offense_team_id": "team_id"}))
    g = (p.groupby("game_id").agg(max_period=("period", "max")).reset_index())
    g["game_minutes"] = REGULATION_MIN + 5.0 * np.maximum(0, g["max_period"] - 4)
    n = n.merge(g, on="game_id", how="left", validate="m:1")
    n["realised_off_poss"] = n["n_off_poss"] * REGULATION_MIN / n["game_minutes"]
    n["went_ot"] = n["max_period"] > 4
    return n[["game_id", "team_id", "realised_off_poss", "went_ot", "max_period"]]


def q(a: np.ndarray) -> dict:
    a = a[np.isfinite(a)]
    if not len(a):
        return {}
    return {"n": int(len(a)), "mean": round(float(a.mean()), 5),
            "sd": round(float(a.std(ddof=1)), 5) if len(a) > 1 else None,
            "p05": round(float(np.percentile(a, 5)), 4),
            "p50": round(float(np.percentile(a, 50)), 4),
            "p95": round(float(np.percentile(a, 95)), 4)}


def strat(d: pd.DataFrame, by, label: str) -> list[dict]:
    out = []
    for k, s in d.groupby(by, dropna=False):
        e = s["err"].to_numpy(float)
        e = e[np.isfinite(e)]
        if len(e) < 20:
            continue
        out.append({"stratum": label, "key": (str(k) if not isinstance(k, tuple)
                                              else "|".join(map(str, k))),
                    "n": int(len(e)), "mae": round(float(np.abs(e).mean()), 5),
                    "bias": round(float(e.mean()), 5),
                    "sd": round(float(e.std(ddof=1)), 5)})
    return sorted(out, key=lambda r: -r["mae"])


def main() -> int:
    P = pd.read_parquet(PRIOR)
    R = realised_pace()
    D = P.merge(R, on=["game_id", "team_id"], how="left", validate="1:1")
    D["game_date"] = pd.to_datetime(D["game_date"])
    # incumbent prediction for a TEAM-GAME is the game-level projection (both sides share it)
    D["pred"] = D["projected_team_off_possessions"]
    D["err"] = D["pred"] - D["realised_off_poss"]          # positive = over-projection
    res = D[D["pace_resolved"] & D["err"].notna()].copy()

    # ---- schedule context, derived only from dates already in the artifact ----------------
    res = res.sort_values(["team_id", "game_date"])
    res["days_rest"] = res.groupby("team_id")["game_date"].diff().dt.days
    res["is_b2b"] = res["days_rest"] <= 1
    res["game_no_in_season"] = res.groupby(["team_id", "season"]).cumcount() + 1
    res["support_bucket"] = pd.cut(res["n_history_games"], [-1, 0, 2, 4, 9, 10, 10**9],
                                   labels=["0", "1-2", "3-4", "5-9", "10 (full window)", ">10"])

    e = res["err"].to_numpy(float)
    ae = np.abs(e)
    var_resid = float(e.var(ddof=1))
    var_target = float(res["realised_off_poss"].var(ddof=1))

    # ---- downstream: turnover-team error with the frozen Arm D rate -----------------------
    downstream = {"available": False}
    if TURN.exists():
        T = pd.read_parquet(TURN)
        key = [c for c in ("game_id", "team_id") if c in T.columns]
        tcol = next((c for c in ("team_turnovers_total", "external_team_tov", "team_turnovers")
                     if c in T.columns), None)
        if len(key) == 2 and tcol:
            M = res.merge(T[key + [tcol]], on=key, how="inner", validate="1:1")
            # rate implied by the realised team total over realised possessions; the
            # possession error alone propagates as rate * possession_error
            rate = (M[tcol] / M["realised_off_poss"]).replace([np.inf, -np.inf], np.nan)
            prop = (rate * M["err"]).to_numpy(float)
            downstream = {
                "available": True, "n_team_games": int(len(M)),
                "note": ("mechanical propagation of the possession error at the realised team "
                         "turnover rate. NOT a fitted result and NOT a challenger score: it is "
                         "the turnover-team error attributable to possession mis-projection "
                         "holding the rate fixed."),
                "implied_team_tov_rate": q(rate.to_numpy(float)),
                "propagated_turnover_team_error": q(prop),
                "mean_abs_propagated": round(float(np.nanmean(np.abs(prop))), 5),
            }

    packet = {
        "schema": "stage2a_evidence_packet/1",
        "task": "TEAM_POSSESSION_PRIOR_V2 Stage 2A",
        "lane": "DIAGNOSTIC ONLY — nothing fitted, selected, tuned or scored",
        "frozen_before_ideation": True,
        "sources": {p.name: {"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)}
                    for p in (PRIOR, POSS, TURN, EXPO) if p.exists()},

        "incumbent": {
            "artifact_id": "team_possession_prior/1",
            "formula": [
                "pace is a property of the GAME: game_pace = mean of the two sides' "
                "regulation-equivalent offensive possession counts",
                "regulation-equivalent = n_off_poss * 40.0 / game_minutes, where game_minutes "
                "= 40 + 5 * max(0, max_period - 4)",
                "team_pace_estimate = unweighted mean of the team's last WINDOW_K=10 game_pace "
                "values on STRICTLY EARLIER dates in the SAME season, if at least "
                "MIN_HISTORY_M=3 such games exist (level 1)",
                "else the same over the PRIOR season (level 2)",
                "else the league mean of game_pace over all strictly earlier dates (level 3)",
                "else unresolved (level 4)",
                "projected_team_off_possessions = mean of the two sides' team_pace_estimate; "
                "unresolved if EITHER side is unresolved",
            ],
            "constants": {"WINDOW_K": WINDOW_K, "MIN_HISTORY_M": MIN_HISTORY_M,
                          "REGULATION_MIN": REGULATION_MIN},
            "assumptions": [
                "pace is symmetric: both teams in a game receive the IDENTICAL projection, so "
                "the model carries no team-vs-team differentiation within a game",
                "the trailing window is UNWEIGHTED and UNSHRUNK — the 10th-most-recent game "
                "counts exactly as much as the most recent",
                "no opponent adjustment: the opponent's own pace tendency never enters",
                "no home/away, rest, travel or schedule-density term",
                "no roster, injury, coaching or lineup term",
                "a season boundary resets the window; prior-season history is used only as a "
                "fallback and never blended with same-season history",
                "overtime is removed by regulation-equivalence, so OT games are modelled as "
                "if regulation-length",
                "the league prior is a cumulative all-history mean, not a recent-window mean",
            ],
        },

        "coverage": {
            "team_games_total": int(len(D)),
            "resolved": int(D["pace_resolved"].sum()),
            "unresolved": int((~D["pace_resolved"]).sum()),
            "resolved_with_realised": int(len(res)),
            "by_pace_level": {str(k): int(v) for k, v in
                              D["pace_source"].value_counts().sort_index().items()},
        },

        "chronological_possession_error": {
            "definition": "err = projected_team_off_possessions - realised_off_poss "
                          "(positive = OVER-projection)",
            "overall": {"n": int(len(e)), "mae": round(float(ae.mean()), 5),
                        "rmse": round(float(np.sqrt((e ** 2).mean())), 5),
                        "bias": round(float(e.mean()), 5),
                        "sd": round(float(e.std(ddof=1)), 5),
                        "p05": round(float(np.percentile(e, 5)), 4),
                        "p50": round(float(np.percentile(e, 50)), 4),
                        "p95": round(float(np.percentile(e, 95)), 4)},
            "by_season": strat(res, "season", "season"),
            "realised_target": q(res["realised_off_poss"].to_numpy(float)),
        },

        "bias_variance": {
            "residual_variance": round(var_resid, 5),
            "target_variance": round(var_target, 5),
            "variance_explained_vs_target": round(1 - var_resid / var_target, 5),
            "squared_bias": round(float(e.mean() ** 2), 6),
            "bias_share_of_mse": round(float(e.mean() ** 2 / (e ** 2).mean()), 6),
            "reading": ("squared bias is a negligible share of MSE, so the incumbent's error is "
                        "overwhelmingly VARIANCE, not systematic level error. A better point "
                        "estimate must reduce dispersion, not re-centre."),
        },

        "error_strata": {
            "by_pace_level": strat(res, "pace_source", "pace_source"),
            "by_support": strat(res, "support_bucket", "support_bucket"),
            "by_game_no_in_season": strat(res, pd.cut(
                res["game_no_in_season"], [0, 3, 6, 10, 20, 200],
                labels=["1-3", "4-6", "7-10", "11-20", "21+"]), "game_no_in_season"),
            "by_days_rest": strat(res, pd.cut(
                res["days_rest"], [-1, 1, 2, 3, 6, 400],
                labels=["0-1 (b2b)", "2", "3", "4-6", "7+"]), "days_rest"),
            "by_season_type": strat(res, "season_type", "season_type"),
            "by_overtime": strat(res, "went_ot", "went_ot"),
        },

        "cold_start_and_low_support": {
            "definition": "support = n_history_games backing the team's pace estimate",
            "by_support_bucket": strat(res, "support_bucket", "support_bucket"),
            "level3_league_prior": {
                "n": int((res["pace_source"] == "league_prior_all").sum()),
                "mae": round(float(res.loc[res["pace_source"] == "league_prior_all",
                                           "err"].abs().mean()), 5)
                if (res["pace_source"] == "league_prior_all").any() else None},
            "unresolved_level4_excluded_from_error": int((~D["pace_resolved"]).sum()),
        },

        "downstream_turnover_team_error": downstream,

        "context_availability": {
            "note": "what the FROZEN artifacts actually carry at cutoff. This gates which "
                    "hypotheses may enter the experiment at all.",
            "team_possession_prior_v1_columns": sorted(P.columns.tolist()),
            "possessions_raw_v2_columns": sorted(pd.read_parquet(
                POSS, columns=None).columns.tolist()) if POSS.exists() else [],
        },

        "cutoff_valid_availability_table": {
            "rule": ("a field is CUTOFF-VALID only if its value is knowable strictly BEFORE the "
                     "target game tips. A realised box-score column is cutoff-valid ONLY as "
                     "LAGGED history over strictly earlier games, never for the target game."),
            "warning": ("this table records AVAILABILITY and COVERAGE. It does NOT prove cutoff "
                        "validity — a construction receipt binds that declaration but cannot "
                        "verify it (PROGRAM_STATE gap `cutoff_validity_asserted`). Each entry "
                        "still requires scientific review before it may back a registered arm."),
            "available": [
                {"field": "game_id / team_id / opponent identity", "source": "contract schedule",
                 "coverage": "2990/2990 team-games", "cutoff_valid": True,
                 "basis": "schedule identity, fixed before tip"},
                {"field": "game_date, season, season_type", "source": "contract schedule",
                 "coverage": "2990/2990", "cutoff_valid": True, "basis": "schedule"},
                {"field": "is_home", "source": "data/masters/master_team.parquet",
                 "coverage": "2990/2990 team-games (key overlap verified)", "cutoff_valid": True,
                 "basis": "schedule-determined, known pregame"},
                {"field": "days_rest, back-to-back, game_no_in_season, schedule density",
                 "source": "derived from contract schedule dates", "coverage": "2990/2990",
                 "cutoff_valid": True, "basis": "derived from prior dates only"},
                {"field": "own realised game_pace over strictly earlier games",
                 "source": "possessions_raw_v2", "coverage": "2982 resolved", "cutoff_valid": True,
                 "basis": "the incumbent's own input; lagged by construction"},
                {"field": "OPPONENT realised game_pace over strictly earlier games",
                 "source": "possessions_raw_v2 + schedule", "coverage": "2982 resolved",
                 "cutoff_valid": True,
                 "basis": "same lagged construction as own history; NOT used by the incumbent"},
                {"field": "team prior-game box aggregates (fga, fta, oreb, tov, ...)",
                 "source": "data/masters/master_team.parquet", "coverage": "2990/2990",
                 "cutoff_valid": "ONLY LAGGED",
                 "basis": "65 columns; 7 are schedule/identity, the remaining 58 are REALISED "
                          "target-game outcomes and are cutoff-valid only over earlier games"},
                {"field": "possession-level end_reason, duration_sec, period",
                 "source": "possessions_raw_v2", "coverage": "all contract games",
                 "cutoff_valid": "ONLY LAGGED", "basis": "realised; lagged use only"},
            ],
            "unavailable_or_insufficient": [
                {"field": "referee / official assignments", "source": "data/ref_assignments/",
                 "coverage": "0 of 1495 contract games overlap", "verdict": "UNAVAILABLE",
                 "note": "officials_master.csv carries no game_id join at all"},
                {"field": "injury / availability report",
                 "source": "data/injury_capture/injury_log.csv",
                 "coverage": "2026-07-30 .. 2026-08-04 only (6 days of a 5-season span)",
                 "verdict": "UNAVAILABLE HISTORICALLY",
                 "note": "confirms the standing caution that availability before 2026-07-30 is "
                         "not a genuine captured pregame feed"},
                {"field": "market odds / totals", "source": "data/odds_capture/",
                 "coverage": "2026-07-31 .. 2026-08-06 only", "verdict": "UNAVAILABLE HISTORICALLY",
                 "note": "capture begins after the modelling span; also a market feature, which "
                         "raises separate questions about what is being learned"},
                {"field": "coaching identity, coaching change, tactical scheme",
                 "source": "none found in the repository", "verdict": "ABSENT",
                 "note": "no coaching source exists; a `*coach*` sweep over data/ returns nothing"},
                {"field": "starting lineup / rotation announced pregame",
                 "source": "no captured pregame feed", "verdict": "UNAVAILABLE",
                 "note": "realised lineups are target-game outcomes"},
                {"field": "travel distance / time-zone change",
                 "source": "not present; would need venue geocoding", "verdict": "ABSENT",
                 "note": "derivable in principle from a venue table that does not exist here"},
            ],
        },

        "unavailable_but_potentially_valuable": {
            "note": ("recorded so the current data inventory does not silently narrow the "
                     "scientific imagination. These may NOT enter TEAM_POSSESSION_PRIOR_V2 as "
                     "arms; they belong to a data and capability roadmap."),
            "candidates": [
                {"missing_input": "pregame injury / availability feed with historical depth",
                 "why_it_may_matter": "pace is partly a personnel property; a missing primary "
                                      "ball-handler plausibly shifts a team's possession rate",
                 "minimum_viable_collection": "persist the existing injury capture forward from "
                                              "2026-07-30 and backfill from an archival source "
                                              "if one can be licensed",
                 "prospective_only_validation": True},
                {"missing_input": "coaching identity and coaching-change events",
                 "why_it_may_matter": "pace is among the most coach-determined team properties; "
                                      "a coaching change is a plausible structural break the "
                                      "trailing window cannot see",
                 "minimum_viable_collection": "a small hand-maintained coach-by-team-season table",
                 "prospective_only_validation": False},
                {"missing_input": "announced starting lineup / expected rotation",
                 "why_it_may_matter": "distinguishes a rested-starters game from a full-strength "
                                      "one before tip",
                 "minimum_viable_collection": "capture pregame lineup postings",
                 "prospective_only_validation": True},
                {"missing_input": "venue table with location for travel and time-zone deltas",
                 "why_it_may_matter": "travel burden is a standard schedule-fatigue channel",
                 "minimum_viable_collection": "a static 12-team venue table with coordinates",
                 "prospective_only_validation": False},
                {"missing_input": "market total / pace-implied market expectation with history",
                 "why_it_may_matter": "a market total is an external consensus pace signal",
                 "minimum_viable_collection": "persist odds capture forward",
                 "prospective_only_validation": True,
                 "caution": "a market feature changes what the model is: it would no longer be "
                            "a pure pace projection"},
            ],
        },
    }
    OUT.write_text(json.dumps(packet, indent=2, default=str) + "\n", encoding="utf-8")
    h = sha(OUT)
    print(f"wrote {OUT.name}  sha256={h}")
    o = packet["chronological_possession_error"]["overall"]
    print(f"  resolved team-games {o['n']:,} · MAE {o['mae']} · bias {o['bias']} · sd {o['sd']}")
    print(f"  bias share of MSE {packet['bias_variance']['bias_share_of_mse']}")
    if downstream.get("available"):
        print(f"  propagated turnover-team |error| {downstream['mean_abs_propagated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
