# M21_EXECUTION_REALISM -- execution realism: limits, slippage, and decision-to-executable latency, measured

**Epistemic status (verbatim, per contract):** EXECUTION SYSTEM MEASUREMENT under the four-system separation. Measures what stands between a signal and a filled bet: posted limits, price movement between decision and action, account frictions. Reuses the ops lane's latency measurement discipline, pointed at sportsbooks. No wager is placed.

**Hard boundary:** this node measured; it did not place, simulate-as-if-placed, recommend, or size a wager. Every orderbook/trade row read carries `is_order=false` structurally in the capture schema -- nothing below is, or could be replayed as, an order. No account credential was used or needed (SX Bet's read endpoints require none; verified in `EXCHANGE_CAPTURE/sxbet/API_AND_WNBA_VERIFICATION_2026-08-06.md`).

---

## 0. A contradiction found before any measurement, and how it was resolved

Before touching the tape, `experiments/market_program/EXCHANGE_CAPTURE/sxbet/HALT_USER_REQUIRED.md` was read, since it sits directly in the read path. It states, in its own words, dated 2026-08-06: *"0 order-book rows, 0 trade rows, 0 poll cycles... Nothing beyond the three verification GETs listed above was executed against SX Bet's live systems."*

The bytes on disk say otherwise. `capture_sxbet.py`, `poll_log.jsonl`, `sxbet_state.json`, and the four `data/*.jsonl` files all postdate that halt document and show a live, continuing, healthy capture run: 131 completed cycles, zero endpoint failures, 6,376 orderbook rows and 7,442 trade rows written between `2026-08-07T02:39:05Z` and `2026-08-07T13:35:08Z`.

Per the standing rule that frozen bytes govern over prose, this was checked rather than assumed benign. `capture_sxbet.py`'s own docstring cites its authority: `DECISION_LEDGER.jsonl` decision `D035_EXCHANGE_DISPOSITIONS` (ts `2026-08-06T19:30:08Z`). Reading that line directly confirms it is a real, ledgered user ruling in chat -- *"SX BET - user rules the official-documented-API reading controls... capture proceeds at gentle read-only rates... provenance EXCHANGE_PUBLIC_API with VENDOR_ASSERTED timestamps, the ToS tension recorded rather than erased, and the disposition reversible if SX Bet ever objects."* This is a genuine `Section 9.7` USER_REQUIRED resolution, not a self-granted exemption, so the tape is legitimately captured and this is not a live stop-condition trip.

**Residual defect (not fixed here -- outside this node's write scope):** `HALT_USER_REQUIRED.md` was never updated to record the D035 resolution. Anyone reading only that file today would wrongly conclude SX Bet capture never started. Flagged, not silently reconciled.

A second, smaller discrepancy: this node's generated contract (`M21_EXECUTION_REALISM.md`) names `REPORT.md` + `FINDINGS.json` as required outputs; the direct dispatch instructions for this session say the opposite (`REPORT_BODY.md` + `EXECUTION_REALISM.json`, coordinator materializes `REPORT.md`). The dispatch instructions were followed, consistent with the `REPORT_BODY.md` convention already referenced (though not yet materialized) inside sibling nodes M16 and M07's `FINDINGS.json` files.

---

## 1. The tape, inventoried

Source: `data/sxbet_capture/{markets,best_line,orderbook,trades}.jsonl` (DATA worktree). Command: `inventory.py` reading each JSONL directly.

| table | rows | distinct cycles | distinct marketHash | distinct games |
|---|---|---|---|---|
| markets | 314 | 54 | 138 | 9 |
| best_line | 4,496 | 131 | 138 | (derived via markets join) |
| orderbook | 6,376 | 131 | 98 (with activity) | 8 (with activity) |
| trades | 7,442 | 131 | 37 (with activity) | 6 (with activity) |

The capture spans **10.93 hours** (`2026-08-07T02:39:05Z` to `2026-08-07T13:35:08Z`), 131 cycles, **zero endpoint failures**. Nine distinct WNBA games appear in the market metadata (moneyline x8, totals x63, spread x67 by distinct `marketHash` -- type codes 226/28/342 respectively). Eight games ever showed a resting order; six ever produced a witnessed trade. Trade-leg notional (stake / 1e6, USDC-scale collateral token) has median $23.96, p90 $103.19, max $5,187.77 across 7,594 legs -- this is retail-scale activity, worth stating plainly since it bears directly on how much weight the depth numbers below can carry.

The dedup mechanics are a finding in their own right: of 131 cycles, `rows_written` totals (314/4,496/6,376/7,442) plus `rows_deduped` totals (5,220/6,572/10,437/0) reconcile exactly against the raw per-cycle counts recorded in `sxbet_state.json`. Trades never dedup (each `fillHash` is unique and immutable); markets/best_line/orderbook dedup heavily because most polled state is unchanged between the ~300s cycles -- the append-only writer only emits a row when `payload_hash` changes. This confirms the append-only + prev_snapshot_ref chain is working as designed, not silently dropping rows.

---

## 2. Depth and slippage -- a depth-walk on the recorded book, at capture instants

**What the tape can and cannot support here, stated up front:** the orderbook file is append-only and deduplicated -- an unchanged order is never rewritten. To get the depth *at* a given instant, `depth_analysis.py` performs event-sourced replay: for each of 14 sampled capture-cycle checkpoints (every 10th cycle of 131, plus the final one), each order's state is taken as the latest row with `retrieval_ts <= checkpoint` for that `(marketHash, orderHash)` key, filtered to `orderStatus == "ACTIVE"` with remaining size `totalBetSize - fillAmount > 0`.

This produced 2,273 `(market, side, snapshot)` combinations with at least one visible resting order. Active-orders-per-side: min 1, median 7, p75 16, max 226.

**Depth at the best price** (USDC-equivalent, i.e. size resting at the single most-favorable quoted price on that side):

| stat | value |
|---|---|
| min | 10.00 |
| p10 | 17.77 |
| p25 | 25.70 |
| median | 49.01 |
| p75 | 87.01 |
| p90 | 275.15 |
| max | 4,500.56 |

**Slippage to walk the book and fill a $50 notional** (percentage-point move in `percentageOdds` from the best price to the volume-weighted fill price): of 2,273 attempts, 1,983 could be filled from the visible depth; 290 could not (visible depth insufficient). Of the fillable ones: min 0.000%, median 0.000%, p90 1.351%, max 27.787%.

**Slippage to fill $100 notional:** 1,856 of 2,273 fillable; 417 insufficient. min 0.000%, median 0.081%, p90 5.229%, max 31.655%.

The median-zero result at $50 is not an error -- it reflects that half the sampled snapshots have enough size resting exactly at the best price to absorb $50 without walking the book at all (consistent with the median depth-at-best of $49.01 above, right at that notional). The tails are where the real story is: at $100, a non-trivial fraction of snapshots (417 of 2,273, ~18%) do not have enough *visible* depth to fill at all, and the p90 slippage of 5.2% is a real, distribution-shaped cost, not a single optimistic constant.

**Two caveats that must travel with every one of these numbers, per the mandate:**

1. **This is depth AT CAPTURE INSTANTS, not a claim about what would have filled.** SX Bet is a peer-to-peer order book. A resting order can be cancelled, filled by someone else, or expire between our poll and any hypothetical action. No market impact, gas/settlement delay, or counterparty risk is modeled. No `EXECUTION_FEASIBLE` label is claimed anywhere in this output.
2. **Price-scale caveat.** `percentageOdds` is SX Bet's own fixed-point encoding (observed as integers scaled by 1e20 in the captured payloads). The slippage percentages above are relative, within-book price moves and are scale-invariant regardless of the exact decimal convention; this node did not independently re-verify the scale against SX Bet's own API documentation, so no claim is made about the exact real-world implied probability.

---

## 3. Decision-to-executable latency -- the resolution floor, and what it rules out

**We cannot measure latency finer than our own polling interval.** Only T0 fields (`retrieval_ts` / `ingestion_ts`, witnessed at capture time by our own process) are used anywhere below. `vendor_ts` fields -- `createdAt` on trades, `apiExpiry` on orderbook entries -- are `VENDOR_ASSERTED` with `vendor_ts_semantics=unknown_unverified` (the M00 Section 6.3 default) and were never used for a latency claim, per the D023 amendment-4 rule that T1 stamps may never enter a timing claim.

**SX Bet exchange tape, own polling floor.** Measured via `sxbet_state.json`'s `cycles[]`: inter-cycle gap (`started_ts[i+1] - started_ts[i]`) across 131 cycles -- min 298.0s, median 300.0s, mean 302.7s, max 657.1s (one slow cycle), stdev 31.2s. Cycle in-flight duration (`finished_ts - started_ts`, i.e. our own round-trip to poll all four endpoints at <=1 rps) -- min 4.24s, median 4.28s, max 10.60s. Our own disk-write pipeline delay (`retrieval_ts -> ingestion_ts`) is negligible: median 1.79ms, max 16.18ms across 6,376 orderbook rows.

**Reading this as a decision-to-executable claim:** a price observed on SX Bet at time *t* cannot be re-confirmed with fresh, witnessed information sooner than the next poll -- at *t* + [298s, 657s], median +300s. That interval **is** the executable-latency floor for this tape.

**Quote-change frequency, same tape.** Time between consecutive recorded `best_line` change events for the same `(marketHash, side)` key, across 4,220 intervals: min 298.0s, p10 299.5s, median 300.1s, p90 1,197.9s, max 16,798.6s. This is **right-censored at our own poll floor** -- because we sample once per ~300s cycle, several true price changes inside one gap collapse into a single observed transition at the next poll. The true underlying SX Bet quote-change rate is *at least* this frequent and cannot be resolved further from this tape; the number reported is a floor, not a rate.

**Sportsbook ladder (`data/market_snapshots/snapshots.csv`), own polling floor.** 3,152 rows, 21 distinct poll instants, span `2026-08-06T18:52:04Z` to `2026-08-07T01:42:03Z`. Inter-poll gaps: min 0.2s, median 599.8s, mean 1,230.0s, max 7,201.3s. This is **not** a fixed-interval poller -- `poll_log.csv` shows an event-adaptive grid keyed to scheduled-tipoff offsets (`T-24h`, `T-4h`, `T-2h`, `T-15m` labels observed; `poll_interval_at_capture` values of 900s / 3,600s / 7,200s / 14,400s / 86,400s). The resolution floor for the sportsbook ladder is therefore not a single number -- it tightens as a game approaches tip-off and is coarse (up to a 24-hour bucket) far from it.

**Cross-venue latency (SX Bet vs. sportsbook), this session: UNSUPPORTABLE.** The two T0 capture windows do not overlap. The sportsbook ladder's witnessed span ends `2026-08-07T01:42:03Z`; the SX Bet exchange tape's witnessed span begins `2026-08-07T02:39:05Z`, roughly 57 minutes later. There is no instant at which both tapes hold a simultaneously-witnessed price, so no "observed here, acted there" latency figure can be computed from owned data for this session. This would become measurable once both pollers run concurrently for an overlapping stretch -- it is a gap in the *data*, not a modeling failure, and is reported as `UNSUPPORTABLE` rather than worked around.

**Amendment-4 fields for the one supportable claim (SX Bet same-tape polling floor):**

```
t_lower / t_upper        298.0s / 657.1s
poll_interval_event      n/a -- same-tape polling-floor claim, not event-to-quote
poll_interval_quote      300s target; observed 298.0-657.1s (median 300.0s)
vendor_latency_bound     UNBOUNDED -- SX Bet documents no book-last-change timestamp
                         distinct from our own retrieval; no independently sourced
                         vendor latency bound exists in owned data
clock_skew_bound         CLOCK_UNBOUNDED -- no NTP/clock-skew measurement performed
                         anywhere in EXCHANGE_CAPTURE/sxbet/
censor_type              interval
tier                     T0 (retrieval_ts/ingestion_ts); vendor_ts held to the
                         VENDOR_ASSERTED advisory channel only
n_trusted / n_excluded   131 / 0
```

**Sharpness-prohibition consequence (M00 Section 6.2):** no point estimate finer than `G = poll_interval + L_max(all vendors) + 2*clock_skew` is admissible. `L_max` is UNBOUNDED and `clock_skew` is unmeasured here, so `G` is itself unbounded beyond the directly-measured same-tape polling gap. Any finer reaction-time claim, or any cross-venue lead-lag claim, is `UNSUPPORTABLE` from this tape as captured. Only the same-tape polling-floor interval above is stated as a result.

---

## 4. Book-side limits -- ABSENT, not estimated

**Sportsbook side:** `data/market_snapshots/snapshots.csv` carries 21 columns (`snapshot_id`, `game_id`, `book`, `market`, `outcome`, `line`, `price`, `price_over`, `price_under`, `implied_prob`, `novig_prob`, `market_status`, plus the amendment-4 fields). None encode a maximum stake, bet limit, or exposure cap. A grep for `max_stake|bet_limit|wager_limit|maxStake|max_bet` across `scripts/` and `market_snapshot_schema.py` returned zero matches -- the schema does not even have a slot for this.

**Exchange side:** SX Bet's `/markets/active` payload (`markets.jsonl` content) carries no venue-imposed maximum-order or maximum-fill field either -- only `__type, chainVersion, gameTime, group1, isQuarterLineMarket, leagueId, leagueLabel, line, liveEnabled, mainLine, marketHash, outcomeOneName, outcomeTwoName, outcomeVoidName, participantOneId, participantTwoId, sportId, sportLabel, sportXeventId, status, teamOneName, teamOneScore, teamTwoName, teamTwoScore, type`. `totalBetSize` on a resting order is that one maker's own chosen order size -- visible depth, already reported in Section 2 -- not a venue-imposed cap.

**Conclusion:** book-side maximum-stake limits are marked **ABSENT** for both venues, structurally, not merely "not observed in this sample." No sportsbook or exchange stake-limit figure is asserted, estimated, or implied anywhere in this node's output.

---

## 5. What could not be established, summarized

- Cross-venue decision-to-executable latency for this capture window (non-overlapping T0 spans) -- `UNSUPPORTABLE`.
- Any reaction-time or lead-lag claim finer than the same-tape polling floor (`L_max` UNBOUNDED, clock skew unmeasured) -- `UNSUPPORTABLE`.
- The true SX Bet quote-change frequency finer than ~300s -- right-censored by our own poll floor; only a lower bound is supportable.
- Sportsbook or SX Bet maximum-stake limits -- `ABSENT` from every owned schema.
- Whether a hypothetical taker order would actually have filled at the modeled depth-walk price -- not claimed; SX Bet is peer-to-peer, resting liquidity is not guaranteed to persist.
- The exact real-world probability implied by SX Bet's `percentageOdds` fixed-point scale -- not independently re-verified against vendor documentation here; only relative, within-book comparisons were used.

## 6. Contradictions found

1. `EXCHANGE_CAPTURE/sxbet/HALT_USER_REQUIRED.md` (stale, claims zero rows captured) vs. the actual capture bytes (131 healthy cycles) -- resolved via `DECISION_LEDGER.jsonl` D035, but the halt document itself was never updated. See Section 0.
2. This node's generated contract names `REPORT.md`/`FINDINGS.json`; the direct dispatch instructions name `REPORT_BODY.md`/`EXECUTION_REALISM.json`. Followed the dispatch instructions. See Section 0.

## 7. Stop conditions -- none tripped by this node's own actions

No wager was placed, no order was simulated as placed, no staking advice was produced, and no account credential was used or required. The one legal/licensing question this node encountered (Section 0) was already resolved by a ledgered `D035` user ruling before this node ran; this node did not itself accept, resolve, or stretch any scraping/licensing risk. The cross-venue latency gap (Section 3) and the book-side-limits gap (Section 4) are reported as measurement gaps, not worked around or estimated past.

**Files behind every number above:** `inventory.py`, `depth_analysis.py`, `latency_analysis.py`, `quote_drift.py`, `final_summary.py` (run against `data/sxbet_capture/*.jsonl`, `data/sxbet_capture/state/sxbet_state.json`, and `data/market_snapshots/{snapshots.csv,poll_log.csv}` in the DATA worktree). Full structured output: `EXECUTION_REALISM.json` in this directory.