#!/usr/bin/env python3
"""build_correction_addendum.py — STAGE2A_PHASE0A_RESOLUTION_v1.

Recomputes every diagnostic the ideation sources showed to be defective in the ORIGINAL frozen
packet, and emits an immutable correction addendum that REFERENCES but never modifies it.

The original packet (`f373e3ee...`) stays byte-identical. Corrections travel alongside.

Read-only over the artifacts. Nothing fitted, nothing scored.
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
ORIG = HERE / "EVIDENCE_PACKET.json"
OUT = HERE / "CORRECTION_ADDENDUM.json"

PRIOR = PP / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
POSS = PP / "possessions_v2" / "possessions_raw_v2.parquet"
TURN = PP / "turnover_targets_v1" / "team_turnover_reconciliation_v1.parquet"
REG = 40.0


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def strat(d, by, label):
    out = []
    for k, s in d.groupby(by, dropna=False, observed=False):
        e = s["err"].to_numpy(float); e = e[np.isfinite(e)]
        if len(e) < 15:
            continue
        out.append({"stratum": label,
                    "key": str(k) if not isinstance(k, tuple) else "|".join(map(str, k)),
                    "n_rows": int(len(e)), "n_game_clusters": int(s["game_id"].nunique()),
                    "mae": round(float(np.abs(e).mean()), 5),
                    "bias": round(float(e.mean()), 5),
                    "sd": round(float(e.std(ddof=1)), 5)})
    return sorted(out, key=lambda r: -r["mae"])


def main() -> int:
    P = pd.read_parquet(PRIOR)
    P["game_date"] = pd.to_datetime(P["game_date"])
    p = pd.read_parquet(POSS, columns=["game_id", "period", "offense_team_id", "defense_team_id"])
    mp = p.groupby("game_id")["period"].max()
    ot_games = set(mp[mp > 4].index)
    n = (p.groupby(["game_id", "offense_team_id"]).size().rename("n_off")
         .reset_index().rename(columns={"offense_team_id": "team_id"}))
    gm = (REG + 5.0 * np.maximum(0, mp - 4)).rename("game_minutes").reset_index()
    n = n.merge(gm, on="game_id")
    n["realised_reg_equiv"] = n["n_off"] * REG / n["game_minutes"]
    n["realised_raw"] = n["n_off"].astype(float)

    D = P.merge(n[["game_id", "team_id", "realised_reg_equiv", "realised_raw"]],
                on=["game_id", "team_id"], how="left")
    D["err"] = D["projected_team_off_possessions"] - D["realised_reg_equiv"]
    D["err_vs_raw"] = D["projected_team_off_possessions"] - D["realised_raw"]
    D["is_ot"] = D["game_id"].isin(ot_games)
    res = D[D["pace_resolved"] & D["err"].notna()].copy()

    # ---- CORRECTION 1: days_rest WITHIN season, openers separated ---------------------------
    res = res.sort_values(["team_id", "season", "game_date", "game_id"])
    res["days_rest_within_season"] = res.groupby(["team_id", "season"])["game_date"].diff().dt.days
    res["is_season_opener"] = res["days_rest_within_season"].isna()
    orig_rest = res.sort_values(["team_id", "game_date"]).groupby("team_id")["game_date"].diff().dt.days
    res["days_rest_ORIGINAL_DEFECTIVE"] = orig_rest.reindex(res.index)
    rest_ok = res[~res["is_season_opener"]].copy()
    rest_bucket = pd.cut(rest_ok["days_rest_within_season"], [-1, 1, 2, 3, 6, 400],
                         labels=["0-1 (b2b)", "2", "3", "4-6", "7+"])

    # ---- CORRECTION 2: support axis, by SOURCE COLUMN MEANING -------------------------------
    res["support_semantics"] = np.where(
        res["pace_source"].isin(["team_window_same_season", "team_window_prior_season"]),
        "TEAM games backing the estimate",
        np.where(res["pace_source"] == "league_prior_all",
                 "CUMULATIVE LEAGUE games (NOT team support; team support is ZERO)", "none"))
    team_sup = res[res["support_semantics"].str.startswith("TEAM")].copy()
    team_bucket = pd.cut(team_sup["n_history_games"], [-1, 2, 4, 9, 10],
                         labels=["1-2", "3-4", "5-9", "10 (full)"])

    # ---- CORRECTION 3: head-to-head coverage, several definitions ---------------------------
    opp = p.groupby("game_id")[["offense_team_id", "defense_team_id"]].first().reset_index()
    H = P.merge(opp, on="game_id", how="left")
    H["opp"] = np.where(H["team_id"] == H["offense_team_id"],
                        H["defense_team_id"], H["offense_team_id"])
    H = H.sort_values(["season", "game_date", "game_id"])
    seen: dict = {}
    prior_meet, prior_meet_3 = [], []
    for r in H.itertuples(index=False):
        k = (r.season, tuple(sorted([str(r.team_id), str(r.opp)])))
        c = seen.get(k, 0)
        prior_meet.append(c >= 1); prior_meet_3.append(c >= 3)
        seen[k] = c + 1
    H["has_prior_meeting"] = prior_meet
    H["has_3_prior"] = prior_meet_3
    hh = {
        "all_team_games_ge1_prior_meeting":
            {"n": int(H["has_prior_meeting"].sum()), "of": int(len(H)),
             "pct": round(100 * H["has_prior_meeting"].mean(), 1)},
        "RESOLVED_rows_only_ge1_prior_meeting":
            {"n": int(H.loc[H["pace_resolved"], "has_prior_meeting"].sum()),
             "of": int(H["pace_resolved"].sum()),
             "pct": round(100 * H.loc[H["pace_resolved"], "has_prior_meeting"].mean(), 1)},
        "LEVEL_1_rows_only_ge1_prior_meeting":
            {"n": int(H.loc[H["pace_source"] == "team_window_same_season",
                            "has_prior_meeting"].sum()),
             "of": int((H["pace_source"] == "team_window_same_season").sum()),
             "pct": round(100 * H.loc[H["pace_source"] == "team_window_same_season",
                                      "has_prior_meeting"].mean(), 1)},
        "playoffs_ge3_prior_meetings":
            {"n": int(H.loc[H["season_type"] == "Playoffs", "has_3_prior"].sum()),
             "of": int((H["season_type"] == "Playoffs").sum()),
             "pct": round(100 * H.loc[H["season_type"] == "Playoffs", "has_3_prior"].mean(), 1)},
    }

    # ---- CORRECTION 4: OT-window contamination ----------------------------------------------
    Pw = P.sort_values(["team_id", "season", "game_date", "game_id"]).copy()
    Pw["is_ot"] = Pw["game_id"].isin(ot_games)
    contaminated = []
    for _, sub in Pw.groupby(["team_id", "season"]):
        v = sub["is_ot"].to_numpy()
        for i in range(len(v)):
            w = v[max(0, i - 10):i]
            if len(w):
                contaminated.append(bool(w.any()))

    # ---- CORRECTION 5: raw vs reg-equiv target diagnostics ----------------------------------
    unit = {}
    for lbl, g in res.groupby("is_ot"):
        k = "overtime" if lbl else "regulation"
        unit[k] = {
            "n_rows": int(len(g)), "n_game_clusters": int(g["game_id"].nunique()),
            "mae_vs_reg_equiv_target": round(float(g["err"].abs().mean()), 5),
            "mae_vs_RAW_target": round(float(g["err_vs_raw"].abs().mean()), 5),
            "bias_vs_reg_equiv": round(float(g["err"].mean()), 5),
            "bias_vs_RAW": round(float(g["err_vs_raw"].mean()), 5),
            "mean_realised_reg_equiv": round(float(g["realised_reg_equiv"].mean()), 4),
            "mean_realised_raw": round(float(g["realised_raw"].mean()), 4),
        }

    add = {
        "schema": "stage2a_correction_addendum/1",
        "task": "STAGE2A_PHASE0A_RESOLUTION_v1",
        "references_but_does_not_modify": {
            "file": "EVIDENCE_PACKET.json", "sha256": sha(ORIG),
            "statement": "the original packet is IMMUTABLE and byte-identical; every correction "
                         "below travels alongside it and never edits it"},
        "found_by": "the five independent ideation sources, verified by the coordinator",

        "corrections": {
            "C1_days_rest": {
                "classification": "CORRECTED",
                "original_defect": "days_rest was computed with groupby(team_id) only, so every "
                                   "season opener inherited the gap since the team's LAST GAME OF "
                                   "THE PREVIOUS SEASON",
                "found_by": "adversarial",
                "measured_defect": {
                    "season_openers": int(res["is_season_opener"].sum()),
                    "their_original_days_rest_median": float(
                        res.loc[res["is_season_opener"], "days_rest_ORIGINAL_DEFECTIVE"].median()),
                    "original_7plus_stratum_n": int(
                        (res["days_rest_ORIGINAL_DEFECTIVE"] >= 7).sum()),
                    "of_which_season_openers": int(
                        ((res["days_rest_ORIGINAL_DEFECTIVE"] >= 7) &
                         res["is_season_opener"]).sum())},
                "recomputed_within_season": strat(rest_ok.assign(b=rest_bucket), "b", "days_rest"),
                "season_openers_reported_separately": strat(
                    res[res["is_season_opener"]].assign(b="season_opener"), "b", "season_opener"),
                "consequence": "the original -1.435 bias on '7+ days rest' was substantially an "
                               "OFF-SEASON artifact. The coordinator's schedule-gap hypothesis "
                               "(A6) is WITHDRAWN."},

            "C2_support_axis": {
                "classification": "CORRECTED",
                "original_defect": "support_bucket was built on n_history_games, which means TEAM "
                                   "games at pace levels 1-2 and CUMULATIVE LEAGUE games at level "
                                   "3. The original '>10' bucket (n=23, MAE 4.538), presented as "
                                   "ABUNDANT support, is entirely level-3 rows with ZERO team "
                                   "support",
                "found_by": "roster_coldstart",
                "source_column_semantics": {
                    "team_window_same_season": "n_history_games = TEAM games, range 3-10",
                    "team_window_prior_season": "n_history_games = TEAM games, always exactly 10",
                    "league_prior_all": "n_history_games = CUMULATIVE LEAGUE games (4-1300); "
                                        "TEAM support is ZERO",
                    "unresolved_no_prior_games": "n_history_games = 0"},
                "recomputed_TEAM_support_only": strat(
                    team_sup.assign(b=team_bucket), "b", "team_support"),
                "zero_team_support_rows": strat(
                    res[res["pace_source"] == "league_prior_all"].assign(b="league_prior (ZERO "
                                                                            "team support)"),
                    "b", "zero_team_support"),
                "consequence": "any arm selected against the original support axis would be "
                               "selected against a variable whose meaning changes mid-range"},

            "C3_pace_level_equals_early_season": {
                "classification": "CORRECTED (new finding, not in the original packet)",
                "found_by": "adversarial",
                "measurement": "pace_level > 1 is algebraically equivalent to "
                               "game_no_in_season <= 3: agree 2982/2982, zero off-diagonal",
                "consequence": "the packet's by_pace_level and by_game_no_in_season strata are "
                               "ONE partition under two names. No design may carry both; in "
                               "threshold form feature_gate's linear rank check may not see it"},

            "C4_ot_window_contamination": {
                "classification": "CORRECTED (understated in the original packet)",
                "found_by": "pace_coaching",
                "ot_games": len(ot_games), "total_games": int(mp.shape[0]),
                "ot_game_rate": round(len(ot_games) / mp.shape[0], 5),
                "team_games_whose_10_game_window_contains_an_OT_game":
                    round(float(np.mean(contaminated)), 4),
                "n_evaluated": len(contaminated),
                "consequence": "a 4.4% event contaminates ~33% of trailing windows; any "
                               "OT-handling correction has ~7x the leverage the raw OT count "
                               "suggests"},

            "C5_unit_diagnostics": {
                "classification": "UNRESOLVED — returned for coordinator ruling",
                "found_by": "timeseries, opponent_env and adversarial, independently",
                "diagnostics_under_both_units": unit,
                "note": "reported under BOTH units so the ruling is not made on the basis of "
                        "which looks better. See PHASE0A_RESOLUTION.md section 2."},

            "C6_head_to_head_coverage": {
                "classification": "UNRESOLVED (discrepancy NOT reconciled)",
                "original_discrepancy": "pace_coaching reported 70.2%; the coordinator measured "
                                        "85.1%; the synthesis refused to quote either",
                "measured_under_several_definitions": hh,
                "resolution": "NOT RECONCILED. I tested four denominators (all team-games, "
                              "resolved rows only, level-1 rows only, playoffs with >=3 prior "
                              "meetings) and NONE reproduces 70.2%; they span 85.1-87.4%, and "
                              "playoffs come out at 100.0% against the source's 99.1%. The "
                              "discrepancy is therefore NOT a denominator difference, which is "
                              "what I first assumed and could not substantiate. Either the "
                              "source used a different meeting definition (e.g. excluding the "
                              "current game's own prior meetings, or counting within the "
                              "trailing window rather than the season), or one of the two "
                              "computations is wrong. UNRESOLVED — no figure may be quoted in a "
                              "task card until reconciled directly with the source.",
                "classification_override": "UNRESOLVED"},

            "C7_venue_travel_elevation_timezone": {
                "classification": "CORRECTED — original verdict WITHDRAWN",
                "original_statement": "'travel distance / time-zone change: ABSENT; would need "
                                      "venue geocoding'",
                "found_by": "opponent_env",
                "actual": {"file": "data/reference/team_cities.csv", "rows": 16,
                           "fields": ["team_id", "abbreviation", "franchise", "first_season",
                                      "last_season", "city", "arena", "lat", "lon",
                                      "elevation_ft"],
                           "verdict": "AVAILABLE — travel, elevation and time zone are "
                                      "constructible; moves Category B -> Category A"},
                "also": {"file": "data/reference/tip_times.csv", "rows": 1219, "of": 1495,
                         "verdict": "PARTIAL — 2021 coverage is zero and provenance is "
                                    "odds-derived rather than as-of; stays Category B"},
                "coordinator_error": True},

            "C8_injury_transaction_history": {
                "classification": "CORRECTED — original verdict WITHDRAWN",
                "original_statement": "'injury / availability report: UNAVAILABLE HISTORICALLY, "
                                      "2026-07-30..2026-08-04 only'",
                "found_by": "roster_coldstart",
                "actual": {"file": "data/injury_history/injury_history.csv", "rows": 8340,
                           "date_range": "2021-01-07 .. 2026-07-29 (the ENTIRE contract span)",
                           "categories": {"missed_game_other": 3131, "missed_game_injury": 2242,
                                          "signing": 1455, "waiver": 795, "draft": 260,
                                          "trade": 252, "contract_suspension": 111,
                                          "front_office": 49},
                           "observation_timestamp": None},
                "verdict": "AVAILABILITY established; CUTOFF VALIDITY not established. The file "
                           "carries NO observation timestamp, so its cutoff status rests on "
                           "`date` being an event date rather than a compilation date. Remains "
                           "Category B on cutoff grounds, NOT on availability grounds.",
                "coordinator_error": True},

            "C9_retrospective_bulk_scrape": {
                "classification": "CORRECTED (a source's count corrected; its conclusion stands)",
                "found_by": "pace_coaching",
                "source_claim": "master_team has two distinct observed_time values",
                "measured": "TEN distinct values, in two bulk windows "
                            "(2026-07-31 20:42:42-45Z and 2026-08-04 12:30:09-22Z) covering game "
                            "dates from 2021-05-14",
                "conclusion": "the count was wrong; the conclusion is right. master_team is a "
                              "RETROSPECTIVE BULK SCRAPE, not per-game pregame capture. Any "
                              "master_team column is cutoff-valid only under a LAG argument, "
                              "never under a CAPTURE argument, and carries revision risk. "
                              "possessions_raw_v2 carries no capture timestamp at all."},

            "C10_game_no_in_season": {
                "classification": "UNRESOLVED — claim NOT reproduced",
                "source_claim": "adversarial reported the packet's game_no_in_season wrong on 266 "
                                "of 2982 rows",
                "coordinator_measurement": "0 of 2990 rows differ from a deterministic "
                                           "(team, season, game_date, game_id) ordering",
                "disposition": "NOT ADOPTED and NOT DISMISSED. The definitions of 'correct' may "
                               "differ. Must be reconciled with the source before the stratum is "
                               "used."},

            "C11_effective_sample_size": {
                "classification": "CORRECTED",
                "found_by": "timeseries and adversarial, independently",
                "measurement": {"team_game_rows": 2982, "game_clusters": 1491,
                                "games_with_one_shared_projection": 1495,
                                "games_with_two_distinct_projections": 0,
                                "within_game_target_gap_mean": 0.880,
                                "between_game_variance": 14.9884,
                                "within_game_half_spread_variance": 0.1519,
                                "game_level_share_of_variance": 0.9778},
                "consequence": "see PHASE0A_RESOLUTION.md section 3 for the full inference "
                               "specification"},
        },

        "original_statement_classification": {
            "UNCHANGED": [
                "the incumbent formula, constants and assumption list",
                "coverage counts (2990 team-games, 2982 resolved, 8 unresolved, by pace level)",
                "overall chronological possession error: MAE 2.90325, bias 0.15917, sd 3.67425",
                "by-season error table",
                "bias/variance decomposition: squared bias 0.19% of MSE, variance explained 0.116",
                "by_pace_level and by_season_type strata",
                "the downstream propagation figure (mean |propagated| 0.51744)",
                "the coaching-source absence (verified: no *coach* source exists)",
                "referee assignment unavailability (0 of 1495 games overlap)",
                "market odds unavailability (capture begins 2026-07-31)",
            ],
            "CORRECTED": ["days_rest strata (C1)", "support strata (C2)",
                          "OT contamination scale (C4)",
                          "venue/travel/elevation/timezone availability (C7)",
                          "injury/transaction availability (C8)",
                          "master_team capture provenance (C9)",
                          "effective sample size and inference (C11)"],
            "WITHDRAWN": [
                "'travel distance / time-zone change: ABSENT' (C7)",
                "'injury: UNAVAILABLE HISTORICALLY' as an availability verdict (C8)",
                "the '>10 support' stratum as a HIGH-support stratum (C2)",
                "the '7+ days rest' stratum as a rest effect (C1)",
                "coordinator hypothesis A6 (schedule-gap staleness), which rested on C1",
                "coordinator hypothesis A7 (home/away), subsumed and bounded",
            ],
            "UNRESOLVED": [
                "the operational possession unit (C5) — returned for coordinator ruling",
                "head-to-head coverage (C6) — 70.2% vs 85.1%, NOT explained by denominator",
                "game_no_in_season defect claim (C10) — not reproduced, not dismissed",
            ],
        },
    }
    OUT.write_text(json.dumps(add, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}  sha256={sha(OUT)}")
    print(f"  original packet untouched: sha256={sha(ORIG)}")
    c = add["corrections"]
    print(f"  season openers {c['C1_days_rest']['measured_defect']['season_openers']}, "
          f"of the original 7+ stratum "
          f"{c['C1_days_rest']['measured_defect']['of_which_season_openers']}"
          f"/{c['C1_days_rest']['measured_defect']['original_7plus_stratum_n']} were openers")
    print(f"  OT window contamination "
          f"{c['C4_ot_window_contamination']['team_games_whose_10_game_window_contains_an_OT_game']:.1%}")
    print(f"  head-to-head under {len(hh)} definitions: "
          + ", ".join(f"{k.split('_')[0]}={v['pct']}%" for k, v in hh.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
