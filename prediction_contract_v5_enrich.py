#!/usr/bin/env python3
"""prediction_contract_v5_enrich.py — Stage 1.5: the estimator-consumable v5 contract.

Stage 1 produced a candidate **universe**: who was a candidate, on what evidence, in which tier.
It is not a contract an estimator can read — it has 29 columns against v4's 54 and carries no
labels, no obligation declarations and no schedule identity. This module adds those, and its
entire discipline is that **adding them may not change who was a candidate.**

THE SEPARATION THIS MODULE EXISTS TO PRESERVE
----------------------------------------------
Five things are kept apart, and the tests prove they stay apart:

  1. pre-cutoff CANDIDATE and FEATURE information  — Stage 1's frozen output, never rewritten
  2. postgame OUTCOME LABELS                       — added here, and only as labels
  3. PREDICTION OBLIGATIONS                        — derived from tier, never from outcomes
  4. SCOREABILITY DECLARATIONS                     — derived from outcomes, never from tier
  5. EXCLUSIONS and AUDIT-ONLY rows                — a separate artifact, never in the contract

`prediction_required__*` and `outcome_scoreable__*` are different concepts and **neither is
inferred from the other**. A row can be required and unscoreable (a DNP owes a minutes forecast
that cannot be graded). A row can never be scoreable and not required.

WHY TIER C ROWS ARE NOT IN THE CONTRACT
----------------------------------------
Tier C is "a player appeared but no pre-cutoff evidence assigned her to that team". **The only way
this module can know a Tier C row exists is that she appeared** — which is postgame information.
Putting her in the contract would therefore use a postgame fact to build the pregame universe,
which is precisely the prohibition. Tier C lives in `candidacy_exclusions.parquet`, produced by
the audit, and is counted in coverage accounting from there. It is never silently discarded and
never silently admitted.

THE ROSTER-PROVENANCE HONESTY RULE
-----------------------------------
`src_asof_roster` is populated **only** from evidence that was genuinely captured before the
cutoff — S1's prior-box availability bound, or S3's capture time. It is left NULL for a row whose
only evidence is the retrospectively-scraped transaction wire or prior-season affiliation, because
writing an effective date into an "as-of" column would imply an observation that never happened.
`roster_evidence_regime` names which of the three kinds of evidence a row actually has.

Run::

    python prediction_contract_v5_enrich.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import cbs_obligation_key as obk
import prediction_contract_v5 as v5

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parent

ENRICH_ID = "prediction_contract_v5_enrich/1"
CONTRACT_VERSION = "player_game_contract/5.1"

PLAYER_TARGETS = ("p_active", "e_minutes_given_active", "attempts_usage",
                  "player_scoring_distribution")

#: Evaluation tiers. Deliberately finer than `universe_tier`, because the amendment requires that
#: transaction-derived and S2-only Tier B rows are never pooled.
EVAL_TIERS = {
    "A_primary": "Tier A. Eligible for primary fitting and primary evaluation.",
    "B_transaction_sensitivity": ("Tier B from the transaction wire. Excluded from coefficient "
                                  "fitting; separately identified sensitivity prediction; "
                                  "evaluated separately."),
    "B_s2_weak_fallback": ("Tier B from prior-season affiliation alone. Excluded from "
                           "coefficient fitting; fallback/sensitivity prediction only; "
                           "is_fallback; reported separately from transaction Tier B because its "
                           "sole-source precision is extremely low (0.87%)."),
}

#: How a row's roster evidence was actually obtained. Never collapsed into one "as-of" column.
ROSTER_REGIMES = {
    "captured_asof": ("evidence genuinely observable before the cutoff: a prior game's box "
                      "availability bound (S1) or a captured report's capture_utc (S3)"),
    "retrospective_effective_date": ("the transaction wire (S_TX): a real per-row EFFECTIVE date, "
                                     "but observed in a single 2026-07-30 scrape with no "
                                     "preserved publication timestamp"),
    "weak_prior_season": ("prior-season franchise affiliation (S2) alone: evidence of PAST "
                          "affiliation, not of current roster membership"),
}


class EnrichError(RuntimeError):
    """The enrichment would have violated a separation this module exists to preserve."""


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# labels — added, never allowed to feed back
# --------------------------------------------------------------------------- #

def outcome_labels(mp: pd.DataFrame) -> pd.DataFrame:
    """Per (game, team, player): did she appear, and her three raw stat labels.

    `appeared` is BOX MEMBERSHIP WITH MINUTES, exactly as v4 defines it. A player listed with a
    DNP reason and null minutes is present in the box and did not appear.
    """
    o = mp[["game_id", "team_id", "player_id", "minutes", "pts", "fga"]].copy()
    o["game_id"] = o["game_id"].astype(str)
    for c in ("team_id", "player_id"):
        o[c] = o[c].astype("int64")
    for c in ("minutes", "pts", "fga"):
        o[c] = pd.to_numeric(o[c], errors="coerce")
    o["appeared"] = o["minutes"].fillna(0.0) > 0
    o["in_target_box"] = True
    return o.drop_duplicates(subset=["game_id", "team_id", "player_id"])


def schedule_identity(v4: pd.DataFrame) -> pd.DataFrame:
    """Tip-time and cutoff-policy identity, inherited from v4 for games v4 covered."""
    cols = ["game_id", "scheduled_tip_time", "tip_time_source", "tip_time_observed_at",
            "tip_time_quality", "tip_revisions_seen", "cutoff_policy", "exact_cutoff_ok"]
    have = [c for c in cols if c in v4.columns]
    s = v4[have].drop_duplicates(subset=["game_id"]).copy()
    s["game_id"] = s["game_id"].astype(str)
    return s


# --------------------------------------------------------------------------- #
# the enrichment
# --------------------------------------------------------------------------- #

def enrich(cand: pd.DataFrame, mp: pd.DataFrame, v4: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Add labels, obligations, scoreability and schedule identity to a FROZEN candidate set."""
    before_keys = set(zip(cand["game_id"].astype(str), cand["team_id"], cand["player_id"]))
    before_cols = {c: cand[c].copy() for c in
                   ("universe_tier", "team_assignment_source", "team_assignment_confidence",
                    "forecast_cutoff", "candidate_source", "is_cold_start", "era")
                   if c in cand.columns}

    df = cand.copy()
    df["game_id"] = df["game_id"].astype(str)

    # ---- 1. evaluation tier: transaction-derived and S2-only never pooled ----
    srcs = df["candidate_source"].str.split("|")
    has_tx = srcs.map(lambda ss: "S_TX" in ss)
    is_a = df["universe_tier"] == "A"
    df["evaluation_tier"] = np.where(
        is_a, "A_primary",
        np.where(has_tx, "B_transaction_sensitivity", "B_s2_weak_fallback"))

    # ---- 2. fitting and history eligibility, from TIER ALONE -----------------
    df["fit_eligible"] = df["evaluation_tier"] == "A_primary"
    df["is_fallback"] = df["evaluation_tier"] == "B_s2_weak_fallback"

    # ---- 3. roster provenance, honestly ------------------------------------
    tier_a_time = df["candidate_published_time"]        # S1/S3 only; null otherwise, by Stage 1
    df["src_asof_roster"] = tier_a_time
    df["roster_asof_absent_reason"] = np.where(
        tier_a_time.notna(), None,
        "no captured pre-cutoff roster evidence; this row rests on a retrospective effective "
        "date or on prior-season affiliation, and writing either into an as-of column would "
        "imply an observation that never happened")
    df["roster_evidence_regime"] = np.where(
        tier_a_time.notna(), "captured_asof",
        np.where(has_tx, "retrospective_effective_date", "weak_prior_season"))
    df["src_policy_roster"] = df["team_assignment_source"]
    df["n_roster_games_consumed"] = df["n_prior_team_games"]

    # ---- 4. schedule identity ----------------------------------------------
    sched = schedule_identity(v4)
    df = df.merge(sched, on="game_id", how="left")
    # A game v4 never covered contributes no schedule identity at all, and neither does a v4
    # frame that predates these columns. Create them explicitly rather than letting a missing
    # column surface later as a KeyError inside a consumer.
    for c in ("scheduled_tip_time", "tip_time_source", "tip_time_observed_at",
              "tip_time_quality", "tip_revisions_seen", "cutoff_policy", "exact_cutoff_ok"):
        if c not in df.columns:
            df[c] = pd.NA
    df["cutoff_policy"] = df["cutoff_policy"].fillna(v5.POLICY_DATE_ONLY)
    df["exact_cutoff_ok"] = df["exact_cutoff_ok"].fillna(False).astype(bool)
    df["fold_id"] = "season:" + df["season"].astype(int).astype(str)

    # ---- 5. LABELS. Added last, and only as labels --------------------------
    lab = outcome_labels(mp)
    df = df.merge(lab, on=["game_id", "team_id", "player_id"], how="left")
    df["in_target_box"] = df["in_target_box"].fillna(False).astype(bool)
    df["appeared"] = df["appeared"].fillna(False).astype(bool)

    # ---- 6. PREDICTION REQUIRED — from tier, never from outcomes ------------
    # Every row in the contract is a candidate, so every row owes every target. The DIFFERENCE
    # between tiers is how the prediction is labelled and evaluated, not whether it is owed.
    for t in PLAYER_TARGETS:
        df[f"prediction_required__{t}"] = True

    # ---- 7. OUTCOME SCOREABLE — from outcomes, never from tier --------------
    # p_active: for Tier A, roster membership is verified, so a non-appearance is a GENUINE
    # negative and the row is scoreable either way. For Tier B it is not: a non-appearance is
    # ambiguous between "rostered and did not dress" and "was never on this roster at all", and
    # a tier label must not manufacture an outcome. So Tier B is scoreable only where she DID
    # appear, which is the case an appearance positively confirms.
    df["outcome_scoreable__p_active"] = np.where(is_a, True, df["appeared"])
    df["p_active_unscoreable_reason"] = np.where(
        is_a | df["appeared"], None,
        "tier B non-appearance is ambiguous between a scratch and a player who was never on "
        "this roster; no outcome label is manufactured")

    df["outcome_scoreable__e_minutes_given_active"] = df["appeared"] & df["minutes"].notna()
    df["outcome_scoreable__attempts_usage"] = df["appeared"] & df["fga"].notna()
    df["outcome_scoreable__player_scoring_distribution"] = df["appeared"] & df["pts"].notna()

    # ---- 7b. cross-team ambiguity, made EXPLICIT ---------------------------
    # A player can legitimately be a candidate for two clubs in one game: she is inside her old
    # club's lookback window and her new club has already named her. At cutoff the contract cannot
    # know which one she will turn out for, and both obligations are genuinely owed. What it must
    # never do is leave that state implicit, so it is a named field rather than something a reader
    # infers by grouping.
    dup = df.groupby(["game_id", "player_id"])["team_id"].transform("nunique")
    df["team_assignment_ambiguous"] = dup > 1
    df["n_teams_claiming_this_player_game"] = dup.astype("int64")
    df["team_assignment_ambiguity_state"] = np.where(
        dup > 1,
        np.where(df["in_target_box"], "claimed_by_multiple_teams__this_club_has_the_box_row",
                 "claimed_by_multiple_teams__no_box_row_for_this_club"),
        "unambiguous")

    # ---- 8. the temporal rule on history -----------------------------------
    # An appearance becomes historically known at its outcome-availability bound. A row may inform
    # a LATER prediction and never its own, and never one at the same cutoff.
    df["history_admissible_from"] = v5.availability_bound(df["game_date"])
    df["history_eligible_after_event"] = df["appeared"]
    bad = int((df["history_admissible_from"] <= df["forecast_cutoff"]).sum())
    if bad:
        raise EnrichError(
            f"{bad} rows whose outcome becomes admissible at or before their own cutoff; a row "
            f"could inform its own prediction")

    # ---- 9. prove the frozen columns did not move --------------------------
    after_keys = set(zip(df["game_id"].astype(str), df["team_id"], df["player_id"]))
    if after_keys != before_keys:
        raise EnrichError(
            f"the candidate set changed during enrichment: "
            f"+{len(after_keys - before_keys)} / -{len(before_keys - after_keys)}")
    for c, orig in before_cols.items():
        if not df[c].reset_index(drop=True).equals(orig.reset_index(drop=True)):
            raise EnrichError(f"enrichment altered the frozen candidate column {c!r}")

    if "n_prior_games" in df.columns:
        raise EnrichError("n_prior_games is retired and must never be emitted")

    receipt = {
        "receipt": "enrichment/1",
        "n_rows": int(len(df)),
        "n_candidate_keys_unchanged": len(before_keys),
        "frozen_columns_verified_unchanged": sorted(before_cols),
        "labels_added": ["appeared", "minutes", "pts", "fga", "in_target_box"],
        "labels_are_labels_only": (
            "the outcome join may not change who was a candidate, her team assignment, her "
            "universe tier, her forecast cutoff, her cold-start state or her prediction "
            "requirement. Asserted above by key-set equality and column-wise equality."),
        "n_in_target_box": int(df["in_target_box"].sum()),
        "n_appeared": int(df["appeared"].sum()),
        "evaluation_tiers": {k: int(v) for k, v in
                             df["evaluation_tier"].value_counts().items()},
        "roster_evidence_regimes": {k: int(v) for k, v in
                                    df["roster_evidence_regime"].value_counts().items()},
        "n_fit_eligible": int(df["fit_eligible"].sum()),
        "n_history_eligible_after_event": int(df["history_eligible_after_event"].sum()),
        "cross_team_ambiguity": {
            "n_ambiguous_rows": int(df["team_assignment_ambiguous"].sum()),
            "n_distinct_player_games_affected": int(
                df.loc[df["team_assignment_ambiguous"], "player_game_uid"].nunique()),
            "states": {k: int(v) for k, v in
                       df["team_assignment_ambiguity_state"].value_counts().items()},
            "why_it_is_legitimate": (
                "a traded player sits inside her old club's lookback window while her new club "
                "has already named her. At cutoff the contract cannot know which club she will "
                "turn out for, so both obligations are owed. The state is NAMED rather than left "
                "for a reader to infer by grouping."),
        },
    }
    return df, receipt


# --------------------------------------------------------------------------- #
# the Tier C artifact — audit-only, never in the contract
# --------------------------------------------------------------------------- #

def tier_c_exclusions(df: pd.DataFrame, mp: pd.DataFrame) -> pd.DataFrame:
    """Appearing player-team-games the pregame universe did not contain.

    Derived POSTGAME, kept OUT of the contract, and counted in coverage accounting from here.
    """
    played = mp.loc[pd.to_numeric(mp["minutes"], errors="coerce").fillna(0) > 0,
                    ["game_id", "team_id", "player_id", "season", "game_date"]].copy()
    played["game_id"] = played["game_id"].astype(str)
    for c in ("team_id", "player_id"):
        played[c] = played[c].astype("int64")
    played = played.drop_duplicates()
    have = set(zip(df["game_id"].astype(str), df["team_id"], df["player_id"]))
    miss = played.loc[[(g, t, p) not in have for g, t, p
                       in zip(played["game_id"], played["team_id"], played["player_id"])]].copy()
    miss["universe_tier"] = "C"
    miss["exclusion_reason"] = "no_pre_cutoff_evidence_assigned_this_player_to_this_team"
    miss["prediction_required"] = False
    miss["retained_for"] = "coverage accounting and the universe-miss audit"
    miss["not_in_contract_because"] = (
        "the only way this row is knowable is that she appeared, which is postgame information; "
        "admitting it to the contract would use a postgame fact to build the pregame universe")
    return miss.reset_index(drop=True)


# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    out = Path(args.out) if args.out else root / "experiments" / "prediction_contract_v5"

    cand = pd.read_parquet(out / "player_game.parquet")
    mp = pd.read_parquet(root / v5.MASTER_PLAYER)
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    v4 = pd.read_parquet(root / v5.V4_CONTRACT)
    v4["game_id"] = v4["game_id"].astype(str)

    df, rec = enrich(cand, mp, v4)
    tc = tier_c_exclusions(df, mp)

    obk.assert_unique_canonical_keys(df, "v5 enriched contract")

    df.to_parquet(out / "player_game_enriched.parquet", index=False)
    tc.to_parquet(out / "candidacy_exclusions.parquet", index=False)

    by = {}
    for tier, g in df.groupby("evaluation_tier"):
        by[tier] = {
            "n_rows": int(len(g)),
            "n_appeared": int(g["appeared"].sum()),
            "n_cold_start": int(g["is_cold_start"].sum()),
            "n_fallback": int(g["is_fallback"].sum()),
            "fit_eligible": bool(g["fit_eligible"].all()) if len(g) else None,
            "required_by_target": {t: int(g[f"prediction_required__{t}"].sum())
                                   for t in PLAYER_TARGETS},
            "scoreable_by_target": {t: int(g[f"outcome_scoreable__{t}"].sum())
                                    for t in PLAYER_TARGETS},
            "by_season": {str(int(s)): int(n) for s, n in g.groupby("season").size().items()},
        }

    receipt = {
        "schema": ENRICH_ID,
        "contract_version": CONTRACT_VERSION,
        "generated_utc": _utc(),
        "stage": "1.5 — contract adapter only. NOTHING IS FITTED, PREDICTED OR SCORED.",
        "separations_preserved": {
            "pre_cutoff_candidate_and_feature_information": "Stage 1 output, frozen",
            "postgame_outcome_labels": "added here, as labels only",
            "prediction_obligations": "derived from TIER, never from outcomes",
            "scoreability_declarations": "derived from OUTCOMES, never from tier",
            "exclusions_and_audit_only_rows": "a separate artifact, never in the contract",
            "prediction_required_and_outcome_scoreable_are_never_inferred_from_each_other": True,
        },
        "evaluation_tiers": EVAL_TIERS,
        "roster_evidence_regimes": ROSTER_REGIMES,
        "enrichment": rec,
        "by_evaluation_tier": by,
        "tier_c": {
            "n_rows": int(len(tc)),
            "artifact": "candidacy_exclusions.parquet",
            "in_contract": False,
            "why_not": ("knowable only from a postgame appearance; admitting it would use a "
                        "postgame fact to build the pregame universe"),
            "by_season": {str(int(s)): int(n) for s, n in tc.groupby("season").size().items()}
            if len(tc) else {},
        },
        "cutoff_sources": {k: int(v) for k, v in df["cutoff_source"].value_counts().items()},
        "n_rows_total": int(len(df)),
        "n_rows_by_season": {str(int(s)): int(n) for s, n in df.groupby("season").size().items()},
        "hashes": {
            "candidate_universe_sha256": _sha(out / "player_game.parquet"),
            "enriched_contract_sha256": _sha(out / "player_game_enriched.parquet"),
            "exclusions_sha256": _sha(out / "candidacy_exclusions.parquet"),
            "enricher_sha256": _sha(Path(__file__).resolve()),
            "generator_sha256": _sha(root / "prediction_contract_v5.py"),
        },
        "columns": sorted(df.columns.tolist()),
        "n_columns": int(df.shape[1]),
    }
    (out / "enrichment_receipt.json").write_text(
        json.dumps(receipt, indent=2, default=str) + "\n", encoding="utf-8", newline="")

    print(f"wrote {out / 'player_game_enriched.parquet'}")
    print(json.dumps({
        "n_rows": receipt["n_rows_total"], "n_columns": receipt["n_columns"],
        "by_evaluation_tier": {k: v["n_rows"] for k, v in by.items()},
        "n_fit_eligible": rec["n_fit_eligible"],
        "tier_c_rows": receipt["tier_c"]["n_rows"],
        "roster_evidence_regimes": rec["roster_evidence_regimes"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
