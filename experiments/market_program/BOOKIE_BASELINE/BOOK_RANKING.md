# BOOK_RANKING — FIXED bookmaker identity ranking

**Node:** `experiments/market_program/BOOKIE_BASELINE/book_ranking.py` · **Lane:** market_intelligence

## D036 provenance block

| Field | Value |
|---|---|
| Decision ID | `D036_SCOREBOARD_MEASUREMENT_SEMANTICS` |
| Ledger | `experiments/player_program/orchestration/DECISION_LEDGER.jsonl` |
| Point governing this artifact | **Point 4**: *"Best/worst book = FIXED bookmaker identities ranked over the same matched universe and cutoff with a minimum common-sample threshold; per-game closest-book selection prohibited."* |
| Contract | `MARKET_PROGRAM_CONTRACT.md`, sha256 `1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de` |
| D034 standard applied | de-vigged threshold probabilities are the primary quantity; no distributional-margin claim is made anywhere in this module |

**How point 4 is discharged.** Every book in this ranking is a **fixed identity** (`fanduel`,
`draftkings`, ...) evaluated on **the same set of games** as every other book it is ranked against.
This module never picks, per game, whichever book happens to have the tightest number that game —
that is exactly the "per-game closest-book selection" point 4 prohibits. Concretely, for each
(snapshot class, market):

1. A book must have an admissible quote on **≥ 200 matched games on its own footprint** to enter the
   candidate pool at all (`MIN_COMMON_THRESHOLD = 200`, this task's instruction).
2. The books actually scored are then restricted to the **intersection** of their individual game-id
   sets — "the same matched universe." If that intersection is under 200 games, the candidate with the
   smallest individual footprint is dropped and the intersection is recomputed, repeating until either
   the intersection clears 200 or fewer than two books remain (in which case the market/class is
   reported `NO_COMMON_UNIVERSE_MEETS_THRESHOLD`/`INSUFFICIENT_CANDIDATE_BOOKS`, never silently ranked
   at a smaller or mismatched n).
3. Every surviving book's metric (spread MAE, total MAE, or moneyline Brier) is computed over that
   **exact same** intersected game-id set — never a book-favorable subset of its own.

This is verified directly by `TESTS_BOOK_RANKING.py::test_rank_market_never_scores_a_books_own_favorable_subset`,
which constructs a book that would look artificially good if scored on its own full footprint and
confirms the common-universe rule refuses to credit it for games outside the shared set.

## Delegation (never reimplemented)

* **Vig removal**: `M11_CONSENSUS_MODEL/consensus.py::no_vig` — the *only* route to a de-vigged
  moneyline probability anywhere in this module (`vig_method = multiplicative_proportional`,
  preregistration hash `021dc75506a43a8a849f2d57a7b4aae1b6410e9bccb3a1a88f5f4412c1f60bc6`). No local
  vig formula exists in `book_ranking.py` — checked directly by
  `TESTS_BOOK_RANKING.py::test_book_ranking_delegates_vig_to_m11_only`.
* **Join / matching / market extraction**: `build_baseline.py`'s `load_outcomes`, `load_archive`,
  `match_outcome`, `extract_market`, `mae_bias`, `brier_logloss`, `NAME_TO_ABBR`, `ET_OFFSET_HOURS`,
  `CAVEAT_TEXT` are called as-is, never forked. The matched-game universe (1,250 games, 14 unmatched)
  and the EARLY/LATE snapshot-class definition and in-play exclusion are identical to `BASELINE.md`'s
  — this module only adds per-fixed-book granularity `outcome_rows.json` does not carry.

## The unknown-snapshot-time caveat (frozen text, inherited unchanged from BOOKIE_BASELINE)

> "This snapshot's timestamp is vendor-asserted and unwitnessed (tier T1: THIRD_PARTY_CONTEMPORANEOUS,
> per MARKET_PROGRAM_CONTRACT.md section 4.3). It is drawn from a third-party historical-odds archive
> retrieved on 2026-08-06, labelled EARLY (vendor-asserted ~16:00Z request) or LATE (vendor-asserted
> ~23:30Z request) relative to the archive's own request day, not from our own real-time capture. LATE
> is closer to commence than EARLY, but neither is a witnessed closing line, and the true
> hours-to-commence at capture is not independently verified. No timing, latency, reaction, or CLV
> inference may be drawn from this snapshot; it supports calibration-against-realized-outcomes only, at
> an unknown-but-bounded-pregame instant."

`caveat_sha256 = 93a816cc9357af8d0a09da60695eee60e6921b1cbf1fbcb2b7c8b125216e21f7`, verified against
the frozen constant in `build_baseline.py` by an assertion at the top of `book_ranking.py::main()` —
this module refuses to emit `book_ranking.json` if the caveat text has drifted from its hash.
**No book identity below is being compared on a witnessed closing line**; "best"/"worst" here means
best/worst against realized outcomes at this archive's two unwitnessed vendor-asserted snapshot
classes, nothing more.

## Load audit

| | n |
|---|---|
| Distinct games in archive | 1,264 |
| Matched to a realized outcome | 1,250 |
| Unmatched | 14 |
| Matched games, EARLY class | 1,248 |
| Matched games, LATE class | 1,071 |

(Identical to `BOOKIE_BASELINE/BASELINE.md`'s join audit — see that document for the full unmatched
list and reasons; this module reuses the same join, it does not re-derive it.)

## Results — pooled rank per snapshot class

Pooled rank = **unweighted mean of each metric's within-market ascending rank** (spread MAE rank,
total MAE rank, moneyline Brier rank; 1 = best on that metric). Each metric is ranked over its *own*
common-universe result — the spread common universe, total common universe, and moneyline common
universe are three different game-id sets per class (a book's spread coverage need not equal its
totals coverage), each independently cleared through the ≥200 threshold procedure above. The pooled
score therefore combines **ranks**, never raw metric values across markets (spread MAE, total MAE,
and Brier are not commensurable units). A book only enters the pooled table if it was ranked (status
`OK`) in **all three** markets for that class; books present in only one or two markets are reported
in the per-market tables below but excluded from the pooled call, never imputed.

### EARLY

| Market | Common universe (n) | Books ranked | Books excluded (below individual threshold) | Books excluded (to reach common intersection) |
|---|---|---|---|---|
| Spread | 373 | 11 | circasports, gtbets, sugarhouse, unibet | wynnbet(205), superbook(232), unibet_us(301), foxbet(347), barstool(384), twinspires(403), pointsbetus(441) |
| Total | 401 | 11 | circasports, gtbets, sugarhouse | wynnbet(206), superbook(232), unibet_us(301), foxbet(334), barstool(384), twinspires(403), pointsbetus(443) |
| Moneyline | 394 | 11 | circasports, gtbets, sugarhouse, unibet | wynnbet(202), superbook(229), unibet_us(300), foxbet(349), barstool(383), twinspires(402), pointsbetus(442) |

**Pooled rank, EARLY (11 books, n=373/401/394 spread/total/moneyline):**

| Rank | Book | Spread MAE | Spread rank | Total MAE | Total rank | ML Brier | ML rank | Pooled avg rank |
|---|---|---|---|---|---|---|---|---|
| 1 | **betrivers** | 10.131 | 2 | 15.029 | 6 | 0.20305 | 1 | **3.00** |
| 2 | williamhill_us | 10.173 | 8 | 15.015 | 1 | 0.20320 | 4 | 4.33 |
| 3 | lowvig | 10.164 | 5 | 15.016 | 3 | 0.20331 | 6 | 4.67 |
| 4 | betus | 10.139 | 4 | 15.032 | 9 | 0.20317 | 2 | 5.00 |
| 5 | fanatics | 10.114 | 1 | 15.024 | 5 | 0.20362 | 10 | 5.33 |
| 6 | betonlineag | 10.166 | 7 | 15.016 | 4 | 0.20331 | 7 | 6.00 |
| 6 | bovada | 10.131 | 3 | 15.040 | 10 | 0.20324 | 5 | 6.00 |
| 8 | fanduel | 10.178 | 10 | 15.030 | 7 | 0.20319 | 3 | 6.67 |
| 9 | draftkings | 10.177 | 9 | 15.016 | 2 | 0.20373 | 11 | 7.33 |
| 10 | mybookieag | 10.166 | 6 | 15.031 | 8 | 0.20344 | 9 | 7.67 |
| 11 | **betmgm** | 10.192 | 11 | 15.049 | 11 | 0.20340 | 8 | **10.00** |

**EARLY best book: `betrivers`** (pooled avg rank 3.00). **EARLY worst book: `betmgm`** (pooled avg
rank 10.00).

### LATE

| Market | Common universe (n) | Books ranked | Books excluded (below individual threshold) | Books excluded (to reach common intersection) |
|---|---|---|---|---|
| Spread | 297 | 11 | circasports, foxbet, gtbets, sugarhouse, superbook, unibet, unibet_us, wynnbet | barstool(226), twinspires(229), pointsbetus(262) |
| Total | 317 | 11 | circasports, foxbet, gtbets, sugarhouse, superbook, unibet_us, wynnbet | barstool(223), twinspires(226), pointsbetus(264) |
| Moneyline | 282 | 11 | circasports, gtbets, sugarhouse, superbook, unibet, unibet_us, wynnbet | foxbet(218), barstool(226), twinspires(229), pointsbetus(257) |

**Pooled rank, LATE (11 books, n=297/317/282 spread/total/moneyline):**

| Rank | Book | Spread MAE | Spread rank | Total MAE | Total rank | ML Brier | ML rank | Pooled avg rank |
|---|---|---|---|---|---|---|---|---|
| 1 | **betrivers** | 10.024 | 2 | 14.800 | 7 | 0.21200 | 2 | **3.67** |
| 2 | draftkings | 10.039 | 7 | 14.765 | 1 | 0.21217 | 4 | 4.00 |
| 3 | betmgm | 10.029 | 4 | 14.793 | 6 | 0.21214 | 3 | 4.33 |
| 4 | fanduel | 10.047 | 11 | 14.771 | 2 | 0.21158 | 1 | 4.67 |
| 5 | betus | 10.037 | 6 | 14.776 | 4 | 0.21247 | 8 | 6.00 |
| 5 | fanatics | 9.966 | 1 | 14.808 | 10 | 0.21242 | 7 | 6.00 |
| 5 | mybookieag | 10.029 | 3 | 14.803 | 9 | 0.21225 | 6 | 6.00 |
| 8 | williamhill_us | 10.030 | 5 | 14.812 | 11 | 0.21220 | 5 | 7.00 |
| 9 | betonlineag | 10.044 | 9 | 14.781 | 5 | 0.21255 | 9 | 7.67 |
| 9 | lowvig | 10.045 | 10 | 14.774 | 3 | 0.21260 | 10 | 7.67 |
| 11 | **bovada** | 10.042 | 8 | 14.800 | 8 | 0.21309 | 11 | **9.00** |

**LATE best book: `betrivers`** (pooled avg rank 3.67). **LATE worst book: `bovada`** (pooled avg rank
9.00).

## Observations (descriptive; not evidence-ladder claims)

* `betrivers` is the pooled-rank best book in **both** snapshot classes on this archive/threshold — a
  descriptive fact about this measurement, not an evidence-ladder claim (no preregistered F-family
  endpoint was run here; this module is machinery over the same T1 vendor-asserted archive
  `BOOKIE_BASELINE` uses, subject to the identical unknown-snapshot-time caveat).
* Only 11 of the 18 distinct book identities present in the archive clear the ≥200 individual-footprint
  threshold in either class; the other 7 (`circasports`, `gtbets`, `sugarhouse`, `unibet`,
  `superbook`, `unibet_us`, `wynnbet`, `foxbet`, `barstool`, `twinspires`, `pointsbetus` — the exact
  excluded set differs slightly by class/market, see the tables above) never enter the ranking on this
  archive; this is a coverage fact about the archive, not a judgment about those books.
* The spread between best and worst pooled rank is narrow in absolute metric terms (e.g. EARLY spread
  MAE ranges 10.114–10.192, a 0.078-point spread across all 11 ranked books) — consistent with
  `BASELINE.md`'s finding that cross-book and best-book (FanDuel) track each other closely at this
  archive's coverage level; the FIXED-identity ranking here resolves that into an ordering, but the
  underlying books are close together on this measurement, not dramatically differentiated.

## What this artifact could NOT establish

* Whether `betrivers`' pooled-rank lead reflects a real pricing-skill difference or is an artifact of
  which ~300-400 games happen to fall in its intersected common universe at this archive's coverage
  level — no significance test or confidence interval is computed here (out of this task's scope; see
  D036 point 7 for the standard a future pass against this artifact should apply).
* Any per-game "which book was closest to true" comparison — structurally prohibited by point 4 and
  never computed anywhere in this module.
* Whether the 7 books excluded for insufficient individual footprint would rank differently on a
  larger/different archive — this artifact only measures the current
  `data/market_snapshots/historical/featured_backfill.jsonl` snapshot.

## Reproducing

```
python experiments/market_program/BOOKIE_BASELINE/TESTS_BOOK_RANKING.py   # fixture tests, known answers
python experiments/market_program/BOOKIE_BASELINE/book_ranking.py         # full measurement pass
```

Output: `book_ranking.json` — full per-class, per-market, per-book detail (MAE/bias/Brier/log-loss/n/
coverage), the common-universe construction trail (which books were dropped and why, at each stage),
and the pooled-rank table with `best_book`/`worst_book` per snapshot class.
