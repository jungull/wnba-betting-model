# S35_FREEZE_TASK_CARDS — REPORT

**Materialized by the RETIRING coordinator** from the agent's S35_REPORT_BODY.md. The agent
returned after this coordinator had already retired; this report and the ledger event exist so the
agent's findings reach the incoming coordinator, since a subagent's returned text lives nowhere
except the retiring coordinator's context.

## THE REGISTRY APPEND HAS NOT BEEN PERFORMED — IT IS THE INCOMING COORDINATOR'S FIRST ACTION

The agent prepared, simulated and proved the append but did not execute it, correctly. The
retiring coordinator has ALSO not executed it, deliberately: the registry is a frozen append-only
path with a single-writer rule, and performing it after handing off would risk two actors mutating
it. Everything needed is on disk:

- Pre-append baseline: **51 records, 223,775 bytes, sha256 `a0aff704…`**, per-line sha256 for all
  51 in `REGISTRY_BASELINE_VERIFICATION.json`. Re-hashed after all agent work: **unchanged**.
- Payload: **14 records, 37,974 bytes, sha256 `6462e150…`** — 1 preregistration_freeze + 11 arm
  records (`authorises_execution: true`, scoped to implementation only) + 1 withdrawal (SC07) +
  1 policy record carrying the downstream obligations.
- **Expected post-append sha256 `6b43f40a…`, 65 records**, recorded in `SPEC.json` so the incoming
  coordinator can prove the result in one command.
- **The payload is LF-terminated. Do NOT normalise the existing mixed line endings** (28 LF /
  23 CRLF) — normalising would rewrite existing records and break byte-identity.

## Two items the agent surfaced that must not be lost

1. **One verification claim did not fully reproduce, reported rather than buried.** The
   `projected_team_off_possessions` pin's `join_key_sha256` did not reproduce because the pin names
   the join columns but not the inter-column separator convention. **The column digest itself
   matched exactly**, and nothing in the slate reads the join-key digest — a documentation gap, not
   a wrong digest. Not a freeze blocker; carried as an S36 obligation to state the convention.
2. **A pre-existing registry anomaly, found and left untouched.** Existing record index 50 has no
   `schema`/`kind`/`experiment_id`: it appears to be the P37 A24 amendment *drafter register* file
   appended whole — contradicting that file's own "DRAFT ONLY, must never be appended" text —
   instead of its nested payload. The agent recorded it and did not edit it, which is correct
   (existing records may never be modified). **This needs a coordinator decision: it is a defect in
   an append-only history, so the remedy can only be a corrective appended record, never an edit.**

---
# S35_FREEZE_TASK_CARDS â€” the cycle-2 score challenger cards are frozen

**Node:** `S35_FREEZE_TASK_CARDS` Â· **Lane:** score Â· **Cycle:** 2 Â· **Role:** coordinator-role
**Program worktree (the only admissible root, stated explicitly):**
`C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program`

> FREEZE. The 17 challenger cards are immutable from this point. Implementation may begin
> against these exact bytes. Nothing here authorizes fitting, and nothing here ever authorizes
> adoption.

**What this node emitted (all inside `experiments\player_program\stage3_score\S35_FREEZE_TASK_CARDS\`):**

| file | sha256 | what it is |
|---|---|---|
| `SPEC.json` | `36b59c9b7d8878f10f210fb04f9b82e882417dbef47163f9c5007045639c1183` | the frozen card set |
| `REGISTRY_APPEND_PAYLOAD.jsonl` | `6462e150a5f3c80dbc0d7782a4f57dd1d3e4fc322b73a5f8ff963fd59f63f59c` | 14 records, for the coordinator to append |
| `REGISTRY_BASELINE_VERIFICATION.json` | â€” | proof the frozen registry was read record-by-record **before** any append |
| `VERIFICATION.json` | `see SPEC.json` | the receipt of the 11 reproduction checks below |
| `VERIFY_REPAIR.py`, `BUILD_FREEZE.py` | â€” | the two scripts, re-runnable in that order |

---

## 1. The freeze was earned, not assumed: every repair claim was re-run

The mandate was explicit that a freeze over an unverified repair is worse than a delay.
`VERIFY_REPAIR.py` re-runs the repair's own measurements at this node, against the program
worktree, and `BUILD_FREEZE.py` **refuses to emit `SPEC.json` at all** unless
`VERIFICATION.json` reports `all_pass`. Eleven checks, eleven PASS.

| # | claim | verdict | what actually reproduced |
|---|---|---|---|
| V1 | the 12 input byte pins in `SPEC_V2.inputs_verified_sha256` | **PASS** | all 12 re-hashed from disk, all match, none absent |
| V2 | 17/17 records schema-valid and cross-field clean | **PASS** | S33R's own `VALIDATE.py` **imported, not re-implemented**, run against the S32B schema (`d1f5e213â€¦`, re-hashed here); 0 failures; result dict **identical** to the declared `self_validation.results` |
| V3 | the same validator fails the frozen S33 bytes on exactly the two SC06 records | **PASS** | 17 records read, exactly 2 fail, both `SC06_SCHED_FATIGUE_DIFF::*`, both on literal `R5`, nothing else. B1 is mechanical, not asserted |
| V4 | the A3 stratum pin | **PASS** | re-derived from the pinned parquet on the 1,491-cluster row base: `max(n_H,n_A) â‰¤ 12` â†’ **472 pooled**, **75/76/74/81/92** per test season, **74** in 2021 â€” exactly the card. Rejected `min â‰¤ 12` reading â†’ **516**. SC02 `minâ‰¤5` â†’ **249**, SC03 `min<10` â†’ **399**. Non-empty in all five test seasons, so the arm-killing stratum stays checkable |
| V5 | the A2 identity-set extension | **PASS** | six members present (`pred_home`, `pred_away`, `pred_total`, `pred_margin`, `p_home`, `projected_team_off_possessions`); **all six column digests recomputed from the pinned parquets and matched byte for byte**, including value counts and NaN counts (1,465Ã—5 with 188 structural NaN on `p_home`; 2,990 values / 8 NaN on the possession column) |
| V6 | the A4 `R_SC08_FLOOR` receipt is in the binding records, not prose | **PASS** | present on `SC08::E3` in `verdict_label_policy` **and** `notes`, plus the non-gating agreement receipt on `SC01::E3` and `SC06::E3`; `mandatory: true`; the `BELOW-FLOOR` label string is on the SC08 record itself |
| V7 | B1's R5 fix on **both** SC06 records | **PASS** | `ERA2024` is the literal key in **both** sides' `structural_terms` and `declaration_routing` and in `invariants.lower_order_structural_terms`, on both records; R5 now passes on both |
| V8 | repair-specific checks N1â€“N8 | **PASS** | N1/N2/N3/N4/N5/N7/N8 re-derived independently here. **N6 was not re-derivable at this node** â€” see Â§5 |
| V9 | C2's power figure | **PASS** | 78 pooled clusters at \|F_Hâˆ’F_A\| â‰¥ 1, per test season 8/9/19/29/12 = 77 test-fold, **17 of them pre-2024** (8 in 2022 + 9 in 2023); the 18 pre-2024 / 60 post-2024 pooled split closes against 78 |
| V10 | the supersedes pin | **PASS** | `eca10740â€¦` matches the frozen S33 draft on disk |
| V11 | the registry pre-append baseline | **PASS** | 51 records, all parse, whole-file sha256 `a0aff704â€¦` |

**One claim that did not fully reproduce, reported rather than buried.** The
`projected_team_off_possessions` byte pin carries a `join_key_sha256` alongside its column
digest. The pin names `join_key_columns [game_id, team_id]` but does not state the
inter-column separator convention, and the join-key digest did **not** reproduce under this
node's reading of it. What *did* reproduce is the thing that matters: the **column digest**
(`9078790427e0câ€¦`, 2,990 values, 8 NaN) matched exactly, as did all five composite column
digests. This is a documentation gap in the pin's own stated rule, not evidence any digest is
wrong, and nothing in the slate reads the join-key digest. It is **not** a freeze blocker; it is
carried in `SPEC.json` as an S36 obligation to state the convention explicitly when R10 pin
recomputation runs.

**Verdict: the repair reproduces. Freezing proceeds.**

---

## 2. What is frozen

**17 element cards over 11 arms.** 12 candidate arms minus SC07 (withdrawn, frozen withdrawn).

The cards are carried **by hash reference**, exactly as cycle-1's P35 did: the card *is* the
`k0_matched[element_id]` object inside
`S33R_PREREGISTRATION_REPAIR/SPEC_V2.json` (`sha256 6402fc11b9118ef6978ca4feb4aec10e3b811209773b7ae5f03ba29962a8e945`),
and each `card_sha256` is that object's sha256 under the cycle-1 canonicalisation
`json.dumps(obj, sort_keys=True, separators=(',',':'))`. Nothing is transcribed, so nothing can
drift; every field of every S33R record is binding.

* `task_cards_sha256` = `aa759da738b6530d85f2400ab5bd1f281335abdc857f4a5818173783726d6508`
* `arm_blocks_sha256` = `a50fa064ca862d13dff16ac9c4643ba759b00f063fda25d9978072a60428df12`

**The family table** is frozen at 8 primary families:
`OPP_INTERACTION{SC01}` Â· `EARLY_SEASON{SC02,SC03}` Â· `HOME_COURT{SC04,SC05}` Â·
`SCHEDULE_FATIGUE{SC06}` Â· `DISPERSION{SC08}` Â· `BLOWOUT_DISCOUNT{SC09,SC12}` Â·
`FORM_DYNAMICS{SC10}` Â· `LEVEL_DRIFT{SC11}`, with four registered partitions (A primary,
B splits â†’ 10 families, C merges SC04â†”SC11, D merges SC10â†”SC12). A disputed element must survive
family-Holm under **every** registered partition; the stricter result governs.

**The program-alpha declaration, stated the way C1 asked for.**

* **0.40 â€” GOVERNING.** 8 primary families Ã— 0.05. Because a disputed element must survive Holm
  under *both* partitions, the realized decision rule is the **intersection**, so the governing
  additive bound is `min(0.40, 0.50) = 0.40`.
* **0.50 â€” DISCLOSED.** 10 maximal-partition families Ã— 0.05. Carried because disclosing the
  looser number while the stricter one governs is the safe direction of error.
* Partition D does not move either number: D is a **merge**, the bound uses the **maximum**
  family count over registered partitions, and a merge never raises that count.
* **No program-wide FWER claim is made anywhere in this cycle.** This is an additive expectation
  bound, not a guarantee.

**The shared universe** (1,491 game clusters / 2,982 team-game rows; 205/239/260/262/310/215 by
season; the 1,495-cluster full schedule always reported alongside; the D010 opening-day caveat
carried) was **re-derived at this node** from the pinned parquet and agrees exactly.

**The frozen inference configuration** â€” game-clustered bootstrap, `B_test = 10000`,
`B_train_refit = 2000`, five expanding folds, master seed `20260807` with the pinned stream
derivation, deterministic fits only, the four-part primary gate, family-Holm at 0.05, kills
uncorrected, within-estimand-only multi-survivor comparisons â€” is restated in `SPEC.json`
because implementation reads that block directly.

---

## 3. The downstream obligations, carried explicitly so they cannot be lost

Three of S34's four Severity C notes impose duties on *later* nodes rather than card edits. An
obligation that lives only in a report is an obligation that gets lost, so all of them are in the
binding freeze record **and** in a registry `policy` record.

| id | obligation | binds |
|---|---|---|
| **O1** | S36 must read `data/masters/master_team.parquet` **from the program worktree** and verify `sha256 ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528` before building anything. It must **never** read the live data-worktree copy (`e8e35b53â€¦`), which legitimately grows with the season and yields a 1,508-cluster universe with 232 clusters in 2026. On mismatch: **HALT** | S36 + every cycle-2 score node |
| **O2 (C4)** | S36 must emit and pin a **pre-build digest of the `game_id` set** before any design matrix is constructed, converting the `invariants.rows` deferral on all 17 records into a receipted invariant *before* any fit runs. Digest rule pinned; must also report n=1491, the per-season census, and the measured identity with the frozen store's `league_average_v1` id set | S36 |
| **O3 (C2)** | SC06's era-instability kill is **essentially unpowered** â€” 17 pooled-test clusters of pre-2024 support (8 in 2022 + 9 in 2023 of 77 test-fold clusters at \|F_Hâˆ’F_A\| â‰¥ 1). The power statement **must print adjacent to any verdict the kill produces**. Consequence spelled out: a kill that does not fire is **not** evidence the era interaction is stable â€” it is evidence this slate cannot tell. The kill itself is unchanged and still arm-killing | S40 + every report; emitted by S36/S38 |
| **O4 (C3)** | SC11's cross-estimand `\|Î”MAE(E2)\|` receipt is labelled **`NON_CITABLE_INTEGRITY_DIAGNOSTIC`**. It is computed on an estimand SC11 is not registered for and sits in no family. It may never be quoted as a result, enters no Holm family / pass tally / multi-survivor comparison, and may be used for exactly one thing: firing or not firing SC11's card-pinned integrity kill at 0.10 MAE points. The label travels with the number | emission, sealing, opening, and every citation |
| **O5** | `R_SC08_FLOOR` â€” mandatory sealed receipt; absence is a **card defect**. Gating on `SC08::E3`, non-gating agreement receipt on `SC01::E3` and `SC06::E3` | S36 emits, S40 applies the below-floor label rule |
| **O6** | `R-A1-EXCEPTIONS` â€” mandatory non-gating sensitivity receipt on every element; an arm-killing A1-SENSITIVITY kill on SC06. `master_team.game_date` is frozen at `CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS`, never at unconditional `CUTOFF_VALID` | S36 emits, S37 re-runs `M_A1_GAME_DATE_CUTOFF_V2` byte-for-byte |
| **O7** | the deletion-invariance receipt runs at **column grain** with the six adjudicated extension columns retained and every other column nulled on the current game's rows. The extension is a reviewable registration: if a reviewer rejects a member, the affected element set is mechanically readable from the `current_game_row_consumed` flags | S36, S37 |

C1 is a disclosure clarification and is discharged **in** this freeze â€” see the program-alpha
block above.

---

## 4. The registry append: prepared, proven, not performed

`experiments/player_program/arm_registry.jsonl` is a **frozen path under GRAPH_POLICY Â§3**.
Existing records may never be edited, reordered or rewritten. Appending is permitted only after a
passed preregistration gate â€” which S33R + S34 + this node's verification now satisfy. **This
node performed no append.** The coordinator is the single writer.

**Pre-append baseline, measured before anything else happened:**
51 records Â· 223,775 bytes Â· whole-file `sha256 a0aff704ba2c70f2edf756c5dc765f0ab63fb528ecc1585f6fc8cfbbcf33a7a6` Â·
file ends with a newline Â· all 51 parse as JSON Â· **mixed line endings (28 LF, 23 CRLF)**.
`REGISTRY_BASELINE_VERIFICATION.json` carries the **sha256 of every individual record line**,
its byte length, its eol style and its `(kind, experiment_id)`, so byte-identity is provable
afterwards rather than assumed.

**The payload: 14 records, 37,974 bytes, `sha256 6462e150a5f3c80dbc0d7782a4f57dd1d3e4fc322b73a5f8ff963fd59f63f59c`.**
Schema learned by reading the existing records, not invented â€” every record uses
`player_program_arm_registry/1` with existing field names (`kind`, `experiment_id`, `arm_id`,
`applies_to`, `registered_at`, `registered_before_execution`, `authorises_execution`, `status`,
`node`, `spec_path`, `extra`, `ruling`, `basis`, `resurrection_bar`, `policy`, `policy_id`,
`provenance`).

| # | kind | experiment_id | `authorises_execution` |
|---|---|---|---|
| 0 | `preregistration_freeze` | `stage3_score_s35_task_card_freeze/1` | **true** |
| 1â€“11 | `arm` Ã— 11 | `stage3_score_cycle2__SC01â€¦SC12` | **true** |
| 12 | `withdrawal` | `â€¦SC07_REF_CREW_TOTALS__withdrawn` | **false** |
| 13 | `policy` | `â€¦s34_severity_c_downstream_obligations/1` | **false** |

Each `arm` record carries its `arm_block_sha256`, the `card_sha256` of every one of its element
cards, JSON pointers into `SPEC_V2.json`, its frozen formula, its frozen kill list and the
obligations touching it. `authorises_execution: true` is scoped in the record itself:
*implementation at S36 against these exact card hashes; **not** fitting; **never** adoption.*
The withdrawal and policy records authorize no execution and say so.

Following the cycle-1 precedent (registry record 40), every record carries
`provenance.registered_at_is_proposed` â€” the coordinator may replace `registered_at` with the
actual append time; every other field is final as proposed.

**The append was simulated in memory and verified.** Concatenating the payload to the existing
bytes yields `sha256 6b43f40a86cefc0961a91c2730df921f843db0b0fdc58445cd151b2d874ba0d4` and 65
records, and **all 51 existing lines re-hash byte-identical**. `SPEC.json` carries that expected
post-append hash so the coordinator can confirm in one command that the payload went in verbatim
*and* that not one byte of the frozen records moved. The payload is LF-terminated, matching the
most recent 16 records including cycle-1's own P35 block; the coordinator must **not** normalise
the existing CRLF lines, since that would rewrite frozen records.

**One anomaly found in the existing registry, reported and not touched.** Record index 50 carries
no `schema`, `kind` or `experiment_id`. It is the P37 A24 amendment **drafter register** file
(`A24_AMENDMENT_PAYLOAD.json`) appended whole, rather than the single amendment payload nested
inside its own `registry_append.payloads` block â€” so the appended line contradicts its own
"DRAFT ONLY â€¦ must never be appended" text and breaks the shape every other record holds. This
node did **nothing** to it: the record is frozen, the S35 append is placed strictly after it, and
the finding is recorded in `REGISTRY_BASELINE_VERIFICATION.json` so the coordinator can decide
whether a correcting erratum record is warranted.

---

## 5. What freezing does and does not authorize â€” stated plainly

**It authorizes IMPLEMENTATION (S36) against these exact bytes.** The 17 element cards and 11 arm
blocks identified by the sha256 pins above, read out of `SPEC_V2.json` at
`6402fc11b9118ef6978ca4feb4aec10e3b811209773b7ae5f03ba29962a8e945`. An implementation that does
not reproduce those hashes is not implementing this preregistration. That covers feature-matrix
construction, K0_MATCHED construction, the receipted diagnostics each card names, and emission of
the mandatory receipts.

**It does NOT authorize fitting.** Fitting requires a **passed S37 implementation audit**. Until
S37 passes, no arm and no K0 may be fitted and no performance number may be computed.

**It NEVER authorizes adoption.** Adoption of any fitted score model for operational or
wager-shaped use is the **S42_ADOPTION_DECISION USER gate**. No node in this lane can grant it,
and nothing downstream of S36 changes that.

**It does not authorize edits.** The cards are immutable. Any defect found downstream is handled
by a **new** registry-appended erratum or amendment record naming the defective field â€” never by
editing these bytes. That is exactly how cycle 1 handled its A24 card defect.

---

## 6. Limits of this node, stated rather than glossed

* **N6 was not re-derived here.** The check "no D043 market-bar numeral appears anywhere in the
  card set" cannot be re-run without reading the bar values, which S30 Â§4 forbids this author
  from quoting. It is carried as S33R's own check and is re-checkable only by a node already
  holding the values.
* **R6/R7/R8/R9 and the full R10 pin recomputation** remain audit-time rules assigned to S36/S37,
  exactly as S33R recorded. R10 was discharged **here** for all six identity-extension column
  pins.
* **`pipeline_id` remains asserted-not-demonstrated** â€” the frozen `comparison_gate`'s own
  documented open gap, inherited rather than introduced.
* **The Severity C notes are a transcription.** S34 wrote no artifact; the four C notes reached
  the repository only through the coordinator's transcription of the reviewer's returned text.
  This node dispositions them as recovered and carries their obligations, but it cannot verify
  the transcription against a session transcript it cannot read. If the S34 session text is ever
  recoverable, Â§3's obligations should be re-checked against the reviewer's actual words.
* **The stop condition is not tripped.** This node changes nothing: estimands, K0 structure,
  inference scaffold, universe, family table, program-alpha arithmetic and leakage status all
  stand exactly as S33R left them. The two boundary items S33R recorded â€” the `game_date`
  promotion and the schedule-identity extension â€” are carried forward unchanged and unenlarged.
* **This node does not mark its own work accepted.**

**Prohibitions honoured.** No fit. No performance number computed or read. Nothing under
`stage2b/SEALED_RESULTS` or `stage3_score/SEALED_RESULTS` was read, listed or globbed. No frozen
artifact modified â€” `SPEC_V2.json`, the S33 draft, the S30 contract and `arm_registry.jsonl` were
all opened read-only, and the registry was **not** appended to by this node. `git` was not run.
All writes are inside `experiments\player_program\stage3_score\S35_FREEZE_TASK_CARDS\`. Every
measurement ran against the program worktree.
