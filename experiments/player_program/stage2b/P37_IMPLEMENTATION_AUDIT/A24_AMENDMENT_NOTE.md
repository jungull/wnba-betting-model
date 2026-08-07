# A24_AMENDMENT_NOTE — line-by-line explanation of A24_AMENDMENT_PAYLOAD.json

**Status: DRAFT, for coordinator review only.** This node (A24 amendment drafter) does not write
`arm_registry.jsonl`. The payload in `A24_AMENDMENT_PAYLOAD.json` is offered for the coordinator
to append verbatim, exactly as `stage2b/P35_FREEZE_TASK_CARDS/SPEC.json`'s own `registry_append`
block was appended at P35 integration. Authority for drafting this amendment: D039 (coordinator
ratification of P37, 2026-08-06), which fixed the A24 disposition to option (a) — "an adjudicated
fallback for the franchise-debut rows, frozen before P38 by a registry-appended amendment."

---

## Why an amendment is needed

`stage2b/P37_IMPLEMENTATION_AUDIT/AUDIT_ARMS_A14_A26.md` finding **A3-B3** (severity B) measured
that A24's frozen card is defective: `p26_k0_record.fold_local_fallback.rule` reads `"none needed
(cross-season prior game covers openers)"`, but three true franchise debuts exist on the archive
(named in A14's own frozen P33 record: `1611661331` first season 2025, `1611661327` and
`1611661332` first season 2026). For each debuting team's own debut game, `rest(t,g)` — "days
since max prior contract game date of t" — has no prior date to measure from, so it is
structurally undefined, not covered by any cross-season lookback. Because A24's design is the
symmetric mean of both teams' rest values, the undefined value propagates to **both** rows of
each debut game (the debuting team's row and its opponent's row), for a minimum of 6 rows
(3 games × 2 rows), including the fold-4/5 TEST rows for the two 2026 debuts. `build_design`
correctly raises `A24ConstructionFailure` rather than invent a substitution — the code matches the
card; the card is what's wrong. Left unfixed, A24 — the preregistered LAG OPERATOR POSITIVE
CONTROL — would raise at P38 fit time, which the auditor and the coordinator (REPORT.md §4) both
treat as unacceptable: a positive-control failure at fit time would contaminate the reading of
every other lagged arm's result, so it must be disposed **before** P38, in writing, not patched
silently inside the P38 executor.

The coordinator's ratified choice is **option (a)**: adjudicate a fallback value for the
franchise-debut rows (rather than option (b), a row/fold-level withdrawal of those rows). This
note explains the payload that implements option (a).

---

## Line-by-line

**`node` / `artifact` / `role` / `authority_note`** — standard P37-family register header (same
shape as `SPEC.json`'s own top matter), stating plainly that this is a draft register, not a write
to the frozen registry, and naming the coordinator as sole writer — mirrors the exact sentence
from P35's `registry_append.protocol` ("the SINGLE WRITER of the append is the COORDINATOR").

**`authorizing_decision`** — quotes D039 verbatim from `REPORT.md` line 3, so the payload's
authority chain is traceable to the actual ratification text, not to this drafter's paraphrase.

**`source_finding`** — the full text of finding A3-B3, with the exact file and the file's sha256
as carried in `P37 SPEC.json`'s `chain_of_custody.audit_files` entry for
`AUDIT_ARMS_A14_A26.md` (`35BBFE0739...D6AF1CD`), so anyone re-measuring the finding file can
confirm they're reading the byte-identical source the amendment rests on.

**`defective_card_reference`** — points at the frozen P35 card's exact defective field
(`p26_k0_record.fold_local_fallback`) with its literal (wrong) text, plus the P35 `SPEC.json`
sha256. **This hash was independently re-measured by this node** (`Get-FileHash -Algorithm
SHA256` on the live file) and confirmed to equal `68EF22F4FCA15A2E8D91EEEB9B84B86F86E8E9E7C
AAB5E23E6A9B950385B4D32` — the same value both the P37 compiler's `chain_of_custody` block and
this task's instructions cite, so the card text quoted here is provably the frozen text, not a
transcription. The A24 model string is carried unchanged beneath it so the reader can see the
fallback slots into an otherwise-untouched frozen model.

**`franchise_debut_facts_source`** — the P33 `SPEC.json` sentence that names all three debuting
teams and seasons (P35's own A14 card only spells out the 2025 team by number; the full
three-team list with seasons lives in P33, `support_measured_by_this_node`, sha256
`066B2A046021DB119A75E2C847C325F6F4E40BB6E418BC7B31C8D072D347D093`, cross-checked against P37's
own `input_pins_cross_checked.P33_SPEC_sha256`). This is what makes the rule's row scope concrete
and auditable rather than a description of "franchise debuts" in the abstract.

**`registry_append.protocol`** — copies the exact sentence pattern from P35's own
`registry_append.protocol` (same "this node's write scope excludes arm_registry.jsonl … the
SINGLE WRITER of the append is the COORDINATOR" language), with a freshly measured baseline: **50
records**, sha256 `9337F964DBD5491C5F433D71117C8F13BB9D1D43681C9220A3A356F42A684609`, measured by
this node against the live `experiments/player_program/arm_registry.jsonl` on 2026-08-06 (41
pre-P35 lines + the 9 P35 `registry_append` payloads = 50, consistent with P35's own recorded
baseline of 41). The coordinator re-verifies this count/hash immediately before appending, exactly
as the P35 protocol requires.

**`registry_append.payloads[0]`** — the one JSON line meant for append:

- `schema` — `"player_program_arm_registry/1"`, identical to every existing registry line; this
  amendment is not a new schema.
- `kind` — `"fallback_adjudication"`: distinguishes this record from `withdrawal`,
  `conditional_not_fit`, `active_set_rule_registration`, and `preregistration_freeze`, the four
  kinds already in the registry. A fallback adjudication is none of those — it neither withdraws
  A24 nor registers a fold-active-set rule; it fixes a previously-missing data-construction rule.
- `experiment_id` / `applies_to` — names the amendment and pins it to `A24_rest_level_symmetric`
  unambiguously, following the `<arm>__<qualifier>` naming already used by P35's own
  `S7_TIER_SUPPORT_v1__A03` etc. entries.
- `decision` — `"D039_P37_ADJUDICATION"`, the ledger pattern this amendment traces to (parallel to
  every existing payload's `"D026_P34_ADJUDICATION"` tag).
- `disposition` — states plainly this is option (a), quotes where the two options were framed,
  and restates the auditor's carried constraint (before P38, by amendment, not a silent patch).
- `basis` — the one-paragraph causal chain: card says "none needed," A14's frozen facts prove
  three real debuts exist, therefore rest(t,g) is undefined on those teams' debut rows, therefore
  both rows of each debut game inherit an undefined symmetric mean; code is exonerated explicitly.
- `rule` — the fallback itself, in full:
  - **What triggers it**: team `t` has zero prior contract-schedule games before game `g` (a
    franchise debut for `t`). This is a fact about schedule membership, checkable by counting
    rows, not an estimate.
  - **What it does**: define `rest(t,g) := cap` (10) for that one (team, game) pair only — the
    debuting team is scored as maximally rested. This is the same value the model's own `min(...,
    10)` cap already produces for every well-rested team, so no new numeric range is introduced.
  - **What it does NOT do**: it does not touch `rest(.,.)` for any row where a prior contract game
    exists, and it does not change the frozen formula `x = (rest(t,g) + rest(opp(g,t),g))/2` —
    that formula is applied unchanged, now over a total (fully defined) `rest` function.
  - **Row scope, made concrete**: exactly 3 debut games × 2 rows/game = 6 rows, matching the
    auditor's measured "≥ 6 rows, including fold-4/5 TEST rows" — the 2026 debuts (`1611661327`,
    `1611661332`) land in later folds, which is why TEST rows are among the 6.
- `precedent_cited` — points out this is not new machinery: A23's `bundle_OM` already freezes
  "assign cap value (fully rested), deterministic, no active-set rule" for its own opener case.
  A24's fallback reuses that exact convention rather than inventing a fourth rest-fallback pattern
  in the fleet, keeping the amendment minimal and precedented.
- `preregistration_decidable` / `..._note` — states and justifies why this rule is
  preregistration-decidable: it is a pure function of which teams have played a prior
  contract-schedule game, a fact fixed by the schedule itself, independent of any fitted
  parameter, fold split, or result. It is being decided now, before P38 unsealing, exactly as
  every other frozen fallback in the P35 cards was.
- `identical_in_arm_and_null` / `..._note` — states and justifies symmetry: the fallback operates
  at the shared row-construction layer both K0_MATCHED members draw from (per A24's own frozen
  `k0_matched_frozen.null`, "same machinery; treatment adds ONLY x"); it is not an arm-only patch,
  so A24's `term_removal` null comparison is not disturbed.
- `kill_conditions_unaffected` — confirms `kill_conditions_frozen` and the LAG OPERATOR POSITIVE
  CONTROL role are carried verbatim; this amendment adds no new kill path and removes none.
- `candidate_universe_unchanged` — ties back to P37 REPORT.md §1's six-dimension no-halt analysis:
  no row, cluster, or fold is added or dropped; the 6 rows were always in the frozen universe, and
  this amendment only fixes one feature's previously-undefined value on them. This is what keeps
  the amendment inside GRAPH_POLICY's "arm-level closure" lane rather than becoming a candidate-
  universe change.
- `provenance` — every hash and path a re-auditor needs to re-derive this amendment from bytes:
  the finding file and its hash, the P35 card and its hash, the P35 task-cards hash (the narrower
  hash P35 itself certifies changes under), and the P33 hash the debut facts came from.
- `registered_before_execution` / `..._note` — states plainly that A24 has not yet been fit (still
  `FIT_READY`, blocked only by this defect per P37 REPORT.md §4) and that this amendment lands
  before that fit, satisfying both the auditor's carried constraint and D039.

---

## What this amendment deliberately does not do

- It does not touch `arms/A24/feature_construction.py` or `arm_a24.py` — those modules are
  card-exact; the fix is to the **card**, not the code, and the amendment defines the corrected
  card text the P38 executor must consume, not a code change.
- It does not adopt option (b) (row/fold withdrawal) — the coordinator's D039 ratification fixed
  option (a) specifically, preserving all 6 rows in the fit (consistent with A24's role as the
  positive control: dropping the very rows that stress the machinery would weaken, not strengthen,
  the positive-control reading).
- It does not touch any other arm's card, the fold policy, or any Severity B mandate items from
  P37 §6 — this is a single, narrowly scoped amendment to one arm's `fold_local_fallback` field.
- It is not itself the registry write. The coordinator remains the single writer; this drafter's
  role ends at handing over a payload the coordinator can validate and append unmodified.
