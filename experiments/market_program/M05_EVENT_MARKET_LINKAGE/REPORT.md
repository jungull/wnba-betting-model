# M05_EVENT_MARKET_LINKAGE - report

**Node:** M05_EVENT_MARKET_LINKAGE | **Lane:** market_intelligence |
**Type:** implementation | **Severity on failure:** A | **Date:** 2026-08-06

## 1. Epistemic status (verbatim from the node prompt)

INFRASTRUCTURE, methodologically load-bearing (severity A): the linkage defines which quote movements may ever be attributed to which information events. A wrong or optimistic join silently fabricates reaction-time evidence downstream, which is exactly what D023 amendment 4 exists to prevent. On the amendment-3 immediate critical path. The design draft was already in flight when this node was created; it lands under this node's directory.

## 2. Frozen inputs, verified by hash before use

Command: `Get-FileHash <file> -Algorithm SHA256` (PowerShell 5.1), run from the working root.

| artifact | expected | measured | match |
|---|---|---|---|
| `M00_MARKET_PROGRAM_CONTRACT/MARKET_PROGRAM_CONTRACT.md` | `1152dcd3...265de` | `1152DCD3BF74000F700844BC8BFC0DF25DE61A067F59534A714AC4F2F20265DE` | yes |
| `M00_MARKET_PROGRAM_CONTRACT/TAXONOMY.json` | `c83e25e7...40a12c` | `C83E25E783A4EE8642A26DD416362E46C2C34196FF8F8354977C28B72940A12C` | yes |
| `W1_DRAFTS/EVENT_LINKAGE_AND_METHODOLOGY.md` | `5d91f6d3...13854d` (contract section 0.4) | `5D91F6D36C15B14FA57EF070A544DC4CA2DF876F4B217C0FAFA667EE1D13854D` | yes |

## 3. What was delivered

All inside `experiments/market_program/M05_EVENT_MARKET_LINKAGE/`:

| file | role |
|---|---|
| `linkage.py` | the linkage layer: poll-log intervals, event construction, quote series/changes, windows, isolation, suspensions, the ten reason codes, B.1/B.2 bound calculus, B.3 sharpness enforcement, amendment-4 claim objects, deterministic `link()` |
| `fixtures.py` | synthetic fixtures whose true event-to-quote assignment is known by construction (all timestamps synthetic year-2030; all entities fictional) |
| `TESTS.py` | 22-test validation suite; exit 0 iff all pass |
| `real_tape_probe.py` | read-only probe of the live capture tape; emits `PROBE_RESULTS.json` |
| `PROBE_RESULTS.json` | machine-readable probe output (DIAGNOSTIC channel) |
| `DESIGN_BASELINE.md` | hash-pinned adoption of the W1 draft + eight reconciliation deltas (DB-1..DB-8) |

Design landing: the draft itself is frozen by hash inside the M00 contract
(section 0.4). Copying its bytes here would duplicate a contract-frozen
artifact, so it "lands" as the hash-pinned adoption record
`DESIGN_BASELINE.md` - the reconciliation the acceptance criterion asks
for, without duplication. If the verifier reads the criterion as demanding
a byte copy, that is a one-command action for the coordinator; I did not
take it unilaterally.

Acceptance-criteria mapping:

1. **Deterministic, first-seen keyed on BOTH sides, no fuzzy time matching**
   - events key on our `capture_utc`, quotes on our `snapshot_utc`; both
   must be instants of the actual poll log or `LinkageError` is raised
   (TESTS T18); `link()` is a pure function, byte-identical across runs and
   input orderings (T02, `result_hash` equality).
2. **Every linked pair carries the censoring interval from capture
   cadence** - intervals are `(t_prev, t_seen]` from the actual poll log,
   never nominal cadence (T18: an 11-hour actual gap yields an 11-hour
   interval where a nominal-hourly assumption would fabricate 1 h); no
   fabricated point time exists anywhere in the record schema.
3. **Entity resolution reuses the adopted capture-layer identity index; no
   fuzzy fallback** - the O14 `_norm_name` normalization is used verbatim
   (cited to `ops_lane/O14_OPS_ENTITY_RESOLUTION/fix_entity_resolution.py`),
   the O14 alias-table format is consumed directly (the probe loads
   `data/entity_resolution/alias_table.json`, schema
   `ops_lane/O14/alias_table/1`, 0 aliases - empty by design), and the only
   resolution rule is normalized-exact against a frozen, hashed map (T10).
4. **Unlinkable events fail closed and are reported** - retained in
   `unlinkable_events` / `unlinkable_quote_rows` with reason
   `ENTITY_UNRESOLVED`, counted in the reason distribution (T10).
5. **Validated on synthetic fixtures with truth known by construction** -
   fixtures.py; 21 synthetic tests pass (see section 4).
6. **Design draft reconciled, not duplicated** - `DESIGN_BASELINE.md`.

## 4. Measurements - validation suite

Command: `python experiments/market_program/M05_EVENT_MARKET_LINKAGE/TESTS.py`

Result: `{"suite": "M05_EVENT_MARKET_LINKAGE/TESTS.py", "n_pass": 22,
"n_fail": 0, "n_skip": 0}` (T22 is the read-only real-tape smoke; it SKIPs
cleanly where the live worktree is absent, so the validator's run may show
21 pass + 1 skip on another machine - still exit 0).

Selected verified facts (each asserted against a truth value fixed before
the code ran):

- Exact B.1/B.2 arithmetic: for a 5-min two-sided grid with a sourced
  L_max = 30 s and measured eps_max = 2 s, the fixture's reaction bound is
  exactly [566 s, 1234 s] with grid G = 634 s (T01); for an 11-hour
  overnight event interval the bound is [0 s, 43234 s] with G = 43234 s
  and `poll_interval_event` = 39600 s (T06). Both intervals carry the full
  amendment-4 field set.
- All ten exclusion reason codes of baseline A.7 are reachable and
  exercised (T19): ENTITY_UNRESOLVED, AMBIGUOUS_PRE, CONFOUNDED@h,
  SUSPENDED_ACROSS_EVENT, UNRESOLVED_AT_GRID, POLL_GAP_EXCEEDS_HORIZON,
  IN_PLAY_ONLY, TRUNCATED_AT_COMMENCE, TIER_INSUFFICIENT, CLOCK_UNBOUNDED.
- Sharpness prohibition: point estimates finer than G raise
  `SharpnessViolation`; comparisons below the combined grid return
  `INDISTINGUISHABLE_AT_GRID`; with an UNBOUNDED vendor no point estimate
  is admissible at all (T14, T17).
- A run without a clock-skew measurement produces zero TRUSTED records and
  zero claims - the CLOCK_UNBOUNDED taint is structural, not advisory
  (T15), and `widen_interval` refuses UNMEASURED skew outright.
- Vendor-asserted stamps (`last_update`) are carried in an advisory field
  and appear in no claim quantity (T20); the fixture plants them 7 s off
  every poll instant so leakage would be detectable.

## 5. Measurements - the real ~hourly tape, honestly

Command: `python experiments/market_program/M05_EVENT_MARKET_LINKAGE/real_tape_probe.py C:/Users/jgallagher/wnba-betting-model 20000`
(read-only; output in `PROBE_RESULTS.json`, channel label **DIAGNOSTIC**).

Sample: first 20,000 of 27,070 `capture_log.csv` rows (all game-level
markets), all 1,408 injury rows, poll logs from the actual capture record
(93 odds polls - the 93 `live_*.json` filenames reconcile 1:1 with the 93
distinct `snapshot_utc` stamps in the CSV; 96 injury polls from distinct
`capture_utc`, consistent with the 96 files under `injury_capture/raw/`).
26 games, 1,612 series, 282 injury state-transition events, 6,340 linkage
records. ER map frozen and hashed before linking (`er_map_hash`
`46f6a9a73d7ac70458bfa6a247f454dd5502896e6244e2100335970081e563e4`).

**Poll grid (measured from the poll logs, not asserted):** median
inter-poll gap 3,600 s on both streams; odds gaps range 3,509-64,799 s;
injury gaps 1-64,799 s (the sub-minute gaps are the 2026-07-30 startup
burst); 7 gaps > 6 h on each stream (overnights plus the 2026-08-02
daytime outage).

**Headline finding 1 - the tape is CLOCK_UNBOUNDED end to end.** No
per-run NTP/clock-skew measurement exists anywhere in the capture logs I
could find (odds, injury, news, props directories). Under contract
section 6.3 every row of the current tape is tainted CLOCK_UNBOUNDED;
consequently the probe yields **0 TRUSTED records out of 6,340** and **0
reaction-time claim objects**. The vendor additionally has no sourced
latency bound (UNBOUNDED - family F9 exists to source one), so even with
skew measured, every claim would be UNSUPPORTABLE for fine-grained
statements. This is the honest state: the current tape cannot support a
single admissible reaction-time claim, and the linkage refuses to
fabricate one.

**Headline finding 2 - what UNRESOLVED_AT_GRID looks like at ~hourly.**
Horizon-window statuses (DIAGNOSTIC - pure poll-grid arithmetic on 6,340
records; percentages of records):

| window | OK | POLL_GAP_EXCEEDS_HORIZON | UNRESOLVED_AT_GRID | TRUNCATED_AT_COMMENCE |
|---|---|---|---|---|
| H+1  | 0.0  | 82.1 | 6.2  | 11.6 |
| H+2  | 0.0  | 81.1 | 6.2  | 12.6 |
| H+5  | 0.0  | 69.7 | 14.6 | 15.8 |
| H+10 | 14.6 | 65.5 | 0.0  | 19.9 |
| H+15 | 14.6 | 65.5 | 0.0  | 19.9 |
| H+30 | 14.6 | 64.4 | 0.0  | 21.0 |
| H+60 | 32.5 | 32.2 | 9.3  | 25.9 |

Reading this honestly:

- The draft predicted "H+1 through H+30 will be UNRESOLVED_AT_GRID almost
  always" at hourly cadence. The mechanism is confirmed but the dominant
  code is **POLL_GAP_EXCEEDS_HORIZON**, not UNRESOLVED_AT_GRID: on this
  tape the EVENT side is as coarse as the quote side, so most sub-hour
  windows die because the event's own censoring interval (~3,600 s or
  wider) exceeds the horizon before the quote grid is even consulted
  (DB-3 makes the two codes disjoint). Under the draft's combined reading
  of rule A.3-2 they are the same verdict - "vacuous below the grid".
- Even **H+60 resolves for only 32.5%** of records, and 25.9% of records
  sit close enough to commence (or after the last pregame poll) that the
  window truncates.
- The nonzero OK rates at H+10..H+30 (14.6%) are **not** evidence of
  sub-hourly capability: they trace to the 2026-07-30 startup burst, where
  five injury polls landed within minutes and event intervals were
  1-250 s wide. Steady-state hourly operation produces the
  H+60-and-nothing-else picture, degraded further by seconds of poller
  jitter: a 3,601 s event interval already kills H+60 (fixture T04
  demonstrates the knife-edge).
- 1,278 of the sampled quote rows (6.4%) were at-or-after commence and
  were structurally dropped at series construction (IN_PLAY_ONLY) - the
  P2B section-7 defect made impossible rather than policed.

This table is the standing, quantified argument for the amendment-3
high-frequency capture: at the current grid, event-to-quote attribution
at any horizon finer than an hour is essentially nonexistent, and the
hourly horizon itself survives for barely a third of linkable events.

## 6. Contradictions found

1. **Internal to the frozen draft (A.2):** the quote-series key includes
   `line` while "line moved" is listed as a change kind of a series - both
   cannot hold. Resolved as DB-1 (line is state, not key, for game-level
   markets), frozen in config. Reported here per standing rule 1 rather
   than silently reconciled.
2. **Acceptance-criterion wording vs contract freeze:** "the design draft
   ... lands under this node's directory" would, read literally as a byte
   copy, duplicate an artifact the contract froze by hash at its W1_DRAFTS
   path. I resolved by adoption-record (`DESIGN_BASELINE.md`, hash-pinned)
   and flag the tension for the verifier.
3. No contradiction between the contract, TAXONOMY.json, and their claimed
   hashes; no contradiction between the P2B-derived facts cited in the
   draft's preamble and the capture surfaces I read (headers and poll logs
   reconcile: 93 = 93 odds polls, 96 ~ 96 injury artifacts).

## 7. What I could NOT establish, and why

- **Any reaction-time claim from the real tape.** Zero admissible claims
  exist (section 5, finding 1). Per amendment 4 such claims are
  UNSUPPORTABLE until (a) a per-run clock-skew measurement exists and
  (b) a sourced vendor latency bound exists. Any timing-flavored number in
  section 5 is either a measured property of OUR OWN poll instants or is
  in the DIAGNOSTIC channel; none is a claim about market reaction.
- **Player-level (props) linkage against the real tape.** The adopted
  capture-layer identity machinery is reused (normalization, alias table,
  fail-closed), but the tape-side player identity index that O14 builds
  from the possession masters was not reconstructed here - doing so would
  require bulk-reading possession-lane data files, outside this node's
  sample-only read envelope. Props linkage is validated synthetically
  (fixtures with known truth) and the probe is game-level only (DB-2).
- **Completeness of the injury poll log.** The injury stream's poll log is
  reconstructed from distinct `capture_utc` values; a poll that ran but
  wrote nothing would be invisible, which would WIDEN true censoring
  intervals relative to what a complete poll log would give. The 96
  distinct stamps match the 96 files in `injury_capture/raw/`, which is
  consistent with completeness but does not prove it (a failed poll may
  leave no raw file either). Intervals derived from this log are therefore
  upper-bound-honest (never narrower than truth), which is the safe
  direction for censoring.
- **Vendor timestamp semantics.** `last_update` (props/odds vendor stamps)
  remains `unknown_unverified` per contract section 6.3; nothing here
  upgrades it. It is carried in the advisory field only.

## 8. Stop conditions

None tripped. No purchase, wager, credential, scraping/licensing risk, or
sealed-results read occurred or was needed; `stage2b/SEALED_RESULTS` was
not touched. Reaction-time claims that could not carry both amendment-4
terms were reported UNSUPPORTABLE (structurally: zero were emitted from
the tape). No use of the T2 final-state odds archive was made at all - the
probe and tests touch only the live T0 capture streams and synthetic
fixtures, so no M00-Ux enumeration entry was consumed and no caveat text
is owed.

## 9. Write-scope statement

Files written: only inside
`experiments/market_program/M05_EVENT_MARKET_LINKAGE/`. The live worktree
was read-only (filenames, headers, capped row samples); no git commands
were run; no frozen artifact was modified.
