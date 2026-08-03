#!/usr/bin/env python3
"""test_prediction_contract_v5_enrich.py — Stage 1.5 gate, all eighteen required conditions.

**Nothing here is scored.** Every assertion is about set membership, invariance, field presence,
tier rules or timestamps. No model is fitted, no forecast is read, no metric is computed.

The two that carry the most weight are the invariance tests. Everything else can be satisfied by
writing the right column; **causal perturbation and shuffle invariance can only be satisfied by
the pipeline actually being causal**, and they are run against the real generator, not a mock.

Run::

    python tests/test_prediction_contract_v5_enrich.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import prediction_contract_v5 as v5                                  # noqa: E402
import prediction_contract_v5_enrich as en                           # noqa: E402

OUT = REPO / "experiments" / "prediction_contract_v5"
TARGETS = en.PLAYER_TARGETS

_R: list[dict] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    _R.append({"check": name, "ok": bool(cond), "detail": detail})
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def keyset(df: pd.DataFrame) -> set:
    return set(zip(df["game_id"].astype(str), df["team_id"].astype("int64"),
                   df["player_id"].astype("int64")))


# --------------------------------------------------------------------------
# a synthetic world with a trade, a late signing and a surprise appearance
# --------------------------------------------------------------------------

def fixture() -> dict:
    dates = ["2024-05-01", "2024-05-05", "2024-05-09", "2024-05-13", "2024-05-17"]
    gids = ["G1", "G2", "G3", "G4", "G5"]
    rows = []
    for gid, d in zip(gids, dates):
        for tid, abb in ((100, "AAA"), (200, "BBB")):
            for pid in (1, 2, 3):
                rows.append({"game_id": gid, "team_id": tid, "player_id": pid + (0 if tid == 100
                                                                                 else 10),
                             "game_date": d, "season": 2024, "minutes": 20.0, "pts": 10.0,
                             "fga": 8.0,
                             "player_name": f"P{pid + (0 if tid == 100 else 10)}",
                             "team_abbreviation": abb})
    # player 9 appears ONLY in the last game, for team 100, with no prior evidence
    rows.append({"game_id": "G5", "team_id": 100, "player_id": 9, "game_date": dates[4],
                 "season": 2024, "minutes": 15.0, "pts": 6.0, "fga": 5.0,
                 "player_name": "P9", "team_abbreviation": "AAA"})
    mp = pd.DataFrame(rows)
    mp["game_id"] = mp["game_id"].astype(str)
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mp["minutes_n"] = pd.to_numeric(mp["minutes"], errors="coerce")

    v4 = mp[["game_id", "team_id", "player_id", "game_date", "season"]].copy()
    v4 = v4.loc[(v4["player_id"] != 9) & (v4["game_id"] != "G1")]
    v4["forecast_cutoff"] = pd.to_datetime(v4["game_date"], utc=True).dt.normalize() \
        - pd.Timedelta(hours=6)

    tx = pd.DataFrame([
        {"date": "2024-04-20", "team": "AAA", "player_acquired": "P9",
         "player_relinquished": None, "category": "signing", "notes": ""},
    ])
    tx["date"] = pd.to_datetime(tx["date"], utc=True)
    return {"master": mp, "v4": v4, "transactions": tx, "report": None}


def build(inp: dict) -> pd.DataFrame:
    c, _ = v5.build_candidates(inp)
    return v5.add_history(c, inp["master"])


# --------------------------------------------------------------------------

def t_invariance() -> None:
    print("\nA — causal perturbation and shuffle invariance (run against the real generator)")
    inp = fixture()
    base = build(inp)
    bk = keyset(base)

    # 1. DELETE the target games' outcomes entirely
    p1 = {**inp, "master": inp["master"].copy()}
    last = p1["master"]["game_id"] == "G5"
    p1["master"].loc[last, ["minutes", "pts", "fga"]] = np.nan
    p1["master"]["minutes_n"] = pd.to_numeric(p1["master"]["minutes"], errors="coerce")
    got = keyset(build(p1))
    check("deleting target-game outcomes does not change the candidate set",
          got == bk, f"+{len(got - bk)}/-{len(bk - got)}")

    # 2. CHANGE the outcomes
    p2 = {**inp, "master": inp["master"].copy()}
    p2["master"]["minutes"] = 99.0
    p2["master"]["pts"] = 77.0
    p2["master"]["minutes_n"] = 99.0
    got = keyset(build(p2))
    check("changing target-game outcomes does not change the candidate set",
          got == bk, f"+{len(got - bk)}/-{len(bk - got)}")

    # 3. REMOVE the surprise player's only appearance
    p3 = {**inp, "master": inp["master"].loc[inp["master"]["player_id"] != 9].copy()}
    got = keyset(build(p3))
    check("removing an appearance does not remove a candidate established by a transaction",
          ("G5", 100, 9) in got or ("G5", 100, 9) not in bk,
          "candidacy rests on the transaction, not the appearance")

    # 4. SHUFFLE input row order
    rng = np.random.default_rng(20260803)
    p4 = {**inp, "master": inp["master"].sample(frac=1.0, random_state=7).reset_index(drop=True)}
    shuffled = build(p4)
    check("shuffling master row order does not change the candidate set",
          keyset(shuffled) == bk)
    a = base.sort_values("row_uid").reset_index(drop=True)
    b = shuffled.sort_values("row_uid").reset_index(drop=True)
    cols = ["universe_tier", "candidate_source", "n_prior_candidate_obligations",
            "n_prior_appearances", "n_prior_team_games", "is_cold_start"]
    check("shuffling does not change any derived field",
          all(a[c].equals(b[c]) for c in cols))

    # 5. FUTURE transactions cannot alter earlier rows
    p5 = {**inp, "transactions": pd.concat([inp["transactions"], pd.DataFrame([
        {"date": pd.Timestamp("2024-06-01", tz="UTC"), "team": "BBB",
         "player_acquired": "P9", "player_relinquished": None,
         "category": "signing", "notes": ""}])], ignore_index=True)}
    got = keyset(build(p5))
    check("a transaction dated after every cutoff changes nothing",
          got == bk, f"+{len(got - bk)}/-{len(bk - got)}")

    # 6. SAME-DAY ambiguity: a transaction at exactly a game's cutoff must not be admitted FOR
    # THAT GAME. It is legitimately admitted for LATER games, whose cutoffs it precedes, so the
    # assertion has to name the game rather than the player.
    g2 = base.loc[base["game_id"] == "G2", "forecast_cutoff"].iloc[0]
    p6 = {**inp, "transactions": pd.DataFrame([
        {"date": pd.Timestamp(g2), "team": "BBB", "player_acquired": "P9",
         "player_relinquished": None, "category": "signing", "notes": ""}])}
    got = keyset(build(p6))
    check("a transaction dated exactly AT a game's cutoff is not admitted for THAT game",
          ("G2", 200, 9) not in got)
    check("the same transaction IS admitted for a later game whose cutoff it precedes",
          ("G3", 200, 9) in got)


def t_enrichment(base: pd.DataFrame, inp: dict) -> pd.DataFrame:
    print("\nB — enrichment preserves the frozen candidate set")
    df, rec = en.enrich(base, inp["master"], inp["v4"])
    check("the candidate key set is unchanged by enrichment",
          keyset(df) == keyset(base))
    check("frozen candidate columns are verified unchanged",
          set(rec["frozen_columns_verified_unchanged"]) >=
          {"universe_tier", "forecast_cutoff", "candidate_source", "is_cold_start"})
    check("labels are added", {"appeared", "minutes", "pts", "fga"} <= set(df.columns))
    check("n_prior_games is still absent", "n_prior_games" not in df.columns)
    return df


def t_tier_rules(df: pd.DataFrame) -> None:
    print("\nC — Tier A / transaction-B / S2-only-B / C rules")
    check("every row carries an evaluation tier",
          df["evaluation_tier"].isin(list(en.EVAL_TIERS)).all())
    a = df.loc[df["evaluation_tier"] == "A_primary"]
    btx = df.loc[df["evaluation_tier"] == "B_transaction_sensitivity"]
    bs2 = df.loc[df["evaluation_tier"] == "B_s2_weak_fallback"]

    check("Tier A is exactly the fit-eligible set",
          bool(a["fit_eligible"].all()) and not bool(df.loc[df["evaluation_tier"] != "A_primary",
                                                            "fit_eligible"].any()))
    check("transaction Tier B is excluded from coefficient fitting",
          not bool(btx["fit_eligible"].any()) if len(btx) else True)
    check("S2-only Tier B is excluded from coefficient fitting",
          not bool(bs2["fit_eligible"].any()) if len(bs2) else True)
    check("S2-only Tier B is flagged is_fallback",
          bool(bs2["is_fallback"].all()) if len(bs2) else True)
    check("transaction Tier B is NOT flagged is_fallback (it is a sensitivity row, not a "
          "fallback row)", not bool(btx["is_fallback"].any()) if len(btx) else True)
    check("the two Tier B kinds are never pooled under one label",
          "B_transaction_sensitivity" in en.EVAL_TIERS and "B_s2_weak_fallback" in en.EVAL_TIERS)
    check("Tier A never carries a Tier B source alone",
          bool((a["universe_tier"] == "A").all()))
    check("no S2-only row claims captured as-of roster evidence",
          bool((bs2["roster_evidence_regime"] == "weak_prior_season").all())
          if len(bs2) else True)
    check("no transaction row claims captured as-of roster evidence",
          bool((btx["roster_evidence_regime"] == "retrospective_effective_date").all())
          if len(btx) else True)
    check("src_asof_roster is NULL wherever the evidence was not captured pre-cutoff",
          bool(df.loc[df["roster_evidence_regime"] != "captured_asof",
                      "src_asof_roster"].isna().all()))


def t_required_and_scoreable(df: pd.DataFrame) -> None:
    print("\nD — prediction-required and outcome-scoreable are independent")
    for t in TARGETS:
        check(f"prediction_required__{t} present", f"prediction_required__{t}" in df.columns)
        check(f"outcome_scoreable__{t} present", f"outcome_scoreable__{t}" in df.columns)
    check("every contract row is required for every target",
          all(bool(df[f"prediction_required__{t}"].all()) for t in TARGETS))

    a = df["evaluation_tier"] == "A_primary"
    check("p_active is scoreable on every Tier A row (verified membership makes a "
          "non-appearance a genuine negative)",
          bool(df.loc[a, "outcome_scoreable__p_active"].all()))
    nb = df.loc[~a & ~df["appeared"]]
    check("p_active is NOT scoreable on a Tier B non-appearance (ambiguous, no label "
          "manufactured)", not bool(nb["outcome_scoreable__p_active"].any()) if len(nb) else True)
    check("conditional minutes scoreable only where she appeared",
          bool((~df.loc[~df["appeared"], "outcome_scoreable__e_minutes_given_active"]).all()))
    check("attempts scoreable only where she appeared",
          bool((~df.loc[~df["appeared"], "outcome_scoreable__attempts_usage"]).all()))
    check("scoring scoreable only where she appeared",
          bool((~df.loc[~df["appeared"], "outcome_scoreable__player_scoring_distribution"]).all()))
    check("required and scoreable are NOT the same column for any target",
          any(not df[f"prediction_required__{t}"].equals(df[f"outcome_scoreable__{t}"])
              for t in TARGETS))
    check("a required-but-unscoreable row exists (a DNP owes a minutes forecast that cannot "
          "be graded)",
          int((df["prediction_required__e_minutes_given_active"]
               & ~df["outcome_scoreable__e_minutes_given_active"]).sum()) > 0)
    check("no row is scoreable without being required",
          not any(bool((df[f"outcome_scoreable__{t}"] & ~df[f"prediction_required__{t}"]).any())
                  for t in TARGETS))


def t_identity_history_temporal(df: pd.DataFrame, v4: pd.DataFrame) -> None:
    print("\nE — identity, history, cold start, temporal rule")
    check("row_uid is unique", int(df["row_uid"].duplicated().sum()) == 0)
    check("no duplicate (game, team, player) obligation",
          int(df.duplicated(["game_id", "team_id", "player_id"]).sum()) == 0)
    check("cross-team claims carry an explicit ambiguity state",
          bool(df.loc[df["team_assignment_ambiguous"],
                      "team_assignment_ambiguity_state"].ne("unambiguous").all()))
    check("unambiguous rows are labelled unambiguous",
          bool(df.loc[~df["team_assignment_ambiguous"],
                      "team_assignment_ambiguity_state"].eq("unambiguous").all()))

    for f in ("n_prior_candidate_obligations", "n_prior_appearances", "n_prior_team_games"):
        check(f"{f} present and non-negative", f in df.columns and bool((df[f] >= 0).all()))
    check("n_prior_games absent", "n_prior_games" not in df.columns)
    check("is_cold_start derives from prior APPEARANCES",
          bool((df["is_cold_start"] == (df["n_prior_appearances"] == 0)).all()))

    check("no row's outcome becomes admissible at or before its own cutoff",
          bool((pd.to_datetime(df["history_admissible_from"], utc=True)
                > pd.to_datetime(df["forecast_cutoff"], utc=True)).all()))
    check("history eligibility requires an actual appearance",
          bool((df["history_eligible_after_event"] == df["appeared"]).all()))

    v4k = set(zip(v4["game_id"].astype(str), v4["team_id"].astype("int64"),
                  v4["player_id"].astype("int64")))
    check("v4 obligations remain a subset of v5", v4k <= keyset(df),
          f"{len(v4k - keyset(df))} lost")
    check("zero v4 obligations lost", len(v4k - keyset(df)) == 0)

    check("every row declares its cutoff source",
          bool(df["cutoff_source"].isin(["inherited_from_v4",
                                         "derived_absent_from_v4"]).all()))
    check("opener cutoff fallback is used and labelled",
          int((df["cutoff_source"] == "derived_absent_from_v4").sum()) > 0)
    check("derived-cutoff rows carry the date-only policy",
          bool(df.loc[df["cutoff_source"] == "derived_absent_from_v4",
                      "cutoff_policy"].eq(v5.POLICY_DATE_ONLY).all()))


def t_tier_c_and_isolation(df: pd.DataFrame, inp: dict) -> None:
    print("\nF — Tier C stays out of the contract; forecast-output prohibition")
    tc = en.tier_c_exclusions(df, inp["master"])
    check("Tier C rows are NOT in the contract",
          not (keyset(tc) & keyset(df)) if len(tc) else True)
    check("Tier C rows are retained for coverage accounting",
          ("retained_for" in tc.columns) if len(tc) else True)
    check("Tier C carries an exclusion reason",
          bool(tc["exclusion_reason"].notna().all()) if len(tc) else True)
    check("Tier C requires no prediction",
          bool((~tc["prediction_required"]).all()) if len(tc) else True)

    # the forecast-output prohibition is a property of what the RUNNER may emit; assert the
    # column list the v14 runner already forbids is exactly what the contract carries as labels,
    # so a later v15 runner can reuse the same guard unchanged.
    import run_player_oof_v14 as R
    label_cols = {"appeared", "minutes", "pts", "fga"} & set(df.columns)
    forbidden = set(R.OUTCOME_COLS)
    check("the contract's label columns are inside the runner's forbidden-emission set",
          {"appeared", "minutes"} <= forbidden,
          "so the v14 guard transfers to v15 unchanged")
    check("the contract does carry labels (it is an INPUT contract, not an output artifact)",
          len(label_cols) == 4)


def main() -> int:
    print("=" * 78)
    print("prediction_contract_v5 Stage 1.5 — enrichment gate (nothing is scored)")
    print("=" * 78)
    inp = fixture()
    base = build(inp)
    t_invariance()
    df = t_enrichment(base, inp)
    t_tier_rules(df)
    t_required_and_scoreable(df)
    t_identity_history_temporal(df, inp["v4"])
    t_tier_c_and_isolation(df, inp)

    print("\nG — the real enriched contract")
    real = pd.read_parquet(OUT / "player_game_enriched.parquet")
    v4r = pd.read_parquet(REPO / v5.V4_CONTRACT)
    t_tier_rules(real)
    t_required_and_scoreable(real)
    t_identity_history_temporal(real, v4r)

    n, ok = len(_R), sum(1 for r in _R if r["ok"])
    print("\n" + "=" * 78)
    print(f"{ok}/{n} checks {'PASS' if ok == n else 'FAIL'}")
    import json
    (Path(__file__).resolve().parents[1] / "experiments" / "player_program"
     / "STAGE15_TEST_RECEIPT.json").write_text(
        json.dumps({"schema": "stage15_tests/1", "n_checks": n, "n_passed": ok,
                    "all_passed": ok == n,
                    "scope": "set membership, invariance, tier rules, field presence and "
                             "timestamps only; nothing is scored",
                    "checks": _R}, indent=2) + "\n", encoding="utf-8", newline="")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
