# Competitor Projection Archive — Design Document

**Lane:** market_intelligence (founding wave, decision D023, 2026-08-06)
**Role:** Competitor Archive Designer (critical path, Amendment 3)
**Status:** DESIGN ONLY — nothing in this document has been implemented, scraped, called, or scheduled.
**Owner file:** `experiments/market_program/W1_DRAFTS/COMPETITOR_ARCHIVE_DESIGN.md`
**Author date:** 2026-08-06

## 0. Scope and non-goals

This document designs a system for archiving *third-party WNBA player projections* (not our own model outputs, not odds) at disciplined, fixed information cutoffs, so that later analysis can benchmark our projections against the market's other participants without accidentally comparing apples that were picked at different times.

Non-goals, explicitly out of scope for this document:
- No scraper code, no cron jobs, no credentials, no API keys.
- No decision on which sources we are legally permitted to archive — every source below carries a licensing flag and an explicit "USER DECISION REQUIRED" marker rather than a recommendation to proceed.
- No training-data policy — Section 6 documents the constraint but treats vendor projections as benchmark-only by default, pending rights clearance.
- Does not touch the odds pipeline (Amendments 1–2 belong to the odds-archive designer role, not this one), except where the two archives need to interoperate (Section 3, `linked_information_event`).
- Does not touch anything under `experiments/player_program/stage2b/SEALED_RESULTS` — not read, not referenced, not required for this design.

This document assumes Amendment 4 (timestamp-uncertainty and vendor-latency terms on every reaction-time claim) applies to every benchmark defined in Section 5, and bakes that requirement into the schema (Section 3) rather than leaving it as a post-hoc caveat.

---

## 1. Fixed-cutoff capture ladder

### 1.1 Why a ladder, not continuous polling

Competitor projections are not point processes we can capture "whenever" — they are step functions that update on the provider's own schedule (roster news, lineup confirmation, injury reports, betting-line moves the provider reacts to). If we capture at arbitrary times, two projections that look "simultaneous" in our archive may actually reflect different information states, and any benchmark built on them silently launders a timing error into an accuracy claim. The ladder exists to make comparison discipline structural rather than a matter of care at analysis time.

### 1.2 Ladder rungs

| Rung | Nominal offset | Anchor | Purpose |
|---|---|---|---|
| R1 | T-24h | scheduled tip-off | Early-week baseline; captures projections made before most injury/rest news is public |
| R2 | T-8h | scheduled tip-off | Morning-of-gameday capture; captures projections made after shootaround-adjacent news but before final lineups |
| R3 | T-2h | scheduled tip-off | Pre-lineup-lock capture; the rung most comparable to "market close" for slow-moving books |
| R4 | T-30m | scheduled tip-off | Post-lineup-confirmation capture; starter/DNP status should be settled for most providers by here |
| R5 | final (pre-tip) | last capture before tip-off | The provider's terminal pre-game number; the standard "closing projection" comparison point |
| R6 | post-material-news | event-triggered, not clock-triggered | Ad hoc capture fired by an information event (see 1.4) that invalidates R1–R5 as "current" |

Every rung is anchored to the **scheduled** tip-off time as published by the league/schedule feed at ladder-definition time, not to the actual tip-off (which can move). If a game is postponed or rescheduled after some rungs have already fired, those captures remain valid records of "what the provider said at T-minus-X-from-the-then-scheduled-tip", they are simply flagged (`schedule_shift_flag`) rather than discarded — discarding would destroy real information about provider staleness.

### 1.3 Identical-timestamp comparison discipline

The single non-negotiable rule for any consumer of this archive: **two projections are only compared as "simultaneous" if they share the same rung AND the same target game AND the same nominal ladder run.** A provider's R3 for Game X may not be compared to another provider's R2 or R4 for Game X, and neither may be compared to a same-rung capture from a *different* ladder run (e.g., a retry after a failed capture). This rule is enforced at the schema level via `capture_rung` and `ladder_run_id` fields (Section 3) and is restated as a hard constraint in Section 5's benchmark design — it is not left as an analyst convention.

Corollary: because provider update cadence is heterogeneous (Section 2), a captured value at rung R3 is not a claim that the provider *updated* at T-2h — only that this was the provider's displayed/API value *when we captured* at T-2h. The gap between "provider's last actual update" (`provider_update_ts`, Section 3) and "our capture" (`capture_ts`) is itself data we retain, not something we collapse away.

### 1.4 Post-material-news trigger (R6)

R6 is not clock-scheduled. It fires when an information event is logged that plausibly invalidates standing projections for a game already on the ladder — most commonly a late scratch, a starter-status flip, or a material line move flagged by the odds-archive lane. Because R6 is event-triggered, its `capture_ts` is whatever time the event fired, and it must record `trigger_event_id` linking to the causing event (see `linked_information_event` in Section 3). R6 can fire multiple times for a single game if multiple qualifying events occur; each is a distinct row, not an overwrite.

### 1.5 What the ladder does *not* attempt

- It does not attempt to capture at the *exact* provider update moment — that would require either provider push notifications (rarely offered) or continuous polling (Section 1.6 addresses cost/ToS tension). The ladder is a compromise: enough rungs to bound staleness, not so many as to look indistinguishable from scraping-for-scraping's-sake to a provider's ToS enforcement.
- It does not promise all providers will have fresh data at all six rungs — cadence varies per provider (Section 2). Rungs where a provider simply hasn't updated since the prior rung are still captured (to record "still stale as of T"), just flagged with a `no_change_since_prior_rung` boolean rather than skipped, so absence-of-update is itself visible in the archive.

### 1.6 Capture frequency vs. access-mode reality (forward pointer, not a decision here)

The ladder above is a target cadence. Whether it is achievable per source depends entirely on access mode and ToS posture (Section 2) — a source offering a documented API with reasonable rate limits can hit all six rungs cheaply; a source only accessible as a rendered web page raises the scraping-consent question this document is explicitly barred from resolving. Section 2 flags this per source; no rung schedule below should be read as authorization to poll a page that has not cleared legal review.

---

## 2. Source survey

Five sources surveyed: the two named (RotoWire, RotoGrinders) plus three additional credible WNBA projection providers identified via search. All ToS characterizations below are from a single automated search pass on 2026-08-06 and are **not a legal opinion** — every "USER DECISION REQUIRED" marker means exactly that, and no source in this table should be treated as cleared for archiving until a human with legal authority signs off.

### 2.1 RotoWire

- **What they publish:** Season-long WNBA projections (`rotowire.com/wnba/projections.php`) and daily/DFS-oriented projections (`rotowire.com/wnba/projections-daily.php`), plus a separate daily lineups page (`rotowire.com/wnba/lineups.php`) covering starter/confirmed-status. Per-stat detail (points/rebounds/assists-level) appears present on the projections pages based on page titles; exact field granularity was not verified beyond title-level survey and should be confirmed by a human before schema mapping.
- **Update cadence:** RotoWire's own site copy states staff set expected lineups roughly 24–30 hours before tip-off and adjust through gameday — i.e., a cadence that roughly maps onto our R1–R4 rungs already.
- **Access mode:** Web page. No public API surfaced in this survey; RotoWire does sell data/API products commercially in other sports, so a licensed data-feed option may exist and should be asked about directly rather than assumed absent.
- **ToS posture:** RotoWire's terms and conditions (`rotowire.com/termsandconditions.php`) explicitly prohibit "manual or automated software, devices, or other processes to 'crawl' or 'spider'" their pages, and prohibit imposing unreasonable load on their infrastructure. This is a direct, explicit anti-scraping clause.
- **Licensing flag:** 🔴 **RED — explicit anti-scraping ToS language found.** Automated capture of the web pages as designed above would likely violate RotoWire's terms as written. **USER DECISION REQUIRED**: either (a) do not archive RotoWire via automated capture at all, (b) pursue a licensed commercial data feed and archive only under that license's terms, or (c) obtain explicit written permission. This design assumes none of those has happened yet.

### 2.2 RotoGrinders

- **What they publish:** `rotogrinders.com/projected-stats/wnba` — DFS stat projections plus pOWN% (projected ownership), described as updated regularly through the day. A `LineupHQ` product (`rotogrinders.com/lineuphq/wnba`) covers optimizer/lineup data, which is adjacent but a distinct product from raw projections.
- **Update cadence:** "Updated regularly" through the slate per page copy; exact cadence (minutes vs. hours) not confirmed in this survey.
- **Access mode:** Web page; premium/paywalled tier noted for full content access. No public API surfaced in this survey.
- **ToS posture:** Not directly retrieved in this pass — search returned only the page itself, not their terms document. **This is a gap, not a clean bill.**
- **Licensing flag:** 🟡 **YELLOW — ToS not yet reviewed; paywall/premium-tier implies a commercial relationship is the intended access path, not open scraping.** **USER DECISION REQUIRED**: pull RotoGrinders' actual terms of service/use before any capture design is finalized, and determine whether the premium subscription's own terms (separate from the public ToS) govern automated re-use of paid content — subscription terms are frequently stricter about redistribution/archiving than general site ToS.

### 2.3 Stokastic (hosts Awesemo WNBA content)

- **What they publish:** DFS projections, ownership, and simulation-based tools (`stokastic.com/wnba/`, `stokastic.com/projections/`) — Boom/Bust, Top Stacks, "Stokastic Sims," and a lineup generator. Awesemo's WNBA DFS content is hosted under the Stokastic domain per this survey, suggesting a business consolidation; treat as one source, not two, unless confirmed otherwise.
- **Update cadence:** Not confirmed in this survey; simulation-based tools typically imply per-slate (not intra-day continuous) regeneration, but this is an inference, not a verified fact.
- **Access mode:** Web page/app. No public API surfaced.
- **ToS posture:** Stokastic's terms of service (`stokastic.com/terms-of-service`) state the service "does not confer any license" under Stokastic's IP and that content is owned by Stokastic or used under license from third parties; the terms also frame the service as "informational and entertainment purposes only." No explicit anti-scraping/anti-crawling clause was surfaced in this pass, but absence-of-evidence is not the same as absence-of-clause — the full document was not read in this pass, only search-summarized.
- **Licensing flag:** 🟡 **YELLOW — no explicit anti-scraping language surfaced, but IP-ownership language is present and the full ToS was not read.** **USER DECISION REQUIRED**: read the full Stokastic ToS before any capture design is finalized; explicit "no license conferred" language is a signal, not a green light.

### 2.4 Dimers

- **What they publish:** Daily WNBA player projections for points, rebounds, assists "and more" (`dimers.com/wnba/player-projections`) — described as updated regularly, with a broader sports-betting-analytics product line (Dimers is primarily known for game-level betting projections, not just DFS).
- **Update cadence:** Not confirmed in this survey beyond "updated regularly."
- **Access mode:** Web page. Dimers is known in the broader betting-analytics space to sometimes offer commercial data licensing; not confirmed for WNBA specifically in this pass.
- **ToS posture:** Not retrieved in this pass — search returned no Dimers-specific terms content, only generic third-party web-scraping-tool results (search-quality miss, not a finding of "no ToS exists").
- **Licensing flag:** ⚪ **UNKNOWN — ToS not located in this survey pass.** **USER DECISION REQUIRED**: locate and read Dimers' actual terms of service directly from their site (a follow-up search or direct site visit is needed; this pass's automated search did not surface it) before any capture design proceeds.

### 2.5 FantasyCruncher / LineStar

- **What they publish:** WNBA DFS projections, ownership, and lineup optimization for DraftKings, FanDuel, Yahoo, and SuperDraft (`fantasycruncher.com/wnba`); LineStar (`linestarapp.com`) separately offers a "DFS Dashboard" with starting lineups and a projections/optimizer product across the same sites. Treated here as two related but distinct sources — do not assume shared ownership/ToS without confirmation.
- **Update cadence:** LineStar's dashboard is dated per-day in its own URL pattern, implying at least daily refresh; intra-day cadence not confirmed.
- **Access mode:** Web page/app for both. No public API surfaced for either in this pass.
- **ToS posture:** Not retrieved for either in this pass.
- **Licensing flag:** ⚪ **UNKNOWN for both.** **USER DECISION REQUIRED**: separately review FantasyCruncher's and LineStar's terms before treating either as archivable, and confirm whether they are affiliated (would matter for whether one legal review covers both).

### 2.6 Survey-level caveats

- This was a single search-engine pass, not a legal review. Every ToS characterization above should be re-verified by reading the actual current terms document immediately before any implementation decision, since terms change and search summaries can be stale or incomplete.
- No source above should be read as "cleared." The one source with an explicit finding (RotoWire) is explicitly *not* cleared. The others are unresolved, not cleared-by-silence.
- "Personal research use" as a distinct, narrower carve-out from general ToS was not confirmed for any source in this pass — some services do distinguish personal/non-commercial research use from commercial redistribution, but none of the retrieved snippets above confirmed such a carve-out explicitly. This is a **USER DECISION REQUIRED** research item on its own: someone should ask each vendor directly, or have a human read the full ToS documents, rather than us inferring a personal-use exception from silence.
- This design recommends nothing about proceeding to capture from any of these sources. That decision is explicitly reserved for the user per this role's instructions.

---

## 3. Archive schema

Conceptual schema (storage-engine-agnostic; column-family or relational both fit). One row = one (provider, player, game, capture) observation.

| Field | Type | Notes |
|---|---|---|
| `record_id` | UUID | Primary key |
| `provider` | enum | RotoWire / RotoGrinders / Stokastic / Dimers / FantasyCruncher / LineStar / ... (extensible) |
| `player_id` | our canonical entity ID | Resolved via our new entity-resolution layer (not provider's own player ID) — see 3.1 |
| `provider_player_id` | string, nullable | The provider's own internal ID/slug for the player, retained for audit and re-resolution if our entity resolution changes |
| `game_id` | our canonical game ID | Must map cleanly to the same game_id used by the odds archive for `linked_information_event` joins |
| `capture_rung` | enum | R1..R6 per Section 1.2 |
| `ladder_run_id` | UUID | Groups all rungs belonging to one ladder execution for one game; enables the "same ladder run" comparison rule from 1.3 |
| `scheduled_tipoff_ts` | timestamp, UTC | The scheduled tip-off this rung's offset was computed against; frozen at ladder-definition time (1.2) |
| `provider_update_ts` | timestamp, UTC, nullable | When the provider says the projection was last updated, if the provider exposes this. Null if the provider does not expose an update timestamp — this null-ability is itself an important field, see 3.2 |
| `provider_update_ts_confidence` | enum: exact / provider-rounded / inferred / unavailable | Amendment 4 compliance field — see 3.2 |
| `capture_ts` | timestamp, UTC | When *we* captured the value. Always exact (our clock), unlike `provider_update_ts` |
| `capture_latency_notes` | text, nullable | Free-text field for known systemic vendor/CDN/cache latency (e.g., "provider CDN caches for ~5 min") — Amendment 4 |
| `no_change_since_prior_rung` | boolean | True if this capture's projection fields are bit-identical to the immediately prior rung in the same ladder run |
| `schedule_shift_flag` | boolean | True if the game's actual tip-off diverged from `scheduled_tipoff_ts` after this rung fired (Section 1.2) |
| `starter_status` | enum: confirmed_starter / probable_starter / bench / questionable / out / unknown | Normalized across providers; provider's raw string retained in `raw_payload` |
| `projected_minutes` | float, nullable | Normalized units; null if provider doesn't publish minutes |
| `projection_fields` | JSON/struct | Per-stat projections (pts, reb, ast, etc.) — kept as an open struct rather than fixed columns since providers vary in what they publish |
| `prev_value` | JSON/struct, nullable | Snapshot of `projection_fields` from the immediately prior capture (any rung, same provider+player+game) — enables change-magnitude computation without a self-join at query time |
| `change_magnitude` | struct: per-field delta + a normalized composite score | Computed at write time from `projection_fields` vs `prev_value` |
| `linked_information_event` | FK, nullable | Points into the shared information-event log (the same log the odds-archive lane and R6 trigger draw from) — e.g., "player X ruled out," "line moved 2pts." Null for routine ladder-clock captures (R1–R5 with no associated event) |
| `payload_hash` | string (sha256) | Hash of the raw captured payload, for integrity/dedup and to detect "provider changed formatting but not substance" vs real changes |
| `raw_payload` | blob/JSON | Full unmodified capture, retained for re-parsing if our normalization logic changes later |
| `access_mode` | enum: api / rendered_page / manual | Records how this row was obtained — matters for later ToS audit trail |
| `license_basis` | enum: unlicensed / licensed_feed / manual_personal_use / unresolved | Per-row record of what legal basis (if any) applied to this capture at capture time — see 3.3 |

### 3.1 Player resolution

`player_id` must come from our entity-resolution layer, not from matching provider name-strings directly — provider naming is inconsistent (suffixes, nicknames, accented characters, trade-current-team labeling) and a naive string join would silently misattribute projections, especially for players who share surnames or who moved teams mid-season. `provider_player_id` is retained alongside so that if our entity resolution improves or a mis-mapping is later discovered, historical rows can be re-resolved without re-capturing.

### 3.2 Amendment 4 compliance in-schema

Amendment 4 requires every future reaction-time claim to carry explicit timestamp-uncertainty and vendor-latency terms. This schema enforces that structurally:
- `provider_update_ts_confidence` forces every row to declare how trustworthy its provider-side timestamp is, rather than letting downstream analysis assume `provider_update_ts` is exact.
- `capture_latency_notes` is a place to record known systemic vendor delay (CDN caching, batch publish jobs, etc.) discovered during operation — this field is expected to be populated iteratively as the archive operator learns each provider's real-world behavior, not filled in perfectly at design time.
- Any benchmark or reaction-time claim built from this archive (Section 5) must surface `provider_update_ts_confidence` and `capture_latency_notes` alongside the result — this is a consumption-contract requirement, not optional metadata.

### 3.3 License basis per row

`license_basis` is deliberately a per-row field, not a per-provider table property, because the legal basis for a given source could change mid-archive (e.g., we sign a licensed feed deal partway through a season, or a manual personal-use judgment is later revisited). Defaulting new capture designs to `unresolved` until Section 2's USER DECISION REQUIRED items are closed keeps the archive honest about its own legal footing over time, and lets a future audit filter to only rows with a defensible basis.

---

## 4. Relationship to the existing final-state odds archive (Amendment 2)

Per Amendment 2, the existing 813-game final-state odds archive is not written off — it has bounded legitimate uses that should be enumerated, not discarded, even though it is `CUTOFF_UNPROVEN` for timing claims. In the context of *this* competitor-projection archive, its legitimate uses are:

1. **Outcome labeling.** The final-state archive's odds are fine as inputs to compute realized outcomes/CLV-style labels for backtesting competitor-projection accuracy, since outcome labeling does not depend on knowing exactly *when* the snapshot was taken — only that it reflects some late/final state of the market for that game.
2. **Cross-sectional (non-timing) benchmarks.** Comparing "final competitor projection vs. final market number" as a same-game snapshot pair does not require precise cutoff provenance on the odds side, as long as both sides are understood as "some late state," not "the closing line at time T." This is different from a reaction-time or timing claim and should be labeled as such wherever used.
3. **Coverage/sanity checks.** Using the 813-game archive to confirm a game existed, had a market, and had *some* recorded odds is a legitimate low-stakes use that doesn't lean on timing precision at all.

What it must **not** be used for in this design: any R1–R6 rung comparison, any `change_magnitude` timing narrative, or any Amendment-4-governed reaction-time claim — those require point-in-time provenance the final-state archive does not have. Where a benchmark (Section 5) wants a "market-implied" comparator at a specific rung, it must draw from the *new* high-frequency live-capture odds pipeline (Amendment 3's other critical-path piece), not from the legacy 813-game archive. This boundary should be enforced by convention in benchmark code (flagging which odds source fed a given comparator) since this document cannot enforce it at the schema level of a system it doesn't own.

---

## 5. Benchmark suite design

All benchmarks below are computed **only at matched cutoffs** — i.e., only across rows sharing `capture_rung` and `ladder_run_id` per the comparison discipline in Section 1.3. No benchmark in this suite averages or otherwise mixes across rungs.

### 5.1 Comparators, per rung

For a given `(game_id, capture_rung, ladder_run_id)`:

- **Per-provider value.** Each provider's own `projection_fields` at that rung, verbatim — the baseline unit everything else is built from.
- **Median consensus.** Median of `projection_fields` across all providers with a valid (non-null, `no_change_since_prior_rung`-aware — see 5.2) capture at that exact rung.
- **Trimmed-mean consensus.** Mean after dropping the top/bottom N% (N configurable, default suggestion 10–20% given the likely small provider count of 4–6 — this default should be revisited once real provider coverage is known, since trimming assumptions that work with 10 providers behave very differently with 4).
- **Market-implied value.** Derived from the *new* high-frequency odds/live-capture pipeline (Amendment 3), read at the closest odds-side capture to this rung's `capture_ts` — never from the legacy 813-game archive (Section 4). The join key and "closest" tolerance window are an interface this document specifies a need for but does not own the implementation of, since it lives in the odds-archive designer's territory.
- **Our incumbent.** Our own model's projection, captured at the same nominal rung under the same cutoff discipline — this requires our own projection pipeline to also emit rung-tagged snapshots, which is a dependency this design flags but does not implement.
- **Blends.** Configurable weighted combinations of the above (e.g., 50/50 median-consensus/market-implied), computed only after all inputs for the blend share the same rung.

### 5.2 Handling missing/stale providers

Not every provider will have a fresh capture at every rung (Section 1.5). Two policy options, both to be supported and selectable per benchmark run rather than hard-coded:
- **Rung-strict:** exclude a provider from that rung's consensus if their captured row is `no_change_since_prior_rung = true` and older than some staleness threshold — avoids consensus being dragged by a stale number masquerading as current.
- **Rung-lenient:** include the provider's last-known value regardless of staleness, on the theory that "still whatever they last said" is itself a valid market state at that instant.
Which policy is "correct" depends on the analysis question; this document does not pick a default and instead requires the policy to be an explicit, logged parameter on every benchmark run.

### 5.3 Amendment 4 propagation into benchmarks

Every benchmark output must carry forward, at minimum:
- the set of `provider_update_ts_confidence` values contributing to it,
- any non-empty `capture_latency_notes` from contributing rows,
- the `license_basis` values of contributing rows (so a benchmark cannot silently launder an `unresolved`-basis row into a published number without that being visible).

A benchmark result that drops these fields on the way to a headline number is, per Amendment 4, not a compliant reaction-time or accuracy claim and should not be presented as one.

---

## 6. Storage / training-rights constraints

Default posture, per this role's brief: **benchmark-only, until rights are established, for every source in Section 2.** Concretely:

- Vendor projection values (`projection_fields`, `raw_payload`) may be used to compute the benchmarks in Section 5 — read-only, comparative, non-redistributive use.
- Vendor projection values must **not** be used as a feature/input into our own player-projection models, must not be used to fine-tune or calibrate our incumbent model's parameters, and must not be redistributed (even internally packaged as a "consensus" number that effectively reconstructs a paywalled source) until:
  1. the relevant source's `license_basis` (Section 3.3) is resolved to something other than `unresolved` or `unlicensed`, **and**
  2. that resolution is a positive human decision (licensed feed signed, or explicit permission obtained, or a `manual_personal_use` judgment is affirmatively made by someone with authority to make it) — not merely "nobody objected."
- This constraint is per-source, not archive-wide: if RotoWire remains unresolved but a hypothetical future source signs a data-licensing deal, only that source's rows become training-eligible, and the schema's per-row `license_basis` (3.3) is what makes that partition enforceable at query time rather than requiring a separate parallel table.
- `payload_hash` and `raw_payload` retention itself (Section 3) is storage, not redistribution or training use — but if a source's ToS is found to prohibit archiving/storage outright (not just automated *access*), that would invalidate even the read-only benchmark use for that source, not just the training-use question. This document flags that distinction because Section 2's survey characterized ToS mostly in terms of *scraping/crawling* language, not storage/archiving language specifically — **USER DECISION REQUIRED**: confirm whether any source's terms separately restrict retention/archiving of captured data beyond restricting the *method* of capture.

---

## 7. Open items requiring a user decision (consolidated)

1. Per-source legal clearance for RotoWire (explicit anti-scraping clause found — red), RotoGrinders, Stokastic, Dimers, FantasyCruncher, and LineStar (all unresolved/yellow-or-unknown) before any capture implementation begins.
2. Whether any source offers a licensed commercial data feed as an alternative to page capture (flagged as possible but unconfirmed for RotoWire and Dimers specifically).
3. Whether "personal research use" is a real carve-out for any source, or an assumption we should not make.
4. Whether any source's terms restrict *storage/archiving* independent of *capture method* (Section 6) — this would affect even the benchmark-only use case, not just training use.
5. Trimmed-mean trim percentage default, pending real provider-count discovery (Section 5.1).
6. Rung-strict vs. rung-lenient staleness policy default (Section 5.2) — left as a required explicit run parameter rather than resolved here.

None of the above have been decided by this document. This document is a design for review, not an authorization to proceed.
