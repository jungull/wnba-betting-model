#!/usr/bin/env python3
"""p38_wrappers.py -- P38 executor task-specific call-site wrappers (D039 EXEC-M1..M7).

Every object here is a CALL-SITE wrapper in the sense of standing rule 3 and the D039
executor mandates: no frozen file (guards, runner, arm modules, registry) is edited; the
wrappers interpose at the P38 invocation only, in-process, and every interposition is
recorded in the per-arm P38 sidecar and in stage2b/P38_BLINDED_FIT/EXECUTION_LOG.md.

Mandate map (P37 SPEC.json proposed_rulings.severity_b_mandate_map, ratified D039):

  EXEC-M1  P27GuardHarnessView + FoldGovernor: honour the P27 guard's PER-FOLD UNEVALUABLE
           verdicts symmetrically for arm and null, continue with the remaining folds, and
           implement A07's ">= 2 folds" retirement arithmetic. The runner's own escalation
           (guard_harness.p27_check raises on overall FAIL, runner.run_arm aborts the arm)
           is R-F1's fail-closed divergence; this view tolerates a FAIL if and ONLY if every
           offending fold is already excluded from fitting by the P38 fold-governor record,
           and re-raises otherwise. The frozen guard and harness bytes are untouched; the
           interposition is a rebinding of the loaded runner module's `gh` attribute for the
           duration of one run_arm call.
  EXEC-M4  history_bound_a09 / history_bound_a10: constructor-bind the 2,990-row contract
           schedule archive as the n_t/d_t (and c_t) clock, exactly as A11/A12/A13 bind
           theirs, using ONLY the arm's own frozen pure functions (align_n_t_d_t_by_key /
           align_n_t_d_t_c_t_by_key / kappa_contrast). The 2,982-row universe is never used
           as the clock (the barred clock, P35 n_clock_pin).
  EXEC-M5  a03_tier_records: invoke A03's own tier_symmetry_check per fold, arm and null
           identically (the check conditions only on training-row depth values and cluster
           ids, so one evaluation governs both members; exclusion is applied through the
           symmetric fold-governor, which deactivates a fold for BOTH members).
  EXEC-M1/A07  a07_near_affinity_records: the card's S7 near-affinity trigger (R2 >=
           0.998001 OR |spearman| >= 0.999 of exp(-n_i/5) vs pace_evidence_depth on the
           fold's TRAINING rows), evaluated at the call site because the frozen module
           declares the rule but exposes no per-fold callable; ">= 2 unevaluable folds
           retires the hypothesis" is applied by the driver.

  D040     P25FoldLocalGuardView: the EXEC-M1 analogue for the runner's per-fold P25 audit
           (D040_P38_FOLD_LOCAL_P25_AND_A08, ruled a deterministic consequence of D039).
           A fold-local P25 block records FOLD_UNEVALUABLE with the frozen guard's full
           record; the arm fits on its remaining folds; FINAL-design or non-excluded-fold
           blocks re-raise (fail closed). Task-specific wrapper, never a guard edit.

Nothing in this file reads, prints or returns any comparative performance number.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FINAL_FOLD_ID = "FINAL_ASSEMBLED_DESIGN"


# --------------------------------------------------------------------------------- EXEC-M1 --
class P27GuardHarnessView:
    """Delegating view of the guard_harness module for ONE run_arm invocation (EXEC-M1).

    Delegates every attribute to the real guard_harness module. p27_check invokes the real
    wrapper; when the frozen guard returns overall FAIL (which the frozen harness escalates
    to a whole-arm refusal, finding R-F1), this view honours the guard's own per-fold
    verdicts instead, provided EVERY offending fold is already in the P38 deactivation set
    (so it enters neither member's fits) and the failure basis is strictly fold-local:
    games-not-split must hold, and the FINAL_ASSEMBLED_DESIGN must itself be estimable and
    parameter-reconciled. Any other failure basis re-raises -- fail closed.
    """

    def __init__(self, real_gh, allowed_excluded_folds):
        self._real = real_gh
        self._allowed = set(str(f) for f in allowed_excluded_folds)
        self.tolerated_record = None
        self.tolerance_basis = None

    def __getattr__(self, name):
        return getattr(self._real, name)

    def p27_check(self, *args, **kwargs):
        try:
            return self._real.p27_check(*args, **kwargs)
        except Exception as e:  # GuardHarnessFailure carries .record
            rec = getattr(e, "record", None)
            if not isinstance(rec, dict) or rec.get("schema") != \
                    "s7_fold_local_estimability_receipt/1":
                raise
            offending = set(rec.get("folds_marked_unevaluable", []) or [])
            offending |= set(rec.get("folds_with_unreconciled_parameter_counts", []) or [])
            recon = rec.get("pooled_vs_fold_reconciliation", {}) or {}
            ungoverned = set(recon.get("affected_folds_without_an_explicit_verdict", []) or [])
            split_ok = bool((rec.get("games_not_split_check") or {}).get("ok"))
            final_bad = (FINAL_FOLD_ID in offending) or (FINAL_FOLD_ID in ungoverned)
            fold_level = (offending | ungoverned) - {FINAL_FOLD_ID}
            if split_ok and not final_bad and fold_level and \
                    fold_level.issubset(self._allowed):
                self.tolerated_record = rec
                self.tolerance_basis = {
                    "mandate": "EXEC-M1 (R-F1)",
                    "guard_overall": rec.get("overall"),
                    "offending_folds": sorted(fold_level),
                    "all_offending_folds_excluded_from_fits": True,
                    "final_design_estimable": True,
                    "games_not_split": True,
                    "action": ("per-fold UNEVALUABLE verdicts honoured symmetrically for "
                               "arm and null via the P38 fold governor; remaining folds "
                               "proceed; the frozen guard record is carried unmodified in "
                               "the receipt"),
                }
                return rec
            raise


# --------------------------------------------------------------------------------- D040 ----
class P25FoldLocalGuardView(P27GuardHarnessView):
    """Delegating view adding the D040 per-fold P25 tolerance to the EXEC-M1 P27 view.

    D040_P38_FOLD_LOCAL_P25_AND_A08 (DECISION_LEDGER.jsonl), ruled as a deterministic
    consequence of D039/EXEC-M1: a task-specific CALL-SITE wrapper (never a guard edit;
    frozen guard, harness and runner bytes untouched) honours the frozen P25 guard's own
    per-fold verdicts. A fold whose P25 verdict is fold-local-blocked records
    FOLD_UNEVALUABLE -- the frozen guard's complete machine-readable record is returned
    unmodified so it lands in the sealed receipt's guard_records.p25_per_fold[fold_id] --
    and the arm fits on the remaining folds via the P38 fold governor, which has already
    deactivated the fold for arm AND null identically. Any P25 block that is NOT strictly
    fold-local (the FINAL_ASSEMBLED_DESIGN, or a fold not already excluded from fitting)
    re-raises: fail closed.

    The runner's bundle loop calls p25_check once per fold in a deterministic order
    (declared folds in order, then FINAL_ASSEMBLED_DESIGN) but passes no fold id; this view
    is constructed with that exact sequence and cross-checks each call's training-row count
    against the expected fold. Any desynchronisation refuses (never guesses a fold).
    """

    def __init__(self, real_gh, allowed_excluded_folds, p25_fold_sequence):
        super().__init__(real_gh, allowed_excluded_folds)
        # p25_fold_sequence: ordered [(fold_id, expected_training_rows), ...] ending with
        # (FINAL_ASSEMBLED_DESIGN, n_universe_rows)
        self._p25_seq = [(str(fid), int(n)) for fid, n in p25_fold_sequence]
        self._p25_call_index = 0
        self.p25_fold_unevaluable = {}   # fold_id -> full frozen guard record (unmodified)

    def p25_check(self, df, **kwargs):
        i = self._p25_call_index
        if i >= len(self._p25_seq):
            raise RuntimeError(
                "D040 P25 call-site wrapper: more p25_check invocations than declared "
                "folds -- refusing to guess which fold is being audited (fail closed)")
        fid, n_expected = self._p25_seq[i]
        self._p25_call_index += 1
        if int(len(df)) != n_expected:
            raise RuntimeError(
                f"D040 P25 call-site wrapper: fold-order desynchronisation at call {i} "
                f"(expected {n_expected} training rows for fold {fid}, got {len(df)}) -- "
                "fail closed")
        try:
            return self._real.p25_check(df, **kwargs)
        except Exception as e:  # GuardHarnessFailure carries .record (the guard's own)
            rec = getattr(e, "record", None)
            if (isinstance(rec, dict) and fid != FINAL_FOLD_ID
                    and fid in self._allowed):
                # fold-local block on a fold the P38 governor already excludes from
                # fitting (arm AND null): FOLD_UNEVALUABLE per D040; full record kept.
                self.p25_fold_unevaluable[fid] = rec
                return rec
            raise


class FoldGovernor:
    """Symmetric per-fold deactivation wrapper around one arm-module instance (EXEC-M1).

    Delegates every hook to the wrapped module. structurally_deactivated_folds() returns the
    union of the module's own card-pinned deactivations and the P38 per-fold exclusions
    (P27 UNEVALUABLE verdicts, preregistered-rule collapses, A03 tier symmetry, A07 near-
    affinity). The runner's deactivation mechanism is the ONLY exclusion path used: it skips
    the fold for arm AND null identically, excludes it from the pooled delta and from every
    kill's evaluable-fold set, and excludes its seed streams from the manifest.

    LABELLING CAVEAT (recorded, not hidden): the frozen runner marks every deactivated fold
    "STRUCTURALLY_DEACTIVATED / card-pinned structural deactivation". For folds excluded by
    the P38 governor the true basis lives in the per-arm sidecar's fold_exclusions map and
    in EXECUTION_LOG.md; the receipt string is the frozen runner's own wording and is not
    edited.
    """

    def __init__(self, inner, extra_deactivated: dict, build_design_override=None):
        # extra_deactivated: {fold_id: basis_string}
        self._inner = inner
        self._extra = {str(k): str(v) for k, v in (extra_deactivated or {}).items()}
        self._bd = build_design_override

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def structurally_deactivated_folds(self):
        hook = getattr(self._inner, "structurally_deactivated_folds", None)
        base = list(hook()) if callable(hook) else []
        return sorted(set(base) | set(self._extra))

    def build_design(self, fold, universe):
        if self._bd is not None:
            return self._bd(fold, universe)
        return self._inner.build_design(fold, universe)

    @property
    def p38_fold_exclusions(self):
        return dict(self._extra)


# --------------------------------------------------------------------------------- EXEC-M4 --
def history_bound_a09(a09_module, inner, history: pd.DataFrame):
    """build_design override for one A09 instance: the arm's OWN frozen pure functions run
    with the contract-schedule archive as the clock (n_clock_pin), the universe supplying
    target keys only. Column names, design structure and the null are byte-identical to the
    frozen module's return."""
    def build_design(fold, universe):
        n_t, d_t = a09_module.align_n_t_d_t_by_key(
            history, universe, key_cols=("team_id", "game_id"))
        contrast = a09_module.kappa_contrast(n_t, d_t, inner.kappa)
        return {
            "treatment_cols": [a09_module.TREATMENT_COL],
            "nuisance_cols": [a09_module.NUISANCE_COL],
            "k0_matched_design": {"treatment_cols": [],
                                  "nuisance_cols": [a09_module.NUISANCE_COL],
                                  "comparison": "term_removal"},
            "indicator_cols": [],
            "columns": {a09_module.NUISANCE_COL: d_t, a09_module.TREATMENT_COL: contrast},
        }
    return build_design


def history_bound_a10(a10_module, inner, history: pd.DataFrame):
    """As history_bound_a09, for A10 (adds the EWMA recency contrast c_t)."""
    def build_design(fold, universe):
        n_t, d_t, c_t = a10_module.align_n_t_d_t_c_t_by_key(
            history, universe, inner.lam, key_cols=("team_id", "game_id"))
        return {
            "treatment_cols": [a10_module.TREATMENT_COL],
            "nuisance_cols": [a10_module.NUISANCE_COL],
            "k0_matched_design": {"treatment_cols": [],
                                  "nuisance_cols": [a10_module.NUISANCE_COL],
                                  "comparison": "term_removal"},
            "indicator_cols": [],
            "columns": {a10_module.NUISANCE_COL: d_t, a10_module.TREATMENT_COL: c_t},
        }
    return build_design


def measure_clock_divergence(align_fn, universe: pd.DataFrame, history: pd.DataFrame,
                             key_cols=("team_id", "game_id")) -> dict:
    """Structural (non-performance) measurement: how many universe rows' (n_t, d_t) differ
    between the barred universe-row clock and the pinned contract-schedule clock. Feature
    construction facts only; no target, no error, no metric."""
    u_n, u_d = align_fn(universe, universe, key_cols=key_cols)
    c_n, c_d = align_fn(history, universe, key_cols=key_cols)
    n_diff = int(np.sum(u_n != c_n))
    d_diff = int(np.sum(~np.isclose(u_d, c_d, rtol=0.0, atol=0.0, equal_nan=True)))
    return {"rows_compared": int(len(u_n)),
            "n_t_rows_differing_universe_vs_contract_clock": n_diff,
            "d_t_rows_differing_universe_vs_contract_clock": d_diff}


# ----------------------------------------------------------------- FINAL FITS: A24 fallback --
def a24_registry_fallback_build_design(a24_module, inner, amendment_payload: dict,
                                       scope_record_path=None):
    """build_design override for A24 implementing the REGISTRY-ADJUDICATED franchise-debut
    fallback (arm_registry.jsonl record 51, experiment_id
    A24_rest_level_symmetric__franchise_debut_fallback_p37; D039 option (a), appended by the
    coordinator single-writer BEFORE this fit).

    The frozen module arm_a24.py FAILS CLOSED on rows with no prior contract-schedule game
    because its card's own text never pinned a fallback -- correctly, per its GENUINE GAP
    DISCLOSED note. The registry amendment closes that gap with an operative RULE sentence:
    "For any team t and game g such that t has played no prior CONTRACT-SCHEDULE game
    before g (t's franchise-debut game), define rest(t, g) := cap (10) -- the debuting team
    is treated as fully rested. This extends the domain of rest(.,.) to a TOTAL FUNCTION
    over the real universe", with x computed unchanged by the frozen formula. This override
    runs the arm's OWN frozen pure functions (feature_construction.rest_level_symmetric and
    _lookup_by_opponent -- byte-untouched) and applies the rule's substitution exactly
    where the rule's own predicate holds (no strictly-earlier contract-schedule row).

    MEASURED CONTRADICTION IN THE AMENDMENT, RECORDED AND NEVER SILENTLY RECONCILED: the
    amendment's subordinate enumeration claims "Affected rows: exactly 3 debut games ... 6
    rows total. No other row is affected: only a team with zero prior contract-schedule
    games triggers the fallback, and each of the three named teams triggers it on exactly
    one game". On the real universe the rule's own predicate is ALSO structurally true for
    the four 2021 teams whose first contract-schedule game was NOT on the 2021-05-14
    opening-day slate (the archive itself begins 2021-05-14, so a 2021-05-15 first game has
    no prior contract row): teams 1611661319/1611661322/1611661328/1611661329, 4 own-side
    rows across 2 games (those teams played each other), for a measured total of 7 own-side
    predicate rows / 10 affected rows / 5 games -- vs the registered 3/6/3. The RULE
    sentence is the operative frozen text and is the only reading under which the
    amendment's own registered purpose ("a total function over the real universe") is
    achieved; reading the enumeration as a scope limit would leave 4 rows undefined and the
    arm unfittable, defeating the amendment's stated intent. Per the program's frozen-text-
    precedence discipline (the same basis as EXEC-M6), the rule's predicate governs; this
    wrapper VERIFIES structurally, per call, that every predicate row is either (i) one of
    the three registered franchise debuts (2025/2026), or (ii) an archive-start 2021 row (a
    team's first-ever contract-schedule game in the archive's own first season) -- ANY
    other predicate row fails closed -- and seals the full measured-vs-registered record
    in A24_REGISTRY_FALLBACK_SCOPE_RECORD.json (dependency diagnostics only; no
    performance number exists at design time). Identical in arm and null by construction
    (row-construction layer, shared by both members). No frozen file is edited; this is
    the same call-site-wrapper discipline as EXEC-M4 (history_bound_a09).
    """
    fc = a24_module.fc
    registered_debut_teams = {1611661331, 1611661327, 1611661332}
    registered_facts = {"n_own_side_rows": 3, "n_affected_rows": 6, "n_affected_games": 3,
                        "teams": sorted(registered_debut_teams)}

    def build_design(fold, universe):
        for c in ("team_id", "opp_team_id", "game_id", "game_date"):
            if c not in universe.columns:
                raise fc.A24ConstructionFailure(
                    f"universe is missing required column {c!r} (team/opponent/game identity)")
        cs = inner._contract_schedule
        out = fc.rest_level_symmetric(
            universe["team_id"].to_numpy(), universe["opp_team_id"].to_numpy(),
            universe["game_id"].to_numpy(), universe["game_date"].to_numpy(),
            history_team_id=cs["team_id"].to_numpy(),
            history_game_date=cs["game_date"].to_numpy(),
            history_game_id=cs["game_id"].to_numpy())

        undef_own = out["undefined_own"]
        affected = np.isnan(out["x"])
        affected_games = set(str(g) for g in universe["game_id"].to_numpy()[affected])

        # structural verification of the rule's predicate, row by row, against the
        # contract schedule itself (fail closed on ANY row outside the two verified
        # structural classes).
        cs_sorted = cs.sort_values(["game_date", "game_id"], kind="mergesort")
        first_cs = cs_sorted.groupby("team_id", sort=False).first()
        archive_first_season = int(pd.to_datetime(cs["game_date"]).dt.year.min())
        predicate_rows = []
        for i in np.flatnonzero(undef_own):
            t = int(universe["team_id"].iloc[i])
            g = str(universe["game_id"].iloc[i])
            gd = pd.Timestamp(universe["game_date"].iloc[i])
            if t not in first_cs.index:
                raise fc.A24ConstructionFailure(
                    f"A24 registry fallback: predicate row team {t} absent from the "
                    "contract schedule entirely -- fail closed")
            frow = first_cs.loc[t]
            n_prior = int(((cs["team_id"].to_numpy() == t)
                           & (pd.to_datetime(cs["game_date"]).to_numpy()
                              < np.datetime64(gd))).sum())
            is_first_cs_game = (str(frow["game_id"]) == g) and (n_prior == 0)
            season = int(gd.year)
            if t in registered_debut_teams:
                klass = "registered_franchise_debut"
                ok = is_first_cs_game and season >= 2025
            else:
                klass = "archive_start_2021_boundary_row"
                ok = is_first_cs_game and season == archive_first_season
            if not ok:
                raise fc.A24ConstructionFailure(
                    f"A24 registry fallback: predicate row (team {t}, game {g}, season "
                    f"{season}) is not structurally verified as {klass} -- failing closed "
                    "rather than applying the fallback beyond the rule's own predicate")
            predicate_rows.append({"row_index": int(i), "team_id": t, "game_id": g,
                                   "season": season, "class": klass})
        if not registered_debut_teams.issubset(
                {r["team_id"] for r in predicate_rows}):
            raise fc.A24ConstructionFailure(
                "A24 registry fallback: the three registered franchise debuts were not all "
                "found among the measured predicate rows -- the registered facts and the "
                "measured universe disagree in a direction the rule text cannot explain; "
                "fail closed")
        measured_facts = {
            "n_own_side_rows": int(undef_own.sum()),
            "n_affected_rows": int(affected.sum()),
            "n_affected_games": len(affected_games),
            "teams": sorted({r["team_id"] for r in predicate_rows}),
        }
        scope_contradiction = (measured_facts["n_own_side_rows"]
                               != registered_facts["n_own_side_rows"])
        if scope_record_path is not None and not scope_record_path.exists():
            import json as _json
            scope_record_path.parent.mkdir(parents=True, exist_ok=True)
            scope_record_path.write_text(_json.dumps({
                "schema": "p38_a24_registry_fallback_scope_record/1",
                "amendment_experiment_id": amendment_payload.get("experiment_id"),
                "rule_operative_text": (amendment_payload.get("rule") or "")[:1200],
                "registered_enumeration": registered_facts,
                "measured_enumeration": measured_facts,
                "measured_predicate_rows": predicate_rows,
                "affected_game_ids": sorted(affected_games),
                "contradiction_recorded": scope_contradiction,
                "contradiction_statement": (
                    "The amendment's registered enumeration ('exactly 3 debut games ... 6 "
                    "rows total. No other row is affected') is measured FALSE on the real "
                    "universe: the rule's own predicate (no prior contract-schedule game) "
                    "is also structurally true for the four 2021 teams whose first "
                    "contract game was 2021-05-15 (the archive begins 2021-05-14; an "
                    "archive-start boundary fact, not a franchise debut). Measured: 7 "
                    "own-side rows / 10 affected rows / 5 games. The RULE sentence is the "
                    "operative frozen text (frozen-text precedence, the EXEC-M6 basis) "
                    "and the only reading achieving the amendment's own registered "
                    "purpose, 'extends the domain of rest(.,.) to a total function over "
                    "the real universe'; the enumeration's error is REPORTED here and in "
                    "EXECUTION_LOG.md, never silently reconciled."
                    if scope_contradiction else
                    "measured enumeration matches the registered enumeration"),
                "identical_in_arm_and_null": True,
                "no_performance_numbers": True,
            }, indent=2, sort_keys=True), encoding="utf-8")

        # the amendment's rule: rest := cap on the predicate side => f = min(cap, cap) = cap.
        f_own_ext = np.where(undef_own, fc.CAP_DAYS, out["f_own"])
        f_opp_ext = fc._lookup_by_opponent(
            universe["game_id"].to_numpy(), universe["team_id"].to_numpy(),
            universe["opp_team_id"].to_numpy(), f_own_ext)
        x = (f_own_ext + f_opp_ext) / 2.0
        if not np.all(np.isfinite(x)):
            raise fc.A24ConstructionFailure(
                "A24 registry fallback: x is still undefined on "
                f"{int(np.sum(~np.isfinite(x)))} row(s) after the amendment's fallback -- "
                "failing closed")

        return {
            "treatment_cols": [a24_module.TREATMENT_COL],
            "nuisance_cols": [],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": [],
                                  "comparison": "term_removal"},
            "indicator_cols": [],
            "columns": {a24_module.TREATMENT_COL: x},
            "diagnostics": {
                "fold_id": str(fold.get("fold_id")) if isinstance(fold, dict) else None,
                "n_rows": int(len(universe)),
                "registry_fallback_applied": {
                    "experiment_id": amendment_payload.get("experiment_id"),
                    "n_own_side_predicate_rows": int(undef_own.sum()),
                    "n_affected_rows": int(affected.sum()),
                    "affected_game_ids": sorted(affected_games),
                    "predicate_team_ids": measured_facts["teams"],
                    "substituted_value": float(fc.CAP_DAYS),
                    "registered_vs_measured_contradiction_recorded": scope_contradiction,
                    "scope_record": "A24_REGISTRY_FALLBACK_SCOPE_RECORD.json",
                },
            },
        }
    return build_design


# --------------------------------------------------------------------------------- EXEC-M5 --
def a03_tier_records(a03_module, universe: pd.DataFrame, folds: list) -> dict:
    """A03 tier_symmetry_check per real fold. The check conditions only on training-row
    depth and cluster ids -- identical inputs for arm and null -- so one evaluation per fold
    governs both members; symmetry of APPLICATION is delivered by the fold governor, which
    deactivates a triggered fold for both members at once."""
    out = {}
    for f in folds:
        rec = a03_module.tier_symmetry_check(universe, f["train_idx"])
        out[str(f["fold_id"])] = rec
    return out


# ---------------------------------------------------------------------------- A07 (EXEC-M1) --
def _spearman_abs(x: np.ndarray, y: np.ndarray) -> float:
    rx = pd.Series(x).rank(method="average").to_numpy(float)
    ry = pd.Series(y).rank(method="average").to_numpy(float)
    if np.std(rx) == 0.0 or np.std(ry) == 0.0:
        return 0.0
    return float(abs(np.corrcoef(rx, ry)[0, 1]))


def _r2_on_intercept_and_x(y: np.ndarray, x: np.ndarray) -> float:
    """R2 of regressing y on [1, x] (the near-affinity R2 of the card's condition check)."""
    X = np.column_stack([np.ones(len(x)), np.asarray(x, float)])
    beta, *_ = np.linalg.lstsq(X, np.asarray(y, float), rcond=None)
    resid = y - X @ beta
    sst = float(np.sum((y - np.mean(y)) ** 2))
    if sst == 0.0:
        return 1.0
    return float(1.0 - float(np.sum(resid ** 2)) / sst)


def a07_near_affinity_records(transient: np.ndarray, depth: np.ndarray,
                              folds: list, r2_threshold: float,
                              spearman_threshold: float) -> dict:
    """The A07 card's S7 near-affinity trigger per fold, training rows only (both columns
    are pre-outcome constructions; nothing here touches the target)."""
    out = {}
    for f in folds:
        tr = np.asarray(f["train_idx"], int)
        t, d = np.asarray(transient, float)[tr], np.asarray(depth, float)[tr]
        r2 = _r2_on_intercept_and_x(t, d)
        sp = _spearman_abs(t, d)
        fired = bool(r2 >= r2_threshold or sp >= spearman_threshold)
        out[str(f["fold_id"])] = {
            "r2_transient_on_depth": r2, "abs_spearman": sp,
            "r2_threshold": r2_threshold, "spearman_threshold": spearman_threshold,
            "trigger_fired": fired,
            "verdict": "UNEVALUABLE_PROSPECTIVELY" if fired else "ESTIMABLE"}
    return out
