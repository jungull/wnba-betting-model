# Byte-pin canonicalisation — the join-key separator convention, stated explicitly

**Epistemic status:** IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

This document discharges the one gap the S35 freeze carried forward into S36:

> **S35 `VERIFICATION.one_documented_gap_carried_not_hidden`**
> *item:* "the `projected_team_off_possessions` byte pin also carries a `join_key_sha256`; the pin
> states `join_key_columns [game_id, team_id]` but not the inter-column separator convention, so
> the join-key digest did NOT reproduce under this node's reading."
> *what DID reproduce:* "the COLUMN digest itself (`9078790427e0c…`, 2,990 values, 8 NaN) matched
> exactly, as did all five composite column digests."
> *assessment:* "a documentation gap in the pin's own stated rule, not evidence any digest is
> wrong."
> *obligation:* "**S36 must state the join-key separator convention explicitly when it recomputes
> byte pins under R10, so the pin becomes reproducible by a third party.**"

**No digest was changed.** The frozen values are reproduced exactly as they stand; what was
missing was the sentence that tells a third party how to reproduce them.

---

## The convention

Two different separator characters are in play, and conflating them is precisely what made the
pin irreproducible:

| role | character | name |
|---|---|---|
| joins one **row** to the next | `U+001F` | UNIT SEPARATOR |
| joins the **components of one composite key**, within a row | `U+001E` | RECORD SEPARATOR |

The full rule, for any pin:

1. Order the rows by the pin's own `sort_rule` (lexicographic on the stringified key columns,
   ascending).
2. Canonicalise each value: floats via `repr(float(v))` (NaN → `'nan'`); ints via `str(int(v))`;
   timestamps via `.isoformat()`; everything else via `str(v)`.
3. For a **column digest**: join the canonicalised values with `U+001F`.
4. For a **composite join key**: join each row's canonicalised components with `U+001E`, then join
   the resulting per-row keys with `U+001F`.
5. UTF-8 encode; `sha256` hexdigest.

A **single-column** join key never exercises step 4's inner join, so it reduces exactly to a
column digest. That is why the three `score_baseline_rows` pins (`join_key_column = "game_id"`)
always reproduced while the one two-column pin did not.

Implemented in `runner/canon.py` (`UNIT_SEP`, `RECORD_SEP`, `column_digest`, `join_key_digest`).

---

## How the convention was established: measured, not guessed

The `U+001E` inner separator is not documented anywhere in the frozen bytes, so it was recovered
by exhaustive search rather than assumed. 576 candidate conventions were enumerated over four
row-orderings (sorted by `(game_id, team_id)`; file order; sorted by the composed key under two
compositions), eleven intra-key separators (`U+001F`, `U+001E`, `|`, `,`, `-`, `:`, tab,
underscore, space, `/`, and empty), six inter-row separators, and both all-rows and
unique-keys-only variants, plus column-sequential and digest-of-digests forms.

**Exactly one reproduced the frozen `join_key_sha256`:** intra-key `U+001E`, inter-row `U+001F`,
rows sorted lexicographically on `(str(game_id), str(team_id))` ascending. The result is
order-insensitive in a reassuring way — every row-ordering that sorts to the same sequence lands
on the same digest, and no other separator combination lands on it at all.

---

## The four frozen pins, re-derived at S36 under R10

All four reproduce. `tests/TESTS.py` re-derives every one on each run, so this table is a live
check rather than a claim.

| artifact | column | n | n_nan | `column_sha256` | `join_key_sha256` |
|---|---|---:|---:|---|---|
| `market_program/SCORE_BASELINES/score_baseline_rows.parquet` (method `composite_pace_x_eff_v1`) | `pred_margin` | 1465 | 0 | `1d79ff3a…4ff4` ✓ | `d3a4b7fa…d249` ✓ |
| same | `pred_total` | 1465 | 0 | `16c312ab…5f3d` ✓ | `d3a4b7fa…d249` ✓ |
| same | `p_home` | 1465 | 188 | `8a92c017…1989` ✓ | `d3a4b7fa…d249` ✓ |
| `player_program/projected_exposure_v1/team_possession_prior_v1.parquet` | `projected_team_off_possessions` | 2990 | 8 | `90787904…71bd` ✓ | `6b8b2709…d59b` ✓ **(the gap, now closed)** |

The negative control matters as much as the positive one: `tests/TESTS.py` also asserts that
digesting the two-column key with the *wrong* (single, `U+001F`) separator does **not** reproduce
the pin. Without that assertion the test would pass for a bad reason.

---

## Two measured facts about the NaN counts, since both are load-bearing downstream

* **`p_home`, 188 NaN of 1,465.** Re-measured on the universe at S36: 188 structural NaN rows.
  This is why the three E3 cards' `composite_p_home` is implemented as a null-granted *ingredient*
  rather than a fitted design column — no card declares an imputation for those rows. See
  `arms/_head.py`, `P_HOME_READING`, and the contradiction raised to S37.
* **`projected_team_off_possessions`, 8 NaN of 2,990.** Re-measured at S36: the 8 are exactly the
  4 games of `2021-05-14` × 2 sides — the D010 opening-day games the universe **excludes**. So the
  pace prior is resolved on all 1,491 universe clusters, matching the card's own
  "measured resolved on all 1,491 universe games". `arms/sc08_sigma_margin_map.py` asserts this
  rather than trusting it, and halts rather than imputing.

---

## The other canonicalisation in this program

Card and manifest hashes use the **cycle-1 P35 rule**, which is unrelated to the column rule above
and is stated here so the two are not confused:

```
sha256( json.dumps(obj, sort_keys=True, separators=(',',':')).encode('utf-8') )
```

`runner/canon.py::canonical_json_sha256`. `tests/TESTS.py` re-derives all seventeen frozen
`card_sha256` values from `SPEC_V2.json` under this rule and matches them against the S35 freeze.
