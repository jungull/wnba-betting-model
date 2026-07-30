"""Time-ordered splitters + locked holdout — no timestamp ambiguity, ever.

Implements ROADMAP "Phase 0.5 — Point-in-time & evaluation certification":

    "Outer walk-forward evaluation; inner walk-forward tuning strictly inside
    the training period; a separate calibration window disjoint from model
    fitting; a locked final holdout touched once (declared in the registry the
    day it is first used)."

Every split object is validated at construction: ``max(train_time) <
min(test_time)`` strictly, disjoint index sets, non-empty sides. A split that
cannot prove its own time ordering raises LeakageError instead of existing.
Splits are cut on whole calendar dates so same-date games never straddle a
boundary (same-date games share news/market environment — see compare.py).

Constitution (HANDOFF §3) rule 2 backdrop: "Walk-forward always."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from . import registry as _reg


class LeakageError(Exception):
    """A split (or tuning setup) would let information flow backward in time."""


class HoldoutError(Exception):
    """Base class for locked-holdout violations."""


class HoldoutNotDeclaredError(HoldoutError):
    pass


class HoldoutNotClaimedError(HoldoutError):
    """Holdout rows requested without a registered, recorded claim."""


class HoldoutAlreadyClaimedError(HoldoutError):
    """The single permitted use of the holdout has already been spent."""


# ---------------------------------------------------------------------------
# split containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OuterSplit:
    """One outer walk-forward fold. Construction proves its own time order."""

    name: str
    train_idx: np.ndarray          # df.index labels
    test_idx: np.ndarray
    train_start: pd.Timestamp
    train_end: pd.Timestamp        # max event date in train
    test_start: pd.Timestamp       # min event date in test
    test_end: pd.Timestamp

    def __post_init__(self):
        _validate_pair(
            self.train_idx, self.test_idx, self.train_end, self.test_start,
            what=f"outer split {self.name!r}",
        )


@dataclass(frozen=True)
class InnerSplit:
    """One inner tuning fold, strictly inside an outer training window."""

    name: str
    train_idx: np.ndarray
    val_idx: np.ndarray
    train_end: pd.Timestamp
    val_start: pd.Timestamp
    val_end: pd.Timestamp

    def __post_init__(self):
        _validate_pair(
            self.train_idx, self.val_idx, self.train_end, self.val_start,
            what=f"inner split {self.name!r}",
        )


@dataclass(frozen=True)
class CalibrationSplit:
    """Outer-train window partitioned into model-fit rows and a calibration
    carve-out. The calibration window is disjoint from model fitting and
    strictly later in time (fit < calib < outer test)."""

    name: str
    fit_idx: np.ndarray
    calib_idx: np.ndarray
    fit_end: pd.Timestamp
    calib_start: pd.Timestamp
    calib_end: pd.Timestamp

    def __post_init__(self):
        _validate_pair(
            self.fit_idx, self.calib_idx, self.fit_end, self.calib_start,
            what=f"calibration carve-out {self.name!r}",
        )


def _validate_pair(early_idx, late_idx, early_end, late_start, *, what):
    if len(early_idx) == 0 or len(late_idx) == 0:
        raise LeakageError(f"{what}: empty side (train={len(early_idx)}, "
                           f"test/val={len(late_idx)})")
    overlap = np.intersect1d(early_idx, late_idx)
    if len(overlap):
        raise LeakageError(f"{what}: {len(overlap)} rows appear on both sides "
                           f"(e.g. {overlap[:5].tolist()})")
    if not (early_end < late_start):
        raise LeakageError(
            f"{what}: max(train_time)={early_end} is not strictly before "
            f"min(test_time)={late_start}. Walk-forward always (HANDOFF §3.2)."
        )


# ---------------------------------------------------------------------------
# input hygiene
# ---------------------------------------------------------------------------

def _dates(df: pd.DataFrame, date_col: str) -> pd.Series:
    if date_col not in df.columns:
        raise KeyError(f"date column {date_col!r} not in frame")
    if not df.index.is_unique:
        raise ValueError("frame index must be unique for split bookkeeping")
    d = pd.to_datetime(df[date_col], errors="coerce")
    if d.isna().any():
        bad = df.index[d.isna()][:5].tolist()
        raise ValueError(
            f"{int(d.isna().sum())} rows have unparseable {date_col!r} "
            f"(e.g. index {bad}). A feature row whose availability time cannot "
            "be established is not a feature (ROADMAP prediction contract); "
            "same rule for evaluation rows."
        )
    return d.dt.normalize()


# ---------------------------------------------------------------------------
# outer splitters
# ---------------------------------------------------------------------------

def walk_forward_by_season(
    df: pd.DataFrame,
    *,
    date_col: str = "game_date",
    season_col: str = "season",
    min_train_seasons: int = 1,
    test_seasons: Optional[Sequence] = None,
) -> list[OuterSplit]:
    """Outer walk-forward by season: for each test season, train on ALL strictly
    earlier seasons (expanding). Seasons are ordered by their first game date;
    a season whose dates interleave with a "later" season is a data bug and
    raises LeakageError at construction.
    """
    if season_col not in df.columns:
        raise KeyError(f"season column {season_col!r} not in frame")
    dates = _dates(df, date_col)
    order = (
        pd.DataFrame({"season": df[season_col].values, "date": dates.values})
        .groupby("season")["date"].min().sort_values()
    )
    seasons = list(order.index)
    if len(seasons) < min_train_seasons + 1:
        raise ValueError(
            f"need at least {min_train_seasons + 1} seasons, have {len(seasons)}"
        )
    wanted = set(test_seasons) if test_seasons is not None else None
    splits: list[OuterSplit] = []
    for i in range(min_train_seasons, len(seasons)):
        s_test = seasons[i]
        if wanted is not None and s_test not in wanted:
            continue
        train_mask = df[season_col].isin(seasons[:i]).values
        test_mask = (df[season_col] == s_test).values
        splits.append(OuterSplit(
            name=f"season:{s_test}",
            train_idx=df.index[train_mask].to_numpy(),
            test_idx=df.index[test_mask].to_numpy(),
            train_start=dates[train_mask].min(),
            train_end=dates[train_mask].max(),
            test_start=dates[test_mask].min(),
            test_end=dates[test_mask].max(),
        ))
    if not splits:
        raise ValueError("no outer splits produced (check test_seasons filter)")
    return splits


def walk_forward_by_date_blocks(
    df: pd.DataFrame,
    *,
    date_col: str = "game_date",
    block_days: int = 14,
    min_train_days: int = 60,
    max_splits: Optional[int] = None,
) -> list[OuterSplit]:
    """Outer walk-forward by rolling date blocks: consecutive ``block_days``
    calendar-day test blocks; train = every row strictly before the block start
    (expanding window). Blocks are aligned to observed unique dates so a date
    never straddles a boundary."""
    if block_days < 1 or min_train_days < 1:
        raise ValueError("block_days and min_train_days must be >= 1")
    dates = _dates(df, date_col)
    uniq = np.sort(dates.unique())
    t0 = uniq[0]
    first_test_day = t0 + pd.Timedelta(days=min_train_days)
    splits: list[OuterSplit] = []
    block_start = first_test_day
    last_day = uniq[-1]
    k = 0
    while block_start <= last_day:
        block_end = block_start + pd.Timedelta(days=block_days - 1)
        test_mask = ((dates >= block_start) & (dates <= block_end)).values
        train_mask = (dates < block_start).values
        if test_mask.any() and train_mask.any():
            k += 1
            splits.append(OuterSplit(
                name=f"block:{pd.Timestamp(block_start).date()}",
                train_idx=df.index[train_mask].to_numpy(),
                test_idx=df.index[test_mask].to_numpy(),
                train_start=dates[train_mask].min(),
                train_end=dates[train_mask].max(),
                test_start=dates[test_mask].min(),
                test_end=dates[test_mask].max(),
            ))
            if max_splits is not None and k >= max_splits:
                break
        block_start = block_end + pd.Timedelta(days=1)
    if not splits:
        raise ValueError("no date-block splits produced; loosen min_train_days")
    return splits


# ---------------------------------------------------------------------------
# inner tuning splitter (strictly inside the outer-train window)
# ---------------------------------------------------------------------------

def inner_tuning_splits(
    df: pd.DataFrame,
    outer: OuterSplit,
    *,
    date_col: str = "game_date",
    n_folds: int = 3,
    candidate_idx: Optional[Iterable] = None,
) -> list[InnerSplit]:
    """Inner walk-forward tuning folds that live STRICTLY inside
    ``outer.train_idx`` (ROADMAP Phase 0.5: "inner walk-forward tuning strictly
    inside the training period").

    ``candidate_idx`` defaults to the whole outer-train window. Passing any row
    that is not part of outer-train — in particular rows from the outer TEST
    period — raises LeakageError before a single fold is produced. Tuning on
    test dates is how a model "wins" through timestamp ambiguity; the harness
    makes that setup unrepresentable.

    Folds: outer-train unique dates are cut into ``n_folds + 1`` contiguous
    segments; fold i trains on segments [0..i] and validates on segment i+1
    (expanding walk-forward, features reset rules are the caller's job).
    """
    if n_folds < 1:
        raise ValueError("n_folds must be >= 1")
    dates = _dates(df, date_col)
    outer_train = np.asarray(outer.train_idx)
    if candidate_idx is None:
        cand = outer_train
    else:
        cand = np.asarray(list(candidate_idx))
        missing = np.setdiff1d(cand, df.index.to_numpy())
        if len(missing):
            raise KeyError(f"candidate_idx rows not in frame: {missing[:5].tolist()}")
        outside = np.setdiff1d(cand, outer_train)
        if len(outside):
            when = dates.loc[outside]
            n_test_period = int((when >= outer.test_start).sum())
            raise LeakageError(
                f"inner tuning candidate set contains {len(outside)} rows outside "
                f"the outer training window ({n_test_period} of them at/after the "
                f"outer test start {outer.test_start.date()}). Inner tuning must "
                "operate strictly within outer-train (ROADMAP Phase 0.5)."
            )
    cand_dates = dates.loc[cand]
    uniq = np.sort(cand_dates.unique())
    if len(uniq) < n_folds + 1:
        raise ValueError(
            f"only {len(uniq)} unique dates in the tuning window; need >= "
            f"{n_folds + 1} for {n_folds} walk-forward folds"
        )
    edges = np.array_split(uniq, n_folds + 1)
    folds: list[InnerSplit] = []
    for i in range(n_folds):
        train_days = np.concatenate(edges[: i + 1])
        val_days = edges[i + 1]
        tr_mask = cand_dates.isin(train_days)
        va_mask = cand_dates.isin(val_days)
        folds.append(InnerSplit(
            name=f"{outer.name}/inner{i + 1}",
            train_idx=cand[tr_mask.values],
            val_idx=cand[va_mask.values],
            train_end=cand_dates[tr_mask].max(),
            val_start=cand_dates[va_mask].min(),
            val_end=cand_dates[va_mask].max(),
        ))
        # belt-and-suspenders: validation must also precede the outer test
        if not (folds[-1].val_end < outer.test_start):
            raise LeakageError(
                f"inner fold {folds[-1].name} validates at "
                f"{folds[-1].val_end.date()}, not strictly before outer test "
                f"start {outer.test_start.date()}"
            )
    return folds


# ---------------------------------------------------------------------------
# calibration carve-out (disjoint from model fit)
# ---------------------------------------------------------------------------

def calibration_carveout(
    df: pd.DataFrame,
    outer: OuterSplit,
    *,
    date_col: str = "game_date",
    calib_frac: float = 0.2,
    calib_days: Optional[int] = None,
) -> CalibrationSplit:
    """Carve the LAST slice of the outer-train window off for calibration.

    ROADMAP Phase 0.5: "a separate calibration window disjoint from model
    fitting". The model fits on fit_idx only; the calibration map (Platt /
    isotonic / hierarchical — an open competition, ROADMAP "Metrics") fits on
    calib_idx only; both strictly precede the outer test window.

    ``calib_days`` (calendar days from the end of train) wins over
    ``calib_frac`` (fraction of unique train dates) when given.
    """
    dates = _dates(df, date_col)
    tr = np.asarray(outer.train_idx)
    tr_dates = dates.loc[tr]
    uniq = np.sort(tr_dates.unique())
    if calib_days is not None:
        if calib_days < 1:
            raise ValueError("calib_days must be >= 1")
        cut = tr_dates.max() - pd.Timedelta(days=calib_days - 1)
        calib_day_set = uniq[uniq >= cut]
    else:
        if not (0.0 < calib_frac < 1.0):
            raise ValueError("calib_frac must be in (0, 1)")
        n_cal = max(1, int(round(len(uniq) * calib_frac)))
        if n_cal >= len(uniq):
            n_cal = len(uniq) - 1
        calib_day_set = uniq[len(uniq) - n_cal:]
    cal_mask = tr_dates.isin(calib_day_set)
    fit_idx = tr[~cal_mask.values]
    calib_idx = tr[cal_mask.values]
    if len(fit_idx) == 0 or len(calib_idx) == 0:
        raise LeakageError(
            f"calibration carve-out for {outer.name!r} produced an empty side; "
            "shrink calib_frac / calib_days"
        )
    return CalibrationSplit(
        name=f"{outer.name}/calib",
        fit_idx=fit_idx,
        calib_idx=calib_idx,
        fit_end=tr_dates[~cal_mask].max(),
        calib_start=tr_dates[cal_mask].min(),
        calib_end=tr_dates[cal_mask].max(),
    )


# ---------------------------------------------------------------------------
# locked final holdout — touched once, claim recorded in the registry
# ---------------------------------------------------------------------------

def declare_holdout(
    name: str,
    *,
    seasons: Optional[Sequence] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    description: str = "",
    registry_path: "Path | str | None" = None,
) -> dict:
    """Declare a locked holdout (a season set and/or date range) in the
    registry. ROADMAP Phase 0.5: "a locked final holdout touched once
    (declared in the registry the day it is first used)".

    Declaration only defines the rows; it does NOT expose them. Redeclaring an
    existing name raises — the definition is immutable.
    """
    if seasons is None and date_start is None and date_end is None:
        raise ValueError("holdout needs seasons and/or a date range")
    if get_holdout_declaration(name, registry_path=registry_path, missing_ok=True):
        raise HoldoutError(f"holdout {name!r} already declared; declarations are immutable")
    record = {
        "kind": "holdout_declared",
        "holdout_name": str(name),
        "seasons": list(seasons) if seasons is not None else None,
        "date_start": str(pd.Timestamp(date_start).date()) if date_start else None,
        "date_end": str(pd.Timestamp(date_end).date()) if date_end else None,
        "description": description,
    }
    return _reg.append_record(record, registry_path)


def get_holdout_declaration(
    name: str, *, registry_path: "Path | str | None" = None, missing_ok: bool = False
) -> Optional[dict]:
    for r in _reg.read_records(registry_path):
        if r.get("kind") == "holdout_declared" and r.get("holdout_name") == name:
            return r
    if missing_ok:
        return None
    raise HoldoutNotDeclaredError(
        f"holdout {name!r} has no declaration record; declare_holdout() first"
    )


def get_holdout_claim(
    name: str, *, registry_path: "Path | str | None" = None
) -> Optional[dict]:
    for r in _reg.read_records(registry_path):
        if r.get("kind") == "holdout_claimed" and r.get("holdout_name") == name:
            return r
    return None


def holdout_mask(
    df: pd.DataFrame,
    name: str,
    *,
    date_col: str = "game_date",
    season_col: str = "season",
    registry_path: "Path | str | None" = None,
) -> pd.Series:
    """Boolean mask of rows belonging to the declared holdout (no exposure —
    masks are needed to STRIP the holdout from working data)."""
    decl = get_holdout_declaration(name, registry_path=registry_path)
    mask = pd.Series(True, index=df.index)
    if decl.get("seasons") is not None:
        if season_col not in df.columns:
            raise KeyError(f"season column {season_col!r} required by holdout {name!r}")
        # registry round-trips through JSON, so compare as strings
        wanted = {str(s) for s in decl["seasons"]}
        mask &= df[season_col].astype(str).isin(wanted)
    if decl.get("date_start") or decl.get("date_end"):
        d = _dates(df, date_col)
        if decl.get("date_start"):
            mask &= d >= pd.Timestamp(decl["date_start"])
        if decl.get("date_end"):
            mask &= d <= pd.Timestamp(decl["date_end"])
    return mask


def strip_holdout(
    df: pd.DataFrame,
    name: str,
    *,
    date_col: str = "game_date",
    season_col: str = "season",
    registry_path: "Path | str | None" = None,
) -> pd.DataFrame:
    """Return the frame WITHOUT holdout rows. This is the routine entry point:
    all development happens on stripped data; the holdout stays dark."""
    m = holdout_mask(df, name, date_col=date_col, season_col=season_col,
                     registry_path=registry_path)
    return df.loc[~m]


def claim_holdout(
    name: str,
    experiment_id: str,
    *,
    registry_path: "Path | str | None" = None,
    note: str = "",
) -> dict:
    """Irreversibly spend the holdout's single use on one registered experiment.

    Appends a claim record to the append-only registry. A second claim — by any
    experiment, ever — raises HoldoutAlreadyClaimedError. There is no unclaim.
    """
    get_holdout_declaration(name, registry_path=registry_path)  # must exist
    _reg.get_registration(experiment_id, registry_path)          # claimant must be registered
    prior = get_holdout_claim(name, registry_path=registry_path)
    if prior is not None:
        raise HoldoutAlreadyClaimedError(
            f"holdout {name!r} was already claimed by experiment "
            f"{prior.get('experiment_id')!r} at {prior.get('recorded_at')}. "
            "A locked final holdout is touched once (ROADMAP Phase 0.5); "
            "there is no second claim."
        )
    return _reg.append_record({
        "kind": "holdout_claimed",
        "holdout_name": str(name),
        "experiment_id": str(experiment_id),
        "note": note,
    }, registry_path)


def expose_holdout(
    df: pd.DataFrame,
    name: str,
    experiment_id: str,
    *,
    date_col: str = "game_date",
    season_col: str = "season",
    registry_path: "Path | str | None" = None,
) -> pd.DataFrame:
    """Return the holdout rows — ONLY for the experiment that holds the claim.

    Refuses when no claim exists (HoldoutNotClaimedError) or when the caller's
    experiment_id differs from the claimant's. The refusal path is the point:
    holdout rows are unreachable through the harness until the single claim is
    on the ledger.
    """
    claim = get_holdout_claim(name, registry_path=registry_path)
    if claim is None:
        raise HoldoutNotClaimedError(
            f"holdout {name!r} is locked: no claim recorded. Call "
            "claim_holdout(name, experiment_id) — knowing that it is single-use "
            "and irreversible — before requesting these rows."
        )
    if claim.get("experiment_id") != experiment_id:
        raise HoldoutNotClaimedError(
            f"holdout {name!r} is claimed by {claim.get('experiment_id')!r}, "
            f"not {experiment_id!r}; its single use is spent."
        )
    m = holdout_mask(df, name, date_col=date_col, season_col=season_col,
                     registry_path=registry_path)
    return df.loc[m]
