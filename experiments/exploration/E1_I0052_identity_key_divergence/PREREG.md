# PREREG — E1_I0052_identity_key_divergence

**Question.** E1_I0048 measured a 10.1 % roster-window divergence between `player_name` and
`player_id` on the exploration partition and named thirteen identities carrying two spellings.
It did not chase that into the research lane. **Where does the research lane key on names, how
many rows diverge, in which direction, and does any published verdict change?**

**Standard adopted before any measurement:** *"the research lane is id-keyed throughout and
nothing diverges"* is the most valuable possible outcome. This screen is written to be able to
return it, and to be disbelieved if it does so without an audit that could have found the
opposite.

---

## 0. Honesty about the order of writing

**This document was committed after the code census (s01–s02) and before every statistic**
(s03 onward). It is not a pre-registration of the census, which was an inventory step with no
statistic attached; it *is* a pre-registration of every number in this screen. The distinction
is recorded rather than papered over. What the census fixed, and what it could not have biased,
is stated in §3.

`PREREG.sha256` is the hash of this file as frozen at that point.

---

## 1. Partition and seals

* **Measurement partition: 2021–2024 only.**
* **2025 and 2026 are a SEALED confirmation holdout and are never read for measurement.**
  Sealed rows may be read for one purpose only — resolving *which person* an id denotes — and
  no statistic may rest on them. Every such read is labelled at the point of use (s10 only).
* Every loader passes through `ik_base.partition_guard`, which filters to
  `season ∈ {2021,2022,2023,2024}`, asserts no sealed season survives, and prints
  `rows_in / rows_kept / sealed_rows_dropped / seasons_seen`.
* Manifests: `row` and `season` granularity usable, `artifact` not, **MISSING = UNVERIFIABLE and
  may back no number**. Manifest status is printed for every artifact opened.
* **The clean window is 2023–2024.** 2021 is degenerate (all forecasts at fallback level 4) and
  2022 depends only on 2021. No result here is a fit, so no result is scoped to that window; the
  fact is recorded so a reader does not read a 2021-inclusive count as a fit population.

## 2. Declarations fixed in advance

**D1 — The two keys.** `player_id` (Int64, stable) versus `player_name` (string). No third key,
no fuzzy matching, no substring selection, no manual repair of any spelling.

**D2 — Divergence.** An operation *diverges* when its output row set differs under the two keys
on the identical input frame. Two directions, declared with their signs:
* **DUPLICATION** — one `player_id` carries two `player_name` values, so the name key emits more
  rows than the id key. Sign: `n_name − n_id > 0`.
* **DROP** — one `player_name` carries two `player_id` values, so the name key emits fewer rows.
  Sign: `n_name − n_id < 0`. **A drop is the dangerous one: it silently removes a player from a
  denominator.** E1_I0048 found zero drop instances in the shipped lane; whether that holds in
  the research lane is an open question this screen must answer either way.
* A third mode is declared here because the prior screen could not see it: **CROSS-FEED DROP** —
  two *different files* hold two spellings of one person and the join between them is
  normalized-exact, so rows are excluded rather than merged. This is a drop even though no single
  frame is internally ambiguous.

**D3 — D101 denominator rule.** Identical response, row set, SST basis, weighting, base. **A
row-set change under a different key IS a denominator change**, and will be labelled as one
explicitly wherever it occurs, including where the change is zero.

**D4 — No name-based selection in my own work.** The ambiguous identities are declared as an
**explicit allowlist of `player_id` integers** in `scripts/ik_base.py`
(`AMBIGUOUS_IDS_2021_2024`). Every selection is `df.player_id == pid` or `.isin(allowlist)`.
The allowlist is asserted equal to the independently recomputed set (anchor A8) and the resolved
list is printed in full. Names appear in output as *labels only*.

**D5 — Exposure is not divergence.** A row belonging to an ambiguous identity inside an
id-keyed frame is **exposure**: what a name key *would* have moved. It will never be reported as
a divergence. Both quantities are reported separately at every surface.

## 3. What the census could and could not bias

The census (s01) is a static AST walk that recovers the key columns of every `merge / join /
groupby / drop_duplicates / set_index / pivot / map / isin / unique / factorize` call under
`experiments/exploration` and `experiments/player_program`. **It searches for keyed operations,
not for the token "name"**; name-keying is a *classification of the recovered keys*.

It can bias the screen in exactly one way: by missing a name-keyed site, which would make the
answer look safer than it is. Three independent checks are therefore pre-declared:

* **C1 — artifact census.** Every persisted `.parquet`/`.csv` in the lane is classified by the
  identity columns it carries: `NO_PLAYER_IDENTITY / ID_ONLY / ID_AND_NAME / NAME_ONLY`. A
  `NAME_ONLY` frame forces name-keying on every consumer regardless of what any call graph says.
* **C2 — key-variable resolution.** Every assignment to a key-shaped variable (`key`, `keys`,
  `gk`, `pk`, `by`, `entity_cols`, …) is recovered by AST and inspected for a player-name column.
  This converts "I could not resolve N keys" into "here is what those variables are bound to".
* **C3 — residual scoping.** Unresolvable keys are only dangerous on a frame where an identity is
  *actually* ambiguous. Every such frame is enumerated, its consuming screens listed, and their
  unresolved structural operations printed in full with source context and adjudicated by hand.

**If C1, C2 and C3 all come back clean and the answer is still "nothing diverges", the answer is
earned. If any of them cannot be completed, the shortfall is reported as a coverage boundary and
the headline is weakened accordingly.**

## 4. Anchors, fixed before any new statistic

Reproduced from E1_I0048 and from the screens measured. Any that fails is reported as a
MISMATCH with its cause, never dropped.

| id | quantity | expected |
|---|---|---:|
| A1 | `master_player` rows, all seasons | 34,199 |
| A2 | null `player_id` rows | 0 |
| A3 | `player_id` dtype | `Int64` |
| A4 | ids with >1 name, all seasons | 13 |
| A5 | names with >1 id, all seasons | 0 |
| A6 | ids with >1 name, 2021–2024 | 12 |
| A7 | names with >1 id, 2021–2024 | 0 |
| A8 | recomputed ambiguous ids == declared allowlist | true |
| A9 | roster windows simulated, 2021–2024 | 1,940 |
| A10 | windows where the keys differ | 196 |
| A11 | divergence rate | 10.10 % |
| A12 | windows with negative delta (drop mode) | 0 |

Screen-level anchors, reproduced inside each measurement rather than asserted:
E0_I0006 high-usage pool **200**, absence-game rows **622**, teammate redistribution rows
**4,983**, events **578**, `top1_share` mean **0.470** / median **0.454**;
the shared screen frame's materialised `DECISION` column against a recomputation of
`n_prior ≥ 8 ∧ ref_trail5_minutes ≥ 24`.

## 5. Measurements, declared in advance

**M1.** For every name-keyed or mixed-key site found by the census, re-execute the owning
screen's own rule under both keys **on the identical frame, one line changed**, and report
`rows_name_key`, `rows_id_key`, the delta, and the direction.

**M2.** Report the **decision-stratum intersection** (`n_prior ≥ 8` ∧ trailing-5 minutes ≥ 24)
for every affected surface, split into stratum rows belonging to an ambiguous identity and
stratum rows a name key would split.

**M3.** Trace each of the twelve individually into: the decision stratum, the champion's fit
pool, and any published table. **Open the named cases; do not report the count.** Nine false
positives were caught elsewhere in this programme by exactly this discipline.

**M4.** Establish the coverage boundary of the verified identity map: where the lane resolves
through it, and where it cannot.

**M5.** Rank affected screens by (rows changed) × (live verdict). Establish cheaply how many
screens are untouched, and say so before the detail.

## 6. Stopping rule and what would change the verdict

The verdict is **"no published verdict changes"** only if every name-keyed site measures a delta
of exactly zero *and* C1–C3 are clean. **A single non-zero delta on a screen with a live verdict
reverses the headline** and the affected statistic is recomputed and reported next to the
published one. A non-zero delta on a screen with no live verdict is reported as an exposure with
its bound.

## 7. Prohibitions

No champion is fitted. No production file is modified. No `git` write command is issued. Nothing
is enacted. Writes are confined to
`experiments/exploration/E1_I0052_identity_key_divergence/`. Signed statistics and raw
unstandardised draws are stored if any are computed; **this screen computes exact counts and
row-set comparisons, not sampled statistics, so no draw file is expected** — if that changes,
draws are written before any standardisation.

Production source files are cited by **absolute path, git blob sha, and the commit that last
changed them**, because a research worktree in this repository has already drifted from
production by 223 lines and a repaired defect read as live for two days.
