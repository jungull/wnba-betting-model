# `contract_baseline_suite_v9` — registered specification

**Status: DEFINITION + COMPLETE SYNTHETIC IMPLEMENTATION + THE FIRST EXECUTABLE REAL CAUSAL
FRAME. Nothing has been fitted, predicted or scored.** No historical OOF, no fitted artifact,
no accuracy or coverage figure, no profitability evaluation. The adapter **builds and hashes**
real frames; it never hands them to a model.

Registry line **87** (86 → 87, a true one-line append; records v1–v8 byte-identical).
Authorised by the Codex supervisor reply `20260802T002154611Z`.

| | |
|---|---|
| `arm_id` | `contract_baseline_suite_v9` |
| supersedes | `contract_baseline_suite_v8` (**byte-untouched**; the modelling core is imported and delegated to) |
| new modules | `cbs_frame_identity.py`, `cbs_provenance.py`, `cbs_real_frames.py`, `cbs_v9.py` |
| tests | `tests/test_cbs_v9.py` — **85 assertions, synthetic only** |
| `config_hash` | **`aa4b3cc53785b9004b88aed748e12e7e4a803c3665c298a6cdd2b0523f6ee260`** |
| manifest | `cbs_snapshot_manifest/3` — `/1` and `/2` are **refused**, not merely superseded |

---

## 1. The five defects

| # | v8 | v9 |
|---|---|---|
| 1 | `frame_digest` used `str(v)`: null collided with `""`, and `1` collided with `"1"`. Frame binding is what stands between a mutated frame and the fitting code. | `cbs_frame_identity/2` — type-tagged, null-distinct, collision-tested |
| 2 | `MUST_BE_ATTESTED` covered **three of five** consumed artifacts while the docs claimed all | all five enforced; the enforced list **is** the documented list |
| 3 | Audit verdicts used `bool(any present)` — one surviving column satisfied it | every registered field required; missing ones named |
| 4 | Unrepairable policy limitations filed as "blockers" alongside repairable ones | **hard blockers** (fix before a real run) separated from **carried policy limitations** (disclose, never repairable retrospectively) |
| 5 | `tests/test_cbs_v8.py` had a second vacuous assertion; the no-arg config helper returned **v7's** digest | an independent exact count; the helper defaults to the v9 arm |

Plus the structural blocker: **`cbs_real_adapter.py` audited frames somebody else had built, and
nothing in the repository built them.** `cbs_real_frames/1` does.

## 2. Frame identity

`None`→`["null",""]`, `True`→`["bool","true"]`, `1`→`["int","1"]`, `1.0`→`["float","1.0"]`,
`"1"`→`["str","1"]`. So `None ≠ ""`, `1 ≠ "1"`, `1 ≠ 1.0`, `True ≠ 1`, `False ≠ 0`.

The bool branch is checked **before** int deliberately — Python's `bool` is a subclass of `int`,
so the natural order would encode `True` as `["int","1"]` and reintroduce a collision.

All null flavours (`None`, `NaN`, `NaT`, `pd.NA`) deliberately collapse to one token: they are
the same claim, and which one a frame carries is pandas dtype plumbing that changes under an
innocuous `reindex`. Row and column **order** remain non-distinguishing — the runners sort
internally, so that invariance is required.

## 3. The real causal frame adapter

`cbs_real_frames/1` joins the contract to the masters, derives the twelve adapter-side Stage-A
features and the four team channels, attaches row-level source-policy timestamps, and returns
train/test/universe frames with schema, join, row-count, timestamp, provenance and identity
receipts.

**The feature definitions are ported, not invented.** `minutes_twostage.py` (registered
`minutes_twostage_availability_v1`) already derives all twelve; its constants are reproduced —
the `0.30` EWMA alpha, the 45-day and 20-game caps, the `min(k,10)` denominator, the DNP prefix
rule, the `returning_flag` conjunction.

**One deliberate divergence, and it is the point.** `minutes_twostage` walks history
**positionally** (`shift(1).ffill()`). v7 established that position is not knowability. Every
feature here is computed over the **availability-admitted** prior set under the same registered
`+36h` policy. Under the daily WNBA cadence that usually excludes a team's most recent game, so
**these features will not equal `minutes_twostage`'s on the same rows.** Causal, deliberate,
disclosed.

### Adapter decisions, stated rather than assumed

| decision | choice | why |
|---|---|---|
| playoffs | **kept** | `minutes_twostage` is Regular-Season-only; the contract carries 2,478 playoff obligations and dropping them would fail coverage |
| `appeared` | from the **contract** | six rows are on the box score with zero minutes; the contract calls them `appeared=False`, `minutes_twostage` drops them |
| DNP prefix rule | **kept as registered** | 82 rows are classed against their own reason text; that is registered behaviour, not silently "fixed" |
| `side` | `home if is_home == 1 else away` | **no such mapping existed anywhere in the repo** — an adapter decision |
| `team_id` | the **contract's** | 8 mid-season-trade rows disagree; the obligation belongs to the team whose game index it came from |
| 3,154 unmatched rows | registered declared defaults | all `appeared=False`, never on a box score; documented as an approximation |

### Measured, fold `season:2024`

| | train | test | at/after cutoff | unmatched that appeared |
|---|---|---|---|---|
| player | 16,556 | 6,094 | **0** | **0** |
| team | 1,416 | 524 | **0** | 0 |

## 4. Five-artifact attestation

All five are now enforced, and all five are attested. The standing scan moves from **29
entries / 29 attested** to **33 / 33**.

Globs added: `data/masters/*.parquet` (matches exactly the two masters), and the two contract
paths **named explicitly** — `experiments/prediction_contract_v2/*.parquet` would also sweep
`game.parquet`, a sixth artifact no CBS arm consumes, and adopting it silently is not the same
as choosing it.

**A disclosed convention divergence.** The four new manifests use `bound_from_dates`
(`2026-08-01T12:00:00Z`). Their already-attested sibling `player_game.parquet` carries
`max(game_date)` read as midnight (`2026-07-31T00:00:00Z`) over identical data, so the new
manifests sit **36 hours later**. That direction is fail-closed. `player_game.parquet`'s
manifest was **not** rewritten; the divergence is disclosed rather than harmonised.

`contract.json` carries no date and no season of its own, so its bound is **inherited** from the
tables it describes, with `asof_granularity="artifact"` and a note saying so.

## 5. Blockers versus carried limitations

A **hard blocker** must be fixed: an absent artifact, an unattested one, a hash drift, a missing
required column. All four that existed have been fixed.

An **accepted policy limitation** is disclosed and carried. No observed historical
feature-source or outcome-availability timestamp exists, and **none can be created
retrospectively** — filing that as "blocking" implies a repair that would have to be fabricated.
Both are handled by the approved conservative policy and labelled `policy` on every row.

The cleared-blockers field is named `provenance_preconditions_met`, **not**
`real_run_permitted`, and carries `supervisory_authorization_required: True`. A field named
"permitted" would have outrun its evidence the moment attestation landed.

## 6. A defect the new tests found

The adapter's `prev_dnp_*` backward scan used a truthiness test on `dnp_class`. A non-DNP row's
class arrives from pandas as `NaN`, and **`if NaN:` is `True`** — so the scan stopped at the
first non-DNP row and reported "no prior DNP" for a player who had one. Caught by the known-row
fixture, which asserts a hand-computed answer rather than whatever the code produces. The same
fixture also caught an unbalanced synthetic box score, because the adapter enforces
`pts == ftm + 3·fg3m + 2·(fgm − fg3m)`.

## 7. Erratum against v8's test file

`tests/test_cbs_v8.py`'s G2 assertion ended in `or True is not None` — unconditionally true, so
it tested nothing. Replaced with an **independent exact recomputation** of every row's prior
count derived from the fixture rather than from the runner. Count **132 → 133**. v8's
implementation files are byte-untouched.

## 8. What is still blocked

No real fitting, no OOF prediction, no scoring, no model coverage or accuracy inspection, no
profitability evaluation, no hierarchical arm. The adapter's output has been built and hashed
and has **not** been handed to a model.
