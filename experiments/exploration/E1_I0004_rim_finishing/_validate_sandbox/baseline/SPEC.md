# CORRECTED OWN-RECENT-RATE BASELINE — `own_rate_v2_split_alpha`

**Produced by:** `experiments/exploration/E1_I0011_split_alpha/` (an **E1** screen).
**Status of the evidence behind it:** E1 is non-claiming. Everything here is a **LEAD**,
not a RESULT. This spec is a *measurement instrument*, not a promoted model, and adopting
it as a baseline requires no promotion decision — it is strictly better-measured than the
thing it replaces, on the exploration partition, and that is the whole claim.

---

## 1. Why this exists

Two live leads in this program state their effect as **incremental value over "the player's
own recent rate."** The estimator the program actually runs in that role is `props_edge.py`'s
frozen `ALPHA = 0.30`, applied to **both** channels of

```
proj = EWMA_0.30(pts/minutes*36) * EWMA_0.30(minutes) / 36
```

That estimator **loses to a plain season-to-date mean** on points, rebounds and assists in
**all four** partition seasons. An increment measured over it is therefore measured over a
baseline that is below the trivial default, and is very likely **overstated**.

This module is the replacement.

---

## 2. The estimator

### 2.1 Channel definition

The projection factors into two channels, and the whole finding is that they want
**different memory**:

| channel | quantity | what it measures | smoothing constant |
|---|---|---|---|
| **efficiency** | `stat / minutes * 36` (per-36 rate) | how productive the player is per unit of court time | `alpha_eff = 0.03` |
| **exposure** | `minutes` | how much court time the player gets | `alpha_exp = 0.30` |

A ~10× separation. Efficiency is close to a season-to-date mean; exposure is strongly
recency-weighted. The incumbent runs 0.30 on both, which over-weights recency on the
efficiency channel badly enough to lose to a season-to-date mean.

### 2.2 Exact update rule

For player *p*, season *s*, game *t*:

1. Restrict to the player's **played rows** in that season: `minutes > 0` **and** the target
   is not NaN. DNP rows may sit in the input; they receive a projection but never contribute
   to state.
2. Order rows by `(player_id, season, game_date, game_id)`, **stable** sort. `game_id` breaks
   same-date ties; any residual tie keeps the caller's own row order. This makes the output
   deterministic.
3. Maintain two exponentially weighted means over the played rows, **pandas convention
   `adjust=True`, `ignore_na=True`** — the house convention in `features/common.py`, and the
   one `props_edge.py` itself uses:
   - `E_t = EWMA_{0.03}( stat/minutes*36 )`
   - `M_t = EWMA_{0.30}( minutes )`
4. **Shift by one within `(player_id, season)`.** The value used for game *t* is the state
   after the last row strictly before *t*. Game *t* can never enter its own feature.
5. Project: `proj(t) = E_{<t} * M_{<t} / 36`.

`alpha = 0.0` is accepted as a sentinel meaning the **expanding (season-to-date) mean**; it
is not the default for either channel.

### 2.3 Warm-up rule

`n_prior` = count of **prior played games in the same season**.

| `n_prior` | default (`warmup="none"`) | recommended for callers needing full coverage (`warmup="std"`) |
|---|---|---|
| `0` | `NaN` | `NaN` — always. No history, no projection. |
| `1–2` | `NaN` (gate not met) | season-to-date mean of the **raw total** |
| `>= 3` | the split-alpha projection | the split-alpha projection |

The default `warmup="none"` and `min_prior=3` **exactly reproduce `props_edge.py`'s registered
appearance gate**, so a caller can swap this in without changing which rows are scored.

`warmup="std"` is measured, not guessed. On the 1,233 partition rows with `n_prior ∈ {1,2}`:

| target | `warmup="std"` | split-alpha, ungated | incumbent, ungated |
|---|---|---|---|
| pts | **4.3135** | 4.3580 | 4.3564 |
| reb | **2.0223** | 2.0450 | 2.0499 |
| ast | **1.2672** | 1.2794 | 1.2822 |

The season-to-date mean wins on all three. Any caller that needs coverage on the warm-up band
should use `warmup="std"`; nobody should use the EWMA there.

### 2.4 Tie / NA handling — the full contract

- **Target NaN or `minutes <= 0`** → the row does not contribute to either channel's state.
  `ignore_na=True` and `min_periods=1` make such rows transparent to the running state rather
  than blanking it.
- **`minutes == 0` on a played row** cannot occur by construction (played requires `> 0`), so
  the per-36 rate is always finite where it is defined.
- **Output `NaN` means "no projection" and must be treated as an explicit skip.** Never impute
  it, never fill it with a league mean. That is the incumbent's own contract and breaking it
  would silently change which rows a downstream comparison scores.
- **Row order of the return value** matches the caller's input order and index exactly.
- **Season boundaries reset the state.** State never crosses seasons. Regular season →
  playoffs is continuous *within* a season, matching house convention.

### 2.5 Role handling

**None. Deliberately.** The role tiers genuinely prefer different alphas — bench / `<15` min /
low-usage players want a much faster exposure channel (0.30–0.50) than starters / `>=25` min
(0.10–0.20), while the efficiency channel sits at 0.02–0.05 in every tier. That pattern is
consistent and was reproduced here.

But **exploiting it does not work.** Selecting alphas per role tier on the training seasons
and scoring on a held-out season changes MAE by between −0.219% and +0.172% across all 18
target × role-family × protocol cells; the across-fold sd is at least as large as |mean| in 17
of 18; and **not one** of the 18 cells has every fold positive. Role-conditioning is carried in
this spec as an explicitly tested and **rejected** option, so the next screen does not spend
its budget rediscovering it.

---

## 3. Constants

```python
ALPHA_EFF = 0.03
ALPHA_EXP = 0.30
MIN_PRIOR = 3
```

**These are not fitted quantities in any load-bearing sense.** All 33 target × fold
selections in the E1 landed with `alpha_eff ∈ [0.00, 0.10]` and `alpha_exp ∈ [0.08, 0.40]`,
and the objective surface is flat enough that this fixed pair **matched or beat per-fold
re-selection on all three targets in every protocol**. Frozen constants beat a tuner here.

**Honest note on provenance:** the pair was fixed by inspecting the aggregate 2021–2024
surface shape. For a caller who wants constants provably untouched by any season it will later
score on, `.fit(train_df, target)` re-selects both alphas on that caller's own training fold
and returns a new instance. On 2021–2024 this changes essentially nothing (differences
≤ 0.007 MAE), so it is offered for hygiene, not accuracy.

**Optional per-target exposure** (`alpha_exp="per_target"`): `{pts: 0.25, reb: 0.30, ast: 0.30}`.
Points prefers a slightly faster exposure channel. Worth ~0.05% MAE — far inside the
fold-to-fold sd of 0.4–1.0% — so the single constant is the recommendation.

---

## 4. Measured out-of-sample performance, seasons 2021–2024

Eval gate: `minutes > 0` and `n_prior >= 3`. n = 16,345 rows (3,433 / 4,030 / 4,435 / 4,447).
The baseline is **frozen** — nothing is fit on any season — so every season below is
out-of-sample in the only sense that matters for a baseline.

### MAE by season

| target | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| **pts** | 4.1828 | 3.9665 | 4.0654 | 4.0331 |
| **reb** | 1.8683 | 1.7645 | 1.7719 | 1.7579 |
| **ast** | 1.2197 | 1.2243 | 1.2054 | 1.2024 |

### Gap versus the two things it replaces — mean ± sd across the four seasons

| target | vs `props_edge.py` incumbent | vs naive season-to-date mean | all 4 seasons positive? |
|---|---|---|---|
| **pts** | **+2.658% ± 0.547** | **+1.286% ± 0.543** | yes / yes |
| **reb** | **+2.720% ± 0.275** | **+1.764% ± 0.571** | yes / yes |
| **ast** | **+3.220% ± 0.946** | **+1.428% ± 0.766** | yes / yes |

### R² on the same rows, pooled 2021–2024 — for callers working in ΔR²

| target | corrected | incumbent | naive expanding total | leave-one-out season rate |
|---|---|---|---|---|
| pts | **0.4928** | 0.4604 | 0.4873 | 0.5129 |
| reb | **0.4799** | 0.4465 | 0.4645 | 0.4936 |
| ast | **0.4748** | 0.4364 | 0.4663 | 0.4947 |

Note the last column: a **leave-one-out full-season rate is *stronger* than this baseline**,
because `(season_sum − y_t)/(n−1)` reads the player's *later* games and is not
pregame-observable. It is not an admissible baseline for a forecasting screen. See
`../i0009_baseline_delta.csv`.

---

## 5. Interface

```python
import sys; sys.path.insert(0, ".../E1_I0011_split_alpha/baseline")
from corrected_baseline import CorrectedOwnRateBaseline, project, BASELINE_ID

# one-liner
proj = project(player_games, "pts")                  # pd.Series aligned to player_games.index

# explicit, and what you want if you are holding one per fold
base = CorrectedOwnRateBaseline()                    # alpha_eff=0.03, alpha_exp=0.30, gate 3
proj = base.project(player_games, "reb")
n_pri = base.n_prior(player_games, "reb")            # exactly which rows were skipped, and why

# coverage on the warm-up band
warm = CorrectedOwnRateBaseline(warmup="std").project(player_games, "ast")

# strict hygiene: constants re-selected on YOUR training fold only
fitted = CorrectedOwnRateBaseline().fit(train_df, "pts")
oos = fitted.project(test_df, "pts")
```

**Required input columns:** `player_id`, `season`, `game_date`, `game_id`, `minutes`, and the
target column. Extra columns are ignored. `KeyError` if any are missing.

**Supported targets:** any per-game counting stat expressible as a per-36 rate × minutes.
Validated here on `pts`, `reb`, `ast`. `minutes` itself is **not** a valid target for this
form — and I0011 already killed the minutes lane: the tuned horizon there independently
recovers α = 0.30, the value already frozen in the program.

**Purity:** every method is pure. `fit` returns a **new** instance and never mutates in place.

---

## 6. How to trust this file

`validate_baseline.py` re-derives everything above from `master_player.parquet` and writes
`BASELINE_PERFORMANCE.json`. Its first act is an **equivalence check**: the shipped module must
reproduce the E1 screen's own grid MAE for the same `(alpha_eff, alpha_exp)` cell on the same
rows to `< 1e-9`, or it hard-exits. All 24 checks MATCH. If the module and the screen ever
drift apart, that check fails loudly rather than silently reporting two different estimators.

```
python validate_baseline.py        # -> BASELINE_PERFORMANCE.json, run_log_validate.txt
```

---

## 7. Exploration-partition discipline for callers

The constants were established on **seasons 2021–2024 only**. The 2025/2026 confirmation
holdout was never read by the screen that produced them.

`corrected_baseline.py` contains **no season logic** and will happily project whatever it is
handed. **A caller doing E0/E1 work must filter to 2021–2024 itself.** Handing this module
holdout rows does not make the holdout safe; it makes the caller the one who broke the
partition.
