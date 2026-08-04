# D11 live-information capture — contract

**Epistemic status.** PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future
features cutoff-provable. Creates no historical evidence and repairs no historical gap.

This document specifies the capture. `REPORT.md` says what was measured and what was not. Where
this document and the code disagree, **the code governs** — `capture_schema.py`, `capture_ledger.py`
and `TESTS.py` are the enforceable statement of everything below.

---

## 1. What is captured

Eight domains, one per acceptance criterion of the node contract. Nothing else is accepted; an
unknown domain raises.

| domain | contract criterion | entity identity (`key_fields`) |
|---|---|---|
| `injury_designation` | injury designation changes | `season`, `team`, `player` |
| `lineup` | lineups | `game_key`, `team` |
| `starter` | starters | `game_key`, `team`, `player` |
| `minute_restriction` | minute restrictions | `season`, `team`, `player` |
| `transaction` | transactions | `transaction_key` |
| `coaching_change` | coaching changes | `season`, `team` |
| `odds` | odds | `game_key`, `book`, `market` |
| `news` | attributable news | `source_item_id` |

`news` requires a non-empty `attributed_to` **and** a `claim_type` drawn from
`REPORT / OFFICIAL_STATEMENT / RUMOUR / SPECULATION / OPINION`. An unattributed item is refused, and
a rumour is stored as a rumour rather than as a fact. This is what makes the domain *attributable*
news.

Each domain declares its required fields, its optional fields and its enumerations. A field that is
not declared is a schema violation, not a silently accepted extra column.

## 2. Three different times, never conflated

| field | meaning | may it admit at a cutoff? |
|---|---|---|
| `observed_at_utc` | when **this repository** saw the fact | **yes**, and only this |
| `published_at_utc` | when the source says it published | no — a source assertion |
| `effective_at_utc` | when the fact takes or took effect | no — a source assertion |
| `ingest_at_utc` | when the record was written to the ledger | no — bookkeeping |

`cutoff_basis` is `observed_at` only when the source is registered with
`observation_provable: true` **and** the record is not flagged `retrospective`. Otherwise it is
`CUTOFF_UNPROVEN` and `admissible_at()` will never return the record, whatever its dates say.

This encodes the program's existing S-TX ruling. A wire with real per-row effective dates covering
2021–2026, obtained in a single retrospective scrape, proves nothing about what was knowable at a
2021 cutoff. Under this contract such a record enters as `retrospective=True`,
`observed_at_utc = ingest_at_utc`, `effective_at_utc = 2021-05-14T00:00:00Z`,
`cutoff_basis = CUTOFF_UNPROVEN` — the true effective date is preserved, and the ledger still
refuses to let it admit.

**A field with no source timestamp is `CUTOFF_UNPROVEN`.** There is no path in the code that
infers an observation time.

## 3. First-seen and change history

* The entity's `first_seen_at_utc` is set from the first observation and **copied unchanged** onto
  every later record for that entity. No function in the module can alter it.
* A later observation is **appended**, never merged into the previous record:
  * `change_kind = first_seen` — the entity's first record, `change_index = 0`;
  * `change_kind = change` — the payload digest differs, `change_index` increments,
    `prev_payload_digest` and `revision_of` point at the record it supersedes;
  * `change_kind = reaffirmation` — the payload digest is identical, `change_index` unchanged. The
    record is still written, because "we saw the same designation again at 16:00" is exactly the
    evidence that proves the state held at a 16:30 cutoff.
* `observations.jsonl` is opened in append mode only. `STATE_INDEX.json` and `WATERMARKS.json` are
  **derived** and are reproduced byte-identically by replaying the ledger.

## 4. A record is never backdated

`append()` refuses, with the named code, and writes nothing:

| code | rule |
|---|---|
| `FUTURE_OBSERVATION` | `observed_at_utc` may not be after the write moment |
| `BACKDATED_OBSERVATION` | `observed_at_utc` may not precede the source's recorded watermark |
| `BACKDATED_ENTITY_OBSERVATION` | `observed_at_utc` may not precede the entity's `first_seen_at_utc` (catches the cross-source case) |
| `RETROSPECTIVE_CLAIMS_EARLY_OBSERVATION` | a `retrospective` record must set `observed_at_utc` equal to its write moment |
| `PUBLISHED_AFTER_OBSERVED` | you cannot observe a thing before it is published |

`effective_at_utc` is deliberately unconstrained in direction: a posted line and a scheduled
transaction legitimately take effect in the future, a wire record legitimately took effect in the
past. It is a source assertion and never admits.

`verify()` re-derives all of the above from the bytes on disk, so a hand-edited ledger is caught
rather than trusted. It detects an overwritten `first_seen_at_utc`, an in-place payload edit, a
deleted intermediate record, a pushed-back `observed_at_utc`, a non-contiguous `ingest_seq` and a
`record_id` that does not rederive.

## 5. Realised outcomes are refused at the call site

A capture record is a **pregame** observation. The payload-key blocklist refuses, in every domain:

* exact keys — `minutes`, `game_minutes`, `duration`, `is_overtime`, `overtime`,
  `n_overtime_periods`, `regulation_seconds_remaining`, `possessions`, `pace`,
  `non_competitive_conservative`, `possession_kind`, `lineup_valid_ten`, `n_off_oncourt`,
  `n_def_oncourt`, `is_zero_duration`, `is_technical_derived`, `final_score`, `turnovers`, and
  others — see `capture_schema.BLOCKED_PAYLOAD_KEYS_EXACT`;
* prefixes — `realised_`, `realized_`, `actual_`, `final_`, `score_diff`, `abs_score_diff`,
  `stint_`, `boxscore_`, `box_`, `postgame_`, `off_p`, `def_p`.

Matching is case-insensitive. The list encodes findings **S1** (`master_team.minutes` is an exact
overtime indicator; `game_minutes` is recoverable by dividing by five) and **S8** (`is_overtime`,
the score-differential columns and `non_competitive_conservative` are realised target-game
outcomes). No shared gate is edited; enforcement is entirely at this call site, as the standing
rules require.

This is a **prohibition on what may be captured**, not a claim about the cutoff-valid feature set.
Nothing here promotes, demotes or adjudicates any feature.

## 6. Write scope

`capture_ledger.assert_in_scope()` resolves every path and refuses anything outside
`experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/`. Constructing a ledger rooted
elsewhere raises `SCOPE_VIOLATION` before any file is created.

## 7. Binding a real source — the obligation on whoever does it

No source is bound. `SOURCE_BINDING.json` records, per domain, why not and what would bind it. A
future binding must:

1. register the source with an honest `observation_provable` flag — true only when **this
   repository** performs the fetch and stamps the time;
2. supply an adapter that maps the source's records onto the domain payload, dropping nothing
   silently and inventing no timestamp;
3. set `observed_at_utc` from the fetch, never from a date inside the content;
4. set `retrospective=True` for any bulk historical pull, which permanently marks it
   `CUTOFF_UNPROVEN`;
5. re-run `TESTS.py` and `selftest_capture.py`, and run `verify()` over the production ledger.

Binding a domain makes its records *capturable*. It does not make any field eligible for a model,
and it does not make any field cutoff-valid for a historical row. **Availability is not
eligibility, and eligibility is not admission.** Nothing captured after today can ever be evidence
about a game played before today.
