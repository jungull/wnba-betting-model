# S34 Severity C findings — RECOVERED TEXT

**Why this file exists.** The S33R repair author correctly identified, as its single biggest
remaining risk, that S34's four Severity C notes existed nowhere in the repository: S34 wrote no
artifact (it was a read-only review returning text), and the coordinator's ledger event compressed
the C notes to a bare count while recording the A and B findings in full. That was a
coordinator record-keeping failure, not an author omission. The four notes are recovered here
verbatim-in-substance from the reviewer's returned text so S35 can freeze against the complete
finding set rather than an incomplete one.

**Provenance discipline.** These are the reviewer's own words and figures, transcribed by the
coordinator from the S34 return. They are NOT re-derived here; each carries the reviewer's
measurement as stated. Where a disposition requires a number, the disposition must re-measure it
rather than trusting this transcription.

---

## C1 — program-alpha arithmetic: conservative disclosure, not an error

> Program-alpha arithmetic checks: maximal partition = {SC01, SC02, SC03, {SC04,SC11}, SC05, SC06,
> SC08, SC09, SC10, SC12} = 10; 8 × 0.05 = 0.40, 10 × 0.05 = 0.50. But under the frozen "must
> survive Holm under **both** partitions" rule the realized decision rule is the intersection, so
> the governing bound is min(0.40, 0.50) = 0.40. Carrying 0.50 is conservative disclosure, not an
> error.

**Coordinator disposition:** ACCEPT AS-IS. Carrying the looser number in disclosure while the
stricter one governs is the safe direction of error. S35 should state both and name 0.40 as
governing, so no future reader mistakes 0.50 for the operative bound.

## C2 — SC06's era-instability kill is essentially unpowered (honestly carded)

> SC06's era-instability kill has ~17 pooled-test clusters of pre-2024 support (8 in 2022 + 9 in
> 2023 of the 77 test-fold clusters at |F_diff| ≥ 1); essentially unpowered, honestly carded.

**Coordinator disposition:** ACCEPT WITH THE POWER STATEMENT CARRIED FORWARD. The kill stays, and
its own unpowered-ness must be printed next to any verdict it produces, so a non-firing kill is
never read as evidence the era interaction is stable. This is a reporting obligation on S40, not a
card change.

## C3 — SC11's E2 integrity receipt computes a ΔMAE on an unregistered estimand

> SC11's E2 integrity receipt produces a ΔMAE on an estimand the arm is not registered for and that
> sits in no family; declared non-gating — note it so it can never be cited.

**Coordinator disposition:** BIND THE NON-CITABILITY EXPLICITLY. A number that exists in the sealed
outputs but belongs to no family and no registration is precisely the kind of quantity that gets
quoted later as if it were a result. SPEC_V2 / S35 must label it `NON_CITABLE_INTEGRITY_DIAGNOSTIC`
so the label travels with the number.

## C4 — `invariants.rows` deferred to S36 on all 17 records

> `invariants.rows` deferred to S36 on all 17 records (J11); I confirmed the interim pin holds
> (`set(league_average_v1.game_id) == universe` → True). Take J11's own invitation and demand a
> pre-build digest of the game_id set.

**Coordinator disposition:** ADOPT THE REVIEWER'S SUGGESTION. S36 must emit a pre-build digest of
the `game_id` set and pin it, converting a deferred invariant into a receipted one before any fit
runs. Added as an S36 obligation.

---

## Consequence for S35

S35 may freeze only against the complete finding set: the 4 Severity A and 8 Severity B closed in
`S34_DISPOSITION.md`, **plus** these four C dispositions. Three of the four (C2, C3, C4) impose
obligations on downstream nodes rather than card edits; C1 is a disclosure clarification.
