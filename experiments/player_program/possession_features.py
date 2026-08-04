#!/usr/bin/env python3
"""possession_features.py — cutoff-valid feature construction for the possession-prior model.

This is the FIRST producer in the repository that emits a construction receipt. Every feature
frame it returns is accompanied by a ``construction_receipt/1`` written to disk during
construction, so ``gate_invocation`` can re-derive the frame's lineage from files rather than
believe a mapping the caller assembled at the invocation site.

WHAT THIS PRODUCER DOES AND DOES NOT CLAIM
------------------------------------------
It establishes producer-backed provenance for the **Stage 2 possession-model feature frame
derived from** the frozen canonical artifacts. It does **not** establish, and must never be read
as establishing, how ``team_possession_prior_v1.parquet`` itself was originally constructed. That
artifact's construction is attested by ``PROJECTED_EXPOSURE_RECEIPT.json`` and
``PROJECTED_EXPOSURE_VALIDATION.json`` — the receipts that already existed — and by nothing
written here. Every receipt this module emits carries that boundary in its own
``claim_boundary`` block, and splits its evidence into ``frozen_source_provenance`` (what was
read, and what the pre-existing receipts say about it) and ``produced_frame_provenance`` (what
this producer emitted).

READ-ONLY. Nothing under ``projected_exposure_v1/`` or ``possessions_v2/`` is written, moved or
touched; the canonical parquets are opened for reading and hashed. Nothing here is fitted and
nothing here is scored: no projection is compared against any realised value, and no accuracy,
error, likelihood or skill statistic is computed anywhere in this module.

THE UNIVERSE IS A SHARED CONTRACT, NOT A PER-DESIGN CHOICE
----------------------------------------------------------
``load_universe()`` returns ONE digested universe (``team_possession_universe/1``) and all three
Stage 2 inputs are drawn from it:

    incumbent_input()   the frozen prior's own projection, which is what the incumbent predicts
                        with. No fitted feature.
    k0_input()          the matched control: the same rows and the same exposure offset with an
                        empty feature set. ``feature_gate`` provides for a zero-feature design
                        explicitly and calls it trivially identified.
    challenger_input()  the incumbent-EQUIVALENT feature construction below.

``parity_report()`` recomputes the row-universe digest of all three and blocks if they differ. A
challenger documented against a universe the incumbent never saw is the parity defect this
program has already paid for once; making the universe a digested contract is what stops it
recurring one level up.

WHAT IS IN THE FRAME, AND WHY EACH COLUMN IS CUTOFF-VALID
---------------------------------------------------------
Every column is a function of games STRICTLY EARLIER than the row's own ``game_date``, or of the
schedule, and of nothing else. The producer of the frozen prior guarantees the first part for the
pace estimates: they are trailing-window means over prior games, or a league prior over strictly
earlier dates, and no realised value of the target game enters them.

    pace_gap                  team_pace_estimate - opp_pace_estimate. The pace CONTRAST between
                              the two clubs. It is deliberately not the pace LEVEL: the level is
                              the exposure offset (below), and a feature in the span of its own
                              offset is an identifiability problem the pairwise gate cannot see.
    pace_evidence_depth       how many team-specific prior games the club's own estimate rests
    opp_pace_evidence_depth   on, capped at the producer's declared window (10), and 0 when the
                              estimate fell back to the league prior rather than to team history.
                              Evidence depth, not evidence content.
    is_playoff_game           schedule fact, known at the cutoff.

Deliberately EXCLUDED, and the exclusions are the honest part:

    projected_team_off_possessions  it is the OFFSET (as a log), not a feature. Carrying it as
                                    both would make the design a deterministic transform of its
                                    own exposure.
    team_pace_estimate,             each is cutoff-valid on its own, but the offset is the log of
    opp_pace_estimate               their mean, so the pair SPANS the offset. Their difference
                                    (``pace_gap``) is the part that does not.
    everything in data/masters/master_team.parquet  it is a realised team box score of the TARGET
                                    game — points, rebounds, turnovers, opponent totals. Every
                                    column of it is an outcome of the game being predicted. It was
                                    inspected and is not read.
    n_history_games (raw)           at pace level 3 it is a cumulative league game count reaching
                                    1300, which is a different quantity from a trailing-window
                                    count of at most 10. Mixing the two in one column would put
                                    two meanings in one number.

The realised possession count IS read, from the frozen ``possessions_v2`` artifact, and is
declared as an ``outcome_source``: it is the model's target and it is supplied to
``feature_gate`` as ``target=`` so that ``target_derived`` and the missingness checks can fire. It
never enters the feature frame, and the receipt records that separation explicitly.

Run::

    python experiments/player_program/possession_features.py            # dry construction + gate
    python experiments/player_program/possession_features.py --receipt-dir <dir>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np, pandas as pd                                                # noqa: E401

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

sys.path.insert(0, str(HERE))
import construction_receipt as cr                                               # noqa: E402

# --------------------------------------------------------------------------- #
# frozen inputs. Paths are module constants so a test can point the producer at temp COPIES;
# the real artifacts are never written by anything here.
# --------------------------------------------------------------------------- #
EXPOSURE_DIR = HERE / "projected_exposure_v1"
PRIOR_PARQUET = EXPOSURE_DIR / "team_possession_prior_v1.parquet"
EXPOSURE_RECEIPT = EXPOSURE_DIR / "PROJECTED_EXPOSURE_RECEIPT.json"
EXPOSURE_VALIDATION = EXPOSURE_DIR / "PROJECTED_EXPOSURE_VALIDATION.json"

POSSESSIONS_DIR = HERE / "possessions_v2"
POSSESSIONS_PARQUET = POSSESSIONS_DIR / "possessions_raw_v2.parquet"
POSSESSIONS_RECEIPT = POSSESSIONS_DIR / "POSSESSION_INTEGRITY_RECEIPT_V2.json"

EXPERIMENT = "possession_prior"
ARM = "incumbent_equivalent"

UNIVERSE_CONTRACT_ID = "team_possession_universe/1"
FEATURE_SET_ID = "possession_prior_incumbent_equivalent/1"

#: the producer's own declared trailing window, mirrored from build_projected_exposure.py. It is
#: the cap on evidence depth, and it is stated here rather than re-derived from the data.
WINDOW_K = 10
REGULATION_MIN = 40.0

#: pace levels that rest on TEAM history rather than on the league prior.
TEAM_HISTORY_LEVELS = (1, 2)

FEATURE_NAMES: tuple[str, ...] = ("pace_gap", "pace_evidence_depth", "opp_pace_evidence_depth",
                                  "is_playoff_game")
OFFSET_COLUMN = "log_projected_team_off_possessions"
TARGET_COLUMN = "realised_team_off_possessions_reg_equiv"
ROW_IDENTITY_COLUMNS: tuple[str, ...] = ("game_id", "team_id")
DECISION_TIME_COLUMN = "game_date"

#: columns the frame carries for identity and fold assignment but never declares as features.
CARRIED_NOT_FEATURES: tuple[str, ...] = (
    "game_id", "team_id", "opp_team_id", "game_date", "season", "season_type", "pace_level",
    "opp_pace_level", "n_history_games", "opp_n_history_games", "team_pace_estimate",
    "opp_pace_estimate", "projected_team_off_possessions", OFFSET_COLUMN)

DECISION_TIME_RULE = (
    "every declared feature is a function of games with game_date STRICTLY EARLIER than the row's "
    "own game_date, or of the schedule. The pace estimates are the frozen producer's "
    "prior-games-only trailing-window means (or its league prior over strictly earlier dates); no "
    "realised minute, lineup, pace or possession of the target game enters any feature column. "
    "The per-row decision time is the row's own game_date")

CLAIM_BOUNDARY_ADDITION = {
    "stage": (
        "Stage 2 possession-model FEATURE FRAME derived from frozen canonical artifacts. This "
        "receipt does not re-establish the construction provenance of team_possession_prior_v1 "
        "itself, which remains attested by its own artifact and validation receipts only"),
}


class PossessionFeatureFailure(RuntimeError):
    """Raised when the possession feature frame cannot be constructed honestly. Nothing is returned."""


# --------------------------------------------------------------------------- #
# the shared universe
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class PossessionUniverse:
    """One digested row universe, plus the frozen sources it was drawn from.

    ``frame`` carries every identity, fold and candidate-feature column. ``contract`` is the
    digest triple that ``incumbent_input``, ``k0_input`` and ``challenger_input`` must all agree
    on, and ``sources`` is the exact source manifest every receipt binds.
    """

    frame: pd.DataFrame
    contract: dict
    sources: list
    paths: dict
    restrictions: list = field(default_factory=list)

    @property
    def row_universe_digest(self) -> str:
        return self.contract["row_universe_digest"]

    def rows(self, mask: Any = None) -> pd.DataFrame:
        return self.frame if mask is None else self.frame.loc[mask]


def _team_game_uid(df: pd.DataFrame) -> pd.Index:
    return pd.Index([f"{g}:{t}" for g, t in zip(df["game_id"], df["team_id"])],
                    name="team_game_uid")


def _realised_offensive_possessions(possessions_path: Path) -> pd.DataFrame:
    """Realised regulation-equivalent offensive possessions per team-game — the OUTCOME.

    Normalised exactly as ``build_projected_exposure.build_pace`` normalises its history, so the
    target is on the scale the frozen projection is expressed in. This is the model's target and
    it is not a feature: it is read here only so the gate can be handed a real ``target=`` and
    run the leakage checks that a missing target silently deletes.
    """
    p = pd.read_parquet(possessions_path, columns=["game_id", "period", "offense_team_id"])
    n_off = (p.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss")
             .reset_index().rename(columns={"offense_team_id": "team_id"}))
    max_period = p.groupby("game_id")["period"].max().rename("max_period").reset_index()
    n_off = n_off.merge(max_period, on="game_id", how="left", validate="m:1")
    game_minutes = REGULATION_MIN + 5.0 * np.maximum(0, n_off["max_period"] - 4)
    n_off[TARGET_COLUMN] = n_off["n_off_poss"] * REGULATION_MIN / game_minutes
    return n_off[["game_id", "team_id", TARGET_COLUMN]]


def load_universe(*, prior_path: str | Path = PRIOR_PARQUET,
                  possessions_path: str | Path = POSSESSIONS_PARQUET,
                  exposure_receipt_path: str | Path | None = EXPOSURE_RECEIPT,
                  exposure_validation_path: str | Path | None = EXPOSURE_VALIDATION,
                  possessions_receipt_path: str | Path | None = POSSESSIONS_RECEIPT,
                  repo_root: str | Path | None = None) -> PossessionUniverse:
    """Read the frozen artifacts READ-ONLY and return the shared, digested team-game universe.

    The paths are arguments so a test can point this at temp COPIES of the canonical parquets and
    perturb THOSE. The canonical bytes are never written by this module.
    """
    prior_path = Path(prior_path)
    possessions_path = Path(possessions_path)
    root = Path(repo_root) if repo_root is not None else ROOT

    sources = [
        cr.source_declaration(
            prior_path, role="feature_source", artifact_id="team_possession_prior/1",
            cutoff_valid=True,
            cutoff_rationale=(
                "prior-games-only by construction: every pace estimate in this artifact is a "
                "trailing-window mean over the club's STRICTLY EARLIER games, or a league mean "
                "over strictly earlier dates. Declared and validated upstream; this producer "
                "asserts the declaration and binds the bytes it read"),
            coverage={"rows": 2990, "unit": "team-game", "seasons": "2021-2026",
                      "note": "row count as published; re-derived from the bytes at load"},
            artifact_receipt=(None if exposure_receipt_path is None else {
                "path": exposure_receipt_path,
                "records_artifact_sha256_at": ["outputs", "team_possession_prior_v1.parquet",
                                               "sha256"]}),
            validation_receipt=(None if exposure_validation_path is None else {
                "path": exposure_validation_path,
                "records_artifact_sha256_at": ["artifact_sha256",
                                               "team_possession_prior_v1.parquet"],
                "verdict_at": ["verdict"]}),
            repo_root=root),
        cr.source_declaration(
            possessions_path, role="outcome_source", artifact_id="player_possessions/2",
            cutoff_valid=False,
            cutoff_rationale=(
                "REALISED possessions of the target game. Not cutoff-valid by definition and "
                "therefore contributes NO feature column. Read only to construct the model "
                "target, which is supplied to feature_gate as target= so that target_derived and "
                "the missingness checks can fire at all"),
            coverage={"unit": "possession", "role": "outcome"},
            artifact_receipt=(None if possessions_receipt_path is None else {
                "path": possessions_receipt_path,
                "records_artifact_sha256_at": ["integrity", "artifact_sha256"]}),
            repo_root=root),
    ]

    P = pd.read_parquet(prior_path)
    required = {"game_id", "team_id", "game_date", "season", "season_type", "pace_level",
                "pace_source", "n_history_games", "team_pace_estimate",
                "projected_team_off_possessions", "pace_resolved"}
    missing = sorted(required - set(P.columns))
    if missing:
        raise PossessionFeatureFailure(
            f"the frozen possession prior is missing expected columns: {missing}")

    side = P[["game_id", "team_id", "team_pace_estimate", "n_history_games", "pace_level"]]
    opp = side.rename(columns={"team_id": "opp_team_id",
                               "team_pace_estimate": "opp_pace_estimate",
                               "n_history_games": "opp_n_history_games",
                               "pace_level": "opp_pace_level"})
    pair = side.merge(opp, on="game_id")
    pair = pair[pair["team_id"] != pair["opp_team_id"]]
    if len(pair) != len(side):
        raise PossessionFeatureFailure(
            "opponent pairing did not produce exactly one opponent per team-game; the universe "
            "would not be a set of two-sided games")

    F = P.merge(pair[["game_id", "team_id", "opp_team_id", "opp_pace_estimate",
                      "opp_n_history_games", "opp_pace_level"]],
                on=["game_id", "team_id"], how="left", validate="1:1")

    n_before = int(len(F))
    F = F[F["pace_resolved"].astype(bool)].copy()
    restrictions = [{
        "restriction": "pace_resolved",
        "n_rows_before": n_before, "n_rows_after": int(len(F)),
        "n_rows_dropped": n_before - int(len(F)),
        "cutoff_valid": True,
        "reason": ("a team-game whose prior-games-only projection is unresolved has no incumbent "
                   "prediction to compare anything against. Resolvability depends only on games "
                   "STRICTLY EARLIER than the row's own date, so the restriction is itself known "
                   "at the decision time and does not select on the outcome"),
    }]

    target = _realised_offensive_possessions(possessions_path)
    F = F.merge(target, on=["game_id", "team_id"], how="left", validate="1:1")
    if F[TARGET_COLUMN].isna().any():
        raise PossessionFeatureFailure(
            f"{int(F[TARGET_COLUMN].isna().sum())} team-games in the universe have no realised "
            f"possession record; the target is not defined for every row")

    depth = np.where(np.isin(F["pace_level"].to_numpy(), TEAM_HISTORY_LEVELS),
                     np.minimum(F["n_history_games"].to_numpy(), WINDOW_K), 0)
    opp_depth = np.where(np.isin(F["opp_pace_level"].to_numpy(), TEAM_HISTORY_LEVELS),
                         np.minimum(F["opp_n_history_games"].to_numpy(), WINDOW_K), 0)
    F["pace_gap"] = F["team_pace_estimate"] - F["opp_pace_estimate"]
    F["pace_evidence_depth"] = depth.astype(float)
    F["opp_pace_evidence_depth"] = opp_depth.astype(float)
    F["is_playoff_game"] = (F["season_type"].astype(str) == "Playoffs").astype(float)
    F[OFFSET_COLUMN] = np.log(F["projected_team_off_possessions"].to_numpy(dtype=float))

    F = F.sort_values(["game_date", "game_id", "team_id"]).reset_index(drop=True)
    F.index = _team_game_uid(F)

    contract = cr.universe_contract(
        F, contract_id=UNIVERSE_CONTRACT_ID,
        row_identity_columns=list(ROW_IDENTITY_COLUMNS),
        description=(
            "every team-game of the frozen team_possession_prior_v1 artifact whose prior-games-"
            "only projection resolved, in chronological order. The SAME universe backs the "
            "incumbent input, the matched K0 input and the challenger feature frame"),
        restrictions=restrictions)

    return PossessionUniverse(frame=F, contract=contract, sources=sources,
                              paths={"prior": str(prior_path.resolve()),
                                     "possessions": str(possessions_path.resolve())},
                              restrictions=restrictions)


# --------------------------------------------------------------------------- #
# chronological folds
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class FoldSpec:
    """One chronological fold: train strictly before the cutoff, evaluate on the target season."""

    fold_id: str
    season: int
    cutoff_date: str
    train_index: pd.Index
    test_index: pd.Index

    @property
    def train_selector(self) -> str:
        return f"game_date < {self.cutoff_date} (season < {self.season})"

    @property
    def test_selector(self) -> str:
        return f"season == {self.season}"


def chronological_folds(u: PossessionUniverse) -> list[FoldSpec]:
    """Expanding-window folds, one per season that has at least one strictly earlier season.

    The cutoff is the first game date of the target season, and the training rows are the rows
    whose own game_date is strictly before it. Nothing in a training row was computed from a game
    on or after the cutoff, because nothing in any row was computed from a game on or after its
    own date.
    """
    F = u.frame
    seasons = sorted(int(s) for s in F["season"].unique())
    out: list[FoldSpec] = []
    for s in seasons[1:]:
        cutoff = F.loc[F["season"] == s, "game_date"].min()
        train = F.index[F["game_date"] < cutoff]
        test = F.index[F["season"] == s]
        if not len(train) or not len(test):
            continue
        out.append(FoldSpec(fold_id=f"train_lt_{s}", season=int(s),
                            cutoff_date=str(pd.Timestamp(cutoff).date()),
                            train_index=train, test_index=test))
    return out


# --------------------------------------------------------------------------- #
# the three Stage 2 inputs, all drawn from the ONE universe (parity, amendment §3)
# --------------------------------------------------------------------------- #

def challenger_input(u: PossessionUniverse, rows: pd.Index | None = None) -> tuple[pd.DataFrame,
                                                                                  list[str]]:
    """The incumbent-EQUIVALENT feature frame. No Stage 2 hypothesis is invented here."""
    F = u.frame if rows is None else u.frame.loc[rows]
    return F.loc[:, list(CARRIED_NOT_FEATURES) + list(FEATURE_NAMES) + [TARGET_COLUMN]], \
        list(FEATURE_NAMES)


def incumbent_input(u: PossessionUniverse, rows: pd.Index | None = None) -> tuple[pd.DataFrame,
                                                                                 list[str]]:
    """The incumbent prediction input: the frozen projection itself, carried as the exposure.

    The incumbent has no fitted feature — its prediction IS ``projected_team_off_possessions`` —
    so its declared feature set is empty and its exposure is the same offset every other input
    uses. Drawn from the same universe so the comparison is about models and not about rows.
    """
    F = u.frame if rows is None else u.frame.loc[rows]
    return F.loc[:, list(CARRIED_NOT_FEATURES) + [TARGET_COLUMN]], []


def k0_input(u: PossessionUniverse, rows: pd.Index | None = None) -> tuple[pd.DataFrame,
                                                                          list[str]]:
    """The matched K0 control: same rows, same offset, empty feature set.

    ``feature_gate.design_rank_report`` provides for exactly this and calls it trivially
    identified. K0 exists so a challenger's difference from the incumbent can be read against a
    control that shares its universe rather than against a differently-drawn one.
    """
    return incumbent_input(u, rows)


def parity_report(u: PossessionUniverse, rows: pd.Index | None = None) -> dict:
    """Prove the three inputs are about the same rows, in the same order. Raises if they are not.

    This is the check that keeps the new producer from documenting the challenger path while the
    incumbent comparison quietly runs off an unaudited row universe.
    """
    built = {}
    for label, fn in (("incumbent", incumbent_input), ("k0", k0_input),
                      ("challenger", challenger_input)):
        frame, names = fn(u, rows)
        built[label] = {
            "n_rows": int(len(frame)),
            "n_features": len(names),
            "features": list(names),
            "row_universe_digest": cr.index_digest(frame.index, sort=True,
                                                   label="raw_index_membership"),
            "row_order_digest": cr.index_digest(frame.index, label="raw_index"),
            "offset_digest": cr.values_digest(frame[OFFSET_COLUMN], label="offset_values"),
            "target_digest": cr.values_digest(frame[TARGET_COLUMN], label="target_values"),
        }
    keys = ("row_universe_digest", "row_order_digest", "offset_digest", "target_digest")
    diverging = [k for k in keys if len({built[b][k] for b in built}) != 1]
    rep = {"universe_contract_id": u.contract["universe_contract_id"],
           "declared_universe_digest": u.contract["row_universe_digest"],
           "inputs": built, "diverging_fields": diverging,
           "parity": not diverging,
           "note": ("incumbent, K0 and challenger must be drawn from ONE digested universe; a "
                    "challenger documented against rows the incumbent never saw reproduces the "
                    "parity defect one level up")}
    if diverging:
        raise PossessionFeatureFailure(
            f"incumbent / K0 / challenger inputs diverge on {diverging}; they are not comparable")
    return rep


# --------------------------------------------------------------------------- #
# construction, with the receipt emitted BY THIS PRODUCER
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ConstructedFrame:
    """What the producer hands downstream: the frame, its arguments, and its receipt PATH.

    The path is the point. A consumer receives a location on disk, not a mapping, and everything
    the receipt asserts is re-derived from files at the moment it is presented.
    """

    fold_id: str
    scope: str
    frame: pd.DataFrame
    feature_names: list
    offset: pd.Series
    target: pd.Series
    outcome_mask: pd.Series
    test_frame: pd.DataFrame | None
    receipt_path: Path
    receipt: dict
    cutoff: dict
    universe_contract: dict

    @property
    def fitted_matrix(self) -> pd.DataFrame:
        return self.frame.loc[:, self.feature_names]


def _outcome_mask(frame: pd.DataFrame) -> pd.Series:
    """The rows whose realised possession count is observed.

    It is constant TRUE over this universe and that is a fact about team-games, not a placeholder:
    every team-game that was played has a realised possession count, so there is no analogue of
    the player-level "did not appear" row. The mask is supplied truthfully rather than fabricated,
    and the gate's ``argument_is_placeholder_default`` finding against it is adjudicated at the
    invocation site WITH A STATED REASON rather than dodged by withholding the argument.
    """
    return pd.Series(frame[TARGET_COLUMN].notna().to_numpy(), index=frame.index,
                     name="target_observed")


def construct(u: PossessionUniverse, *, receipt_dir: str | Path, run_id: str,
              fold: FoldSpec | None = None,
              experiment: str = EXPERIMENT, arm: str = ARM,
              producer_path: str | Path | None = None,
              repo_root: str | Path | None = None) -> ConstructedFrame:
    """Build ONE fold's design (or the final assembled design) and emit its construction receipt.

    ``fold=None`` builds the final assembled design over the whole universe. The receipt is
    written before this function returns; if it cannot be written,
    ``construction_receipt.ConstructionReceiptFailure`` propagates and NO frame is returned, which
    is the intended shape — a frame whose construction was never recorded must not reach a fitter.
    """
    scope = "fold" if fold is not None else "final_design"
    fold_id = fold.fold_id if fold is not None else "final_design"
    rows = fold.train_index if fold is not None else u.frame.index

    frame, names = challenger_input(u, rows)
    offset = frame[OFFSET_COLUMN].rename("log_exposure")
    target = frame[TARGET_COLUMN].rename("realised_off_possessions")
    mask = _outcome_mask(frame)
    test_frame = None
    if fold is not None:
        test_frame, _ = challenger_input(u, fold.test_index)

    fold_rows_universe = cr.universe_contract(
        frame, contract_id=UNIVERSE_CONTRACT_ID,
        row_identity_columns=list(ROW_IDENTITY_COLUMNS),
        description=u.contract["description"],
        restrictions=list(u.restrictions) + ([{
            "restriction": "chronological_fold",
            "fold_id": fold.fold_id, "cutoff_date": fold.cutoff_date,
            "selector": fold.train_selector, "cutoff_valid": True,
            "reason": "training rows are strictly earlier than the fold cutoff",
        }] if fold is not None else [{
            "restriction": "final_assembled_design", "cutoff_valid": True,
            "selector": "every resolved team-game in the universe",
            "reason": "the pooled construction, audited in addition to and never instead of the "
                      "per-fold ones",
        }]))

    cutoff = cr.cutoff_contract(
        decision_time_rule=DECISION_TIME_RULE,
        per_row_decision_time_column=DECISION_TIME_COLUMN,
        fold_cutoff=(fold.cutoff_date if fold is not None else None),
        target_cutoff=(fold.cutoff_date if fold is not None else
                       str(pd.Timestamp(u.frame["game_date"].max()).date())),
        notes=("the final assembled design has no forward cutoff: it is the pooled construction "
               "over everything the frozen artifact resolves"
               if fold is None else
               "training rows are strictly earlier than the cutoff; the held-out frame is the "
               "target season"))

    fold_ident = cr.fold_declaration(
        fold_id=fold_id, kind=scope, n_rows=int(len(frame)),
        first_decision_time=str(pd.Timestamp(frame["game_date"].min()).date()),
        last_decision_time=str(pd.Timestamp(frame["game_date"].max()).date()),
        train_selector=(fold.train_selector if fold is not None
                        else "every resolved team-game"),
        test_selector=(fold.test_selector if fold is not None else None),
        n_test_rows=(int(len(test_frame)) if test_frame is not None else None))

    receipt_path = Path(receipt_dir) / f"CONSTRUCTION_RECEIPT__{experiment}__{arm}__{fold_id}.json"
    receipt = cr.emit_construction_receipt(
        receipt_path=receipt_path,
        experiment=experiment, arm=arm, fold=fold_id, scope=scope, run_id=run_id,
        frame=frame, feature_names=names,
        universe=fold_rows_universe, fold_identity=fold_ident, cutoff=cutoff,
        sources=u.sources, feature_set_id=FEATURE_SET_ID,
        transformation=None,
        gate_arguments={"offset": offset, "target": target, "outcome_mask": mask},
        output={"kind": "frame", "digest": cr.matrix_digest(frame, names),
                "note": "no artifact is written; the frame IS the output"},
        generation_result="ok",
        producer_path=producer_path, repo_root=repo_root,
        claim_boundary_additions=CLAIM_BOUNDARY_ADDITION,
        notes={
            "universe_contract": {k: u.contract[k] for k in
                                  ("universe_contract_id", "row_universe_digest", "n_rows")},
            "excluded_columns_and_why": {
                "projected_team_off_possessions": "it is the exposure offset, not a feature",
                "team_pace_estimate + opp_pace_estimate": "the pair spans the offset; their "
                                                          "difference does not",
                "data/masters/master_team.parquet": "realised target-game box score; every column "
                                                    "is an outcome of the game being predicted",
                "n_history_games (raw)": "mixes a trailing-window count with a cumulative league "
                                         "count reaching 1300",
            },
            "target_is_not_a_feature": {
                "target_column": TARGET_COLUMN,
                "in_feature_names": TARGET_COLUMN in names,
                "source_role": "outcome_source",
            },
        })

    return ConstructedFrame(fold_id=fold_id, scope=scope, frame=frame, feature_names=list(names),
                            offset=offset, target=target, outcome_mask=mask,
                            test_frame=test_frame, receipt_path=receipt_path, receipt=receipt,
                            cutoff=cutoff, universe_contract=fold_rows_universe)


def construct_all(u: PossessionUniverse, *, receipt_dir: str | Path, run_id: str,
                  experiment: str = EXPERIMENT, arm: str = ARM,
                  producer_path: str | Path | None = None,
                  repo_root: str | Path | None = None) -> list[ConstructedFrame]:
    """Every chronological fold AND the final assembled design, each with its own receipt."""
    out = [construct(u, receipt_dir=receipt_dir, run_id=run_id, fold=f, experiment=experiment,
                     arm=arm, producer_path=producer_path, repo_root=repo_root)
           for f in chronological_folds(u)]
    out.append(construct(u, receipt_dir=receipt_dir, run_id=run_id, fold=None,
                         experiment=experiment, arm=arm, producer_path=producer_path,
                         repo_root=repo_root))
    return out


# --------------------------------------------------------------------------- #
# the invocation-site declarations this producer's frames require
# --------------------------------------------------------------------------- #

#: the outcome mask is constant over this universe, truthfully. Withholding it would delete the
#: exact-indicator branch silently; supplying it and adjudicating states the same fact out loud
#: and carries the reason in the record forever.
OUTCOME_MASK_ADJUDICATION = {
    "outcome_mask:argument_is_placeholder_default": {
        "reason": ("every team-game that was played has a realised possession count, so the "
                   "outcome mask is constant TRUE over this universe as a fact about team-games "
                   "rather than as a placeholder. The exact-indicator branch of "
                   "missingness_encodes_outcome is consequently dead here, and that is recorded "
                   "rather than hidden by withholding the argument. The raw frame carries no "
                   "missingness at all, which the receipt's per-column mask digests attest")},
}

#: the final assembled design has no forward frame to check schema drift against.
FINAL_DESIGN_NOT_APPLICABLE = {
    "test_df": ("the final assembled design is the pooled construction over every resolved "
                "team-game; there is no held-out frame after it. schema_mismatch is therefore "
                "unfireable and the record is marked INCOMPLETE rather than passed as if the "
                "check had run"),
}


def gate_kwargs(c: ConstructedFrame) -> dict:
    """The exact keyword arguments ``gate_invocation.audit_fold`` needs for this frame.

    Assembled by the PRODUCER, from the objects it constructed, including the path of the receipt
    it emitted. The caller does not hand-build a provenance mapping, which is the whole point.

    The frame is emitted and fitted unchanged, so the declaration is Case 1: ``raw_df`` is the same
    object and ``transformation`` asserts ``kind: none``, which the wrapper then PROVES by digest
    rather than believing. No imputation occurs anywhere in this producer — the universe is
    restricted to rows whose prior resolved, and the receipt's per-column mask digests attest that
    the raw frame carries no missingness at all.
    """
    import gate_invocation as gi

    kw: dict[str, Any] = {
        "experiment": c.receipt["identity"]["experiment"],
        "arm": c.receipt["identity"]["arm"],
        "fold": c.fold_id,
        "scope": c.scope,
        "offset": c.offset,
        "target": c.target,
        "outcome_mask": c.outcome_mask,
        "raw_df": c.frame,
        "transformation": gi.no_transformation(
            "this producer emits the frame and it is fitted unchanged: no imputation, no "
            "rescaling and no re-encoding occurs between construction and the fitter. Declared so "
            "the identity of the pre-transformation and fitted frames is proven by digest rather "
            "than assumed"),
        "fitted_matrix": c.fitted_matrix,
        "construction_receipt": str(c.receipt_path),
        "adjudications": dict(OUTCOME_MASK_ADJUDICATION),
    }
    if c.test_frame is not None:
        kw["test_df"] = c.test_frame
    else:
        kw["not_applicable"] = dict(FINAL_DESIGN_NOT_APPLICABLE)
    return kw


# --------------------------------------------------------------------------- #
# dry execution
# --------------------------------------------------------------------------- #

def dry_run(receipt_dir: str | Path | None = None, *, run_id: str = "possession_features_dry",
            verbose: bool = True) -> dict:
    """Construct every fold and the final design, verify each receipt, and audit through the gate.

    Nothing is fitted. No projection is compared against any realised value and no accuracy,
    error or skill statistic is computed: the only verdicts here are gate verdicts.
    """
    import gate_invocation as gi

    tmp = None
    if receipt_dir is None:
        tmp = tempfile.mkdtemp(prefix="possession_construction_")
        receipt_dir = tmp
    receipt_dir = Path(receipt_dir)

    before = {k: cr._sha256_file(v) for k, v in
              {"team_possession_prior_v1.parquet": PRIOR_PARQUET,
               "possessions_raw_v2.parquet": POSSESSIONS_PARQUET}.items()}

    u = load_universe()
    parity = parity_report(u)
    built = construct_all(u, receipt_dir=receipt_dir, run_id=run_id)

    results = []
    for c in built:
        verification = cr.verify_construction_receipt(
            c.receipt_path, frame=c.frame, feature_names=c.feature_names,
            experiment=EXPERIMENT, arm=ARM, fold=c.fold_id, scope=c.scope,
            universe=c.universe_contract, cutoff=c.cutoff,
            gate_arguments={"offset": c.offset, "target": c.target,
                            "outcome_mask": c.outcome_mask},
            fitted_frame=c.fitted_matrix)
        rep = gi.audit_fold(c.frame, c.feature_names, raise_on_block=False, **gate_kwargs(c))
        results.append({
            "fold": c.fold_id, "scope": c.scope,
            "n_rows": int(len(c.frame)),
            "n_test_rows": (int(len(c.test_frame)) if c.test_frame is not None else None),
            "receipt_path": str(c.receipt_path),
            "receipt_digest": c.receipt["binding"]["receipt_digest"],
            "receipt_verified": verification["verified"],
            "receipt_blocking": sorted({f["kind"] for f in verification["blocking"]}),
            "gate_passed": rep["passed"],
            "gate_invoked": rep["gate_invoked"],
            "assurance": rep["assurance"],
            "stage1_pass": rep["stage1_pass"],
            "complete": rep["complete"],
            "checks_not_run": rep["checks_not_run"],
            "blocking": sorted({f["kind"] for f in rep["blocking"]}),
            "gate_findings": sorted({f["kind"] for f in rep.get("gate_findings", [])}),
        })

    after = {k: cr._sha256_file(v) for k, v in
             {"team_possession_prior_v1.parquet": PRIOR_PARQUET,
              "possessions_raw_v2.parquet": POSSESSIONS_PARQUET}.items()}

    out = {
        "schema": "possession_features.dry_run/1",
        "run_id": run_id,
        "receipt_dir": str(receipt_dir),
        "nothing_fitted": True,
        "nothing_scored": True,
        "no_accuracy_computed": (
            "this module compares no projection against any realised possession; the realised "
            "count is read only to supply feature_gate's target= argument"),
        "canonical_artifact_hashes_before": before,
        "canonical_artifact_hashes_after": after,
        "canonical_artifacts_unchanged": before == after,
        "universe": {k: u.contract[k] for k in
                     ("universe_contract_id", "n_rows", "row_universe_digest", "row_order_digest")},
        "parity": parity,
        "folds": results,
        "assurance_by_fold": {r["fold"]: r["assurance"] for r in results},
    }
    if verbose:
        _print_dry_run(out)
    if tmp:
        out["receipt_dir_note"] = ("receipts were written to a temporary directory; nothing was "
                                   "written into the repository")
    return out


def _print_dry_run(out: Mapping[str, Any]) -> None:      # pragma: no cover - descriptive
    print("=" * 100)
    print("possession_features — REAL possession-prior construction, gated end to end")
    print("=" * 100)
    print(f"universe            : {out['universe']['universe_contract_id']}  "
          f"n_rows={out['universe']['n_rows']}")
    print(f"universe digest     : {out['universe']['row_universe_digest']}")
    print(f"incumbent/K0/challenger parity : {out['parity']['parity']}")
    print(f"canonical artifacts unchanged  : {out['canonical_artifacts_unchanged']}")
    for k, v in out["canonical_artifact_hashes_before"].items():
        print(f"    {k:<34} {v}")
    print()
    print(f"{'fold':<16}{'rows':>7}{'test':>7}  {'receipt':<9}{'gate':<7}"
          f"{'assurance':<26}{'stage1':<8}complete")
    for r in out["folds"]:
        print(f"{r['fold']:<16}{r['n_rows']:>7}"
              f"{(r['n_test_rows'] if r['n_test_rows'] is not None else 0):>7}  "
              f"{('verified' if r['receipt_verified'] else 'BLOCKED'):<9}"
              f"{('pass' if r['gate_passed'] else 'BLOCK'):<7}"
              f"{r['assurance']:<26}{str(r['stage1_pass']):<8}{r['complete']}")
        if r["blocking"]:
            print(f"{'':<16}blocking: {r['blocking']}")
        if r["checks_not_run"]:
            print(f"{'':<16}checks not run: {r['checks_not_run']}")
    print("=" * 100)
    print("CLAIM BOUNDARY: this establishes producer-backed provenance for the Stage 2 possession")
    print("feature frame DERIVED FROM the frozen artifacts. It does NOT re-establish how")
    print("team_possession_prior_v1.parquet itself was constructed; that remains attested by its")
    print("own artifact and validation receipts only.")
    print("=" * 100)


def _main(argv: Sequence[str] | None = None) -> int:              # pragma: no cover - descriptive
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--receipt-dir", default=None,
                    help="where construction receipts are written; a temporary directory by "
                         "default, so a dry run writes nothing into the repository")
    ap.add_argument("--json", action="store_true", help="print the machine-readable report")
    a = ap.parse_args(list(argv) if argv is not None else None)
    out = dry_run(a.receipt_dir, verbose=not a.json)
    if a.json:
        print(json.dumps(out, indent=2, default=str))
    ok = (out["canonical_artifacts_unchanged"] and out["parity"]["parity"]
          and all(r["receipt_verified"] and r["gate_passed"] for r in out["folds"]))
    return 0 if ok else 1


if __name__ == "__main__":                                       # pragma: no cover
    try:
        raise SystemExit(_main())
    except (PossessionFeatureFailure, cr.ConstructionReceiptFailure) as exc:
        print(f"PRODUCER FAILED CLOSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
