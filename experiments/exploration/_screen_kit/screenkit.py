"""screenkit -- the shared, tested guard rails for FUTURE E0/E1 exploration screens.

WHY THIS EXISTS
---------------
There is no shared library for exploration screens in this program; every screen is a
self-contained directory that re-implements its own statistics.  The measured consequence is
that the SAME FOUR ERRORS were independently rediscovered, each time at full cost:

  TRAP 1  wrong-null            -- team/game aggregates given a naive ROW-LEVEL permutation null
                                   (anticonservative).  Found 4x.  Cluster-robust SEs are NOT a
                                   substitute; they moved t the WRONG way in two screens.
  TRAP 2  retrospective baseline-- an increment over a baseline that READS THE FUTURE is not a
                                   forecasting increment.  Found 4x.  Names lie: "leave-one-out",
                                   "expected", "pregame", "prior", "baseline" have ALL appeared on
                                   quantities that read the future.
  TRAP 3  byte-scan partition   -- verifying the 2021-2024 partition by regex/text-scanning files.
                                   Failed 3x with false hits (prose about the rule; columns NAMED
                                   `*_team_season` holding dR2 draws).  The check must be on
                                   COLUMN VALUES.
  TRAP 4  weighted-R2 defect    -- `sst = sum((sqrt(w)*y - mean(sqrt(w)*y))**2)` instead of the
                                   standard weighted SST about the weighted mean.  Copy-pasted into
                                   SIX analyze.py files.  Understates dR2 by 0% to 25.3%.

SCOPE
-----
This kit is for NEW screens.  It does NOT retrofit anything.  Standing decision D069 rules that
the six copies of the defective helper in frozen screens STAY AS THEY ARE so their published
numbers remain reproducible.  `wls_r2_DEFECTIVE` below exists ONLY so a new screen can reproduce
a frozen screen's published number before re-running it correctly.

CONVENTION (D069): the adopted default is PLAIN UNWEIGHTED OLS R2 = 1 - SSE/SST with SST about the
UNWEIGHTED mean.  Use `r2_plain` / `delta_r2_plain` unless there is a substantive reason to weight.

PROVENANCE
----------
Adapted, not reinvented, from these FROZEN screens (read-only):
  * `r2_plain`, `delta_r2_plain`          <- E1_I0013_tempo_redundancy/e1_lib.py :: r2()
                                             (identical SST-about-unweighted-mean form)
  * `r2_weighted_standard`                <- E1_I0009_r2_rerun/step23_reproduce_and_rerun.py
                                             :: r2_standard_weighted()
  * `wls_r2_DEFECTIVE`                    <- E1_I0009_r2_rerun/step23_reproduce_and_rerun.py
                                             :: r2_defective(), itself VERBATIM from
                                             E0_I0009_additive_pressure/analyze.py :: wls_r2()
  * `permutation_null` group semantics    <- E1_I0013_tempo_redundancy/e1_lib.py :: GamePerm
                                             ("permute WHICH GROUP's already-computed value each
                                             group receives, then broadcast back to rows.  Nothing
                                             is recomputed.")
  * `_perm_rows` (the deliberate wrong null, reported only for contrast)
                                          <- E1_I0013_tempo_redundancy/e1_lib.py :: perm_rows
                                             and E0_I0013_possession_volume/run_screen.py
  * `assert_partition` value-gate         <- E1_I0013_tempo_redundancy/verify_partition.py
                                             :: looks_like_a_season_column()
  * `check_manifest` field names/verdicts <- E1_I0008_height_mismatch/build_frame.py manifest block
  * `future_leakage_probe`                <- E1_I0009_r2_rerun/step5_baseline_audit_and_gate.py
                                             section (a), the probe that caught the 4th instance
  * `noop_placebo` tolerance behaviour     <- E1_I0008_height_mismatch/stage1_noise_floor.py and
                                             E0_I0013_possession_volume/run_screen.py no-op block
  * `_permute_within_groups` (scheme="within")
                                          <- E0_I0014_residual_heterogeneity/rh_base.py ::
                                             within_block_index()
  * `var_share_between`                   <- E0_I0014_residual_heterogeneity/rh_base.py ::
                                             var_share_between()
  * `r2_of_forecast`                      <- E0_I0014_residual_heterogeneity/rh_base.py ::
                                             r2_plain(y, yhat)  -- SAME NAME, DIFFERENT FUNCTION
                                             from this module's `r2_plain(y, X)`.  See the
                                             NAME COLLISION note on both.
  * `EntitySwap`, `entity_swap_null`      <- E0_I0016_efficiency_predictors/ep_base.py ::
                                             EntitySwap / entity_swap_null (read-only), which the
                                             kit's third user had to build itself because NO valid
                                             permutation scheme existed for the between-entity
                                             question on a within-varying feature.

REVISION HISTORY -- FOUND BY THE KIT'S FIRST REAL USER
------------------------------------------------------
The adoption note for this kit (D077) recorded the deliberate risk that "a shared kit concentrates
failure -- one wrong function would propagate silently into everything downstream and carry more
authority while doing it."  The FIRST screen to use it, `E0_I0015_points_skill_decomposition`,
found four issues within hours.  All four are closed here, each with a regression test in TESTS.py
that FAILS against the pre-fix code:

  P1  CRASH ON BOOLEAN FEATURES.  `bool` passes `pd.api.types.is_numeric_dtype`, so
      `_constant_within` took the numeric branch and `max - min` on numpy booleans raised
      `TypeError: numpy boolean subtract ...`.  `permutation_null` inherited it through the same
      helper.  The 49-assertion suite never exercised a boolean.  Booleans are now handled
      EXPLICITLY (see `_as_float_for_spread`); the loud crash is replaced by correct handling, not
      by a silent coercion, and a bool feature is handed BACK to `stat_fn` as bool.
  P2  `recommended_permutation_level: "row"` -- A DESIGN DEFECT, AND THE SILENT ONE.  The field
      NAME undid the docstring caveat: a field called `recommended_permutation_level` holding the
      value `"row"` reads as the kit RECOMMENDING the anticonservative null, with the kit's
      authority behind it.  That is the exact error this kit exists to prevent.  FIXED BY CHANGING
      THE SEMANTICS: `recommended_permutation_level` is now `None` whenever no coarser level
      exists, `status` carries `NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE`, and the
      bare string `"row"` is only ever reachable through the opt-in field
      `level_if_you_accept_the_anticonservative_row_null`.  *** THIS IS A BREAKING CHANGE. ***
  P3  NAME COLLISION.  `screenkit.r2_plain(y, X)` REFITS OLS.  The screens' own
      `rh_base.r2_plain(y, yhat)` SCORES AN ALREADY-GIVEN FORECAST.  Same name, different
      semantics; the reporter got 0.4747 against a published 0.4694 and briefly believed its
      reproduction had failed.  `r2_of_forecast(y, yhat)` is added; `r2_plain` is UNCHANGED in
      behaviour (frozen screens and committed work depend on it) and both docstrings now say
      plainly which is which.
  P4  MISSING MACHINERY.  Only a between-block permutation scheme existed, and there was no
      paired forecast-versus-forecast machinery -- which is what every skill comparison in this
      program actually needs.  `permutation_null(..., scheme="within")`, `var_share_between` and
      `paired_forecast_comparison` are added, adapted from E0_I0014's rh_base.py (frozen, read
      only), which had to reimplement all three itself.

REVISION HISTORY -- FOUND BY THE KIT'S SECOND AND THIRD REAL USERS
------------------------------------------------------------------
`E0_I0016_efficiency_predictors` (and a second reporter alongside it) found THREE more defects plus
one usage nit.  Each is closed below with a regression test in TESTS.py that FAILS against the
pre-fix code (git 56dc793).

  K0  `assert_partition` RAISED ON CLEAN DATA -- and it is TRAP 3 IN A NEW SHAPE, INSIDE THE GUARD
      BUILT TO STOP TRAP 3.  The date branch auto-detected date columns by
      `"date" in name.lower()`.  *** THE WORD "candi-DATE" CONTAINS "date". ***  So `candidate`,
      `n_candidates`, `mae_with_candidate`, `update_flag` and `validated` were all parsed as dates,
      and `pd.to_datetime` on a FLOAT column DOES NOT RAISE -- it reads the values as epoch
      nanoseconds and returns 1970-01-01.  Year 1970 is outside every real partition, so a frame
      whose every value sits inside 2021-2024 raised `PartitionViolation`.
      THE REAL DEFECT WAS AN ASYMMETRY.  The SEASON branch already had `_is_season_valued`, added
      precisely to stop name-based false hits, with a regression test (`_team_season_2025`).  The
      DATE branch had no equivalent.  `_is_date_valued` is now that equivalent: a name-matched
      column is treated as a date only if its VALUES are dates -- datetime64 dtype outright, or a
      string column that parses at a high rate into years inside [1990, 2100].  A NUMERIC column is
      REFUSED OUTRIGHT: the epoch-nanosecond reading is never used to manufacture a year.
      The obvious workaround was deliberately NOT made the fix: `date_cols=[]` used to silence the
      true check as well as the false one (a real 2026 date passed clean under it).  Datetime-dtype
      columns are therefore ALWAYS checked regardless of `date_cols`.  *** BEHAVIOURAL CHANGE ***,
      see the two declared breaks below.
      The `UserWarning: Could not infer format ...` that the kit emitted on every call with an
      object column is gone: parsing now passes `format="mixed"`, which is also strictly more
      capable (`07/04/2022` now parses; it used to become NaT).
  K1  `future_leakage_probe` STATED A FALSE CONCLUSION IN ITS VERDICT TEXT.  It asserted "That is
      only possible because it CONTAINS the future."  THAT IS NOT TRUE IN GENERAL.  It fired on
      `refB_ppm` versus `refA_ppm` -- BOTH STRICTLY PRIOR-GAMES-ONLY, differing only as estimators.
      A better (less noisy) estimator of a persistent quantity naturally correlates more with the
      entity's future WITHOUT containing any of it.  A caller who trusted that wording would
      discard a clean baseline.  The NUMBERS ARE UNCHANGED; only the claim attached to them is
      fixed.  The probe now says what it actually licenses: a screening flag, consistent with
      leakage AND consistent with a better estimator, which it cannot distinguish.  New neutral
      fields `screening_flag`, `status` and `alternative_explanation` are added; `reads_future` is
      kept for compatibility with its value unchanged, but ITS NAME OVERSTATES -- read `status`.
  K2  A GENUINE CAPABILITY GAP, NOT MISUSE.  No valid permutation scheme existed for the
      BETWEEN-ENTITY question on a WITHIN-VARYING feature.  `scheme=SCHEME_BETWEEN` requires
      constancy within groups (and forcing it with `allow_nonconstant=True` is what this module
      itself calls a p "manufactured rather than measured"); `scheme=SCHEME_WITHIN` is the identity
      when the feature IS constant.  Every expanding-prior candidate is neither: the reporter
      verified with `detect_grouping_level` that NO candidate was constant within its entity-season
      in ANY of 132 cells.  `EntitySwap` / `entity_swap_null` are ported in from
      E0_I0016_efficiency_predictors/ep_base.py (read-only), which had to build them itself.
  K3  USAGE NIT.  `detect_grouping_level`'s `candidate_keys` must be a MAPPING; passing a list gave
      a bare `AttributeError: 'list' object has no attribute 'items'`.  It now raises a `TypeError`
      that names the parameter, the type received, and the shape required.

*** TWO DECLARED BEHAVIOURAL BREAKS IN `assert_partition` (K0) ***  (as D082 declared its one)
  B1  A NUMERIC column whose NAME contains "date" is no longer parsed as a date.  Before: parsed as
      epoch nanoseconds and almost always flagged as a year-1970 violation.  After: recorded in
      `skipped_name_only` and never flagged.  A caller who genuinely stores dates as epoch integers
      must convert the column with `pd.to_datetime(..., unit=...)` FIRST -- the kit will not guess
      an encoding, exactly as `_feature_to_float` refuses to guess one.
  B2  `date_cols` is now ADDITIVE, not exhaustive: datetime64-dtype columns are checked even when
      `date_cols` is given (including `date_cols=[]`).  Before: `date_cols=[]` disabled the date
      check entirely, which is a FALSE-PASS DOOR -- the reporter showed a genuine 2026 date passing
      clean under it.  Pass `include_datetime_dtype_cols=False` for the old behaviour, and say in
      FINDINGS.json why you turned the check off.
      Additionally, a column named EXPLICITLY in `date_cols` whose values are not dates now raises
      `ValueError` rather than being silently skipped: an explicit request that cannot be honoured
      must be loud, never silent.

REVISION HISTORY -- FOUND BY THE KIT'S SEVENTH AND EIGHTH REAL USERS
--------------------------------------------------------------------
`E1_I0020_coldstart_tiering` (seventh) reported K4 and K5; `E1_I0021_heterogeneity_diagnostic`
(eighth) reported K6 and K7.  Nine defects across seven users now.  Each is closed below with a
regression test in TESTS.py that FAILS against the pre-fix code (git 6d6a17c).

*** FALSE-ASSURANCE DEFECTS -- THE CLASS K6 AND K7 BELONG TO, AND THE POINT OF THIS ROUND ***
  The early defects CRASHED or were obviously wrong (P1 TypeError, K0 raising on clean data).  The
  last three are SILENT: a field NAME that endorsed the wrong choice (P2), a guard whose obvious
  workaround HIDES real leaks (K4), and a null that is TOO NARROW (K6).  A defect class that has
  recurred three times is a DESIGN PROPERTY, not bad luck, so name it:

    A FALSE-ASSURANCE DEFECT IS ONE WHERE THE KIT RETURNS A CONFIDENT, WELL-FORMED, NON-CRASHING
    ANSWER THAT IS WRONG IN THE REASSURING DIRECTION.

  There are exactly TWO shapes of it here, and every function in this module is now audited against
  both (see the FALSE-ASSURANCE AUDIT section below):
    SHAPE 1 -- A CONTROL THAT CANNOT FAIL.  It reports "clean" because it tests nothing.  Examples:
      the permute-the-key-and-recompute placebo (`noop_placebo` exists for it); `SCHEME_WITHIN` on
      a feature constant within groups (refused); relabelling the entity key when the statistic is
      a function of the per-entity fits (K7).
    SHAPE 2 -- A NULL THAT IS TOO NARROW.  It reports a small p because the permuted draws destroy
      MORE structure than the null hypothesis says is exchangeable.  Examples: the row-level null
      on a clustered feature (trap 1); `SCHEME_WITHIN` on an AUTOCORRELATED feature (K6).
  Both look identical to a working tool from the outside.  Neither is detectable from the output
  alone.  That is why the kit must refuse or warn rather than leave it to the caller to notice.

  K6  *** `SCHEME_WITHIN` IS ANTICONSERVATIVE FOR AN AUTOCORRELATED REGRESSOR.  PRIORITY. ***
      The within-group shuffle destroys the regressor's SERIAL structure while the response keeps
      its own slow drift, so the null comes out TOO NARROW by exactly the overlap between them.
      MEASURED BY THE REPORTER: p = 0.0015 where an honest null gives 0.39, on a real screen whose
      headline would have been "per-player heterogeneity is real and pooling has been destroying
      it" -- the most consequential result the program could have produced, and a FALSE POSITIVE.
      *** THIS IS THE MODAL CASE, NOT AN EDGE CASE: the program's most common construction is
      `.shift(1).expanding()`, which is autocorrelated BY DESIGN. ***  The reporter measured
      corr(lag-1 within-group acf of x, N1-minus-N4 null-ratio gap) = +0.832 across 48 cells, with
      the gap at 0.004 on both iid negative controls and +0.121/+0.179 on the running-mean
      regressors.  TWO CHANGES, both required:
        (a) `SCHEME_WITHIN_CYCLIC` is added -- a within-group CYCLIC SHIFT that preserves each
            group's marginal distribution AND its serial structure and destroys only the alignment
            to the response.  Ported from `E1_I0021_heterogeneity_diagnostic/hd_base.py ::
            cyclic_shift_within_groups` (read-only), which the reporter had to write itself.
        (b) `permutation_null` now MEASURES the within-group lag-1 autocorrelation of the feature
            and REFUSES `SCHEME_WITHIN` when it is material, naming `SCHEME_WITHIN_CYCLIC`.
            *** BEHAVIOURAL BREAK B3, see below. ***  REFUSE, not warn, and the justification is
            the D086 P2 precedent: the unsafe path must require an EXPLICIT OPT-IN, because a
            warning on a path that still returns a well-formed p is exactly the "silent" failure
            mode P2 was made to prevent -- and that precedent has since been vindicated twice in
            the wild (the seventh user read `status` rather than the field and chose correctly;
            the eighth user's `recommended_permutation_level = None` refusal is what stopped it
            reaching for the row null).  A caller who genuinely wants the shuffle passes
            `accept_serial_structure_destroyed=True` and must say so in FINDINGS.json.
      Also added: `within_group_acf1` as a public helper, and `acf1_within_group` as a per-level
      diagnostic field on `detect_grouping_level` (the reporter's suggestion 3).
  K7  *** THE NATURAL PER-ENTITY CONTROL IS A LITERAL NO-OP -- SHAPE 1, ONE LEVEL DOWN. ***
      "Relabel the player key and refit the per-player coefficients" is the control an analyst
      reaches for FIRST when validating per-player work, and it TESTS NOTHING: relabelling ids is a
      bijection on whole groups, so every player's row set travels intact to its new label and the
      multiset of fitted coefficients -- and therefore its spread -- is EXACTLY unchanged.  The
      reporter confirmed it at observed sd = 5.207e-17 over 3 distinct draw values.
      *** THIS IS NOT A BUG IN `noop_placebo`. ***  It worked exactly as designed and correctly
      reported a no-op.  THE DEFECT IS THAT THE KIT OFFERED NO ALTERNATIVE AND NO GUIDANCE: a tool
      that says "your control is vacuous" and stops there leaves the caller stuck.  `per_entity_
      control` is added: it runs the vacuous relabel arm AND a genuine arm that actually perturbs
      the fitted per-entity structure (a within-entity CYCLIC shift of the feature, so the per-
      entity fits really do change while each entity keeps its sample size, its marginal and its
      serial structure), and it reports both side by side with a verdict.  `noop_placebo`'s no-op
      verdict now NAMES that alternative instead of ending at the diagnosis.
  K4  `assert_partition` RAISED ON CLEAN DATA when a YEAR-VALUED PLAYER ATTRIBUTE is present
      (`draft_year` 2002-2020, `birth_year`, `grad_year`, `founded`).  *** IT IS NOT A REPEAT OF
      K0, AND IT WAS NOT FIXED THE SAME WAY. ***  K4 SATISFIES the K0 invariant: the name token
      "year" NOMINATES the column, the value gate `_is_season_valued` is asked "are these years?"
      and answers YES, correctly, and the column is then checked against a partition it legitimately
      PREDATES.  THE GATE WAS ANSWERING THE WRONG QUESTION:
          it asks              "are these values plausible YEARS?"
          the partition needs  "is this column the ROW'S OBSERVATION SEASON?"
      Every year-valued attribute of a person or an organisation answers YES to the first and NO to
      the second.  TWO CHANGES:
        (a) DIRECTION IS NOW EXPLICIT.  An out-of-partition value is classified as `FUTURE` (>
            max(allowed) -- the holdout direction, the whole reason the guard exists), `INTERIOR`
            (inside the span but not in `allowed`) or `PAST` (< min(allowed) -- historical, and it
            CANNOT be a holdout leak).  For an AUTO-DETECTED column a purely PAST verdict is
            recorded in the new `historical_year_cols` field and is NOT fatal.  FUTURE and INTERIOR
            stay fatal in every column.  A column the caller NAMES in `season_cols` stays STRICT IN
            BOTH DIRECTIONS -- naming it asserts that it IS an observation season, and that
            assertion is honoured loudly.  Violations are also returned as STRUCTURED RECORDS
            (`violation_records`: col/kind/direction/values/fatal) so a caller can adjudicate
            without parsing the guard's own prose, which is the textual check this module forbids.
        (b) THE OBVIOUS WORKAROUND IS CLOSED, exactly as B2 closed `date_cols=[]`.  Pre-fix,
            `season_cols=["season"]` silenced the false alarm AND SILENCED A GENUINE 2026 LEAK in
            `source_season`, a column the caller never named.  `season_cols` is now ADDITIVE, not
            exhaustive: name-matched columns are ALWAYS value-tested as well.  *** BEHAVIOURAL
            BREAK B4, see below. ***
      NOT DONE, and deliberately: the reporter's suggestion (3) of an `_ATTRIBUTE_YEAR_TOKENS`
      nomination list.  Direction subsumes it -- every case the token list would route to the
      historical branch is already routed there BY ITS VALUES -- and adding a third name-based
      mechanism to a module whose standing audit says "a substring match may only ever nominate a
      column for a value test" buys nothing and costs a maintenance surface.  A `draft_year` of
      2026 must still surface, and under direction it does; under the token list it might not.
  K5  USAGE NIT (behaviour correct, message correct).  `permutation_null` raises `TypeError` on a
      str/categorical feature: "the kit will not guess an encoding for you."  That refusal IS the
      right answer -- guessing an encoding would impose an ordering the caller never declared -- but
      group priors over categorical labels (position, draft bucket, depth bucket) are among the most
      natural things to permute in this program, so most users meet it.  NO CODE CHANGE.  A worked
      bijective-codebook example is added to README.md so the round trip is not needed.
  K8  FOUND BY THIS ROUND'S OWN FALSE-ASSURANCE AUDIT, not by a user.  `_group_codes` built a
      composite key as `codes * n_levels + next_code`, and `pd.factorize` returns the sentinel -1
      for a NULL key value, so a NaN in ANY key column could make two DIFFERENT key tuples collide
      onto the SAME group code -- e.g. ('B', 3.0) and ('C', NaN) both mapped to 2 in a 6-row frame,
      SILENTLY MERGING TWO GROUPS.  Every consumer of `_group_codes` inherited it: `n_groups` was
      wrong, `constant_within` was wrong, and the permutation itself shuffled values across two
      genuinely different groups while reporting a clean result.  That is SHAPE 1/SHAPE 2 with no
      symptom at all.  Fixed by factorizing with `use_na_sentinel=False`, which gives NULL its own
      real code and makes the composite injective.  *** BEHAVIOURAL CHANGE B5, see below. ***

*** THREE MORE DECLARED BEHAVIOURAL BREAKS ***  (D082 declared one, D086 declared two)
  B3  `permutation_null(scheme=SCHEME_WITHIN)` now RAISES when the feature's within-group lag-1
      autocorrelation exceeds the materiality threshold.  Before: it ran and returned a p that was
      too small, with no signal.  After: it names the measured acf1, the threshold and
      `SCHEME_WITHIN_CYCLIC`.  Pass `accept_serial_structure_destroyed=True` for the old behaviour;
      the result then carries a non-None `warning` and `serial_structure_preserved=False`, and you
      must declare it in FINDINGS.json.  The threshold is `max(0.15, 2/sqrt(n_pairs))` -- a
      materiality floor of 0.15, OR twice the sampling standard error of acf1 under the iid null on
      a small frame, whichever is larger -- and is overridable per call via `acf1_threshold`.
  B4  `season_cols` is ADDITIVE, not exhaustive (the season-branch twin of B2).  Before,
      `season_cols=[...]` REPLACED auto-detection and was therefore a FALSE-PASS DOOR.  After,
      name-matched columns are always value-tested too, and a column named in `season_cols` is
      additionally treated as STRICT IN BOTH DIRECTIONS.  Pass
      `include_name_matched_season_cols=False` for the old behaviour, and say in FINDINGS.json why
      you turned auto-detection off.
  B5  A NULL/NaN value in a composite grouping key now forms its OWN group instead of being folded
      into the -1 sentinel (K8).  Before: silent group collisions.  After: `n_groups` counts the
      NULL cell as a level.  If you were relying on NULL key rows being dropped or merged, they
      never were -- they were being merged with an ARBITRARY other group.

AUDIT: EVERY NAME-BASED DETECTION IN THIS MODULE  (prompted by K0)
------------------------------------------------------------------
K0 is the FOURTH instance in this program of a name-based false hit, and the FIRST one inside the
guard built to prevent them.  A defect class that recurs four times is a design smell, not bad
luck, so the whole module was swept.  There are exactly TWO substring matches on column names:

  1. `_SEASONISH_TOKENS = ("season", "year")` in `assert_partition`.  GUARDED by
     `_is_season_valued` since the kit shipped.  (False hits it stops: `_team_season_2025`
     holding dR2 draws.  False hits it would otherwise take: `years_pro`, `seasonality_index`.)
  2. `_DATEISH_TOKENS = ("date",)` in `assert_partition`.  GUARDED by `_is_date_valued` AS OF K0,
     and unguarded before it.  (`candidate`, `n_candidates`, `mae_with_candidate`, `update_flag`,
     `validated`, `mandate`, `consolidated` -- all contain "date".)

BOTH are now value-gated, and the invariant is: A SUBSTRING MATCH ON A COLUMN NAME MAY ONLY EVER
NOMINATE A COLUMN FOR A VALUE TEST.  IT MAY NEVER, BY ITSELF, CAUSE A VIOLATION.  Any future
name-based detection added here must ship with its value gate in the same commit.

TWO RESIDUAL NAME-SHAPED RISKS, REPORTED AND DELIBERATELY NOT CHANGED:
  a. `DEFAULT_CANDIDATE_KEYS` selects grouping levels by EXACT column name (`game_id`, `team_id`,
     `player_id`, `season`).  Exact matching cannot produce the substring false hit that bit K0
     four times, and `detect_grouping_level` reports every level's measured group count so a
     mismatched key is visible in the output rather than silent.  It does NOT check that a column
     named `season` holds seasons.  Left alone: the caller names the keys, and inventing a value
     test for an arbitrary user-supplied key column is guesswork of the kind this kit refuses.
  b. `assert_partition`'s final sweep flags any numeric column whose values are ALL whole numbers
     inside [2020, 2030] and intersect the holdout.  That is VALUE-based, not name-based, so it is
     not the K0 defect class -- but it can still false-alarm on a count or rating column that
     happens to live entirely in that decade.  It is deliberately kept: its whole purpose is to
     catch a year-valued column with an innocuous name (the `fit_through` case in TESTS.py), and
     its failure direction is a false ALARM, never a false PASS.

FALSE-ASSURANCE AUDIT: WHERE ELSE CAN THIS MODULE BE CONFIDENTLY WRONG?  (prompted by K6/K7)
--------------------------------------------------------------------------------------------
Every public function swept against SHAPE 1 (a control that cannot fail) and SHAPE 2 (a null that
is too narrow).  Findings, including the ones NOT changed:

  FIXED THIS ROUND
    * `permutation_null(SCHEME_WITHIN)` on an autocorrelated feature -- SHAPE 2.  See K6.
    * the relabel-the-entity-key control -- SHAPE 1.  See K7.
    * `_group_codes` NULL-sentinel group collisions -- both shapes, no symptom.  See K8.

  REPORTED AND DELIBERATELY NOT CHANGED -- each is a real way to get a confident wrong answer:
    c. `SCHEME_WITHIN_CYCLIC` DEPENDS ON ROW ORDER AND CANNOT VERIFY IT.  A cyclic shift is only
       serial-structure-preserving if the rows inside each group are in TIME order.  The kit cannot
       know your time column unless you pass `order_col`, and a frame whose rows are scrambled
       inside the group will get a cyclic shift of a scrambled sequence -- which preserves nothing
       and is WORSE than a shuffle (it has only n_g distinct draws).  MITIGATION, not a fix: pass
       `order_col`; and when you do not, the measured `acf1_within_group` is reported and a
       non-material value on a feature you believe is autocorrelated is the signature of exactly
       this mistake, so the result carries an explicit `warning` naming it.
    d. `SCHEME_WITHIN_CYCLIC` HAS ONLY n_g DISTINCT DRAWS PER GROUP.  For small groups the null is
       coarse and the p is granular; the joint null over G independent groups is far richer, but a
       single 4-row group contributes only 4 states.  `cyclic_min_group_size` and
       `cyclic_median_group_size` are returned so this is visible, with a `warning` under 5.
    e. THE ACF GATE INSPECTS THE FEATURE ONLY.  The shuffle null is too narrow when the feature AND
       the response both carry serial structure.  `permutation_null` never sees the response --
       `stat_fn` is a black box -- so the gate fires on the feature's acf1 alone.  That is the
       CONSERVATIVE direction (it can refuse a shuffle that would in fact have been fine when the
       response is white), and it is stated rather than silently assumed.
    f. `paired_forecast_comparison`'s cluster sign-flip null has only 2^n_groups states.  With few
       clusters the attainable p is floored (8 clusters -> nothing below 1/257 in practice, and the
       two-sided count saturates).  `n_groups` is returned; read it before believing a small p.
    g. `var_share_between` is a RAW variance share, not an ICC: it is biased upward with many small
       groups because each group mean carries sampling noise.  It is a scheme-choosing diagnostic,
       not an estimate, and it is documented as one.
    h. `future_leakage_probe` NOT firing is not a certificate, and `check_manifest` returning
       UNVERIFIABLE is not a failure.  Both already say so in their own words; both are SHAPE 1 in
       the sense that a caller can read "no flag" as "clean" -- which is why neither returns a
       boolean named `is_clean`.
    i. `permutation_null` drops non-finite draws and computes p over the survivors.  If `stat_fn`
       returns NaN on the draws that would have been most extreme, p is computed on a biased
       subset.  `n_finite_draws` is returned beside `n_draws` precisely so the caller can see it;
       compare them before reading p.

DEPENDENCIES: standard library + numpy + pandas only.  scipy is NOT installed in this environment.
"""

from __future__ import annotations

import json
import os
import warnings

import numpy as np
import pandas as pd

__all__ = [
    "EXPLORATION_SEASONS", "HOLDOUT_SEASONS", "ROW_LEVEL", "DEFAULT_CANDIDATE_KEYS",
    "SCHEME_BETWEEN", "SCHEME_WITHIN", "SCHEME_WITHIN_CYCLIC", "SCHEME_ENTITY_SWAP",
    "STATUS_COARSER_LEVEL_FOUND", "STATUS_NO_COARSER_LEVEL",
    "SCREEN_FLAG_AMBIGUOUS", "SCREEN_NOT_FLAGGED",
    "ACF1_MATERIALITY_FLOOR",
    "DIRECTION_FUTURE", "DIRECTION_INTERIOR", "DIRECTION_PAST",
    "PartitionViolation",
    "r2_plain", "delta_r2_plain",
    "r2_of_forecast",
    "r2_weighted_standard", "delta_r2_weighted",
    "wls_r2_DEFECTIVE",
    "detect_grouping_level", "permutation_null", "null_width_comparison",
    "within_group_acf1",
    "EntitySwap", "entity_swap_null",
    "var_share_between", "paired_forecast_comparison",
    "noop_placebo", "per_entity_control",
    "assert_partition", "check_manifest", "future_leakage_probe",
]

EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
HOLDOUT_SEASONS = (2025, 2026)

#: Sentinel a caller must pass EXPLICITLY to get the naive row-level permutation null.
#: It is never a default.  See `permutation_null`.
ROW_LEVEL = "row"

#: Permutation schemes for `permutation_null`.  See its docstring for when each is the right null.
SCHEME_BETWEEN = "between"      #: reassign whole groups' values BETWEEN groups (group level dies)
SCHEME_WITHIN = "within"        #: shuffle values INSIDE each group (group level SURVIVES)

#: The fourth scheme (K6).  A within-group CYCLIC SHIFT.  It preserves each group's marginal
#: distribution AND its SERIAL STRUCTURE, and destroys only the alignment to the response.
#: *** THIS IS THE HONEST NULL FOR ANY `.shift(1).expanding()`-SHAPED REGRESSOR, WHICH IS THE
#: PROGRAM'S MOST COMMON CONSTRUCTION. ***  `SCHEME_WITHIN` is anticonservative for such a feature:
#: it destroys the regressor's autocorrelation while the response keeps its own drift, so the null
#: comes out too narrow (measured by the reporter: p = 0.0015 where the honest null gives 0.39).
#: Ported from E1_I0021_heterogeneity_diagnostic/hd_base.py :: cyclic_shift_within_groups.
SCHEME_WITHIN_CYCLIC = "within_cyclic"

#: Materiality floor for the within-group lag-1 autocorrelation gate on `SCHEME_WITHIN` (K6).  The
#: gate threshold is `max(ACF1_MATERIALITY_FLOOR, 2/sqrt(n_pairs))`: the floor says "an acf1 below
#: this is not worth refusing over", the second term says "and never fire on what is only sampling
#: noise on a small frame", where 1/sqrt(n_pairs) is acf1's standard error under the iid null.
#: The reporter's iid negative controls measured -0.029 and -0.025; the running-mean regressors
#: measured +0.550 and +0.864.  Overridable per call via `permutation_null(acf1_threshold=...)`.
ACF1_MATERIALITY_FLOOR = 0.15

#: `assert_partition` violation DIRECTIONS (K4).  The guard exists to stop the HOLDOUT -- the
#: FUTURE -- from entering exploration work.  A value that PREDATES the partition cannot be a
#: holdout leak, and conflating the two is what made the guard fire on `draft_year`.
DIRECTION_FUTURE = "FUTURE"      #: value > max(allowed).  The holdout direction.  ALWAYS FATAL.
DIRECTION_INTERIOR = "INTERIOR"  #: inside the span but not in `allowed`.  ALWAYS FATAL.
DIRECTION_PAST = "PAST"          #: value < min(allowed).  Historical.  Fatal only if the caller
                                 #: NAMED the column in `season_cols`.

#: The third scheme (K2).  NOT a `permutation_null` option -- it has its own entry point,
#: `entity_swap_null`, because it swaps whole SERIES rather than individual values.  It is the only
#: valid null here for the BETWEEN-ENTITY question on a feature that varies WITHIN its entity.
SCHEME_ENTITY_SWAP = "entity_swap"

#: `detect_grouping_level` status values.  READ THE STATUS, NOT JUST THE LEVEL.
STATUS_COARSER_LEVEL_FOUND = "COARSER_LEVEL_FOUND"
STATUS_NO_COARSER_LEVEL = "NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE"

#: `future_leakage_probe` status values (K1).  THE PROBE IS A SCREEN, NOT A VERDICT: a flag is
#: consistent with leakage AND consistent with the suspect merely being a better estimator of a
#: persistent quantity, and the probe cannot distinguish them.  The status value says so out loud
#: so that no caller can read a flag as a finding of leakage.
SCREEN_FLAG_AMBIGUOUS = "FLAGGED__CONSISTENT_WITH_LEAKAGE__ALSO_CONSISTENT_WITH_A_BETTER_ESTIMATOR"
SCREEN_NOT_FLAGGED = "NOT_FLAGGED__NOT_A_CERTIFICATE_OF_CLEANLINESS"

#: Standard candidate grouping levels, finest to coarsest by construction.  `detect_grouping_level`
#: drops any level whose key columns are absent from the frame, and orders by MEASURED group count
#: rather than by this listing, because e.g. `game` and `team_season` do not nest.
DEFAULT_CANDIDATE_KEYS = {
    "row": None,
    "player_game": ["player_id", "game_id"],
    "team_game": ["team_id", "game_id"],
    "game": ["game_id"],
    "team_season": ["team_id", "season"],
    "season": ["season"],
}


class PartitionViolation(AssertionError):
    """Raised by `assert_partition` when a column VALUE falls outside the allowed seasons."""


# ===========================================================================================
# R2 CONVENTIONS  (trap 4)
# ===========================================================================================

def _design(X, add_intercept=True):
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    if add_intercept:
        X = np.column_stack([np.ones(len(X)), X])
    return X


def _fit_sse(y, X):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return beta, float(r @ r), r


def r2_plain(y, X, add_intercept=True):
    """*** THIS FUNCTION REFITS OLS.  IT DOES NOT SCORE A FORECAST YOU ALREADY HAVE. ***

    Plain UNWEIGHTED OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean, where SSE is the residual
    sum of squares of a FRESHLY FITTED least-squares regression of `y` on `X`.

    NAME COLLISION -- READ THIS BEFORE YOU BELIEVE A REPRODUCTION FAILED
      Several screens define their OWN `r2_plain(y, yhat)` that takes an ALREADY-COMPUTED FORECAST
      and returns `1 - sum((y-yhat)^2)/SST` with NO FITTING -- e.g.
      `E0_I0014_residual_heterogeneity/rh_base.py :: r2_plain`.  Same name, different function.
      Calling THIS one with a forecast in the `X` slot silently refits `y ~ a + b*yhat`, which
      rescales and re-centres the forecast and therefore returns a DIFFERENT (generally larger)
      number.  The kit's first user hit exactly this: 0.4747 here against a published 0.4694, and
      briefly believed its reproduction of a frozen screen had failed.

        want to SCORE a forecast you already have?   -> `r2_of_forecast(y, yhat)`
        want to FIT a model and score the fit?       -> `r2_plain(y, X)`  (this function)

    THIS IS THE ADOPTED DEFAULT CONVENTION (D069) FOR FITTED MODELS.  Adapted from
    E1_I0013_tempo_redundancy/e1_lib.py :: r2().

    GUARANTEES
      * The fit is unweighted OLS via `np.linalg.lstsq` (same solver every frozen screen used, so
        numbers are comparable across screens).
      * SST is `sum((y - y.mean())**2)` -- the unweighted mean, unconditionally.
      * An intercept column is prepended unless `add_intercept=False`.

    DOES *NOT*
      * score a given forecast.  It FITS.  Use `r2_of_forecast` for that.
      * weight anything.  If you have a substantive reason to weight, use
        `r2_weighted_standard`, and say in FINDINGS.json why.
      * adjust for degrees of freedom.  This is raw R2, not adjusted R2.
      * handle NaN.  Drop or impute before calling; NaN propagates into a NaN result.
      * say anything about out-of-sample performance.  This is in-sample R2.

    Parameters
    ----------
    y : (n,) array_like of float
    X : (n,) or (n, k) array_like of float -- regressors WITHOUT an intercept column
    add_intercept : bool

    Returns
    -------
    float
    """
    y = np.asarray(y, dtype=float)
    Xd = _design(X, add_intercept)
    _, sse, _ = _fit_sse(y, Xd)
    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0:
        return float("nan")
    return 1.0 - sse / sst


def r2_of_forecast(y, yhat):
    """*** SCORES A FORECAST YOU ALREADY HAVE.  NOTHING IS FITTED. ***

    `1 - sum((y - yhat)^2) / sum((y - mean(y))^2)`.  This is the "R2" that a screen means when it
    reports how well a MODEL'S OUTPUT tracks the outcome: the forecast is taken exactly as given,
    with no intercept, no slope, no rescaling and no re-centring.

    Adapted from E0_I0014_residual_heterogeneity/rh_base.py :: r2_plain(y, yhat) (frozen, read
    only), which is the form the screens in this program actually use on OOF predictions.

    NAME COLLISION -- THE REASON THIS FUNCTION EXISTS
      This module's `r2_plain(y, X)` REFITS OLS.  `rh_base.r2_plain(y, yhat)` does NOT.  Passing a
      forecast to `r2_plain` fits `y ~ a + b*yhat` and returns the R2 OF THAT REFIT, which is
      >= this value and equals it only when the forecast is already perfectly calibrated in the
      least-squares sense (a=0, b=1).  The kit's first user was misled by exactly this and briefly
      thought a reproduction of a frozen screen had failed (0.4747 vs a published 0.4694).

      A screen reproducing a published number from a stored prediction column wants THIS function.

    GUARANTEES
      * No fitting of any kind.  The returned value is a deterministic function of `y` and `yhat`
        alone, so it is comparable bit-for-bit with any screen using the `1 - SSE/SST` form.
      * SST is about the UNWEIGHTED mean of `y` (D069), matching `r2_plain`'s denominator, so the
        two differ ONLY in the numerator.
      * CAN BE NEGATIVE, and is meant to be: a forecast worse than the sample mean of `y` scores
        below 0.  That is information, not a bug -- do not clip it.

    DOES *NOT*
      * fit, calibrate, rescale or de-bias `yhat`.  If you want to know how much of the gap is
        miscalibration, compare this against `r2_plain(y, yhat)` and report BOTH.
      * handle NaN.  Drop or impute first; NaN propagates.
      * adjust for degrees of freedom, or say anything about out-of-sample performance beyond what
        the provenance of `yhat` already establishes.

    Parameters
    ----------
    y    : (n,) array_like of float -- the outcome
    yhat : (n,) array_like of float -- the ALREADY-COMPUTED forecast, used verbatim

    Returns
    -------
    float
    """
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    if y.shape != yhat.shape:
        raise ValueError("r2_of_forecast: y and yhat must have the same shape, got %s and %s "
                         "-- this function scores a FORECAST, it does not take a design matrix "
                         "(you may want r2_plain)" % (y.shape, yhat.shape))
    sse = float(((y - yhat) ** 2).sum())
    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0:
        return float("nan")
    return 1.0 - sse / sst


def delta_r2_plain(y, X_base, X_full, add_intercept=True):
    """Incremental plain OLS R2: r2_plain(y, X_full) - r2_plain(y, X_base).

    GUARANTEES
      * Both models use the SAME SST (about the unweighted mean of the SAME y), so the difference
        is exactly (SSE_base - SSE_full) / SST.
      * Both fits use the same solver and the same intercept handling.

    DOES *NOT*
      * check that X_base is nested inside X_full.  If it is not, the "increment" is not an
        increment and may be negative.  Nesting is the caller's responsibility.
      * penalise the extra parameters.  A dR2 of 1/n is what one junk regressor buys for free;
        compare against a permutation null (`permutation_null`), never against zero.
    """
    y = np.asarray(y, dtype=float)
    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0:
        return float("nan")
    _, sse_b, _ = _fit_sse(y, _design(X_base, add_intercept))
    _, sse_f, _ = _fit_sse(y, _design(X_full, add_intercept))
    return (sse_b - sse_f) / sst


def r2_weighted_standard(y, X, w, add_intercept=True):
    """STANDARD weighted R2: WLS fit, SSE = sum(w*r^2), SST = sum(w*(y - mu_w)^2), mu_w weighted.

    Adapted from E1_I0009_r2_rerun/step23_reproduce_and_rerun.py :: r2_standard_weighted(), which
    took it verbatim from E1_I0009_additive_pressure/analyze.py.

    GUARANTEES
      * SST is taken about the WEIGHTED mean `np.average(y, weights=w)`.  This is the textbook
        weighted R2 and the one to use when weighting is substantively justified.
      * The fit is the sqrt-weight-transformed least squares solution, identical to the fit used by
        `wls_r2_DEFECTIVE`, so the two differ ONLY in the denominator.

    DOES *NOT*
      * decide FOR you that weighting is appropriate.  D069 makes plain unweighted OLS the default;
        a weighted number must be justified in FINDINGS.json.
      * equal `r2_plain` -- the fitted coefficients differ too, not just the denominator.
    """
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    Xd = _design(X, add_intercept)
    s = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(Xd * s[:, None], y * s, rcond=None)
    r = y - Xd @ beta
    ybar_w = np.average(y, weights=w)
    sst = float(np.sum(w * (y - ybar_w) ** 2))
    if sst <= 0:
        return float("nan")
    return 1.0 - float(np.sum(w * r ** 2)) / sst


def delta_r2_weighted(y, X_base, X_full, w, add_intercept=True):
    """Incremental STANDARD weighted R2 (SST about the weighted mean, shared across both models).

    GUARANTEES / DOES NOT: as `delta_r2_plain`, but weighted, and with SST about `mu_w`.
    """
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    ybar_w = np.average(y, weights=w)
    sst = float(np.sum(w * (y - ybar_w) ** 2))
    if sst <= 0:
        return float("nan")
    s = np.sqrt(w)

    def _wsse(Xd):
        beta, *_ = np.linalg.lstsq(Xd * s[:, None], y * s, rcond=None)
        r = y - Xd @ beta
        return float(np.sum(w * r ** 2))

    return (_wsse(_design(X_base, add_intercept)) - _wsse(_design(X_full, add_intercept))) / sst


def wls_r2_DEFECTIVE(y, X, w, add_intercept=True):
    """*** DEFECTIVE. DO NOT USE FOR ANY NEW RESULT. REPRODUCTION ONLY. ***

    VERBATIM logic from `wls_r2` in E0_I0009_additive_pressure/analyze.py, preserved here (and
    loudly named) so a new screen can REPRODUCE a frozen screen's published number before
    re-running it under a correct convention.  Standing decision D069 keeps the six copy-pasted
    originals in place; this is the seventh copy and it is the only one that admits what it is.

    THE DEFECT
      It computes `sst = sum((sqrt(w)*y - mean(sqrt(w)*y))**2)` -- the SST of the
      sqrt-weight-TRANSFORMED response about ITS OWN unweighted mean -- instead of the standard
      weighted SST about the weighted mean, `sum(w*(y - mu_w)**2)`.  SSE is identical to the
      standard form, so this is a PURE DENOMINATOR EFFECT.

    MEASURED CONSEQUENCE
      Understates dR2 by 0% to 25.3%, governed by weight dispersion and response centering.
      It collapses to EXACTLY 1.0000000000 x the standard value under UNIFORM weights, and to
      ~0.99931 (NOT exactly 1) under a centered response, because exact cancellation requires
      BOTH sum(w*y)=0 and sum(sqrt(w)*y)=0.

    GUARANTEES
      * Bit-comparable reproduction of the frozen convention (same solver, same arithmetic order).

    DOES *NOT*
      * produce a defensible R2.  It is not a valid weighted R2 and must never carry a verdict.
      * get "close enough".  Report it side by side with `r2_weighted_standard` or `r2_plain`, and
        label it `defective_weighted` in FINDINGS.json exactly as E1_I0009_r2_rerun did.
    """
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    Xd = _design(X, add_intercept)
    sw = np.sqrt(w)
    Xw = Xd * sw[:, None]
    yw = y * sw
    beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    resid = yw - Xw @ beta
    sse = float(resid @ resid)
    sst = float(((yw - yw.mean()) ** 2).sum())          # <-- THE DEFECT
    if sst <= 0:
        return float("nan")
    return 1.0 - sse / sst


# ===========================================================================================
# GROUPING LEVEL DETECTION  (trap 1 -- the anti-trap helper)
# ===========================================================================================

def _factorize_no_sentinel(s):
    """`pd.factorize` with NULL given its OWN real code instead of the -1 sentinel.  *** K8 FIX. ***

    THE BUG THIS CLOSES.  `_group_codes` builds a composite key as `codes * n_levels + next_code`.
    That is injective ONLY while every code is in [0, n_levels).  `pd.factorize` returns -1 for a
    NULL value, and -1 breaks the arithmetic: with n_levels = 3,

        (group 0, next_code -1)  ->  0*3 + (-1)  = -1
        (group -1, next_code  2) -> -1*3 +   2   = -1

    so TWO DIFFERENT KEY TUPLES LAND ON THE SAME GROUP CODE and two genuinely different groups are
    SILENTLY MERGED.  Verified on a 6-row frame: ('B', 3.0) and ('C', NaN) both received code 2, so
    six distinct key tuples became five groups.  Every consumer inherited it -- `n_groups` was
    wrong, `constant_within` was wrong, and `permutation_null` shuffled values across two different
    groups while returning a perfectly well-formed p.  No crash, no warning, no symptom: a
    FALSE-ASSURANCE defect of the purest kind, found by this round's own audit rather than by a
    user.  Giving NULL its own code restores injectivity and makes the NULL cell a visible level.
    """
    try:
        codes, uq = pd.factorize(s, sort=False, use_na_sentinel=False)
    except TypeError:                                   # a pandas without use_na_sentinel
        codes, uq = pd.factorize(s, sort=False)
        codes = np.asarray(codes, dtype=np.int64)
        if (codes < 0).any():                           # fold the sentinel into a real, unused code
            codes = np.where(codes < 0, len(uq), codes)
            return codes.astype(np.int64), len(uq) + 1
        return codes.astype(np.int64), len(uq)
    return np.asarray(codes, dtype=np.int64), int(len(uq))


def _group_codes(df, cols):
    """Contiguous integer group code per row for a key (list of columns), or 0..n-1 for rows.

    K8: NULL key values get their own code (see `_factorize_no_sentinel`), so the composite-key
    arithmetic below is injective and two different key tuples can never collide onto one group.
    """
    if cols is None:
        return np.arange(len(df), dtype=np.int64)
    cols = list(cols)
    codes, _ = _factorize_no_sentinel(df[cols[0]])
    for c in cols[1:]:
        cc, n_lv = _factorize_no_sentinel(df[c])
        codes = codes * np.int64(max(n_lv, 1)) + cc
        codes, _ = _factorize_no_sentinel(pd.Series(codes))
    return codes


# ===========================================================================================
# WITHIN-GROUP SERIAL STRUCTURE  (K6)
# ===========================================================================================

def _group_slices(codes):
    """(order, starts, ends) for a stable sort by group code.

    The sort is STABLE, so the rows inside each group keep the order they had in the FRAME.  That
    is what makes the frame's row order the time order for `SCHEME_WITHIN_CYCLIC` and for the
    lag-1 autocorrelation below -- and it is why `order_col` exists.
    """
    codes = np.asarray(codes)
    order = np.argsort(codes, kind="stable")
    sc = codes[order]
    if not len(sc):
        return order, np.array([], dtype=int), np.array([], dtype=int)
    starts = np.flatnonzero(np.r_[True, sc[1:] != sc[:-1]])
    ends = np.r_[starts[1:], len(sc)]
    return order, starts, ends


def within_group_acf1(data, feature_col, group_col, order_col=None):
    """POOLED LAG-1 AUTOCORRELATION OF A FEATURE *INSIDE* ITS GROUPS.  *** THE K6 DIAGNOSTIC. ***

    WHY THIS NUMBER DECIDES A NULL.  `permutation_null(scheme=SCHEME_WITHIN)` shuffles the feature
    inside each group.  That destroys the feature's SERIAL structure.  If the RESPONSE carries slow
    within-group structure of its own -- and in this program it always does, because players and
    teams drift -- then the shuffled draws are LESS like the real data than the null hypothesis
    says they should be, the null comes out TOO NARROW, and the p is too small.  The reporter
    measured the size of the effect directly: across 48 (floor x relationship) cells,
    corr(this statistic, the shuffle-minus-cyclic null-ratio gap) = +0.832, with the gap at 0.004
    on iid controls and +0.121/+0.179 on running-mean regressors.

    THE ESTIMATOR.  Inside each group the values are DEMEANED ON THEIR OWN GROUP MEAN -- the
    question is about structure INSIDE the group, not about the group level, which the within
    schemes preserve exactly.  The consecutive pairs from every group are then pooled and a single
    Pearson correlation is taken over the pooled pairs, so the result is bounded in [-1, 1] and a
    group of length 1 simply contributes nothing.

    ROW ORDER IS THE INPUT AND THE KIT CANNOT VERIFY IT.  "Consecutive" means consecutive in
    `order_col` if you pass one, and consecutive IN THE FRAME'S ROW ORDER if you do not.  A frame
    scrambled inside its groups will report acf1 ~ 0 for a strongly autocorrelated feature.  That
    is not a wrong answer -- it is the honest answer to "is this column serially structured AS THE
    ROWS ARE ORDERED", which is exactly the quantity the cyclic shift acts on.

    Returns
    -------
    dict: acf1 (float, nan when there are fewer than 2 usable pairs), n_pairs, n_groups,
          min_group_size, median_group_size, order_basis
    """
    if feature_col not in data.columns:
        raise KeyError("feature_col %r not in frame" % feature_col)
    key = [group_col] if isinstance(group_col, str) else list(group_col)
    missing = [c for c in key if c not in data.columns]
    if missing:
        raise KeyError("group_col columns missing from frame: %s" % missing)
    codes = _group_codes(data, key)
    v, _ = _feature_to_float(data[feature_col], feature_col)
    out = _acf1_from_codes(v, codes, _order_within_groups(data, codes, order_col))
    out["acf1"] = _nan_to_none(out["acf1"])
    return out


def _order_within_groups(data, codes, order_col):
    """Row permutation putting rows in (group, `order_col`) order; None means FRAME ORDER.

    Returned as a plain index array so both the acf and the cyclic shift use ONE definition of
    "consecutive".  A stable sort keeps ties in frame order.
    """
    if order_col is None:
        return None
    ocols = [order_col] if isinstance(order_col, str) else list(order_col)
    missing = [c for c in ocols if c not in data.columns]
    if missing:
        raise KeyError("order_col columns missing from frame: %s" % missing)
    tmp = pd.DataFrame({"_g": np.asarray(codes)})
    for i, c in enumerate(ocols):
        tmp["_o%d" % i] = data[c].to_numpy()
    return tmp.sort_values(["_g"] + ["_o%d" % i for i in range(len(ocols))],
                           kind="stable").index.to_numpy()


def _acf1_from_codes(values, codes, seq_order=None):
    """Pooled within-group lag-1 acf.  `seq_order` = row order defining "consecutive" (None=frame)."""
    v = np.asarray(values, dtype=float)
    codes = np.asarray(codes)
    if seq_order is not None:
        v = v[seq_order]
        codes = codes[seq_order]
    order, starts, ends = _group_slices(codes)
    a_parts, b_parts, sizes = [], [], []
    for s, e in zip(starts, ends):
        idx = order[s:e]
        sizes.append(e - s)
        if e - s < 2:
            continue
        g = v[idx]
        fin = np.isfinite(g)
        if fin.sum() < 2:
            continue
        g = g - float(np.nanmean(g[fin]))               # demean ON ITS OWN GROUP
        a_parts.append(g[:-1])
        b_parts.append(g[1:])
    out = {
        "n_groups": int(len(starts)),
        "min_group_size": int(min(sizes)) if sizes else 0,
        "median_group_size": float(np.median(sizes)) if sizes else 0.0,
        "order_basis": ("order_col" if seq_order is not None else "FRAME ROW ORDER"),
    }
    if not a_parts:
        out["acf1"] = float("nan")
        out["n_pairs"] = 0
        return out
    a = np.concatenate(a_parts)
    b = np.concatenate(b_parts)
    d_all = np.concatenate([np.concatenate([p, q[-1:]]) for p, q in zip(a_parts, b_parts)])
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    out["n_pairs"] = int(len(a))
    if len(a) < 2:
        out["acf1"] = float("nan")
        return out
    # The TEXTBOOK lag-1 estimator on the group-demeaned series: sum of consecutive products over
    # the total sum of squares.  NOT a Pearson correlation of the two shifted vectors -- re-centring
    # those separately adds a second O(1/m) bias on top of the one demeaning already carries, and
    # it made an IID feature in 15-row groups report acf1 = -0.157 instead of the -1/(m-1) = -0.071
    # that demeaning alone explains.  Cauchy-Schwarz bounds this form inside [-1, 1].
    den = float(d_all[np.isfinite(d_all)] @ d_all[np.isfinite(d_all)])
    out["acf1"] = float((a @ b) / den) if den > 0 else float("nan")
    return out


def _nan_to_none(x):
    """nan -> None, so every report field this module returns is JSON-serialisable AND comparable.

    `float('nan') != float('nan')`, so a nan buried in a report dict silently breaks any equality
    check a caller makes on it, and `json.dump` writes a bare `NaN` that is not valid JSON.  Both
    are small false-assurance surfaces of their own.
    """
    try:
        return None if x is None or not np.isfinite(x) else float(x)
    except (TypeError, ValueError):
        return None


def _acf1_gate_threshold(n_pairs, acf1_threshold=None):
    """max(materiality floor, 2 sampling SEs).  See `ACF1_MATERIALITY_FLOOR` for the reasoning."""
    if acf1_threshold is not None:
        return float(acf1_threshold)
    if not n_pairs:
        return float("inf")
    return float(max(ACF1_MATERIALITY_FLOOR, 2.0 / np.sqrt(float(n_pairs))))


def _as_float_for_spread(s):
    """Return a float Series suitable for a `max - min` within-group spread, or None.

    *** BOOLEAN FEATURES ARE HANDLED EXPLICITLY HERE.  THIS IS THE P1 FIX. ***

    THE BUG THIS CLOSES.  `pd.api.types.is_numeric_dtype` returns True for `bool`, so a boolean
    feature used to fall into the plain numeric branch below, where
    `groupby.transform("max") - groupby.transform("min")` raises

        TypeError: numpy boolean subtract, the `-` operator, is not supported, use the
                   bitwise_xor, the `^` operator, or the logical_xor function instead.

    Found by the kit's first user (E0_I0015).  It matters concretely: binary pre-game flags are
    among the most common candidates in this program -- two of the four surviving leads from
    E0_I0014's residual-heterogeneity screen are booleans, `is_fallback` among them.

    WHY A CAST AND NOT A `nunique` FALLBACK.  `False -> 0.0`, `True -> 1.0` is exact, total and
    order-preserving, so `max - min <= tol` means for a boolean exactly what it means for any other
    numeric feature, and `max_within_group_spread` stays comparable across features.  Routing
    booleans to the non-numeric `nunique` path instead would report `nan` for the spread and would
    silently ignore `tol`.  Missing values in a nullable `boolean` column become `nan` and are
    handled by the same `nanmax` the numeric branch already uses.

    NOTE ON THE FAILURE MODE.  The pre-fix behaviour -- a loud, immediate TypeError -- was the SAFE
    failure mode, and it is deliberately NOT replaced by a permissive coercion of arbitrary dtypes.
    Only `bool` is converted, and only because the conversion is exact.  Anything that is neither
    boolean nor numeric still goes to the distinct-count path, and anything that cannot be handled
    at all still raises.
    """
    if pd.api.types.is_bool_dtype(s):
        return s.astype("float64")          # exact: False->0.0, True->1.0, pd.NA->nan
    if pd.api.types.is_numeric_dtype(s):
        return s
    return None


def _constant_within(values, codes, tol=0.0):
    """(is_constant, max_distinct_within_a_group, max_within_group_spread) under grouping `codes`."""
    s = pd.Series(values)
    g = s.groupby(codes, sort=False)
    s_num = _as_float_for_spread(s)
    if s_num is not None:
        gn = s_num.groupby(codes, sort=False)
        spread = gn.transform("max") - gn.transform("min")
        spread = pd.to_numeric(spread, errors="coerce").abs()
        max_spread = float(np.nanmax(spread.to_numpy())) if len(spread) else 0.0
        is_const = bool(max_spread <= tol)
    else:
        is_const = bool(g.nunique().max() <= 1)
        max_spread = float("nan")
    max_distinct = int(g.nunique().max()) if len(s) else 0
    return is_const, max_distinct, max_spread


def detect_grouping_level(df, feature_col, candidate_keys=None, tol=0.0, verbose=False):
    """THE ANTI-TRAP HELPER FOR TRAP 1.  Report the level at which a feature actually varies.

    For each candidate key it reports how many DISTINCT VALUES the feature really takes and
    whether the feature is CONSTANT within groups at that level, then names the COARSEST level at
    which it is constant.  THAT LEVEL IS THE CORRECT PERMUTATION LEVEL.

    This is the function that would have caught all four instances of trap 1 -- e.g. a feature with
    only 12 distinct values per season shared across 16,345 rows, and a feature taking ONE VALUE
    PER GAME (774 distinct values across 10,167 rows from 48 team-season series) whose published
    family-wise p of 0.003 was computed against a row-level null entirely.

    *** THE `row` CASE IS NOT A RECOMMENDATION.  READ `status`. ***  (P2, fixed 2026-08-07)
      This function used to return `recommended_permutation_level: "row"` for a genuinely
      row-varying feature -- 34 of 55 candidates in the screen that reported it.  The docstring
      carried the caveat, but the FIELD NAME undid it: a field called
      `recommended_permutation_level` holding the value `"row"` reads as THE KIT RECOMMENDING THE
      ANTICONSERVATIVE NULL, with the kit's authority behind it, and unlike a crash it is SILENT.
      A caller who trusted the field name would do the wrong thing with no signal at all.

      The semantics are therefore changed, not just the wording:
        * `recommended_permutation_level` is `None` -- never the string `"row"` -- whenever no
          coarser level exists.  Feeding `None` to `permutation_null` triggers its REFUSAL, so the
          naive path is now unreachable by accident even for a caller who reads nothing else.
        * `status` is `STATUS_NO_COARSER_LEVEL`, whose literal value is
          "NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE".
        * `row_null_is_anticonservative` is True and `warning` carries the full explanation.
        * The bare `"row"` sentinel is reachable ONLY through the opt-in field
          `level_if_you_accept_the_anticonservative_row_null`, whose name cannot be read as an
          endorsement.
      *** BREAKING CHANGE *** for any caller that compared `recommended_permutation_level` to
      `"row"` or `ROW_LEVEL`.  Compare `status` to `STATUS_NO_COARSER_LEVEL` instead.

    GUARANTEES
      * "Coarsest" is decided by the MEASURED number of groups (fewest groups wins), not by an
        assumed hierarchy, because `game` and `team_season` do not nest in each other.
      * A level is only eligible to be recommended if it is BOTH constant-within AND has strictly
        FEWER GROUPS THAN ROWS.  A key that happens to identify rows uniquely (e.g. `player_game`
        on a player-game frame) is a row-level null wearing key columns, and is reported with
        `is_row_equivalent: True` rather than recommended.
      * Levels whose key columns are absent from `df` are skipped and listed under `skipped`.
      * The `row` level is reported in `levels` for contrast only.  It is constant by construction
        and can never be the recommendation.

    DOES *NOT*
      * prove the recommended level is the right unit of INFERENCE for your statistic.  It reports
        where the FEATURE is constant.  If your outcome is clustered at a coarser level than the
        feature, that is a separate (and also real) problem this does not detect.
      * tell you that a row-varying feature is safe to permute row-wise.  It tells you the opposite:
        that no coarser level exists, that the row null is anticonservative, and that you must
        either find a clustering level from the OUTCOME side, use
        `permutation_null(..., scheme=SCHEME_WITHIN)` at a level the feature varies inside, or
        declare the anticonservatism explicitly in FINDINGS.json.
      * handle a feature that is constant within groups only up to floating-point noise unless you
        raise `tol` -- the default requires exact constancy (max - min <= 0).
      * inspect the OUTCOME at all.
      * decide anything from `acf1_within_group` (K6).  That field is a DIAGNOSTIC: a material
        value means a within-group SHUFFLE at that level would give a null that is too narrow, and
        `SCHEME_WITHIN_CYCLIC` is the scheme that preserves the structure.  It is measured in the
        FRAME'S ROW ORDER, which is the time order only if you sorted the frame that way.

    Parameters
    ----------
    df : pandas.DataFrame
    feature_col : str
    candidate_keys : dict[str, list[str] | None], default DEFAULT_CANDIDATE_KEYS.  MUST be a
                     mapping LEVEL NAME -> KEY COLUMNS.  A bare list raises TypeError (K3).
    tol : float -- max within-group spread still counted as constant (numeric and BOOLEAN features)
    verbose : bool -- print the table

    Returns
    -------
    dict with keys:
      n_rows, feature_col, n_distinct_values_global, feature_dtype, feature_is_boolean,
      levels : dict level -> {key_cols, n_groups, constant_within, max_distinct_within_group,
                              max_within_group_spread, n_distinct_at_level, is_row_equivalent,
                              acf1_within_group, acf1_n_pairs}   -- the last two are K6
      constant_levels : list[str]
      status : STATUS_COARSER_LEVEL_FOUND | STATUS_NO_COARSER_LEVEL
      recommended_permutation_level : str | None   -- NEVER the string "row"; None means REFUSE
      recommended_key_cols : list[str] | None
      row_null_is_anticonservative : bool
      warning : str | None
      level_if_you_accept_the_anticonservative_row_null : str | None
      skipped : dict level -> missing columns
    """
    if candidate_keys is None:
        candidate_keys = DEFAULT_CANDIDATE_KEYS
    # K3: a list here used to reach `.items()` and die with a bare
    # `AttributeError: 'list' object has no attribute 'items'`, which names neither the parameter
    # nor the required shape.  Reported as a usage nit by the kit's second user.
    if not hasattr(candidate_keys, "items"):
        raise TypeError(
            "detect_grouping_level: candidate_keys must be a MAPPING from a level NAME to its key "
            "COLUMNS, e.g. {'game': ['game_id'], 'team_season': ['team_id', 'season']}; got %s. "
            "A bare list of column names is not enough -- the level name is what appears in "
            "`levels`, in `recommended_permutation_level` and in your FINDINGS.json, so the kit "
            "will not invent one for you. If you meant one level, pass {'my_level': %r}. Omit the "
            "argument entirely to use screenkit.DEFAULT_CANDIDATE_KEYS."
            % (type(candidate_keys).__name__,
               list(candidate_keys) if isinstance(candidate_keys, (list, tuple)) else ["col_a"]))
    if feature_col not in df.columns:
        raise KeyError("feature_col %r not in frame" % feature_col)

    values = df[feature_col]
    n_rows = int(len(df))
    out = {
        "n_rows": n_rows,
        "feature_col": feature_col,
        "feature_dtype": str(values.dtype),
        "feature_is_boolean": bool(pd.api.types.is_bool_dtype(values)),
        "n_distinct_values_global": int(values.nunique(dropna=False)),
        "levels": {},
        "skipped": {},
    }
    for level, cols in candidate_keys.items():
        if cols is not None:
            missing = [c for c in cols if c not in df.columns]
            if missing:
                out["skipped"][level] = missing
                continue
        codes = _group_codes(df, cols)
        n_groups = int(len(np.unique(codes)))
        is_const, max_distinct, max_spread = _constant_within(values, codes, tol=tol)
        rep = values.groupby(codes, sort=False).first()
        # K6 (the reporter's suggestion 3): report the within-group lag-1 autocorrelation at every
        # level as a DIAGNOSTIC.  A material value here means `scheme=SCHEME_WITHIN` at that level
        # would give a null that is TOO NARROW; see `within_group_acf1` and `permutation_null`.
        # It is measured in the FRAME'S ROW ORDER, which is only the time order if you sorted.
        try:
            fv, _ = _feature_to_float(values, feature_col)
            acf = _acf1_from_codes(fv, codes, None)
        except TypeError:                               # non-numeric feature: no serial structure
            acf = {"acf1": float("nan"), "n_pairs": 0}
        out["levels"][level] = {
            "key_cols": list(cols) if cols else None,
            "n_groups": n_groups,
            "constant_within": bool(is_const),
            "max_distinct_within_group": max_distinct,
            "max_within_group_spread": max_spread,
            "n_distinct_at_level": int(pd.Series(rep).nunique(dropna=False)),
            # a key that identifies rows uniquely gives a ROW-LEVEL null wearing key columns
            "is_row_equivalent": bool(n_groups >= n_rows),
            "acf1_within_group": _nan_to_none(acf["acf1"]),
            "acf1_n_pairs": int(acf["n_pairs"]),
        }

    const = [(lv, d["n_groups"]) for lv, d in out["levels"].items() if d["constant_within"]]
    const.sort(key=lambda t: t[1])                      # fewest groups == coarsest
    out["constant_levels"] = [lv for lv, _ in const]

    # ---- P2: a level only counts if it is genuinely COARSER than the rows -----------------
    eligible = [(lv, n) for lv, n in const
                if lv != ROW_LEVEL and not out["levels"][lv]["is_row_equivalent"]]
    if eligible:
        rec = eligible[0][0]
        out["status"] = STATUS_COARSER_LEVEL_FOUND
        out["recommended_permutation_level"] = rec
        out["recommended_key_cols"] = out["levels"][rec]["key_cols"]
        out["row_null_is_anticonservative"] = False
        out["warning"] = None
        out["level_if_you_accept_the_anticonservative_row_null"] = None
    else:
        rec = None
        out["status"] = STATUS_NO_COARSER_LEVEL
        out["recommended_permutation_level"] = None
        out["recommended_key_cols"] = None
        out["row_null_is_anticonservative"] = True
        out["level_if_you_accept_the_anticonservative_row_null"] = ROW_LEVEL
        out["warning"] = (
            "NO COARSER LEVEL EXISTS for %r: it varies row by row (or every constant key "
            "identifies rows uniquely), so there is NOTHING here to recommend. THIS IS NOT A "
            "RECOMMENDATION TO PERMUTE ROWS. A row-level null is ANTICONSERVATIVE whenever the "
            "OUTCOME is clustered, which this function does not and cannot check -- it inspects "
            "the feature only. Your options, in order of preference: (a) find the level at which "
            "the OUTCOME clusters and permute there; (b) use "
            "permutation_null(..., scheme=SCHEME_WITHIN) at a level the feature varies inside, "
            "which preserves the group level and kills only the within-group alignment; "
            "(c) pass screenkit.ROW_LEVEL explicitly and record in FINDINGS.json that the p is "
            "anticonservative and by how much (null_width_comparison reports the factor). "
            "recommended_permutation_level is None precisely so that piping it into "
            "permutation_null REFUSES instead of quietly doing (c)." % feature_col)

    if verbose:
        print("  detect_grouping_level(%s): n_rows=%d  dtype=%s  distinct values overall=%d"
              % (feature_col, out["n_rows"], out["feature_dtype"],
                 out["n_distinct_values_global"]))
        print("    %-14s %10s %10s %12s %6s %8s %s"
              % ("level", "n_groups", "distinct", "constant?", "row==?", "acf1",
                 "max within-group distinct"))
        for lv, d in out["levels"].items():
            a = d.get("acf1_within_group")
            print("    %-14s %10d %10d %12s %6s %8s %d"
                  % (lv, d["n_groups"], d["n_distinct_at_level"],
                     "YES" if d["constant_within"] else "no",
                     "YES" if d["is_row_equivalent"] else "no",
                     ("%+.3f" % a) if a is not None else "  n/a",
                     d["max_distinct_within_group"]))
        for lv, miss in out["skipped"].items():
            print("    %-14s SKIPPED (missing columns: %s)" % (lv, miss))
        if rec is not None:
            print("    -> status=%s" % out["status"])
            print("    -> COARSEST CONSTANT LEVEL = %r  == THE CORRECT PERMUTATION LEVEL" % rec)
        else:
            print("    -> status=%s" % out["status"])
            print("    -> recommended_permutation_level = None  (NOT 'row' -- there is no")
            print("       recommendation to make here, and a row null would be anticonservative)")
            print("    !! %s" % out["warning"])
    return out


# ===========================================================================================
# PERMUTATION NULLS  (trap 1)
# ===========================================================================================

def _permute_group_values(values, codes, block_codes, rng):
    """Permute WHICH GROUP's already-computed value each group receives, then broadcast to rows.

    Semantics copied from E1_I0013_tempo_redundancy/e1_lib.py :: GamePerm.  Nothing is recomputed:
    only the ASSIGNMENT of an already-computed value to a group changes.  This is deliberately NOT
    the "permute the grouping key and recompute the aggregate" form, which is a no-op (see
    `noop_placebo`).
    """
    uniq_groups, first_idx = np.unique(codes, return_index=True)
    gvals = np.asarray(values, dtype=float)[first_idx]           # one value per group
    gblock = np.asarray(block_codes)[first_idx]
    perm_gvals = np.empty(len(uniq_groups), dtype=float)
    for b in np.unique(gblock):
        idx = np.where(gblock == b)[0]
        perm_gvals[idx] = gvals[idx][rng.permutation(len(idx))]
    slot = np.searchsorted(uniq_groups, codes)                   # vectorised broadcast back to rows
    return perm_gvals[slot]


def _permute_within_groups(values, codes, rng):
    """WITHIN-GROUP permutation: shuffle values INSIDE each group, keeping group membership.

    Adapted from E0_I0014_residual_heterogeneity/rh_base.py :: within_block_index() (frozen, read
    only), which had to implement this itself because the kit only shipped the between-group form.
    Its comment states the case exactly: "values are shuffled INSIDE each (season,key) block, so
    the block's LEVEL survives and only the within-block (game-to-game) alignment is destroyed.
    This is the correct null for a candidate whose variance is mostly WITHIN its block -- for such
    a candidate the between-block reassignment leaves the effect almost intact and is not a null at
    all.  A candidate is only credited if it beats BOTH."

    Use `var_share_between` to see which regime a candidate is in before choosing.

    NOTE: this is the IDENTITY for a feature that is constant within groups, which is why
    `permutation_null` refuses that combination rather than returning a vacuous null (the same
    failure `noop_placebo` exists to detect).  No block_col loop is needed: groups are required to
    nest inside blocks, so a within-group shuffle never crosses a block.
    """
    v = np.asarray(values, dtype=float)
    out = np.empty(len(v), dtype=float)
    order = np.argsort(codes, kind="stable")
    sorted_codes = np.asarray(codes)[order]
    starts = np.flatnonzero(np.r_[True, sorted_codes[1:] != sorted_codes[:-1]])
    ends = np.r_[starts[1:], len(sorted_codes)] if len(starts) else np.array([], dtype=int)
    for s, e in zip(starts, ends):
        idx = order[s:e]
        out[idx] = v[idx][rng.permutation(e - s)]
    return out


def _permute_within_groups_cyclic(values, codes, rng, seq_order=None):
    """WITHIN-GROUP CYCLIC SHIFT: rotate each group's series by a random offset.  *** K6 FIX. ***

    PORTED FROM `E1_I0021_heterogeneity_diagnostic/hd_base.py :: cyclic_shift_within_groups`
    (frozen, read-only), which the kit's EIGHTH user had to write itself because the kit shipped no
    serial-structure-preserving null.  Credit and the measured justification are that reporter's.

    WHAT IT PRESERVES AND WHY THAT IS THE WHOLE POINT.  `_permute_within_groups` above preserves
    each group's MARGINAL distribution and destroys everything else -- including the feature's
    AUTOCORRELATION.  Several of this program's regressors are RUNNING MEANS of an entity's own
    history (`.shift(1).expanding()`), so they are autocorrelated by construction and they trend
    inside a season.  If the response also carries a within-season trend, a plain shuffle produces
    draws that are LESS like the real data than exchangeability licenses: the null is too narrow
    and a shared time trend masquerades as a real effect.  A CYCLIC SHIFT preserves the marginal
    AND the serial correlation exactly and destroys only the alignment to the response.  An excess
    that survives this null is not a trend artefact.

    `seq_order` defines what "consecutive" means (None = the frame's row order).  A rotation by
    k = 0 is a legitimate member of the rotation group and is deliberately not excluded: excluding
    it would make the null non-exact.
    """
    v = np.asarray(values, dtype=float)
    if seq_order is not None:
        inv = np.empty(len(seq_order), dtype=np.int64)
        inv[seq_order] = np.arange(len(seq_order), dtype=np.int64)
        v_seq = v[seq_order]
        codes_seq = np.asarray(codes)[seq_order]
    else:
        v_seq, codes_seq, inv = v, np.asarray(codes), None
    out = np.empty(len(v_seq), dtype=float)
    order, starts, ends = _group_slices(codes_seq)
    for s, e in zip(starts, ends):
        idx = order[s:e]
        n = e - s
        if n <= 1:
            out[idx] = v_seq[idx]
            continue
        k = int(rng.integers(0, n))
        out[idx] = np.roll(v_seq[idx], k)
    return out if inv is None else out[inv]


def _permute_rows(values, block_codes, rng):
    """THE NAIVE ROW-LEVEL PERMUTATION.  Adapted from e1_lib.py :: perm_rows.

    Reported ONLY to expose how much too narrow the wrong null is.  Never used for a verdict.
    """
    v = np.asarray(values, dtype=float)
    out = np.empty(len(v), dtype=float)
    bc = np.asarray(block_codes)
    for b in np.unique(bc):
        idx = np.where(bc == b)[0]
        out[idx] = v[idx][rng.permutation(len(idx))]
    return out


def _feature_to_float(s, feature_col):
    """Feature column -> float array, with BOOLEAN handled explicitly (P1).

    Returns (values_float, restore_fn) where `restore_fn(v)` turns a permuted float array back
    into a column of the ORIGINAL dtype.  For a boolean feature this matters: permutation only
    reshuffles values that are already exactly 0.0/1.0, so restoring `bool` is exact, and it means
    `stat_fn` sees the SAME dtype on the real frame and on every permuted frame.  Without the
    restore, a `stat_fn` that boolean-masks (`d[d[col]]`) would behave differently on the draws
    than on the real data -- a silent, direction-unknown bias.  Only bool is special-cased.
    """
    if pd.api.types.is_bool_dtype(s):
        v = s.astype("float64").to_numpy()
        nullable = not isinstance(s.dtype, np.dtype)        # pandas "boolean" vs numpy bool

        def _restore(x):
            has_nan = bool(np.isnan(x).any())
            if not has_nan and not nullable:
                return x.astype(bool)
            arr = pd.array(x != 0.0, dtype="boolean")
            if has_nan:
                arr[np.isnan(x)] = pd.NA
            return arr

        return v, _restore
    try:
        v = np.asarray(s.to_numpy(), dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "permutation_null cannot permute feature %r of dtype %s: it is neither numeric nor "
            "boolean and could not be converted to float (%s). Convert it yourself and say in "
            "FINDINGS.json what the conversion means -- the kit will not guess an encoding for "
            "you." % (feature_col, s.dtype, exc))
    return v, (lambda x: x)


def permutation_null(stat_fn, data, group_col, n_draws, seed, *,
                     feature_col, block_col=None, alternative="greater",
                     allow_nonconstant=False, tol=0.0, scheme=SCHEME_BETWEEN,
                     order_col=None, acf1_threshold=None,
                     accept_serial_structure_destroyed=False):
    """Permutation null AT A SPECIFIED GROUPING LEVEL.  REFUSES to guess.

    THE POINT: a team- or game-level aggregate permuted ROW BY ROW gets a null that is far too
    narrow.  Measured in this program: row-level nulls were 1.00-3.82x too narrow in one screen and
    1.60x too narrow in another.  Cluster-robust standard errors are NOT a substitute -- clustering
    moved t the WRONG way (up, anticonservatively) in two screens and landed nowhere near the
    permutation width in a third.

    GUARANTEES
      * `group_col` has NO DEFAULT and `None` raises.  There is no accidental row-level null.
        To get the row-level null you must pass the sentinel `screenkit.ROW_LEVEL` ("row")
        explicitly, which is what `null_width_comparison` does, for contrast only.
      * At a group level, the feature must be CONSTANT within groups; otherwise it raises and tells
        you to run `detect_grouping_level`.  (Pass `allow_nonconstant=True` to permute the
        group-representative value anyway -- you are then discarding within-group variation and you
        must say so.)
      * Only the ASSIGNMENT of already-computed values is permuted.  No aggregate is recomputed
        from a permuted key -- that form is a no-op (see `noop_placebo`).
      * `stat_fn` receives a DataFrame whose `feature_col` has been replaced.  A single working copy
        is reused across draws for speed; `stat_fn` MUST NOT mutate it.
      * A BOOLEAN feature is permuted as 0.0/1.0 and handed back to `stat_fn` AS BOOL, so the real
        frame and every permuted frame carry the same dtype.  (P1: this used to raise TypeError
        before reaching here, via the constancy check.)
      * p is the standard add-one estimator, (1 + #{draw at least as extreme}) / (n_draws + 1), so
        it is never 0.

    THREE SCHEMES -- `SCHEME_BETWEEN` (default), `SCHEME_WITHIN` (P4), `SCHEME_WITHIN_CYCLIC` (K6)
      BETWEEN: reassign WHICH GROUP's already-computed value each group receives.  The group's
        LEVEL is destroyed; within-group structure is untouched (and for a constant feature there
        is none).  This is the right null for a feature whose signal lives BETWEEN groups.
      WITHIN: shuffle values INSIDE each group.  The group's LEVEL SURVIVES and only the
        within-group (game-to-game) alignment is destroyed.  This is the right null for a candidate
        whose variance is mostly WITHIN its group -- for such a candidate the BETWEEN scheme leaves
        the effect almost intact and is not a null at all.
        *** IT ALSO DESTROYS THE FEATURE'S SERIAL STRUCTURE, AND THAT MAKES IT ANTICONSERVATIVE
        FOR AN AUTOCORRELATED FEATURE.  THIS PATH IS NOW GATED (K6, break B3). ***
      WITHIN_CYCLIC: rotate each group's series by a random offset.  The group's LEVEL survives,
        the group's MARGINAL survives, AND THE FEATURE'S SERIAL STRUCTURE SURVIVES; only the
        alignment to the response is destroyed.  *** THIS IS THE HONEST NULL FOR ANY
        `.shift(1).expanding()`-SHAPED REGRESSOR -- WHICH IS THIS PROGRAM'S MOST COMMON
        CONSTRUCTION, SO IT IS THE MODAL CASE AND NOT AN EDGE CASE. ***

      THE K6 GATE, AND WHY IT REFUSES RATHER THAN WARNS.  Before running `SCHEME_WITHIN` this
      function measures the feature's within-group lag-1 autocorrelation (`within_group_acf1`).
      When |acf1| exceeds `max(ACF1_MATERIALITY_FLOOR, 2/sqrt(n_pairs))` it RAISES, naming the
      measured value and `SCHEME_WITHIN_CYCLIC`.  The reporter who found this measured p = 0.0015
      under the shuffle where the honest null gives 0.39, on a screen whose headline would have
      been the most consequential finding in the program's history -- and a false positive.  A
      WARNING would not have been enough: the call would still have returned a well-formed p, and
      the D086 P2 precedent (make the unsafe path require an EXPLICIT OPT-IN, because a field or a
      value that reads as endorsed carries the kit's authority) has since been vindicated twice in
      the wild.  Pass `accept_serial_structure_destroyed=True` to proceed anyway; the result then
      carries `serial_structure_preserved=False` and a non-None `warning`, and you must declare it.
      THE GATE INSPECTS THE FEATURE ONLY.  The shuffle is too narrow when the feature AND the
      response both carry serial structure, and `stat_fn` is a black box, so the response is never
      seen.  That errs toward refusing a shuffle that would have been fine, never toward allowing
      one that is not.

      ROW ORDER IS AN INPUT.  "Consecutive" means consecutive in `order_col` if you pass one, and
      consecutive IN THE FRAME'S ROW ORDER if you do not.  A cyclic shift of rows that are NOT in
      time order preserves nothing -- pass `order_col`, or sort the frame by (group, date) first.
      When `SCHEME_WITHIN_CYCLIC` is used on a feature whose measured acf1 is NOT material, the
      result carries a `warning` saying so, because that is the signature of exactly this mistake.

      Adapted from E0_I0014_residual_heterogeneity/rh_base.py, which ran BETWEEN and WITHIN and
      credited a candidate ONLY IF IT BEAT BOTH.  Use `var_share_between` to see which regime you
      are in; report both nulls when the share is not near 0 or 1.
      Both WITHIN schemes are REFUSED when the feature is constant within groups, because they are
      then the literal identity -- the same vacuous control `noop_placebo` exists to catch.
      NO SCHEME HERE ANSWERS THE BETWEEN-ENTITY QUESTION FOR A WITHIN-VARYING FEATURE (K2).  If
      `detect_grouping_level` finds NO constant level and your question is nonetheless "does WHICH
      ENTITY this row belongs to matter", use `entity_swap_null`, which swaps whole entity-season
      SERIES.  Do NOT reach for `allow_nonconstant=True` for that question -- it broadcasts one
      value per group and the resulting p is manufactured rather than measured.
      If your question is "is the PER-ENTITY structure real", the control you reach for first --
      relabel the entity key and refit -- is a LITERAL NO-OP.  Use `per_entity_control` (K7).

    DOES *NOT*
      * choose the level for you, verify that the level is right, or look at the outcome's
        clustering.  Run `detect_grouping_level` first and record its output in FINDINGS.json.
      * choose the SCHEME for you either.  Neither scheme is a superset of the other and a
        candidate that beats only one has not been shown to beat a null.
      * re-derive the feature.  If your feature is built from an aggregate, permuting the finished
        column is correct; permuting the KEY and recomputing is not (it is the identity).
      * give a valid null if your statistic depends on columns other than `feature_col` that are
        themselves linked to the permuted structure.

    Parameters
    ----------
    stat_fn      : callable(DataFrame) -> float
    data         : pandas.DataFrame
    group_col    : str column name, list[str] key columns, or `screenkit.ROW_LEVEL`.  Required.
    n_draws      : int
    seed         : int
    feature_col  : str (keyword-only, required) -- the column that gets permuted
    block_col    : str | list[str] | None -- permute only WITHIN these blocks (e.g. "season")
    alternative  : "greater" | "less" | "two_sided"
    allow_nonconstant : bool
    tol          : float -- constancy tolerance passed to the within-group spread check
    scheme       : SCHEME_BETWEEN (default) | SCHEME_WITHIN | SCHEME_WITHIN_CYCLIC
    order_col    : str | list[str] | None (K6) -- the column that puts rows in TIME order inside a
                   group.  Defines "consecutive" for both the cyclic shift and the acf1 gate.
                   None means the FRAME'S ROW ORDER is already the time order.
    acf1_threshold : float | None (K6) -- override the gate threshold.  None uses
                   max(ACF1_MATERIALITY_FLOOR, 2/sqrt(n_pairs)).
    accept_serial_structure_destroyed : bool (K6) -- explicit opt-in to run `SCHEME_WITHIN` on an
                   autocorrelated feature anyway.  The result then carries a `warning` and
                   `serial_structure_preserved=False`.  Declare it in FINDINGS.json.

    Returns
    -------
    dict: real, draws (np.ndarray), n_draws, mean, sd, p, alternative, level, key_cols, n_groups,
          block_col, constant_within, scheme, feature_is_boolean, seed, is_row_level_naive, warning,
          and (K6) acf1_within_group, acf1_n_pairs, acf1_threshold, acf1_is_material,
          serial_structure_preserved, order_basis, cyclic_min_group_size,
          cyclic_median_group_size
    """
    if group_col is None:
        raise ValueError(
            "permutation_null REFUSES to run without an explicit grouping level. "
            "Run screenkit.detect_grouping_level(df, feature_col) and pass its "
            "recommended_key_cols; or pass screenkit.ROW_LEVEL explicitly if you genuinely intend "
            "the naive row-level null (which is anticonservative for any aggregate feature).")
    if feature_col not in data.columns:
        raise KeyError("feature_col %r not in frame" % feature_col)
    if alternative not in ("greater", "less", "two_sided"):
        raise ValueError("alternative must be greater|less|two_sided")
    if scheme not in (SCHEME_BETWEEN, SCHEME_WITHIN, SCHEME_WITHIN_CYCLIC):
        raise ValueError("scheme must be %r, %r or %r, got %r"
                         % (SCHEME_BETWEEN, SCHEME_WITHIN, SCHEME_WITHIN_CYCLIC, scheme))
    is_within_family = scheme in (SCHEME_WITHIN, SCHEME_WITHIN_CYCLIC)

    rng = np.random.default_rng(seed)
    feature_series = data[feature_col]
    feature_is_boolean = bool(pd.api.types.is_bool_dtype(feature_series))
    values, _restore_dtype = _feature_to_float(feature_series, feature_col)

    if block_col is None:
        block_codes = np.zeros(len(data), dtype=int)
        block_desc = None
    else:
        bcols = [block_col] if isinstance(block_col, str) else list(block_col)
        block_codes = _group_codes(data, bcols)
        block_desc = bcols

    is_row_level = isinstance(group_col, str) and group_col == ROW_LEVEL
    if is_row_level:
        if is_within_family:
            raise ValueError(
                "scheme=%r is meaningless at ROW_LEVEL: each 'group' is a single row, so shuffling "
                "inside it is the identity. Pass a real grouping level, or scheme=%r."
                % (scheme, SCHEME_BETWEEN))
        key_cols, codes, n_groups, is_const = None, None, int(len(data)), True
        level = ROW_LEVEL
    else:
        key_cols = [group_col] if isinstance(group_col, str) else list(group_col)
        missing = [c for c in key_cols if c not in data.columns]
        if missing:
            raise KeyError("group_col columns missing from frame: %s" % missing)
        codes = _group_codes(data, key_cols)
        n_groups = int(len(np.unique(codes)))
        is_const, max_distinct, _ = _constant_within(feature_series, codes, tol=tol)
        if scheme == SCHEME_BETWEEN and not is_const and not allow_nonconstant:
            raise ValueError(
                "feature %r is NOT constant within groups %s (up to %d distinct values inside one "
                "group). Permuting group-representative values would silently discard within-group "
                "variation. Run screenkit.detect_grouping_level to find the right level, pass "
                "scheme=screenkit.SCHEME_WITHIN if the signal lives INSIDE the groups, or pass "
                "allow_nonconstant=True and declare it." % (feature_col, key_cols, max_distinct))
        if is_within_family and is_const:
            raise ValueError(
                "feature %r IS constant within groups %s, so scheme=%r is the LITERAL IDENTITY: "
                "every row would receive its own value back and the 'null' would reproduce the "
                "real statistic with sd ~ 0. That is the vacuous control screenkit.noop_placebo "
                "exists to detect. Use scheme=%r at this level instead."
                % (feature_col, key_cols, scheme, SCHEME_BETWEEN))
        # groups must nest inside blocks
        if block_col is not None:
            nest = pd.DataFrame({"g": codes, "b": block_codes}).groupby("g", sort=False)["b"].nunique()
            if int(nest.max()) > 1:
                raise ValueError("groups %s do not nest inside block_col %s" % (key_cols, block_desc))
        level = "+".join(key_cols)

    # ---- K6: MEASURE THE FEATURE'S SERIAL STRUCTURE BEFORE CHOOSING TO DESTROY IT -------------
    seq_order = None
    acf = {"acf1": float("nan"), "n_pairs": 0, "min_group_size": 0, "median_group_size": 0.0,
           "order_basis": None}
    acf_thresh = float("nan")
    acf_material = False
    scheme_warning = None
    if is_within_family:
        seq_order = _order_within_groups(data, codes, order_col)
        acf = _acf1_from_codes(values, codes, seq_order)
        acf_thresh = _acf1_gate_threshold(acf["n_pairs"], acf1_threshold)
        # ONE-SIDED, and deliberately so.  POSITIVE serial correlation in the feature is what makes
        # the shuffle null too narrow when the response also drifts -- that is the K6 hazard, and it
        # is the shape of every running-mean regressor.  A NEGATIVE acf1 (an alternating or
        # mean-reverting feature) makes the shuffle null WIDER, i.e. CONSERVATIVE, so refusing on it
        # would block a safe call.  It also avoids firing on the O(1/m) NEGATIVE bias that demeaning
        # inside small groups puts on this estimator.  The signed value is always reported.
        acf_material = bool(np.isfinite(acf["acf1"]) and acf["acf1"] > acf_thresh)

        if scheme == SCHEME_WITHIN and acf_material and not accept_serial_structure_destroyed:
            raise ValueError(
                "*** REFUSED (K6): scheme=%r WOULD GIVE YOU A NULL THAT IS TOO NARROW. *** "
                "Feature %r has within-group lag-1 autocorrelation acf1 = %+.4f over %d "
                "consecutive pairs in %d groups (threshold %.4f, measured in %s). A within-group "
                "SHUFFLE destroys that serial structure while the RESPONSE keeps its own drift, so "
                "the permuted draws are less like the real data than exchangeability licenses and "
                "the p comes out too small. Measured on a real screen: p = 0.0015 under this "
                "scheme where the honest null gives 0.39, on a result that would have been "
                "published. THE FIX: pass scheme=screenkit.SCHEME_WITHIN_CYCLIC, which rotates "
                "each group's series and preserves the marginal AND the serial structure while "
                "destroying only the alignment to the response -- and make sure the rows inside "
                "each group are in TIME order (pass order_col=...). If you genuinely want the "
                "shuffle, pass accept_serial_structure_destroyed=True and record in FINDINGS.json "
                "that the resulting p is anticonservative."
                % (scheme, feature_col, acf["acf1"], acf["n_pairs"], acf["n_groups"],
                   acf_thresh, acf["order_basis"]))

        if scheme == SCHEME_WITHIN and acf_material:
            scheme_warning = (
                "SCHEME_WITHIN RUN UNDER accept_serial_structure_destroyed=True ON AN "
                "AUTOCORRELATED FEATURE (acf1 = %+.4f > %.4f). THIS NULL IS TOO NARROW AND THIS p "
                "IS ANTICONSERVATIVE. Report it beside a SCHEME_WITHIN_CYCLIC null, never alone."
                % (acf["acf1"], acf_thresh))
        elif scheme == SCHEME_WITHIN_CYCLIC and not acf_material:
            scheme_warning = (
                "SCHEME_WITHIN_CYCLIC on a feature whose measured within-group acf1 is only %+.4f "
                "(threshold %.4f, measured in %s). The cyclic shift is then buying nothing over "
                "SCHEME_WITHIN -- which is fine -- BUT IF YOU BELIEVE THIS FEATURE IS "
                "AUTOCORRELATED, THE ROWS INSIDE EACH GROUP ARE PROBABLY NOT IN TIME ORDER, and a "
                "cyclic shift of a scrambled series preserves nothing while offering only n_g "
                "distinct draws per group. Pass order_col=<your date column>."
                % (acf["acf1"], acf_thresh, acf["order_basis"]))
        elif scheme == SCHEME_WITHIN_CYCLIC and acf["min_group_size"] < 5:
            scheme_warning = (
                "SCHEME_WITHIN_CYCLIC: the smallest group has only %d rows, so it contributes only "
                "%d distinct rotations. The joint null over %d groups is still rich, but a p "
                "computed on very small groups is granular. min/median group size = %d/%.1f."
                % (acf["min_group_size"], max(acf["min_group_size"], 1), acf["n_groups"],
                   acf["min_group_size"], acf["median_group_size"]))

    work = data.copy()
    draws = np.empty(n_draws, dtype=float)
    for i in range(n_draws):
        if is_row_level:
            v = _permute_rows(values, block_codes, rng)
        elif scheme == SCHEME_WITHIN:
            v = _permute_within_groups(values, codes, rng)
        elif scheme == SCHEME_WITHIN_CYCLIC:
            v = _permute_within_groups_cyclic(values, codes, rng, seq_order)
        else:
            v = _permute_group_values(values, codes, block_codes, rng)
        work[feature_col] = _restore_dtype(v)
        draws[i] = float(stat_fn(work))

    real = float(stat_fn(data))
    finite = draws[np.isfinite(draws)]
    if alternative == "greater":
        n_ext = int((finite >= real).sum())
    elif alternative == "less":
        n_ext = int((finite <= real).sum())
    else:
        c = float(np.median(finite)) if len(finite) else 0.0
        n_ext = int((np.abs(finite - c) >= abs(real - c)).sum())
    p = (1.0 + n_ext) / (len(finite) + 1.0)

    return {
        "real": real,
        "draws": draws,
        "n_draws": int(n_draws),
        "n_finite_draws": int(len(finite)),
        "mean": float(finite.mean()) if len(finite) else float("nan"),
        "sd": float(finite.std(ddof=1)) if len(finite) > 1 else float("nan"),
        "p": float(p),
        "alternative": alternative,
        "level": level,
        "key_cols": key_cols,
        "n_groups": n_groups,
        "block_col": block_desc,
        "constant_within": bool(is_const),
        "scheme": ROW_LEVEL if is_row_level else scheme,
        "feature_is_boolean": feature_is_boolean,
        "seed": int(seed),
        "is_row_level_naive": bool(is_row_level),
        # ---- K6 diagnostics.  Reported on EVERY within-family call, not only on the gated one. --
        "acf1_within_group": _nan_to_none(acf["acf1"]),
        "acf1_n_pairs": int(acf["n_pairs"]),
        "acf1_threshold": _nan_to_none(acf_thresh),
        "acf1_is_material": bool(acf_material),
        "serial_structure_preserved": (None if not is_within_family
                                       else scheme == SCHEME_WITHIN_CYCLIC),
        "order_basis": acf["order_basis"],
        "cyclic_min_group_size": int(acf["min_group_size"]),
        "cyclic_median_group_size": float(acf["median_group_size"]),
        "warning": (
            "THIS IS THE NAIVE ROW-LEVEL NULL. It is anticonservative whenever the feature or the "
            "outcome is clustered, and it must not carry a verdict. It is here for CONTRAST -- "
            "report it beside a correct-level null and its inflation factor (see "
            "null_width_comparison), never on its own." if is_row_level else scheme_warning),
    }


def null_width_comparison(stat_fn, data, group_col, n_draws, seed, *,
                          feature_col, block_col=None, alternative="greater",
                          allow_nonconstant=False, scheme=SCHEME_BETWEEN, verbose=False,
                          order_col=None, acf1_threshold=None,
                          accept_serial_structure_destroyed=False):
    """Run BOTH the correct-level null and the naive ROW-LEVEL null; report the INFLATION FACTOR.

    Every screen should surface this number rather than rediscovering it.  Measured precedents:
    1.00-3.82x (E0_I0013) and 1.60x (E1_I0013).

    GUARANTEES
      * Both nulls use the SAME seed, the SAME n_draws and the SAME statistic, so the ratio is
        attributable to the permutation scheme alone.
      * `inflation` = sd(correct level) / sd(row level).  A value > 1 means the row-level null was
        TOO NARROW by that factor, i.e. any p taken on it was anticonservative.

    DOES *NOT*
      * make the row-level p usable.  It is reported for contrast only and must never carry a
        verdict, no matter how small the inflation factor turns out to be.
      * substitute for cluster-robust SEs being wrong -- it replaces them.  Do not report a
        cluster-robust t as if it were an alternative to this.

    Returns
    -------
    dict: correct (permutation_null result), row_level (permutation_null result),
          inflation, p_correct, p_row_level_NAIVE, verdict
    """
    correct = permutation_null(stat_fn, data, group_col, n_draws, seed,
                               feature_col=feature_col, block_col=block_col,
                               alternative=alternative, allow_nonconstant=allow_nonconstant,
                               scheme=scheme, order_col=order_col,
                               acf1_threshold=acf1_threshold,
                               accept_serial_structure_destroyed=(
                                   accept_serial_structure_destroyed))
    naive = permutation_null(stat_fn, data, ROW_LEVEL, n_draws, seed,
                             feature_col=feature_col, block_col=block_col,
                             alternative=alternative)
    infl = correct["sd"] / naive["sd"] if naive["sd"] > 0 else float("inf")
    res = {
        "correct": correct,
        "row_level": naive,
        "inflation": float(infl),
        "p_correct": correct["p"],
        "p_row_level_NAIVE": naive["p"],
        "verdict": ("row-level null is %.2fx TOO NARROW -- any p taken on it is anticonservative"
                    % infl) if infl > 1.0 else
                   ("row-level null is not narrower here (ratio %.2f); the correct-level null "
                    "still carries the verdict" % infl),
    }
    if verbose:
        print("  null_width_comparison(%s): real=%.6g" % (feature_col, correct["real"]))
        print("    correct level %-22s sd=%.6g  p=%.4f  (n_groups=%d)"
              % (correct["level"], correct["sd"], correct["p"], correct["n_groups"]))
        print("    NAIVE row level %-20s sd=%.6g  p=%.4f  [CONTRAST ONLY]"
              % ("row", naive["sd"], naive["p"]))
        print("    INFLATION FACTOR sd_correct/sd_row = %.3f -> %s" % (infl, res["verdict"]))
    return res


# ===========================================================================================
# ENTITY-SWAP NULL -- THE BETWEEN-ENTITY QUESTION ON A WITHIN-VARYING FEATURE  (trap 1 / K2)
# ===========================================================================================

class EntitySwap:
    """Reassign whole entity-season SERIES to other entity-seasons inside the same season.

    *** THIS CLOSES A GENUINE CAPABILITY GAP (K2), NOT A MISUSE. ***
    Before this existed, the kit shipped exactly two schemes and NEITHER answered the
    between-entity question for a feature that varies WITHIN its entity:

      `SCHEME_BETWEEN` REQUIRES the feature to be constant within groups, and forcing it on with
        `allow_nonconstant=True` broadcasts one representative value per group -- annihilating 100%
        of the within-group variation the real statistic keeps.  This module's own docstrings call
        the resulting p "manufactured rather than measured".
      `SCHEME_WITHIN` is the LITERAL IDENTITY when the feature IS constant within groups, which is
        why `permutation_null` refuses that combination.

    Every expanding-prior candidate is neither: it varies within its entity-season AND carries most
    of its signal at the entity-season level.  The kit's third user
    (`E0_I0016_efficiency_predictors`) verified with `detect_grouping_level` that NO candidate was
    constant within its entity-season in ANY OF 132 CELLS, declared the gap, and built this itself.
    Ported from `E0_I0016_efficiency_predictors/ep_base.py :: EntitySwap` (read-only), generalised
    only in that the date tiebreak column is a parameter rather than hard-coded to `game_id` and
    the season blocking may be switched off.

    EXCHANGEABILITY TESTED: THE ENTITY LABELS.  Under H0 that WHICH ENTITY a row is attached to
    carries no information about the outcome beyond the reference model, relabelling entities
    leaves the joint distribution unchanged.

    CONSTRUCTION.  Rows are grouped by `entity_cols` and ordered by `date_col` within each group.
    Per draw, entity groups are permuted INSIDE each season; an entity of length n_a receives its
    partner's values at PROPORTIONAL positions `round(k/(n_a-1) * (n_b-1))`, so position 0 maps to
    position 0 and the last position maps to the last.  SERIES LENGTH AND WITHIN-SEASON TEMPORAL
    SHAPE ARE PRESERVED -- which matters, because an early-season expanding prior is mechanically
    noisier than a late-season one and a null that scrambled that would not be comparing like with
    like.

    GUARANTEES
      * Every row keeps its own position in its own entity's series; only WHICH ENTITY's values
        land there changes.
      * Swaps never cross a season (with `season_col=None`, the whole frame is one block).
      * An entity that spans more than one season raises rather than being silently assigned to
        one of them -- put the season in `entity_cols`, or pass `season_col=None` deliberately.
      * A season block holding a single entity yields that entity's own values back, exactly.

    DOES *NOT*
      * preserve the exact marginal distribution when partners differ in length (values are
        resampled with repetition under the proportional map).
      * preserve cross-entity correlation structure.
      * bootstrap anything.  It randomises LABELS, so it says nothing about the sampling
        variability of the effect size.
      * test the WITHIN-entity question.  For that use `permutation_null(..., scheme=SCHEME_WITHIN)`
        at the entity level, and credit a candidate only if it beats BOTH -- as E0_I0014 did.

    Parameters
    ----------
    df          : pandas.DataFrame
    entity_cols : str | list[str] -- e.g. ["opp_team_id", "season"]
    date_col    : str (keyword-only, required) -- within-entity ordering
    season_col  : str | None (keyword-only, default "season") -- swaps stay inside a season;
                  None means the whole frame is one block
    tiebreak_col: str | None (keyword-only) -- secondary sort inside a date (e.g. "game_id");
                  None uses the row's original position, which is a stable tiebreak
    """

    def __init__(self, df, entity_cols, *, date_col, season_col="season", tiebreak_col=None):
        ent = [entity_cols] if isinstance(entity_cols, str) else list(entity_cols)
        need = list(ent) + [date_col] + ([season_col] if season_col else []) + \
            ([tiebreak_col] if tiebreak_col else [])
        missing = [c for c in need if c not in df.columns]
        if missing:
            raise KeyError("EntitySwap: columns missing from frame: %s" % missing)

        codes = _group_codes(df, ent)
        tie = (df[tiebreak_col].to_numpy() if tiebreak_col is not None
               else np.arange(len(df)))
        order = np.lexsort((tie, df[date_col].to_numpy(), codes))

        self.n = int(len(df))
        self.entity_cols = ent
        self.date_col = date_col
        self.season_col = season_col
        self.groups = []                                  # list of row-index arrays, date-ordered
        oc = codes[order]
        starts = np.flatnonzero(np.r_[True, oc[1:] != oc[:-1]]) if len(oc) else np.array([], int)
        ends = np.r_[starts[1:], len(oc)] if len(starts) else np.array([], int)

        if season_col is None:
            season_codes = np.zeros(len(df), dtype=np.int64)
            season_labels = np.array(["ALL_ROWS_ONE_BLOCK"], dtype=object)
        else:
            sc, season_labels = pd.factorize(df[season_col], sort=True)
            season_codes = np.asarray(sc, dtype=np.int64)
            season_labels = np.asarray(season_labels, dtype=object)

        group_season = []
        for s, e in zip(starts, ends):
            idx = order[s:e]
            ssn = np.unique(season_codes[idx])
            if len(ssn) > 1:
                raise ValueError(
                    "EntitySwap: entity %s spans more than one %r (%s). An entity that changes "
                    "season is not exchangeable with a single-season entity. Put the season inside "
                    "entity_cols (e.g. %s), or pass season_col=None if you really intend swaps "
                    "across seasons and will declare that in FINDINGS.json."
                    % (ent, season_col, [season_labels[i] for i in ssn], ent + [season_col]))
            self.groups.append(idx)
            group_season.append(int(ssn[0]))

        self.by_season = {}
        for gi, sc_i in enumerate(group_season):
            self.by_season.setdefault(sc_i, []).append(gi)
        self.season_labels = {k: season_labels[k] for k in self.by_season}
        self.n_groups = len(self.groups)
        self.n_seasons = len(self.by_season)
        self.group_sizes = np.array([len(g) for g in self.groups], dtype=np.int64)

    def draw(self, values, rng):
        """One draw: every entity receives some same-season entity's series, proportionally mapped.

        `values` is a float array in the ORIGINAL row order; the return is the same.
        """
        x = np.asarray(values, dtype=float)
        if len(x) != self.n:
            raise ValueError("EntitySwap.draw: expected %d values, got %d" % (self.n, len(x)))
        out = np.empty(self.n, dtype=float)
        for gis in self.by_season.values():
            partners = [gis[p] for p in rng.permutation(len(gis))]
            for a, b in zip(gis, partners):
                ia, ib = self.groups[a], self.groups[b]
                na, nb = len(ia), len(ib)
                if na == 1 or nb == 1:
                    src = np.zeros(na, dtype=np.int64)
                else:
                    src = np.rint(np.arange(na) / (na - 1) * (nb - 1)).astype(np.int64)
                out[ia] = x[ib[src]]
        return out


def entity_swap_null(stat_fn, data, entity_cols, n_draws, seed, *, feature_col,
                     date_col, season_col="season", tiebreak_col=None,
                     alternative="greater", swapper=None, verbose=False):
    """Permutation null from `EntitySwap`: the BETWEEN-ENTITY question, WITHIN-varying feature ok.

    Ported from `E0_I0016_efficiency_predictors/ep_base.py :: entity_swap_null` (read-only) and
    given this module's `stat_fn(DataFrame) -> float` calling convention, so it composes with
    everything else here.  Read `EntitySwap`'s docstring for what is and is not exchanged.

    WHEN THIS IS THE RIGHT NULL
      Your question is "does WHICH ENTITY this row belongs to matter", your feature varies WITHIN
      the entity (so `SCHEME_BETWEEN` is invalid and `SCHEME_WITHIN` answers a different question),
      and the within-entity temporal shape is meaningful and must be preserved.  Run
      `detect_grouping_level` first: if NO level is constant-within, that is the signature of this
      case, and it is exactly what the reporter observed across 132 candidate-by-cell combinations.

    GUARANTEES
      * `entity_cols` has NO DEFAULT.  There is no accidental row-level null here either.
      * p is the add-one estimator, (1 + #{draw at least as extreme}) / (n_finite + 1), never 0.
      * A BOOLEAN feature is permuted as 0.0/1.0 and handed back to `stat_fn` AS BOOL, matching
        `permutation_null`, so `stat_fn` sees one dtype on the real frame and on every draw.
      * `stat_fn` receives a DataFrame whose `feature_col` has been replaced.  One working copy is
        reused across draws for speed; `stat_fn` MUST NOT mutate it.
      * Passing a prebuilt `swapper` reuses the (comparatively expensive) grouping across many
        candidates; it is validated against `data`'s length.

    DOES *NOT*
      * substitute for the within-entity null.  A candidate that beats only one of the two has not
        been shown to beat a null; report both.
      * make the entity-level question well posed if your OUTCOME is clustered at a level coarser
        than the entity.  That is a separate problem this does not detect.
      * preserve the marginal distribution exactly when entity series differ in length -- see the
        DOES NOT list on `EntitySwap`.

    Returns
    -------
    dict: real, draws, n_draws, n_finite_draws, mean, sd, p, alternative, level, key_cols,
          n_groups, n_seasons, season_col, scheme, feature_is_boolean, seed, is_row_level_naive,
          warning
    """
    if entity_cols is None:
        raise ValueError(
            "entity_swap_null REFUSES to run without explicit entity columns. The whole point of "
            "this null is WHICH ENTITY a row belongs to; there is no default entity.")
    if feature_col not in data.columns:
        raise KeyError("feature_col %r not in frame" % feature_col)
    if alternative not in ("greater", "less", "two_sided"):
        raise ValueError("alternative must be greater|less|two_sided")

    if swapper is None:
        swapper = EntitySwap(data, entity_cols, date_col=date_col, season_col=season_col,
                             tiebreak_col=tiebreak_col)
    elif swapper.n != len(data):
        raise ValueError("entity_swap_null: the supplied swapper was built on %d rows but `data` "
                         "has %d. A swapper holds row POSITIONS and cannot be reused across "
                         "differently-shaped frames." % (swapper.n, len(data)))

    feature_series = data[feature_col]
    feature_is_boolean = bool(pd.api.types.is_bool_dtype(feature_series))
    values, _restore_dtype = _feature_to_float(feature_series, feature_col)

    rng = np.random.default_rng(seed)
    work = data.copy()
    draws = np.empty(int(n_draws), dtype=float)
    for i in range(int(n_draws)):
        work[feature_col] = _restore_dtype(swapper.draw(values, rng))
        draws[i] = float(stat_fn(work))

    real = float(stat_fn(data))
    finite = draws[np.isfinite(draws)]
    if alternative == "greater":
        n_ext = int((finite >= real).sum())
    elif alternative == "less":
        n_ext = int((finite <= real).sum())
    else:
        c = float(np.median(finite)) if len(finite) else 0.0
        n_ext = int((np.abs(finite - c) >= abs(real - c)).sum())
    p = (1.0 + n_ext) / (len(finite) + 1.0)

    ent = [entity_cols] if isinstance(entity_cols, str) else list(entity_cols)
    res = {
        "real": real,
        "draws": draws,
        "n_draws": int(n_draws),
        "n_finite_draws": int(len(finite)),
        "mean": float(finite.mean()) if len(finite) else float("nan"),
        "sd": float(finite.std(ddof=1)) if len(finite) > 1 else float("nan"),
        "p": float(p),
        "alternative": alternative,
        "level": "+".join(str(c) for c in ent),
        "key_cols": ent,
        "n_groups": int(swapper.n_groups),
        "n_seasons": int(swapper.n_seasons),
        "season_col": season_col,
        "scheme": SCHEME_ENTITY_SWAP,
        "feature_is_boolean": feature_is_boolean,
        "seed": int(seed),
        "is_row_level_naive": False,
        "warning": (
            "entity_swap answers the BETWEEN-ENTITY question only. It leaves the within-entity "
            "temporal shape intact by construction, so it says nothing about whether the "
            "candidate's WITHIN-entity movement carries signal. Run "
            "permutation_null(..., scheme=SCHEME_WITHIN) for that and credit the candidate only if "
            "it beats BOTH."),
    }
    if verbose:
        print("  entity_swap_null(%s at %s): real=%.6g" % (feature_col, res["level"], real))
        print("    %d entity groups across %d season block(s); %d draws, seed %d"
              % (res["n_groups"], res["n_seasons"], res["n_draws"], res["seed"]))
        print("    null mean=%.6g  sd=%.6g  p=%.4f  (alternative=%s)"
              % (res["mean"], res["sd"], res["p"], alternative))
        print("    !! %s" % res["warning"])
    return res


# ===========================================================================================
# VARIANCE DECOMPOSITION -- WHICH PERMUTATION SCHEME IS THE REAL NULL?  (trap 1 / P4)
# ===========================================================================================

def var_share_between(data, feature_col, group_col, block_col=None):
    """Fraction of a feature's variance that lives BETWEEN groups rather than WITHIN them.

    Adapted from E0_I0014_residual_heterogeneity/rh_base.py :: var_share_between() (frozen, read
    only), which had to write it itself because the kit shipped no such helper.

    WHY YOU NEED THIS BEFORE CHOOSING A SCHEME
      `permutation_null(..., scheme=SCHEME_BETWEEN)` destroys the BETWEEN-group signal and leaves
      the WITHIN-group signal intact.  If a candidate's variance is almost entirely WITHIN its
      groups (share near 0), the between-scheme barely perturbs it: the "null" draws still contain
      nearly the whole effect, and beating that null is not evidence of anything.  The mirror
      holds for `SCHEME_WITHIN` on a share near 1 -- there it is the literal identity, and
      `permutation_null` refuses it.

        share ~ 1.0  -> the feature is (near) constant within groups.  BETWEEN is the null.
        share ~ 0.0  -> the feature is (near) mean-free across groups.  WITHIN is the null.
        in between   -> RUN BOTH and credit the candidate only if it beats BOTH, which is exactly
                        what E0_I0014 did.

    GUARANTEES
      * The ratio is SS_between / SS_total over the FINITE rows only, with both taken about the
        same global mean, so it is exactly 1.0 for a feature constant within groups and exactly 0.0
        for a feature whose group means are all equal.
      * NaNs are dropped, not imputed; groups left empty by that drop are skipped.
      * `nan` is returned (never an exception, never 0) when total variance is zero or non-finite.

    DOES *NOT*
      * decide the scheme for you, or adjust for group sizes / unbalanced designs -- this is a raw
        variance share, not an ICC estimate with a correction.
      * say anything about the OUTCOME's clustering, which is a separate question and the one that
        governs whether a row-level null is anticonservative.

    Parameters
    ----------
    data        : pandas.DataFrame
    feature_col : str
    group_col   : str | list[str] -- the same key you would pass to `permutation_null`
    block_col   : str | list[str] | None -- appended to the key, matching rh_base's
                  (season, key) blocks.  A no-op when groups already nest inside blocks.

    Returns
    -------
    float
    """
    if feature_col not in data.columns:
        raise KeyError("feature_col %r not in frame" % feature_col)
    key = [group_col] if isinstance(group_col, str) else list(group_col)
    if block_col is not None:
        bcols = [block_col] if isinstance(block_col, str) else list(block_col)
        key = bcols + [c for c in key if c not in bcols]
    missing = [c for c in key if c not in data.columns]
    if missing:
        raise KeyError("group_col/block_col columns missing from frame: %s" % missing)

    v, _ = _feature_to_float(data[feature_col], feature_col)
    codes = _group_codes(data, key)
    fin = np.isfinite(v)
    if fin.sum() == 0:
        return float("nan")
    vf, cf = v[fin], np.asarray(codes)[fin]
    tot = float(np.var(vf))                       # population variance, as rh_base used
    if not np.isfinite(tot) or tot <= 0:
        return float("nan")
    gm = float(vf.mean())
    order = np.argsort(cf, kind="stable")
    sc, sv = cf[order], vf[order]
    starts = np.flatnonzero(np.r_[True, sc[1:] != sc[:-1]])
    ends = np.r_[starts[1:], len(sc)]
    num = 0.0
    for s, e in zip(starts, ends):
        num += (e - s) * (float(sv[s:e].mean()) - gm) ** 2
    return float(num / len(vf) / tot)


# ===========================================================================================
# PAIRED FORECAST-VS-FORECAST COMPARISON  (P4)
# ===========================================================================================

def paired_forecast_comparison(y, yhat_a, yhat_b, groups, n_draws=2000, seed=0, *,
                               name_a="A", name_b="B", alternative="two_sided", verbose=False):
    """Is forecast A better than forecast B on the SAME rows?  Clustered paired sign-flip test.

    THIS IS THE SHAPE EVERY SKILL COMPARISON IN THIS PROGRAM ACTUALLY HAS: two forecasts of one
    outcome on one row set, and the question of whether the difference between them survives the
    clustering.  Before this existed, screens either compared two R2 numbers with no null at all,
    or reimplemented a null themselves.

    THE STATISTIC
      Per row, the PAIRED loss difference `d_i = (y_i - a_i)^2 - (y_i - b_i)^2`; `d_i < 0` means A
      is closer on that row.  Aggregated, `dr2_a_minus_b = -sum(d)/SST = r2_of_forecast(y, a) -
      r2_of_forecast(y, b)` exactly.  The pairing is what buys the power: the shared, and usually
      dominant, difficulty of each row cancels inside `d_i`.

    THE NULL: SIGN-FLIP WHOLE CLUSTERS
      Under H0 that the two forecasts are exchangeable, swapping the labels A/B within an entire
      cluster negates that cluster's whole contribution to `sum(d)` and leaves the joint
      distribution unchanged.  So the null is generated by flipping the sign of each CLUSTER'S SUM
      independently -- not each row's.  Flipping ROWS independently is the paired analogue of the
      row-level permutation null and is anticonservative in exactly the same way and for exactly
      the same reason; it is computed here for CONTRAST ONLY and reported as
      `p_row_level_NAIVE` with the inflation factor beside it.

    GUARANTEES
      * `groups` has NO DEFAULT and `None` raises, mirroring `permutation_null`.  Getting the naive
        row-level version requires passing `screenkit.ROW_LEVEL` by name.
      * `dr2_a_minus_b` equals `r2_of_forecast(y, yhat_a) - r2_of_forecast(y, yhat_b)` to machine
        precision, on the rows where all three of y, a, b are finite.
      * The cluster-level test is EXACT under exchangeability of the two forecasts within a
        cluster -- it is not an asymptotic approximation, and it needs no scipy.
      * Identical forecasts give `d == 0` for every row, hence `p == 1.0` exactly, not a small
        random number.  A comparison of a forecast with itself can never look significant.
      * p is the add-one estimator, so it is never 0.
      * Both the cluster and the row-level nulls use the SAME seed and the SAME `d`, so the
        inflation factor is attributable to the clustering alone.

    DOES *NOT*
      * fit or calibrate either forecast.  Both are scored exactly as given (see `r2_of_forecast`).
        If A wins only after refitting, that is a different and much weaker claim.
      * test "equal expected loss" in general -- it tests whether the cluster contributions are
        symmetric about zero, which is what exchangeability of the two forecasts implies.  A
        difference in loss VARIANCE with equal means is not detected.
      * know whether your clusters are the right ones.  If the errors are correlated at a level
        COARSER than `groups`, this is still anticonservative; use the coarsest level you can
        defend and say which one in FINDINGS.json.
      * handle NaN by imputing.  Rows where any of y, a, b is non-finite are DROPPED, and the count
        that survived is returned as `n`.

    Parameters
    ----------
    y, yhat_a, yhat_b : (n,) array_like of float
    groups   : (n,) array_like of cluster labels, or `screenkit.ROW_LEVEL`.  Required.
    n_draws  : int
    seed     : int
    alternative : "two_sided" (default) | "greater" (A better) | "less" (B better)
    verbose  : bool

    Returns
    -------
    dict: n, n_groups, r2_a, r2_b, dr2_a_minus_b, mean_paired_loss_diff, draws, sd, p,
          p_row_level_NAIVE, inflation, alternative, is_row_level_naive, seed, verdict, warning
    """
    if groups is None:
        raise ValueError(
            "paired_forecast_comparison REFUSES to run without an explicit clustering level. "
            "Pass the cluster labels the forecast errors are correlated within (game, team-season, "
            "player-season ...), or pass screenkit.ROW_LEVEL explicitly if you genuinely intend "
            "the naive independent-rows null, which is anticonservative for clustered errors.")
    if alternative not in ("greater", "less", "two_sided"):
        raise ValueError("alternative must be greater|less|two_sided")

    y = np.asarray(y, dtype=float)
    a = np.asarray(yhat_a, dtype=float)
    b = np.asarray(yhat_b, dtype=float)
    if not (y.shape == a.shape == b.shape) or y.ndim != 1:
        raise ValueError("paired_forecast_comparison: y, yhat_a, yhat_b must be 1-D and the same "
                         "length, got %s, %s, %s" % (y.shape, a.shape, b.shape))

    is_row_level = isinstance(groups, str) and groups == ROW_LEVEL
    if is_row_level:
        g = np.arange(len(y))
    else:
        g = np.asarray(groups)
        if g.shape[0] != y.shape[0]:
            raise ValueError("groups must have one label per row (%d), got %d"
                             % (len(y), g.shape[0]))

    m = np.isfinite(y) & np.isfinite(a) & np.isfinite(b)
    if m.sum() < 2:
        raise ValueError("paired_forecast_comparison: fewer than 2 rows are finite in all of "
                         "y, yhat_a, yhat_b")
    y, a, b, g = y[m], a[m], b[m], g[m]
    n = int(len(y))

    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0:
        raise ValueError("paired_forecast_comparison: y has zero variance, R2 is undefined")
    d = (y - a) ** 2 - (y - b) ** 2                       # >0 => A worse on that row
    r2_a = 1.0 - float(((y - a) ** 2).sum()) / sst
    r2_b = 1.0 - float(((y - b) ** 2).sum()) / sst
    real = -float(d.sum()) / sst                          # == r2_a - r2_b

    gcodes = pd.factorize(g, sort=False)[0]
    n_groups = int(gcodes.max()) + 1 if len(gcodes) else 0
    csum = np.bincount(gcodes, weights=d, minlength=n_groups)

    def _draws_for(vec, rng):
        signs = rng.integers(0, 2, size=(int(n_draws), len(vec))) * 2 - 1
        return -(signs @ vec) / sst

    draws = _draws_for(csum, np.random.default_rng(seed))
    row_draws = _draws_for(d, np.random.default_rng(seed))

    def _p(dr):
        if alternative == "greater":
            n_ext = int((dr >= real).sum())
        elif alternative == "less":
            n_ext = int((dr <= real).sum())
        else:
            n_ext = int((np.abs(dr) >= abs(real)).sum())   # sign-flip null is centred at 0
        return (1.0 + n_ext) / (len(dr) + 1.0)

    p = _p(draws)
    p_row = _p(row_draws)
    sd = float(draws.std(ddof=1)) if n_draws > 1 else float("nan")
    sd_row = float(row_draws.std(ddof=1)) if n_draws > 1 else float("nan")
    infl = sd / sd_row if sd_row > 0 else float("inf")

    better = name_a if real > 0 else (name_b if real < 0 else "neither")
    res = {
        "n": n,
        "n_groups": n_groups,
        "name_a": name_a,
        "name_b": name_b,
        "r2_a": r2_a,
        "r2_b": r2_b,
        "dr2_a_minus_b": real,
        "mean_paired_loss_diff": float(d.mean()),
        "draws": draws,
        "n_draws": int(n_draws),
        "sd": sd,
        "p": float(p),
        "p_row_level_NAIVE": float(p_row),
        "sd_row_level_NAIVE": sd_row,
        "inflation": float(infl),
        "alternative": alternative,
        "is_row_level_naive": bool(is_row_level),
        "seed": int(seed),
        "verdict": ("%s beats %s by dR2 = %+.6f (cluster sign-flip p = %.4f over %d clusters). "
                    "The naive independent-rows null would have given p = %.4f; it is %.2fx TOO "
                    "NARROW." % (better, name_b if better == name_a else name_a, abs(real), p,
                                 n_groups, p_row, infl))
                   if real != 0 else
                   ("the two forecasts are IDENTICAL on these rows (dR2 = 0 exactly, p = %.4f)" % p),
        "warning": (
            "groups=ROW_LEVEL: this is the NAIVE independent-rows paired test. It is "
            "anticonservative whenever forecast errors are correlated within games, teams or "
            "players, which they are. Report it for contrast only." if is_row_level else None),
    }
    if verbose:
        print("  paired_forecast_comparison(%s vs %s): n=%d over %d clusters"
              % (name_a, name_b, n, n_groups))
        print("    r2_of_forecast(%-10s) = %+.6f" % (name_a, r2_a))
        print("    r2_of_forecast(%-10s) = %+.6f" % (name_b, r2_b))
        print("    dR2 (A - B)            = %+.6f   mean paired loss diff = %+.6g"
              % (real, res["mean_paired_loss_diff"]))
        print("    CLUSTER sign-flip null : sd = %.6g   p = %.4f" % (sd, p))
        print("    NAIVE row sign-flip    : sd = %.6g   p = %.4f   [CONTRAST ONLY]" % (sd_row, p_row))
        print("    null-width inflation (cluster/row) = %.3f" % infl)
        print("    -> %s" % res["verdict"])
    return res


# ===========================================================================================
# NO-OP PLACEBO DIAGNOSTIC
# ===========================================================================================

def noop_placebo(stat_fn, data, n_draws, transform=None, tol=1e-15, verbose=False):
    """Detect a DEFECTIVE placebo: one that reproduces the real statistic because it is the identity.

    The classic defective form is "permute the grouping key everywhere and RECOMPUTE the aggregate
    from the permuted key".  The permuted cell is the same row set under a bijection, so every row
    still receives its own true value.  Signature: the real number is reproduced with sd ~ 0, and
    such a control tests NOTHING.  See E0_I0013_possession_volume/run_screen.py and
    E1_I0008_height_mismatch/stage1_noise_floor.py.

    TOLERANCE -- READ THIS
      Do NOT assert bitwise-exact zero.  A real screen found 5 of 7 statistics bitwise exact and 2
      at ~1e-19 owing to LAPACK non-determinism.  This function therefore tests `sd < tol` with
      tol=1e-15 by default and RETURNS the observed sd so the caller can report it honestly rather
      than rounding it to "0.000000".

    GUARANTEES
      * Returns the draws, the real statistic, the observed sd (float, never rounded), the number
        of distinct draw values, and the max absolute deviation from the real statistic.
      * `is_noop` is True iff sd < tol AND max|draw - real| < tol.
      * Never raises on a confirmed no-op.  A confirmed no-op is a DIAGNOSTIC RESULT, not an error;
        the finding is "this control was vacuous", which the screen must report.

    THE SECOND, ONE LEVEL DOWN  (K7)
      The same bijection argument kills the control an analyst reaches for FIRST when validating
      PER-ENTITY work: "relabel the player key and refit the per-player coefficients".  Relabelling
      ids is a bijection on whole GROUPS, so every player's row set travels intact to its new label
      and the multiset of fitted coefficients -- and therefore its spread -- is EXACTLY unchanged.
      The kit's eighth user confirmed it at observed sd = 5.207e-17.  This function will correctly
      report that as a no-op; `per_entity_control` runs it BESIDE a control that can actually fail,
      which is the thing a caller who has just been told "your control is vacuous" needs next.

    DOES *NOT*
      * fix the placebo.  If `is_noop` is True your control is worthless and you need a real one
        (permute the ASSIGNMENT of already-computed values -- see `permutation_null`; for a
        PER-ENTITY statistic see `per_entity_control`).
      * prove a placebo is VALID when `is_noop` is False.  Nonzero sd only rules out the identity;
        the scheme can still be at the wrong grouping level.

    Parameters
    ----------
    stat_fn   : callable(DataFrame) -> float
    data      : pandas.DataFrame
    n_draws   : int
    transform : callable(DataFrame, np.random.Generator) -> DataFrame, or None.
                None means the literal identity (the purest no-op).  Pass the transform you SUSPECT
                is a no-op -- e.g. the relabel-the-key-and-recompute pipeline -- to test it.
    tol       : float
    """
    rng = np.random.default_rng(0)
    real = float(stat_fn(data))
    draws = np.empty(n_draws, dtype=float)
    for i in range(n_draws):
        d = data if transform is None else transform(data, rng)
        draws[i] = float(stat_fn(d))
    sd = float(draws.std(ddof=0))
    max_dev = float(np.max(np.abs(draws - real))) if n_draws else 0.0
    is_noop = bool(sd < tol and max_dev < tol)
    res = {
        "real": real,
        "draws": draws,
        "n_draws": int(n_draws),
        "sd": sd,
        "max_abs_dev_from_real": max_dev,
        "n_distinct_draw_values": int(len(np.unique(draws))),
        "tol": float(tol),
        "is_noop": is_noop,
        # K7: a diagnosis that stops at "your control is vacuous" leaves the caller stuck, so the
        # verdict now NAMES the non-vacuous alternatives.
        "verdict": ("CONFIRMED NO-OP -- this control tests nothing (sd=%.3e < tol=%.0e, real "
                    "reproduced). YOU STILL NEED A CONTROL THAT CAN FAIL: permute the ASSIGNMENT "
                    "of already-computed values with screenkit.permutation_null (scheme="
                    "SCHEME_WITHIN_CYCLIC if the feature is autocorrelated), or -- if the "
                    "statistic is a function of PER-ENTITY fits, where relabelling the entity key "
                    "is a bijection on whole groups and therefore always a no-op -- use "
                    "screenkit.per_entity_control, which runs the vacuous arm and a genuine arm "
                    "side by side." % (sd, tol)) if is_noop else
                   ("NOT a no-op (sd=%.3e) -- the transform does move the statistic" % sd),
    }
    if verbose:
        print("  noop_placebo: real=%.10g  sd=%.3e  max|draw-real|=%.3e  distinct=%d -> %s"
              % (real, sd, max_dev, res["n_distinct_draw_values"], res["verdict"]))
    return res


# ===========================================================================================
# PER-ENTITY CONTROL -- THE CONTROL THAT CAN ACTUALLY FAIL  (K7)
# ===========================================================================================

def _relabel_entity_transform(entity_col):
    """Build the classic VACUOUS per-entity control: relabel the entity key, change nothing else."""
    ecols = [entity_col] if isinstance(entity_col, str) else list(entity_col)

    def _transform(d, rgen):
        w = d.copy()
        for c in ecols:
            uq = pd.unique(w[c])
            perm = rgen.permutation(len(uq))
            mapping = dict(zip(uq, [uq[i] for i in perm]))
            w[c] = w[c].map(mapping)
        return w
    return _transform


def per_entity_control(stat_fn, data, entity_col, *, feature_col, n_draws, seed,
                       scheme=SCHEME_WITHIN_CYCLIC, order_col=None, n_relabel_draws=None,
                       tol=1e-15, alternative="greater", acf1_threshold=None,
                       accept_serial_structure_destroyed=False, verbose=False):
    """TWO controls for a PER-ENTITY statistic: the vacuous one, and one that CAN FAIL.  *** K7. ***

    *** THE CONTROL AN ANALYST REACHES FOR FIRST WHEN VALIDATING PER-ENTITY WORK TESTS NOTHING. ***
    "Shuffle the player labels and see whether the coefficient spread shrinks" is the natural
    control for a per-player claim, and it is a LITERAL NO-OP.  Relabelling entity ids is a
    BIJECTION ON WHOLE GROUPS: every player's row set travels intact to the new label, every
    per-player fit is refitted on exactly the same rows, and the MULTISET of coefficients -- hence
    its spread, its max, its interquartile range, any function of the multiset -- is EXACTLY
    unchanged.  The kit's eighth user measured it: observed sd 5.207e-17 over 3 distinct draw
    values, reported as CONFIRMED NO-OP.  It returned a clean bill of health while testing nothing.
    This is the same trap family this program has now caught nine times, one level down: not the
    ROW-level no-op, the ENTITY-level one.

    *** THIS FUNCTION EXISTS BECAUSE DIAGNOSING THE VACUITY IS NOT ENOUGH. ***  `noop_placebo`
    already reports the relabel arm correctly.  What was missing was the alternative, so this runs
    both and reports them side by side:

      ARM 1  RELABEL (vacuous, and PROVEN vacuous on YOUR statistic rather than argued).  Permute
             the entity key labels and recompute.  Expected result: sd ~ 0, is_noop True.  If it is
             NOT a no-op for your `stat_fn`, that is itself worth knowing -- your statistic depends
             on entity IDENTITY, not only on the per-entity fits, and you should say which.
      ARM 2  GENUINE.  Permute the FEATURE INSIDE each entity, which really does change every
             per-entity fit while leaving each entity's sample size, its marginal distribution and
             (under the default `SCHEME_WITHIN_CYCLIC`) its SERIAL structure exactly as they were.
             The reporter's own honest null has this shape.  Expected result: a null with real
             width, against which the observed statistic can genuinely fail to be extreme.
             The default is the CYCLIC shift, not the shuffle, for the K6 reason: a per-entity
             regressor in this program is usually a running mean of the entity's own history, and
             shuffling it gives a null that is too narrow.

    GUARANTEES
      * Arm 2 goes through `permutation_null`, so it inherits the K6 acf gate, the constancy
        refusal, and the add-one p.
      * `controls_are_informative` is True only if arm 1 is a confirmed no-op AND arm 2 moves the
        statistic.  Anything else is reported with a `warning` rather than a verdict.
      * Neither arm ever raises on a confirmed no-op.  A vacuous control is a RESULT.

    DOES *NOT*
      * prove the per-entity structure is real when arm 2's p is small.  Arm 2 is a null over
        WITHIN-ENTITY alignment; a per-entity claim can still be confounded at a level this does
        not touch, and `entity_swap_null` answers the different "does WHICH entity matter" question.
      * choose `order_col` for you.  Under the cyclic scheme the rows inside each entity must be in
        TIME order or the shift preserves nothing -- see `permutation_null`.

    Parameters
    ----------
    stat_fn     : callable(DataFrame) -> float -- your per-entity statistic (e.g. sd of per-entity
                  slopes).  Must recompute the per-entity fits from the frame it is handed.
    data        : pandas.DataFrame
    entity_col  : str | list[str] -- the entity key that gets relabelled in arm 1 and grouped on
                  in arm 2.
    feature_col : str (keyword-only) -- the column arm 2 permutes inside each entity.
    n_draws     : int -- draws for arm 2.
    n_relabel_draws : int | None -- draws for arm 1 (default min(n_draws, 25); the relabel arm
                  needs only enough draws to establish sd ~ 0, and each one refits everything).
    scheme      : SCHEME_WITHIN_CYCLIC (default) | SCHEME_WITHIN
    order_col, acf1_threshold, accept_serial_structure_destroyed : passed to `permutation_null`.

    Returns
    -------
    dict: relabel (noop_placebo result), genuine (permutation_null result or None),
          relabel_is_vacuous, genuine_control_moves, controls_are_informative, real,
          entity_col, feature_col, scheme, genuine_error, verdict, warning
    """
    if scheme not in (SCHEME_WITHIN, SCHEME_WITHIN_CYCLIC):
        raise ValueError("per_entity_control: scheme must be %r or %r (the between-group schemes "
                         "do not perturb a per-entity fit), got %r"
                         % (SCHEME_WITHIN_CYCLIC, SCHEME_WITHIN, scheme))
    ecols = [entity_col] if isinstance(entity_col, str) else list(entity_col)
    missing = [c for c in ecols if c not in data.columns]
    if missing:
        raise KeyError("per_entity_control: entity_col columns missing from frame: %s" % missing)
    if feature_col not in data.columns:
        raise KeyError("feature_col %r not in frame" % feature_col)

    n_rel = int(n_relabel_draws) if n_relabel_draws is not None else int(min(n_draws, 25))
    relabel = noop_placebo(stat_fn, data, n_rel,
                           transform=_relabel_entity_transform(ecols), tol=tol)

    genuine, genuine_error = None, None
    try:
        genuine = permutation_null(stat_fn, data, ecols, n_draws, seed,
                                   feature_col=feature_col, alternative=alternative,
                                   scheme=scheme, order_col=order_col,
                                   acf1_threshold=acf1_threshold,
                                   accept_serial_structure_destroyed=(
                                       accept_serial_structure_destroyed))
    except (ValueError, TypeError, KeyError) as exc:                    # noqa: BLE001
        genuine_error = "%s: %s" % (type(exc).__name__, exc)

    moves = bool(genuine is not None and np.isfinite(genuine["sd"]) and genuine["sd"] > tol)
    informative = bool(relabel["is_noop"] and moves)

    warn = None
    if not relabel["is_noop"]:
        warn = ("THE RELABEL ARM IS NOT A NO-OP (sd = %.3e). For a statistic that is a function of "
                "the per-entity FITS this arm must be exactly vacuous, so your stat_fn depends on "
                "entity IDENTITY as well -- through a merge, a sort, a lookup or a fixed effect. "
                "Say which in FINDINGS.json before reading arm 2." % relabel["sd"])
    elif genuine is None:
        warn = ("THE GENUINE ARM COULD NOT RUN (%s), so you currently have NO control that can "
                "fail. Do not report the relabel arm on its own -- it is vacuous by construction."
                % genuine_error)
    elif not moves:
        warn = ("THE GENUINE ARM DID NOT MOVE THE STATISTIC EITHER (sd = %.3e). Both controls are "
                "vacuous, so nothing here tests anything. Check that stat_fn really refits from "
                "the frame it is handed rather than closing over precomputed per-entity values."
                % genuine["sd"])

    res = {
        "entity_col": ecols,
        "feature_col": feature_col,
        "scheme": scheme,
        "real": relabel["real"],
        "relabel": relabel,
        "genuine": genuine,
        "genuine_error": genuine_error,
        "relabel_is_vacuous": bool(relabel["is_noop"]),
        "genuine_control_moves": moves,
        "controls_are_informative": informative,
        "warning": warn,
        "verdict": (
            "RELABEL ARM: CONFIRMED VACUOUS (sd = %.3e over %d draws, %d distinct values) -- "
            "relabelling %s is a bijection on whole groups and tests NOTHING. GENUINE ARM "
            "(%s inside %s): sd = %.6g, p = %.4f over %d draws -- THIS control can fail, and this "
            "is the one to report."
            % (relabel["sd"], n_rel, relabel["n_distinct_draw_values"], ecols, feature_col, ecols,
               genuine["sd"], genuine["p"], genuine["n_draws"]) if informative else
            "CONTROLS ARE NOT BOTH INFORMATIVE -- read `warning` before reporting anything."),
    }
    if verbose:
        print("  per_entity_control(%s, feature=%s, scheme=%s): real = %.10g"
              % (ecols, feature_col, scheme, res["real"]))
        print("    ARM 1 RELABEL  %-28s sd = %.3e  distinct = %d  -> %s"
              % ("(the vacuous one)", relabel["sd"], relabel["n_distinct_draw_values"],
                 "CONFIRMED NO-OP" if relabel["is_noop"] else "NOT a no-op"))
        if genuine is not None:
            _a = genuine["acf1_within_group"]
            print("    ARM 2 GENUINE  %-28s sd = %.6g   p = %.4f  acf1 = %s"
                  % ("(%s)" % scheme, genuine["sd"], genuine["p"],
                     ("%+.4f" % _a) if _a is not None else "n/a"))
        else:
            print("    ARM 2 GENUINE  COULD NOT RUN: %s" % genuine_error)
        print("    -> %s" % res["verdict"])
        if warn:
            print("    !! %s" % warn)
    return res


# ===========================================================================================
# PARTITION CHECK  (trap 3)
# ===========================================================================================

_SEASONISH_TOKENS = ("season", "year")
_DATEISH_TOKENS = ("date",)

#: Years a PARSED STRING must fall inside before the kit will believe the column holds dates.
#: 1970 (the epoch, i.e. what a float column parses to) is deliberately OUTSIDE this window.
_PLAUSIBLE_DATE_YEARS = (1990, 2100)

#: Fraction of non-null values in a string column that must parse as dates before the column is
#: treated as a date column.  A candidate-name column of feature ids parses at 0.0.
_DATE_PARSE_MIN_RATE = 0.8


def _parse_datetimes(s):
    """`pd.to_datetime(s, errors='coerce')` WITHOUT the "Could not infer format" UserWarning.

    Reported by the kit's second user: the kit emitted that warning on every `assert_partition`
    call that saw an object column, because a column of feature ids parses as nothing.  Passing
    `format="mixed"` asks for exactly the per-element parsing the warning was recommending against
    guessing, so the warning is no longer appropriate -- and `format="mixed"` is strictly MORE
    capable than the default here (`07/04/2022` parses; under the default it became NaT).

    The `warnings` filter is belt and braces for a pandas that does not accept `format="mixed"`.
    """
    try:
        return pd.to_datetime(s, errors="coerce", format="mixed")
    except (TypeError, ValueError):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Could not infer format",
                                    category=UserWarning)
            return pd.to_datetime(s, errors="coerce")


def _is_date_valued(s):
    """A column is date-VALUED only if its VALUES are dates.  *** THIS IS THE K0 FIX. ***

    THE ASYMMETRY THIS CLOSES.  `_is_season_valued` below was added because a name is not a value:
    columns NAMED `<rung>_team_season` hold dR2 draws near 1e-4, and flagging them is the
    name/text false positive this program has now been burned by FOUR times.  The DATE branch never
    got the same guard.  It matched `"date" in name.lower()`, *** AND THE WORD "candi-DATE"
    CONTAINS "date" ***, so `candidate`, `n_candidates` and `mae_with_candidate` -- the single most
    common column names in this program's exploration screens -- were all parsed as dates.

    WHY THAT WAS NOT MERELY COSMETIC.  `pd.to_datetime` on a FLOAT column DOES NOT RAISE.  It reads
    the floats as NANOSECONDS SINCE THE EPOCH and returns 1970-01-01.  Year 1970 is outside every
    real partition, so `assert_partition` raised `PartitionViolation` on a frame whose every value
    was inside 2021-2024.  A guard that cries wolf on the program's most common column name trains
    callers to switch it off -- and the natural way to switch it off, `date_cols=[]`, is a
    FALSE-PASS door.

    THE RULE, in the order it is applied:
      1. datetime64 dtype (tz-aware included) -> ACCEPT OUTRIGHT.  The dtype IS the proof; no year
         range is imposed, so a genuine 2026 column is still checked and still flagged.
      2. NUMERIC dtype (int, float, bool) -> REFUSE OUTRIGHT.  *** THE EPOCH-NANOSECOND READING IS
         NEVER USED. ***  There is no threshold, no heuristic and no rescue here: a float is not a
         date, and inferring a year from one is precisely how the false positive was manufactured.
      3. anything else (string/object) -> parse it, and require BOTH a parse-success rate of at
         least `_DATE_PARSE_MIN_RATE` over the non-null values AND every parsed year inside
         `_PLAUSIBLE_DATE_YEARS` = (1990, 2100).  The year window is a second, independent line of
         defence: even if some future dtype slipped an epoch reading past rule 2, 1970 is outside
         it.  The window is deliberately WIDER than any partition, so it can never mask a real
         violation -- 2025 and 2026 are inside it and remain checkable.

    Returns (is_date_valued, years:set[int], reason:str).  `reason` is empty when accepted.
    """
    if pd.api.types.is_datetime64_any_dtype(s):
        d = pd.to_datetime(s, errors="coerce")
        yrs = set(int(y) for y in d.dt.year.dropna().unique())
        if not yrs:
            return False, set(), "dtype is datetime64 but every value is NaT -> nothing to check"
        return True, yrs, ""

    if pd.api.types.is_numeric_dtype(s):
        num = pd.to_numeric(s, errors="coerce")
        return False, set(), (
            "name is date-like but VALUES are NUMERIC (dtype %s, range %s..%s) -> NOT a date "
            "column, skipped. pd.to_datetime would read these as epoch NANOSECONDS and return "
            "1970, which is a FALSE partition violation, so the kit refuses that reading. If this "
            "really is an epoch column, convert it yourself with pd.to_datetime(col, unit=...) "
            "before calling -- the kit will not guess an encoding for you."
            % (s.dtype, num.min(), num.max()))

    nn = s.notna()
    n_nonnull = int(nn.sum())
    if n_nonnull == 0:
        return False, set(), "name is date-like but the column is entirely null -> skipped"
    d = _parse_datetimes(s)
    n_parsed = int(d.notna().sum())
    rate = n_parsed / float(n_nonnull)
    if rate < _DATE_PARSE_MIN_RATE:
        return False, set(), (
            "name is date-like but VALUES are not dates (only %d of %d non-null values parsed, "
            "%.0f%% < %.0f%%) -> NOT a date column, skipped"
            % (n_parsed, n_nonnull, 100 * rate, 100 * _DATE_PARSE_MIN_RATE))
    yrs = set(int(y) for y in d.dt.year.dropna().unique())
    lo, hi = _PLAUSIBLE_DATE_YEARS
    if not yrs or min(yrs) < lo or max(yrs) > hi:
        return False, set(), (
            "name is date-like and the values parse, but the resulting YEARS %s fall outside the "
            "plausible window %d-%d -> these are not dates, skipped" % (sorted(yrs), lo, hi))
    return True, yrs, ""


def _is_season_valued(s):
    """A column is season-VALUED only if its values are whole numbers in a plausible season range.

    Adapted verbatim in spirit from E1_I0013_tempo_redundancy/verify_partition.py ::
    looks_like_a_season_column.  NAME ALONE IS NOT ENOUGH: permutation-draw files in this program
    carry columns named `<rung>_team_season` whose values are dR2 draws near 1e-4, and flagging
    those is exactly the name/text false positive this program has been burned by three times.
    """
    v = pd.to_numeric(s, errors="coerce").dropna()
    if not len(v):
        return False, set()
    if not bool((v % 1 == 0).all()):
        return False, set()
    vs = set(int(x) for x in v.unique())
    return (min(vs) >= 1990 and max(vs) <= 2100), vs


def _classify_direction(bad_values, allowed_set):
    """Split out-of-partition VALUES by DIRECTION.  *** THE K4 FIX. ***

    The guard exists to stop the HOLDOUT -- 2025 and 2026, the FUTURE -- from entering exploration
    work.  `draft_year = 2008` is not a holdout leak and cannot become one: it is fourteen years in
    the PAST.  Pre-fix the module treated "outside `allowed`" as one undifferentiated category, so
    a harmless 2008 and a genuine 2026 produced violation strings of the SAME SHAPE and a caller
    could not tell them apart without re-parsing the guard's own prose -- which is the textual
    check this whole module exists to forbid.

    Returns (direction, future, interior, past) with the three value lists.  `direction` is the
    most serious present: FUTURE > INTERIOR > PAST.
    """
    lo, hi = min(allowed_set), max(allowed_set)
    future = sorted(v for v in bad_values if v > hi)
    past = sorted(v for v in bad_values if v < lo)
    interior = sorted(v for v in bad_values if lo <= v <= hi)
    if future:
        direction = DIRECTION_FUTURE
    elif interior:
        direction = DIRECTION_INTERIOR
    else:
        direction = DIRECTION_PAST
    return direction, future, interior, past


def assert_partition(df, date_cols=None, season_cols=None, allowed=EXPLORATION_SEASONS,
                     raise_on_violation=True, verbose=False, *,
                     include_datetime_dtype_cols=True,
                     include_name_matched_season_cols=True):
    """VALUE-BASED verification that a frame lies inside the exploration partition (2021-2024).

    *** A TEXTUAL / REGEX / BYTE SCAN IS THE WRONG CHECK. ***
    Scanning file bytes or column NAMES for "2025" has failed three times in this program:
      * one verifier returned 14 hits that were ALL PROSE about the partition rule -- including its
        own log re-scanning its own context lines;
      * another returned 18 false hits from columns NAMED `_team_season` that actually held dR2
        permutation draws.
    A name is not a value.  This function therefore parses COLUMN VALUES: season columns must hold
    whole numbers in a plausible season range and those numbers must be inside `allowed`; date
    columns must be DATE-VALUED (see `_is_date_valued`) and then have their YEAR VALUES checked.

    *** THE FOURTH INSTANCE OF THAT SAME FALSE HIT WAS INSIDE THIS FUNCTION (K0). ***
    The date branch used to match `"date" in name.lower()` with NO value guard, and the word
    "candi-DATE" contains "date", so `candidate`, `n_candidates` and `mae_with_candidate` were
    parsed as dates; `pd.to_datetime` reads a float column as epoch nanoseconds and returns 1970;
    1970 is outside every partition; so THIS FUNCTION RAISED ON CLEAN 2021-2024 DATA.  The season
    branch had been hardened against exactly this and the date branch had not.  `_is_date_valued`
    is now the missing half of that symmetry.

    *** IT RAISED ON CLEAN DATA AGAIN (K4), AND NOT FOR THE K0 REASON. ***
    A frame whose every observation sits in 2021-2024 was REJECTED if it carried a year-valued
    PLAYER ATTRIBUTE -- `draft_year` (2002-2020), `birth_year`, `grad_year`, `founded`.  K4
    SATISFIES the K0 invariant and fails anyway: the token "year" NOMINATES the column, the value
    gate is asked "are these values years?", answers YES *correctly*, and the column is checked
    against a partition it legitimately PREDATES.

        the gate asked          "are these values plausible YEARS?"
        the partition needs     "is this column the ROW'S OBSERVATION SEASON?"

    Every year-valued attribute of a person or an organisation answers YES to the first and NO to
    the second, so no sharper value test can separate them -- but DIRECTION can, and direction is
    what the guard is actually for.  See `_classify_direction`.  An AUTO-DETECTED column whose
    out-of-partition values are ALL in the PAST is recorded in `historical_year_cols` and is NOT
    fatal; FUTURE and INTERIOR values stay fatal everywhere; and a column the caller NAMES in
    `season_cols` is STRICT IN BOTH DIRECTIONS, because naming it asserts that it IS an observation
    season and that assertion is honoured loudly (the same asymmetry B2 established for date_cols).

    AND THE OBVIOUS WORKAROUND WAS AGAIN WORSE THAN THE BUG (B4).  Pre-fix, `season_cols=["season"]`
    silenced the `draft_year` false alarm AND SILENCED A GENUINE 2026 LEAK in `source_season`, a
    column the caller never named.  `season_cols` is now ADDITIVE, exactly as `date_cols` is: it
    adds columns and marks them strict; it never disables auto-detection.

    THE ONE PLACE DIRECTION ALONE WOULD HAVE OPENED A NEW FALSE-PASS DOOR, AND WHAT CLOSES IT.
    "PAST is not fatal" taken literally would wave through a frame whose `season` column genuinely
    holds 2019 OBSERVATION rows -- a real out-of-partition frame, quietly passed.  A purely-PAST
    verdict is therefore non-fatal ONLY WHEN THE FRAME CARRIES AN ANCHOR: some season or date
    column every one of whose values is INSIDE the partition.  With an anchor, the frame's
    observation window is demonstrably in-partition and an earlier column is an ATTRIBUTE.  Without
    one, nothing establishes that the frame is in-partition at all, and every out-of-partition
    value stays FATAL in every direction.  `in_partition_anchor_cols` reports which columns
    anchored the frame, or is empty.

    GUARANTEES
      * Never inspects file text, source code, prose, or logs.  Only column values.
      * A column whose NAME looks season-like but whose VALUES are not season-valued (e.g. dR2
        draws in a column named `_team_season_2025`) is SKIPPED, recorded under
        `skipped_name_only`, and can never cause a failure.
      * SYMMETRICALLY (K0): a column whose NAME looks date-like but whose VALUES are not dates
        (e.g. MAE floats in a column named `mae_with_candidate`) is SKIPPED the same way, with the
        same wording, and can never cause a failure.  A NUMERIC column is never read as epoch time.
      * Every datetime64-dtype column is checked whether or not it is named in `date_cols`, so the
        date check CANNOT be switched off by accident.  (B2 -- see the module header.)
      * SYMMETRICALLY (K4/B4): every name-matched SEASON column is value-tested whether or not
        `season_cols` is given, so the season check cannot be switched off by accident either.
      * Additionally sweeps every numeric column for all-whole-number values inside [2020, 2030]
        that fall outside the partition -- catching a year-valued column with an innocuous name.
      * Every violation is ALSO returned as a STRUCTURED RECORD in `violation_records`
        ({col, kind, direction, values, fatal, source}), so a caller can adjudicate by DIRECTION
        without parsing the guard's prose.  `violations` (the strings) is unchanged in shape.
      * A FUTURE value (> max(allowed)) is FATAL in every column, always, however it was detected.
      * Emits NO warnings.  Parsing goes through `_parse_datetimes`, which does not trip pandas'
        "Could not infer format" UserWarning.
      * Raises `PartitionViolation` on any FATAL violation when `raise_on_violation=True`.

    DOES *NOT*
      * decide whether a `historical_year_cols` entry is legitimate.  It records that a column
        holds years EARLIER than the partition, which cannot be a holdout leak but can still be an
        upstream join you did not intend.  Read the field; that is what it is for.
      * verify PROVENANCE.  A 2021-2024 frame can still be contaminated by an upstream artifact
        that was FIT through 2026.  That is `check_manifest`'s job, and filtering does not fix it.
      * detect leakage from the future WITHIN the partition (a 2024 row reading later 2024 games).
        That is `future_leakage_probe`'s job.
      * check anything about files on disk.  Pass the loaded frame.
      * accept dates stored as epoch integers/floats.  Convert them yourself with
        `pd.to_datetime(col, unit=...)`; the kit will not guess an encoding.

    Parameters
    ----------
    df : pandas.DataFrame
    date_cols   : list[str] | None -- None auto-detects columns with "date" in the name.  When
                  given, it is ADDITIVE, not exhaustive (B2): datetime64 columns are still checked
                  unless `include_datetime_dtype_cols=False`.  A column named here whose values are
                  NOT dates raises ValueError rather than being silently skipped.
    season_cols : list[str] | None -- columns the caller ASSERTS are observation seasons.  ADDITIVE,
                  not exhaustive (B4): name-matched columns are value-tested as well.  A column
                  named here is STRICT IN BOTH DIRECTIONS -- a PAST value in it is fatal.
    allowed     : iterable[int]
    raise_on_violation : bool
    verbose     : bool
    include_datetime_dtype_cols : bool (keyword-only, default True) -- check every datetime64-dtype
                  column regardless of name and regardless of `date_cols`.  Setting this False
                  restores the pre-K0 behaviour in which `date_cols=[]` disabled the date check
                  entirely; that is a false-pass door, so declare it in FINDINGS.json if you use it.
    include_name_matched_season_cols : bool (keyword-only, default True) -- value-test every
                  name-matched season column regardless of `season_cols`.  Setting this False
                  restores the pre-K4 behaviour in which `season_cols=[...]` disabled auto-
                  detection; that is the false-pass door B4 closes, so declare it if you use it.

    Returns
    -------
    dict: ok, allowed, checked_season_cols, checked_date_cols, skipped_name_only,
          historical_year_cols, strict_season_cols, in_partition_anchor_cols, violation_records,
          violations
    """
    allowed_set = set(int(a) for a in allowed)
    rep = {
        "ok": True,
        "allowed": sorted(allowed_set),
        "checked_season_cols": {},
        "checked_date_cols": {},
        "skipped_name_only": {},
        #: K4: auto-detected year-valued columns whose out-of-partition values are ALL EARLIER than
        #: the partition.  Recorded and visible; NOT fatal.  A `draft_year` of 2008 lands here.
        "historical_year_cols": {},
        #: columns the caller NAMED in `season_cols`: strict in both directions.
        "strict_season_cols": [],
        #: K4: columns every one of whose values is INSIDE the partition.  Their existence is what
        #: licenses reading a purely-earlier column as an attribute rather than as an out-of-
        #: partition frame.  Empty => nothing is waved through in any direction.
        "in_partition_anchor_cols": [],
        #: K4: structured violations, so direction can be read without parsing prose.
        "violation_records": [],
        "violations": [],
    }

    def _record(col, kind, direction, values, fatal, source):
        rep["violation_records"].append({
            "col": str(col), "kind": kind, "direction": direction,
            "values": sorted(values), "fatal": bool(fatal), "source": source,
        })

    # ---- season candidates (B4: `season_cols` is ADDITIVE, never a replacement) ---------------
    explicit_season = [] if season_cols is None else [c for c in season_cols]
    rep["strict_season_cols"] = [str(c) for c in explicit_season]
    if include_name_matched_season_cols:
        name_matched_season = [c for c in df.columns
                               if any(t in str(c).lower() for t in _SEASONISH_TOKENS)]
    else:
        name_matched_season = []
    cand_season = list(explicit_season) + [c for c in name_matched_season
                                           if c not in explicit_season]

    # ---- date candidates -------------------------------------------------------------------
    # `explicit` are columns the CALLER named: a failure to honour those must be LOUD (B2).
    # Name-matched and dtype-matched columns are advisory: a name-only match is skipped quietly and
    # recorded, exactly as the season branch does.
    if date_cols is None:
        explicit_date = []
        cand_date = [c for c in df.columns
                     if any(t in str(c).lower() for t in _DATEISH_TOKENS)]
    else:
        explicit_date = [c for c in date_cols]
        cand_date = list(explicit_date)
    if include_datetime_dtype_cols:
        cand_date += [c for c in df.columns
                      if c not in cand_date and pd.api.types.is_datetime64_any_dtype(df[c])]

    # ---- PASS A: value-test every candidate; DEFER the fatality decision -----------------------
    # Fatality needs one fact the per-column loop does not have: whether ANY column establishes an
    # observation window INSIDE the partition.  See `_anchor` below.
    pending = []                      # (col, kind, strict, values, bad)
    for c in cand_season:
        if c not in df.columns:
            if c in explicit_season:
                raise KeyError("assert_partition: season_cols names %r, which is not in the frame "
                               "(columns: %s)" % (c, list(df.columns)))
            continue
        if str(c) in rep["checked_season_cols"]:
            continue
        strict = c in explicit_season
        is_season, vs = _is_season_valued(df[c])
        if not is_season:
            num = pd.to_numeric(df[c], errors="coerce")
            why = ("name is season-like but VALUES are not seasons (range %s..%s) -> NOT a season "
                   "column, skipped" % (num.min(), num.max()))
            if strict:
                # An explicit assertion that cannot be honoured must be LOUD, never a silent
                # no-check -- the same rule B2 established for `date_cols` (K0).
                raise ValueError(
                    "assert_partition: season_cols explicitly names %r, but %s Convert the column "
                    "yourself, or drop it from season_cols; the kit refuses to invent a season "
                    "from values that are not seasons." % (c, why))
            rep["skipped_name_only"][str(c)] = why
            continue
        rep["checked_season_cols"][str(c)] = sorted(vs)
        bad = sorted(vs - allowed_set)
        if bad:
            pending.append((c, "season_column", strict, vs, bad))

    for c in cand_date:
        if c not in df.columns:
            if c in explicit_date:
                raise KeyError("assert_partition: date_cols names %r, which is not in the frame "
                               "(columns: %s)" % (c, list(df.columns)))
            continue
        # *** K0: the value gate the date branch never had.  Mirrors _is_season_valued. ***
        is_date, yrs, why = _is_date_valued(df[c])
        if not is_date:
            if c in explicit_date:
                # The caller ASKED for this column to be checked as a date and it cannot be. Being
                # silent here would turn an explicit request into a silent no-check -- the exact
                # false-pass shape B2 exists to close.  Fail loudly instead.
                raise ValueError(
                    "assert_partition: date_cols explicitly names %r, but %s Convert the column "
                    "yourself (e.g. pd.to_datetime(df[%r], unit='ns')) and pass the converted "
                    "frame; the kit refuses to invent a date from values that are not dates."
                    % (c, why, c))
            rep["skipped_name_only"][str(c)] = why
            continue
        rep["checked_date_cols"][str(c)] = sorted(yrs)
        bad = sorted(yrs - allowed_set)
        if bad:
            pending.append((c, "date_column", c in explicit_date, yrs, bad))

    # ---- the numeric catch-all sweep (VALUE-based, deliberately kept -- see the module header) --
    handled = (set(rep["checked_season_cols"]) | set(rep["checked_date_cols"])
               | set(rep["skipped_name_only"]))
    for c in df.columns:
        if str(c) in handled:
            continue
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if not len(s):
            continue
        if bool(s.between(2020, 2030).all()) and bool((s % 1 == 0).all()):
            vs = set(int(x) for x in s.unique())
            bad = sorted(vs - allowed_set)
            if bad:
                pending.append((c, "numeric_sweep", False, vs, bad))

    # ---- PASS B: DIRECTION DECIDES.  *** THIS IS THE K4 FIX. *** -------------------------------
    # An ANCHOR is a column that establishes an observation window INSIDE the partition: a season or
    # date column every one of whose values is in `allowed`.  Its existence is what licenses reading
    # a purely-EARLIER column as a year-valued ATTRIBUTE (draft_year, birth_year, founded) rather
    # than as evidence that the frame itself sits before the partition.
    #   * NO ANCHOR -> nothing here shows the frame is in-partition, so EVERY out-of-partition value
    #     stays FATAL in every direction.  A frame whose `season` column really does hold 2019 rows
    #     is therefore still rejected: 2019 is not waved through just for being in the past.
    #   * ANCHOR + purely PAST + AUTO-DETECTED -> recorded in `historical_year_cols`, NOT fatal.
    #   * FUTURE or INTERIOR -> FATAL, always, everywhere.  That is the holdout direction.
    #   * NAMED in season_cols / date_cols -> STRICT IN BOTH DIRECTIONS.  Naming a column asserts it
    #     is the row's observation season, and an explicit assertion is honoured loudly.
    anchor_cols = ([c for c, v in rep["checked_season_cols"].items() if set(v) <= allowed_set]
                   + [c for c, v in rep["checked_date_cols"].items() if set(v) <= allowed_set])
    has_anchor = bool(anchor_cols)
    rep["in_partition_anchor_cols"] = sorted(anchor_cols)

    for c, kind, strict, _vs, bad in pending:
        direction, future, interior, past = _classify_direction(bad, allowed_set)
        if direction == DIRECTION_PAST and not strict and has_anchor:
            rep["historical_year_cols"][str(c)] = {
                "values_before_partition": past,
                "kind": kind,
                "why": ("auto-detected year-valued column whose out-of-partition VALUES are ALL "
                        "EARLIER than the partition %d-%d, in a frame whose observation window IS "
                        "inside the partition (anchor columns: %s). It CANNOT be a holdout leak. "
                        "This is the `draft_year` / `birth_year` / `founded` shape (K4). Recorded, "
                        "NOT fatal, and NOT a certificate that the join was intended. If this "
                        "column really IS the row's observation season, name it in season_cols and "
                        "it becomes strict in both directions."
                        % (min(allowed_set), max(allowed_set), sorted(anchor_cols))),
            }
            _record(c, kind, direction, bad, False, "historical attribute (K4)")
            continue
        why_fatal = ("named by the caller, therefore strict in both directions" if strict else
                     ("no column establishes an in-partition observation window, so a PAST value "
                      "is not adjudicable as an attribute" if direction == DIRECTION_PAST
                      else "%s values are the direction this guard exists to stop" % direction))
        _record(c, kind, direction, bad, True, why_fatal)
        label = {"season_column": "season column %r has out-of-partition VALUES %s",
                 "date_column": "date column %r has out-of-partition YEAR VALUES %s",
                 "numeric_sweep": "column %r holds year-like VALUES outside the partition: %s"}[kind]
        rep["violations"].append((label % (c, bad)) + " [direction=%s; %s]" % (direction, why_fatal))

    rep["violations"] = sorted(set(rep["violations"]))
    rep["ok"] = not rep["violations"]

    if verbose:
        print("  assert_partition: allowed=%s" % rep["allowed"])
        for c, v in rep["checked_season_cols"].items():
            print("    season col %-24s VALUES = %s" % (c, v))
        for c, v in rep["checked_date_cols"].items():
            print("    date   col %-24s YEARS  = %s" % (c, v))
        for c, why in rep["skipped_name_only"].items():
            print("    skipped    %-24s %s" % (c, why))
        for c, d in rep["historical_year_cols"].items():
            print("    HISTORICAL %-24s values BEFORE the partition = %s  (recorded, not fatal)"
                  % (c, d["values_before_partition"]))
        print("    in-partition anchor columns: %s" % (rep["in_partition_anchor_cols"] or "NONE"))
        print("    -> %s" % ("PASS" if rep["ok"] else "VIOLATIONS: %s" % rep["violations"]))

    if rep["violations"] and raise_on_violation:
        raise PartitionViolation("; ".join(rep["violations"]))
    return rep


# ===========================================================================================
# MANIFEST CHECK  (GRAPH_POLICY 13.2.2)
# ===========================================================================================

def check_manifest(artifact_path, verbose=False):
    """Read `<artifact>.manifest.json` and return the artifact's as-of granularity and usability.

    Field names and the pass test follow E1_I0008_height_mismatch/build_frame.py, which read the
    manifest from bytes in-session rather than citing it.

    THE RULE
      asof_granularity == "row"       -> USABLE_IF_FILTERED.  Each row's value is as-of that row's
                                         own date, so filtering to 2021-2024 is sufficient.
      asof_granularity == "artifact"  -> UNUSABLE at E0/E1.  FILTERING DOES NOT HELP.  The whole
                                         file is bounded by its LATEST input, so a 2021 row's value
                                         may embed 2026 data.  You cannot subset your way out of it.
      manifest missing                -> UNVERIFIABLE.  Explicitly NOT a pass.  Two input parquets
                                         were recently found with no sibling manifest at all, and
                                         45 market-named files carry none.
      manifest present, field missing
        or an unrecognised value      -> UNVERIFIABLE.

    GUARANTEES
      * A missing manifest returns status "UNVERIFIABLE" and `usable_at_e0_e1` is False.  It never
        silently passes and never raises -- the caller must record the UNVERIFIABLE status.
      * The manifest is read from disk at call time, not cached and not cited from a NOTES file.

    DOES *NOT*
      * validate the manifest's honesty (no content hash is recomputed here), infer granularity
        from the data, or make an "artifact"-granular file usable by any filtering.

    Returns
    -------
    dict: artifact, manifest_path, manifest_present, asof_granularity, status,
          usable_at_e0_e1, filtering_helps, fit_seasons, fit_through_season, content_sha256, note
    """
    manifest_path = str(artifact_path) + ".manifest.json"
    res = {
        "artifact": str(artifact_path),
        "manifest_path": manifest_path,
        "manifest_present": False,
        "asof_granularity": None,
        "status": "UNVERIFIABLE",
        "usable_at_e0_e1": False,
        "filtering_helps": None,
        "fit_seasons": None,
        "fit_through_season": None,
        "content_sha256": None,
        "note": "",
    }

    if not os.path.exists(manifest_path):
        res["note"] = ("NO SIBLING MANIFEST. Status is UNVERIFIABLE, which is NOT a pass. Two input "
                       "parquets and 45 market-named files in this repo carry none. Record this "
                       "status in FINDINGS.json; do not treat the artifact as clean.")
        if verbose:
            print("  check_manifest %s -> UNVERIFIABLE (no manifest)" % os.path.basename(str(artifact_path)))
        return res

    res["manifest_present"] = True
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            man = json.load(fh)
    except (OSError, ValueError) as exc:
        res["note"] = "manifest present but unreadable/unparseable: %s" % exc
        return res

    gran = man.get("asof_granularity")
    res["asof_granularity"] = gran
    res["fit_seasons"] = man.get("fit_seasons")
    res["fit_through_season"] = man.get("fit_through_season")
    res["content_sha256"] = man.get("content_sha256")

    if gran == "row":
        res["status"] = "USABLE_IF_FILTERED"
        res["usable_at_e0_e1"] = True
        res["filtering_helps"] = True
        res["note"] = ("row-granular: each row's value is as-of that row's own date. Filter to "
                       "2021-2024 on COLUMN VALUES and re-assert with assert_partition.")
    elif gran == "artifact":
        res["status"] = "UNUSABLE"
        res["usable_at_e0_e1"] = False
        res["filtering_helps"] = False
        res["note"] = ("artifact-granular: the WHOLE FILE is bounded by its latest input, so a 2021 "
                       "row's value may embed 2026 data. FILTERING DOES NOT HELP. Do not use at "
                       "E0/E1.")
    else:
        res["note"] = ("manifest present but asof_granularity is %r (expected 'row' or 'artifact'). "
                       "UNVERIFIABLE -- not a pass." % gran)

    if verbose:
        print("  check_manifest %-40s granularity=%-10r -> %s"
              % (os.path.basename(str(artifact_path)), gran, res["status"]))
    return res


# ===========================================================================================
# FUTURE-LEAKAGE PROBE  (trap 2)
# ===========================================================================================

def future_leakage_probe(df, baseline_col, clean_col, entity_col, date_col, outcome_col,
                         weight_col=None, verbose=False):
    """Cheap empirical probe: does a baseline predict the entity's OWN UNPLAYED FUTURE?

    *** THIS IS A SCREENING FLAG, NOT A VERDICT.  READ THE NEXT PARAGRAPH BEFORE ACTING ON IT. ***

    WHAT A FLAG DOES AND DOES NOT LICENSE  (K1, fixed 2026-08-08)
      This function used to conclude, in its own `verdict` string, "That is only possible because it
      CONTAINS the future."  *** THAT IS FALSE IN GENERAL, AND IT WAS FIXED BECAUSE IT MISLED A
      REAL CALLER. ***  The probe fired on `refB_ppm` versus `refA_ppm` -- BOTH STRICTLY
      PRIOR-GAMES-ONLY, differing only as ESTIMATORS of the same persistent quantity.  A better
      (less noisy) estimator of a quantity that persists over time correlates MORE with the
      entity's future WITHOUT reading a single future row.  A caller who trusted the old wording
      would have discarded a clean baseline.

      A flag therefore means exactly this and no more:

        the suspect tracks the entity's own unplayed future MORE CLOSELY than the contrast does,
        which is CONSISTENT WITH (a) the suspect containing future information, and EQUALLY
        CONSISTENT WITH (b) the suspect simply being a better estimator of a persistent quantity.

      THIS PROBE CANNOT DISTINGUISH (a) FROM (b), and no amount of extra correlation can.  Treat a
      flag as a REQUEST FOR AN AUDIT of the construction -- what time window does every input read?
      -- not as a finding of leakage.  The numbers it reports are unchanged and remain worth
      reading; only the claim attached to them was wrong.

    Adapted from E1_I0009_r2_rerun/step5_baseline_audit_and_gate.py section (a) -- the probe that
    caught the fourth retrospective-baseline instance.  It measured
    corr(player_tendency_loo, the player's own strictly-after-date future rate) = +0.6455 versus
    +0.3647 for a legitimately pregame baseline, and a dR2 of the suspect over the clean one IN
    PREDICTING THAT FUTURE of 0.3319.  In THAT case the audit confirmed leakage -- the construction
    was a full-season leave-one-out.  The confirmation came from reading the construction, not from
    the correlation gap.

    WHY YOU CANNOT SKIP THIS: names lie systematically.  "leave-one-out", "expected", "pregame",
    "prior" and "baseline" have ALL appeared in this program on quantities that read the future.
    Read the construction AND run this probe.

    THE CONSTRUCTION
      Rows are sorted within `entity_col` by `date_col`.  For each row, the entity's FUTURE outcome
      is the entity total minus the cumulative total through that row -- i.e. strictly the rows that
      come AFTER it in that ordering.  With `weight_col`, the future rate is
      sum(w*outcome)/sum(w) over those rows; without it, the plain mean.

    GUARANTEES
      * The future quantity uses only rows strictly after the current one in the sorted order, so
        no row can predict itself.
      * The two correlations are computed on the SAME row set (rows that have a nonempty future).
      * `dr2_suspect_over_clean_predicting_future` uses `delta_r2_plain`, i.e. the adopted D069
        convention, with the FUTURE as the target.

    DOES *NOT*
      * prove that a FLAGGED baseline reads the future.  A strictly prior-games-only estimator that
        is merely BETTER than the contrast flags too, and that is not a defect in the estimator.
        See the screening-flag paragraph above; this is the K1 fix.
      * prove cleanliness when the numbers come out similar.  A baseline can read the future without
        being more correlated with it than a pregame one (e.g. it reads a different season).  This
        probe is a cheap POSITIVE detector, not a certificate.  Read the construction as well.
      * handle same-date ties precisely: rows sharing an entity and a date are ordered by their
        position after a stable sort, so an exact tie is treated as "before". This matches the
        frozen implementation it was adapted from.
      * distinguish leakage in the PREDICTOR from leakage in the BASELINE. Run it on every
        constructed column you intend to publish an increment over.

    Parameters
    ----------
    df          : pandas.DataFrame
    baseline_col: str -- the SUSPECT baseline
    clean_col   : str -- a baseline believed to be strictly pregame, for contrast
    entity_col  : str | list[str] -- e.g. "player_id" or ["player_id", "season"]
    date_col    : str
    outcome_col : str
    weight_col  : str | None
    verbose     : bool

    Returns
    -------
    dict: n_rows_with_future, corr_suspect_with_future, corr_clean_with_future,
          dr2_suspect_over_clean_predicting_future, screening_flag, status,
          alternative_explanation, reads_future (LEGACY -- its NAME overstates what the value
          means; read `status`), verdict
    """
    ent = [entity_col] if isinstance(entity_col, str) else list(entity_col)
    needed = ent + [date_col, outcome_col, baseline_col, clean_col] + \
        ([weight_col] if weight_col else [])
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise KeyError("future_leakage_probe: missing columns %s" % missing)

    d = df.copy()
    d["_orig_pos"] = np.arange(len(d))
    d = d.sort_values(ent + [date_col], kind="stable")
    g = d.groupby(ent, sort=False)

    out = pd.to_numeric(d[outcome_col], errors="coerce").astype(float)
    if weight_col is None:
        w = pd.Series(np.ones(len(d)), index=d.index)
    else:
        w = pd.to_numeric(d[weight_col], errors="coerce").astype(float)
    num = out * w

    tot_n = num.groupby(g.ngroup(), sort=False).transform("sum")
    tot_w = w.groupby(g.ngroup(), sort=False).transform("sum")
    cum_n = num.groupby(g.ngroup(), sort=False).cumsum()
    cum_w = w.groupby(g.ngroup(), sort=False).cumsum()

    fut_n = (tot_n - cum_n).to_numpy(float)
    fut_w = (tot_w - cum_w).to_numpy(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        future = np.where(fut_w > 0, fut_n / fut_w, np.nan)

    d["_future"] = future
    d = d.sort_values("_orig_pos", kind="stable")

    sus = pd.to_numeric(d[baseline_col], errors="coerce").to_numpy(float)
    cln = pd.to_numeric(d[clean_col], errors="coerce").to_numpy(float)
    fut = d["_future"].to_numpy(float)
    m = np.isfinite(sus) & np.isfinite(cln) & np.isfinite(fut)

    if m.sum() < 3:
        raise ValueError("future_leakage_probe: fewer than 3 rows have a nonempty future")

    corr_sus = float(np.corrcoef(sus[m], fut[m])[0, 1])
    corr_cln = float(np.corrcoef(cln[m], fut[m])[0, 1])
    dr2 = float(delta_r2_plain(fut[m], cln[m][:, None],
                               np.column_stack([cln[m], sus[m]])))

    # The FLAG rule and its inputs are UNCHANGED by K1.  Only the claim attached to them is fixed.
    flag = (abs(corr_sus) > abs(corr_cln)) and dr2 > 0.01
    res = {
        "n_rows_with_future": int(m.sum()),
        "baseline_col": baseline_col,
        "clean_col": clean_col,
        "corr_suspect_with_future": corr_sus,
        "corr_clean_with_future": corr_cln,
        "dr2_suspect_over_clean_predicting_future": dr2,
        #: THE NEUTRAL NAME.  Prefer this and `status` over `reads_future`.
        "screening_flag": bool(flag),
        "status": (SCREEN_FLAG_AMBIGUOUS if flag else SCREEN_NOT_FLAGGED),
        "alternative_explanation": (
            "A STRICTLY PRIOR-GAMES-ONLY estimator that is simply BETTER (less noisy) than %r will "
            "correlate more with the entity's own future than %r does, because the underlying "
            "quantity PERSISTS -- with no future information anywhere in its construction. This "
            "probe cannot separate that from genuine leakage. Rule it out by reading the "
            "construction, not by looking harder at these numbers." % (clean_col, clean_col)
            if flag else None),
        #: *** LEGACY FIELD. Value unchanged; the NAME overstates what it means (K1). ***
        #: `reads_future=True` means FLAGGED, not PROVEN TO READ THE FUTURE.  Read `status`.
        "reads_future": bool(flag),
        "verdict": (
            "SCREENING FLAG (NOT A VERDICT): %r tracks the entity's UNPLAYED FUTURE more closely "
            "than %r does (|%.4f| vs |%.4f|) and adds dR2=%.4f over it in predicting that future. "
            "TWO EXPLANATIONS FIT THESE NUMBERS EQUALLY WELL: (a) %r CONTAINS future information, "
            "in which case an increment measured over it is NOT a forecasting increment; or (b) %r "
            "is simply a BETTER ESTIMATOR of a quantity that persists over time, reads nothing but "
            "prior games, and is perfectly clean. THIS PROBE CANNOT TELL THEM APART. Do not "
            "discard a baseline on this output alone -- audit the construction and establish the "
            "time window of every input."
            % (baseline_col, clean_col, corr_sus, corr_cln, dr2, baseline_col, baseline_col))
            if flag else (
            "NOT FLAGGED: %r does not out-predict %r on the unplayed future (|%.4f| vs |%.4f|, "
            "dR2=%.4f). This probe found nothing; it is NOT a certificate -- a baseline can read "
            "the future without out-predicting a pregame one. Also read the construction."
            % (baseline_col, clean_col, corr_sus, corr_cln, dr2)),
    }
    if verbose:
        print("  future_leakage_probe: n=%d" % res["n_rows_with_future"])
        print("    corr(%-24s, own strictly-after-date future) = %+.4f" % (baseline_col, corr_sus))
        print("    corr(%-24s, own strictly-after-date future) = %+.4f" % (clean_col, corr_cln))
        print("    dR2 of suspect over clean, TARGET = the FUTURE          = %.6f" % dr2)
        print("    status = %s" % res["status"])
        print("    -> %s" % res["verdict"])
        if res["alternative_explanation"]:
            print("    !! %s" % res["alternative_explanation"])
    return res
