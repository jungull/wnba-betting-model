# MARKET_PROGRAM_CONTRACT — constitution of the market_intelligence lane

**Node:** M00_MARKET_PROGRAM_CONTRACT · **Version:** 1.0.0 · **Date frozen:** 2026-08-06
**Machine-readable companion:** `TAXONOMY.json` (same directory; where prose and JSON disagree, the JSON is a defect to be fixed by amendment, never silently reconciled)

**Epistemic status:** CONTRACT. Freezes what the market lane may claim and how claims are labelled. It is a specification, not evidence: it decides no signal's fate and admits no data source. Every other market node cites it; a market claim that cannot be stated in this contract's vocabulary is not a claim this program makes.

---

## §0. Authority, citations, and the non-relitigation clause

### §0.1 D023 — lane authorization and the four user amendments (cited verbatim)

From `experiments/player_program/orchestration/DECISION_LEDGER.jsonl`, decision `D023_MARKET_PROGRAM_AUTHORIZED` (ts 2026-08-06T15:51:29Z), ruling quoted verbatim:

> "AUTHORIZED with four user amendments, 2026-08-06: (1) VERIFY The Odds API historical coverage before concluding no historical tape exists - the user believes historic data should be available and declares it critical to the market research arm; if absent there, acquiring historical point-in-time data by another route becomes a program priority. (2) PRESERVE BOUNDED USES for the existing final-state odds archive - do not declare all historical analysis worthless; the lane contract must enumerate what one-snapshot-per-game data honestly supports and what it can never support. (3) The IMMEDIATE CRITICAL PATH is high-frequency live capture, event-to-market linkage, and competitor projection archiving - ahead of retrospective studies. (4) Every future reaction-time claim must carry EXPLICIT timestamp uncertainty and vendor latency terms. Lane market_intelligence is created under the existing graph engine with all standing governance; no purchases, no wagers, no credentials without USER_REQUIRED gates; the possession critical path is never delayed."

This contract discharges amendment (2) in §5 and freezes amendment (4) lane-wide in §6. Amendments (1) and (3) are owned by other founding-wave nodes; this contract binds how their outputs enter evidence (tier rules, §4) but does not perform them.

### §0.2 D024 — execution policy (cited, encoded in §7)

Decision `D024_EXECUTION_MODE_LADDER_AND_VENUE_POLICY` (ts 2026-08-06T16:04:13Z) adopted the four-mode execution ladder and venue policy synthesized in `W1_DRAFTS/VENUE_EXECUTION_RESEARCH.md` (sha256 `9aedd0d178a1767efd43b9c647cf1dbda97e29e2635bae28fd27b976dce3dd6b`). §7 encodes it as lane law.

### §0.3 D016/P2B — settled adjudication, never relitigated

Decision `D016_P2B_COORDINATOR_CORROBORATION` (ts 2026-08-06T13:05:52Z) established, from bytes: `master_odds.csv` holds 20,004 rows over 813 games with exactly ONE distinct snapshot per game (min=median=max=1); the harvest was a single retrospective burst (292 files, mtimes spanning 571 seconds on 2026-07-30); the archive is **permanently CUTOFF_UNPROVEN** for timing. **No market-lane node may reopen, re-examine, or relitigate this adjudication.** New evidence about *other* data sources (e.g. amendment-1 verification of The Odds API historical endpoint) creates new rows under new tiers; it never rehabilitates the T2 archive's timing status.

### §0.4 Baseline methodology adopted by reference

`W1_DRAFTS/EVENT_LINKAGE_AND_METHODOLOGY.md` (sha256 `5d91f6d36c15b14fa57ef070a544dc4ca2df876f4b217c0fafa667ee1d13854d`, working-tree bytes at contract time) is this lane's methodology baseline: its §0 trust tiers (T0/T1/T2), §A deterministic linkage, §B timestamp-uncertainty calculus, and §D hypothesis families F1–F10 with preregistration and multiplicity budget. Its Section C is ratified verbatim in §5 below.

---

## §1. The opportunity taxonomy — FROZEN

Six classes. Every market-lane claim of opportunity names exactly one class. A signal that fits no class is not an opportunity claim this program makes.

**Reserved-term rule:** the word **"arbitrage"** may be used for class 1 only. Calling anything else arbitrage — a middle, a stale line, a model edge, an unmatched-poll price pair — is a Severity A vocabulary breach.

### 1.1 `TRUE_CROSS_BOOK_ARBITRAGE`
- **Definition:** A set of wagers across two or more venues, **simultaneously executable at witnessed prices**, whose combined return is locked positive in **every** settlement outcome after applying each venue's own settlement rules (push handling, void/DNP rules, dead-heat, listed-player rules). Nothing else may use the word.
- **Mechanism that would make it real:** venues reprice asynchronously and hold mutually inconsistent prices long enough for both sides to be struck.
- **Falsified by:** same-poll cross-book combinations (family F3, same-poll quotes only) never positive after settlement-rule alignment; or paper-positive combinations that never survive the simultaneity requirement or persist ≥1 poll interval. Persistence is denominated in poll-grid units, never minutes finer than the grid, and carries no executability claim without the `EXECUTION_FEASIBLE` label.

### 1.2 `MIDDLES_AND_DISLOCATIONS`
- **Definition:** Line pairs where both wagers can win simultaneously (middles) or related markets within/across books are mutually inconsistent beyond combined vig (dislocations). Positive expectation is probabilistic, never locked. Not arbitrage.
- **Mechanism:** asynchronous line moves leave straddleable gaps; correlated markets are repriced by independent processes.
- **Falsified by:** F4/F7 endpoints null — middle-hit frequency consistent with no informational content; gap distributions explained by vig and discretization.

### 1.3 `STALE_LINE_DELAYED_REACTION`
- **Definition:** A venue's quote provably lags an information event or other venues' repricing, leaving a window in which the pre-event price is still offered post-event.
- **Mechanism:** heterogeneous, finite reaction latencies across books to injury/news/lineup events.
- **Falsified by:** interval-censored reaction analysis (F1/F2, TRUSTED links only) returning `INDISTINGUISHABLE_AT_GRID` or showing no post-event persistence of PRE-window prices. Every claim in this class is a reaction-time claim and carries the full §6 field set. **This class can never be supported by the T2 archive (§5).**

### 1.4 `MODEL_VS_MARKET_VALUE`
- **Definition:** The fundamental system's frozen, pre-commence, hashed projection diverges from the market-implied value, and the divergence predicts realized outcomes better than the no-vig market does.
- **Mechanism:** the market misprices fundamentals that our frozen model captures.
- **Falsified by:** residual (F8-style, frozen projection published before commence) shows no predictive content for realized outcomes; calibration no better than the no-vig market at matched cutoffs.

### 1.5 `THIRD_PARTY_PROJECTION_VALUE`
- **Definition:** Third-party (vendor/competitor) projections, archived at disciplined cutoffs, carry predictive content beyond the market and/or beyond our own model at matched rungs.
- **Mechanism:** specific vendors incorporate information (lineups, minutes, usage) faster or better than books reprice.
- **Falsified by:** matched-cutoff benchmarks (same `capture_rung`, same `ladder_run_id` — never mixed rungs) show no incremental accuracy over market-implied or incumbent comparators.

### 1.6 `PURE_MICROSTRUCTURE`
- **Definition:** Exploitable regularities in quote dynamics themselves — suspension/reopening displacement, book-specific update rhythm, overround pumping around events — requiring no fundamental opinion about the game.
- **Mechanism:** mechanical/operational behavior of venue pricing engines and risk desks.
- **Falsified by:** F6/F7 preregistered endpoints null; patterns fail to persist in the next registration window.

---

## §2. The four-system separation — FROZEN

Four systems. Each exposes a defined interface to the next. **None substitutes for another**: no output of one system is ever accepted as evidence belonging to another.

| # | System | Owns | Interface it exposes |
|---|---|---|---|
| S-FUND | **Fundamental** | player/possession models (the frozen possession-lane incumbents, and any future market-lane fundamental model), scenario tables (M13-style precomputed repricing states) | frozen, hashed, rung-tagged projections with publication timestamp strictly before commence; per-scenario fair-value deltas |
| S-MKT | **Market-reaction** | capture (ladder + burst), event-to-quote linkage, reaction/consensus/coherence analysis (F1–F10) | TRUSTED linkage records; interval-censored reaction distributions with full §6 fields; witnessed quote series with tier labels; consensus states at matched polls |
| S-EXEC | **Execution** | venue registry (M26), order router and shadow execution (M27), usable-edge transform, fill/latency/fee realism (M21/M23) | per-venue feasibility rows with citations and last-verified dates; `usable_edge = model_edge − fees − expected slippage − latency penalty − uncertainty buffer`; shadow audit records |
| S-DEC | **Decision-portfolio** | staking, exposure caps, correlation/duplicate control, mode *requests* | orders/alerts within the §7 mode in force; complete per-opportunity audit records; requests for mode transitions (never grants) |

**Substitution prohibitions (each a Severity A breach):**
- A fundamental-model edge (S-FUND) is never evidence of executability (S-EXEC), and never evidence the market reacts slowly (S-MKT).
- A market-reaction signal (S-MKT) never rescues or retunes a fundamental model; the possession-lane incumbent is frozen and the P2B §8 model-identity question stays closed to this lane.
- Execution feasibility (S-EXEC) never upgrades an evidence label (§3) on its own; a tradable venue does not make a signal true.
- The decision system (S-DEC) generates no evidence. It consumes labels; it cannot confer them, and it cannot grant its own mode transitions (§7).

---

## §3. The evidence ladder — FROZEN

Seven labels, strictly ordered. Every candidate strategy carries the **set** of labels it currently holds, reported individually. **The labels are never collapsed into a single success label** — there is no "WORKS", no "VALIDATED", no aggregate score. **No label is skippable:** promotion to a label requires every lower label to be currently held and its evidentiary record to exist independently. A verdict of `UNDERPOWERED` or `INDISTINGUISHABLE_AT_GRID` at any rung is a publishable outcome, not a failure to be papered over.

1. **`MARKET_MECHANISM_SUPPORTED`** — a named mechanism (from §1) is demonstrated in TRUSTED T0 data via a preregistered family endpoint (baseline §D.2), surviving the measurement grid. *Promotion requires:* preregistration frozen before results were visible; T0 tier throughout; amendment-4 fields on any timing component; the registered estimator from the approved set.
2. **`LINE_MOVEMENT_PREDICTIVE_ONLY`** — the signal's relationship to subsequent line movement is measured and classified: it predicts movement of the line, **and at this rung that is all it is evidence of**. This label is explicitly not evidence of profit and may never be cited as value. *Promotion requires:* out-of-registration-window prediction of quote movement at grid-respecting horizons, clustering per `report_id` respected.
3. **`CLOSING_LINE_VALUE_SUPPORTED`** — the signal systematically beats the **witnessed** close (the `CLOSE` window of baseline §A.3, T0 only; never the T2 archive, which has no close — §5). *Promotion requires:* witnessed pregame closes across multiple registration windows; preregistered CLV endpoint; in-play exclusion structural.
4. **`HISTORICALLY_PROFITABLE`** — backtested P&L is positive under **executable definitions only** (§8): prices witnessed at or before decision time, per-venue settlement rules applied, no in-play leakage, degradation-tested. *Promotion requires:* the §8 standards in full — multi-season where the capture record permits, not driven by extreme wins, capacity reported.
5. **`EXECUTION_FEASIBLE`** — a venue path exists in the M26 registry on which the wager class is legally and technically executable in the operating jurisdiction, with fees, limits, latency, and order types characterized, every legal-status cell carrying a citation and last-verified date. *Promotion requires:* registry row not self-certified by the platform's own claim; §8 degradation grid applied on that venue's measured latency profile.
6. **`PROSPECTIVELY_SUPPORTED`** — a SHADOW-mode prospective record, on data captured entirely after the registration froze, meets preregistered performance gates. *Promotion requires:* shadow audit records per the M23 schema; no retro-registration; gates fixed before the window opened.
7. **`PRODUCTION_ELIGIBLE`** — all six lower labels held simultaneously, the §7 hard risk controls verified, and the mode transition granted through its USER_REQUIRED gate. *This label is never self-granted by the graph.* Losing any lower label (e.g. a venue's legal status changes, a degradation retest fails) revokes it automatically.

A strategy document that reports a higher label without the per-label records beneath it commits a Severity A methodology breach.

---

## §4. Point-in-time integrity — FROZEN

1. **The point-in-time rule.** A claim about market state at time T requires a capture record whose **first-seen (witnessed) timestamp is at or before T**, of tier T0 (or T1 under rule 3). State asserted at T persists only until the next successful poll; between polls the state is interval-censored, never interpolated.
2. **Reconstructed or final-state data is never presented as point-in-time.** No retrospective harvest, no vendor back-fill, no "the line must have been" reconstruction may be displayed, tabulated, or cited as the state of the market at any instant.
3. **Tier discipline (baseline §0).** T0 (WITNESSED) supports timing claims within the §6 bounds. T1 (THIRD_PARTY_CONTEMPORANEOUS — including any amendment-1 Odds API historical rows, which enter as T1 *at best*) supports claims only with an explicit vendor-latency term, an explicit "vendor-asserted, unwitnessed" label on every claim, and never as the sole basis for an executability claim. T2 (RETROSPECTIVE_HARVEST) never supports a timing claim: bounded non-timing uses only, per §5. A derived quantity inherits the weakest tier of any input. Verification of coverage never upgrades witness.
4. **In-play exclusion is structural.** Any row with `snapshot_utc >= commence_time` is excluded from every pregame series at series construction, including every §5 use touching the extension files.
5. **Exclusion, never patching.** Records failing linkage or tier rules are retained with reason codes (baseline §A.7) and excluded; no imputation, no midpointing, no borrowing from correlated books, no narrowing an interval by assumption.

---

## §5. Bounded final-state archive uses — the D023 amendment-2 ruling, RATIFIED VERBATIM

The drafted ruling (EVENT_LINKAGE_AND_METHODOLOGY.md, Section C) is hereby **ratified unchanged** as the M00 contract ruling. It is reproduced verbatim below; the caveat texts are additionally frozen by sha256 in `TAXONOMY.json`, and the enforcement hook is binding on every market-lane artifact.

> ## C. Bounded uses of the final-state archive — the M00 contract ruling (amendment 2)
>
> **Object ruled on:** `data/drive_masters/master_odds.csv` (20,004 rows, 813 games, event dates
> 2022-05-21 → 2025-07-03) and, where noted, the two extension files (406 games, 2025–2026). Per P2B
> (coordinator-corroborated in D016): exactly one distinct snapshot per game across all 813 games;
> snapshots sit on a :25/:55 grid at a modal 64–65 minutes before commence; the harvest was a single
> 571-second retrospective burst on 2026-07-30; the vendor-asserted stamps are internally consistent
> but unwitnessed and unfalsifiable from this repository. Tier: **T2**.
>
> **Ruling shape:** the archive is neither worthless nor a timing record. It is a *cross-sectional
> census with an unverified timing label*. Uses are enumerated as M00-Ux classes. Any market-lane
> artifact touching the archive must cite the use class and reproduce that class's caveat text
> **verbatim**. A use not enumerated here is prohibited until this contract is amended.
>
> ### C.1 Permitted uses
>
> **M00-U1 — Book / market / season coverage census.** Which bookmakers, markets, seasons, and games
> appear; coverage rates (e.g. the P2B §5 table); fan-out structure (22 bookmakers × teams).
> > *Caveat (verbatim):* "Coverage figures derive from a retrospective single-snapshot harvest
> > (T2). They describe what the vendor could return in July 2026 about past games, not what was
> > observable at any pregame instant. Presence in this census is not evidence a price was available,
> > firm, or executable at any particular time."
>
> **M00-U2 — Vig structure and no-vig calibration against realized outcomes, unknown-time.**
> Overround by book/market/season; no-vig implied probabilities calibrated against realized results —
> as a property of *the vendor's asserted ~T−64m snapshot*, whatever instant it truly reflects.
> > *Caveat (verbatim):* "Calibration is of a snapshot whose capture time is vendor-asserted and
> > unwitnessed (P2B: CUTOFF_UNPROVEN). Results characterize an unknown-time pregame price level and
> > must not be read as closing-line calibration, opening-line calibration, or calibration at T−64
> > minutes. No CLV, timing, or line-movement inference may be built on this result."
>
> **M00-U3 — Settlement-rule and identifier inventory.** Team-name spellings, market keys, price
> formats, outcome labeling, push/settlement conventions — input to the frozen ER map (§A.6) and
> schema design.
> > *Caveat (verbatim):* "Identifier and settlement conventions are as of the 2026-07-30 harvest and
> > may not reflect conventions in force during the seasons the rows describe."
>
> **M00-U4 — Coarse cross-season price-level context.** Descriptive distributions of spread
> magnitudes, totals levels (2025+ only — the 2022-reaching archive has no totals, P2B §6), and
> price dispersion across books, by season. Descriptive display and sanity-checking only; never a
> feature, never a benchmark.
> > *Caveat (verbatim):* "Season-level price distributions from a T2 harvest describe one unknown-time
> > snapshot per game. Cross-season comparisons may confound market drift with harvest-selection
> > effects; the 2022 season's 75.3% coverage has an undocumented selection rule (P2B §10.3)."
>
> **M00-U5 — Schema fixtures and test corpora.** Real-shaped rows for parser tests, linkage
> dry-runs, and ER-map tests — with **timestamps replaced by synthetic values** in any fixture used
> to test timing logic, so a passing test can never be secretly leaning on T2 stamps.
> > *Caveat (verbatim):* "Fixture data only. Timing fields are synthetic or T2 and carry no
> > evidentiary weight."
>
> **M00-U6 — Prior elicitation and power analysis for prospective designs.** Variances of prices
> across books, typical overrounds, book counts per game — as inputs to sample-size and
> detectability planning for the prospective (T0) experiments of Section D.
> > *Caveat (verbatim):* "Priors elicited from a T2 harvest inform design only. They are superseded by
> > the first adequately-powered T0 measurement and are never combined with T0 data in a single
> > likelihood as if exchangeable."
>
> ### C.2 Prohibited uses — what one snapshot per game can NEVER support
>
> No timing, latency, lead-lag, reaction, or sequencing claim of any kind; no CLV or
> closing-line-value computation (the snapshot is not a close and there is no open); no stale-line or
> stale-window claim; no open-vs-close movement (there is exactly one snapshot; F10 is structurally
> impossible on this archive); no intra-day or event-response dynamics; no executability, liquidity,
> or "this price was gettable" claim; no use as a feature or benchmark in any predictive model in
> either lane (the possession-lane exclusion in P2B stands and is not reopened here); no treatment of
> `odds_snapshot_timestamp` as witnessed for any purpose. The extension files additionally carry
> 232 + 338 in-play rows (P2B §7): **every** M00 use touching the extensions filters
> `snapshot < commence` first, including the census.
>
> **Enforcement hook:** M00-class artifacts carry a machine-readable header
> (`m00_use_class`, `caveat_hash`). A missing or mismatched caveat hash fails review; a T2 field
> reaching a timing claim is a Severity A methodology breach.

### §5.1 Subordination rulings on the other W1 drafts (amendments to those drafts, not to C)

The enumeration above is **exclusive**. Two passages of `COMPETITOR_ARCHIVE_DESIGN.md` §4 are overruled or restricted where they exceed it:

1. **§4 item 1 ("Outcome labeling ... CLV-style labels") is OVERRULED in part.** Realized game outcomes for scoring projection accuracy come from game results, not from the archive, and need no archive at all. Any "CLV-style label" computed from the T2 archive is a closing-line-value computation, which C.2 prohibits without exception. No CLV-style quantity may be derived from the archive.
2. **§4 item 2 (cross-sectional "final projection vs final market number" benchmarks) is NOT a currently enumerated use.** M00-U4 is descriptive display and sanity-checking only — "never a feature, never a benchmark." Using the archive as a benchmark comparator for competitor projections is prohibited until this contract is amended to add a use class. Market-implied comparators draw from the new T0 capture pipeline only (the competitor draft's own §5.1 already requires this).
3. **§4 item 3 (coverage/sanity checks) maps to M00-U1** and is permitted with the U1 caveat verbatim.

---

## §6. Timestamp-uncertainty discipline — D023 amendment 4, FROZEN LANE-WIDE

**Every future reaction-time claim carries EXPLICIT timestamp-uncertainty and vendor-latency terms. A reaction-time figure missing either term is a defect, not a result.** A claim that cannot carry both terms is reported `UNSUPPORTABLE`, never stated without them.

### §6.1 Mandatory fields on every reaction-time claim (baseline §B.2, no exceptions)

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

### §6.2 Sharpness prohibition (baseline §B.3)

No point estimate finer than the measurement grid `G = Δ_event + Δ_quote + L_max(all vendors) + 2·ε_max`. Comparative claims below the combined grid resolve to `INDISTINGUISHABLE_AT_GRID`. Summary statistics of interval-censored data are intervals or named-model estimates, never bare numbers. Vendor-asserted stamps live only in the `VENDOR_ASSERTED` advisory channel; advisory numbers never enter a headline, a gate, a preregistered endpoint, or a decision, and the two channels are never averaged.

### §6.3 Mandatory schema fields (amendment-4 fields made compulsory at the schema level)

Any market-snapshot table this lane builds (per `CAPTURE_UPGRADE_DESIGN.md` (d)) **must** carry, on every row: `vendor_ts`; `vendor_ts_semantics` (enum `book_last_change` / `vendor_ingest_time` / `unknown_unverified`, **defaulting to `unknown_unverified` until vendor documentation or support confirms which**); `retrieval_ts`; `ingestion_ts`; `max_staleness_bound`; `poll_interval_at_capture`; `vendor_latency_note`; `payload_hash`; `prev_snapshot_ref`. The table is append-only; a correction is a new row, never an UPDATE.

Any competitor-projection archive this lane builds (per `COMPETITOR_ARCHIVE_DESIGN.md` §3) **must** carry, on every row: `capture_rung`; `ladder_run_id`; `scheduled_tipoff_ts`; `provider_update_ts` (nullable); `provider_update_ts_confidence` (enum exact / provider-rounded / inferred / unavailable); `capture_ts`; `capture_latency_notes`; `no_change_since_prior_rung`; `schedule_shift_flag`; `payload_hash`; `raw_payload`; `access_mode`; `license_basis`. Benchmarks compare only rows sharing `capture_rung` **and** `ladder_run_id`, and every benchmark output propagates the contributing `provider_update_ts_confidence`, non-empty `capture_latency_notes`, and `license_basis` values; a result that drops them is non-compliant and may not be presented as a claim.

A capture run without a clock-skew measurement taints its rows `CLOCK_UNBOUNDED`; a vendor without a sourced latency bound is `UNBOUNDED` and inherits inadmissibility for fine-grained statements.

---

## §7. Execution-mode ladder and venue policy — D024 as lane law, FROZEN

Four explicit, mutually exclusive modes. **Transitions are one-way gates, never automatic, and none is self-grantable by the graph.**

| mode | meaning | gate to enter |
|---|---|---|
| `OFF` | no orders, no alerts | — |
| `SHADOW` | generate the exact order that would have been placed, full audit record, send nothing | **default and starting mode for every strategy** |
| `CONFIRM` | order generated; a single human confirmation or nothing happens | USER_REQUIRED gate. The only mode ever contemplated for licensed NY books, and the entry mode for exchange testing with real funds |
| `AUTO` | API order placement without per-order approval | requires ALL of: written platform authorization for algorithmic entry on our account class; jurisdiction clearance in writing; passed sandbox tests; prospective SHADOW performance meeting preregistered gates; verified hard risk controls; and an explicit financial USER_REQUIRED authorization. None self-grantable |

**Hard risk controls required before any non-SHADOW order** (the M24 checklist skeleton, adopted verbatim from D024/VENUE_EXECUTION_RESEARCH §2): approved event source; minimum confidence; minimum edge; maximum quote age; maximum stake; per-game and per-player exposure caps; minimum liquidity; no duplicate or correlated-order conflict; no trading through a suspension; daily loss and volume caps; global kill switch.

**Venue policy:** jurisdiction gates engineering. Exchange APIs (ProphetX, BettorEdge) are sandbox/shadow research tracks while the NY legal conflict stands unresolved in writing. Kalshi is excluded from production planning during its active NY dispute. Novig is out (excludes NY). Licensed NY books: alert-plus-manual-confirm ONLY; automating their sites, scraping, or reverse-engineering private endpoints is prohibited by their terms and by this program. All venue claims are unverified web assertions until independently cited in the M26 venue automation registry with last-verified dates; nothing in the registry is self-certified by a platform's own claim. Account creation, KYC, deposits, and letters to venues are USER actions exclusively.

---

## §8. Profitability standards — FROZEN

A profitability claim in this lane is admissible only under all of the following:

1. **Executable definitions only.** P&L is computed from prices witnessed (T0) at or before the decision time, at venues where the wager class existed, with each venue's settlement rules applied. No in-play rows, no reconstructed prices, no "best price anywhere" unless every book quoted at the same poll.
2. **Survives degradation.** The result must survive the latency test ladder (100ms / 500ms / 1s / 5s / 30s on the exchange track; 15s–5m per the M21 delay grid), stated stake limits, and explicit slippage and fee models. A strategy profitable only at zero latency holds `LINE_MOVEMENT_PREDICTIVE_ONLY` at best.
3. **Multi-season where possible.** Where the witnessed capture record spans multiple seasons, the claim must; where it cannot, the claim is labeled window-limited and no multi-season generalization is stated.
4. **Not driven by extreme wins.** Influence diagnostics are mandatory (leave-out-top-N wins, per-cluster influence). Profit that vanishes when the top wins are removed is not `HISTORICALLY_PROFITABLE`.
5. **Capacity reported.** Every profitability claim states the estimated stake/capital at which the edge is expected to persist (limits, liquidity, market depth), or states `CAPACITY_UNKNOWN` explicitly. A claim silent on capacity is incomplete.

---

## §9. USER_REQUIRED boundary — FROZEN

The following are user actions exclusively. The graph may draft, model, and simulate; it may never perform, and no node may resolve one of these inside itself — it HALTS and raises a USER_REQUIRED gate:

1. **Purchases** — API tier upgrades, subscriptions, data licenses, any spend.
2. **Accounts** — creation, KYC, deposits, withdrawals, sandbox account setup.
3. **Credentials** — obtaining, holding, or entering any credential or key beyond the already-provisioned capture keys.
4. **Wagers and orders** — any non-SHADOW order on any venue; every CONFIRM click.
5. **Staking changes** — bankroll size, staking plan, exposure-cap changes.
6. **Deployment** — any mode transition on the §7 ladder (SHADOW→CONFIRM, CONFIRM→AUTO, and any re-entry after a kill).
7. **Legal/risk acceptance** — scraping or licensing risk, ToS interpretation, `license_basis` resolutions, letters to venues, jurisdiction judgments.

---

## §10. Hypothesis-family baseline and preregistration — ADOPTED

Families F1–F10 (baseline §D.1) are the lane's frozen hypothesis universe: F1 injury-report latency, F2 book lead-lag, F3 arbitrage windows, F4 middles, F5 consensus residual, F6 suspension/reopening, F7 cross-market coherence, F8 player-value residual, F9 vendor residual, F10 open/close (structurally impossible on the T2 archive). Preregistration records per §D.2 (one primary endpoint per family per window; estimators from the approved interval-censored set; frozen degeneracy fallbacks; `UNDERPOWERED` below minimum n). Multiplicity budget per §D.3 (per-window allocation before unsealing; no roll-forward; no retro-registration; negative and `INDISTINGUISHABLE_AT_GRID` verdicts published with equal prominence; raw outputs frozen and hashed before review; independent verifier before `node_passed`). Standing constraints per §D.4 inherited by every family.

---

## §11. Amendment and enforcement

- This contract is amended only by a ledgered decision citing user authorization, never by a node's own reading of convenience. Stretching the §5 enumeration, coining a new success label, or blending §3 labels is a Severity A breach.
- A market-lane artifact touching the T2 archive without `m00_use_class` + matching `caveat_hash` (values frozen in `TAXONOMY.json`) fails review.
- A reaction-time figure missing timestamp-uncertainty or vendor-latency terms is a defect, not a result (§6).
- Stop conditions inherited by every market node: spending money, placing a wager, entering credentials, accepting scraping/licensing risk, or reading sealed possession results → HALT to USER_REQUIRED; an unsupportable timing claim → report `UNSUPPORTABLE`; an archive use outside §5 → HALT and raise.

*End of contract v1.0.0.*
