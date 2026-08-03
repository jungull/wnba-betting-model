#!/usr/bin/env python3
"""test_prediction_contract_v5.py — Stage 1 validation of the tiered candidacy universe.

**Nothing here is scored.** Every assertion is about set membership, timestamps, tier labels or
field presence. No model is fitted, no forecast is read, no metric is computed.

Sections
    1  the postgame prohibition, tested BEHAVIOURALLY on a fixture
    2  cutoff strictness — equality is a violation, not a pass
    3  tier integrity — a Tier B source can never produce a Tier A row, and S4 never appears
    4  era discipline — S3 may not admit before the report era
    5  the superset property over v4
    6  history accounting — three named fields, `n_prior_games` retired
    7  the real artifact, end to end

Run::

    python tests/test_prediction_contract_v5.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import prediction_contract_v5 as v5                                  # noqa: E402

ART = REPO / "experiments" / "prediction_contract_v5" / "player_game.parquet"

_N = [0]


def check(name: str, cond: bool, detail: str = "") -> None:
    _N[0] += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        raise AssertionError(f"{name}: {detail}")


# --------------------------------------------------------------------------
# a small synthetic world: 2 teams, 3 games, one player who only ever plays
# in the LAST game and is named by no pre-cutoff source
# --------------------------------------------------------------------------

def fixture() -> dict:
    rows = []
    dates = ["2024-05-01", "2024-05-05", "2024-05-09"]
    gids = ["G1", "G2", "G3"]
    for gid, d in zip(gids, dates):
        for tid in (100, 200):
            for pid in (1, 2):                       # regulars, in every box
                rows.append({"game_id": gid, "team_id": tid, "player_id": pid,
                             "game_date": d, "season": 2024, "minutes": 20.0,
                             "player_name": f"P{pid}", "team_abbreviation": f"T{tid}"})
    # the SURPRISE: player 9 appears only in G3, for team 100, with no prior evidence anywhere
    rows.append({"game_id": "G3", "team_id": 100, "player_id": 9, "game_date": dates[2],
                 "season": 2024, "minutes": 15.0, "player_name": "P9",
                 "team_abbreviation": "T100"})
    mp = pd.DataFrame(rows)
    mp["game_id"] = mp["game_id"].astype(str)
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mp["minutes_n"] = pd.to_numeric(mp["minutes"], errors="coerce")

    # A stand-in for v4 must obey v4's OWN rule, or the superset test compares v5 against a
    # universe v4 could not have produced. v4 requires a PRIOR same-season team game, so G1 — the
    # opener — has no v4 obligations at all, and player 9 has none anywhere.
    v4 = mp[["game_id", "team_id", "player_id", "game_date", "season"]].copy()
    v4 = v4.loc[(v4["player_id"] != 9) & (v4["game_id"] != "G1")]
    v4["forecast_cutoff"] = pd.to_datetime(v4["game_date"], utc=True).dt.normalize() \
        - pd.Timedelta(hours=6)
    return {"master": mp, "v4": v4, "transactions": None, "report": None}


def s1_postgame_prohibition() -> None:
    print("\n1 — the postgame prohibition, tested behaviourally")
    inp = fixture()
    cand, rec = v5.build_candidates(inp)
    got = set(zip(cand["game_id"].astype(str), cand["team_id"], cand["player_id"]))

    check("player 9 APPEARED in G3 for team 100",
          bool(((inp["master"]["player_id"] == 9)
                & (inp["master"]["game_id"] == "G3")).any()))
    check("player 9 is NOT a candidate for G3 — her appearance did not create her obligation",
          ("G3", 100, 9) not in got)
    check("the regulars ARE candidates for G3 from prior boxes",
          ("G3", 100, 1) in got and ("G3", 100, 2) in got)

    aud = v5.audit_universe(cand, inp["master"])
    check("she is recorded as a candidate-universe MISS",
          aud["totals"]["appearing_players_missed_by_the_universe"] >= 1,
          str(aud["totals"]["appearing_players_missed_by_the_universe"]))
    check("the audit declares that the box score is used only for auditing",
          "never reads it" in aud["postgame_use_declaration"])


def s2_cutoff_strictness() -> None:
    print("\n2 — cutoff strictness")
    inp = fixture()
    cand, _ = v5.build_candidates(inp)
    late = int((cand["candidate_evidence_time"] >= cand["forecast_cutoff"]).sum())
    check("no row's evidence time is at or after its own cutoff", late == 0, f"{late} violations")

    # G1 is a season opener with no prior box; S1 must contribute nothing to it
    g1 = cand.loc[cand["game_id"] == "G1"]
    check("the opener has no S1 candidate — S1 requires a PRIOR same-season box",
          not g1["candidate_source"].str.contains("S1").any())


def s3_tier_integrity() -> None:
    print("\n3 — tier integrity")
    inp = fixture()
    cand, _ = v5.build_candidates(inp)
    srcs = cand["candidate_source"].str.split("|")
    a_by_source = srcs.map(lambda ss: any(s in v5.TIER_A_SOURCES for s in ss))
    check("universe_tier agrees with the sources named on every row",
          bool((a_by_source == (cand["universe_tier"] == "A")).all()))
    b_only = cand.loc[~a_by_source]
    check("every Tier-B-only row is labelled B", bool((b_only["universe_tier"] == "B").all()))
    check("every Tier-B-only row is flagged is_fallback", bool(b_only["is_fallback"].all()))
    check("S4 is declared unavailable", v5.SOURCES["S4"]["available"] is False)
    check("S4 never appears in any candidate_source",
          not cand["candidate_source"].str.contains("S4").any())
    check("S2 is never a Tier A source", "S2" not in v5.TIER_A_SOURCES)
    check("S_TX is never a Tier A source", "S_TX" not in v5.TIER_A_SOURCES)
    check("S2's confidence is recorded as weak", v5.SOURCES["S2"]["confidence"] == "weak")


def s4_era() -> None:
    print("\n4 — era discipline")
    inp = fixture()
    cand, _ = v5.build_candidates(inp)
    bad = int(((cand["candidate_source"].str.contains("S3"))
               & (cand["forecast_cutoff"] < v5.REPORT_ERA_START)).sum())
    check("S3 never admits before the report era begins", bad == 0, f"{bad} rows")
    check("every row carries an era label", cand["era"].notna().all())
    check("this 2024 fixture is entirely box_only",
          bool((cand["era"] == "box_only").all()))


def s5_superset_and_history() -> None:
    print("\n5/6 — superset over v4, and history accounting")
    inp = fixture()
    cand, _ = v5.build_candidates(inp)
    cand = v5.add_history(cand, inp["master"])
    val = v5.validate(cand, inp["v4"])
    check("validation passes on the fixture", val["ok"], "; ".join(val["problems"]))
    check("no v4 obligation is lost", val["n_lost_vs_v4"] == 0)
    check("the superset property is asserted", val["superset_property_holds"])

    for f in ("n_prior_candidate_obligations", "n_prior_appearances", "n_prior_team_games"):
        check(f"{f} is emitted", f in cand.columns)
        check(f"{f} is non-negative", bool((cand[f] >= 0).all()))
    check("n_prior_games is NOT emitted", "n_prior_games" not in cand.columns)
    check("is_cold_start is derived from prior APPEARANCES, not obligations",
          bool((cand["is_cold_start"] == (cand["n_prior_appearances"] == 0)).all()))
    check("appearances-exceeding-obligations is reported, not enforced",
          "appearances_exceed_obligations" in cand.columns
          and val["n_rows_where_appearances_exceed_obligations"] is not None)


def s7_real_artifact() -> None:
    print("\n7 — the real artifact")
    if not ART.exists():
        check("artifact present", False, f"{ART} not found; run prediction_contract_v5.py first")
        return
    cand = pd.read_parquet(ART)
    v4 = pd.read_parquet(REPO / v5.V4_CONTRACT)
    v4["game_id"] = v4["game_id"].astype(str)
    for c in ("player_id", "team_id"):
        v4[c] = v4[c].astype("int64")

    val = v5.validate(cand, v4)
    check("validation passes on the real universe", val["ok"], "; ".join(val["problems"][:3]))
    check("no v4 obligation lost", val["n_lost_vs_v4"] == 0)
    check("v5 strictly adds", val["n_added_vs_v4"] > 0, f"+{val['n_added_vs_v4']}")

    late = int((pd.to_datetime(cand["candidate_evidence_time"], utc=True)
                >= pd.to_datetime(cand["forecast_cutoff"], utc=True)).sum())
    check("no evidence time at or after its cutoff, on the real universe", late == 0)

    a = cand.loc[cand["universe_tier"] == "A"]
    b = cand.loc[cand["universe_tier"] == "B"]
    check("Tier A is at least the v4 universe", len(a) >= len(v4), f"{len(a)} vs {len(v4)}")
    check("Tier B is non-empty and reported separately", len(b) > 0, str(len(b)))
    check("every Tier B row carries a confidence",
          bool(b["team_assignment_confidence"].notna().all()))
    check("every Tier B row carries an evidence time",
          bool(b["candidate_evidence_time"].notna().all()))
    check("every Tier B row is flagged is_fallback", bool(b["is_fallback"].all()))
    check("no Tier A row is flagged is_fallback", bool((~a["is_fallback"]).all()))
    check("S4 absent from the real universe",
          not cand["candidate_source"].str.contains("S4").any())
    check("n_prior_games absent from the real universe", "n_prior_games" not in cand.columns)

    src_ok = cand["cutoff_source"].isin(["inherited_from_v4", "derived_absent_from_v4"]).all()
    check("every row declares where its cutoff came from", bool(src_ok))
    n_der = int((cand["cutoff_source"] == "derived_absent_from_v4").sum())
    check("derived cutoffs are labelled and non-zero", n_der > 0, f"{n_der} rows")


def main() -> int:
    print("=" * 78)
    print("prediction_contract_v5 — Stage 1 validation (nothing is scored)")
    print("=" * 78)
    s1_postgame_prohibition()
    s2_cutoff_strictness()
    s3_tier_integrity()
    s4_era()
    s5_superset_and_history()
    s7_real_artifact()
    print("\n" + "=" * 78)
    print(f"{_N[0]}/{_N[0]} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
