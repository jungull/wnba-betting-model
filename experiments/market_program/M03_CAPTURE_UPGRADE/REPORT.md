# M03_CAPTURE_UPGRADE — cadence measured, latency fields specified, quota costed

**PROSPECTIVE CAPTURE INFRASTRUCTURE.** Creates no historical evidence and repairs no
historical gap. Every week without the upgraded tape is a week of event studies that can never
be run.

Everything below is measured by [`s01_measure.py`](s01_measure.py) and re-derivable by running
it. Tests are in [`TESTS.py`](TESTS.py) (32 checks); the schema and its reference implementation
are in [`capture_schema.py`](capture_schema.py).

---

## 1. Cadence, measured (criterion 1)

Odds capture, 2026-07-30 → 2026-08-22, **524 captures over 23.1 days**:

| era | n gaps | median gap | p90 |
|---|---|---|---|
| before 2026-08-19 | 170 | **60.0 min** | 60.2 |
| five-minute era | 353 | **5.0 min** | 15.0 |

The two eras are reported separately on purpose. Averaged together they would produce a single
figure describing neither.

## 2. Coverage against the T−24h → final requirement

Per game, keyed on (home, away, ET game-date), scored against each game's latest observed tip:

| | |
|---|---|
| games | 58 |
| captures inside T−24h..tip | median **14**, p10 **5**, max 117 |
| **games with zero in-window** | **4 (6.9%)** |
| closest capture to tip | median **14.0 min**, p90 **993.8 min** (16.5 h) |
| earliest capture before tip | median 35.2 h |

The requirement is **partially met**. Median coverage is adequate; the tail is not — for one game
in fourteen there is no capture at all inside the final 24 hours, and for one in ten the last
capture is over 16 hours before tip. That is the sleep-coverage limit (D154) again, not a
polling-rate problem: **the machine being awake is the binding constraint**, and no cadence
change fixes it.

## 3. Tip drift — a finding that arrived as a bug

Grouping games on exact `commence_time` **split single games into several**, because the vendor
revises tip times. One game appeared as `@23:30` with 214 captures and `@23:32` with 1. The naive
grouping then reported *"35.2% of games have zero in-window capture"* — an artifact, and one
that would have read as a serious coverage failure.

Measured properly:

| | |
|---|---|
| games | 58 |
| **games whose `commence_time` was revised** | **43 (74.1%)** |
| spread when it moves | median **5.0 min**, max **30.0 min** |

**Three-quarters of games have a tip time that moves.** This is why a point-in-time tip rule must
compare an observation against the tip **as reported at that moment**, never against the final
tip — which is exactly what `resolve_tip_times` does, and M35's reading of it is vindicated here.

## 4. Quota, costed against the real tier (criteria 1 and 5)

Cost models taken from the capture scripts themselves: odds = 1 request × 3 markets × 1 region =
**3 credits/run**; props = `/events` free, then each event × 4 markets × 1 region.

| | |
|---|---|
| odds | 524 runs × 3 = 1,572 |
| props | 262 event-fetches × 4 = 1,048 |
| **observed, 23.1 days** | **2,620 credits** |
| **projected** | **3,407 / 30d = 3.41% of the 100,000 tier** |

Games per day is **measured**, not assumed: mean **2.91**, max **6** over 94 game-days of the
2026 season. An assumed 5.0 would have been **72% too high** — the difference between a design
that fits and one that appears not to.

### Design envelope (odds at 5-min always; props targeted)

| option | expected/30d | worst-day/30d |
|---|---|---|
| B: props 15-min in T−6h..tip | 34,315 (34%) | 43,200 (43%) |
| **D: props 5-min in T−3h..tip** | **38,512 (39%)** | **51,840 (52%)** |
| C: props 5-min in T−6h..tip | 51,105 (51%) | 77,760 (78%) |
| E: C + 20 burst fetches/game | 58,100 (58%) | 92,160 (92%) |
| naive: props 5-min **continuous** | 126,659 (**127%**) | — |

**Recommendation: D as the base, with event-driven bursts on top.** It sits at 39% expected and
52% on a six-game day, leaving genuine headroom for bursts. Option E is inside the tier on
average but reaches 92% on a worst-case day, which is not a margin worth running on.

**Naive continuous polling does not fit — 127% of the tier.** That is the whole reason polling
must be *targeted* rather than uniformly fast.

**No purchase is required.** Nothing here spends money, so no USER_REQUIRED line item is raised
to M02B (criterion 5).

## 5. The latency fields (criterion 3)

### The defect, measured rather than asserted

`props_capture_daily.py:197` takes one `snapshot_utc` at the top of `main()`, **before** the
events list is fetched and before any request is issued, then writes it to every row of the
cycle. So `snapshot_utc ≤ true retrieval time`, and for a cutoff question that is the
**optimistic** direction — it can admit a quote whose true retrieval fell after the cutoff. The
odds capture has the same shape.

Measured exposure today is **zero** (M36 s02: 0 of 10,285 quotes wrongly admitted at T−90m),
because the cadence is too coarse to put anything near the boundary.

**That is the argument for fixing it now, not later.** Section 4 of this node proposes tightening
the cadence — which is precisely the change that would make this defect start to bite.

### The pattern already exists in this repository

The **injury capture does it correctly**, carrying `attempted_ts_utc` alongside
`retrieval_ts_utc`, plus vendor-side `doc_last_modified_utc`. Nothing needs inventing; the odds
and props captures need to adopt what the injury capture already does.

### Schema

| field | meaning |
|---|---|
| `fetch_requested_utc` | stamped immediately **before** the HTTP request |
| `fetch_returned_utc` | stamped immediately **after** the response arrives |
| `vendor_reported_utc` | the vendor's own timestamp (`last_update`) |
| `vendor_latency_bound_s` | `fetch_returned_utc − vendor_reported_utc` |
| `first_seen_utc` | earliest `fetch_returned_utc` for this exact (key, payload); never revised down |

The request/return pair **brackets** the true retrieval instant, which is what makes a cutoff
decision fail-closed: use `fetch_returned_utc`, and a quote is admitted only if it was
demonstrably in hand by then.

**Additive and reversible (criterion 7):** `snapshot_utc` and `last_update` are retained
unchanged and keep their positions, so every current consumer keeps working and the change
reverts by ignoring the new columns. **No running capture script is modified by this node** — its
write scope is its own directory, and `capture_schema.py` is a specification plus a reference
implementation for the capture to import.

**No backdating (criterion 4):** `first_seen_utc` is monotone per key. Re-observing an unchanged
payload leaves it alone; a changed payload becomes a **new record**, never an edit. Timing fields
are excluded from the payload digest — otherwise every cycle would append a spurious record and
`first_seen_utc` would mean nothing.

## 6. Event-driven bursts (criterion 2)

Triggers are the existing first-seen injury/news capture events. The injury tape already records
`game_time_et` beside `retrieval_ts_utc` and arrives at a **22.8-hour median lead** (M35), so it
is available early enough to drive a burst rather than merely to explain one afterwards.

Burst budget is the headroom between option D (52% worst-day) and a 75% ceiling — roughly
**23,000 credits/month**, or about 20 extra event-fetches per game per day at the measured
game rate. Wiring is specified, not deployed: deployment touches the running captures, which is
outside this node's write scope.

## 7. Tests

32 checks, all passing, in five groups: schema additivity, the fetch bracket, no-backdating,
quota arithmetic, and claims about the live archives.

**Every invariant was tamper-tested**, because this programme has twice shipped checks that could
not fail (D171):

| tamper | result |
|---|---|
| allow `first_seen_utc` to be overwritten | 3 checks fail |
| drop a required field from the schema | 1 check fails |
| stamp `requested` after the call | 2 checks fail |

One subtlety worth carrying forward. When `first_seen_utc` was removed from
`REQUIRED_TIMING_FIELDS`, the positive check *"all five required timing fields present"* still
**passed** — it validates the schema against the same constant that was edited, so it cannot
detect the constant shrinking. Only the **negative** check caught it. A positive assertion
against a mutable constant is a check that grades its own homework.

## What this node does not do

- **It changes no running capture.** Criterion 7 requires the upgrade be additive and reversible
  with existing jobs still running; deployment is a separate, scoped act.
- **It does not fix the coverage tail.** 6.9% of games with no in-window capture is a
  machine-uptime problem (D154), and no schema or cadence change addresses it.
- **It makes no timing claim about historical data.** The new fields exist only from the moment
  they are deployed; every archived row keeps the weaker single stamp, and any timing claim over
  historical rows must still carry that limitation (D023 amendment 4).
- **It does not measure whether faster capture is worth anything.** That is M08's question, and
  M08 is BLOCKED on M07_BOOK_LEAD_LAG.
