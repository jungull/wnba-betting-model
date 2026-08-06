# P37 TARGETED RE-AUDIT — A08_league_lag_level remediation (finding A-1)

* **Auditor role**: A08 TARGETED RE-AUDITOR per D039 — implemented nothing in A08 or any sibling arm.
* **Date**: 2026-08-06.
* **Scope**: `stage2b/P36_IMPLEMENT_ARMS/arms/A08/` remediation of P37 finding A-1
  (`AUDIT_ARMS_A02_A13.md` §5), verified against the frozen card
  `stage2b/P35_FREEZE_TASK_CARDS/SPEC.json`.
* **Frozen-card integrity**: SPEC.json sha256 re-measured this session =
  `68EF22F4FCA15A2E8D91EEEB9B84B86F86E8E9E7CAAB5E23E6A9B950385B4D32` — matches the pinned hash.
* **Blinding**: no real fold, no SEALED_RESULTS access, no comparative performance number touched.
  All verification ran on synthetic frames only; `P38_UNSEALED` absent throughout.

## Verdict

**PASS — fit-eligible.** Finding A-1 is remediated: `arms/A08/features.py` is date-granular on
every prior-window relation, `d_t` is bitwise identical to A09/A10 (and A11's single-season
`dcur`) on an independently built tie-heavy fixture, the K-window boundary semantics match the
frozen `a08_window_tie_break` pin exactly, and the full 12-test suite passes 12/12 on re-run.
The remediation is confined to `features.py` + `tests/test_a08.py` (the fix direction the finding
prescribed); `a08_arm.py` is byte-unchanged since the original implementation window (mtime
2:41 PM vs remediation 6:44–6:47 PM) and A09/A10 source files are untouched.

## 1. What the finding required

A-1 (Severity A): the old `features.py` defined "strictly earlier" by dense game-rank over
`(game_date, game_id)`, letting a same-date sibling game with a smaller `game_id` count as prior —
contradicting `construction_pins.d_t_league_mean_pin` ("strictly before game_date(g)"),
`construction_pins.a08_window_tie_break` (the `(game_date, game_id)` ordering is a tie-break
WITHIN the strictly-earlier-date set, not a redefinition of "earlier"), and K4 (`d_t` is ONE
shared column across A08/A09/A10). Measured then: 156/240 divergent d_t rows vs A09 on a
3-games/date fixture.

## 2. Line-by-line date-granular strictness (code read)

`features.py` (remediated, 275 lines) was read in full against the frozen card:

* **d_t** is now built on `_prior_sum_count_by_date` — verified **byte-for-byte identical
  source** to `arms/A09/feature_construction.py::_prior_sum_count_by_date` via
  `inspect.getsource` comparison (A10's copy differs only by one docstring line; code-identical
  after docstring strip). Same-date rows never enter either the own-team or the league prior
  aggregate. Empty-window rule `d_t := 0` at `n_prior_own == 0` matches A09/A10's shared OP-2
  rule (`np.where(n_own > 0, ...)`, zero-filled league mean where the league count is 0 —
  identical expression order, hence bitwise-reproducible).
* **L_t window membership** is decided by `date_boundary` — for each game, the count of DISTINCT
  games at STRICTLY EARLIER dates (`_game_date_boundary_map`: `groupby("game_date")` transform
  of the block-start rank). `game_id` is used only to order already-strictly-earlier-dated games
  inside the window (the pinned tie-break role), never to decide priority. `n_prior_league :=
  date_boundary`, `windowed_defined := n_prior_league >= K`.
* **FOLDS F1 / OP-3**: pre-window rows take `L_raw := 0` and centered `L_t := 0` (`center_L`
  applies the zero-fill after centering, so `Lbar_train` cannot leak into pre-window rows); no
  row is ever dropped.
* **Card conformance otherwise unchanged from the accepted first-pass audit**: K ∈ {20, 80}
  hard-rejected off-grid (constructor `ValueError` on K=50, re-verified); null =
  `[log_exposure | d_t]` by `term_removal`; no global intercept; d_t K-free. `a08_arm.py` was
  not modified by the remediation, so the first-pass acceptance of the model/null shapes stands.

## 3. Independent tie-heavy fixture (NOT the remediation fixture)

Built fresh by this re-auditor (seed 20260806; the remediation fixture is seed 71, 3 games/date,
40 dates, 6 teams, monotone game_ids, no doubleheaders):

* 8 teams, 60 dates with **variable 1–4 games/date** and 1–3-day date gaps; 150 games /
  300 team-rows;
* **non-monotone game_ids** (random permutation of 10000–99999 — exercises the tie-break as an
  ordering, not an arrival index);
* **68 same-team same-date doubleheader (team, date) cells** — a tie class the remediation
  fixture never produces;
* **120 OT team-rows** (`max_period ∈ {4,5,6}`), pace fed to A08 as
  `lagged_pace(n_off_poss, max_period)` — the exact pinned regulation-equivalent formula A09/A10/
  A11 apply internally, i.e. the production relationship, not the max_period=4 identity trick the
  remediation test T12 uses;
* history and target frames independently shuffled (order-independence stress).

### 3a. Brute-force oracle (all 300 rows, K=10)

Every output compared against a per-row brute-force reimplementation written by this re-auditor:

| check | result |
|---|---|
| `n_prior_league` == count of strictly-earlier-**dated** games | exact, all rows |
| `windowed_defined` == (date-strict count >= K) | exact, all rows |
| `n_prior_own` == date-strict own-team prior count | exact, all rows |
| `L_raw` == mean over team-rows of last K strictly-earlier-dated games | allclose rtol 1e-11 |
| `d_t` == date-strict all-prior own mean − all-prior league mean | allclose rtol 1e-11 |
| `L_raw == 0.0` exactly below the K floor; `d_t == 0.0` exactly at zero own-priors | exact |

Note the oracle's window ("last K of the globally (date, game_id)-sorted strictly-earlier-dated
games") independently exercises the case where the window's lower edge cuts **inside** a
multi-game date block — the only place the (game_date, game_id) tie-break is load-bearing — and
matched on all rows.

### 3b. d_t bitwise parity (K4)

| comparison | result |
|---|---|
| A08 `d_t` vs A09 `align_n_t_d_t_by_key` | **bitwise identical** (`tobytes()` equal) |
| A08 `d_t` vs A10 `align_n_t_d_t_c_t_by_key` | **bitwise identical** |
| A08 `d_t` vs A11 `compute_features(...)["dcur"]` (single-season fixture) | **bitwise identical** |
| A08 `n_prior_own` vs A09 `n_t` | equal, all rows |
| `d_t` across K=20 vs K=80 arm-path designs (`build_design`) | **bitwise identical** (K-free) |
| arm-path `d_t` (through `A08Arm.build_design`) vs A09's `d_t` on the same frame | **bitwise identical** |

### 3c. K-window boundary semantics

* Rows with **exactly K** strictly-earlier-dated games: `windowed_defined` True and the window
  covers ALL earlier games (L_raw == all-prior mean) — verified at K=14 (a boundary value present
  in the fixture) plus over all rows via the oracle equality at K=10.
* Rows one date-block below the floor: `L_raw := 0` exactly.
* Perturbation battery on a deep row (window `[b-K, b-1]` in the earlier-game ordering):
  * game at rank **b−K−1** (just outside): L_raw unchanged (residual 1.8e-13, pure float
    cancellation in the cumulative-sum difference — the same game demonstrably DOES move the
    all-prior `d_t`, so the exclusion is a real boundary, not a dead perturbation);
  * oldest in-window game (rank b−K): moves L_raw; newest (rank b−1): moves L_raw;
  * **same-date sibling game**: moves neither L_raw nor d_t;
  * later-dated game: moves nothing;
  * **same-team same-date doubleheader sibling row**: does not enter the other row's d_t.

31/31 independent checks passed.

## 4. Full 12-test suite re-run

`python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A08/tests/test_a08.py`
re-executed by this re-auditor: **12/12 PASS** (T01–T12), receipt rewritten to
`arms/A08/A08_TEST_RECEIPT.json` (`n_passed: 12`, `unseal_flag_absent: true`). T11 (tie-heavy
date strictness) and T12 (cross-arm bitwise parity, 0/240 divergent rows vs the 156/240 the audit
measured pre-fix) directly regression-guard A-1. The T02 strict-lagging fixture remains
one-game-per-day (the original blind spot), but T11/T12 now cover the tie case, and this
re-audit's independent fixture covers tie classes neither suite fixture has (doubleheaders,
variable density, non-monotone game_ids, OT pace path).

## 5. Residual notes (none promotion-blocking)

1. **C-14 carried, unchanged**: A08 still defers the pinned pace construction to its caller
   (`pace_col`). Bitwise K4 parity holds when the caller supplies
   lagged `realised_team_off_possessions_reg_equiv` computed by the pinned period-based formula
   (this re-audit fed exactly that); P38's execution record must pin the caller's pace
   construction, per the first-pass audit note.
2. **Card measurement note, not a code defect**: `task_cards[A08].p26_k0_record
   .fold_local_fallback.numeric_trigger` records "measured 44 (K=20) and 162 (K=80)" pre-window
   rows. If those P33-era counts were measured under the old rank-strict relation, the
   date-strict counts on the real schedule can only be ≥ those numbers (same-date games no longer
   count toward the floor). The frozen RULE (zero-fill, no rows dropped) is what binds and is
   correctly implemented; P38 should re-measure and record the date-strict counts alongside the
   card's numbers rather than treat 44/162 as an identity check.
3. **Bytecode-cache side effect only**: the parity test's read-only load of A10's
   `feature_construction.py` regenerated `arms/A10/__pycache__/feature_construction.cpython-313
   .pyc` (mtime 6:46 PM). No source bytes outside `arms/A08/` were modified (A09/A10 `.py` mtimes
   predate the remediation). OWNERSHIP upheld in substance.
4. T12's max_period=4.0 identity trick (`lagged_pace(x, 4) == x` bitwise) held on its fixture but
   is not guaranteed by IEEE-754 for arbitrary doubles (`x*40.0/40.0` can round); this re-audit's
   parity run avoided relying on it by feeding A08 the `lagged_pace` output directly. Cosmetic
   robustness note for any future fixture reseed of T12; no action required.

## 6. Reproduction

Re-audit driver (session scratchpad, reproduced here for the record): builds the fixture of §3,
runs the oracle, boundary battery, and parity checks. Fixed seeds: fixture PCG64(20260806),
history shuffle random_state=13, target shuffle random_state=7, perturbation +9999.0 on `pace`.
Suite re-run command as in §4. Frozen-spec hash check:
`Get-FileHash stage2b/P35_FREEZE_TASK_CARDS/SPEC.json -Algorithm SHA256`.

— A08 TARGETED RE-AUDITOR, D039
