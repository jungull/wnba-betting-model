#!/usr/bin/env python3
"""cbs_v7.py — the runner for `contract_baseline_suite_v7`.

v6 supplied the pipeline v5 never had, and its 104 synthetic assertions pass. But
every one of those assertions ran inside a single season, against a runner that
would have accepted a contaminated frame, any valid-looking identity, and a
caller's word about when its features were readable. The defects v7 closes are
all at the **outer-fold and as-of boundaries** — the two places where a baseline
stops being a baseline and starts being a leak.

**Synthetic only, and structurally so.** No frame ever arrives from a path: every
input is a DataFrame argument. The *only* file this module reads is
`experiments/registry.jsonl`, and only to recompute the registered config hash it
is bound to — never as a model input. Running it produces no artifact, no
accuracy figure and no coverage score.

WHAT v7 ADDS OVER v6
--------------------
1. **An explicit outer-fold guard.** v6 never checked that `fold_id=season:Y`
   meant anything. A frame whose training rows sat in the *same* season as its
   test rows — which is exactly what v6's own fixtures did — produced
   `scoring_permitted=True`. `require_outer_fold` proves every test row is in
   season Y, every training row is in a season strictly before Y, the row-id sets
   are disjoint, and the training boundary precedes the test fold; it returns a
   fold-boundary receipt that the composite gate requires.
2. **Availability-aware walk-forward history.** v6's batch histories used earlier
   test rows' outcomes because their row *order* was prior, which is not the same
   as those outcomes having been *knowable*. `WalkForwardPlan` admits a prior
   outcome only when its availability timestamp is strictly earlier than the
   current row's cutoff. Where a real observed timestamp exists it is used and
   labelled `observed`; otherwise a frozen conservative policy timestamp is
   derived and labelled `policy` — it is never relabelled as an observation.
3. **Exact identity binding.** v6's `require_identity` accepted any nonzero
   64-hex string, emitted it, and then "validated" it against itself. v7 requires
   the exact registered constant, recomputes that constant from the registry
   record, and derives the snapshot identity from an independently supplied
   artifact manifest rather than echoing the caller's value back.
4. **A real feature-source contract.** v6 never called `resolve_feature_asof`;
   `_emit` copied the caller's column, and `synthetic=False` still defaulted
   `allow_declared_defaults=True`. On the real path v7 requires every Stage-A
   input and every source timestamp actually read, derives the row maximum, and
   forbids declared defaults outright.
5. **The registered fallback ladders, implemented.** Player rows with one or two
   prior appearances are level-2 fallbacks, zero-history/NaN-center rows level 3,
   season 2021 level 4. Team `MIN_PRIOR=5` now both **masks emission** and
   **restricts selection**: histories of 1-4 games can no longer influence an
   alpha or produce a nonfallback prediction.
6. **A hashed, validated provenance sidecar.** One row per (row_uid, target_key)
   carrying component id, fallback level, selected alpha/lambda, residual-pool
   count and the separate prior-history fields, with its own SHA-256, identity
   fields, schema validator and one-to-one binding to each prediction frame. A
   substituted sidecar changes the digest in the run receipt.
7. **A composite gate.** `scoring_permitted` is true only when the prediction,
   fold-boundary, provenance-history, exclusion cross-tab and coverage receipts
   all pass — not merely when the prediction validator did.
8. **Separated train-history and current-obligation inputs.** A test row no
   longer needs its own postgame outcome in order to be predicted; outcome
   columns on the test frame are optional and feed only later rows' history.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from cbs_builders import QUANTILE_LEVELS, QUANTILE_Z
from cbs_generator import (ALPHA_GRID, DECLARED, LAMBDA_GRID, SplitContext,
                           Standardizer, TEAM_POINTS_FLOOR, emit_quantiles,
                           logistic_fit, logistic_predict, order_obligations,
                           player_split, prefix_mean, select_alpha_bound, team_split)
from cbs_v5 import (MissingRequiredInput, P_ACTIVE_FEATURES, REQUIRED_CHANNELS,
                    REQUIRED_SIDES, SIDE_COL, TEAM_HISTORY_GROUP, TEAM_MIN_PRIOR,
                    TEAM_SORT_KEYS, PLAYER_SORT_KEYS, apply_side_maps, dispersion,
                    fit_side_maps, fitted_state_hash, residuals)
from contract_validator_v3_strict import validate_arm_output_v3

ARM_ID = "contract_baseline_suite_v7"
REGISTRY_PATH = Path(__file__).resolve().parent / "experiments" / "registry.jsonl"

PROVENANCE_SIDECAR_SCHEMA = "cbs_provenance_history/1"
SNAPSHOT_MANIFEST_SCHEMA = "cbs_snapshot_manifest/1"

PLAYER_TARGETS = ("p_active", "e_minutes_given_active", "attempts_usage",
                  "player_scoring_distribution")
CONDITIONAL_TARGETS = ("e_minutes_given_active", "attempts_usage",
                       "player_scoring_distribution")
TEAM_TARGET = "team_game_distribution"

# --------------------------------------------------------------------------
# frozen v7 constants
# --------------------------------------------------------------------------

#: The registered config digest. Recomputed from the registry by
#: `recompute_registered_config_hash`; a real run must be handed exactly this.
REGISTERED_CONFIG_HASH = \
    "237b4c1815d3b9a5c0f7f1af09c9d143c186ff2bfc9244f73fd5c63c6a440fc4"

#: The synthetic-path config sentinel. Synthetic runs are bound just as tightly
#: as real ones — to a different, fixed value — so "any valid 64-hex string is
#: accepted" is untrue on both paths and a wrong-but-valid digest is rejected.
SYNTHETIC_CONFIG_HASH = hashlib.sha256(
    b"contract_baseline_suite_v7/synthetic-config").hexdigest()

#: Outcome availability. Where an adapter supplies a genuine observed timestamp
#: in this column it is used and labelled `observed`.
OUTCOME_OBSERVED_AT_COL = "outcome_observed_at"

#: Otherwise a conservative timestamp is DERIVED FROM POLICY: midnight UTC of
#: the game date, plus this many hours. 36h places availability at noon UTC on
#: the day AFTER the game, comfortably after any box score is final. It is a
#: policy constant, not an observation, and is labelled as such on every row.
OUTCOME_AVAILABILITY_POLICY_ID = "postgame_policy_lag_36h_from_game_date_utc/1"
OUTCOME_AVAILABILITY_POLICY_LAG_HOURS = 36.0

#: Registered fallback ladder. Higher levels win; `is_fallback == level > 0`.
FALLBACK_LADDER = {
    0: "none: fitted component produced the emitted value",
    1: "degenerate fold: no usable training window, declared constants",
    2: "short history: 1-2 prior appearances (player) / 1-4 prior games (team)",
    3: "no history or non-finite center",
    4: "registered declared-constant season",
}
MAX_FALLBACK_LEVEL = 4

#: Seasons the registration pins to declared constants.
DECLARED_CONSTANT_SEASONS = (2021,)

#: Player short-history band: 1 or 2 prior appearances is a level-2 fallback.
PLAYER_SHORT_HISTORY_MAX = 2

#: Stage-A source timestamp columns a REAL adapter must supply. `feature_asof`
#: is the row maximum over these; it is never copied from the caller.
REQUIRED_PLAYER_FEATURE_SOURCES = ("src_asof_gamelog", "src_asof_roster",
                                   "src_asof_schedule")
REQUIRED_TEAM_FEATURE_SOURCES = ("src_asof_team_gamelog", "src_asof_schedule")

MIN_RESID_PLAYER = 200
MIN_RESID_TEAM = 30


class OuterFoldViolation(RuntimeError):
    """The train/test frames do not form a clean season outer fold."""


class AdapterBoundaryError(RuntimeError):
    """Registered identity was not supplied, or did not match, where mandatory."""


class AvailabilityViolation(RuntimeError):
    """An outcome would have been read before it could have been known."""


class ProvenanceError(RuntimeError):
    """The provenance sidecar is absent, malformed, or not bound to its rows."""


# --------------------------------------------------------------------------
# 1. outer-fold guard  (Codex defect 1)
# --------------------------------------------------------------------------

def parse_fold_season(fold_id: str) -> int:
    """`season:Y` -> Y, or raise. The fold id is a claim; this checks it parses."""
    if not isinstance(fold_id, str) or not fold_id.startswith("season:"):
        raise OuterFoldViolation(
            f"fold_id must be of the form 'season:<year>'; got {fold_id!r}")
    tail = fold_id.split(":", 1)[1]
    if not tail.isdigit():
        raise OuterFoldViolation(f"fold_id season is not an integer: {fold_id!r}")
    return int(tail)


def require_outer_fold(train: pd.DataFrame, test: pd.DataFrame, fold_id: str, *,
                       cutoff_col: str = "forecast_cutoff") -> dict:
    """Prove the frames form the outer fold their `fold_id` claims, or raise.

    v6 proved none of this. Its own player fixture drew train and test from the
    same season, so a frame with the training rows sitting *inside* the test
    season could reach `scoring_permitted=True`. Each clause below is a distinct
    way for that to happen:

      * a test row outside season Y means the fold is not the fold it names;
      * a training row in season Y or later is same-season or future-season
        contamination;
      * an overlapping `row_uid` is the same observation on both sides;
      * a training cutoff at or after the earliest test cutoff means the
        "training" window extends into the fold it is supposed to precede.

    Returns the fold-boundary receipt the composite gate requires.
    """
    season = parse_fold_season(fold_id)
    for name, frame in (("train", train), ("test", test)):
        for c in ("row_uid", "season", cutoff_col):
            if c not in frame.columns:
                raise OuterFoldViolation(f"{name} frame missing {c!r}")
        if frame["row_uid"].isna().any():
            raise OuterFoldViolation(f"{name} frame has null row_uid")
        if frame["season"].isna().any():
            raise OuterFoldViolation(f"{name} frame has null season")

    if len(test) == 0:
        raise OuterFoldViolation("test fold is empty; there is nothing to predict")

    test_seasons = sorted(pd.unique(test["season"].astype(int)))
    if test_seasons != [season]:
        raise OuterFoldViolation(
            f"fold {fold_id!r} requires every test row in season {season}; "
            f"found {test_seasons}")

    train_seasons = sorted(pd.unique(train["season"].astype(int))) if len(train) else []
    bad = [s for s in train_seasons if s >= season]
    if bad:
        raise OuterFoldViolation(
            f"fold {fold_id!r} requires every training row STRICTLY BEFORE season "
            f"{season}; found training seasons {bad} (same-season or future-season "
            f"contamination)")

    overlap = set(train["row_uid"]) & set(test["row_uid"])
    if overlap:
        raise OuterFoldViolation(
            f"{len(overlap)} row_uid appear in BOTH train and test "
            f"(e.g. {sorted(overlap)[:3]})")

    tr_cut = pd.to_datetime(train[cutoff_col], utc=True, errors="coerce") \
        if len(train) else pd.Series([], dtype="datetime64[ns, UTC]")
    te_cut = pd.to_datetime(test[cutoff_col], utc=True, errors="coerce")
    if te_cut.isna().any():
        raise OuterFoldViolation("unparseable forecast_cutoff on the test frame")
    if len(train):
        if tr_cut.isna().any():
            raise OuterFoldViolation("unparseable forecast_cutoff on the training frame")
        if tr_cut.max() >= te_cut.min():
            raise OuterFoldViolation(
                f"training boundary {tr_cut.max().isoformat()} does not precede the "
                f"test fold, which opens at {te_cut.min().isoformat()}")

    return {
        "receipt": "fold_boundary/1", "ok": True, "fold_id": fold_id,
        "test_season": season, "train_seasons": [int(s) for s in train_seasons],
        "n_train_rows": int(len(train)), "n_test_rows": int(len(test)),
        "row_uid_disjoint": True,
        "train_cutoff_max": tr_cut.max().isoformat() if len(train) else None,
        "test_cutoff_min": te_cut.min().isoformat(),
        "test_cutoff_max": te_cut.max().isoformat(),
        "train_boundary_precedes_test": True,
    }


# --------------------------------------------------------------------------
# 2. outcome availability  (Codex defect 4)
# --------------------------------------------------------------------------

def resolve_outcome_availability(frame: pd.DataFrame, *,
                                 date_col: str = "game_date") -> tuple[pd.Series, str]:
    """(availability timestamp per row, source label).

    Two sources, and the label always says which:

      * ``observed`` — the adapter supplied a genuine per-row timestamp in
        `outcome_observed_at`. Used as given.
      * ``policy``   — no observation exists, so a conservative timestamp is
        DERIVED: midnight UTC of the game date plus 36 hours. This is a policy
        constant. It is recorded as `policy` on every row and in the receipt, and
        must never be described as an observation.

    A partially-populated observed column is rejected rather than silently
    back-filled with policy values: a column that is an observation on some rows
    and a derivation on others is neither.
    """
    if date_col not in frame.columns:
        raise MissingRequiredInput(f"cannot resolve outcome availability: no {date_col!r}")

    if OUTCOME_OBSERVED_AT_COL in frame.columns:
        obs = pd.to_datetime(frame[OUTCOME_OBSERVED_AT_COL], utc=True, errors="coerce")
        supplied = frame[OUTCOME_OBSERVED_AT_COL].notna()
        if supplied.all():
            if obs.isna().any():
                raise MissingRequiredInput(
                    f"{OUTCOME_OBSERVED_AT_COL} present but unparseable on "
                    f"{int(obs.isna().sum())} rows")
            return obs, "observed"
        if supplied.any():
            raise MissingRequiredInput(
                f"{OUTCOME_OBSERVED_AT_COL} is populated on {int(supplied.sum())} of "
                f"{len(frame)} rows; a column that is an observation on some rows and "
                f"a policy derivation on others is neither. Supply it everywhere or "
                f"nowhere.")

    d = pd.to_datetime(frame[date_col], utc=True, errors="coerce")
    if d.isna().any():
        raise MissingRequiredInput(
            f"{date_col} unparseable on {int(d.isna().sum())} rows; a policy "
            f"availability timestamp cannot be derived from it")
    return (d.dt.floor("D")
            + pd.Timedelta(hours=OUTCOME_AVAILABILITY_POLICY_LAG_HOURS)), "policy"


def require_own_outcome_unavailable(frame: pd.DataFrame, avail: pd.Series, *,
                                    cutoff_col: str = "forecast_cutoff") -> None:
    """No row's own outcome may be available before its own cutoff.

    This is the invariant that makes the walk-forward engine's cutoff test
    sufficient: if a row's own outcome could be available before its own cutoff,
    gating history on `availability < cutoff` would admit the row's own answer.
    Fail closed rather than assume the policy lag is generous enough.
    """
    cut = pd.to_datetime(frame[cutoff_col], utc=True, errors="coerce")
    if cut.isna().any():
        raise MissingRequiredInput("unparseable forecast_cutoff")
    bad = int((avail < cut).sum())
    if bad:
        raise AvailabilityViolation(
            f"{bad} rows whose own outcome would be available BEFORE their own "
            f"forecast cutoff; such a row could read its own answer")


# --------------------------------------------------------------------------
# 3. the walk-forward engine  (Codex defect 4)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class WalkForwardPlan:
    """Which prior rows each row may read, decided by timestamps alone.

    Admission depends only on `(group, cutoff, availability)`, never on a model
    parameter — so the plan is computed once and reused across every alpha in
    the grid. That is not merely an optimisation: it makes it impossible for a
    tuning choice to widen the history it is tuned on.

    `admitted[i]` holds positions into `order` — the rows whose outcome was
    available strictly before `order[i]`'s cutoff, within the same group.
    """
    order: np.ndarray                 # frame index, chronological
    admitted: tuple                   # per ordered position: np.ndarray of positions
    group_key: tuple                  # per ordered position: the group value
    availability_source: str
    policy_id: str | None

    @property
    def n_admitted(self) -> np.ndarray:
        return np.asarray([len(a) for a in self.admitted], dtype=int)


def build_walk_forward_plan(frame: pd.DataFrame, *, group_cols: list[str],
                            sort_cols: list[str],
                            cutoff_col: str = "forecast_cutoff",
                            date_col: str = "game_date") -> WalkForwardPlan:
    """Admit a prior row only when its outcome was knowable at this row's cutoff.

    v6 used row *order* as a proxy for knowability. Order is not availability: a
    game played the evening before a morning cutoff is prior in every sort key
    and its box score may still not have existed. Here every admission is an
    explicit `availability < cutoff` comparison.
    """
    avail, source = resolve_outcome_availability(frame, date_col=date_col)
    require_own_outcome_unavailable(frame, avail, cutoff_col=cutoff_col)

    d = frame.sort_values(sort_cols, kind="mergesort")
    order = np.asarray(d.index)
    cut = pd.to_datetime(d[cutoff_col], utc=True, errors="coerce").to_numpy()
    av = avail.reindex(d.index).to_numpy()
    gkey = list(zip(*[d[c].to_numpy() for c in group_cols])) if group_cols else \
        [()] * len(d)

    admitted: list[np.ndarray] = []
    starts: dict = {}
    for i, g in enumerate(gkey):
        members = starts.setdefault(g, [])
        if members:
            prior = np.asarray(members, dtype=int)
            admitted.append(prior[av[prior] < cut[i]])
        else:
            admitted.append(np.array([], dtype=int))
        members.append(i)

    return WalkForwardPlan(order=order, admitted=tuple(admitted),
                           group_key=tuple(gkey), availability_source=source,
                           policy_id=(OUTCOME_AVAILABILITY_POLICY_ID
                                      if source == "policy" else None))


def _ewma_last(values: np.ndarray, alpha: float) -> float:
    """Last value of an `adjust=True` EWMA over a finite sequence."""
    if len(values) == 0:
        return np.nan
    w = (1.0 - alpha) ** np.arange(len(values) - 1, -1, -1)
    return float(np.sum(w * values) / np.sum(w))


def walk_forward_ewma(plan: WalkForwardPlan, value: pd.Series, alpha: float, *,
                      mask: pd.Series | None = None) -> pd.Series:
    """Shifted EWMA over the ADMITTED prior subsequence, per row.

    `mask` restricts admission further — the conditional targets pass the
    activity mask, because their history is the *active* subsequence: a DNP's
    recorded zero is not a small performance, it is an absence.
    """
    v = value.reindex(plan.order).to_numpy(dtype=float)
    m = (mask.reindex(plan.order).to_numpy(dtype=bool) if mask is not None
         else np.ones(len(plan.order), dtype=bool))
    ok = m & np.isfinite(v)
    out = np.full(len(plan.order), np.nan)
    for i, prior in enumerate(plan.admitted):
        if len(prior):
            sel = prior[ok[prior]]
            if len(sel):
                out[i] = _ewma_last(v[sel], alpha)
    return pd.Series(out, index=plan.order).reindex(value.index)


def walk_forward_ratio_ewma(plan: WalkForwardPlan, num: pd.Series, den: pd.Series,
                            alpha: float, scale: float = 36.0, *,
                            mask: pd.Series | None = None) -> pd.Series:
    """Shifted ratio-of-EWMAs over the admitted prior subsequence.

    A zero denominator becomes NaN and routes the row to its fallback level,
    never a silent zero.
    """
    n = walk_forward_ewma(plan, num, alpha, mask=mask)
    q = walk_forward_ewma(plan, den, alpha, mask=mask)
    return (n / q.replace(0.0, np.nan)) * scale


def walk_forward_counts(plan: WalkForwardPlan, *, mask: pd.Series | None = None
                        ) -> pd.Series:
    """How many admitted prior rows each row has (optionally masked)."""
    m = (mask.reindex(plan.order).to_numpy(dtype=bool) if mask is not None
         else np.ones(len(plan.order), dtype=bool))
    out = np.asarray([int(m[p].sum()) if len(p) else 0 for p in plan.admitted])
    return pd.Series(out, index=plan.order)


def conditional_center(plan: WalkForwardPlan, frame: pd.DataFrame, active: pd.Series,
                       target: str, *, minutes_alpha: float,
                       rate_alpha: float) -> pd.Series:
    """The conditional point estimate, identical in form to the v6 estimator.

    The minutes leg is held fixed at its own selected alpha while the rate leg
    is tuned, exactly as the registration froze; only the *history admitted into
    each EWMA* has changed, from "positionally prior" to "knowable at the cutoff".
    """
    mins = walk_forward_ewma(plan, frame["minutes"], minutes_alpha, mask=active)
    if target == "e_minutes_given_active":
        return mins
    if target == "attempts_usage":
        rate = walk_forward_ratio_ewma(plan, frame["fga"], frame["minutes"],
                                       rate_alpha, mask=active)
    elif target == "player_scoring_distribution":
        rate = walk_forward_ewma(
            plan, frame["points"] / frame["minutes"].replace(0, np.nan) * 36.0,
            rate_alpha, mask=active)
    else:
        raise ValueError(f"not a conditional target: {target!r}")
    return rate * (mins / 36.0)


def combine_history_frames(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """One history frame over the union of columns, in a DETERMINISTIC order.

    The union matters: `test` is a frame of *current obligations* and may carry
    no outcome columns at all. Intersecting would silently drop `minutes` from
    the training rows too, leaving the history engine with nothing to average.
    Sorting the column list matters because a `set` iteration order would make
    the frame — and therefore every hash downstream of it — irreproducible.
    """
    cols = sorted(set(train.columns) | set(test.columns))
    parts = [f.reindex(columns=cols) for f in (train, test) if len(f)]
    return pd.concat(parts, ignore_index=True) if parts else test.reindex(columns=cols)


# --------------------------------------------------------------------------
# 4. availability-gated player history accounting
# --------------------------------------------------------------------------

def player_history_walk_forward(frame: pd.DataFrame, plan: WalkForwardPlan
                                ) -> pd.DataFrame:
    """Separate prior-history fields, every one of them availability-gated.

    v5/v6 counted prior obligations and appearances with a `cumcount`, i.e. by
    position. Here `n_prior_appearances` counts only appearances whose outcome
    was knowable at this row's cutoff, and `p_plays_prior` divides it by the
    obligations from that SAME admitted set — a ratio whose numerator and
    denominator disagree about what was known is not a rate.
    """
    appeared = frame["appeared"].astype(bool) if "appeared" in frame.columns else None
    n_avail_oblig = walk_forward_counts(plan)
    n_app = (walk_forward_counts(plan, mask=appeared) if appeared is not None
             else pd.Series(0, index=plan.order))

    out = pd.DataFrame(index=plan.order)
    out["n_prior_available_obligations"] = n_avail_oblig.astype(int)
    out["n_prior_appearances"] = n_app.astype(int)
    # candidate obligations are a SCHEDULING fact, known pregame, so they are
    # counted by prior cutoff rather than by outcome availability
    out["n_prior_candidate_games"] = np.asarray(
        [len(p) for p in _prior_by_cutoff(plan)], dtype=int)
    out["has_prior_obligation"] = out["n_prior_candidate_games"] > 0
    out["has_prior_appearance"] = out["n_prior_appearances"] > 0
    # A row can be scheduled after several prior obligations and still have NO
    # readable outcome among them, because the availability lag has not elapsed.
    # `p_plays_prior` must fall back to the base rate on exactly that condition,
    # not on the weaker "never had an obligation" — otherwise the rate is NaN and
    # would be silently zero-filled.
    out["has_prior_available_obligation"] = out["n_prior_available_obligations"] > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        out["p_plays_prior"] = np.where(
            out["n_prior_available_obligations"] > 0,
            out["n_prior_appearances"] / out["n_prior_available_obligations"].replace(0, np.nan),
            np.nan)
    return out.reindex(frame.index)


def _prior_by_cutoff(plan: WalkForwardPlan) -> list[np.ndarray]:
    """Prior rows by CUTOFF rather than outcome availability.

    Whether a player was a candidate for an earlier game is known from the
    schedule and roster before that game is played, so it does not need the
    outcome-availability gate the appearance counts need.
    """
    out: list[np.ndarray] = []
    seen: dict = {}
    for i, g in enumerate(plan.group_key):
        members = seen.setdefault(g, [])
        out.append(np.asarray(members, dtype=int))
        members.append(i)
    return out


# --------------------------------------------------------------------------
# 5. fallback ladders  (Codex defect 5)
# --------------------------------------------------------------------------

def player_fallback_level(frame: pd.DataFrame, n_prior: pd.Series,
                          center_finite: pd.Series, *,
                          degenerate: bool = False) -> pd.Series:
    """The registered player ladder. Higher wins.

    v6 emitted one opaque `is_fallback` boolean and marked a player with two
    prior appearances no differently from one with forty. The band matters: an
    EWMA over one or two observations is a fallback wearing a model's clothes.
    """
    lvl = pd.Series(0, index=frame.index, dtype=int)
    if degenerate:
        lvl[:] = 1
    short = (n_prior >= 1) & (n_prior <= PLAYER_SHORT_HISTORY_MAX)
    lvl = lvl.mask(short & (lvl < 2), 2)
    none_or_nan = (n_prior <= 0) | (~center_finite.astype(bool))
    lvl = lvl.mask(none_or_nan & (lvl < 3), 3)
    declared_season = frame["season"].astype(int).isin(DECLARED_CONSTANT_SEASONS)
    lvl = lvl.mask(declared_season, 4)
    return lvl.astype(int)


def team_fallback_level(frame: pd.DataFrame, prior_games: pd.Series,
                        center_finite: pd.Series, *,
                        degenerate: bool = False) -> pd.Series:
    """The registered team ladder, with `MIN_PRIOR=5` actually binding.

    v5 froze `TEAM_MIN_PRIOR = 5` and v6 never read it. A team with one prior
    game had a channel EWMA of exactly one observation, and that number both
    influenced alpha selection and was emitted as a nonfallback prediction.
    """
    lvl = pd.Series(0, index=frame.index, dtype=int)
    if degenerate:
        lvl[:] = 1
    short = (prior_games >= 1) & (prior_games < TEAM_MIN_PRIOR)
    lvl = lvl.mask(short & (lvl < 2), 2)
    none_or_nan = (prior_games <= 0) | (~center_finite.astype(bool))
    lvl = lvl.mask(none_or_nan & (lvl < 3), 3)
    declared_season = frame["season"].astype(int).isin(DECLARED_CONSTANT_SEASONS)
    lvl = lvl.mask(declared_season, 4)
    return lvl.astype(int)


# --------------------------------------------------------------------------
# 6. identity binding  (Codex defect 2)
# --------------------------------------------------------------------------

def _canon(obj):
    if isinstance(obj, dict):
        return {str(k): _canon(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_canon(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if not np.isfinite(float(obj)) else round(float(obj), 12)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, pd.Series):
        return _canon(obj.tolist())
    if isinstance(obj, np.ndarray):
        return _canon(obj.tolist())
    return obj


def canonical_digest(obj) -> str:
    return hashlib.sha256(json.dumps(_canon(obj), sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def recompute_registered_config_hash(registry_path: Path | str = REGISTRY_PATH,
                                     *, experiment_id: str = ARM_ID) -> str:
    """SHA-256 over the registry's own frozen_config, minus its self-reference.

    This is the *only* file this module reads, and it is read for identity, never
    for model inputs. The convention — canonical JSON with
    `hashes.config_hash_value` removed — is the one v1-v6 used and the supervisor
    verified. Because the value is recomputed rather than asserted, editing the
    registered configuration invalidates the constant instead of silently
    redefining what the arm is.
    """
    path = Path(registry_path)
    if not path.exists():
        raise AdapterBoundaryError(f"registry not found at {path}")
    record = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("experiment_id") == experiment_id:
            record = obj                       # last wins; append-only registry
    if record is None:
        raise AdapterBoundaryError(f"no registry record for {experiment_id!r}")
    frozen = record.get("extra", {}).get("frozen_config")
    if not isinstance(frozen, dict):
        raise AdapterBoundaryError(f"{experiment_id!r} record has no frozen_config")
    payload = json.loads(json.dumps(frozen))
    payload.get("hashes", {}).pop("config_hash_value", None)
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def snapshot_identity(manifest: dict) -> str:
    """Derive the snapshot identity FROM the artifact manifest.

    v6 accepted a caller's `snapshot_hash`, emitted it, and then compared it to
    itself — a check that cannot fail. Here the caller must hand over the
    manifest of the artifacts actually consumed; the identity is computed from
    it, and the caller's claimed digest is checked against that computation. A
    wrong-but-well-formed digest now fails.
    """
    if not isinstance(manifest, dict):
        raise AdapterBoundaryError("snapshot manifest must be a mapping")
    if manifest.get("schema") != SNAPSHOT_MANIFEST_SCHEMA:
        raise AdapterBoundaryError(
            f"snapshot manifest schema must be {SNAPSHOT_MANIFEST_SCHEMA!r}; "
            f"got {manifest.get('schema')!r}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise AdapterBoundaryError("snapshot manifest lists no artifacts")
    for name, digest in artifacts.items():
        if not isinstance(digest, str) or len(digest) != 64 or \
                not all(c in "0123456789abcdef" for c in digest.lower()):
            raise AdapterBoundaryError(
                f"snapshot manifest entry {name!r} is not a 64-hex digest")
    if "captured_at" not in manifest:
        raise AdapterBoundaryError("snapshot manifest has no captured_at")
    return canonical_digest(manifest)


def require_registered_identity(config_hash: str, snapshot_hash: str,
                                snapshot_manifest: dict | None, *,
                                synthetic: bool,
                                registry_path: Path | str = REGISTRY_PATH) -> dict:
    """Bind the run to the EXACT registered config and an independent snapshot.

    Returns the identity receipt. Raises rather than degrading: an arm that
    cannot prove which configuration it is may not produce rows at all.
    """
    expected_cfg = SYNTHETIC_CONFIG_HASH if synthetic else REGISTERED_CONFIG_HASH
    if not isinstance(config_hash, str) or config_hash.lower() != expected_cfg:
        raise AdapterBoundaryError(
            f"config_hash must be the exact registered "
            f"{'synthetic' if synthetic else 'v7'} digest {expected_cfg}; "
            f"got {config_hash!r}")

    recomputed = None
    if not synthetic:
        recomputed = recompute_registered_config_hash(registry_path)
        if recomputed != REGISTERED_CONFIG_HASH:
            raise AdapterBoundaryError(
                f"the registered config no longer hashes to the bound constant: "
                f"registry recomputes to {recomputed}, module holds "
                f"{REGISTERED_CONFIG_HASH}")

    if snapshot_manifest is None:
        raise AdapterBoundaryError(
            "snapshot_manifest is mandatory: the snapshot identity is DERIVED "
            "from the artifacts consumed, never taken on the caller's word")
    derived = snapshot_identity(snapshot_manifest)
    if not isinstance(snapshot_hash, str) or snapshot_hash.lower() != derived:
        raise AdapterBoundaryError(
            f"snapshot_hash {snapshot_hash!r} does not match the identity derived "
            f"from the supplied artifact manifest ({derived})")

    return {"receipt": "identity_binding/1", "ok": True, "synthetic": bool(synthetic),
            "config_hash": expected_cfg,
            "config_hash_recomputed_from_registry": recomputed,
            "snapshot_hash": derived,
            "n_snapshot_artifacts": len(snapshot_manifest["artifacts"])}


# --------------------------------------------------------------------------
# 7. the real feature-source contract  (Codex defect 3)
# --------------------------------------------------------------------------

def resolve_feature_asof_strict(frame: pd.DataFrame, source_cols) -> pd.Series:
    """The row MAXIMUM over the source timestamps actually read, or raise.

    v6 declared this function's v5 ancestor and then never called it: `_emit`
    copied `uni["feature_asof"]`, so the contract's central as-of guarantee was
    whatever the caller had written in a column. Deriving it from the sources
    is the difference between a provenance field and a comment.
    """
    missing = [c for c in source_cols if c not in frame.columns]
    if missing:
        raise MissingRequiredInput(
            f"cannot derive feature_asof: source timestamp columns absent: {missing}")
    ts = frame[list(source_cols)].apply(pd.to_datetime, utc=True, errors="coerce")
    if ts.isna().any().any():
        bad = {c: int(ts[c].isna().sum()) for c in ts.columns if ts[c].isna().any()}
        raise MissingRequiredInput(
            f"missing or unparseable source timestamps; provenance ambiguous: {bad}")
    asof = ts.max(axis=1)
    cutoff = pd.to_datetime(frame["forecast_cutoff"], utc=True, errors="coerce")
    if cutoff.isna().any():
        raise MissingRequiredInput("unparseable forecast_cutoff")
    late = int((asof >= cutoff).sum())
    if late:
        raise MissingRequiredInput(
            f"{late} rows read a feature source at or after their own forecast "
            f"cutoff; those features were not available when the forecast was due")
    return asof.dt.strftime("%Y-%m-%dT%H:%M:%S%z").str.replace(
        r"(\+0000)$", "+00:00", regex=True)


def stage_a_features_v7(frame: pd.DataFrame, hist: pd.DataFrame, base_rate: float,
                        *, allow_declared_defaults: bool) -> pd.DataFrame:
    """The 14 canonical features. On the real path, every one must be supplied.

    v6 passed `allow_declared_defaults=True` by default *including when
    `synthetic=False`*, so a real frame missing half its features still produced
    confident probabilities out of zeros. The runners now refuse to set this True
    on the real path at all.
    """
    derived = {"p_plays_prior", "player_gp_season"}          # from admitted history
    supplied = {c for c in P_ACTIVE_FEATURES if c in frame.columns}
    missing = [c for c in P_ACTIVE_FEATURES if c not in supplied | derived]
    if missing and not allow_declared_defaults:
        raise MissingRequiredInput(
            f"Stage-A features absent and declared defaults are not permitted on "
            f"this path: {missing}")

    X = pd.DataFrame(index=frame.index)
    for c in P_ACTIVE_FEATURES:
        if c == "p_plays_prior":
            X[c] = hist["p_plays_prior"].where(
                hist["has_prior_available_obligation"], base_rate)
        elif c == "player_gp_season":
            X[c] = hist["n_prior_appearances"].astype(float)
        elif c in frame.columns:
            X[c] = pd.to_numeric(frame[c], errors="coerce").astype(float)
        else:
            X[c] = 45.0 if c == "days_since_last_appearance" else 0.0
    X = X[P_ACTIVE_FEATURES].astype(float)
    if not allow_declared_defaults and not np.isfinite(X.to_numpy()).all():
        raise MissingRequiredInput(
            "non-finite Stage-A feature values on the real path; a null feature "
            "may not become a silent zero")
    return X.fillna(0.0)


# --------------------------------------------------------------------------
# 8. team input contracts, training vs prediction  (Codex defect 8)
# --------------------------------------------------------------------------

def _require_team_common(frame: pd.DataFrame, role: str) -> None:
    """Structural preconditions shared by both roles, all fail-closed."""
    for k in ("row_uid", "team_id", "game_id", "season", "game_date",
              "forecast_cutoff"):
        if k not in frame.columns:
            raise MissingRequiredInput(f"team {role} frame missing {k!r}")
        if frame[k].isna().any():
            raise MissingRequiredInput(
                f"team {role} frame has null {k!r} on "
                f"{int(frame[k].isna().sum())} rows")
    if not np.issubdtype(pd.to_numeric(frame["season"], errors="coerce").dtype,
                         np.number) or pd.to_numeric(
            frame["season"], errors="coerce").isna().any():
        raise MissingRequiredInput(f"team {role} frame has non-numeric season")
    if pd.to_datetime(frame["game_date"], errors="coerce").isna().any():
        raise MissingRequiredInput(f"team {role} frame has unparseable game_date")
    if pd.to_datetime(frame["forecast_cutoff"], utc=True, errors="coerce").isna().any():
        raise MissingRequiredInput(f"team {role} frame has unparseable forecast_cutoff")
    if frame["row_uid"].duplicated().any():
        raise MissingRequiredInput(f"team {role} frame has duplicate row_uid")

    missing = [c for c in REQUIRED_CHANNELS if f"ch_{c}" not in frame.columns]
    if missing:
        raise MissingRequiredInput(f"required team channels absent: {missing}")
    for c in REQUIRED_CHANNELS:
        col = pd.to_numeric(frame[f"ch_{c}"], errors="coerce")
        if col.isna().any() or not np.isfinite(col).all():
            raise MissingRequiredInput(f"channel ch_{c} has null/non-finite values")

    if SIDE_COL not in frame.columns:
        raise MissingRequiredInput(f"required side indicator {SIDE_COL!r} absent")
    if frame[SIDE_COL].isna().any():
        raise MissingRequiredInput(f"{SIDE_COL} has null values")
    bad = set(pd.unique(frame[SIDE_COL])) - set(REQUIRED_SIDES)
    if bad:
        raise MissingRequiredInput(f"unexpected {SIDE_COL} values: {sorted(bad)}")
    if frame.duplicated(subset=["team_id", "game_id"]).any():
        raise MissingRequiredInput("duplicate (team_id, game_id) team rows")
    for gid, sides in frame.groupby("game_id")[SIDE_COL].agg(list).items():
        if sorted(sides) != sorted(REQUIRED_SIDES):
            raise MissingRequiredInput(
                f"game {gid!r} is not exactly one home and one away row: {sides}")


def require_team_train_inputs(frame: pd.DataFrame) -> None:
    """Training additionally requires a finite outcome on every row.

    A training row without an outcome teaches nothing; a training row with a
    non-finite one teaches something false.
    """
    _require_team_common(frame, "training")
    if "team_points" not in frame.columns:
        raise MissingRequiredInput("team training frame missing team_points")
    y = pd.to_numeric(frame["team_points"], errors="coerce")
    if y.isna().any() or not np.isfinite(y).all():
        raise MissingRequiredInput(
            f"{int((~np.isfinite(y.fillna(np.nan))).sum())} training rows have a "
            f"null or non-finite team_points outcome")


def require_team_predict_inputs(frame: pd.DataFrame) -> None:
    """Prediction requires the structure but NOT the row's own outcome.

    v6 ran one checker over both frames, so a current test row needed its own
    postgame `team_points` merely to be predicted — which is precisely the
    dependency an as-of forecast is supposed not to have.
    """
    _require_team_common(frame, "prediction")


# --------------------------------------------------------------------------
# 9. fitted state and emission
# --------------------------------------------------------------------------

@dataclass
class FittedState:
    """Everything that can change a prediction, in one hashable object."""
    target: str
    fold_id: str
    component_id: str = ""
    feature_order: list = field(default_factory=list)
    scaler_mean: list = field(default_factory=list)
    scaler_std: list = field(default_factory=list)
    dropped_features: list = field(default_factory=list)
    lam: float | None = None
    beta: list = field(default_factory=list)
    alphas: dict = field(default_factory=dict)
    calibration_maps: dict = field(default_factory=dict)
    base_rate: float | None = None
    fallback_mean: float | None = None
    dispersion_sd: float | None = None
    dispersion_method: str | None = None
    dispersion_offsets: list = field(default_factory=list)
    residual_pool_n: int | None = None
    min_prior: int | None = None
    support: dict = field(default_factory=dict)
    availability_source: str | None = None
    availability_policy_id: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    def hash(self) -> str:
        return fitted_state_hash(self.to_dict())


def _emit(rows: pd.DataFrame, target: str, point: pd.Series, sd: pd.Series | None,
          offsets: np.ndarray | None, *, fold_id: str, config_hash: str,
          snapshot_hash: str, model_hash: str, feature_asof: pd.Series,
          fallback_level: pd.Series, component_id: pd.Series, is_cold: pd.Series,
          n_prior: pd.Series, exclusion: pd.Series, low, high,
          want_q: bool) -> pd.DataFrame:
    """Build contract rows. `feature_asof` is DERIVED and passed in, never copied."""
    lvl = pd.Series(fallback_level, index=rows.index).astype(int)
    out = pd.DataFrame({
        "row_uid": rows["row_uid"].to_numpy(),
        "target_key": target, "arm_id": ARM_ID, "fold_id": fold_id,
        "forecast_cutoff": rows["forecast_cutoff"].to_numpy(),
        "pred_point": np.asarray(point, dtype=float),
        "pred_sd": (np.asarray(sd, dtype=float) if sd is not None
                    else np.full(len(rows), np.nan)),
        "is_fallback": (lvl > 0).to_numpy(),
        "fallback_level": lvl.to_numpy(),
        "component_id": pd.Series(component_id, index=rows.index).to_numpy(),
        "is_cold_start": np.asarray(is_cold, dtype=bool),
        "n_prior_games": np.asarray(n_prior, dtype=int),
        "feature_asof": pd.Series(feature_asof, index=rows.index).to_numpy(),
        "model_hash": model_hash, "config_hash": config_hash,
        "data_snapshot_hash": snapshot_hash,
        "exclusion_reason": pd.Series(exclusion, index=rows.index).to_numpy(),
    })
    for c in ("pred_q05", "pred_q25", "pred_q50", "pred_q75", "pred_q95"):
        out[c] = np.nan

    if low is not None:
        out["pred_point"] = out["pred_point"].clip(lower=low)
    if high is not None:
        out["pred_point"] = out["pred_point"].clip(upper=high)

    if want_q and offsets is not None and np.all(np.isfinite(offsets)):
        q = emit_quantiles(out["pred_point"].to_numpy(dtype=float), offsets,
                           low=low, high=high)
        for i, c in enumerate(("pred_q05", "pred_q25", "pred_q50",
                               "pred_q75", "pred_q95")):
            out[c] = q[:, i]

    excl = out.exclusion_reason.notna()
    if excl.any():                       # excluded rows carry NO values, full lineage
        out.loc[excl, ["pred_point", "pred_sd", "pred_q05", "pred_q25",
                       "pred_q50", "pred_q75", "pred_q95"]] = np.nan
    return out


# --------------------------------------------------------------------------
# 10. the provenance/history sidecar  (Codex defects 6, 7, 10)
# --------------------------------------------------------------------------

SIDECAR_COLS = [
    "schema", "arm_id", "fold_id", "target_key", "row_uid", "config_hash",
    "data_snapshot_hash", "forecast_cutoff", "feature_asof", "component_id",
    "fallback_level", "selected_alpha", "selected_lambda", "residual_pool_n",
    "n_prior_candidate_games", "n_prior_appearances", "n_prior_available_obligations",
    "team_prior_games", "outcome_availability_source", "outcome_availability_policy_id",
    "exclusion_reason",
]


def build_provenance_rows(pred: pd.DataFrame, *, target: str, fold_id: str,
                          config_hash: str, snapshot_hash: str,
                          selected_alpha, selected_lambda, residual_pool_n,
                          hist: pd.DataFrame | None, team_prior: pd.Series | None,
                          availability_source: str, policy_id: str | None
                          ) -> pd.DataFrame:
    """One provenance row per emitted prediction row, carrying what it was made of."""
    n = len(pred)
    out = pd.DataFrame({
        "schema": PROVENANCE_SIDECAR_SCHEMA, "arm_id": ARM_ID, "fold_id": fold_id,
        "target_key": target, "row_uid": pred["row_uid"].to_numpy(),
        "config_hash": config_hash, "data_snapshot_hash": snapshot_hash,
        "forecast_cutoff": pred["forecast_cutoff"].to_numpy(),
        "feature_asof": pred["feature_asof"].to_numpy(),
        "component_id": pred["component_id"].to_numpy(),
        "fallback_level": pred["fallback_level"].to_numpy().astype(int),
        "selected_alpha": np.full(n, np.nan if selected_alpha is None
                                  else float(selected_alpha)),
        "selected_lambda": np.full(n, np.nan if selected_lambda is None
                                   else float(selected_lambda)),
        "residual_pool_n": np.full(n, -1 if residual_pool_n is None
                                   else int(residual_pool_n), dtype=int),
        "outcome_availability_source": availability_source,
        "outcome_availability_policy_id": policy_id if policy_id else "",
        "exclusion_reason": pred["exclusion_reason"].to_numpy(),
    })
    idx = pred.index
    for col, src in (("n_prior_candidate_games", "n_prior_candidate_games"),
                     ("n_prior_appearances", "n_prior_appearances"),
                     ("n_prior_available_obligations", "n_prior_available_obligations")):
        out[col] = (hist[src].reindex(idx).to_numpy().astype(float)
                    if hist is not None else np.nan)
    out["team_prior_games"] = (team_prior.reindex(idx).to_numpy().astype(float)
                               if team_prior is not None else np.nan)
    return out[SIDECAR_COLS]


def sidecar_digest(sidecar: pd.DataFrame) -> str:
    """A content digest over the sidecar, order-independent.

    Sorting on the natural key first means a row-order permutation is not a
    different artifact, but a changed value is. Without this the digest would be
    trivially breakable by a reindex and trivially satisfiable by a reorder.
    """
    d = sidecar.sort_values(["target_key", "row_uid"], kind="mergesort")
    payload = [[("" if pd.isna(v) else v) for v in rec]
               for rec in d[SIDECAR_COLS].astype(object).to_numpy().tolist()]
    return canonical_digest({"schema": PROVENANCE_SIDECAR_SCHEMA,
                             "columns": SIDECAR_COLS, "rows": payload})


def validate_provenance_sidecar(sidecar: pd.DataFrame, preds: dict, *,
                                fold_id: str, config_hash: str,
                                snapshot_hash: str) -> dict:
    """Uniqueness, types, invariants and a ONE-TO-ONE binding to every frame.

    v6's sidecar was never validated or hashed and was bound to nothing, so a
    sidecar from a different fold — or from a different run entirely — could be
    substituted without any receipt noticing. Each clause here closes one way
    that substitution could pass unremarked.
    """
    problems: list[str] = []
    try:
        missing = [c for c in SIDECAR_COLS if c not in sidecar.columns]
        if missing:
            return {"receipt": "provenance_history/1", "ok": False,
                    "problems": [f"sidecar missing columns: {missing}"]}
        if (sidecar["schema"] != PROVENANCE_SIDECAR_SCHEMA).any():
            problems.append(f"sidecar schema is not {PROVENANCE_SIDECAR_SCHEMA!r}")
        if (sidecar["arm_id"] != ARM_ID).any():
            problems.append(f"sidecar arm_id is not uniformly {ARM_ID!r}")
        if (sidecar["fold_id"] != fold_id).any():
            problems.append(f"sidecar fold_id is not uniformly {fold_id!r}")
        if (sidecar["config_hash"].astype(str) != config_hash).any():
            problems.append("sidecar config_hash does not match the run")
        if (sidecar["data_snapshot_hash"].astype(str) != snapshot_hash).any():
            problems.append("sidecar data_snapshot_hash does not match the run")

        if sidecar.duplicated(subset=["target_key", "row_uid"]).any():
            problems.append(
                f"{int(sidecar.duplicated(subset=['target_key', 'row_uid']).sum())} "
                f"duplicate (target_key, row_uid) provenance rows")

        # ---- one-to-one with EVERY prediction frame ----------------------
        for tgt, p in preds.items():
            sub = sidecar[sidecar.target_key == tgt]
            if len(sub) != len(p):
                problems.append(f"{tgt}: sidecar has {len(sub)} rows for "
                                f"{len(p)} predictions")
            if set(sub.row_uid) != set(p.row_uid):
                problems.append(f"{tgt}: sidecar row_uid set does not equal the "
                                f"prediction row_uid set")
                continue
            j = p[["row_uid", "component_id", "fallback_level", "feature_asof",
                   "forecast_cutoff"]].merge(
                sub[["row_uid", "component_id", "fallback_level", "feature_asof",
                     "forecast_cutoff"]], on="row_uid", suffixes=("", "__sc"))
            for c in ("component_id", "fallback_level", "feature_asof",
                      "forecast_cutoff"):
                bad = int((j[c].astype(str) != j[f"{c}__sc"].astype(str)).sum())
                if bad:
                    problems.append(f"{tgt}: {bad} rows where sidecar {c} disagrees "
                                    f"with the emitted prediction")
        extra = set(sidecar.target_key) - set(preds)
        if extra:
            problems.append(f"sidecar carries targets not emitted: {sorted(extra)}")

        # ---- types and invariants ---------------------------------------
        lvl = pd.to_numeric(sidecar.fallback_level, errors="coerce")
        if lvl.isna().any() or (lvl % 1 != 0).any() or (lvl < 0).any() \
                or (lvl > MAX_FALLBACK_LEVEL).any():
            problems.append(f"fallback_level must be an integer 0..{MAX_FALLBACK_LEVEL}")
        rp = pd.to_numeric(sidecar.residual_pool_n, errors="coerce")
        if rp.isna().any() or (rp % 1 != 0).any() or (rp < -1).any():
            problems.append("residual_pool_n must be an integer >= -1 (-1 = not applicable)")

        cand = pd.to_numeric(sidecar.n_prior_candidate_games, errors="coerce")
        app = pd.to_numeric(sidecar.n_prior_appearances, errors="coerce")
        avail = pd.to_numeric(sidecar.n_prior_available_obligations, errors="coerce")
        have = cand.notna() & app.notna()
        if have.any() and (app[have] > cand[have]).any():
            problems.append("prior appearances exceed prior candidate obligations")
        have2 = app.notna() & avail.notna()
        if have2.any() and (app[have2] > avail[have2]).any():
            problems.append("prior appearances exceed AVAILABLE prior obligations; "
                            "an appearance was counted from an outcome that was not "
                            "yet knowable")
        for c in ("n_prior_candidate_games", "n_prior_appearances",
                  "n_prior_available_obligations", "team_prior_games"):
            v = pd.to_numeric(sidecar[c], errors="coerce")
            if (v.dropna() < 0).any():
                problems.append(f"{c} must be non-negative where present")

        src = set(pd.unique(sidecar.outcome_availability_source))
        if not src <= {"observed", "policy"}:
            problems.append(f"unexpected outcome_availability_source values: "
                            f"{sorted(src - {'observed', 'policy'})}")
        if "policy" in src:
            pol = sidecar.loc[sidecar.outcome_availability_source == "policy",
                              "outcome_availability_policy_id"]
            if (pol.astype(str) != OUTCOME_AVAILABILITY_POLICY_ID).any():
                problems.append("policy-derived availability rows must name the "
                                "registered policy id")
        if "observed" in src:
            pol = sidecar.loc[sidecar.outcome_availability_source == "observed",
                              "outcome_availability_policy_id"]
            if (pol.astype(str) != "").any():
                problems.append("observed availability rows must NOT carry a policy "
                                "id; a policy timestamp is not an observation")

        return {"receipt": "provenance_history/1", "ok": not problems,
                "problems": problems, "schema": PROVENANCE_SIDECAR_SCHEMA,
                "n_rows": int(len(sidecar)),
                "digest": sidecar_digest(sidecar),
                "targets": sorted(set(sidecar.target_key))}
    except Exception as exc:                       # fail closed, never raise
        return {"receipt": "provenance_history/1", "ok": False,
                "problems": [f"sidecar validator raised {type(exc).__name__}: {exc}"]}


# --------------------------------------------------------------------------
# 11. exclusion cross-tab  (Codex defect 6)
# --------------------------------------------------------------------------

def exclusion_receipt(preds: dict, universe: pd.DataFrame) -> dict:
    """Cross-tab exclusions and raise the outcome-selection alarm.

    Standing obligation: if exclusion predicts non-appearance, the run is VOID —
    that is outcome selection wearing a coverage costume.
    """
    cols = ["row_uid"] + [c for c in ("in_target_box", "appeared")
                          if c in universe.columns]
    per_target, alarm, total = {}, False, 0
    for tgt, p in preds.items():
        j = p[["row_uid", "exclusion_reason"]].merge(universe[cols], on="row_uid",
                                                     how="left")
        ex = j[j.exclusion_reason.notna()]
        entry = {"n_excluded": int(len(ex)),
                 "by_reason": ex.exclusion_reason.value_counts().to_dict()}
        total += len(ex)
        if "appeared" in j.columns and len(ex):
            entry["excluded_appeared_rate"] = float(ex["appeared"].astype(float).mean())
            entry["overall_appeared_rate"] = float(j["appeared"].astype(float).mean())
            entry["outcome_selection_alarm"] = bool(
                entry["excluded_appeared_rate"] == 0.0 and entry["n_excluded"] > 0)
        else:
            entry["outcome_selection_alarm"] = False
        alarm = alarm or entry["outcome_selection_alarm"]
        per_target[tgt] = entry
    return {"receipt": "exclusion_crosstab/1", "ok": not alarm,
            "problems": (["exclusion predicts non-appearance: outcome selection"]
                         if alarm else []),
            "n_excluded_total": int(total), "outcome_selection_alarm": alarm,
            "per_target": per_target}


def coverage_receipt(preds: dict, universe: pd.DataFrame) -> dict:
    """Exact obligation coverage per target; anything short of 1.0 fails."""
    per_target, problems = {}, []
    for tgt, p in preds.items():
        req_col = f"prediction_required__{tgt}"
        if req_col not in universe.columns:
            problems.append(f"universe lacks {req_col}")
            continue
        required = set(universe.loc[universe[req_col].astype(bool), "row_uid"])
        covered = required & set(p.row_uid)
        per_target[tgt] = {
            "n_required": len(required), "n_covered": len(covered),
            "n_emitted": int(len(p)),
            "n_excluded": int(p.exclusion_reason.notna().sum()),
            "n_fallback": int(p.is_fallback.sum()),
            "n_cold_start": int(p.is_cold_start.sum()),
            "fallback_levels": {int(k): int(v) for k, v in
                                p.fallback_level.value_counts().sort_index().items()},
            "coverage": (len(covered) / len(required)) if required else float("nan"),
        }
        if required and len(covered) != len(required):
            problems.append(f"{tgt}: {len(required) - len(covered)} required rows "
                            f"neither predicted nor excluded")
    return {"receipt": "coverage/1", "ok": not problems, "problems": problems,
            "per_target": per_target}


# --------------------------------------------------------------------------
# 12. player fold
# --------------------------------------------------------------------------

def run_player_fold(train: pd.DataFrame, test: pd.DataFrame, fold_id: str, *,
                    config_hash: str, snapshot_hash: str,
                    snapshot_manifest: dict | None = None, universe=None,
                    synthetic: bool = True,
                    allow_declared_defaults: bool | None = None,
                    registry_path: Path | str = REGISTRY_PATH) -> dict:
    """All four player targets, every obligation row, with every receipt.

    `train` supplies history and outcomes; `test` supplies *current obligations*.
    Outcome columns on `test` are optional and are used only as later rows'
    history, gated on availability — a test row never needs its own outcome to
    be predicted.
    """
    identity = require_registered_identity(config_hash, snapshot_hash,
                                           snapshot_manifest, synthetic=synthetic,
                                           registry_path=registry_path)
    config_hash = identity["config_hash"]
    snapshot_hash = identity["snapshot_hash"]

    if allow_declared_defaults is None:
        allow_declared_defaults = bool(synthetic)
    if not synthetic and allow_declared_defaults:
        raise AdapterBoundaryError(
            "declared Stage-A defaults are forbidden on the real path; every "
            "registered input must actually be supplied")

    fold = require_outer_fold(train, test, fold_id)

    train = order_obligations(train) if len(train) else train
    test = order_obligations(test)

    # feature_asof is DERIVED from the sources actually read, on both frames on
    # the real path. Synthetic frames may carry a declared column instead.
    if not synthetic:
        feature_asof = resolve_feature_asof_strict(test, REQUIRED_PLAYER_FEATURE_SOURCES)
    elif set(REQUIRED_PLAYER_FEATURE_SOURCES) <= set(test.columns):
        feature_asof = resolve_feature_asof_strict(test, REQUIRED_PLAYER_FEATURE_SOURCES)
    elif "feature_asof" in test.columns:
        feature_asof = test["feature_asof"]
    else:
        raise MissingRequiredInput("no feature source timestamps and no feature_asof")

    # one combined history frame: training rows plus the test fold's own earlier
    # rows, every admission gated on outcome availability
    combined = combine_history_frames(train, test)
    if "appeared" not in combined.columns:
        combined["appeared"] = np.nan

    plan_all = build_walk_forward_plan(
        combined, group_cols=["player_id", "season"],
        sort_cols=list(PLAYER_SORT_KEYS))
    hist_all = player_history_walk_forward(combined, plan_all)
    hist_by_uid = hist_all.set_axis(combined["row_uid"].to_numpy(), axis=0)

    hist_te = hist_by_uid.reindex(test["row_uid"].to_numpy()).set_axis(test.index, axis=0)
    hist_tr = (hist_by_uid.reindex(train["row_uid"].to_numpy())
               .set_axis(train.index, axis=0) if len(train) else None)

    avail_src, policy_id = plan_all.availability_source, plan_all.policy_id
    diag: dict = {"fold_id": fold_id, "selected": {}, "dispersion": {},
                  "fallback_mean": {}, "fitted_state": {},
                  "availability": {"source": avail_src, "policy_id": policy_id},
                  "walk_forward": {
                      "n_rows": int(len(combined)),
                      "mean_admitted_prior": float(np.mean(plan_all.n_admitted)),
                      "max_admitted_prior": int(np.max(plan_all.n_admitted))}}

    ctx = (player_split(train) if len(train) else
           SplitContext(np.array([], dtype=np.int64), np.array([], dtype=np.int64),
                        degenerate=True, reason="empty training window", label="player"))
    diag["degenerate"], diag["reason"] = ctx.degenerate, ctx.reason
    diag["fold_boundary"] = fold

    preds: dict[str, pd.DataFrame] = {}
    prov: list[pd.DataFrame] = []
    no_excl = pd.Series(pd.NA, index=test.index)

    # `_emit` builds a fresh frame, so the emitted rows carry a RangeIndex while
    # `hist_te` carries the test frame's own index. They agree ROW BY ROW because
    # `_emit` preserves `test`'s order, so the history is re-based positionally
    # rather than joined on a label space the two do not share.
    hist_flat = hist_te.reset_index(drop=True)

    def record(tgt, pred, alpha, lam, npool):
        preds[tgt] = pred
        prov.append(build_provenance_rows(
            pred, target=tgt, fold_id=fold_id, config_hash=config_hash,
            snapshot_hash=snapshot_hash, selected_alpha=alpha, selected_lambda=lam,
            residual_pool_n=npool, hist=hist_flat,
            team_prior=None, availability_source=avail_src, policy_id=policy_id))

    # ---- degenerate fold: declared constants, level 1 --------------------
    if ctx.degenerate or len(train) == 0:
        for tgt in PLAYER_TARGETS:
            d = DECLARED[tgt]
            sd = d.get("sd")
            comp = f"{tgt}/declared_constant"
            st = FittedState(target=tgt, fold_id=fold_id, component_id=comp,
                             fallback_mean=d["point"], dispersion_sd=sd,
                             dispersion_method="declared",
                             availability_source=avail_src,
                             availability_policy_id=policy_id,
                             support={"low": d.get("low"), "high": d.get("high")})
            n_prior = hist_te["n_prior_appearances"]
            # the declared constant IS the emitted center and it is finite, so
            # the ladder reads level 1 (degenerate fold) rather than level 3
            # (no center); a row with no history still escalates to 3 on its own.
            lvl = player_fallback_level(test, n_prior,
                                        pd.Series(True, index=test.index),
                                        degenerate=True)
            record(tgt, _emit(
                test, tgt, pd.Series(d["point"], index=test.index),
                pd.Series(sd, index=test.index) if sd else None,
                (np.asarray(QUANTILE_Z) * sd) if sd else None,
                fold_id=fold_id, config_hash=config_hash, snapshot_hash=snapshot_hash,
                model_hash=st.hash(), feature_asof=feature_asof,
                fallback_level=lvl, component_id=pd.Series(comp, index=test.index),
                is_cold=pd.Series(True, index=test.index), n_prior=n_prior,
                exclusion=no_excl, low=d.get("low"), high=d.get("high"),
                want_q=(tgt != "p_active")), None, None, None)
            diag["fitted_state"][tgt] = st.to_dict()
        diag["fallback"] = "declared_constants"
        return _finish(preds, pd.concat(prov, ignore_index=True), diag, universe,
                       fold_id, config_hash, snapshot_hash, fold, identity)

    tuning_mask = pd.Series(False, index=train.index)
    tuning_mask.loc[ctx.tuning_idx] = True
    active_any = train["appeared"].astype(bool)
    all_tune, active_tune = tuning_mask, tuning_mask & active_any

    # ---- p_active: ALL candidate obligations -----------------------------
    base_rate = prefix_mean(train["appeared"].astype(float), ctx, all_tune)
    Xtr = stage_a_features_v7(train, hist_tr, base_rate,
                              allow_declared_defaults=allow_declared_defaults)
    Xte = stage_a_features_v7(test, hist_te, base_rate,
                              allow_declared_defaults=allow_declared_defaults)
    lam, lam_default, inner = _select_lambda(Xtr, train["appeared"].astype(float),
                                             ctx, train)
    tr_idx = ctx.require_tuning(np.asarray(train.index[all_tune]))
    std = Standardizer(Xtr.loc[tr_idx])
    beta = logistic_fit(std.transform(Xtr.loc[tr_idx]),
                        train["appeared"].reindex(tr_idx).to_numpy(float), lam)
    p_hat = pd.Series(logistic_predict(std.transform(Xte), beta), index=test.index)

    comp_pa = "p_active/ridge_logistic_stage_a"
    st_pa = FittedState(target="p_active", fold_id=fold_id, component_id=comp_pa,
                        feature_order=list(P_ACTIVE_FEATURES),
                        scaler_mean=std.mean.tolist(), scaler_std=std.std.tolist(),
                        dropped_features=list(std.dropped), lam=lam,
                        beta=np.round(beta, 12).tolist(), base_rate=base_rate,
                        availability_source=avail_src, availability_policy_id=policy_id,
                        support={"low": 0.0, "high": 1.0})
    diag["selected"].update({"lambda": lam, "lambda_default": lam_default,
                             "lambda_inner_fit_dates": len(inner.fit_dates),
                             "lambda_inner_val_dates": len(inner.val_dates)})
    diag["base_rate"] = base_rate
    diag["fitted_state"]["p_active"] = st_pa.to_dict()

    # p_active's history unit is prior OBLIGATIONS: 0-of-k is evidence.
    n_oblig = hist_te["n_prior_candidate_games"]
    lvl_pa = player_fallback_level(test, n_oblig, np.isfinite(p_hat))
    comp_col_pa = pd.Series(comp_pa, index=test.index).mask(
        lvl_pa > 0, "p_active/declared_constant")
    pa_point = p_hat.where(lvl_pa == 0, DECLARED["p_active"]["point"])
    record("p_active", _emit(
        test, "p_active", pa_point, None, None, fold_id=fold_id,
        config_hash=config_hash, snapshot_hash=snapshot_hash, model_hash=st_pa.hash(),
        feature_asof=feature_asof, fallback_level=lvl_pa, component_id=comp_col_pa,
        is_cold=~hist_te["has_prior_obligation"], n_prior=hist_te["n_prior_appearances"],
        exclusion=no_excl, low=0.0, high=1.0, want_q=False), None, lam, None)

    # ---- conditional targets, ordered tuning with the minutes leg fixed ---
    plan_tr = build_walk_forward_plan(train, group_cols=["player_id", "season"],
                                      sort_cols=list(PLAYER_SORT_KEYS))
    act_tr = train["appeared"].astype(bool)

    def minutes_pred(a):
        return walk_forward_ewma(plan_tr, train["minutes"], a, mask=act_tr)

    m_alpha, _, m_b = select_alpha_bound(minutes_pred, train["minutes"], ctx, active_tune)

    def attempts_pred(a):
        return conditional_center(plan_tr, train, act_tr, "attempts_usage",
                                  minutes_alpha=m_alpha, rate_alpha=a)

    def points_pred(a):
        return conditional_center(plan_tr, train, act_tr,
                                  "player_scoring_distribution",
                                  minutes_alpha=m_alpha, rate_alpha=a)

    a_alpha, _, a_b = select_alpha_bound(attempts_pred, train["fga"], ctx, active_tune)
    p_alpha, _, p_b = select_alpha_bound(points_pred, train["points"], ctx, active_tune)
    diag["selected"].update({"minutes_alpha": m_alpha, "attempts_alpha": a_alpha,
                             "points_alpha": p_alpha,
                             "minutes_alpha_held_fixed_at": m_alpha,
                             "boundaries": {"minutes": m_b, "attempts": a_b,
                                            "points": p_b}})

    # A DNP's recorded zero is an absence, not a small performance, so the
    # activity mask is False wherever `appeared` is absent or null on the
    # combined frame — a test row with no outcome yet simply never enters history.
    act_all = combined["appeared"].astype(float).fillna(0.0).astype(bool)

    def _center(alpha_rate, tgt):
        """The conditional center on the COMBINED frame, aligned to test by uid."""
        s = conditional_center(plan_all, combined, act_all, tgt,
                               minutes_alpha=m_alpha, rate_alpha=alpha_rate)
        return (pd.Series(s.to_numpy(), index=combined["row_uid"].to_numpy())
                .reindex(test["row_uid"].to_numpy()).set_axis(test.index))

    for tgt, alpha, ycol, tr_fn in (
            ("e_minutes_given_active", m_alpha, "minutes",
             lambda: walk_forward_ewma(plan_tr, train["minutes"], m_alpha, mask=act_tr)),
            ("attempts_usage", a_alpha, "fga", lambda: attempts_pred(a_alpha)),
            ("player_scoring_distribution", p_alpha, "points",
             lambda: points_pred(p_alpha))):
        d = DECLARED[tgt]
        fb_mean = prefix_mean(train[ycol].astype(float), ctx, active_tune)
        if not np.isfinite(fb_mean):
            fb_mean = d["point"]
        diag["fallback_mean"][tgt] = fb_mean

        cal = np.intersect1d(ctx.calibration_idx, np.asarray(train.index[act_tr]))
        sd_v, off, method = dispersion(
            residuals(train[ycol].reindex(cal), tr_fn().reindex(cal)),
            min_resid=MIN_RESID_PLAYER)
        if method == "insufficient":
            sd_v = d["sd"]
            off = np.asarray(QUANTILE_Z) * sd_v
        diag["dispersion"][tgt] = {"method": method, "sd": float(sd_v),
                                   "n_resid": int(len(cal))}

        raw = _center(alpha, tgt)
        n_prior = hist_te["n_prior_appearances"]
        lvl = player_fallback_level(test, n_prior, np.isfinite(raw))
        comp = f"{tgt}/walk_forward_active_ewma"
        comp_col = pd.Series(comp, index=test.index).mask(lvl > 0, f"{tgt}/prefix_mean")
        point = raw.where(lvl == 0, fb_mean)

        st = FittedState(target=tgt, fold_id=fold_id, component_id=comp,
                         alphas={"minutes": m_alpha, "attempts": a_alpha,
                                 "points": p_alpha},
                         fallback_mean=fb_mean, dispersion_sd=float(sd_v),
                         dispersion_method=method,
                         dispersion_offsets=np.round(off, 12).tolist(),
                         residual_pool_n=int(len(cal)),
                         availability_source=avail_src, availability_policy_id=policy_id,
                         support={"low": d.get("low"), "high": d.get("high")})
        diag["fitted_state"][tgt] = st.to_dict()
        record(tgt, _emit(
            test, tgt, point, pd.Series(sd_v, index=test.index), off,
            fold_id=fold_id, config_hash=config_hash, snapshot_hash=snapshot_hash,
            model_hash=st.hash(), feature_asof=feature_asof, fallback_level=lvl,
            component_id=comp_col, is_cold=~hist_te["has_prior_appearance"],
            n_prior=n_prior, exclusion=no_excl, low=d.get("low"), high=d.get("high"),
            want_q=True), alpha, None, int(len(cal)))

    return _finish(preds, pd.concat(prov, ignore_index=True), diag, universe,
                   fold_id, config_hash, snapshot_hash, fold, identity)


def _select_lambda(X: pd.DataFrame, y: pd.Series, ctx: SplitContext,
                   frame: pd.DataFrame):
    """v5's chronological inner split, unchanged, re-exported for the v7 runner."""
    from cbs_v5 import select_lambda_chronological
    return select_lambda_chronological(X, y, ctx, frame)


# --------------------------------------------------------------------------
# 13. team fold
# --------------------------------------------------------------------------

def run_team_fold(train: pd.DataFrame, test: pd.DataFrame, fold_id: str, *,
                  config_hash: str, snapshot_hash: str,
                  snapshot_manifest: dict | None = None, universe=None,
                  synthetic: bool = True,
                  registry_path: Path | str = REGISTRY_PATH) -> dict:
    """The team target, with `MIN_PRIOR=5` binding both selection and emission."""
    identity = require_registered_identity(config_hash, snapshot_hash,
                                           snapshot_manifest, synthetic=synthetic,
                                           registry_path=registry_path)
    config_hash = identity["config_hash"]
    snapshot_hash = identity["snapshot_hash"]

    require_team_train_inputs(train)
    require_team_predict_inputs(test)
    fold = require_outer_fold(train, test, fold_id)

    if not synthetic:
        feature_asof = resolve_feature_asof_strict(test, REQUIRED_TEAM_FEATURE_SOURCES)
    elif set(REQUIRED_TEAM_FEATURE_SOURCES) <= set(test.columns):
        feature_asof = resolve_feature_asof_strict(test, REQUIRED_TEAM_FEATURE_SOURCES)
    elif "feature_asof" in test.columns:
        feature_asof = test["feature_asof"]
    else:
        raise MissingRequiredInput("no feature source timestamps and no feature_asof")

    d = DECLARED[TEAM_TARGET]
    tgt = TEAM_TARGET

    combined = combine_history_frames(train, test)

    plan_all = build_walk_forward_plan(combined, group_cols=list(TEAM_HISTORY_GROUP),
                                       sort_cols=list(TEAM_SORT_KEYS))
    plan_tr = build_walk_forward_plan(train, group_cols=list(TEAM_HISTORY_GROUP),
                                      sort_cols=list(TEAM_SORT_KEYS))
    avail_src, policy_id = plan_all.availability_source, plan_all.policy_id

    prior_all = walk_forward_counts(plan_all).reindex(combined.index)
    prior_by_uid = pd.Series(prior_all.to_numpy(),
                             index=combined["row_uid"].to_numpy())
    prior_te = prior_by_uid.reindex(test["row_uid"].to_numpy()).set_axis(test.index)
    prior_tr = walk_forward_counts(plan_tr).reindex(train.index)

    diag: dict = {"fold_id": fold_id, "fold_boundary": fold,
                  "availability": {"source": avail_src, "policy_id": policy_id},
                  "team_min_prior": TEAM_MIN_PRIOR,
                  "n_test_below_min_prior": int((prior_te < TEAM_MIN_PRIOR).sum()),
                  "n_train_eligible_for_selection": int(
                      (prior_tr >= TEAM_MIN_PRIOR).sum())}
    ts = team_split(train)
    diag["degenerate"], diag["reason"] = ts.degenerate, ts.reason
    diag["segment_dates"] = {"T1": len(ts.t1_dates), "T2": len(ts.t2_dates),
                             "T3": len(ts.t3_dates)}
    diag["zero_candidate_team_games"] = int(
        test.get("n_candidates", pd.Series(1, index=test.index)).eq(0).sum())
    no_excl = pd.Series(pd.NA, index=test.index)

    # `_emit` preserves `test`'s row order but rebuilds the index, so the prior
    # counts are re-based positionally rather than joined on differing labels.
    prior_flat = prior_te.reset_index(drop=True)

    def finish_one(pred, alpha, npool):
        sidecar = build_provenance_rows(
            pred, target=tgt, fold_id=fold_id, config_hash=config_hash,
            snapshot_hash=snapshot_hash, selected_alpha=alpha, selected_lambda=None,
            residual_pool_n=npool, hist=None, team_prior=prior_flat,
            availability_source=avail_src, policy_id=policy_id)
        return _finish({tgt: pred}, sidecar, diag, universe, fold_id, config_hash,
                       snapshot_hash, fold, identity)

    if ts.degenerate:
        comp = f"{tgt}/declared_constant"
        st = FittedState(target=tgt, fold_id=fold_id, component_id=comp,
                         fallback_mean=d["point"], dispersion_sd=d["sd"],
                         dispersion_method="declared", min_prior=TEAM_MIN_PRIOR,
                         availability_source=avail_src, availability_policy_id=policy_id,
                         support={"low": d["low"]})
        lvl = team_fallback_level(test, prior_te, pd.Series(True, index=test.index),
                                  degenerate=True)
        diag["fitted_state"] = {tgt: st.to_dict()}
        diag["fallback"] = "declared_constants"
        return finish_one(_emit(
            test, tgt, pd.Series(d["point"], index=test.index),
            pd.Series(d["sd"], index=test.index), np.asarray(QUANTILE_Z) * d["sd"],
            fold_id=fold_id, config_hash=config_hash, snapshot_hash=snapshot_hash,
            model_hash=st.hash(), feature_asof=feature_asof, fallback_level=lvl,
            component_id=pd.Series(comp, index=test.index),
            is_cold=(prior_te == 0), n_prior=prior_te, exclusion=no_excl,
            low=d["low"], high=None, want_q=True), None, None)

    # ---- selection sees ONLY rows with >= MIN_PRIOR admitted prior games ----
    # v6 let a team with one prior game — an "EWMA" over a single observation —
    # vote on the channel alphas and then emit a nonfallback prediction from it.
    eligible = prior_tr >= TEAM_MIN_PRIOR
    ctx1 = ts.context_for_alpha()
    t1_mask = pd.Series(False, index=train.index)
    t1_mask.loc[ts.t1] = True
    sel_mask = t1_mask & eligible
    alphas: dict[str, float] = {}
    for ch in REQUIRED_CHANNELS:
        def chan_pred(a, ch=ch):
            return walk_forward_ewma(plan_tr, train[f"ch_{ch}"], a)
        alphas[ch], _, _ = select_alpha_bound(chan_pred, train[f"ch_{ch}"],
                                              ctx1, sel_mask, grid=ALPHA_GRID)
    diag["channel_alphas"] = alphas
    diag["n_selection_rows"] = int(sel_mask.sum())

    def structural(plan, frame):
        total = None
        for ch in REQUIRED_CHANNELS:
            s = walk_forward_ewma(plan, frame[f"ch_{ch}"], alphas[ch])
            total = s if total is None else total + s
        return total

    ctx2 = ts.context_for_calibration_map()
    struct_tr = structural(plan_tr, train)
    map_idx = np.intersect1d(np.asarray(ctx2.tuning_idx),
                             np.asarray(train.index[eligible]))
    maps = fit_side_maps(train, struct_tr, map_idx)
    diag["calibration_maps"] = maps
    diag["n_calibration_map_rows"] = int(len(map_idx))

    fitted = apply_side_maps(train, struct_tr, maps)
    t3_idx = np.intersect1d(np.asarray(ts.t3), np.asarray(train.index[eligible]))
    sd_v, off, method = dispersion(
        residuals(train["team_points"].reindex(t3_idx), fitted.reindex(t3_idx)),
        min_resid=MIN_RESID_TEAM)
    if method == "insufficient":
        sd_v = d["sd"]
        off = np.asarray(QUANTILE_Z) * sd_v
    diag["dispersion"] = {"method": method, "sd": float(sd_v),
                          "n_resid": int(len(t3_idx))}

    struct_all = structural(plan_all, combined)
    struct_te = pd.Series(struct_all.to_numpy(), index=combined["row_uid"].to_numpy()) \
        .reindex(test["row_uid"].to_numpy()).set_axis(test.index)
    raw = apply_side_maps(test, struct_te, maps)

    lvl = team_fallback_level(test, prior_te, np.isfinite(raw))
    comp = f"{tgt}/walk_forward_channel_ewma_side_map"
    comp_col = pd.Series(comp, index=test.index).mask(lvl > 0, f"{tgt}/declared_constant")
    point = raw.where(lvl == 0, d["point"])

    st = FittedState(target=tgt, fold_id=fold_id, component_id=comp,
                     alphas=dict(alphas),
                     calibration_maps={k: list(v) for k, v in maps.items()},
                     fallback_mean=d["point"], dispersion_sd=float(sd_v),
                     dispersion_method=method,
                     dispersion_offsets=np.round(off, 12).tolist(),
                     residual_pool_n=int(len(t3_idx)), min_prior=TEAM_MIN_PRIOR,
                     availability_source=avail_src, availability_policy_id=policy_id,
                     support={"low": d["low"]})
    diag["fitted_state"] = {tgt: st.to_dict()}
    return finish_one(_emit(
        test, tgt, point, pd.Series(sd_v, index=test.index), off, fold_id=fold_id,
        config_hash=config_hash, snapshot_hash=snapshot_hash, model_hash=st.hash(),
        feature_asof=feature_asof, fallback_level=lvl, component_id=comp_col,
        is_cold=(prior_te == 0), n_prior=prior_te, exclusion=no_excl,
        low=d["low"], high=None, want_q=True), None, int(len(t3_idx)))


# --------------------------------------------------------------------------
# 14. the composite gate  (Codex defect 6)
# --------------------------------------------------------------------------

def _finish(preds, sidecar, diag, universe, fold_id, config_hash, snapshot_hash,
            fold_receipt, identity_receipt) -> dict:
    """Every named receipt, then and only then `scoring_permitted`.

    v6 set `scoring_permitted = all(prediction receipts ok)`, which is a narrower
    claim than its documentation made: a run with a substituted sidecar, an
    exclusion set that predicted non-appearance, or a fold that was never checked
    could still be permitted. Here the permission is the conjunction of every
    receipt the registration names, and a missing universe means NO permission
    rather than a vacuous one.
    """
    receipts = {"identity_binding": identity_receipt, "fold_boundary": fold_receipt}

    prov = validate_provenance_sidecar(sidecar, preds, fold_id=fold_id,
                                       config_hash=config_hash,
                                       snapshot_hash=snapshot_hash)
    receipts["provenance_history"] = prov

    prediction: dict = {}
    if universe is not None:
        for tgt, p in preds.items():
            prediction[tgt] = validate_arm_output_v3(
                p, universe, tgt, expected_arm_id=ARM_ID, expected_fold_id=fold_id,
                expected_config_hash=config_hash, expected_snapshot_hash=snapshot_hash)
        receipts["prediction_validation"] = {
            "receipt": "prediction_validation/1",
            "ok": all(r["ok"] for r in prediction.values()) and bool(prediction),
            "problems": [f"{t}: {p}" for t, r in prediction.items()
                         for p in r.get("problems", [])],
            "per_target": prediction}
        receipts["exclusion_crosstab"] = exclusion_receipt(preds, universe)
        receipts["coverage"] = coverage_receipt(preds, universe)
    else:
        for name in ("prediction_validation", "exclusion_crosstab", "coverage"):
            receipts[name] = {"receipt": name, "ok": False,
                              "problems": ["no universe supplied; this receipt "
                                           "cannot be produced, so it does not pass"]}

    required = ("identity_binding", "fold_boundary", "provenance_history",
                "prediction_validation", "exclusion_crosstab", "coverage")
    failed = [n for n in required if not receipts.get(n, {}).get("ok")]
    permitted = not failed

    return {
        "arm_id": ARM_ID, "fold_id": fold_id,
        "predictions": preds, "provenance_sidecar": sidecar,
        "provenance_sidecar_digest": prov.get("digest"),
        "diagnostics": diag, "receipts": receipts,
        "validation_receipts": prediction,
        "coverage": receipts["coverage"].get("per_target", {}),
        "required_receipts": list(required), "failed_receipts": failed,
        "validated": permitted,
        "scoring_permitted": permitted,
        "scoring_note": "scoring_permitted requires EVERY named receipt to pass; "
                        "this runner computes no accuracy or coverage score in any "
                        "case and reads no file but the registry",
    }
