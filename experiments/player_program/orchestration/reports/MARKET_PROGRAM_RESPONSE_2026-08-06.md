# Coordinator response — proposed Market Intelligence & Execution program

Status: RESPONSE TO A DRAFT DIRECTIVE. Nothing in this document creates nodes, spends money,
or starts capture. It reconciles the two proposed versions (MKT00–MKT15 and M00–M25) against
what the repository already contains, states what is already done, and lays out exactly how I
would execute if the directive is issued.

---

## 1. The single most important correction

Both drafts assume meaningful retrospective market analysis can begin "where point-in-time
data exists." **This program has already adjudicated that question, and the answer is
unfavorable and frozen:**

* Our only historical odds archive (`data/odds_capture/historical/`, 292 files;
  `master_odds.csv`, 20,004 rows, 813 games back to 2022-05-21) is a **single retrospective
  harvest pulled on 2026-07-30** — exactly ONE snapshot per game (min=median=max=1), the
  signature of a final-state scrape, not a capture stream. Decision D016/P2B ruled it
  **permanently CUTOFF_UNPROVEN**: it can never support event-timing, latency, lead-lag, or
  stale-window claims, because none of those quotes carry a defensible "we could have seen
  this at time T."
* Genuine point-in-time capture exists **only from 2026-07-31 onward** — our own daily jobs.

Consequences for the proposal, using its own classification scheme:

| proposal asks for | actual state |
|---|---|
| historical odds files | FINAL_STATE_ONLY (ruled, frozen) |
| opening/closing timestamps, snapshot frequency, suspensions | ABSENT historically; PROSPECTIVE_ONLY |
| injury-to-move latency, book lead-lag, stale windows (MKT05–07 / M06–M08) | PROSPECTIVE_ONLY on our tape, or paid vendor with verified revision history |
| retrospective bankroll simulation from 2022 (MKT12 / M12 spirit) | impossible on owned data; the drafts' own "do not force a 2022 start" clause is the operative one |

So the market program's scarce asset is **calendar time on a real tape**. Every week of delay
in upgrading capture is a week of event studies we can never run. That reordering — capture
first, studies later — is the biggest practical difference between the drafts as written and
what I would execute.

## 2. What already exists (do not rebuild)

**Point-in-time capture, live since 2026-07-31** (D11_LIVE_INFORMATION_CAPTURE, PASSED):
daily jobs for odds (`odds_capture_daily.py`), player props (`props_capture_daily.py`,
2,471 rows), injuries (`injury_capture_daily.py`, 551 rows), news (`news_capture_daily.py`),
and referee assignments — with first-seen timestamps and change history. The proposal's
"information events" table (§4B / M-model) is ~70% live already; what's missing is the
structured before/after implication fields and the event-to-market linkage.

**Entity resolution, adopted TODAY under D022 (user-approved O16):** capture-time
`player_id` resolution against a cross-season identity index, raw strings retained,
single-tenant rosters with assignment provenance, unbindable Out/Doubtful designations now
fail closed (BLOCK), and a human-curated alias table with no fuzzy fallback (55/55 tests).
The proposal's player-identity requirements for market snapshots are already satisfied at
the capture layer.

**Model snapshots:** the forecast log was upgraded TODAY to a versioned SCHEMA/2 with a
both-versions reader; per-game execution scope adopted; `alternative_model_log` exists; the
reproducibility runner (I13) pins commits, seeds, and data hashes. The proposal's table D
(model snapshots) is substantially covered; gaps are fair-line/fair-probability fields,
which arrive only when the fundamental model starts emitting priceable outputs.

**Ops latency machinery:** the O-lane already measured obligation-discovery lag over 84
obligations / 21 games, lead-window latency, and per-game scope defects — the same
measurement discipline MKT07/M21 (execution realism) needs, pointed today at our own
pipeline rather than at sportsbooks.

**Governance the drafts re-specify from scratch — already built and battle-tested:** the
graph engine (append-only events, derived state, frozen-path guard, single-writer commits),
isolated worktrees with exclusive file ownership, model tiering (D015), constants-inline
dispatch (D020), preregistration + red-team + sealed-results blinding, multiplicity
budgeting per family, preserved disagreements, evidence-status vocabulary (LANDED ≠
VERIFIED), USER_REQUIRED gates. The drafts' §6 hypothesis discipline and §7/§8 promotion
rules map almost one-to-one onto RESEARCH_CONTRACT_V1 + GRAPH_POLICY. The market lane
inherits all of it by living in the same graph — that is the strongest argument for building
it as a lane rather than a separate project.

**UI/API pattern:** U10–U13 (versioned API schema, fixture-built UI shell, immutable history
views, staleness/monitoring surface) are PASSED product nodes. MKT14/M25 is an extension of
an existing pattern, not a new build.

**Vendor groundwork:** `wnba_odds_system/` + `wnba-odds-aggregator/` contain a prior
Odds-API integration, scraping strategies, and research docs (WNBA_Odds_Research_Report,
Scraping_Strategy, Setup_Guide). MKT15/M02's vendor evaluation starts from real prior
experience, including known rate limits — not from zero.

**Market-family scientific rulings that bind the new lane:** P2B (above), F14
(decision-time market comparison design, PASSED), and the P32 spec's preserved market-arm
disagreements. The market lane must consume these rulings, not relitigate them silently.

## 3. Reconciling the two draft versions

They are ~85% the same program. Differences that matter:

* The M-series (M00–M25) is more granular and has the better taxonomy (§1 A–F) and
  promotion rules; the MKT-series has the better four-system separation (fundamental /
  market-reaction / execution / decision) and the cleaner deliverable packet. I would adopt
  the **M-series node set** under the **MKT-series system architecture**, one lane id:
  `market_intelligence`, node prefix `M`.
* Both drafts' "first action: audit" (MKT00/M01) is **already half-answered** by this
  session and prior rulings — the audit node should verify and fill gaps, not rediscover.
* Both would create duplicates of existing nodes if executed verbatim: information-event
  capture (exists: D11 + today's O16 upgrades), UI shell (exists: U11/U13 pattern),
  reproducibility (exists: I13), execution-latency measurement discipline (exists: O-lane).
  The market lane should declare dependencies on those PASSED nodes instead.

## 4. What I would do, and how

Same engine, new lane. Every node gets a generated contract (write scope, hash-pinned
inputs, acceptance criteria, stop conditions), agents run in isolated worktrees under D015
tiering and D020 dispatch discipline, evidence stays append-only, and nothing self-certifies.

**Wave 1 — launch immediately, all parallel (no new money, no new authority beyond the
directive itself):**

1. `M00_MARKET_PROGRAM_CONTRACT` — freeze the taxonomy (arbitrage vs value vs middle, the
   four-system separation, evidence labels, promotion boundaries). Small, load-bearing,
   everything cites it.
2. `M01_MARKET_DATA_INVENTORY` — the audit, seeded with §1–§2 above as *claims to verify
   against bytes* (classify every source; produce the coverage matrix; rule formally on the
   earliest valid tape date).
3. `M03_CAPTURE_UPGRADE` — the urgent one. Measure current cadence against the drafts'
   requirement (T-24h…final + event-driven bursts); design the upgrade within current source
   rate limits; wire injury/news first-seen events (already captured) as **triggers** for
   burst polling around events. Anything needing paid quota returns as a USER_REQUIRED line
   item with exact cost.
4. `M02_BUILD_VS_BUY` — vendor matrix (The Odds API history tier, SportsDataIO, RotoWire,
   etc.), seeded from `wnba_odds_system` docs; ends in a recommendation + the specific user
   decision; **no purchase**.
5. `M04_COMPETITOR_ARCHIVE_DESIGN` — fixed-cutoff competitor-projection capture design;
   licensing questions surfaced explicitly (scraping RotoWire et al. is a user call, listed
   under §5 decisions).
6. `M05_LINKAGE` — deterministic event↔quote linkage keyed on first-seen timestamps
   (both tables already exist on our side of the join).
7. `M25_UI_FIXTURES` — market screen shell against fixtures, extending U11/U13.

**Wave 2 — unlocked by tape accrual, not by permission:** M06 injury event study, M07
lead-lag, M08 stale windows, M17 suspension/reopening, M19 prop microstructure — each gated
on a preregistered minimum of usable events on OUR tape (or vendor history if bought), with
interval-censoring treated honestly (daily snapshots cannot time a 4-minute move; the event
study must say so rather than pretend).

**Wave 3 — unlocked by the possession/player program's own milestones:** M13/M14
model-vs-market residuals (needs frozen point-in-time model distributions — arriving via
P33→P38), M09 true-arb scanner and M10/M16 coherence checks (can prototype on live quotes
earlier), M11 consensus model, then M21–M24 execution realism → capacity → shadow trading →
staking, in that order, each behind its predeclared gate.

**Hard lines carried over from the drafts and existing policy, unchanged:** no real wagers,
no purchases, no credentials, no automated bet submission — all USER_REQUIRED; no reading
sealed possession results; no reconstructed data presented as point-in-time; profitability
claims only on executable definitions; the possession critical path is never delayed
(market lane = separate lane, separate worktrees, separate write scopes — the same way
today's O16 adoption ran beside P32/P33 without touching them).

## 5. Decisions only the user can make (surfaced now, not mid-program)

1. **Issue the directive?** If yes, which text governs — I recommend the merged form in §3.
2. **Capture cadence budget:** event-driven burst polling may exhaust free-tier quota;
   the exact quota math comes back from M03 before anything is spent.
3. **Competitor-projection capture:** scraping stance and licensing comfort for RotoWire /
   RotoGrinders et al. (M04 proceeds design-only without it).
4. **Historical odds appetite:** if retrospective event studies matter to you this season,
   a paid vendor with verified revision history is the only path (M02 returns the matrix);
   otherwise the program is prospective-first by necessity and that is fine — it just means
   patience.

## 6. Bottom line

Roughly **60% of the proposed program's infrastructure already exists** — capture jobs,
identity resolution, versioned logging, latency measurement, governance, UI pattern, vendor
groundwork — and the fastest path to profit-relevant evidence is not more historical
analysis (there is nothing valid to analyze) but **upgrading the live tape now** and letting
the event studies accumulate power while the fundamental model finishes its own critical
path. The proposal's instincts about discipline (point-in-time integrity, execution realism,
promotion gates) are exactly the discipline this repository already enforces; the lane can
inherit it wholesale instead of rebuilding it.
