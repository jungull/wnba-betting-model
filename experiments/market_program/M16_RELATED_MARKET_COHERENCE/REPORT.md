# M16_RELATED_MARKET_COHERENCE — REPORT

**Materialized by the coordinator** from the node agent's returned text (the harness refuses
subagent-authored report files; same precedent as M03). Coordinator verification and corrections
are recorded in §7 at the end — read them before citing §4's contradiction list.

## Epistemic status (verbatim, per node contract)

DIAGNOSTIC MEASUREMENT. Tests whether related quotes jointly satisfy the no-arbitrage relations
the M00 taxonomy implies. An incoherence is a timestamped observation about quotes, not an
executable opportunity claim.

## 1. Inventory

Scripts: `inventory.py` → `inventory.json`; `coherence.py` → `COHERENCE.json`/`FINDINGS.json`;
stdlib-only (pandas/numpy/scipy verified absent before any analysis code was written).

**Live ladder — `data/market_snapshots/snapshots.csv`**: 3,152 rows, 4 games, 5 books, but only 4
market values, **all player props** (`player_assists/points/rebounds/threes`) — **zero**
`h2h`/`spreads`/`totals` rows. Root cause measured from `data/market_snapshots/poll_log.csv`: all
21 poll attempts against the game-level odds endpoint returned HTTP 200 with `n_rows_written=0`,
no rejects, no error text, while every per-event props poll wrote rows summing to exactly 3,152.
**The live ladder cannot supply this mandate's universe.** (Coordinator: independently confirmed —
see §7.2.)

**Historical archive — `featured_backfill.jsonl`**: 1,415 batch polls, 1,268 distinct events,
~3.9 polls/event, 2022-05-21 → 2026-08-01, 22 books; market-key counts spreads 45,618 / totals
44,482 / h2h 42,633. All `T1_VENDOR_ASSERTED` / `vendor_asserted_unwitnessed`.

**`props_discovery.jsonl`**: 1,240 batches, 870 events, 33% null payload; out of scope, unused.

**Working universe (reported honestly, not widened)**: one instant = `(event_id, bookmaker key,
batch requested_ts)` with h2h + spreads + totals **all** present from the **same book, same
poll**: **40,589 instances, 1,266 games, 21 books** — 88% of all (event, book, poll) keys carrying
any of the three carry all three. Two independently coded counting passes disagreed by <1%
(40,199 vs 40,589); the two most likely causes (duplicate event ids per batch, duplicate bookmaker
keys per event) were checked and ruled out; root cause unresolved and reported rather than hidden.
One book (`unibet`, distinct from `unibet_us`) contributes ~0 triples — directly observed in raw
JSON to quote only h2h + spreads, never totals.

## 2. Coherence relations tested

All cross-sectional within one poll batch. No timing, reaction, lead-lag or CLV claim anywhere.

**Relation A — favorite-sign coherence (model-free).**
`team(argmax(p_novig)) == team(argmin(spread_point))`. Raw disagreement 190/40,589 (0.47%).
Sample inspection found 150 of the 190 are moneyline exact pick'ems (`p_home == p_away == 0.5`)
where a strict argmax tie-break mechanically mislabels "no favorite" as "away favored" — not a
real flip. **Corrected genuine-disagreement rate: 40/40,589 = 0.099%**, thinly spread across
books, several books at exactly 0. Cross-quote latency window (D023 amendment-4 required field):
0.0 s on all 190 — vendor `last_update` identical across the three markets at capture.

**Relation B — normal-margin model cross-check.**
Margin ~ Normal(μ = spread magnitude, σ), with σ **self-calibrated from this archive only, never
from outcomes**: `median(μ / Φ⁻¹(p_fav))` = **12.54 points**. Model-implied P(favorite wins) vs the
book's own de-vigged moneyline: **median disagreement 1.30 pp**, p95 3.34 pp, p99 4.84 pp, max
35.9 pp; >5 pp on 0.90% of instances, >10 pp on 0.24%. Remarkably uniform across books (every book
with N ≥ 100 falls in 1.21–1.53 pp median) — **no book stands out as incoherent**. Flat by
hours-to-tip except the `post_commence_or_live` bucket (polled after scheduled tip — likely
postponed/live games), where it roughly doubles. **Sensitivity variant** (σ scaling with the
book's own total) makes the fit *worse* (2.42 pp median vs 1.30 pp), so the simpler constant-σ
model is not being artificially rescued.

**Relation C — cross-market vig consistency (descriptive; no pass/fail asserted).**
Median overround: h2h 4.60%, spread 4.76%, total 4.76% — near the standard −110/−110 baseline.
Spread↔total vig correlate tightly (Pearson 0.91); moneyline is more loosely coupled (0.73–0.75).

**Relation D — cross-book dispersion at the same instant (descriptive).**
4,599 multi-book instants; median spread range 0.5 pts, total range 1.0 pt, moneyline range
2.2 pp. 6.5% cross a stated (not validated) "large dispersion" flag. The single largest outlier
(37-point total range across 2 books) reads as a one-sided data-quality artifact, not genuine
disagreement — flagged as such rather than narrated as an opportunity.

## 3. Could not establish

1. Any reaction-time / stale-window / CLV claim — out of scope by design; nothing here is a timing
   claim even where hours-to-tip appears (that is our own request timestamp, not vendor-witnessed).
2. Whether A/B disagreements are exploitable — that is M21's mandate; not assessed here.
3. M05 linkage-key joins (see §7.1 — the agent's premise was wrong; joins used the archive's native
   `(event_id, book, batch requested_ts)` tuple).
4. Ground-truth calibration of Relation B against realized outcomes — deliberately out of scope
   (that would convert a coherence check into a calibration study).
5. The ~390-row reconciliation gap between the two counting passes (§1).

## 4. Contradictions found (as filed by the agent; two are corrected in §7)

1. Report/JSON filenames vs the harness (resolved: both `COHERENCE.json` and `FINDINGS.json`
   written with identical content; report materialized by the coordinator).
2. "M05 does not exist" — **incorrect, see §7.1.**
3. "M00's frozen contract does not exist" — **incorrect, see §7.1.** The substantive half of this
   item (the archive-shape mismatch vs M00's "813-game one-snapshot-per-game" description) stands
   and is routed in §7.3.

## 5. Stop conditions

No money, wager, credentials or scraping risk; zero live vendor calls; sealed results never
opened; no unsupported timing claim made. The bounded-final-state-archive question was flagged as
a borderline item rather than self-certified — coordinator disposition in §7.3.

## 6. Compressed summary

40,589 same-book same-poll instants (1,266 games, 21 books) from the historical archive; the live
ladder contributes zero. Favorite-sign coherence holds 99.9% of the time after correcting a
tie-artifact. A self-calibrated normal-margin model reproduces the books' own moneyline
probabilities to ~1.3 pp median, uniformly across books, with a ~1% tail beyond 5 pp. Cross-book
dispersion is modest with one likely single-book data artifact.

---

## 7. Coordinator verification and corrections

**7.1 Two "does not exist" findings are FALSE — worktree confusion, not missing artifacts.**
The agent read data from the DATA worktree and concluded the market-program nodes were absent.
Both exist in the program worktree and are committed:
`experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/` (`MARKET_PROGRAM_CONTRACT.md`,
`TAXONOMY.json`) and `experiments/market_program/M05_EVENT_MARKET_LINKAGE/`
(`DESIGN_BASELINE.md`, `linkage.py`, `fixtures.py`, `PROBE_RESULTS.json`, `real_tape_probe.py`,
`REPORT.md`, `TESTS.py`). The acceptance criterion invoking M05 linkage keys is therefore
**not** blocked upstream; it is unmet because this node joined on the archive's native tuple
instead. Recorded as an open item for the M16 follow-up rather than a repo gap. **Discipline
for future dispatches: state the worktree root explicitly for every read path.**

**7.2 The zero-row game-odds finding is CONFIRMED and is the operationally important result.**
Independently re-derived from `poll_log.csv`: 42 poll rows total — 21 game-odds polls, every one
HTTP 200 with `n_rows_written = 0`, and 21 props polls writing 118–169 rows each. Our live ladder
has been capturing **props only**; game lines are silently absent. This is a live-capture defect,
not an analysis limitation, and is routed to the remediation node created this session.

**7.3 Archive-shape mismatch: routed, not resolved here.** M00's prompt text describes an
"813-game one-snapshot-per-game archive"; what M16 measured is 1,268 events averaging ~3.9 polls
each. Both readings are preserved. Because every relation tested here is cross-sectional within a
single poll and makes no timing claim, the coordinator's disposition is that this analysis sits
inside M00's bounded uses; the numeric discrepancy is filed for M00 reconciliation and is NOT
treated as settled by this node.
