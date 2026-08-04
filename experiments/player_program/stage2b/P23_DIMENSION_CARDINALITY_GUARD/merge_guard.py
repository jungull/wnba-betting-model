#!/usr/bin/env python3
"""merge_guard.py -- CALL-SITE dimension-merge cardinality guard (S2).

Epistemic status: INFRASTRUCTURE + task-specific INVARIANT. Proves a dimension merge cannot
silently change the row universe. Does NOT establish that any dimension is scientifically usable.

Why this module exists
----------------------
`GATE_INVOCATION_CONTRACT.md` section 7.3 states plainly that `feature_gate.py` "sees the
assembled matrix, not how it was built". A dimension merge that fans a fact frame out from 2,982
to 3,228 rows produces a matrix that is entirely innocent to every check `feature_gate.audit`
performs: no duplicate column, no collinearity, no rank deficiency. The corruption is in the ROW
UNIVERSE, and the row universe is not a property of the design matrix.

V2_STOP_CONDITION S2 is the concrete case. `data/reference/team_cities.csv` carries 16 rows over
15 distinct `team_id`, because `team_id` 1611661317 appears twice for the PHO/PHX rebrand. A naive
`merge(on="team_id")` duplicates that franchise's rows. Separately `last_season` is float64 with
15 of 16 values null, so a null-unsafe interval filter drops every current franchise.

This module is a CALL-SITE wrapper. It edits no shared gate. It is imported by the code that
performs a dimension merge, and it fails that merge closed.

What it enforces
----------------
1. every merge declares explicit left keys, right keys and an expected cardinality (`"m:1"`/`"1:1"`);
2. row count, game key SET and team-game key SET are asserted unchanged across the merge;
3. duplicate primary keys on the dimension side are REJECTED before the merge runs, and any
   observed fan-out fails the merge;
4. null expansion is measured and reported per imported column, split into the part attributable
   to unmatched fact rows and the part already present in the dimension source;
5. a multi-row dimension key is resolved ONLY through DECLARED effective-date / season interval
   columns. If the declared interval semantics do not yield exactly one dimension row per required
   (key, effective-value) pair, `AmbiguousDimensionError` is raised and the caller's contract is to
   EXCLUDE the feature family. There is no guessing path;
6. an open-ended (null) interval endpoint must be declared by the caller as an explicit semantic
   choice. An undeclared null endpoint is a hard failure, not a silently-dropped row;
7. deduplication by arbitrary first/last row order is used NOWHERE. `assert_no_order_dependent_dedup`
   scans source text for the constructs that would do it, and is applied to this module by its own
   test suite.

Nothing here is adjudicable away. There is no `adjudicated` escape hatch, because a changed row
universe is Severity A under RESEARCH_CONTRACT_V1 ("wrong prediction universe") and Severity A is
not a matter of local judgement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


class MergeCardinalityFailure(RuntimeError):
    """A dimension merge violated a declared cardinality or row-universe invariant."""


class AmbiguousDimensionError(MergeCardinalityFailure):
    """A multi-row dimension key could not be resolved from DECLARED interval semantics.

    The caller's obligation on this exception is to EXCLUDE the affected feature family. It is
    explicitly NOT to pick a row.
    """


class UndeclaredNullIntervalError(MergeCardinalityFailure):
    """An interval endpoint is null and the caller did not declare what a null endpoint means."""


# --------------------------------------------------------------------------------------------
# row universe
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RowUniverse:
    """An immutable snapshot of the row universe that a merge must preserve exactly.

    `n_rows`, `game_keys` and `team_game_keys` are all captured because they fail independently:
    a fan-out changes `n_rows` and the multiplicity of `team_game_keys` while leaving `game_keys`
    identical, and a null-unsafe inner filter changes all three.
    """

    n_rows: int
    game_col: str
    team_col: str
    game_keys: frozenset
    team_game_keys: frozenset

    @classmethod
    def capture(cls, df: pd.DataFrame, game_col: str = "game_id",
                team_col: str = "team_id") -> "RowUniverse":
        for c in (game_col, team_col):
            if c not in df.columns:
                raise MergeCardinalityFailure(
                    f"cannot capture row universe: column {c!r} absent from frame with columns "
                    f"{list(df.columns)[:12]}")
        tg = list(zip(df[game_col].tolist(), df[team_col].tolist()))
        if len(set(tg)) != len(tg):
            raise MergeCardinalityFailure(
                f"the frame is already non-unique on ({game_col}, {team_col}): "
                f"{len(tg)} rows, {len(set(tg))} distinct team-game keys. A row universe cannot be "
                f"captured from a frame that is already fanned out.")
        return cls(n_rows=int(len(df)), game_col=game_col, team_col=team_col,
                   game_keys=frozenset(df[game_col].tolist()),
                   team_game_keys=frozenset(tg))

    def describe(self) -> dict:
        return {"n_rows": self.n_rows, "n_game_keys": len(self.game_keys),
                "n_team_game_keys": len(self.team_game_keys),
                "game_col": self.game_col, "team_col": self.team_col}

    def assert_unchanged(self, df: pd.DataFrame, context: str) -> dict:
        """Assert the post-merge frame has the identical row universe. Raises on any difference."""
        problems: list[dict] = []
        if len(df) != self.n_rows:
            problems.append({"kind": "row_count_changed", "before": self.n_rows,
                             "after": int(len(df)), "delta": int(len(df) - self.n_rows)})
        after_games = frozenset(df[self.game_col].tolist())
        if after_games != self.game_keys:
            problems.append({"kind": "game_key_set_changed",
                             "n_before": len(self.game_keys), "n_after": len(after_games),
                             "n_lost": len(self.game_keys - after_games),
                             "n_gained": len(after_games - self.game_keys),
                             "example_lost": sorted(map(str, self.game_keys - after_games))[:5],
                             "example_gained": sorted(map(str, after_games - self.game_keys))[:5]})
        tg_list = list(zip(df[self.game_col].tolist(), df[self.team_col].tolist()))
        after_tg = frozenset(tg_list)
        if after_tg != self.team_game_keys:
            problems.append({"kind": "team_game_key_set_changed",
                             "n_before": len(self.team_game_keys), "n_after": len(after_tg),
                             "n_lost": len(self.team_game_keys - after_tg),
                             "n_gained": len(after_tg - self.team_game_keys)})
        if len(tg_list) != len(after_tg):
            counts: dict = {}
            for k in tg_list:
                counts[k] = counts.get(k, 0) + 1
            fanned = {k: v for k, v in counts.items() if v > 1}
            problems.append({"kind": "team_game_key_fan_out",
                             "n_fanned_keys": len(fanned),
                             "n_excess_rows": len(tg_list) - len(after_tg),
                             "max_multiplicity": max(fanned.values()),
                             "example_keys": [list(map(str, k)) for k in list(fanned)[:5]]})
        report = {"context": context, "universe_before": self.describe(),
                  "n_rows_after": int(len(df)), "problems": problems,
                  "preserved": len(problems) == 0}
        if problems:
            raise MergeCardinalityFailure(
                f"[{context}] row universe NOT preserved: {problems}")
        return report


# --------------------------------------------------------------------------------------------
# dimension specification
# --------------------------------------------------------------------------------------------

VALID_CARDINALITIES = ("m:1", "1:1")


@dataclass(frozen=True)
class DimensionSpec:
    """Every field here is mandatory to state. Nothing is inferred from the data.

    `cardinality` is the EXPECTED fact-to-dimension relationship, declared before the merge, and
    is what makes an unexpected fan-out a failure rather than a silent change.

    Interval fields (`effective_from` / `effective_to` / `effective_on`) are how a dimension key
    that legitimately appears on more than one row is resolved. `open_ended_upper_bound` is the
    caller's EXPLICIT declaration of what a null `effective_to` means. It is not defaulted to
    anything permissive because a wrong answer here is exactly the S2 null-unsafe-filter defect.
    """

    name: str
    left_keys: tuple[str, ...]
    right_keys: tuple[str, ...]
    cardinality: str
    value_columns: tuple[str, ...]
    require_total_coverage: bool = True
    effective_from: str | None = None
    effective_to: str | None = None
    effective_on: str | None = None
    open_ended_upper_bound: bool | None = None
    open_ended_lower_bound: bool | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.cardinality not in VALID_CARDINALITIES:
            raise MergeCardinalityFailure(
                f"{self.name}: cardinality must be one of {VALID_CARDINALITIES}, "
                f"got {self.cardinality!r}. It must be DECLARED, never inferred.")
        if len(self.left_keys) != len(self.right_keys):
            raise MergeCardinalityFailure(
                f"{self.name}: left_keys {self.left_keys} and right_keys {self.right_keys} "
                f"differ in arity")
        if not self.left_keys:
            raise MergeCardinalityFailure(f"{self.name}: at least one join key must be declared")
        if not self.value_columns:
            raise MergeCardinalityFailure(
                f"{self.name}: value_columns must be declared explicitly; an undeclared column "
                f"set means the null-expansion report cannot be complete")
        iv = (self.effective_from, self.effective_to, self.effective_on)
        if any(x is not None for x in iv) and not all(x is not None for x in iv):
            raise MergeCardinalityFailure(
                f"{self.name}: effective_from, effective_to and effective_on must be declared "
                f"together or not at all; got {iv}")

    @property
    def has_interval(self) -> bool:
        return self.effective_from is not None

    def describe(self) -> dict:
        return {"name": self.name, "left_keys": list(self.left_keys),
                "right_keys": list(self.right_keys), "cardinality": self.cardinality,
                "value_columns": list(self.value_columns),
                "require_total_coverage": self.require_total_coverage,
                "effective_from": self.effective_from, "effective_to": self.effective_to,
                "effective_on": self.effective_on,
                "open_ended_upper_bound": self.open_ended_upper_bound,
                "open_ended_lower_bound": self.open_ended_lower_bound,
                "notes": self.notes}


# --------------------------------------------------------------------------------------------
# primary-key checks
# --------------------------------------------------------------------------------------------

def _key_tuples(df: pd.DataFrame, cols) -> list:
    return list(zip(*[df[c].tolist() for c in cols]))


def check_dimension_primary_key(dim: pd.DataFrame, spec: DimensionSpec) -> dict:
    """Reject a dimension whose declared primary key is not unique.

    This runs BEFORE any merge. It is the check that catches team_id 1611661317 in
    team_cities.csv, and it is deliberately a hard rejection rather than a warning.
    """
    missing = [c for c in spec.right_keys if c not in dim.columns]
    if missing:
        raise MergeCardinalityFailure(
            f"{spec.name}: declared right_keys {missing} absent from the dimension")
    keys = _key_tuples(dim, spec.right_keys)
    counts: dict = {}
    for k in keys:
        counts[k] = counts.get(k, 0) + 1
    dups = {k: v for k, v in counts.items() if v > 1}
    report = {"dimension": spec.name, "n_rows": int(len(dim)),
              "declared_primary_key": list(spec.right_keys),
              "n_distinct_keys": len(counts),
              "n_duplicated_keys": len(dups),
              "duplicated_keys": {"|".join(map(str, k)): v for k, v in sorted(
                  dups.items(), key=lambda kv: str(kv[0]))},
              "unique": len(dups) == 0}
    if dups:
        raise MergeCardinalityFailure(
            f"{spec.name}: declared primary key {list(spec.right_keys)} is NOT unique -- "
            f"{len(dups)} duplicated key(s) over {len(dim)} rows: {report['duplicated_keys']}. "
            f"Merging on a non-unique key fans the fact frame out. Resolve the key with DECLARED "
            f"effective-date/season interval semantics, or exclude the feature family.")
    return report


# --------------------------------------------------------------------------------------------
# interval resolution -- the ONLY sanctioned way to collapse a multi-row dimension key
# --------------------------------------------------------------------------------------------

def resolve_effective_dimension(dim: pd.DataFrame, spec: DimensionSpec,
                                required_pairs: set) -> tuple[pd.DataFrame, dict]:
    """Collapse a multi-row-per-key dimension to one row per (key..., effective value).

    `required_pairs` is the set of (key..., effective_value) tuples the fact frame actually needs.
    The function asserts EXACTLY ONE dimension interval covers each of them. Zero matches is an
    uncovered pair; two or more is genuine ambiguity. Either raises `AmbiguousDimensionError`.

    Row ORDER is never consulted. No sort, no `keep=`, no `first`/`last`, no positional selection.
    """
    if not spec.has_interval:
        raise MergeCardinalityFailure(
            f"{spec.name}: resolve_effective_dimension requires declared interval columns")
    # `right_keys` are the merge keys on the RESOLVED dimension and therefore include
    # `effective_on`. The RAW dimension is keyed by the remainder -- the natural key whose
    # multiplicity the interval columns exist to resolve.
    natural_keys = tuple(k for k in spec.right_keys if k != spec.effective_on)
    if not natural_keys:
        raise MergeCardinalityFailure(
            f"{spec.name}: right_keys {spec.right_keys} contain no natural key besides "
            f"{spec.effective_on!r}")
    if spec.effective_on not in spec.right_keys:
        raise MergeCardinalityFailure(
            f"{spec.name}: effective_on {spec.effective_on!r} must appear in right_keys "
            f"{spec.right_keys}; the resolved dimension is keyed by (natural key, effective value)")
    for c in (spec.effective_from, spec.effective_to, *natural_keys):
        if c not in dim.columns:
            raise MergeCardinalityFailure(f"{spec.name}: interval column {c!r} absent")

    lo_raw = pd.to_numeric(dim[spec.effective_from], errors="coerce")
    hi_raw = pd.to_numeric(dim[spec.effective_to], errors="coerce")
    n_lo_null, n_hi_null = int(lo_raw.isna().sum()), int(hi_raw.isna().sum())

    if n_hi_null and spec.open_ended_upper_bound is not True:
        raise UndeclaredNullIntervalError(
            f"{spec.name}: {n_hi_null} of {len(dim)} rows have a null {spec.effective_to!r} and "
            f"open_ended_upper_bound was not declared True. A null upper bound is NOT a missing "
            f"value to be filtered away -- filtering it drops every still-current key. Declare "
            f"the semantics explicitly.")
    if n_lo_null and spec.open_ended_lower_bound is not True:
        raise UndeclaredNullIntervalError(
            f"{spec.name}: {n_lo_null} of {len(dim)} rows have a null {spec.effective_from!r} and "
            f"open_ended_lower_bound was not declared True.")

    lo = lo_raw.fillna(-np.inf).to_numpy(float)
    hi = hi_raw.fillna(np.inf).to_numpy(float)

    inverted = int((lo > hi).sum())
    if inverted:
        raise MergeCardinalityFailure(
            f"{spec.name}: {inverted} interval(s) have {spec.effective_from} > {spec.effective_to}")

    keys = _key_tuples(dim, natural_keys)

    # overlap detection, computed pairwise within a key -- order-independent by construction
    by_key: dict = {}
    for i, k in enumerate(keys):
        by_key.setdefault(k, []).append(i)
    overlaps = []
    for k, idxs in by_key.items():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                if lo[i] <= hi[j] and lo[j] <= hi[i]:
                    overlaps.append({"key": "|".join(map(str, k)),
                                     "interval_a": [float(lo[i]), float(hi[i])],
                                     "interval_b": [float(lo[j]), float(hi[j])]})
    if overlaps:
        raise AmbiguousDimensionError(
            f"{spec.name}: {len(overlaps)} overlapping interval pair(s); the declared "
            f"effective-date semantics do not determine a unique row. EXCLUDE this feature "
            f"family. {overlaps[:4]}")

    n_key = len(natural_keys)
    rows, uncovered, ambiguous = [], [], []
    for pair in sorted(required_pairs, key=lambda p: tuple(map(str, p))):
        key, eff = tuple(pair[:n_key]), pair[n_key]
        try:
            effv = float(eff)
        except (TypeError, ValueError):
            uncovered.append({"pair": list(map(str, pair)),
                              "reason": "effective value is not numeric"})
            continue
        hits = [i for i in by_key.get(key, []) if lo[i] <= effv <= hi[i]]
        if len(hits) == 0:
            uncovered.append({"pair": list(map(str, pair)), "reason": "no interval covers it"})
        elif len(hits) > 1:
            ambiguous.append({"pair": list(map(str, pair)), "n_matching_intervals": len(hits)})
        else:
            rec = dim.iloc[hits[0]].to_dict()
            rec[spec.effective_on] = eff
            rows.append(rec)

    report = {"dimension": spec.name, "n_dimension_rows": int(len(dim)),
              "natural_key": list(natural_keys),
              "n_distinct_dimension_keys": len(by_key),
              "n_multi_row_keys": sum(1 for v in by_key.values() if len(v) > 1),
              "multi_row_keys": ["|".join(map(str, k)) for k, v in by_key.items() if len(v) > 1],
              "n_null_upper_bound": n_hi_null, "n_null_lower_bound": n_lo_null,
              "open_ended_upper_bound_declared": spec.open_ended_upper_bound,
              "n_required_pairs": len(required_pairs),
              "n_resolved": len(rows), "n_uncovered": len(uncovered),
              "n_ambiguous": len(ambiguous),
              "uncovered_examples": uncovered[:8], "ambiguous_examples": ambiguous[:8],
              "resolution_basis": (f"declared interval [{spec.effective_from}, "
                                   f"{spec.effective_to}] evaluated at {spec.effective_on}; "
                                   f"row order never consulted"),
              "resolved": len(uncovered) == 0 and len(ambiguous) == 0}

    if ambiguous:
        raise AmbiguousDimensionError(
            f"{spec.name}: {len(ambiguous)} (key, {spec.effective_on}) pair(s) match MORE THAN ONE "
            f"declared interval. The documented semantics do not resolve them. EXCLUDE this "
            f"feature family; do not choose a row. {ambiguous[:4]}")
    if uncovered and spec.require_total_coverage:
        raise AmbiguousDimensionError(
            f"{spec.name}: {len(uncovered)} (key, {spec.effective_on}) pair(s) match NO declared "
            f"interval. The dimension does not cover the fact universe. EXCLUDE this feature "
            f"family or extend the dimension; do not fill from a neighbouring row. "
            f"{uncovered[:4]}")

    # the effective_on column may already be a dimension column name; do not emit it twice
    out_cols = list(dim.columns) + ([spec.effective_on]
                                    if spec.effective_on not in dim.columns else [])
    resolved = pd.DataFrame(rows, columns=out_cols)
    return resolved.reset_index(drop=True), report


# --------------------------------------------------------------------------------------------
# the guarded merge
# --------------------------------------------------------------------------------------------

def null_expansion_report(before: pd.DataFrame, after: pd.DataFrame, dim: pd.DataFrame,
                          spec: DimensionSpec, matched_mask: np.ndarray) -> dict:
    """Measure, per imported column, how many nulls the merge introduced and from where.

    Two sources are distinguished because they have different remedies: nulls on rows the
    dimension did not cover at all, and nulls that were already values in the dimension.
    """
    cols = []
    n_unmatched = int((~matched_mask).sum())
    for c in spec.value_columns:
        if c not in after.columns:
            cols.append({"column": c, "present_after_merge": False})
            continue
        na = after[c].isna().to_numpy()
        n_after = int(na.sum())
        from_unmatched = int((na & ~matched_mask).sum())
        cols.append({
            "column": c,
            "present_after_merge": True,
            "n_null_in_dimension_source": int(dim[c].isna().sum()) if c in dim.columns else None,
            "n_null_after_merge": n_after,
            "null_rate_after_merge": round(n_after / len(after), 8) if len(after) else 0.0,
            "n_null_from_unmatched_fact_rows": from_unmatched,
            "n_null_from_dimension_values": n_after - from_unmatched,
            "null_expansion": n_after > 0,
        })
    return {"n_fact_rows": int(len(before)), "n_unmatched_fact_rows": n_unmatched,
            "unmatched_rate": round(n_unmatched / len(before), 8) if len(before) else 0.0,
            "columns": cols,
            "any_null_expansion": any(c.get("null_expansion") for c in cols)}


def guarded_merge(fact: pd.DataFrame, dim: pd.DataFrame, spec: DimensionSpec,
                  universe: RowUniverse | None = None,
                  game_col: str = "game_id", team_col: str = "team_id"
                  ) -> tuple[pd.DataFrame, dict]:
    """Perform a dimension merge that cannot silently change the row universe.

    Returns `(merged, report)`. Raises `MergeCardinalityFailure` on any violation. There is no
    mode in which a violation returns a frame.
    """
    for c in spec.left_keys:
        if c not in fact.columns:
            raise MergeCardinalityFailure(f"{spec.name}: left key {c!r} absent from the fact frame")
    for c in spec.value_columns:
        if c not in dim.columns:
            raise MergeCardinalityFailure(
                f"{spec.name}: declared value column {c!r} absent from the dimension")
        if c in fact.columns:
            raise MergeCardinalityFailure(
                f"{spec.name}: declared value column {c!r} already exists on the fact frame; the "
                f"merge would produce suffixed columns and the null-expansion report would be "
                f"measuring the wrong column")

    if universe is None:
        universe = RowUniverse.capture(fact, game_col=game_col, team_col=team_col)

    pk = check_dimension_primary_key(dim, spec)

    if spec.cardinality == "1:1":
        lk = _key_tuples(fact, spec.left_keys)
        if len(set(lk)) != len(lk):
            raise MergeCardinalityFailure(
                f"{spec.name}: cardinality declared 1:1 but the fact frame has "
                f"{len(lk) - len(set(lk))} duplicate join key(s)")

    right = dim.loc[:, list(spec.right_keys) + [c for c in spec.value_columns
                                                if c not in spec.right_keys]]
    validate = "m:1" if spec.cardinality == "m:1" else "1:1"
    merged = fact.merge(right, how="left", left_on=list(spec.left_keys),
                        right_on=list(spec.right_keys), validate=validate,
                        indicator="_merge_guard_ind")
    matched = (merged["_merge_guard_ind"].to_numpy() == "both")
    merged = merged.drop(columns=["_merge_guard_ind"])

    uni = universe.assert_unchanged(merged, context=spec.name)
    nulls = null_expansion_report(fact, merged, dim, spec, matched)

    if spec.require_total_coverage and nulls["n_unmatched_fact_rows"] > 0:
        raise MergeCardinalityFailure(
            f"{spec.name}: require_total_coverage is declared but "
            f"{nulls['n_unmatched_fact_rows']} fact row(s) matched no dimension row. Those rows "
            f"would carry silently-imputed nulls into the design.")

    report = {"spec": spec.describe(), "primary_key_check": pk, "row_universe": uni,
              "null_expansion": nulls,
              "observed_cardinality": f"{len(fact)}:{len(merged)}",
              "fan_out_rows": int(len(merged) - len(fact)),
              "passed": True}
    return merged, report


# --------------------------------------------------------------------------------------------
# criterion 6: deduplication by arbitrary row order is used NOWHERE
# --------------------------------------------------------------------------------------------

#: constructs whose result depends on which row happens to come first
ORDER_DEPENDENT_PATTERNS = {
    "drop_duplicates": r"\.drop_duplicates\s*\(",
    "keep_first_or_last": r"keep\s*=\s*['\"](first|last)['\"]",
    "groupby_first": r"\.first\s*\(\s*\)",
    "groupby_last": r"\.last\s*\(\s*\)",
    "nth": r"\.nth\s*\(",
    "head": r"\.head\s*\(",
    "tail": r"\.tail\s*\(",
    "idxmin_idxmax": r"\.idx(min|max)\s*\(",
    "positional_row_pick": r"\.iloc\s*\[\s*0\s*\]",
    "sort_then_take": r"\.sort_values\s*\(",
}


def assert_no_order_dependent_dedup(paths, ignore_lines_matching: str = r"^\s*#") -> dict:
    """Scan source files for constructs that deduplicate by arbitrary first/last row order.

    This is a source-text check, not a runtime one, because the property being asserted is that
    the construct is ABSENT -- a runtime check can only observe the paths it happens to execute.
    Comment lines are ignored so that this module may name the forbidden constructs in prose.
    """
    hits = []
    ig = re.compile(ignore_lines_matching)
    for p in paths:
        p = Path(p)
        if not p.exists():
            hits.append({"file": str(p), "pattern": "__missing__", "line": 0,
                         "text": "file does not exist"})
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if ig.search(line):
                continue
            for name, pat in ORDER_DEPENDENT_PATTERNS.items():
                if re.search(pat, line):
                    hits.append({"file": str(p), "pattern": name, "line": n,
                                 "text": line.strip()[:160]})
    return {"files_scanned": [str(p) for p in paths], "n_hits": len(hits), "hits": hits,
            "clean": len(hits) == 0}
