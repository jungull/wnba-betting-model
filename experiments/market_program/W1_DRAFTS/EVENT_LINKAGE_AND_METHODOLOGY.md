# EVENT LINKAGE AND METHODOLOGY — market_intelligence lane, W1 draft

**Status:** DESIGN ONLY. Nothing in this document is implemented, and nothing in it authorizes a fit,
a query, a purchase, or a wager. It binds *method*, not code.

**Authority:** D023_MARKET_PROGRAM_AUTHORIZED (2026-08-06), user amendments 2, 3, 4. Section C of
this document is the proposed **M00 contract ruling** on the final-state archive (amendment 2).
Sections A and B implement the linkage and timestamp-uncertainty discipline (amendments 3 and 4).
Section D defines the lane's hypothesis families under RESEARCH_CONTRACT_V1-style preregistration.

**Evidentiary basis (read-only, verified in P2B and D016):**
the P2B report (`experiments/player_program/stage2b/P2B_MARKET_ODDS_ELIGIBILITY/REPORT.md`),
D016 in `experiments/player_program/orchestration/DECISION_LEDGER.jsonl`, the capture-file headers
on the data branch (headers only — no rows were read for this document), and
`experiments/player_program/stage2a/V2_STOP_CONDITION.json` for the fold-degeneracy precedent.
Nothing under `stage2b/SEALED_RESULTS/` was read.

**Capture schemas this design consumes (headers only, data branch):**

| stream | file | header |
|---|---|---|
| odds (live) | `data/odds_capture/capture_log.csv` | `snapshot_utc, commence_time, home_team, away_team, bookmaker, market, outcome, point, price` |
| injuries | `data/injury_capture/injury_log.csv` | `capture_utc, report_date, game_date, team, player, status, reason, source` |
| news | `data/news_capture/news_items.csv` | `capture_utc, source, published_utc, title, url, summary_text, teams_mentioned, players_mentioned_raw` |
| props | `data/props_capture/master_props.csv` | `api_event_id, home_team, away_team, commence_time, bookmaker_key, market_key, player_name, line, over_price, under_price, snapshot_utc, last_update` |

Two facts about these streams are load-bearing and are treated as constraints, not annoyances:

1. **`capture_log.csv` carries no `game_id`** (P2B §10.2). Every linkage below therefore passes
   through a frozen entity-resolution map (§A.6). Resolution failure is a linkage failure, never a
   fuzzy match.
2. **The live poll grid is coarse and irregular.** The `live_*.json` filenames show roughly hourly
   polls during US daytime/evening with overnight gaps of ~11 hours (e.g. `...T030003Z` →
   `...T140012Z`) and at least one multi-hour daytime outage (2026-08-02, 03:00Z → 21:00Z). The
   uncertainty calculus in §B therefore derives intervals from the **actual poll log**, never from a
   nominal cadence.

---

## 0. Trust tiers for timestamps (the vocabulary everything else uses)

Every timestamp in this lane belongs to exactly one tier. The tier is recorded on the row and
propagates through every derived claim. A derived quantity inherits the **weakest** tier of any
input.

| tier | name | definition | admissible for timing claims? |
|---|---|---|---|
| **T0** | WITNESSED | Our process wrote the row at the moment of observation; file mtime tracks the embedded stamp (the P2B E4 signature: median 1.6 s). | Yes — with §B bounds. |
| **T1** | THIRD_PARTY_CONTEMPORANEOUS | A vendor recorded the snapshot at the asserted time and we retrieved it later; the vendor's contemporaneous recording is plausible but **unwitnessed by us and unfalsifiable from inside this repo** (P2B §10.1). The Odds API historical endpoint, if amendment-1 verification succeeds, lands here — not in T0. | Yes, but only with an explicit vendor-latency term, an explicit "vendor-asserted, unwitnessed" label on every claim, and never as the sole basis for an executability claim. |
| **T2** | RETROSPECTIVE_HARVEST | One or few pulls made long after the events described (the P2B E1–E3 signature: one snapshot per game, single 571-second download burst). The 813-game archive is T2. **Permanently CUTOFF_UNPROVEN for timing.** | **Never.** Bounded non-timing uses only — Section C. |

Amendment 1 (Odds API historical verification) is owned by another founding-wave member. The
interface this document commits to: whatever that verification returns, its rows enter as **T1 at
best**, and §B tells you exactly which terms widen when T1 data is used. Verification of *coverage*
does not upgrade *witness*.

---

## A. Deterministic event-to-quote linkage

### A.1 What an event is

An **event** is a first-seen state transition in one of OUR capture streams, keyed on OUR
`capture_utc` — never on a vendor's or a reporter's asserted time.

Formally, for a monitored entity (player, team, game) and a monitored state field:

- `t_seen` = the `capture_utc` of the first poll at which the new state is observed;
- `t_prev` = the `capture_utc` of the immediately preceding **successful** poll of the same stream
  (from the poll log, not the nominal schedule);
- the event's true occurrence time is **interval-censored**: `t_event ∈ (t_prev, t_seen]`.

An event is a tuple:

```
event_id            deterministic hash of (stream, entity_keys, old_state, new_state, t_seen)
stream              injury | news | props_line | odds_line | official_report | ...
report_id           groups all entity-level events emitted by one underlying report (A.4)
entity              resolved player_id / team_id / game_id via the frozen ER map (A.6)
old_state, new_state
t_prev, t_seen      the censoring interval, from the poll log
tier                T0 for our streams; T1 rows may define events only in T1-labeled analyses
severity_class      frozen taxonomy (e.g. OUT / DOUBTFUL / QUESTIONABLE / PROBABLE / AVAILABLE /
                    SUSPENSION / TRADE / REST / OTHER) — frozen before any linkage runs
```

Vendor fields like `published_utc` (news) and `last_update` (props) are **carried, never keyed on**.
They may appear only in the VENDOR_ASSERTED advisory channel of §B.5.

### A.2 What a quote is, and what a quote *change* is

A **quote series** is the ordered sequence of our polls for one key
`(game_id, bookmaker, market, outcome, line)` after entity resolution. Each poll of a series yields
one of: a price, an absence (market not offered / suspended), or a poll failure.

A **quote-change** is the first poll at which the series differs from its previous successful poll
(price moved, line moved, market appeared, market disappeared). Like events, quote-changes are
interval-censored: `t_change ∈ (t_prev_poll, t_seen_poll]`.

**In-play filter, unconditional:** any row with `snapshot_utc >= commence_time` is excluded from
every pregame series at the point of series construction. This is the P2B §7 defect (the incumbent
"last snapshot" rule selects in-play rows) made structurally impossible rather than policed.

### A.3 Window construction

All windows are anchored on the event's censoring interval `(e_lo, e_up] = (t_prev, t_seen]`, in OUR
clock. For each quote series relevant to the event (relevance = same game, plus player-market series
for the named player), the linkage emits:

| window | definition |
|---|---|
| `PRE` | the last quote-change whose interval `(q_lo, q_up]` satisfies `q_up <= e_lo` — provably pre-event |
| `POST_FIRST` | the first quote-change with `q_lo >= e_up` — provably post-event |
| `H+1, H+2, H+5, H+10, H+15, H+30, H+60` (minutes) | the last quote observation with `q_up <= e_up + h` — "state of the series no later than h minutes after the event was at latest observable" |
| `CLOSE` | the last pregame quote observation (`snapshot_utc < commence_time`) |

Three hard rules:

1. **Ambiguity is excluded, not resolved.** A quote-change whose interval overlaps the event
   interval (`q_up > e_lo` and `q_lo < e_up`) is **AMBIGUOUS**: it cannot be proven pre- or
   post-event. It is assigned to neither side. If the `PRE` slot can only be filled by an ambiguous
   change, `PRE` is empty and the linkage record is downgraded (A.7).
2. **Horizon windows narrower than the grid are vacuous and say so.** If the series' local poll
   spacing around the anchor exceeds `h`, the `H+h` window is emitted as `UNRESOLVED_AT_GRID`, not
   as a copy of the nearest observation. At the current ~60-minute cadence, `H+1` through `H+30`
   will be `UNRESOLVED_AT_GRID` almost always — that is the honest output, and it is the standing
   argument for the amendment-3 high-frequency capture, not a reason to blur windows.
3. **Windows never cross `commence_time`.** A horizon that would extend past commence truncates to
   `CLOSE` and is flagged `TRUNCATED_AT_COMMENCE`.

### A.4 Overlapping events and multi-player reports

- **Isolation predicate.** Event E is *isolated at horizon h* for a series iff no other event
  linked to the same series has `(e_lo − g, e_up + h)` overlapping E's corresponding span, where `g`
  is a frozen guard (default: one poll interval). Attribution of a quote move to E at horizon h is
  admissible **only if E is isolated at h**. Otherwise the linkage row is marked `CONFOUNDED@h`. An
  event can be isolated at `H+5` and confounded at `H+60`; the flags are per-horizon.
- **Multi-player reports.** One report naming k players emits k player-level events sharing one
  `report_id`. Player-specific series (props) link to the player-level event. Game-level series
  (spread, total, h2h) link to the `report_id` as a single composite event. **Game-level analyses
  cluster on `report_id`** — one report is one observation, never k.
- **Same-poll pile-ups.** Multiple events first seen in the same poll of the same stream share
  identical intervals and are mutually confounded at every horizon for shared series; only
  series exclusive to one of them (that player's own props) escape.

### A.5 Suspensions, reopenings, out-of-hours announcements

- **Suspension** = a series present at poll p−1 and absent at poll p (game still pregame):
  interval-censored suspension start. **Reopening** = present again after absence. If a suspension
  interval overlaps or covers the event interval, the linkage row is classed
  `SUSPENDED_ACROSS_EVENT`: the reopening quote is recorded, but the row is **excluded from
  continuous reaction-latency estimates** (the price path during suspension is unobservable) and
  routed instead to family F6, where suspension behavior is itself the endpoint.
- **Out-of-hours announcements.** An event whose interval spans a poller gap (overnight ~11 h, or
  an outage) is simply a wide-interval observation: `(t_prev, t_seen]` with width in hours. It is
  **never patched** to "next morning", never midpointed, and never narrowed by a reporter's
  asserted time. It is usable in the §B survival framing exactly as censored, and unusable in any
  horizon window narrower than its own width.

### A.6 Entity resolution as a frozen precondition

Linkage requires `(home_team, away_team, commence_time) → game_id` and
`player_name → player_id` maps. These are **versioned, frozen, and hashed before any linkage run**;
the linkage config records the map hash. No fuzzy matching at link time; no manual per-row fixes
after results are visible. An unresolved name is a linkage failure with reason
`ENTITY_UNRESOLVED` — fixing the map produces a new map version and a full re-run, not a patch.

### A.7 The exclusion rule and reason codes

A linkage record enters **causal/latency analyses** only with status `TRUSTED`. Every other record
is retained (nothing is deleted) with exactly one primary reason code:

`ENTITY_UNRESOLVED · AMBIGUOUS_PRE · CONFOUNDED@h · SUSPENDED_ACROSS_EVENT ·
UNRESOLVED_AT_GRID · POLL_GAP_EXCEEDS_HORIZON · IN_PLAY_ONLY · TRUNCATED_AT_COMMENCE ·
TIER_INSUFFICIENT (any T2 input) · CLOCK_UNBOUNDED (no skew measurement for the capture run)`

Excluded records are **excluded, never patched**: no imputation of the missing side, no borrowing a
quote from a correlated book, no narrowing an interval by assumption. Every published analysis
reports the count and reason distribution of its exclusions next to its n.

### A.8 Determinism

The linkage is a pure function: `link(event_table, quote_table, poll_log, er_map, config) → links`.
Config (horizons, guard, severity taxonomy, ER map hash) is frozen and hashed before the first run
whose output anyone sees. Same inputs, same bytes out. There is no interactive mode.

---

## B. Timestamp-uncertainty calculus (amendment 4)

### B.1 The three terms

Every observed instant in this lane carries three uncertainty terms, each with a named source:

1. **Poll interval Δ** — from the poll log: the gap between the observing poll and the previous
   successful poll of that stream. Not nominal cadence. Currently ~3600 s daytime, ~40,000 s
   overnight for odds; injury/news cadences read from their own logs.
2. **Vendor latency L ∈ [0, L_max]** — the lag between a book changing a price and the vendor
   surface reflecting it. `L_max` per vendor is a **declared, sourced bound** (vendor documentation,
   or measured by a future paired-capture experiment); until a vendor has a sourced bound, its
   `L_max` is recorded as `UNBOUNDED` and every downstream claim inherits `CLOCK_UNBOUNDED`-style
   inadmissibility for fine-grained statements. For T1 historical data, `L` additionally includes
   the vendor's own recording pipeline and is strictly a claim.
3. **Clock skew ε** — `|our clock − reference| ≤ ε_max`, measured and logged per capture run (NTP
   offset check at poll time). A capture run without a skew measurement taints its rows
   `CLOCK_UNBOUNDED`.

The **true availability interval** for an observation first seen at poll `t_seen` with previous
poll `t_prev` is:

```
t_true ∈ [ t_prev − L_max − ε_max ,  t_seen + ε_max ]
```

(the change could have happened just after the previous poll's vendor-surface state was formed, or
as late as the observing instant).

### B.2 Reaction-time bounds

A reaction time is a difference of two intervals and is reported **only** as an interval. For event
interval `[e_lo, e_up]` and quote-change interval `[q_lo, q_up]` (both already widened per B.1):

```
R ∈ [ max(0, q_lo − e_up) ,  q_up − e_lo ]
```

Mandatory fields on **every** reaction-time claim, with no exceptions, per amendment 4:

```
[t_lower, t_upper]            the interval itself
poll_interval_event           Δ of the event stream at the observation
poll_interval_quote           Δ of the quote stream at the observation
vendor_latency_bound          value and source, per vendor touched (or UNBOUNDED)
clock_skew_bound              ε_max and measurement method
censor_type                   interval | right (never "exact")
tier                          min tier of inputs
n_trusted / n_excluded        with reason-code distribution
```

### B.3 The sharpness prohibition

**No point estimate may be stated at a precision finer than the measurement grid.** The grid for a
claim is `G = Δ_event + Δ_quote + L_max(all vendors) + 2·ε_max`. Forbidden: "the book repriced in
4.2 minutes" when G ≈ 60 minutes. Permitted: "repricing occurred within [0, 71] minutes of the
announcement (grid 61 m: poll 60 m + latency bound 30 s + skew 30 s)". Summary statistics over many
observations do not escape this: a mean of interval-censored data is reported as an interval or as
a model-based estimate under §B.4 with the model named, never as a bare number.

**Comparative claims** ("book A reacts faster than book B by δ") are admissible only when δ exceeds
the combined grid at the stated confidence; otherwise the pre-registered verdict is
`INDISTINGUISHABLE_AT_GRID` — a legitimate, publishable outcome, not a failure.

### B.4 Interval-censoring representation and the survival framing

Daily-cadence streams (injury `report_date` grain) yield intervals of ~24 h; overnight gaps yield
~11 h; the current odds poller yields ~1 h. The representation and estimators that consume this
honestly:

- **Observation** = `(L, R, censor_type, grid_id, covariates)` where `[L, R]` is the §B.2 interval;
  right-censored when no repricing was observed before `CLOSE` (`R = +∞`); `grid_id` identifies the
  poll-regime stratum (daytime-hourly / overnight / outage / future high-frequency).
- **Nonparametric:** Turnbull NPMLE for the reaction-time distribution — the estimator is defined
  on exactly this data shape and returns probability mass on the innermost intervals it can
  identify, which *is* the honest statement of what the grid resolves.
- **Parametric:** AFT families (log-logistic, Weibull) fit by the interval-censored likelihood
  `∏ [S(L_i) − S(R_i)]`, never by imputing a time inside the interval.
- **Group comparisons:** Finkelstein's interval-censored score test or likelihood-ratio tests on
  the parametric fits, stratified by `grid_id` so that a poll-regime difference can never
  masquerade as a book difference.
- **Forbidden explicitly:** midpoint imputation; treating `t_seen` as the event time; Kaplan–Meier
  on midpoints; any estimator that requires exact times. In our regime interval widths are
  comparable to the latencies of interest, which is precisely where midpointing is most biased.

### B.5 The vendor-asserted advisory channel

Vendor-asserted stamps (`last_update`, `published_utc`, and T1 historical `odds_snapshot_timestamp`)
may be used to compute a **parallel, advisory** set of narrower intervals, reported only alongside
the witnessed bounds and always labeled `VENDOR_ASSERTED`. Advisory numbers never enter a headline,
a gate, a preregistered endpoint, or a decision. The two channels are never averaged. This is the
standing home for amendment-1 data: if Odds API historical coverage verifies, its point-in-time
stamps power the advisory channel and T1-labeled analyses under §0 — they do not sharpen a T0
witnessed bound.

---

## C. Bounded uses of the final-state archive — the M00 contract ruling (amendment 2)

**Object ruled on:** `data/drive_masters/master_odds.csv` (20,004 rows, 813 games, event dates
2022-05-21 → 2025-07-03) and, where noted, the two extension files (406 games, 2025–2026). Per P2B
(coordinator-corroborated in D016): exactly one distinct snapshot per game across all 813 games;
snapshots sit on a :25/:55 grid at a modal 64–65 minutes before commence; the harvest was a single
571-second retrospective burst on 2026-07-30; the vendor-asserted stamps are internally consistent
but unwitnessed and unfalsifiable from this repository. Tier: **T2**.

**Ruling shape:** the archive is neither worthless nor a timing record. It is a *cross-sectional
census with an unverified timing label*. Uses are enumerated as M00-Ux classes. Any market-lane
artifact touching the archive must cite the use class and reproduce that class's caveat text
**verbatim**. A use not enumerated here is prohibited until this contract is amended.

### C.1 Permitted uses

**M00-U1 — Book / market / season coverage census.** Which bookmakers, markets, seasons, and games
appear; coverage rates (e.g. the P2B §5 table); fan-out structure (22 bookmakers × teams).
> *Caveat (verbatim):* "Coverage figures derive from a retrospective single-snapshot harvest
> (T2). They describe what the vendor could return in July 2026 about past games, not what was
> observable at any pregame instant. Presence in this census is not evidence a price was available,
> firm, or executable at any particular time."

**M00-U2 — Vig structure and no-vig calibration against realized outcomes, unknown-time.**
Overround by book/market/season; no-vig implied probabilities calibrated against realized results —
as a property of *the vendor's asserted ~T−64m snapshot*, whatever instant it truly reflects.
> *Caveat (verbatim):* "Calibration is of a snapshot whose capture time is vendor-asserted and
> unwitnessed (P2B: CUTOFF_UNPROVEN). Results characterize an unknown-time pregame price level and
> must not be read as closing-line calibration, opening-line calibration, or calibration at T−64
> minutes. No CLV, timing, or line-movement inference may be built on this result."

**M00-U3 — Settlement-rule and identifier inventory.** Team-name spellings, market keys, price
formats, outcome labeling, push/settlement conventions — input to the frozen ER map (§A.6) and
schema design.
> *Caveat (verbatim):* "Identifier and settlement conventions are as of the 2026-07-30 harvest and
> may not reflect conventions in force during the seasons the rows describe."

**M00-U4 — Coarse cross-season price-level context.** Descriptive distributions of spread
magnitudes, totals levels (2025+ only — the 2022-reaching archive has no totals, P2B §6), and
price dispersion across books, by season. Descriptive display and sanity-checking only; never a
feature, never a benchmark.
> *Caveat (verbatim):* "Season-level price distributions from a T2 harvest describe one unknown-time
> snapshot per game. Cross-season comparisons may confound market drift with harvest-selection
> effects; the 2022 season's 75.3% coverage has an undocumented selection rule (P2B §10.3)."

**M00-U5 — Schema fixtures and test corpora.** Real-shaped rows for parser tests, linkage
dry-runs, and ER-map tests — with **timestamps replaced by synthetic values** in any fixture used
to test timing logic, so a passing test can never be secretly leaning on T2 stamps.
> *Caveat (verbatim):* "Fixture data only. Timing fields are synthetic or T2 and carry no
> evidentiary weight."

**M00-U6 — Prior elicitation and power analysis for prospective designs.** Variances of prices
across books, typical overrounds, book counts per game — as inputs to sample-size and
detectability planning for the prospective (T0) experiments of Section D.
> *Caveat (verbatim):* "Priors elicited from a T2 harvest inform design only. They are superseded by
> the first adequately-powered T0 measurement and are never combined with T0 data in a single
> likelihood as if exchangeable."

### C.2 Prohibited uses — what one snapshot per game can NEVER support

No timing, latency, lead-lag, reaction, or sequencing claim of any kind; no CLV or
closing-line-value computation (the snapshot is not a close and there is no open); no stale-line or
stale-window claim; no open-vs-close movement (there is exactly one snapshot; F10 is structurally
impossible on this archive); no intra-day or event-response dynamics; no executability, liquidity,
or "this price was gettable" claim; no use as a feature or benchmark in any predictive model in
either lane (the possession-lane exclusion in P2B stands and is not reopened here); no treatment of
`odds_snapshot_timestamp` as witnessed for any purpose. The extension files additionally carry
232 + 338 in-play rows (P2B §7): **every** M00 use touching the extensions filters
`snapshot < commence` first, including the census.

**Enforcement hook:** M00-class artifacts carry a machine-readable header
(`m00_use_class`, `caveat_hash`). A missing or mismatched caveat hash fails review; a T2 field
reaching a timing claim is a Severity A methodology breach.

---

## D. Hypothesis families, preregistration, and the multiplicity budget

### D.1 The families

Ten families, frozen as the lane's hypothesis universe. Adding a family later is permitted;
doing so retroactively over already-seen data is not (D.3).

| id | family | primary endpoint (one per family) | unit / clustering | data floor |
|---|---|---|---|---|
| F1 | Injury-report latency | Interval-censored time from injury event to first quote-change in the affected game's series | event, clustered by `report_id` | T0; TRUSTED links only |
| F2 | Book lead-lag | Ordering of first-mover book on TRUSTED isolated events, per B.3 comparability rule | event × book pair | T0; both books' grids bounded |
| F3 | Arbitrage windows | Existence/persistence (in poll-grid units) of cross-book no-vig arb at simultaneous polls | poll × game × market | T0; same-poll quotes only |
| F4 | Middles | Existence/persistence of middle-able line pairs at simultaneous polls | poll × game × market | T0; same-poll quotes only |
| F5 | Consensus residual | Predictive content of book-vs-consensus deviation for later consensus movement | game × book | T0 |
| F6 | Suspension / reopening | Reopen-vs-presuspension displacement; suspension duration (interval-censored) | suspension episode | T0 |
| F7 | Cross-market coherence | Internal consistency of spread / total / h2h / props surfaces within a book at one poll | poll × game | T0; T2 permitted for *descriptive* U4-style context only |
| F8 | Player-value residual | Props line vs frozen player-model projection: residual structure (never a wager signal without its own future contract) | player × game | T0 props + a **frozen, hashed** projection published before commence |
| F9 | Vendor residual | Witnessed-vs-vendor-asserted stamp discrepancies (`last_update` vs `capture_utc`); vendor latency measurement that would *source* the B.1 L_max bounds | poll × vendor | T0; this family is the only place VENDOR_ASSERTED stamps are the object rather than advisory |
| F10 | Open / close | Movement from first-witnessed quote to close | game × book × market | T0 with witnessed opens only — **structurally impossible on the T2 archive**, and "first-witnessed" is stated as such, not as "the open", unless capture provably began before the book opened the market |

F3/F4 persistence claims are denominated in poll-grid units ("survived ≥1 poll interval"), never in
minutes finer than the grid, and carry no executability claim (prohibited-class under C.2 logic:
we witness prices, not fills).

### D.2 Preregistration record (per family, per season-window)

Frozen and hashed **before any result of the analysis is visible**, mirroring
RESEARCH_CONTRACT_V1 and GATE_INVOCATION_CONTRACT §4 discipline:

```
family_id, version
primary_endpoint          exactly one; everything else is exploratory and labeled so
estimator                 from the B.4 approved set, named in advance
grid_strata               poll-regime strata and how they enter
inclusion_rule            TRUSTED-only; reason-code exclusions predeclared
alpha_allocation          from the lane budget (D.3)
minimum_n                 below it, the registered verdict is UNDERPOWERED, not a smaller claim
degeneracy_fallback       frozen numeric trigger and action for strata that come up empty or
                          zero-variance (the S7 / P2B-SC3 lesson: pooled-healthy, stratum-degenerate
                          must FAIL or hit a pre-frozen fallback — "there is no third option")
stop_conditions           what halts the family and escalates to the coordinator
```

### D.3 Multiplicity budget

- One lane-level budget per season-window, split across families **in the registration, before any
  data from that window is unsealed**; unspent budget does not roll forward.
- One primary endpoint per family per window. Secondary analyses are exploratory, reported as
  such, and can only *generate* a registration for the next window — never a claim in this one.
- A family added mid-window starts at the **next** window boundary with fresh data; no
  retro-registration over seen data.
- Negative and `INDISTINGUISHABLE_AT_GRID` and `UNDERPOWERED` verdicts are published with the same
  prominence as positives; the registration record is the commitment device.
- Raw outputs frozen and hashed before review (the D016 pattern), and an independent verifier runs
  before any `node_passed`.

### D.4 Standing constraints inherited by every family

TRUSTED-linkage-only (§A.7); full amendment-4 field set on every reaction-time claim (§B.2);
sharpness prohibition (§B.3); tier labels on every table (§0); T2 confined to M00 classes (§C);
in-play exclusion at series construction (§A.2); `report_id` clustering (§A.4); no possession-lane
artifact modified or delayed, and the P2B §8 model-identity question remains open and is **not**
reopened by anything in this lane.

---

*End of W1 draft. Proposed next actions for the coordinator: (1) adopt §C as the M00 contract
ruling; (2) circulate §A/§B to the capture owner so the poll log, skew measurement, and ER-map
freeze become capture-side requirements; (3) accept §D.1 as the frozen family universe for the
first registration window.*
