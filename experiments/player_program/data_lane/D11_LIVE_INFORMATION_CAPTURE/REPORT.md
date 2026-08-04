# D11_LIVE_INFORMATION_CAPTURE - report

**Lane:** data | **Type:** implementation | **Severity on failure:** B | **Role:** data and
cutoff-validity engineer

## Epistemic status

> PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future features cutoff-provable. Creates no historical evidence and repairs no historical gap.

## The one-sentence result

The capture mechanism exists, is tested, and enforces first-seen, full change history, no
backdating and lane-only writes -- and it is bound to **zero** live sources and has captured
**zero** real observations, because every candidate source lies outside this node's declared read
scope or does not exist at all.

That second half is not a shortfall worked around. It is the finding.

---

## 1. What was built

| file | what it is |
|---|---|
| `capture_schema.py` | the eight domains, one per contract criterion; declared fields and enumerations; the call-site blocklist that refuses realised target-game outcomes |
| `capture_ledger.py` | the append-only ledger: immutable first-seen, appended change history, five no-backdating rules, derived-and-replayable index, an independent `verify()`, strict-inequality cutoff admission |
| `CAPTURE_CONTRACT.md` | the specification, with the code named as governing where the two disagree |
| `build_source_binding.py` -> `SOURCE_BINDING.json` | per-domain declaration of why no source is bound, every verdict extracted programmatically from a frozen in-scope artifact with its sha256 |
| `selftest_capture.py` -> `SELFTEST_RECEIPT.json` | a **synthetic** corpus exercising all eight domains and every rejection path |
| `TESTS.py` | standalone suite; `main()` returns 1 on failure (pytest is not installed) |
| `build_findings.py` -> `FINDINGS.json` | the machine-readable findings, composed from the artifacts rather than typed |
| `ledger/` | the production ledger. **Empty**, and committed empty |
| `selftest/` | the synthetic ledger. Fictional teams, players, book and sources. Never evidence about anything |

Three times are kept apart and never conflated: `observed_at_utc` (when *this repository* saw it --
the only one that can admit at a cutoff), `published_at_utc` and `effective_at_utc` (source
assertions, which never admit). `cutoff_basis` is `observed_at` only for a source registered as
`observation_provable` and not flagged `retrospective`; otherwise it is `CUTOFF_UNPROVEN` and
`admissible_at()` will never return the record whatever its dates say. A field with no source
timestamp is `CUTOFF_UNPROVEN` -- no code path infers an observation time.

---

## 2. What was measured, and with what

Every figure below came from code run against the files named. Nothing is estimated.

| claim | value | how it was produced |
|---|---|---|
| all eight contract domains accepted | **8 of 8** exercised end to end; 8 criteria, one domain each | `python selftest_capture.py` -> `SELFTEST_RECEIPT.json .counts.domains_exercised`; `python TESTS.py` test *"domains: exactly the eight contract criteria, one domain each"* |
| synthetic corpus size | **13 records over 9 entities** -- 9 `first_seen`, 3 `change`, 1 `reaffirmation` | `SELFTEST_RECEIPT.json .counts` |
| first-seen never overwritten | **9 entities checked, 0** with more than one `first_seen` value | `SELFTEST_RECEIPT.json .first_seen_immutability`; independently `TESTS.py` *"verify: catches an overwritten first_seen_at_utc"* |
| change history preserved, not collapsed | the worked injury entity carries **3 records** -- `QUESTIONABLE -> OUT -> OUT` reaffirmed -- with `change_index` 0, 1, 1 and every prior payload still present | `SELFTEST_RECEIPT.json .change_history_example.trace` |
| append-only | **13 of 13 writes** prefix-preserving (bytes-before is a prefix of bytes-after) | `SELFTEST_RECEIPT.json .append_only` |
| a record is never backdated | **11 rejection cases, 11** raised the expected code, **0** modified the ledger | `SELFTEST_RECEIPT.json .rejections` / `.rejection_summary`; codes `FUTURE_OBSERVATION`, `BACKDATED_OBSERVATION`, `BACKDATED_ENTITY_OBSERVATION`, `RETROSPECTIVE_CLAIMS_EARLY_OBSERVATION`, `PUBLISHED_AFTER_OBSERVED` |
| derived index is a pure function of the ledger | `STATE_INDEX.json` and `WATERMARKS.json` both reproduced **byte-identically** after deletion and replay | `SELFTEST_RECEIPT.json .replay_determinism` |
| ledger internally consistent | `verify()` **ok=True, 0 violations over 13 records** | `SELFTEST_RECEIPT.json .integrity_verify` |
| cutoff admission is strict | **0** entities admissible at a cutoff *equal* to the first observation; **8** at T0+31min returning `QUESTIONABLE`; **8** at T0+120min returning `OUT` | `SELFTEST_RECEIPT.json .cutoff_admission` |
| unproven observation never admits | **1** `CUTOFF_UNPROVEN` record in the ledger; **0** admitted even at a 2030 cutoff | `SELFTEST_RECEIPT.json .cutoff_unproven_never_admitted` |
| test suite | **24/24**, exit code 0 | `python TESTS.py` |
| **live sources bound** | **0 of 8** | `python build_source_binding.py` -> `SOURCE_BINDING.json .n_bound` |
| **real observations captured** | **0 records, 0 bytes** in `ledger/observations.jsonl` | `ledger/MANIFEST.json .n_records`; `os.stat` on the file |
| no pregame minute-restriction source in scope | **5** matching lines over **284** files; **3** are this graph restating D11's own acceptance criterion, the other **2** are a 40-minute exposure validation cap in `build_projected_exposure.py` and its validation receipt. **Zero name a source** | `build_source_binding.grep_count` with pattern `minute[s]?[ _-]?(restriction/cap/limit)` over `experiments/player_program/`, this node's own directory excluded; all hits enumerated in `SOURCE_BINDING.json` |
| no coaching source in scope | **0** hits for a `data/*coach*` path over 284 files; the frozen packet independently records verdict **`ABSENT`** | `build_source_binding.grep_count` with pattern `data/[a-z0-9_]*coach`; `EVIDENCE_PACKET_V2.json .cutoff_valid_availability_table_CORRECTED` |
| no captured pregame lineup or starter feed | frozen packet verdict **`UNAVAILABLE`**, source *"no captured pregame feed"*; a text search returns **12** mentions, all program prose recording the absence or a derived *projected lineup strength* feature -- none a capture path | `EVIDENCE_PACKET_V2.json` availability table; `build_source_binding.grep_count`, hits enumerated in `SOURCE_BINDING.json` |
| frozen inputs unchanged | `EVIDENCE_PACKET_V2.json` `3a35ae73...30a32c` and `V2_STOP_CONDITION.json` `a4dd090b...92244d` both equal the values pinned in `orchestration/nodes/G00_LIVE_RECONCILIATION/RECONCILIATION.json` | `hashlib.sha256` in `build_source_binding.py`, compared against `RECONCILIATION.json .checks.frozen_hashes` |

### The acceptance criteria, one by one

1. **Covers injury designation changes, lineups, starters, minute restrictions, transactions,
   coaching changes, odds and attributable news** -- met **as mechanism only**. Eight domains,
   one per criterion, each with declared fields and enumerations, all eight driven end to end.
   `news` requires a non-empty `attributed_to` and a `claim_type`, so an unattributed headline is
   refused and a rumour is stored as a rumour, not as a fact. **No domain is bound to a live
   source.**
2. **First-seen and full change history preserved, never overwritten** -- met. `first_seen_at_utc`
   is set once and copied forward; changes and reaffirmations are appended, never merged; a
   reaffirmation is written precisely because *"we saw the same designation again at 16:00"* is
   what proves the state held at a 16:30 cutoff. `verify()` catches an overwritten first-seen, an
   in-place payload edit, a deleted intermediate record and a pushed-back `observed_at_utc`.
3. **A record is never backdated** -- met, by five rules at `append()` and re-derived independently
   by `verify()` from the bytes on disk.
4. **Writes only under its own lane directory** -- met. `assert_in_scope()` guards every write
   path; a ledger rooted elsewhere raises `SCOPE_VIOLATION` before a file is created; a test walks
   every file this node wrote and asserts each resolves inside the lane directory.

### One design decision worth naming

The payload-key blocklist refuses, in every domain and case-insensitively, `minutes`,
`game_minutes`, `is_overtime`, `possessions`, `pace`, `regulation_seconds_remaining`,
`non_competitive_conservative`, the score-differential columns and the `realised_` / `actual_` /
`final_` / `stint_` / `boxscore_` / `off_p` / `def_p` prefixes. This encodes findings **S1**
(`master_team.minutes` is an exact overtime indicator; `game_minutes` recoverable by dividing by
five) and **S8** (`is_overtime`, the score-differential columns and `non_competitive_conservative`
are realised target-game outcomes). It is enforced entirely at this call site; no shared gate was
edited.

It is a restriction on **what may be captured**. It adjudicates nothing, promotes nothing and does
not touch the cutoff-valid feature set.

---

## 3. What I could not establish

* **Whether the existing live captures actually preserve first-seen and change history.**
  `data/injury_capture/`, `data/news_capture/`, `data/odds_capture/` and `data/ref_assignments/`
  are outside this node's `allowed_read_paths` (`experiments/player_program/`). I did not open
  them. The only in-scope statement is `ROSTER_SOURCE_AUDIT_RECEIPT.json`'s q5 for
  `data/injury_capture/injury_log.csv` -- *corrections overwrite history: NO* -- which is **another
  node's measurement**, quoted with its sha256, not mine.
* **Current row counts, spans or schemas of any live capture.** Every such figure appearing in my
  outputs is quoted from a frozen in-scope receipt and labelled as someone else's measurement.
* **Whether any historical odds exist.** `V2_STOP_CONDITION.json` records, unresolved, that
  `tip_times.csv` is odds-derived and covers 2022-2026 while the packet says market odds are
  historically unavailable. `tip_times.csv` is outside my read scope; I did not open it.
* **Real-world observation latency** -- the gap between a designation changing and this repository
  seeing it. That becomes measurable only once a source is bound and has run. The ledger already
  records the two fields needed for it (`published_at_utc` against `observed_at_utc`).
* **Whether any captured field would help any model.** No fit, no score, no comparison. Nothing
  under `stage2b/SEALED_RESULTS/` was read.

---

## 4. Contradictions found

**C1 -- the frozen availability table's `coverage` column mixes two kinds of span.**
`EVIDENCE_PACKET_V2.json` records market odds as *"2026-07-31 .. 2026-08-06 only"*. Measured
against the machine clock at the time of writing (`2026-08-04T19:58:51Z`), the stated end is **2
days after the current date**, while the injury row in the same table ends `2026-08-04`, exactly
today. A line posted today for a game on 2026-08-06 is *observed* today. So one column is carrying
an **observation span** for the injury row and an **event-date span** for the odds row. A reader
who takes the odds row as an observation span credits the repository with having seen two days of
the future. Severity B. **Not resolved here -- the packet is frozen and was not edited.** This
node's schema separates `observed_at_utc` from `effective_at_utc` precisely so the conflation
cannot recur inside the capture.

**C2 -- the injury-capture span differs between two in-scope receipts.**
`ROSTER_SOURCE_AUDIT_RECEIPT.json` (generated `2026-08-03T21:26:32Z`) gives
`2026-07-30 .. 2026-08-01`, 551 rows. `EVIDENCE_PACKET_V2.json` gives `2026-07-30 .. 2026-08-04`.
Three days apart. This is consistent with a live capture that grew between the two measurements
and is **not** presented as a defect. It is recorded because neither figure can be cited as *the*
span without naming the moment it was measured -- the same failure mode as C1, one step removed.
Severity C. Not verifiable from inside this node's read scope.

**C3 -- the node's read scope cannot reach the sources the node is contracted to capture.**
`PROGRAM_GRAPH.json` gives D11 `allowed_read_paths = ["experiments/player_program/"]`. Every
candidate source named anywhere in the program record for the eight domains lives under the
repository's `data/` tree -- `data/injury_capture/`, `data/injury_history/`, `data/news_capture/`,
`data/odds_capture/`. **0 of 8 is reachable.** The mechanism can be built and tested, and was; but
no adapter can honestly be written against a file that was never read, so the node ships with zero
bindings and an empty production ledger. Severity B -- a contract defect, not a scientific one. An
agent may not broaden its own scope, so this is raised, not fixed.

---

## 5. Negative results, preserved

* **No source of pregame minute restrictions exists** anywhere in this node's read scope, and the
  frozen availability table does not list the field at all -- it has never been adjudicated, even
  as unavailable. Of the eight criteria this is the weakest-supported.
* **No coaching source exists.** The frozen packet's verdict is `ABSENT`; my own search agrees at
  0 hits. Note the packet records coaching as the **only** one of these candidates whose
  `prospective_only_validation` is `false` -- i.e. the only one that could in principle be
  reconstructed historically from a hand-maintained table. Reconstructing it is not this node's
  mandate.
* **No captured pregame lineup or starter feed exists.** The only lineup artifacts in the
  repository (`derive_lineups.py` -> `stints.parquet`, `starters.csv`) are **realised** and are an
  explicit must-not-reuse.
* **The production ledger is empty and is committed empty.** That is the honest state, and an
  empty ledger with a working mechanism is a more useful artifact than a populated one with an
  unverified adapter.
* **Capture forward from today can never retro-fit history.** Nothing built here creates evidence
  about any game already played. This restates, and does not soften, `prediction_contract_v5`'s
  section 7 finding that for 2021 through 2026-07-29 there is no Tier-A source that can assign a
  player to a team before her first box appearance.

---

## 6. Stop conditions

**None tripped.** The declared stop condition is a finding that would change the primary target,
the K0 structure, the inference structure, the candidate universe, the cutoff-valid feature set or
the leakage status. This node adjudicates no field, promotes no field, fits nothing and touches no
historical row. The payload blocklist restricts what may be *captured*; it neither widens nor
narrows the cutoff-valid feature set.

Three items are raised rather than resolved, and are in `FINDINGS.json .escalations`:

1. **C1** -- how the frozen availability table's `coverage` column should be read. It changes the
   reading of an availability verdict, not the underlying data. Goes to the possession lane.
2. **The `tip_times.csv` / odds tension**, already recorded and unresolved in
   `V2_STOP_CONDITION.json`. D11 confirms it is material -- it decides whether the odds domain has
   *any* pre-2026-07-31 evidence, and if so whether that evidence is a single retrospective pull
   (the S-TX regime, permanently `CUTOFF_UNPROVEN`) or something better. **Not measured here**;
   the file is outside my read scope.
3. **C3** -- D11's read scope against D11's mandate. Goes to the coordinator: either widen the read
   scope for a follow-up binding node, or record that D11 delivers mechanism only.

## 7. Frozen artifacts

None modified. No git command was run. `EVIDENCE_PACKET_V2.json` and `V2_STOP_CONDITION.json` were
read and hash-checked against the values pinned in `RECONCILIATION.json`; both match.

## 8. Reproducing this

```
cd experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE
python build_source_binding.py     # -> SOURCE_BINDING.json
python selftest_capture.py         # -> selftest/, ledger/, SELFTEST_RECEIPT.json
python TESTS.py                    # 24/24, exit 0
python build_findings.py           # -> FINDINGS.json
```

`selftest_capture.py` uses a deterministic injected clock, so the synthetic ledger's sha256
(`4c0a48677a11da9def7b2f5ec22aa5e4da0bcb5ccb4939c02b58828920f8bbf9`) reproduces exactly; `TESTS.py`
asserts that it does across two independent runs.
