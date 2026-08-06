# P34_PREREGISTRATION_RED_TEAM — REPORT (coordinator adjudication)

ADVERSARIAL REVIEW. Reviewers are independent of the preregistration author. A clean review
does not make an arm true; it makes it fittable.

Seven independent reviewers, one per contract dimension, mutually blind, none the P33
author. All seven: ACCEPT_WITH_REQUIRED_CHANGES with ALL_MATCH hash checks and clean
blindness attestations. The operational reviewer is a REPLACEMENT for one lost to a session
usage cap (GRAPH_POLICY §4 — not a new independent source); its predecessor's partial file
was superseded by the replacement's verified rerun of the same dimension.

## Verdict table

| dimension | verdict | A / B / C | stop raise |
|---|---|---|---|
| leakage | ACCEPT_W_R_C | 0 / 4 / 4 | no |
| offset dependence | ACCEPT_W_R_C | 2 / 3 / 6 | **yes** |
| K0 parity | ACCEPT_W_R_C | 1 / 3 / 4 | **yes** |
| fold estimability | ACCEPT_W_R_C | 0 / 6 / 4 | no |
| multiplicity | ACCEPT_W_R_C | 0 / 7 / 4 | no |
| target units | ACCEPT_W_R_C | 0 / 2 / 5 | no |
| operational | ACCEPT_W_R_C | 1 / 4 / 6 | no |

Headline: **zero Severity A leakage across all 26 arms** — every "strictly lagged" claim was
verified against bytes, no same-game surrogate reaches any prediction path, and the S8
lagged-use licences hold everywhere.

## The four Severity A findings and their rulings (D026)

**A-1 / A01 — WITHDRAWN.** The reviewer ran the frozen `offset_dependency_guard` bytes on
A01's complete preregistered design: blocked under SUBSTANTIVE (seven kinds) and under a
truthful RECALIBRATION declaration; the only passing invocation attests
`k0_carries_offset_slope=True`, which is false of A01's slope-fixed null. An arm fittable
only by lying to a frozen guard about its own null is not fittable. Withdrawal is rejection
for failing a predeclared integrity check (GRAPH_POLICY §5). The alternative — re-reading
the guard's S4 rule — would change frozen-gate enforcement semantics and is refused. The
question A01 carried (free recalibration slope vs slope-1) is recorded as **structurally
unanswerable under the frozen guard**; answering it requires a guard revision, which is a
USER gate.

**A-2 / A04 — WITHDRAWN.** No declared family exists under which its design passes the
frozen guard — not even a false attestation rescues it. Same basis as A01. Its
depth-adaptive-gain mechanism survives in guard-compatible form in A09; the A04/A09
collapse rule is moot.

**K1 / A11 — REPAIR AT P35.** Three clauses of one frozen record disagree about its null.
Frozen precedence already forces reading (1) — the arm's own formula ("null fixes rho == 1")
and the frozen P26 `hierarchical_pooling` kind — a deterministic consequence of accepted
rulings. P35 pins the null to the single blended column with free β, strikes the
two-free-mains gloss, and replaces the never-firing rho-interval kill with the decidable
per-element set. If the repair cannot be expressed exactly, A11 withdraws.

**OP-1 / A19 — WITHDRAWN BY ITS OWN PREREGISTERED CLAUSE.** Measured on the pinned bytes:
`end_reason` carries a single undifferentiated turnover level; the live-ball subset A19
needs is inexpressible, so its preregistered withdrawal-as-design-failure clause is already
triggered. The designed fail-closed path executed. (Convergent finding: leakage L5.) A20
survives the same check.

## Stop-condition adjudication

**NO HALT.** Both raises are answered by choosing closure paths that leave every frozen
structure untouched: the guard bytes stand, the per-arm K0_MATCHED map (D007) stands, the
five-fold D006 inference scaffold stands, the universe and cutoff-valid set and leakage
status stand. Arms yield to structures; structures never yield to arms.

## Arm count

26 preregistered → **3 withdrawn** (A01, A04, A19) → **23 fit-eligible**, of which A06
remains conditional on its schedule receipt and A14 remains promotion-ineligible
(single-active-fold) while gathering evidence. A11 fit-eligible subject to its P35 repair.

## Severity B disposition

All Severity B findings from all seven reviews are **mandatory items of the P35 task-card
freeze mandate** — P35 may not freeze a card that leaves any B open against its arm.
Notables: per-arm `declared_family` + truthful recalibration declarations for every guard
invocation; intercept structure defined per arm and null with an explicit
no-implementation-default-intercept invariant (the S4 recreation risk named by two
reviewers); written disposal of the quasi-Poisson freeze against the V2 retired-families
record it cites; the P26 K0-validator schema/call-site gap; the d_t league-mean window and
n_i contract-schedule clock pins; A16's opening-day NULL-row handling; A23 bundle_AI's
receipt-or-redefinition; A13's training-only centering pin; multiplicity denominators
recomputed after the withdrawals.

## Preserved disagreements

* A11's two null readings both stand on the record; the ruling pins (1) by precedence
  without erasing the contradiction.
* The quasi-Poisson self-freeze: leakage-inert (leakage), coherent-but-in-tension with the
  V2 retirement record (offset), parity-clean (K0). The tension is disposed in writing at
  P35, not averaged here.

## Chain of custody

Seven review files frozen as returned (see ARTIFACT_LEDGER); SPEC.json in this directory is
the machine-readable register of all findings plus the D026 rulings; the node validation
command passes against it.
