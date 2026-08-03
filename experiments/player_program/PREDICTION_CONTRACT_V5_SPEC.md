# `prediction_contract_v5` — a tiered candidacy universe

**Status:** SPECIFIED (amended 2026-08-03 after supervisory review). Stage 1 implementation
authorised. **v4 is not edited, amended or regenerated.**
**Registered in:** `experiments/player_program/registry.jsonl`. The shared
`experiments/registry.jsonl` is untouched.
**Evidence label:** specification only. Nothing is fitted, predicted or scored. "Coverage" means
obligation completeness.

> **AMENDMENT — what changed and why.** The first draft treated prior-season franchise membership
> (S2) as a candidacy source strong enough to create an ordinary obligation. That was wrong.
> Prior-season affiliation is cutoff-valid evidence of **past** affiliation; it is **not proof of
> current-season roster membership**. A prior-season player may have been traded, waived, left
> unsigned, retired, suspended, or moved to another league, and rookies and new signings are
> absent from it entirely. This revision demotes S2, introduces the **Tier A / B / C** distinction,
> adds a genuine transaction source found by the bounded roster-source audit, and states the
> prohibition on using actual participation to build the pregame universe.

---

## 1. The defect, measured

`prediction_contract_v4`'s membership rule is
`prior_admitted_team_game_box_membership_including_dnp/1`: a candidate for `(team, game)` is a
player in that team's box score for one of the latest **five prior same-season** team games whose
availability bound is strictly earlier than the forecast cutoff. Candidacy is therefore established
**only** by already having been in that club's box score, this season.

Measured by `audit_candidacy_gap.py` against `master_player.parquet`:

| | rows | players | games |
|---|---|---|---|
| played player-team-games (`minutes > 0`) | 28,322 | | |
| **not an obligation under v4** | **977 (3.45%)** | 356 | 233 |

| cause | rows | share |
|---|---|---|
| **`season_opener`** — no prior same-season game exists, so every team's first game of every season yields zero candidates | **749** | 77% |
| **`mid_season_arrival`** (team-game index ≥ 5) — signing, hardship, waiver, trade | **176** | 18% |
| `early_season_partial_window` (index 1–4) | 52 | 5% |

Stable at 2.9–4.6% every season. The 51 rows in the Phase 0 audit were the subset visible where the
registered minutes universe overlapped the contract.

## 2. The bounded roster-source audit

Full receipt: `ROSTER_SOURCE_AUDIT_RECEIPT.json`. Every source in or already fetched by this
repository, graded on six questions.

| source | seasons | timestamps | as-of reconstructable | identity | corrections overwrite | **regime** |
|---|---|---|---|---|---|---|
| **in-season box membership** (S1) | 2021–2026 | per-game availability bound | **yes** | `player_id`, `team_id` | no | **A** |
| **captured pregame availability report** (S3) `data/injury_capture/` | **2026-07-30 →** | per-row `capture_utc` | **yes**, in span | names, resolvable | no — revisions preserved | **A within span / D-eligible** |
| **BBRef transaction wire** (S-TX) `data/injury_history/` | 2021–2026 | per-row **effective** date; **no** publication time | **no, not provably** | names, 80.3% resolve | **yes** | **B** |
| prior-season franchise affiliation (S2) | 2022–2026 | prior season's games | yes, but proves only *past* affiliation | ids | no | **B, weak** |
| `data/w1_truth/roster_asof.csv` | 2021–2026 | artifact-level only | **no** | ids | n/a | **unusable** |
| `data/reference/player_bios.csv` | 2021–2026 | — | — | ids, **no team column** | — | **unusable** |
| `data/news_capture/` | 2026-05-20 → | per-row published/capture | yes, but content is prose | — | no | **unusable without extraction** |
| official WNBA transaction log | — | — | — | — | — | **not present** |
| archived roster endpoints | — | — | — | — | — | **not present** (no roster endpoint is called anywhere) |
| prosportstransactions.com | — | — | — | — | — | **not accessible** (Cloudflare; bypass disallowed) |

### The find, and its exact limitation

`data/injury_history/injury_history.csv` — captured but never indexed for roster purposes — is a
genuine transaction wire: 8,340 rows, 2021–2026, including **1,455 signings, 795 waivers, 252
trades, 260 draft, 18 waiver claims, 111 suspensions**, each with a team and an effective date.

Its limitation is precise and disqualifying for Tier A. It was scraped in **one retrospective
pass** — the CSV was committed 2026-07-30 13:42 in `98271bb` — so the observation time for every
record, including 2021 ones, is 2026-07-30. The raw HTML that might have carried a fetch timestamp
is gitignored (`data/injury_history/raw/`) and absent. Basketball-Reference edits pages in place,
so corrections overwrite history and a re-fetch cannot be diffed.

`ROADMAP.md` already rules on exactly this class: *"the historical injury archive records what was
eventually known, not what was knowable at a historical cutoff. W1 backtests are regime-B only."*
The same test applied to affiliation gives the same answer. **Regime B → Tier B.**

## 3. Tiers

Candidacy and verified obligation status are **separate questions**. v5 answers them separately.

### Tier A — verified obligation

The player-team assignment is supported by information **provably available before the forecast
cutoff**: a timestamped official roster, a timestamped transaction, a captured availability report
carrying team affiliation, a prior current-season obligation with no later contrary transaction, or
any source whose publication *and* observation times are provable.

**Tier A is the only tier eligible for headline availability and coverage evaluation.**

Qualifying sources: **S1** (a prior game's box is observable at that game's availability bound,
strictly before the cutoff) and **S3** (per-row `capture_utc`), the latter only from 2026-07-30.

### Tier B — fallback candidate

Included through weaker but cutoff-safe evidence; **current roster membership is not verified**.
Qualifying sources: **S-TX** and **S2**.

Every Tier B row carries, without exception:

| field | meaning |
|---|---|
| `candidate_source` | which source(s) admitted her |
| `candidate_published_time` | when the evidence was published, or null if unknowable |
| `candidate_observed_time` | when this repository observed it |
| `candidate_evidence_time` | the bound actually used for admission |
| `team_assignment_source` | which source assigned the team |
| `team_assignment_confidence` | `verified` / `probable` / `weak` |
| `universe_tier` | `A` / `B` / `C` |
| `is_fallback` | true |
| `is_cold_start` | no prior appearance for this team this season |
| `exclusion_reason` | null unless excluded |

**Tier B is reported separately and is never mixed silently into Tier A headline metrics.** A
metric computed over A∪B must say so and must also be reported over A alone.

### Tier C — unverifiable or excluded

No defensible pre-cutoff evidence assigns the player to the team. **No obligation is manufactured.**
If she later appears, the row is preserved in the postgame coverage audit as a
**candidate-universe miss** — and that eventual appearance is never used to pretend she was
knowable beforehand.

## 4. Sources and precedence

A source is admitted only if its evidence time is **strictly earlier** than the row's
`forecast_cutoff`. Equality is a violation, not a pass.

| id | source | tier | rule | span |
|---|---|---|---|---|
| **S1** | in-season box membership | **A** | v4's rule, unchanged: box row in one of the latest 5 admitted prior same-season team games | all |
| **S3** | captured pregame availability report | **A** | listed for that team on a report whose `capture_utc` is strictly earlier than the cutoff | 2026-07-30 → |
| **S-TX** | transaction wire | **B** | an acquisition (`signing`, `trade`, `waiver_claim`, `draft`, `contract_conversion`) effective strictly before the cutoff, with no later release (`waiver`, `retirement`, `contract_suspension`) before it, **bounded** — see §5 | 2021–2026 |
| **S2** | prior-season franchise affiliation | **B, weak** | a box row for the same `team_id` in any strictly-earlier season, admitted only below `S2_HORIZON = 5` | 2022 → |
| **S4** | official roster / transaction feed with provable publication times | **A** | **RESERVED. DECLARED UNAVAILABLE.** No implementation may substitute another source for it | — |

**Precedence.** S1 ≻ S3 ≻ S-TX ≻ S2. A row admitted by any Tier A source is Tier A regardless of
what else names it. `candidate_source` records **every** source that named the row, so
corroboration is visible rather than collapsed.

**S2 is never sufficient alone for a normal obligation.** Its only permitted roles are: a fallback
candidate superset, a weak prior on likely affiliation, an explicitly weaker operational tier, and
an audited development universe. It is never described as a verified roster source.

## 5. The S-TX horizon, chosen against a measured trade-off

An acquisition creates affiliation that persists indefinitely unless a release is recorded — and
releases are incomplete (795 waivers against 1,455 signings; training-camp cuts frequently have no
record). An unbounded rule therefore keeps departed and never-signed players in the universe
forever. This is the same failure mode the amendment flags for S2, and it is **worse** for S-TX.

Measured, with releases honoured and S1 taking over once the player has appeared for that team this
season:

| horizon (team games since acquisition) | gap rows recovered | recall | non-appearing candidate-games added |
|---|---|---|---|
| **3** | **559** | **57.2%** | **747** |
| 5 | 567 | 58.0% | 1,011 |
| 10 | 568 | 58.1% | 1,621 |
| 20 | 576 | 59.0% | 2,904 |
| unbounded | 731 | 74.8% | **31,302** |

Unbounded buys 17.6 points of recall for **30,555** extra non-appearing candidate-games against a
v4 universe of 35,627 obligations — it would roughly double the universe with players who never
play. From 3 to 5 costs 264 candidates for 0.8 points; 5 to 10 costs 610 for 0.1.

**`S_TX_HORIZON = 3`**, registered. The table is registered with it so the choice is auditable
rather than asserted.

**"Did not appear" is not the same as "false candidate."** A rostered healthy scratch is a *correct*
candidate and a legitimate low-`p_active` obligation. The inflation figure bounds candidate growth;
it does not count errors. It is reported because **candidate quality cannot be judged by recall
alone** — which is exactly why S2's value was never established by counting how many opening-night
players it recovers.

## 6. The postgame prohibition

**Actual participation may not construct the forecast universe.**

The box score may be used to audit missed players, false candidate assignments, incorrect team
assignments and obligation coverage. It may **not** be used to create the pregame candidate set for
that same game. A player who appears unexpectedly is recorded as a **candidate-universe miss**, not
retroactively added.

Enforced structurally: the candidate generator takes the transaction wire, the report capture, and
prior-game box scores **strictly before the cutoff**, and never reads the target game's box. The
audit runs afterwards, in a separate module, over the generator's frozen output.

## 7. Eras

S3 exists only from 2026-07-30, so a single uniform coverage figure would misrepresent the record.

| era | span | Tier A sources | Tier B sources |
|---|---|---|---|
| `box_only` | 2021 → 2026-07-29 | S1 | S-TX, S2 |
| `report_assisted` | 2026-07-30 → | S1, S3 | S-TX, S2 |

Coverage is reported **per era**. A model whose training window spans the boundary must record
that it spans two candidacy regimes.

**The honest headline finding:** for 2021 through 2026-07-29 there is **no Tier A source** that can
assign a player to a team before her first box appearance for that team. Opening night and
mid-season arrivals are Tier B or Tier C in that era, and no amount of specification changes that.
Capturing an official roster or transaction feed **forward from today** is the only route to Tier A,
and it will never retro-fit history.

## 8. Transactions, teams, timestamps, cold start

* **Timestamping.** S3 uses `capture_utc`. S-TX uses the transaction's **effective date**, recorded
  as `candidate_published_time = null`, `candidate_observed_time = 2026-07-30` (the scrape), and
  `candidate_evidence_time = effective date` — so a reader can see exactly what was and was not
  provable. S1 uses the prior game's availability bound.
* **A traded player changes teams** when an admitted source names her for the new club. She remains
  a candidate for the old club while inside its S1 window, and **both obligations are owed** — at
  cutoff the contract cannot know she has gone. This is v4's dual-obligation behaviour, retained;
  `cbs_obligation_key.row_uid` names both rows distinctly and the old-club row carries
  `master_row_present = False`, which is absence of an event, not missing data.
* **Same-day and uncertain transactions.** Not admitted — strict inequality. A transaction that
  cannot be placed strictly before the cutoff creates no candidacy, and the resulting row is
  audited under §10.
* **Missing historical timestamps.** Never invented. The obligation is not created; the row appears
  in the exclusion audit as Tier C.
* **Cold start.** Candidacy and history are separate. An S-TX- or S3-established candidate
  typically has no in-season history at all — a valid obligation with an empty history, which is
  what the fallback ladder exists for. The contract supplies the counts; the **ladder belongs to
  the arm**, not the contract.

## 9. History accounting — `n_prior_games` is retired

**Defect P-D3.** `cbs_player_runner_v14` emits `n_prior_games` meaning `n_prior_candidate_games`
for `p_active` on fitted folds but `n_prior_appearances` for all four targets on the degenerate
2021 fold. One column, meaning conditioned on fold and target.

Three fields, each defined once and **never** conditioned on fold or target:

| field | definition |
|---|---|
| `n_prior_candidate_obligations` | obligations in the same `(player_id, season)` whose `forecast_cutoff` is **strictly earlier** than this row's. Counts obligations, not distinct games |
| `n_prior_appearances` | admitted prior rows in the same `(player_id, season)` with `appeared = True` |
| `n_prior_team_games` | admitted prior games of this row's `team_id` this season, regardless of player |

Every emitted forecast carries all three and records **which one it read**. `n_prior_games` is not
emitted under any circumstances; a consumer requesting it gets an error, not a guess.

## 10. Required universe diagnostics

Reported **by season and by source tier**, in `universe_diagnostics.json`:

* verified Tier A obligations
* Tier B fallback candidates
* Tier C exclusions
* **actual appearing players missed by the pregame universe** (candidate-universe misses)
* candidates who did not appear
* incorrect team assignments
* duplicated players across teams
* same-day transaction ambiguities
* season-opener gaps
* trade / signing / hardship gaps
* **coverage before and after each source tier**, so each tier's marginal contribution is visible

Plus, explicitly: **whether S2 and S-TX create false obligations for departed players.** Their
value is not established by recall alone.

A build whose diagnostics are absent or unreadable **fails**. A non-zero exclusion count is
expected; an *unknown* one is never permitted. **A build reporting zero exclusions has a bug.**

## 11. Validation

Ordered; each fails closed.

1. **Key identity** — `row_uid` unique and re-derivable from `(player_id, game_id, team_id)`.
2. **Cutoff safety** — every admitted evidence time strictly earlier than `forecast_cutoff`.
3. **Tier integrity** — every Tier A row names a Tier A source; no Tier B source ever produces
   Tier A; S4 never appears.
4. **Source attribution** — every obligation names ≥1 admitted source with its times.
5. **Era declaration** — S3 never admits before 2026-07-30.
6. **Superset property** — every v4 obligation is a v5 obligation. v5 may only *add*. Reported as
   `row_diff_vs_v4.json`.
7. **Postgame prohibition** — the generator's inputs are asserted not to include the target game's
   box score.
8. **History fields** — all three present and non-negative; `n_prior_appearances ≤
   n_prior_candidate_obligations`; `n_prior_games` absent.
9. **Diagnostics** — present, readable, complete per §10.

## 12. Two stages

**Stage 1 — contract and universe only (authorised).** Candidate-universe generator, source
precedence, Tier A/B/C classification, team assignment, cold-start, exclusions, history accounting,
validation receipts, coverage audits. **No fitting. No scoring.**

**Stage 2 — the unchanged v14 model (not yet authorised).** Only after Stage 1 validates: run the
existing v14 fitting logic **without modifying its model form**, generate the first real
out-of-fold artifact, inspect coverage and validation receipts **before** accuracy, then score it
as the baseline that was already written. **No hierarchical challenger** until the unchanged v14
baseline is established.

## 13. Preserved facts

Unchanged by this amendment: 977 played player-team-games absent under v4; 77% of them at season
openers; prior-season membership recovers only part of that set (43.3% of openers, 12.5% of
mid-season arrivals); and `bottomup_3pt_channel_v1` improved its own channel while worsening margin
through reduced home/away residual covariance — which closes **that implementation**, not P1, P2 or
P3 generally.
