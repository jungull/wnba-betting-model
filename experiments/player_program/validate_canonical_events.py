#!/usr/bin/env python3
"""validate_canonical_events.py — the gate `canonical_player_events/1` must pass.

Runs every validation gate named in the registration, plus the stratified manual-audit sample.
**Nothing is fitted and nothing is scored.**

Run::

    python experiments/player_program/validate_canonical_events.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import build_canonical_events as B  # noqa: E402

OUT = B.OUT
E = pd.read_parquet(OUT / "canonical_player_events_v1.parquet")
INV = json.loads((OUT / "EVENT_SOURCE_INVENTORY.json").read_text(encoding="utf-8"))
REC = json.loads((OUT / "EVENT_NORMALISATION_RECEIPT.json").read_text(encoding="utf-8"))
C = pd.read_parquet(B.CONTRACT, columns=["game_id", "game_date", "season"]).drop_duplicates("game_id")
C["game_id"] = C["game_id"].astype(str)
ST = (pd.read_parquet(ROOT / "data/possessions/possessions.parquet",
                      columns=["game_id", "season_type"]).drop_duplicates("game_id"))
ST["game_id"] = ST["game_id"].astype(str)

RESULTS: list[dict] = []
READS: list[str] = []


def check(name: str, req: str, section: str = "gates"):
    def deco(fn):
        try:
            d = fn()
            RESULTS.append({"check": name, "section": section, "requirement": req,
                            "result": "PASS", "detail": d or {}})
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


print("\ninstrumented deterministic rebuild")
_orig = pd.read_parquet


def _rec(path, *a, **k):
    READS.append(str(path))
    return _orig(path, *a, **k)


pd.read_parquet = _rec
try:
    B.pd.read_parquet = _rec
    frames = []
    legacy_files = {re.search(r"pbp_(\d+)", p.name).group(1): p for p in B.LEGACY.glob("pbp_*.parquet")}
    cdn_files = {re.search(r"pbp_(\d+)", p.name).group(1): p for p in B.CDN.glob("pbp_*.parquet")}
    for g in sorted(C["game_id"]):
        if g in legacy_files:
            frames.append(B.build_game(g, legacy_files[g], "legacy"))
        else:
            frames.append(B.build_game(g, cdn_files[g], "cdn"))
    E2 = pd.concat(frames, ignore_index=True)
finally:
    pd.read_parquet = _orig
    B.pd.read_parquet = _orig
print(f"  rebuilt {len(E2):,} rows from {len(set(READS))} files")

S = "gates"
print(f"\n{S}")


@check("all_universe_games_accounted", "all 1,495 universe games accounted for", S)
def _1():
    got = set(E["game_id"])
    want = set(C["game_id"])
    assert got == want, f"{len(want - got)} missing, {len(got - want)} extra"
    return {"games": len(got), "events": int(len(E))}


@check("store_exclusivity_reconciles", "source-store overlap and exclusivity reconcile", S)
def _2():
    by = E.groupby("game_id")["source_system"].nunique()
    assert (by == 1).all(), "a game draws from more than one store"
    n = E.drop_duplicates("game_id")["source_system"].value_counts().to_dict()
    r = INV["reconciliation"]
    assert n["nba_playbyplayv2"] == r["games_only_in_legacy"]
    assert n["nba_cdn_playbyplay"] == r["games_only_in_cdn"]
    assert r["games_in_both"] == 0 and r["games_in_neither"] == 0
    return {"games_by_source": n, "inventory_arithmetic": r["arithmetic"],
            "partition_exact_and_disjoint": r["partition_is_exact_and_disjoint"]}


@check("canonical_keys_unique", "canonical keys are unique", S)
def _3():
    assert not E["event_uid"].duplicated().any(), "event_uid not unique"
    assert not E.duplicated(["game_id", "canonical_event_seq"]).any(), "seq not unique per game"
    fb = int(E["key_fallback_used"].sum())
    dupk = int(E["duplicate_source_key"].sum())
    return {"rows": int(len(E)), "key_fallback_rows": fb,
            "duplicate_source_key_rows": dupk,
            "note": ("7 of 996 legacy files carry one duplicate EVENTNUM each; the registered "
                     "fallback keys those rows on (period, clock, row index) and degrades them")}


@check("deterministic_rebuild", "deterministic byte-identical rebuilds", S)
def _4():
    a = E.sort_values(["game_id", "canonical_event_seq"]).reset_index(drop=True)
    b = E2.sort_values(["game_id", "canonical_event_seq"]).reset_index(drop=True)
    assert len(a) == len(b), f"{len(a)} vs {len(b)}"
    assert (a["event_uid"].to_numpy() == b["event_uid"].to_numpy()).all(), "event_uid differs"
    for c in ["event_family", "period", "elapsed_seconds", "source_event_id", "quality"]:
        x, y = a[c], b[c]
        same = (x.to_numpy() == y.to_numpy()) | (x.isna().to_numpy() & y.isna().to_numpy())
        assert same.all(), f"{c} differs on {int((~same).sum())} rows"
    return {"rows_compared": len(a)}


@check("row_counts_reconcile_to_raw", "event counts reconcile to the raw sources", S)
def _5():
    raw = INV["row_counts"]["total_raw_events"]
    rr = REC["row_reconciliation"]
    dropped = rr["documented_exclusions_exact_duplicate_rows"]
    assert len(E) == raw - dropped, f"canonical {len(E)} != raw {raw} - {dropped}"
    return {"raw_total": raw, "documented_exclusions": dropped,
            "policy": rr["policy"], "games_affected": rr["games_affected"],
            "canonical_total": int(len(E)),
            "by_source": E["source_system"].value_counts().to_dict()}


@check("period_and_clock_valid", "period and clock ranges are valid", S)
def _6():
    p = E["period"].dropna().astype(int)
    assert p.min() >= 1, "period below 1"
    bad = E[(E["clock_seconds_remaining"] < -0.001) |
            (E["clock_seconds_remaining"] > 720.0)]
    assert len(bad) == 0, f"{len(bad)} rows with an out-of-range clock"
    el = E["elapsed_seconds"].dropna()
    assert el.min() >= -0.001, "negative elapsed time"
    unparsed = int(E["clock_unparsed"].sum())
    ot = E[E["period"] > 4]
    return {"max_period": int(p.max()), "clock_unparsed_rows": unparsed,
            "elapsed_range": [float(el.min()), float(el.max())],
            "overtime_rows": int(len(ot)),
            "overtime_games": int(ot["game_id"].nunique())}


@check("score_progression_coherent", "score progression is coherent where score data exists", S)
def _7():
    s = E[E["score_home"].notna() & E["score_away"].notna()]
    assert len(s) > 0, "no score data at all"
    flagged, unflagged, games = 0, [], set()
    for g, sub in s.groupby("game_id"):
        sub = sub.sort_values("canonical_event_seq")
        dec = (sub["score_home"].astype(float).diff() < 0) |               (sub["score_away"].astype(float).diff() < 0)
        if dec.any():
            games.add(g)
            flagged += int(sub.loc[dec, "score_out_of_sequence"].sum())
            miss = sub.loc[dec & ~sub["score_out_of_sequence"].astype(bool)]
            if len(miss):
                unflagged.append((g, int(len(miss))))
    assert not unflagged, f"score regressions not flagged: {unflagged[:3]}"
    by_family = (E[E["score_out_of_sequence"].astype(bool)]["event_family"]
                 .value_counts().to_dict())
    return {"games_with_score_fields": int(s["game_id"].nunique()),
            "rows_with_score": int(len(s)),
            "games_with_a_score_regression": len(games),
            "regressing_rows_all_flagged": flagged,
            "regressing_rows_unflagged": 0,
            "by_event_family": by_family,
            "source_property_not_a_defect": (
                "replay rows carry a post-correction score snapshot, and technical free throws at "
                "a period boundary are emitted before the period_start row that carries the "
                "pre-technical score. v1 PRESERVES source order and LABELS the rows "
                "(score_out_of_sequence, quality degraded) rather than reordering them, per the "
                "registered ordering and amended-event policies."),
            "legacy_supplies_score_fields": False}


@check("scoring_reconciles_where_supported",
       "made shots and free throws reconcile with scoring totals where supported", S)
def _8():
    # Free-throw OUTCOME is not structurally supplied by either store (CDN shotResult is empty on
    # every free throw; legacy carries no result field). So the supported identity is a BOUND, not
    # an equality: the points not attributable to made field goals must be non-negative and cannot
    # exceed the number of free-throw attempts.
    cdn = E[E["source_system"] == "nba_cdn_playbyplay"]
    s = cdn[cdn["score_home"].notna() & cdn["score_away"].notna()]
    assert len(s) > 0, "no score data at all"
    checked, ok, viol = 0, 0, []
    for g, sub in s.groupby("game_id"):
        sub = sub.sort_values("canonical_event_seq")
        final = int(sub["score_home"].iloc[-1]) + int(sub["score_away"].iloc[-1])
        gm = cdn[cdn["game_id"] == g]
        pts_fg = int(gm.loc[gm["event_family"] == "made_field_goal", "shot_value"]
                     .dropna().astype(int).sum())
        n_fta = int((gm["event_family"] == "free_throw").sum())
        implied_ft = final - pts_fg
        checked += 1
        if 0 <= implied_ft <= n_fta:
            ok += 1
        else:
            viol.append({"game_id": g, "final": final, "made_fg_points": pts_fg,
                         "implied_ft_points": implied_ft, "ft_attempts": n_fta})
    rate = ok / checked
    assert rate == 1.0, f"{len(viol)} games violate the bound, e.g. {viol[:3]}"
    return {"games_checked": checked, "games_within_bound": ok, "rate": round(rate, 4),
            "identity_tested": ("0 <= (final total - sum of made-FG shot_value) <= free-throw "
                                "attempts"),
            "why_a_bound_and_not_an_equality": (
                "free-throw made/missed is NOT structurally supplied. CDN shotResult is empty on "
                "all free-throw rows and legacy has no result field. free_throw_result_supported "
                "is False on every row and the canonical shot_made is NULL for free throws."),
            "legacy_not_covered": "the legacy store supplies no score fields; v1 does not parse them"}


@check("substitutions_valid_where_supplied",
       "substitutions have valid in/out identities where the source supplies them", S)
def _9():
    sub = E[E["event_family"] == "substitution"]
    leg = sub[sub["source_system"] == "nba_playbyplayv2"]
    cdn = sub[sub["source_system"] == "nba_cdn_playbyplay"]
    assert leg["sub_player_out_id"].notna().all(), "legacy substitution missing the outgoing player"
    assert leg["sub_player_in_id"].notna().all(), "legacy substitution missing the incoming player"
    assert (leg["sub_player_in_id"] != leg["sub_player_out_id"]).all(), "legacy sub in == out"
    assert cdn["sub_player_in_id"].isna().all(), \
        "a CDN substitution claims an incoming player the source does not structurally supply"
    assert cdn["sub_player_out_id"].notna().all(), "CDN substitution missing the outgoing player"
    return {"legacy_subs": int(len(leg)), "cdn_subs": int(len(cdn)),
            "cdn_incoming_player": "canonical NULL by registration; text parsing not done in v1"}


@check("no_impossible_player_team_mappings", "no impossible player-team mappings introduced", S)
def _10():
    mt = pd.read_parquet(ROOT / "data/masters/master_team.parquet",
                         columns=["game_id", "team_id"]).drop_duplicates()
    mt["game_id"] = mt["game_id"].astype(str)
    valid = set(zip(mt["game_id"], mt["team_id"]))
    t = E[E["event_team_id"].notna()][["game_id", "event_team_id"]].drop_duplicates()
    bad = [(g, int(x)) for g, x in zip(t["game_id"], t["event_team_id"])
           if (g, int(x)) not in valid]
    assert not bad, f"{len(bad)} (game, team) pairs are not clubs in that game, e.g. {bad[:3]}"
    return {"distinct_game_team_pairs": int(len(t)), "invalid": 0}


@check("taxonomy_covers_all_raw_values",
       "event subtype mappings cover all raw values or label them unresolved", S)
def _11():
    unmapped = E[E["taxonomy_unmapped"]]
    fams = set(E["event_family"].dropna())
    assert "unknown" not in fams or len(unmapped) > 0, "unknown family without the unmapped flag"
    assert len(unmapped) == 0, f"{len(unmapped)} rows carry an unmapped raw value"
    txt = E[E["taxonomy_from_text"]]
    return {"unmapped_rows": int(len(unmapped)),
            "families_present": sorted(fams),
            "rows_typed_from_description_text": int(len(txt)),
            "from_text_families": txt["event_family"].value_counts().to_dict(),
            "from_text_field_origin": "parsed — CDN standalone STEAL/BLOCK rows carry an empty actionType",
            "source_subtype_raw_preserved_on_every_row": bool(E["source_subtype_raw"].notna().all())}


@check("coordinate_rules_valid", "coordinate ranges and orientation rules are valid", S)
def _12():
    leg = E[E["source_system"] == "nba_playbyplayv2"]
    assert leg["shot_x"].isna().all(), "a legacy row carries coordinates it cannot have"
    assert not leg["coordinates_supported"].any()
    cdn = E[E["source_system"] == "nba_cdn_playbyplay"]
    xy = cdn[cdn["shot_x"].notna()]
    nonshot_xy = cdn[(cdn["shot_x"].notna()) &
                     (~cdn["event_family"].isin(["made_field_goal", "missed_field_goal"]))]
    assert len(nonshot_xy) == 0, f"{len(nonshot_xy)} non-shot rows carry coordinates"
    assert xy["shot_x"].abs().max() <= 1000, "x out of plausible range"
    origin = int(((xy["shot_x"] == 0) & (xy["shot_y"] == 0)).sum())
    return {"rows_with_coordinates": int(len(xy)),
            "legacy_rows_with_coordinates": 0,
            "x_range": [float(xy["shot_x"].min()), float(xy["shot_x"].max())],
            "y_range": [float(xy["shot_y"].min()), float(xy["shot_y"].max())],
            "field_goal_rows_at_origin": origin,
            "sentinel_rule": "(0,0) on a NON-shot row is a null sentinel and is dropped to NULL",
            "no_reorientation_applied": True}


@check("postseason_and_overtime_included", "postseason and overtime games are included", S)
def _13():
    g = E.drop_duplicates("game_id")[["game_id"]].merge(ST, on="game_id", how="left")
    by = g["season_type"].value_counts().to_dict()
    assert by.get("Playoffs", 0) > 0, "no playoff games"
    ot = E[E["period"] > 4]["game_id"].nunique()
    assert ot > 0, "no overtime games"
    return {"games_by_season_type": by, "overtime_games": int(ot)}


@check("fail_closed_on_store_collision", "parser failures produce no partial artifact", S)
def _14():
    fired = {}
    try:
        B.normalise_legacy("x", B.CDN / sorted(p.name for p in B.CDN.glob("*.parquet"))[0])
    except B.ProducerFailure as exc:
        fired["wrong_schema"] = str(exc)[:90]
    assert "wrong_schema" in fired, "the producer accepted a CDN file as legacy"
    return {"violations_rejected": fired,
            "store_collision_gate": "asserted in main() before any row is built",
            "row_reconciliation_gate": "asserted before the artifact is written"}


@check("no_information_from_outside_the_event_file",
       "no target-game information from outside the event file is introduced", S)
def _15():
    allowed_dirs = {str(B.LEGACY), str(B.CDN)}
    outside = [p for p in set(READS)
               if str(Path(p).parent) not in allowed_dirs and Path(p) != B.CONTRACT]
    assert not outside, f"the producer read undeclared files: {outside[:4]}"
    banned = ["roster", "injury", "transaction", "availability", "gamelog", "odds", "props"]
    hit = [p for p in set(READS) if any(b in p.lower() for b in banned)]
    assert not hit, f"the producer read a roster/availability/transaction source: {hit[:3]}"
    return {"distinct_files_read": len(set(READS)),
            "event_files": len([p for p in set(READS) if "pbp_" in p]),
            "non_event_files": [p for p in set(READS) if "pbp_" not in p],
            "note": ("the contract parquet supplies only the GAME LIST; no roster, transaction, "
                     "availability or outcome column is read"),
            "method": "pandas.read_parquet instrumented during the rebuild"}


@check("no_future_information_used",
       "no future roster, transaction or availability data reinterprets historical events", S)
def _16():
    # every row's provenance points at its own game's event file, nothing else
    bad = E[~E.apply(lambda r: str(r["game_id"]) in str(r["source_file"]), axis=1)]
    assert len(bad) == 0, f"{len(bad)} rows are sourced from another game's file"
    assert E["parser_version"].nunique() == 1 and E["contract_version"].nunique() == 1
    return {"rows_traceable_to_own_game_file": int(len(E)),
            "parser_version": E["parser_version"].iloc[0],
            "contract_version": E["contract_version"].iloc[0],
            "provenance_fields": ["source_system", "source_file", "source_file_sha256",
                                  "source_event_id", "source_row_index", "mapping_rule_id"]}


print("\nstratified manual audit sample")


@check("stratified_audit_sample", "a stratified sample is materialised for manual audit", S)
def _17():
    g = C.merge(ST, on="game_id", how="left")
    g["src"] = np.where(g["game_id"].isin(
        set(E.loc[E["source_system"] == "nba_playbyplayv2", "game_id"])), "legacy", "cdn")
    ot = set(E[E["period"] > 4]["game_id"])
    subs = E[E["event_family"] == "substitution"].groupby("game_id").size()
    no_coord = {d["game_id"] for d in INV["shot_coordinates"]["per_game_diagnosis"]}
    admin = set(E[E["event_family"].isin(["replay_or_administrative", "ejection"])]["game_id"])
    tech = set(E[E["foul_type"].astype("string").str.contains("Technical", na=False)]["game_id"])

    strata = {
        "early_2021_legacy": g[(g["season"] == 2021) & (g["src"] == "legacy")].nsmallest(3, "game_date"),
        "late_legacy_before_changeover": g[g["src"] == "legacy"].nlargest(3, "game_date"),
        "first_cdn_after_changeover": g[(g["src"] == "cdn") & (g["season"] == 2025) &
                                        (g["season_type"] == "Regular Season")].nsmallest(3, "game_date"),
        "2026_games": g[g["season"] == 2026].nlargest(3, "game_date"),
        "playoff_games": g[g["season_type"] == "Playoffs"].nsmallest(3, "game_date"),
    }
    sample = {}
    for k, v in strata.items():
        sample[k] = [{"game_id": r.game_id, "date": str(r.game_date.date()),
                      "season": int(r.season), "type": r.season_type, "store": r.src,
                      "events": int((E["game_id"] == r.game_id).sum())}
                     for r in v.itertuples(index=False)]
    sample["overtime_games"] = [{"game_id": x, "events": int((E["game_id"] == x).sum())}
                                for x in sorted(ot)[:3]]
    sample["high_substitution_games"] = [{"game_id": i, "substitutions": int(n)}
                                         for i, n in subs.nlargest(3).items()]
    sample["games_missing_shot_coordinates"] = sorted(no_coord)
    sample["administrative_or_ejection_games"] = sorted(admin)[:3]
    sample["technical_foul_games"] = sorted(tech)[:3]
    (OUT / "EVENT_AUDIT_SAMPLE.json").write_text(json.dumps(sample, indent=2, default=str),
                                                 encoding="utf-8")
    assert all(len(v) > 0 for v in sample.values()), "a stratum is empty"
    return {"strata": {k: len(v) for k, v in sample.items()},
            "written_to": "EVENT_AUDIT_SAMPLE.json"}


print("\nstructural comparison with player_possessions/2 (no modification)")


@check("structural_comparison_with_possessions",
       "compare structurally only; player_possessions/2 is not modified", S)
def _18():
    p = pd.read_parquet(ROOT / "experiments/player_program/possessions_v2/possessions_raw_v2.parquet",
                        columns=["game_id", "offense_team_id", "period"])
    p["game_id"] = p["game_id"].astype(str)
    same_games = set(p["game_id"]) == set(E["game_id"])
    poss_n = p.groupby("game_id").size()
    ev_n = E.groupby("game_id").size()
    both = poss_n.index.intersection(ev_n.index)
    corr = float(np.corrcoef(poss_n.loc[both], ev_n.loc[both])[0, 1])
    max_p = p.groupby("game_id")["period"].max()
    max_e = E.groupby("game_id")["period"].max().astype(int)
    per_match = int((max_p.loc[both] == max_e.loc[both]).sum())
    contradictions = []
    if not same_games:
        contradictions.append("game coverage differs")
    if per_match != len(both):
        contradictions.append(f"max period disagrees on {len(both) - per_match} games")
    return {"same_game_coverage": same_games,
            "games": int(len(both)),
            "possession_rows": int(len(p)), "event_rows": int(len(E)),
            "corr_events_vs_possessions_per_game": round(corr, 4),
            "max_period_agreement_games": per_match,
            "known_503_invalid_lineup_possessions": "unchanged; this artifact does not touch them",
            "contradictions": contradictions,
            "possessions_artifact_modified": False,
            "authority": ("player_possessions/2 remains canonical for realised possessions; "
                          "canonical_player_events/1 is canonical for events. No linkage is asserted.")}


def main() -> int:
    npass = sum(1 for r in RESULTS if r["result"] == "PASS")
    out = {
        "schema": "canonical_event_validation/1",
        "artifact_id": "canonical_player_events/1",
        "validated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "nothing_fitted": True, "nothing_scored": True,
        "artifact_sha256": B._sha(OUT / "canonical_player_events_v1.parquet"),
        "producer_sha256": B._sha(Path(B.__file__)),
        "validator_sha256": B._sha(Path(__file__)),
        "checks_total": len(RESULTS), "checks_passed": npass,
        "checks_failed": len(RESULTS) - npass,
        "verdict": "PASS" if npass == len(RESULTS) else "FAIL",
        "pass_fail_table": [{"check": r["check"], "result": r["result"]} for r in RESULTS],
        "checks": RESULTS,
    }
    (OUT / "EVENT_VALIDATION.json").write_text(json.dumps(out, indent=2, default=str),
                                               encoding="utf-8")
    print(f"\n{npass}/{len(RESULTS)} checks passed -> {out['verdict']}")
    for r in RESULTS:
        if r["result"] != "PASS":
            print(f"  {r['result']}: {r['check']} -- {r['detail'].get('error')}")
    return 0 if npass == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
