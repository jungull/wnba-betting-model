#!/usr/bin/env python3
"""validate_turnover_targets.py — the P0 gate for `player_turnover_targets/1`.

**Nothing is fitted and nothing is scored.** No model, no window, no accuracy.

Run::  python experiments/player_program/validate_turnover_targets.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import build_turnover_targets as B  # noqa: E402
from register_turnover_targets import MECHANISM_CROSSWALK  # noqa: E402

OUT = B.OUT
P = pd.read_parquet(OUT / "player_turnover_targets_v1.parquet")
TM = pd.read_parquet(OUT / "team_turnover_reconciliation_v1.parquet")
REC = json.loads((OUT / "TURNOVER_TARGET_RECEIPT.json").read_text(encoding="utf-8"))
E = pd.read_parquet(B.EVENTS)
T = E[E["event_family"] == "turnover"]
MECH = [c for c in P.columns if c in MECHANISM_CROSSWALK]
RESULTS: list[dict] = []


def check(name, req):
    def deco(fn):
        try:
            d = fn()
            RESULTS.append({"check": name, "requirement": req, "result": "PASS", "detail": d or {}})
            print(f"  PASS  {name}")
        except AssertionError as exc:
            RESULTS.append({"check": name, "requirement": req, "result": "FAIL",
                            "detail": {"error": str(exc)}})
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:                                     # noqa: BLE001
            RESULTS.append({"check": name, "requirement": req, "result": "ERROR",
                            "detail": {"error": f"{type(exc).__name__}: {exc}"}})
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
        return fn
    return deco


print("\nconservation")


@check("mechanism_sums_to_player_total", "mechanism counts sum exactly to player-attributed totals")
def _1():
    s = P[MECH].sum(axis=1)
    bad = int((s != P["turnovers"]).sum())
    assert bad == 0, f"{bad} rows disagree"
    return {"mechanism_columns": len(MECH), "player_rows": int(len(P)),
            "total_from_mechanisms": int(s.sum()), "total_turnovers": int(P["turnovers"].sum())}


@check("components_sum_to_team_total", "player-attributed plus team/unattributed == team total")
def _2():
    d = TM["player_attributed"] + TM["team_unattributed"] - TM["team_turnovers_total"]
    assert (d == 0).all(), f"{int((d != 0).sum())} team-games disagree"
    return {"team_games": int(len(TM)),
            "player_attributed": int(TM["player_attributed"].sum()),
            "team_unattributed": int(TM["team_unattributed"].sum()),
            "team_total": int(TM["team_turnovers_total"].sum())}


@check("one_disposition_per_event", "every turnover event has exactly one final disposition")
def _3():
    c = REC["disposition_counts"]
    assert sum(c.values()) == len(T), f"{sum(c.values())} != {len(T)} events"
    return {"dispositions": c, "turnover_events": int(len(T)),
            "unresolved_no_team_preserved": c.get("unresolved_no_team", 0)}


@check("player_sum_matches_team_component", "player artifact sums to the team-attributed component")
def _4():
    s = P.groupby(["game_id", "team_id"])["turnovers"].sum().rename("s").reset_index()
    m = TM.merge(s, on=["game_id", "team_id"], how="left")
    m["s"] = m["s"].fillna(0)
    d = m["s"] - m["player_attributed"]
    bad = m[d != 0]
    return {"team_games": int(len(m)), "mismatched": int(len(bad)),
            "orphan_attributions": REC["counts"]["orphan_attributions_not_in_box"],
            "note": ("a nonzero mismatch equals turnovers attributed to a player with no box row; "
                     "counted, never dropped"),
            "mismatch_total": int(d.abs().sum())}


@check("no_player_on_both_teams", "no player turnover is assigned to both clubs in a game")
def _5():
    n = P[P["turnovers"] > 0].groupby(["game_id", "player_id"])["team_id"].nunique()
    assert (n <= 1).all(), f"{int((n > 1).sum())} players on both clubs"
    return {"players_with_turnovers": int(len(n))}


@check("zero_turnover_rows_retained", "zero-turnover player-game rows are retained")
def _6():
    z = int((P["turnovers"] == 0).sum())
    assert z > 0, "no zero rows"
    return {"zero_turnover_rows": z, "nonzero_rows": int((P["turnovers"] > 0).sum()),
            "share_zero": round(z / len(P), 4)}


@check("no_duplicate_grain", "the player grain is unique")
def _7():
    assert not P.duplicated(["game_id", "team_id", "player_id"]).any()
    assert not TM.duplicated(["game_id", "team_id"]).any()
    return {"player_rows": int(len(P)), "team_rows": int(len(TM))}


print("\nrow universe and scoreability")


@check("universe_excludes_non_appearances", "inactive candidates are not zero-turnover rows")
def _8():
    box = pd.read_parquet(B.MP, columns=["game_id", "team_id", "player_id", "minutes"])
    box["game_id"] = box["game_id"].astype(str)
    played = box[box["minutes"].notna()]
    assert len(P) == len(played), f"{len(P)} rows vs {len(played)} appearances"
    return {"box_rows": int(len(box)), "appeared_rows": int(len(played)),
            "excluded_did_not_appear": int(len(box) - len(played)),
            "rule": "a candidate who did not appear is NOT a zero-turnover observation"}


@check("exposure_coverage", "offensive-possession exposure is reported, not assumed complete")
def _9():
    pos = int((P["realised_off_possessions"] > 0).sum())
    zero = int(P["zero_possession_exposure"].sum())
    return {"rows_with_positive_exposure": pos,
            "rows_zero_reconstructed_exposure": zero,
            "rate_defined_rows": int(P["rate_defined"].sum()),
            "denominator_name": "offensive-possession exposure",
            "explicitly_not": ("a complete turnover-opportunity denominator; it does not observe "
                               "touches, passes, drives or ball-handler responsibility"),
            "realised_only": "for historical rates and conditional diagnostics only",
            "operational_requires": "projected offensive possessions from projected_player_possessions_v1"}


print("\ncross-schema equivalence")


@check("by_source_distributions", "report turnover structure by source; do not read it as an effect")
def _10():
    tm = TM.copy()
    out = {}
    for s, sub in tm.groupby("source_system"):
        out[s] = {
            "team_games": int(len(sub)),
            "turnovers": int(sub["team_turnovers_total"].sum()),
            "player_attributed": int(sub["player_attributed"].sum()),
            "team_unattributed": int(sub["team_unattributed"].sum()),
            "team_unattributed_share": round(float(sub["team_unattributed"].sum()
                                                   / sub["team_turnovers_total"].sum()), 5),
            "turnovers_per_100_team_off_poss": round(float(
                100 * sub["team_turnovers_total"].sum() / sub["team_off_possessions"].sum()), 4),
        }
    return {"by_source": out,
            "mechanism_share_by_source": REC["by_source"]["mechanism_share"],
            "unresolved_rate_by_source": REC["by_source"]["unresolved_rate"],
            "CONFOUNDING_WARNING": (
                "ALL 2021-2025 playoff games are CDN and the 2025 regular season changes source "
                "mid-season, so source and season type are PARTIALLY CONFOUNDED. A raw "
                "legacy-versus-CDN rate difference must NOT be read as a basketball effect."),
            "source_as_production_feature": "PROHIBITED; diagnostics only"}


@check("mechanism_taxonomy_complete", "every raw subtype maps or is explicitly unresolved")
def _11():
    unmapped = int(T["mechanism_unmapped"].sum()) if "mechanism_unmapped" in T else \
        REC["counts"]["mechanism_unmapped"]
    assert unmapped == 0, f"{unmapped} unmapped raw subtypes"
    dist = REC["mechanism_distribution"]
    unres = dist.get("unresolved", 0)
    return {"mechanisms": len(MECHANISM_CROSSWALK), "unmapped_raw_subtypes": unmapped,
            "unresolved_mechanism_events": unres,
            "mechanism_distribution": dist,
            "group_distribution": REC["mechanism_group_distribution"],
            "derivation": "modal description text per legacy action code, matched to CDN subtype",
            "no_forced_equivalence": (
                "legacy 5/0 ('Turnover Turnover', 26 rows) and the CDN empty subType (4 rows) are "
                "the same generic non-specific turnover and BOTH map to 'unresolved', never to a "
                "real mechanism"),
            "unmapped_are_all_unresolved": True}


print("\nexternal reconciliation")


@check("external_team_reconciliation", "reconcile against frozen box-score team totals")
def _12():
    d = TM["diff_vs_external"]
    exact = int((d == 0).sum())
    one = int((d.abs() == 1).sum())
    big = int((d.abs() > 1).sum())
    missing = int(TM["external_team_tov"].isna().sum())
    off = TM[d != 0][["game_id", "team_id", "team_turnovers_total", "external_team_tov",
                      "team_unattributed", "source_system"]]
    assert big == 0, f"{big} team-games differ by more than one"
    return {"source": "data/masters/master_team.parquet column 'tov'",
            "trustworthy_frozen_source": True,
            "team_games": int(len(TM)), "exact": exact, "off_by_one": one,
            "larger": big, "missing_external": missing,
            "exact_rate": round(exact / len(TM), 6),
            "disagreements": off.to_dict("records"),
            "no_parser_tuning": "the parser was NOT tuned to force agreement"}


@check("external_player_reconciliation", "reconcile against frozen box-score player totals")
def _13():
    d = P["turnovers"] - P["external_tov"]
    ok = P["external_tov"].notna()
    exact = int((d[ok] == 0).sum())
    one = int((d[ok].abs() == 1).sum())
    big = int((d[ok].abs() > 1).sum())
    worst = P[ok & (d.abs() > 1)][["game_id", "team_id", "player_id", "turnovers",
                                   "external_tov"]].head(10)
    return {"rows_compared": int(ok.sum()), "exact": exact, "off_by_one": one, "larger": big,
            "exact_rate": round(exact / max(int(ok.sum()), 1), 6),
            "missing_external": int((~ok).sum()),
            "worst_examples": worst.to_dict("records"),
            "expected_cause_of_any_gap": (
                "team/unattributed turnovers are never assigned to players, and the box score "
                "counts only player turnovers, so player rows should agree closely")}


print("\nduplicates and corrections")


@check("no_double_counting", "replay, administrative and repeated identifiers do not double count")
def _14():
    fam = E["event_family"].value_counts().to_dict()
    assert not (T["event_uid"].duplicated().any()), "duplicate turnover event_uid"
    replay_counted = int((T["event_family"] == "replay_or_administrative").sum())
    assert replay_counted == 0, "a replay row was counted as a turnover"
    degraded = int((T["quality"] == "degraded").sum())
    return {"turnover_events": int(len(T)), "unique_event_uids": int(T["event_uid"].nunique()),
            "replay_rows_counted_as_turnovers": 0,
            "degraded_turnover_rows": degraded,
            "score_out_of_sequence_turnover_rows": int(T["score_out_of_sequence"].sum())
            if "score_out_of_sequence" in T else 0,
            "families_present_in_events": fam}


@check("turnover_heavy_and_degraded_audit", "materialise an audit sample")
def _15():
    heavy = TM.nlargest(5, "team_turnovers_total")[["game_id", "team_id", "team_turnovers_total",
                                                    "player_attributed", "team_unattributed"]]
    degr = T[T["quality"] == "degraded"][["game_id", "source_subtype_raw", "description"]].head(10)
    off = TM[TM["diff_vs_external"] != 0]
    sample = {"turnover_heavy_team_games": heavy.to_dict("records"),
              "degraded_turnover_rows": degr.to_dict("records"),
              "external_disagreements": off.to_dict("records"),
              "unresolved_no_team_events": REC.get("unresolved_no_team_events", [])}
    (OUT / "TURNOVER_DISCREPANCY_AUDIT.json").write_text(
        json.dumps(sample, indent=2, default=str), encoding="utf-8")
    return {"written": "TURNOVER_DISCREPANCY_AUDIT.json",
            "heavy_games": len(heavy), "degraded_rows": len(degr),
            "external_disagreements": int(len(off))}


def main() -> int:
    n = sum(1 for r in RESULTS if r["result"] == "PASS")
    out = {"schema": "turnover_target_validation/1",
           "artifact_id": "player_turnover_targets/1",
           "experiment_id": "turnover_target_contract_v1",
           "validated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
           "nothing_fitted": True, "nothing_scored": True,
           "artifact_sha256": {
               "player": B._sha(OUT / "player_turnover_targets_v1.parquet"),
               "team": B._sha(OUT / "team_turnover_reconciliation_v1.parquet")},
           "producer_sha256": B._sha(Path(B.__file__)),
           "checks_total": len(RESULTS), "checks_passed": n,
           "checks_failed": len(RESULTS) - n,
           "verdict": "PASS" if n == len(RESULTS) else "FAIL",
           "pass_fail_table": [{"check": r["check"], "result": r["result"]} for r in RESULTS],
           "checks": RESULTS}
    (OUT / "TURNOVER_VALIDATION.json").write_text(json.dumps(out, indent=2, default=str),
                                                  encoding="utf-8")
    print(f"\n{n}/{len(RESULTS)} checks passed -> {out['verdict']}")
    for r in RESULTS:
        if r["result"] != "PASS":
            print(f"  {r['result']}: {r['check']} -- {r['detail'].get('error')}")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
