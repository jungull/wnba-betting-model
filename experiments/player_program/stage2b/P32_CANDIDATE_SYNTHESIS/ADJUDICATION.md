# P32_CANDIDATE_SYNTHESIS — coordinator adjudication

Epistemic status: COORDINATOR ADJUDICATION over a SYNTHESIS node. Nothing here is an empirical
result; nothing has been fitted. This document records how the two independent adversarial
reviews were resolved into the amended SPEC.

## Chain of custody

| artifact | sha256 | frozen |
|---|---|---|
| SPEC.json (raw synthesis, pre-review) | `f71fc4451e6f68b458229139ef733b57c0c40696a46e9e63b2a16cf99abdb757` | before reviewer dispatch |
| REPORT.md (synthesis record, never amended) | `175a17f168fbb377109fb37d8430e4ecade4484cd0e3a1915176e3ed3b70e3f5` | before reviewer dispatch |
| REVIEW_IDENTIFIABILITY_K0.md | `db3e9038146c38e2d4ce270ed8fe0ee3ea185a35a65a258db62b0204f93d5e60` | as returned, before adjudication |
| REVIEW_CUTOFF_FOLD_DEDUP.md | `54292af376e92b638399671ec28b605673c410ef68a13c9cc98107ee0078a123` | as returned, before adjudication |
| SPEC.json (amended, authoritative for P33) | `1dc25981ed14be0ef59c994a47a99970d790b644d8cdce354c617f9198c2138c` | after 14/14 amendments |
| AMENDMENT_LOG.md (per-edict record) | `41e20920e6bdd4af34a20790e4f5a7712380da261a5677ef9e08d3d5348a5f53` | with amended SPEC |

This wave was a REPLACEMENT for a dispatch lost at session logout (no output existed; replacement
labelled per GRAPH_POLICY §4, so source counts are not inflated).

## Verdicts

Both reviewers: **ACCEPT_WITH_REQUIRED_CHANGES**, blindness attested, all input hashes rederived
MATCH by both. The two lenses returned complementary findings with **no contradictory rulings**.
Review B independently re-verified the deduplication as honest and complete: 26 + 5 = 31 exactly
covering the union, all four duplicate rejections true duplicates against source bytes, no
surviving duplicate, no unlagged use of a LAGGED_USE_ONLY field, no same-game surrogate in any
prediction path.

## The Severity A ruling (D021)

Review B, F-1: A06's phase/index denominator (scheduled season length) has **no cutoff-valid
source anywhere in EVIDENCE_PACKET_V3** — its cited adjudication covers only the per-game date,
and an archive-derived denominator is a function of realized playoff length and capture
truncation, i.e. post-cutoff information. The reviewer explicitly posed the halt question.

**Ruling: NO HALT.** The packet's cutoff-valid feature set is not changed by this finding; A06
cited a field the packet never adjudicated, an arm-level definitional defect. A06 is
**INADMISSIBLE_UNTIL_RECEIPTED** with two repair paths named in SPEC: a preseason-published
schedule artifact receipted under P23 discipline, or redefinition from past-only schedule facts.
Receipt acquisition is parallel data-lane work.

## Option calls resolved (D021)

* A04 kernel basis **struck** (narrower option); preserved in the R3/D1a record. No null invented.
* A03/A07 get a named cross-family near-affinity collapse rule mirroring the A04/A09 precedent.
* Franchise-continuity (PHO/PHX) receipt precondition extended **uniformly** to all nine
  boundary-spanning arms rather than recording a confinement reason.
* R5 rationale amended (fatigue-after-OT recorded as unproposed-but-legitimate); rejection
  outcome, category and diagnostic preservation unchanged.

## Preserved disagreement

R5's category label: Review A reads "downstream-mismatch-exploitation-only" as stretched for an
audit arm already outside the promotion universe; Review B keeps the label with the amended
rationale. Both readings stand; the outcome is identical under either.

## Amendment execution

14/14 edicts APPLIED, zero blocked (AMENDMENT_LOG.md maps every edit to its finding). One count
discrepancy recorded honestly: edict 1 said three A08 occurrences; the bytes contained five; all
five corrected. Post-amendment validation: SPEC parses, 20 families / 26 arms / 5 rejections
unchanged, arm ids unique.

## The inference-spec finding

The frozen inference specification was **located and pinned** (EVIDENCE_PACKET_V3 `inference`
block; lineage D006 → possession_features.chronological_folds → PHASE0A_RESOLUTION.md §3 →
EVIDENCE_PACKET_V2 `inference_specification`; I10 utilities excluded by their own non-adoption
header). It fixes folds, clustering, resampling, row weighting and the estimand, but **does not
fix the GLM link or the centered-offset treatment scale**. No convention was invented:
**INFERENCE_SPEC_GAP** stands in SPEC.json as a named P33 obligation.

## What P33 inherits

1. INFERENCE_SPEC_GAP: fix link + centered-offset scale from the receipted estimator convention
   before any fit.
2. A06 INADMISSIBLE_UNTIL_RECEIPTED; A02 INADMISSIBLE_UNTIL_SHOWN (receipts obligations).
3. Seven enumeration obligations (A03, A06, A08, A09, A10, A11, A16): finite elements fixed at
   preregistration, each charged to its family budget; "small" is not a specification.
4. A14 single-active-fold inference licensing and decidable kill conditions.
5. A03/A07 and A04/A09 collapse-rule execution under P25/S7.
6. A23 source-consistent bundle pairing recommendation (no cross-producted variants no source
   proposed).
7. D1–D9 preserved disagreements; preregistration may not silently harmonize any of them.
