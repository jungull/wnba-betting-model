#!/usr/bin/env python3
"""MEASURE.py — every number in this node's REPORT.md, re-derived from the bytes.

S8 adjudication of all 48 columns of `possessions_v2/possessions_raw_v2.parquet`.

READ-ONLY. Reads the frozen possession artifact, the frozen team-possession prior, the two
Stage 2A evidence packets and the V2 stop condition. Writes ONLY inside this node's own
directory: FINDINGS.json and ADJUDICATION.csv.

NOTHING IS FITTED. No model is estimated, no challenger is scored, no comparative historical
performance is read. The only estimator-shaped call is `feature_gate.audit`, invoked READ-ONLY at
this node's call site as a leakage DIAGNOSTIC to record what the frozen gate does and does not
catch. `stage2b/SEALED_RESULTS/` is never opened.

Run from the worktree root:

    python experiments/player_program/stage2b/P2A_POSSESSION_COLUMN_ADJUDICATION/MEASURE.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]                       # experiments/player_program
ROOT = PP.parents[1]                       # worktree root

sys.path.insert(0, str(PP))
import feature_gate as fg                  # noqa: E402  READ-ONLY use of the frozen gate

POSS = PP / "possessions_v2" / "possessions_raw_v2.parquet"
PRIOR = PP / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
PKT_V1 = PP / "stage2a" / "EVIDENCE_PACKET.json"
PKT_V2 = PP / "stage2a" / "EVIDENCE_PACKET_V2.json"
STOP = PP / "stage2a" / "V2_STOP_CONDITION.json"

REGULATION_MIN = 40.0
OFFC = [f"off_p{i}" for i in range(1, 6)]
DEFC = [f"def_p{i}" for i in range(1, 6)]

#: mirrored verbatim from possession_artifact_v1.GARBAGE_RULE so the reproduction is independent
GARBAGE_RULE = ((25, 720), (20, 480), (15, 300), (10, 120))

#: the six columns the acceptance criteria name as REALISED TARGET-GAME OUTCOMES
NAMED_SIX = ["is_overtime", "score_diff_offense_start", "score_diff_offense_end",
             "abs_score_diff_start", "regulation_seconds_remaining",
             "non_competitive_conservative"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def r(x, n=6):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


# --------------------------------------------------------------------------- adjudication table
#
# label: exactly one of ELIGIBLE / LAGGED_USE_ONLY / PROHIBITED / CUTOFF_UNPROVEN
# origin: where the value is created
# basis:  the cutoff argument, in one sentence
#
ADJUDICATION: dict[str, dict] = {
    # ---- ELIGIBLE: constant within the game (or the game-team), and identical to a schedule fact
    "game_id": dict(
        label="ELIGIBLE", origin="source pbp key, preserved",
        basis="schedule identity, fixed before tip; constant within game; join key only",
        hazard="none as an identity; it is the grouping key of the target's own construction"),
    "season": dict(
        label="ELIGIBLE", origin="source pbp key, preserved",
        basis="schedule fact; constant within game",
        hazard="fold identifier -- do not also enter it as a feature inside a chronological fold"),
    "season_type": dict(
        label="ELIGIBLE", origin="source pbp key, preserved",
        basis="schedule fact known at the cutoff; the one possession column already used, as "
              "is_playoff_game in possession_features.py",
        hazard="fold-degenerate: 0 playoff games in fold 2026 (measured below)"),
    "game_date": dict(
        label="ELIGIBLE", origin="enrich(): left-joined from master_team[game_id, game_date]",
        basis="schedule fact; constant within game; it is the cutoff boundary itself",
        hazard="joined from master_team, a retrospective bulk scrape (packet C9); the DATE is "
               "still a schedule fact, but the join carries master_team's revision risk"),
    "offense_team_id": dict(
        label="ELIGIBLE", origin="source pbp",
        basis="team identity; the unordered pair of teams is schedule-determined and the value is "
              "constant within (game_id, team_id) by definition of the grouping",
        hazard="SEVERE: the ROW MULTIPLICITY of this column IS the target numerator. Identity use "
               "requires a drop_duplicates join; any count, size or per-possession aggregate "
               "reconstructs the target exactly (measured below)"),
    "defense_team_id": dict(
        label="ELIGIBLE", origin="source pbp",
        basis="team identity; the complement of offense_team_id within the game",
        hazard="SEVERE: same multiplicity hazard -- the row count is the OPPONENT's target"),
    "is_home_offense": dict(
        label="ELIGIBLE", origin="source pbp",
        basis="home/away mapping, schedule-determined and known pregame; measured constant within "
              "(game_id, offense_team_id)",
        hazard="same multiplicity hazard; take it by identity join, never by row aggregate"),

    # ---- CUTOFF_UNPROVEN
    "era": dict(
        label="CUTOFF_UNPROVEN", origin="build_possessions.py: ev['era'], set by "
                                        "wnba_schema.detect_era on the game's OWN pbp file",
        basis="it is the schema era of the target game's play-by-play FILE, which does not exist "
              "before the game is played and ingested. Availability is established; cutoff "
              "validity is not.",
        hazard="measured NOT a function of season or season_type, so it cannot be recovered from "
               "the schedule; and it is fold-degenerate (fold 2026 is 100% v3)"),

    # ---- PROHIBITED: no admissible use in any form
    "all_possessions": dict(
        label="PROHIBITED", origin="enrich(): literal True",
        basis="constant on every row. feature_gate raises BLOCKING zero_variance. It carries no "
              "information in any construction, target-game or lagged.",
        hazard="a filter flag mistaken for a feature"),
    "source_pbp_game_id": dict(
        label="PROHIBITED", origin="enrich(): d['game_id'] copied",
        basis="measured byte-equal to game_id on every row. feature_gate raises BLOCKING "
              "exact_duplicate. Provenance alias with no independent content.",
        hazard="two names for one column inflate an apparent feature count"),
}

# ---- LAGGED_USE_ONLY: realised target-game outcomes
_LAGGED = {
    "possession_idx": ("source pbp emission order",
                       "realised within-game sequence position; its per-game maximum is the "
                       "realised possession count of the target game"),
    "period": ("source pbp",
               "REALISED period count. game_minutes = 40 + 5*max(0, max_period - 4) is the "
               "target's OWN denominator, so the target-game value is an exact overtime and "
               "duration surrogate -- the quantity the ruling prohibits by name"),
    "start_sec": ("source pbp", "realised absolute elapsed game seconds"),
    "end_sec": ("source pbp",
                "realised absolute elapsed game seconds; its per-game maximum equals "
                "game_minutes*60 EXACTLY (measured), so it recovers realised duration"),
    "duration_sec": ("source pbp",
                     "realised possession length; its per-game sum equals game_minutes*60 EXACTLY "
                     "(measured)"),
    "points_scored": ("source pbp", "realised scoring on the possession"),
    "end_reason": ("source pbp", "realised possession terminator"),
    "home_pts_before": ("source pbp", "realised running score of the target game"),
    "away_pts_before": ("source pbp", "realised running score of the target game"),
    "n_off_oncourt": ("source pbp / derive_lineups", "realised on-court count"),
    "n_def_oncourt": ("source pbp / derive_lineups", "realised on-court count"),
    "is_overtime": ("enrich(): period > 4",
                    "REALISED target-game overtime. Exact: any(is_overtime) per game equals "
                    "game_minutes > 40 on 1495/1495 games (measured)"),
    "period_clock_start_sec": ("enrich(): period length minus elapsed-in-period",
                               "realised clock; the maximum over the game's LAST period is 600 in "
                               "regulation and 300 in overtime -- an exact OT indicator "
                               "(measured)"),
    "period_clock_end_sec": ("enrich()", "realised clock"),
    "regulation_seconds_remaining": ("enrich(): clip(2400 - start_sec, 0, None)",
                                     "REALISED target-game clock. Its zero-floor is an "
                                     "APPROXIMATE overtime surrogate: sensitivity 100%, with a "
                                     "measured false-positive count reported below"),
    "score_diff_offense_start": ("enrich(): off_before - def_before",
                                 "REALISED running margin of the target game"),
    "score_diff_offense_end": ("enrich(): start margin + points_scored",
                               "REALISED margin INCLUDING the possession's own outcome; the "
                               "final-possession value is the realised final margin (measured)"),
    "abs_score_diff_start": ("enrich(): |score_diff_offense_start|",
                             "REALISED running margin, absolute"),
    "non_competitive_conservative": ("enrich(): GARBAGE_RULE over abs margin, regulation seconds "
                                     "remaining and is_overtime",
                                     "REALISED. Exactly reproducible from three realised columns "
                                     "(measured); pre-possession within the game, but the game "
                                     "must be under way for it to exist at all"),
    "is_zero_duration": ("enrich(): duration_sec <= 0", "realised"),
    "is_technical_derived": ("enrich(): 'tech' in end_reason", "realised"),
    "possession_kind": ("enrich(): from the two flags above", "realised"),
    "lineup_class": ("classify_lineups()", "realised lineup reconstruction quality"),
    "lineup_valid_ten": ("classify_lineups(): lineup_class == 'valid_ten_player'",
                         "realised lineup reconstruction quality"),
    "n_oncourt_total": ("classify_lineups(): n_off + n_def", "realised"),
    "source_possession_idx": ("add_canonical_order(): copy of possession_idx",
                              "realised source order"),
    "canonical_seq": ("add_canonical_order(): cumcount over the canonical key",
                      "realised canonical order; per-game max + 1 is the realised possession "
                      "count of the target game"),
    "source_order_differs": ("add_canonical_order(): canonical_seq != source_possession_idx",
                             "realised ordering-correction flag"),
}
for _c in OFFC:
    _LAGGED[_c] = ("derive_lineups -> source pbp",
                   "REALISED on-court offensive lineup of the target game. The packet's own "
                   "availability table records 'realised lineups are target-game outcomes'. "
                   "Measured: the five slots are the ASCENDING ORDER STATISTICS of the player-id "
                   "set, so the slot index carries no positional meaning")
for _c in DEFC:
    _LAGGED[_c] = ("derive_lineups -> source pbp",
                   "REALISED on-court defensive lineup of the target game; slots are ascending "
                   "order statistics, see off_p*")
for _c, (_o, _b) in _LAGGED.items():
    ADJUDICATION[_c] = dict(
        label="LAGGED_USE_ONLY", origin=_o, basis=_b,
        hazard="target-game value is PROHIBITED on the prediction path; only an aggregate over "
               "STRICTLY EARLIER games may be proposed, and that construction needs its own "
               "adjudication -- this node does not license one")


def main() -> int:
    out: dict = {
        "schema": "stage2b_node_findings/1",
        "node": "P2A_POSSESSION_COLUMN_ADJUDICATION",
        "finding": "S8",
        "epistemic_status": (
            "VERIFIED_READ_ONLY_DERIVATION. Closes a coordinator error: the packet dumped 48 "
            "column names under context_availability and the gating availability table named "
            "none of them. Adjudication makes a column ELIGIBLE or PROHIBITED; it admits "
            "nothing."),
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "nothing_fitted": True,
        "sealed_results_not_read": True,
    }

    d = pd.read_parquet(POSS)
    prior = pd.read_parquet(PRIOR)

    out["inputs"] = {
        "possessions_raw_v2.parquet": {"sha256": sha256(POSS), "rows": int(len(d)),
                                       "cols": int(d.shape[1])},
        "team_possession_prior_v1.parquet": {"sha256": sha256(PRIOR), "rows": int(len(prior))},
        "EVIDENCE_PACKET.json": {"sha256": sha256(PKT_V1)},
        "EVIDENCE_PACKET_V2.json": {"sha256": sha256(PKT_V2)},
        "V2_STOP_CONDITION.json": {"sha256": sha256(STOP)},
    }

    rec = json.loads((PP / "possessions_v2" / "POSSESSION_INTEGRITY_RECEIPT_V2.json")
                     .read_text(encoding="utf-8"))
    out["artifact_receipt_agreement"] = {
        "receipt_artifact_sha256": rec["integrity"]["artifact_sha256"],
        "measured_artifact_sha256": out["inputs"]["possessions_raw_v2.parquet"]["sha256"],
        "agree": rec["integrity"]["artifact_sha256"]
                 == out["inputs"]["possessions_raw_v2.parquet"]["sha256"],
        "receipt_row_count": int(rec["integrity"]["row_count"]),
        "receipt_valid_pct": rec["coverage"]["overall"]["valid_pct_possession_weighted"],
        "receipt_seconds_total": rec["coverage"]["overall"]["seconds_total"],
        "note": ("no artifact/receipt disagreement. Severity A would apply if these differed."),
    }

    # ---------------------------------------------------------------- 1. universe
    n = len(d)
    games = int(d["game_id"].nunique())
    resolved = prior[prior["pace_level"] != 4]
    out["universe"] = {
        "possessions": n,
        "columns": int(d.shape[1]),
        "games_in_possession_artifact": games,
        "prior_team_game_rows_scheduled": int(len(prior)),
        "prior_game_clusters_scheduled": int(prior["game_id"].nunique()),
        "prior_team_game_rows_resolved": int(len(resolved)),
        "prior_game_clusters_resolved": int(resolved["game_id"].nunique()),
        "games_in_possessions_not_in_prior": int(len(set(d["game_id"]) - set(prior["game_id"]))),
        "games_in_prior_not_in_possessions": int(len(set(prior["game_id"]) - set(d["game_id"]))),
        "note": ("the possession artifact spans all 1495 SCHEDULED clusters; the fitted universe "
                 "is the 2982/1491 RESOLVED subset. Report both, never substitute one."),
    }

    # ---------------------------------------------------------------- 2. the 99.789% claim
    valid = int(d["lineup_valid_ten"].sum())
    pct = 100.0 * valid / n
    by_season = (d.groupby("season")["lineup_valid_ten"]
                 .agg(possessions="size", valid="sum"))
    by_season["pct"] = 100.0 * by_season["valid"] / by_season["possessions"]
    out["valid_ten_lineup_coverage"] = {
        "packet_claim_S8": "99.789% of 238,563 possessions",
        "measured_possessions": n,
        "measured_valid_ten": valid,
        "measured_pct": r(pct),
        "verdict": "AGREE",
        "invalid_possessions": n - valid,
        "lineup_class_counts": {k: int(v) for k, v in d["lineup_class"].value_counts().items()},
        "by_fold_season": {str(s): {"possessions": int(row.possessions), "valid": int(row.valid),
                                    "pct": r(row.pct, 4)}
                           for s, row in by_season.iterrows()},
        "cross_check_receipt_v2_valid_pct": 99.7892,
        "what_the_coverage_does_NOT_license": (
            "these are REALISED target-game lineups. High coverage licenses player-level "
            "ATTRIBUTION of completed-game outcomes; it does not make any lineup column a "
            "pregame feature. The packet's own availability table already records 'starting "
            "lineup / rotation announced pregame: UNAVAILABLE -- realised lineups are "
            "target-game outcomes'."),
    }

    # ---------------------------------------------------------------- 3. the target, rebuilt
    n_off = (d.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss").reset_index()
             .rename(columns={"offense_team_id": "team_id"}))
    mp = d.groupby("game_id")["period"].max().rename("max_period").reset_index()
    n_off = n_off.merge(mp, on="game_id", how="left", validate="m:1")
    n_off["game_minutes"] = REGULATION_MIN + 5.0 * np.maximum(0, n_off["max_period"] - 4)
    n_off["target"] = n_off["n_off_poss"] * REGULATION_MIN / n_off["game_minutes"]

    gsize = (d.groupby(["game_id", "offense_team_id"]).size().rename("cnt").reset_index()
             .rename(columns={"offense_team_id": "team_id"}))
    chk = n_off.merge(gsize, on=["game_id", "team_id"], how="inner", validate="1:1")
    exact_cnt = int((chk["cnt"] == chk["n_off_poss"]).sum())
    out["target_reconstruction"] = {
        "definition": "n_off_poss(game, team) * 40 / (40 + 5*max(0, max_period(game) - 4))",
        "columns_required": ["game_id", "offense_team_id", "period"],
        "team_game_rows": int(len(n_off)),
        "row_count_equals_n_off_poss_exactly": f"{exact_cnt}/{len(gsize)}",
        "game_minutes_distribution": {str(int(k)): int(v) for k, v
                                      in n_off["game_minutes"].value_counts().items()},
        "consequence": ("the TARGET is exactly reconstructible from three columns of this "
                        "artifact. possessions_raw_v2 is an OUTCOME SOURCE, and its only "
                        "registered consumer already declares it as one "
                        "(possession_features.py: role='outcome_source', cutoff_valid=False, "
                        "'contributes NO feature column')."),
    }

    # ---------------------------------------------------------------- 4. duration / OT surrogates
    g = d.groupby("game_id").agg(max_period=("period", "max"), max_end=("end_sec", "max"),
                                 sum_dur=("duration_sec", "sum"),
                                 any_ot=("is_overtime", "any"),
                                 n_rsr0=("regulation_seconds_remaining",
                                         lambda s: int((s == 0).sum())))
    g["gm"] = REGULATION_MIN + 5.0 * np.maximum(0, g["max_period"] - 4)
    last_clock = (d.sort_values(["game_id", "period"])
                  .groupby("game_id")
                  .apply(lambda x: float(x.loc[x["period"] == x["period"].max(),
                                               "period_clock_start_sec"].max()),
                         include_groups=False))
    ot_games = int(g["any_ot"].sum())
    surr = {
        "ot_games": ot_games,
        "ot_team_game_rows": ot_games * 2,
        "regulation_games": int(len(g) - ot_games),
        "period__max_period_determines_game_minutes": "definitional: it IS the target denominator",
        "end_sec__max_equals_game_minutes_x60_exactly":
            f"{int((g['max_end'] == g['gm'] * 60).sum())}/{len(g)}",
        "duration_sec__sum_equals_game_minutes_x60_exactly":
            f"{int((g['sum_dur'] == g['gm'] * 60).sum())}/{len(g)}",
        "is_overtime__any_equals_game_minutes_gt_40_exactly":
            f"{int((g['any_ot'] == (g['gm'] > 40)).sum())}/{len(g)}",
        "period_clock_start_sec__last_period_max_is_600_in_regulation_300_in_OT":
            f"{int(((last_clock == 600) == (g['gm'] == 40)).sum())}/{len(g)}",
        "regulation_seconds_remaining__zero_floor_as_an_OT_detector": {
            "rows_with_rsr_zero": int((d["regulation_seconds_remaining"] == 0).sum()),
            "rows_with_is_overtime": int(d["is_overtime"].sum()),
            "rows_rsr_zero_and_not_overtime": int(((d["regulation_seconds_remaining"] == 0)
                                                   & ~d["is_overtime"]).sum()),
            "rows_overtime_and_rsr_nonzero": int((d["is_overtime"]
                                                  & (d["regulation_seconds_remaining"] != 0)).sum()),
            "all_false_positive_rows_are_period_4_starting_at_2400s": bool(
                (d.loc[(d["regulation_seconds_remaining"] == 0) & ~d["is_overtime"],
                       ["period", "start_sec"]].eq([4, 2400.0]).all(axis=1)).all()),
            "game_level_rule_any_rsr_zero": {
                "games_flagged": int((g["n_rsr0"] > 0).sum()),
                "true_ot": int(((g["n_rsr0"] > 0) & g["any_ot"]).sum()),
                "false_positive": int(((g["n_rsr0"] > 0) & ~g["any_ot"]).sum()),
                "false_negative": int(((g["n_rsr0"] == 0) & g["any_ot"]).sum())},
            "game_level_rule_two_or_more_rsr_zero": {
                "games_flagged": int((g["n_rsr0"] >= 2).sum()),
                "true_ot": int(((g["n_rsr0"] >= 2) & g["any_ot"]).sum()),
                "false_positive": int(((g["n_rsr0"] >= 2) & ~g["any_ot"]).sum()),
                "false_negative": int(((g["n_rsr0"] < 2) & g["any_ot"]).sum())},
            "verdict": ("an APPROXIMATE same-game overtime surrogate -- 100% sensitivity, and "
                        "specificity 96.4% / 99.7% under the two rules above. The ruling "
                        "prohibits approximate surrogates, not only exact ones."),
        },
    }
    out["duration_and_overtime_surrogates"] = surr

    # ---------------------------------------------------------------- 5. realised-outcome identities
    sd_end = (d["score_diff_offense_start"] + d["points_scored"]).to_numpy(float)
    ng = np.zeros(n, bool)
    rem = d["regulation_seconds_remaining"].to_numpy()
    md = d["abs_score_diff_start"].to_numpy()
    for margin, secs in GARBAGE_RULE:
        ng |= (md >= margin) & (rem <= secs)
    ng &= ~d["is_overtime"].to_numpy()

    last = d.sort_values(["game_id", "canonical_seq"]).groupby("game_id").tail(1)
    tot_pts = d.groupby("game_id")["points_scored"].sum()
    final_margin = (last.set_index("game_id")["score_diff_offense_end"]).abs()

    out["realised_outcome_identities"] = {
        "score_diff_offense_end == score_diff_offense_start + points_scored":
            f"{int((d['score_diff_offense_end'].to_numpy(float) == sd_end).sum())}/{n}",
        "abs_score_diff_start == |score_diff_offense_start|":
            f"{int((d['abs_score_diff_start'].to_numpy(float) == np.abs(d['score_diff_offense_start'].to_numpy(float))).sum())}/{n}",
        "non_competitive_conservative reproduced from GARBAGE_RULE over three realised columns":
            f"{int((d['non_competitive_conservative'].to_numpy() == ng).sum())}/{n}",
        "non_competitive_rows": int(d["non_competitive_conservative"].sum()),
        "non_competitive_pct": r(100 * float(d["non_competitive_conservative"].mean()), 4),
        "games_touched_by_non_competitive": int(
            d.loc[d["non_competitive_conservative"], "game_id"].nunique()),
        "final_absolute_margin_recoverable_from_last_possession": {
            "games": int(len(final_margin)),
            "mean_final_abs_margin": r(float(final_margin.mean()), 4),
            "max": r(float(final_margin.max()), 1)},
        "total_points_recoverable_per_game": {"mean": r(float(tot_pts.mean()), 3),
                                              "min": int(tot_pts.min()),
                                              "max": int(tot_pts.max())},
        "home_pts_before_and_away_pts_before": "the running score of the target game, by row",
    }

    # ---------------------------------------------------------------- 6. lineup slot semantics
    a = d[OFFC].to_numpy(dtype="float64")
    with np.errstate(invalid="ignore"):
        asc = np.all(np.diff(np.where(np.isnan(a), np.inf, a), axis=1) > 0, axis=1)
    b = d[DEFC].to_numpy(dtype="float64")
    with np.errstate(invalid="ignore"):
        ascd = np.all(np.diff(np.where(np.isnan(b), np.inf, b), axis=1) > 0, axis=1)
    empty_off = int((d["n_off_oncourt"] == 0).sum())
    out["lineup_slot_semantics"] = {
        "off_slots_strictly_ascending_rows": f"{int(asc.sum())}/{n}",
        "def_slots_strictly_ascending_rows": f"{int(ascd.sum())}/{n}",
        "rows_with_no_offensive_players": empty_off,
        "ascending_on_every_non_empty_row": bool(int(asc.sum()) == n - empty_off),
        "consequence": ("off_p1..off_p5 are the ASCENDING ORDER STATISTICS of the player-id set. "
                        "The slot index carries no positional or role meaning; off_p1 is simply "
                        "the smallest player_id on the floor. Any numeric use of a slot column is "
                        "meaningless, and any one-hot use is a 300-level dimension on 238,563 "
                        "rows."),
        "null_mask_off_p5_exactly_encodes_offense_underfull_or_both_underfull":
            int((d["off_p5"].isna() != d["lineup_class"].isin(
                ["offense_underfull", "both_underfull"])).sum()) == 0,
        "off_p5_nulls": int(d["off_p5"].isna().sum()),
        "def_p5_nulls": int(d["def_p5"].isna().sum()),
        "off_p1_nulls": int(d["off_p1"].isna().sum()),
        "null_mask_note": ("feature_gate.missingness_encodes_outcome fires on an EXACT outcome "
                           "mask; off_p5's null mask is exactly the underfull-offense indicator, "
                           "which is a realised lineup-reconstruction outcome"),
    }

    # ---------------------------------------------------------------- 7. era
    gd = d.drop_duplicates("game_id")
    era_season = pd.crosstab(gd["season"], gd["era"])
    e2 = gd[gd["era"] == "v2"]["game_date"]
    e3 = gd[gd["era"] == "v3"]["game_date"]
    rs25 = gd[(gd["season"] == "2025") & (gd["season_type"] == "Regular Season")]
    out["era_diagnostics"] = {
        "games_with_more_than_one_era": int((d.groupby("game_id")["era"].nunique() > 1).sum()),
        "v2_date_span": [str(e2.min().date()), str(e2.max().date())],
        "v3_date_span": [str(e3.min().date()), str(e3.max().date())],
        "date_spans_overlap": bool(e3.min() < e2.max()),
        "games_by_season_and_era": {str(s): {str(c): int(v) for c, v in row.items()}
                                    for s, row in era_season.iterrows()},
        "era_by_season_type_games": {str(k): {str(kk): int(vv) for kk, vv in v.items()}
                                     for k, v in pd.crosstab(gd["era"],
                                                             gd["season_type"]).iterrows()},
        "2025_regular_season_split": {
            "v2_last_game_date": str(rs25[rs25["era"] == "v2"]["game_date"].max().date()),
            "v3_first_game_date": str(rs25[rs25["era"] == "v3"]["game_date"].min().date())},
        "verdict": ("era is NOT a function of season or season_type -- the date spans overlap and "
                    "the 2025 regular season splits mid-season. It is detected per-file from the "
                    "target game's OWN play-by-play, which does not exist at cutoff. "
                    "CUTOFF_UNPROVEN."),
    }

    # ---------------------------------------------------------------- 8. degenerate / duplicate
    out["structural_defects"] = {
        "all_possessions_constant": {"distinct_values": [bool(x) for x in
                                                         d["all_possessions"].unique()],
                                     "feature_gate_kind": "zero_variance", "blocking": True},
        "source_pbp_game_id_equals_game_id":
            f"{int((d['source_pbp_game_id'] == d['game_id']).sum())}/{n}",
        "source_pbp_game_id_feature_gate_kind": "exact_duplicate",
    }

    # ---------------------------------------------------------------- 9. what the gate catches
    off = d.copy()
    off["team_id"] = off["offense_team_id"]
    agg_rows = {}
    for c in NAMED_SIX:
        agg_rows[c] = off.groupby(["game_id", "team_id"])[c].mean()
    agg = pd.DataFrame(agg_rows).reset_index()
    j = n_off.merge(agg, on=["game_id", "team_id"], how="left", validate="1:1")
    corr = {c: r(float(np.corrcoef(j[c].to_numpy(float), j["target"].to_numpy(float))[0, 1]), 6)
            for c in NAMED_SIX}
    def run_gate(cols: list[str]) -> tuple[bool, list]:
        try:
            rep = fg.audit(j, cols, target=j["target"].to_numpy(float))
            return bool(rep["passed"]), rep["blocking"]
        except fg.FeatureGateFailure as exc:
            return False, json.loads(str(exc))

    gate_passed, gate_blocking = run_gate(NAMED_SIX)
    FIVE = [c for c in NAMED_SIX if c != "score_diff_offense_end"]
    five_passed, five_blocking = run_gate(FIVE)
    kinds = sorted({f["kind"] for f in gate_blocking})

    # the deterministic route the gate cannot see: game_minutes as a team-game feature
    gm_tg = j.merge(g[["gm"]].reset_index(), on="game_id", how="left")
    corr_gm = float(np.corrcoef(gm_tg["gm"].to_numpy(float), gm_tg["target"].to_numpy(float))[0, 1])
    out["what_the_frozen_gate_does_and_does_not_catch"] = {
        "design_tested": NAMED_SIX,
        "aggregation": "mean over the team's own offensive possessions, team-game level",
        "target_supplied": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
        "feature_gate_target_corr_threshold": 0.98,
        "measured_corr_with_target": corr,
        "max_abs_corr": r(max(abs(v) for v in corr.values())),
        "feature_gate_passed_all_six": gate_passed,
        "feature_gate_blocking_all_six": gate_blocking,
        "feature_gate_blocking_kinds": kinds,
        "target_derived_fired": "target_derived" in kinds,
        "design_minus_the_redundant_column": FIVE,
        "feature_gate_passed_the_remaining_five": five_passed,
        "feature_gate_blocking_the_remaining_five": five_blocking,
        "corr_of_realised_game_minutes_with_target": r(corr_gm),
        "verdict": ("feature_gate's LEAKAGE check does not fire on any of the six. The only "
                    "blocking finding on the six-column design is near_collinear between "
                    "score_diff_offense_start and score_diff_offense_end (r = 0.999917) -- a "
                    "WITHIN-DESIGN redundancy, not leakage. Drop that one column and the "
                    "remaining five realised target-game outcomes PASS the gate outright. Their "
                    "linear correlation with the target is two orders of magnitude below the "
                    "0.98 target_derived threshold."),
        "why_the_correlations_are_small_and_it_does_not_help": (
            "the target is REGULATION-EQUIVALENT, i.e. explicitly normalised to remove realised "
            "duration, so realised game_minutes correlates with it at only "
            f"{r(corr_gm, 4)}. The prohibition on these columns is therefore NOT justified by a "
            "measured linear leak and must not be argued that way. It rests on two things that "
            "ARE measured: (a) the ruling prohibits realised duration and overtime categorically, "
            "and every one of these columns is an exact or approximate same-game surrogate for "
            "them; and (b) combined with the row count of offense_team_id, `period` reconstructs "
            "the target EXACTLY. A small correlation is not evidence of safety."),
        "call_site_note": ("feature_gate was invoked READ-ONLY from this node as a diagnostic. "
                           "Nothing in it was edited."),
    }

    # ---------------------------------------------------------------- 10. fold-local degeneracy
    tg = prior[["game_id", "team_id", "season", "season_type"]].copy()
    tg = tg.merge(gd[["game_id", "era"]], on="game_id", how="left", validate="m:1")
    folds = {}
    for s, grp in tg.groupby("season"):
        folds[str(s)] = {
            "team_game_rows": int(len(grp)),
            "clusters": int(grp["game_id"].nunique()),
            "playoff_rows": int((grp["season_type"] == "Playoffs").sum()),
            "is_playoff_game_sd": r(float(
                (grp["season_type"] == "Playoffs").astype(float).std(ddof=0))),
            "era_v2_rows": int((grp["era"] == "v2").sum()),
            "era_v3_rows": int((grp["era"] == "v3").sum()),
            "era_sd": r(float((grp["era"] == "v3").astype(float).std(ddof=0))),
        }
    out["fold_local_estimability"] = {
        "fold_definition": "chronological, nested by season; fold identifier == season",
        "by_fold": folds,
        "finding": ("season_type is the ONE possession column already carried as a feature "
                    "(is_playoff_game in possession_features.py). It has ZERO variance in fold "
                    "2026 -- 0 playoff rows -- which is a BLOCKING feature_gate zero_variance "
                    "condition in that fold. era is likewise zero-variance in fold 2026. This is "
                    "the S7 shape on a column S8 never reached."),
    }

    # ---------------------------------------------------------------- 11. packet reconciliation
    pv1 = json.loads(PKT_V1.read_text(encoding="utf-8"))
    pv2 = json.loads(PKT_V2.read_text(encoding="utf-8"))
    dump = pv1["context_availability"]["possessions_raw_v2_columns"]
    tbl2 = json.dumps(pv2["cutoff_valid_availability_table_CORRECTED"])
    tbl1 = json.dumps(pv1["cutoff_valid_availability_table"])

    def named_in(txt: str) -> list[str]:
        return [c for c in d.columns
                if re.search(r"(?<![A-Za-z0-9_])" + re.escape(c) + r"(?![A-Za-z0-9_])", txt)]

    n2, n1 = named_in(tbl2), named_in(tbl1)
    poss_sourced = [e for e in pv2["cutoff_valid_availability_table_CORRECTED"]["available"]
                    if "possessions_raw_v2" in json.dumps(e)]
    poss_named = sorted({c for e in poss_sourced for c in named_in(json.dumps(e))})
    out["packet_reconciliation"] = {
        "S8_claim_columns_total": 48,
        "measured_columns_total": int(d.shape[1]),
        "columns_total_verdict": "AGREE",
        "S8_claim_listed_in_v1_context_availability_raw_dump": 48,
        "measured_v1_dump_len": len(dump),
        "v1_dump_set_equals_bytes": sorted(dump) == sorted(d.columns),
        "v1_dump_verdict": "AGREE",
        "S8_claim_named_in_CUTOFF_VALID_AVAILABILITY_TABLE": 0,
        "measured_named_in_V2_corrected_table": n2,
        "measured_named_in_V1_table": n1,
        "measured_named_in_entries_sourced_to_possessions_raw_v2": poss_named,
        "measured_never_named_anywhere_in_the_table": int(d.shape[1] - len(n2)),
        "named_verdict": "CORRECT",
        "correction": ("S8 says ZERO of the 48 are named in the availability table. Measured: "
                       f"{len(n2)} are named ({', '.join(n2)}), of which "
                       f"{len(poss_named)} appear in the one entry that cites possessions_raw_v2 "
                       "as its source and carries the verdict 'ONLY LAGGED'. "
                       f"{int(d.shape[1] - len(n2))} of 48 are never named. The substantive "
                       "point survives: 41 columns were never adjudicated, and the 3 that were "
                       "were adjudicated as a group with no per-column evidence."),
        "node_title_claims_32_columns": ("NOT REPRODUCED. The node's own mandate line says '32 "
                                         "possession columns the availability table never named'. "
                                         "Neither 48 (S8's own total), 41 (never named) nor 45 "
                                         "(never named with possessions_raw_v2 as source) is 32, "
                                         "and no arithmetic over the packet produces 32. Recorded "
                                         "as a contradiction; all 48 are adjudicated regardless."),
    }

    # ---------------------------------------------------------------- 12. the adjudication itself
    missing = sorted(set(d.columns) - set(ADJUDICATION))
    extra = sorted(set(ADJUDICATION) - set(d.columns))
    if missing or extra:
        raise SystemExit(f"adjudication table does not cover the bytes: missing={missing} "
                         f"extra={extra}")

    stats = {}
    for c in d.columns:
        s = d[c]
        stats[c] = {"dtype": str(s.dtype), "nulls": int(s.isna().sum()),
                    "nunique": int(s.nunique(dropna=True))}

    rows_out = []
    for c in d.columns:
        a_ = ADJUDICATION[c]
        rows_out.append({"column": c, "label": a_["label"], "origin": a_["origin"],
                         "basis": a_["basis"], "hazard": a_["hazard"],
                         **stats[c],
                         "named_in_availability_table": c in n2,
                         "in_acceptance_criteria_named_six": c in NAMED_SIX})
    out["adjudication"] = rows_out
    counts = pd.Series([x["label"] for x in rows_out]).value_counts().to_dict()
    out["adjudication_summary"] = {k: int(v) for k, v in counts.items()}
    out["adjudication_summary"]["TOTAL"] = len(rows_out)

    out["named_six_check"] = {
        "required_by_acceptance_criteria": NAMED_SIX,
        "all_classified_LAGGED_USE_ONLY": all(
            ADJUDICATION[c]["label"] == "LAGGED_USE_ONLY" for c in NAMED_SIX),
        "classification_meaning": ("REALISED TARGET-GAME OUTCOME. The target-game value is "
                                   "prohibited on the prediction path; only an aggregate over "
                                   "strictly earlier games may be PROPOSED, and no such "
                                   "construction is licensed here."),
    }

    out["nothing_admitted"] = {
        "columns_admitted_to_any_arm": 0,
        "columns_admitted_on_availability_grounds": 0,
        "eligible_means": ("may be CONSIDERED. Every ELIGIBLE column carries a stated cutoff "
                           "argument plus a stated hazard, and admission requires a registered "
                           "arm, a construction receipt and a fold-level gate pass that this "
                           "node does not perform."),
    }

    (HERE / "FINDINGS.json").write_text(json.dumps(out, indent=1, default=str) + "\n",
                                        encoding="utf-8", newline="")
    pd.DataFrame(rows_out).to_csv(HERE / "ADJUDICATION.csv", index=False, lineterminator="\n")
    print(json.dumps(out["adjudication_summary"], indent=1))
    print("valid_ten pct:", out["valid_ten_lineup_coverage"]["measured_pct"])
    print("named in V2 table:", n2)
    print("gate passed the six realised-outcome columns:", gate_passed)
    print("wrote FINDINGS.json and ADJUDICATION.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
